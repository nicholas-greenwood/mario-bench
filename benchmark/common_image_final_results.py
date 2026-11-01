"""Separate public image progress-baseline projection; no inference or state inputs.

The execution engine does not import this module. Public acceptance/source hashes
are independently reviewed; failed historical pilot gates remain failed.
"""
from collections import Counter,defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from benchmark import common_image_final_run as engine
from benchmark.client import digest
from benchmark.costs import COST_FIELDS,validate_public_cost
from benchmark.run import read_events,write_json


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_registration(output,preflight=None):
    output=Path(output);m=json.loads((output/'manifest.json').read_text());engine.verify_manifest(m,output)
    engine.require(m['phase']=='evaluation' and m['policy']=='openrouter','Only the real registered48 image evaluation can publish this header')
    preflight=Path(preflight) if preflight else output.parent/'preflight-openrouter';s=engine.validate_preflight(preflight/'summary.json')
    engine.require(s['manifest_sha256']==m['preflight_provenance']['protocol_sha256'] and sha(preflight/'summary.json')==m['preflight_report_sha256'] and sha(preflight/'audit.json')==m['preflight_provenance']['audit_sha256'],'Final image registration used different actual16preflight')
    return m


def public_manifest(m):
    keys=('protocol_id','phase','evaluation_scope','tracks','frozen_at_utc','level','temperature','cadence_native_frames','requested_native_hold','native_frame_budget','life_budget','maximum_control_actions','repeat_schedule','media','sampling','software_sha256','roster_source_sha256','actual_rom_sha256','initial_observation_sha256','initial_screen_sha256','observation_and_controller_hashes','acceptance_contract')
    header={k:deepcopy(m[k]) for k in keys};header.update(protocol_sha256=digest(m),preregistered=True,emulator_seed=0,provider_seed=None,predeclared_local_sampler_seeds={'image':[101,102,103]},calibration_only_episodes_excluded=True)
    header['acceptance_contract']['track']='image' # public scope alias, no policy/input change
    header['eligible_model_provider_pairs']=[dict(model_id=x['id'],track='image',request_model=x.get('request_model',x['id']),expected_returned_model=x['expected_returned_model'],provider=deepcopy(x['provider']),expected_returned_provider_names=list(x['expected_returned_provider_names'])) for x in m['models']]
    return header


def aggregates(m,trials):
    groups=defaultdict(list);expected=defaultdict(list)
    for job in m['repeat_schedule']:expected[job['model_id']].append(job)
    known_ids=set();rows=[]
    for trial in trials:
        engine.require(trial['id'] not in known_ids,'Duplicate image trial');known_ids.add(trial['id']);groups[trial['model_id']].append(trial)
    engine.require(set(groups)<=set(expected),'Unexpected image model')
    for mid,jobs in expected.items():
        ids=[j['episode_id'] for j in jobs];by={j['episode_id']:j for j in jobs};records=groups[mid];valid=[];complete_cost=[]
        engine.require(len(jobs)==3 and len(set(ids))==3,'Exactly three predeclared image repeats required')
        for r in records:
            engine.require(r['id'] in by and r['phase']=='evaluation' and r['protocol_sha256']==digest(m),'Foreign image protocol/slot')
            job=by[r['id']];engine.require(all(r[k]==job[k] for k in ('model_id','track','repeat_id','temperature','emulator_seed','local_rng_seed')),'Wrong image seed/pin slot')
            engine.require(r['native_frame_budget']==6000 and r['life_budget']==1 and r['cadence_native_frames']==7 and r['native_replay_verified'] is True,'Unverified image envelope')
            engine.require(type(r['rankable']) is bool,'Rankable flag must be boolean')
            if r['rankable']:
                f=r['native_frames'];p=r['progress_pct'];engine.require(type(f) is int and 0<=f<=6000 and type(p) in (int,float) and math.isfinite(p) and 0<=p<=100,'Invalid native grade')
                if r['status']=='completed':engine.require(r['flag_get'] is True and r['death'] is False and p==100 and f>0 and r['native_frames_to_completion']==f,'Only confirmed native flag may score100')
                else:engine.require(r['status'] in ('game_over','frame_budget') and r['flag_get'] is False and p<=99.9 and r['native_frames_to_completion'] is None and (r['status']!='frame_budget' or f==6000),'Invalid failure/budget grade')
                valid.append(r)
            validate_public_cost(r)
            if r.get('cost_usd') is not None or r.get('cost_estimate_usd') is not None:complete_cost.append(r)
        full=len(records)==len(valid)==3 and {r['id'] for r in records}==set(ids);times=[r['native_frames_to_completion'] for r in valid if r['status']=='completed' and r['flag_get'] is True]
        full_cost=len(records)==len(complete_cost)==3;actual=full_cost and all(r.get('cost_usd') is not None for r in complete_cost);total=sum(r['cost_usd'] for r in complete_cost) if actual else None;estimate=sum(r['cost_usd'] if r.get('cost_usd') is not None else r['cost_estimate_usd'] for r in complete_cost) if full_cost and not actual else None
        rows.append(dict(model_id=mid,track='image',level='1-1',protocol_sha256=digest(m),expected_trial_ids=ids,recorded_trial_ids=[r['id'] for r in records],expected_trials=3,valid_trials=len(valid),coverage_complete=full,status_counts=dict(Counter(r['status'] for r in records)),mean_progress_pct=mean(r['progress_pct'] for r in valid) if full else None,clear_count=sum(r['flag_get'] for r in valid),clear_rate_pct=100*sum(r['flag_get'] for r in valid)/3 if full else None,best_clear_native_frames=min(times) if times else None,best_clear_game_seconds=min(times)/60 if times else None,mean_completed_native_frames=mean(times) if times else None,mean_completed_game_seconds=mean(times)/60 if times else None,n_completed=len(times),actual_cost_total_usd=total,cost_total_estimate_usd=estimate,mean_actual_cost_usd=total/3 if total is not None else None,mean_cost_estimate_usd=estimate/3 if estimate is not None else None,cost_coverage_counts=dict(expected_trials=3,recorded_trials=len(records),complete_cost_trials=len(complete_cost),actual_cost_trials=sum(r.get('cost_usd') is not None for r in complete_cost),estimated_cost_trials=sum(r.get('cost_estimate_usd') is not None for r in complete_cost),unknown_cost_trials=3-len(complete_cost))))
    return rows


