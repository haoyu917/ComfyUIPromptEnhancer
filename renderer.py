"""Stable Production Director Prompt rendering with selectable output language."""

from __future__ import annotations

from typing import Any, Mapping

try:
    from .director_modules import MODULE_SPECS
    from .audio_control import collect_storyboard_speaker_ids, compile_h3_dialogue_blocks
except ImportError:
    from director_modules import MODULE_SPECS
    from audio_control import collect_storyboard_speaker_ids, compile_h3_dialogue_blocks


def _active(states: Mapping[str, str], key: str) -> bool:
    return states.get(key, "Off") != "Off"


def _is_zh(language: Any) -> bool:
    value = str(language or "English").strip().lower()
    return value in {"中文", "chinese", "zh", "zh-cn", "简体中文"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, Mapping):
                parts = [f"{key}: {_text(val)}" for key, val in item.items() if _text(val)]
                lines.append("; ".join(parts))
            elif _text(item):
                lines.append(_text(item))
        return "\n".join(lines)
    if isinstance(value, Mapping):
        return "\n".join(f"{key}: {_text(val)}" for key, val in value.items() if _text(val))
    return str(value)


ZH_HEADINGS = {
    "PRODUCTION DIRECTOR PROMPT": "制作导演提示词",
    "OVERVIEW": "整体概述",
    "ASSUMPTIONS": "必要假设",
    "SHOT BUDGET RATIONALE": "分镜数量依据",
    "CHARACTER NAMES — VERBATIM": "角色名称（原样保留）",
    "CHARACTER PROFILES": "角色设定",
    "CHARACTER RELATIONSHIPS": "角色关系",
    "SCENE ENVIRONMENT": "场景环境",
    "KEYWORDS — VERBATIM": "LoRA 触发词 / Keywords（原样保留）",
    "EXTRA REQUIREMENTS": "其他要求",
    "REFERENCE & ENTITY BINDINGS": "参考图与实体绑定",
    "REFERENCE SUMMARY": "参考图摘要",
    "SCENE OBJECTIVE": "本场目标",
    "LITERAL EVENT": "表层事件",
    "DRAMATIC QUESTION": "戏剧问题",
    "CONFLICT": "冲突",
    "SUBTEXT": "潜台词",
    "EMOTIONAL MOVEMENT": "情绪变化",
    "VISUAL THESIS": "视觉核心",
    "DRAMATIC BEATS": "戏剧节拍",
    "DIRECTOR BOOK / VISUAL TREATMENT": "导演书 / 视觉统筹",
    "VISUAL CONTINUITY": "视觉连续性",
    "GLOBAL BLOCKING & STAGING": "全局走位与调度",
    "GLOBAL CAMERA REQUIREMENTS": "全局摄影要求",
    "GLOBAL PERFORMANCE REQUIREMENTS": "全局表演要求",
    "SPATIAL CONTINUITY": "空间连续性",
    "CHARACTER CONTINUITY": "角色连续性",
    "GLOBAL LIGHTING & COLOR": "全局灯光与色彩",
    "GLOBAL DIALOGUE DIRECTION": "全局对白 / 配音指导",
    "GLOBAL SOUND DESIGN": "全局声音设计",
    "GLOBAL OFF-SCREEN AUDIO": "全局画外声音",
    "KEYFRAME STRATEGY": "关键帧策略",
    "TRANSITION & EDIT ASSEMBLY": "转场与剪辑方案",
    "GLOBAL TRANSITION CONTINUITY": "全局镜间承接",
    "GENRE PLAYBOOK": "类型片手法",
    "DIRECTING STYLE LENS": "导演风格方法",
    "CLIP HANDOFF PLAN": "多片段交接方案",
    "TARGET MODEL ADAPTER": "目标模型适配",
    "QC PLAN": "质量检查方案",
    "GLOBAL NEGATIVE CONSTRAINTS": "全局负面约束",
    "PRODUCT / MACRO PLAN": "产品 / 微距方案",
    "SHOTS": "分镜",
    "PURPOSE": "镜头目的",
    "CAMERA CAPTURE": "镜头技术捕捉",
    "VISUAL INFORMATION": "画面具体信息",
    "BLOCKING & STAGING": "人物走位与调度",
    "PERFORMANCE & ACTION": "表演与动作",
    "FACIAL EXPRESSION & EYELINE": "表情与视线",
    "LIGHTING DESIGN": "光线设计",
    "SPATIAL / ENTITY CONSTRAINTS": "空间 / 实体约束",
    "REFERENCE ASSIGNMENTS": "参考图绑定",
    "CHARACTER CONTINUITY ANCHORS": "角色连续性锚点",
    "KEYFRAME NOTE": "关键帧说明",
    "MODEL GENERATION NOTE": "模型生成说明",
    "ACTION TIMELINE": "动作时间线",
    "DIALOGUE": "对白",
    "OFF-SCREEN / AUDIO EVENTS": "画外 / 声音事件",
    "SOUND LAYERS": "声音层次",
    "H3 DIALOGUE / VOICE CONTROL": "H3 对白 / 语音控制",
    "NON-SPEECH SOUND LAYERS": "非语言声音层",
    "CONTINUITY IN": "镜头进入状态",
    "CONTINUITY OUT": "镜头结束状态",
    "INTER-SHOT CONTINUITY": "镜间连续性",
    "EDIT NOTE": "剪辑说明",
    "RECEIVER-IN": "承接进入",
    "HANDOFF-OUT": "交接结束",
    "RISK / QC NOTE": "风险 / 质检提示",
    "NEGATIVE CONSTRAINTS": "负面约束",
    "LORA KEYWORDS": "LoRA 触发词 / Keywords（原样保留）",
}


