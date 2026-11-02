"""Read-only pending image technical overlay. Never sends requests or edits runs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from benchmark import common_image_recovery as R


def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def safe(raw):
    R.E.require(not any(x in raw for x in ('/Users/','sk-or-','OPENROUTER_API_KEY','gen-dec-')),'Private path/credential/receipt ID in public projection')


def public_manifest(m,prefix_href):
    value={k:deepcopy(v) for k,v in m.items() if k not in ('parent_output','prefix_proof_path','slots')}
    value['protocol_sha256']=R.digest(m);value['prefix_proof_href']=prefix_href
    value['slots']=[{k:deepcopy(v) for k,v in s.items() if k!='parent_episode_path'} for s in m['slots']]
    return value


def project(parent,m,prefix,prefix_href):
    """Pure projection; callers must first validate the actual native authority."""
    original=deepcopy(parent);cohort=original['common_benchmark'];base=cohort['manifest'];trials=cohort['trials']
    R.E.require('technical_recovery' not in cohort,'Never replace an existing recovery overlay')
    R.E.require(base['protocol_sha256']==m['parent_protocol_sha256']==R.PARENT_PROTOCOL_SHA256 and len(trials)==48 and len({t['id'] for t in trials})==48,'Wrong original48 cohort')
    R.E.require(cohort['release_provenance']['source_manifest_sha256']==m['parent_manifest_file_sha256'],'Original public/native manifest differs')
    R.E.require(prefix['verified'] is True and prefix['parent_protocol_sha256']==m['parent_protocol_sha256'],'Wrong independent prefix proof')
    R.E.require({t['id']:t['attempt_proof']['source_episode_sha256'] for t in trials}==prefix['source_log_sha256'],'Public original48 source files differ from independent native proof')
    eligible={t['id'] for t in trials if t['rankable'] is not True};slots=[{k:v for k,v in s.items() if k!='parent_episode_path'} for s in m['slots']]
    R.E.require(eligible=={s['original_trial_id'] for s in slots} and slots==prefix['slots'],'Must include all and only the independently verified technical slots')
    R.E.require(all(t['status']=='infra_error' and t['technical_pending'] is True for t in trials if t['id'] in eligible),'Never recover a legal native outcome')
    cohort['technical_recovery']=dict(manifest=public_manifest(m,prefix_href),continuations=[],resolutions=[])
    stripped=deepcopy(original);del stripped['common_benchmark']['technical_recovery'];R.E.require(stripped==parent,'Original48 records/means changed')
    return original


def export(recovery_output,parent_index,destination):
    recovery_output,parent_index,destination=Path(recovery_output),Path(parent_index),Path(destination)
    m,pm=R.verify(recovery_output);raw=parent_index.read_bytes();parent=json.loads(raw);prefix_raw=Path(m['prefix_proof_path']).read_bytes();prefix=json.loads(prefix_raw)
    R.E.require(sha_bytes(prefix_raw)==m['prefix_proof_sha256'],'Prefix proof bytes changed')
    root=(destination/'common-image').resolve()
    R.E.require(not root.is_relative_to(recovery_output.resolve()) and not root.is_relative_to(Path(m['parent_output']).resolve()) and root/'index.json'!=parent_index.resolve(),'Export cannot overwrite native worker/original public source')
    prefix_href='common-image/recovery/proofs/independent-prefix-'+m['prefix_proof_sha256']+'.json';value=project(parent,m,prefix,prefix_href)
    # Native authority also binds every original public grade and scheduled ID.
    audit=R.E.verified_audit(m['parent_output'],pm);audited={r['episode_id']:r for r in audit['episodes']}
    R.E.require(set(audited)=={t['id'] for t in value['common_benchmark']['trials']},'Wrong public native census')
    for trial in value['common_benchmark']['trials']:
        grade=audited[trial['id']]
        R.E.require(all(trial[k]==grade[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed','status','rankable','progress_pct','max_progress_x','flag_get','death','decisions','native_frames_to_completion','native_frame_budget','life_budget','native_replay_verified')) and trial['native_frames']==grade['frames'],'Original public/native quality differs')
    encoded=json.dumps(value,indent=2)+'\n';safe(encoded);safe(prefix_raw.decode());proof_path=destination/prefix_href;proof_path.parent.mkdir(parents=True,exist_ok=True)
    R.E.require(not(root/'index.json').exists(),'Never overwrite a pending capture')
    proof_path.write_bytes(prefix_raw);(root/'recovery'/'original48-index.json').write_bytes(raw);(root/'index.json').write_text(encoded)
    report=dict(schema_version=1,pending_unexecuted=True,protocol_sha256=R.digest(m),parent_protocol_sha256=m['parent_protocol_sha256'],parent_public_index_sha256=sha_bytes(raw),pending_index_sha256=sha_bytes(encoded.encode()),prefix_proof_sha256=sha_bytes(prefix_raw),exporter_sha256=R.sha(__file__),planned=len(m['slots']),child_records=0,resolutions=0,original_trials=48,original_complete_means=sum(r['mean_progress_pct'] is not None for r in parent['common_benchmark']['rows']),original_document_unchanged=True,model_calls=0)
    (root/'recovery'/'pending-export-proof.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recovery-output',type=Path,required=True);p.add_argument('--parent-index',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args();print(json.dumps(export(a.recovery_output,a.parent_index,a.destination),indent=2))
if __name__=='__main__':main()
