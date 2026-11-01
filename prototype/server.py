"""Local muted, paused fixed-step Mario decision-track prototype."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import queue
import threading
import time
from urllib.parse import parse_qs, urlparse

from PIL import Image

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prototype.decisions import DEFAULT_MODEL, OpenRouterPolicy
from prototype.emulator import MarioGame

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent


def load_key():
    value = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if value:
        return value
    path = PROJECT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and key.strip() == "OPENROUTER_API_KEY":
                return value.strip().strip('"').strip("'")
    return ""


def screenshot_png(rgb):
    stream = BytesIO()
    image = Image.fromarray(rgb)
    if image.size != (256, 240):
        raise RuntimeError(f"Unexpected NES screenshot dimensions: {image.size}")
    image.resize((512, 480), Image.Resampling.NEAREST).save(stream, format="PNG")
    return stream.getvalue()


class Runner:
    def __init__(self, frames_per_action=4, max_frames=6000, max_decisions=1500,
                 model=DEFAULT_MODEL, track="state", timeout=30, *,
                 policy=None, game_factory=MarioGame, run_dir=None):
        self.frames_per_action = frames_per_action
        self.max_frames = max_frames
        self.max_decisions = max_decisions
        self.lock = threading.RLock()
        self.image_ready = threading.Condition()
        self.commands = queue.Queue()
        self.requests = queue.Queue(maxsize=1)
        self.results = queue.Queue()
        self.stopping = threading.Event()
        self.ready = threading.Event()
        self.jpeg = b""
        self.input_png = b""
        self.input_artifacts = {}
        self.image_version = 0
        self.game_factory = game_factory
        self.policy = policy or OpenRouterPolicy(load_key(), model=model, timeout=timeout)
        self.state = dict(running=False, pending=False, phase="loading", model=model,
                          track=track, frames_per_action=frames_per_action,
                          max_frames=max_frames, max_decisions=max_decisions,
                          episode=1, frame=0, x=0, progress=0, decisions=0,
                          completed_actions=0, buttons={}, cost_usd=None, last_error=None,
                          done=False, outcome="Loading emulator", context={},
                          probabilities={}, screenshot=None, batch_remaining=0)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.run_dir = Path(run_dir) if run_dir else ROOT / "runs" / stamp
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.run_dir / "events.jsonl"
        self.log = self.log_file.open("a", buffering=1)
        self.state["log_file"] = str(self.log_file)
        self._write_log(dict(event="session", model=model, track=track,
                             mode="paused_fixed_step", frames_per_action=frames_per_action,
                             max_frames=max_frames, max_decisions=max_decisions,
                             note="Development cadence; not a frozen benchmark protocol. Timing is internal debugging only."))
        self.worker = threading.Thread(target=self._inference, daemon=True, name="decisions")
        self.game_worker = threading.Thread(target=self._game, daemon=True, name="emulator")
        self.worker.start()
        self.game_worker.start()

    def _write_log(self, record):
        self.log.write(json.dumps(record, allow_nan=False, default=str) + "\n")

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def command(self, name, options=None):
        ack = queue.Queue(maxsize=1)
        self.commands.put((name, options or {}, ack))
        try:
            error = ack.get(timeout=5)
        except queue.Empty:
            raise RuntimeError("Emulator is not responding") from None
        if error:
            raise ValueError(error)
        return self.snapshot()

    def _inference(self):
        try:
            while not self.stopping.is_set():
                try:
                    generation, observation, png, model = self.requests.get(timeout=.1)
                except queue.Empty:
                    continue
                try:
                    self.policy.model = model
                    result, error = self.policy.decide(observation, image_png=png), None
                except Exception as exc:
                    result, error = None, str(exc)
                self.results.put((generation, observation, result, error))
        finally:
            self.policy.close()

    def _publish_frame(self, game):
        stream = BytesIO()
        Image.fromarray(game.frame_rgb()).save(stream, format="JPEG", quality=85)
        with self.image_ready:
            self.jpeg = stream.getvalue()
            self.image_version += 1
            self.image_ready.notify_all()

    def _game(self):
        game = None
        try:
            game = self.game_factory()
            observation = game.observe()
            generation, episode, remaining = 0, 1, 0
            total_decisions, actions = 0, 0
            paid_cost, has_cost, pending = 0.0, False, False
            self._publish_frame(game)
            self._update(observation, remaining, pending, episode, total_decisions, actions)
            with self.lock:
                self.state.update(phase="paused", outcome="Paused — ready for one decision")
            self.ready.set()
            while not self.stopping.is_set():
                while True:
                    try:
                        name, options, ack = self.commands.get_nowait()
                    except queue.Empty:
                        break
                    error = None
                    if name in ("start", "step"):
                        if pending or remaining:
                            error = "A request is already pending; pause and wait before starting another batch."
                        elif observation["done"]:
                            error = "Episode finished; reset before continuing."
                        elif total_decisions >= self.max_decisions or observation["frame"] + self.frames_per_action > self.max_frames:
                            error = "Development budget reached; reset starts a new episode."
                        else:
                            remaining = 1 if name == "step" else options.get("decisions", 10)
                            with self.lock:
                                self.state.update(last_error=None, outcome="Preparing paused observation")
                    elif name == "pause":
                        generation += 1
                        remaining = 0
                        with self.lock:
                            self.state.update(phase="paused", outcome="Paused; pending replies will be discarded" if pending else "Paused")
                    elif name == "reset":
                        generation += 1
                        remaining = 0
                        game.reset()
                        observation = game.observe()
                        episode += 1
                        total_decisions, actions = 0, 0
                        self.input_png = b""
                        self._publish_frame(game)
                        with self.lock:
                            self.state.update(phase="paused", last_error=None, outcome="Paused — fresh episode",
                                              context={}, probabilities={}, screenshot=None)
                        self._write_log(dict(event="reset", episode=episode))
                    elif name == "configure":
                        if pending or remaining:
                            error = "Pause and wait for the pending request before changing track, model or cadence."
                        else:
                            self.frames_per_action = options.get("frames_per_action", self.frames_per_action)
                            with self.lock:
                                self.state.update(track=options.get("track", self.state["track"]),
                                                  model=options.get("model", self.state["model"]),
                                                  frames_per_action=self.frames_per_action)
                            self._write_log(dict(event="configure", frame=observation["frame"], **options))
                    self._update(observation, remaining, pending, episode, total_decisions, actions)
                    ack.put(error)

                try:
                    result_gen, seen, result, error = self.results.get_nowait()
                except queue.Empty:
                    pass
                else:
                    pending = False
                    # Session cost includes discarded old-episode replies; episode
                    # decision budgets count only requests issued within that episode.
                    if result and isinstance(result.get("cost_usd"), (int, float)):
                        paid_cost += result["cost_usd"]
                        has_cost = True
                    accepted = result_gen == generation and remaining > 0 and not observation["done"]
                    before = observation["frame"]
                    self._write_log(dict(event="decision", accepted=accepted, episode=seen["episode"],
                                         observed_frame=seen["frame"], applied_frame=before,
                                         result=result, error=error))
                    with self.lock:
                        self.state["cost_usd"] = paid_cost if has_cost else None
                    if accepted and error:
                        remaining = 0
                        with self.lock:
                            self.state.update(phase="error", last_error=error, outcome="Request failed — emulator stayed frozen")
                    elif accepted:
                        if before != seen["frame"]:
                            raise RuntimeError("Emulator advanced during inference")
                        with self.lock:
                            self.state.update(phase="stepping", buttons=dict(result["buttons"]),
                                              probabilities=result["probabilities"],
                                              response_model=result.get("model"), provider=result.get("provider"),
                                              request_id=result.get("request_id"), outcome="Applying model action")
                        # Only this block advances the environment. Rendering pace
                        # cannot affect the fixed number of native emulator steps.
                        for _ in range(self.frames_per_action):
                            observation = game.step(result["buttons"])
                            self._publish_frame(game)
                            self._update(observation, remaining, pending, episode, total_decisions, actions)
                            if observation["done"]:
                                break
                            self.stopping.wait(1/60)
                        actions += 1
                        remaining -= 1
                        self._write_log(dict(event="action_applied", episode=episode,
                                             observed_frame=seen["frame"], start_frame=before,
                                             end_frame=observation["frame"],
                                             native_frames=observation["frame"]-before,
                                             requested_frames=self.frames_per_action,
                                             buttons=result["buttons"], terminal=observation["done"],
                                             state=observation))
                        if observation["done"]:
                            remaining = 0
                            with self.lock:
                                self.state.update(phase="finished", outcome="Level cleared" if observation["flag_get"] else "Episode ended")
                        else:
                            with self.lock:
                                self.state.update(phase="paused", outcome="Paused — batch complete" if not remaining else "Preparing next observation")

                if remaining and not pending:
                    if total_decisions >= self.max_decisions or observation["frame"] + self.frames_per_action > self.max_frames:
                        remaining = 0
                        with self.lock:
                            self.state.update(phase="paused", outcome="Development frame or decision budget reached")
                    else:
                        # Both are captured by the sole emulator owner with no step
                        # between them. Never attach a later viewer/JPEG frame.
                        track = self.state["track"]
                        context = (dict(frame=observation["frame"], level=observation["level"], buttons=deepcopy(observation["buttons"]))
                                   if track in ("image", "state_image") else deepcopy(observation))
                        context["episode"] = episode
                        context["control_interval_frames"] = self.frames_per_action
                        context["control_interval"] = dict(mode="paused_fixed_step", native_frames=self.frames_per_action,
                            instruction="The emulator is frozen throughout inference. The four complete button states will replace previous controls and be held for exactly this many native frames, stopping early only if the episode terminates. Repeating held A keeps A held; release A to enable a fresh press.")
                        png = screenshot_png(game.frame_rgb())
                        digest = hashlib.sha256(png).hexdigest()
                        track = self.state["track"]
                        artifact = self.run_dir / f"e{episode:03d}-f{observation['frame']:06d}-{digest[:12]}.png"
                        artifact.write_bytes(png)
                        self.input_artifacts[digest] = artifact
                        metadata = dict(frame=observation["frame"], sha256=digest,
                                        width=512, height=480, format="png", native_width=256,
                                        native_height=240, scaling="nearest_neighbour_2x", attached=track in ("image", "state_image"),
                                        path=str(artifact), url="/api/input.png")
                        self.input_png = png
                        total_decisions += 1
                        self._write_log(dict(event="request", episode=episode, decision=total_decisions,
                                             model=self.state["model"], track=track, context=context, screenshot=metadata))
                        self.requests.put_nowait((generation, context, png if track in ("image", "state_image") else None, self.state["model"]))
                        pending = True
                        with self.lock:
                            self.state.update(context=context, screenshot=metadata, phase="waiting",
                                              outcome="Waiting for model — emulator frozen")
                self._update(observation, remaining, pending, episode, total_decisions, actions)
                self.stopping.wait(.005)
        except Exception as exc:
            with self.lock:
                self.state.update(running=False, pending=False, phase="error", last_error=f"Emulator error: {exc}", outcome="Emulator unavailable")
            self.ready.set()
        finally:
            if game is not None:
                game.close()

    def _update(self, observation, remaining, pending, episode, decisions, actions):
        x = observation.get("player", {}).get("x", 0)
        with self.lock:
            self.state.update(running=bool(remaining), pending=pending, episode=episode,
                              frame=observation.get("frame", 0), x=x,
                              progress=min(1, max(0, (observation.get("progress_max_x", x)-40)/3120)),
                              buttons=deepcopy(observation.get("buttons", {})), decisions=decisions,
                              completed_actions=actions, done=bool(observation.get("done")),
                              time_remaining=observation.get("time_remaining"), lives=observation.get("lives"),
                              batch_remaining=remaining)

    def close(self):
        self.stopping.set()
        with self.image_ready:
            self.image_ready.notify_all()
        self.game_worker.join(3)
        self.worker.join(1)
        self.log.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _reply(self, body, content_type="application/json", status=200):
        if isinstance(body, dict):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            self._reply(self.server.runner.snapshot())
        elif path == "/api/input.png":
            digest = parse_qs(urlparse(self.path).query).get("sha", [None])[0]
            if digest is None:
                png = self.server.runner.input_png
            else:
                artifact = self.server.runner.input_artifacts.get(digest)
                png = artifact.read_bytes() if artifact else b""
            self._reply(png if png else b"No decision screenshot yet", "image/png" if png else "text/plain", 200 if png else 404)
        elif path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            version = -1
            try:
                while not self.server.runner.stopping.is_set():
                    with self.server.runner.image_ready:
                        self.server.runner.image_ready.wait_for(lambda: self.server.runner.image_version != version or self.server.runner.stopping.is_set(), timeout=2)
                        jpeg = self.server.runner.jpeg
                        version = self.server.runner.image_version
                    if jpeg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
        else:
            files = {"/": ROOT/"static"/"index.html", "/static/styles.css": ROOT/"static"/"styles.css", "/static/app.js": ROOT/"static"/"app.js"}
            target = files.get(path)
            if target and target.is_file():
                self._reply(target.read_bytes(), mimetypes.guess_type(target.name)[0] or "text/plain")
            else:
                self._reply({"error": "Not found"}, status=404)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            self._reply({"error": "Origin not allowed"}, status=403)
            return
        path = urlparse(self.path).path
        commands = {"/api/start": "start", "/api/step": "step", "/api/pause": "pause", "/api/reset": "reset", "/api/configure": "configure"}
        if path not in commands:
            self._reply({"error": "Not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 4096:
                raise ValueError("Request too large")
            options = json.loads(self.rfile.read(length) if length else b"{}")
            if not isinstance(options, dict):
                raise ValueError("Expected a JSON object")
            if "decisions" in options and (type(options["decisions"]) is not int or not 1 <= options["decisions"] <= 100):
                raise ValueError("Batch must contain 1–100 decisions")
            if "track" in options and options["track"] not in ("state", "image", "state_image"):
                raise ValueError("Choose state or state_image")
            if "frames_per_action" in options and (type(options["frames_per_action"]) is not int or not 1 <= options["frames_per_action"] <= 60):
                raise ValueError("Choose 1–60 native frames per action")
            if "model" in options and (not isinstance(options["model"], str) or not options["model"].strip() or len(options["model"]) > 200):
                raise ValueError("A valid OpenRouter decision model ID is required")
            self._reply(self.server.runner.command(commands[path], options))
        except (ValueError, TypeError) as exc:
            self._reply({"error": str(exc)}, status=400)
        except RuntimeError as exc:
            self._reply({"error": str(exc)}, status=503)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--frames-per-action", type=int, default=4, choices=range(1,61))
    parser.add_argument("--max-frames", type=int, default=6000)
    parser.add_argument("--max-decisions", type=int, default=1500)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--track", choices=("state", "image", "state_image"), default="state")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    # Claim the port before starting inference/emulator workers.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    runner = Runner(args.frames_per_action, args.max_frames, args.max_decisions, args.model, args.track, args.timeout)
    server.runner = runner
    if not runner.ready.wait(30):
        runner.close()
        raise RuntimeError("Emulator startup timed out")
    print(f"Mario viewer: http://127.0.0.1:{args.port}; paused; muted; {args.frames_per_action} native frames/action (development default)", flush=True)
    print(f"Model: {args.model}; track: {args.track}; logs: {runner.log_file}", flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runner.close()


if __name__ == "__main__":
    main()
