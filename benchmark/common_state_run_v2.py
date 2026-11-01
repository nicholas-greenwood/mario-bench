"""Preregister, execute and independently replay a common World 1-1 cohort."""
from __future__ import annotations
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import fcntl
import io
import json
import math
import multiprocessing
import os
import platform
import importlib.metadata
from pathlib import Path
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image
from benchmark.client import Client, canonical, digest
from benchmark.common_state_runtime_v2 import StateCompactSession as CommonSession, ACTIONS
from benchmark.costs import costs_from_events
from benchmark.run import append, read_events, write_json, load_key, safe_name
from benchmark.scoring import score_episode, aggregate_results, validated_progress_x
from prototype.emulator import MarioGame

ROOT=Path(__file__).resolve().parents[1]
STATE_PILOT=['perplexity/pplx-decider-v1.2','inception/mercury-decide','nace-ai/drex-max','liquid/d1-ultra']
IMAGE_PILOT=['baseten/mammoth-1','perplexity/pplx-decider-v1.2','inception/mercury-decide']
SOURCES=['benchmark/common_state_run_v2.py','benchmark/common_state_runtime_v2.py','benchmark/common_state_compact_v2.py','benchmark/common_profiles/state-compact-v2.json','benchmark/common_policy.py','benchmark/client.py','benchmark/costs.py','benchmark/scoring.py','benchmark/profiles/state_v1.py','prototype/emulator.py','prototype/decisions.py','prototype/control.py','requirements.lock.txt']


def require(condition,message):
    if not condition:raise RuntimeError(message)


def rgb_png(game):
    stream=io.BytesIO();Image.fromarray(game.frame_rgb()).save(stream,format='PNG');return stream.getvalue()


def screen_hash(game):return hashlib.sha256(game.frame_rgb().tobytes()).hexdigest()


def plain(value):return json.loads(canonical(value))


def actual_rom_sha256():
    from gym_super_mario_bros._roms import smb1_rom_path
    return hashlib.sha256(Path(smb1_rom_path()).read_bytes()).hexdigest()


def locked_sources():return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


def roster():
    models=json.loads((ROOT/'benchmark/models.json').read_text())['models']
    require(len(models)==22,'State v2 freezes all22 registered model/provider pairs')
    return models,[],[]


def track_model(model,track):
    result=deepcopy(model)
    if track=='image':
        result['provider']=result.get('image_provider',result['provider'])
        result['expected_returned_provider_names']=result.get('image_expected_returned_provider_names',result['expected_returned_provider_names'])
    require(result['provider'].get('allow_fallbacks') is False,'Provider fallbacks forbidden')
    return result


def fixture():
    """Truthful, unscored neutral-input fixture for maximum media cardinality."""
    game=MarioGame(level='1-1');images=[]
    try:
        initial=game.observe();proof=[]
        for f in (0,6,12):
            while game.frame<f:game.step(dict(horizontal='released',vertical='released',jump='released',run='released'))
            images.append((f,rgb_png(game)));proof.append(dict(frame=f,ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),screen_sha256=screen_hash(game),png_sha256=hashlib.sha256(images[-1][1]).hexdigest()))
        return initial,images,proof
    finally:game.close()


def fixture_session(model,track):
    initial,images,_=fixture();session=CommonSession(model,track,temperature=.05 if track=='image' else None,sampler_seed=9001 if track=='image' else None)
    if track=='state':session.begin_state(initial)
    else:
        neutral=dict(horizontal='released',vertical='released',jump='released',run='released')
        for f,png in images:
            session.begin_image(png,frame=f)
            if f<12:session.advance(buttons=neutral,frame_after=f+6,actual_frames=6)
    return session


