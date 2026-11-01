"""Release-only technical-recovery overlays; original evaluation trials stay intact.

No worker execution or paid calls. Closed child logs are audited on disposable
copies by the unchanged recovery helper before their public lineage is exported.
"""
from __future__ import annotations

from copy import deepcopy
from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from benchmark.client import digest
from benchmark.common_state_release import (PROTOCOL_SHA256, aggregate_release_trials, attempt_evidence, sha, utc)
from benchmark.costs import COST_FIELDS, validate_public_cost
from benchmark.public_results import public_native_response
from benchmark.run import read_events, write_json

CHECKPOINT_KEYS = ('checkpoint_native_frame', 'checkpoint_ram_sha256', 'checkpoint_rgb_sha256',
                   'checkpoint_observation_sha256', 'controller_history_sha256', 'failed_request_sha256',
                   'controller_sha256', 'pin_sha256', 'rng_mode', 'rng_state_sha256')
VERIFIED = ('prefix_replay_verified', 'failed_body_identical', 'controller_pin_history_rng_verified',
            'total_native_budget_verified')
AUDITED = ('frames','native_frames','level','start_x','started_at_utc','status','rankable','progress_pct',
           'max_progress_x','flag_get','completed','death','native_frames_to_completion','decisions',
           'native_frame_budget','life_budget','cadence_native_frames','repeat_id','local_rng_seed','emulator_seed',
           'temperature','model_id','track','phase','protocol_sha256','parent_protocol_sha256',
           'resolves_original_trial_id','parent_episode_sha256','checkpoint','reconstructed_checkpoint',
           'native_replay_verified','continuation_native_frames','continuation_decisions','technical_pending')
ASSETS = ('trace_href','trace_sha256','replay_href','replay_sha256','proof_href','proof_sha256')
METRICS = ('status', 'rankable', 'progress_pct', 'max_progress_x', 'native_frames', 'decisions',
           'native_frames_to_completion', 'completed', 'flag_get', 'death', 'technical_pending')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def public_header(manifest, parent):
    header = {key: deepcopy(value) for key, value in manifest.items()
              if key not in ('parent_output', 'prefix_proof_path', 'slots')}
    header['protocol_sha256'] = digest(manifest)
    header['slots'] = []
    for slot in manifest['slots']:
        item = {key: deepcopy(value) for key, value in slot.items() if key != 'parent_episode_path'}
        model = next(model for model in parent['models'] if model['id'] == slot['model_id'])
        item['pin_payload'] = {key: deepcopy(model[key]) for key in
                               ('id', 'request_model', 'provider', 'expected_returned_model', 'expected_returned_provider_names')}
        require(digest(item['pin_payload']) == item['pin_sha256'], 'Registered provider pin digest differs')
        header['slots'].append(item)
    return header


