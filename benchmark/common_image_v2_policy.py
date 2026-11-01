"""Conditional common image-v2 candidate: fixed full-frame pixels, one native call.

Pure policy only. The outer preregistered runner owns temperature, RNG seed,
truthful screenshot/control provenance, native stepping and budget truncation.
No RAM, emulator, network, filesystem, model-specific policy or activation logic.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
import math

from PIL import Image
from benchmark.profiles import image_v1
from benchmark.profiles.probability_sampler_v1 import sample_choice

BUILDER_PROFILE_ID = 'pixels-edge-pplx-c7-v1'
FRAMES_PER_ACTION = 7
TEMPERATURES = (.05, .2)
DEPENDENCIES = ('benchmark/common_image_v2_policy.py', 'benchmark/profiles/image_v1.py',
                'benchmark/profiles/probability_sampler_v1.py')
_BUTTON_OPTIONS = dict(horizontal={'left', 'released', 'right'}, vertical={'released'},
                       jump={'held', 'released'}, run={'held', 'released'})


def _clock(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{label} must be a nonnegative native/control clock')
    return value


def _buttons(value):
    if (not isinstance(value, dict) or set(value) != set(_BUTTON_OPTIONS)
            or any(not isinstance(value[name], str) or value[name] not in options
                   for name, options in _BUTTON_OPTIONS.items())):
        raise ValueError('Only the four declared joint-controller button fields are permitted')
    return dict(value)


def _screen(data):
    if not isinstance(data, bytes) or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('A lossless full-screen PNG is required')
    with Image.open(BytesIO(data)) as image:
        image.load()
        if image.mode != 'RGB' or image.size not in ((256, 240), (512, 480)):
            raise ValueError('Only full native RGB256x240 or nearest2x512x480 screenshots are permitted')
        if image.size == (512, 480):
            restored = image.resize((256, 240), Image.Resampling.NEAREST).resize((512, 480), Image.Resampling.NEAREST)
            if restored.tobytes() != image.tobytes():
                raise ValueError('Full screens must preserve exact nearest-neighbour native pixels')
    return data


def build_request(model, image_png, native_frame, decision_index, buttons,
                  previous_controls=(), previous_images=()):
    """Exact historical neutral evidence; substitute only declared wire identities."""
    _clock(native_frame, 'native_frame')
    _clock(decision_index, 'decision_index')
    current = _buttons(buttons)
    controls = list(previous_controls)
    images = list(previous_images)
    if len(controls) > 2 or len(images) > 1:
        raise ValueError('The shared contract permits only two own controls and one past full screen')
    previous_end = None
    for record in controls:
        if not isinstance(record, dict) or set(record) != {'frame', 'frames', 'buttons'}:
            raise ValueError('Only declared control clocks, holds and buttons are permitted; no RAM fields')
        start = _clock(record['frame'], 'control frame')
        hold = _clock(record['frames'], 'control hold')
        _buttons(record['buttons'])
        if not 1 <= hold <= FRAMES_PER_ACTION or start + hold > native_frame:
            raise ValueError('Invalid actual control hold or future control clock')
        if previous_end is not None and start != previous_end:
            raise ValueError('Own-control records must be chronological and consecutive')
        previous_end = start + hold
    if controls and (previous_end != native_frame or controls[-1]['buttons'] != current):
        raise ValueError('Current declared buttons/clock must match the most recent actual own control')
    for record in images:
        if not isinstance(record, (tuple, list)) or len(record) != 2:
            raise ValueError('Past screens accept only a native clock and PNG bytes')
        stamp, data = record
        if _clock(stamp, 'past image frame') >= native_frame:
            raise ValueError('A past screen must precede the current native frame')
        _screen(data)
    body = image_v1.profile_request(BUILDER_PROFILE_ID, image_png=_screen(image_png),
                                   frame=native_frame, decision_index=decision_index,
                                   buttons=current, previous_controls=controls, previous_images=images)
    request_model = model.get('request_model', model.get('id'))
    if not isinstance(request_model, str) or not request_model or not isinstance(model.get('provider'), dict):
        raise ValueError('Explicit pinned request model and provider routing are required')
    body['model'] = request_model
    body['provider'] = deepcopy(model['provider'])
    return body


def parse(raw, body, model):
    """Validate native identity and the whole12-way vector, without consuming RNG."""
    if (not isinstance(raw, dict) or raw.get('error')
            or raw.get('model') != model['expected_returned_model']
            or raw.get('provider') not in model['expected_returned_provider_names']):
        raise ValueError('Native response differs from the declared returned model/provider pins')
    if (set(body) != {'model', 'provider', 'state', 'questions'}
            or body['model'] != model.get('request_model', model.get('id'))
            or body['provider'] != model['provider']
            or body['questions'] != image_v1.PROFILES[BUILDER_PROFILE_ID]['questions']):
        raise ValueError('Request differs from the shared frozen wire contract')
    answers = raw.get('answers')
    if not isinstance(answers, dict) or set(answers) != {'action'}:
        raise ValueError('Exactly one native joint action answer is required')
    answer = answers['action']
    criteria = body['questions']['action']['criteria']
    if (not isinstance(answer, dict) or answer.get('type') != 'choice'
            or not isinstance(answer.get('choice'), str) or answer['choice'] not in criteria):
        raise ValueError('Invalid native joint choice')
    probabilities = answer.get('probabilities')
    if (not isinstance(probabilities, dict) or set(probabilities) != set(criteria)
            or len(probabilities) != 12
            or any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p)
                   or not 0 <= p <= 1 for p in probabilities.values())
            or abs(sum(probabilities.values()) - 1) >= .03):
        raise ValueError('A complete finite native12-way probability distribution is required')
    return dict(native_choice=answer['choice'], probabilities=deepcopy(probabilities))


def choose(raw, body, temperature, rng, *, model):
    """One draw per committed action; never seed here or alter the requested hold."""
    parsed = parse(raw, body, model)
    if isinstance(temperature, bool) or temperature not in TEMPERATURES:
        raise ValueError('Temperature must be one of the globally preregistered .05 or .2 candidates')
    before = rng.getstate()
    selected, draw, weights = sample_choice(parsed['probabilities'], rng, temperature)
    after = rng.getstate()
    response = deepcopy(raw)
    response['answers']['action']['choice'] = selected
    buttons = image_v1.decode_profile_response(BUILDER_PROFILE_ID, response)
    return dict(buttons=buttons, choice=selected, requested_frames=FRAMES_PER_ACTION,
                sampling=dict(native_api_choice=parsed['native_choice'], sampled_choice=selected,
                              temperature=temperature, random_uniform=draw,
                              raw_probabilities=parsed['probabilities'], tempered_probabilities=weights,
                              rng_state_before=json.loads(json.dumps(before)),
                              rng_state_after=json.loads(json.dumps(after))))
