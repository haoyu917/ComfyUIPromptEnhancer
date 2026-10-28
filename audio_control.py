"""Strict speech whitelisting and MiniMax H3 dialogue compilation."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    from .language_policy import parse_dialogue_source
except ImportError:
    from language_policy import parse_dialogue_source


AUDIO_POLICIES = (
    "Strict Dialogue Only",
    "Dialogue + Exact Offscreen",
    "SFX Only",
    "Full Auto Audio",
)

_SPEECH_TERMS = re.compile(
    r"\b(?:speech|spoken|voice|voices|dialogue|dialog|narration|narrator|whisper(?:ing|s)?|"
    r"talk(?:ing|s)?|conversation|chat(?:ting)?|chant(?:ing|s)?|sing(?:ing|s)?|"
    r"shout(?:ing|s)?|yell(?:ing|s)?|words?|announcement|announces?|says?|said)\b"
    r"|(?:说话|对白|人声|旁白|低语|耳语|交谈|喊话|喊声|叫喊|歌唱|唱歌|台词|播报|宣告|对话)",
    re.IGNORECASE,
)


def parse_exact_offscreen_dialogue(text: str) -> List[Dict[str, Any]]:
    rows = parse_dialogue_source(text)
    return [
        {
            "source_index": int(row.get("source_index", idx) or idx),
            "speaker": str(row.get("speaker", "") or "").strip(),
            "text": str(row.get("text", "") or "").strip(),
            "offscreen": True,
        }
        for idx, row in enumerate(rows, start=1)
        if str(row.get("text", "") or "").strip()
    ]


def _speaker_key(row: Mapping[str, Any]) -> str:
    speaker = str(row.get("speaker", "") or "").strip()
    if speaker:
        return speaker
    return "Unspecified speaker"


def assign_speaker_ids(
    dialogues: Sequence[Mapping[str, Any]],
    offscreen_dialogues: Sequence[Mapping[str, Any]],
) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for row in list(dialogues or []) + list(offscreen_dialogues or []):
        speaker = _speaker_key(row)
        if speaker not in mapping:
            mapping[speaker] = f"S{len(mapping) + 1}"
    return mapping


def detect_h3_language_tag(text: str) -> str:
    value = str(text or "")
    if re.search(r"[\u3040-\u30ff]", value):
        return "Japanese"
    if re.search(r"[\uac00-\ud7af]", value):
        return "Korean"
    if re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", value):
        return "Chinese"
    if re.search(r"[\u0400-\u04ff]", value):
        return "Russian"
    if re.search(r"[\u0600-\u06ff]", value):
        return "Arabic"
    if re.search(r"[\u0e00-\u0e7f]", value):
        return "Thai"
    return "English"


def _normalized_dialogue_from_allowed(
    source: Mapping[str, Any],
    ai_row: Mapping[str, Any] | None = None,
    *,
    global_direction: str = "",
) -> Dict[str, Any]:
    ai = dict(ai_row or {})
    return {
        "source_index": int(source.get("source_index", 0) or 0),
        "speaker": str(source.get("speaker", "") or "").strip(),
        "voice_direction": str(ai.get("voice_direction", "") or global_direction or "").strip(),
        "state": str(ai.get("state", "") or "").strip(),
        "tone": str(ai.get("tone", "") or "").strip(),
        "text": str(source.get("text", "") or "").strip(),
    }


def _sanitize_sound_text(value: Any) -> Any:
    """Remove clauses that can be interpreted as verbal content under strict policies."""
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            cleaned = _sanitize_sound_text(item)
            if cleaned not in (None, "", [], {}):
                out[key] = cleaned
        return out
    if isinstance(value, list):
        cleaned_items = [_sanitize_sound_text(item) for item in value]
        return [item for item in cleaned_items if item not in (None, "", [], {})]
    text = str(value or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?。！？])\s+|\s*[;,；，]\s*|\n+", text)
    keep = [part.strip() for part in parts if part.strip() and not _SPEECH_TERMS.search(part)]
    return ", ".join(keep)


def _match_allowed_dialogues(
    ai_rows: Iterable[Mapping[str, Any]],
    allowed: Sequence[Mapping[str, Any]],
    *,
    global_direction: str = "",
) -> tuple[List[Dict[str, Any]], set[int]]:
    by_index = {
        int(row.get("source_index", 0) or 0): row
        for row in allowed
        if int(row.get("source_index", 0) or 0) > 0
    }
    used: set[int] = set()
    out: List[Dict[str, Any]] = []
    for ai_row in ai_rows or []:
        if not isinstance(ai_row, Mapping):
            continue
        try:
            idx = int(ai_row.get("source_index", 0) or 0)
        except Exception:
            idx = 0
        if idx not in by_index or idx in used:
            continue
        out.append(
            _normalized_dialogue_from_allowed(
                by_index[idx], ai_row, global_direction=global_direction
            )
        )
        used.add(idx)
    return out, used


def enforce_audio_policy(
    storyboard: Mapping[str, Any],
    *,
    policy: str,
    dialogue_entries: Sequence[Mapping[str, Any]],
    offscreen_entries: Sequence[Mapping[str, Any]],
    strict_speech_lock: bool,
    global_dialogue_direction: str = "",
) -> Dict[str, Any]:
    policy = policy if policy in AUDIO_POLICIES else "Dialogue + Exact Offscreen"
    out = copy.deepcopy(dict(storyboard or {}))
    shots = [dict(shot) for shot in out.get("shots", []) if isinstance(shot, Mapping)]
    out["shots"] = shots
    out["audio_policy"] = policy
    out["strict_speech_lock"] = bool(strict_speech_lock)

    if policy == "Full Auto Audio" and not strict_speech_lock:
        return out

    # Under every strict policy, soundscape fields must never contain verbal content.
    if strict_speech_lock or policy != "Full Auto Audio":
        out["sound_design"] = _sanitize_sound_text(out.get("sound_design", ""))
        out["offscreen_audio"] = "" if policy != "Full Auto Audio" else out.get("offscreen_audio", "")
        for shot in shots:
            shot["sound_layers"] = _sanitize_sound_text(shot.get("sound_layers", ""))

    if policy == "SFX Only":
        for shot in shots:
            shot["dialogues"] = []
            shot["exact_offscreen_dialogues"] = []
            shot["offscreen_events"] = []
        return out

    if policy == "Full Auto Audio":
        # Strict lock + Full Auto means keep AI audio but append a guard at render time.
        return out

    allowed_dialogues = list(dialogue_entries or [])
    used_dialogue: set[int] = set()
    for shot in shots:
        filtered, used = _match_allowed_dialogues(
            shot.get("dialogues", []),
            allowed_dialogues,
            global_direction=global_dialogue_direction,
        )
        shot["dialogues"] = filtered
        used_dialogue.update(used)
        # AI-authored off-screen events are not allowed to carry speech under strict whitelist policies.
        shot["offscreen_events"] = []
        shot["exact_offscreen_dialogues"] = []

    # Reinsert any user dialogue that the AI omitted, using the longest shot as the safest fallback.
    if shots:
        fallback = max(shots, key=lambda shot: float(shot.get("duration", 0.0) or 0.0))
        for row in allowed_dialogues:
            idx = int(row.get("source_index", 0) or 0)
            if idx > 0 and idx not in used_dialogue:
                fallback.setdefault("dialogues", []).append(
                    _normalized_dialogue_from_allowed(
                        row, None, global_direction=global_dialogue_direction
                    )
                )
                used_dialogue.add(idx)

    if policy == "Dialogue + Exact Offscreen" and shots:
        # Exact off-screen lines are user-owned. Put them in the final shot by default;
        # users can control timing through an explicit shot plan and narrative context.
        target = shots[-1]
        target["exact_offscreen_dialogues"] = [copy.deepcopy(dict(row)) for row in offscreen_entries or []]

    return out


def compile_h3_dialogue_blocks(
    dialogues: Sequence[Mapping[str, Any]],
    offscreen_dialogues: Sequence[Mapping[str, Any]],
    *,
    strict_speech_lock: bool,
    speaker_ids: Mapping[str, str] | None = None,
) -> str:
    mapping = dict(speaker_ids or assign_speaker_ids(dialogues, offscreen_dialogues))
    lines: List[str] = []
    for row in dialogues or []:
        speaker = _speaker_key(row)
        speaker_id = mapping.setdefault(speaker, f"S{len(mapping) + 1}")
        text = str(row.get("text", "") or "")
        if not text:
            continue
        language = detect_h3_language_tag(text)
        delivery = str(row.get("voice_direction", "") or "").strip()
        delivery_text = f" with {delivery}" if delivery else ""
        lines.append(
            f"{speaker} ({speaker_id}) says{delivery_text}: <d>[{language}]{text}</d>"
        )

    for row in offscreen_dialogues or []:
        speaker = _speaker_key(row)
        speaker_id = mapping.setdefault(speaker, f"S{len(mapping) + 1}")
        text = str(row.get("text", "") or "")
        if not text:
            continue
        language = detect_h3_language_tag(text)
        lines.append(
            f"{speaker} ({speaker_id}) says in an off-screen voiceover: "
            f"<d>[{language}]{text}</d> The visible on-screen characters' lips remain completely closed during this off-screen line."
        )

    if strict_speech_lock:
        lines.extend(
            [
                "SPEECH LOCK:",
                "Only the exact lines enclosed inside <d>...</d> are allowed to be spoken.",
                "Do not generate any additional dialogue, narration, ad-lib, muttering, whispered words, chanting, crowd speech, background conversation, or invented vocal content.",
            ]
        )
    return "\n".join(lines).strip()


def collect_storyboard_speaker_ids(storyboard: Mapping[str, Any]) -> Dict[str, str]:
    dialogues: List[Mapping[str, Any]] = []
    offscreen: List[Mapping[str, Any]] = []
    for shot in storyboard.get("shots", []) if isinstance(storyboard.get("shots"), list) else []:
        if not isinstance(shot, Mapping):
            continue
        dialogues.extend(row for row in shot.get("dialogues", []) if isinstance(row, Mapping))
        offscreen.extend(row for row in shot.get("exact_offscreen_dialogues", []) if isinstance(row, Mapping))
    return assign_speaker_ids(dialogues, offscreen)
