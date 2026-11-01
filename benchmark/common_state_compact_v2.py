"""One compact state controller for every registered model; definition only."""
from copy import deepcopy
import json
from pathlib import Path
from benchmark.profiles.state_v1 import compact_state

PROFILE=json.loads(Path(__file__).with_name('common_profiles').joinpath('state-compact-v2.json').read_text())


def state_text(state):
    return PROFILE['rules']+'\n'+compact_state(state,4)


def request(model,state):
    text=state_text(state)
    evidence={'observation_text':text} if model.get('state_serialization')=='json_object' else text
    return dict(model=model.get('request_model',model['id']),provider=deepcopy(model['provider']),state=evidence,questions=deepcopy(PROFILE['questions']))
