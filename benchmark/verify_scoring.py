"""No-network scorer boundary checks: python -m benchmark.verify_scoring."""
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.scoring import aggregate_results, score_episode, validated_progress_x


def episode(status="frame_budget", x=520, eid="1-1:seed0:trial000", level="1-1"):
    return score_episode(dict(episode_id=eid, level=level, status=status, completed=status == "completed",
                              start_x=40, max_progress_x=x), {"goal_x": 1000})


def verify():
    assert episode("completed")["progress_pct"] == 100
    assert episode(x=-100)["progress_pct"] == 0
    assert episode(x=100000)["progress_pct"] == 99.9
    assert episode()["progress_pct"] == 50
    assert episode("invalid_action")["clear"] == 0
    assert episode("completed")["native_frames_to_completion"] is None
    timed = score_episode(dict(episode_id="timed", level="1-1", status="completed", completed=True,
                               start_x=40, max_progress_x=1000, native_frames_to_completion=1208), {"goal_x": 1000})
    assert timed["native_frames_to_completion"] == 1208
    assert timed["speedrun_score_native_frames"] == 1208
    assert timed["nominal_game_seconds_to_completion"] == 1208 / 60
    # Timing cannot be inferred from request wall time or generic diagnostic frames.
    untimed = score_episode(dict(episode_id="untimed", level="1-1", status="completed", completed=True, frames=99,
                                 start_x=40, max_progress_x=1000), {"goal_x": 1000})
    assert untimed["native_frames_to_completion"] is None
    failed_timing = score_episode(dict(episode_id="failed", level="1-1", status="game_over",
                                       start_x=40, max_progress_x=520, native_frames_to_completion=1208), {"goal_x": 1000})
    assert failed_timing["native_frames_to_completion"] is None
    assert failed_timing["speedrun_score_native_frames"] is None
    for native_flag in (None, False, 1):
        try:
            score_episode(dict(episode_id="false_clear", level="1-1", status="completed", completed=native_flag,
                               start_x=40, max_progress_x=1000), {"goal_x": 1000})
        except ValueError:
            pass
        else:
            raise AssertionError("Completion without an explicit native flag accepted")
    unknown = score_episode(dict(episode_id="unknown", level="1-2", status="frame_budget",
                                 start_x=40, max_progress_x=520), {"goal_x": None})
    assert unknown["rankable"] and unknown["progress_pct"] is None
    unknown_aggregate = aggregate_results([unknown], ["unknown"])
    assert unknown_aggregate["comparable"] and not unknown_aggregate["progress_comparable"]
    assert unknown_aggregate["mean_progress_pct"] is None
    unknown_clear = score_episode(dict(episode_id="unknown_clear", level="1-2", status="completed", completed=True,
                                       start_x=40, max_progress_x=520), {"goal_x": None})
    assert unknown_clear["progress_pct"] == 100 and not unknown_clear["progress_mapping_validated"]
    assert aggregate_results([unknown_clear], ["unknown_clear"])["mean_progress_pct"] is None
    assert episode("infra_error")["progress_pct"] is None
    assert not episode("request_budget")["rankable"]
    normal = dict(player=dict(x=520, y=100, state_raw=8), done=False, death=False)
    assert validated_progress_x(normal, 40) == 520
    assert validated_progress_x({**normal, "death": True}, 40) is None
    assert validated_progress_x({**normal, "done": True}, 40) is None
    assert validated_progress_x({**normal, "player": dict(x=9000, y=100, state_raw=11)}, 40) is None
    assert validated_progress_x({**normal, "player": dict(x=9000, y=256, state_raw=8)}, 40) is None
    assert validated_progress_x({**normal, "player": dict(x=float("nan"), y=0, state_raw=8)}, 40) is None
    # The pre-death maximum is retained; dying at an enormous RAM x adds none.
    maximum = 520
    candidate = validated_progress_x({**normal, "death": True, "player": dict(x=9000, y=100, state_raw=11)}, 40)
    maximum = max(maximum, candidate if candidate is not None else maximum)
    assert episode(x=maximum)["progress_pct"] == 50
    ids = ["a", "b"]
    full = aggregate_results([episode("completed", eid="a"), episode(eid="b")], ids)
    assert full["comparable"] and full["clear_rate_pct"] == 50 and full["mean_progress_pct"] == 75
    for rows in ([episode(eid="a")], [episode(eid="a"), episode("infra_error", eid="b")]):
        partial = aggregate_results(rows, ids)
        assert not partial["comparable"] and partial["clear_rate_pct"] is None and partial["coverage_pct"] == 50
    # Fixed equal level weights: extra trials on one level cannot dominate.
    balanced = aggregate_results([episode("completed", eid="a"), episode("completed", eid="b"),
                                  episode(eid="c", level="1-2")], ["a", "b", "c"])
    assert balanced["clear_rate_pct"] == 50
    slower = {**timed, "episode_id": "slower", "native_frames_to_completion": 1530,
              "nominal_game_seconds_to_completion": 1530 / 60}
    speed = aggregate_results([timed, slower, failed_timing], ["timed", "slower", "failed"])
    timing = speed["per_level_observed"]["1-1"]["completed_only_timing"]
    assert timing["attempts"] == 3 and timing["completions"] == timing["timed_completions"] == 2
    assert timing["median_native_frames_to_completion"] == 1369
    assert timing["median_nominal_game_seconds_to_completion"] == 1369 / 60
    assert speed["speedrun_completed_only"]["direction"] == "lower_is_better"
    assert speed["speedrun_completed_only"]["per_level_observed"]["1-1"] == timing
    for rows, expected in (([episode(eid="a"), episode(eid="a")], ids),
                           ([episode(eid="z")], ids),
                           ([{**episode(eid="a"), "model": "x"}, {**episode(eid="b"), "model": "y"}], ids)):
        try:
            aggregate_results(rows, expected)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid cohort accepted")
    print("PASS: native completion, valid progress, unknown route mappings, completed-only native timing, coverage and equal-level aggregation; no network.")


