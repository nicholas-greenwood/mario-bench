"""Execute and audit selected frozen controllers under an immutable fresh envelope."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

from benchmark.client import Client, digest
from benchmark.profile_runtime import ProfileSession, fixture_response
from benchmark.run import append, load_key, png, read_events, safe_name, write_json
from benchmark.scoring import aggregate_results, score_episode, validated_progress_x
from prototype.emulator import MarioGame

ROOT = Path(__file__).resolve().parents[1]


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _same(recorded, expected, description):
    _require(all(recorded.get(key) == value for key, value in expected.items()),
             f'{description} differs from deterministic replay')


def _screen_hash(game):
    return hashlib.sha256(game.frame_rgb().tobytes()).hexdigest()


class StageFailure(Exception):
    def __init__(self, status, error, calls):
        self.status, self.error, self.calls = status, error, calls


def request_stage(*, session, game, rows, config, output, path, episode_id, index,
                  stage, body, image, before, audit, client_box, has_action):
    """One frozen stage's durable request ledger; no draw or emulator step."""
    identity = dict(episode_id=episode_id, decision_index=index, frame=before,
                    observation_sha256=digest(game.observe()),
                    image_sha256=hashlib.sha256(image).hexdigest() if image else None,
                    request_sha256=digest(body), stage=stage)
    prior = [row for row in rows if row.get('decision_index') == index and row.get('stage', 'decision') == stage]
    intents = [row for row in prior if row['event'] == 'request_intent']
    outcomes = [row for row in prior if row['event'] == 'request_result']
    _require(len(outcomes) <= len(intents) <= len(outcomes) + 1, 'Request ledger is not a committed prefix')
    for attempt, intent in enumerate(intents):
        _same(intent, dict(identity, attempt=attempt), 'Stage request body/observation')
    for attempt, result in enumerate(outcomes):
        _same(result, dict(frame=before, frame_after_request=before, attempt=attempt,
                           request_sha256=digest(body), stage=stage), 'Paused stage result')
        if result['valid']:
            parsed = session.parse(result['raw_response'], body, result.get('header_request_id'))
            _same(result['decision'], parsed, 'Native stage response decoding')
    calls = len(outcomes)
    if len(intents) > len(outcomes):
        _require(not has_action, 'An uncertain request cannot have a committed action')
        raise StageFailure('infra_error', 'Uncertain interrupted request; no duplicate sent', calls)
    outcome = outcomes[-1] if outcomes else None
    while not outcome or (not outcome['valid'] and outcome.get('retryable') and len(outcomes) <= config['retries']):
        _require(not has_action, 'Committed action has no validated native stage response')
        _require(not audit, 'Audit cannot issue or complete a missing stage request')
        attempt = len(outcomes)
        if attempt:
            time.sleep(min(2 ** (attempt - 1), 4))
        if image:
            destination = Path(output) / 'images' / safe_name(session.model['id']) / episode_id.replace(':', '_')
            destination.mkdir(parents=True, exist_ok=True)
            (destination / f'{index:06d}.png').write_bytes(image)
        append(path, dict(event='request_intent', attempt=attempt, **identity))
        if config['policy'] == 'fake':
            raw = fixture_response(session.model, body, index)
            outcome = dict(valid=True, retryable=False, raw_response=raw, decision=session.parse(raw, body),
                           request_sha256=digest(body), http_status=None)
        else:
            if client_box[0] is None:
                client_box[0] = client_box[1](os.environ['OPENROUTER_API_KEY'], session.model,
                                            config['timeout'], decoder=session.parse)
            outcome = client_box[0].call(body)
        _require(digest(game.observe()) == identity['observation_sha256'] and game.frame == before,
                 'Emulator advanced during stage inference')
        outcome['frame_after_request'] = before
        append(path, dict(event='request_result', episode_id=episode_id, decision_index=index,
                          attempt=attempt, frame=before, stage=stage, **outcome))
        outcomes.append(outcome)
        calls += 1
    if not outcome or not outcome['valid']:
        _require(not has_action, 'Invalid stage response cannot have a committed action')
        status = 'invalid_action' if outcome and outcome.get('error_type') == 'invalid_action' else 'infra_error'
        raise StageFailure(status, (outcome or {}).get('error', 'No validated response'), calls)
    return outcome, calls


