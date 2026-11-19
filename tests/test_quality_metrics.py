import json

import pytest

import run_logger
from director_modules import MODULE_SPECS
from director_router import build_dynamic_schema
from quality_metrics import (
    build_run_metrics,
    change_ratio,
    expected_fields_from_schema,
    is_acceptable,
    lock_violations,
    recompute_acceptable,
    score_response,
)
from tests.test_node_integration import FakeClient, MockNode, _base_kwargs, _minimal_response


DIALOGUE = [
    {"source_index": 1, "speaker": "@紫衣女妖", "text": "妖王，您明日便要大婚了，切莫如此……"},
    {"source_index": 2, "speaker": "@铁角妖王", "text": "你怕什么？"},
]


def _schema(**states):
    module_states = {key: "Off" for key in MODULE_SPECS}
    module_states.update(states)
    return build_dynamic_schema(module_states, "English")


def _full_response(shot_count=2, dialogues=None, keywords=""):
    top_fields, shot_fields = expected_fields_from_schema(_schema())
    raw = {field: "filled" for field in top_fields}
    raw["keywords"] = keywords
    raw["shots"] = []
    for i in range(shot_count):
        shot = {field: "filled" for field in shot_fields}
        shot["id"] = i + 1
        shot["dialogues"] = list(dialogues[i]) if dialogues and i < len(dialogues) else []
        raw["shots"].append(shot)
    return raw


def test_schema_fields_follow_active_modules_and_skip_user_owned_fields():
    base_top, base_shot = expected_fields_from_schema(_schema())
    top, shot = expected_fields_from_schema(_schema(blocking_staging="Auto"))
    assert "blocking_staging" in top and "blocking_staging" not in base_top
    assert "blocking_start" in shot and "blocking_start" not in base_shot
    for owned in ("keywords", "character_names", "shots"):
        assert owned not in top
    assert "id" not in shot and "dialogues" not in shot


def test_invalid_json_scores_as_unacceptable():
    metrics = build_run_metrics(first=None, strict_speech=True, schema_text=_schema())
    assert metrics["first"] == {"json_ok": False}
    assert metrics["lock_violations"] == ["invalid_json"]
    assert metrics["acceptable"] is False


def test_complete_compliant_response_is_acceptable():
    raw = _full_response(
        dialogues=[[{"source_index": 1, "text": DIALOGUE[0]["text"]}], [{"source_index": 2, "text": DIALOGUE[1]["text"]}]]
    )
    metrics = build_run_metrics(
        first=raw,
        strict_speech=True,
        schema_text=_schema(),
        dialogue_entries=DIALOGUE,
        target_shots=2,
        safe_max_shots=9,
    )
    first = metrics["first"]
    assert first["top_field_coverage"] == 1.0
    assert first["shot_field_coverage"] == 1.0
    assert first["dialogue_coverage"] == 1.0
    assert first["dialogue_verbatim_rate"] == 1.0
    assert metrics["lock_violations"] == []
    assert metrics["acceptable"] is True


def test_missing_altered_and_invented_dialogue_are_each_detected():
    raw = _full_response(
        dialogues=[[{"source_index": 1, "text": "妖王，您明天要大婚了"}, {"source_index": 0, "text": "吉时已到！"}]]
    )
    scores = score_response(raw, schema_text=_schema(), dialogue_entries=DIALOGUE, target_shots=2, safe_max_shots=9)
    assert scores["dialogue_coverage"] == 0.5
    assert scores["dialogue_verbatim_rate"] == 0.0
    assert scores["invented_dialogue_count"] == 1
    violations = lock_violations(scores, strict_speech=True)
    assert {"dialogue_missing", "dialogue_altered", "dialogue_invented"} <= set(violations)
    # Invented speech is only a violation under a strict speech policy.
    assert "dialogue_invented" not in lock_violations(scores, strict_speech=False)


def test_duplicate_dialogue_assignment_is_detected():
    line = {"source_index": 2, "text": DIALOGUE[1]["text"]}
    raw = _full_response(dialogues=[[line], [line]])
    scores = score_response(raw, schema_text=_schema(), dialogue_entries=DIALOGUE[1:], target_shots=2, safe_max_shots=9)
    assert scores["dialogue_duplicates"] == 1
    assert "dialogue_duplicated" in lock_violations(scores, strict_speech=True)


