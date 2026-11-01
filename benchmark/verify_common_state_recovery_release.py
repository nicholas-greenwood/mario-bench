"""Pure synthetic metadata/trace-lineage tests; no actual recovery results or calls."""
from copy import deepcopy
import hashlib
import json
import unittest
from benchmark.client import digest
from benchmark.costs import COST_FIELDS, aggregate_receipts
from benchmark.common_state_release import PROTOCOL_SHA256
from benchmark import common_state_recovery_release as release


def h(value):return hashlib.sha256(value.encode()).hexdigest()
def encoded(proof):return (json.dumps(proof,indent=2)+'\n').encode()


def fixture():
    pairs=[];jobs=[];trials=[];slots=[]
    for model in range(22):
        mid=f'fixture-model{model}'
        pin=dict(id=mid,request_model=mid+'-dated',expected_returned_model=mid+'-dated',
                 provider=dict(only=['fixture'],allow_fallbacks=False),expected_returned_provider_names=['Fixture'])
        pairs.append(dict(model_id=mid,**{k:v for k,v in pin.items() if k!='id'}))
        for repeat in range(3):
            index=len(trials);eid=f'fixture-{model}-repeat{repeat}';eligible=index<8
            condition=dict(model_id=mid,track='state',repeat_id=repeat,local_rng_seed=None,emulator_seed=0,temperature=None)
            jobs.append(dict(episode_id=eid,**condition))
            trial=dict(id=eid,episode_id=eid,phase='evaluation',protocol_sha256=PROTOCOL_SHA256,**condition,
                status='infra_error' if eligible else 'game_over',rankable=not eligible,progress_pct=None if eligible else 10.,
                max_progress_x=44.,native_frames=4,decisions=1,native_frames_to_completion=None,completed=False,flag_get=False,
                death=not eligible,technical_pending=eligible,native_frame_budget=6000,life_budget=1,native_replay_verified=True,
                started_at_utc='2026-11-01T00:01:00+00:00',display_name=mid,
                attempt_proof=dict(source_episode_sha256=h(eid),native_audit_sha256=h('audit'+eid),request_intent_count=4 if eligible else 1,request_result_count=4 if eligible else 1,unanswered_attempt_count=0,terminal_at_utc='2026-11-01T00:02:00+00:00',error_attempt_count=3 if eligible else 0),
                **{key:None for key in COST_FIELDS})
            trials.append(trial)
            if eligible:
                cp={key:h(key+eid) for key in release.CHECKPOINT_KEYS}
                cp.update(checkpoint_native_frame=4,pin_sha256=digest(pin),rng_mode='not_used_native_choice',rng_state_sha256=None)
                slots.append(dict(original_trial_id=eid,child_run_id=eid+'--technical-recovery-v1',**condition,**cp,
                    parent_episode_sha256=h(eid),remaining_native_frame_budget=5996,parent_valid_native_actions=1,parent_http_attempts=4,
                    provider_outcome_unknown_attempt_count=int(index<5),no_observed_valid_choice_discarded=True,unmatched_ledger_intent_count=0,pin_payload=pin))
    base=dict(release_provenance=dict(source_manifest_sha256=h('manifest')),manifest=dict(protocol_sha256=PROTOCOL_SHA256,repeat_schedule=jobs,eligible_model_provider_pairs=pairs),trials=trials,rows=[])
    header=dict(parent_manifest_file_sha256=h('manifest'),protocol_sha256=h('SYNTHETIC-NOT-ACTUAL-RECOVERY'),parent_protocol_sha256=PROTOCOL_SHA256,phase='technical_recovery',
                preregistered=True,policy='openrouter',frozen_at_utc='2026-11-01T01:00:00+00:00',slots=slots,native_frame_budget=6000,
                native_frame_cap=6000,life_budget=1,max_continuations_per_slot=1,cadence_native_frames=4,provider_seed=None,
                provider_outcome_unknown_attempt_count=5)
    return base,dict(manifest=header,continuations=[],resolutions=[]),{}


