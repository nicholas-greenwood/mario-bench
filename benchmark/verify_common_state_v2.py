"""Offline proof of the globally shared compact-state calibration revision."""
import json
from pathlib import Path
import tempfile
import unittest
from benchmark.client import digest
from benchmark.common_state_compact_v2 import request
from benchmark.common_state_runtime_v2 import StateCompactSession
from benchmark.common_state_run_v2 import execute_episode,plan,verify_manifest,validate_preflight,roster
from prototype.emulator import MarioGame

class StateV2Tests(unittest.TestCase):
    def test_all302_captured_requests_match_neutral_definition(self):
        source=Path(__file__).resolve().parents[1]/'results/traces/pplx-state-clear.json'
        trace=json.loads(source.read_text());model=next(m for m in roster()[0] if m['id']=='perplexity/pplx-decider-v1.2');game=MarioGame()
        try:
            for action in trace['actions']:
                body=request(model,game.observe())
                self.assertEqual(body['questions'],trace['contract']['questions'])
                self.assertEqual(digest(body),action['request_sha256'])
                for frames,buttons in action['sequence']:
                    for _ in range(frames):game.step(buttons)
                self.assertEqual(digest(game.observe()),action['after_observation_sha256'])
            self.assertEqual(len(trace['actions']),302);self.assertEqual(game.frame,1208);self.assertTrue(game.flag_get)
        finally:game.close()
    def test_state_only_has_no_image_or_sampler(self):
        model=roster()[0][0]
        with self.assertRaises(ValueError):StateCompactSession(model,'image',temperature=.05,sampler_seed=9001)
    def test_native_budget_replay_and_completed_resume_costs(self):
        model=next(m for m in roster()[0] if m['id'].startswith('perplexity/pplx-decider-v1.2'));game=MarioGame();initial=game.observe();game.close()
        cfg=dict(models=[model],timeout_seconds=60,policy='fake',native_frame_cap=3,retries_after_initial=2,phase='offline_test',initial_observation_sha256=digest(initial));job=dict(episode_id='offline-state-v2',model_id=model['id'],track='state',temperature=None,local_rng_seed=None,repeat_id=0)
        with tempfile.TemporaryDirectory() as directory:
            first=execute_episode(directory,cfg,job);self.assertEqual(first['frames'],3);again=execute_episode(directory,cfg,job);self.assertEqual(first['cost_provenance'],again['cost_provenance']);proof=execute_episode(directory,cfg,job,audit=True);self.assertTrue(proof['native_replay_verified'])
    def test_preregistration_and_fake_preflight_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            m=plan('preflight',directory,policy='fake');self.assertEqual(len(m['repeat_schedule']),22);self.assertEqual(m['image_eligible_models'],[]);verify_manifest(m,directory)
            p=Path(directory)/'summary.json';p.write_text(json.dumps(dict(accepted=True,policy='openrouter')))
            with self.assertRaises(RuntimeError):validate_preflight(p)
            m['repeat_schedule'].pop()
            with self.assertRaises(RuntimeError):verify_manifest(m,directory)
    def test_cannot_launch_final_from_state_gate_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError,'cannot launch a final cohort'):plan('evaluation',directory,policy='fake')

if __name__=='__main__':unittest.main()
