"""Automatic quality metrics for research run records.

The node repairs model output after it arrives: it pads or truncates shots,
reinserts missing dialogue, restores keywords, and canonicalizes @entity names.
The final storyboard therefore always looks compliant, and scoring it would say
nothing about the configuration that produced it. These metrics score the RAW
parsed model response, before any repair, so they measure how well a given
module configuration made the model follow instructions.

Every raw measurement is recorded alongside the derived ``acceptable`` label,
so the label can be recomputed offline with different thresholds.
"""

from __future__ import annotations

import difflib
import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

METRICS_VERSION = 1

# Schema fields that may legitimately be empty, or that the user owns rather
# than the model, and so do not count toward field coverage.
_OPTIONAL_TOP_FIELDS = frozenset({"assumptions", "keywords", "character_names", "extra_requirements", "shots"})
_OPTIONAL_SHOT_FIELDS = frozenset({"id", "dialogues", "offscreen_events", "duration_weight"})

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "min_top_field_coverage": 0.8,
    "min_shot_field_coverage": 0.8,
    "min_entity_token_rate": 0.8,
}


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def expected_fields_from_schema(schema_text: str) -> tuple[List[str], List[str]]:
    """Return (top-level fields, shot fields) the active-module schema asks for."""

    try:
        schema = json.loads(schema_text)
    except (TypeError, ValueError):
        return [], []
    if not isinstance(schema, Mapping):
        return [], []
    top = [key for key in schema if key not in _OPTIONAL_TOP_FIELDS]
    shots = schema.get("shots")
    shot_template = shots[0] if isinstance(shots, list) and shots and isinstance(shots[0], Mapping) else {}
    shot = [key for key in shot_template if key not in _OPTIONAL_SHOT_FIELDS]
    return top, shot