def build_schedule(phase,models,images,temperature=None):
    schedule=[]
    for m in models:
        tracks=['state']+(['image'] if m['id'] in images else [])
        for track in tracks:
            if phase=='pilot' and m['id'] not in (STATE_PILOT if track=='state' else IMAGE_PILOT):continue
            temps=([.05,.2] if phase=='pilot' else [temperature]) if track=='image' else [None]
            repeats=[0] if phase in ('pilot','preflight') else [0,1,2]
            for t in temps:
                for repeat in repeats:
                    seed=(9001 if phase in ('pilot','preflight') else 101+repeat) if track=='image' else None
                    eid=f'state-v2-{phase}-{track}-{safe_name(m["id"])}-t{str(t).replace(".","")}-repeat{repeat}'
                    schedule.append(dict(episode_id=eid,model_id=m['id'],track=track,temperature=t,repeat_id=repeat,local_rng_seed=seed,emulator_seed=0))
    return schedule


def plan(phase,output,*,selection=None,preflight=None,policy='openrouter',concurrency=22):
    models,images,evidence=roster();selected=None
    require(phase in ('preflight','pilot'),'This isolated state calibration cannot launch a final cohort')
    if phase=='evaluation':
        require(selection is not None,'Evaluation requires a frozen complete pilot selection')
        selected=validated_selection(selection)
        require(selected['promotion_eligible'],'Pilot native-clear gate is not satisfied')
    temperature=selected['selected_temperature'] if selected else None
    schedule=build_schedule(phase,models,images,temperature)
    initial,_,fixture_proof=fixture()
    value=dict(schema_version=1,protocol_id='mario-common-state-compact-v2',phase=phase,frozen_at_utc=datetime.now(timezone.utc).isoformat(),level='1-1',emulator_seed=0,life_budget=1,native_frame_cap=6000 if phase=='evaluation' else 3000,minimum_hold={'state':4},timeout_seconds=60,retries_after_initial=2,no_stall_abort=True,provider_seed=None,policy=policy,models=models,image_eligible_models=images,image_eligibility_evidence=evidence,repeat_schedule=schedule,concurrency=min(concurrency,len(models)),max_active_cases_per_model=1,software_sha256=locked_sources(),roster_source_sha256=hashlib.sha256((ROOT/'benchmark/models.json').read_bytes()).hexdigest(),initial_observation_sha256=digest(initial),initial_screen_sha256=fixture_proof[0]['screen_sha256'],endpoint_calibration=json.loads((ROOT/'benchmark/protocol.json').read_text())['endpoint_calibration'],scoring=dict(start_x=40,goal_x=3161,primary='mean_prespecified_episode_progress',technical_errors='incomplete_null_until_cause_proven',speed='best_completed_native_frames_and_mean_completed'),sampling=dict(image='all12nativep**(1/T);sortedkeys;oneRandom(seed)drawpercommittedmotor',state='native_choice_direct'),pilot_selection_rule='Complete equal-model mean progress; T must itself have >=1nativeclear; choose highest eligible mean, exact tie .05; state >=1nativeclear; no infrastructure omission',media=dict(current_lower_crop=[0,80,256,240],crop_size=[768,480],current_full_size=[512,480],past_full_screens=2,own_controls=3,order='currentcrop,currentfull,pastlatest,pastolder'),questions_sha256={},preflight_report_sha256=hashlib.sha256(Path(preflight).read_bytes()).hexdigest() if preflight else None,pilot_selection_sha256=hashlib.sha256(Path(selection).read_bytes()).hexdigest() if selection else None)
    value['actual_rom_sha256']=actual_rom_sha256()
    require(value['actual_rom_sha256']==value['endpoint_calibration']['rom_sha256'],'Installed ROM differs from native calibration')
    require(fixture_proof[0]['ram_sha256']==value['endpoint_calibration']['initial_ram_sha256'],'Initial native RAM differs from calibrated reset')
    from benchmark.common_state_compact_v2 import PROFILE
    ACTION_QUESTION=PROFILE['questions']['action'];DURATION_QUESTION={};RULES=PROFILE['rules']
    value['media']=None;value['sampling']={'state':'validated_native_action_choice_direct'}
    value['pilot_selection_rule']='Complete four-family state calibration; at least one genuine native flag; any technical pending prevents promotion'
    value['runtime']=dict(python=platform.python_version(),system=platform.system(),machine=platform.machine(),packages={name:importlib.metadata.version(name) for name in ['Pillow','numpy','nes_py','gym-super-mario-bros']})
    value['controller_contracts']=dict(rules=RULES,action_question=ACTION_QUESTION,duration_question=DURATION_QUESTION,state_profile='common-state-compact-v2',image_profile=None,state_observer='common_state_compact_v2.state_text; exact compact current-state formatter',image_stages=[],schema_failure_attribution='technical_pending; no model score absent explicit independent behavioral proof')
    value['questions_sha256']={'action':digest(ACTION_QUESTION),'rules':hashlib.sha256(RULES.encode()).hexdigest()}
    if phase=='preflight':
        value['fixture']=dict(description='Not scored: actual reset0 and two fixed neutral6-frame advances, frames0/6/12; no gameplay action chosen from these calls',frames=fixture_proof);templates={}
        for job in schedule:
            m=track_model(next(m for m in models if m['id']==job['model_id']),job['track']);s=fixture_session(m,job['track']);h={}
            if job['track']=='image':
                h['duration']=digest(s.body('duration'));h['motor_by_native_hold']={}
                for duration in (2,4,6,8,12):s.duration=duration;h['motor_by_native_hold'][str(duration)]=digest(s.body('motor'))
            else:h['motor']=digest(s.body('motor'))
            templates[job['episode_id']]=h
        value['fixture_request_templates_sha256']=templates
    elif policy!='fake':
        require(preflight is not None,'Paid gameplay requires accepted frozen preflight report')
        accepted=validate_preflight(preflight)
        require(accepted['software_sha256']==value['software_sha256'],'Preflight software differs from gameplay')
    output=Path(output);output.mkdir(parents=True,exist_ok=True);destination=output/'manifest.json'
    require(not destination.exists(),'Never overwrite a preregistration; choose a fresh output')
    if selected:
        value['pilot_selection_evidence']=dict(state_gate_passed=selected['state_native_clears']>=1,selected_image_temperature_gate_passed=selected['pixel_candidates'][str(selected['selected_temperature'])]['native_clears']>=1,selected_temperature=selected['selected_temperature'],pilot_protocol_sha256=selected['pilot_manifest_sha256'],pilot_summary_sha256=selected['pilot_summary_sha256'],pilot_audit_sha256=selected['pilot_audit_sha256'])
    write_json(destination,value)
    write_json(output/'preregistration.json',dict(protocol_sha256=digest(value),frozen_at_utc=value['frozen_at_utc'],software_sha256=value['software_sha256'],policy=policy,phase=phase))
    return value


