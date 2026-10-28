"""Module catalogue for BUFF AI Director V3.

The prompt blocks in this file are an original, compact adaptation of
transferable directing principles described by the MIT-licensed Cinematic
Director Skill v2.0 by wangzhang-wu. See THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


VALID_MODULE_STATES: Tuple[str, ...] = ("Off", "Auto", "Guided")
DIRECTOR_PRESETS: Tuple[str, ...] = (
    "Full Auto Director",
    "Professional",
    "Simple",
    "Custom",
)


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    title_en: str
    title_zh: str
    guidance_input: str
    default_state: str
    skill_prompt: str
    top_level_fields: Tuple[str, ...] = ()
    shot_fields: Tuple[str, ...] = ()
    source_inputs: Tuple[str, ...] = ()

    @property
    def state_input(self) -> str:
        return f"module_{self.key}"


def _m(
    key: str,
    title_en: str,
    title_zh: str,
    guidance_input: str,
    prompt: str,
    *,
    default: str = "Auto",
    top: Tuple[str, ...] = (),
    shot: Tuple[str, ...] = (),
    source: Tuple[str, ...] = (),
) -> ModuleSpec:
    return ModuleSpec(
        key=key,
        title_en=title_en,
        title_zh=title_zh,
        guidance_input=guidance_input,
        default_state=default,
        skill_prompt=prompt.strip(),
        top_level_fields=top,
        shot_fields=shot,
        source_inputs=source,
    )


MODULE_SPECS: Dict[str, ModuleSpec] = {
    "story_subtext": _m(
        "story_subtext",
        "Story & Subtext",
        "剧情与潜台词",
        "story_subtext_guidance",
        """
Identify the literal event, dramatic question, external and internal conflict,
subtext, emotional movement, and one concrete visual thesis. The visual thesis
must describe a change that can be photographed, not an abstract theme. Every
later directing decision must serve this analysis.
""",
        top=("literal_event", "dramatic_question", "conflict", "subtext", "emotional_movement", "visual_thesis"),
        source=("prompt", "scene_objective", "story_subtext_guidance"),
    ),
    "dramatic_beats": _m(
        "dramatic_beats",
        "Dramatic Beats",
        "戏剧节拍",
        "dramatic_beats_guidance",
        """
Break the scene into beats before shots. A beat is a visible change in pressure,
information, intention, power, emotion, or action. For each beat define story
function, character state in/out, visible action, pressure change, and likely
shot family. Do not create a new beat merely because the camera changes.
""",
        top=("dramatic_beats",),
        source=("dramatic_beats_guidance", "shot_plan"),
    ),
    "director_book": _m(
        "director_book",
        "Director Book / Visual Treatment",
        "导演书与视觉统筹",
        "director_book_guidance",
        """
Create a reusable visual rule set: tone, palette, framing policy, allowed camera
moves, performance register, production-design logic, editing rhythm, sound
direction, and invariant clauses. The result must be specific enough that two
artists could create compatible shots from it.
""",
        top=("director_book", "visual_continuity"),
        source=("director_book_guidance", "visual_style", "visual_continuity"),
    ),
    "blocking_staging": _m(
        "blocking_staging",
        "Blocking & Staging",
        "人物走位与调度",
        "blocking_staging_guidance",
        """
Design bodies in space before choosing framing. Define start position, movement,
interaction with props and architecture, distance changes, eyelines, camera
relationship, and end position. Blocking must reveal power, attraction, fear,
secrecy, isolation, irony, or another story relationship.
""",
        top=("blocking_staging",),
        shot=("blocking_start", "blocking_motion", "blocking_end"),
        source=("blocking_staging_guidance", "character_relationships", "spatial_continuity"),
    ),
    "shot_planning": _m(
        "shot_planning",
        "Shot Planning",
        "分镜规划",
        "shot_plan",
        """
Build shots only after beats and blocking are clear. Every shot needs a story
function and must change what the audience understands, feels, or anticipates.
Choose shot count from dramatic necessity, dialogue duration, action complexity,
reaction needs, and the safe duration budget; never generate variety for its own
sake. Respect any explicit user shot order and timing as hard locks.
""",
        top=("shot_budget_reason",),
        shot=("purpose",),
        source=("shot_plan",),
    ),
    "camera_language": _m(
        "camera_language",
        "Camera Language",
        "摄影机语言",
        "camera_requirements",
        """
For each shot specify readable framing, lens behavior, angle, camera position,
and at most one dominant camera behavior. A locked camera is valid. Camera
movement must follow blocking and story function, preserve the action axis,
screen direction, eyeline logic, and sufficient angle change between cuts.
""",
        top=("camera_requirements",),
        shot=("camera_capture",),
        source=("camera_requirements", "camera_style"),
    ),
    "performance_direction": _m(
        "performance_direction",
        "Performance Direction",
        "人物表演指导",
        "performance_requirements",
        """
