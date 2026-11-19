import importlib.util
import json
import sys
from pathlib import Path

import pytest

from director_modules import MODULE_SPECS
from shot_planner import parse_shot_plan

ROOT = Path(__file__).resolve().parents[1]


def _load_sweep():
    spec = importlib.util.spec_from_file_location("run_sweep_under_test", ROOT / "experiments" / "run_sweep.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sweep = _load_sweep()


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_benchmark_prompts_are_valid_node_inputs():
    cases = sweep.load_prompts(sweep.DEFAULT_PROMPTS)
    assert len(cases) >= 12
    for case in cases:
        assert case["prompt"].strip()
        assert float(case["duration"]) > 0
        assert isinstance(case.get("tags", []), list) and case["tags"]
        # Locked shot plans must parse and, when timed, add up to the duration.
        parse_shot_plan(case.get("shot_plan", ""), float(case["duration"]))


def test_load_prompts_rejects_duplicates_and_missing_fields(tmp_path):
    path = tmp_path / "p.jsonl"
    path.write_text('{"id": "A", "prompt": "x", "duration": 4}\n{"id": "A", "prompt": "y", "duration": 4}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicates"):
        sweep.load_prompts(path)
    path.write_text('{"id": "A", "prompt": "x"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duration"):
        sweep.load_prompts(path)


def test_plan_has_baselines_and_reproducible_distinct_random_configs():
    cases = sweep.load_prompts(sweep.DEFAULT_PROMPTS)[:2]
    first = sweep.plan_runs(cases, experiment="e", n_random=4, seed=7)
    again = sweep.plan_runs(cases, experiment="e", n_random=4, seed=7)
    other = sweep.plan_runs(cases, experiment="e", n_random=4, seed=8)
    assert [run.tag for run in first] == [run.tag for run in again]
    assert [run.tag for run in first] != [run.tag for run in other]
    assert len(first) == 2 * (3 + 4)
    for case in cases:
        configs = [run.config for run in first if run.case["id"] == case["id"]]
        assert {c.config_id for c in configs if c.source == "baseline"} == {"full_auto", "professional", "simple"}
        signatures = [sweep.states_signature(c.module_states) for c in configs]
        assert len(signatures) == len(set(signatures))
        for config in configs:
            assert set(config.module_states) == set(MODULE_SPECS)
            assert set(config.module_states.values()) <= {"Off", "Auto"}


def test_product_module_only_in_random_configs_for_product_prompts():
    plain = sweep.random_configs({"id": "X", "tags": ["drama"]}, 20, seed=1)
    product = sweep.random_configs({"id": "Y", "tags": ["product"]}, 20, seed=1)
    assert all(c.module_states["product_macro"] == "Off" for c in plain)
    assert any(c.module_states["product_macro"] == "Auto" for c in product)


def test_tags_round_trip():
    tag = sweep.make_tag("pilot1", "P03", "rabc12345")
    assert sweep.parse_tag(tag) == {"exp": "pilot1", "prompt": "P03", "cfg": "rabc12345"}


def test_node_kwargs_pass_case_locks_and_module_states():
    case = {"id": "P", "prompt": "x", "duration": 6, "keywords": "kw", "audio_policy": "SFX Only", "tags": ["a"]}
    config = sweep.random_configs(case, 1, seed=3)[0]
    run = sweep.PlannedRun(case=case, config=config, tag="t")
    kwargs = sweep.node_kwargs(run, mode="Fast", language="中文", temperature=0.5, log_level="Full text", api_base_url="u", api_model="m", timeout=30)
    assert kwargs["director_preset"] == "Custom"
    assert kwargs["keywords"] == "kw" and kwargs["audio_policy"] == "SFX Only"
    assert kwargs["research_tag"] == "t" and kwargs["research_log"] == "Full text"
    for key, state in config.module_states.items():
        assert kwargs[MODULE_SPECS[key].state_input] == state


def test_dry_run_logs_one_record_per_run_and_resumes(tmp_path, capsys):
    args = ["--experiment", "t", "--random-configs", "1", "--dry-run", "--only", "P01", "P06", "--log-dir", str(tmp_path)]
    assert sweep.main(args) == 0
    records = _records(tmp_path / "runs.jsonl")
    assert len(records) == 2 * (3 + 1)
    for record in records:
        parts = sweep.parse_tag(record["tag"])
        assert parts["exp"] == "DRYRUN-t"
        assert record["outcome"]["status"] == "ok"
        assert "acceptable" in record["metrics"]
        assert record["config"]["director_preset"] == "Custom"

    assert sweep.main(args) == 0
    assert len(_records(tmp_path / "runs.jsonl")) == len(records)
    assert "Nothing to do." in capsys.readouterr().out


def test_max_runs_caps_new_runs(tmp_path):
    args = ["--experiment", "cap", "--random-configs", "2", "--dry-run", "--max-runs", "3", "--log-dir", str(tmp_path)]
    assert sweep.main(args) == 0
    assert len(_records(tmp_path / "runs.jsonl")) == 3


def test_plan_mode_makes_no_runs(tmp_path, capsys):
    assert sweep.main(["--experiment", "p", "--plan", "--log-dir", str(tmp_path)]) == 0
    assert not (tmp_path / "runs.jsonl").exists()
    assert "API calls" in capsys.readouterr().out


def test_real_run_requires_endpoint_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("BUFF_AI_API_BASE_URL", raising=False)
    monkeypatch.delenv("BUFF_AI_API_MODEL", raising=False)
    code = sweep.main(["--experiment", "r", "--only", "P11", "--log-dir", str(tmp_path), "--yes", "--api-base-url", "", "--api-model", ""])
    assert code == 2
    assert not (tmp_path / "runs.jsonl").exists()


def test_main_restores_environment(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", "api.example.com")
    monkeypatch.delenv("BUFF_AI_RESEARCH_LOG_DIR", raising=False)
    sweep.main(["--experiment", "env", "--random-configs", "0", "--dry-run", "--only", "P11", "--log-dir", str(tmp_path)])
    assert os.environ["BUFF_AI_TRUSTED_API_HOSTS"] == "api.example.com"
    assert "BUFF_AI_RESEARCH_LOG_DIR" not in os.environ


# ---- Claude Code CLI backend ---------------------------------------------------

import subprocess as _subprocess
from types import SimpleNamespace as _NS

sys.path.insert(0, str(ROOT / "experiments"))
from claude_cli_client import ClaudeCodeCLIClient  # noqa: E402
from api_client import APIClientError  # noqa: E402


def _cli_result(result='{"ok": true}', *, returncode=0, **extra):
    payload = {
        "type": "result", "subtype": "success", "is_error": False, "stop_reason": "end_turn", "result": result,
        "usage": {"input_tokens": 5, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 0, "output_tokens": 40},
        "modelUsage": {"claude-opus-5-5": {}},
    }
    payload.update(extra)
    return _NS(returncode=returncode, stdout=json.dumps(payload), stderr="")


class _Runner:
    def __init__(self, completed):
        self.completed = completed
        self.calls = []

    def __call__(self, command, **kwargs):
        system_file = Path(command[command.index("--system-prompt-file") + 1])
        self.calls.append({"command": command, "system": system_file.read_text(encoding="utf-8"), **kwargs})
        if isinstance(self.completed, BaseException):
            raise self.completed
        return self.completed


def test_cli_client_builds_isolated_command_and_reads_usage():
    runner = _Runner(_cli_result())
    client = ClaudeCodeCLIClient("claude-sonnet-5-5", 60, effort="high", runner=runner)
    assert client.chat("SYSTEM PROMPT", "USER PROMPT") == '{"ok": true}'
    [call] = runner.calls
    command = call["command"]
    assert command[:2] == ["claude", "-p"]
    assert command[command.index("--model") + 1] == "claude-sonnet-5-5"
    assert command[command.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in command and "--no-session-persistence" in command
    assert command[command.index("--effort") + 1] == "high"
    assert call["system"] == "SYSTEM PROMPT"
    assert call["input"] == "USER PROMPT"
    assert "USER PROMPT" not in command  # sent on stdin, not argv
    assert client.last_usage == {"prompt_tokens": 1005, "completion_tokens": 40, "total_tokens": 1045}
    assert client.last_served_model == "claude-opus-5-5"


@pytest.mark.parametrize("model", ["--dangerously-skip-permissions", "", "a b", "-x"])
def test_cli_client_rejects_model_names_that_could_be_flags(model):
    with pytest.raises(APIClientError):
        ClaudeCodeCLIClient(model, 60)


@pytest.mark.parametrize(
    "completed, message",
    [
        (_cli_result(is_error=True, subtype="error_during_execution"), "failed"),
        (_cli_result(returncode=1), "failed"),
        (_cli_result(stop_reason="refusal"), "refusal"),
        (_cli_result(stop_reason="max_tokens"), "truncated"),
        (_cli_result(result=""), "empty"),
        (_NS(returncode=1, stdout="not json with PROMPT TEXT", stderr="secret stderr"), "no JSON"),
        (_subprocess.TimeoutExpired(cmd="claude", timeout=5), "within"),
    ],
)
def test_cli_client_failures_raise_without_echoing_output(completed, message):
    client = ClaudeCodeCLIClient("claude-opus-5-5", 5, runner=_Runner(completed))
    with pytest.raises(APIClientError, match=message) as info:
        client.chat("s", "u")
    assert "PROMPT TEXT" not in str(info.value) and "secret stderr" not in str(info.value)


def test_cli_client_rejects_reference_images():
    client = ClaudeCodeCLIClient("claude-opus-5-5", 5, runner=_Runner(_cli_result()))
    with pytest.raises(APIClientError, match="reference images"):
        client.chat("s", "u", user_content=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}}])


def test_sweep_cli_provider_labels_records_and_never_uses_http(tmp_path, monkeypatch):
    response = json.dumps(
        {
            "title": "t", "overview": "o", "keywords": "",
            "shots": [{"id": 1, "visual_information": "v", "performance_action": "p", "dialogues": []}],
        },
        ensure_ascii=False,
    )
    runner = _Runner(_cli_result(response))
    original = ClaudeCodeCLIClient.__init__

    def patched(self, model, timeout_seconds, **kwargs):
        original(self, model, timeout_seconds, runner=runner, **kwargs)

    monkeypatch.setattr(ClaudeCodeCLIClient, "__init__", patched)
    monkeypatch.setattr(sweep.ClaudeCodeCLIClient, "__init__", patched)
    code = sweep.main(["--experiment", "cli", "--provider", "claude-cli", "--only", "P11", "--random-configs", "0", "--no-baselines", "--yes", "--log-dir", str(tmp_path)])
    assert code == 0  # no configs planned: nothing to do
    code = sweep.main(["--experiment", "cli", "--provider", "claude-cli", "--only", "P11", "--random-configs", "1", "--no-baselines", "--yes", "--log-dir", str(tmp_path)])
    assert code == 0
    [record] = _records(tmp_path / "runs.jsonl")
    assert record["config"]["api_provider"] == "Claude Code CLI"
    assert record["config"]["api_model"] == "claude-opus-5-5"
    assert record["totals"]["total_tokens"] == 1045
    assert len(runner.calls) == 1