def verify_manifest(manifest,output):
    registration=json.loads((Path(output)/'preregistration.json').read_text())
    require(registration['protocol_sha256']==digest(manifest),'Preregistered manifest was modified')
    require(registration['frozen_at_utc']==manifest['frozen_at_utc'] and registration['policy']==manifest['policy'],'Registration identity changed')
    require(manifest['actual_rom_sha256']==actual_rom_sha256()==manifest['endpoint_calibration']['rom_sha256'],'Actual installed ROM differs from frozen calibration')
    require(manifest['software_sha256']==locked_sources(),'Frozen software changed; new scientific envelope required')
    require(manifest['phase'] in ('preflight','pilot'),'Unknown phase')
    require(manifest['life_budget']==1 and manifest['no_stall_abort'] is True,'Invalid native envelope')
    require(manifest['native_frame_cap']==(6000 if manifest['phase']=='evaluation' else 3000),'Native cap differs from protocol')
    models,images,evidence=roster()
    require(manifest['models']==models and manifest['image_eligible_models']==images and manifest['image_eligibility_evidence']==evidence,'Frozen roster/provider eligibility changed')
    ts={j['temperature'] for j in manifest['repeat_schedule'] if j['track']=='image'}
    temperature=next(iter(ts)) if manifest['phase']=='evaluation' and len(ts)==1 else None
    require(manifest['phase']!='evaluation' or temperature in (.05,.2),'Evaluation requires one selected common temperature')
    require(manifest['repeat_schedule']==build_schedule(manifest['phase'],models,images,temperature),'Prespecified case/seed schedule changed')


