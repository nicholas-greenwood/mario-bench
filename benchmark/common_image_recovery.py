"""New same-checkpoint image transport authority; original image48 stays immutable.

Preparation is offline. Planning requires all48 original native audits and an
independent prefix proof; execution additionally requires exact approval.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import fcntl
import json
import math
import os
from pathlib import Path

from benchmark import common_image_final_run as E
from benchmark.client import Client,digest
from benchmark.costs import costs_from_events
from benchmark.run import append,read_events,write_json,load_key
from benchmark.scoring import validated_progress_x,score_episode
from prototype.emulator import MarioGame

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL_ID='mario-image-technical-recovery-v1'
PARENT_PROTOCOL_SHA256='2f11c42b8d47f8cd8959e828243acacb8abcf83c478a6206508ebd635004fdf1'
PIN_KEYS=('id','request_model','provider','expected_returned_model','expected_returned_provider_names')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def plain(value):return E.plain(value)


def source_hashes():return dict(E.locked_sources(),**{'benchmark/common_image_recovery.py':sha(__file__)})


def verify_source_archive(output,hashes):
    root=Path(output)/'sources'
    E.require(len(hashes)==22 and hashes==source_hashes(),'Recovery requires the exact original21 plus helper source closure')
    E.require(root.is_dir() and not root.is_symlink() and not any(p.is_symlink() for p in root.rglob('*')),'Missing or symlinked recovery source archive')
    files={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    E.require(files==set(hashes),'Missing or unexpected recovery source snapshot')
    for name,expected in hashes.items():E.require(sha(root/name)==expected,'Archived recovery source bytes changed: '+name)


def archive_sources(output,hashes):
    root=Path(output)/'sources'
    E.require(len(hashes)==22 and hashes==source_hashes(),'Recovery source closure changed before archival')
    E.require(not root.is_symlink(),'Recovery source archive cannot be a symlink')
    root.mkdir(parents=True,exist_ok=True)
    E.require(not any(p.is_symlink() for p in root.rglob('*')),'Recovery source archive contains symlinks')
    for name,expected in hashes.items():
        source=ROOT/name;target=root/name;raw=source.read_bytes()
        E.require(hashlib.sha256(raw).hexdigest()==expected,'Recovery source changed while archiving: '+name)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():E.require(sha(target)==expected,'Never overwrite a different archived source: '+name)
        else:target.write_bytes(raw)
        E.require(sha(source)==sha(target)==expected,'Source/archive changed during copy: '+name)
    verify_source_archive(output,hashes)


def unknown_attempts(rows):
    """Unanswered requests and matched timeouts may have reached the provider."""
    intents=sum(r['event']=='request_intent' for r in rows);results=[r for r in rows if r['event']=='request_result']
    return intents-len(results)+sum(r.get('error')=='TimeoutError' or r.get('error_type')=='TimeoutError' for r in results)


def validate_actual_receipts(rows,policy):
    if policy!='openrouter':return
    ids=[]
    for row in rows:
        if row['event']=='request_result' and row.get('valid'):
            raw=row.get('raw_response',{});E.require(type(row.get('http_status')) is int and 200<=row['http_status']<300
                and isinstance(raw.get('id'),str) and raw['id'].startswith('gen-'),'Offline/unproven receipt cannot authorise actual recovery evidence');ids.append(raw['id'])
    E.require(len(ids)==len(set(ids)),'A provider receipt was reused across original/new attempts')


def checkpoint(game,session,body,model,controller,history):
    state=plain(session.rng.getstate())
    return dict(checkpoint_native_frame=game.frame,checkpoint_ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),
                checkpoint_rgb_sha256=E.screen_hash(game),checkpoint_observation_sha256=digest(game.observe()),
                controller_history_sha256=digest(history),session_controls=plain(list(session.controls)),
                session_controls_sha256=digest(list(session.controls)),current_png_sha256=hashlib.sha256(session.current).hexdigest(),
                previous_images=[dict(frame=f,png_sha256=hashlib.sha256(p).hexdigest()) for f,p in session.previous],
                failed_request_sha256=digest(body),controller_sha256=controller,pin_sha256=digest({k:model[k] for k in PIN_KEYS}),
                rng_mode='global_full12_temperature_sampling',rng_state=state,rng_state_sha256=digest(state),
                rng_mt_index=state[1][-1],rng_draw_count=session.index)


def advance(game,session,choice,index,eid,maximum,history):
    before=game.frame;native=[]
    for _ in range(min(choice['requested_frames'],6000-before)):
        observed=game.step(choice['buttons']);x=validated_progress_x(observed,40)
        if x is not None:maximum=max(maximum,x)
        native.append(dict(frame=game.frame,ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),screen_sha256=E.screen_hash(game)))
        if game.done or game.flag_get:break
    actual=game.frame-before
    chunk=dict(event='chunk_end',episode_id=eid,decision_index=index,frame=game.frame,actual_frames=actual,
               observation_sha256=digest(game.observe()),screen_sha256=E.screen_hash(game),native_frame_hashes=native)
    session.advance(buttons=choice['buttons'],frame_after=game.frame,actual_frames=actual)
    history.append(dict(frame_before=before,frame_after=game.frame,actual_native_frames=actual,buttons=choice['buttons']))
    return maximum,chunk


def validate_ledger(rows,eid,first=0,*,child=False):
    """Fail closed before Client creation, including valid-then-retry corruption."""
    if not rows:return
    allowed={'continuation_start' if child else 'episode_start','request_intent','request_result','action','chunk_end','episode_end'}
    if child:allowed.add('inherited_valid_response')
    start='continuation_start' if child else 'episode_start'
    E.require(rows[0]['event']==start and sum(r['event']==start for r in rows)==1,'Missing unique initial authority')
    E.require(all(r.get('episode_id')==eid and r.get('event') in allowed for r in rows),'Foreign/unconsumed ledger row')
    ends=[i for i,r in enumerate(rows) if r['event']=='episode_end'];E.require(not ends or ends==[len(rows)-1],'Ledger advanced after terminal result')
    groups=defaultdict(list);ordered=[]
    for row in rows:
        if row['event'] in ('request_intent','request_result','action','chunk_end','inherited_valid_response'):
            i=row.get('decision_index');E.require(type(i) is int and first<=i<858,'Foreign decision index');groups[i].append(row);ordered.append(i)
    E.require(ordered==sorted(ordered),'Reordered decision groups')
    if groups:E.require(sorted(groups)==list(range(first,max(groups)+1)),'Skipped native decision')
    for i,group in groups.items():
        attempts=[r for r in group if r['event'] in ('request_intent','request_result')]
        intents=[r for r in attempts if r['event']=='request_intent'];results=[r for r in attempts if r['event']=='request_result']
        E.require(len(results)<=len(intents)<=len(results)+1 and len(intents)<=3,'Invalid/excessive attempt scope')
        inherited=[r for r in group if r['event']=='inherited_valid_response']
        E.require(not inherited or (child and i==first and len(inherited)==1 and not attempts),'An inherited response cannot be duplicated/re-requested')
        valid=bool(inherited)
        for n,row in enumerate(attempts):
            E.require(not valid and row.get('stage')=='motor' and row.get('attempt')==n//2
                      and row['event']==('request_intent' if n%2==0 else 'request_result'),'Attempt after observed valid result, or reordered/unpaired attempt')
            if row['event']=='request_result' and row.get('valid') is True:valid=True
        actions=[r for r in group if r['event']=='action'];chunks=[r for r in group if r['event']=='chunk_end']
        E.require(len(actions)<=1 and len(chunks)<=len(actions) and (not actions or valid),'Action lacks unique received choice')
        E.require([r['event'] for r in group]==['inherited_valid_response']*len(inherited)+[r['event'] for r in attempts]+['action']*len(actions)+['chunk_end']*len(chunks),'Unconsumed/reordered action ledger')
        if i<max(groups):E.require(len(chunks)==1,'Next decision before prior native commit')


def reconstruct(rows,pm,eid):
    """Return the exact staged failed request without another begin_image call."""
    validate_ledger(rows,eid);validate_actual_receipts(rows,pm['policy']);E.require(rows[-1]['event']=='episode_end' and rows[-1]['result']['status']=='infra_error','Only a closed technical abort may be inspected')
    start=rows[0];job=start['job'];E.require(start['protocol_sha256']==digest(pm) and job in pm['repeat_schedule'],'Wrong original slot')
    model=E.track_model(next(m for m in pm['models'] if m['id']==job['model_id']),'image')
    session=E.CommonSession(model,'image',temperature=job['temperature'],sampler_seed=job['local_rng_seed']);game=MarioGame(level='1-1')
    maximum=40.;history=[];groups=defaultdict(list)
    for row in rows:
        if 'decision_index' in row:groups[row['decision_index']].append(row)
    try:
        E.require(digest(game.observe())==start['initial_observation_sha256'] and E.screen_hash(game)==start['initial_screen_sha256'],'Original reset differs')
        for i in range(858):
            E.require(not game.done and not game.flag_get and game.frame<6000,'A valid native outcome cannot be recovered')
            session.begin_image(E.rgb_png(game),frame=game.frame);body=session.body('motor');prior=groups[i]
            E.require(prior,'Missing failed or committed original decision')
            for row in prior:
                if row['event']=='request_intent':E.require(row['body']==body and row['request_sha256']==digest(body) and row['frame']==game.frame,'Original full image request differs')
                if row['event']=='request_result':
                    E.require(row['request_sha256']==digest(body) and row['frame_after_request']==game.frame,'Original inference advanced native time')
                    if row.get('valid'):session.parse(row['raw_response'],body)
            actions=[r for r in prior if r['event']=='action']
            if not actions:
                E.require(set(groups)==set(range(i+1)),'Unconsumed original decision after abort')
                cp=checkpoint(game,session,body,model,digest(pm['controller_contracts']),history)
                E.require(rows[-1]['result']['frames']==game.frame and rows[-1]['result']['decisions']==i
                          and rows[-1]['result']['max_progress_x']==maximum,'Original whole-prefix grade differs')
                return game,session,maximum,history,cp,body,prior
            response=next(r for r in prior if r['event']=='request_result' and r.get('valid'));choice=session.choose(response['raw_response'],body)
            expected=plain(dict(event='action',episode_id=eid,decision_index=i,frame_before=game.frame,observation_sha256=digest(game.observe()),**choice,frames=min(7,6000-game.frame)))
            E.require(all(actions[0].get(k)==v for k,v in expected.items()),'Original buttons/fullMT sampling differs')
            maximum,chunk=advance(game,session,choice,i,eid,maximum,history);old=next(r for r in prior if r['event']=='chunk_end')
            E.require(all(old.get(k)==v for k,v in chunk.items()),'Original per-frame RAM/RGB/native checkpoint differs')
        raise RuntimeError('No technical prefix remains inside the native cap')
    except BaseException:game.close();raise


def inspect_prefix(parent,episode_id):
    """Read-only inventory facts; never registers or executes a recovery."""
    parent=Path(parent);pm=read(parent/'manifest.json');E.verify_manifest(pm,parent)
    E.require(digest(pm)==PARENT_PROTOCOL_SHA256 and pm['policy']=='openrouter','Exact real image48 parent required')
    path=parent/'episodes'/(episode_id+'.jsonl');before=sha(path);rows=read_events(path)
    game,session,maximum,history,cp,body,failed=reconstruct(rows,pm,episode_id)
    try:
        intents=[r for r in failed if r['event']=='request_intent'];results=[r for r in failed if r['event']=='request_result'];valid=[r for r in results if r.get('valid')]
        mode='unanswered_no_resend' if len(intents)>len(results) else 'reuse_recorded_valid_response' if valid else 'fresh_after_observed_failures'
        E.require(intents and (valid or len(results)==3 or mode=='unanswered_no_resend'),'Not an exhausted or uncertain original transport abort')
        E.require(sha(path)==before,'Original source changed during inspection');job=rows[0]['job']
        return dict(original_trial_id=episode_id,child_run_id=episode_id+'--image-technical-recovery-v1',parent_episode_path=str(path.resolve()),parent_episode_sha256=before,
                    **{k:job[k] for k in ('model_id','track','repeat_id','temperature','emulator_seed','local_rng_seed')},checkpoint=cp,
                    pin_payload={k:deepcopy(session.model[k]) for k in PIN_KEYS},
                    failed_decision_index=session.index,failed_stage='motor',failed_attempt_chain=len(intents),continuation_mode=mode,
                    inherited_parent_valid_response_sha256=digest(valid[0]['raw_response']) if valid else None,
                    inherited_parent_receipt_id_sha256=hashlib.sha256(valid[0]['raw_response']['id'].encode()).hexdigest() if valid else None,
                    parent_abort_status='infra_error',parent_valid_native_actions=session.index,parent_http_attempts=sum(r['event']=='request_intent' for r in rows),
                    parent_max_progress_x=maximum,remaining_native_frame_budget=6000-game.frame,provider_outcome_unknown_attempt_count=unknown_attempts(rows),
                    no_observed_valid_choice_discarded=True,unmatched_ledger_intent_count=len(intents)-len(results))
    finally:game.close()


def restore(slot,pm):
    path=Path(slot['parent_episode_path']);E.require(sha(path)==slot['parent_episode_sha256'],'Original source bytes changed');rows=read_events(path)
    game,session,maximum,history,cp,body,failed=reconstruct(rows,pm,slot['original_trial_id'])
    try:
        job=rows[0]['job'];intents=[r for r in failed if r['event']=='request_intent'];results=[r for r in failed if r['event']=='request_result']
        mode='unanswered_no_resend' if len(intents)>len(results) else 'reuse_recorded_valid_response' if any(r.get('valid') for r in results) else 'fresh_after_observed_failures'
        valid=[r for r in results if r.get('valid')]
        E.require(slot['child_run_id']==slot['original_trial_id']+'--image-technical-recovery-v1' and all(slot[k]==job[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed'))
                  and slot['continuation_mode']==mode and slot['parent_http_attempts']==sum(r['event']=='request_intent' for r in rows)
                  and slot['provider_outcome_unknown_attempt_count']==unknown_attempts(rows),'Original condition/attempt/pending scope changed')
        E.require(slot.get('inherited_parent_valid_response_sha256')==(digest(valid[0]['raw_response']) if valid else None)
                  and slot.get('inherited_parent_receipt_id_sha256')==(hashlib.sha256(valid[0]['raw_response']['id'].encode()).hexdigest() if valid else None),'Inherited parent receipt binding changed')
        E.require(cp==slot['checkpoint'] and session.index==slot['failed_decision_index']==slot['parent_valid_native_actions'] and maximum==slot['parent_max_progress_x'],'Checkpoint/current-pastPNG/control/RNG/pin/body changed')
        E.require(session.seed==slot['local_rng_seed'] and session.temperature==slot['temperature'] and game.frame+slot['remaining_native_frame_budget']==6000,'Original seed/T/native budget changed')
        return game,session,maximum,history,cp,rows,body,failed
    except BaseException:game.close();raise


def original(parent):
    parent=Path(parent);pm=read(parent/'manifest.json');E.verify_manifest(pm,parent)
    E.require(digest(pm)==PARENT_PROTOCOL_SHA256 and pm['policy']=='openrouter' and pm['phase']=='evaluation','Exact original image48 authority required')
    audit=E.verified_audit(parent,pm)
    E.require(audit['verified'] is True and len(audit['episodes'])==48,'Wait for ALL48 original terminal native audits before registration')
    return pm,audit


def validate_prefix_proof(manifest,proof,audit):
    E.require(proof.get('verified') is True and proof['parent_protocol_sha256']==manifest['parent_protocol_sha256']
              and proof['source_log_sha256']==audit['source_log_sha256'],'Independent all48 source/prefix binding differs')
    expected=[{k:v for k,v in slot.items() if k!='parent_episode_path'} for slot in manifest['slots']]
    E.require(proof['slots']==expected,'Independent native/PNG/history/MT/body prefix proof differs')


def plan(output,parent,prefix_proof):
    """Authority owner only, after full original closure; never called by inspection."""
    output,parent=Path(output),Path(parent);E.require(not (output/'manifest.json').exists(),'Never replace a recovery registration')
    pm,audit=original(parent);eligible=[r['episode_id'] for r in audit['episodes'] if r['status']=='infra_error']
    E.require(eligible,'No technical image slot requires recovery')
    slots=[inspect_prefix(parent,eid) for eid in eligible]
    m=dict(schema_version=1,protocol_id=PROTOCOL_ID,acceptance_mode='same_checkpoint_technical_recovery_v1',phase='technical_recovery',preregistered=True,policy='openrouter',
           frozen_at_utc=datetime.now(timezone.utc).isoformat(),parent_protocol_sha256=digest(pm),parent_manifest_file_sha256=sha(parent/'manifest.json'),
           parent_audit_sha256=sha(parent/'audit.json'),parent_output=str(parent.resolve()),prefix_proof_path=str(Path(prefix_proof).resolve()),prefix_proof_sha256=sha(prefix_proof),
           software_sha256=source_hashes(),slots=slots,tracks=['image'],native_frame_budget=6000,native_frame_cap=6000,cadence_native_frames=7,requested_native_hold=7,
           life_budget=1,max_continuations_per_slot=1,retries_after_initial=2,timeout_seconds=pm['timeout_seconds'],minimum_request_spacing_seconds=pm['minimum_request_spacing_seconds'],
           temperature=.05,provider_seed=None,emulator_seed=0,concurrency=min(len(slots),4),provider_outcome_unknown_attempt_count=sum(s['provider_outcome_unknown_attempt_count'] for s in slots))
    validate_prefix_proof(m,read(prefix_proof),audit)
    output.mkdir(parents=True,exist_ok=True);archive_sources(output,m['software_sha256']);write_json(output/'manifest.json',m)
    write_json(output/'preregistration.json',dict(protocol_sha256=digest(m),frozen_at_utc=m['frozen_at_utc'],parent_protocol_sha256=digest(pm)))
    return m


def verify(output,approval=False):
    output=Path(output);m=read(output/'manifest.json');r=read(output/'preregistration.json')
    E.require(m['protocol_id']==PROTOCOL_ID and r['protocol_sha256']==digest(m) and r['frozen_at_utc']==m['frozen_at_utc'],'New recovery registration changed')
    E.require(m['software_sha256']==source_hashes(),'Recovery or original21 sources changed')
    verify_source_archive(output,m['software_sha256'])
    pm,audit=original(m['parent_output'])
    E.require(m['parent_protocol_sha256']==digest(pm) and m['parent_manifest_file_sha256']==sha(Path(m['parent_output'])/'manifest.json')
              and m['parent_audit_sha256']==sha(Path(m['parent_output'])/'audit.json'),'Original48 authority changed')
    E.require(m['policy']=='openrouter' and m['phase']=='technical_recovery' and m['preregistered'] is True and m['tracks']==['image'] and m['acceptance_mode']=='same_checkpoint_technical_recovery_v1'
              and m['native_frame_budget']==m['native_frame_cap']==6000 and m['cadence_native_frames']==m['requested_native_hold']==7
              and m['life_budget']==m['max_continuations_per_slot']==1 and m['retries_after_initial']==2 and m['temperature']==.05
              and m['provider_seed'] is None and m['emulator_seed']==0 and m['timeout_seconds']==pm['timeout_seconds']
              and m['minimum_request_spacing_seconds']==pm['minimum_request_spacing_seconds'],'Recovery native/transport/sampler envelope changed')
    eligible={r['episode_id'] for r in audit['episodes'] if r['status']=='infra_error'}
    E.require(len(m['slots'])==len(eligible) and {s['original_trial_id'] for s in m['slots']}==eligible
              and len({s['child_run_id'] for s in m['slots']})==len(eligible),'Must recover ALL and ONLY technical slots once')
    E.require(m['provider_outcome_unknown_attempt_count']==sum(s['provider_outcome_unknown_attempt_count'] for s in m['slots'])
              and type(m['concurrency']) is int and 1<=m['concurrency']<=min(len(eligible),4),'Recovery uncertainty/resource scope changed')
    for slot in m['slots']:
        E.require(slot==inspect_prefix(m['parent_output'],slot['original_trial_id']),'Declared original slot checkpoint/pin/T/seed changed')
    E.require(sha(m['prefix_proof_path'])==m['prefix_proof_sha256'],'Independent prefix proof bytes changed')
    validate_prefix_proof(m,read(m['prefix_proof_path']),audit)
    if approval:
        a=read(output/'independent-approval.json')
        E.require(a.get('approved') is True and a['protocol_sha256']==digest(m) and a['software_sha256']==m['software_sha256']
                  and a['parent_protocol_sha256']==digest(pm) and a.get('reviewer') in ('promotion_review','/root/promotion_review'),'Exact independent native/lineage approval required before any call')
        ui=read(output/'ui-review-approval.json')
        E.require(ui.get('approved') is True and ui['protocol_sha256']==digest(m) and ui['software_sha256']==m['software_sha256']
                  and ui['parent_protocol_sha256']==digest(pm) and ui.get('acceptance_mode')=='same_checkpoint_technical_recovery_v1'
                  and ui.get('reviewer') in ('replay_backfill','/root/replay_backfill','promotion_review','/root/promotion_review'),'Exact independent UI/lineage approval required before any call')
    return m,pm


def execute_one(output,m,pm,slot,audit=False):
    if not audit:
        registered,parent=verify(output,approval=True)
        E.require(registered==m and parent==pm and slot in m['slots'],'Unregistered recovery invocation')
    output=Path(output);eid=slot['child_run_id'];path=output/'episodes'/(eid+'.jsonl');path.parent.mkdir(parents=True,exist_ok=True)
    rows=read_events(path);validate_ledger(rows,eid,slot['failed_decision_index'],child=True)
    game,session,maximum,history,cp,parentrows,staged_body,failed=restore(slot,pm)
    groups=defaultdict(list);visited=set();client=None;status=error=None;decisions=slot['parent_valid_native_actions']
    for row in rows:
        if 'decision_index' in row:groups[row['decision_index']].append(row)
    try:
        start=dict(event='continuation_start',episode_id=eid,protocol_sha256=digest(m),parent_protocol_sha256=digest(pm),resolves_original_trial_id=slot['original_trial_id'],
                   parent_episode_sha256=slot['parent_episode_sha256'],checkpoint=cp,reconstructed_checkpoint=cp)
        starts=[r for r in rows if r['event']=='continuation_start']
        if starts:E.require(all(starts[0].get(k)==v for k,v in start.items()),'Child initial authority changed')
        else:E.require(not audit and not rows,'Missing child start');append(path,start)
        started=starts[0]['utc'] if starts else read_events(path)[0]['utc'];E.require(started>=m['frozen_at_utc'],'Child precedes its registration')
        # All prefix/body/pin/fullMT checks above precede Client construction.
        if slot['continuation_mode']=='unanswered_no_resend':status='infra_error';error='Original request outcome unknown; no duplicate sent'
        for i in range(slot['failed_decision_index'],858):
            if status or game.done or game.flag_get or game.frame>=6000:break
            visited.add(i)
            if i==slot['failed_decision_index']:body=staged_body
            else:session.begin_image(E.rgb_png(game),frame=game.frame);body=session.body('motor')
            inherited=i==slot['failed_decision_index'] and slot['continuation_mode']=='reuse_recorded_valid_response'
            if inherited:
                out=next(r for r in failed if r['event']=='request_result' and r.get('valid'));session.parse(out['raw_response'],body)
                # Parent owns this already-received receipt and billing; no new intent/result.
                prior=groups[i];E.require(not any(r['event'] in ('request_intent','request_result') for r in prior),'Inherited valid reply cannot be requested again')
                inherited_record=dict(event='inherited_valid_response',episode_id=eid,decision_index=i,parent_episode_sha256=slot['parent_episode_sha256'],
                                      raw_response_sha256=digest(out['raw_response']),request_sha256=digest(body))
                old=[r for r in prior if r['event']=='inherited_valid_response']
                if old:E.require(len(old)==1 and all(old[0].get(k)==v for k,v in inherited_record.items()),'Inherited parent choice changed')
                else:E.require(not audit,'Missing inherited response binding');append(path,inherited_record)
            else:
                requests=[r for r in groups[i] if r['event']=='request_intent'];responses=[r for r in groups[i] if r['event']=='request_result']
                needs_call=len(requests)==len(responses) and (not responses or (not responses[-1]['valid'] and responses[-1].get('retryable') and len(responses)<3))
                if not audit and needs_call and client is None:client=Client(os.environ['OPENROUTER_API_KEY'],session.model,m['timeout_seconds'],decoder=session.parse)
                out,error=E.stage_call(session,'motor',body,path=path,episode_id=eid,index=i,game=game,prior=groups[i],audit=audit,manifest=m,client=client)
                if error:status='infra_error';break
            choice=session.choose(out['raw_response'],body)
            action=plain(dict(event='action',episode_id=eid,decision_index=i,frame_before=game.frame,observation_sha256=digest(game.observe()),**choice,frames=min(7,6000-game.frame)))
            old=[r for r in groups[i] if r['event']=='action']
            if old:E.require(len(old)==1 and all(old[0].get(k)==v for k,v in action.items()),'Child action/fullMT differs')
            else:E.require(not audit,'Missing child action');append(path,action)
            maximum,chunk=advance(game,session,choice,i,eid,maximum,history);old=[r for r in groups[i] if r['event']=='chunk_end']
            if old:E.require(len(old)==1 and all(old[0].get(k)==v for k,v in chunk.items()),'Child per-frame native replay differs')
            else:E.require(not audit,'Missing child native checkpoint');append(path,chunk)
            decisions+=1
        E.require(set(groups)<=visited,'Unconsumed child decisions after native terminal/error/budget')
        if status is None:status='completed' if game.flag_get else 'game_over' if game.done else 'frame_budget'
        E.require(math.isfinite(maximum) and maximum>=slot['parent_max_progress_x'],'Whole-trajectory progress must retain the finite original prefix maximum')
        result=score_episode(dict(id=eid,episode_id=eid,record_kind='technical_continuation',phase='technical_recovery',protocol_sha256=digest(m),parent_protocol_sha256=digest(pm),
            resolves_original_trial_id=slot['original_trial_id'],parent_episode_sha256=slot['parent_episode_sha256'],started_at_utc=started,model=slot['model_id'],model_id=slot['model_id'],track='image',level='1-1',
            repeat_id=slot['repeat_id'],local_rng_seed=slot['local_rng_seed'],temperature=slot['temperature'],emulator_seed=0,native_frame_budget=6000,life_budget=1,cadence_native_frames=7,
            status=status,technical_pending=status=='infra_error',completed=bool(game.flag_get),flag_get=bool(game.flag_get),death=bool(game.death),frames=game.frame,native_frames=game.frame,
            continuation_native_frames=game.frame-slot['checkpoint']['checkpoint_native_frame'],decisions=decisions,continuation_decisions=decisions-slot['parent_valid_native_actions'],
            native_frames_to_completion=game.frame if game.flag_get else None,start_x=40,max_progress_x=maximum,error=error,native_replay_verified=bool(audit),checkpoint=cp,reconstructed_checkpoint=cp),dict(start_x=40,goal_x=3161))
        ends=[r for r in rows if r['event']=='episode_end']
        if ends:
            old=dict(ends[-1]['result']);old['native_replay_verified']=bool(audit);E.require(old==result,'Whole prefix+tail grade differs')
        else:E.require(not audit,'Missing child end');append(path,dict(event='episode_end',episode_id=eid,result=result))
        childrows=read_events(path);joined=parentrows+childrows;validate_actual_receipts(joined,pm['policy'])
        if audit:
            def count(events,event):return sum(r['event']==event for r in events)
            def errors(events):return sum(r['event']=='request_result' and r.get('valid') is not True for r in events)
            proof=dict(schema_version=1,verified=True,original_trial_id=slot['original_trial_id'],child_run_id=eid,parent_protocol_sha256=digest(pm),recovery_protocol_sha256=digest(m),
                parent_episode_sha256=slot['parent_episode_sha256'],child_episode_sha256=sha(path),declared_checkpoint=slot['checkpoint'],reconstructed_checkpoint=cp,
                original_attempt_count=sum(r['event']=='request_intent' for r in parentrows),recovery_attempt_count=sum(r['event']=='request_intent' for r in childrows),
                joined_attempt_count=sum(r['event']=='request_intent' for r in joined),total_native_frames=game.frame,new_native_frames=result['continuation_native_frames'],total_native_frame_budget=6000,
                provider_outcome_unknown_attempt_count=unknown_attempts(parentrows),new_provider_outcome_unknown_attempt_count=unknown_attempts(childrows),total_provider_outcome_unknown_attempt_count=unknown_attempts(joined),
                inherited_parent_valid_choice_count=int(slot['continuation_mode']=='reuse_recorded_valid_response'),no_observed_valid_choice_discarded=True,
                inherited_parent_valid_response_sha256=slot.get('inherited_parent_valid_response_sha256'),inherited_parent_receipt_id_sha256=slot.get('inherited_parent_receipt_id_sha256'),
                prefix_replay_verified=True,failed_body_identical=True,controller_pin_history_rng_verified=True,total_native_budget_verified=True,result=result)
            for label,events in (('original',parentrows),('recovery',childrows),('joined',joined)):
                proof[label+'_request_result_count']=count(events,'request_result');proof[label+'_error_attempt_count']=errors(events)
                proof[label+'_unanswered_attempt_count']=count(events,'request_intent')-count(events,'request_result')
            write_json(path.with_suffix('.audit.json'),proof)
        return dict(result,**costs_from_events(joined))
    finally:
        if client:client.close()
        game.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    inspect=sub.add_parser('inspect');inspect.add_argument('--parent',type=Path,required=True);inspect.add_argument('--episode-id',required=True)
    freeze=sub.add_parser('plan');freeze.add_argument('--parent',type=Path,required=True);freeze.add_argument('--output',type=Path,required=True);freeze.add_argument('--prefix-proof',type=Path,required=True)
    execute=sub.add_parser('run');execute.add_argument('--output',type=Path,required=True);execute.add_argument('--audit',action='store_true')
    a=p.parse_args()
    if a.command=='inspect':value=inspect_prefix(a.parent,a.episode_id)
    elif a.command=='plan':value=plan(a.output,a.parent,a.prefix_proof)
    else:
        m,pm=verify(a.output,approval=not a.audit)
        with (a.output/'orchestrator.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            if not a.audit:load_key()
            value=[execute_one(a.output,m,pm,slot,audit=a.audit) for slot in m['slots']]
            write_json(a.output/('audit-summary.json' if a.audit else 'summary.json'),dict(protocol_sha256=digest(m),verified=bool(a.audit),episodes=value))
    print(json.dumps(value,indent=2))


if __name__=='__main__':main()
