"""Storyboard normalization, exact timing, dialogue locks, and continuity."""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    from .shot_planner import ShotPlanLock
except ImportError:
    from shot_planner import ShotPlanLock


def _positive_number(value: Any, default: float = 1.0) -> float:
    try:
        parsed = float(value)
        if math.isfinite(parsed) and parsed > 0:
            return parsed
    except Exception:
        pass
    return float(default)


def allocate_durations(
    total_duration: float,
    weights: Sequence[float],
    min_duration: float = 0.75,
) -> List[float]:
    total = float(total_duration)
    count = len(weights)
    if count == 0:
        return []
    if count == 1:
        return [total]

    safe = [_positive_number(weight, 1.0) for weight in weights]
    floor = min(float(min_duration), total / count)
    remaining = max(0.0, total - floor * count)
    weight_sum = sum(safe) or float(count)
    values = [floor + remaining * (weight / weight_sum) for weight in safe]
    values[-1] += total - sum(values)
    return values


def normalize_action_beats(
    action_beats: Iterable[Mapping[str, Any]],
    shot_duration: float,
    global_start: float,
) -> List[Dict[str, Any]]:
    valid: List[Dict[str, Any]] = []
    for raw in action_beats or []:
        if not isinstance(raw, Mapping):
            continue
        valid.append(
            {
                "description": str(raw.get("description", "visible action progression") or "visible action progression").strip(),
                "weight": _positive_number(raw.get("weight", 1.0), 1.0),
                "intensity": str(raw.get("intensity", "medium") or "medium").strip(),
            }
        )
    if not valid:
        valid = [{"description": "visible action progression", "weight": 1.0, "intensity": "medium"}]

    durations = allocate_durations(
        float(shot_duration),
        [item["weight"] for item in valid],
        min_duration=min(0.25, float(shot_duration) / len(valid)),
    )

    out: List[Dict[str, Any]] = []
    cursor = 0.0
    for item, duration in zip(valid, durations):
        local_start = cursor
        local_end = local_start + duration
        out.append(
            {
                "description": item["description"],
                "intensity": item["intensity"],
                "local_start": round(local_start, 3),
                "local_end": round(local_end, 3),
                "global_start": round(float(global_start) + local_start, 3),
                "global_end": round(float(global_start) + local_end, 3),
                "duration": round(duration, 3),
            }
        )
        cursor = local_end

    if out:
        out[-1]["local_end"] = round(float(shot_duration), 3)
        out[-1]["global_end"] = round(float(global_start) + float(shot_duration), 3)
        out[-1]["duration"] = round(out[-1]["local_end"] - out[-1]["local_start"], 3)
    return out


def _default_negative() -> str:
    return (
        "identity drift, face change, costume change, prop-state error, spatial discontinuity, "
        "screen-direction reversal, background flicker, malformed anatomy, extra fingers, "
        "motion jitter, missing action endpoint, contradictory camera movement"
    )


