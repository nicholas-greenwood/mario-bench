"""Pixels-only model input. No emulator or RAM observation is accepted here."""
from __future__ import annotations

import base64
import io
import json
import re
from collections.abc import Mapping, Sequence

from PIL import Image


_BUTTON_CHOICES = {
    'horizontal': {'left', 'released', 'right'},
    'vertical': {'up', 'released', 'down'},
    'jump': {'held', 'released'},
    'run': {'held', 'released'},
}


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return value


def _buttons(value: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(_BUTTON_CHOICES):
        raise ValueError('Image input requires exactly four declared button states')
    if any(value[name] not in choices for name, choices in _BUTTON_CHOICES.items()):
        raise ValueError('Invalid image-input button value')
    return {name: value[name] for name in _BUTTON_CHOICES}


def _screen_png(data: bytes) -> bytes:
    if not isinstance(data, bytes) or not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Screenshot must be lossless PNG bytes')
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        image = source.convert('RGB')
    if image.size == (256, 240):
        image = image.resize((512, 480), Image.Resampling.NEAREST)
    elif image.size == (512, 480):
        enlarged = image.resize((256, 240), Image.Resampling.NEAREST).resize((512, 480), Image.Resampling.NEAREST)
        if image.tobytes() != enlarged.tobytes():
            raise ValueError('512x480 screenshot must be native pixels enlarged 2x by nearest neighbour')
    else:
        raise ValueError('Screenshot must be native 256x240 or its exact 512x480 nearest-neighbour enlargement')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def image_parts(
    image_png: bytes,
    frame: int,
    interval: int,
    buttons: Mapping[str, str],
    history: Sequence[Mapping] | None = None,
    *,
    previous_images: Sequence[tuple[int, bytes]] = (),
    level: str = '1-1',
) -> list:
    """Build native Decisions state using pixels and declared controls only.

    ``history`` contains model-chosen action records with exactly ``frame``,
    ``frames`` and ``buttons``. Never pass the emulator's position history.
    Screenshots are chronological, with at most two previous screens. Frame
    numbers are the emulator's native-frame clock, not a sensor reading.
    """
    from prototype.control import RULES

    if not isinstance(level, str) or re.fullmatch(r'[1-8]-[1-4]', level) is None:
        raise ValueError('Declared level must be a Super Mario Bros. world-stage identifier')
    rules = RULES if level == '1-1' else RULES.replace('World 1-1', f'World {level}', 1)
    frame = _integer(frame, 'frame')
    interval = _integer(interval, 'interval', 1)
    current_buttons = _buttons(buttons)
    actions = []
    for record in history or ():
        if not isinstance(record, Mapping) or set(record) != {'frame', 'frames', 'buttons'}:
            raise ValueError('Image action history permits only frame, frames and buttons; RAM history is forbidden')
        action_frame = _integer(record['frame'], 'previous action frame')
        duration = _integer(record['frames'], 'previous action frames', 1)
        if action_frame + duration > frame:
            raise ValueError('Previous actions must already have finished')
        if actions and action_frame < actions[-1]['frame'] + actions[-1]['frames']:
            raise ValueError('Previous action records must be chronological and non-overlapping')
        actions.append({'frame': action_frame, 'frames': duration, 'buttons': _buttons(record['buttons'])})
    if len(actions) > 12:
        raise ValueError('At most twelve previous model actions are allowed')
    if len(previous_images) > 2:
        raise ValueError('At most two previous screenshots are allowed')
    screens = []
    for prior_frame, prior_png in previous_images:
        prior_frame = _integer(prior_frame, 'previous screenshot frame')
        if prior_frame >= frame or (screens and prior_frame <= screens[-1][0]):
            raise ValueError('Previous screenshots must be chronological and older than the current screenshot')
        screens.append((prior_frame, _screen_png(prior_png)))
    screens.append((frame, _screen_png(image_png)))
    metadata = {
        'game': f'Super Mario Bros., world {level}',
        'rules_and_button_semantics': rules,
        'observation_interface': 'image_only',
        'native_frame': frame,
        'control_interval_frames': interval,
        'currently_held_buttons': current_buttons,
        'previous_model_controls': actions,
        'screenshot_format': 'Native 256x240 game screens enlarged to 512x480 with nearest-neighbour interpolation. Chronological oldest first, CURRENT last. Infer all game geometry and motion from these pixels.',
    }
    parts = [json.dumps(metadata, separators=(',', ':'), allow_nan=False)]
    for index, (screen_frame, screen_png) in enumerate(screens):
        label = 'CURRENT paused screenshot' if index == len(screens) - 1 else 'PAST screenshot for motion context'
        parts.extend([
            f'{label}, native frame {screen_frame}.',
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(screen_png).decode('ascii')}},
        ])
    return parts