def add_child(base,overlay,proofs,*,rankable=True):
    slot=overlay['manifest']['slots'][0];original=base['trials'][0];cid=slot['child_run_id']
    cp={key:slot[key] for key in release.CHECKPOINT_KEYS}
    metrics=dict(id=cid,episode_id=cid,record_kind='technical_continuation',phase='technical_recovery',
        protocol_sha256=overlay['manifest']['protocol_sha256'],parent_protocol_sha256=PROTOCOL_SHA256,
        resolves_original_trial_id=original['id'],parent_episode_sha256=slot['parent_episode_sha256'],
        model_id=slot['model_id'],track='state',repeat_id=slot['repeat_id'],local_rng_seed=None,emulator_seed=0,temperature=None,
        native_frame_budget=6000,life_budget=1,cadence_native_frames=4,checkpoint=cp,reconstructed_checkpoint=cp,
        frames=8,native_frames=8,continuation_native_frames=4,decisions=2,continuation_decisions=1,level='1-1',start_x=40,
        started_at_utc='2026-11-01T01:01:00+00:00',status='game_over' if rankable else 'infra_error',rankable=rankable,
        progress_pct=30. if rankable else None,max_progress_x=100.,flag_get=False,completed=False,death=rankable,
        native_frames_to_completion=None,native_replay_verified=True,technical_pending=not rankable)
    proof=dict(schema_version=1,verified=True,original_trial_id=original['id'],child_run_id=cid,parent_protocol_sha256=PROTOCOL_SHA256,
        recovery_protocol_sha256=overlay['manifest']['protocol_sha256'],parent_episode_sha256=slot['parent_episode_sha256'],
        child_episode_sha256=h('childbytes'),declared_checkpoint=cp,reconstructed_checkpoint=cp,
        original_attempt_count=4,recovery_attempt_count=1,joined_attempt_count=5,original_error_attempt_count=3,recovery_error_attempt_count=0,
        joined_error_attempt_count=3,original_unanswered_attempt_count=0,recovery_unanswered_attempt_count=0,joined_unanswered_attempt_count=0,
        original_request_result_count=4,recovery_request_result_count=1,joined_request_result_count=5,provider_outcome_unknown_attempt_count=1,new_provider_outcome_unknown_attempt_count=0,
        total_provider_outcome_unknown_attempt_count=1,no_observed_valid_choice_discarded=True,**{key:True for key in release.VERIFIED},
        total_native_frame_budget=6000,total_native_frames=8,new_native_frames=4,result=deepcopy(metrics))
    if not rankable:
        proof.update(recovery_attempt_count=2,joined_attempt_count=6,recovery_request_result_count=2,joined_request_result_count=6,recovery_error_attempt_count=1,joined_error_attempt_count=4)
    cost=aggregate_receipts([dict(openrouter_cost_usd=.01,is_byok=False)]+[dict(request_failed=True)]*3+[dict(openrouter_cost_usd=.02,is_byok=False)]+([] if rankable else [dict(request_failed=True)]),
        coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True)
    cost=release.joined_cost(cost,proof)
    raw=encoded(proof);ps=hashlib.sha256(raw).hexdigest()
    child=dict(metrics,**cost,attempt_proof=dict(scope='composed_trajectory',source_episode_sha256=h('childbytes'),native_audit_sha256=ps,request_intent_count=proof['joined_attempt_count'],request_result_count=proof['joined_request_result_count'],error_attempt_count=proof['joined_error_attempt_count'],unanswered_attempt_count=0),
        proof_href='common-state/recovery/proofs/'+cid+'.json',proof_sha256=ps,
        trace_href='common-state/recovery/traces/'+cid+'.json',trace_sha256=h('joinedtrace'),replay_href=None,replay_sha256=None)
    overlay['continuations'].append(child);proofs[cid]=raw
    if rankable:
        effective=deepcopy(child);effective.update(id=original['id'],logical_trial_id=original['id'],source_run_id=cid,
            record_kind='technical_resolution',base_protocol_sha256=PROTOCOL_SHA256)
        overlay['resolutions'].append(dict(original_trial_id=original['id'],child_run_id=cid,parent_episode_sha256=slot['parent_episode_sha256'],
            child_episode_sha256=h('childbytes'),proof_href=child['proof_href'],proof_sha256=ps,**{key:True for key in release.VERIFIED},effective_trial=effective))
    return child,proof


