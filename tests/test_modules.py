from director_modules import MODULE_SPECS, PRESET_STATES, VALID_MODULE_STATES, resolve_module_states


def test_module_inventory_contains_all_planned_modules():
    expected = {
        "story_subtext",
        "dramatic_beats",
        "director_book",
        "blocking_staging",
        "shot_planning",
        "camera_language",
        "performance_direction",
        "spatial_continuity",
        "character_continuity",
        "lighting_color",
        "dialogue_direction",
        "sound_offscreen",
        "keyframe_strategy",
        "transition_editing",
        "genre_playbook",
        "directing_style",
        "reference_binding",
        "clip_handoff",
        "model_adapter",
        "qc_failure_prevention",
        "product_macro",
    }
    assert set(MODULE_SPECS) == expected
    assert VALID_MODULE_STATES == ("Off", "Auto", "Guided")


def test_every_module_has_state_and_guidance_widget_names():
    for key, spec in MODULE_SPECS.items():
        assert spec.key == key
        assert spec.state_input == f"module_{key}"
        assert spec.guidance_input
        assert spec.title_en
        assert spec.title_zh
        assert spec.skill_prompt.strip()


def test_presets_exist_and_resolve_all_modules():
    for preset in ("Full Auto Director", "Professional", "Simple", "Custom"):
        assert preset in PRESET_STATES

    full_auto = resolve_module_states("Full Auto Director", {})
    professional = resolve_module_states("Professional", {})
    simple = resolve_module_states("Simple", {})

    assert set(full_auto) == set(MODULE_SPECS)
    assert set(professional) == set(MODULE_SPECS)
    assert set(simple) == set(MODULE_SPECS)
    assert all(state in VALID_MODULE_STATES for state in full_auto.values())
    assert full_auto["story_subtext"] == "Auto"
    assert full_auto["product_macro"] == "Off"
    assert professional["clip_handoff"] == "Auto"
    assert simple["keyframe_strategy"] == "Off"
    assert simple["story_subtext"] == "Auto"


def test_custom_preset_uses_valid_user_states_and_sanitizes_unknown_values():
    raw = {
        "module_story_subtext": "Guided",
        "module_dramatic_beats": "Off",
        "module_camera_language": "nonsense",
    }
    resolved = resolve_module_states("Custom", raw)
    assert resolved["story_subtext"] == "Guided"
    assert resolved["dramatic_beats"] == "Off"
    assert resolved["camera_language"] == MODULE_SPECS["camera_language"].default_state


def test_non_custom_preset_overrides_manual_state_widgets():
    raw = {"module_story_subtext": "Off", "module_product_macro": "Guided"}
    resolved = resolve_module_states("Full Auto Director", raw)
    assert resolved["story_subtext"] == "Auto"
    assert resolved["product_macro"] == "Off"
