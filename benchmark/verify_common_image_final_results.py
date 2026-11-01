"""Offline public projection/cost regression tests; zero inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from benchmark import common_image_final_results as R
from benchmark.costs import aggregate_receipts

OUTPUT=Path('playground/common-image-final/evaluation-openrouter')
class ImageResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models,images,_=R.engine.roster();h='0'*64
        cls.m=dict(protocol_id=R.engine.PROTOCOL_ID,phase='evaluation',evaluation_scope='image_progress_baseline',tracks=['image'],frozen_at_utc='2026-11-01T00:00:00+00:00',level='1-1',temperature=.05,cadence_native_frames=7,requested_native_hold=7,native_frame_budget=6000,life_budget=1,maximum_control_actions=858,models=models,repeat_schedule=R.engine.build_schedule('evaluation',models,images),media=dict(current_full_size=[512,480],past_full_screens=1,own_controls=2),sampling=dict(temperature=.05,final_seeds=[101,102,103]),software_sha256={'synthetic_fixture.py':h},roster_source_sha256=h,actual_rom_sha256=h,initial_observation_sha256=h,initial_screen_sha256=h,observation_and_controller_hashes={'image_controller_sha256':h},acceptance_contract=R.engine.acceptance_contract(dict(protocol_sha256=h,summary_sha256=h,audit_sha256=h,model_count=16,audit_complete=True)))
    def record(self,job,**changes):
        r=dict(job);r['id']=r.pop('episode_id');r.update(phase='evaluation',protocol_sha256=R.digest(self.m),native_frame_budget=6000,life_budget=1,cadence_native_frames=7,native_replay_verified=True,status='game_over',rankable=True,progress_pct=20.,native_frames=100,flag_get=False,death=True,native_frames_to_completion=None);r.update(changes);return r
    def test_pending_projection_is_no_fake_trial_or_score(self):
        with patch.object(R,'load_registration',return_value=self.m):v=R.pending(OUTPUT)['common_benchmark'];self.assertEqual(len(v['rows']),16);self.assertEqual(len(v['manifest']['repeat_schedule']),48);self.assertEqual(v['trials'],[])
        for r in v['rows']:
            for field in ('mean_progress_pct','best_clear_game_seconds','mean_completed_game_seconds','mean_actual_cost_usd','mean_cost_estimate_usd'):self.assertIsNone(r[field])
        self.assertEqual(v['manifest']['acceptance_contract']['track'],'image')
    def test_foreign_seed_and_false_clear_rejected(self):
        job=self.m['repeat_schedule'][0]
        with self.assertRaises(RuntimeError):R.aggregates(self.m,[self.record(job,local_rng_seed=0)])
        with self.assertRaises(RuntimeError):R.aggregates(self.m,[self.record(job,progress_pct=100)])
    def test_infra_three_does_not_mean_zero_or_partial(self):
        jobs=self.m['repeat_schedule'][:3];rs=[self.record(j,rankable=False,status='infra_error',progress_pct=None) for j in jobs];row=R.aggregates(self.m,rs)[0];self.assertIsNone(row['mean_progress_pct']);self.assertEqual(row['valid_trials'],0)
    def test_complete_byok_estimate_is_not_lost_as_false_validator_return(self):
        receipt=aggregate_receipts([dict(openrouter_cost_usd=0,is_byok=True,byok_upstream_estimated_cost_usd=.01)],coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True)
        rs=[dict(self.record(j),**receipt) for j in self.m['repeat_schedule'][:3]];row=R.aggregates(self.m,rs)[0];self.assertIsNone(row['mean_actual_cost_usd']);self.assertAlmostEqual(row['mean_cost_estimate_usd'],.01)
    def test_cost_116_receipts_cannot_cover_117_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'episode.jsonl';events=[]
            for i in range(117):
                ident=dict(decision_index=i,stage='motor',attempt=0);events.extend([dict(event='request_intent',**ident),dict(event='request_result',valid=i<116,**ident)])
            p.write_text(''.join(json.dumps(r)+'\n' for r in events));cost=aggregate_receipts([dict(openrouter_cost_usd=.001,is_byok=False)]*116,coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True);cost['episode_sha256']=R.sha(p);p.with_suffix('.cost.json').write_text(json.dumps(cost))
            with self.assertRaises(RuntimeError):R.cost(p)
    def test_worker_destination_never_overwritten(self):
        with patch.object(R,'load_registration',return_value=self.m):
            with self.assertRaises(RuntimeError):R.export(OUTPUT,OUTPUT/'not-allowed',pending_only=True)
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(RuntimeError):R.export(Path(d)/'common-image',d,pending_only=True)
    def test_fake_registration_never_reaches_preflight_or_published_header(self):
        with tempfile.TemporaryDirectory() as d:
            m=dict(self.m,policy='fake');Path(d,'manifest.json').write_text(json.dumps(m))
            with patch.object(R.engine,'verify_manifest'),patch.object(R.engine,'validate_preflight') as preflight:
                with self.assertRaises(RuntimeError):R.load_registration(d)
                preflight.assert_not_called()
if __name__=='__main__':unittest.main()