def _heading(name: str, language: Any) -> str:
    return ZH_HEADINGS.get(name, name) if _is_zh(language) else name


def _append_section(lines: list[str], heading: str, value: Any, language: Any = "English") -> None:
    content = _text(value)
    if not content:
        return
    lines.extend([_heading(heading, language), content, ""])


def _render_beats(beats: Any, language: Any = "English") -> str:
    if not isinstance(beats, list):
        return _text(beats)
    lines = []
    for beat in beats:
        if not isinstance(beat, Mapping):
            continue
        beat_id = beat.get("id", len(lines) + 1)
        function = _text(beat.get("story_function"))
        action = _text(beat.get("visible_action"))
        pressure = _text(beat.get("pressure_delta"))
        state_out = _text(beat.get("state_out"))
        parts = [part for part in (function, action, pressure, state_out) if part]
        prefix = "节拍" if _is_zh(language) else "Beat"
        lines.append(f"{prefix} {beat_id}: " + " | ".join(parts))
    return "\n".join(lines)


def _render_dialogues(dialogues: Any, language: Any = "English") -> str:
    if not isinstance(dialogues, list):
        return ""
    blocks = []
    zh = _is_zh(language)
    for idx, dialogue in enumerate(dialogues, start=1):
        if not isinstance(dialogue, Mapping):
            continue
        speaker = _text(dialogue.get("speaker")) or ("未指定角色" if zh else "Unspecified speaker")
        voice = _text(dialogue.get("voice_direction")) or ("自然、清晰" if zh else "Natural and readable")
        state = _text(dialogue.get("state")) or ("保持当前场景状态" if zh else "Maintain scene state")
        tone = _text(dialogue.get("tone")) or ("与场景一致" if zh else "Consistent with the scene")
        text = _text(dialogue.get("text"))
        if zh:
            blocks.append(
                f"[台词 {idx}｜{speaker}｜配音指导：{voice}｜状态：{state}｜语气：{tone}｜对白：{text}]"
            )
        else:
            blocks.append(
                f"[Dialogue {idx} | {speaker} | Voice Direction: {voice} | State: {state} | Tone: {tone} | Dialogue: {text}]"
            )
    return "\n".join(blocks)


