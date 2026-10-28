"""OpenAI-compatible Chat Completions client used by the ComfyUI node."""

from __future__ import annotations

import json
import ipaddress
import os
import re
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any, Callable, Dict, Optional


class APIClientError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


Transport = Callable[[str, Dict[str, str], Dict[str, Any], int], Dict[str, Any]]

TRUSTED_HOSTS_ENV = "BUFF_AI_TRUSTED_API_HOSTS"
API_KEY_ENV_VARS_ENV = "BUFF_AI_API_KEY_ENV_VARS"
DEFAULT_API_KEY_ENV = "BUFF_AI_API_KEY"
_SECRET_TOKEN = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"
)


def _normalize_hostname(hostname: str) -> str:
    host = str(hostname or "").strip().rstrip(".").lower()
    if not host:
        raise ValueError("empty host")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        normalized = host.encode("idna").decode("ascii")
        if len(normalized) > 253 or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in normalized.split(".")
        ):
            raise ValueError("invalid host")
        return normalized


def _is_loopback(hostname: str) -> bool:
    normalized = _normalize_hostname(hostname)
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if getattr(address, "ipv4_mapped", None) is not None:
        address = address.ipv4_mapped
    return address.is_loopback


def parse_trusted_api_hosts(value: str | None = None) -> set[tuple[str, int]]:
    """Parse the server-owned comma-separated host[:port] trust list."""
    raw = os.getenv(TRUSTED_HOSTS_ENV, "") if value is None else str(value)
    trusted: set[tuple[str, int]] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            parsed = urlsplit("//" + entry)
            if parsed.hostname is None or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise ValueError
            hostname = _normalize_hostname(parsed.hostname)
            port = parsed.port if parsed.port is not None else 443
        except (ValueError, UnicodeError):
            raise APIClientError("BUFF_AI_TRUSTED_API_HOSTS contains an invalid host entry") from None
        if not (1 <= port <= 65535):
            raise APIClientError("BUFF_AI_TRUSTED_API_HOSTS contains an invalid port")
        trusted.add((hostname, port))
    return trusted


def validate_api_endpoint(base_url: str, trusted_hosts: str | None = None) -> str:
    """Validate scheme, local HTTP use, userinfo, and explicit host trust."""
    value = str(base_url or "").strip()
    try:
        parsed = urlsplit(value)
        hostname = _normalize_hostname(parsed.hostname or "")
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme.lower() == "https" else 80)
    except (ValueError, UnicodeError):
        raise APIClientError("API 地址格式无效；请检查主机名和端口。") from None

    scheme = parsed.scheme.lower()
    if scheme not in {"https", "http"} or not parsed.netloc or not hostname:
        raise APIClientError("API 地址必须使用 http:// 或 https:// 并包含主机名。")
    if parsed.username is not None or parsed.password is not None:
        raise APIClientError("API 地址中不能包含用户名或密码；请使用环境变量配置凭据。")
    if parsed.fragment:
        raise APIClientError("API 地址不能包含片段标记。")
    if not (1 <= port <= 65535):
        raise APIClientError("API 地址端口无效。")
    if scheme == "http" and not _is_loopback(hostname):
        raise APIClientError("远程 API 地址必须使用 HTTPS；HTTP 仅允许回环地址。")

    if (hostname, port) not in parse_trusted_api_hosts(trusted_hosts):
        raise APIClientError(
            f"API 主机 {hostname}:{port} 未获本机信任。请将其加入 {TRUSTED_HOSTS_ENV}。"
        )
    return value


def allowed_api_key_env_vars(value: str | None = None) -> set[str]:
    """Return environment-variable names explicitly allowed by the server."""
    raw = os.getenv(API_KEY_ENV_VARS_ENV, DEFAULT_API_KEY_ENV) if value is None else str(value)
    names = {DEFAULT_API_KEY_ENV}
    for name in raw.split(","):
        name = name.strip()
        if not name:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise APIClientError(f"{API_KEY_ENV_VARS_ENV} contains an invalid variable name")
        names.add(name)
    return names


def validate_api_key_env_name(name: str, allowed_names: str | None = None) -> str:
    value = str(name or DEFAULT_API_KEY_ENV).strip() or DEFAULT_API_KEY_ENV
    if value not in allowed_api_key_env_vars(allowed_names):
        raise APIClientError(
            f"API Key 环境变量名未获本机授权。默认允许 {DEFAULT_API_KEY_ENV}；自定义名称需加入 {API_KEY_ENV_VARS_ENV}。"
        )
    return value


