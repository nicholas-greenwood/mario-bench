"""Offline native/PNG/MT/retry tests. Synthetic receipts never enter public data."""
from copy import deepcopy
import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark import common_image_recovery as R
from benchmark.client import digest
from benchmark.run import write_json


def fixture(root,mode='fresh_after_observed_failures'):
    model=R.E.roster()[0][0];eid='synthetic-image-parent';job=dict(episode_id=eid,model_id=model['id'],track='image',repeat_id=1,local_rng_seed=102,temperature=.05,emulator_seed=0)
    pm=dict(policy='fake',models=[model],repeat_schedule=[job],controller_contracts={'synthetic':True},timeout_seconds=1,retries_after_initial=2,minimum_request_spacing_seconds=0)
    g=R.MarioGame(level='1-1');s=R.E.CommonSession(model,'image',temperature=.05,sampler_seed=102);maximum=40.;history=[]
    rows=[dict(event='episode_start',episode_id=eid,job=job,protocol_sha256=digest(pm),initial_observation_sha256=digest(g.observe()),initial_screen_sha256=R.E.screen_hash(g),utc='2026-11-01T00:00:00+00:00')]
    try:
        for i in (0,1):
            s.begin_image(R.E.rgb_png(g),frame=g.frame);body=s.body('motor');valid=i==0 or mode=='reuse_recorded_valid_response'
            count=1 if valid or mode=='unanswered_no_resend' else 3
            for attempt in range(count):
                ident=dict(episode_id=eid,decision_index=i,stage='motor',attempt=attempt,frame=g.frame,request_sha256=digest(body))
                rows.append(dict(event='request_intent',body=body,**ident))
                if i==1 and mode=='unanswered_no_resend':break
                raw=R.E.fixture_response(model,body,i) if valid else None
                rows.append(dict(event='request_result',valid=valid,retryable=not valid,raw_response=raw,http_status=None if valid else 503,frame_after_request=g.frame,**ident))
            if i==1:break
            choice=s.choose(raw,body);action=R.plain(dict(event='action',episode_id=eid,decision_index=i,frame_before=g.frame,observation_sha256=digest(g.observe()),**choice,frames=7));rows.append(action)
            maximum,chunk=R.advance(g,s,choice,i,eid,maximum,history);rows.append(chunk)
        cp=R.checkpoint(g,s,body,model,digest(pm['controller_contracts']),history)
        rows.append(dict(event='episode_end',episode_id=eid,result=dict(status='infra_error',frames=g.frame,decisions=s.index,max_progress_x=maximum),utc='2026-11-01T00:01:00+00:00'))
        path=root/'parent.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        slot=dict(original_trial_id=eid,child_run_id=eid+'--image-technical-recovery-v1',parent_episode_path=str(path),parent_episode_sha256=R.sha(path),checkpoint=cp,
                  **{k:job[k] for k in ('model_id','track','repeat_id','local_rng_seed','temperature','emulator_seed')},failed_decision_index=1,parent_valid_native_actions=1,parent_http_attempts=sum(r['event']=='request_intent' for r in rows),
                  continuation_mode=mode,parent_max_progress_x=maximum,remaining_native_frame_budget=6000-g.frame,provider_outcome_unknown_attempt_count=R.unknown_attempts(rows))
        slot.update(inherited_parent_valid_response_sha256=digest(raw) if mode=='reuse_recorded_valid_response' else None,
                    inherited_parent_receipt_id_sha256=hashlib.sha256(raw['id'].encode()).hexdigest() if mode=='reuse_recorded_valid_response' else None)
        return pm,slot,rows
    finally:g.close()


class FakeClient:
    calls=[]
    def __init__(self,key,model,timeout,decoder):self.model=model;self.decoder=decoder
    def call(self,body):
        self.calls.append(digest(body))
        if len(self.calls)==1:
            raw=R.E.fixture_response(self.model,body,1)
            return dict(valid=True,retryable=False,raw_response=raw,http_status=None,request_sha256=digest(body))
        return dict(valid=False,retryable=True,raw_response=None,http_status=503,request_sha256=digest(body))
    def close(self):pass


class FailedClient(FakeClient):
    calls=[]
    def call(self,body):
        self.calls.append(digest(body))
        return dict(valid=False,retryable=True,raw_response=None,http_status=503,request_sha256=digest(body))


