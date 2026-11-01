"""Explicit progress-baseline authority; unchanged fixed7 image motor and native engine. Prior failed pilot gates remain immutable and are not represented as passed."""
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
from benchmark.common_image_runtime_v2 import CommonImageSession as CommonSession, ACTIONS
from benchmark.common_image_v2_policy import FRAMES_PER_ACTION,BUILDER_PROFILE_ID
from benchmark.profiles.image_v1 import PROFILES
from benchmark.costs import costs_from_events
from benchmark.run import append, read_events, write_json, load_key, safe_name
from benchmark.scoring import score_episode, aggregate_results, validated_progress_x
from prototype.emulator import MarioGame

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL_ID='mario-common-image-h7-progress-baseline-v1'
FINAL_SPEC_SHA256='86e4974bc01f983980c1773184e75900856d55a3d68fa6fc32c43c416e91bf29'
SOURCES=['benchmark/common_image_final_run.py','benchmark/common_image_final_spec.json','benchmark/common_image_final_evidence/negative-v1.json','benchmark/common_image_final_evidence/negative-v2.json','benchmark/common_image_final_evidence/negative-v3.json','benchmark/common_image_final_evidence/historical-mechanics.json','benchmark/common_image_v2_policy.py','benchmark/common_image_runtime_v2.py','benchmark/common_image_run_v2.py','benchmark/profiles/image_v1.py','benchmark/profiles/probability_sampler_v1.py','benchmark/client.py','benchmark/costs.py','benchmark/scoring.py','benchmark/run.py','prototype/emulator.py','prototype/decisions.py','prototype/control.py','benchmark/protocol.json','benchmark/models.json','requirements.lock.txt']



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


def all_roster():
    data=json.loads((ROOT/'benchmark/models.json').read_text());models=data['models'];images=[];evidence=[]
    index=json.loads((ROOT/'results/index.json').read_text())
    for model in models:
        if model['id'] in ('cloudflare/clef','cloudflare/clef-flash'):
            row=next(r for r in index['observations'] if r['model_id']==model['id'] and r['mode']=='image')
            require(row['verified'] and row['input_audit']['privileged_state_sent'] is False and row['provider']=='Cloudflare','Missing strict image provider evidence')
            require(row['returned_model']==model['expected_returned_model'],'Image identity mismatch')
            model['image_provider']={'only':['cloudflare'],'allow_fallbacks':False}
            model['image_expected_returned_provider_names']=['Cloudflare'];model['image_preflight_passed']=True
            evidence.append(dict(model_id=model['id'],trace_href=row['trace_href'],trace_sha256=hashlib.sha256((ROOT/'results'/row['trace_href']).read_bytes()).hexdigest(),source_hashes=row['source_hashes'],image_provider=model['image_provider'],expected_returned_providers=['Cloudflare']))
        if model.get('image_preflight_passed'):images.append(model['id'])
    require(len(models)==22 and len(images)==16,'Common roster must explicitly contain22state/16image pairs')
    return models,images,evidence

def roster():
    all_models,images,evidence=all_roster()
    selected=[track_model(m,'image') for m in all_models if m['id'] in images]
    require(len(selected)==16 and len({m['id'] for m in selected})==16,'Exactly16 image model/provider pairs required')
    return selected,images,evidence


def track_model(model,track):
    result=deepcopy(model)
    if track=='image':
        result['provider']=result.get('image_provider',result['provider'])
        result['expected_returned_provider_names']=result.get('image_expected_returned_provider_names',result['expected_returned_provider_names'])
    require(result['provider'].get('allow_fallbacks') is False,'Provider fallbacks forbidden')
    return result


def fixture():
    """Unscored actual neutral7+7 setup, current14 and maximum one past7."""
    game=MarioGame(level='1-1');images=[];proof=[]
    neutral=dict(horizontal='released',vertical='released',jump='released',run='released')
    try:
        initial=game.observe()
        for frame in (0,7,14):
            while game.frame<frame:game.step(neutral)
            data=rgb_png(game);images.append((frame,data));proof.append(dict(frame=frame,ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),screen_sha256=screen_hash(game),png_sha256=hashlib.sha256(data).hexdigest()))
        return initial,images,proof
    finally:game.close()


