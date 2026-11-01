"""Release-only partial image48 snapshots; audits copies and never sends requests."""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
import multiprocessing
from pathlib import Path
import shutil
import tempfile

from benchmark import common_image_final_run as engine
from benchmark.common_image_final_results import public_manifest, aggregates, cost, load_registration
from benchmark.common_state_release import attempt_evidence, sha, utc, validate_trial_cost
from benchmark.client import digest
from benchmark.public_results import public_native_response
from benchmark.run import read_events, write_json

PROTOCOL_SHA256 = '2f11c42b8d47f8cd8959e828243acacb8abcf83c478a6206508ebd635004fdf1'
MANIFEST_SHA256 = '81eb6495bc0b6ce1da0ba6d4957efda2283ccbf9cc20c0b750dfcb0a7a9ea8a3'
REGISTRATION_SHA256 = '9fd345aafefd0bb27fb28916afc173600e01c66c53eb486a2ac4b1c7b8504fc7'
EVENTS = {'episode_start','request_intent','request_result','action','chunk_end','episode_end'}


def validate_log(rows, job, manifest, cutoff):
    eid=job['episode_id']
    engine.require(rows and rows[-1]['event']=='episode_end', 'Only durably closed image logs may publish')
    engine.require(all(r['event'] in EVENTS and r.get('episode_id')==eid for r in rows), 'Unknown or differently scoped image event')
    starts=[r for r in rows if r['event']=='episode_start'];ends=[r for r in rows if r['event']=='episode_end']
    engine.require(len(starts)==len(ends)==1 and starts[0]['job']==job and starts[0]['protocol_sha256']==digest(manifest), 'Image start/job/protocol differs')
    engine.require(utc(manifest['frozen_at_utc'])<=utc(starts[0]['utc'])<=utc(ends[0]['utc'])<=utc(cutoff), 'Image episode is outside its fresh capture window')


def validate_census(manifest,capture,census):
    jobs={j['episode_id']:j for j in manifest['repeat_schedule']};items=census['episodes']
    engine.require(census['protocol_sha256']==digest(manifest) and census['captured_at_utc']==capture['captured_at_utc']
                   and len(items)==len(jobs)==census['scheduled']==48 and {r['episode_id'] for r in items}==set(jobs), 'Census must retain all48 prescribed slots at the same cutoff')
    closed={}
    for row in items:
        job=jobs[row['episode_id']]
        engine.require(type(row['closed_at_cutoff']) is bool and all(row[k]==job[k] for k in ('model_id','repeat_id','local_rng_seed')), 'Census slot/seed/closure differs')
        if row['closed_at_cutoff']:
            engine.require(utc(row['terminal_utc'])<=utc(capture['captured_at_utc']), 'Census includes an episode after cutoff')
            closed[row['episode_id']]=row['source_episode_sha256']
    engine.require(closed==capture['source_episode_sha256'] and len(closed)==census['closed'] and census['pending']==48-len(closed), 'A completed cutoff episode was omitted or altered')


def validate_snapshot(snapshot, *, preflight=None):
    snapshot=Path(snapshot).resolve()
    engine.require(not (snapshot/'orchestrator.lock').exists(), 'Use an isolated snapshot, never an active worker output')
    engine.require(not any(p.is_symlink() for p in snapshot.rglob('*')), 'Snapshot symlinks forbidden')
    engine.require(sha(snapshot/'manifest.json')==MANIFEST_SHA256 and sha(snapshot/'preregistration.json')==REGISTRATION_SHA256, 'Frozen image registration bytes differ')
    manifest=load_registration(snapshot,preflight)
    engine.require(digest(manifest)==PROTOCOL_SHA256 and len(manifest['models'])==16 and len(manifest['repeat_schedule'])==48, 'Exact image48 authority required')
    capture=json.loads((snapshot/'capture.json').read_text())
    engine.require(capture['protocol_sha256']==PROTOCOL_SHA256 and capture['source_manifest_sha256']==MANIFEST_SHA256
                   and capture['source_preregistration_sha256']==REGISTRATION_SHA256, 'Capture registration binding differs')
    engine.require(utc(capture['captured_at_utc'])>=utc(manifest['frozen_at_utc']), 'Capture precedes freeze')
    validate_census(manifest,capture,json.loads((snapshot/'census.json').read_text()))
    jobs={j['episode_id']:j for j in manifest['repeat_schedule']};captured=capture['source_episode_sha256']
    files={p.stem:p for p in (snapshot/'episodes').glob('*.jsonl')}
    engine.require(isinstance(captured,dict) and set(files)==set(captured)<=set(jobs), 'Snapshot includes missing, unscheduled or historical episodes')
    hashes={name:sha(snapshot/name) for name in ('manifest.json','preregistration.json','capture.json','census.json')}
    for name,expected in manifest['software_sha256'].items():
        relative='sources/'+name;engine.require(sha(snapshot/relative)==expected, 'Frozen source copy differs');hashes[relative]=expected
    for eid,path in files.items():
        engine.require(path.read_bytes().endswith(b'\n') and sha(path)==captured[eid], 'Closed episode bytes differ from stable capture')
        validate_log(read_events(path),jobs[eid],manifest,capture['captured_at_utc'])
        hashes[str(path.relative_to(snapshot))]=captured[eid]
        sidecar=path.with_suffix('.cost.json')
        if sidecar.exists():
            cost(path);hashes[str(sidecar.relative_to(snapshot))]=sha(sidecar)
    return manifest,capture,hashes