def checked_header(base, header):
    require(base['manifest']['protocol_sha256'] == header['parent_protocol_sha256'] == PROTOCOL_SHA256,
            'Recovery must reference the original independent state evaluation')
    require(len(base['trials']) == 66 and len({trial['id'] for trial in base['trials']}) == 66,
            'Publish all66 original trials before adding a recovery overlay')
    expected = {job['episode_id'] for job in base['manifest']['repeat_schedule']}
    require({trial['id'] for trial in base['trials']} == expected, 'Original trial denominator changed')
    require(header['phase'] == 'technical_recovery' and header['preregistered'] is True and header['policy'] == 'openrouter'
            and header['native_frame_budget'] == header['native_frame_cap'] == 6000
            and header['life_budget'] == header['max_continuations_per_slot'] == 1
            and header['cadence_native_frames'] == 4 and header['provider_seed'] is None,
            'Recovery controller, life or native budget changed')
    require(base['release_provenance']['source_manifest_sha256'] == header['parent_manifest_file_sha256'], 'Public original manifest-byte binding differs')
    slots = header['slots']
    require(len(slots) == 8 and len({s['original_trial_id'] for s in slots}) == 8
            and len({s['child_run_id'] for s in slots}) == 8, 'Exactly8 unique predeclared technical slots are required')
    originals = {trial['id']: trial for trial in base['trials']}
    pairs = {pair['model_id']: pair for pair in base['manifest']['eligible_model_provider_pairs']}
    for slot in slots:
        original = originals[slot['original_trial_id']]
        require(original['protocol_sha256'] == PROTOCOL_SHA256 and original['phase'] == 'evaluation'
                and original['status'] == 'infra_error' and not original['rankable'] and original['technical_pending'] is True
                and original['native_replay_verified'] is True
                and not original['flag_get'] and not original['death'], 'A valid native outcome cannot be recovered')
        require(slot['child_run_id'] == slot['original_trial_id']+'--technical-recovery-v1', 'Only one named child per original slot is registered')
        require(original['attempt_proof']['source_episode_sha256'] == slot['parent_episode_sha256'],
                'Original abort bytes differ from the registered parent')
        require(all(original[key] == slot[key] for key in ('model_id','track','repeat_id','emulator_seed','local_rng_seed','temperature')),
                'Recovery changes the original logical slot')
        proof=original['attempt_proof']
        require(proof['request_intent_count'] == proof['request_result_count'] == slot['parent_http_attempts']
                and proof['unanswered_attempt_count'] == 0
                and proof['request_result_count']-proof['error_attempt_count'] == slot['parent_valid_native_actions']
                and utc(proof['terminal_at_utc']) <= utc(header['frozen_at_utc']), 'Original ledger was not closed or has an unconsumed valid choice')
        require(original['native_frames'] == slot['checkpoint_native_frame']
                and slot['remaining_native_frame_budget'] == 6000-slot['checkpoint_native_frame']
                and original['decisions'] == slot['parent_valid_native_actions'], 'Recovery prefix/budget changed')
        require(slot['no_observed_valid_choice_discarded'] is True and slot['unmatched_ledger_intent_count'] == 0,
                'A received valid native choice cannot be discarded')
        pair=pairs[slot['model_id']]
        expected_pin={key:deepcopy(pair[key]) for key in ('request_model','provider','expected_returned_model','expected_returned_provider_names')}
        expected_pin['id']=slot['model_id']
        require(slot['pin_payload'] == expected_pin and digest(slot['pin_payload']) == slot['pin_sha256'], 'Recovery pin payload was modified')
    require(sum(slot['provider_outcome_unknown_attempt_count'] for slot in slots)
            == header['provider_outcome_unknown_attempt_count'], 'Original provider uncertainty denominator changed')
    return originals, {slot['child_run_id']:slot for slot in slots}


def joined_cost(value, proof):
    cost = {key: deepcopy(value.get(key)) for key in COST_FIELDS}
    validate_public_cost(cost)
    provenance = cost.get('cost_provenance')
    if provenance is not None:
        require(all(provenance.get(key) == proof['joined_attempt_count'] for key in
                    ('request_count','source_request_count','source_attempt_count')), 'Child-only billing cannot price the logical trial')
        require(provenance.get('error_count') == proof['joined_error_attempt_count'], 'Joined billing omits original/child errors')
        provenance['joined_attempt_count'] = proof['joined_attempt_count']
    if proof['total_provider_outcome_unknown_attempt_count'] > 0:
        cost['cost_usd'] = cost['cost_estimate_usd'] = None
        if provenance is not None:
            provenance['coverage_complete'] = False
    return cost


