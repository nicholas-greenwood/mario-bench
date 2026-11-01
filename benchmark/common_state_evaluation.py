"""Independent, preregistered state-only evaluation:22models×3fresh episodes.

This new authority imports the unchanged compact-v2 native controller/engine. It
cannot authorise images or the older combined suite, and never reuses pilot runs.
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
from benchmark import common_state_run_v2 as engine
from benchmark.client import digest
from benchmark.run import load_key,write_json,safe_name

ROOT=Path(__file__).resolve().parents[1]
EXTRA_SOURCES=['benchmark/common_state_evaluation.py','benchmark/common_state_results.py','benchmark/common_results.py']
PROTOCOL_ID='mario-common-state-compact-v2-evaluation-v1'


def source_hashes():
    return dict(engine.locked_sources(),**{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in EXTRA_SOURCES})


def schedule(models,cohort_id):
    return [dict(episode_id=f'{cohort_id}-{safe_name(m["id"])}-repeat{r}',model_id=m['id'],track='state',temperature=None,repeat_id=r,local_rng_seed=None,emulator_seed=0) for m in models for r in (0,1,2)]


def authority(calibration,preflight):
    calibration=Path(calibration);preflight=Path(preflight);selected=engine.validated_selection(calibration/'selection.json');p=engine.validate_preflight(preflight/'summary.json')
    cm=json.loads((calibration/'manifest.json').read_text());pm=json.loads((preflight/'manifest.json').read_text())
    engine.require(selected['promotion_eligible'] and selected['state_native_clears']>=1,'State calibration native-clear gate failed')
    engine.require(cm['preflight_report_sha256']==hashlib.sha256((preflight/'summary.json').read_bytes()).hexdigest(),'State calibration used a different preflight')
    engine.require(cm['software_sha256']==engine.locked_sources()==selected['software_sha256'],'Frozen state controller/engine changed')
    evidence=dict(state_gate_passed=True,state_native_clear_count=selected['state_native_clears'],state_preflight_model_count=len(p['results']),state_pilot_episode_count=4,state_preflight_audit_complete=True,state_pilot_audit_complete=True,state_preflight_protocol_sha256=digest(pm),state_preflight_report_sha256=hashlib.sha256((preflight/'summary.json').read_bytes()).hexdigest(),state_preflight_audit_sha256=hashlib.sha256((preflight/'audit.json').read_bytes()).hexdigest(),state_pilot_protocol_sha256=digest(cm),state_pilot_summary_sha256=selected['pilot_summary_sha256'],state_pilot_audit_sha256=selected['pilot_audit_sha256'],state_selection_sha256=hashlib.sha256((calibration/'selection.json').read_bytes()).hexdigest(),state_controller_sha256=hashlib.sha256((ROOT/'benchmark/common_profiles/state-compact-v2.json').read_bytes()).hexdigest())
    engine.require(evidence['state_preflight_model_count']==22,'All22 actual state contracts must be audited')
    return cm,evidence


def plan(output,calibration,preflight,concurrency=22):
    cm,evidence=authority(calibration,preflight);models,_,_=engine.roster();now=datetime.now(timezone.utc);cohort='state-v2-eval-'+now.strftime('%Y%m%dT%H%M%S%fZ');m=deepcopy(cm)
    m.update(protocol_id=PROTOCOL_ID,phase='evaluation',evaluation_scope='state_only',tracks=['state'],preregistered=True,frozen_at_utc=now.isoformat(),cohort_id=cohort,repeat_schedule=schedule(models,cohort),native_frame_cap=6000,native_frame_budget=6000,life_budget=1,cadence_native_frames=4,models=models,image_eligible_models=[],image_evaluation_status='calibration_pending',software_sha256=source_hashes(),concurrency=min(concurrency,22),pilot_selection_evidence=evidence,authority_paths=dict(calibration=str(Path(calibration).resolve()),preflight=str(Path(preflight).resolve())),observation_and_controller_hashes=dict(state_controller_sha256=evidence['state_controller_sha256'],state_engine_sources_sha256=digest(engine.locked_sources())),provider_seed=None)
    output=Path(output);output.mkdir(parents=True,exist_ok=True);engine.require(not (output/'manifest.json').exists(),'Never overwrite an evaluation registration')
    write_json(output/'manifest.json',m);write_json(output/'preregistration.json',dict(protocol_sha256=digest(m),frozen_at_utc=m['frozen_at_utc'],evaluation_scope='state_only',policy='openrouter',expected_episodes=66))
    return m


def verify(m,output):
    output=Path(output);registration=json.loads((output/'preregistration.json').read_text())
    engine.require(registration['protocol_sha256']==digest(m) and registration['frozen_at_utc']==m['frozen_at_utc'],'State evaluation registration modified')
    engine.require(m['protocol_id']==PROTOCOL_ID and m['phase']=='evaluation' and m['evaluation_scope']=='state_only' and m['tracks']==['state'],'Incorrect independent evaluation scope')
    engine.require(m['policy']=='openrouter' and m['preregistered'] is True,'Only actual preregistered API evaluation is supported')
    engine.require(m['native_frame_cap']==m['native_frame_budget']==6000 and m['life_budget']==1 and m['cadence_native_frames']==4 and m['no_stall_abort'] is True,'Native envelope changed')
    engine.require(m['software_sha256']==source_hashes(),'Frozen evaluation/controller/scoring/export source changed')
    engine.require(m['actual_rom_sha256']==engine.actual_rom_sha256()==m['endpoint_calibration']['rom_sha256'],'Installed ROM differs from actual calibration')
    models,_,_=engine.roster();engine.require(m['models']==models and m['repeat_schedule']==schedule(models,m['cohort_id']) and len(m['repeat_schedule'])==66,'Evaluation roster or exact3-repeat schedule changed')
    _,evidence=authority(m['authority_paths']['calibration'],m['authority_paths']['preflight']);engine.require(m['pilot_selection_evidence']==evidence,'Actual state calibration/preflight/audit evidence changed')
    engine.require(m['observation_and_controller_hashes']['state_controller_sha256']==evidence['state_controller_sha256'],'State controller identity mismatch')


def worker(output,m,jobs,audit):
    output=Path(output);(output/'workers').mkdir(exist_ok=True);rows=[];model_id=jobs[0]['model_id'];lease=output/'workers'/(safe_name(model_id)+'.json')
    for job in jobs:
        write_json(lease,dict(pid=os.getpid(),model_id=model_id,episode_id=job['episode_id'],status='auditing' if audit else 'running',protocol_sha256=digest(m)))
        rows.append(engine.execute_episode(output,m,job,audit=audit))
    write_json(lease,dict(pid=os.getpid(),model_id=model_id,status='finished',protocol_sha256=digest(m)));return rows


def run(output,audit=False,reserved=()):
    output=Path(output);m=json.loads((output/'manifest.json').read_text());verify(m,output)
    with (output/'orchestrator.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);lock.seek(0);lock.truncate();lock.write(json.dumps(dict(pid=os.getpid(),audit=audit,started_at_utc=datetime.now(timezone.utc).isoformat(),reserved_models=list(reserved))));lock.flush()
        if not audit:load_key()
        groups=defaultdict(list)
        for job in m['repeat_schedule']:
            if job['model_id'] not in reserved:groups[job['model_id']].append(job)
        engine.require(set(reserved)<=set(x['id'] for x in m['models']),'Unknown reserved provider pin')
        rows=[];failures=[]
        with ProcessPoolExecutor(max_workers=min(m['concurrency'],len(groups)),mp_context=multiprocessing.get_context('spawn')) as pool:
            futures={pool.submit(worker,str(output),m,jobs,audit):mid for mid,jobs in groups.items()}
            for f in as_completed(futures):
                try:
                    batch=f.result();rows.extend(batch);print(json.dumps(dict(model=futures[f],statuses=[r['status'] for r in batch],progress=[r['progress_pct'] for r in batch])),flush=True)
                except Exception as e:failures.append(dict(model=futures[f],error=type(e).__name__+': '+str(e)));print(json.dumps(failures[-1]),flush=True)
                if not audit:engine.summarize(output,m,rows,failures)
        if audit:
            engine.require(not reserved,'Full evaluation audit cannot omit reserved models')
            hashes={j['episode_id']:hashlib.sha256((output/'episodes'/(j['episode_id']+'.jsonl')).read_bytes()).hexdigest() for j in m['repeat_schedule']}
            write_json(output/'audit.json',dict(verified=not failures and len(rows)==66,protocol_sha256=digest(m),episodes=rows,worker_failures=failures,source_log_sha256=hashes))
        else:engine.summarize(output,m,rows,failures)
        engine.require(not failures,'Worker failures preserved; evaluation remains incomplete')


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True);x=sub.add_parser('plan');x.add_argument('--output',type=Path,required=True);x.add_argument('--calibration',type=Path,required=True);x.add_argument('--preflight',type=Path,required=True);x.add_argument('--concurrency',type=int,default=22)
    for name in ('execute','audit'):
        x=sub.add_parser(name);x.add_argument('--output',type=Path,required=True);x.add_argument('--reserved-models',nargs='*',default=[])
    a=p.parse_args()
    if a.command=='plan':
        m=plan(a.output,a.calibration,a.preflight,a.concurrency);print(json.dumps(dict(protocol_sha256=digest(m),manifest=str(a.output/'manifest.json'),episodes=66,tracks=['state'],paid_calls=0),indent=2))
    else:run(a.output,audit=a.command=='audit',reserved=a.reserved_models)

if __name__=='__main__':main()
