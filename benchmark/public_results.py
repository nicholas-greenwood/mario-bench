"""Verify portable public action traces and optionally render their silent replays.

No API calls, credentials or private experiment directories are needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor

from benchmark.client import digest
from benchmark.scoring import validated_progress_x
from prototype.control import ACTIONS
from prototype.emulator import MarioGame

ROOT = Path(__file__).resolve().parents[1]


def decode_answers(trace, response):
    """Expand native choices directly; never insert a gameplay helper."""
    answers = response['answers']
    for name, question in trace['contract']['questions'].items():
        answer = answers[name]
        probabilities = answer['probabilities']
        assert answer['type'] == 'choice'
        assert set(probabilities) == set(question['criteria'])
        assert answer['choice'] in probabilities
        assert all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1
                   for v in probabilities.values())
        assert abs(sum(probabilities.values()) - 1) <= .03
    adapter = trace['contract'].get('adapter')
    if adapter is None:
        if set(answers) == {'horizontal', 'vertical', 'run', 'jump'}:
            adapter = 'independent_buttons'
        elif set(answers) == {'movement', 'jump'}:
            adapter = 'movement_and_jump'
        elif answers['action']['choice'] in ACTIONS:
            adapter = 'joint12'
        else:
            adapter = 'explicit_ab_joint12'
    if adapter == 'joint12':
        return dict(ACTIONS[answers['action']['choice']])
    if adapter == 'explicit_ab_joint12':
        match = re.fullmatch(r'(left|released|right)_B_(held|released)_A_(held|released)',
                             answers['action']['choice'])
        assert match
        horizontal, run, jump = match.groups()
        return dict(horizontal=horizontal, vertical='released', run=run, jump=jump)
    if adapter == 'independent_buttons':
        return {name: answers[name]['choice'] for name in ('horizontal', 'vertical', 'run', 'jump')}
    if adapter == 'movement_and_jump':
        movement = trace['contract'].get('movement', {
            'brake_left': dict(horizontal='left', vertical='released', run='held'),
            'coast': dict(horizontal='released', vertical='released', run='released'),
            'run_right': dict(horizontal='right', vertical='released', run='held'),
            'walk_right': dict(horizontal='right', vertical='released', run='released'),
        })
        buttons = dict(movement[answers['movement']['choice']])
        buttons['jump'] = answers['jump']['choice']
        return buttons
    raise ValueError(f'Unsupported public adapter: {adapter}')


def decode_sequence(trace, response, cadence):
    """Expand fixed temporal choices as declared, without inspecting the game."""
    choice = response['answers'].get('action', {}).get('choice', '')
    fresh = re.fullmatch(r'fresh_(running|walking|left)_jump_(24|40)', choice)
    fixed = re.fullmatch(r'(run_forward|walk_forward|run_left|sustain_running_jump|sustain_walking_jump|coast_release_jump)_(4|8|16)', choice)
    if not fresh and not fixed:
        return [[cadence, decode_answers(trace, response)]]
    # Validate the same native probability contract before expanding the macro.
    answer = response['answers']['action']
    criteria = trace['contract']['questions']['action']['criteria']
    assert answer['type'] == 'choice' and choice in criteria
    assert set(answer['probabilities']) == set(criteria)
    assert all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1
               for v in answer['probabilities'].values())
    assert abs(sum(answer['probabilities'].values()) - 1) <= .03
    buttons = dict(horizontal='right', vertical='released', run='held', jump='released')
    if fresh:
        style, duration = fresh.groups()
        buttons['horizontal'] = 'left' if style == 'left' else 'right'
        buttons['run'] = 'released' if style == 'walking' else 'held'
        return [[1, buttons], [int(duration), dict(buttons, jump='held')]]
    name, duration = fixed.groups()
    if name == 'coast_release_jump':
        buttons.update(horizontal='released', run='released')
    elif name == 'run_left':
        buttons['horizontal'] = 'left'
    elif name == 'walk_forward':
        buttons['run'] = 'released'
    elif name.startswith('sustain_'):
        buttons.update(jump='held', run='released' if 'walking' in name else 'held')
    return [[int(duration), buttons]]


def safe_asset(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Public asset path escapes the dataset')
    return path


def verify_episode(root, summary, render=False):
    trace_path = safe_asset(root, summary['trace_href'])
    assert hashlib.sha256(trace_path.read_bytes()).hexdigest() == summary['trace_sha256']
    trace = json.loads(trace_path.read_text())
    assert trace['id'] == summary['id']
    assert digest(trace['contract']) == summary['experiment_config']['contract_sha256']
    game, encoder = MarioGame(summary['level']), None
    furthest = float(game.observe()['player']['x'])
    try:
        if render:
            video = safe_asset(root, summary['replay_href'])
            video.parent.mkdir(parents=True, exist_ok=True)
            encoder = subprocess.Popen([
                'ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                '-s', '256x240', '-r', '60', '-i', '-', '-an', '-vf',
                'scale=512:480:flags=neighbor', '-c:v', 'libx264', '-crf', '26',
                '-pix_fmt', 'yuv420p', '-threads', '1', '-movflags', '+faststart', str(video),
            ], stdin=subprocess.PIPE)
            encoder.stdin.write(game.frame_rgb().tobytes())
        for index, action in enumerate(trace['actions']):
            assert action['index'] == index and action['frame_before'] == game.frame
            assert action['native_response']['model'] == summary['returned_model']
            assert action['native_response']['provider'] == summary['provider']
            expected = decode_sequence(trace, action['native_response'], summary['experiment_config']['cadence'])
            # Older showcase exports shorten only their terminal held interval.
            recorded = action['sequence']
            assert len(recorded) == len(expected)
            for (duration, buttons), (maximum, expected_buttons) in zip(recorded, expected):
                assert buttons == expected_buttons and 0 < duration <= maximum
            if action.get('before_observation_sha256'):
                assert digest(game.observe()) == action['before_observation_sha256']
            for frames, held in action['sequence']:
                for _ in range(frames):
                    observation = game.step(held)
                    candidate = validated_progress_x(observation, summary['start_x'])
                    if candidate is not None:
                        furthest = max(furthest, candidate)
                    if encoder:
                        encoder.stdin.write(game.frame_rgb().tobytes())
                    if game.done:
                        break
                if game.done:
                    break
            assert recorded == expected or game.done, 'Only terminal actions can have a partial interval'
            assert action['frame_after'] == game.frame
            assert digest(game.observe()) == action['after_observation_sha256']
            assert hashlib.sha256(game.frame_rgb().tobytes()).hexdigest() == action['screen_after_sha256']
        assert game.frame == summary['native_frames']
        assert len(trace['actions']) == summary['decisions']
        assert bool(game.flag_get) == summary['completed']
        assert bool(game.death) == summary['death']
        assert furthest == summary['furthest_valid_x']
        expected_progress = 100.0 if game.flag_get else min(99.9, max(0.0,
            100 * (furthest - summary['start_x']) / (summary['goal_x'] - summary['start_x'])))
        assert expected_progress == summary.get('observed_progress_pct', summary['progress_pct'])
        expected_speed = game.frame if game.flag_get else None
        assert summary['speedrun_score_native_frames'] == expected_speed
        assert summary['nominal_game_seconds_to_completion'] == (expected_speed / 60 if expected_speed else None)
        return dict(id=summary['id'], mode=summary['mode'], native_frames=game.frame,
                    decisions=len(trace['actions']), completed=bool(game.flag_get),
                    furthest_valid_x=furthest, native_replay_verified=True)
    finally:
        if encoder:
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError('Replay video encoding failed')
        game.close()


def probe_replay(path, native_frames):
    streams = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path),
    ]))['streams']
    assert len(streams) == 1, 'Replay must contain one video stream and no audio'
    stream = streams[0]
    assert stream['codec_type'] == 'video' and stream['codec_name'] == 'h264'
    assert (stream['width'], stream['height']) == (512, 480)
    assert stream['r_frame_rate'] == '60/1'
    assert int(stream['nb_frames']) == native_frames + 1, 'Initial screen plus every native frame required'
    assert abs(float(stream['duration']) - (native_frames + 1) / 60) < .001


def _render_group(task):
    root, summaries, replay_href, render = task
    for index, summary in enumerate(summaries):
        verify_episode(root, dict(summary, replay_href=replay_href), render and index == 0)
    replay = safe_asset(root, replay_href)
    probe_replay(replay, summaries[0]['native_frames'])
    return replay_href, hashlib.sha256(replay.read_bytes()).hexdigest(), [e['id'] for e in summaries]


def backfill_replays(root, jobs=4):
    """Render all playable public traces; reuse videos only for identical input tapes."""
    index_path = root / 'index.json'
    index = json.loads(index_path.read_text())
    groups, unavailable = {}, []
    records = [record for section in ('examples', 'observations', 'technical_diagnostics')
               for record in index.get(section, [])]
    for record in records:
        trace_path = safe_asset(root, record['trace_href'])
        assert hashlib.sha256(trace_path.read_bytes()).hexdigest() == record['trace_sha256']
        trace = json.loads(trace_path.read_text())
        if not trace['actions']:
            assert record['native_frames'] == record['decisions'] == 0
            record.update(replay_href=None, replay_sha256=None,
                          replay_unavailable_reason='no native gameplay frames: the api attempt ended before any action')
            unavailable.append(record['id'])
            continue
        # The initial state is deterministic for each level. Expand segments to
        # per-frame holds so different decision boundaries can share one video.
        tape = [buttons for action in trace['actions'] for duration, buttons in action['sequence']
                for _ in range(duration)][:record['native_frames']]
        key = digest(dict(level=record['level'], native_frames=record['native_frames'], tape=tape))
        groups.setdefault(key, []).append(record)
    tasks = []
    for records_for_tape in groups.values():
        existing = next((record for record in records_for_tape if record.get('replay_href')), None)
        if existing:
            replay_href = existing['replay_href']
            replay = safe_asset(root, replay_href)
            assert hashlib.sha256(replay.read_bytes()).hexdigest() == existing['replay_sha256']
        else:
            assert re.fullmatch(r'[a-zA-Z0-9_-]+', records_for_tape[0]['id'])
            replay_href = f"replays/{records_for_tape[0]['id']}.mp4"
        tasks.append((root, records_for_tape, replay_href, existing is None))
    with ProcessPoolExecutor(max_workers=jobs) as workers:
        for href, checksum, ids in workers.map(_render_group, tasks):
            for record in records:
                if record['id'] in ids:
                    record.update(replay_href=href, replay_sha256=checksum)
                    record.pop('replay_unavailable_reason', None)
            print(json.dumps(dict(replay=href, verified_ids=ids)), flush=True)
    index_path.write_text(json.dumps(index, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(unique_replay_videos=len(groups),
                          playable_observations=sum(bool(e.get('replay_href')) for e in index.get('observations', [])),
                          unavailable=unavailable)))


def verify_dataset(root, render=False):
    index = json.loads((root / 'index.json').read_text())
    assert index['data_class'] == 'selected_development_examples'
    assert index['comparable_aggregate'] is None
    assert {e['mode'] for e in index['examples']} == {'state', 'image'}
    models = json.loads(safe_asset(root, index['models_href']).read_text())['models']
    assert len(models) == index['model_counts']['state']
    assert sum(m['modes']['image'] for m in models) == index['model_counts']['image']
    model_ids = {m['id'] for m in models}
    for example in index['examples']:
        assert example['model_id'] in model_ids and example['verified'] is True
        assert example['data_class'] == index['data_class']
        assert example['mode'] != 'image' or example['input_audit']['privileged_state_sent'] is False
        profile_path = safe_asset(root, example['profile_href'])
        assert hashlib.sha256(profile_path.read_bytes()).hexdigest() == example['profile_sha256']
        profile = json.loads(profile_path.read_text())
        trace = json.loads(safe_asset(root, example['trace_href']).read_text())
        assert profile['contract'] == trace['contract']
        assert profile['cadence'] == example['experiment_config']['cadence']
        assert profile['mode'] == example['mode']
    reports = [verify_episode(root, e, render) for e in index['examples']]
    for example in index['examples']:
        replay = safe_asset(root, example['replay_href'])
        assert replay.exists()
        if not render:
            assert hashlib.sha256(replay.read_bytes()).hexdigest() == example['replay_sha256']
    print(json.dumps(dict(episodes=len(reports), verified=reports), indent=2))
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path, nargs='?', default=ROOT / 'results')
    parser.add_argument('--render', action='store_true', help='Recreate silent MP4s from the recorded model choices')
    parser.add_argument('--backfill', action='store_true', help='Verify every public trace, render missing videos and update their links')
    parser.add_argument('--jobs', type=int, default=4, choices=range(1, 9), help='Parallel offline replay workers (default: 4)')
    args = parser.parse_args()
    if args.backfill:
        backfill_replays(args.dataset.resolve(), args.jobs)
    else:
        verify_dataset(args.dataset, args.render)


if __name__ == '__main__':
    main()
