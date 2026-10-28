from director_modules import MODULE_SPECS
from director_router import (
    build_director_system_prompt,
    build_dynamic_schema,
    build_module_context,
    resolve_module_runtime,
)


def _states(default="Off", **overrides):
    out = {key: default for key in MODULE_SPECS}
    out.update(overrides)
    return out


def test_permanent_core_contains_all_six_unavoidable_rules():
    prompt = build_director_system_prompt(_states())
    low = prompt.lower()
    assert "story function" in low
    assert "blocking before framing" in low
    assert "one dominant camera behavior" in low
    assert "start state" in low and "end state" in low
    assert "observable" in low and "emotion" in low
    assert "continuity" in low and "engineered" in low


def test_off_module_is_not_loaded_into_system_prompt():
    prompt = build_director_system_prompt(_states(story_subtext="Auto", lighting_color="Off"))
    assert "MODULE: STORY & SUBTEXT" in prompt
    assert "MODULE: LIGHTING & COLOR" not in prompt
    assert MODULE_SPECS["lighting_color"].skill_prompt not in prompt


def test_auto_module_with_user_data_marks_it_as_user_supplied_constraint():
    inputs = {
        "scene_objective": "建立压迫关系",
        "story_subtext_guidance": "",
        "prompt": "妖王逼近女妖",
    }
    runtime = resolve_module_runtime(_states(story_subtext="Auto"), inputs)
    block = build_module_context(runtime)
    assert "Story & Subtext" in block
    assert "USER-SUPPLIED CONSTRAINT" in block
    assert "建立压迫关系" in block
    assert "AI-GENERATE MISSING MATERIAL" in block


def test_guided_module_marks_non_empty_guidance_as_hard_intent_lock():
    inputs = {"camera_requirements": "中近景，轻微前移，不要环绕"}
    runtime = resolve_module_runtime(_states(camera_language="Guided"), inputs)
    block = build_module_context(runtime)
    assert "HARD USER INTENT LOCK" in block
    assert "中近景，轻微前移，不要环绕" in block
    assert "may professionalize" in block.lower()
    assert "must not contradict" in block.lower()


def test_guided_empty_field_falls_back_to_ai_generation():
    runtime = resolve_module_runtime(_states(blocking_staging="Guided"), {})
    block = build_module_context(runtime)
    assert "GUIDED FIELD IS BLANK" in block
    assert "AI-GENERATE" in block


def test_dynamic_schema_only_contains_enabled_module_fields():
    schema = build_dynamic_schema(
        _states(shot_planning="Auto", camera_language="Auto", lighting_color="Off")
    )
    assert '"shot_budget_reason"' in schema
    assert '"camera_capture"' in schema
    assert '"lighting_design"' not in schema
    assert '"shots"' in schema
    assert '"dialogues"' in schema  # common literal-lock container


def test_runtime_metadata_exposes_loaded_modules_and_states():
    runtime = resolve_module_runtime(
        _states(story_subtext="Auto", camera_language="Guided"),
        {"camera_requirements": "locked camera"},
    )
    assert list(runtime) == ["story_subtext", "camera_language"]
    assert runtime["story_subtext"].state == "Auto"
    assert runtime["camera_language"].state == "Guided"
    assert runtime["camera_language"].user_values["camera_requirements"] == "locked camera"


def test_dynamic_schema_always_requests_minimum_production_fields():
    schema = build_dynamic_schema(_states())
    for field in (
        '"scene_objective"',
        '"character_profiles"',
        '"character_relationships"',
        '"scene_environment"',
        '"extra_requirements"',
        '"purpose"',
        '"visual_information"',
        '"performance_action"',
    ):
        assert field in schema


def test_generation_mode_guidance_distinguishes_first_frame_reference_and_text_modes():
    from director_router import build_generation_mode_guidance

    image = build_generation_mode_guidance("Image to Video").lower()
    reference = build_generation_mode_guidance("Reference to Video").lower()
    text = build_generation_mode_guidance("Text to Video").lower()
    assert "exact initial visual state" in image
    assert "not a mandatory first frame" in reference
    assert "no visual source" in text


def test_target_model_guidance_has_specific_adapters():
    from director_router import build_target_model_guidance

    assert "restrained camera" in build_target_model_guidance("MiniMax / Hailuo").lower()
    assert "readable motion" in build_target_model_guidance("Wan").lower()
    assert "handoff" in build_target_model_guidance("Seedance").lower()
    assert "temporal" in build_target_model_guidance("Kling").lower()
    assert "environmental response" in build_target_model_guidance("Veo").lower()


def test_sound_fields_are_only_requested_when_sound_module_is_enabled():
    without_sound = build_dynamic_schema(_states())
    with_sound = build_dynamic_schema(_states(sound_offscreen="Auto"))
    assert '"offscreen_events"' not in without_sound
    assert '"sound_layers"' not in without_sound
    assert '"offscreen_events"' in with_sound
    assert '"sound_layers"' in with_sound
