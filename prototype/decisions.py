"""One synchronous OpenRouter Decisions call per Mario controller decision.

OpenRouter uses ``state`` + a keyed ``questions``/``criteria`` object, unlike
OpenAI's native API (``input`` + question/choice arrays). Verified against:
https://openrouter.ai/openai/gpt-6-luna-decisions/providers
https://openrouter.ai/blog/tutorials/how-to-use-jev/
https://developers.openai.com/api/docs/guides/decisions
"""

from __future__ import annotations

import base64
import http.client
import json
import math
import socket
import time


ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "perplexity/pplx-decider-v1.2"

# These define button meanings, not an action-selection heuristic.
LEGACY_QUESTIONS = {
    "horizontal": {
        "type": "choice",
        "instructions": "Which horizontal D-pad state should Mario use for the next control interval to complete the level alive?",
        "criteria": {
            "left": "Hold left for the entire next interval.",
            "released": "Release both horizontal directions for the entire next interval.",
            "right": "Hold right for the entire next interval.",
        },
    },
    "vertical": {
        "type": "choice",
        "instructions": "Which vertical D-pad state should Mario use for the next control interval to complete the level alive?",
        "criteria": {
            "up": "Hold up for the entire next interval.",
            "released": "Release both vertical directions for the entire next interval.",
            "down": "Hold down for the entire next interval (crouch or enter a pipe when possible).",
        },
    },
    "jump": {
        "type": "choice",
        "instructions": "Should the A jump button be held or released for the next control interval? Use current button state, grounded state and nearby geometry. A must be released before a fresh jump can begin after a previous jump.",
        "criteria": {
            "held": "Hold A for the entire next interval: start a jump if eligible, or sustain the current jump. Holding A continuously does not create a fresh jump upon landing.",
            "released": "Release A for the entire next interval: stop sustaining a jump and allow a subsequent fresh A press to start another jump.",
        },
    },
    "run": {
        "type": "choice",
        "instructions": "Should the B run/fire button be held or released for the next control interval to complete the level alive?",
        "criteria": {
            "held": "Hold B for the entire next interval: run faster while moving, and use fire when the game permits it.",
            "released": "Release B for the entire next interval: use ordinary walking speed while moving.",
        },
    },
}

LEGACY_RULES = [
    "The objective is to reach the level's flag alive. Falling into a gap, running out of time, or touching a damaging enemy can kill Mario.",
    "All four answers are simultaneous button states, held until the next decision; released means the button is not pressed.",
    "Left/right move horizontally; momentum can continue after release. Up/down do not jump. Down can crouch or enter a pipe when eligible.",
    "A jumps when Mario is grounded and eligible. Holding A can sustain a higher jump. A must be released before pressing A for a fresh jump; continuing to hold A through landing does not automatically jump again.",
    "B increases movement speed and can fire when Mario has the fire power-up. Running changes travel distance and jump distance.",
    "Solid blocks and pipes obstruct movement. Mario can stand on solid surfaces. Ordinary enemies can often be defeated by landing on top; side contact can damage Mario.",
    "Use the supplied observation as evidence. Missing information is unknown. Choose actions yourself; no suggested action or precomputed move is supplied.",
]


from prototype.control import QUESTIONS, RULES, state_text, decode_action_response


class PolicyError(RuntimeError):
    """A safe, user-displayable API failure; never contains request credentials."""


