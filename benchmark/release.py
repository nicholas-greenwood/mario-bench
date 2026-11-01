"""Export the current development contract without calls, staging or publication."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

from benchmark.client import digest
from prototype.control import ACTIONS, QUESTIONS, RULES

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_manifest() -> dict:
    """Lock a reviewable candidate; this never promotes exploratory wins to scores."""
    from gym_super_mario_bros._roms import smb1_rom_path

    protocol = json.loads((ROOT / 'benchmark/protocol.json').read_text())
    roster = json.loads((ROOT / 'benchmark/models.json').read_text())
    source_files = sorted(
        path for package in ('prototype', 'benchmark')
        for path in (ROOT / package).rglob('*.py')
    )
    source_files += sorted((ROOT / 'benchmark/profiles').glob('*.json'))
    source_files += [ROOT / name for name in (
        'benchmark/protocol.json', 'benchmark/models.json', 'pyproject.toml',
        'requirements.txt', 'requirements.lock.txt',
    )]
    rom_hash = sha256(Path(smb1_rom_path()))
    expected_rom = protocol.get('endpoint_calibration', {}).get('rom_sha256')
    if expected_rom and rom_hash != expected_rom:
        raise ValueError('Installed ROM differs from calibrated protocol; recalibrate before evaluation')
    models = roster['models']
    return dict(
        schema_version=1,
        release_status='development_candidate',
        leaderboard_ready=False,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        protocol=protocol,
        control_profile='joint-visible-v1',
        prompt=RULES,
        questions=QUESTIONS,
        actions=ACTIONS,
        prompt_and_action_schema_sha256=digest(dict(rules=RULES, questions=QUESTIONS, actions=ACTIONS)),
        observation_profiles=dict(
            state='compact current visible RAM geometry/motion and recent positions',
            image='current pixels only plus declared buttons/native frame/action interval; no RAM state',
            previous_screens=0,
            previous_model_controls=0,
        ),
        defaults=dict(cadence=protocol['timing']['native_frames_per_action'],
                      native_frames=protocol['timing']['frame_budget'],
                      decisions=protocol['timing']['decision_budget'],
                      lives=protocol['timing']['life_budget']),
        levels=protocol['levels'],
        model_provider_roster=models,
        eligible_state_model_ids=[m['id'] for m in models],
        eligible_image_model_ids=[m['id'] for m in models if m.get('image_preflight_passed')],
        rom_sha256=rom_hash,
        calibrated_1_1_initial_ram_sha256=protocol.get('endpoint_calibration', {}).get('initial_ram_sha256'),
        runtime=dict(python=platform.python_version(), packages={
            name: version(name) for name in ('gym-super-mario-bros', 'nes-py', 'pillow')
        }),
        software_sha256={str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        remaining_before_final_freeze=[
            'finish the verified three-distinct-model clears on each World 1-1 observation track',
            'select one common configuration from all successful and near-miss development evidence',
            'prespecify the complete matched repeat cohort and validated per-level progress mappings',
            'run and publish every prespecified outcome under the common frozen manifest',
        ],
        interpretation='This snapshots working code, not an evaluation result or a final benchmark release.',
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write JSON here; otherwise print it')
    args = parser.parse_args()
    manifest = candidate_manifest()
    encoded = json.dumps(manifest, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(json.dumps(dict(output=str(args.output.resolve()), release_status=manifest['release_status'],
                              state_models=len(manifest['eligible_state_model_ids']),
                              image_models=len(manifest['eligible_image_model_ids']))))
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