def project_trial(directory, manifest, job, result):
    eid=job['episode_id'];path=Path(directory)/'episodes'/(eid+'.jsonl');rows=read_events(path)
    attempts,proof,ids=attempt_evidence(rows)
    engine.require(result['episode_id']==eid and result['protocol_sha256']==PROTOCOL_SHA256 and result['native_replay_verified'] is True, 'Image audit result authority differs')
    groups=defaultdict(list)
    for row in rows:
        if 'decision_index' in row:groups[row['decision_index']].append(row)
    actions=[];identities=set();consumed=set()
    for index,records in sorted(groups.items()):
        controls=[r for r in records if r['event']=='action'];chunks=[r for r in records if r['event']=='chunk_end']
        if not controls:
            engine.require(not chunks and result['status']=='infra_error' and index==result['decisions'], 'Unconsumed request/checkpoint after native termination')
            continue
        receipts=[r for r in records if r['event']=='request_result' and r.get('valid')]
        engine.require(len(controls)==len(chunks)==len(receipts)==1 and index==len(actions), 'Image action/receipt/checkpoint is not one committed sequence')
        action,chunk,response=controls[0],chunks[0],receipts[0];raw=response['raw_response'];identities.add((raw['model'],raw['provider']));consumed.add(index)
        actions.append(dict(index=index,frame_before=action['frame_before'],frame_after=chunk['frame'],sequence=[[chunk['actual_frames'],action['buttons']]],
                            requested_frames=action['requested_frames'],actual_frames=chunk['actual_frames'],request_sha256=response['request_sha256'],
                            native_response=public_native_response(raw),chosen_action={k:v for k,v in action.items() if k not in ('event','episode_id','utc')},
                            after_observation_sha256=chunk['observation_sha256'],screen_after_sha256=chunk['screen_sha256'],native_frame_hashes=chunk['native_frame_hashes']))
    engine.require(len(actions)==result['decisions']==len(ids) and sum(a['actual_frames'] for a in actions)==result['frames'], 'Image valid responses/actions/native frames differ')
    engine.require(all(a['frame_after']==b['frame_before'] for a,b in zip(actions,actions[1:])), 'Native trace has a gap or duplicate')
    proof.update(source_episode_sha256=sha(path),native_audit_sha256=sha(path.with_suffix('.audit.json')),started_at_utc=rows[0]['utc'],terminal_at_utc=rows[-1]['utc'])
    trace=dict(schema_version=1,id=eid,phase='evaluation',protocol_sha256=PROTOCOL_SHA256,model_id=job['model_id'],track='image',mode='image',level='1-1',
               actions=actions,request_attempts=attempts,attempt_proof=proof,source_episode_sha256=sha(path),native_replay_verified=True)
    keep=('status','rankable','progress_pct','max_progress_x','repeat_id','local_rng_seed','emulator_seed','temperature','native_frames_to_completion',
          'native_frame_budget','life_budget','native_replay_verified','started_at_utc','decisions','flag_get','death','technical_pending')
    model=next(m for m in manifest['models'] if m['id']==job['model_id']);actual=sorted(identities)
    trial={k:result[k] for k in keep}
    trial.update(id=eid,episode_id=eid,model_id=job['model_id'],display_name=model['name'],track='image',mode='image',phase='evaluation',protocol_id=manifest['protocol_id'],
                 protocol_sha256=PROTOCOL_SHA256,level='1-1',native_frames=result['frames'],completed=result['flag_get'],verified=True,cadence_native_frames=7,
                 returned_model=actual[0][0] if actual else None,provider=actual[0][1] if actual else None,
                 actual_returned_model_provider_pairs=[dict(model=a,provider=b) for a,b in actual],trace_href='common-image/traces/'+eid+'.json',trace_sha256=digest(trace),
                 profile_href='common-image/profiles/protocol.json',replay_href=None,replay_sha256=None,attempt_proof=proof,**validate_trial_cost(cost(path),proof))
    return trial,trace,ids