def validate_child(original, slot, child, proof, recovery_sha):
    require(proof['result'].get('id') == proof['result'].get('episode_id') == child['id']
            and proof['result'].get('record_kind') == 'technical_continuation', 'Proof result belongs to another child')
    for key in ('original_attempt_count','recovery_attempt_count','joined_attempt_count','original_error_attempt_count',
                'recovery_error_attempt_count','joined_error_attempt_count','provider_outcome_unknown_attempt_count',
                'new_provider_outcome_unknown_attempt_count','total_provider_outcome_unknown_attempt_count',
                'total_native_frames','new_native_frames','original_unanswered_attempt_count','recovery_unanswered_attempt_count',
                'joined_unanswered_attempt_count','original_request_result_count','recovery_request_result_count','joined_request_result_count'):
        require(type(proof.get(key)) is int and proof[key]>=0, 'Proof counters must be explicit nonnegative integers')
    require(all(key in proof['result'] and child.get(key) == proof['result'][key] for key in AUDITED),
            'Child quality metrics differ from the native audit proof result')
    require(child['id'] == slot['child_run_id'] and child['record_kind'] == 'technical_continuation'
            and child['phase'] == 'technical_recovery' and child['protocol_sha256'] == recovery_sha
            and child['parent_protocol_sha256'] == PROTOCOL_SHA256
            and child['resolves_original_trial_id'] == original['id']
            and child['parent_episode_sha256'] == slot['parent_episode_sha256'], 'Child lineage changed')
    require(all(child[key] == slot[key] for key in ('model_id','track','repeat_id','emulator_seed','local_rng_seed','temperature')),
            'Child provider/model/repeat condition differs')
    checkpoint = {key: slot[key] for key in CHECKPOINT_KEYS}
    require(child['checkpoint'] == child['reconstructed_checkpoint'] == checkpoint
            and proof['declared_checkpoint'] == proof['reconstructed_checkpoint'] == checkpoint, 'Checkpoint/history/controller/pin/RNG differs')
    require(proof['verified'] is True and all(proof[key] is True for key in VERIFIED)
            and proof['no_observed_valid_choice_discarded'] is True and child['native_replay_verified'] is True,
            'Only fully native-audited continuations can be projected')
    require(proof['original_trial_id'] == original['id'] and proof['child_run_id'] == child['id']
            and proof['parent_protocol_sha256'] == PROTOCOL_SHA256 and proof['recovery_protocol_sha256'] == recovery_sha
            and proof['parent_episode_sha256'] == slot['parent_episode_sha256']
            and proof['child_episode_sha256'] == child['attempt_proof']['source_episode_sha256'], 'Proof source IDs/hashes differ')
    require(proof['original_attempt_count'] == slot['parent_http_attempts']
            == original['attempt_proof']['request_intent_count']
            and proof['joined_attempt_count'] == proof['original_attempt_count']+proof['recovery_attempt_count'],
            'Joined attempt denominator changed')
    require(proof['original_unanswered_attempt_count'] == original['attempt_proof']['unanswered_attempt_count']
            and proof['original_request_result_count'] == original['attempt_proof']['request_result_count']
            and proof['joined_request_result_count'] == proof['original_request_result_count']+proof['recovery_request_result_count']
            and proof['joined_unanswered_attempt_count'] == proof['original_unanswered_attempt_count']+proof['recovery_unanswered_attempt_count']
            == proof['joined_attempt_count']-proof['joined_request_result_count']
            and proof['joined_request_result_count']-proof['joined_error_attempt_count'] == child['decisions']
            and proof['recovery_request_result_count']-proof['recovery_error_attempt_count'] == child['continuation_decisions'], 'Composed response/action ledger differs')
    require(child['attempt_proof'].get('scope') == 'composed_trajectory'
            and child['attempt_proof']['request_intent_count'] == proof['joined_attempt_count']
            and child['attempt_proof']['request_result_count'] == proof['joined_request_result_count']
            and child['attempt_proof']['error_attempt_count'] == proof['joined_error_attempt_count']
            and child['attempt_proof']['unanswered_attempt_count'] == proof['joined_unanswered_attempt_count'], 'Child attempt scope must be the composed trajectory')
    require(proof['joined_error_attempt_count'] == proof['original_error_attempt_count']+proof['recovery_error_attempt_count']
            and proof['original_error_attempt_count'] == original['attempt_proof']['error_attempt_count'], 'Joined error scope changed')
    require(proof['provider_outcome_unknown_attempt_count'] == slot['provider_outcome_unknown_attempt_count']
            and proof['total_provider_outcome_unknown_attempt_count'] == proof['provider_outcome_unknown_attempt_count']
            + proof['new_provider_outcome_unknown_attempt_count'], 'Provider-outcome uncertainty was dropped')
    require(proof['total_native_frame_budget'] == child['native_frame_budget'] == 6000
            and child['life_budget'] == 1 and child['cadence_native_frames'] == 4
            and slot['checkpoint_native_frame'] <= proof['total_native_frames'] == child['native_frames'] <= 6000
            and child['frames'] == child['native_frames']
            and child['continuation_decisions'] == child['decisions']-slot['parent_valid_native_actions'] >= 0
            and proof['new_native_frames'] == child['continuation_native_frames']
            == child['native_frames']-slot['checkpoint_native_frame'], 'Continuation extended or reset the native budget')
    require(child['max_progress_x'] >= original['max_progress_x'], 'Prefix progress was discarded')
    validate_public_cost(child)
    provenance = child.get('cost_provenance')
    if provenance is not None:
        require(provenance.get('joined_attempt_count') == proof['joined_attempt_count']
                and all(provenance.get(key) == proof['joined_attempt_count'] for key in
                        ('request_count','source_request_count','source_attempt_count'))
                and provenance.get('error_count') == proof['joined_error_attempt_count'], 'Logical cost is not the joined attempt scope')
    if proof['total_provider_outcome_unknown_attempt_count']:
        require(child.get('cost_usd') is None and child.get('cost_estimate_usd') is None, 'Unknown original/new outcome cannot be priced as a complete total')


