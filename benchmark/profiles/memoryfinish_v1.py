"""Frozen first strict pixels-only clear profile, memoryfinish240-v1.

Pure controller/image functions. A generic completion rule is revealed only by
prior model input history, never RAM, progress, position or a flag-status sensor.
All buttons and post-event2/4/6/8-frame durations remain native model decisions.
"""
import json
from benchmark.profiles.memoryduration_v1 import build_request as _timed_request, decode_response, long_input_occurred
from benchmark.profiles.edgezoom_v1 import _canonical
PROFILE_VERSION = "memoryfinish240-v1"
CADENCE_FRAMES_BEFORE_DURATION_EVENT = 6
HISTORY_IMAGES = 2
DURATION_EVENT_NATIVE_FRAMES = 120
FINISH_RULE_EVENT_NATIVE_FRAMES = 240
FROZEN_RUNNER_SHA256 = '064a2439a117f96b9a6b6f51975e0ce2c8a123a2f120eade99eab552644e1234'
FINISH_RULE = ' General level-completion rule: finish by touching the flagpole above its solid base. The base obeys the same solid-side collision mechanics as other blocks: the feet must rise above its top before the body can cross its side. Choose any necessary jump yourself from the screenshots and declared controls.'

def build_request(model, provider, images, previous_controls=()):
    body = _timed_request(model, provider, images, previous_controls)
    if long_input_occurred(previous_controls, FINISH_RULE_EVENT_NATIVE_FRAMES):
        metadata = json.loads(body["state"][0])
        metadata["instructions"] += FINISH_RULE
        body["state"][0] = _canonical(metadata)
    return body
