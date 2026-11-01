"""Explicit same-checkpoint technical continuations of eight immutable state slots.

A new transport authority, never a replacement execution of the original cohort.
A matched timeout may have been processed/billed upstream. Only absence of an
observed valid discarded decision is asserted. No native input is inferred here.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
from benchmark import common_state_evaluation as base
from benchmark.client import Client,digest
from benchmark.costs import costs_from_events
from benchmark.run import append,read_events,write_json,load_key
from benchmark.scoring import validated_progress_x,score_episode
from prototype.emulator import MarioGame

ROOT=Path(__file__).resolve().parents[1]
E=base.engine
PROTOCOL_ID='mario-state-technical-recovery-v1'
PIN_KEYS=('id','request_model','provider','expected_returned_model','expected_returned_provider_names')
CHECKPOINT_KEYS=('checkpoint_native_frame','checkpoint_ram_sha256','checkpoint_rgb_sha256','checkpoint_observation_sha256','controller_history_sha256','failed_request_sha256','controller_sha256','pin_sha256','rng_mode','rng_state_sha256')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def checkpoint(game,history,body,model,controller):
    return dict(checkpoint_native_frame=game.frame,checkpoint_ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),checkpoint_rgb_sha256=E.screen_hash(game),checkpoint_observation_sha256=digest(game.observe()),controller_history_sha256=digest(history[-3:]),failed_request_sha256=digest(body),controller_sha256=controller,pin_sha256=digest({k:model[k] for k in PIN_KEYS if k in model}),rng_mode='not_used_native_choice',rng_state_sha256=None)

def original(parent):
    parent=Path(parent);m=read(parent/'manifest.json');base.verify(m,parent);audit=E.verified_audit(parent,m)
    E.require(audit['verified'] and len(audit['episodes'])==66,'Full original66 audit required')
    return m,audit

def validate_prefix_binding(m,proof):
    E.require(proof.get('verified') is True and proof.get('all66_original_episode_files_unchanged') is True and proof.get('valid_slots_excluded_from_recovery')==58,'Invalid independent original-prefix audit')
    records={(r['model_id'],r['repeat_id']):r for r in proof['proofs']}
    E.require(len(records)==len(m['slots'])==8,'Prefix proof slot coverage differs')
    mapping={'parent_episode_sha256':'episode_sha256','checkpoint_native_frame':'prefix_native_frames','checkpoint_ram_sha256':'checkpoint_rawRAM_sha256','checkpoint_rgb_sha256':'checkpoint_RGB_sha256','checkpoint_observation_sha256':'checkpoint_observation_sha256','controller_history_sha256':'checkpoint_session_history_sha256','parent_valid_native_actions':'prefix_decisions','parent_http_attempts':'intents','remaining_native_frame_budget':'remaining_native_frame_budget'}
    for slot in m['slots']:
        record=records[slot['model_id'],slot['repeat_id']];f=record['failed_checkpoint']
        E.require(all(slot[k]==record[v] for k,v in mapping.items()),'Independent prefix checkpoint/source differs')
        E.require(slot['failed_request_sha256']==f['request_sha256'] and slot['failed_attempt_chain']==f['failed_attempt_chain'] and slot['failure_kind']==f['failure_kind'] and slot['provider_outcome_unknown_attempt_count']==f['provider_outcome_unknown_timeout_attempts'],'Failed attempt chain differs from independent source audit')
        E.require(record['unmatched_ledger_intents']==record['valid_discarded_choices_at_failed_index']==0 and slot['no_observed_valid_choice_discarded'] is True,'Unmatched or discarded valid choice cannot be resent')
        E.require(slot['rng_mode']=='not_used_native_choice' and slot['rng_state_sha256'] is None and slot['remaining_native_frame_budget']==6000-slot['checkpoint_native_frame'],'State recovery native/RNG envelope changed')


def plan(output,parent,inventory,prefix_proof):
    output=Path(output);E.require(not(output/'manifest.json').exists(),'Never overwrite a recovery registration')
    pm,a=original(parent);inv=read(inventory);proof=read(prefix_proof)
    E.require(inv['parent_protocol_sha256']==digest(pm)==proof['cohort_protocol_sha256'] and proof['verified'] is True,'Wrong parent/prefix authority')
    eligible={r['episode_id'] for r in a['episodes'] if r['status']=='infra_error'}
    E.require(len(eligible)==8 and {s['original_trial_id'] for s in inv['slots']}==eligible,'Recovery must include all and only eight technical slots')
    slots=deepcopy(inv['slots']);E.require(sum(s['provider_outcome_unknown_attempt_count'] for s in slots)==5,'Five upstream-uncertain timeouts must be retained')
    for s in slots:
        E.require(sha(s['parent_episode_path'])==s['parent_episode_sha256'] and s['parent_abort_status']=='infra_error','Original abort source changed')
        E.require(s['child_run_id']==s['original_trial_id']+'--technical-recovery-v1','One fixed child per original slot')
    m=dict(schema_version=1,protocol_id=PROTOCOL_ID,phase='technical_recovery',preregistered=True,policy='openrouter',frozen_at_utc=datetime.now(timezone.utc).isoformat(),parent_protocol_sha256=digest(pm),parent_manifest_file_sha256=sha(Path(parent)/'manifest.json'),parent_audit_sha256=sha(Path(parent)/'audit.json'),parent_output=str(Path(parent).resolve()),prefix_proof_path=str(Path(prefix_proof).resolve()),prefix_proof_sha256=sha(prefix_proof),software_sha256=dict(base.source_hashes(),**{'benchmark/common_state_recovery.py':sha(__file__)}),slots=slots,tracks=['state'],native_frame_budget=6000,native_frame_cap=6000,cadence_native_frames=4,life_budget=1,max_continuations_per_slot=1,retries_after_initial=2,timeout_seconds=pm['timeout_seconds'],provider_seed=None,emulator_seed=0,provider_outcome_unknown_attempt_count=5,transport_unknown_semantics='Matched timeouts may have been processed and billed upstream. No observed valid choice discarded; received valid pending choices must be reused.',concurrency=5)
    validate_prefix_binding(m,proof)
    output.mkdir(parents=True,exist_ok=True);write_json(output/'manifest.json',m);write_json(output/'preregistration.json',dict(protocol_sha256=digest(m),frozen_at_utc=m['frozen_at_utc'],parent_protocol_sha256=digest(pm)))
    return m

def verify(output,approval=False):
    output=Path(output);m=read(output/'manifest.json');r=read(output/'preregistration.json')
    E.require(m['protocol_id']==PROTOCOL_ID and m['phase']=='technical_recovery' and r['protocol_sha256']==digest(m) and r['frozen_at_utc']==m['frozen_at_utc'],'Recovery registration modified')
    E.require(m['software_sha256']==dict(base.source_hashes(),**{'benchmark/common_state_recovery.py':sha(__file__)}),'Frozen recovery/controller sources changed')
    E.require(m['native_frame_budget']==m['native_frame_cap']==6000 and m['cadence_native_frames']==4 and m['life_budget']==m['max_continuations_per_slot']==1 and m['retries_after_initial']==2,'Recovery envelope changed')
    parent=Path(m['parent_output']);pm,a=original(parent)
    E.require(m['policy']=='openrouter' and m['preregistered'] is True and m['provider_seed'] is None and m['emulator_seed']==pm['emulator_seed']==0 and m['timeout_seconds']==pm['timeout_seconds'],'Recovery transport/reset envelope changed')
    E.require(digest(pm)==m['parent_protocol_sha256'] and sha(parent/'manifest.json')==m['parent_manifest_file_sha256'] and sha(parent/'audit.json')==m['parent_audit_sha256'],'Parent authority changed')
    E.require(sha(m['prefix_proof_path'])==m['prefix_proof_sha256'],'Independent prefix proof changed')
    validate_prefix_binding(m,read(m['prefix_proof_path']))
    eligible={r['episode_id'] for r in a['episodes'] if r['status']=='infra_error'}
    E.require(len(m['slots'])==len(eligible)==8 and {s['original_trial_id'] for s in m['slots']}==eligible,'Incorrect recovery slot set')
    E.require(len({s['child_run_id'] for s in m['slots']})==8 and sum(s['provider_outcome_unknown_attempt_count'] for s in m['slots'])==5,'Child or timeout coverage changed')
    for s in m['slots']:
        E.require(s['child_run_id']==s['original_trial_id']+'--technical-recovery-v1' and sha(s['parent_episode_path'])==s['parent_episode_sha256'],'Parent source/child changed')
    if approval:
        approved=read(output/'independent-approval.json');E.require(approved['approved'] is True and approved['protocol_sha256']==digest(m),'Exact independent recovery/lineage approval missing')
    return m,pm

def advance(game,session,choice,index,eid,maximum,history):
    before=game.frame;native=[]
    for _ in range(min(choice['requested_frames'],6000-before)):
        observed=game.step(choice['buttons']);x=validated_progress_x(observed,40)
        if x is not None:maximum=max(maximum,x)
        native.append(dict(frame=game.frame,ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest(),screen_sha256=E.screen_hash(game)))
        if game.done or game.flag_get:break
    actual=game.frame-before;chunk=dict(event='chunk_end',episode_id=eid,decision_index=index,frame=game.frame,actual_frames=actual,observation_sha256=digest(game.observe()),screen_sha256=E.screen_hash(game),native_frame_hashes=native)
    session.advance(buttons=choice['buttons'],frame_after=game.frame,actual_frames=actual);history.append(dict(frame_before=before,frame_after=game.frame,actual_native_frames=actual,buttons=choice['buttons']))
    return maximum,chunk

def restore(slot,pm):
    controller=sha(ROOT/'benchmark/common_profiles/state-compact-v2.json');E.require(controller==slot['controller_sha256']==pm['observation_and_controller_hashes']['state_controller_sha256'],'Actual frozen controller identity changed')
    rows=read_events(Path(slot['parent_episode_path']));model=E.track_model(next(x for x in pm['models'] if x['id']==slot['model_id']),'state');s=E.CommonSession(model,'state');g=MarioGame(level='1-1');maximum=40.;history=[]
    try:
        start=next(r for r in rows if r['event']=='episode_start');E.require(digest(g.observe())==start['initial_observation_sha256'] and E.screen_hash(g)==start['initial_screen_sha256'],'Reset checkpoint changed')
        by=defaultdict(list)
        for r in rows:
            if 'decision_index' in r:by[r['decision_index']].append(r)
        for i in range(slot['failed_decision_index']):
            prior=by[i];s.begin_state(g.observe());body=s.body('motor');out,error=E.stage_call(s,'motor',body,path=None,episode_id=slot['original_trial_id'],index=i,game=g,prior=prior,audit=True,manifest=pm,client=None);E.require(not error,'Parent native choice unavailable')
            choice=s.choose(out['raw_response'],body);act=next(r for r in prior if r['event']=='action');expected=E.plain(dict(event='action',episode_id=slot['original_trial_id'],decision_index=i,frame_before=g.frame,observation_sha256=digest(g.observe()),**choice,frames=min(4,6000-g.frame)))
            E.require(all(act.get(k)==v for k,v in expected.items()),'Parent action mismatch');maximum,chunk=advance(g,s,choice,i,slot['original_trial_id'],maximum,history);old=next(r for r in prior if r['event']=='chunk_end');E.require(all(old.get(k)==v for k,v in chunk.items()),'Parent native RAM/RGB mismatch')
        E.require(not g.done and not g.flag_get,'Never recover a valid native terminal outcome');s.begin_state(g.observe());body=s.body('motor');cp=checkpoint(g,history,body,model,controller);E.require(cp=={k:slot[k] for k in CHECKPOINT_KEYS},'Reconstructed native/history/body/pin checkpoint changed')
        failed=by[slot['failed_decision_index']];intents=[r for r in failed if r['event']=='request_intent'];results=[r for r in failed if r['event']=='request_result'];E.require(len(intents)==len(results)==3 and not any(r['valid'] for r in results),'Unmatched intent or observed valid pending choice requires reuse, not new invocation')
        E.require(all(r['body']==body for r in intents),'Failed request body changed')
        return g,s,maximum,history,cp,rows
    except BaseException:g.close();raise

def validate_child_ledger(rows,slot):
    """Reject impossible committed histories before constructing any HTTP client."""
    if not rows:return
    eid=slot['child_run_id'];allowed={'continuation_start','request_intent','request_result','action','chunk_end','episode_end'}
    E.require(rows[0]['event']=='continuation_start' and sum(r['event']=='continuation_start' for r in rows)==1,'Child ledger has no unique initial authority')
    E.require(all(r.get('episode_id')==eid and r.get('event') in allowed for r in rows),'Foreign or unconsumed child ledger row')
    ends=[i for i,r in enumerate(rows) if r['event']=='episode_end'];E.require(not ends or ends==[len(rows)-1],'Child ledger advanced after its terminal result')
    groups=defaultdict(list)
    for row in rows:
        if row['event'] in {'request_intent','request_result','action','chunk_end'}:
            i=row.get('decision_index');E.require(type(i) is int and slot['failed_decision_index']<=i<1500,'Foreign decision index');groups[i].append(row)
    if groups:
        E.require(sorted(groups)==list(range(slot['failed_decision_index'],max(groups)+1)),'Skipped child decision')
        ordered=[r['decision_index'] for r in rows if r['event'] in {'request_intent','request_result','action','chunk_end'}]
        E.require(ordered==sorted(ordered),'Reordered child decision groups')
    for i,group in groups.items():
        attempts=[r for r in group if r['event'] in {'request_intent','request_result'}];intents=[r for r in attempts if r['event']=='request_intent'];results=[r for r in attempts if r['event']=='request_result']
        E.require(len(results)<=len(intents)<=len(results)+1 and len(intents)<=3,'Invalid or excessive retry scope')
        seen_valid=False
        for n,row in enumerate(attempts):
            E.require(not seen_valid,'Observed valid choice cannot be followed by another attempt')
            E.require(row.get('stage')=='motor' and row.get('attempt')==n//2 and row['event']==('request_intent' if n%2==0 else 'request_result'),'Unpaired or reordered child attempt')
            if row['event']=='request_result' and row.get('valid') is True:seen_valid=True
        actions=[r for r in group if r['event']=='action'];chunks=[r for r in group if r['event']=='chunk_end']
        E.require(len(actions)<=1 and len(chunks)<=len(actions) and (not actions or seen_valid),'Child action lacks unique valid choice')
        E.require([r['event'] for r in group]==[r['event'] for r in attempts]+['action']*len(actions)+['chunk_end']*len(chunks),'Reordered or unconsumed child stage/action/chunk')
        if i<max(groups):E.require(len(chunks)==1,'New child decision before prior chunk committed')


def execute_one(output,m,pm,slot,audit=False):
    eid=slot['child_run_id'];path=Path(output)/'episodes'/(eid+'.jsonl');path.parent.mkdir(exist_ok=True);prior_rows=read_events(path);validate_child_ledger(prior_rows,slot);g,s,maximum,history,cp,parentrows=restore(slot,pm);client=None;error=None;status=None;decisions=slot['parent_valid_native_actions'];by=defaultdict(list);visited=set()
    for r in prior_rows:
        if 'decision_index' in r:by[r['decision_index']].append(r)
    try:
        start=dict(event='continuation_start',episode_id=eid,protocol_sha256=digest(m),parent_protocol_sha256=m['parent_protocol_sha256'],resolves_original_trial_id=slot['original_trial_id'],parent_episode_sha256=slot['parent_episode_sha256'],checkpoint=cp,reconstructed_checkpoint=cp)
        starts=[r for r in prior_rows if r['event']=='continuation_start']
        if starts:E.require(len(starts)==1 and all(starts[0].get(k)==v for k,v in start.items()),'Child source authority/checkpoint changed')
        else:E.require(not audit and not prior_rows,'Missing child start');append(path,start)
        started=starts[0]['utc'] if starts else read_events(path)[0]['utc'];E.require(started>=m['frozen_at_utc'],'Child predates registration')
        if not audit and m['policy']!='fake':client=Client(os.environ['OPENROUTER_API_KEY'],s.model,m['timeout_seconds'],decoder=s.parse)
        for i in range(slot['failed_decision_index'],1500):
            if g.done or g.flag_get or g.frame>=6000:break
            visited.add(i);s.begin_state(g.observe());body=s.body('motor');prior=by[i]
            if i==slot['failed_decision_index']:E.require(digest(body)==slot['failed_request_sha256'],'First continuation body differs from exact failed body')
            out,error=E.stage_call(s,'motor',body,path=path,episode_id=eid,index=i,game=g,prior=prior,audit=audit,manifest=m,client=client)
            if error:status='infra_error';break
            choice=s.choose(out['raw_response'],body);action=E.plain(dict(event='action',episode_id=eid,decision_index=i,frame_before=g.frame,observation_sha256=digest(g.observe()),**choice,frames=min(4,6000-g.frame)));old=[r for r in prior if r['event']=='action']
            if old:E.require(len(old)==1 and all(old[0].get(k)==v for k,v in action.items()),'Child action differs on resume')
            else:E.require(not audit,'Missing child action');append(path,action)
            maximum,chunk=advance(g,s,choice,i,eid,maximum,history);old=[r for r in prior if r['event']=='chunk_end']
            if old:E.require(len(old)==1 and all(old[0].get(k)==v for k,v in chunk.items()),'Child native RAM/RGB differs on resume')
            else:E.require(not audit,'Missing child native checkpoint');append(path,chunk)
            decisions+=1
        E.require(set(by)<=visited,'Unconsumed child decisions after native terminal/budget/error')
        if status is None:status='completed' if g.flag_get else 'game_over' if g.done else 'frame_budget'
        result=score_episode(dict(id=eid,episode_id=eid,record_kind='technical_continuation',phase='technical_recovery',protocol_sha256=digest(m),parent_protocol_sha256=m['parent_protocol_sha256'],resolves_original_trial_id=slot['original_trial_id'],parent_episode_sha256=slot['parent_episode_sha256'],started_at_utc=started,model=slot['model_id'],model_id=slot['model_id'],track='state',level='1-1',repeat_id=slot['repeat_id'],local_rng_seed=None,temperature=None,emulator_seed=0,native_frame_budget=6000,life_budget=1,cadence_native_frames=4,status=status,technical_pending=status=='infra_error',completed=bool(g.flag_get),flag_get=bool(g.flag_get),death=bool(g.death),frames=g.frame,native_frames=g.frame,continuation_native_frames=g.frame-slot['checkpoint_native_frame'],decisions=decisions,continuation_decisions=decisions-slot['parent_valid_native_actions'],native_frames_to_completion=g.frame if g.flag_get else None,start_x=40,max_progress_x=maximum,error=error,native_replay_verified=bool(audit),checkpoint=cp,reconstructed_checkpoint=cp),dict(start_x=40,goal_x=3161))
        ends=[r for r in prior_rows if r['event']=='episode_end']
        if ends:
            old=dict(ends[-1]['result']);old['native_replay_verified']=bool(audit);E.require(old==result,'Child native/scored result differs')
        else:E.require(not audit,'Missing child end');append(path,dict(event='episode_end',episode_id=eid,result=result))
        childrows=read_events(path);joined=costs_from_events(parentrows+childrows)
        if audit:
            proof=dict(schema_version=1,verified=True,original_trial_id=slot['original_trial_id'],child_run_id=eid,parent_protocol_sha256=m['parent_protocol_sha256'],recovery_protocol_sha256=digest(m),parent_episode_sha256=slot['parent_episode_sha256'],child_episode_sha256=sha(path),declared_checkpoint=cp,reconstructed_checkpoint=cp,original_attempt_count=sum(r['event']=='request_intent' for r in parentrows),recovery_attempt_count=sum(r['event']=='request_intent' for r in childrows),joined_attempt_count=sum(r['event']=='request_intent' for r in parentrows+childrows),total_native_frames=g.frame,new_native_frames=g.frame-slot['checkpoint_native_frame'],total_native_frame_budget=6000,provider_outcome_unknown_attempt_count=slot['provider_outcome_unknown_attempt_count'],new_provider_outcome_unknown_attempt_count=sum(r.get('event')=='request_result' and r.get('error')=='TimeoutError' for r in childrows),total_provider_outcome_unknown_attempt_count=slot['provider_outcome_unknown_attempt_count']+sum(r.get('event')=='request_result' and r.get('error')=='TimeoutError' for r in childrows),no_observed_valid_choice_discarded=True,prefix_replay_verified=True,failed_body_identical=True,controller_pin_history_rng_verified=True,total_native_budget_verified=True,result=result)
            write_json(path.with_suffix('.audit.json'),proof)
        return dict(result,**joined)
    finally:
        if client:client.close()
        g.close()

def worker(output,m,pm,slots,audit):return [execute_one(output,m,pm,s,audit) for s in slots]
def run(output,audit=False):
    output=Path(output);m,pm=verify(output,approval=not audit)
    with (output/'orchestrator.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);lock.seek(0);lock.truncate();lock.write(json.dumps(dict(pid=os.getpid(),audit=audit)));lock.flush()
        if not audit:load_key()
        groups=defaultdict(list)
        for s in m['slots']:groups[s['model_id']].append(s)
        rows=[]
        with ProcessPoolExecutor(max_workers=5,mp_context=multiprocessing.get_context('spawn')) as pool:
            fs=[pool.submit(worker,str(output),m,pm,slots,audit) for slots in groups.values()]
            for f in as_completed(fs):
                batch=f.result();rows.extend(batch);print(json.dumps([{k:r[k] for k in ('id','status','native_frames','progress_pct')} for r in batch]),flush=True)
                write_json(output/('audit-summary.json' if audit else 'summary.json'),dict(protocol_sha256=digest(m),verified=audit and len(rows)==8,episodes=rows))

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True);x=sub.add_parser('plan');x.add_argument('--output',type=Path,required=True);x.add_argument('--parent',type=Path,required=True);x.add_argument('--inventory',type=Path,required=True);x.add_argument('--prefix-proof',type=Path,required=True)
    for name in ('verify','execute','audit'):
        x=sub.add_parser(name);x.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='plan':print(json.dumps(dict(protocol_sha256=digest(plan(a.output,a.parent,a.inventory,a.prefix_proof)),paid_calls=0)))
    elif a.command=='verify':m,_=verify(a.output);print(json.dumps(dict(verified=True,protocol_sha256=digest(m))))
    else:run(a.output,a.command=='audit')
if __name__=='__main__':main()
