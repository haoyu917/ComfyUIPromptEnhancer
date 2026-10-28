import pytest

from shot_planner import parse_shot_plan
from storyboard import allocate_durations, normalize_action_beats, normalize_storyboard


def test_allocate_durations_exact_total():
    values = allocate_durations(12.0, [2, 8, 1, 1], min_duration=0.25)
    assert len(values) == 4
    assert abs(sum(values) - 12.0) < 1e-9
    assert all(value > 0 for value in values)


def test_normalize_action_beats_exact_local_and_global_end():
    beats = normalize_action_beats(
        [
            {"description": "pause", "weight": 1, "intensity": "low"},
            {"description": "speak", "weight": 3, "intensity": "medium"},
        ],
        shot_duration=8.0,
        global_start=2.0,
    )
    assert beats[0]["global_start"] == 2.0
    assert beats[-1]["global_end"] == 10.0
    assert sum(b["duration"] for b in beats) == pytest.approx(8.0)


def test_explicit_shot_plan_hard_locks_count_and_times_even_if_ai_returns_wrong_count():
    lock = parse_shot_plan(
        "Shot 1 · 0-2s\nA\nShot 2 · 2-10s\nB\nShot 3 · 10-11s\nC\nShot 4 · 11-12s\nD",
        12.0,
    )
    raw = {
        "title": "x",
        "shots": [
            {"id": 1, "duration_weight": 1, "purpose": "one"},
            {"id": 2, "duration_weight": 1, "purpose": "two"},
        ],
    }
    out = normalize_storyboard(
        raw,
        total_duration=12.0,
        shot_mode="Auto",
        continuity_lock=True,
        shot_lock=lock,
        dialogue_entries=[],
    )
    assert out["shot_count"] == 4
    assert [(s["start_time"], s["end_time"]) for s in out["shots"]] == [
        (0.0, 2.0),
        (2.0, 10.0),
        (10.0, 11.0),
        (11.0, 12.0),
    ]
    assert "Shot 4" in out["shots"][3]["user_shot_source"]


def test_count_only_shot_plan_locks_count_but_uses_ai_weights():
    lock = parse_shot_plan("Shot 1\nA\nShot 2\nB\nShot 3\nC", 9.0)
    raw = {
        "shots": [
            {"duration_weight": 1},
            {"duration_weight": 2},
            {"duration_weight": 1},
            {"duration_weight": 99},
        ]
    }
    out = normalize_storyboard(
        raw,
        total_duration=9.0,
        shot_mode="Auto",
        continuity_lock=False,
        shot_lock=lock,
        dialogue_entries=[],
    )
    assert out["shot_count"] == 3
    assert out["shots"][1]["duration"] > out["shots"][0]["duration"]
    assert out["shots"][-1]["end_time"] == 9.0


def test_no_user_plan_allows_ai_shot_count_with_safe_time_cap():
    raw = {"shots": [{"purpose": str(i)} for i in range(20)]}
    out = normalize_storyboard(
        raw,
        total_duration=5.0,
        shot_mode="Auto",
        continuity_lock=False,
        shot_lock=parse_shot_plan("", 5.0),
        dialogue_entries=[],
    )
    assert 1 <= out["shot_count"] <= 4
    assert out["shots"][-1]["end_time"] == 5.0


def test_single_and_multi_shot_modes_are_enforced():
    raw = {"shots": [{"purpose": "a"}, {"purpose": "b"}]}
    single = normalize_storyboard(
        raw,
        total_duration=5.0,
        shot_mode="Single Shot",
        continuity_lock=False,
        shot_lock=parse_shot_plan("", 5.0),
        dialogue_entries=[],
    )
    assert single["shot_count"] == 1

    with pytest.raises(ValueError, match="at least 2"):
        normalize_storyboard(
            {"shots": [{"purpose": "a"}]},
            total_duration=5.0,
            shot_mode="Multi Shot",
            continuity_lock=False,
            shot_lock=parse_shot_plan("", 5.0),
            dialogue_entries=[],
        )


def test_dialogue_source_is_reinserted_verbatim_when_ai_omits_it():
    raw = {"shots": [{"purpose": "dialogue", "duration_weight": 1, "dialogues": []}]}
    entries = [{"source_index": 1, "speaker": "@紫衣女妖", "text": "妖王，切莫如此……"}]
    out = normalize_storyboard(
        raw,
        total_duration=8.0,
        shot_mode="Single Shot",
        continuity_lock=True,
        shot_lock=parse_shot_plan("", 8.0),
        dialogue_entries=entries,
        global_dialogue_direction="Low and restrained.",
    )
    dialogue = out["shots"][0]["dialogues"][0]
    assert dialogue["speaker"] == "@紫衣女妖"
    assert dialogue["text"] == "妖王，切莫如此……"
    assert dialogue["voice_direction"] == "Low and restrained."


def test_continuity_out_is_inherited_by_next_shot():
    raw = {
        "shots": [
            {"continuity_out": "Sword remains drawn."},
            {"continuity_in": "AI wrote something else."},
        ]
    }
    out = normalize_storyboard(
        raw,
        total_duration=6.0,
        shot_mode="Auto",
        continuity_lock=True,
        shot_lock=parse_shot_plan("", 6.0),
        dialogue_entries=[],
    )
    assert out["shots"][1]["continuity_in"] == "Sword remains drawn."