class OpenRouterPolicy:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, *, timeout: float = 4.0):
        if not isinstance(api_key, str) or not api_key.strip():
            raise PolicyError("OPENROUTER_API_KEY is missing; set it in .env before starting.")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("A decision model ID is required.")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("The decision timeout must be a positive number of seconds.")
        self._api_key = api_key.strip()
        self.model = model
        self.timeout = float(timeout)
        self._connection: http.client.HTTPSConnection | None = None

    def close(self) -> None:
        """Release the persistent connection; use from the policy's owning thread."""
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    def decide(self, state: dict, image_png: bytes | None = None) -> dict:
        """Return simultaneous button choices and API telemetry, or raise PolicyError.

        ``state`` is JSON-serialisable factual emulator evidence, including current
        buttons and the control interval when available. No retries or fallback
        actions are performed. Call this blocking method from one background
        thread; sequential calls reuse the same HTTPS connection.
        """
        if not isinstance(state, dict):
            raise ValueError("Mario state must be a dictionary.")
        interval = state.get("control_interval_frames", 4)
        if image_png is None:
            parts = state_text(state, interval)
        else:
            from prototype.image_observation import image_parts
            parts = image_parts(image_png, state["frame"], interval, state["buttons"], level=state.get("level", "1-1"))
        from pathlib import Path
        roster = json.loads((Path(__file__).resolve().parents[1] / "benchmark/models.json").read_text())
        selected = next((m for m in roster["models"] if m["id"] == self.model), None)
        body = {"model": selected.get("request_model", self.model) if selected else self.model,
                "state": parts, "questions": QUESTIONS}
        if selected:
            body["provider"] = selected["provider"]
        try:
            encoded = json.dumps(body, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise PolicyError("Mario observation is not valid JSON evidence.") from None
        started = time.perf_counter()
        try:
            if self._connection is None:
                self._connection = http.client.HTTPSConnection("openrouter.ai", timeout=self.timeout)
            self._connection.request(
                "POST", "/api/alpha/decisions", body=encoded,
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            )
            response = self._connection.getresponse()
            # Draining the response is required before reusing an HTTP/1.1 socket.
            raw = response.read()
            header_id = response.getheader("x-request-id")
            if not 200 <= response.status < 300:
                messages = {
                    400: "request rejected; check the Decisions schema and model support",
                    401: "API key rejected; check OPENROUTER_API_KEY in .env",
                    402: "insufficient OpenRouter credits",
                    403: "access denied for this API key or model",
                    404: "Decisions endpoint or model unavailable",
                    408: "upstream decision request timed out",
                    429: "rate limit exceeded; reduce decision frequency",
                }
                detail = messages.get(response.status, "OpenRouter or its model provider failed")
                raise PolicyError(f"OpenRouter HTTP {response.status}: {detail}.")
        except PolicyError:
            self.close()
            raise
        except (TimeoutError, socket.timeout):
            self.close()
            raise PolicyError(f"OpenRouter decision timed out after {self.timeout:g}s.") from None
        except (socket.gaierror, ConnectionRefusedError):
            self.close()
            raise PolicyError("Could not reach OpenRouter; check the network connection.") from None
        except (OSError, ValueError, http.client.HTTPException):
            self.close()
            raise PolicyError("OpenRouter connection failed before a decision was returned.") from None
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            self.close()
            raise PolicyError("OpenRouter returned an invalid JSON decision response.") from None
        try:
            if not isinstance(result.get("answers"), dict) or set(result["answers"]) != set(QUESTIONS):
                raise PolicyError("Response question keys differ from the requested contract")
            parsed = self._parse_response(result, latency_ms, header_id)
            if selected and (parsed["model"] != selected["expected_returned_model"]
                             or parsed.get("provider") not in selected["expected_returned_provider_names"]):
                raise PolicyError("Returned model/provider differs from the pinned roster")
            return parsed
        except PolicyError:
            self.close()
            raise

    def _parse_response(self, result: object, latency_ms: float, header_id: str | None = None) -> dict:
        if not isinstance(result, dict) or result.get("error"):
            raise PolicyError("OpenRouter returned an API error instead of a decision.")
        answers = result.get("answers")
        if not isinstance(answers, dict):
            raise PolicyError("OpenRouter response is missing its keyed decision answers.")
        if "action" in answers:
            try:
                buttons, probabilities = decode_action_response(result)
            except ValueError as exc:
                raise PolicyError(str(exc)) from None
        else:
            # Historical recorded four-question episodes remain replayable.
            buttons, probabilities = {}, {}
            for name, question in LEGACY_QUESTIONS.items():
                answer = answers.get(name)
                allowed = question["criteria"]
                if not isinstance(answer, dict) or answer.get("type") != "choice":
                    raise PolicyError(f"OpenRouter returned no valid {name} choice.")
                choice = answer.get("choice")
                if not isinstance(choice, str) or choice not in allowed:
                    raise PolicyError(f"OpenRouter returned an unsupported {name} button value.")
                distribution = answer.get("probabilities")
                if not isinstance(distribution, dict) or set(distribution) != set(allowed):
                    raise PolicyError(f"OpenRouter returned no complete {name} probability distribution.")
                if any(not _number(value) or not 0 <= value <= 1 for value in distribution.values()):
                    raise PolicyError(f"OpenRouter returned invalid {name} probabilities.")
                if not math.isclose(sum(distribution.values()), 1.0, abs_tol=0.03):
                    raise PolicyError(f"OpenRouter {name} probabilities do not sum to one.")
                buttons[name] = choice
                probabilities[name] = distribution
        usage = result.get("usage", {})
        if not isinstance(usage, dict):
            raise PolicyError("OpenRouter returned invalid usage telemetry.")
        output = {
            "buttons": buttons,
            "latency_ms": latency_ms,
            "probabilities": probabilities,
            "usage": usage,
            "model": result.get("model") or self.model,
            "request_id": result.get("id") or header_id,
        }
        if "cost" in usage:
            if not _number(usage["cost"]) or usage["cost"] < 0:
                raise PolicyError("OpenRouter returned invalid cost telemetry.")
            output["cost_usd"] = usage["cost"]
        if result.get("provider") is not None:
            output["provider"] = result["provider"]
        return output


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
