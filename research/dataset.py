"""Turn research run records into an information table.

Objects are run records. Condition attributes describe the request and the
module (skill) configuration; the decision class X is the set of runs whose
raw model response was ``acceptable`` (see quality_metrics.py).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from director_modules import MODULE_SPECS  # noqa: E402
from quality_metrics import recompute_acceptable  # noqa: E402
from research.granular_3wd import Attribute, InformationTable  # noqa: E402

SYNTHETIC_PREFIX = "DRYRUN-"
MODULE_PREFIX = "module:"


def parse_tag(tag: str) -> Dict[str, str]:
    parts: Dict[str, str] = {}
    for item in str(tag or "").split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    return parts


def is_synthetic(record: Mapping[str, Any]) -> bool:
    return parse_tag(record.get("tag", "")).get("exp", "").startswith(SYNTHETIC_PREFIX)


def load_records(paths: Iterable[Path], *, allow_synthetic: bool = False, experiments: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Read JSONL run records, skipping synthetic ones unless allowed."""

    wanted = set(experiments or [])
    records = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            if is_synthetic(record) and not allow_synthetic:
                continue
            if wanted and parse_tag(record.get("tag", "")).get("exp") not in wanted:
                continue
            records.append(record)
    return records


def usable(record: Mapping[str, Any]) -> bool:
    """A record can be analysed when the model answered and was scored.

    Runs that failed before a response arrived (network or endpoint errors)
    say nothing about the module configuration and are excluded. Invalid-JSON
    responses are kept: they are a real, unacceptable outcome.
    """

    metrics = record.get("metrics")
    return isinstance(metrics, Mapping) and "acceptable" in metrics and isinstance(record.get("module_states"), Mapping)


def load_benchmark_tags(path: Optional[Path]) -> Dict[str, List[str]]:
    if path is None or not Path(path).exists():
        return {}
    tags: Dict[str, List[str]] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            tags[str(case["id"])] = list(case.get("tags", []))
    return tags


REQUEST_ATTRIBUTES: Tuple[Tuple[str, str], ...] = (
    ("target_model", "categorical"),
    ("generation_mode", "categorical"),
    ("language", "categorical"),
    ("mode", "categorical"),
    ("audio_policy", "categorical"),
    ("shot_mode", "categorical"),
    ("duration", "numeric"),
    ("has_dialogue", "categorical"),
    ("has_offscreen_dialogue", "categorical"),
    ("has_references", "categorical"),
    ("has_entities", "categorical"),
    ("locked_shots", "categorical"),
    ("locked_times", "categorical"),
    ("has_keywords", "categorical"),
    ("prompt_has_cjk", "categorical"),
    ("tags", "set"),
    ("filled_guidance", "set"),
)


def request_values(record: Mapping[str, Any], benchmark_tags: Mapping[str, List[str]]) -> Dict[str, Any]:
    config = record.get("config", {}) or {}
    features = record.get("features", {}) or {}
    prompt_id = parse_tag(record.get("tag", "")).get("prompt", "")
    return {
        "target_model": config.get("target_model", ""),
        "generation_mode": config.get("generation_mode", ""),
        "language": config.get("language", ""),
        "mode": config.get("mode", ""),
        "audio_policy": config.get("audio_policy", ""),
        "shot_mode": config.get("shot_mode", ""),
        "duration": float(config.get("duration", 0.0) or 0.0),
        "has_dialogue": int(features.get("dialogue_count", 0) or 0) > 0,
        "has_offscreen_dialogue": int(features.get("offscreen_dialogue_count", 0) or 0) > 0,
        "has_references": int(features.get("reference_count", 0) or 0) > 0,
        "has_entities": int(features.get("entity_count", 0) or 0) > 0,
        "locked_shots": int(features.get("locked_shot_count", 0) or 0) > 0,
        "locked_times": bool(features.get("locked_times", False)),
        "has_keywords": bool(features.get("has_keywords", False)),
        "prompt_has_cjk": bool(features.get("prompt_has_cjk", False)),
        "tags": benchmark_tags.get(prompt_id, []),
        "filled_guidance": list(features.get("filled_guidance", [])),
    }


@dataclass
class Dataset:
    table: InformationTable
    groups: List[str]  # prompt ID of each object, for grouped cross-validation
    records: List[Dict[str, Any]]
    module_attributes: List[str]
    request_attributes: List[str]


def build_dataset(
    records: Sequence[Mapping[str, Any]],
    *,
    benchmark_tags: Optional[Mapping[str, List[str]]] = None,
    module_weight: float = 1.0,
    request_weight: float = 1.0,
    thresholds: Optional[Mapping[str, float]] = None,
) -> Dataset:
    """Build the information table from usable run records.

    ``module_weight`` and ``request_weight`` set the total weight of each
    attribute group in the distance function, split evenly inside the group,
    so 21 module attributes do not outweigh the request attributes by count.
    ``thresholds`` re-derives the acceptable label with different limits.
    """

    benchmark_tags = benchmark_tags or {}
    kept = [dict(record) for record in records if usable(record)]
    if not kept:
        raise ValueError("No usable run records (records need metrics and module states).")

    durations = [float((r.get("config") or {}).get("duration", 0.0) or 0.0) for r in kept]
    duration_scale = max(max(durations) - min(durations), 1.0)

    module_names = [f"{MODULE_PREFIX}{key}" for key in MODULE_SPECS]
    request_names = [name for name, _ in REQUEST_ATTRIBUTES]
    attributes = [Attribute(name, "categorical", weight=module_weight / len(module_names)) for name in module_names]
    for name, kind in REQUEST_ATTRIBUTES:
        attributes.append(
            Attribute(name, kind, weight=request_weight / len(REQUEST_ATTRIBUTES), scale=duration_scale if kind == "numeric" else 1.0)
        )

    rows, labels, groups, ids = [], [], [], []
    for number, record in enumerate(kept):
        row = {f"{MODULE_PREFIX}{key}": record["module_states"].get(key, "Off") for key in MODULE_SPECS}
        row.update(request_values(record, benchmark_tags))
        rows.append(row)
        if thresholds:
            labels.append(bool(recompute_acceptable(record, thresholds)))
        else:
            labels.append(bool(record["metrics"]["acceptable"]))
        tag = parse_tag(record.get("tag", ""))
        groups.append(tag.get("prompt") or (record.get("features") or {}).get("prompt_sha256", "")[:12] or f"run{number}")
        ids.append(tag.get("cfg") and f"{tag.get('prompt')}/{tag.get('cfg')}" or record.get("run_id", f"run{number}"))

    table = InformationTable(attributes, rows, labels=labels, ids=ids)
    return Dataset(table=table, groups=groups, records=kept, module_attributes=module_names, request_attributes=request_names)