def test_invented_keywords_violate_the_blank_keyword_lock():
    scores = score_response(_full_response(keywords="masterpiece, 8k"), schema_text=_schema(), target_shots=2, safe_max_shots=9)
    assert scores["keywords_ok"] is False
    assert "keywords" in lock_violations(scores, strict_speech=True)
    exact = score_response(_full_response(keywords="buffStyle"), schema_text=_schema(), user_keywords="buffStyle", target_shots=2, safe_max_shots=9)
    assert exact["keywords_ok"] is True


def test_locked_shot_count_must_match_but_unlocked_count_is_a_recommendation():
    raw = _full_response(shot_count=3)
    locked = score_response(raw, schema_text=_schema(), target_shots=2, shot_count_locked=True, safe_max_shots=9)
    assert locked["shot_count_ok"] is False and locked["shot_count_deviation"] == 1
    unlocked = score_response(raw, schema_text=_schema(), target_shots=2, shot_count_locked=False, safe_max_shots=9)
    assert unlocked["shot_count_ok"] is True
    too_many = score_response(_full_response(shot_count=10), schema_text=_schema(), target_shots=2, safe_max_shots=9)
    assert too_many["shot_count_ok"] is False


def test_entity_token_rate_counts_full_at_tokens_only():
    raw = _full_response()
    raw["overview"] = "@铁角妖王 leans toward 紫衣女妖."
    scores = score_response(raw, schema_text=_schema(), entities=["铁角妖王", "紫衣女妖"], target_shots=2, safe_max_shots=9)
    assert scores["entity_token_rate"] == 0.5
    assert is_acceptable(scores, strict_speech=True) is False
    assert is_acceptable(scores, strict_speech=True, thresholds={"min_entity_token_rate": 0.5}) is True


def test_low_field_coverage_is_unacceptable_without_lock_violations():
    raw = _full_response()
    for shot in raw["shots"]:
        for key in list(shot):
            if key not in {"id", "dialogues"}:
                shot[key] = ""
    metrics = build_run_metrics(first=raw, strict_speech=True, schema_text=_schema(), target_shots=2, safe_max_shots=9)
    assert metrics["first"]["shot_field_coverage"] == 0.0
    assert metrics["lock_violations"] == []
    assert metrics["acceptable"] is False


def test_change_ratio_is_zero_for_identical_and_positive_for_rewrites():
    before = {"shots": [{"id": 1, "visual_information": "A stone chamber."}]}
    after = {"shots": [{"id": 1, "visual_information": "A torch-lit stone chamber with cold mist."}]}
    assert change_ratio(before, before) == 0.0
    assert 0.0 < change_ratio(before, after) <= 1.0


def test_recompute_acceptable_uses_stored_measurements():
    raw = _full_response()
    raw["overview"] = "@铁角妖王 only"
    metrics = build_run_metrics(
        first=raw, strict_speech=True, schema_text=_schema(), entities=["铁角妖王", "紫衣女妖"], target_shots=2, safe_max_shots=9
    )
    record = {"config": {"strict_speech_lock": True}, "metrics": metrics}
    assert recompute_acceptable(record, {}) is False
    assert recompute_acceptable(record, {"min_entity_token_rate": 0.5}) is True
    assert recompute_acceptable({"config": {}}, {}) is None


# ---- end-to-end through the node --------------------------------------------


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(run_logger.RESEARCH_LOG_DIR_ENV, str(tmp_path))
    return tmp_path