def _normalize_dialogues(
    raw_dialogues: Any,
    dialogue_by_index: Mapping[int, Mapping[str, Any]],
    used_indices: set[int],
) -> List[Dict[str, Any]]:
    rows = raw_dialogues if isinstance(raw_dialogues, list) else []
    out: List[Dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        try:
            source_index = int(raw.get("source_index", 0) or 0)
        except Exception:
            source_index = 0
        speaker = str(raw.get("speaker", "") or "").strip()
        text = str(raw.get("text", "") or "").strip()
        if source_index in dialogue_by_index:
            source = dialogue_by_index[source_index]
            speaker = str(source.get("speaker", "") or "").strip()
            text = str(source.get("text", "") or "").strip()
            used_indices.add(source_index)
        out.append(
            {
                "source_index": source_index,
                "speaker": speaker,
                "voice_direction": str(raw.get("voice_direction", "") or "").strip(),
                "state": str(raw.get("state", "") or "").strip(),
                "tone": str(raw.get("tone", "") or "").strip(),
                "text": text,
            }
        )
    return out


def _safe_shot_count(total_duration: float) -> int:
    return max(1, min(12, int(max(float(total_duration), 1.0) / 1.25)))


def normalize_storyboard(
    storyboard: Mapping[str, Any],
    *,
    total_duration: float,
    shot_mode: str,
    continuity_lock: bool,
    shot_lock: ShotPlanLock,
    dialogue_entries: Sequence[Mapping[str, Any]],
    global_dialogue_direction: str = "",
    module_report: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    source = dict(storyboard or {})
    raw_shots = source.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raw_shots = [{}]
    raw_shots = [copy.deepcopy(item) if isinstance(item, Mapping) else {} for item in raw_shots]

    if shot_lock.shot_count:
        target_count = shot_lock.shot_count
        if len(raw_shots) < target_count:
            raw_shots.extend({} for _ in range(target_count - len(raw_shots)))
        raw_shots = raw_shots[:target_count]
    elif shot_mode == "Single Shot":
        raw_shots = raw_shots[:1]
    else:
        raw_shots = raw_shots[: _safe_shot_count(total_duration)]

    if shot_mode == "Multi Shot" and len(raw_shots) < 2:
        raise ValueError("Multi Shot mode requires at least 2 shots.")

    count = len(raw_shots)
    if shot_lock.has_locked_times:
        ranges = list(shot_lock.time_ranges)
        durations = [end - start for start, end in ranges]
    else:
        weights = [_positive_number(raw.get("duration_weight", 1.0), 1.0) for raw in raw_shots]
        durations = allocate_durations(float(total_duration), weights, min_duration=0.75)
        ranges = []
        cursor = 0.0
        for duration in durations:
            ranges.append((cursor, cursor + duration))
            cursor += duration

    dialogue_by_index: Dict[int, Mapping[str, Any]] = {}
    for row in dialogue_entries or []:
        try:
            index = int(row.get("source_index", 0) or 0)
        except Exception:
            index = 0
        if index > 0:
            dialogue_by_index[index] = row
    used_dialogue_indices: set[int] = set()

    normalized: List[Dict[str, Any]] = []
    previous_out = ""
    for idx, raw in enumerate(raw_shots):
        start, end = ranges[idx]
        duration = end - start
        shot = dict(raw)
        shot["id"] = idx + 1
        shot["start_time"] = round(start, 3)
        shot["end_time"] = round(end, 3)
        shot["duration"] = round(duration, 3)
        shot["purpose"] = str(raw.get("purpose", "") or "").strip()
        shot["user_shot_source"] = (
            shot_lock.sections[idx].source_text if idx < len(shot_lock.sections) else ""
        )

        continuity_in = str(raw.get("continuity_in", "") or "").strip()
        continuity_out = str(raw.get("continuity_out", "") or "").strip()
        if continuity_lock and idx > 0 and previous_out:
            continuity_in = previous_out
        shot["continuity_in"] = continuity_in
        shot["continuity_out"] = continuity_out

        beats = raw.get("action_beats") if isinstance(raw.get("action_beats"), list) else []
        if not beats:
            fallback = str(raw.get("performance_action", "") or "").strip() or "visible action progression"
            beats = [{"description": fallback, "weight": 1.0, "intensity": "medium"}]
        shot["action_beats"] = normalize_action_beats(beats, duration, start)
        shot["dialogues"] = _normalize_dialogues(
            raw.get("dialogues", []), dialogue_by_index, used_dialogue_indices
        )
        events = raw.get("offscreen_events") if isinstance(raw.get("offscreen_events"), list) else []
        shot["offscreen_events"] = [dict(event) for event in events if isinstance(event, Mapping)]
        shot["negative_prompt"] = str(raw.get("negative_prompt", "") or "").strip() or _default_negative()
        normalized.append(shot)
        previous_out = continuity_out

    missing_dialogues = [index for index in dialogue_by_index if index not in used_dialogue_indices]
    if missing_dialogues and normalized:
        target = max(normalized, key=lambda item: item["duration"])
        for index in missing_dialogues:
            source_row = dialogue_by_index[index]
            target["dialogues"].append(
                {
                    "source_index": index,
                    "speaker": str(source_row.get("speaker", "") or "").strip(),
                    "voice_direction": str(global_dialogue_direction or "").strip(),
                    "state": "",
                    "tone": "",
                    "text": str(source_row.get("text", "") or "").strip(),
                }
            )

    if normalized:
        normalized[-1]["end_time"] = round(float(total_duration), 3)
        normalized[-1]["duration"] = round(
            normalized[-1]["end_time"] - normalized[-1]["start_time"], 3
        )
        source_beats = [
            {
                "description": beat.get("description", ""),
                "weight": max(float(beat.get("duration", 0.0)), 0.001),
                "intensity": beat.get("intensity", "medium"),
            }
            for beat in normalized[-1]["action_beats"]
        ]
        normalized[-1]["action_beats"] = normalize_action_beats(
            source_beats,
            normalized[-1]["duration"],
            normalized[-1]["start_time"],
        )

    result = {key: copy.deepcopy(value) for key, value in source.items() if key != "shots"}
    result.update(
        {
            "title": str(source.get("title", "Production Director Prompt") or "Production Director Prompt"),
            "overview": str(source.get("overview", "") or ""),
            "total_duration": round(float(total_duration), 3),
            "shot_count": len(normalized),
            "shot_plan_locked": bool(shot_lock.shot_count),
            "shot_timing_locked": bool(shot_lock.has_locked_times),
            "module_report": list(module_report or []),
            "shots": normalized,
        }
    )
    return result