def normalise(base, overlay, proof_documents):
    """Return one effective logical record per original slot; never append children."""
    originals, slots = checked_header(base, overlay['manifest'])
    recovery_sha = overlay['manifest']['protocol_sha256']
    children = {}
    for child in overlay['continuations']:
        require(child['id'] not in children and child['id'] in slots, 'Unexpected or duplicate continuation')
        slot = slots[child['id']]
        proof_bytes = proof_documents[child['id']]
        require(isinstance(proof_bytes, bytes) and hashlib.sha256(proof_bytes).hexdigest()
                == child['attempt_proof']['native_audit_sha256'] == child['proof_sha256'], 'Public proof bytes/hash differ')
        proof = json.loads(proof_bytes)
        require(utc(child['started_at_utc']) >= utc(overlay['manifest']['frozen_at_utc']), 'Child precedes its own registration')
        validate_child(originals[slot['original_trial_id']], slot, child, proof, recovery_sha)
        children[child['id']] = child
    effective = {key:deepcopy(value) for key,value in originals.items()}
    resolved = set()
    for resolution in overlay['resolutions']:
        oid, cid = resolution['original_trial_id'], resolution['child_run_id']
        require(oid not in resolved and cid in children and slots[cid]['original_trial_id'] == oid, 'Duplicate or cross-slot resolution')
        child, proof = children[cid], json.loads(proof_documents[cid])
        require(proof['joined_unanswered_attempt_count'] == 0, 'A rankable resolution cannot leave an unanswered attempt')
        require(child['rankable'] and child['status'] in ('completed','game_over','frame_budget')
                and not child['technical_pending'], 'A failed infrastructure continuation cannot become a model score')
        require(resolution['parent_episode_sha256'] == slots[cid]['parent_episode_sha256']
                and resolution['child_episode_sha256'] == child['attempt_proof']['source_episode_sha256']
                and resolution['proof_sha256'] == child['attempt_proof']['native_audit_sha256']
                and resolution['proof_href'] == child['proof_href']
                and all(resolution[key] is True for key in VERIFIED), 'Resolution proof lineage changed')
        record = resolution['effective_trial']
        require(record['id'] == record['logical_trial_id'] == oid and record['source_run_id'] == cid
                and record['record_kind'] == 'technical_resolution' and record['phase'] == 'technical_recovery'
                and record['protocol_sha256'] == recovery_sha and record['base_protocol_sha256'] == PROTOCOL_SHA256,
                'The effective record must remain an explicitly labelled recovery projection')
        require(all(record[key] == child[key] for key in AUDITED+COST_FIELDS+ASSETS), 'Effective metrics/billing differ from the audited child')
        effective[oid] = deepcopy(record);resolved.add(oid)
    records = [effective[trial['id']] for trial in base['trials']]
    # Frozen aggregation receives scratch-normalised authority labels only. The
    # published raw records retain R/e1 labels and original66 objects untouched.
    proxy = dict(repeat_schedule=base['manifest']['repeat_schedule'])
    scratch = deepcopy(records)
    for trial in scratch:
        trial['phase']='evaluation';trial['protocol_sha256']=digest(proxy)
    rows = aggregate_release_trials(proxy,scratch)
    for row in rows:
        row['protocol_sha256']=PROTOCOL_SHA256
    return dict(effective_trials=records,effective_rows=rows,resolved_slots=len(resolved),logical_trials=len(records))


