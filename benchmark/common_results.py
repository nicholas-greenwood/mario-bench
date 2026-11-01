"""Export only fresh, audited, preregistered evaluation trials and their means."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from statistics import mean
from benchmark.client import digest
from benchmark.common_run import verified_audit,verify_manifest,require,track_model
from benchmark.costs import COST_FIELDS,validate_public_cost
from benchmark.run import read_events,write_json


def public_cost(path):
    proof=path.with_suffix('.cost.json')
    if not proof.exists():return {k:None for k in COST_FIELDS if k!='cost_provenance'}
    value=json.loads(proof.read_text());require(value['episode_sha256']==hashlib.sha256(path.read_bytes()).hexdigest(),'Billing sidecar belongs to different episode bytes')
    result={k:value.get(k) for k in COST_FIELDS};validate_public_cost(result);return result


def cost_means(trials,expected=3):
    complete=[r for r in trials if validate_public_cost(r)]
    actual=[r for r in complete if r.get('cost_usd') is not None]
    estimates=[r for r in complete if r.get('cost_usd') is None and r.get('cost_estimate_usd') is not None]
    full=len(trials)==expected and len(complete)==expected
    exact=sum(r['cost_usd'] for r in actual) if full and len(actual)==expected else None
    proxy=sum(r['cost_usd'] if r.get('cost_usd') is not None else r['cost_estimate_usd'] for r in complete) if full and estimates else None
    return dict(actual_cost_total_usd=exact,cost_total_estimate_usd=proxy,mean_actual_cost_usd=exact/expected if exact is not None else None,mean_cost_estimate_usd=proxy/expected if proxy is not None else None,cost_coverage_counts=dict(expected_trials=expected,recorded_trials=len(trials),complete_cost_trials=len(complete),actual_cost_trials=len(actual),estimated_cost_trials=len(estimates),unknown_cost_trials=expected-len(complete)))


def aggregate_trials(manifest,trials):
    grouped=defaultdict(list);expected=defaultdict(list)
    for j in manifest['repeat_schedule']:expected[(j['model_id'],j['track'])].append(j)
    seen=set()
    for r in trials:
        require(r['id'] not in seen,'Duplicate evaluation trial ID');seen.add(r['id']);grouped[(r['model_id'],r['track'])].append(r)
    require(set(grouped)<=set(expected),'Unexpected model/track group')
    rows=[]
    for (mid,track),jobs in expected.items():
        records=grouped[(mid,track)];ids=[j['episode_id'] for j in jobs];require(len(jobs)==3 and len(set(ids))==3,'Expected exactly3distinct preregistered repeats')
        by={j['episode_id']:j for j in jobs}
        for r in records:
            require(r['id'] in by and r['phase']=='evaluation' and r['protocol_sha256']==digest(manifest),'Trial identity/protocol is not preregistered')
            j=by[r['id']];require(all(r[k]==j[k] for k in ['model_id','track','repeat_id','local_rng_seed','emulator_seed','temperature']),'Trial condition differs from schedule')
            require(r['native_frame_budget']==6000 and r['life_budget']==1 and r['native_replay_verified'],'Unverified or differently budgeted evaluation')
        valid=[r for r in records if r['rankable']]
        complete=len(records)==3 and len(valid)==3 and {r['id'] for r in records}==set(ids)
        times=[r['native_frames_to_completion'] for r in valid if r['flag_get'] and r['status']=='completed']
        values=[r['progress_pct'] for r in valid];require(all(v is not None for v in values),'Rankable trial missing validated progress')
        row=dict(model_id=mid,track=track,protocol_sha256=digest(manifest),level='1-1',expected_trial_ids=ids,recorded_trial_ids=[r['id'] for r in records],expected_trials=3,valid_trials=len(valid),coverage_complete=complete,status_counts=dict(Counter(r['status'] for r in records)),mean_progress_pct=mean(values) if complete else None,clear_count=sum(r['flag_get'] for r in valid),clear_rate_pct=100*sum(r['flag_get'] for r in valid)/3 if complete else None,best_clear_native_frames=min(times) if times else None,best_clear_game_seconds=min(times)/60 if times else None,mean_completed_native_frames=mean(times) if times else None,mean_completed_game_seconds=mean(times)/60 if times else None,n_completed=len(times),**cost_means(records))
        rows.append(row)
    return rows


def export(output,destination):
    output=Path(output);destination=Path(destination);m=json.loads((output/'manifest.json').read_text());verify_manifest(m,output)
    require(m['phase']=='evaluation' and m['policy']=='openrouter','Only real fresh evaluation can publish common benchmark means')
    a=verified_audit(output,m);require(len(a['episodes'])==114,'Final common schedule requires114fresh audited episodes')
    dest=destination/'common';(dest/'traces').mkdir(parents=True,exist_ok=True);(dest/'profiles').mkdir(exist_ok=True);(dest/'pilot').mkdir(exist_ok=True)
    audited={r['episode_id']:r for r in a['episodes']};trials=[];pairs={}
    for job in m['repeat_schedule']:
        eid=job['episode_id'];result=audited[eid];path=output/'episodes'/(eid+'.jsonl');events=read_events(path);model=track_model(next(x for x in m['models'] if x['id']==job['model_id']),job['track'])
        require(result['protocol_sha256']==digest(m) and result['native_replay_verified'],'Trial audit protocol differs')
        groups=defaultdict(list)
        for e in events:
            if 'decision_index'in e:groups[e['decision_index']].append(e)
        actions=[]
        for index,rows in sorted(groups.items()):
            action=next((r for r in rows if r['event']=='action'),None);chunk=next((r for r in rows if r['event']=='chunk_end'),None)
            if not action:continue
            require(chunk is not None,'Committed action missing native checkpoint');responses=[]
            for r in rows:
                if r['event']=='request_result' and r.get('valid'):
                    raw=r['raw_response'];responses.append(dict(stage=r['stage'],request_sha256=r['request_sha256'],native_response={k:raw[k] for k in ['model','provider','answers']}))
            sampling=deepcopy(action['sampling'])
            if sampling:
                sampling.pop('rng_state_before',None);sampling.pop('rng_state_after',None)
            actions.append(dict(index=index,frame_before=action['frame_before'],frame_after=chunk['frame'],sequence=[[chunk['actual_frames'],action['buttons']]],requested_frames=action['requested_frames'],actual_frames=chunk['actual_frames'],provider_stages=responses,sampling=sampling,after_observation_sha256=chunk['observation_sha256'],screen_after_sha256=chunk['screen_sha256'],native_frame_hashes=chunk['native_frame_hashes']))
        trace=dict(schema_version=1,id=eid,phase='evaluation',protocol_sha256=digest(m),model_id=job['model_id'],track=job['track'],level='1-1',actions=actions,source_episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),native_replay_verified=True)
        trace_path=dest/'traces'/(eid+'.json');write_json(trace_path,trace)
        keep=['status','rankable','progress_pct','max_progress_x','repeat_id','local_rng_seed','emulator_seed','temperature','native_frames_to_completion','native_frame_budget','life_budget','native_replay_verified','started_at_utc','decisions','flag_get','death','technical_pending']
        trial={k:result[k] for k in keep};trial.update(id=eid,episode_id=eid,model_id=job['model_id'],display_name=model['name'],track=job['track'],mode=job['track'],phase='evaluation',protocol_id=m['protocol_id'],protocol_sha256=digest(m),level='1-1',native_frames=result['frames'],completed=result['flag_get'],verified=True,returned_model=model['expected_returned_model'],provider=model['expected_returned_provider_names'][0],trace_href='common/traces/'+eid+'.json',trace_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest(),profile_href='common/profiles/protocol.json',replay_href=None,replay_sha256=None,**public_cost(path));trials.append(trial)
        pairs[(job['model_id'],job['track'])]=dict(model_id=job['model_id'],track=job['track'],request_model=model.get('request_model',model['id']),expected_returned_model=model['expected_returned_model'],provider=model['provider'],expected_returned_provider_names=model['expected_returned_provider_names'])
    public_manifest=dict(protocol_id=m['protocol_id'],protocol_sha256=digest(m),phase='evaluation',preregistered=True,frozen_at_utc=m['frozen_at_utc'],level='1-1',repeat_schedule=m['repeat_schedule'],eligible_model_provider_pairs=list(pairs.values()),native_frame_budget=6000,life_budget=1,emulator_seed=0,pilot_selection_evidence=dict(m['pilot_selection_evidence'],selection_href='common/pilot/selection.json'),observation_and_controller_hashes=dict(software=m['software_sha256'],questions=m['questions_sha256'],contracts=digest(m['controller_contracts'])),actual_rom_sha256=m['actual_rom_sha256'],initial_observation_sha256=m['initial_observation_sha256'],initial_screen_sha256=m['initial_screen_sha256'],predeclared_seeds=dict(state=[0,1,2],image=[101,102,103]),common_scope='World1-1 only; mean3fresh prespecified repeats; legacy and pilot episodes excluded')
    write_json(dest/'profiles/protocol.json',dict(schema_version=1,manifest=public_manifest,controller_contracts=m['controller_contracts'],media=m['media'],sampling=m['sampling']))
    value=dict(schema_version=1,common_benchmark=dict(manifest=public_manifest,trials=trials,rows=aggregate_trials(m,trials)))
    write_json(dest/'index.json',value);print(json.dumps(dict(common_index=str(dest/'index.json'),trials=len(trials),rows=len(value['common_benchmark']['rows']),complete_rows=sum(r['coverage_complete'] for r in value['common_benchmark']['rows'])),indent=2));return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();export(a.output,a.destination)

if __name__=='__main__':main()
