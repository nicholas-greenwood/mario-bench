"""Frozen pixels-only edgezoom-v1 development profile.

Pure request/controller functions: no environment, network, emulator or RAM access.
Images arrive oldest first; the provider receives CURRENT full pixels, two fixed
CURRENT crops, then PAST full pixels. Actual emulator provenance is audited by
an independent replay, outside this module.
"""
from __future__ import annotations
import base64
import io
import json
import math
from PIL import Image

PROFILE_VERSION = "edgezoom-v1"
CADENCE_FRAMES = 6
HISTORY_IMAGES = 2
FROZEN_RUNNER_SHA256 = "97ed785eb83191455a4c1576af69a31a68a7b28e177a003b118fba0ec5756334"
RULES = 'You control Mario in Super Mario Bros. World1-1. Reach the flag alive. Choose all simultaneous held buttons using only the screenshot and declared previous controls. Right moves forward; B runs faster and extends jumps. Grounded plus a new A press starts a jump. Holding A throughout ascent makes a higher, longer jump. Releasing A early during ascent makes a low, short hop. Pressing A while airborne does not start another jump on later landing. Release A during descent so it is ready for the next grounded takeoff. Holding A through landing does not automatically jump again. Enemy side contact kills small Mario; descending onto enemies stomps them. Jump early enough to rise before enemy side contact. Gaps require takeoff near the visible edge so the jump lasts until the far side. Pipes and stairs support Mario: feet must rise above their top before the body crosses the side. A ceiling stops ascent. Momentum persists when controls are released. Avoid unnecessary hopping on open flat ground; it can waste the next jump near a hazard. Background hills are decorative. Game pauses while deciding. All choices are yours.'
IMAGE_RULES = ' CURRENT full screenshot is FIRST. Any PAST screenshot is labelled and appears last. Mario is the red/brown person; brown mushroom-shaped enemies are different characters. A near landing is still airborne: feet must actually touch a solid surface before a NEW jump can begin. Infer contact and ascent/descent from the pixels, including the labelled past image. A_held means continue the exact same A press if already held, not a new jump.'
QUESTIONS = {'action': {'criteria': {'left_B_held_A_held': "Hold {'horizontal': 'left', 'vertical': 'released', 'jump': 'held', 'run': 'held'} simultaneously for the next interval.", 'left_B_held_A_released': "Hold {'horizontal': 'left', 'vertical': 'released', 'jump': 'released', 'run': 'held'} simultaneously for the next interval.", 'left_B_released_A_held': "Hold {'horizontal': 'left', 'vertical': 'released', 'jump': 'held', 'run': 'released'} simultaneously for the next interval.", 'left_B_released_A_released': "Hold {'horizontal': 'left', 'vertical': 'released', 'jump': 'released', 'run': 'released'} simultaneously for the next interval.", 'released_B_held_A_held': "Hold {'horizontal': 'released', 'vertical': 'released', 'jump': 'held', 'run': 'held'} simultaneously for the next interval.", 'released_B_held_A_released': "Hold {'horizontal': 'released', 'vertical': 'released', 'jump': 'released', 'run': 'held'} simultaneously for the next interval.", 'released_B_released_A_held': "Hold {'horizontal': 'released', 'vertical': 'released', 'jump': 'held', 'run': 'released'} simultaneously for the next interval.", 'released_B_released_A_released': "Hold {'horizontal': 'released', 'vertical': 'released', 'jump': 'released', 'run': 'released'} simultaneously for the next interval.", 'right_B_held_A_held': "Hold {'horizontal': 'right', 'vertical': 'released', 'jump': 'held', 'run': 'held'} simultaneously for the next interval.", 'right_B_held_A_released': "Hold {'horizontal': 'right', 'vertical': 'released', 'jump': 'released', 'run': 'held'} simultaneously for the next interval.", 'right_B_released_A_held': "Hold {'horizontal': 'right', 'vertical': 'released', 'jump': 'held', 'run': 'released'} simultaneously for the next interval.", 'right_B_released_A_released': "Hold {'horizontal': 'right', 'vertical': 'released', 'jump': 'released', 'run': 'released'} simultaneously for the next interval."}, 'instructions': 'Choose ONE coherent simultaneous controller state for the whole interval. Use the screenshots to anticipate collisions and landings, sustain jumps long enough to clear hazards and release A between separate jumps. All choices release vertical buttons.', 'type': 'choice'}}

ACTIONS = {}
for name in QUESTIONS["action"]["criteria"]:
    direction, remaining = name.split("_B_")
    run, jump = remaining.split("_A_")
    ACTIONS[name] = dict(horizontal=direction, vertical="released", run=run, jump=jump)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _buttons(value):
    choices = {"horizontal": {"left", "released", "right"}, "vertical": {"up", "released", "down"}, "jump": {"held", "released"}, "run": {"held", "released"}}
    if not isinstance(value, dict) or set(value) != set(choices):
        raise ValueError("Exactly four declared button states are required")
    if any(value[name] not in options for name, options in choices.items()):
        raise ValueError("Invalid declared button state")
    return dict(value)