def _render_offscreen(events: Any, language: Any = "English") -> str:
    if not isinstance(events, list):
        return ""
    lines = []
    zh = _is_zh(language)
    for idx, event in enumerate(events, start=1):
        if not isinstance(event, Mapping):
            continue
        source = _text(event.get("source")) or ("画外" if zh else "off-screen")
        event_text = _text(event.get("event"))
        delivery = _text(event.get("delivery"))
        reaction = _text(event.get("reaction"))
        if zh:
            lines.append(
                f"[画外事件 {idx}｜来源：{source}｜事件：{event_text}｜声音表现：{delivery}｜人物反应：{reaction}]"
            )
        else:
            lines.append(
                f"[Off-screen Event {idx} | Source: {source} | Event: {event_text} | Delivery: {delivery} | Reaction: {reaction}]"
            )
    return "\n".join(lines)


def _render_timeline(beats: Any) -> str:
    if not isinstance(beats, list):
        return ""
    lines = []
    for beat in beats:
        if not isinstance(beat, Mapping):
            continue
        start = float(beat.get("global_start", 0.0) or 0.0)
        end = float(beat.get("global_end", 0.0) or 0.0)
        lines.append(f"{start:.2f}–{end:.2f}s: {_text(beat.get('description'))}")
    return "\n".join(lines)


def render_shot_block(
    shot: Mapping[str, Any],
    *,
    module_states: Mapping[str, str],
    language: Any = "English",
    keywords: Any = "",
    config: Mapping[str, Any] | None = None,
    speaker_ids: Mapping[str, str] | None = None,
) -> str:
    shot_id = int(shot.get("id", 0) or 0)
    start = float(shot.get("start_time", 0.0) or 0.0)
    end = float(shot.get("end_time", 0.0) or 0.0)
    prefix = "镜头" if _is_zh(language) else "Shot"
    lines = [f"{prefix} {shot_id} · {start:.2f}–{end:.2f}s", ""]

    # When shot_prompts is consumed independently, every shot carries the exact
    # LoRA trigger tokens so downstream per-shot generation cannot lose them.
    _append_section(lines, "LORA KEYWORDS", keywords, language)

    if _active(module_states, "shot_planning"):
        _append_section(lines, "PURPOSE", shot.get("purpose"), language)
    if _active(module_states, "camera_language"):
        _append_section(lines, "CAMERA CAPTURE", shot.get("camera_capture"), language)

    _append_section(lines, "VISUAL INFORMATION", shot.get("visual_information"), language)

    if _active(module_states, "blocking_staging"):
        blocking_parts = [
            _text(shot.get("blocking_start")),
            _text(shot.get("blocking_motion")),
            _text(shot.get("blocking_end")),
        ]
        _append_section(lines, "BLOCKING & STAGING", " → ".join(part for part in blocking_parts if part), language)
    if _active(module_states, "performance_direction"):
        _append_section(lines, "PERFORMANCE & ACTION", shot.get("performance_action"), language)
        _append_section(lines, "FACIAL EXPRESSION & EYELINE", shot.get("facial_expression_eyeline"), language)
    if _active(module_states, "lighting_color"):
        _append_section(lines, "LIGHTING DESIGN", shot.get("lighting_design"), language)
    if _active(module_states, "spatial_continuity") or _active(module_states, "reference_binding"):
        _append_section(lines, "SPATIAL / ENTITY CONSTRAINTS", shot.get("spatial_entity_constraints"), language)
    if _active(module_states, "reference_binding"):
        _append_section(lines, "REFERENCE ASSIGNMENTS", shot.get("reference_assignments"), language)
    if _active(module_states, "character_continuity"):
        _append_section(lines, "CHARACTER CONTINUITY ANCHORS", shot.get("character_continuity_anchors"), language)
    if _active(module_states, "keyframe_strategy"):
        _append_section(lines, "KEYFRAME NOTE", shot.get("keyframe_note"), language)
    if _active(module_states, "model_adapter"):
        _append_section(lines, "MODEL GENERATION NOTE", shot.get("model_generation_note"), language)

    _append_section(lines, "ACTION TIMELINE", _render_timeline(shot.get("action_beats")), language)

    cfg = dict(config or {})
    is_h3 = _text(cfg.get("target_model")) == "MiniMax / Hailuo"
    if is_h3:
        h3_audio = compile_h3_dialogue_blocks(
            shot.get("dialogues", []) if isinstance(shot.get("dialogues"), list) else [],
            shot.get("exact_offscreen_dialogues", []) if isinstance(shot.get("exact_offscreen_dialogues"), list) else [],
            strict_speech_lock=bool(cfg.get("strict_speech_lock", False)),
            speaker_ids=speaker_ids,
        )
        if h3_audio:
            _append_section(lines, "H3 DIALOGUE / VOICE CONTROL", h3_audio, language)
        if _active(module_states, "sound_offscreen"):
            if cfg.get("audio_policy") == "Full Auto Audio":
                _append_section(lines, "OFF-SCREEN / AUDIO EVENTS", _render_offscreen(shot.get("offscreen_events"), language), language)
            _append_section(lines, "NON-SPEECH SOUND LAYERS", shot.get("sound_layers"), language)
    else:
        dialogue_text = _render_dialogues(shot.get("dialogues"), language)
        if dialogue_text:
            _append_section(lines, "DIALOGUE", dialogue_text, language)
        if _active(module_states, "sound_offscreen"):
            _append_section(lines, "OFF-SCREEN / AUDIO EVENTS", _render_offscreen(shot.get("offscreen_events"), language), language)
            _append_section(lines, "SOUND LAYERS", shot.get("sound_layers"), language)

    _append_section(lines, "CONTINUITY IN", shot.get("continuity_in"), language)
    _append_section(lines, "CONTINUITY OUT", shot.get("continuity_out"), language)
    if _active(module_states, "transition_editing"):
        _append_section(lines, "INTER-SHOT CONTINUITY", shot.get("transition_continuity"), language)
        _append_section(lines, "EDIT NOTE", shot.get("edit_note"), language)
    if _active(module_states, "clip_handoff"):
        _append_section(lines, "RECEIVER-IN", shot.get("receiver_in"), language)
        _append_section(lines, "HANDOFF-OUT", shot.get("handoff_out"), language)
    if _active(module_states, "qc_failure_prevention"):
        _append_section(lines, "RISK / QC NOTE", shot.get("risk"), language)
        _append_section(lines, "NEGATIVE CONSTRAINTS", shot.get("negative_prompt"), language)

    return "\n".join(lines).strip()


