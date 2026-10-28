"""Language and literal-lock helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping


_CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF]")


def contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(str(text or "")))


def source_language(text: str) -> str:
    return "Chinese" if contains_cjk(text) else "English"


def resolve_user_field(user_text: str, ai_text: str, *, exact: bool = False) -> str:
    user = str(user_text or "").strip()
    ai = str(ai_text or "").strip()
    if exact and user:
        return user
    if not user:
        return ai
    if not contains_cjk(user):
        return user
    return ai or user


def parse_dialogue_source(text: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        speaker = ""
        dialogue = line
        parts = re.split(r"\s*[|｜]\s*", line, maxsplit=1)
        if len(parts) == 2 and parts[0].strip():
            speaker, dialogue = parts[0].strip(), parts[1].strip()
        else:
            colon = re.match(r"^([^:：]{1,80})[:：]\s*(.+)$", line)
            if colon:
                speaker, dialogue = colon.group(1).strip(), colon.group(2).strip()
        entries.append(
            {
                "source_index": len(entries) + 1,
                "speaker": speaker,
                "text": dialogue,
            }
        )
    return entries


def collect_text_inputs(names: Iterable[str], values: Mapping[str, Any]) -> Dict[str, str]:
    return {name: str(values.get(name, "") or "").strip() for name in names}


def extract_json_object(text: str) -> Dict[str, Any] | None:
    source = str(text or "").strip()
    source = re.sub(r"^\s*```(?:json)?\s*", "", source, flags=re.IGNORECASE)
    source = re.sub(r"\s*```\s*$", "", source)
    try:
        import json

        parsed = json.loads(source)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    start = source.find("{")
    end = source.rfind("}")
    if start >= 0 and end > start:
        try:
            import json

            parsed = json.loads(source[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None
