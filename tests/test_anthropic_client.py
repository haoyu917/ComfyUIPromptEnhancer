import json
from types import SimpleNamespace

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

from anthropic_client import (  # noqa: E402
    DEFAULT_ANTHROPIC_BASE_URL,
    AnthropicClient,
    normalize_anthropic_base_url,
    to_anthropic_content,
)
from api_client import APIClientError  # noqa: E402
from node import BuffAIDirectorEnhancer  # noqa: E402
from tests.test_node_integration import _base_kwargs, _minimal_response  # noqa: E402

TRUSTED = "api.anthropic.com"


def _message(text, *, stop_reason="end_turn", input_tokens=120, output_tokens=30):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, cache_creation_input_tokens=0, cache_read_input_tokens=None),
    )


class FakeMessages:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _client(result, **kwargs):
    fake = SimpleNamespace(messages=FakeMessages(result))
    client = AnthropicClient(DEFAULT_ANTHROPIC_BASE_URL, "k", kwargs.pop("model", "claude-opus-5-5"), 30, trusted_hosts=TRUSTED, sdk_client=fake, **kwargs)
    return client, fake.messages


def _response(status):
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_base_url_defaults_and_drops_v1_suffix():
    assert normalize_anthropic_base_url("") == "https://api.anthropic.com"
    assert normalize_anthropic_base_url("https://api.anthropic.com/v1/") == "https://api.anthropic.com"


def test_chat_sends_messages_request_without_sampling_parameters():
    client, messages = _client(_message('{"ok": true}'))
    text = client.chat("SYSTEM", "USER", temperature=0.5, prefer_json_mode=True)
    assert text == '{"ok": true}'
    [call] = messages.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == "SYSTEM"
    assert call["messages"] == [{"role": "user", "content": "USER"}]
    assert call["max_tokens"] == 16000
    for unsupported in ("temperature", "top_p", "top_k", "response_format"):
        assert unsupported not in call
    assert client.last_usage == {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}


def test_model_is_whatever_the_user_chose():
    client, messages = _client(_message("x"), model="claude-sonnet-5-5")
    client.chat("s", "u")
    assert messages.calls[0]["model"] == "claude-sonnet-5-5"


def test_reference_images_become_base64_image_blocks():
    content = to_anthropic_content(
        "prompt",
        [
            {"type": "text", "text": "prompt"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
        ],
    )
    assert content == [
        {"type": "text", "text": "prompt"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}},
    ]
    with pytest.raises(APIClientError):
        to_anthropic_content("p", [{"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}])


def test_untrusted_endpoint_is_rejected_before_any_request():
    fake = SimpleNamespace(messages=FakeMessages(_message("x")))
    client = AnthropicClient("https://evil.example", "k", "m", 30, trusted_hosts=TRUSTED, sdk_client=fake)
    with pytest.raises(APIClientError):
        client.chat("s", "u")
    assert fake.messages.calls == []


@pytest.mark.parametrize(
    "error, status",
    [
        (anthropic.AuthenticationError("bad key sk-ant-SECRET", response=_response(401), body={"secret": "sk-ant-SECRET"}), 401),
        (anthropic.PermissionDeniedError("denied", response=_response(403), body=None), 403),
        (anthropic.NotFoundError("no model", response=_response(404), body=None), 404),
        (anthropic.RateLimitError("slow down", response=_response(429), body=None), 429),
        (anthropic.BadRequestError("bad", response=_response(400), body={"echo": "prompt text"}), 400),
        (anthropic.InternalServerError("boom", response=_response(500), body=None), 500),
    ],
)
def test_api_errors_map_to_status_without_leaking_response_body(error, status):
    client, _ = _client(error)
    with pytest.raises(APIClientError) as info:
        client.chat("s", "u")
    assert info.value.status == status
    assert "sk-ant-SECRET" not in str(info.value)
    assert "prompt text" not in str(info.value)


def test_connection_and_timeout_errors_are_readable():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    client, _ = _client(anthropic.APITimeoutError(request=request))
    with pytest.raises(APIClientError, match="30"):
        client.chat("s", "u")
    client, _ = _client(anthropic.APIConnectionError(request=request))
    with pytest.raises(APIClientError, match="无法连接"):
        client.chat("s", "u")


def test_refusal_and_truncation_raise():
    client, _ = _client(_message("", stop_reason="refusal"))
    with pytest.raises(APIClientError, match="refusal"):
        client.chat("s", "u")
    client, _ = _client(_message('{"partial": ', stop_reason="max_tokens"))
    with pytest.raises(APIClientError, match="max_tokens"):
        client.chat("s", "u")


def test_node_offers_provider_and_uses_anthropic_client(monkeypatch):
    optional = BuffAIDirectorEnhancer.INPUT_TYPES()["optional"]
    assert optional["api_provider"][0] == ["OpenAI-compatible", "Anthropic"]
    assert optional["api_provider"][1]["default"] == "OpenAI-compatible"

    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", TRUSTED)
    monkeypatch.setenv("BUFF_AI_API_KEY", "test-only-dummy")
    holder = {}

    class Node(BuffAIDirectorEnhancer):
        def _make_client(self, config):
            client = super()._make_client(config)
            client._sdk_client = SimpleNamespace(messages=FakeMessages(_message(json.dumps(_minimal_response(1)))))
            holder["client"] = client
            holder["config"] = config
            return client

    kwargs = _base_kwargs(api_base_url="", api_model="claude-sonnet-5-5", api_key="")
    outputs = Node().generate(**kwargs, api_provider="Anthropic")
    assert isinstance(holder["client"], AnthropicClient)
    assert holder["config"]["api_base_url"] == DEFAULT_ANTHROPIC_BASE_URL
    assert holder["client"].model == "claude-sonnet-5-5"
    assert outputs[0]


def test_validation_allows_blank_url_for_anthropic_but_still_requires_trust(monkeypatch):
    monkeypatch.setenv("BUFF_AI_API_KEY", "test-only-dummy")
    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", TRUSTED)
    assert BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "", "claude-opus-5-5", "", api_provider="Anthropic") is True
    assert "API 地址未填写" in BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "", "m", "", api_provider="OpenAI-compatible")
    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317")
    assert "未获本机信任" in BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "", "claude-opus-5-5", "", api_provider="Anthropic")


def test_default_provider_still_uses_openai_compatible_client():
    from api_client import OpenAICompatibleClient

    node = BuffAIDirectorEnhancer()
    config = {"api_provider": "OpenAI-compatible", "api_base_url": "http://127.0.0.1:8317/v1", "api_key": "k", "api_model": "m", "timeout_seconds": 10}
    assert isinstance(node._make_client(config), OpenAICompatibleClient)
