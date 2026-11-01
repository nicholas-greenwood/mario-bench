"""Pure, evaluator-only outcomes for the paused Mario development pilot."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import mean, median

VALID_OUTCOMES = {"completed", "game_over", "frame_budget", "decision_budget", "invalid_action"}
INCOMPLETE_OUTCOMES = {"infra_error", "request_budget", "interrupted"}


def validated_progress_x(observation: dict, start_x: float) -> float | None:
    """Read actual normal-play RAM x, never a policy's claimed maximum.

    Airborne play counts; death/fall/transition animations do not. This is for
    the single-area 1-1 pilot only, not a route metric for arbitrary levels.
    """
    player = observation.get("player", {})
    x, y = player.get("x"), player.get("y")
    if (observation.get("death") or observation.get("done")
            or player.get("state_raw") != 8):
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) for v in (x, y)):
        return None
    return float(x) if x >= start_x and y < 240 else None


def score_episode(result: dict, level_spec: dict) -> dict:
    """Score a runner summary; infrastructure failures remain unscored.

    Required input: episode_id, level, status, start_x, max_progress_x.
    A completed status additionally requires the native ``completed=True`` flag.
    Runner must accumulate max_progress_x with validated_progress_x every native
    frame. The level spec supplies evaluator-only goal_x, never sent to policy.
    """
    status = result["status"]
    if status not in VALID_OUTCOMES | INCOMPLETE_OUTCOMES:
        raise ValueError(f"Unknown episode status: {status}")
    scored = dict(result)
    scored.update(rankable=status in VALID_OUTCOMES, clear=None, progress_pct=None,
                  progress_mapping_validated=False,
                  native_frames_to_completion=None, nominal_game_seconds_to_completion=None,
                  speedrun_score_native_frames=None)
    if not scored["rankable"]:
        return scored
    clear = status == "completed"
    if clear and result.get("completed") is not True:
        raise ValueError("Completed status requires explicit native completion evidence")
    frames = result.get("native_frames_to_completion")
    if clear and frames is not None:
        if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
            raise ValueError("Completion frames must be a positive native-frame integer")
        scored.update(native_frames_to_completion=frames,
                      nominal_game_seconds_to_completion=frames / 60,
                      speedrun_score_native_frames=frames)
    scored["clear"] = int(clear)
    coordinates = (result.get("start_x"), level_spec.get("goal_x"), result.get("max_progress_x"))
    # A new route without a calibrated mapping is unknown, never a guessed zero
    # or the World 1-1 denominator. Native completion remains authoritative.
    if any(v is None for v in coordinates):
        scored["progress_pct"] = 100.0 if clear else None
        return scored
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) for v in coordinates):
        raise ValueError("Finite numeric progress coordinates are required")
    start, goal, furthest = map(float, coordinates)
    if goal <= start:
        raise ValueError("goal_x must be greater than start_x")
    scored["progress_mapping_validated"] = True
    # Only the emulator's completion condition can award 100. Rounding display
    # to one decimal must not make a failure appear to have finished.
    progress = 100.0 if clear else min(99.9, max(0.0, 100 * (furthest - start) / (goal - start)))
    scored["progress_pct"] = progress
    return scored


def aggregate_results(results: list[dict], expected_episode_ids: list[str]) -> dict:
    """Equal-level aggregate over an explicit, complete matched cohort.

    A model with missing/infrastructure episodes has no comparable aggregate.
    Never condition a ranking on whichever calls happened to return successfully.
    """
    expected = set(expected_episode_ids)
    if not expected or len(expected) != len(expected_episode_ids):
        raise ValueError("Expected episode IDs must be nonempty and unique")
    ids = [r["episode_id"] for r in results]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate episode ID; reconcile retries before aggregation")
    if set(ids) - expected:
        raise ValueError("Unexpected episode ID; cohort must match the manifest")
    groups = {(r.get("model"), r.get("track")) for r in results}
    if len(groups) > 1:
        raise ValueError("Aggregate one model and observation track at a time")
    rankable = [r for r in results if r["rankable"]]
    incomplete = [r["episode_id"] for r in results if not r["rankable"]]
    missing = sorted(expected - set(ids))
    comparable = not missing and not incomplete
    by_level = defaultdict(list)
    for result in rankable:
        by_level[result["level"]].append(result)
    per_level = {}
    recorded_per_level = Counter(r["level"] for r in results)
    for level, rows in sorted(by_level.items()):
        timed = [r["native_frames_to_completion"] for r in rows
                 if r["clear"] and r.get("native_frames_to_completion") is not None]
        known_progress = [r["progress_pct"] for r in rows
                          if r["progress_pct"] is not None and r.get("progress_mapping_validated", True)]
        per_level[level] = dict(
            n=len(rows), clears=sum(r["clear"] for r in rows),
            observed_clear_rate_pct=100 * mean(r["clear"] for r in rows),
            progress_scored_episodes=len(known_progress),
            observed_mean_progress_pct=mean(known_progress) if len(known_progress) == len(rows) else None,
            completed_only_timing=dict(
                attempts=recorded_per_level[level], valid_attempts=len(rows),
                completions=sum(r["clear"] for r in rows),
                timed_completions=len(timed),
                median_native_frames_to_completion=median(timed) if timed else None,
                median_nominal_game_seconds_to_completion=median(timed) / 60 if timed else None,
            ),
        )
    progress_comparable = comparable and all(r["progress_pct"] is not None
                                            and r.get("progress_mapping_validated", True) for r in rankable)
    return dict(
        comparable=comparable, expected_episodes=len(expected), recorded_episodes=len(results),
        valid_episodes=len(rankable), coverage_pct=100 * len(rankable) / len(expected),
        missing_episode_ids=missing, incomplete_episode_ids=sorted(incomplete),
        status_counts=dict(Counter(r["status"] for r in results)),
        clear_rate_pct=mean(v["observed_clear_rate_pct"] for v in per_level.values()) if comparable else None,
        progress_comparable=progress_comparable,
        progress_scored_episodes=sum(r["progress_pct"] is not None
                                    and r.get("progress_mapping_validated", True) for r in rankable),
        mean_progress_pct=mean(v["observed_mean_progress_pct"] for v in per_level.values()) if progress_comparable else None,
        per_level_observed=per_level,
        speedrun_completed_only=dict(
            metric="median_native_frames_to_completion", direction="lower_is_better",
            nominal_frames_per_second=60, comparable_cohort=comparable,
            per_level_observed={level: values["completed_only_timing"]
                                for level, values in per_level.items()},
        ),
        uncertainty="Descriptive pilot only; repeated deterministic starts are not independent level samples.",
    )