Translate emotion into observable behavior: posture, body weight, breathing,
facial tension, eye movement, hand behavior, hesitation, reaction, and recovery.
Every action must have a visible start state, continuous progression, and clear
end state that can be inherited by the next shot.
""",
        top=("performance_requirements",),
        shot=("performance_action", "facial_expression_eyeline"),
        source=("performance_requirements",),
    ),
    "spatial_continuity": _m(
        "spatial_continuity",
        "Spatial Continuity",
        "空间连续性",
        "spatial_continuity",
        """
Engineer geography explicitly. Lock character and prop positions, distances,
entry/exit directions, screen direction, eyelines, action axis, doorway/window
orientation, and movement vectors. Each shot must state inherited spatial state
and its end-state handoff.
""",
        top=("spatial_continuity",),
        shot=("spatial_entity_constraints", "continuity_in", "continuity_out"),
        source=("spatial_continuity",),
    ),
    "character_continuity": _m(
        "character_continuity",
        "Character Continuity",
        "角色连续性",
        "visual_continuity",
        """
Lock identity, face, hairstyle, costume, body proportions, accessories, props,
handedness, injuries, and object states. Repeat invariant identity clauses
consistently across shots. Do not redesign any user-supplied reference identity.
""",
        top=("character_continuity",),
        shot=("character_continuity_anchors",),
        source=("character_names", "character_profiles", "visual_continuity"),
    ),
    "lighting_color": _m(
        "lighting_color",
        "Lighting & Color",
        "灯光与色彩",
        "lighting_requirements",
        """
Define motivated light sources, direction, color, quality, contrast, practicals,
rim/key/fill behavior, shadow response, palette, and continuity. Preserve the
same light direction unless the story or camera geography clearly justifies a
change. Describe what the light does to subjects and surfaces.
""",
        top=("lighting_requirements",),
        shot=("lighting_design",),
        source=("lighting_requirements",),
    ),
    "dialogue_direction": _m(
        "dialogue_direction",
        "Dialogue Direction",
        "对白与配音指导",
        "dialogue_direction",
        """
Preserve user dialogue verbatim. Direct breathing, volume, pace, pauses, stress,
mouth start/end state, eyeline, body reaction, and the physical consequence of
speech. Prefer one clearly identified speaker per generated clip unless the
model and user plan explicitly support more.
""",
        top=("dialogue_direction",),
        shot=("dialogues",),
        source=("dialogue_text", "dialogue_direction"),
    ),
    "sound_offscreen": _m(
        "sound_offscreen",
        "Sound & Off-screen Events",
        "声音与画外事件",
        "sound_design",
        """
Plan room tone, ambience, foley, spot effects, score, silence, and off-screen
voices or actions. Sound may create a dramatic beat and must trigger a visible
reaction when appropriate. Use a continuous ambience bed as continuity glue
across generated clips.
""",
        top=("sound_design", "offscreen_audio"),
        shot=("offscreen_events", "sound_layers"),
        source=("sound_design", "offscreen_audio"),
    ),
    "keyframe_strategy": _m(
        "keyframe_strategy",
        "Keyframe Strategy",
        "关键帧策略",
        "keyframe_strategy_guidance",
        """
Choose the minimum reference strategy that controls the real risk: single first
frame for stable composition, first-plus-last for a defined transformation,
per-shot keyframes for high identity/blocking risk, or storyboard panels for
multi-beat structure. Keyframes must imply motion and pass continuity checks.
""",
        top=("keyframe_strategy",),
        shot=("keyframe_note",),
        source=("keyframe_strategy_guidance",),
    ),
    "transition_editing": _m(
        "transition_editing",
        "Transition & Editing",
        "转场与剪辑",
        "transition_continuity",
        """
Design clip order, edit boundary, trim handles, transition logic, visual/audio
bridges, and the state carried into the next shot. Prefer a clean cut when it
serves the beat. Build matched end/start states rather than hiding bad continuity
with decorative transitions.
""",
        top=("transition_continuity", "edit_assembly_plan"),
        shot=("transition_continuity", "edit_note"),
        source=("transition_continuity", "edit_assembly_guidance"),
    ),
    "genre_playbook": _m(
        "genre_playbook",
        "Genre Playbook",
        "类型片手法",
        "genre_guidance",
        """
Select or obey a genre contract that controls audience expectation, pacing,
shot duration, performance register, reveal strategy, lighting, sound, and risk.
Use genre as a coherent operating system, not a list of adjectives.
""",
        top=("genre_playbook",),
        source=("genre_guidance",),
    ),
    "directing_style": _m(
        "directing_style",
        "Directing Style Lens",
        "导演风格镜头",
        "directing_style_guidance",
        """
