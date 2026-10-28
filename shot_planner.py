"""Parse and validate user-authored shot plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple


class ShotPlanError(ValueError):
    pass


@dataclass(frozen=True)
class ShotSection:
    number: int
    start: float | None
    end: float | None
    header: str
    body: str
    source_text: str


@dataclass(frozen=True)
class ShotPlanLock:
    sections: Tuple[ShotSection, ...] = ()
    time_ranges: Tuple[Tuple[float, float], ...] = ()

    @property
    def shot_count(self) -> int:
        return len(self.sections)

    @property
    def has_locked_times(self) -> bool:
        return bool(self.time_ranges)


_HEADER_RE = re.compile(
    r"(?im)^[ \t]*(?:shot|镜头)[ \t]*(?P<number>\d+)"
    r"(?:[ \t]*(?:[·:：]|[-–—])[ \t]*"
    r"(?P<start>\d+(?:\.\d+)?)\s*(?:[-–—~～]|至|to)\s*"
    r"(?P<end>\d+(?:\.\d+)?)\s*(?:s|sec(?:onds?)?|秒)?)?"
    r"[ \t]*$"
)


def parse_shot_plan(text: str, total_duration: float, tolerance: float = 0.05) -> ShotPlanLock:
    source = str(text or "").strip()
    if not source:
        return ShotPlanLock()

    matches = list(_HEADER_RE.finditer(source))
    if not matches:
        return ShotPlanLock()

    sections = []
    for idx, match in enumerate(matches):
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        header = match.group(0).strip()
        body = source[match.end():end_pos].strip()
        start_text = match.group("start")
        end_text = match.group("end")
        sections.append(
            ShotSection(
                number=int(match.group("number")),
                start=float(start_text) if start_text is not None else None,
                end=float(end_text) if end_text is not None else None,
                header=header,
                body=body,
                source_text=(header + ("\n" + body if body else "")),
            )
        )

    expected_numbers = list(range(1, len(sections) + 1))
    actual_numbers = [section.number for section in sections]
    if actual_numbers != expected_numbers:
        raise ShotPlanError(
            f"Shot numbers must be sequential from 1; received {actual_numbers}."
        )

    timed_count = sum(section.start is not None and section.end is not None for section in sections)
    if timed_count not in (0, len(sections)):
        raise ShotPlanError("Timestamp ranges must be supplied for all shots or none.")

    if timed_count == 0:
        return ShotPlanLock(sections=tuple(sections))

    ranges = tuple((float(section.start), float(section.end)) for section in sections)  # type: ignore[arg-type]
    if abs(ranges[0][0]) > tolerance:
        raise ShotPlanError("Explicit shot timing must start at 0 seconds.")

    for idx, (start, end) in enumerate(ranges):
        if end <= start:
            raise ShotPlanError(f"Shot {idx + 1} must end after it starts.")
        if idx > 0 and abs(start - ranges[idx - 1][1]) > tolerance:
            raise ShotPlanError("Explicit shot timing must be contiguous without gaps or overlaps.")

    if abs(ranges[-1][1] - float(total_duration)) > tolerance:
        raise ShotPlanError(
            f"Explicit shot timing must end at the requested duration ({float(total_duration):.3f}s)."
        )

    return ShotPlanLock(sections=tuple(sections), time_ranges=ranges)