def fixture_response(model,body,index):
    answers={}
    for name,q in body['questions'].items():
        keys=list(q['criteria']);choice=('routine_6' if name=='duration' else 'right_run_jump' if index%16<10 else 'right_run_release')
        answers[name]=dict(type='choice',choice=choice,probabilities={k:.85 if k==choice else .15/(len(keys)-1) for k in keys})
    return dict(id=f'offline-{index}',model=model['expected_returned_model'],provider=model['expected_returned_provider_names'][0],answers=answers,usage={})


def stage_call(session,stage,body,*,path,episode_id,index,game,prior,audit,manifest,client):
    """Exactly one durable intent/result per HTTP attempt; no RNG side effects."""
    bh=digest(body);before=digest(game.observe()) if game else None;frame=game.frame if game else session.frame
    old=[r for r in prior if r.get('stage')==stage];intents=[r for r in old if r['event']=='request_intent'];results=[r for r in old if r['event']=='request_result']
    require(len(results)<=len(intents)<=len(results)+1,'Stage attempt ledger is not a committed prefix')
    for n,row in enumerate(intents):require(row['attempt']==n and row['request_sha256']==bh and row['body']==body and row['frame']==frame,'Recorded request differs from frozen stage body')
    for n,row in enumerate(results):
        require(row['attempt']==n and row['request_sha256']==bh and row['frame_after_request']==frame,'Recorded inference was not frozen')
        if row['valid']:session.parse(row['raw_response'],body)
    if len(intents)>len(results):return None,'Uncertain interrupted request; no duplicate sent'
    outcome=results[-1] if results else None
    while outcome is None or (not outcome['valid'] and outcome.get('retryable') and len(results)<=manifest['retries_after_initial']):
        require(not audit,'Audit cannot send or complete a request');attempt=len(results)
        if attempt:time.sleep(min(2**(attempt-1),4))
        identity=dict(episode_id=episode_id,decision_index=index,stage=stage,attempt=attempt,frame=frame,request_sha256=bh)
        append(path,dict(event='request_intent',body=body,**identity))
        if manifest['policy']=='fake':
            raw=fixture_response(session.model,body,index);outcome=dict(valid=True,retryable=False,raw_response=raw,decision=session.parse(raw,body),request_sha256=bh,http_status=None)
        else:outcome=client.call(body)
        require(not game or (game.frame==frame and digest(game.observe())==before),'Game advanced during inference')
        outcome['frame_after_request']=frame;append(path,dict(event='request_result',episode_id=episode_id,decision_index=index,stage=stage,attempt=attempt,frame=frame,**outcome));results.append(outcome)
    if not outcome or not outcome['valid']:return outcome,'Technical pending: transport, provenance, schema or parser failure; not model skill'
    return outcome,None