def execute_episode(output, config, trial=0, *, audit=False, client_factory=Client):
    """Replay a durable prefix before continuing; never resend an uncertain intent."""
    session = ProfileSession(config['control_profile'])
    model = session.model
    path = Path(output) / (safe_name(model['id']) + '.jsonl')
    episode_id = f'1-1:seed0:trial{trial:03d}'
    rows = [row for row in read_events(path) if row.get('episode_id') == episode_id]
    ends = [row for row in rows if row['event'] == 'episode_end']
    if ends and not audit:
        return ends[-1]['result']
    game = MarioGame(level='1-1')
    client_box = [None, client_factory]
    calls = 0
    try:
        state = game.observe()
        initial = dict(event='episode_start', episode_id=episode_id, initial_sha256=digest(state),
                       initial_screen_sha256=_screen_hash(game), initial=state)
        begins = [row for row in rows if row['event'] == 'episode_start']
        if begins:
            _require(len(begins) == 1, 'Duplicate episode start')
            _same(begins[0], initial, 'Initial state')
        else:
            _require(not audit and not rows, 'Missing episode start')
            append(path, initial)
        start_x = state['player']['x']
        max_x, decisions = start_x, 0
        status, error = None, None
        for index in range(config['decisions']):
            if game.done or game.frame >= config['frames']:
                break
            state, before = game.observe(), game.frame
            image = session.screenshot(game.frame_rgb()) if session.mode == 'image' else None
            image_hash = hashlib.sha256(image).hexdigest() if image else None
            prior = [row for row in rows if row.get('decision_index') == index]
            actions = [row for row in prior if row['event'] == 'action']
            chunks = [row for row in prior if row['event'] == 'chunk_end']
            _require(len(actions) <= 1 and len(chunks) <= 1, 'Duplicate committed action/chunk')
            stage_hashes = {}
            try:
                for stage in session.stages:
                    body = (session.image_request(image, before, index, stage=stage) if image is not None
                            else session.state_request(state))
                    stage_hashes[stage] = digest(body)
                    outcome, stage_calls = request_stage(session=session, game=game, rows=rows, config=config,
                        output=output, path=path, episode_id=episode_id, index=index, stage=stage, body=body,
                        image=image, before=before, audit=audit, client_box=client_box, has_action=bool(actions))
                    calls += stage_calls
                    session.accept_stage(stage, outcome['raw_response'], body)
            except StageFailure as failure:
                calls += failure.calls
                status, error = failure.status, failure.error
                break
            request_hash = digest(body)
            # This is the only sampler draw. Replay reconstructs the same RNG prefix;
            # retries and response-only recovery have not consumed any earlier draw.
            chosen = session.choose(outcome['raw_response'], body)
            steps = min(chosen['requested_frames'], config['frames'] - before)
            action = dict(event='action', episode_id=episode_id, decision_index=index,
                          observed_frame=before, observation_sha256=digest(state), request_sha256=request_hash,
                          image_sha256=image_hash, buttons=chosen['buttons'], frames=steps,
                          requested_frames=chosen['requested_frames'], sampling=chosen['sampling'],
                          native_choice=outcome['raw_response']['answers'].get('action', {}).get('choice'))
            if 'action' not in outcome['raw_response']['answers']:
                action['native_choices'] = {name: answer['choice']
                                            for name, answer in outcome['raw_response']['answers'].items()}
            if session.multistage:
                action['stage_request_sha256'] = stage_hashes
            if actions:
                _same(actions[0], action, 'Committed model action/sampler draw')
            else:
                _require(not audit, 'Missing committed action')
                append(path, action)
            for _ in range(steps):
                state = game.step(chosen['buttons'])
                candidate = validated_progress_x(state, start_x)
                if candidate is not None:
                    max_x = max(max_x, candidate)
                if game.done:
                    break
            actual = game.frame - before
            terminal = ('completed' if game.flag_get else 'game_over') if game.done else (
                'frame_budget' if game.frame == config['frames'] else None)
            chunk = dict(event='chunk_end', episode_id=episode_id, decision_index=index,
                         frame=game.frame, actual_frames=actual, requested_frames=chosen['requested_frames'],
                         observation_sha256=digest(game.observe()), screen_sha256=_screen_hash(game),
                         terminal_reason=terminal)
            if chunks:
                _same(chunks[0], chunk, 'Native action replay')
            else:
                _require(not audit, 'Missing native-frame checkpoint')
                append(path, chunk)
            session.advance(image=image, frame=before, decision=index, buttons=chosen['buttons'],
                            actual_frames=actual)
            decisions += 1
        if status is None:
            status = ('completed' if game.flag_get else 'game_over') if game.done else (
                'frame_budget' if game.frame == config['frames'] else 'decision_budget')
        result = score_episode(dict(episode_id=episode_id, model=model['id'], track=session.mode,
                                    level='1-1', seed=0, status=status, completed=bool(game.flag_get),
                                    max_progress_x=max_x, start_x=start_x, frames=game.frame,
                                    decisions=decisions, deaths=int(game.death), error=error,
                                    native_frames_to_completion=game.frame if game.flag_get else None),
                               config['level_spec'])
        if ends:
            _require(len(ends) == 1 and ends[0]['result'] == result, 'Episode result differs from replay')
        else:
            _require(not audit, 'Missing committed episode result')
            append(path, dict(event='episode_end', episode_id=episode_id, result=result))
        return dict(result, audit_calls=calls) if audit else result
    finally:
        game.close()
        if client_box[0]:
            client_box[0].close()


