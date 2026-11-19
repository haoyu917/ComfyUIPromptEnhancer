"""Opt-in research run logging for BUFF AI Director.

Each node execution can append one JSON line describing the configuration that
was used (module states and main parameters), features of the request, the
cost of each language-model call, and the outcome. The resulting JSONL file is
the raw information table for offline analysis of skill (module) selection.

Design rules:
- Logging is off unless the workflow selects a ``research_log`` level.
- The output directory comes from the machine-local environment variable
  ``BUFF_AI_RESEARCH_LOG_DIR`` (or the plugin's own ``research_logs`` folder),
  never from the workflow, so an imported workflow cannot choose where files
  are written.
- API keys, base URLs, and trusted-host lists are never recorded.
- ``Metrics only`` records a SHA-256 digest of the prompt instead of its text.
  ``Full text`` additionally stores the prompt and the generated outputs.
- A logging failure never breaks prompt generation.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

RESEARCH_LOG_DIR_ENV = "BUFF_AI_RESEARCH_LOG_DIR"
RESEARCH_LOG_FILENAME = "runs.jsonl"
RESEARCH_LOG_LEVELS = ("Off", "Metrics only", "Full text")
RECORD_SCHEMA_VERSION = 1

_PACKAGE_DIR = Path(__file__).resolve().parent
_WRITE_LOCK = threading.Lock()
_CJK_RE = re.compile(r"[㐀-鿿豈-﫿]")
_MAX_ERROR_CHARS = 300

# Configuration keys copied into every record. Anything that could carry a
# credential or a private endpoint (api_key, api_base_url, trusted hosts) is
# intentionally absent.
CONFIG_FIELDS = (
    "director_preset",
    "interface_mode",
    "generation_mode",
    "target_model",
    "language",
    "mode",
    "duration",
    "aspect_ratio",
    "visual_style",
    "camera_style",
    "action_level",
    "story_curve",
    "shot_mode",
    "continuity_lock",
    "project_format",
    "genre",
    "directing_style",
    "audio_policy",
    "strict_speech_lock",
    "temperature",
    "api_model",
)


def _plugin_version() -> str:
    try:
        return (_PACKAGE_DIR / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def normalize_log_level(value: Any) -> str:
    text = str(value or "Off").strip()
    return text if text in RESEARCH_LOG_LEVELS else "Off"


def resolve_log_path(env_value: Optional[str] = None) -> Path:
    """Return the JSONL file path chosen by the local machine configuration."""

    raw = os.getenv(RESEARCH_LOG_DIR_ENV, "") if env_value is None else env_value
    directory = Path(raw).expanduser() if str(raw or "").strip() else _PACKAGE_DIR / "research_logs"
    return directory / RESEARCH_LOG_FILENAME


def _usage_dict(usage: Any) -> Optional[Dict[str, int]]:
    if not isinstance(usage, Mapping):
        return None
    result: Dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            result[key] = int(value)
    return result or None


def _filled(values: Mapping[str, Any], names: Iterable[str]) -> List[str]:
    return sorted(name for name in names if str(values.get(name, "") or "").strip())


class RunRecorder:
    """Collects facts about one node execution and writes them as one JSON line.

    A disabled recorder accepts every call and does nothing, so the node can
    call it unconditionally.
    """

    def __init__(self, level: Any = "Off", tag: Any = "", log_path: Optional[Path] = None):
        self.level = normalize_log_level(level)
        self.tag = str(tag or "").strip()[:200]
        self.log_path = log_path
        self.started = time.perf_counter()
        self.record: Dict[str, Any] = {}
        self.calls: List[Dict[str, Any]] = []
        self.written = False
        if self.enabled:
            self.record = {
                "schema_version": RECORD_SCHEMA_VERSION,
                "run_id": uuid.uuid4().hex,
                "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                "plugin_version": _plugin_version(),
                "log_level": self.level,
                "tag": self.tag,
            }

    @property
    def enabled(self) -> bool:
        return self.level != "Off"

    @property
    def full_text(self) -> bool:
        return self.level == "Full text"

    # ---- collection -----------------------------------------------------

    def set_request(
        self,
        *,
        config: Mapping[str, Any],
        inputs: Mapping[str, Any],
        module_states: Mapping[str, str],
        guidance_inputs: Iterable[str],
        dialogue_count: int,
        offscreen_dialogue_count: int,
        reference_count: int,
        entity_count: int,
        locked_shot_count: int,
        locked_times: bool,
        desired_shots: int,
    ) -> None:
        if not self.enabled:
            return
        prompt = str(config.get("prompt", "") or "")
        self.record["config"] = {key: config.get(key) for key in CONFIG_FIELDS}
        self.record["module_states"] = dict(module_states)
        self.record["features"] = {
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_chars": len(prompt),
            "prompt_has_cjk": bool(_CJK_RE.search(prompt)),
            "dialogue_count": int(dialogue_count),
            "offscreen_dialogue_count": int(offscreen_dialogue_count),
            "reference_count": int(reference_count),
            "entity_count": int(entity_count),
            "locked_shot_count": int(locked_shot_count),
            "locked_times": bool(locked_times),
            "desired_shots": int(desired_shots),
            "has_keywords": bool(str(inputs.get("keywords", "") or "").strip()),
            "has_must_keep": bool(str(config.get("must_keep", "") or "").strip()),
            "has_must_avoid": bool(str(config.get("must_avoid", "") or "").strip()),
            # Set-valued attribute: which module guidance fields the user filled.
            "filled_guidance": _filled(inputs, guidance_inputs),
        }
        if self.full_text:
            self.record["prompt_text"] = prompt

    def add_call(
        self,
        stage: str,
        *,
        elapsed_s: float,
        ok: bool,
        system_chars: int = 0,
        user_chars: int = 0,
        response_chars: int = 0,
        usage: Any = None,
        json_ok: Optional[bool] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        if not self.enabled:
            return
        call: Dict[str, Any] = {
            "stage": stage,
            "elapsed_s": round(float(elapsed_s), 3),
            "ok": bool(ok),
            "system_chars": int(system_chars),
            "user_chars": int(user_chars),
            "response_chars": int(response_chars),
            "usage": _usage_dict(usage),
        }
        if json_ok is not None:
            call["json_ok"] = bool(json_ok)
        if error is not None:
            call["error_type"] = type(error).__name__
        self.calls.append(call)

    def succeed(
        self,
        *,
        storyboard: Mapping[str, Any],
        enhanced_prompt: str,
        shot_prompts: str,
        quality_applied: bool,
    ) -> None:
        if not self.enabled:
            return
        shots = storyboard.get("shots", []) if isinstance(storyboard, Mapping) else []
        self.record["outcome"] = {
            "status": "ok",
            "shot_count": len(shots) if isinstance(shots, list) else 0,
            "quality_applied": bool(quality_applied),
            "enhanced_prompt_chars": len(enhanced_prompt or ""),
            "shot_prompts_chars": len(shot_prompts or ""),
        }
        if self.full_text:
            self.record["outputs"] = {
                "storyboard": storyboard,
                "enhanced_prompt": enhanced_prompt,
                "shot_prompts": shot_prompts,
            }

    def fail(self, stage: str, error: BaseException) -> None:
        if not self.enabled:
            return
        self.record["outcome"] = {
            "status": "error",
            "error_stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error)[:_MAX_ERROR_CHARS],
        }

    # ---- output ---------------------------------------------------------

    def build_record(self) -> Dict[str, Any]:
        record = dict(self.record)
        record["calls"] = list(self.calls)
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        usage_complete = bool(self.calls)
        for call in self.calls:
            usage = call.get("usage")
            if not usage:
                usage_complete = False
                continue
            for key in totals:
                totals[key] += int(usage.get(key, 0))
        record["totals"] = {
            "api_calls": len(self.calls),
            "api_elapsed_s": round(sum(call["elapsed_s"] for call in self.calls), 3),
            "wall_elapsed_s": round(time.perf_counter() - self.started, 3),
            "usage_complete": usage_complete,
            **totals,
        }
        return record

    def write(self) -> Optional[Path]:
        """Append the record once. Returns the file path, or None if skipped."""

        if not self.enabled or self.written:
            return None
        if "config" not in self.record:
            # The run failed before a request was assembled (for example an
            # invalid shot plan). That is an input mistake, not an outcome of
            # a configuration, so nothing is recorded.
            return None
        self.written = True
        path = self.log_path or resolve_log_path()
        try:
            line = json.dumps(self.build_record(), ensure_ascii=False, default=str)
            path.parent.mkdir(parents=True, exist_ok=True)
            with _WRITE_LOCK:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except Exception as exc:  # Logging must never break generation.
            print(f"[BUFF AI] 研究记录写入失败（不影响提示词生成）：{type(exc).__name__}: {exc}", flush=True)
            return None
        return path