def _record(log_dir):
    lines = (log_dir / run_logger.RESEARCH_LOG_FILENAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_node_scores_raw_response_not_the_repaired_storyboard(log_dir):
    # The model omits the user's dialogue line; the node repairs the final
    # storyboard, but the metrics must still report the omission.
    MockNode([_minimal_response(1)]).generate(
        **_base_kwargs(),
        research_log="Metrics only",
        dialogue_text="@紫衣女妖｜妖王，您明日便要大婚了。",
    )
    record = _record(log_dir)
    metrics = record["metrics"]
    assert metrics["first"]["dialogue_coverage"] == 0.0
    assert metrics["first"]["dialogue_verbatim_rate"] is None
    assert "dialogue_missing" in metrics["lock_violations"]
    assert "dialogue_altered" not in metrics["lock_violations"]
    assert metrics["acceptable"] is False
    assert record["outcome"]["status"] == "ok"


def test_node_flags_model_invented_keywords_even_though_output_is_repaired(log_dir):
    # _minimal_response returns keywords "AI keywords" while the user left them blank.
    outputs = MockNode([_minimal_response(1)]).generate(**_base_kwargs(), research_log="Metrics only")
    assert "AI keywords" not in outputs[0]
    assert "keywords" in _record(log_dir)["metrics"]["lock_violations"]


def test_node_records_invalid_json_metrics_on_failure(log_dir):
    class BadClient(FakeClient):
        def chat(self, system_prompt, user_prompt, **kwargs):
            return "no json here"

    node = MockNode([])
    node.fake_client = BadClient([])
    with pytest.raises(RuntimeError):
        node.generate(**_base_kwargs(), research_log="Metrics only")
    metrics = _record(log_dir)["metrics"]
    assert metrics["first"]["json_ok"] is False
    assert metrics["acceptable"] is False


def test_node_scores_quality_pass_separately(log_dir):
    second = _minimal_response(1)
    second["shots"][0]["visual_information"] = "A rewritten, much more detailed description of the chamber."
    MockNode([_minimal_response(1), second]).generate(**_base_kwargs(mode="Quality"), research_log="Metrics only")
    metrics = _record(log_dir)["metrics"]
    assert metrics["quality"]["json_ok"] is True
    assert "quality_lock_violations" in metrics
    assert metrics["quality_change_ratio"] > 0.0


def test_node_skips_metrics_when_logging_is_off(log_dir, monkeypatch):
    import node as node_module

    def explode(**kwargs):
        raise AssertionError("metrics must not run when logging is off")

    monkeypatch.setattr(node_module, "build_run_metrics", explode)
    MockNode([_minimal_response(1)]).generate(**_base_kwargs())


def test_sfx_only_treats_any_returned_line_as_invented(log_dir):
    response = _minimal_response(1)
    response["shots"][0]["dialogues"] = [{"source_index": 1, "speaker": "@紫衣女妖", "text": "妖王，您明日便要大婚了。"}]
    MockNode([response]).generate(
        **_base_kwargs(),
        research_log="Metrics only",
        audio_policy="SFX Only",
        dialogue_text="@紫衣女妖｜妖王，您明日便要大婚了。",
    )
    metrics = _record(log_dir)["metrics"]
    assert metrics["first"]["dialogue_lines"] == 0
    assert metrics["first"]["invented_dialogue_count"] == 1
    assert "dialogue_invented" in metrics["lock_violations"]


def test_allowed_offscreen_line_reusing_an_index_is_not_an_onscreen_violation():
    # Observed with a real model: the off-screen line was placed in a shot's
    # dialogues with source_index 1, the same index as on-screen line 1.
    offscreen = [{"source_index": 1, "speaker": "门外司仪", "text": "吉时已到！"}]
    raw = _full_response(
        dialogues=[
            [{"source_index": 1, "text": DIALOGUE[0]["text"]}, {"source_index": 2, "text": DIALOGUE[1]["text"]}],
            [{"source_index": 1, "speaker": "门外司仪", "text": "吉时已到！"}],
        ]
    )
    common = dict(schema_text=_schema(), dialogue_entries=DIALOGUE, target_shots=2, safe_max_shots=9)
    allowed = score_response(raw, offscreen_entries=offscreen, **common)
    assert allowed["offscreen_lines_in_dialogues"] == 1
    assert allowed["dialogue_duplicates"] == 0 and allowed["dialogue_verbatim_rate"] == 1.0
    assert lock_violations(allowed, strict_speech=True) == []
    # When off-screen speech is not allowed, the same line is a violation.
    not_allowed = score_response(raw, **common)
    assert lock_violations(not_allowed, strict_speech=True) != []
