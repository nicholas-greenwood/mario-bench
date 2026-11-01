"""Public-fixture controller/request/native replay and interruption checks; no API calls."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.client import Client, digest
from benchmark.frozen_run import execute_episode, profile_manifest
from benchmark.profile_runtime import PROFILE_IDS, ProfileSession, fixture_response
from benchmark.run import png, read_events, safe_name, write_json
from prototype.decisions import PolicyError
from prototype.emulator import MarioGame

ROOT = Path(__file__).resolve().parents[1]


def config(name, frames=20):
    session = ProfileSession(name)
    protocol = json.loads((ROOT / 'benchmark/protocol.json').read_text())
    return dict(control_profile=name, policy='openrouter', track=session.mode,
                cadence=session.profile.get('cadence'), frames=frames,
                decisions=(frames + session.min_hold - 1) // session.min_hold,
                trials=1, timeout=1, retries=1, level_spec=protocol['levels'][0])


def public_parity():
    for name in PROFILE_IDS:
        trace = json.loads((ROOT / 'results/traces' / (name + '.json')).read_text())
        session, game = ProfileSession(name), MarioGame()
        mismatches = 0
        try:
            for action in trace['actions']:
                before, index = game.frame, action['index']
                image = session.screenshot(game.frame_rgb()) if session.mode == 'image' else None
                frozen_raw = deepcopy(action['native_response'])
                if session.multistage:
                    from benchmark.public_results import duration_first_choice
                    chosen = duration_first_choice(session, action, image, before, index)
                else:
                    body = (session.image_request(image, before, index) if image else session.state_request(game.observe()))
                    assert digest(body) == action['request_sha256'], (name, index, 'request')
                    chosen = session.choose(frozen_raw, body)
                assert frozen_raw == action['native_response'], 'Sampler mutated native argmax response'
                frames, buttons = action['sequence'][0]
                assert chosen['buttons'] == buttons
                if session.sampler and not session.multistage:
                    expected = action['sampling']
                    assert chosen['sampling']['sampled_choice'] == expected['sampled_choice']
                    assert chosen['sampling']['random_uniform'] == expected['random_uniform']
                    mismatches += chosen['sampling']['sampled_choice'] != frozen_raw['answers']['action']['choice']
                assert chosen['requested_frames'] >= frames
                # The fixture's last hold ends early at native flag_get, not a controller override.
                for _ in range(chosen['requested_frames']):
                    game.step(buttons)
                    if game.done:
                        break
                actual = game.frame - before
                assert actual == frames and game.frame == action['frame_after']
                assert digest(game.observe()) == action['after_observation_sha256']
                assert hashlib.sha256(game.frame_rgb().tobytes()).hexdigest() == action['screen_after_sha256']
                session.advance(image=image, frame=before, decision=index, buttons=buttons, actual_frames=actual)
            assert game.flag_get
            if session.sampler and not session.multistage:
                assert mismatches == 9
            print(f'PASS: {name}: {len(trace["actions"])} exact request/choice checkpoints, {game.frame} native frames, flag_get')
        finally:
            game.close()


def reject_bad_vectors():
    name = 'pplx-pixels-sampled-clear-t005-seed0'
    session, game = ProfileSession(name), MarioGame()
    try:
        body = session.image_request(png(game), 0, 0)
    finally:
        game.close()
    raw = fixture_response(session.model, body, 0)
    invalid = []
    for kind in ('missing', 'unknown', 'boolean', 'negative', 'above_one', 'nan', 'sum', 'list_choice', 'dict_choice'):
        changed = deepcopy(raw)
        answer = changed['answers']['action']
        keys = list(answer['probabilities'])
        if kind == 'missing': answer['probabilities'].pop(keys[0])
        if kind == 'unknown': answer['probabilities']['wrong_action'] = answer['probabilities'].pop(keys[0])
        if kind == 'boolean': answer['probabilities'][keys[0]] = True
        if kind == 'negative': answer['probabilities'][keys[0]] = -.1
        if kind == 'above_one': answer['probabilities'][keys[0]] = 1.02
        if kind == 'nan': answer['probabilities'][keys[0]] = float('nan')
        if kind == 'sum': answer['probabilities'] = dict.fromkeys(keys, .01)
        if kind == 'list_choice': answer['choice'] = []
        if kind == 'dict_choice': answer['choice'] = {}
        invalid.append(changed)
    rng = session.rng.getstate()
    for changed in invalid:
        try:
            session.choose(changed, body)
        except PolicyError:
            pass
        else:
            raise AssertionError('Invalid native vector accepted')
        assert session.rng.getstate() == rng

    # Exercise the real HTTP/parser wrapper and durable runner using a local response stub.
    class Response:
        status = 200
        def getheader(self, name): return None
        def read(self): return json.dumps(invalid[0]).encode()
    class Connection:
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass
    def factory(key, model, timeout, *, decoder):
        client = Client(key, model, timeout, decoder=decoder)
        client.connection = Connection()
        return client
    with tempfile.TemporaryDirectory() as tmp:
        result = execute_episode(tmp, config(name), client_factory=factory)
        assert result['status'] == 'invalid_action' and result['frames'] == 0 and result['decisions'] == 0
    print('PASS: complete 12-way finite probability validation rejects malformed choices before RNG/native frames')


def recovery():
    name = 'pplx-pixels-sampled-clear-t005-seed0'
    trace = json.loads((ROOT / 'results/traces' / (name + '.json')).read_text())
    calls = []
    def factory(key, model, timeout, *, decoder):
        class Transport:
            def call(self, body):
                # A transient failure is logged, with no draw and no emulator advance.
                calls.append(digest(body))
                if len(calls) == 1:
                    return dict(valid=False, retryable=True, error_type='transport', error='offline timeout',
                                request_sha256=digest(body), raw_response=None)
                index = len(calls) - 2
                assert digest(body) == trace['actions'][index]['request_sha256']
                raw = deepcopy(trace['actions'][index]['native_response'])
                return dict(valid=True, retryable=False, raw_response=raw, decision=decoder(raw, body),
                            request_sha256=digest(body))
            def close(self): pass
        return Transport()
    def forbidden(*args, **kwargs):
        raise AssertionError('Recovery sent another request')
    cfg = config(name, 20)
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        with patch('benchmark.frozen_run.time.sleep'):
            original = execute_episode(output, cfg, client_factory=factory)
        assert original['frames'] == 20 and original['status'] == 'frame_budget'
        assert len(calls) == 4 and calls[0] == calls[1]
        path = output / (safe_name(ProfileSession(name).model['id']) + '.jsonl')
        original_bytes = path.read_bytes()
        events = read_events(path)
        last = [row for row in events if row['event'] == 'chunk_end'][-1]
        assert last['requested_frames'] == 7 and last['actual_frames'] == 6 and last['terminal_reason'] == 'frame_budget'
        # Completed resume is byte-identical and makes no calls.
        assert execute_episode(output, cfg, client_factory=forbidden) == original
        assert path.read_bytes() == original_bytes
        for crash_event, include in [('action', False), ('action', True), ('chunk_end', True)]:
            cut = next(i for i, row in enumerate(events) if row['event'] == crash_event and row.get('decision_index') == 2)
            prefix = events[:cut + int(include)]
            path.write_text(''.join(json.dumps(row) + '\n' for row in prefix))
            assert execute_episode(output, cfg, client_factory=forbidden) == original
            recovered = read_events(path)
            assert [row for row in recovered if row['event'] == 'action'] == [row for row in events if row['event'] == 'action'] or all(
                {k: v for k, v in a.items() if k != 'utc'} == {k: v for k, v in b.items() if k != 'utc'}
                for a, b in zip([r for r in recovered if r['event'] == 'action'], [r for r in events if r['event'] == 'action']))
        # An uncertain request stops frozen; it must never be resent.
        cut = next(i for i, row in enumerate(events) if row['event'] == 'request_intent' and row.get('decision_index') == 2)
        path.write_text(''.join(json.dumps(row) + '\n' for row in events[:cut + 1]))
        uncertain = execute_episode(output, cfg, client_factory=forbidden)
        assert uncertain['status'] == 'infra_error' and uncertain['frames'] == 14
    print('PASS: paused retries, one seeded draw per decision, completed/response/action/checkpoint recovery, uncertain-request protection, strict cap')


def mercury_recovery():
    """Both stages freeze; plan-only commits recover without another plan call."""
    name = 'mercury-pixels-planner-sampled-clear-t02-seed0'
    trace = json.loads((ROOT / 'results/traces' / (name + '.json')).read_text())
    cfg = config(name, 25)
    calls = []
    scheduled = [(0, 'plan'), (0, 'motor'), (1, 'plan'), (1, 'motor'),
                 (1, 'motor'), (2, 'plan'), (2, 'motor')]
    def make_outcome(index, stage, body, decoder):
        assert digest(body) == trace['actions'][index]['stage_request_sha256'][stage]
        field = 'native_plan_response' if stage == 'plan' else 'native_response'
        raw = deepcopy(trace['actions'][index][field])
        raw['usage'] = dict(cost=.001, is_byok=False)
        return dict(valid=True, retryable=False, raw_response=raw,
                    decision=decoder(raw, body), request_sha256=digest(body))
    def factory(key, model, timeout, *, decoder):
        class Transport:
            def call(self, body):
                index, stage = scheduled[len(calls)]
                calls.append((index, stage))
                assert json.loads(body['state'][0])['stage'] == stage
                if len(calls) == 4:
                    return dict(valid=False, retryable=True, error_type='infrastructure', error='HTTP 502',
                                raw_response={'error': {'code': 502}}, request_sha256=digest(body))
                return make_outcome(index, stage, body, decoder)
            def close(self): pass
        return Transport()
    def forbidden(*args, **kwargs):
        raise AssertionError('A committed stage was sent again')
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp)
        with patch('benchmark.frozen_run.time.sleep'):
            original = execute_episode(output, cfg, client_factory=factory)
        assert original['frames'] == 25 and original['decisions'] == 3
        assert len(calls) == 7 and calls[3] == calls[4]
        path = output / (safe_name(ProfileSession(name).model['id']) + '.jsonl')
        rows = read_events(path)
        from benchmark.costs import costs_from_events
        costs = costs_from_events(rows)
        assert costs['cost_usd'] is None and costs['cost_estimate_usd'] is None
        assert costs['recorded_openrouter_cost_usd'] == .006
        assert costs['cost_provenance']['request_count'] == 7
        assert costs['cost_provenance']['unreceipted_count'] == 1
        action_rows = [row for row in rows if row['event'] == 'action']
        def prefix(cut):
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows[:cut]))
        for event, stage in [('request_result', 'motor'), ('action', None)]:
            cut = next(i for i, row in enumerate(rows) if row['event'] == event and row.get('decision_index') == 2
                       and (stage is None or row.get('stage') == stage))
            prefix(cut + 1)
            assert execute_episode(output, cfg, client_factory=forbidden) == original
            recovered = [row for row in read_events(path) if row['event'] == 'action']
            assert [{k: v for k, v in row.items() if k != 'utc'} for row in recovered] == [
                {k: v for k, v in row.items() if k != 'utc'} for row in action_rows]
        plan_cut = next(i for i, row in enumerate(rows) if row['event'] == 'request_result'
                        and row.get('decision_index') == 2 and row.get('stage') == 'plan')
        prefix(plan_cut + 1)
        actor_calls = []
        def actor_only(key, model, timeout, *, decoder):
            class Transport:
                def call(self, body):
                    actor_calls.append(body)
                    assert json.loads(body['state'][0])['stage'] == 'motor'
                    return make_outcome(2, 'motor', body, decoder)
                def close(self): pass
            return Transport()
        assert execute_episode(output, cfg, client_factory=actor_only) == original
        assert len(actor_calls) == 1
        for stage in ('plan', 'motor'):
            cut = next(i for i, row in enumerate(rows) if row['event'] == 'request_intent'
                       and row.get('decision_index') == 2 and row.get('stage') == stage)
            prefix(cut + 1)
            stopped = execute_episode(output, cfg, client_factory=forbidden)
            assert stopped['status'] == 'infra_error' and stopped['frames'] == 24
    print('PASS: Mercury per-stage retry, pending-plan/motor safety, plan-only and actor/action recovery, sampled choices and 502 cost unknown')


def cli_envelope():
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / 'run'
        base = [sys.executable, '-m', 'benchmark.run', '--profile', 'mammoth-pixels-first-clear',
                '--policy', 'fake', '--output', str(output), '--execute']
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        first = subprocess.run(base + ['--max-native-frames', '13'], cwd='/tmp', env=env,
                               capture_output=True, text=True)
        assert first.returncode == 0, first.stderr
        manifest = json.loads((output / 'manifest.json').read_text())
        assert manifest['config']['decisions'] == 7 and manifest['config']['frames'] == 13
        assert manifest['run_envelope_sha256'] == digest(manifest['run_envelope'])
        audit = subprocess.run([sys.executable, '-m', 'benchmark.audit', str(output)], cwd='/tmp', env=env,
                               capture_output=True, text=True)
        assert audit.returncode == 0, audit.stderr
        before = {path.name: path.read_bytes() for path in output.glob('*.jsonl')}
        changed = subprocess.run(base + ['--max-native-frames', '14'], cwd='/tmp', env=env,
                                 capture_output=True, text=True)
        assert changed.returncode != 0 and 'Resume manifest differs' in changed.stderr
        assert before == {path.name: path.read_bytes() for path in output.glob('*.jsonl')}
        rejected = subprocess.run(base + ['--max-native-frames', '13', '--decisions', '2'], cwd='/tmp', env=env,
                                  capture_output=True, text=True)
        assert rejected.returncode != 0 and 'derived' in rejected.stderr
    print('PASS: public CLI from /tmp, variable-duration audit, derived cap and immutable envelope/no extension')


def main():
    with patch.dict(os.environ, OPENROUTER_API_KEY='offline-test-no-network'):
        public_parity()
        reject_bad_vectors()
        recovery()
        mercury_recovery()
        cli_envelope()


if __name__ == '__main__':
    main()
