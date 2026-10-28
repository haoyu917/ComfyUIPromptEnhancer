"""Dynamic routing of optional directing knowledge into API prompts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, OrderedDict as OrderedDictType
from collections import OrderedDict

try:
    from .director_core import DIRECTOR_CORE_PROMPT
    from .director_modules import MODULE_SPECS, ModuleSpec
except ImportError:
    from director_core import DIRECTOR_CORE_PROMPT
    from director_modules import MODULE_SPECS, ModuleSpec


@dataclass(frozen=True)
class ModuleRuntime:
    spec: ModuleSpec
    state: str
    user_values: Dict[str, str]
    guidance_value: str

    @property
    def has_user_data(self) -> bool:
        return bool(self.user_values)


def _clean(value: object) -> str:
    return str(value or "").strip()


def resolve_module_runtime(
    states: Mapping[str, str],
    user_inputs: Mapping[str, Any],
) -> "OrderedDictType[str, ModuleRuntime]":
    runtime: "OrderedDictType[str, ModuleRuntime]" = OrderedDict()
    for key, spec in MODULE_SPECS.items():
        state = str(states.get(key, "Off") or "Off")
        if state == "Off":
            continue

        values: Dict[str, str] = {}
        for name in spec.source_inputs:
            value = _clean(user_inputs.get(name, ""))
            if value:
                values[name] = value

        guidance = _clean(user_inputs.get(spec.guidance_input, ""))
        if guidance:
            values.setdefault(spec.guidance_input, guidance)

        runtime[key] = ModuleRuntime(
            spec=spec,
            state=state,
            user_values=values,
            guidance_value=guidance,
        )
    return runtime


def _output_language_name(output_language: str) -> str:
    value = str(output_language or "English").strip().lower()
    return "Chinese" if value in {"中文", "chinese", "zh", "zh-cn", "简体中文"} else "English"


def build_director_system_prompt(states: Mapping[str, str], output_language: str = "English") -> str:
    language_name = _output_language_name(output_language)
    language_directive = (
        "OUTPUT LANGUAGE: Simplified Chinese. Write every production/directing field in natural, professional "
        "Simplified Chinese. Keep JSON keys unchanged because the schema parser depends on them. Character names, "
        "dialogue text, Keywords, LoRA trigger tokens, reference names, and other opaque tokens must remain verbatim."
        if language_name == "Chinese"
        else
        "OUTPUT LANGUAGE: English. Write every production/directing field in professional English. Character names, "
        "dialogue text, Keywords, LoRA trigger tokens, reference names, and other opaque tokens must remain verbatim."
    )
    blocks = [DIRECTOR_CORE_PROMPT, language_directive]
    for key, spec in MODULE_SPECS.items():
        if states.get(key, "Off") == "Off":
            continue
        blocks.append(f"MODULE: {spec.title_en.upper()}\n{spec.skill_prompt}")
    return "\n\n".join(blocks)


def build_module_context(runtime: Mapping[str, ModuleRuntime]) -> str:
    if not runtime:
        return "No optional director modules are loaded for this request."

    blocks = []
    for item in runtime.values():
        lines = [f"## {item.spec.title_en}", f"State: {item.state}"]
        if item.state == "Guided":
            if item.guidance_value:
                lines.extend(
                    [
                        "HARD USER INTENT LOCK:",
                        item.guidance_value,
                        "The AI may professionalize and complete this guidance but must not contradict, replace, or weaken it.",
                    ]
                )
            else:
                lines.append("GUIDED FIELD IS BLANK — AI-GENERATE the missing module deliverable professionally.")
        elif item.user_values:
            lines.append("USER-SUPPLIED CONSTRAINTS — preserve their decisions and AI-GENERATE MISSING MATERIAL:")

        if item.user_values:
            for name, value in item.user_values.items():
                if item.state == "Guided" and name == item.spec.guidance_input:
                    continue
                lines.append(f"- {name}: {value}")
        elif item.state == "Auto":
            lines.append("AI-GENERATE MISSING MATERIAL from the core idea, references, and active modules.")

        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _top_example(field: str, language_name: str = "English") -> Any:
    if field == "dramatic_beats":
        return [
            {
                "id": 1,
                "story_function": language_name,
                "state_in": language_name,
                "visible_action": language_name,
                "pressure_delta": language_name,
                "state_out": language_name,
                "likely_shot_family": language_name,
            }
        ]
    if field in {"character_names", "keywords"}:
        return "verbatim user text or source-language AI text"
    return language_name


def _shot_example(field: str, language_name: str = "English") -> Any:
    if field == "dialogues":
        return [
            {
                "source_index": 0,
                "speaker": "verbatim original-language name",
                "voice_direction": language_name,
                "state": language_name,
                "tone": language_name,
                "text": "verbatim original-language dialogue",
            }
        ]
    if field == "offscreen_events":
        return [
            {
                "source": ("准确实体名称或中文来源" if language_name == "Chinese" else "exact entity name or English source"),
                "event": language_name,
                "delivery": language_name,
                "reaction": language_name,
            }
        ]
    if field == "sound_layers":
        return {
            "room_tone": language_name,
            "ambience": language_name,
            "foley": language_name,
            "spot_effects": language_name,
            "score_or_silence": language_name,
        }
    if field == "reference_assignments":
        return (["参考图 1 -> 准确实体/作用"] if language_name == "Chinese" else ["Reference 1 -> exact entity/role"])
    return language_name


def build_dynamic_schema(states: Mapping[str, str], output_language: str = "English") -> str:
    language_name = _output_language_name(output_language)
    top: Dict[str, Any] = {
        "title": f"{language_name} production title",
        "overview": f"{language_name} summary",
        "assumptions": [f"{language_name} assumption only when necessary"],
        "scene_objective": language_name,
        "character_names": "verbatim original-language names",
        "character_profiles": language_name,
        "character_relationships": language_name,
        "scene_environment": language_name,
        "keywords": "verbatim user keywords in any language",
        "extra_requirements": language_name,
        "shot_count_reason": language_name,
    }
    shot: Dict[str, Any] = {
        "id": 1,
        "purpose": f"{language_name} story function",
        "duration_weight": 1.0,
        "visual_information": f"{language_name} executable screen description",
        "performance_action": f"{language_name} start state, progression, and end state",
        "continuity_in": language_name,
        "continuity_out": language_name,
        "action_beats": [
            {
                "description": f"{language_name} visible action",
                "weight": 1.0,
                "intensity": "low|medium|high",
            }
        ],
        "dialogues": _shot_example("dialogues", language_name),
    }

    for key, spec in MODULE_SPECS.items():
        if states.get(key, "Off") == "Off":
            continue
        for field in spec.top_level_fields:
            top.setdefault(field, _top_example(field, language_name))
        for field in spec.shot_fields:
            shot.setdefault(field, _shot_example(field, language_name))

    top["shots"] = [shot]
    return json.dumps(top, ensure_ascii=False, indent=2)


def runtime_report(runtime: Mapping[str, ModuleRuntime]) -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "title": item.spec.title_en,
            "state": item.state,
            "has_user_data": item.has_user_data,
            "guidance_input": item.spec.guidance_input,
        }
        for key, item in runtime.items()
    ]


def build_generation_mode_guidance(generation_mode: str) -> str:
    """Return non-optional source-image semantics for one generation mode."""

    table = {
        "Image to Video": (
            "Treat the uploaded image as the exact initial visual state. Preserve visible identity, "
            "wardrobe, props, pose logic, scene geography, and major composition. Begin motion naturally "
            "from the source pose; do not redesign, teleport, or introduce unexplained state changes."
        ),
        "Reference to Video": (
            "Use connected reference images to lock identity, design, props, layout, lighting, or atmosphere, "
            "but each reference is not a mandatory first frame. New starting poses, compositions, and blocking "
            "are allowed when the story requires them. Keep reference roles distinct and preserve relationships."
        ),
        "Text to Video": (
            "There is no visual source. Build identity, wardrobe, environment, starting pose, composition, and "
            "spatial relationships from the user's text while maintaining internal continuity."
        ),
    }
    return table.get(generation_mode, table["Image to Video"])


def build_target_model_guidance(target_model: str) -> str:
    """Return a compact capability-first adapter for the selected video model family."""

    table = {
        "MiniMax / Hailuo": (
            "Prioritize one clear subject action, continuous performance, stable identity and scene layout, "
            "a restrained camera, and an explicit end state. Avoid overloaded action chains."
        ),
        "Wan": (
            "Prioritize readable motion, stable identity, clear start-to-end action, and simple physically legible "
            "camera behavior. Avoid multiple competing actions in one short clip."
        ),
        "Seedance": (
            "Prioritize rhythmic blocking, multi-shot continuity, receiver-in and handoff-out states, screen "
            "direction, eyeline, prop state, and clean edit boundaries between clips."
        ),
        "Kling": (
            "Prioritize temporal stability, coherent anatomy, natural camera movement, explicit action endpoints, "
            "and physically plausible transitions between poses."
        ),
        "Veo": (
            "Prioritize cinematic story clarity, environmental response, physically plausible motion, sound-aware "
            "performance cues, and coherent audiovisual cause and effect."
        ),
        "Generic": (
            "Prioritize temporal continuity, stable identity, readable action, one dominant camera behavior, and a "
            "clear end state compatible with the next shot."
        ),
    }
    return table.get(target_model, table["Generic"])