def sanitize_url(url: str) -> str:
    """Remove URL userinfo and redact credential-like query parameters."""
    try:
        parsed = urlsplit(str(url or ""))
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc += f":{parsed.port}"
        # Query values are omitted from diagnostics altogether: providers use
        # inconsistent parameter names for credentials and signed URLs.
        query = urlencode(
            [(key, "[REDACTED]") for key, _ in parse_qsl(parsed.query, keep_blank_values=True)]
        )
        clean = urlunsplit((parsed.scheme, netloc, parsed.path, query, ""))
        return _SECRET_TOKEN.sub("[REDACTED]", clean)
    except (ValueError, UnicodeError):
        return "[invalid API URL]"


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        *,
        transport: Optional[Transport] = None,
        trusted_hosts: str | None = None,
    ):
        self.base_url = str(base_url or "").strip()
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout_seconds = int(timeout_seconds)
        self.transport = transport or self._urllib_transport
        self.trusted_hosts = trusted_hosts

    @staticmethod
    def build_chat_url(base_url: str) -> str:
        base = str(base_url or "").strip().rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        user_content: Any | None = None,
        temperature: float = 0.6,
        prefer_json_mode: bool = True,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": float(temperature),
            # Explicitly disable SSE streaming. Some OpenAI-compatible relay
            # stacks otherwise route the request through their streaming path,
            # which can surface misleading `client_gone` states.
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content if user_content is not None else user_prompt},
            ],
        }
        if prefer_json_mode:
            payload["response_format"] = {"type": "json_object"}

        first_payload = dict(payload)
        try:
            data = self._request(first_payload)
        except APIClientError as exc:
            low = str(exc).lower()
            can_retry = prefer_json_mode and (
                exc.status in {400, 422}
                or "response_format" in low
                or "json_object" in low
            )
            if not can_retry:
                raise
            retry_payload = dict(payload)
            retry_payload.pop("response_format", None)
            data = self._request(retry_payload)

        return self._extract_content(data)

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.base_url:
            raise APIClientError("api_base_url is empty")
        if not self.model:
            raise APIClientError("api_model is empty")
        validate_api_endpoint(self.base_url, self.trusted_hosts)
        if not self.api_key:
            raise APIClientError("api_key is empty")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "BUFF-AI-Director/3.2.1",
        }
        return self.transport(
            self.build_chat_url(self.base_url),
            headers,
            payload,
            self.timeout_seconds,
        )

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise APIClientError("API response is not compatible with Chat Completions.") from exc

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = []
            for part in content:
                if isinstance(part, str):
                    chunks.append(part)
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
            if chunks:
                return "\n".join(chunks)
        raise APIClientError("API response content is not recognized as text.")

    class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
        """Reject all redirects so Authorization is never forwarded on redirect."""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    @staticmethod
    def _urllib_transport(
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout: int,
    ) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            opener = urllib.request.build_opener(OpenAICompatibleClient._RejectRedirectHandler())
            with opener.open(request, timeout=timeout) as response:
                content_type = str(response.headers.get("Content-Type", "") or "").lower()
                if "text/event-stream" in content_type:
                    # Compatibility fallback for relays that return SSE even when
                    # the request explicitly says stream=false. Stop at [DONE]
                    # instead of waiting for the TCP connection to close.
                    chunks = []
                    last_obj: Dict[str, Any] | None = None
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_text = line[5:].strip()
                        if data_text == "[DONE]":
                            break
                        try:
                            event = json.loads(data_text)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(event, dict):
                            continue
                        if isinstance(event.get("error"), dict):
                            raise APIClientError("API returned an SSE error response.")
                        last_obj = event
                        try:
                            choice = event.get("choices", [])[0]
                        except Exception:
                            choice = {}
                        if isinstance(choice, dict):
                            delta = choice.get("delta")
                            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                                chunks.append(delta["content"])
                            message = choice.get("message")
                            if isinstance(message, dict) and isinstance(message.get("content"), str):
                                chunks.append(message["content"])
                    if chunks:
                        return {"choices": [{"message": {"content": "".join(chunks)}}]}
                    if isinstance(last_obj, dict):
                        return last_obj
                    raise APIClientError("API returned an empty SSE stream")
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            hints = {
                400: "请求格式不被中转/API 接受",
                401: "API Key 无效、过期或未被授权",
                403: "API Key 没有访问该模型/接口的权限",
                404: "API 地址或 /v1/chat/completions 路径不正确",
                408: "中转/API 请求超时",
                409: "中转/API 返回冲突",
                422: "请求参数不兼容",
                429: "额度不足、并发限制或请求过快",
                500: "中转或上游模型内部错误",
                502: "中转无法从上游取得有效响应",
                503: "中转或上游模型暂时不可用",
                504: "中转等待上游模型超时",
            }
            hint = hints.get(exc.code, "API 返回错误")
            raise APIClientError(
                f"{hint} (HTTP {exc.code}). 未显示服务端响应正文以避免泄露敏感内容。", status=exc.code
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError,)):
                raise APIClientError(f"API 请求超过 {timeout} 秒仍未完成") from None
            raise APIClientError("无法连接到已授权的 API 主机。") from None
        except (TimeoutError, OSError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
                raise APIClientError(f"API 请求超过 {timeout} 秒仍未完成") from exc
            raise APIClientError("API 连接异常；详细系统错误已省略。") from None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise APIClientError("API returned a non-JSON response; response body omitted.") from exc
        if not isinstance(parsed, dict):
            raise APIClientError("API returned a JSON value that is not an object")
        return parsed
