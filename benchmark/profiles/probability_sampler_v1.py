"""Frozen unmasked native-probability decoder; no game state or controller helpers."""
import math
import random


def sample_choice(probabilities, rng, temperature=0.05):
    if temperature <= 0 or not math.isfinite(temperature):
        raise ValueError('Temperature must be positive and finite')
    if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p < 0
           for p in probabilities.values()):
        raise ValueError('Invalid native probabilities')
    if abs(sum(probabilities.values()) - 1) >= .03:
        raise ValueError('Incomplete native distribution')
    candidates = sorted(probabilities)
    weights = {key: probabilities[key] ** (1 / temperature) for key in candidates}
    total = sum(weights.values())
    if not total > 0:
        raise ValueError('Empty tempered distribution')
    tempered = {key: weights[key] / total for key in candidates}
    draw = rng.random()
    cumulative, selected = 0.0, candidates[-1]
    for key in candidates:
        cumulative += tempered[key]
        if draw < cumulative:
            selected = key
            break
    return selected, draw, tempered
