"""Built-in API connectivity test node for BUFF AI."""

from __future__ import annotations

import os
try:
    from .api_client import APIClientError, OpenAICompatibleClient, sanitize_url, validate_api_endpoint
    from .anthropic_client import DEFAULT_ANTHROPIC_BASE_URL, AnthropicClient
except ImportError:  # Standalone test fallback.
    from api_client import APIClientError, OpenAICompatibleClient, sanitize_url, validate_api_endpoint
    from anthropic_client import DEFAULT_ANTHROPIC_BASE_URL, AnthropicClient

API_PROVIDERS = ("OpenAI-compatible", "Anthropic")


def _provider(value) -> str:
    text = str(value or "").strip()
    return text if text in API_PROVIDERS else "OpenAI-compatible"


def _base_url(provider: str, value) -> str:
    base = str(value or "").strip() or os.getenv("BUFF_AI_API_BASE_URL", "").strip()
    return base or (DEFAULT_ANTHROPIC_BASE_URL if provider == "Anthropic" else "")


class BuffAIAPITest:
    DESCRIPTION = "Test BUFF AI API settings (OpenAI-compatible or Anthropic) with a tiny non-streaming request."
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("status",)
    FUNCTION = "test_api"
    CATEGORY = "BUFF AI/Debug"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_base_url": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "OpenAI 兼容 API 地址。远程使用 HTTPS；目标主机必须在本机 BUFF_AI_TRUSTED_API_HOSTS 中。",
                    },
                ),
                "api_model": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "中转站 /v1/models 返回的准确模型 ID。",
                    },
                ),
            },
            "optional": {
                "timeout_seconds": (
                    "INT",
                    {"default": 20, "min": 5, "max": 120, "step": 5},
                ),
                # Added after V3.2.1; kept last so older saved workflows keep
                # their positional widget values.
                "api_provider": (
                    list(API_PROVIDERS),
                    {"default": "OpenAI-compatible", "tooltip": "OpenAI-compatible：中转站；Anthropic：Claude 官方 API（地址可留空）。"},
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, api_base_url="", api_model="", api_key="", api_provider="OpenAI-compatible"):
        base_url = _base_url(_provider(api_provider), api_base_url)
        model = str(api_model or "").strip() or os.getenv("BUFF_AI_API_MODEL", "").strip()
        key = os.getenv("BUFF_AI_API_KEY", "").strip()
        if not base_url:
            return "[BUFF AI 配置错误] API 地址未填写。"
        try:
            validate_api_endpoint(base_url)
        except APIClientError as exc:
            return f"[BUFF AI 配置错误] {exc}"
        if not model:
            return "[BUFF AI 配置错误] 导演 LLM 模型未填写。"
        if not key:
            return "[BUFF AI 配置错误] API Key 未填写。"
        return True

    def test_api(
        self,
        api_base_url: str,
        api_model: str,
        api_key: str = "",
        timeout_seconds: int = 20,
        api_provider: str = "OpenAI-compatible",
    ):
        provider = _provider(api_provider)
        base_url = _base_url(provider, api_base_url)
        model = str(api_model or "").strip() or os.getenv("BUFF_AI_API_MODEL", "").strip()
        # Keep the argument for compatibility with old workflows, but never
        # consume a workflow-serialized credential from the API test node.
        key = os.getenv("BUFF_AI_API_KEY", "").strip()
        if provider == "Anthropic":
            endpoint = sanitize_url(base_url.rstrip("/") + "/v1/messages")
            client = AnthropicClient(base_url, key, model, int(timeout_seconds), max_tokens=1024)
        else:
            endpoint = sanitize_url(OpenAICompatibleClient.build_chat_url(base_url))
            client = OpenAICompatibleClient(base_url, key, model, int(timeout_seconds))
        print(f"[BUFF AI] API 连接测试：{endpoint} | provider={provider} | model={model} | stream=false", flush=True)

        try:
            client.chat(
                "You are a connectivity probe. Reply briefly with BUFF_OK.",
                "ping",
                temperature=0.0,
                prefer_json_mode=False,
            )
        except APIClientError as exc:
            print(f"[BUFF AI] API 连接测试失败：{exc}", flush=True)
            raise RuntimeError(f"[BUFF AI API 连接测试失败] {exc}") from None

        status = (
            "API 连接成功\n"
            f"类型: {provider}\n"
            f"地址: {endpoint}\n"
            f"模型: {model}\n"
            "请求模式: stream=false\n"
            "已收到兼容响应。"
        )
        print("[BUFF AI] API 连接测试成功。", flush=True)
        return {
            "ui": {"text": [status], "preview_title": ["API 连接测试"]},
            "result": (status,),
        }