def _actions(rows):
    groups=defaultdict(list)
    for row in rows:
        if 'decision_index'in row:groups[row['decision_index']].append(row)
    actions=[]
    for i,records in sorted(groups.items()):
        action=next((r for r in records if r['event']=='action'),None)
        if action is None:continue
        chunk=next(r for r in records if r['event']=='chunk_end')
        response=next(r for r in records if r['event']=='request_result' and r.get('valid'))
        actions.append(dict(index=i,frame_before=action['frame_before'],frame_after=chunk['frame'],
                            sequence=[[chunk['actual_frames'],action['buttons']]],requested_frames=action['requested_frames'],
                            actual_frames=chunk['actual_frames'],request_sha256=response['request_sha256'],
                            native_response=public_native_response(response['raw_response']),
                            after_observation_sha256=chunk['observation_sha256'],screen_after_sha256=chunk['screen_sha256'],
                            native_frame_hashes=chunk['native_frame_hashes']))
    return actions


def export(base_directory,recovery_workspace,destination,*,reaudit=True):
    """Add an overlay, auditing child/parent copies; never change original trials."""
    from benchmark import common_state_recovery as helper
    base_directory,recovery_workspace,destination=map(lambda p:Path(p).resolve(),(base_directory,recovery_workspace,destination))
    require(destination!=recovery_workspace and not destination.is_relative_to(recovery_workspace), 'Destination must not be a worker workspace')
    source=base_directory/'common-state/index.json';base_document=json.loads(source.read_text());base=base_document['common_benchmark']
    manifest,parent=helper.verify(recovery_workspace,approval=False)
    parent_workspace=Path(manifest['parent_output']).resolve()
    require(destination!=parent_workspace and not destination.is_relative_to(parent_workspace), 'Destination must not be the original worker workspace')
    header=public_header(manifest,parent);originals,slots=checked_header(base,header)
    overlay=dict(manifest=header,continuations=[],resolutions=[]);proofs={};assets={}
    with tempfile.TemporaryDirectory(prefix='mario-recovery-release-') as temp:
        scratch=Path(temp);(scratch/'episodes').mkdir();(scratch/'parents').mkdir()
        for slot in manifest['slots']:
            cid,oid=slot['child_run_id'],slot['original_trial_id'];path=recovery_workspace/'episodes'/(cid+'.jsonl')
            if not path.exists():continue
            raw=path.read_bytes()
            if not raw.endswith(b'\n'):continue
            rows=[json.loads(line) for line in raw.splitlines() if line]
            if not rows or rows[-1]['event']!='episode_end':continue
            source_sha=hashlib.sha256(raw).hexdigest();target=scratch/'episodes'/path.name;target.write_bytes(raw)
            require(sha(path)==source_sha,'Closed child changed during copy')
            pp=Path(slot['parent_episode_path']);parent_raw=pp.read_bytes();parent_copy=scratch/'parents'/pp.name;parent_copy.write_bytes(parent_raw)
            require(sha(pp)==sha(parent_copy)==slot['parent_episode_sha256'],'Original parent changed during copy')
            local=deepcopy(slot);local['parent_episode_path']=str(parent_copy)
            if reaudit:
                result=helper.execute_one(scratch,manifest,parent,local,audit=True)
                proof=json.loads(target.with_suffix('.audit.json').read_text())
            else:
                proof=json.loads(path.with_suffix('.audit.json').read_text());result=deepcopy(proof['result'])
                # Metadata-only reuse still recomputes the joined raw attempt scope.
                from benchmark.costs import costs_from_events
                result.update(costs_from_events(read_events(parent_copy)+rows))
            parent_rows=read_events(parent_copy);pa,pproof,pids=attempt_evidence(parent_rows);ca,cproof,cids=attempt_evidence(rows)
            require(not set(pids).intersection(cids),'An original API response was reused as a new child call')
            require(all(result.get(key) == proof['result'].get(key) for key in AUDITED), 'Helper result differs from its native audit')
            proof['source_native_audit_sha256'] = sha(target.with_suffix('.audit.json')) if reaudit else sha(path.with_suffix('.audit.json'))
            proof['result'] = {key:value for key,value in proof['result'].items() if key!='error'}
            proof.update(original_error_attempt_count=pproof['error_attempt_count'],recovery_error_attempt_count=cproof['error_attempt_count'],
                         joined_error_attempt_count=pproof['error_attempt_count']+cproof['error_attempt_count'],
                         original_request_result_count=pproof['request_result_count'],
                         recovery_request_result_count=cproof['request_result_count'],
                         joined_request_result_count=pproof['request_result_count']+cproof['request_result_count'],
                         original_unanswered_attempt_count=pproof['unanswered_attempt_count'],
                         recovery_unanswered_attempt_count=cproof['unanswered_attempt_count'],
                         joined_unanswered_attempt_count=pproof['unanswered_attempt_count']+cproof['unanswered_attempt_count'])
            model=next(model for model in parent['models'] if model['id']==slot['model_id'])
            session=helper.E.CommonSession(model,'state')
            for response in rows:
                if response['event']=='request_result' and response.get('valid'):
                    intent=next(row for row in rows if row['event']=='request_intent' and row['decision_index']==response['decision_index'] and row['stage']==response['stage'] and row['attempt']==response['attempt'])
                    require(digest(intent['body'])==intent['request_sha256'], 'Child request body hash differs')
                    session.parse(response['raw_response'],intent['body'])
            proof_bytes=(json.dumps(proof,indent=2,allow_nan=False)+'\n').encode();proof_sha=hashlib.sha256(proof_bytes).hexdigest()
            proof_href='common-state/recovery/proofs/'+cid+'.json';trace_href='common-state/recovery/traces/'+cid+'.json'
            child=deepcopy(proof['result'])
            child.update(checkpoint=proof['declared_checkpoint'],reconstructed_checkpoint=proof['reconstructed_checkpoint'],
                         display_name=originals[oid]['display_name'],returned_model=None,provider=None,
                         mode='state',profile_href=originals[oid].get('profile_href'),
                         attempt_proof=dict(scope='composed_trajectory',started_at_utc=proof['result']['started_at_utc'],terminal_at_utc=rows[-1]['utc'],source_episode_sha256=source_sha,native_audit_sha256=proof_sha,
                                            request_intent_count=proof['joined_attempt_count'],error_attempt_count=proof['joined_error_attempt_count'],
                                            request_result_count=pproof['request_result_count']+cproof['request_result_count'],
                                            unanswered_attempt_count=proof['joined_unanswered_attempt_count'],
                                            original_attempt_count=proof['original_attempt_count'],recovery_attempt_count=proof['recovery_attempt_count']),
                         proof_href=proof_href,proof_sha256=proof_sha,trace_href=trace_href,replay_href=None,replay_sha256=None,
                         **joined_cost(result,proof))
            actual=[r['raw_response'] for r in rows if r['event']=='request_result' and r.get('valid')]
            child['actual_returned_model_provider_pairs']=[dict(model=a,provider=b) for a,b in sorted({(r['model'],r['provider']) for r in actual})]
            if actual:child.update(returned_model=actual[0]['model'],provider=actual[0]['provider'])
            for attempt in pa:attempt['source_run_id']=oid
            for attempt in ca:attempt['source_run_id']=cid
            prefix=_actions(parent_rows);suffix=_actions(rows)
            require(len(prefix)==slot['parent_valid_native_actions'] and (not suffix or suffix[0]['index']==slot['failed_decision_index']), 'Continuation action prefix was reset or duplicated')
            require(len(prefix+suffix)==child['decisions'] and all(a['frame_after']==b['frame_before'] for a,b in zip(prefix+suffix,(prefix+suffix)[1:])), 'Composed native trace has a gap or duplicate action')
            trace=dict(schema_version=1,id=cid,model_id=slot['model_id'],track='state',mode='state',level='1-1',attempt_proof=child['attempt_proof'],record_kind='technical_continuation',phase='technical_recovery',
                       protocol_sha256=header['protocol_sha256'],parent_protocol_sha256=PROTOCOL_SHA256,
                       resolves_original_trial_id=oid,parent_episode_sha256=slot['parent_episode_sha256'],
                       source_episode_sha256=source_sha,actions=prefix+suffix,request_attempts=pa+ca,proof_href=proof_href,proof_sha256=proof_sha,
                       native_replay_verified=True)
            trace_bytes=(json.dumps(trace,indent=2,allow_nan=False)+'\n').encode();child['trace_sha256']=hashlib.sha256(trace_bytes).hexdigest()
            proofs[cid]=proof_bytes;assets[proof_href]=proof_bytes;assets[trace_href]=trace_bytes;overlay['continuations'].append(child)
            if child['rankable'] and child['status'] in ('completed','game_over','frame_budget'):
                effective=deepcopy(child);effective.update(id=oid,logical_trial_id=oid,source_run_id=cid,record_kind='technical_resolution',base_protocol_sha256=PROTOCOL_SHA256)
                overlay['resolutions'].append(dict(original_trial_id=oid,child_run_id=cid,parent_episode_sha256=slot['parent_episode_sha256'],
                    child_episode_sha256=source_sha,proof_href=proof_href,proof_sha256=proof_sha,**{key:True for key in VERIFIED},effective_trial=effective))
            require(sha(path)==source_sha and sha(pp)==slot['parent_episode_sha256'],'Input source changed during release audit')
    normalised=normalise(base,overlay,proofs)
    output=deepcopy(base_document);output['common_benchmark']['technical_recovery']=overlay
    require(output['common_benchmark']['trials']==base['trials'],'Original66 records must remain unchanged')
    public=json.dumps(output)+''.join(value.decode() for value in assets.values())
    require(not any(value in public for value in ('/Users/','OPENROUTER_API_KEY','gen-')),'Private source paths, credentials or raw API IDs in release')
    for relative,data in assets.items():
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    root=destination/'common-state';root.mkdir(parents=True,exist_ok=True);write_json(root/'index.json',output)
    return dict(continuations=len(overlay['continuations']),resolved_slots=normalised['resolved_slots'],logical_trials=normalised['logical_trials'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--recovery-workspace',type=Path,required=True);parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--reuse-existing-audit',action='store_true',help='Metadata-only projection from an already independently audited immutable child')
    args=parser.parse_args();print(json.dumps(export(args.base,args.recovery_workspace,args.destination,reaudit=not args.reuse_existing_audit),indent=2))


if __name__=='__main__':main()
