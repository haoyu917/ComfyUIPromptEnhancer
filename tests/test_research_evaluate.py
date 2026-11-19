import json

import pytest

from director_modules import MODULE_SPECS
from research.dataset import build_dataset, is_synthetic, load_records, parse_tag, usable
from research.evaluate import build_methods, evaluate, grouped_folds, main, score
from research.granular_3wd import ACCEPT, DEFER, REJECT


def _record(prompt, cfg, acceptable, *, exp="pilot", modules_on=(), target_model="Wan", tags_ok=True, metrics=True):
    record = {
        "tag": f"exp={exp};prompt={prompt};cfg={cfg}",
        "run_id": f"{prompt}-{cfg}",
        "config": {"target_model": target_model, "duration": 8.0, "language": "中文", "mode": "Fast", "audio_policy": "SFX Only", "shot_mode": "Auto", "generation_mode": "Text to Video"},
        "module_states": {key: ("Auto" if key in modules_on else "Off") for key in MODULE_SPECS},
        "features": {"dialogue_count": 1, "filled_guidance": []},
        "outcome": {"status": "ok"},
    }
    if metrics:
        record["metrics"] = {"acceptable": acceptable, "first": {"json_ok": True}}
    return record


def _write(path, records):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def test_parse_tag_and_synthetic_detection():
    assert parse_tag("exp=a;prompt=P1;cfg=x") == {"exp": "a", "prompt": "P1", "cfg": "x"}
    assert is_synthetic({"tag": "exp=DRYRUN-a;prompt=P1"})
    assert not is_synthetic({"tag": "exp=a;prompt=P1"})


def test_load_records_skips_synthetic_unless_allowed_and_filters_experiments(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(path, [_record("P1", "a", True), _record("P1", "b", False, exp="DRYRUN-x"), _record("P2", "a", True, exp="other")])
    assert len(load_records([path])) == 2
    assert len(load_records([path], allow_synthetic=True)) == 3
    assert [parse_tag(r["tag"])["exp"] for r in load_records([path], experiments=["other"])] == ["other"]


def test_api_failures_are_not_usable_but_invalid_json_is():
    api_failure = _record("P1", "a", False, metrics=False)
    api_failure["outcome"] = {"status": "error", "error_stage": "first_request"}
    invalid_json = _record("P1", "b", False)
    invalid_json["metrics"]["first"] = {"json_ok": False}
    assert not usable(api_failure)
    assert usable(invalid_json)


def test_build_dataset_creates_module_and_request_attributes():
    records = [_record("P1", "a", True, modules_on={"story_subtext"}), _record("P2", "b", False)]
    data = build_dataset(records, benchmark_tags={"P1": ["action", "dialogue"]})
    names = [a.name for a in data.table.attributes]
    assert names[: len(MODULE_SPECS)] == [f"module:{key}" for key in MODULE_SPECS]
    assert "tags" in names and "duration" in names
    tags_index = names.index("tags")
    assert data.table.rows[0][tags_index] == frozenset({"action", "dialogue"})
    assert data.table.labels == [True, False]
    assert data.groups == ["P1", "P2"]
    module_total = sum(a.weight for a in data.table.attributes if a.name.startswith("module:"))
    request_total = sum(a.weight for a in data.table.attributes if not a.name.startswith("module:"))
    assert module_total == pytest.approx(1.0) and request_total == pytest.approx(1.0)


def test_build_dataset_requires_usable_records():
    with pytest.raises(ValueError):
        build_dataset([_record("P1", "a", True, metrics=False)])


def test_grouped_folds_never_split_a_prompt():
    groups = ["P1", "P1", "P2", "P3", "P3", "P4"]
    folds = grouped_folds(groups, 2)
    assert len(folds) == 2
    for train, test in folds:
        assert not {groups[i] for i in train} & {groups[i] for i in test}
    assert sorted(i for _, test in folds for i in test) == list(range(len(groups)))
    assert len(grouped_folds(groups, 0)) == 4  # leave one prompt out
    with pytest.raises(ValueError):
        grouped_folds(["P1", "P1"], 2)


def test_score_separates_deferral_from_errors():
    truth = [True, True, False, False]
    outcomes = [ACCEPT, DEFER, REJECT, ACCEPT]
    result = score(truth, outcomes)
    assert result["coverage"] == 0.75
    assert result["accuracy"] == pytest.approx(2 / 3)
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["defer_rate"] == 0.25
    assert score([True], [DEFER])["precision"] is None


def test_learnable_pattern_is_learned_by_granular_classifier():
    # Runs with story_subtext on are acceptable, others are not, across prompts.
    records = []
    for p in range(6):
        for c in range(4):
            on = c % 2 == 0
            records.append(_record(f"P{p}", f"c{c}", on, modules_on={"story_subtext"} if on else set()))
    data = build_dataset(records)
    # One module flip moves the distance by (1/21 module weight) / (2 total) ~ 0.024,
    # so theta must be below that to separate the configurations.
    methods, _ = build_methods([0.01, 0.3], [1.0], [0.0], include_quotient=False, include_baselines=False)
    results = {r["method"]: r for r in evaluate(data, methods, n_folds=3)}
    for name in ("3WD-N(0.01,1,0)", "3WD-MC(0.01,1,0)"):
        assert results[name]["accuracy"] == 1.0
        assert results[name]["coverage"] == 1.0
    # Too coarse a relation mixes the classes in every granule: all deferred.
    assert results["3WD-N(0.3,1,0)"]["coverage"] == 0.0


def test_cli_writes_report_and_marks_synthetic(tmp_path, capsys):
    records = [_record(f"P{p}", f"c{c}", (p + c) % 2 == 0, exp="DRYRUN-t") for p in range(4) for c in range(3)]
    log = tmp_path / "runs.jsonl"
    _write(log, records)
    assert main(["--log", str(log)]) == 2  # synthetic records need opt-in
    out_dir = tmp_path / "report"
    code = main(["--log", str(log), "--allow-synthetic", "--thetas", "0.2", "--alphas", "1", "--betas", "0", "--folds", "2", "--out-dir", str(out_dir)])
    assert code == 0
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in report
    payload = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    assert payload["synthetic"] is True
    assert any(r["method"] == "Majority" for r in payload["results"])


def test_sklearn_baselines_run_when_available():
    pytest.importorskip("sklearn")
    records = [_record(f"P{p}", f"c{c}", c % 2 == 0, modules_on={"story_subtext"} if c % 2 == 0 else set()) for p in range(4) for c in range(4)]
    data = build_dataset(records)
    methods, notes = build_methods([], [1.0], [0.0], include_quotient=False)
    names = {r["method"]: r for r in evaluate(data, methods, n_folds=2)}
    assert not notes
    assert names["DecisionTree(gini)"]["accuracy"] == 1.0
