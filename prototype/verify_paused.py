"""No-network smoke checks using the real emulator and a gated fake policy.

Run: python -m prototype.verify_paused
All run artefacts go into a temporary directory; no .env or API calls are used.
"""
from io import BytesIO
import json
from pathlib import Path
import sys
import queue
import tempfile
import threading
import time
from unittest.mock import patch

import numpy as np
from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototype import decisions
from prototype.emulator import MarioGame
from prototype.server import Runner, screenshot_png

BUTTONS = dict(horizontal="right", vertical="released", jump="held", run="held")


class GatePolicy:
    def __init__(self):
        self.calls = queue.Queue()
        self.model = "offline-test"
        self.error = False

    def decide(self, state, image_png=None):
        gate = threading.Event()
        self.calls.put((state, image_png, gate))
        assert gate.wait(5), "Test policy gate timed out"
        if self.error:
            raise RuntimeError("Injected request failure")
        return dict(buttons=BUTTONS, probabilities={}, latency_ms=99999)

    def close(self):
        pass


def wait_for(predicate, description):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError(description)


def check_runner():
    with tempfile.TemporaryDirectory(prefix="mario-paused-smoke-") as directory:
        policy, games = GatePolicy(), []

        def factory():
            game = MarioGame()
            games.append(game)
            return game

        runner = Runner(policy=policy, game_factory=factory, run_dir=directory, frames_per_action=8, track="image",
                        max_frames=24, max_decisions=3)
        try:
            assert runner.ready.wait(15)
            assert runner.snapshot()["phase"] == "paused", runner.snapshot()
            runner.command("step")
            state, png, gate = policy.calls.get(timeout=5)
            assert state["frame"] == 0
            assert state["control_interval"]["native_frames"] == 8
            native = games[0].frame_rgb()
            assert png == screenshot_png(native), "Image and state capture diverged"
            image = np.asarray(Image.open(BytesIO(png)))
            assert image.shape == (480, 512, 3)
            for dy in (0, 1):
                for dx in (0, 1):
                    assert np.array_equal(image[dy::2, dx::2], native)
            time.sleep(.25)
            assert runner.snapshot()["frame"] == games[0].frame == 0
            public = runner.snapshot()
            assert not set(public).intersection({"latency_ms", "decision_hz", "simulation_fps", "observation_age_ms"})
            gate.set()
            wait_for(lambda: runner.snapshot()["completed_actions"] == 1, "Action not applied")
            assert runner.snapshot()["frame"] == games[0].frame == 8
            time.sleep(.2)
            assert runner.snapshot()["frame"] == 8, "Unrequested frames advanced"

            runner.command("step")
            state, png, gate = policy.calls.get(timeout=5)
            assert state["frame"] == 8 and png == screenshot_png(games[0].frame_rgb())
            runner.command("pause")
            gate.set()
            wait_for(lambda: not runner.snapshot()["pending"], "Paused reply not discarded")
            assert runner.snapshot()["frame"] == 8
            assert runner.snapshot()["completed_actions"] == 1

            runner.command("step")
            _, _, gate = policy.calls.get(timeout=5)
            runner.command("reset")
            gate.set()
            wait_for(lambda: not runner.snapshot()["pending"], "Reset reply not discarded")
            assert runner.snapshot()["frame"] == 0 and runner.snapshot()["episode"] == 2
            assert runner.snapshot()["decisions"] == 0

            policy.error = True
            runner.command("step")
            _, _, gate = policy.calls.get(timeout=5)
            gate.set()
            wait_for(lambda: runner.snapshot()["phase"] == "error", "Failure not surfaced")
            assert runner.snapshot()["frame"] == runner.snapshot()["completed_actions"] == 0

            policy.error = False
            runner.command("reset")
            runner.command("configure", {"track": "state"})
            runner.command("start", {"decisions": 4})
            for expected in (0, 8, 16):
                state, png, gate = policy.calls.get(timeout=5)
                assert state["frame"] == expected and png is None
                gate.set()
            wait_for(lambda: runner.snapshot()["frame"] == 24 and not runner.snapshot()["running"], "Budget did not stop batch")
            assert runner.snapshot()["completed_actions"] == runner.snapshot()["decisions"] == 3
        finally:
            runner.close()


def check_payloads():
    calls = []

    class Response:
        status = 200

        def getheader(self, _):
            return None

        def read(self):
            answers = {name: dict(type="choice", choice=next(iter(question["criteria"])),
                       probabilities={value: float(index == 0) for index, value in enumerate(question["criteria"])})
                       for name, question in decisions.QUESTIONS.items()}
            return json.dumps(dict(answers=answers, model="perplexity/pplx-decider-v1.2-20261016", provider="Perplexity")).encode()

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            calls.append(json.loads(kwargs["body"]))

        def getresponse(self):
            return Response()

        def close(self):
            pass

    stream = BytesIO()
    Image.new("RGB", (512, 480)).save(stream, format="PNG")
    png = stream.getvalue()
    game = MarioGame()
    state = game.observe()
    state["control_interval_frames"] = 4
    game.close()
    with patch.object(decisions.http.client, "HTTPSConnection", Connection):
        policy = decisions.OpenRouterPolicy("offline-test-key")
        policy.decide(state)
        policy.decide(state, image_png=png)
        policy.close()
    plain, image = calls
    assert plain["model"] == image["model"] and plain["questions"] == image["questions"]
    assert isinstance(plain["state"], str)
    metadata = json.loads(image["state"][0])
    assert metadata["observation_interface"] == "image_only"
    assert not set(metadata).intersection({"player", "terrain", "nearby_objects", "history", "camera_x"})
    assert metadata["native_frame"] == state["frame"]
    assert len(image["state"]) == 3
    uri = image["state"][2]["image_url"]["url"]
    assert uri.startswith("data:image/png;base64,")
    assert list(decisions.QUESTIONS) == ["action"]
    assert len(decisions.QUESTIONS["action"]["criteria"]) == 12



if __name__ == "__main__":
    check_runner()
    check_payloads()
    print("PASS: paused frames, fixed actions, same-frame PNG, exact 2x scaling, stale replies, failures, budgets, pixels-only payload isolation and joint controls; no network calls.")