def source_hashes():
    files = [path for package in ('prototype', 'benchmark') for path in (ROOT / package).rglob('*.py')]
    files += list((ROOT / 'benchmark/profiles').glob('*.json'))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


def profile_manifest(config):
    session = ProfileSession(config['control_profile'])
    profile_path = ROOT / 'benchmark/profiles' / (session.id + '.json')
    envelope = dict(native_frame_budget=config['frames'], decision_budget=config['decisions'],
                    trials=config['trials'], level='1-1', seed=0, life_budget=1,
                    minimum_hold_frames=session.min_hold, maximum_budget='native_frames',
                    request_stages=list(session.stages),
                    final_hold_rule='min(model_chosen_hold, remaining_native_budget); death/flag also stop immediately',
                    sampler_seed_per_episode=session.sampler['seed'] if session.sampler else None)
    return dict(schema_version=3, runner='frozen-profiles-v1', config=config,
                models=[session.model], frozen_profile=session.profile,
                profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                controller_sha256=digest(session.profile['contract']), run_envelope=envelope,
                run_envelope_sha256=digest(envelope), software_sha256=source_hashes(),
                common_benchmark_default=False, leaderboard_ready=False,
                interpretation='Frozen selected controller, fresh immutable run envelope; historical research budgets can differ.')


def run_profile(args, parser):
    session = ProfileSession(args.profile)
    if args.levels != ['1-1'] or args.models and args.models != [session.model['id']]:
        parser.error('Frozen profile pins one model and World 1-1; use its profile ID alone')
    if args.track not in (None, session.mode) or args.cadence not in (None, session.profile.get('cadence')):
        parser.error('Track and cadence are frozen by the profile, including native selected durations')
    if args.state_serialization not in ('auto', 'text'):
        parser.error('Frozen profiles use their original request serialization')
    if args.roster.resolve() != (ROOT / 'benchmark/models.json').resolve():
        parser.error('Frozen profiles pin their own model/provider; a custom roster is not supported')
    if args.max_native_frames is not None and args.frames not in (6000, args.max_native_frames):
        parser.error('Use one consistent native cap with --frames or --max-native-frames')
    frames = args.max_native_frames if args.max_native_frames is not None else args.frames
    if (frames < 1 or args.trials < 1 or not 0 <= args.retries <= 3
            or not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error('Positive budgets/timeouts required; retries must be between zero and three')
    decisions = math.ceil(frames / session.min_hold)
    if args.decisions not in (None, decisions):
        parser.error('Frozen profile decision budget is derived from native budget/minimum hold')
    protocol = json.loads((ROOT / 'benchmark/protocol.json').read_text())
    config = dict(control_profile=args.profile, policy=args.policy, track=session.mode,
                  cadence=session.profile.get('cadence'), frames=frames, decisions=decisions,
                  trials=args.trials, timeout=args.timeout, retries=args.retries,
                  level_spec=next(spec for spec in protocol['levels'] if spec['level'] == '1-1'))
    manifest = profile_manifest(config)
    output = (args.output or ROOT / 'benchmark/runs' /
              (args.profile + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    print(json.dumps(dict(output=str(output), profile=args.profile, model=session.model['id'],
                          track=session.mode, native_frame_budget=frames, derived_decisions=decisions,
                          max_successful_stage_requests=decisions * len(session.stages) * args.trials,
                          run_envelope_sha256=manifest['run_envelope_sha256'], execute=args.execute), indent=2), flush=True)
    if not args.execute:
        return
    output.mkdir(parents=True, exist_ok=True)
    destination = output / 'manifest.json'
    if destination.exists():
        _require(json.loads(destination.read_text()) == manifest,
                 'Resume manifest differs; source/profile/envelope cannot change or extend')
    else:
        _require(not any(output.iterdir()), 'Refusing an output directory without its original manifest')
        write_json(destination, manifest)
    if args.policy == 'openrouter':
        load_key()
    results = [execute_episode(output, config, trial) for trial in range(args.trials)]
    expected = [f'1-1:seed0:trial{trial:03d}' for trial in range(args.trials)]
    from benchmark.costs import costs_from_events
    billing = costs_from_events(read_events(output / (safe_name(session.model['id']) + '.jsonl')))
    summary = dict(profile=args.profile, results=results, **billing, aggregate=aggregate_results(results, expected),
                   development_only=True, common_benchmark_default=False)
    write_json(output / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


def audit_profile(path, manifest):
    config = manifest['config']
    _require(manifest == profile_manifest(config), 'Audit source/profile/envelope differs from run manifest')
    results = [execute_episode(path, config, trial, audit=True) for trial in range(config['trials'])]
    return dict(run=str(path), profile=config['control_profile'], episodes=len(results),
                calls=sum(row['audit_calls'] for row in results), actions=sum(row['decisions'] for row in results),
                statuses={status: sum(row['status'] == status for row in results)
                          for status in sorted({row['status'] for row in results})},
                replay='all request, native-choice/sampler, state, screen and native-frame hashes match')
