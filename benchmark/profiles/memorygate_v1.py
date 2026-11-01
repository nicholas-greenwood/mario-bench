"""Frozen memorygate120-v1 pixels-only controller profile.

A context-budget trigger uses only the model's own prior buttons and native-frame
holds. It neither estimates movement/contact nor selects or changes any action.
No network, environment, emulator, RAM, coordinates or filesystem access.
"""
import json
from benchmark.profiles.edgezoom_v1 import build_request as _base_request, decode_response, _controls, _canonical
PROFILE_VERSION = "memorygate120-v1"
CADENCE_FRAMES = 6
HISTORY_IMAGES = 2
THRESHOLD_NATIVE_FRAMES = 120
FROZEN_RUNNER_SHA256 = '6fd5b1dbe51bafd18dea7e677eceafd6d513d170cdde23cd61deaa05003b4f9b'
RUNUP_RULES = ' General running-jump mechanics: jump height and travel depend on actual horizontal speed at takeoff, not merely holding B. Holding right+B while pressed against a wall does not build running speed. If standing jumps cannot clear a tall obstacle, first back away to create run-up space, then run toward it and take off before hitting its side. Repeated stationary jumps can remain too low even with A held throughout ascent. You must judge the current situation from the screenshots; this text reports no current state or route. Begin an enemy jump early enough that your feet rise above its head before your body crosses its side: pressing A is not instant collision immunity.'
MEMORY_REMINDER = ' The input-memory counters report only your previously chosen buttons and native-frame durations, not movement/contact/blockage. Repetition alone does not mean Mario is blocked. Compare the actual screenshots: if a visible obstacle remains in front despite repeated right inputs, a different input may be needed. A standing jump can clear low obstacles without a run-up. Every next input remains your choice.'

def control_memory(controls):
    # Only declared input choices/durations enter this summary, never game state.
    result={'same_complete_input_native_frames':0,'same_complete_input_records':0,'same_A_state_native_frames':0,'same_horizontal_state_native_frames':0,'same_B_state_native_frames':0}
    if not controls:return result
    current=controls[-1]['buttons'];result['last_chosen_buttons']=dict(current)
    for record in reversed(controls):
        if record['buttons']!=current:break
        result['same_complete_input_native_frames']+=record['held_native_frames'];result['same_complete_input_records']+=1
    for field,key in [('jump','same_A_state_native_frames'),('horizontal','same_horizontal_state_native_frames'),('run','same_B_state_native_frames')]:
        for record in reversed(controls):
            if record['buttons'][field]!=current[field]:break
            result[key]+=record['held_native_frames']
    return result


def build_request(model, provider, images, previous_controls=()):
    controls = [_controls([record])[0] for record in previous_controls]
    body = _base_request(model, provider, images, controls[-2:])
    metadata = json.loads(body["state"][0])
    metadata["instructions"] += RUNUP_RULES
    memory = control_memory(controls)
    if memory["same_complete_input_native_frames"] >= THRESHOLD_NATIVE_FRAMES:
        metadata["model_chosen_input_memory"] = memory
        metadata["instructions"] += MEMORY_REMINDER
    body["state"][0] = _canonical(metadata)
    return body
