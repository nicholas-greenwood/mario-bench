"""Portable release-boundary tests; synthetic fixtures never authorise real results."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark.client import digest
from benchmark.common_image_final_results import aggregates
from benchmark.common_state_release import validate_trial_cost
from benchmark.costs import aggregate_receipts
from benchmark import common_image_final_release as release
from benchmark.run import write_json


def fixture():
    jobs=[];models=[]
    for model in range(16):
        mid=f'synthetic-{model}';models.append(dict(id=mid,name=mid))
        for repeat in range(3):jobs.append(dict(episode_id=f'{mid}-repeat{repeat}',model_id=mid,track='image',repeat_id=repeat,local_rng_seed=101+repeat,temperature=.05,emulator_seed=0))
    return dict(protocol_id='synthetic-not-actual-authority',frozen_at_utc='2026-11-01T00:00:00+00:00',models=models,repeat_schedule=jobs)


def result(manifest,job):
    return dict(episode_id=job['episode_id'],phase='evaluation',protocol_sha256=digest(manifest),**{k:v for k,v in job.items() if k!='episode_id'},
                native_replay_verified=True,status='game_over',rankable=True,progress_pct=10.,max_progress_x=352.1,frames=7,native_frames=7,decisions=1,
                native_frame_budget=6000,life_budget=1,cadence_native_frames=7,started_at_utc='2026-11-01T00:01:00+00:00',
                flag_get=False,death=True,completed=False,technical_pending=False,native_frames_to_completion=None)


def events(manifest,job):
    eid=job['episode_id'];identity=dict(episode_id=eid,decision_index=0,stage='motor',attempt=0,request_sha256=digest({'fixture':True}))
    rows=[dict(event='episode_start',episode_id=eid,job=job,protocol_sha256=digest(manifest),utc='2026-11-01T00:01:00+00:00'),
          dict(event='request_intent',body={'fixture':True},**identity),
          dict(event='request_result',valid=True,http_status=200,raw_response=dict(id='gen-synthetic-only',model='Synthetic',provider='Synthetic',answers={}),**identity),
          dict(event='action',episode_id=eid,decision_index=0,frame_before=0,requested_frames=7,buttons={'horizontal':'right'}),
          dict(event='chunk_end',episode_id=eid,decision_index=0,frame=7,actual_frames=7,observation_sha256='obs',screen_sha256='rgb',native_frame_hashes=[]),
          dict(event='episode_end',episode_id=eid,utc='2026-11-01T00:02:00+00:00')]
    return rows


class ImageReleaseTests(unittest.TestCase):
    def project(self,rows,manifest,job,scored):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'episodes').mkdir();path=root/'episodes'/(job['episode_id']+'.jsonl')
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows));write_json(path.with_suffix('.audit.json'),{'fixture':True})
            with patch.object(release,'PROTOCOL_SHA256',digest(manifest)):
                return release.project_trial(root,manifest,job,scored)

    def test_all48_slots_and16_rows_no_incomplete_mean(self):
        m=fixture();records=[]
        for job in m['repeat_schedule'][:3]:
            r=result(m,job);r.update(id=job['episode_id']);records.append(r)
        rows=aggregates(m,records[:2]);self.assertEqual(len(rows),16);self.assertIsNone(rows[0]['mean_progress_pct'])
        rows=aggregates(m,records);self.assertEqual(rows[0]['mean_progress_pct'],10.);self.assertEqual(sum(r['coverage_complete'] for r in rows),1)
        self.assertEqual(sum(len(r['expected_trial_ids']) for r in rows),48);self.assertTrue(all(r['mean_progress_pct'] is None for r in rows[1:]))
        records[-1].update(status='infra_error',rankable=False,progress_pct=None,technical_pending=True)
        self.assertIsNone(aggregates(m,records)[0]['mean_progress_pct'])

    def test_projection_origin_attempt_proof_and_privacy(self):
        m=fixture();job=m['repeat_schedule'][0];rows=events(m,job);scored=result(m,job)
        trial,trace,ids=self.project(rows,m,job,scored)
        self.assertEqual(ids,['gen-synthetic-only']);self.assertEqual(trial['attempt_proof']['request_intent_count'],1)
        self.assertEqual(trial['native_frames'],7);self.assertIsNone(trial['cost_usd']);self.assertIsNone(trial['cost_estimate_usd'])
        self.assertEqual(trace['actions'][0]['chosen_action']['requested_frames'],7)
        self.assertNotIn('gen-synthetic-only',json.dumps(dict(trial=trial,trace=trace)))
        self.assertEqual(trace['attempt_proof'],trial['attempt_proof'])

    def test_forged_http_ids_unconsumed_actions_and_ledger_rejected(self):
        for kind in ('id','http','http_bool','duplicate','response_without_intent','after_terminal','actions','native_frames'):
            m=fixture();job=m['repeat_schedule'][0];rows=events(m,job);scored=result(m,job)
            if kind=='id':rows[2]['raw_response']['id']='fake-response'
            if kind=='http':rows[2]['http_status']=500
            if kind=='http_bool':rows[2]['http_status']=True
            if kind=='duplicate':rows.insert(3,deepcopy(rows[2]))
            if kind=='response_without_intent':rows.pop(1)
            if kind=='after_terminal':rows.insert(-1,dict(rows[1],decision_index=1))
            if kind=='actions':rows.insert(4,deepcopy(rows[3]))
            if kind=='native_frames':scored['frames']=8
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):self.project(rows,m,job,scored)

    def test_closed_fresh_exact_job_capture_required(self):
        for kind in ('open','time','job','scope','historical','unknown'):
            m=fixture();job=m['repeat_schedule'][0];rows=events(m,job)
            if kind=='open':rows.pop()
            if kind=='time':rows[-1]['utc']='2026-11-01T03:00:00+00:00'
            if kind=='job':rows[0]['job']=dict(job,local_rng_seed=9001)
            if kind=='scope':rows[2]['episode_id']='other'
            if kind=='historical':rows[0]['utc']='2026-10-31T23:00:00+00:00'
            if kind=='unknown':rows.insert(-1,dict(event='request_error',episode_id=job['episode_id']))
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):release.validate_log(rows,job,m,'2026-11-01T02:00:00+00:00')

    def test_117_attempts_cannot_take_116_receipt_certificate(self):
        known=aggregate_receipts([dict(openrouter_cost_usd=.01,is_byok=False)]*116,coverage_complete=True,includes_retries=True,includes_auxiliary_calls=True)
        with self.assertRaises(RuntimeError):validate_trial_cost(known,dict(request_intent_count=117,error_attempt_count=1,unanswered_attempt_count=0))

    def test_cutoff_census_cannot_omit_closed_or_prescribed_slots(self):
        m=fixture();stamp='2026-11-01T02:00:00+00:00';items=[]
        for i,j in enumerate(m['repeat_schedule']):
            items.append(dict(episode_id=j['episode_id'],**{k:j[k] for k in ('model_id','repeat_id','local_rng_seed')},closed_at_cutoff=i<3,terminal_utc=stamp if i<3 else None,source_episode_sha256=str(i) if i<3 else None))
        capture=dict(captured_at_utc=stamp,source_episode_sha256={r['episode_id']:r['source_episode_sha256'] for r in items[:3]})
        census=dict(protocol_sha256=digest(m),captured_at_utc=stamp,scheduled=48,closed=3,pending=45,episodes=items)
        release.validate_census(m,capture,census)
        omitted=deepcopy(capture);omitted['source_episode_sha256'].pop(items[0]['episode_id'])
        with self.assertRaises(RuntimeError):release.validate_census(m,omitted,census)
        missing=deepcopy(census);missing['episodes'].pop()
        with self.assertRaises(RuntimeError):release.validate_census(m,capture,missing)


if __name__=='__main__':unittest.main()