def render_shot_prompts(
    storyboard: Mapping[str, Any],
    *,
    module_states: Mapping[str, str],
    language: Any = "English",
    include_keywords: bool = True,
    config: Mapping[str, Any] | None = None,
) -> str:
    keywords = storyboard.get("keywords") if include_keywords else ""
    cfg = dict(config or {})
    speaker_ids = collect_storyboard_speaker_ids(storyboard) if _text(cfg.get("target_model")) == "MiniMax / Hailuo" else {}
    blocks = [
        render_shot_block(
            shot,
            module_states=module_states,
            language=language,
            keywords=keywords,
            config=cfg,
            speaker_ids=speaker_ids,
        )
        for shot in storyboard.get("shots", [])
        if isinstance(shot, Mapping)
    ]
    return "\n\n---\n\n".join(blocks).strip()


def render_master_prompt(
    storyboard: Mapping[str, Any],
    *,
    module_states: Mapping[str, str],
    config: Mapping[str, Any],
) -> str:
    language = config.get("language", "English")
    zh = _is_zh(language)
    if zh:
        lines = [
            _heading("PRODUCTION DIRECTOR PROMPT", language),
            "",
            f"标题：{_text(storyboard.get('title')) or '未命名'}",
            f"总时长：{float(storyboard.get('total_duration', 0.0) or 0.0):.2f}s",
            f"画面比例：{_text(config.get('aspect_ratio'))}",
            f"生成方式：{_text(config.get('generation_mode'))}",
            f"目标模型：{_text(config.get('target_model'))}",
            f"导演预设：{_text(config.get('director_preset'))}",
            f"语音策略：{_text(config.get('audio_policy')) or 'Dialogue + Exact Offscreen'}",
            f"严格对白锁定：{bool(config.get('strict_speech_lock', False))}",
            "",
        ]
    else:
        lines = [
            _heading("PRODUCTION DIRECTOR PROMPT", language),
            "",
            f"TITLE: {_text(storyboard.get('title')) or 'Untitled'}",
            f"TOTAL DURATION: {float(storyboard.get('total_duration', 0.0) or 0.0):.2f}s",
            f"ASPECT RATIO: {_text(config.get('aspect_ratio'))}",
            f"GENERATION MODE: {_text(config.get('generation_mode'))}",
            f"TARGET MODEL: {_text(config.get('target_model'))}",
            f"DIRECTOR PRESET: {_text(config.get('director_preset'))}",
            f"AUDIO POLICY: {_text(config.get('audio_policy')) or 'Dialogue + Exact Offscreen'}",
            f"STRICT SPEECH LOCK: {bool(config.get('strict_speech_lock', False))}",
            "",
        ]

    _append_section(lines, "OVERVIEW", storyboard.get("overview"), language)
    _append_section(lines, "ASSUMPTIONS", storyboard.get("assumptions"), language)
    if _active(module_states, "shot_planning"):
        _append_section(lines, "SHOT BUDGET RATIONALE", storyboard.get("shot_budget_reason") or storyboard.get("shot_count_reason"), language)
    _append_section(lines, "CHARACTER NAMES — VERBATIM", storyboard.get("character_names"), language)
    _append_section(lines, "CHARACTER PROFILES", storyboard.get("character_profiles"), language)
    _append_section(lines, "CHARACTER RELATIONSHIPS", storyboard.get("character_relationships"), language)
    _append_section(lines, "SCENE ENVIRONMENT", storyboard.get("scene_environment"), language)
    _append_section(lines, "KEYWORDS — VERBATIM", storyboard.get("keywords"), language)
    _append_section(lines, "EXTRA REQUIREMENTS", storyboard.get("extra_requirements"), language)

    if _active(module_states, "reference_binding"):
        _append_section(lines, "REFERENCE & ENTITY BINDINGS", storyboard.get("entity_reference_bindings"), language)
        _append_section(lines, "REFERENCE SUMMARY", storyboard.get("reference_summary"), language)
    if _active(module_states, "story_subtext"):
        _append_section(lines, "SCENE OBJECTIVE", storyboard.get("scene_objective"), language)
        _append_section(lines, "LITERAL EVENT", storyboard.get("literal_event"), language)
        _append_section(lines, "DRAMATIC QUESTION", storyboard.get("dramatic_question"), language)
        _append_section(lines, "CONFLICT", storyboard.get("conflict"), language)
        _append_section(lines, "SUBTEXT", storyboard.get("subtext"), language)
        _append_section(lines, "EMOTIONAL MOVEMENT", storyboard.get("emotional_movement"), language)
        _append_section(lines, "VISUAL THESIS", storyboard.get("visual_thesis"), language)
    if _active(module_states, "dramatic_beats"):
        _append_section(lines, "DRAMATIC BEATS", _render_beats(storyboard.get("dramatic_beats"), language), language)
    if _active(module_states, "director_book"):
        _append_section(lines, "DIRECTOR BOOK / VISUAL TREATMENT", storyboard.get("director_book"), language)
        _append_section(lines, "VISUAL CONTINUITY", storyboard.get("visual_continuity"), language)
    if _active(module_states, "blocking_staging"):
        _append_section(lines, "GLOBAL BLOCKING & STAGING", storyboard.get("blocking_staging"), language)
    if _active(module_states, "camera_language"):
        _append_section(lines, "GLOBAL CAMERA REQUIREMENTS", storyboard.get("camera_requirements"), language)
    if _active(module_states, "performance_direction"):
        _append_section(lines, "GLOBAL PERFORMANCE REQUIREMENTS", storyboard.get("performance_requirements"), language)
    if _active(module_states, "spatial_continuity"):
        _append_section(lines, "SPATIAL CONTINUITY", storyboard.get("spatial_continuity"), language)
    if _active(module_states, "character_continuity"):
        _append_section(lines, "CHARACTER CONTINUITY", storyboard.get("character_continuity"), language)
    if _active(module_states, "lighting_color"):
        _append_section(lines, "GLOBAL LIGHTING & COLOR", storyboard.get("lighting_requirements"), language)
    if _active(module_states, "dialogue_direction"):
        _append_section(lines, "GLOBAL DIALOGUE DIRECTION", storyboard.get("dialogue_direction"), language)
    if _active(module_states, "sound_offscreen"):
        _append_section(lines, "GLOBAL SOUND DESIGN", storyboard.get("sound_design"), language)
        _append_section(lines, "GLOBAL OFF-SCREEN AUDIO", storyboard.get("offscreen_audio"), language)
    if _active(module_states, "keyframe_strategy"):
        _append_section(lines, "KEYFRAME STRATEGY", storyboard.get("keyframe_strategy"), language)
    if _active(module_states, "transition_editing"):
        _append_section(lines, "TRANSITION & EDIT ASSEMBLY", storyboard.get("edit_assembly_plan"), language)
        _append_section(lines, "GLOBAL TRANSITION CONTINUITY", storyboard.get("transition_continuity"), language)
    if _active(module_states, "genre_playbook"):
        _append_section(lines, "GENRE PLAYBOOK", storyboard.get("genre_playbook"), language)
    if _active(module_states, "directing_style"):
        _append_section(lines, "DIRECTING STYLE LENS", storyboard.get("directing_style"), language)
    if _active(module_states, "clip_handoff"):
        _append_section(lines, "CLIP HANDOFF PLAN", storyboard.get("clip_handoff_plan"), language)
    if _active(module_states, "model_adapter"):
        _append_section(lines, "TARGET MODEL ADAPTER", storyboard.get("model_adapter"), language)
    if _active(module_states, "qc_failure_prevention"):
        _append_section(lines, "QC PLAN", storyboard.get("qc_plan"), language)
        _append_section(lines, "GLOBAL NEGATIVE CONSTRAINTS", storyboard.get("negative_constraints"), language)
    if _active(module_states, "product_macro"):
        _append_section(lines, "PRODUCT / MACRO PLAN", storyboard.get("product_macro_plan"), language)

    # The master prompt already carries the global keyword lock once above.
    shot_text = render_shot_prompts(storyboard, module_states=module_states, language=language, include_keywords=False, config=config)
    if shot_text:
        lines.extend([_heading("SHOTS", language), "", shot_text])
    return "\n".join(lines).strip()