class RecoveryTests(unittest.TestCase):
    def test_exact22_source_archive_missing_tampered_and_extra_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);hashes=R.source_hashes();self.assertEqual(len(hashes),22)
            R.archive_sources(root,hashes);R.verify_source_archive(root,hashes)
            original='benchmark/common_image_v2_policy.py';target=root/'sources'/original;raw=target.read_bytes()
            target.unlink()
            with self.assertRaises(RuntimeError):R.verify_source_archive(root,hashes)
            target.write_bytes(raw+b'\n# changed\n')
            with self.assertRaises(RuntimeError):R.verify_source_archive(root,hashes)
            with self.assertRaises(RuntimeError):R.archive_sources(root,hashes)
            target.write_bytes(raw);R.verify_source_archive(root,hashes)
            (root/'sources/unregistered.py').write_text('# unexpected')
            with self.assertRaises(RuntimeError):R.verify_source_archive(root,hashes)

    def test_exact_prefix_png_controls_mt_and_no_double_begin(self):
        with tempfile.TemporaryDirectory() as temp:
            pm,slot,rows=fixture(Path(temp));g,s,maximum,history,cp,source,body,failed=R.restore(slot,pm)
            try:
                self.assertEqual(g.frame,7);self.assertEqual(s.index,1);self.assertEqual(cp['rng_draw_count'],1);self.assertEqual(cp['rng_mt_index'],2)
                self.assertEqual(cp['rng_state_sha256'],digest(s.rng.getstate()));self.assertEqual(cp['previous_images'][0]['frame'],0)
                self.assertEqual(digest(s.body('motor')),cp['failed_request_sha256'])
                with self.assertRaises(ValueError):s.begin_image(R.E.rgb_png(g),frame=g.frame)
                before=s.rng.getstate();out,error=R.E.stage_call(s,'motor',body,path=None,episode_id=slot['original_trial_id'],index=1,game=g,prior=failed,audit=True,manifest=pm,client=None)
                self.assertIsNotNone(error);self.assertEqual(s.rng.getstate(),before);self.assertEqual(g.frame,7)
            finally:g.close()

    def test_wrong_seed_temperature_source_body_pin_budget_fail_before_client(self):
        for field in ('seed','temperature','source','body','pin','rng','controls','budget','shortened_budget','mode'):
            with tempfile.TemporaryDirectory() as temp:
                pm,slot,rows=fixture(Path(temp));bad=deepcopy(slot)
                if field=='seed':bad['local_rng_seed']=103
                if field=='temperature':bad['temperature']=.2
                if field=='source':bad['parent_episode_sha256']='wrong'
                if field=='body':bad['checkpoint']['failed_request_sha256']='wrong'
                if field=='pin':bad['checkpoint']['pin_sha256']='wrong'
                if field=='rng':bad['checkpoint']['rng_state'][1][0]+=1
                if field=='controls':bad['checkpoint']['session_controls'][0]['frames']=6
                if field=='budget':bad['remaining_native_frame_budget']+=1
                if field=='shortened_budget':bad['remaining_native_frame_budget']-=1
                if field=='mode':bad['continuation_mode']='unanswered_no_resend'
                with self.subTest(field=field),patch.object(R,'Client',side_effect=AssertionError('network forbidden')),self.assertRaises(RuntimeError):R.restore(bad,pm)

    def test_retry_resume_does_not_resample_and_wholeprefix_grade_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pm,slot,rows=fixture(root);out=root/'child';out.mkdir();m=dict(frozen_at_utc='2026-11-01T00:02:00+00:00',slots=[slot],retries_after_initial=2,minimum_request_spacing_seconds=0,policy='openrouter',timeout_seconds=1)
            FakeClient.calls=[]
            with patch.object(R,'verify',return_value=(m,pm)),patch.object(R,'Client',FakeClient),patch.dict(os.environ,{'OPENROUTER_API_KEY':'offline-fixture'}):
                live=R.execute_one(out,m,pm,slot)
            self.assertEqual(len(FakeClient.calls),4);self.assertEqual(live['status'],'infra_error');self.assertEqual(live['frames'],14);self.assertEqual(live['continuation_decisions'],1)
            before=(out/'episodes'/(slot['child_run_id']+'.jsonl')).read_bytes()
            with patch.object(R,'Client',side_effect=AssertionError('audit network forbidden')):audited=R.execute_one(out,m,pm,slot,audit=True)
            self.assertEqual(before,(out/'episodes'/(slot['child_run_id']+'.jsonl')).read_bytes());self.assertEqual(audited['frames'],live['frames'])
            self.assertGreaterEqual(audited['max_progress_x'],slot['parent_max_progress_x']);self.assertEqual(audited['checkpoint']['rng_draw_count'],1)
            proof=R.read(out/'episodes'/(slot['child_run_id']+'.audit.json'));self.assertEqual(proof['joined_attempt_count'],slot['parent_http_attempts']+4)

    def test_unanswered_parent_never_resends_or_advances(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pm,slot,rows=fixture(root,'unanswered_no_resend');out=root/'child';out.mkdir();m=dict(frozen_at_utc='2026-11-01T00:02:00+00:00',slots=[slot])
            with patch.object(R,'verify',return_value=(m,pm)),patch.object(R,'Client',side_effect=AssertionError('no resend')):r=R.execute_one(out,m,pm,slot)
            self.assertEqual(r['status'],'infra_error');self.assertEqual(r['continuation_native_frames'],0);self.assertEqual(r['decisions'],1)
            with patch.object(R,'Client',side_effect=AssertionError('no audit calls')):R.execute_one(out,m,pm,slot,audit=True)

    def test_received_parent_pending_choice_reused_one_draw_no_duplicate_billing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pm,slot,rows=fixture(root,'reuse_recorded_valid_response');out=root/'child';out.mkdir()
            m=dict(frozen_at_utc='2026-11-01T00:02:00+00:00',slots=[slot],retries_after_initial=2,minimum_request_spacing_seconds=0,policy='openrouter',timeout_seconds=1)
            FailedClient.calls=[]
            with patch.object(R,'verify',return_value=(m,pm)),patch.object(R,'Client',FailedClient),patch.dict(os.environ,{'OPENROUTER_API_KEY':'offline-fixture'}):live=R.execute_one(out,m,pm,slot)
            self.assertEqual(live['frames'],14);self.assertEqual(live['continuation_decisions'],1);self.assertEqual(len(FailedClient.calls),3)
            self.assertNotEqual(FailedClient.calls[0],slot['checkpoint']['failed_request_sha256'])
            child=R.read_events(out/'episodes'/(slot['child_run_id']+'.jsonl'))
            self.assertEqual(sum(r['event']=='inherited_valid_response' for r in child),1)
            self.assertFalse(any(r['event']=='request_intent' and r['decision_index']==1 for r in child))
            with patch.object(R,'Client',side_effect=AssertionError('no audit calls')):R.execute_one(out,m,pm,slot,audit=True)
            proof=R.read(out/'episodes'/(slot['child_run_id']+'.audit.json'));self.assertEqual(proof['inherited_parent_valid_choice_count'],1)

    def test_crash_after_response_or_action_replays_same_single_draw(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pm,slot,rows=fixture(root);full=root/'full';full.mkdir()
            m=dict(frozen_at_utc='2026-11-01T00:02:00+00:00',slots=[slot],retries_after_initial=2,minimum_request_spacing_seconds=0,policy='openrouter',timeout_seconds=1)
            FakeClient.calls=[]
            with patch.object(R,'verify',return_value=(m,pm)),patch.object(R,'Client',FakeClient),patch.dict(os.environ,{'OPENROUTER_API_KEY':'offline-fixture'}):R.execute_one(full,m,pm,slot)
            original=R.read_events(full/'episodes'/(slot['child_run_id']+'.jsonl'));at=next(i for i,r in enumerate(original) if r['event']=='action');action=original[at]
            for cut in (at,at+1):
                out=root/str(cut);(out/'episodes').mkdir(parents=True);path=out/'episodes'/(slot['child_run_id']+'.jsonl')
                path.write_text(''.join(json.dumps(r)+'\n' for r in original[:cut]));FailedClient.calls=[]
                with patch.object(R,'verify',return_value=(m,pm)),patch.object(R,'Client',FailedClient),patch.dict(os.environ,{'OPENROUTER_API_KEY':'offline-fixture'}):r=R.execute_one(out,m,pm,slot)
                replayed=next(r for r in R.read_events(path) if r['event']=='action')
                self.assertEqual({k:v for k,v in replayed.items() if k!='utc'},{k:v for k,v in action.items() if k!='utc'})
                self.assertEqual(len(FailedClient.calls),3);self.assertEqual(r['frames'],14)

    def test_valid_then_retry_and_post_terminal_rows_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            pm,slot,rows=fixture(Path(temp));broken=deepcopy(rows);broken[2]['valid']=True
            # A second attempt after the valid result is impossible, even with no action yet.
            extra=dict(broken[1],attempt=1);broken.insert(3,extra)
            with self.assertRaises(RuntimeError):R.validate_ledger(broken,slot['original_trial_id'])
            with self.assertRaises(RuntimeError):R.validate_ledger(rows+[deepcopy(rows[1])],slot['original_trial_id'])

    def test_last7_truncates_to1_and_preserves_prefix_maximum(self):
        class Game:
            frame=5999;done=False;flag_get=False
            class Env:
                class Ram:
                    def tobytes(self):return b'native'
                ram=Ram()
            env=Env()
            def step(self,buttons):self.frame+=1;return {}
            def observe(self):return {}
        class Session:
            def advance(self,**values):self.values=values
        game,session=Game(),Session()
        with patch.object(R.E,'screen_hash',return_value='rgb'),patch.object(R,'validated_progress_x',return_value=45):maximum,chunk=R.advance(game,session,dict(requested_frames=7,buttons={}),857,'fixture',500.,[])
        self.assertEqual(chunk['actual_frames'],1);self.assertEqual(game.frame,6000);self.assertEqual(maximum,500.);self.assertEqual(session.values['actual_frames'],1)


if __name__=='__main__':unittest.main()
