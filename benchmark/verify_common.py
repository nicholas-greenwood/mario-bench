"""Offline acceptance checks for common sensing, sampling and durable recovery."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from benchmark.client import digest
from benchmark.common_policy import CommonSession,DURATIONS,ACTIONS
from benchmark.common_run import fixture,fixture_session,fixture_response,execute_episode,roster,track_model,plan,verify_manifest,validate_preflight,pilot_selection
from benchmark.run import read_events
from prototype.decisions import PolicyError

class CommonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models,_,_=roster();cls.model=next(m for m in cls.models if m['id']=='perplexity/pplx-decider-v1.2')
        cls.state,cls.images,_=fixture()
    def image(self,t=.05,seed=9001):
        s=CommonSession(self.model,'image',temperature=t,sampler_seed=seed)
        for f,p in self.images:
            s.begin_image(p,frame=f)
            if f<12:s.advance(buttons=dict(horizontal='released',vertical='released',jump='released',run='released'),frame_after=f+6,actual_frames=6)
        return s
    def test_pixels_boundary_and_real_maximum_media(self):
        s=self.image();b=s.body('duration');self.assertEqual(sum(isinstance(x,dict) for x in b['state']),4)
        meta=json.loads(b['state'][0]);self.assertEqual(meta['native_frame'],12);self.assertEqual(len(meta['previous_chosen_controls']),2)
        self.assertFalse(any(k in meta for k in ('player','terrain','grounded','velocity','progress','objects')))
        with self.assertRaises(ValueError):s.begin_state(dict(self.state,private_sentinel='FORBIDDEN'))
        with self.assertRaises(TypeError):s.begin_image(self.images[0][1],frame=0,observation=self.state)
    def test_known_duration_without_probability_vector_and_same_images(self):
        s=self.image();first=s.body('duration');raw=fixture_response(s.model,first,0);raw['answers']['duration']['choice']='travel_8';s.accept_duration(raw,first);motor=s.body('motor')
        self.assertEqual(json.loads(motor['state'][0])['next_interval_native_frames'],8)
        self.assertNotIn('probabilities',motor['state'][0]);self.assertEqual(first['state'][1:],motor['state'][1:])
        self.assertEqual(set(motor['questions']['action']['criteria']),set(ACTIONS));self.assertEqual(set(first['questions']['duration']['criteria']),set(DURATIONS))
    def test_temperature_changes_decoder_only(self):
        a=self.image(.05);b=self.image(.2);self.assertEqual(a.body('duration'),b.body('duration'));a.duration=b.duration=6;self.assertEqual(a.body('motor'),b.body('motor'))
    def test_retries_parse_without_consuming_rng(self):
        s=self.image();s.duration=6;b=s.body('motor');raw=fixture_response(s.model,b,0);before=s.rng.getstate()
        s.parse(raw,b);s.parse(raw,b);self.assertEqual(before,s.rng.getstate());choice=s.choose(raw,b);self.assertNotEqual(before,s.rng.getstate());self.assertEqual(len(choice['sampling']['raw_probabilities']),12)
        other=self.image();other.duration=6;self.assertEqual(choice,other.choose(raw,b))
    def test_probability_schema_fails_before_draw(self):
        s=self.image();s.duration=4;b=s.body('motor');raw=fixture_response(s.model,b,0);state=s.rng.getstate();raw['answers']['action']['probabilities'].pop(next(iter(ACTIONS)))
        with self.assertRaises(PolicyError):s.choose(raw,b)
        self.assertEqual(state,s.rng.getstate())
        raw=fixture_response(s.model,b,0);raw['answers']['action']['probabilities'][next(iter(ACTIONS))]=True
        with self.assertRaises(PolicyError):s.choose(raw,b)
    def test_state_wire_preserves_exact_evidence(self):
        text=CommonSession(self.model,'state');text.begin_state(self.state)
        model=next(m for m in self.models if m['id'].startswith('openai/'));obj=CommonSession(model,'state');obj.begin_state(self.state)
        self.assertEqual(text.body('motor')['state'],obj.body('motor')['state']['observation_text']);self.assertEqual(text.body('motor')['questions'],obj.body('motor')['questions'])
    def config(self):
        return dict(models=[self.model],timeout_seconds=60,policy='fake',native_frame_cap=3,retries_after_initial=2,phase='offline_test',initial_observation_sha256=digest(self.state))
    def job(self):return dict(episode_id='offline-state',model_id=self.model['id'],track='state',temperature=None,local_rng_seed=None,repeat_id=0)
    def test_budget_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            result=execute_episode(d,self.config(),self.job());self.assertEqual(result['frames'],3);self.assertEqual(result['status'],'frame_budget');self.assertIsNone(result['native_frames_to_completion'])
            resumed=execute_episode(d,self.config(),self.job());self.assertEqual(result['cost_provenance'],resumed['cost_provenance'])
            audited=execute_episode(d,self.config(),self.job(),audit=True);self.assertTrue(audited['native_replay_verified']);self.assertEqual(audited['frames'],3)
    def test_uncertain_intent_never_resends(self):
        with tempfile.TemporaryDirectory() as d:
            execute_episode(d,self.config(),self.job());p=Path(d)/'episodes/offline-state.jsonl';rows=read_events(p);prefix=rows[:2];self.assertEqual(prefix[-1]['event'],'request_intent');p.write_text(''.join(json.dumps(x)+'\n' for x in prefix))
            result=execute_episode(d,self.config(),self.job());self.assertEqual(result['status'],'infra_error');self.assertIsNone(result['progress_pct']);self.assertEqual(sum(r['event']=='request_intent' for r in read_events(p)),1)
    def test_schema_failure_is_technical_not_poor_play(self):
        with tempfile.TemporaryDirectory() as d:
            execute_episode(d,self.config(),self.job());p=Path(d)/'episodes/offline-state.jsonl';rows=read_events(p);rows=rows[:3];rows[-1].update(valid=False,retryable=False,error_type='invalid_action',error='fixture schema failure');p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            result=execute_episode(d,self.config(),self.job());self.assertEqual(result['status'],'infra_error');self.assertFalse(result['rankable']);self.assertIsNone(result['progress_pct']);self.assertEqual(result['frames'],0)

    def test_immutable_preregistration_and_fake_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m=plan('preflight',d,policy='fake');verify_manifest(m,d)
            changed=deepcopy(m);changed['repeat_schedule']=changed['repeat_schedule'][:-1]
            with self.assertRaisesRegex(RuntimeError,'modified'):verify_manifest(changed,d)
            report=Path(d)/'summary.json';report.write_text(json.dumps(dict(accepted=True,policy='openrouter')))
            with self.assertRaisesRegex(RuntimeError,'real OpenRouter'):validate_preflight(report)
    def test_fake_pilot_cannot_authorise_final_controller(self):
        with tempfile.TemporaryDirectory() as d:
            plan('pilot',d,policy='fake')
            with self.assertRaisesRegex(RuntimeError,'Only real preregistered'):pilot_selection(d)
    def test_malformed_choice_is_policy_error(self):
        s=self.image();s.duration=4;b=s.body('motor');raw=fixture_response(s.model,b,0);raw['answers']['action']['choice']=[]
        with self.assertRaises(PolicyError):s.parse(raw,b)

if __name__=='__main__':unittest.main()
