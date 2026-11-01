"""Headless SMB1 controller and factual, current-frame RAM observations.

The caller owns pacing and synchronisation. No background work occurs here.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
import math

import numpy as np
from gym_super_mario_bros import SuperMarioBrosEnv


class _FrameEnvironment(SuperMarioBrosEnv):
    def _did_step(self, done):
        # The stock wrapper skips busy states and edits timers during play.
        # Keep its boot-to-level/reset support, but advance exactly one frame
        # for each subsequent step, including pipes and animations.
        pass


_NEUTRAL = dict(horizontal="released", vertical="released", jump="released", run="released")
_OPTIONS = {
    "horizontal": {"left", "released", "right"},
    "vertical": {"up", "released", "down"},
    "jump": {"held", "released"},
    "run": {"held", "released"},
}
_OBJECT_NAMES = {
    0x00: "green_koopa", 0x01: "red_koopa", 0x02: "buzzy_beetle",
    0x03: "red_koopa", 0x04: "green_koopa", 0x05: "hammer_bro",
    0x06: "goomba", 0x0C: "podoboo", 0x0D: "piranha_plant",
    0x2D: "bowser", 0x30: "powerup", 0x31: "flagpole",
}


def _signed(value: int) -> int:
    return value - 256 if value >= 128 else value


class MarioGame:
    """A single playable World 1 level, with explicit button holds."""

    def __init__(self, level="1-1"):
        if level not in {"1-1", "1-2", "1-3", "1-4"}:
            raise ValueError(f"Unsupported level: {level}")
        self.level = level
        # None creates neither a viewer nor an audio output device.
        self.env = _FrameEnvironment(target=tuple(map(int, level.split("-"))), render_mode=None)
        self._closed = False
        self.reset()

    def reset(self) -> None:
        self.env.reset(seed=0)
        self.frame = 0
        self.buttons = dict(_NEUTRAL)
        self.done = False
        self.death = False
        self.flag_get = False
        self._history = deque(maxlen=12)
        self._previous_objects = {}
        self._object_velocity = {}
        self._vx = None
        self._vy = None
        self._last_xy = self._position()
        self._max_x = self._last_xy[0]
        self._record_history()

    def _position(self):
        r = self.env.ram
        return int(r[0x6D]) * 256 + int(r[0x86]), int(r[0xB5]) * 256 + int(r[0xCE]) - 256

    def _record_history(self):
        x, y = self._position()
        self._history.append(dict(frame=self.frame, x=x, y=y, buttons=dict(self.buttons)))

    def step(self, buttons: dict[str, str]) -> dict:
        if self._closed:
            raise RuntimeError("MarioGame is closed")
        if self.done:
            return self.observe()
        unknown = set(buttons) - set(_OPTIONS)
        if unknown:
            raise ValueError(f"Unknown button fields: {sorted(unknown)}")
        # A complete control state is accepted; omitted fields are released.
        current = {key: buttons.get(key, "released") for key in _OPTIONS}
        for key, value in current.items():
            if value not in _OPTIONS[key]:
                raise ValueError(f"Invalid {key}: {value!r}")
        changed = current != self.buttons
        self.buttons = current
        mask = {"left": 64, "right": 128}.get(current["horizontal"], 0)
        mask |= {"up": 16, "down": 32}.get(current["vertical"], 0)
        mask |= 1 if current["jump"] == "held" else 0
        mask |= 2 if current["run"] == "held" else 0
        _, _, terminated, truncated, info = self.env.step(mask)
        self.frame += 1
        self.done = bool(terminated or truncated)
        self.death = bool(info.get("death", False))
        self.flag_get = bool(info.get("flag_get", False))
        x, y = self._position()
        self._vx, self._vy = x - self._last_xy[0], y - self._last_xy[1]
        self._last_xy = x, y
        self._max_x = max(self._max_x, x)
        objects = self._objects()
        self._object_velocity = {}
        now = {}
        for obj in objects:
            identity = obj["slot"], obj["kind_id"]
            previous = self._previous_objects.get(identity)
            if previous is not None and abs(obj["x"] - previous[0]) <= 16:
                self._object_velocity[identity] = (obj["x"] - previous[0], obj["y"] - previous[1])
            now[identity] = obj["x"], obj["y"]
        self._previous_objects = now
        if changed or self.frame % 30 == 0 or self.done:
            self._record_history()
        return self.observe()

    def _objects(self):
        r = self.env.ram
        camera = int(r[0x71A]) * 256 + int(r[0x71C])
        px, py = self._position()
        objects = []
        for slot in range(5):
            active = int(r[0x0F + slot])
            if active == 0 or active & 0x80:
                continue
            x = int(r[0x6E + slot]) * 256 + int(r[0x87 + slot])
            y = int(r[0xB6 + slot]) * 256 + int(r[0xCF + slot]) - 256
            if not (camera - 16 <= x < camera + 256 and -32 <= y < 240):
                continue
            kind = int(r[0x16 + slot])
            objects.append(dict(slot=slot, kind_id=kind,
                                kind=_OBJECT_NAMES.get(kind, f"object_0x{kind:02x}"),
                                x=x, y=y, dx=x-px, dy=y-py,
                                state_raw=int(r[0x1E + slot])))
        return objects

    def observe(self) -> dict:
        r = self.env.ram
        x, y = self._position()
        camera = int(r[0x71A]) * 256 + int(r[0x71C])
        # Read only fully visible columns: alternating buffers contain stale
        # data beyond the viewport, which must not become model foresight.
        first = math.ceil(camera / 16)
        last = (camera + 256) // 16 - 1
        columns = []
        for column in range(first, last + 1):
            base = 0x500 + ((column // 16) % 2) * 208
            columns.append(dict(x=column*16, dx=column*16-x,
                                tiles=[int(r[base + row*16 + column % 16]) for row in range(13)]))
        objects = self._objects()
        for obj in objects:
            velocity = self._object_velocity.get((obj["slot"], obj["kind_id"]))
            obj["vx_px_per_frame"] = velocity[0] if velocity is not None else None
            obj["vy_px_per_frame"] = velocity[1] if velocity is not None else None
            obj["relative_vx_px_per_frame"] = velocity[0] - self._vx if velocity is not None and self._vx is not None else None
        status = int(r[0x756])
        digits = lambda start, length: sum(int(r[start+i]) * 10**(length-i-1) for i in range(length))
        return dict(
            game="super_mario_bros", level=self.level, frame=self.frame, fps=60,
            done=self.done, death=self.death, flag_get=self.flag_get,
            world=int(r[0x75F])+1, stage=int(r[0x75C])+1,
            lives=max(0, int(r[0x75A])+1) if int(r[0x75A]) != 255 else 0,
            time_remaining=digits(0x7F8, 3), coins=digits(0x7ED, 2), score=digits(0x7DE, 6),
            progress_max_x=self._max_x, camera_x=camera,
            coordinates="Pixels: x right, y down. Object origin is y; Mario feet approximately y+32; width 16. Body top y+16 when small, y when tall/fire.",
            player=dict(x=x, y=y, screen_x=x-camera,
                        vx_px_per_frame=self._vx, vy_px_per_frame=self._vy,
                        vx_raw=_signed(int(r[0x57])), vy_raw=_signed(int(r[0x9F])),
                        grounded=int(r[0x1D]) == 0, motion_state_raw=int(r[0x1D]),
                        state_raw=int(r[0x0E]), status={0:"small", 1:"tall", 2:"fire"}.get(status, "unknown")),
            terrain=dict(tile_size=16, top_y=32, rows=13,
                         legend="Raw metatiles, columns left-to-right, rows top-to-bottom. 0=empty; 84=ground; 16/17=pipe tops; 81/82=bricks; 192/193=question blocks. Other nonzero values are terrain/objects, not necessarily solid. Unreported columns unknown.",
                         columns=columns),
            nearby_objects=objects, buttons=dict(self.buttons), history=deepcopy(list(self._history)),
        )

    def frame_rgb(self) -> np.ndarray:
        return np.array(self.env.screen, dtype=np.uint8, copy=True, order="C")

    def close(self):
        if not self._closed:
            self.env.close()
            self._closed = True