def calibrate():
    """Privileged endpoint diagnostic, explicitly not a ranked policy."""
    import hashlib
    import json
    from pathlib import Path
    import sys
    from prototype.emulator import MarioGame
    from gym_super_mario_bros._roms import smb1_rom_path

    protocol = json.loads(Path(__file__).with_name("protocol.json").read_text())
    endpoints = []
    for _ in range(2):
        game = MarioGame()
        try:
            assert game.observe()["player"]["x"] == protocol["levels"][0]["start_x"]
            initial_hash = hashlib.sha256(game.env.ram.tobytes()).hexdigest()
            for _frame in range(6000):
                # Prevent collision/falls for endpoint inspection. Do not write
                # x, flag/completion bytes or level geometry; x advances normally.
                ram = game.env.ram
                ram[0x079F] = 255  # invincibility countdown
                ram[0x00B5] = 1    # normal vertical page
                ram[0x00CE] = 48   # hold Mario above obstacles
                ram[0x009F] = 0    # vertical speed
                observation = game.step(dict(horizontal="right", run="held"))
                if game.done:
                    break
            assert game.flag_get and not game.death, observation
            endpoint = observation["player"]["x"]
            assert endpoint == protocol["levels"][0]["goal_x"], endpoint
            endpoints.append(dict(initial_ram_sha256=initial_hash, endpoint_x=endpoint,
                                  endpoint_frame=game.frame,
                                  endpoint_ram_sha256=hashlib.sha256(game.env.ram.tobytes()).hexdigest()))
        finally:
            game.close()
    assert endpoints[0] == endpoints[1], "Endpoint calibration was not deterministic"
    print(json.dumps(dict(calibration_only=True, ranked_baseline=False,
                          rom_sha256=hashlib.sha256(Path(smb1_rom_path()).read_bytes()).hexdigest(),
                          repeats=2, **endpoints[0]), indent=2))


if __name__ == "__main__":
    verify()
    import sys
    if "--calibrate" in sys.argv:
        calibrate()
