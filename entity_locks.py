"""Canonical @entity-name locks for BUFF AI director output.

The video prompt is easier for downstream reference/LoRA systems to consume when every
named character, prop and location is referenced by one stable token such as
``@铁角妖王`` or ``@石桌``.  This module builds those tokens from explicit character
names, dialogue speakers and reference-image names, then applies them deterministically
after the LLM pass while preserving literal dialogue text and LoRA keywords.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    from .reference_images import parse_reference_manifest
except ImportError:  # pragma: no cover - standalone test fallback
    from reference_images import parse_reference_manifest


# Short forms that are useful in natural Chinese prose but are unsafe for reference
# binding because they can drift away from the exact named entity.  Only derive an
# alias when the canonical entity actually ends with one of these known role/object
# words.  Exact full names are always handled regardless of this list.
_SAFE_SUFFIX_ALIASES = (
    "妖王", "女妖", "国王", "女王", "王后", "王子", "公主", "皇帝", "皇后",
    "将军", "长老", "师父", "师尊", "掌门", "侍女", "侍卫", "护卫", "武士",
    "门口", "大门", "城门", "石桌", "祭坛", "王座", "宝座", "石室", "妖谷",
    "山谷", "森林", "洞穴", "房间", "大厅", "宫殿", "城堡", "神殿", "街道",
    "长剑", "宝剑", "战刀", "飞船", "汽车", "车辆",
)

_GENERIC_REFERENCE_NAMES = {
    "参考图", "reference", "reference image", "image", "图像", "图片",
}


def _strip_entity_marker(value: Any) -> str:
    text = str(value or "").strip()
    while text.startswith("@"):
        text = text[1:].strip()
    return text


def _reference_entity_name(note: Any) -> str:
    """Extract the entity token portion from a manifest note.

    Manual manifests commonly use ``1=@角色 | 锁定服装``.  Only the left side is the
    entity name; the role description must not become part of the @ token.
    """
    text = str(note or "").strip()
    if not text:
        return ""
    text = re.split(r"\s*[|｜]\s*", text, maxsplit=1)[0].strip()
    bare = _strip_entity_marker(text)
    if not bare:
        return ""
    lowered = bare.lower()
    if lowered in _GENERIC_REFERENCE_NAMES or re.fullmatch(r"(?:参考图|reference(?: image)?)\s*\d+", lowered, re.I):
        return ""
    return bare


def _split_name_list(text: Any) -> List[str]:
    source = str(text or "").strip()
    if not source:
        return []
    parts = re.split(r"[\n\r,，;；]+", source)
    result: List[str] = []
    for raw in parts:
        bare = _strip_entity_marker(raw)
        if bare and bare not in result:
            result.append(bare)
    return result


def canonical_token(name: Any) -> str:
    bare = _strip_entity_marker(name)
    return f"@{bare}" if bare else ""


def canonicalize_name_list(text: Any) -> str:
    return ", ".join(canonical_token(name) for name in _split_name_list(text) if canonical_token(name))


def build_entity_registry(
    *,
    character_names: Any = "",
    reference_manifest: Any = "",
    dialogue_entries: Sequence[Mapping[str, Any]] | None = None,
) -> List[str]:
    """Return canonical bare entity names in stable priority order."""
    names: List[str] = []

    def add(name: Any) -> None:
        bare = _strip_entity_marker(name)
        if bare and bare not in names:
            names.append(bare)

    for name in _split_name_list(character_names):
        add(name)

    for row in dialogue_entries or []:
        if isinstance(row, Mapping):
            add(row.get("speaker", ""))

    manifest = parse_reference_manifest(str(reference_manifest or ""))
    for index in sorted(manifest):
        add(_reference_entity_name(manifest[index]))

    return names


def entity_lock_instruction(entities: Iterable[str]) -> str:
    tokens = [canonical_token(name) for name in entities if canonical_token(name)]
    if not tokens:
        return "- No named @entity locks were supplied."
    joined = ", ".join(tokens)
    return (
        f"- Canonical named entities for this request: {joined}.\n"
        "- In EVERY production/directing description, use the exact full canonical @name whenever that entity is mentioned.\n"
        "- Never drop the @ marker and never abbreviate a canonical entity (for example, do not write 妖王 when @铁角妖王 exists).\n"
        "- The same rule applies to named props and locations (for example @石桌, @石室门口).\n"
        "- User dialogue BODY text remains verbatim even if it intentionally contains a short form; dialogue speaker labels still use canonical @names."
    )


def _alias_map(entities: Sequence[str]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    # Full names have priority and are never ambiguous.
    for bare in entities:
        token = canonical_token(bare)
        if bare and token:
            aliases[bare] = token

    # Add safe short aliases only if a single canonical entity owns that suffix.
    candidates: Dict[str, List[str]] = {}
    for bare in entities:
        for suffix in _SAFE_SUFFIX_ALIASES:
            if bare != suffix and bare.endswith(suffix):
                candidates.setdefault(suffix, []).append(bare)
    for suffix, owners in candidates.items():
        unique = list(dict.fromkeys(owners))
        if len(unique) == 1:
            aliases[suffix] = canonical_token(unique[0])
    return aliases


def canonicalize_entity_text(text: Any, entities: Sequence[str]) -> str:
    source = str(text or "")
    if not source or not entities:
        return source

    aliases = _alias_map(entities)
    if not aliases:
        return source

    # Protect already-canonical tokens first so a shorter alias cannot match inside
    # an existing @full-name (e.g. the 妖王 inside @铁角妖王).
    placeholders: Dict[str, str] = {}
    protected = source
    for index, bare in enumerate(sorted(set(entities), key=len, reverse=True)):
        token = canonical_token(bare)
        if not token:
            continue
        placeholder = f"\uFFF0BUFFENTITY{index}\uFFF1"
        if token in protected:
            protected = protected.replace(token, placeholder)
            placeholders[placeholder] = token

    alternatives = sorted(aliases, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(item) for item in alternatives))
    protected = pattern.sub(lambda match: aliases.get(match.group(0), match.group(0)), protected)

    for placeholder, token in placeholders.items():
        protected = protected.replace(placeholder, token)
    return protected


def _canonicalize_value(value: Any, entities: Sequence[str], path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            child_path = path + (key,)

            # User-owned literal locks must stay byte-for-byte unchanged.
            if key in {"keywords", "dialogue_text", "user_shot_source"}:
                out[raw_key] = copy.deepcopy(raw_value)
                continue
            if key == "text" and "dialogues" in path:
                out[raw_key] = copy.deepcopy(raw_value)
                continue

            out[raw_key] = _canonicalize_value(raw_value, entities, child_path)
        return out
    if isinstance(value, list):
        return [_canonicalize_value(item, entities, path) for item in value]
    if isinstance(value, str):
        return canonicalize_entity_text(value, entities)
    return copy.deepcopy(value)


def apply_entity_identity_locks(
    storyboard: Mapping[str, Any],
    *,
    entities: Sequence[str],
    explicit_character_names: Any = "",
) -> Dict[str, Any]:
    """Apply deterministic @full-name normalization to the final storyboard."""
    out = _canonicalize_value(dict(storyboard or {}), list(entities))

    # Character-name heading should itself use exact @full names.  Explicit user
    # character names take priority; otherwise normalize the model's list.
    if str(explicit_character_names or "").strip():
        out["character_names"] = canonicalize_name_list(explicit_character_names)
    elif out.get("character_names"):
        raw_names = _split_name_list(out.get("character_names"))
        resolved = []
        registry = list(entities)
        for raw in raw_names:
            text = canonicalize_entity_text(raw, registry)
            token = text if text.startswith("@") else canonical_token(text)
            if token and token not in resolved:
                resolved.append(token)
        out["character_names"] = ", ".join(resolved)

    # Dialogue bodies remain literal, but speaker labels should use the registry.
    for shot in out.get("shots", []) if isinstance(out.get("shots"), list) else []:
        if not isinstance(shot, dict):
            continue
        dialogues = shot.get("dialogues")
        if not isinstance(dialogues, list):
            continue
        for row in dialogues:
            if not isinstance(row, dict):
                continue
            speaker = str(row.get("speaker", "") or "")
            row["speaker"] = canonicalize_entity_text(speaker, list(entities))

    return out
