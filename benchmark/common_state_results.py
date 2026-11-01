"""Public state-only66 schema/export, retaining all three prescribed attempts."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from benchmark.client import digest
from benchmark.common_results import aggregate_trials,public_cost
from benchmark.run import read_events,write_json


def public_manifest(m):
    pairs=[dict(model_id=x['id'],track='state',request_model=x.get('request_model',x['id']),expected_returned_model=x['expected_returned_model'],provider=x['provider'],expected_returned_provider_names=x['expected_returned_provider_names'],state_serialization=x.get('state_serialization','text')) for x in m['models']]
    keys=['protocol_id','phase','evaluation_scope','tracks','preregistered','frozen_at_utc','cohort_id','repeat_schedule','native_frame_budget','life_budget','cadence_native_frames','image_evaluation_status','pilot_selection_evidence','observation_and_controller_hashes','actual_rom_sha256','initial_observation_sha256','initial_screen_sha256']
    result={k:deepcopy(m[k]) for k in keys};result.update(protocol_sha256=digest(m),level='1-1',emulator_seed=0,eligible_model_provider_pairs=pairs,predeclared_repeat_ids={'state':[0,1,2]},provider_seed=None,calibration_only_episodes_excluded=True,scope='State track only, World1-1, mean3fresh prescribed repeats; image calibration pending')
    return result


def pending_dataset(m):
    """Truthful preregistered pending shape; never a fake completed score."""
    return dict(schema_version=1,common_benchmark=dict(manifest=public_manifest(m),trials=[],rows=aggregate_trials(m,[])))


def export(output,destination):
    from benchmark.common_state_evaluation import verify
    from benchmark import common_state_run_v2 as engine
    output=Path(output);destination=Path(destination);m=json.loads((output/'manifest.json').read_text());verify(m,output);audit=engine.verified_audit(output,m)
    engine.require(len(audit['episodes'])==66,'State evaluation requires all66 native-audited records, including technical failures')
    root=destination/'common-state';(root/'traces').mkdir(parents=True,exist_ok=True);(root/'profiles').mkdir(exist_ok=True);(root/'calibration').mkdir(exist_ok=True)
    audited={r['episode_id']:r for r in audit['episodes']};trials=[]
    for job in m['repeat_schedule']:
        eid=job['episode_id'];result=audited[eid];path=output/'episodes'/(eid+'.jsonl');events=read_events(path);groups=defaultdict(list);actual=[];attempts=[]
        for row in events:
            if 'decision_index'in row:groups[row['decision_index']].append(row)
            if row['event']=='request_result':
                attempts.append(dict(decision_index=row['decision_index'],stage=row['stage'],attempt=row['attempt'],request_sha256=row['request_sha256'],http_status=row.get('http_status'),valid=row['valid'],failure_class=row.get('error_type')))
                if row.get('valid'):actual.append((row['raw_response']['model'],row['raw_response']['provider']))
        actions=[]
        for i,rows in sorted(groups.items()):
            action=next((r for r in rows if r['event']=='action'),None);chunk=next((r for r in rows if r['event']=='chunk_end'),None)
            if action is None:continue
            engine.require(chunk is not None,'Committed control lacks its native checkpoint')
            source=next(r for r in rows if r['event']=='request_result' and r.get('valid'));raw=source['raw_response']
            actions.append(dict(index=i,frame_before=action['frame_before'],frame_after=chunk['frame'],sequence=[[chunk['actual_frames'],action['buttons']]],requested_frames=action['requested_frames'],actual_frames=chunk['actual_frames'],request_sha256=source['request_sha256'],native_response={k:raw[k] for k in ['model','provider','answers']},after_observation_sha256=chunk['observation_sha256'],screen_after_sha256=chunk['screen_sha256'],native_frame_hashes=chunk['native_frame_hashes']))
        trace=dict(schema_version=1,id=eid,phase='evaluation',protocol_sha256=digest(m),model_id=job['model_id'],track='state',mode='state',level='1-1',actions=actions,request_attempts=attempts,source_episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),native_replay_verified=True)
        tracepath=root/'traces'/(eid+'.json');write_json(tracepath,trace)
        keep=['status','rankable','progress_pct','max_progress_x','repeat_id','local_rng_seed','emulator_seed','temperature','native_frames_to_completion','native_frame_budget','life_budget','native_replay_verified','started_at_utc','decisions','flag_get','death','technical_pending']
        trial={k:result[k] for k in keep};model=next(x for x in m['models'] if x['id']==job['model_id']);trial.update(id=eid,episode_id=eid,model_id=job['model_id'],display_name=model['name'],track='state',mode='state',phase='evaluation',protocol_id=m['protocol_id'],protocol_sha256=digest(m),level='1-1',native_frames=result['frames'],completed=result['flag_get'],verified=True,returned_model=actual[0][0] if actual else None,provider=actual[0][1] if actual else None,trace_href='common-state/traces/'+eid+'.json',trace_sha256=hashlib.sha256(tracepath.read_bytes()).hexdigest(),profile_href='common-state/profiles/protocol.json',replay_href=None,replay_sha256=None,**public_cost(path));trials.append(trial)
    header=public_manifest(m);write_json(root/'profiles/protocol.json',dict(schema_version=1,manifest=header,controller_contracts=m['controller_contracts'],software_sha256=m['software_sha256']))
    selection=Path(m['authority_paths']['calibration'])/'selection.json';write_json(root/'calibration/selection.json',json.loads(selection.read_text()))
    value=dict(schema_version=1,common_benchmark=dict(manifest=header,trials=trials,rows=aggregate_trials(m,trials)))
    raw=json.dumps(value);engine.require('/Users/' not in raw and 'gen-dec-' not in raw and 'OPENROUTER_API_KEY' not in raw,'Private paths/request IDs/credentials must not appear in public dataset')
    write_json(root/'index.json',value);return value


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();value=export(a.output,a.destination);print(json.dumps(dict(trials=len(value['common_benchmark']['trials']),rows=len(value['common_benchmark']['rows'])),indent=2))

if __name__=='__main__':main()