Apply one coherent high-level directing lens only. It may govern composition,
lens tendency, camera grammar, palette, lighting, editing rhythm, sound, and
performance, but must never copy a specific existing film shot, character,
dialogue, or plot. Story function and user constraints outrank style.
""",
        top=("directing_style",),
        source=("directing_style_guidance",),
    ),
    "reference_binding": _m(
        "reference_binding",
        "Reference Binding",
        "参考图绑定",
        "reference_binding_guidance",
        """
Bind each connected reference index to a distinct character, prop, location,
layout, or atmosphere role. Preserve multi-entity relationships and prevent
identity or function swapping. State which references are authoritative for
identity, design, geography, lighting, and mood.
""",
        top=("entity_reference_bindings",),
        shot=("reference_assignments",),
        source=("reference_binding_guidance", "reference_manifest"),
    ),
    "clip_handoff": _m(
        "clip_handoff",
        "Clip Handoff",
        "多片段交接",
        "clip_handoff_guidance",
        """
For multi-clip work, design receiver-in and handoff-out states: pose, motion
vector, screen direction, eyeline, prop state, lighting, audio bridge, and any
visual bridge. The next clip must begin from a state the previous clip can
actually end on.
""",
        top=("clip_handoff_plan",),
        shot=("receiver_in", "handoff_out"),
        source=("clip_handoff_guidance",),
    ),
    "model_adapter": _m(
        "model_adapter",
        "Target Model Adapter",
        "目标模型适配",
        "model_adapter_guidance",
        """
Match the prompt to the target model's exposed control surface and generation
mode. Choose motion-only, full-description, keyframe-pair, or timestamped
multi-shot shape as appropriate. Respect the model's safe duration, motion
budget, reference behavior, audio capability, and camera controllability; never
invent unsupported controls.
""",
        top=("model_adapter",),
        shot=("model_generation_note",),
        source=("model_adapter_guidance", "target_model", "generation_mode"),
    ),
    "qc_failure_prevention": _m(
        "qc_failure_prevention",
        "QC & Failure Prevention",
        "质量检查与失败预防",
        "qc_requirements",
        """
Audit reference mismatch, prompt overload, weak implied motion, missing action
endpoint, contradictory camera logic, continuity gaps, and tool mismatch. Add
only targeted negatives tied to real shot risks. Prefer the cheapest structural
fix, and recommend re-planning when a shot is too complex to generate reliably.
""",
        top=("qc_plan", "negative_constraints"),
        shot=("risk", "negative_prompt"),
        source=("qc_requirements", "negative_constraints"),
    ),
    "product_macro": _m(
        "product_macro",
        "Product / Macro Direction",
        "产品与微距导演",
        "product_macro_guidance",
        """
For product, food, cosmetics, packshot, or macro work, replace narrative subtext
with claim, proof, material behavior, hero angle, surface detail, controlled
motion, brand-safe composition, and readable end state. Do not force character
drama onto a product brief.
""",
        default="Off",
        top=("product_macro_plan",),
        shot=("product_proof",),
        source=("product_macro_guidance",),
    ),
}


def _preset(**overrides: str) -> Dict[str, str]:
    values = {key: spec.default_state for key, spec in MODULE_SPECS.items()}
    values.update(overrides)
    return values


PRESET_STATES: Dict[str, Dict[str, str]] = {
    "Full Auto Director": _preset(
        product_macro="Off",
    ),
    "Professional": _preset(
        directing_style="Off",
        product_macro="Off",
    ),
    "Simple": {key: "Off" for key in MODULE_SPECS},
    "Custom": {key: spec.default_state for key, spec in MODULE_SPECS.items()},
}

for _key in (
    "story_subtext",
    "dramatic_beats",
    "blocking_staging",
    "shot_planning",
    "camera_language",
    "performance_direction",
    "spatial_continuity",
    "character_continuity",
    "reference_binding",
    "model_adapter",
    "qc_failure_prevention",
):
    PRESET_STATES["Simple"][_key] = "Auto"


def resolve_module_states(
    preset: str,
    raw_inputs: Mapping[str, object],
) -> Dict[str, str]:
    """Resolve effective module states for one generation.

    Non-Custom presets intentionally override individual widget values. Custom
    uses the user's widgets and falls back to each module's declared default.
    """

    selected = preset if preset in PRESET_STATES else "Full Auto Director"
    if selected != "Custom":
        return dict(PRESET_STATES[selected])

    resolved: Dict[str, str] = {}
    for key, spec in MODULE_SPECS.items():
        value = str(raw_inputs.get(spec.state_input, spec.default_state) or spec.default_state)
        resolved[key] = value if value in VALID_MODULE_STATES else spec.default_state
    return resolved


def active_module_keys(states: Mapping[str, str]) -> Tuple[str, ...]:
    return tuple(key for key in MODULE_SPECS if states.get(key, "Off") != "Off")