def render_director_summary(
    storyboard: Mapping[str, Any],
    *,
    module_states: Mapping[str, str],
    preset: str,
    language: Any = "English",
) -> str:
    zh = _is_zh(language)
    if zh:
        lines = [
            f"标题：{_text(storyboard.get('title')) or '未命名'}",
            f"预设：{preset}",
            f"总时长：{float(storyboard.get('total_duration', 0.0) or 0.0):.2f}s",
            f"镜头数量：{int(storyboard.get('shot_count', 0) or 0)}",
            f"分镜计划锁定：{bool(storyboard.get('shot_plan_locked'))}",
            f"镜头时间锁定：{bool(storyboard.get('shot_timing_locked'))}",
            "",
            "已加载模块：",
        ]
    else:
        lines = [
            f"Title: {_text(storyboard.get('title')) or 'Untitled'}",
            f"Preset: {preset}",
            f"Total duration: {float(storyboard.get('total_duration', 0.0) or 0.0):.2f}s",
            f"Shot count: {int(storyboard.get('shot_count', 0) or 0)}",
            f"Shot plan locked: {bool(storyboard.get('shot_plan_locked'))}",
            f"Shot timing locked: {bool(storyboard.get('shot_timing_locked'))}",
            "",
            "Loaded modules:",
        ]
    for key, spec in MODULE_SPECS.items():
        state = module_states.get(key, "Off")
        if state != "Off":
            title = spec.title_zh if zh else spec.title_en
            lines.append(f"- {title}: {state}")

    lines.append("")
    lines.append("镜头概览：" if zh else "Shot overview:")
    prefix = "镜头" if zh else "Shot"
    for shot in storyboard.get("shots", []):
        if not isinstance(shot, Mapping):
            continue
        lines.append(
            f"- {prefix} {int(shot.get('id', 0) or 0)} | "
            f"{float(shot.get('start_time', 0.0) or 0.0):.2f}–{float(shot.get('end_time', 0.0) or 0.0):.2f}s | "
            f"{_text(shot.get('purpose'))}"
        )
    return "\n".join(lines).strip()
