"""Validated execution of selected frozen development controllers.

Image builders receive only real pixels, a clock and declared prior controls.
The evaluator's RAM observations never enter their request interface.
"""
from __future__ import annotations

from copy import deepcopy
import math
import random

from benchmark.profiles import load_profile, state_text
from benchmark.profiles import image_v1, memoryfinish_v1
from benchmark.profiles.probability_sampler_v1 import sample_choice
from prototype.control import ACTIONS as STATE_ACTIONS
from prototype.decisions import PolicyError

PROFILE_IDS = ('pplx-state-clear', 'mammoth-pixels-first-clear',
               'pplx-pixels-sampled-clear-t005-seed0', 'mercury-pixels-planner-sampled-clear-t02-seed0')
NEUTRAL = dict(horizontal='released', vertical='released', jump='released', run='released')


def validate_response(response, body, *, require_action=True):
    """Require the complete requested native distributions before any action/draw."""
    if not isinstance(response, dict) or response.get('error'):
        raise PolicyError('Expected a native decision response')
    answers = response.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(body['questions']):
        raise PolicyError('Response question keys differ from the requested contract')
    for name, question in body['questions'].items():
        answer = answers[name]
        criteria = question['criteria']
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise PolicyError('Invalid native choice answer')
        probabilities = answer.get('probabilities')
        if (not isinstance(probabilities, dict) or set(probabilities) != set(criteria)
                or not isinstance(answer.get('choice'), str) or answer['choice'] not in criteria):
            raise PolicyError('Native choice or complete probability keys differ from the contract')
        if any(isinstance(p, bool) or not isinstance(p, (int, float))
               or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
            raise PolicyError('Invalid native probabilities')
        if abs(sum(probabilities.values()) - 1) >= .03:
            raise PolicyError('Native probabilities do not sum to one')
    if require_action and ('action' not in body['questions'] or len(body['questions']['action']['criteria']) != 12):
        raise PolicyError('Frozen controllers require all 12 native action choices')


class ProfileSession:
    """One episode's controller memory and reproducible sampler, with no emulator."""
    def __init__(self, profile_id):
        if profile_id not in PROFILE_IDS:
            raise ValueError('Unsupported runnable frozen profile')
        self.profile = load_profile(profile_id)
        self.id = profile_id
        self.images, self.controls, self.plans = [], [], []
        self.current_plan = None
        self.stages = ('plan', 'motor') if profile_id == 'mercury-pixels-planner-sampled-clear-t02-seed0' else ('decision',)
        self.multistage = len(self.stages) > 1
        self.buttons = dict(NEUTRAL)
        self.rng = random.Random(0)
        self.cadence = self.profile.get('cadence') or self.profile['initial_cadence_frames']
        self.min_hold = 2 if profile_id == 'mammoth-pixels-first-clear' or self.multistage else self.cadence
        self.mode = self.profile['mode']
        self.sampler = self.profile.get('probability_sampler')
        if self.multistage:
            self.model = dict(id='inception/mercury-decide', request_model=self.profile['settings']['model'],
                              expected_returned_model=self.profile['settings']['model'],
                              provider=dict(only=['inception'], allow_fallbacks=False),
                              expected_returned_provider_names=[self.profile['settings']['provider']])
        elif profile_id == 'mammoth-pixels-first-clear':
            self.model = deepcopy(self.profile['settings']['model'])
        else:
            self.model = dict(id='perplexity/pplx-decider-v1.2',
                              request_model='perplexity/pplx-decider-v1.2-20261016',
                              expected_returned_model='perplexity/pplx-decider-v1.2-20261016',
                              provider=dict(only=['perplexity'], allow_fallbacks=False),
                              expected_returned_provider_names=['Perplexity'])

    def state_request(self, state):
        if self.mode != 'state':
            raise ValueError('Pixels-only profiles cannot accept a RAM observation')
        return dict(model=self.model['request_model'], provider=deepcopy(self.model['provider']),
                    state=state_text(self.profile, state), questions=deepcopy(self.profile['contract']['questions']))

    def image_request(self, image, frame, decision, *, stage=None):
        if self.mode != 'image':
            raise ValueError('State profile requires its declared observation')
        if self.multistage:
            from benchmark.profiles import mercury_plan_v1 as policy
            return policy.policy_body(self.model, self.images[-2:] + [image], self.controls[-6000:],
                                      self.plans[-2:], 12, stage or 'plan',
                                      self.current_plan if stage == 'motor' else None)
        if self.id == 'mammoth-pixels-first-clear':
            return memoryfinish_v1.build_request(self.model['request_model'], self.model['provider'],
                                                self.images[-1:] + [(decision, image)], self.controls)
        return image_v1.profile_request(self.profile['base_builder_profile'], image_png=image,
                                       frame=frame, decision_index=decision, buttons=self.buttons,
                                       previous_controls=self.controls, previous_images=self.images[-1:])

    def parse(self, response, body, header_id=None):
        """Transport validation preserves the provider choice; it never draws RNG."""
        planning = self.multistage and 'action' not in body['questions']
        validate_response(response, body, require_action=not planning)
        if (response.get('model') != self.model['expected_returned_model']
                or response.get('provider') not in self.model['expected_returned_provider_names']):
            raise PolicyError('Returned model/provider differs from pinned expected identity')
        usage = response.get('usage', {})
        if not isinstance(usage, dict):
            raise PolicyError('Invalid usage telemetry')
        decoded = (dict(plan={key: dict(choice=answer['choice'], probabilities=answer['probabilities'])
                              for key, answer in response['answers'].items()}) if planning else self._decode(response))
        return dict(**decoded, model=response['model'], provider=response['provider'],
                    probabilities={key: answer['probabilities'] for key, answer in response['answers'].items()},
                    native_choice=(response['answers']['action']['choice'] if not planning else None), usage=usage,
                    request_id=response.get('id') or header_id)

    def accept_stage(self, stage, response, body):
        if self.multistage and stage == 'plan':
            self.current_plan = self.parse(response, body)['plan']

    def screenshot(self, rgb):
        if self.multistage:
            from benchmark.profiles.mercury_plan_v1 import screen_png
            return screen_png(rgb)
        from io import BytesIO
        from PIL import Image
        stream = BytesIO()
        Image.fromarray(rgb).resize((512, 480), Image.Resampling.NEAREST).save(stream, format='PNG')
        return stream.getvalue()

    def _decode(self, response):
        if self.multistage:
            from benchmark.profiles import mercury_plan_v1 as policy
            if self.current_plan is None:
                raise PolicyError('Motor response requires a committed native plan')
            duration = policy.DURATIONS[self.current_plan['duration']['choice']] if 'duration' in self.current_plan else 12
            return dict(buttons=dict(policy.ACTIONS[response['answers']['action']['choice']]), native_frames=duration)
        if self.id == 'pplx-state-clear':
            return dict(buttons=dict(STATE_ACTIONS[response['answers']['action']['choice']]),
                        native_frames=self.cadence)
        if self.id == 'mammoth-pixels-first-clear':
            return memoryfinish_v1.decode_response(response, self.controls)
        return dict(buttons=image_v1.decode_profile_response(self.profile['base_builder_profile'], response),
                    native_frames=self.cadence)

    def choose(self, response, body):
        """Called exactly once per committed action, including deterministic replay."""
        parsed = self.parse(response, body)
        sampling = None
        if self.multistage:
            from benchmark.profiles import mercury_plan_v1 as policy
            action, buttons, sampling = policy.sample_motor(response['answers'], self.rng)
            from benchmark.client import canonical
            import json
            sampling = json.loads(canonical(sampling))
            self.last_action_label = action
            parsed['buttons'] = buttons
        elif self.sampler:
            choice, draw, weights = sample_choice(parsed['probabilities']['action'], self.rng,
                                                  self.sampler['temperature'])
            changed = deepcopy(response)
            changed['answers']['action']['choice'] = choice
            parsed.update(self._decode(changed))
            sampling = dict(native_choice=response['answers']['action']['choice'], sampled_choice=choice,
                            random_uniform=draw, tempered_probabilities=weights)
        return dict(buttons=parsed['buttons'], requested_frames=parsed['native_frames'], sampling=sampling)

    def advance(self, *, image, frame, decision, buttons, actual_frames):
        """Remember only executed declared controls, with their actual native hold."""
        if self.multistage:
            self.images = (self.images + [image])[-2:]
            self.controls = (self.controls + [dict(action=self.last_action_label, buttons=dict(buttons), native_frames=actual_frames)])[-6000:]
            self.plans = (self.plans + [deepcopy(self.current_plan)])[-2:]
            self.buttons = dict(buttons)
            return
        if self.mode == 'image':
            stamp = decision if self.id == 'mammoth-pixels-first-clear' else frame
            self.images = [(stamp, image)]
        if self.id == 'mammoth-pixels-first-clear':
            self.controls.append(dict(decision=decision, buttons=dict(buttons), held_native_frames=actual_frames))
        else:
            self.controls.append(dict(frame=frame, buttons=dict(buttons), frames=actual_frames))
        self.buttons = dict(buttons)


def fixture_response(model, body, index):
    """Offline transport fixture; never a policy score or provider request."""
    answers = {}
    for name, question in body['questions'].items():
        keys = list(question['criteria'])
        preferred = 'right_run_release' if 'right_run_release' in keys else 'right_B_held_A_released'
        choice = preferred if name == 'action' else ('precision_2' if 'precision_2' in keys else keys[0])
        # Slightly nontrivial probabilities exercise the full sampler contract.
        weights = {key: (0.8 if key == choice else 0.2 / (len(keys) - 1)) for key in keys}
        answers[name] = dict(type='choice', choice=choice, probabilities=weights)
    return dict(model=model['expected_returned_model'], provider=model['expected_returned_provider_names'][0],
                id=f'offline-{index}', answers=answers, usage={})
