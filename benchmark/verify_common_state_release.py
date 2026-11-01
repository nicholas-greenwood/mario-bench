"""Portable release-projection unit tests; optional real copied-snapshot audit.

Default tests mock source authority/native execution explicitly and never claim
synthetic traces are actual benchmark results. --snapshot invokes the real engine.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark.client import digest
from benchmark.common_results import aggregate_trials
from benchmark.run import write_json
from benchmark import common_state_release as release


class ReleaseTests(unittest.TestCase):
    def manifest(self, calibration):
        models = [dict(id=f'model{i}', name=f'Model {i}', request_model=f'model{i}-dated',
                       expected_returned_model=f'model{i}-dated', provider=dict(only=['provider'], allow_fallbacks=False),
                       expected_returned_provider_names=['Provider']) for i in range(22)]
        schedule = [dict(episode_id=f'fixture-model{i}-repeat{r}', model_id=f'model{i}', track='state', repeat_id=r,
                         local_rng_seed=None, emulator_seed=0, temperature=None) for i in range(22) for r in range(3)]
        return dict(protocol_id='synthetic-unit-fixture', phase='evaluation', evaluation_scope='state_only', tracks=['state'],
                    preregistered=True, frozen_at_utc='2026-11-01T00:00:00+00:00', cohort_id='fixture',
                    repeat_schedule=schedule, native_frame_budget=6000, life_budget=1, cadence_native_frames=4,
                    image_evaluation_status='calibration_pending', pilot_selection_evidence={},
                    observation_and_controller_hashes={}, actual_rom_sha256='fixture', initial_observation_sha256='fixture',
                    initial_screen_sha256='fixture', models=models, policy='openrouter', software_sha256={},
                    controller_contracts={}, authority_paths=dict(calibration=str(calibration)))

    def result(self, manifest, job, progress=40, technical=False):
        return dict(episode_id=job['episode_id'], id=job['episode_id'], model_id=job['model_id'],
                    track='state', status='infra_error' if technical else 'frame_budget', rankable=not technical,
                    progress_pct=None if technical else progress, max_progress_x=40, repeat_id=job['repeat_id'],
                    local_rng_seed=None, emulator_seed=0, temperature=None, native_frames_to_completion=None,
                    native_frame_budget=6000, life_budget=1, native_replay_verified=False,
                    started_at_utc='2026-11-01T00:01:00+00:00', decisions=0, flag_get=False, death=False,
                    technical_pending=technical, frames=0, phase='evaluation', protocol_sha256=digest(manifest))

    def test_denominator_missing_and_technical_never_fake_zero(self):
        m = self.manifest(Path('/unused'))
        trials = []
        for i, job in enumerate(m['repeat_schedule'][:3]):
            row = self.result(m, job, [30, 60, 90][i]);row['native_replay_verified'] = True
            trials.append(row)
        rows = aggregate_trials(m, trials)
        self.assertEqual(len(rows), 22);self.assertEqual(rows[0]['mean_progress_pct'], 60)
        self.assertTrue(all(row['mean_progress_pct'] is None for row in rows[1:]))
        trials[-1].update(rankable=False, progress_pct=None, status='infra_error')
        self.assertIsNone(aggregate_trials(m, trials)[0]['mean_progress_pct'])

    def test_actual_origin_attempt_counts_and_pending_receipts(self):
        rows = [dict(event='request_intent', decision_index=0, stage='motor', attempt=0, request_sha256='a'),
                dict(event='request_result', decision_index=0, stage='motor', attempt=0, request_sha256='a',
                     valid=False, http_status=502, raw_response={'error': {'code':502}}),
                dict(event='request_intent', decision_index=0, stage='motor', attempt=1, request_sha256='a'),
                dict(event='request_result', decision_index=0, stage='motor', attempt=1, request_sha256='a',
                     valid=True, http_status=200, raw_response={'id':'gen-fixture-actual', 'usage':{'cost':0}}),
                dict(event='request_intent', decision_index=1, stage='motor', attempt=0, request_sha256='b')]
        attempts, proof, ids = release.attempt_evidence(rows)
        self.assertEqual((proof['request_intent_count'], proof['request_result_count'], proof['error_attempt_count'],
                          proof['unanswered_attempt_count']), (3, 2, 1, 1))
        self.assertNotIn('gen-fixture-actual', json.dumps(attempts))
        for field, value in [('id', 'offline-0'), ('id', None)]:
            bad = deepcopy(rows);bad[3]['raw_response'][field] = value
            with self.assertRaises(RuntimeError):release.attempt_evidence(bad)
        for status in (True, None, 429):
            bad = deepcopy(rows);bad[3]['http_status'] = status
            with self.assertRaises(RuntimeError):release.attempt_evidence(bad)

    def test_billing_cannot_drop_source_error_and_estimates_are_not_actual(self):
        from benchmark.costs import aggregate_receipts
        receipts=[dict(openrouter_cost_usd=.001,is_byok=False) for _ in range(116)]
        cost=aggregate_receipts(receipts,coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True)
        proof=dict(request_intent_count=117,error_attempt_count=1,unanswered_attempt_count=0)
        with self.assertRaises(RuntimeError):release.validate_trial_cost(cost,proof)
        cost['cost_provenance'].update(request_count=117,source_request_count=117,source_attempt_count=117,
                                       costed_request_count=117,actual_costed_request_count=117)
        with self.assertRaises(RuntimeError):release.validate_trial_cost(cost,proof)
        cost['cost_provenance']['error_count']=1
        proof['unanswered_attempt_count']=1
        with self.assertRaises(RuntimeError):release.validate_trial_cost(cost,proof)
        m=self.manifest(Path('/unused'));trials=[]
        for job,estimate in zip(m['repeat_schedule'][:3],[.01,.02,.03]):
            trial=self.result(m,job);trial['native_replay_verified']=True
            value=aggregate_receipts([dict(openrouter_cost_usd=0,is_byok=True,byok_upstream_estimated_cost_usd=estimate)],
                                     coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True)
            trial.update(value);trial['attempt_proof']=dict(request_intent_count=1,error_attempt_count=0,unanswered_attempt_count=0);trials.append(trial)
        row=release.aggregate_release_trials(m,trials)[0]
        self.assertIsNone(row['mean_actual_cost_usd']);self.assertAlmostEqual(row['mean_cost_estimate_usd'],.02)
        trials[0].update(aggregate_receipts([dict(openrouter_cost_usd=.01,is_byok=False)],coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True))
        mixed=release.aggregate_release_trials(m,trials)[0]
        self.assertIsNone(mixed['actual_cost_total_usd']);self.assertAlmostEqual(mixed['cost_total_estimate_usd'],.06)

    def test_copy_only_audit_projection_and_capture_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp);source=base/'snapshot';source.mkdir();(source/'episodes').mkdir()
            calibration=base/'calibration';calibration.mkdir();write_json(calibration/'selection.json', {'fixture':True})
            m=self.manifest(calibration);write_json(source/'manifest.json',m);write_json(source/'preregistration.json',{'fixture':True})
            recorded={}
            for i,job in enumerate(m['repeat_schedule'][:3]):
                result=self.result(m,job,[30,60,90][i]);path=source/'episodes'/(job['episode_id']+'.jsonl')
                rows=[dict(event='episode_start',episode_id=job['episode_id'],job=job,protocol_sha256=digest(m),utc=result['started_at_utc']),
                      dict(event='episode_end',episode_id=job['episode_id'],result=result,utc='2026-11-01T00:02:00+00:00')]
                path.write_text(''.join(json.dumps(row)+'\n' for row in rows));recorded[job['episode_id']]=release.sha(path)
            capture=dict(captured_at_utc='2026-11-01T01:00:00+00:00',protocol_sha256=digest(m),
                         source_manifest_sha256=release.sha(source/'manifest.json'),source_preregistration_sha256=release.sha(source/'preregistration.json'),source_episode_sha256=recorded)
            write_json(source/'capture.json',capture)
            original={p.name:p.read_bytes() for p in (source/'episodes').iterdir()}
            destination=base/'public';destination.mkdir();(destination/'legacy.json').write_text('untouched')
            calls=[]
            def audit(directory, manifest, job, *, audit):
                self.assertTrue(audit);self.assertNotEqual(Path(directory).resolve(), source.resolve())
                path=Path(directory)/'episodes'/(job['episode_id']+'.jsonl')
                self.assertEqual(release.sha(path),recorded[job['episode_id']]);calls.append(job['episode_id'])
                result=json.loads(path.read_text().splitlines()[-1])['result'];result['native_replay_verified']=True
                write_json(path.with_suffix('.audit.json'),dict(verified=True,fixture=True))
                return result
            with patch.object(release,'PROTOCOL_SHA256',digest(m)), patch.object(release,'MANIFEST_SHA256',release.sha(source/'manifest.json')), \
                 patch.object(release,'REGISTRATION_SHA256',release.sha(source/'preregistration.json')), \
                 patch.object(release.authority,'verify') as authority_check, patch.object(release.engine,'execute_episode',side_effect=audit):
                value=release.export(source,destination)
                self.assertEqual(len(calls),3);self.assertGreaterEqual(authority_check.call_count,2)
                self.assertEqual(len(value['common_benchmark']['rows']),22)
                self.assertEqual(value['common_benchmark']['rows'][0]['mean_progress_pct'],60)
                self.assertEqual(original,{p.name:p.read_bytes() for p in (source/'episodes').iterdir()})
                self.assertEqual((destination/'legacy.json').read_text(),'untouched')
                self.assertNotIn('/Users/',json.dumps(value));self.assertNotIn('gen-',json.dumps(value))
                self.assertTrue(all(row.get('cost_usd') is None for row in value['common_benchmark']['trials']))
                log=next((source/'episodes').glob('*.jsonl'));log.write_text(log.read_text()+'\n')
                with self.assertRaises(RuntimeError):release.validate_snapshot(source)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',type=Path);parser.add_argument('--destination',type=Path);parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseTests))
    if not result.wasSuccessful():raise SystemExit(1)
    if args.snapshot:
        if not args.destination:parser.error('--destination is required with --snapshot')
        value=release.export(args.snapshot,args.destination,jobs=args.jobs)['common_benchmark']
        print(json.dumps(dict(real_snapshot_trials=len(value['trials']),rows=len(value['rows']),complete_model_rows=sum(r['coverage_complete'] for r in value['rows'])),indent=2))
        print(json.dumps(release.verify_public(args.destination),indent=2))


if __name__=='__main__':main()
