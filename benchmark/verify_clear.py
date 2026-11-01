"""Offline exact replay of recorded development clears; never calls a model."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from benchmark.client import digest, request_body
from prototype.control import QUESTIONS, RULES, compact_state, decode_action_response
from prototype.emulator import MarioGame


def verify(path, video=None):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    start = rows[0]
    assert start['event'] == 'start'
    model, interval = start['model'], start['interval']
    game, encoder = MarioGame(), None
    calls = 0
    cost = 0
    pending = None
    current_contract_matches = start['rules'] == RULES and start['questions'] == QUESTIONS
    try:
        assert compact_state(game.observe(), interval) == start['initial']
        if video:
            encoder = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
                '-pix_fmt', 'rgb24', '-s', '256x240', '-r', '60', '-i', '-', '-an',
                '-vf', 'scale=768:720:flags=neighbor', '-c:v', 'libx264', '-crf', '18',
                '-pix_fmt', 'yuv420p', str(video)], stdin=subprocess.PIPE)
            encoder.stdin.write(game.frame_rgb().tobytes())
        for row in rows[1:]:
            if row['event'] == 'request':
                assert row['frame'] == game.frame
                assert digest(row['body']) == row['body_sha256']
                assert row['body']['questions'] == start['questions']
                assert row['body']['state'] == start['rules'] + '\n' + compact_state(game.observe(), interval)
                if current_contract_matches:
                    state = game.observe()
                    state['control_interval_frames'] = interval
                    assert request_body(model, state) == row['body'], 'Current request contract differs from verified clear'
                pending = row['index']
            elif row['event'] == 'response':
                assert pending == row['index']
                response = row['response']
                assert response['model'] == model['expected_returned_model']
                assert response['provider'] in model['expected_returned_provider_names']
                buttons, _ = decode_action_response(response)
                assert buttons == row['buttons'] and row['frames'] == interval
                assert response['answers']['action']['choice'] == row['action']
                for _ in range(interval):
                    game.step(buttons)
                    if encoder:
                        encoder.stdin.write(game.frame_rgb().tobytes())
                    if game.done:
                        break
                cost += response.get('usage', {}).get('cost', 0)
                calls += 1
                pending = None
            elif row['event'] == 'step':
                assert compact_state(game.observe(), interval) == row['observation']
                assert game.observe() == row['native']
                assert hashlib.sha256(game.frame_rgb().tobytes()).hexdigest() == row['screen_sha256']
            elif row['event'] == 'end':
                assert row['result']['flag_get'] == game.flag_get
                assert row['result']['frames'] == game.frame
                assert row['result']['decisions'] == calls
        assert rows[-1]['event'] == 'end' and game.flag_get
        return dict(model=model['id'], provider=model['expected_returned_provider_names'],
                    flag_get=game.flag_get, frames=game.frame, decisions=calls,
                    cost_usd=cost, current_request_contract_matches=current_contract_matches,
                    replay='all prompt, action, native observation and screen hashes match',
                    video=str(video) if video else None)
    finally:
        game.close()
        if encoder:
            encoder.stdin.close()
            assert encoder.wait() == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path)
    parser.add_argument('--video', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.episode, args.video), indent=2))

if __name__ == '__main__':
    main()