def pending(output,preflight=None):
    m=load_registration(output,preflight);return dict(schema_version=1,common_benchmark=dict(manifest=public_manifest(m),trials=[],rows=aggregates(m,[])))


def cost(path):
    p=path.with_suffix('.cost.json')
    if not p.exists():return {k:None for k in COST_FIELDS}
    value=json.loads(p.read_text());engine.require(value['episode_sha256']==sha(path),'Billing source differs');result={k:value.get(k) for k in COST_FIELDS};validate_public_cost(result)
    events=read_events(path);intents=[r for r in events if r['event']=='request_intent'];responses=[r for r in events if r['event']=='request_result'];ident=lambda r:(r.get('decision_index'),r.get('stage'),r.get('attempt'))
    engine.require(len({ident(r) for r in intents})==len(intents) and len({ident(r) for r in responses})==len(responses) and {ident(r) for r in responses}<={ident(r) for r in intents},'Ambiguous cost attempt ledger')
    engine.require(not any(r['event'].startswith(('api_','request_')) and r['event'] not in ('request_intent','request_result') for r in events),'Unrecognised attempt/error event cannot certify cost')
    proof=result.get('cost_provenance') or {};count=len(intents);errors=sum(r.get('valid') is not True for r in responses)
    engine.require(all(proof.get(k)==count for k in ('request_count','source_request_count','source_attempt_count')) and proof.get('error_count')==errors,'Cost receipt scope omits actual requests/errors/pending attempts')
    if result.get('cost_usd') is not None or result.get('cost_estimate_usd') is not None:
        engine.require(len(intents)==len(responses),'Unanswered attempt cannot claim complete total cost')
    return result