def _raw_shots(raw: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    shots = raw.get("shots") if isinstance(raw, Mapping) else None
    if not isinstance(shots, list):
        return []
    return [shot for shot in shots if isinstance(shot, Mapping)]


def _coverage(raw: Mapping[str, Any], top_fields: Sequence[str], shot_fields: Sequence[str]) -> Dict[str, Any]:
    top_missing = [field for field in top_fields if not _filled(raw.get(field))]
    top_cov = 1.0 if not top_fields else 1.0 - len(top_missing) / len(top_fields)

    shots = _raw_shots(raw)
    if not shot_fields:
        shot_cov = 1.0
    elif not shots:
        shot_cov = 0.0
    else:
        per_shot = [sum(_filled(shot.get(field)) for field in shot_fields) / len(shot_fields) for shot in shots]
        shot_cov = sum(per_shot) / len(per_shot)
    missing_counter: Counter[str] = Counter()
    for shot in shots:
        missing_counter.update(field for field in shot_fields if not _filled(shot.get(field)))
    return {
        "top_field_coverage": round(top_cov, 4),
        "shot_field_coverage": round(shot_cov, 4),
        "top_fields_expected": len(top_fields),
        "shot_fields_expected": len(shot_fields),
        "top_fields_missing": sorted(top_missing),
        "shot_fields_missing": sorted(missing_counter),
    }


def _source_index(row: Mapping[str, Any]) -> int:
    try:
        return int(row.get("source_index", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _dialogue_metrics(raw: Mapping[str, Any], dialogue_entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    allowed = {_source_index(row): str(row.get("text", "") or "").strip() for row in dialogue_entries}
    allowed.pop(0, None)

    assigned: Counter[int] = Counter()
    verbatim = 0
    matched_rows = 0
    invented = 0
    for shot in _raw_shots(raw):
        rows = shot.get("dialogues")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            idx = _source_index(row)
            text = str(row.get("text", "") or "").strip()
            if idx in allowed:
                assigned[idx] += 1
                matched_rows += 1
                if text == allowed[idx]:
                    verbatim += 1
            elif text:
                invented += 1

    if not allowed:
        coverage: Optional[float] = None
        verbatim_rate: Optional[float] = None
    else:
        coverage = round(len(assigned) / len(allowed), 4)
        # With no matched rows there is nothing to judge for alteration;
        # the omission is already reported by dialogue_coverage.
        verbatim_rate = round(verbatim / matched_rows, 4) if matched_rows else None
    return {
        "dialogue_lines": len(allowed),
        "dialogue_coverage": coverage,
        "dialogue_verbatim_rate": verbatim_rate,
        "dialogue_duplicates": sum(count - 1 for count in assigned.values() if count > 1),
        "invented_dialogue_count": invented,
    }


def _entity_token_rate(raw: Mapping[str, Any], entities: Sequence[str]) -> Optional[float]:
    names = [str(name or "").strip().lstrip("@") for name in entities]
    names = [name for name in names if name]
    if not names:
        return None
    text = json.dumps(raw, ensure_ascii=False)
    return round(sum(1 for name in names if f"@{name}" in text) / len(names), 4)


def _keywords_ok(raw: Mapping[str, Any], user_keywords: str) -> bool:
    returned = str(raw.get("keywords", "") or "").strip() if isinstance(raw, Mapping) else ""
    expected = str(user_keywords or "").strip()
    # Blank user keywords must stay blank: the model may not invent LoRA tokens.
    return returned == expected


def _shot_count_metrics(raw: Mapping[str, Any], target: int, locked: bool, safe_max: int) -> Dict[str, Any]:
    count = len(_raw_shots(raw))
    if locked:
        ok = count == target
    else:
        # Unlocked counts are only a recommendation; flag outputs the node
        # would have to pad (none) or truncate (above its safe maximum).
        ok = 1 <= count <= safe_max
    return {
        "shot_count_raw": count,
        "shot_count_target": int(target),
        "shot_count_locked": bool(locked),
        "shot_count_deviation": count - int(target),
        "shot_count_ok": bool(ok),
    }


def score_response(
    raw: Optional[Mapping[str, Any]],
    *,
    schema_text: str,
    dialogue_entries: Sequence[Mapping[str, Any]] = (),
    entities: Sequence[str] = (),
    user_keywords: str = "",
    target_shots: int = 1,
    shot_count_locked: bool = False,
    safe_max_shots: int = 12,
) -> Dict[str, Any]:
    """Measure one raw parsed model response. ``raw=None`` means invalid JSON."""

    if not isinstance(raw, Mapping) or not raw:
        return {"json_ok": False}
    top_fields, shot_fields = expected_fields_from_schema(schema_text)
    metrics: Dict[str, Any] = {"json_ok": True}
    metrics.update(_coverage(raw, top_fields, shot_fields))
    metrics.update(_shot_count_metrics(raw, target_shots, shot_count_locked, safe_max_shots))
    metrics.update(_dialogue_metrics(raw, dialogue_entries))
    metrics["entity_token_rate"] = _entity_token_rate(raw, entities)
    metrics["keywords_ok"] = _keywords_ok(raw, user_keywords)
    return metrics


def lock_violations(metrics: Mapping[str, Any], *, strict_speech: bool) -> List[str]:
    """Name every user lock the raw response broke (each one needed a repair)."""

    if not metrics.get("json_ok"):
        return ["invalid_json"]
    violations = []
    if not metrics.get("shot_count_ok", True):
        violations.append("shot_count")
    coverage = metrics.get("dialogue_coverage")
    if coverage is not None and coverage < 1.0:
        violations.append("dialogue_missing")
    verbatim = metrics.get("dialogue_verbatim_rate")
    if verbatim is not None and verbatim < 1.0:
        violations.append("dialogue_altered")
    if metrics.get("dialogue_duplicates", 0):
        violations.append("dialogue_duplicated")
    if strict_speech and metrics.get("invented_dialogue_count", 0):
        violations.append("dialogue_invented")
    if not metrics.get("keywords_ok", True):
        violations.append("keywords")
    return violations


def is_acceptable(
    metrics: Mapping[str, Any],
    *,
    strict_speech: bool,
    thresholds: Optional[Mapping[str, float]] = None,
) -> bool:
    """Decision class X: the raw response met every lock and enough of the schema."""

    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if lock_violations(metrics, strict_speech=strict_speech):
        return False
    if metrics.get("top_field_coverage", 0.0) < limits["min_top_field_coverage"]:
        return False
    if metrics.get("shot_field_coverage", 0.0) < limits["min_shot_field_coverage"]:
        return False
    entity_rate = metrics.get("entity_token_rate")
    if entity_rate is not None and entity_rate < limits["min_entity_token_rate"]:
        return False
    return True


def _prose(storyboard: Mapping[str, Any]) -> str:
    shots = storyboard.get("shots", []) if isinstance(storyboard, Mapping) else []
    return json.dumps(shots, ensure_ascii=False, sort_keys=True)


def change_ratio(before: Mapping[str, Any], after: Mapping[str, Any]) -> float:
    """0.0 means the shots are identical, 1.0 means completely rewritten."""

    a, b = _prose(before), _prose(after)
    if a == b:
        return 0.0
    return round(1.0 - difflib.SequenceMatcher(None, a, b).ratio(), 4)


def build_run_metrics(
    *,
    first: Optional[Mapping[str, Any]],
    quality: Optional[Mapping[str, Any]] = None,
    quality_attempted: bool = False,
    pre_quality_storyboard: Optional[Mapping[str, Any]] = None,
    post_quality_storyboard: Optional[Mapping[str, Any]] = None,
    strict_speech: bool,
    thresholds: Optional[Mapping[str, float]] = None,
    **score_kwargs: Any,
) -> Dict[str, Any]:
    """Combine per-response scores into the ``metrics`` block of a run record.

    ``acceptable`` (decision class X) is judged on the first response, which is
    what the module configuration itself produced. The Quality pass is scored
    separately so its effect can be analysed on its own.
    """

    first_scores = score_response(first, **score_kwargs)
    first_violations = lock_violations(first_scores, strict_speech=strict_speech)
    result: Dict[str, Any] = {
        "metrics_version": METRICS_VERSION,
        "thresholds": {**DEFAULT_THRESHOLDS, **(thresholds or {})},
        "first": first_scores,
        "lock_violations": first_violations,
        "repairs_needed": len(first_violations),
        "acceptable": is_acceptable(first_scores, strict_speech=strict_speech, thresholds=thresholds),
    }
    if quality_attempted:
        quality_scores = score_response(quality, **score_kwargs)
        result["quality"] = quality_scores
        result["quality_lock_violations"] = lock_violations(quality_scores, strict_speech=strict_speech)
        if pre_quality_storyboard is not None and post_quality_storyboard is not None:
            result["quality_change_ratio"] = change_ratio(pre_quality_storyboard, post_quality_storyboard)
    return result


def recompute_acceptable(record: Mapping[str, Any], thresholds: Mapping[str, float]) -> Optional[bool]:
    """Re-derive the label of a stored run record under different thresholds."""

    metrics = record.get("metrics") if isinstance(record, Mapping) else None
    if not isinstance(metrics, Mapping) or "first" not in metrics:
        return None
    config = record.get("config", {}) if isinstance(record.get("config"), Mapping) else {}
    strict = bool(config.get("strict_speech_lock", True)) or config.get("audio_policy") != "Full Auto Audio"
    return is_acceptable(metrics["first"], strict_speech=strict, thresholds=thresholds)


def iter_records(lines: Iterable[str]) -> Iterable[Dict[str, Any]]:
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            yield record
