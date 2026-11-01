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
    adapter = trace['contract']['adapter']
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
        buttons = dict(trace['contract']['movement'][answers['movement']['choice']])
        buttons['jump'] = answers['jump']['choice']
        return buttons
    raise ValueError(f'Unsupported public adapter: {adapter}')


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
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video),
            ], stdin=subprocess.PIPE)
            encoder.stdin.write(game.frame_rgb().tobytes())
        for index, action in enumerate(trace['actions']):
            assert action['index'] == index and action['frame_before'] == game.frame
            assert action['native_response']['model'] == summary['returned_model']
            assert action['native_response']['provider'] == summary['provider']
            buttons = decode_answers(trace, action['native_response'])
            assert len(action['sequence']) == 1
            duration, recorded_buttons = action['sequence'][0]
            cadence = summary['experiment_config']['cadence']
            assert recorded_buttons == buttons and 0 < duration <= cadence
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
            assert duration == cadence or game.done, 'Only terminal actions can have a partial interval'
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
        assert expected_progress == summary['progress_pct']
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
    args = parser.parse_args()
    verify_dataset(args.dataset, args.render)


if __name__ == '__main__':
    main()