def execute_episode(output,manifest,job,*,audit=False):
    model=track_model(next(m for m in manifest['models'] if m['id']==job['model_id']),job['track']);session=CommonSession(model,job['track'],temperature=job['temperature'],sampler_seed=job['local_rng_seed'])
    eid=job['episode_id'];path=Path(output)/'episodes'/(eid+'.jsonl');path.parent.mkdir(exist_ok=True);rows=read_events(path);ends=[r for r in rows if r['event']=='episode_end']
    if ends and not audit:
        result=ends[-1]['result'];require(result['protocol_sha256']==digest(manifest) and result['episode_id']==eid and result['model_id']==job['model_id'] and result['track']==job['track'] and result['repeat_id']==job['repeat_id'] and result['local_rng_seed']==job['local_rng_seed'],'Completed episode belongs to a different frozen job')
        return dict(result,**costs_from_events(rows,episode_id=eid))
    by_index=defaultdict(list)
    for row in rows:
        if 'decision_index'in row:by_index[row['decision_index']].append(row)
    game=MarioGame(level='1-1');client=None if audit or manifest['policy']=='fake' else Client(os.environ.get('OPENROUTER_API_KEY',''),model,manifest['timeout_seconds'],decoder=session.parse);maximum=40.;decisions=0;status=error=None
    try:
        initial=game.observe();begin=dict(event='episode_start',episode_id=eid,initial_observation_sha256=digest(initial),initial_screen_sha256=screen_hash(game),protocol_sha256=digest(manifest),job=job)
        require(begin['initial_observation_sha256']==manifest['initial_observation_sha256'],'Initial RAM state differs from preregistration')
        if 'initial_screen_sha256' in manifest:require(begin['initial_screen_sha256']==manifest['initial_screen_sha256'],'Initial screen differs from preregistered reset')
        if 'endpoint_calibration' in manifest:require(hashlib.sha256(game.env.ram.tobytes()).hexdigest()==manifest['endpoint_calibration']['initial_ram_sha256'],'Initial native RAM differs from calibrated reset')
        starts=[r for r in rows if r['event']=='episode_start']
        if starts:require(len(starts)==1 and all(starts[0].get(k)==v for k,v in begin.items()),'Recorded start differs from fresh reset')
        else:require(not audit and not rows,'Missing start checkpoint');append(path,begin)
        started_at_utc=starts[0]['utc'] if starts else read_events(path)[0]['utc']
        require(started_at_utc>=manifest.get('frozen_at_utc',''),'Episode precedes preregistration')
        for index in range(math.ceil(manifest['native_frame_cap']/(4 if job['track']=='state' else 2))):
            if game.done or game.flag_get or game.frame>=manifest['native_frame_cap']:break
            before=game.frame;state=game.observe();observation_hash=digest(state)
            if job['track']=='image':session.begin_image(rgb_png(game),frame=before)
            else:session.begin_state(state)
            prior=by_index[index]
            for stage in session.stages:
                body=session.body(stage);outcome,error=stage_call(session,stage,body,path=path,episode_id=eid,index=index,game=game,prior=prior,audit=audit,manifest=manifest,client=client)
                if error:status='infra_error';break
                if stage=='duration':session.accept_duration(outcome['raw_response'],body)
            if error:break
            choice=session.choose(outcome['raw_response'],body);steps=min(choice['requested_frames'],manifest['native_frame_cap']-before)
            action=plain(dict(event='action',episode_id=eid,decision_index=index,frame_before=before,observation_sha256=observation_hash,**choice,frames=steps));actions=[r for r in prior if r['event']=='action']
            if actions:require(len(actions)==1 and all(actions[0].get(k)==v for k,v in action.items()),'Action or RNG differs from exact replay')
            else:require(not audit,'Missing committed action');append(path,action)
            native=[]
            for _ in range(steps):
                observed=game.step(choice['buttons']);x=validated_progress_x(observed,40)
                if x is not None:maximum=max(maximum,x)
                native.append(dict(frame=game.frame,ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),screen_sha256=screen_hash(game)))
                if game.done or game.flag_get:break
            actual=game.frame-before;chunk=dict(event='chunk_end',episode_id=eid,decision_index=index,frame=game.frame,actual_frames=actual,observation_sha256=digest(game.observe()),screen_sha256=screen_hash(game),native_frame_hashes=native);chunks=[r for r in prior if r['event']=='chunk_end']
            if chunks:require(len(chunks)==1 and all(chunks[0].get(k)==v for k,v in chunk.items()),'Native physics/checkpoint differs from exact replay')
            else:require(not audit,'Missing native checkpoint');append(path,chunk)
            session.advance(buttons=choice['buttons'],frame_after=game.frame,actual_frames=actual);decisions+=1
            if not audit:write_json(path.with_suffix('.progress.json'),dict(episode_id=eid,frame=game.frame,decisions=decisions,flag_get=bool(game.flag_get),death=bool(game.death),phase=manifest['phase']))
        if status is None:status='completed' if game.flag_get else 'game_over' if game.done else 'frame_budget'
        result=dict(episode_id=eid,id=eid,started_at_utc=started_at_utc,model=job['model_id'],model_id=job['model_id'],track=job['track'],level='1-1',status=status,completed=bool(game.flag_get),flag_get=bool(game.flag_get),death=bool(game.death),emulator_seed=0,repeat_id=job['repeat_id'],local_rng_seed=job['local_rng_seed'],temperature=job['temperature'],start_x=40,max_progress_x=maximum,frames=game.frame,native_frames=game.frame,decisions=decisions,native_frames_to_completion=game.frame if game.flag_get else None,error=error,technical_pending=status=='infra_error',phase=manifest['phase'],protocol_sha256=digest(manifest),native_frame_budget=manifest['native_frame_cap'],life_budget=1,native_replay_verified=bool(audit))
        result=score_episode(result,dict(start_x=40,goal_x=3161))
        if ends:
            old=dict(ends[-1]['result']);old['native_replay_verified']=bool(audit);require(old==result,'Scored result differs from independently replayed native evidence')
        else:require(not audit,'Missing episode end');append(path,dict(event='episode_end',episode_id=eid,result=result))
        if audit:write_json(path.with_suffix('.audit.json'),dict(verified=True,episode_id=eid,protocol_sha256=digest(manifest),native_frames=game.frame,flag_get=bool(game.flag_get),death=bool(game.death),decisions=decisions,episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        return dict(result,**costs_from_events(read_events(path),episode_id=eid))
    finally:
        if client:client.close()
        game.close()


def execute_preflight(output,manifest,job,*,audit=False):
    model=track_model(next(m for m in manifest['models'] if m['id']==job['model_id']),job['track']);s=fixture_session(model,job['track']);eid=job['episode_id'];path=Path(output)/'episodes'/(eid+'.jsonl');path.parent.mkdir(exist_ok=True);prior=read_events(path);client=None if audit or manifest['policy']=='fake' else Client(os.environ.get('OPENROUTER_API_KEY',''),model,60,decoder=s.parse);stages=[]
    try:
        for stage in s.stages:
            body=s.body(stage);templates=manifest['fixture_request_templates_sha256'][eid];expected=templates[stage] if stage=='duration' or job['track']=='state' else templates['motor_by_native_hold'][str(s.duration)];require(digest(body)==expected,'Preflight fixture/body differs from preregistration')
            outcome,error=stage_call(s,stage,body,path=path,episode_id=eid,index=0,game=None,prior=prior,audit=audit,manifest=manifest,client=client)
            stages.append(dict(stage=stage,valid=not error,request_sha256=digest(body),technical_error=error))
            if error:break
            if stage=='duration':s.accept_duration(outcome['raw_response'],body)
        result=dict(episode_id=eid,model_id=job['model_id'],track=job['track'],passed=len(stages)==len(s.stages) and all(x['valid'] for x in stages),stages=stages,scored=False,actions_executed=0,fixture_native_frame=s.frame)
        if not audit:write_json(path.with_suffix('.preflight.json'),result)
        return result
    finally:
        if client:client.close()


def model_worker(output,manifest,jobs,audit):
    rows=[]
    for job in jobs:
        result=(execute_preflight if manifest['phase']=='preflight' else execute_episode)(output,manifest,job,audit=audit);rows.append(result)
    return rows


def summarize(output,manifest,rows,failures):
    if manifest['phase']=='preflight':
        value=dict(schema_version=1,policy=manifest['policy'],accepted=manifest['policy']=='openrouter' and len(rows)==len(manifest['repeat_schedule']) and all(r['passed'] for r in rows) and not failures,transport_complete=len(rows)==len(manifest['repeat_schedule']) and all(r['passed'] for r in rows) and not failures,requires_audit_before_pilot=True,scored=False,actual_gameplay_actions=0,software_sha256=manifest['software_sha256'],manifest_sha256=digest(manifest),results=rows,worker_failures=failures)
    else:
        groups=defaultdict(list);expected=defaultdict(list)
        for job in manifest['repeat_schedule']:expected[(job['model_id'],job['track'],job['temperature'])].append(job['episode_id'])
        for row in rows:groups[(row['model_id'],row['track'],row['temperature'])].append(row)
        aggregates=[]
        for (mid,track,t),ids in expected.items():
            records=groups[(mid,track,t)];agg=aggregate_results(records,ids);times=[r['native_frames_to_completion'] for r in records if r['rankable'] and r['clear'] and r['native_frames_to_completion'] is not None]
            aggregates.append(dict(model_id=mid,track=track,temperature=t,expected_trial_ids=ids,recorded_trial_ids=[r['episode_id'] for r in records],aggregate=agg,best_clear_native_frames=min(times) if times else None,best_clear_game_seconds=min(times)/60 if times else None,mean_completed_native_frames=statistics.mean(times) if times else None,mean_completed_game_seconds=statistics.mean(times)/60 if times else None,n_completed=len(times)))
        value=dict(schema_version=1,phase=manifest['phase'],protocol_sha256=digest(manifest),episodes=rows,rows=aggregates,worker_failures=failures,pilot_results_excluded_from_evaluation=True)
    write_json(Path(output)/'summary.json',value);return value


def _execute_locked(output,*,audit=False):
    output=Path(output);manifest=json.loads((output/'manifest.json').read_text());verify_manifest(manifest,output)
    if not audit and manifest['policy']=='openrouter':load_key()
    grouped=defaultdict(list)
    for job in manifest['repeat_schedule']:grouped[job['model_id']].append(job)
    rows=[];failures=[]
    with ProcessPoolExecutor(max_workers=manifest['concurrency'],mp_context=multiprocessing.get_context('spawn')) as pool:
        fs={pool.submit(model_worker,str(output),manifest,jobs,audit):mid for mid,jobs in grouped.items()}
        for future in as_completed(fs):
            try:
                batch=future.result();rows.extend(batch);print(json.dumps(dict(model=fs[future],phase=manifest['phase'],cases=len(batch),statuses=[r.get('status','passed' if r.get('passed') else 'technical_pending') for r in batch])),flush=True)
            except Exception as exc:failures.append(dict(model=fs[future],error=type(exc).__name__+': '+str(exc)));print(json.dumps(failures[-1]),flush=True)
            if not audit:summarize(output,manifest,rows,failures)
    if audit:write_json(output/'audit.json',dict(verified=not failures and len(rows)==len(manifest['repeat_schedule']),protocol_sha256=digest(manifest),episodes=rows,worker_failures=failures,source_log_sha256={j['episode_id']:hashlib.sha256((output/'episodes'/(j['episode_id']+'.jsonl')).read_bytes()).hexdigest() for j in manifest['repeat_schedule']}))
    else:summarize(output,manifest,rows,failures)
    require(not failures,'Worker failures preserved; cohort incomplete')


def execute(output,*,audit=False):
    output=Path(output)
    with (output/'orchestrator.lock').open('a+') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('This output already has an active orchestrator; no requests sent') from None
        lock.seek(0);lock.truncate();lock.write(json.dumps(dict(pid=os.getpid(),audit=audit,started_at_utc=datetime.now(timezone.utc).isoformat())));lock.flush()
        return _execute_locked(output,audit=audit)


def verified_audit(output,manifest):
    output=Path(output);audit=json.loads((output/'audit.json').read_text())
    require(audit['verified'] and audit['protocol_sha256']==digest(manifest),'Missing exact native/request replay audit')
    expected={j['episode_id'] for j in manifest['repeat_schedule']}
    require(set(audit['source_log_sha256'])==expected,'Audit source coverage differs from schedule')
    for eid,h in audit['source_log_sha256'].items():
        path=output/'episodes'/(eid+'.jsonl');require(hashlib.sha256(path.read_bytes()).hexdigest()==h,'Audited source log changed')
        if manifest['policy']=='openrouter':
            for r in read_events(path):
                if r['event']=='request_result' and r.get('valid'):
                    raw=r.get('raw_response',{});require(isinstance(raw.get('id'),str) and raw['id'].startswith('gen-') and type(r.get('http_status')) is int and 200<=r['http_status']<300,'Offline/unproven response cannot authorise paid benchmark evidence')
    require({r['episode_id'] for r in audit['episodes']}==expected and len(audit['episodes'])==len(expected),'Audit episode identities differ')
    return audit


def validate_preflight(report):
    output=Path(report).parent;m=json.loads((output/'manifest.json').read_text());verify_manifest(m,output)
    require(m['phase']=='preflight' and m['policy']=='openrouter','Paid gameplay requires a real OpenRouter common-format preflight')
    s=json.loads(Path(report).read_text());a=verified_audit(output,m)
    require(s.get('accepted') is True and s.get('policy')=='openrouter' and s['manifest_sha256']==digest(m),'Incomplete or differently frozen preflight')
    require(len(a['episodes'])==22 and all(r['passed'] and r['actions_executed']==0 for r in a['episodes']),'Common-format stage coverage is incomplete')
    require(sum(len(r['stages']) for r in a['episodes'])==22,'Expected22native state stages')
    return s


def pilot_selection(output):
    output=Path(output);m=json.loads((output/'manifest.json').read_text());verify_manifest(m,output)
    require(m['phase']=='pilot' and m['policy']=='openrouter','Only real state calibration can authorise a state gate')
    s=json.loads((output/'summary.json').read_text());require(s['protocol_sha256']==digest(m),'State pilot summary manifest mismatch');a=verified_audit(output,m)
    require(not s['worker_failures'] and len(s['episodes'])==4,'State pilot is incomplete')
    live={r['episode_id']:r for r in s['episodes']};rows=a['episodes']
    compare=['episode_id','phase','protocol_sha256','model_id','track','level','repeat_id','local_rng_seed','temperature','status','rankable','progress_pct','max_progress_x','frames','completed','flag_get','death','decisions','emulator_seed','native_frames_to_completion','native_frame_budget','life_budget','started_at_utc']
    require(set(live)=={j['episode_id'] for j in m['repeat_schedule']},'State pilot IDs differ from schedule')
    for r in rows:require(all(live[r['episode_id']].get(k)==r.get(k) for k in compare),'State summary differs from native-audited episode')
    require(all(r['rankable'] and r['native_replay_verified'] and r['track']=='state' for r in rows),'Technical pending prevents state promotion')
    require({r['model_id'] for r in rows}==set(STATE_PILOT),'Missing state calibration family')
    clears=sum(r['clear'] for r in rows)
    return dict(schema_version=1,track='state',pilot_policy='openrouter',state_profile='common-state-compact-v2',software_sha256=m['software_sha256'],controller_contracts_sha256=digest(m['controller_contracts']),state_native_clears=clears,promotion_eligible=clears>=1,pilot_manifest_sha256=digest(m),pilot_summary_sha256=hashlib.sha256((output/'summary.json').read_bytes()).hexdigest(),pilot_audit_sha256=hashlib.sha256((output/'audit.json').read_bytes()).hexdigest(),interpretation='State-only calibration evidence. Does not authorise any final/common cohort without separately verified image selected-T clear evidence.')


def validated_selection(path):
    expected=pilot_selection(Path(path).parent);actual=json.loads(Path(path).read_text());require(actual==expected,'Selection differs from exact real pilot/audit/source chain');return actual


def select_pilot(output):
    value=pilot_selection(output);path=Path(output)/'selection.json'
    if path.exists():require(json.loads(path.read_text())==value,'Never overwrite different pilot selection evidence')
    else:write_json(path,value)
    print(json.dumps(value,indent=2));return value


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    x=sub.add_parser('plan');x.add_argument('--phase',choices=['preflight','pilot'],required=True);x.add_argument('--output',type=Path,required=True);x.add_argument('--selection',type=Path);x.add_argument('--preflight',type=Path);x.add_argument('--policy',choices=['openrouter','fake'],default='openrouter');x.add_argument('--concurrency',type=int,default=22)
    for name in ['execute','audit','select']:
        x=sub.add_parser(name);x.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='plan':
        m=plan(a.phase,a.output,selection=a.selection,preflight=a.preflight,policy=a.policy,concurrency=a.concurrency);print(json.dumps(dict(manifest=str(a.output/'manifest.json'),protocol_sha256=digest(m),phase=m['phase'],cases=len(m['repeat_schedule']),preregistered=True),indent=2))
    elif a.command=='select':select_pilot(a.output)
    else:execute(a.output,audit=a.command=='audit')

if __name__=='__main__':main()
