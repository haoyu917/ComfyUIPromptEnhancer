"""Dynamic reference-image collection and multimodal request construction."""

from __future__ import annotations

import base64
import io
import re
from typing import Any, Dict, List, Mapping

import numpy as np
from PIL import Image


def parse_reference_manifest(text: str) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for raw in str(text or "").splitlines():
        line = raw.strip().lstrip("-*• ").strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\s*(?:[:=：\-]|\.)\s*(.+)$", line)
        if not match:
            continue
        index = int(match.group(1))
        note = match.group(2).strip()
        if note:
            mapping[index] = note
    return mapping


def image_to_data_url(image: Any, max_side: int = 1024) -> str:
    array = image
    if hasattr(array, "detach"):
        array = array.detach().cpu().numpy()
    else:
        array = np.asarray(array)

    if array.ndim == 4:
        array = array[0]
    if array.ndim != 3:
        raise ValueError(f"Unsupported IMAGE tensor shape: {getattr(array, 'shape', None)}")
    if array.shape[-1] not in (1, 3, 4) and array.shape[0] in (1, 3, 4):
        array = np.transpose(array, (1, 2, 0))

    if array.dtype.kind in ("f", "c"):
        array = np.clip(array, 0.0, 1.0) * 255.0
    else:
        array = np.clip(array, 0, 255)
    array = array.astype(np.uint8)
    if array.shape[-1] == 1:
        array = array[:, :, 0]

    image_obj = Image.fromarray(array)
    safe_max = max(64, int(max_side))
    width, height = image_obj.size
    longest = max(width, height)
    if longest > safe_max:
        scale = safe_max / float(longest)
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:  # Pillow < 9 compatibility.
            resample = Image.LANCZOS
        image_obj = image_obj.resize(new_size, resample=resample)
    buffer = io.BytesIO()
    image_obj.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def collect_reference_assets(
    manifest_text: str,
    inputs: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    notes = parse_reference_manifest(manifest_text)
    found = []
    for key, value in inputs.items():
        match = re.fullmatch(r"reference_image_(\d+)", str(key))
        if match and value is not None:
            found.append((int(match.group(1)), value))
    found.sort(key=lambda item: item[0])

    refs: List[Dict[str, Any]] = []
    for index, image in found:
        note = str(inputs.get(f"reference_note_{index}", "") or "").strip() or notes.get(index, "")
        refs.append(
            {
                "index": index,
                "note": note,
                "data_url": image_to_data_url(image),
            }
        )
    return refs


def reference_summary(reference_assets: List[Dict[str, Any]]) -> str:
    if not reference_assets:
        return "None"
    return "; ".join(
        f"Reference {ref['index']}: {ref.get('note') or 'no note provided'}"
        for ref in reference_assets
    )


def build_multimodal_content(
    user_prompt: str,
    reference_assets: List[Dict[str, Any]],
) -> Any:
    if not reference_assets:
        return user_prompt
    parts: List[Dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for ref in reference_assets:
        note = ref.get("note") or "no note provided"
        parts.append(
            {
                "type": "text",
                "text": (
                    f"Reference image {ref['index']} note: {note}. Use the note and the image together "
                    "to identify its character, prop, location, layout, or atmosphere role. Keep all "
                    "reference roles distinct and preserve their relationships."
                ),
            }
        )
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": ref["data_url"]},
            }
        )
    return parts
