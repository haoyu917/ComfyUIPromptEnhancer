import json

import pytest

import run_logger
from api_client import APIClientError, OpenAICompatibleClient
from director_modules import MODULE_SPECS
from node import BuffAIDirectorEnhancer
from run_logger import RunRecorder, resolve_log_path
from tests.test_node_integration import FakeClient, MockNode, _base_kwargs, _minimal_response


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(run_logger.RESEARCH_LOG_DIR_ENV, str(tmp_path))
    return tmp_path


def _records(log_dir):
    path = log_dir / run_logger.RESEARCH_LOG_FILENAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class UsageClient(FakeClient):
    """Fake client that reports token usage like a real endpoint."""

    def chat(self, system_prompt, user_prompt, **kwargs):
        text = super().chat(system_prompt, user_prompt, **kwargs)
        self.last_usage = {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}
        return text


class UsageNode(MockNode):
    def __init__(self, responses):
        self.fake_client = UsageClient(responses)


class FailingClient(FakeClient):
    def chat(self, system_prompt, user_prompt, **kwargs):
        raise APIClientError("HTTP 503 from upstream", status=503)


class InvalidJsonClient(FakeClient):
    def chat(self, system_prompt, user_prompt, **kwargs):
        return "not json at all"


def test_input_types_expose_research_log_controls_defaulting_to_off():
    optional = BuffAIDirectorEnhancer.INPUT_TYPES()["optional"]
    assert optional["research_log"][0] == ["Off", "Metrics only", "Full text"]
    assert optional["research_log"][1]["default"] == "Off"
    assert optional["research_tag"][1]["default"] == ""


def test_research_log_off_writes_nothing(log_dir):
    MockNode([_minimal_response(1)]).generate(**_base_kwargs())
    assert _records(log_dir) == []


def test_metrics_only_records_configuration_features_and_outcome_without_text(log_dir):
    node = UsageNode([_minimal_response(2)])
    node.generate(
        **_base_kwargs(),
        research_log="Metrics only",
        research_tag="pilot-01",
        dialogue_text="@紫衣女妖｜妖王，您明日便要大婚了。",
        keywords="buffStyle",
    )
    [record] = _records(log_dir)

    assert record["schema_version"] == 1
    assert record["tag"] == "pilot-01"
    assert record["log_level"] == "Metrics only"
    assert set(record["module_states"]) == set(MODULE_SPECS)
    assert record["config"]["target_model"] == "MiniMax / Hailuo"
    assert record["config"]["mode"] == "Fast"

    features = record["features"]
    assert len(features["prompt_sha256"]) == 64
    assert features["prompt_has_cjk"] is True
    assert features["dialogue_count"] == 1
    assert features["has_keywords"] is True
    assert isinstance(features["filled_guidance"], list)

    assert record["outcome"]["status"] == "ok"
    assert record["outcome"]["shot_count"] >= 1
    assert record["totals"]["api_calls"] == 1
    assert record["totals"]["total_tokens"] == 140
    assert record["totals"]["usage_complete"] is True
    assert record["calls"][0]["json_ok"] is True

    assert "prompt_text" not in record
    assert "outputs" not in record
    raw = json.dumps(record, ensure_ascii=False)
    assert "妖王逼近女妖" not in raw


def test_records_never_contain_api_key_or_endpoint(log_dir):
    MockNode([_minimal_response(1)]).generate(
        **_base_kwargs(api_key="super-secret-key-123"),
        research_log="Full text",
    )
    raw = (log_dir / run_logger.RESEARCH_LOG_FILENAME).read_text(encoding="utf-8")
    assert "super-secret-key-123" not in raw
    assert "127.0.0.1:8317" not in raw
    assert "api_key" not in raw


def test_full_text_also_records_prompt_and_outputs(log_dir):
    MockNode([_minimal_response(1)]).generate(**_base_kwargs(), research_log="Full text")
    [record] = _records(log_dir)
    assert record["prompt_text"].startswith("妖王逼近女妖")
    assert record["outputs"]["enhanced_prompt"]
    assert record["outputs"]["storyboard"]["shots"]


def test_quality_mode_records_both_calls(log_dir):
    node = UsageNode([_minimal_response(1), _minimal_response(1)])
    node.generate(**_base_kwargs(mode="Quality"), research_log="Metrics only")
    [record] = _records(log_dir)
    assert [call["stage"] for call in record["calls"]] == ["first", "quality"]
    assert record["outcome"]["quality_applied"] is True
    assert record["totals"]["total_tokens"] == 280


def test_api_failure_is_recorded_as_outcome_and_still_raised(log_dir):
    node = MockNode([])
    node.fake_client = FailingClient([])
    with pytest.raises(RuntimeError):
        node.generate(**_base_kwargs(), research_log="Metrics only")
    [record] = _records(log_dir)
    assert record["outcome"]["status"] == "error"
    assert record["outcome"]["error_stage"] == "first_request"
    assert record["calls"][0]["ok"] is False
    assert record["calls"][0]["error_type"] == "APIClientError"


def test_invalid_json_is_recorded_as_parse_failure(log_dir):
    node = MockNode([])
    node.fake_client = InvalidJsonClient([])
    with pytest.raises(RuntimeError):
        node.generate(**_base_kwargs(), research_log="Metrics only")
    [record] = _records(log_dir)
    assert record["outcome"]["error_stage"] == "parse_first_response"
    assert record["calls"][0]["json_ok"] is False


def test_input_errors_before_the_request_are_not_recorded(log_dir):
    with pytest.raises(RuntimeError):
        MockNode([]).generate(
            **_base_kwargs(),
            research_log="Metrics only",
            shot_plan="Shot 1\nA\nShot 3\nB",
        )
    assert _records(log_dir) == []


def test_write_failure_does_not_break_generation(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv(run_logger.RESEARCH_LOG_DIR_ENV, str(blocker))
    outputs = MockNode([_minimal_response(1)]).generate(**_base_kwargs(), research_log="Metrics only")
    assert outputs[0]


def test_unknown_level_is_treated_as_off_and_default_path_is_inside_plugin(monkeypatch):
    assert RunRecorder("Everything").enabled is False
    monkeypatch.delenv(run_logger.RESEARCH_LOG_DIR_ENV, raising=False)
    path = resolve_log_path()
    assert path.name == "runs.jsonl"
    assert path.parent.name == "research_logs"


def test_api_client_keeps_reported_token_usage():
    def transport(url, headers, payload, timeout):
        return {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        }

    client = OpenAICompatibleClient(
        "http://127.0.0.1:8317/v1", "k", "m", 10, transport=transport, trusted_hosts="127.0.0.1:8317"
    )
    client.chat("s", "u")
    assert client.last_usage == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