class RecoveryReleaseTests(unittest.TestCase):
    def test_pending_and_one_effective_logical_record(self):
        base,overlay,proofs=fixture();original=deepcopy(base)
        self.assertEqual(release.normalise(base,overlay,proofs)['logical_trials'],66)
        child,proof=add_child(base,overlay,proofs)
        value=release.normalise(base,overlay,proofs)
        self.assertEqual(base,original);self.assertEqual(value['logical_trials'],66);self.assertEqual(value['resolved_slots'],1)
        self.assertEqual(value['effective_trials'][0]['source_run_id'],child['id'])
        self.assertEqual(value['effective_trials'][0]['phase'],'technical_recovery')
        self.assertIsNone(value['effective_trials'][0]['cost_usd']);self.assertIsNone(value['effective_trials'][0]['cost_estimate_usd'])
        self.assertEqual(child['cost_provenance']['joined_attempt_count'],5)

    def test_infrastructure_child_never_resolves_quality(self):
        base,overlay,proofs=fixture();add_child(base,overlay,proofs,rankable=False)
        value=release.normalise(base,overlay,proofs)
        self.assertEqual(value['resolved_slots'],0);self.assertFalse(value['effective_trials'][0]['rankable'])

    def test_forged_metrics_source_checkpoint_cost_and_duplicate_rejected(self):
        for kind in ('metrics','parent','checkpoint','proofbytes','duplicate','pin','budget','asset','count','error','unanswered','original_time','manifest'):
            base,overlay,proofs=fixture();child,proof=add_child(base,overlay,proofs)
            if kind=='metrics':child.update(progress_pct=100.,flag_get=True,completed=True,status='completed')
            if kind=='parent':base['trials'][0]['attempt_proof']['source_episode_sha256']=h('wrong-parent')
            if kind=='checkpoint':child['checkpoint']=dict(child['checkpoint'],checkpoint_native_frame=0)
            if kind=='proofbytes':proofs[child['id']]+=b' '
            if kind=='duplicate':overlay['resolutions'].append(deepcopy(overlay['resolutions'][0]))
            if kind=='pin':overlay['manifest']['slots'][0]['pin_payload']['provider']={'only':['wrong'],'allow_fallbacks':False}
            if kind=='budget':child['native_frames']=6001
            if kind=='count':child['attempt_proof']['request_intent_count']-=1
            if kind=='error':child['attempt_proof']['error_attempt_count']-=1
            if kind=='unanswered':child['attempt_proof']['unanswered_attempt_count']=1
            if kind=='original_time':base['trials'][0]['attempt_proof']['terminal_at_utc']='2026-11-01T02:00:00+00:00'
            if kind=='manifest':base['release_provenance']['source_manifest_sha256']=h('othermanifest')
            if kind=='asset':overlay['resolutions'][0]['effective_trial']['trace_sha256']=h('wrong-video')
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):release.normalise(base,overlay,proofs)
        base,overlay,proofs=fixture();child,proof=add_child(base,overlay,proofs)
        child_only=aggregate_receipts([dict(openrouter_cost_usd=.02,is_byok=False)],coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True)
        with self.assertRaises(RuntimeError):release.joined_cost(child_only,proof)

    def test_trace_composes_prefix_and_suffix_without_reusing_ids(self):
        def rows(index,before,after):
            return [dict(event='action',decision_index=index,frame_before=before,requested_frames=4,buttons=['right']),
                    dict(event='request_result',decision_index=index,valid=True,request_sha256=h(str(index)),
                         raw_response=dict(id='gen-private-'+str(index),model='fixture',provider='Fixture',answers={})),
                    dict(event='chunk_end',decision_index=index,frame=after,actual_frames=after-before,
                         observation_sha256=h('obs'),screen_sha256=h('rgb'),native_frame_hashes=[])]
        prefix=release._actions(rows(0,0,4));suffix=release._actions(rows(1,4,6))
        joined=prefix+suffix
        self.assertEqual([a['index'] for a in joined],[0,1])
        self.assertEqual([a['actual_frames'] for a in joined],[4,2])
        self.assertEqual(joined[0]['frame_after'],joined[1]['frame_before'])
        self.assertNotIn('gen-private',json.dumps(joined))
        self.assertEqual(joined[1]['sequence'],[[2,['right']]])

    def test_valid_native_outcome_cannot_be_selected_for_recovery(self):
        base,overlay,proofs=fixture();base['trials'][0].update(status='game_over',rankable=True,death=True)
        with self.assertRaises(RuntimeError):release.normalise(base,overlay,proofs)


if __name__=='__main__':unittest.main()
