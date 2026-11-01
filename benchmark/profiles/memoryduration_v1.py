"""Frozen memoryduration120-v1 pixels-only profile: a near-clear, not a clear.

Only own prior input choices activate the model's native duration question.
The native model then chooses both complete buttons and2/4/6/8-frame holds.
No contact, movement, blockage, terrain or other game-state sensor is accepted.
"""
import copy
import json
from benchmark.profiles.memorygate_v1 import build_request as _memory_request
from benchmark.profiles.edgezoom_v1 import decode_response as _buttons, _choice, _canonical, _controls
PROFILE_VERSION = "memoryduration120-v1"
CADENCE_FRAMES = 6
HISTORY_IMAGES = 2
THRESHOLD_NATIVE_FRAMES = 120
DURATIONS = {"precision_2":2, "precision_4":4, "routine_6":6, "sustain_8":8}
FROZEN_RUNNER_SHA256 = '8114ae821b126b00d5fa0de7d95f3e559d0a38b36d3d6fd30c47bc52d5843929'
DURATION_QUESTION = {'criteria': {'precision_2': 'Hold selected buttons2nativeframes, then inspect again. Finest timing for contact, landing or a new A press.', 'precision_4': 'Hold selected buttons4nativeframes, then inspect again. Precise timing near a solid side, enemy or edge.', 'routine_6': 'Hold selected buttons6nativeframes, then inspect again. Routine progress when there is room.', 'sustain_8': 'Hold selected buttons8nativeframes, then inspect again. Sustain an appropriate trajectory when there is enough safe travel.'}, 'instructions': 'Choose how many native frames to hold YOUR chosen complete controller state before observing again. Duration is your decision with no contact-triggered stopping or automatic correction. Consider precision near a landing, solid side, enemy or fresh A edge.', 'type': 'choice'}
ACTIVE_INTERVAL_TEXT = 'You choose exactly2,4,6or8nativeframes using the duration question. No automatic contact-based stopping.'

def long_input_occurred(controls, threshold=120):
    # Endogenous input history only. This says nothing about game movement.
    previous=None;frames=0
    for record in controls:
        frames=frames+record['held_native_frames'] if record['buttons']==previous else record['held_native_frames']
        previous=record['buttons']
        if frames>=threshold:return True
    return False


def build_request(model, provider, images, previous_controls=()):
    controls = [_controls([record])[0] for record in previous_controls]
    body = _memory_request(model, provider, images, controls)
    if long_input_occurred(controls, THRESHOLD_NATIVE_FRAMES):
        body["questions"] = copy.deepcopy(body["questions"])
        body["questions"]["duration"] = DURATION_QUESTION
        metadata = json.loads(body["state"][0])
        metadata["next_control_interval_native_frames"] = ACTIVE_INTERVAL_TEXT
        body["state"][0] = _canonical(metadata)
    return body


def decode_response(response, previous_controls=()):
    controls = [_controls([record])[0] for record in previous_controls]
    buttons = _buttons(response)
    duration = None
    if long_input_occurred(controls, THRESHOLD_NATIVE_FRAMES):
        duration = _choice(response, "duration", DURATIONS)
    elif "duration" in response.get("answers", {}):
        raise ValueError("Unrequested duration choice")
    return dict(buttons=buttons, native_frames=DURATIONS[duration] if duration is not None else CADENCE_FRAMES, duration_choice=duration)