def audit_copy(task):
    directory,manifest,job=task
    return engine.execute_episode(directory,manifest,job,audit=True)


def export(snapshot,destination,*,preflight=None,jobs=1):
    snapshot,destination=Path(snapshot).resolve(),Path(destination).resolve()
    engine.require(snapshot!=destination and not destination.is_relative_to(snapshot) and not snapshot.is_relative_to(destination), 'Snapshot and public destination must be separate')
    engine.require(type(jobs) is int and 1<=jobs<=8, 'Audit jobs must be1..8')
    manifest,capture,hashes=validate_snapshot(snapshot,preflight=preflight);adapter_hash=sha(__file__)
    with tempfile.TemporaryDirectory(prefix='mario-image-release-audit-') as temporary:
        copied=Path(temporary)
        for relative,expected in hashes.items():
            source,target=snapshot/relative,copied/relative
            engine.require(sha(source)==expected,'Snapshot changed before copy');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            engine.require(sha(source)==sha(target)==expected,'Snapshot changed during copy')
        selected=[j for j in manifest['repeat_schedule'] if j['episode_id'] in capture['source_episode_sha256']]
        tasks=[(str(copied),manifest,j) for j in selected]
        if jobs==1:results=[audit_copy(task) for task in tasks]
        else:
            with ProcessPoolExecutor(max_workers=jobs,mp_context=multiprocessing.get_context('spawn')) as pool:results=list(pool.map(audit_copy,tasks))
        trials=[];traces={};ids=set()
        for job,result in zip(selected,results):
            trial,trace,receipts=project_trial(copied,manifest,job,result)
            engine.require(not ids.intersection(receipts),'One receipt reused across image trials');ids.update(receipts);trials.append(trial);traces[trial['id']]=trace
        header=public_manifest(manifest);rows=aggregates(manifest,trials)
        provenance=dict(schema_version=1,release_status='partial_evaluation_snapshot',protocol_sha256=PROTOCOL_SHA256,source_manifest_sha256=MANIFEST_SHA256,
                        source_preregistration_sha256=REGISTRATION_SHA256,release_adapter_sha256=adapter_hash,capture_sha256=hashes['capture.json'],census_sha256=hashes['census.json'],captured_at_utc=capture['captured_at_utc'],
                        expected_trials=48,expected_models=16,native_audited_trials=len(trials),complete_model_rows=sum(r['coverage_complete'] for r in rows),pilot_episodes_included=0,
                        source_log_sha256=capture['source_episode_sha256'],billing_sidecar_sha256={k:v for k,v in hashes.items() if k.endswith('.cost.json')})
        value=dict(schema_version=1,common_benchmark=dict(manifest=header,trials=trials,rows=rows,release_provenance=provenance))
        profile=dict(schema_version=1,manifest=header,controller_contracts=manifest['controller_contracts'],software_sha256=manifest['software_sha256'])
        public=json.dumps(dict(index=value,profile=profile,traces=traces))
        engine.require(not any(token in public for token in ('/Users/','OPENROUTER_API_KEY','sk-or-','gen-')), 'Private paths, credentials or raw API IDs in public output')
        _,_,final_hashes=validate_snapshot(snapshot,preflight=preflight)
        engine.require(final_hashes==hashes and sha(__file__)==adapter_hash,'Snapshot/billing/adapter changed during audit')
        root=destination/'common-image'
        if (root/'index.json').exists():
            old=json.loads((root/'index.json').read_text())['common_benchmark']
            engine.require(old['manifest']['protocol_sha256']==PROTOCOL_SHA256 and {r['id'] for r in old['trials']}<=set(traces),'Partial refresh cannot change authority or remove published trials')
        (root/'traces').mkdir(parents=True,exist_ok=True);(root/'profiles').mkdir(exist_ok=True)
        for eid,trace in traces.items():
            path=root/'traces'/(eid+'.json');write_json(path,trace);next(r for r in trials if r['id']==eid)['trace_sha256']=sha(path)
        write_json(root/'profiles/protocol.json',profile);write_json(root/'index.json',value)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--preflight',type=Path);parser.add_argument('--jobs',type=int,default=1);args=parser.parse_args()
    value=export(args.snapshot,args.destination,preflight=args.preflight,jobs=args.jobs)['common_benchmark']
    print(json.dumps(dict(trials=len(value['trials']),rows=len(value['rows']),complete_model_rows=sum(r['coverage_complete'] for r in value['rows']))))


if __name__=='__main__':main()
