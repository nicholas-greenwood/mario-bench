"""Release-only projection of copied, completed state-evaluation episodes.

Audits temporary copies with the unchanged authority/engine. Never runs workers,
loads credentials, reads live evaluation outputs or changes the frozen protocol.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil
import tempfile

from benchmark.client import digest
from benchmark.common_results import aggregate_trials, public_cost
from benchmark.common_state_results import public_manifest
from benchmark import common_state_evaluation as authority
from benchmark import common_state_run_v2 as engine
from benchmark.public_results import public_native_response
from benchmark.run import read_events, write_json

PROTOCOL_SHA256 = 'e1c1086b8dc2d5613deaad37cbc75003dedaf7564cf82802a17b0e81fcdb8371'
MANIFEST_SHA256 = '1d7a87dd60bd740161b607132f06752450a87a04312d83e1a67b14662ac54533'
REGISTRATION_SHA256 = '4276f81c070b8b2269ab813b9d11aa31470c2b3479bb91a53bba959932f4de0d'
EVENTS = {'episode_start', 'request_intent', 'request_result', 'action', 'chunk_end', 'episode_end'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    engine.require(stamp.tzinfo is not None, 'Evidence timestamps must include a timezone')
    return stamp


def validate_snapshot(snapshot):
    snapshot = Path(snapshot).resolve()
    engine.require(not (snapshot / 'orchestrator.lock').exists() and not (snapshot / 'workers').exists(),
                   'Use an isolated release snapshot, never a worker output directory')
    engine.require(not any(p.is_symlink() for p in snapshot.rglob('*')), 'Snapshot symlinks are forbidden')
    engine.require(sha(snapshot / 'manifest.json') == MANIFEST_SHA256, 'Snapshot manifest bytes differ from authority')
    engine.require(sha(snapshot / 'preregistration.json') == REGISTRATION_SHA256, 'Registration bytes differ from authority')
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    engine.require(digest(manifest) == PROTOCOL_SHA256, 'Only the exact independent state66 protocol is supported')
    authority.verify(manifest, snapshot)
    capture = json.loads((snapshot / 'capture.json').read_text())
    engine.require(capture['protocol_sha256'] == PROTOCOL_SHA256
                   and capture['source_manifest_sha256'] == MANIFEST_SHA256
                   and capture['source_preregistration_sha256'] == REGISTRATION_SHA256,
                   'Capture does not bind the original manifest and registration')
    engine.require(utc(capture['captured_at_utc']) >= utc(manifest['frozen_at_utc']), 'Capture precedes registration')
    jobs = {job['episode_id']: job for job in manifest['repeat_schedule']}
    engine.require(len(jobs) == 66 and len(manifest['models']) == 22, 'The complete denominator must remain state66/22models')
    captured = capture['source_episode_sha256']
    engine.require(isinstance(captured, dict) and set(captured) <= set(jobs), 'Capture includes an unscheduled/pilot episode')
    files = {path.stem: path for path in (snapshot / 'episodes').glob('*.jsonl')}
    engine.require(set(files) == set(captured), 'Snapshot log census differs from the capture')
    hashes = {name: sha(snapshot / name) for name in ('manifest.json', 'preregistration.json', 'capture.json')}
    for eid, path in files.items():
        engine.require(sha(path) == captured[eid], 'Copied episode differs from its stable captured source bytes')
        rows = read_events(path)
        engine.require(rows and rows[-1]['event'] == 'episode_end', 'Only durably completed logs can be released')
        engine.require(all(row['event'] in EVENTS and row.get('episode_id') == eid for row in rows),
                       'Unexpected or differently scoped episode event')
        starts = [row for row in rows if row['event'] == 'episode_start']
        ends = [row for row in rows if row['event'] == 'episode_end']
        engine.require(len(starts) == len(ends) == 1 and starts[0]['job'] == jobs[eid]
                       and starts[0]['protocol_sha256'] == PROTOCOL_SHA256, 'Episode job/start binding differs')
        engine.require(utc(manifest['frozen_at_utc']) <= utc(starts[0]['utc']) <= utc(ends[0]['utc'])
                       <= utc(capture['captured_at_utc']), 'Episode is not a fresh completed capture after freeze')
        hashes[str(path.relative_to(snapshot))] = captured[eid]
        cost = path.with_suffix('.cost.json')
        if cost.exists():
            public_cost(path)  # Checks episode-byte binding and complete/unknown billing semantics.
            hashes[str(cost.relative_to(snapshot))] = sha(cost)
    return manifest, capture, hashes


def attempt_evidence(rows):
    """Replicate actual-origin checks and account for every durable HTTP intent."""
    intents, outcomes, ids = {}, {}, []
    for row in rows:
        if row['event'] not in ('request_intent', 'request_result'):
            continue
        key = (row['decision_index'], row['stage'], row['attempt'])
        if row['event'] == 'request_intent':
            engine.require(key not in intents, 'Duplicate request intent')
            intents[key] = row
        else:
            engine.require(key in intents and key not in outcomes, 'Response lacks a unique captured intent')
            engine.require(row['request_sha256'] == intents[key]['request_sha256'], 'Response/request hash mismatch')
            outcomes[key] = row
            if row.get('valid'):
                raw = row.get('raw_response', {})
                engine.require(isinstance(raw.get('id'), str) and raw['id'].startswith('gen-')
                               and type(row.get('http_status')) is int and 200 <= row['http_status'] < 300,
                               'Offline/unproven response cannot authorise actual API evidence')
                ids.append(raw['id'])
    engine.require(len(ids) == len(set(ids)), 'One API receipt cannot substitute for fresh independent calls')
    attempts = []
    for key, intent in intents.items():
        response = outcomes.get(key)
        raw = response.get('raw_response') if response else None
        value = dict(decision_index=key[0], stage=key[1], attempt=key[2],
                     request_sha256=intent['request_sha256'], http_status=response.get('http_status') if response else None,
                     valid=bool(response and response.get('valid')), response_recorded=response is not None,
                     failure_class=response.get('error_type') if response else 'unanswered_attempt',
                     raw_response_sha256=digest(raw) if raw is not None else None)
        if isinstance(raw, dict) and isinstance(raw.get('id'), str):
            value['response_id_sha256'] = hashlib.sha256(raw['id'].encode()).hexdigest()
        if isinstance(raw, dict) and isinstance(raw.get('usage'), dict):
            value['usage'] = public_native_response(raw).get('usage', {})
        attempts.append(value)
    proof = dict(request_intent_count=len(intents), request_result_count=len(outcomes),
                 error_attempt_count=sum(not row.get('valid') for row in outcomes.values()),
                 unanswered_attempt_count=len(intents) - len(outcomes))
    return attempts, proof, ids


def validate_trial_cost(cost, proof):
    """Billing coverage must match the captured source attempts, not receipt count."""
    from benchmark.costs import validate_public_cost
    validate_public_cost(cost)
    provenance = cost.get('cost_provenance')
    if provenance is None:
        return cost
    for key in ('request_count', 'source_request_count', 'source_attempt_count'):
        engine.require(type(provenance.get(key)) is int
                       and provenance[key] == proof['request_intent_count'], 'Billing certificate omits source attempts')
    engine.require(type(provenance.get('error_count')) is int
                   and provenance['error_count'] == proof['error_attempt_count'], 'Billing certificate omits source errors')
    if cost.get('cost_usd') is not None or cost.get('cost_estimate_usd') is not None:
        engine.require(proof['unanswered_attempt_count'] == 0, 'Unanswered source attempts cannot have complete billing')
    return cost


def aggregate_release_trials(manifest, trials):
    """Keep frozen gameplay aggregates; include validated estimates in billing only."""
    from benchmark.costs import validate_public_cost
    rows = aggregate_trials(manifest, trials)
    for row in rows:
        records = [trial for trial in trials if trial['model_id'] == row['model_id'] and trial['track'] == row['track']]
        complete, actual, estimates = [], [], []
        for trial in records:
            validate_public_cost(trial)  # False means validated estimate/unknown, not validation failure.
            if trial.get('cost_provenance') is not None:
                engine.require(isinstance(trial.get('attempt_proof'), dict), 'Billing needs captured source-attempt proof')
                validate_trial_cost(trial, trial['attempt_proof'])
            if trial.get('cost_usd') is not None:
                actual.append(trial);complete.append(trial)
            elif trial.get('cost_estimate_usd') is not None:
                estimates.append(trial);complete.append(trial)
        full = len(records) == len(complete) == 3
        exact = sum(trial['cost_usd'] for trial in actual) if full and len(actual) == 3 else None
        proxy = sum(trial['cost_usd'] if trial.get('cost_usd') is not None else trial['cost_estimate_usd']
                    for trial in complete) if full and estimates else None
        row.update(actual_cost_total_usd=exact, cost_total_estimate_usd=proxy,
                   mean_actual_cost_usd=exact/3 if exact is not None else None,
                   mean_cost_estimate_usd=proxy/3 if proxy is not None else None,
                   cost_coverage_counts=dict(expected_trials=3, recorded_trials=len(records), complete_cost_trials=len(complete),
                                             actual_cost_trials=len(actual), estimated_cost_trials=len(estimates),
                                             unknown_cost_trials=3-len(complete)))
    return rows


def audit_copy(task):
    directory, manifest, job = task
    return engine.execute_episode(directory, manifest, job, audit=True)


def project_trial(directory, manifest, job, result):
    eid = job['episode_id']
    path = directory / 'episodes' / (eid + '.jsonl')
    rows = read_events(path)
    attempts, proof, ids = attempt_evidence(rows)
    engine.require(result['episode_id'] == eid and result['protocol_sha256'] == PROTOCOL_SHA256
                   and result['native_replay_verified'], 'Native audit returned a different or unverified trial')
    engine.require(not result['flag_get'] or (not result['death'] and result['status'] == 'completed'
                   and result['rankable'] and result['native_frames_to_completion'] == result['frames']),
                   'Contradictory native completion cannot be published')
    groups = defaultdict(list)
    for row in rows:
        if 'decision_index' in row:
            groups[row['decision_index']].append(row)
    actions, actual = [], set()
    for index, records in sorted(groups.items()):
        action = next((row for row in records if row['event'] == 'action'), None)
        if action is None:
            continue
        chunk = next((row for row in records if row['event'] == 'chunk_end'), None)
        engine.require(chunk is not None, 'Committed control lacks its audited native checkpoint')
        response = next(row for row in records if row['event'] == 'request_result' and row.get('valid'))
        raw = response['raw_response']
        actual.add((raw['model'], raw['provider']))
        actions.append(dict(index=index, frame_before=action['frame_before'], frame_after=chunk['frame'],
                            sequence=[[chunk['actual_frames'], action['buttons']]],
                            requested_frames=action['requested_frames'], actual_frames=chunk['actual_frames'],
                            request_sha256=response['request_sha256'], native_response=public_native_response(raw),
                            after_observation_sha256=chunk['observation_sha256'], screen_after_sha256=chunk['screen_sha256'],
                            native_frame_hashes=chunk['native_frame_hashes']))
    proof.update(source_episode_sha256=sha(path), native_audit_sha256=sha(path.with_suffix('.audit.json')),
                 started_at_utc=rows[0]['utc'], terminal_at_utc=rows[-1]['utc'])
    trace = dict(schema_version=1, id=eid, phase='evaluation', protocol_sha256=PROTOCOL_SHA256,
                 model_id=job['model_id'], track='state', mode='state', level='1-1', actions=actions,
                 request_attempts=attempts, attempt_proof=proof, source_episode_sha256=sha(path), native_replay_verified=True)
    keep = ['status', 'rankable', 'progress_pct', 'max_progress_x', 'repeat_id', 'local_rng_seed', 'emulator_seed',
            'temperature', 'native_frames_to_completion', 'native_frame_budget', 'life_budget',
            'native_replay_verified', 'started_at_utc', 'decisions', 'flag_get', 'death', 'technical_pending']
    model = next(model for model in manifest['models'] if model['id'] == job['model_id'])
    identities = sorted(actual)
    trial = {key: result[key] for key in keep}
    trial.update(id=eid, episode_id=eid, model_id=job['model_id'], display_name=model['name'], track='state', mode='state',
                 phase='evaluation', protocol_id=manifest['protocol_id'], protocol_sha256=PROTOCOL_SHA256, level='1-1',
                 native_frames=result['frames'], completed=result['flag_get'], verified=True,
                 returned_model=identities[0][0] if identities else None, provider=identities[0][1] if identities else None,
                 actual_returned_model_provider_pairs=[dict(model=a, provider=b) for a, b in identities],
                 trace_href='common-state/traces/' + eid + '.json', trace_sha256=digest(trace),
                 profile_href='common-state/profiles/protocol.json', replay_href=None, replay_sha256=None,
                 attempt_proof=proof, **validate_trial_cost(public_cost(path), proof))
    return trial, trace, ids


def export(snapshot, destination, *, jobs=1):
    snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
    engine.require(snapshot != destination and not destination.is_relative_to(snapshot)
                   and not snapshot.is_relative_to(destination), 'Snapshot and public destination must be separate')
    manifest, capture, hashes = validate_snapshot(snapshot)
    adapter_hash = sha(Path(__file__))
    original_capture = sha(snapshot / 'capture.json')
    with tempfile.TemporaryDirectory(prefix='mario-state-release-audit-') as temporary:
        copied = Path(temporary)
        for relative, expected in hashes.items():
            source, target = snapshot / relative, copied / relative
            engine.require(sha(source) == expected, 'Snapshot changed before copying')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            engine.require(sha(source) == sha(target) == expected, 'Snapshot changed while copying')
        selected = [job for job in manifest['repeat_schedule'] if job['episode_id'] in capture['source_episode_sha256']]
        # Authority verification is read-only. Native audit writes only to disposable copies.
        authority.verify(manifest, copied)
        tasks = [(str(copied), manifest, job) for job in selected]
        if jobs == 1:
            results = [audit_copy(task) for task in tasks]
        else:
            engine.require(1 <= jobs <= 8, 'Audit jobs must be1..8')
            with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context('spawn')) as pool:
                results = list(pool.map(audit_copy, tasks))
        trials, traces, receipt_ids = [], {}, set()
        for job, result in zip(selected, results):
            trial, trace, ids = project_trial(copied, manifest, job, result)
            engine.require(not receipt_ids.intersection(ids), 'One API receipt was reused across evaluation trials')
            receipt_ids.update(ids)
            trials.append(trial)
            traces[trial['id']] = trace
        rows = aggregate_release_trials(manifest, trials)
        header = public_manifest(manifest)
        provenance = dict(schema_version=1, release_status='partial_evaluation_snapshot', protocol_sha256=PROTOCOL_SHA256,
                          source_manifest_sha256=MANIFEST_SHA256, source_preregistration_sha256=REGISTRATION_SHA256,
                          release_adapter_sha256=adapter_hash,
                          capture_sha256=original_capture, captured_at_utc=capture['captured_at_utc'],
                          expected_trials=66, expected_models=22, native_audited_trials=len(trials),
                          complete_model_rows=sum(row['coverage_complete'] for row in rows),
                          pilot_episodes_included=0, source_log_sha256=capture['source_episode_sha256'],
                          billing_sidecar_sha256={name: value for name,value in hashes.items() if name.endswith('.cost.json')})
        value = dict(schema_version=1, common_benchmark=dict(manifest=header, trials=trials, rows=rows,
                                                            release_provenance=provenance))
        from benchmark.common_state_compact_v2 import PROFILE
        profile = dict(schema_version=1, manifest=header, controller_contracts=manifest['controller_contracts'],
                       state_controller=PROFILE, software_sha256=manifest['software_sha256'])
        selection = json.loads((Path(manifest['authority_paths']['calibration']) / 'selection.json').read_text())
        payloads = dict(index=value, profile=profile, selection=selection, traces=traces)
        public = json.dumps(payloads)
        engine.require(not any(token in public for token in ('/Users/', 'OPENROUTER_API_KEY', 'gen-')),
                       'Private paths, credentials or raw request IDs must not enter the public release')
        # Reject mutation of any bound source while native audit was in progress.
        _, _, final_hashes = validate_snapshot(snapshot)
        engine.require(final_hashes == hashes, 'Snapshot file/billing inventory changed during audit')
        engine.require(sha(Path(__file__)) == adapter_hash, 'Release adapter changed during audit')
        engine.require(all(sha(snapshot / relative) == expected for relative, expected in hashes.items()),
                       'Snapshot source/billing bytes changed during audit')
        root = destination / 'common-state'
        if (root / 'index.json').exists():
            old = json.loads((root / 'index.json').read_text())['common_benchmark']
            engine.require(old['manifest']['protocol_sha256'] == PROTOCOL_SHA256, 'Public cohort identity cannot change')
            engine.require({row['id'] for row in old['trials']} <= set(traces), 'A partial refresh cannot remove published trials')
        (root / 'traces').mkdir(parents=True, exist_ok=True)
        (root / 'profiles').mkdir(exist_ok=True)
        (root / 'calibration').mkdir(exist_ok=True)
        for eid, trace in traces.items():
            path = root / 'traces' / (eid + '.json')
            write_json(path, trace)
            trial = next(row for row in trials if row['id'] == eid)
            trial['trace_sha256'] = sha(path)
        write_json(root / 'profiles/protocol.json', profile)
        write_json(root / 'calibration/selection.json', selection)
        # Write the referencing index last; unrelated/legacy result trees are untouched.
        write_json(root / 'index.json', value)
        return value


def verify_public(destination):
    """Rebuild native requests/replay all public trials without private authority paths."""
    from copy import deepcopy
    from benchmark.common_state_compact_v2 import PROFILE
    from benchmark.common_state_runtime_v2 import StateCompactSession
    from benchmark.scoring import validated_progress_x
    from prototype.emulator import MarioGame
    root = Path(destination).resolve() / 'common-state'
    data = json.loads((root / 'index.json').read_text())['common_benchmark']
    header = data['manifest']
    engine.require(header['protocol_sha256'] == PROTOCOL_SHA256 and header['phase'] == 'evaluation'
                   and header['tracks'] == ['state'] and len(header['repeat_schedule']) == 66,
                   'Public release does not retain the independent state66 authority')
    profile = json.loads((root / 'profiles/protocol.json').read_text())
    engine.require(profile['manifest'] == header and profile['state_controller'] == PROFILE,
                   'Public compact controller differs from its frozen definition')
    source_root = Path(__file__).resolve().parents[1]
    engine.require(len(profile['software_sha256']) == 16, 'Public projection omitted frozen source bindings')
    for name, expected in profile['software_sha256'].items():
        path = (source_root / name).resolve()
        engine.require(path.is_relative_to(source_root) and sha(path) == expected, 'Frozen public source differs')
    engine.require(engine.actual_rom_sha256() == header['actual_rom_sha256'], 'Installed ROM differs from public protocol')
    jobs = {job['episode_id']: job for job in header['repeat_schedule']}
    pairs = {pair['model_id']: pair for pair in header['eligible_model_provider_pairs']}
    engine.require(len(jobs) == 66 and len(pairs) == 22, 'Public schedule/roster denominator changed')
    trials = data['trials']
    engine.require(len({row['id'] for row in trials}) == len(trials), 'Duplicate public trial')
    reports = []
    for trial in trials:
        eid = trial['id']
        engine.require(eid in jobs and all(trial[key] == jobs[eid][key] for key in
                       ('model_id', 'track', 'repeat_id', 'local_rng_seed', 'emulator_seed', 'temperature')),
                       'Public trial is not one of the prescribed fresh repeats')
        engine.require(trial['protocol_sha256'] == PROTOCOL_SHA256 and trial['phase'] == 'evaluation'
                       and trial['native_frame_budget'] == 6000 and trial['life_budget'] == 1
                       and utc(trial['started_at_utc']) >= utc(header['frozen_at_utc']), 'Public trial envelope changed')
        engine.require(trial['trace_href'] == 'common-state/traces/' + eid + '.json', 'Trace path is not canonical')
        path = root / 'traces' / (eid + '.json')
        engine.require(sha(path) == trial['trace_sha256'], 'Public trace bytes differ')
        trace = json.loads(path.read_text())
        engine.require(trace['protocol_sha256'] == PROTOCOL_SHA256 and trace['id'] == eid
                       and trace['native_replay_verified'] and trace['source_episode_sha256'] ==
                       data['release_provenance']['source_log_sha256'][eid], 'Public native/source binding changed')
        proof = trace['attempt_proof']
        validate_trial_cost(trial, proof)
        attempts = trace['request_attempts']
        engine.require(trial['attempt_proof'] == proof
                       and proof['request_intent_count'] == len(attempts)
                       and proof['request_result_count'] == sum(row['response_recorded'] for row in attempts)
                       and proof['error_attempt_count'] == sum(row['response_recorded'] and not row['valid'] for row in attempts)
                       and proof['unanswered_attempt_count'] == sum(not row['response_recorded'] for row in attempts),
                       'Public all-attempt coverage proof differs')
        pair = pairs[trial['model_id']]
        model = dict(pair, id=trial['model_id'])
        session, game = StateCompactSession(model, 'state'), MarioGame(level='1-1')
        maximum, attempts_verified = 40., set()
        try:
            engine.require(digest(game.observe()) == header['initial_observation_sha256']
                           and engine.screen_hash(game) == header['initial_screen_sha256'], 'Public initial state differs')
            def check_attempts(index, body):
                attempts = [row for row in trace['request_attempts'] if row['decision_index'] == index]
                engine.require(attempts and len({(row['stage'], row['attempt']) for row in attempts}) == len(attempts),
                               'Missing or duplicate public request attempts')
                for row in attempts:
                    engine.require(row['stage'] == 'motor' and row['request_sha256'] == digest(body), 'Public request body differs')
                    if row['valid']:
                        engine.require(type(row['http_status']) is int and 200 <= row['http_status'] < 300
                                       and isinstance(row.get('response_id_sha256'), str)
                                       and len(row['response_id_sha256']) == 64, 'Public actual-origin receipt proof missing')
                attempts_verified.add(index)
            for index, action in enumerate(trace['actions']):
                engine.require(action['index'] == index and action['frame_before'] == game.frame, 'Public native action clock differs')
                session.begin_state(game.observe())
                body = session.body('motor')
                check_attempts(index, body)
                engine.require(digest(body) == action['request_sha256'], 'Public action request differs from frozen observer')
                choice = session.choose(action['native_response'], body)
                engine.require(choice['buttons'] == action['sequence'][0][1]
                               and choice['requested_frames'] == action['requested_frames'] == 4
                               and len(action['sequence']) == 1, 'Public native choice/controller differs')
                actual = action['sequence'][0][0]
                engine.require(0 < actual <= min(4, 6000-game.frame)
                               and len(action['native_frame_hashes']) == actual, 'Public native hold/checkpoint count differs')
                before = game.frame
                for expected in action['native_frame_hashes']:
                    observed = game.step(choice['buttons'])
                    candidate = validated_progress_x(observed, 40)
                    if candidate is not None:
                        maximum = max(maximum, candidate)
                    engine.require(game.frame == expected['frame']
                                   and hashlib.sha256(game.env.ram.tobytes()).hexdigest() == expected['ram_sha256']
                                   and engine.screen_hash(game) == expected['screen_sha256'], 'Public per-frame RAM/RGB replay differs')
                engine.require(actual == 4 or game.done or game.flag_get or game.frame == 6000, 'Unjustified shortened native action')
                engine.require(game.frame == action['frame_after'] and digest(game.observe()) == action['after_observation_sha256']
                               and engine.screen_hash(game) == action['screen_after_sha256'], 'Public action checkpoint differs')
                session.advance(buttons=choice['buttons'], frame_after=game.frame, actual_frames=game.frame-before)
            remaining = {row['decision_index'] for row in trace['request_attempts']} - attempts_verified
            if remaining:
                engine.require(remaining == {len(trace['actions'])} and trial['technical_pending']
                               and not game.done and not game.flag_get, 'Unexpected unexecuted request stage')
                session.begin_state(game.observe())
                check_attempts(len(trace['actions']), session.body('motor'))
            engine.require(game.frame == trial['native_frames'] and len(trace['actions']) == trial['decisions']
                           and bool(game.flag_get) == trial['flag_get'] == trial['completed']
                           and bool(game.death) == trial['death'] and maximum == trial['max_progress_x'],
                           'Public final native outcome differs')
            if trial['rankable']:
                expected_status = 'completed' if game.flag_get else 'game_over' if game.done else 'frame_budget'
                progress = 100. if game.flag_get else min(99.9, max(0., 100*(maximum-40)/(3161-40)))
                engine.require(trial['status'] == expected_status and trial['progress_pct'] == progress
                               and (game.done or game.flag_get or game.frame == 6000), 'Public rankable score differs')
            else:
                engine.require(trial['technical_pending'] and trial['status'] == 'infra_error'
                               and trial['progress_pct'] is None, 'Technical outcome became a model score')
            engine.require(trial['native_frames_to_completion'] == (game.frame if game.flag_get else None), 'Public completion time differs')
            identities = sorted({(a['native_response']['model'], a['native_response']['provider']) for a in trace['actions']})
            engine.require(trial['actual_returned_model_provider_pairs'] == [dict(model=a, provider=b) for a,b in identities]
                           and trial['returned_model'] == (identities[0][0] if identities else None)
                           and trial['provider'] == (identities[0][1] if identities else None), 'Public actual identity label differs')
            reports.append(dict(id=eid, native_frames=game.frame, native_replay_verified=True))
        finally:
            game.close()
    # The unmodified aggregate helper only needs the public exact schedule. Its
    # internal protocol equality is rebound in scratch copies; public e1 IDs stay unchanged.
    proxy = dict(repeat_schedule=header['repeat_schedule'])
    copied_trials = deepcopy(trials)
    for row in copied_trials:
        row['protocol_sha256'] = digest(proxy)
    calculated = aggregate_release_trials(proxy, copied_trials)
    for row in calculated:
        row['protocol_sha256'] = PROTOCOL_SHA256
    engine.require(calculated == data['rows'], 'Public three-prescribed-trial means or pending rows differ')
    return dict(trials=len(reports), rows=len(calculated), complete_model_rows=sum(row['coverage_complete'] for row in calculated),
                native_frames=sum(row['native_frames'] for row in reports), verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--verify-public', type=Path, help='Offline native/body verification of a public destination; no private paths or key')
    parser.add_argument('--jobs', type=int, default=1, choices=range(1, 9))
    args = parser.parse_args()
    if args.verify_public:
        print(json.dumps(verify_public(args.verify_public), indent=2))
        return
    if not args.snapshot or not args.destination:
        parser.error('--snapshot and --destination are required for release projection')
    result = export(args.snapshot, args.destination, jobs=args.jobs)['common_benchmark']
    print(json.dumps(dict(trials=len(result['trials']), rows=len(result['rows']),
                          complete_model_rows=sum(row['coverage_complete'] for row in result['rows']),
                          protocol_sha256=PROTOCOL_SHA256), indent=2))


if __name__ == '__main__':
    main()
