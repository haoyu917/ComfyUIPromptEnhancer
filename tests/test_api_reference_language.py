import json
import io
import urllib.error

import numpy as np
import pytest

from api_client import APIClientError, OpenAICompatibleClient
from language_policy import contains_cjk, parse_dialogue_source, resolve_user_field, source_language
from reference_images import (
    build_multimodal_content,
    collect_reference_assets,
    parse_reference_manifest,
    reference_summary,
)


def test_api_url_builder_accepts_base_v1_and_full_endpoint():
    assert OpenAICompatibleClient.build_chat_url("https://example.com") == "https://example.com/v1/chat/completions"
    assert OpenAICompatibleClient.build_chat_url("https://example.com/v1") == "https://example.com/v1/chat/completions"
    assert OpenAICompatibleClient.build_chat_url("https://example.com/v1/chat/completions") == "https://example.com/v1/chat/completions"


def test_api_client_retries_without_response_format_for_compatible_gateway():
    calls = []

    def transport(url, headers, payload, timeout):
        calls.append(payload)
        if len(calls) == 1:
            raise APIClientError("response_format is unsupported", status=400)
        return {"choices": [{"message": {"content": '{"shots": []}'}}]}

    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:8317/v1",
        api_key="secret",
        model="gpt-test",
        timeout_seconds=10,
        transport=transport,
    )
    content = client.chat("system", "user", prefer_json_mode=True)
    assert content == '{"shots": []}'
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]




def test_api_client_explicitly_disables_streaming_for_compatible_relays():
    calls = []

    def transport(url, headers, payload, timeout):
        calls.append(payload)
        return {"choices": [{"message": {"content": '{"shots": []}'}}]}

    client = OpenAICompatibleClient("http://127.0.0.1:8317/v1", "secret", "gpt-test", 10, transport=transport)
    client.chat("system", "user", prefer_json_mode=False)
    assert calls[0]["stream"] is False

def test_api_client_extracts_content_parts():
    def transport(url, headers, payload, timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "part A"},
                            {"type": "text", "text": "part B"},
                        ]
                    }
                }
            ]
        }

    client = OpenAICompatibleClient("https://x", "k", "m", 10, transport=transport)
    assert client.chat("s", "u") == "part A\npart B"




def test_urllib_transport_accepts_sse_fallback_and_stops_at_done(monkeypatch):
    class Headers:
        def get(self, key, default=None):
            if key.lower() == "content-type":
                return "text/event-stream; charset=utf-8"
            return default

    class FakeResponse:
        headers = Headers()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"hello "}}]}\n'
            yield b'data: {"choices":[{"delta":{"content":"world"}}]}\n'
            yield b'data: [DONE]\n'
            raise AssertionError("transport should stop reading after [DONE]")

    class FakeOpener:
        def open(self, request, timeout):
            return FakeResponse()

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: FakeOpener())
    result = OpenAICompatibleClient._urllib_transport(
        "https://example.test/v1/chat/completions",
        {"Content-Type": "application/json"},
        {"model": "x", "stream": False},
        5,
    )
    assert result["choices"][0]["message"]["content"] == "hello world"


def test_endpoint_policy_requires_trust_tls_for_remote_and_allows_trusted_local_http():
    from api_client import validate_api_endpoint

    assert validate_api_endpoint("https://api.example.com/v1", "api.example.com")
    assert validate_api_endpoint("http://127.0.0.1:8317/v1", "127.0.0.1:8317")
    assert validate_api_endpoint("http://[::1]:8080/v1", "[::1]:8080")

    with pytest.raises(APIClientError, match="HTTPS"):
        validate_api_endpoint("http://api.example.com/v1", "api.example.com")
    with pytest.raises(APIClientError, match="未获本机信任"):
        validate_api_endpoint("https://attacker.example/v1", "api.example.com")
    with pytest.raises(APIClientError, match="不能包含用户名或密码"):
        validate_api_endpoint("https://user:password@api.example.com/v1", "api.example.com")
    with pytest.raises(APIClientError):
        validate_api_endpoint("file:///tmp/secret", "api.example.com")


