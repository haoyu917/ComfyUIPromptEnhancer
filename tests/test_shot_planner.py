import pytest

from shot_planner import ShotPlanError, parse_shot_plan


def test_parse_chinese_timed_shot_plan_locks_count_and_exact_times():
    text = """
Shot 1 · 0–2 秒
妖王逼近女妖。

Shot 2 · 2–10 秒
女妖说话。

Shot 3 · 10–11 秒
画外音打断。

Shot 4 · 11–12 秒
两人停顿。
"""
    lock = parse_shot_plan(text, total_duration=12.0)
    assert lock.shot_count == 4
    assert lock.has_locked_times is True
    assert lock.time_ranges == ((0.0, 2.0), (2.0, 10.0), (10.0, 11.0), (11.0, 12.0))
    assert "妖王逼近女妖" in lock.sections[0].body


def test_parse_english_count_only_plan_locks_order_but_not_time():
    text = """
Shot 1
Establish the room.
Shot 2
The character speaks.
Shot 3
An interruption lands.
"""
    lock = parse_shot_plan(text, total_duration=9.0)
    assert lock.shot_count == 3
    assert lock.has_locked_times is False
    assert lock.time_ranges == ()
    assert lock.sections[2].number == 3


def test_parse_supports_chinese_camera_marker():
    lock = parse_shot_plan("镜头1 · 0-3秒\n建立空间\n镜头2 · 3-6秒\n人物反应", 6.0)
    assert lock.shot_count == 2
    assert lock.has_locked_times


def test_partial_timestamps_are_rejected():
    with pytest.raises(ShotPlanError, match="all shots or none"):
        parse_shot_plan("Shot 1 · 0-2s\nA\nShot 2\nB", 5.0)


def test_non_contiguous_timestamps_are_rejected():
    with pytest.raises(ShotPlanError, match="contiguous"):
        parse_shot_plan("Shot 1 · 0-2s\nA\nShot 2 · 3-5s\nB", 5.0)


def test_timestamps_must_start_zero_and_end_at_duration():
    with pytest.raises(ShotPlanError, match="start at 0"):
        parse_shot_plan("Shot 1 · 1-2s\nA\nShot 2 · 2-5s\nB", 5.0)
    with pytest.raises(ShotPlanError, match="requested duration"):
        parse_shot_plan("Shot 1 · 0-2s\nA\nShot 2 · 2-4s\nB", 5.0)


def test_blank_shot_plan_returns_no_lock():
    lock = parse_shot_plan("", 10.0)
    assert lock.shot_count == 0
    assert not lock.has_locked_times
