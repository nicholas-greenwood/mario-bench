"""Native Decisions transport, pinned routing and lossless audit records."""
from __future__ import annotations
import base64
import hashlib
import http.client
import json
import socket
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from prototype.decisions import QUESTIONS, RULES, LEGACY_QUESTIONS, LEGACY_RULES, OpenRouterPolicy, PolicyError
from prototype.control import state_text


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def legacy_request_body(model, state, image_png=None):
    evidence = dict(game='Super Mario Bros., world 1-1', rules_and_button_semantics=LEGACY_RULES,
                    observation=state)
    text = canonical(evidence).decode()
    if model.get('state_adapter') == 'text' and image_png is None:
        parts = text
    else:
        parts = [text]
        if image_png is not None:
            parts += ['The attached screenshot is the same paused observation frame. It is the native 256x240 screen scaled 2x to 512x480 with nearest-neighbour interpolation; screen coordinates map by (x*2,y*2).',
                      {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image_png).decode()}}]
    return dict(model=model.get('request_model', model['id']), state=parts,
                questions=LEGACY_QUESTIONS, provider=model['provider'])


def request_body(model, state, image_png=None, *, profile="joint-visible-v1"):
    if profile == "legacy":
        if image_png is not None:
            raise ValueError("Legacy RAM-plus-image inputs are replay-only; use the pixels-only profile")
        return legacy_request_body(model, state, image_png)
    if profile != "joint-visible-v1":
        raise ValueError(f"Unknown control profile: {profile}")
    interval = state.get("control_interval_frames", 4)
    if image_png is None:
        parts = state_text(state, interval)
    else:
        from prototype.image_observation import image_parts
        # Deliberately enumerate permitted metadata. No RAM-derived state/history
        # is passed to the visual observation contract.
        parts = image_parts(image_png, state["frame"], interval, state["buttons"], level=state.get("level", "1-1"))
    return dict(model=model.get("request_model", model["id"]), provider=model["provider"],
                state=parts, questions=QUESTIONS)


class Client:
    def __init__(self, key, model, timeout):
        self.key, self.model, self.timeout = key, model, timeout
        self.connection = None
        self.validator = OpenRouterPolicy(key, model=model['id'], timeout=timeout)

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def call(self, body):
        record = dict(request_sha256=digest(body), http_status=None, raw_response=None,
                      valid=False, retryable=False)
        started = time.perf_counter()
        try:
            if self.connection is None:
                self.connection = http.client.HTTPSConnection('openrouter.ai', timeout=self.timeout)
            self.connection.request('POST', '/api/alpha/decisions', body=canonical(body),
                                    headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'})
            response = self.connection.getresponse()
            record['http_status'] = response.status
            record['header_request_id'] = response.getheader('x-request-id')
            raw = response.read()
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeError):
                record['response_text'] = raw.decode(errors='replace')[:16384]
                record.update(failure_class='infrastructure', retryable=True)
                raise PolicyError('Invalid JSON response') from None
            record['raw_response'] = result
            if not 200 <= response.status < 300:
                record['retryable'] = response.status in (408, 429, 500, 502, 503, 504)
                raise PolicyError('HTTP ' + str(response.status))
            if not isinstance(result, dict) or result.get('error'):
                record['failure_class'] = 'infrastructure'
                envelope = result.get('error') if isinstance(result, dict) else None
                code = envelope.get('code') if isinstance(envelope, dict) else None
                record['retryable'] = code in (408, 429, 500, 502, 503, 504) or not isinstance(result, dict)
                raise PolicyError('API service error envelope instead of a decision')
            if not isinstance(result.get('answers'), dict) or set(result['answers']) != set(body['questions']):
                raise PolicyError('Response question keys differ from the requested contract')
            parsed = self.validator._parse_response(result, 0, record['header_request_id'])
            # A schema error is a model invalid action; service errors remain infrastructure.
            expected = self.model.get('expected_returned_model')
            if expected and parsed['model'] != expected:
                raise PolicyError('Returned model differs from pinned expected model')
            names = self.model.get('expected_returned_provider_names')
            if names and parsed.get('provider') not in names:
                raise PolicyError('Returned provider differs from pinned expected provider')
            record.update(valid=True, decision={k: v for k, v in parsed.items() if k != 'latency_ms'})
        except (OSError, socket.timeout, http.client.HTTPException) as exc:
            record.update(error_type='transport', error=type(exc).__name__, retryable=True)
            self.close()
        except PolicyError as exc:
            is_schema = record.get('failure_class') != 'infrastructure' and record['http_status'] is not None and 200 <= record['http_status'] < 300
            record.update(error_type='invalid_action' if is_schema else 'infrastructure',
                          error=str(exc).replace(self.key, '[redacted]'))
            if 'pinned expected' in record['error']:
                record['error_type'] = 'provenance_mismatch'
            self.close()
        record['debug_elapsed_ms'] = round((time.perf_counter() - started) * 1000, 2)
        return record


class FakeClient:
    """Deterministic smoke fixture, never used in model scoring."""
    def call(self, body):
        evidence = body['state']
        text = evidence if isinstance(evidence, str) else next(p for p in evidence if isinstance(p, str))
        try:
            data = json.loads(text)
            frame = data['native_frame'] if 'native_frame' in data else data['observation']['frame']
        except (ValueError, KeyError, TypeError):
            import re
            match = re.search(r'Frame (\d+)', text)
            if not match:
                raise ValueError('Offline fixture needs declared frame metadata')
            frame = int(match.group(1))
        time.sleep(0.05)  # Exercise paused waits and process overlap without any API calls.
        buttons = dict(horizontal='right', vertical='released', jump='held' if frame % 64 < 40 else 'released', run='held')
        return dict(valid=True, retryable=False, http_status=None, raw_response={'fixture': True},
                    decision=dict(buttons=buttons, model='offline-fixture', provider='none', usage={}),
                    request_sha256=digest(body))

    def close(self):
        pass