def _png(data):
    if not isinstance(data, bytes) or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("A lossless PNG screenshot is required")
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.mode != "RGB":
            raise ValueError("Screenshots must contain native RGB pixels")
        if image.size == (256, 240):
            enlarged = image.resize((512, 480), Image.Resampling.NEAREST)
            stream = io.BytesIO(); enlarged.save(stream, format="PNG")
            return stream.getvalue()
        if image.size != (512, 480):
            raise ValueError("Screenshot must be native256x240 or nearest2x512x480")
        if image.tobytes() != image.resize((256, 240), Image.Resampling.NEAREST).resize((512, 480), Image.Resampling.NEAREST).tobytes():
            raise ValueError("512x480 screenshot must be exact nearest-neighbour2x")
    return data


def _controls(previous_controls):
    if len(previous_controls) > 2:
        raise ValueError("This frozen profile permits two previous controls")
    result = []
    for record in previous_controls:
        if set(record) != {"decision", "buttons", "held_native_frames"}:
            raise ValueError("Only declared model controls and durations are permitted")
        if not isinstance(record["decision"], int) or isinstance(record["decision"], bool) or record["decision"] < 0:
            raise ValueError("Invalid decision index")
        if not isinstance(record["held_native_frames"], int) or isinstance(record["held_native_frames"], bool) or record["held_native_frames"] < 1:
            raise ValueError("Invalid control duration")
        result.append(dict(decision=record["decision"], buttons=_buttons(record["buttons"]), held_native_frames=record["held_native_frames"]))
    return result


def _image_part(data):
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(data).decode()}}


def build_state(images, previous_controls=(), frames=CADENCE_FRAMES):
    """Accept only (decision_index, PNG) pairs and declared prior controls."""
    if frames != CADENCE_FRAMES:
        raise ValueError("edgezoom-v1 is frozen at six native frames")
    if not 1 <= len(images) <= HISTORY_IMAGES:
        raise ValueError("Provide current screenshot and at most one older screenshot")
    screens = []
    for decision, data in images:
        if not isinstance(decision, int) or isinstance(decision, bool) or decision < 0 or screens and decision <= screens[-1][0]:
            raise ValueError("Screenshot decision indices must be chronological")
        screens.append((decision, _png(data)))
    controls = _controls(previous_controls)
    rules = RULES
    if controls:
        current = controls[-1]["buttons"]
        rules += " Current declared buttons: horizontal=" + current["horizontal"] + ", B=" + current["run"] + ", A=" + current["jump"] + ". "
        rules += ("A is currently held: a NEW jump later requires releasing A before pressing it again on a solid surface." if current["jump"] == "held" else "A is currently released: a NEW press starts a jump only if Mario is visibly standing on a solid surface.")
    rules += IMAGE_RULES
    metadata = {"game": "Super Mario Bros 1-1", "instructions": rules, "next_control_interval_native_frames": frames, "previous_controls": controls}
    index, current_png = screens[-1]
    parts = [_canonical(metadata), "CURRENT paused screenshot; use this for your next action. Screenshot taken before decision " + str(index), _image_part(current_png)]
    with Image.open(io.BytesIO(current_png)) as full:
        for left, right, label in [(0, 192, "left"), (192, 384, "middle")]:
            crop = full.crop((left, 160, right, 448)).resize((384, 576), Image.Resampling.NEAREST)
            stream = io.BytesIO(); crop.save(stream, format="PNG")
            parts += ["CURRENT paused screenshot fixed " + label + " zoom, exact pixels from this same screen enlarged4x. Screenshot taken before decision " + str(index), _image_part(stream.getvalue())]
    for prior_index, prior_png in screens[:-1]:
        parts += ["PAST screenshot for motion context. Screenshot taken before decision " + str(prior_index), _image_part(prior_png)]
    return parts


def build_request(model, provider, images, previous_controls=()):
    return dict(model=model, provider=provider, state=build_state(images, previous_controls), questions=QUESTIONS)


def _choice(response, question, criteria):
    answer = response.get("answers", {}).get(question, {})
    probabilities = answer.get("probabilities", {})
    if answer.get("type") != "choice" or answer.get("choice") not in criteria or set(probabilities) != set(criteria):
        raise ValueError("Invalid native decision")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values()) or not math.isclose(sum(probabilities.values()), 1, abs_tol=.03):
        raise ValueError("Invalid native decision probabilities")
    return answer["choice"]


def decode_response(response):
    return dict(ACTIONS[_choice(response, "action", ACTIONS)])
