"""Native Claude client (Anthropic Messages API) for BUFF AI Director.

Used when the node's ``api_provider`` is ``Anthropic``. It exposes the same
``chat()`` / ``last_usage`` interface as ``OpenAICompatibleClient``, so the
node's pipeline does not change.

The official ``anthropic`` SDK is an optional dependency: it is imported only
when this provider is used, so OpenAI-compatible users install nothing extra.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from .api_client import APIClientError, validate_api_endpoint
except ImportError:  # Standalone test fallback.
    from api_client import APIClientError, validate_api_endpoint

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_MAX_TOKENS = 16000
INSTALL_HINT = (
    "使用 Anthropic 接入需要官方 SDK。请在 ComfyUI 使用的 Python 环境中运行：pip install anthropic"
)
_DATA_URL_RE = re.compile(r"^data:(?P<mime>image/[A-Za-z0-9.+-]+);base64,(?P<data>.+)$", re.DOTALL)


def normalize_anthropic_base_url(base_url: str) -> str:
    """The SDK appends /v1/messages itself, so drop a trailing /v1."""

    base = str(base_url or "").strip().rstrip("/") or DEFAULT_ANTHROPIC_BASE_URL
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


def to_anthropic_content(user_prompt: str, user_content: Any = None) -> Any:
    """Convert the node's OpenAI-style multimodal content to Messages API blocks."""

    if user_content is None or isinstance(user_content, str):
        return user_content if isinstance(user_content, str) else user_prompt
    blocks: List[Dict[str, Any]] = []
    for part in user_content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            blocks.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            url = str((part.get("image_url") or {}).get("url", ""))
            match = _DATA_URL_RE.match(url)
            if not match:
                raise APIClientError("参考图格式无法转换为 Claude 图片输入（需要 base64 data URL）。")
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": match.group("mime"), "data": match.group("data")},
                }
            )
    return blocks or user_prompt


def _usage_dict(usage: Any) -> Optional[Dict[str, int]]:
    """Map Messages API usage to the prompt/completion/total shape the logger expects."""

    if usage is None:
        return None
    prompt = 0
    for name in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = getattr(usage, name, None)
        if isinstance(value, int):
            prompt += value
    completion = getattr(usage, "output_tokens", None)
    completion = completion if isinstance(completion, int) else 0
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


class AnthropicClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        *,
        trusted_hosts: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        sdk_client: Any = None,
    ):
        self.base_url = normalize_anthropic_base_url(base_url)
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout_seconds = int(timeout_seconds)
        self.trusted_hosts = trusted_hosts
        self.max_tokens = int(max_tokens)
        self._sdk_client = sdk_client
        self.last_usage: Optional[Dict[str, int]] = None

    def _client(self) -> Any:
        if self._sdk_client is None:
            try:
                import anthropic
            except ImportError:
                raise APIClientError(INSTALL_HINT) from None
            self._sdk_client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=float(self.timeout_seconds),
                max_retries=2,
            )
        return self._sdk_client

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        user_content: Any | None = None,
        temperature: float = 0.6,
        prefer_json_mode: bool = True,
    ) -> str:
        # ``temperature`` and ``prefer_json_mode`` are accepted for interface
        # compatibility but not sent: current Claude models reject sampling
        # parameters with HTTP 400, and the node's prompt already requires a
        # single JSON object, which the node parses from the text.
        del temperature, prefer_json_mode
        self.last_usage = None
        if not self.model:
            raise APIClientError("api_model is empty")
        validate_api_endpoint(self.base_url, self.trusted_hosts)
        if not self.api_key:
            raise APIClientError("api_key is empty")
        client = self._client()

        try:
            import anthropic
        except ImportError:
            raise APIClientError(INSTALL_HINT) from None

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": to_anthropic_content(user_prompt, user_content)}],
            )
        except anthropic.AuthenticationError:
            raise APIClientError("API Key 无效、过期或未被授权 (HTTP 401)。", status=401) from None
        except anthropic.PermissionDeniedError:
            raise APIClientError("API Key 没有访问该模型的权限 (HTTP 403)。", status=403) from None
        except anthropic.NotFoundError:
            raise APIClientError("模型 ID 或 API 地址不正确 (HTTP 404)。", status=404) from None
        except anthropic.RateLimitError:
            raise APIClientError("请求过快或额度不足 (HTTP 429)。", status=429) from None
        except anthropic.BadRequestError:
            raise APIClientError("请求不被 Claude API 接受 (HTTP 400)。未显示响应正文以避免泄露敏感内容。", status=400) from None
        except anthropic.APIStatusError as exc:
            raise APIClientError(f"Claude API 返回错误 (HTTP {exc.status_code})。", status=exc.status_code) from None
        except anthropic.APITimeoutError:
            raise APIClientError(f"API 请求超过 {self.timeout_seconds} 秒仍未完成") from None
        except anthropic.APIConnectionError:
            raise APIClientError("无法连接到已授权的 API 主机。") from None

        self.last_usage = _usage_dict(getattr(response, "usage", None))
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            raise APIClientError("Claude 拒绝了该请求 (stop_reason=refusal)。")
        text = "\n".join(
            block.text for block in getattr(response, "content", []) or [] if getattr(block, "type", "") == "text"
        ).strip()
        if stop_reason == "max_tokens":
            raise APIClientError(f"输出达到 max_tokens={self.max_tokens} 上限被截断。")
        if not text:
            raise APIClientError("Claude 响应中没有文本内容。")
        return text
