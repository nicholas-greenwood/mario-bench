"""Versioned development contracts; separate from the common benchmark default."""
from __future__ import annotations
import json
from pathlib import Path
from benchmark.profiles.state_v1 import compact_state, compact_phase, exposed_surfaces


def load_profile(name):
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name):
        raise ValueError('Invalid profile name')
    return json.loads(Path(__file__).with_name(name + '.json').read_text())


def state_text(profile, state):
    builders = {'compact_state': compact_state, 'compact_phase': compact_phase, 'exposed_surfaces': exposed_surfaces}
    return profile['rules'] + '\n' + builders[profile['observer']](state, profile['cadence'])
