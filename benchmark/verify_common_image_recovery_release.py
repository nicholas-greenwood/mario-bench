"""Portable synthetic image overlay lineage/grade/billing boundary tests."""
from copy import deepcopy
import hashlib
import json
import random
import tempfile
from pathlib import Path
import unittest
from benchmark.client import digest
from benchmark.costs import COST_FIELDS,aggregate_receipts
from benchmark import common_image_recovery_release as L


def h(s):return hashlib.sha256(s.encode()).hexdigest()
def encode(v):return (json.dumps(v,indent=2)+'\n').encode()


def fixture():
    trials=[];jobs=[];pairs=[]
    for model in range(16):
        mid=f'synthetic{model}';pin=dict(id=mid,request_model=mid,provider={'only':['fixture'],'allow_fallbacks':False},expected_returned_model=mid,expected_returned_provider_names=['Fixture'])
        pairs.append(dict(model_id=mid,**{k:v for k,v in pin.items() if k!='id'}))
        for repeat in range(3):
            eid=f'{mid}-r{repeat}';condition=dict(model_id=mid,track='image',repeat_id=repeat,local_rng_seed=101+repeat,temperature=.05,emulator_seed=0);jobs.append(dict(episode_id=eid,**condition));pending=len(trials)==0
            trials.append(dict(id=eid,episode_id=eid,**condition,phase='evaluation',protocol_sha256=L.R.PARENT_PROTOCOL_SHA256,status='infra_error' if pending else 'game_over',rankable=not pending,
                technical_pending=pending,progress_pct=None if pending else 10.,max_progress_x=45.,native_frames=7,decisions=1,flag_get=False,death=not pending,completed=False,
                native_frame_budget=6000,life_budget=1,cadence_native_frames=7,native_frames_to_completion=None,native_replay_verified=True,
                attempt_proof=dict(source_episode_sha256=h(eid),request_intent_count=4 if pending else 1,request_result_count=4 if pending else 1,error_attempt_count=3 if pending else 0,unanswered_attempt_count=0,terminal_at_utc='2026-11-01T00:01:00+00:00'),**{k:None for k in COST_FIELDS}))
    controller=h('controller');rng=random.Random(101);rng.random();state=json.loads(json.dumps(rng.getstate()));cp=dict(checkpoint_native_frame=7,rng_draw_count=1,rng_state=state,rng_state_sha256=digest(state),rng_mt_index=state[1][-1],controller_sha256=controller,
        session_controls=[],session_controls_sha256=digest([]),previous_images=[],current_png_sha256=h('png'),rng_mode='global_full12_temperature_sampling',pin_sha256=digest(dict(id='synthetic0',**{k:v for k,v in pairs[0].items() if k!='model_id'})))
    original=trials[0];slot=dict(original_trial_id=original['id'],child_run_id=original['id']+'--image-technical-recovery-v1',parent_episode_sha256=original['attempt_proof']['source_episode_sha256'],
        **{k:original[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed')},checkpoint=cp,pin_payload=dict(id='synthetic0',**{k:v for k,v in pairs[0].items() if k!='model_id'}),
        parent_http_attempts=4,parent_valid_native_actions=1,failed_decision_index=1,remaining_native_frame_budget=5993,continuation_mode='fresh_after_observed_failures',provider_outcome_unknown_attempt_count=0,
        inherited_parent_valid_response_sha256=None,inherited_parent_receipt_id_sha256=None)
    base=dict(manifest=dict(protocol_sha256=L.R.PARENT_PROTOCOL_SHA256,repeat_schedule=jobs,eligible_model_provider_pairs=pairs,observation_and_controller_hashes={'image_controller_sha256':controller}),trials=trials,rows=[],release_provenance={'source_manifest_sha256':h('manifest')})
    prefix=dict(verified=True,parent_protocol_sha256=L.R.PARENT_PROTOCOL_SHA256,source_log_sha256={t['id']:t['attempt_proof']['source_episode_sha256'] for t in trials},slots=[slot]);prefix_raw=encode(prefix)
    header=dict(protocol_sha256=h('SYNTHETIC-NOT-ACTUAL-R'),parent_protocol_sha256=L.R.PARENT_PROTOCOL_SHA256,prefix_proof_sha256=hashlib.sha256(prefix_raw).hexdigest(),parent_manifest_file_sha256=h('manifest'),slots=[slot],
        acceptance_mode='same_checkpoint_technical_recovery_v1',phase='technical_recovery',preregistered=True,native_frame_budget=6000,native_frame_cap=6000,cadence_native_frames=7,requested_native_hold=7,life_budget=1,max_continuations_per_slot=1,temperature=.05,frozen_at_utc='2026-11-01T01:00:00+00:00')
    return base,dict(manifest=header,continuations=[],resolutions=[]),{},prefix_raw


def add_child(base,overlay,documents,rankable=True):
    slot=overlay['manifest']['slots'][0];original=base['trials'][0];cid=slot['child_run_id'];result=dict(id=cid,episode_id=cid,record_kind='technical_continuation',phase='technical_recovery',protocol_sha256=overlay['manifest']['protocol_sha256'],parent_protocol_sha256=L.R.PARENT_PROTOCOL_SHA256,
      resolves_original_trial_id=original['id'],parent_episode_sha256=slot['parent_episode_sha256'],**{k:slot[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed')},checkpoint=slot['checkpoint'],reconstructed_checkpoint=slot['checkpoint'],
      frames=14,native_frames=14,continuation_native_frames=7,decisions=2,continuation_decisions=1,level='1-1',start_x=40,started_at_utc='2026-11-01T01:01:00+00:00',native_frame_budget=6000,life_budget=1,cadence_native_frames=7,
      status='game_over' if rankable else 'infra_error',rankable=rankable,technical_pending=not rankable,progress_pct=20. if rankable else None,max_progress_x=500.,flag_get=False,death=rankable,completed=False,native_frames_to_completion=None,native_replay_verified=True)
    proof=dict(verified=True,original_trial_id=original['id'],child_run_id=cid,parent_protocol_sha256=L.R.PARENT_PROTOCOL_SHA256,recovery_protocol_sha256=overlay['manifest']['protocol_sha256'],parent_episode_sha256=slot['parent_episode_sha256'],child_episode_sha256=h('child'),declared_checkpoint=slot['checkpoint'],reconstructed_checkpoint=slot['checkpoint'],result=deepcopy(result),
      original_attempt_count=4,recovery_attempt_count=1,joined_attempt_count=5,original_request_result_count=4,recovery_request_result_count=1,joined_request_result_count=5,original_error_attempt_count=3,recovery_error_attempt_count=0,joined_error_attempt_count=3,original_unanswered_attempt_count=0,recovery_unanswered_attempt_count=0,joined_unanswered_attempt_count=0,
      provider_outcome_unknown_attempt_count=0,new_provider_outcome_unknown_attempt_count=0,total_provider_outcome_unknown_attempt_count=0,inherited_parent_valid_choice_count=0,inherited_parent_valid_response_sha256=None,inherited_parent_receipt_id_sha256=None,no_observed_valid_choice_discarded=True,total_native_frame_budget=6000,total_native_frames=14,new_native_frames=7,**{k:True for k in L.VERIFIED})
    cost=aggregate_receipts([dict(openrouter_cost_usd=.01,is_byok=False)]*2+[dict(request_failed=True)]*3,coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True);cost=L.joined_cost(cost,proof);raw=encode(proof);ps=hashlib.sha256(raw).hexdigest()
    child=dict(result,**cost,attempt_proof=dict(scope='composed_trajectory',source_episode_sha256=h('child'),native_audit_sha256=ps,request_intent_count=5,request_result_count=5,error_attempt_count=3,unanswered_attempt_count=0),proof_href='proof.json',proof_sha256=ps,trace_href='trace.json',trace_sha256=h('trace'),replay_href=None,replay_sha256=None)
    overlay['continuations'].append(child);documents[cid]=raw
    if rankable:
        effective=deepcopy(child);effective.update(id=original['id'],logical_trial_id=original['id'],source_run_id=cid,record_kind='technical_resolution',base_protocol_sha256=L.R.PARENT_PROTOCOL_SHA256)
        overlay['resolutions'].append(dict(original_trial_id=original['id'],child_run_id=cid,parent_episode_sha256=slot['parent_episode_sha256'],child_episode_sha256=h('child'),proof_sha256=ps,proof_href='proof.json',effective_trial=effective,**{k:True for k in L.VERIFIED}))
    return child,proof


class ImageRecoveryReleaseTests(unittest.TestCase):
    def test_one_logical_slot_and_original48_unchanged(self):
        base,overlay,docs,prefix=fixture();saved=deepcopy(base);child,proof=add_child(base,overlay,docs)
        value=L.normalise(base,overlay,docs,prefix);self.assertEqual(value['logical_trials'],48);self.assertEqual(value['resolved_slots'],1);self.assertEqual(base,saved)
        self.assertEqual(len(value['effective_rows']),16);self.assertEqual(sum(r['coverage_complete'] for r in value['effective_rows']),16)
        self.assertIsNone(value['effective_trials'][0]['cost_usd']);self.assertIsNone(value['effective_trials'][0]['cost_estimate_usd'])

    def test_infrastructure_child_stays_unknown(self):
        base,overlay,docs,prefix=fixture();add_child(base,overlay,docs,False);value=L.normalise(base,overlay,docs,prefix)
        self.assertEqual(value['resolved_slots'],0);self.assertFalse(value['effective_trials'][0]['rankable'])

    def test_forged_grade_checkpoint_pin_source_attempts_and_asset_rejected(self):
        for kind in ('grade','checkpoint','pin','source','attempts','errors','asset','duplicate','prefix_bytes','budget'):
            base,overlay,docs,prefix=fixture();child,proof=add_child(base,overlay,docs)
            if kind=='grade':child['progress_pct']=100.;child['flag_get']=True
            if kind=='checkpoint':child['checkpoint']=dict(child['checkpoint'],rng_mt_index=0)
            if kind=='pin':overlay['manifest']['slots'][0]['pin_payload']['provider']['only']=['wrong']
            if kind=='source':base['trials'][0]['attempt_proof']['source_episode_sha256']=h('wrong')
            if kind=='attempts':child['attempt_proof']['request_intent_count']=4
            if kind=='errors':child['cost_provenance']['error_count']=0
            if kind=='asset':overlay['resolutions'][0]['effective_trial']['trace_sha256']=h('different')
            if kind=='duplicate':overlay['resolutions'].append(deepcopy(overlay['resolutions'][0]))
            if kind=='prefix_bytes':prefix+=b' '
            if kind=='budget':child['native_frame_budget']=6007
            with self.subTest(kind=kind),self.assertRaises((RuntimeError,ValueError)):L.normalise(base,overlay,docs,prefix)

    def test_coherent_child_grade_cannot_drop_prefix_progress(self):
        base,overlay,docs,prefix=fixture();child,proof=add_child(base,overlay,docs)
        child['max_progress_x']=proof['result']['max_progress_x']=0.;raw=encode(proof);ps=hashlib.sha256(raw).hexdigest();docs[child['id']]=raw;child['proof_sha256']=child['attempt_proof']['native_audit_sha256']=ps
        overlay['resolutions'][0]['effective_trial']['max_progress_x']=0.
        with self.assertRaises(RuntimeError):L.normalise(base,overlay,docs,prefix)

    def test_inherited_action_trace_reuses_parent_receipt_without_new_http(self):
        response=dict(event='request_result',decision_index=42,valid=True,request_sha256=h('body'),raw_response=dict(id='gen-synthetic-parent',model='Fixture',provider='Fixture',answers={}))
        rows=[dict(event='inherited_valid_response',decision_index=42,raw_response_sha256=digest(response['raw_response'])),
              dict(event='action',decision_index=42,frame_before=294,requested_frames=7,buttons={'horizontal':'right'}),
              dict(event='chunk_end',decision_index=42,frame=301,actual_frames=7,observation_sha256=h('obs'),screen_sha256=h('rgb'),native_frame_hashes=[])]
        tape=L.actions(rows,response);self.assertEqual(len(tape),1);self.assertEqual(tape[0]['index'],42);self.assertEqual(tape[0]['request_sha256'],response['request_sha256'])
        self.assertEqual(sum(r['event']=='request_result' for r in rows),0);self.assertNotIn('gen-synthetic-parent',json.dumps(tape))
        with self.assertRaises(RuntimeError):L.actions(rows,dict(response,raw_response=dict(response['raw_response'],id='different')))

    def test_reused_audit_requires_exact_captured_episode_and_proof_bytes(self):
        base,overlay,docs,prefix=fixture();child,proof=add_child(base,overlay,docs);slot=overlay['manifest']['slots'][0];manifest={'synthetic_fixture':True}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'episode.jsonl';result=deepcopy(proof['result']);result['native_replay_verified']=False
            path.write_bytes((json.dumps(dict(event='episode_end',result=result))+'\n').encode());proof['child_episode_sha256']=L.sha(path);proof['recovery_protocol_sha256']=digest(manifest)
            path.with_suffix('.audit.json').write_bytes(encode(proof));declared=dict(episode_sha256=L.sha(path),audit_sha256=L.sha(path.with_suffix('.audit.json')))
            self.assertEqual(L.reused_audit(path,declared,slot,manifest)['result'],proof['result'])
            path.write_bytes(path.read_bytes()+b'\n')
            with self.assertRaises(RuntimeError):L.reused_audit(path,declared,slot,manifest)
            path.write_bytes((json.dumps(dict(event='episode_end',result=result))+'\n').encode());path.with_suffix('.audit.json').write_bytes(encode(proof)+b' ')
            with self.assertRaises(RuntimeError):L.reused_audit(path,declared,slot,manifest)


if __name__=='__main__':unittest.main()