def export(output,destination,*,preflight=None,pending_only=False):
    output=Path(output);m=load_registration(output,preflight);dest=Path(destination).resolve();pref=Path(preflight).resolve() if preflight else output.parent.resolve()/'preflight-openrouter'
    root=dest/'common-image'
    engine.require(not root.is_relative_to(output.resolve()) and not root.is_relative_to(pref),'Export destination must be outside worker/preflight output')
    root.mkdir(parents=True,exist_ok=True);trials=[]
    if not pending_only:
        audit=engine.verified_audit(output,m);engine.require(len(audit['episodes'])==48,'Final48 native audit required; never select development wins')
        indexed={r['episode_id']:r for r in audit['episodes']};(root/'traces').mkdir(exist_ok=True)
        for job in m['repeat_schedule']:
            eid=job['episode_id'];result=indexed[eid];path=output/'episodes'/(eid+'.jsonl');events=read_events(path);groups=defaultdict(list);attempts=[];actual=[]
            for r in events:
                if 'decision_index'in r:groups[r['decision_index']].append(r)
                if r['event']=='request_result':
                    attempts.append({k:r.get(k) for k in ('decision_index','stage','attempt','request_sha256','http_status','valid','error_type')})
                    if r.get('valid'):actual.append((r['raw_response']['model'],r['raw_response']['provider']))
            actions=[]
            for i,rs in sorted(groups.items()):
                a=next((r for r in rs if r['event']=='action'),None);c=next((r for r in rs if r['event']=='chunk_end'),None)
                if a is None:continue
                engine.require(c is not None,'Native action lacks checkpoint');receipt=next(r for r in rs if r['event']=='request_result' and r.get('valid'));raw=receipt['raw_response']
                actions.append(dict(index=i,frame_before=a['frame_before'],frame_after=c['frame'],sequence=[[c['actual_frames'],a['buttons']]],requested_frames=a['requested_frames'],actual_frames=c['actual_frames'],request_sha256=receipt['request_sha256'],native_response={k:raw[k] for k in ('model','provider','answers')},chosen_action={k:v for k,v in a.items() if k not in ('event','episode_id','utc')},after_observation_sha256=c['observation_sha256'],screen_after_sha256=c['screen_sha256'],native_frame_hashes=c['native_frame_hashes']))
            trace=dict(schema_version=1,id=eid,phase='evaluation',protocol_sha256=digest(m),model_id=job['model_id'],track='image',mode='image',level='1-1',actions=actions,request_attempts=attempts,source_episode_sha256=sha(path),native_replay_verified=True);trace_path=root/'traces'/(eid+'.json');write_json(trace_path,trace)
            keep=('status','rankable','progress_pct','max_progress_x','repeat_id','local_rng_seed','emulator_seed','temperature','native_frames_to_completion','native_frame_budget','life_budget','native_replay_verified','started_at_utc','decisions','flag_get','death','technical_pending')
            trial={k:result[k] for k in keep};model=next(x for x in m['models'] if x['id']==job['model_id']);ends=[r for r in events if r['event']=='episode_end'];intents=[r for r in events if r['event']=='request_intent'];responses=[r for r in events if r['event']=='request_result'];trial.update(id=eid,episode_id=eid,model_id=job['model_id'],display_name=model['name'],track='image',mode='image',phase='evaluation',protocol_id=m['protocol_id'],protocol_sha256=digest(m),level='1-1',native_frames=result['frames'],completed=result['flag_get'],verified=True,cadence_native_frames=7,returned_model=actual[0][0] if actual else None,provider=actual[0][1] if actual else None,trace_href='common-image/traces/'+eid+'.json',trace_sha256=sha(trace_path),profile_href='common-image/profiles/protocol.json',replay_href=None,replay_sha256=None,attempt_proof=dict(source_episode_sha256=sha(path),native_audit_sha256=sha(path.with_suffix('.audit.json')),request_intent_count=len(intents),request_result_count=len(responses),error_attempt_count=sum(r['valid'] is not True for r in responses),unanswered_attempt_count=len(intents)-len(responses),terminal_at_utc=ends[-1]['utc']),**cost(path));trials.append(trial)
    header=public_manifest(m);value=dict(schema_version=1,common_benchmark=dict(manifest=header,trials=trials,rows=aggregates(m,trials),release_provenance=dict(source_manifest_sha256=sha(output/'manifest.json'))));(root/'profiles').mkdir(exist_ok=True);write_json(root/'profiles/protocol.json',dict(schema_version=1,manifest=header,controller_contracts=m['controller_contracts']))
    raw=json.dumps(value);engine.require(not any(s in raw for s in ('/Users/','OPENROUTER_API_KEY','sk-or-','gen-dec-')),'Private paths/IDs/credentials cannot appear in public data');write_json(root/'index.json',value);return value


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--preflight',type=Path);p.add_argument('--pending',action='store_true');a=p.parse_args();v=export(a.output,a.destination,preflight=a.preflight,pending_only=a.pending);print(json.dumps(dict(trials=len(v['common_benchmark']['trials']),rows=len(v['common_benchmark']['rows']))))
if __name__=='__main__':main()
