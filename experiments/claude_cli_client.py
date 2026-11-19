"""Run experiment requests through the Claude Code CLI (``claude -p``).

This lets a researcher run pilot sweeps on their own Claude subscription
instead of a paid API key. It is an experiment backend only and is not offered
by the ComfyUI node.

Each call runs ``claude -p`` once, with:
- the node's system prompt replacing Claude Code's default (``--system-prompt-file``),
- no tools (``--tools ""``) and no MCP servers (``--strict-mcp-config``),
- an empty temporary working directory, so no project files are loaded,
- no saved session (``--no-session-persistence``),
- JSON output, from which the text and token usage are read.

Claude Code still adds a little context of its own (about 1.3k input tokens
were observed for a one-line prompt), so records from this backend are a
different condition from direct API runs and should not be pooled with them.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import APIClientError  # noqa: E402

PROVIDER_LABEL = "Claude Code CLI"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
# Model IDs or aliases only; a leading "-" could be read as a CLI flag.
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,99}$")


class ClaudeCodeCLIClient:
    def __init__(
        self,
        model: str,
        timeout_seconds: int,
        *,
        effort: Optional[str] = None,
        executable: str = "claude",
        runner: Any = None,
    ):
        model = str(model or "").strip()
        if not _MODEL_RE.match(model):
            raise APIClientError(f"Invalid model name for the Claude Code CLI: {model!r}")
        if effort is not None and effort not in EFFORT_LEVELS:
            raise APIClientError(f"Invalid effort {effort!r}; use one of {EFFORT_LEVELS}.")
        self.model = model
        self.timeout_seconds = int(timeout_seconds)
        self.effort = effort
        self.executable = executable
        self.runner = runner or subprocess.run
        self.last_usage: Optional[Dict[str, int]] = None
        self.last_served_model: Optional[str] = None

    def build_command(self, system_prompt_file: Path) -> list[str]:
        command = [
            self.executable,
            "-p",
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt-file", str(system_prompt_file),
            "--tools", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if self.effort:
            command += ["--effort", self.effort]
        return command

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        user_content: Any | None = None,
        temperature: float = 0.6,
        prefer_json_mode: bool = True,
    ) -> str:
        del temperature, prefer_json_mode  # Not controllable through the CLI.
        self.last_usage = None
        self.last_served_model = None
        if isinstance(user_content, list) and any(
            isinstance(part, dict) and part.get("type") == "image_url" for part in user_content
        ):
            raise APIClientError("The Claude Code CLI backend does not support reference images.")

        with tempfile.TemporaryDirectory(prefix="buff-cli-") as workdir:
            system_file = Path(workdir) / "system_prompt.txt"
            system_file.write_text(system_prompt, encoding="utf-8")
            try:
                completed = self.runner(
                    self.build_command(system_file),
                    input=user_prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_seconds,
                    cwd=workdir,
                )
            except subprocess.TimeoutExpired:
                raise APIClientError(f"Claude Code CLI did not finish within {self.timeout_seconds} seconds.") from None
            except FileNotFoundError:
                raise APIClientError(f"Claude Code CLI executable not found: {self.executable}") from None

        try:
            data = json.loads(completed.stdout or "")
        except ValueError:
            # stderr and stdout are not echoed: they can contain prompt text.
            raise APIClientError(f"Claude Code CLI returned no JSON result (exit code {completed.returncode}).") from None
        if not isinstance(data, dict):
            raise APIClientError("Claude Code CLI returned an unexpected result.")

        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt = sum(int(usage.get(key) or 0) for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        completion = int(usage.get("output_tokens") or 0)
        self.last_usage = {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion} if usage else None
        models = data.get("modelUsage")
        if isinstance(models, dict) and models:
            self.last_served_model = next(iter(models))

        if completed.returncode != 0 or data.get("is_error"):
            raise APIClientError(
                f"Claude Code CLI request failed ({data.get('subtype') or 'error'}, exit code {completed.returncode})."
            )
        stop_reason = data.get("stop_reason")
        if stop_reason == "refusal":
            raise APIClientError("Claude declined the request (stop_reason=refusal).")
        if stop_reason == "max_tokens":
            raise APIClientError("Claude Code CLI output hit the token limit and was truncated.")
        text = data.get("result")
        if not isinstance(text, str) or not text.strip():
            raise APIClientError("Claude Code CLI returned an empty result.")
        return text