def fixture_session(model,track):
    _,images,_=fixture();s=CommonSession(model,track,temperature=.05,sampler_seed=9001)
    neutral=dict(horizontal='released',vertical='released',jump='released',run='released')
    for frame,png in images:
        s.begin_image(png,frame=frame)
        if frame<14:s.advance(buttons=neutral,frame_after=frame+7,actual_frames=7)
    return s








def fixture_response(model,body,index):
    keys=list(body['questions']['action']['criteria']);choice='right_B_held_A_held' if index%16<10 else 'right_B_held_A_released'
    return dict(id=f'offline-{index}',model=model['expected_returned_model'],provider=model['expected_returned_provider_names'][0],answers={'action':dict(type='choice',choice=choice,probabilities={k:.85 if k==choice else .15/(len(keys)-1) for k in keys})},usage={})


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
        if manifest['policy']=='openrouter':time.sleep(manifest['minimum_request_spacing_seconds'])
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
    verify_manifest(manifest,output)
    if not audit and manifest['policy']=='openrouter':require_review_approval(output,manifest)
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
        for index in range(math.ceil(manifest['native_frame_cap']/7)):
            if game.done or game.flag_get or game.frame>=manifest['native_frame_cap']:break
            before=game.frame;state=game.observe();observation_hash=digest(state)
            session.begin_image(rgb_png(game),frame=before)
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
        result=dict(episode_id=eid,id=eid,source_policy=manifest['policy'],started_at_utc=started_at_utc,model=job['model_id'],model_id=job['model_id'],track=job['track'],level='1-1',status=status,completed=bool(game.flag_get),flag_get=bool(game.flag_get),death=bool(game.death),emulator_seed=0,repeat_id=job['repeat_id'],local_rng_seed=job['local_rng_seed'],temperature=job['temperature'],start_x=40,max_progress_x=maximum,frames=game.frame,native_frames=game.frame,decisions=decisions,native_frames_to_completion=game.frame if game.flag_get else None,error=error,technical_pending=status=='infra_error',phase=manifest['phase'],protocol_sha256=digest(manifest),native_frame_budget=manifest['native_frame_cap'],life_budget=1,native_replay_verified=bool(audit))
        result=score_episode(result,dict(start_x=40,goal_x=3161))
        if manifest['policy']=='fake':result.update(offline_fixture_only=True,rankable=False,clear=None,progress_pct=None,progress_mapping_validated=False,native_frames_to_completion=None,nominal_game_seconds_to_completion=None,speedrun_score_native_frames=None)
        if ends:
            old=dict(ends[-1]['result']);old['native_replay_verified']=bool(audit);require(old==result,'Scored result differs from independently replayed native evidence')
        else:require(not audit,'Missing episode end');append(path,dict(event='episode_end',episode_id=eid,result=result))
        if audit:write_json(path.with_suffix('.audit.json'),dict(verified=True,episode_id=eid,protocol_sha256=digest(manifest),native_frames=game.frame,flag_get=bool(game.flag_get),death=bool(game.death),decisions=decisions,episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        return dict(result,**costs_from_events(read_events(path),episode_id=eid))
    finally:
        if client:client.close()
        game.close()


def execute_preflight(output,manifest,job,*,audit=False):
    verify_manifest(manifest,output)
    if not audit and manifest['policy']=='openrouter':require_review_approval(output,manifest)
    model=track_model(next(m for m in manifest['models'] if m['id']==job['model_id']),job['track']);s=fixture_session(model,job['track']);rng_before=digest(s.rng.getstate());eid=job['episode_id'];path=Path(output)/'episodes'/(eid+'.jsonl');path.parent.mkdir(exist_ok=True);prior=read_events(path);client=None if audit or manifest['policy']=='fake' else Client(os.environ.get('OPENROUTER_API_KEY',''),model,60,decoder=s.parse);stages=[]
    try:
        for stage in s.stages:
            body=s.body(stage);templates=manifest['fixture_request_templates_sha256'][eid];expected=templates[stage];require(digest(body)==expected,'Preflight fixture/body differs from preregistration')
            outcome,error=stage_call(s,stage,body,path=path,episode_id=eid,index=0,game=None,prior=prior,audit=audit,manifest=manifest,client=client)
            stages.append(dict(stage=stage,valid=not error,request_sha256=digest(body),technical_error=error))
            if error:break
            if stage=='duration':s.accept_duration(outcome['raw_response'],body)
        result=dict(episode_id=eid,model_id=job['model_id'],track=job['track'],passed=len(stages)==len(s.stages) and all(x['valid'] for x in stages),stages=stages,scored=False,actions_executed=0,rng_draws=0,rng_state_unchanged=digest(s.rng.getstate())==rng_before,fixture_native_frame=s.frame)
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
        value=dict(schema_version=1,phase=manifest['phase'],policy=manifest['policy'],offline_fixture_only=manifest['policy']=='fake',protocol_sha256=digest(manifest),episodes=rows,rows=aggregates,worker_failures=failures,pilot_results_excluded_from_evaluation=True)
    write_json(Path(output)/'summary.json',value);return value


def _execute_locked(output,*,audit=False):
    output=Path(output);manifest=json.loads((output/'manifest.json').read_text());verify_manifest(manifest,output)
    if not audit and manifest['policy']=='openrouter':
        require_review_approval(output,manifest);load_key()
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















def build_schedule(phase,models,images):
    require(phase in ('preflight','evaluation'),'Only parse-only preflight or the fresh48 baseline is authorised')
    jobs=[]
    for model in models:
        for repeat in ([0] if phase=='preflight' else [0,1,2]):
            seed=9001 if phase=='preflight' else 101+repeat
            eid=f'image-h7-baseline-{phase}-{safe_name(model["id"])}-repeat{repeat}-seed{seed}'
            jobs.append(dict(episode_id=eid,model_id=model['id'],track='image',temperature=.05,repeat_id=repeat,local_rng_seed=seed,emulator_seed=0))
    return jobs


def acceptance_contract(preflight_provenance=None):
    profile=PROFILES[BUILDER_PROFILE_ID]
    contract=dict(builder_profile_id=BUILDER_PROFILE_ID,rules=profile['metadata_template']['rules_and_button_semantics'],questions=profile['questions'],metadata_template=profile['metadata_template'],a_button_notes=profile['a_button_notes'],requested_frames=7)
    spec=json.loads((ROOT/'benchmark/common_image_final_spec.json').read_text())
    provenance=preflight_provenance or {}
    return dict(mode='explicit_progress_baseline_v1',positive_pilot_required=False,native_clear_is_outcome=True,
        prior_failed_pilot_gates_preserved=True,spec_sha256=FINAL_SPEC_SHA256,image_controller_sha256=digest(contract),historical_mechanics=deepcopy(spec['historical_mechanics']),
        historical_mechanics_proof_sha256=hashlib.sha256((ROOT/'benchmark/common_image_final_evidence/historical-mechanics.json').read_bytes()).hexdigest(),
        preflight_protocol_sha256=provenance.get('protocol_sha256'),preflight_report_sha256=provenance.get('summary_sha256'),
        preflight_audit_sha256=provenance.get('audit_sha256'),preflight_model_count=provenance.get('model_count',0),
        preflight_audit_complete=provenance.get('audit_complete',False),negative_calibration_proofs=deepcopy(spec['negative_calibrations']))


def plan(phase,output,*,preflight=None,policy='openrouter',concurrency=8):
    require(phase in ('preflight','evaluation'),'This authority has no new pilot, temperature selection or seed search')
    require(policy in ('openrouter','fake'),'Unknown transport policy')
    spec_path=ROOT/'benchmark/common_image_final_spec.json'
    require(hashlib.sha256(spec_path.read_bytes()).hexdigest()==FINAL_SPEC_SHA256,'Explicit root-approved progress-baseline spec is not frozen')
    models,images,evidence=roster();schedule=build_schedule(phase,models,images);initial,_,proof=fixture();profile=PROFILES[BUILDER_PROFILE_ID]
    manifest=dict(schema_version=1,protocol_id=PROTOCOL_ID,phase=phase,frozen_at_utc=datetime.now(timezone.utc).isoformat(),acceptance_contract=acceptance_contract(),evaluation_scope='image_progress_baseline',tracks=['image'],temperature=.05,cadence_native_frames=7,native_frame_budget=6000 if phase=='evaluation' else 0,
        level='1-1',emulator_seed=0,life_budget=1,native_frame_cap=6000 if phase=='evaluation' else 0,minimum_hold={'image':7},requested_native_hold=7,
        maximum_control_actions=858 if phase=='evaluation' else 0,timeout_seconds=60,retries_after_initial=2,no_stall_abort=True,provider_seed=None,
        policy=policy,models=models,image_eligible_models=images,image_eligibility_evidence=evidence,repeat_schedule=schedule,
        concurrency=min(concurrency,8 if phase=='evaluation' else 4),max_active_cases_per_model=1,
        resource_scope='one active image case per model; three final repeats serial within model; at most one independently queued state case may share the stateless provider pin',
        minimum_request_spacing_seconds=.5,software_sha256=locked_sources(),roster_source_sha256=hashlib.sha256((ROOT/'benchmark/models.json').read_bytes()).hexdigest(),
        initial_observation_sha256=digest(initial),initial_screen_sha256=proof[0]['screen_sha256'],initial_rgb_sha256=proof[0]['screen_sha256'],initial_ram_sha256=proof[0]['ram_sha256'],endpoint_calibration=json.loads((ROOT/'benchmark/protocol.json').read_text())['endpoint_calibration'],
        scoring=dict(start_x=40,goal_x=3161,primary='mean_prespecified_episode_progress',technical_errors='incomplete_null_until_cause_proven',speed='best_completed_native_frames_and_mean_completed',clear_requires_native_flag=True,failed_speed_is_null=True),
        sampling=dict(head='action',formula='all12nativep**(1/T);sortedkeys;oneRandom(seed)drawpercommittedmotor',temperature=.05,final_seeds=[101,102,103],preflight_seed=9001,selection_method='predeclared_shared_baseline_not_pilot_selected'),
        media=dict(current_full_size=[512,480],source_native_size=[256,240],nearest_scale=2,past_full_screens=1,own_controls=2,order='FULLCURRENT then one FULLPAST; no crops or additional heads'),
        controller_contracts=dict(builder_profile_id=BUILDER_PROFILE_ID,rules=profile['metadata_template']['rules_and_button_semantics'],questions=profile['questions'],metadata_template=profile['metadata_template'],a_button_notes=profile['a_button_notes'],requested_frames=7),
        questions_sha256=dict(action=digest(profile['questions']),rules=hashlib.sha256(profile['metadata_template']['rules_and_button_semantics'].encode()).hexdigest()),
        preflight_report_sha256=hashlib.sha256(Path(preflight).read_bytes()).hexdigest() if preflight else None,
        runtime=dict(python=platform.python_version(),system=platform.system(),machine=platform.machine(),packages={name:importlib.metadata.version(name) for name in ['Pillow','numpy','nes_py','gym-super-mario-bros']}))
    manifest['actual_rom_sha256']=actual_rom_sha256();require(manifest['actual_rom_sha256']==manifest['endpoint_calibration']['rom_sha256'],'Installed ROM differs from calibration');require(proof[0]['ram_sha256']==manifest['endpoint_calibration']['initial_ram_sha256'],'Initial RAM differs from calibration')
    if phase=='preflight':
        manifest['fixture']=dict(description='Unscored actual neutral7+7 preparation; current14/past7. Neutral inputs were protocol fixture setup, not model-selected gameplay. All inference calls execute zero subsequent controls.',frames=proof,native_preparation_frames=14,current_native_frame=14,past_native_frame=7,declared_actual_neutral_controls=[dict(frame=0,frames=7),dict(frame=7,frames=7)],rng_draws=0)
        manifest['fixture_request_templates_sha256']={job['episode_id']:{'motor':digest(fixture_session(next(m for m in models if m['id']==job['model_id']),'image').body('motor'))} for job in schedule}
    elif policy!='fake':
        require(preflight is not None,'Fresh48 requires accepted real16-image preflight');accepted=validate_preflight(preflight);require(accepted['software_sha256']==manifest['software_sha256'],'Preflight source differs from final')
        preflight_root=Path(preflight).parent
        manifest['preflight_provenance']=dict(protocol_sha256=accepted['manifest_sha256'],summary_sha256=manifest['preflight_report_sha256'],audit_sha256=hashlib.sha256((preflight_root/'audit.json').read_bytes()).hexdigest(),model_count=16,audit_complete=True)
    manifest['acceptance_contract']=acceptance_contract(manifest.get('preflight_provenance'))
    manifest['observation_and_controller_hashes']=dict(image_controller_sha256=digest(manifest['controller_contracts']))
    manifest['historical_mechanics_witness']=deepcopy(json.loads(spec_path.read_text())['historical_mechanics'])
    output=Path(output);output.mkdir(parents=True,exist_ok=True);require(not (output/'manifest.json').exists(),'Never overwrite a registration')
    for name,h in manifest['software_sha256'].items():
        destination=output/'sources'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():require(hashlib.sha256(destination.read_bytes()).hexdigest()==h,'Existing source snapshot differs; choose a new output')
        else:destination.write_bytes((ROOT/name).read_bytes())
    write_json(output/'manifest.json',manifest);write_json(output/'preregistration.json',dict(protocol_sha256=digest(manifest),frozen_at_utc=manifest['frozen_at_utc'],software_sha256=manifest['software_sha256'],policy=policy,phase=phase));return manifest


def verify_manifest(manifest,output):
    registration=json.loads((Path(output)/'preregistration.json').read_text());require(registration['protocol_sha256']==digest(manifest),'Manifest changed after preregistration')
    require(registration['frozen_at_utc']==manifest['frozen_at_utc'] and registration['policy']==manifest['policy'],'Registration identity changed')
    require(manifest['phase'] in ('preflight','evaluation') and manifest['protocol_id']==PROTOCOL_ID,'No pilot/tuning authority in this engine')
    require(manifest['acceptance_contract']==acceptance_contract(manifest.get('preflight_provenance')),'Explicit progress acceptance changed; failed pilot gates cannot be relabelled as passed')
    require(manifest['software_sha256']==locked_sources(),'Frozen software changed')
    require(hashlib.sha256((ROOT/'benchmark/common_image_final_spec.json').read_bytes()).hexdigest()==FINAL_SPEC_SHA256,'Explicit baseline authority spec changed')
    require(manifest['actual_rom_sha256']==actual_rom_sha256()==manifest['endpoint_calibration']['rom_sha256'],'Installed ROM changed')
    models,images,evidence=roster();require(manifest['models']==models and manifest['image_eligible_models']==images and manifest['image_eligibility_evidence']==evidence,'Roster/provider eligibility changed')
    require(manifest['repeat_schedule']==build_schedule(manifest['phase'],models,images),'Frozen schedule changed')
    require(manifest['evaluation_scope']=='image_progress_baseline' and manifest['tracks']==['image'],'Image baseline must remain separate from state')
    require(manifest['temperature']==.05 and manifest['cadence_native_frames']==7 and manifest['native_frame_budget']==manifest['native_frame_cap'],'Baseline aliases differ')
    require(manifest['observation_and_controller_hashes']==dict(image_controller_sha256=digest(manifest['controller_contracts'])),'Controller hash differs')
    require(manifest['life_budget']==1 and manifest['no_stall_abort'] is True,'Native envelope changed')
    require(manifest['requested_native_hold']==7 and manifest['native_frame_cap']==(6000 if manifest['phase']=='evaluation' else 0),'Native hold/budget changed')
    require(manifest['maximum_control_actions']==(858 if manifest['phase']=='evaluation' else 0),'Native action cap changed')
    require(manifest['max_active_cases_per_model']==1 and 1<=manifest['concurrency']<=(8 if manifest['phase']=='evaluation' else 4),'Resource scope changed')
    require(all(j['track']=='image' and j['temperature']==.05 for j in manifest['repeat_schedule']),'Only the shared imageT.05 baseline is authorised')
    if manifest['phase']=='evaluation':
        require(len(manifest['repeat_schedule'])==48 and all(j['local_rng_seed']==101+j['repeat_id'] and j['repeat_id'] in (0,1,2) for j in manifest['repeat_schedule']),'Only fresh prespecified final seeds101/102/103 are authorised')
        if manifest['policy']=='openrouter':require(manifest['acceptance_contract']['preflight_audit_complete'] is True and manifest['acceptance_contract']['preflight_model_count']==16,'Real final48 requires complete actual16preflight')
    for name,h in manifest['software_sha256'].items():require(hashlib.sha256((Path(output)/'sources'/name).read_bytes()).hexdigest()==h,'Frozen source snapshot differs')


def validate_preflight(report):
    output=Path(report).parent;m=json.loads((output/'manifest.json').read_text());verify_manifest(m,output);require(m['phase']=='preflight' and m['policy']=='openrouter','Final requires a real native preflight');s=json.loads(Path(report).read_text());a=verified_audit(output,m)
    require(s.get('accepted') is True and s.get('policy')=='openrouter' and s['manifest_sha256']==digest(m),'Unaccepted or differently registered preflight')
    require(len(a['episodes'])==16 and all(r['passed'] and r['actions_executed']==0 and r['rng_draws']==0 and r['rng_state_unchanged'] is True and r['fixture_native_frame']==14 for r in a['episodes']),'All16 native pairs must pass parse-only fixture')
    require(sum(len(r['stages']) for r in a['episodes'])==16,'Exactly16 native motor-stage preflights required');require_review_approval(output,m);return s


def require_review_approval(output,manifest):
    path=Path(output)/'review-approval.json';require(path.exists(),'Exact reviewer sidecar required before real calls');value=json.loads(path.read_text())
    require(value.get('approved') is True and value.get('protocol_sha256')==digest(manifest) and value.get('phase')==manifest['phase'] and value.get('software_sha256')==manifest['software_sha256'],'Reviewer approval does not match exact frozen source/protocol')
    require(value.get('reviewer') in ('promotion_review','/root/promotion_review'),'Expected independent reviewer identity')
    if manifest['phase']=='evaluation':
        ui_path=Path(output)/'ui-review-approval.json';require(ui_path.exists(),'Explicit image-only progress-baseline UI/schema review required before paid48')
        ui=json.loads(ui_path.read_text());require(ui.get('approved') is True and ui.get('protocol_sha256')==digest(manifest) and ui.get('software_sha256')==manifest['software_sha256'] and ui.get('acceptance_mode')=='explicit_progress_baseline_v1','UI acceptance does not match the exact final source/protocol')
        require(ui.get('reviewer') in ('replay_backfill','/root/replay_backfill','promotion_review','/root/promotion_review'),'Expected independent UI/schema reviewer')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    x=sub.add_parser('plan');x.add_argument('--phase',choices=['preflight','evaluation'],required=True);x.add_argument('--output',type=Path,required=True);x.add_argument('--preflight',type=Path);x.add_argument('--policy',choices=['openrouter','fake'],default='openrouter');x.add_argument('--concurrency',type=int,default=8)
    for name in ['execute','audit']:
        x=sub.add_parser(name);x.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='plan':
        m=plan(a.phase,a.output,preflight=a.preflight,policy=a.policy,concurrency=a.concurrency);print(json.dumps(dict(manifest=str(a.output/'manifest.json'),protocol_sha256=digest(m),phase=m['phase'],cases=len(m['repeat_schedule']),preregistered=True),indent=2))
    else:execute(a.output,audit=a.command=='audit')

if __name__=='__main__':main()
