"""Meaningful no-API checks of isolation, exact stepping, PNG parity and recovery."""
from pathlib import Path
import collections
import json
import shutil
import subprocess
import sys
import tempfile
from PIL import Image

HERE = Path(__file__).resolve().parent

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = HERE.parent


def run(output, *extra):
    subprocess.run([sys.executable, str(HERE / 'run.py'), '--policy', 'fake', '--frames', '96',
                    '--concurrency', '22', '--output', str(output), '--execute', *extra], check=True,
                   stdout=subprocess.DEVNULL)


def audit(output, expected):
    config = json.loads((output / 'manifest.json').read_text())['config']
    cadence, frames = config['cadence'], config['frames']
    decisions = frames // cadence
    files = list(output.glob('*.jsonl'))
    assert len(files) == expected
    traces, pids = [], set()
    for file in files:
        rows = [json.loads(line) for line in file.read_text().splitlines()]
        first = rows[0]
        pids.add(first['worker_pid'])
        waiting = None
        trace = []
        for row in rows:
            event = row['event']
            if event == 'request_intent':
                assert waiting is None, 'More than one request in flight for a model'
                waiting = row['frame']
            elif event == 'request_result':
                assert waiting == row['frame_after_request'] == row['frame']
                waiting = None
            elif event == 'action':
                assert row['frames'] == cadence
                trace.append((row['observed_frame'], row['buttons'], row['observation_sha256'], row['image_sha256']))
            elif event == 'chunk_end':
                assert row['frame'] == (row['decision_index'] + 1) * cadence
        assert waiting is None
        result = rows[-1]['result']
        assert result['frames'] == frames and result['decisions'] == decisions and result['status'] == 'frame_budget'
        assert len(trace) == decisions
        traces.append((first['initial_sha256'], first['initial_screen_sha256'], trace))
    assert len(pids) == expected, f'{len(pids)} processes, expected {expected}'
    assert all(trace == traces[0] for trace in traces), 'Identical fake policies diverged across models'
    for file in output.glob('images/**/*.png'):
        with Image.open(file) as im:
            assert im.size == (512, 480) and im.format == 'PNG'
    return files


def main():
    with tempfile.TemporaryDirectory(prefix='mario-benchmark-smoke-') as tmp:
        base = Path(tmp)
        state = base / 'state'
        run(state)
        files = audit(state, 22)
        before = {f.name: f.read_bytes() for f in files}
        run(state)
        assert before == {f.name: f.read_bytes() for f in files}, 'Completed resume made requests'
        recovery = base / 'recovery'
        shutil.copytree(state, recovery)
        file = recovery / files[0].name
        rows = [json.loads(line) for line in file.read_text().splitlines()]
        cut = next(i for i, row in enumerate(rows) if row['event'] == 'action' and row['decision_index'] == 5)
        prefix = rows[:cut + 1]
        file.write_text(''.join(json.dumps(row) + '\n' for row in prefix))
        run(recovery)
        audit(recovery, 22)
        recovered = [json.loads(line) for line in file.read_text().splitlines()]
        assert recovered[-1]['result'] == rows[-1]['result']
        config = json.loads((state / 'manifest.json').read_text())['config']
        assert len([r for r in recovered if r['event'] == 'request_intent']) == config['frames'] // config['cadence']
        uncertain = base / 'uncertain'
        shutil.copytree(state, uncertain)
        file = uncertain / files[0].name
        cut = next(i for i, row in enumerate(rows) if row['event'] == 'request_intent' and row['decision_index'] == 5)
        file.write_text(''.join(json.dumps(row) + '\n' for row in rows[:cut + 1]))
        run(uncertain)
        after = [json.loads(line) for line in file.read_text().splitlines()]
        assert after[-1]['result']['status'] == 'infra_error'
        assert len([r for r in after if r['event'] == 'request_intent']) == 6, 'Uncertain paid request repeated'
        image = base / 'image'
        run(image, '--track', 'image', '--image-eligibility', 'advertised')
        audit(image, 17)
    print('PASS: 22 isolated state workers, 17 same-frame PNG workers, exact fixed steps, paused waits, identical trajectories, completed resume, action replay, uncertain-request protection')


if __name__ == '__main__':
    main()