def test_untrusted_endpoint_is_rejected_before_transport_receives_key():
    calls = []

    def transport(url, headers, payload, timeout):
        calls.append((url, headers))
        return {"choices": [{"message": {"content": "unexpected"}}]}

    client = OpenAICompatibleClient(
        "https://attacker.example/v1", "dummy-test-key", "gpt-test", 5,
        transport=transport, trusted_hosts="api.example.com",
    )
    with pytest.raises(APIClientError, match="未获本机信任"):
        client.chat("system", "private prompt", prefer_json_mode=False)
    assert calls == []


def test_sanitized_url_redacts_userinfo_query_secrets_and_token_values():
    from api_client import sanitize_url

    cleaned = sanitize_url(
        "https://user:pass@api.example.com/v1?api_key=hidden&api-version=2025&x=opaque-value-for-test"
    )
    assert "user" not in cleaned and "pass" not in cleaned
    assert "hidden" not in cleaned
    assert "opaque-value-for-test" not in cleaned
    assert "api-version=%5BREDACTED%5D" in cleaned


def test_http_error_response_body_is_not_exposed(monkeypatch):
    secret_body = b"provider echoed highly private request detail"

    class FakeOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 500, "server error", {}, io.BytesIO(secret_body)
            )

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: FakeOpener())
    with pytest.raises(APIClientError) as caught:
        OpenAICompatibleClient._urllib_transport(
            "https://example.test/v1/chat/completions",
            {}, {}, 5,
        )
    assert caught.value.status == 500
    assert "highly private" not in str(caught.value)


def test_redirect_handler_refuses_redirects():
    handler = OpenAICompatibleClient._RejectRedirectHandler()
    assert handler.redirect_request(
        None, None, 302, "Found", {}, "https://attacker.example/steal"
    ) is None

def test_reference_manifest_and_dynamic_images_are_sorted_and_bound():
    manifest = parse_reference_manifest(
        "1=@铁角妖王 | main male character\n3=@石室 | room and table\n2=@紫衣女妖 | female character"
    )
    assert manifest[1].startswith("@铁角妖王")
    img = np.zeros((1, 8, 8, 3), dtype=np.float32)
    refs = collect_reference_assets(
        manifest_text="1=@铁角妖王\n2=@紫衣女妖",
        inputs={"reference_image_2": img, "reference_image_1": img},
    )
    assert [ref["index"] for ref in refs] == [1, 2]
    assert refs[0]["note"] == "@铁角妖王"
    assert refs[0]["data_url"].startswith("data:image/png;base64,")
    assert reference_summary(refs).startswith("Reference 1: @铁角妖王")


def test_multimodal_content_contains_text_notes_and_all_images():
    refs = [
        {"index": 1, "note": "hero", "data_url": "data:image/png;base64,AAA"},
        {"index": 2, "note": "room", "data_url": "data:image/png;base64,BBB"},
    ]
    content = build_multimodal_content("plan", refs)
    assert content[0] == {"type": "text", "text": "plan"}
    assert [part["type"] for part in content].count("image_url") == 2
    assert "Reference image 1 note: hero" in content[1]["text"]


def test_language_policy_detects_cjk_and_preserves_literal_locks():
    assert contains_cjk("一个想法")
    assert not contains_cjk("one idea")
    assert source_language("一个想法") == "Chinese"
    assert source_language("one idea") == "English"
    assert resolve_user_field("@紫衣女妖", "@PurpleDemoness", exact=True) == "@紫衣女妖"
    assert resolve_user_field("locked camera", "AI rewrite") == "locked camera"
    assert resolve_user_field("固定镜头", "Locked camera") == "Locked camera"


def test_dialogue_parser_preserves_original_script_and_supports_common_separators():
    rows = parse_dialogue_source("@紫衣女妖｜妖王，切莫如此……\n@铁角妖王|你怕什么？\n无名旁白：婚礼准备完毕")
    assert rows[0] == {"source_index": 1, "speaker": "@紫衣女妖", "text": "妖王，切莫如此……"}
    assert rows[1]["speaker"] == "@铁角妖王"
    assert rows[2]["speaker"] == "无名旁白"
    assert rows[2]["text"] == "婚礼准备完毕"


def test_reference_image_payload_is_downscaled_to_safe_max_side():
    import base64
    import io

    from PIL import Image
    from reference_images import image_to_data_url

    image = np.zeros((1, 1200, 2400, 3), dtype=np.float32)
    url = image_to_data_url(image)
    raw = base64.b64decode(url.split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as decoded:
        assert max(decoded.size) <= 1024
        assert decoded.size == (1024, 512)
