"""Replay a completed run from its initial state and recorded actions; never calls an API."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototype.emulator import MarioGame
from benchmark.client import FakeClient, digest, request_body, legacy_request_body
from prototype.decisions import OpenRouterPolicy
from benchmark.run import snapshot, png
from benchmark.scoring import score_episode, validated_progress_x


def audit(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    cadence = manifest['config']['cadence']
    models = {m['id']: m for m in manifest['models']}
    calls = valid = actions = 0
    reported_cost = 0
    episodes = []
    for file in sorted(path.glob('*.jsonl')):
        rows = [json.loads(line) for line in file.read_text().splitlines()]
        model_id = next(m for m in models if m.replace('/', '__') == file.stem)
        validator = OpenRouterPolicy('offline-audit', model=model_id)
        game = None
        waiting = None
        try:
            for row in rows:
                event = row['event']
                if event == 'episode_start':
                    if game:
                        game.close()
                    game = MarioGame(level=row["initial"].get("level", "1-1"))
                    assert digest(snapshot(game, cadence)) == row['initial_sha256']
                    assert hashlib.sha256(game.frame_rgb().tobytes()).hexdigest() == row['initial_screen_sha256']
                    start_x = game.observe()['player']['x']
                    max_x, decisions = start_x, 0
                elif event == 'request_intent':
                    assert waiting is None
                    assert digest(snapshot(game, cadence)) == row['observation_sha256']
                    waiting = row['frame']
                    image = png(game) if manifest['config']['track'] == 'image' else None
                    assert (hashlib.sha256(image).hexdigest() if image else None) == row['image_sha256']
                    profile = manifest['config'].get('control_profile', 'legacy')
                    body = (legacy_request_body(models[model_id], row['observation'], image) if profile == 'legacy'
                            else request_body(models[model_id], row['observation'], image, profile=profile,
                                              state_serialization='text' if manifest['config']['track'] == 'image' else manifest['config'].get('state_serialization', 'text')))
                    # Requests use the manifest's frozen questions/rules. Current code must match that contract.
                    assert body['questions'] == manifest['questions']
                    assert digest(body) == row['request_sha256']
                elif event == 'request_result':
                    calls += 1
                    assert game.frame == waiting == row['frame_after_request'] == row['frame']
                    waiting = None
                    if isinstance(row.get('raw_response'), dict):
                        reported_cost += row['raw_response'].get('usage', {}).get('cost', 0)
                    if row['valid']:
                        valid += 1
                        if manifest['config']['policy'] == 'fake':
                            assert row['raw_response'] == {'fixture': True}
                            parsed = FakeClient().call(body)['decision']
                        else:
                            parsed = validator._parse_response(row['raw_response'], 0)
                        assert parsed['buttons'] == row['decision']['buttons']
                elif event == 'action':
                    actions += 1
                    assert row['frames'] == cadence
                    assert row['observed_frame'] == game.frame
                    assert digest(snapshot(game, cadence)) == row['observation_sha256']
                    for _ in range(row['frames']):
                        observation = game.step(row['buttons'])
                        candidate = validated_progress_x(observation, start_x)
                        if candidate is not None:
                            max_x = max(max_x, candidate)
                        if game.done:
                            break
                    decisions += 1
                elif event == 'chunk_end':
                    assert game.frame == row['frame']
                    assert digest(snapshot(game, cadence)) == digest(row['observation'])
                    assert hashlib.sha256(game.frame_rgb().tobytes()).hexdigest() == row['screen_sha256']
                elif event == 'episode_end':
                    result = row['result']
                    assert result['frames'] == game.frame and result['decisions'] == decisions
                    assert result['max_progress_x'] == max_x
                    specs = manifest['config'].get('level_specs', [manifest['config']['level_spec']])
                    level_spec = next(spec for spec in specs if spec['level'] == result['level'])
                    rescored = score_episode(result, level_spec)
                    assert all(rescored.get(key) == value for key, value in result.items()), 'Recorded score fields changed'
                    episodes.append(result)
        finally:
            if game:
                game.close()
    return dict(run=str(path), episodes=len(episodes), calls=calls, valid_responses=valid,
                recovered_service_failures=calls-valid, actions=actions, reported_cost_usd=reported_cost,
                statuses={status: sum(r['status'] == status for r in episodes) for status in sorted({r['status'] for r in episodes})},
                replay='all state, screenshot and native-frame hashes match')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path, nargs='+')
    args = parser.parse_args()
    for path in args.runs:
        print(json.dumps(audit(path.resolve()), indent=2))


if __name__ == '__main__':
    main()
