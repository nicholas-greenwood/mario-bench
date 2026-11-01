"""Process-isolated paused Mario development benchmark; no website or audio."""
from __future__ import annotations
import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = HERE.parent

from prototype.emulator import MarioGame
from PIL import Image
from benchmark.client import Client, FakeClient, canonical, digest, request_body, QUESTIONS, RULES


def write_json(path, value):
    path.write_bytes(json.dumps(value, indent=2, allow_nan=False).encode() + b'\n')


def read_events(path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    # A torn final append cannot count as a sent request or committed action.
    # Preserve it for forensic inspection; refusal is safer than making a duplicate paid request.
    if raw and not raw.endswith(b'\n'):
        raise RuntimeError(f'Torn log tail requires manual recovery: {path}')
    return [json.loads(line) for line in raw.splitlines() if line]


def append(path, event):
    event = dict(utc=datetime.now(timezone.utc).isoformat(), **event)
    with path.open('ab') as stream:
        stream.write(canonical(event) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def snapshot(game, cadence):
    state = game.observe()
    state['control_interval_frames'] = cadence
    return state


def png(game):
    stream = io.BytesIO()
    Image.fromarray(game.frame_rgb()).resize((512, 480), Image.Resampling.NEAREST).save(stream, format='PNG')
    return stream.getvalue()


def safe_name(model):
    return model.replace('/', '__')


def worker(job):
    """One process owns one model, environment, connection and JSONL file at a time."""
    from benchmark.scoring import score_episode, validated_progress_x, aggregate_results
    model, config, output = job
    path = Path(output) / (safe_name(model['id']) + '.jsonl')
    events = read_events(path)
    key = os.environ.get('OPENROUTER_API_KEY', '')
    client = FakeClient() if config['policy'] == 'fake' else Client(key, model, config['timeout'])
    game = None
    results = []
    try:
        level_specs = config.get('level_specs', [config['level_spec']])
        schedule = [(spec, trial) for spec in level_specs for trial in range(config['trials'])]
        for level_spec, trial in schedule:
            level = level_spec['level']
            episode_id = f'{level}:seed0:trial{trial:03d}'
            prior = [e for e in events if e.get('episode_id') == episode_id]
            finished = [e for e in prior if e['event'] == 'episode_end']
            if finished:
                results.append(finished[-1]['result'])
                continue
            game = MarioGame(level=level)
            state = snapshot(game, config['cadence'])
            start_x = state['player']['x']
            max_x = start_x
            decisions = 0
            if not prior:
                append(path, dict(event='episode_start', episode_id=episode_id, initial=state,
                                  worker_pid=os.getpid(), initial_sha256=digest(state), initial_screen_sha256=hashlib.sha256(game.frame_rgb().tobytes()).hexdigest()))
            else:
                begin = next(e for e in prior if e['event'] == 'episode_start')
                if digest(state) != begin['initial_sha256']:
                    raise RuntimeError('Initial emulator state differs from recorded run')
            status, error = None, None
            for index in range(config['decisions']):
                if game.done:
                    status = 'completed' if game.flag_get else 'game_over'
                    break
                if game.frame >= config['frames']:
                    status = 'frame_budget'
                    break
                state = snapshot(game, config['cadence'])
                recorded = [e for e in prior if e.get('decision_index') == index]
                actions = [e for e in recorded if e['event'] == 'action']
                if actions:
                    action = actions[-1]
                    if action['observation_sha256'] != digest(state):
                        raise RuntimeError(f'Replay mismatch at decision {index}')
                    buttons, steps = action['buttons'], action['frames']
                else:
                    # An intent without an outcome may already have been charged; never resend silently.
                    intents = [e for e in recorded if e['event'] == 'request_intent']
                    outcomes = [e for e in recorded if e['event'] == 'request_result']
                    if len(intents) > len(outcomes):
                        status, error = 'infra_error', 'Uncertain interrupted request; no duplicate sent'
                        break
                    image = png(game) if config['track'] == 'image' else None
                    image_hash = hashlib.sha256(image).hexdigest() if image else None
                    if image:
                        images = Path(output) / 'images' / safe_name(model['id']) / episode_id.replace(':', '_')
                        images.mkdir(parents=True, exist_ok=True)
                        (images / f'{index:06d}.png').write_bytes(image)
                    body = request_body(model, state, image, state_serialization='text' if config['track'] == 'image' else config.get('state_serialization', 'text'))
                    outcome = outcomes[-1] if outcomes else None
                    for attempt in range(len(outcomes), config['retries'] + 1):
                        if outcome and (outcome.get('valid') or not outcome.get('retryable')):
                            break
                        if attempt:
                            time.sleep(min(2 ** (attempt - 1), 4))
                        append(path, dict(event='request_intent', episode_id=episode_id, decision_index=index,
                                          attempt=attempt, frame=game.frame, observation=state,
                                          observation_sha256=digest(state), image_sha256=image_hash,
                                          request_sha256=digest(body)))
                        outcome = client.call(body)
                        if digest(snapshot(game, config['cadence'])) != digest(state):
                            raise RuntimeError('Emulator advanced while decision request was pending')
                        outcome['frame_after_request'] = game.frame
                        append(path, dict(event='request_result', episode_id=episode_id, decision_index=index,
                                          attempt=attempt, frame=game.frame, **outcome))
                        if outcome['valid'] or not outcome.get('retryable'):
                            break
                    if not outcome or not outcome['valid']:
                        status = 'invalid_action' if outcome and outcome.get('error_type') == 'invalid_action' else 'infra_error'
                        error = (outcome or {}).get('error', 'No validated response')
                        break
                    buttons = outcome['decision']['buttons']
                    steps = min(config['cadence'], config['frames'] - game.frame)
                    append(path, dict(event='action', episode_id=episode_id, decision_index=index,
                                      observed_frame=game.frame, observation_sha256=digest(state),
                                      image_sha256=image_hash, buttons=buttons, frames=steps))
                for _ in range(steps):
                    observation = game.step(buttons)
                    candidate = validated_progress_x(observation, start_x)
                    if candidate is not None:
                        max_x = max(max_x, candidate)
                    if game.done:
                        break
                decisions += 1
                if not actions:
                    append(path, dict(event='chunk_end', episode_id=episode_id, decision_index=index,
                                      frame=game.frame, observation=snapshot(game, config['cadence']),
                                      screen_sha256=hashlib.sha256(game.frame_rgb().tobytes()).hexdigest()))
            if status is None:
                status = ('completed' if game.flag_get else 'game_over') if game.done else ('frame_budget' if game.frame >= config['frames'] else 'decision_budget')
            result = dict(episode_id=episode_id, model=model['id'], track=config['track'], level=level, seed=0,
                          status=status, completed=bool(game.flag_get), max_progress_x=max_x, start_x=start_x,
                          frames=game.frame, decisions=decisions, deaths=int(game.death), error=error,
                          native_frames_to_completion=game.frame if status == 'completed' and game.flag_get else None)
            result = score_episode(result, level_spec)
            append(path, dict(event='episode_end', episode_id=episode_id, result=result))
            results.append(result)
            game.close()
            game = None
    finally:
        if game:
            game.close()
        client.close()
    return dict(model=model['id'], results=results, aggregate=aggregate_results(results, [f"{spec['level']}:seed0:trial{trial:03d}" for spec in config.get('level_specs', [config['level_spec']]) for trial in range(config['trials'])]))


def load_key():
    if os.environ.get('OPENROUTER_API_KEY'):
        return
    path = ROOT / '.env'
    for line in path.read_text().splitlines() if path.exists() else []:
        name, sep, value = line.strip().partition('=')
        if sep and name == 'OPENROUTER_API_KEY':
            os.environ[name] = value.strip().strip('"').strip("'")
            return
    raise RuntimeError('OPENROUTER_API_KEY is missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', help='Explicit selected frozen development profile; see benchmark/profiles/README.md')
    parser.add_argument('--max-native-frames', type=int, help='Frozen-profile immutable native frame cap (default6000)')
    parser.add_argument('--roster', type=Path, default=HERE / 'models.json')
    parser.add_argument('--models', nargs='+')
    parser.add_argument('--levels', nargs='+', choices=['1-1', '1-2', '1-3', '1-4'], default=['1-1'])
    parser.add_argument('--track', choices=['state', 'image'], default=None)
    parser.add_argument('--state-serialization', choices=['auto', 'text', 'json_object'], default='auto')
    parser.add_argument('--image-eligibility', choices=['verified', 'advertised'], default='verified')
    parser.add_argument('--policy', choices=['openrouter', 'fake'], default='openrouter')
    parser.add_argument('--concurrency', type=int, default=22)
    parser.add_argument('--cadence', type=int, default=None)
    parser.add_argument('--frames', type=int, default=6000)
    parser.add_argument('--decisions', type=int)
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--retries', type=int, default=1)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--execute', action='store_true', help='Run planned model requests; otherwise print plan only')
    args = parser.parse_args()
    if args.profile:
        from benchmark.profile_runtime import PROFILE_IDS
        if args.profile not in PROFILE_IDS:
            parser.error("Runnable frozen profiles: " + ", ".join(PROFILE_IDS))
        from benchmark.frozen_run import run_profile
        return run_profile(args, parser)
    if args.max_native_frames is not None:
        parser.error("--max-native-frames requires --profile; use --frames for the common runner")
    args.track = args.track or "state"
    args.cadence = 4 if args.cadence is None else args.cadence
    if min(args.concurrency, args.cadence, args.frames, args.trials) < 1 or not 0 <= args.retries <= 3 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('Positive budgets/timeouts required; retries must be between zero and three')
    if args.frames % args.cadence:
        parser.error('Frame budget must be divisible by cadence so every action interval is identical')
    decisions = args.decisions or math.ceil(args.frames / args.cadence)
    if decisions < math.ceil(args.frames / args.cadence):
        parser.error('Decision budget must cover the entire frame budget; lower --frames for a shorter shared run')
    roster = json.loads(args.roster.read_text())
    models = roster['models']
    if args.models:
        models = [m for m in models if m['id'] in args.models]
        if {m['id'] for m in models} != set(args.models):
            parser.error('Unknown requested model')
    if args.track == 'image':
        models = [m for m in models if m['image_advertised'] and (args.image_eligibility == 'advertised' or m.get('image_preflight_passed') or args.policy == 'fake')]
        models = [dict(m, provider=m.get('image_provider', m['provider']), expected_returned_provider_names=m.get('image_expected_returned_provider_names', m.get('expected_returned_provider_names'))) for m in models]
    if not models:
        parser.error('No eligible models')
    if args.track == 'image' and args.state_serialization == 'json_object':
        parser.error('State serialization adapters are state-track only; pixels-only input stays unchanged')
    from benchmark.scoring import score_episode
    protocol = json.loads((HERE / 'protocol.json').read_text())
    level_specs = [spec for spec in protocol['levels'] if spec['level'] in args.levels]
    if len(level_specs) != len(set(args.levels)):
        parser.error('Requested level is missing from protocol')
    level_spec = level_specs[0]
    config = dict(policy=args.policy, track=args.track, cadence=args.cadence, frames=args.frames,
                  control_profile='joint-visible-v1', state_serialization=args.state_serialization,
                  decisions=decisions, trials=args.trials, timeout=args.timeout, retries=args.retries,
                  level_spec=level_spec, level_specs=level_specs)
    output = (args.output or HERE / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    # A request can spend account credits. The key's account cap is the user's chosen financial limit.
    manifest = dict(schema_version=2, config=config, models=models, protocol=protocol,
                    roster_sha256=digest(roster), questions=QUESTIONS, rules=RULES,
                    software_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), HERE / 'client.py', HERE / 'scoring.py', HERE.parent / 'prototype/emulator.py', HERE.parent / 'prototype/decisions.py', HERE.parent / 'prototype/control.py', HERE.parent / 'prototype/image_observation.py']},
                    conditions='Explicit selected levels, seed0, one life per trial; public development only; shared cadence4 default; controller chosen during public 1-1 development',
                    concurrency=min(args.concurrency, len(models)), max_inflight_per_model=1)
    print(json.dumps(dict(output=str(output), models=len(models), track=args.track, frames=args.frames,
                          max_successful_decisions_per_model=decisions * args.trials * len(level_specs),
                          concurrency=manifest['concurrency'], execute=args.execute), indent=2), flush=True)
    if not args.execute:
        return
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / 'manifest.json'
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise RuntimeError('Resume manifest differs; choose another output directory')
    else:
        write_json(manifest_path, manifest)
    if args.policy == 'openrouter':
        load_key()
    ctx = multiprocessing.get_context('spawn')
    results, failures = [], []
    with concurrent.futures.ProcessPoolExecutor(max_workers=manifest['concurrency'], mp_context=ctx) as pool:
        futures = {pool.submit(worker, (m, config, str(output))): m['id'] for m in models}
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(json.dumps(dict(model=model, statuses=[r['status'] for r in result['results']], frames=[r['frames'] for r in result['results']])), flush=True)
            except Exception as exc:
                failures.append(dict(model=model, error=type(exc).__name__ + ': ' + str(exc)))
                print(json.dumps(failures[-1]), flush=True)
            write_json(output / 'summary.json', dict(models=sorted(results, key=lambda r: r['model']), worker_failures=failures,
                                                     expected_models=[m['id'] for m in models], development_only=True))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
