from director_modules import MODULE_SPECS
from renderer import render_director_summary, render_master_prompt, render_shot_prompts


def _states(default="Off", **overrides):
    out = {key: default for key in MODULE_SPECS}
    out.update(overrides)
    return out


def _storyboard():
    return {
        "title": "Stone Chamber Interruption",
        "overview": "An oppressive approach is interrupted.",
        "total_duration": 12.0,
        "shot_count": 1,
        "character_names": "@铁角妖王, @紫衣女妖",
        "keywords": "紫衣女妖触发词, X9_LoRA",
        "scene_objective": "Establish pressure and interrupt it.",
        "lighting_requirements": "Cold cyan rear-left light and warm doorway firelight.",
        "reference_summary": "Reference 1: @铁角妖王; Reference 2: @紫衣女妖",
        "module_report": [
            {"key": "story_subtext", "title": "Story & Subtext", "state": "Auto", "has_user_data": False},
            {"key": "camera_language", "title": "Camera Language", "state": "Guided", "has_user_data": True},
        ],
        "shots": [
            {
                "id": 1,
                "start_time": 0.0,
                "end_time": 12.0,
                "duration": 12.0,
                "purpose": "Establish and interrupt pressure.",
                "camera_capture": "Stable medium close two-shot with a subtle push-in.",
                "visual_information": "@铁角妖王 leans toward @紫衣女妖 beside the stone table.",
                "performance_action": "He advances and holds; she contracts her shoulders.",
                "facial_expression_eyeline": "She raises her eyes briefly, then averts them.",
                "lighting_design": "Cold cyan rim and warm doorway edge light.",
                "spatial_entity_constraints": "Keep the stone table behind @紫衣女妖.",
                "continuity_in": "Both remain beside the table.",
                "continuity_out": "@铁角妖王 turns his gaze toward the doorway.",
                "transition_continuity": "Carry his doorway eyeline into the next clip.",
                "action_beats": [
                    {"global_start": 0.0, "global_end": 2.0, "description": "He closes distance."},
                    {"global_start": 2.0, "global_end": 12.0, "description": "She speaks and the interruption lands."},
                ],
                "dialogues": [
                    {
                        "speaker": "@紫衣女妖",
                        "voice_direction": "Low and restrained.",
                        "state": "Shy but controlled.",
                        "tone": "Slightly slow.",
                        "text": "妖王，您明日便要大婚了，切莫如此……",
                    }
                ],
                "offscreen_events": [
                    {
                        "source": "@石室门口",
                        "event": "A wedding announcement enters off-screen.",
                        "delivery": "Sudden and clear.",
                        "reaction": "Both freeze; he redirects his gaze.",
                    }
                ],
                "negative_prompt": "identity drift, layout change",
            }
        ],
    }


def test_master_prompt_omits_disabled_module_sections_even_if_data_exists():
    text = render_master_prompt(
        _storyboard(),
        module_states=_states(story_subtext="Auto", camera_language="Auto", lighting_color="Off"),
        config={"aspect_ratio": "16:9", "target_model": "MiniMax / Hailuo", "generation_mode": "Reference to Video", "director_preset": "Custom"},
    )
    assert "SCENE OBJECTIVE" in text
    assert "CAMERA CAPTURE" in text
    assert "LIGHTING DESIGN" not in text
    assert "Cold cyan rear-left light" not in text


def test_master_prompt_renders_enabled_lighting_and_literal_locks_verbatim():
    text = render_master_prompt(
        _storyboard(),
        module_states=_states(story_subtext="Auto", camera_language="Auto", lighting_color="Auto", dialogue_direction="Auto"),
        config={"aspect_ratio": "16:9", "target_model": "MiniMax / Hailuo", "generation_mode": "Reference to Video", "director_preset": "Full Auto Director"},
    )
    assert "LIGHTING DESIGN" in text
    assert "@铁角妖王, @紫衣女妖" in text
    assert "紫衣女妖触发词, X9_LoRA" in text
    assert "妖王，您明日便要大婚了，切莫如此……" in text
    assert "@PurpleDemoness" not in text


def test_shot_block_contains_timing_action_timeline_dialogue_and_end_state():
    text = render_shot_prompts(
        _storyboard(),
        module_states=_states(camera_language="Auto", performance_direction="Auto", dialogue_direction="Auto", spatial_continuity="Auto", qc_failure_prevention="Auto"),
    )
    assert "Shot 1 · 0.00–12.00s" in text
    assert "ACTION TIMELINE" in text
    assert "0.00–2.00s" in text
    assert "DIALOGUE" in text
    assert "CONTINUITY OUT" in text
    assert "NEGATIVE CONSTRAINTS" in text


def test_director_summary_reports_loaded_modules_states_and_shot_count():
    text = render_director_summary(
        _storyboard(),
        module_states=_states(story_subtext="Auto", camera_language="Guided"),
        preset="Custom",
    )
    assert "Preset: Custom" in text
    assert "Story & Subtext: Auto" in text
    assert "Camera Language: Guided" in text
    assert "Shot count: 1" in text
    assert "0.00–12.00s" in text


def test_master_prompt_renders_baseline_user_information_sections():
    board = _storyboard()
    board.update(
        {
            "character_profiles": "@铁角妖王 wears horned armor; @紫衣女妖 wears purple robes.",
            "character_relationships": "He controls the distance; she resists while constrained.",
            "scene_environment": "A cold stone chamber with a stone table and a warm-lit doorway.",
            "extra_requirements": "Preserve the intimate oppressive tone without explicit contact.",
        }
    )
    text = render_master_prompt(
        board,
        module_states=_states(),
        config={
            "aspect_ratio": "16:9",
            "target_model": "MiniMax / Hailuo",
            "generation_mode": "Reference to Video",
            "director_preset": "Full Auto Director",
        },
    )
    assert "CHARACTER PROFILES" in text
    assert "CHARACTER RELATIONSHIPS" in text
    assert "SCENE ENVIRONMENT" in text
    assert "EXTRA REQUIREMENTS" in text


def test_master_prompt_explains_assumptions_and_shot_budget_when_available():
    board = _storyboard()
    board["assumptions"] = ["The wedding announcement comes from the doorway."]
    board["shot_budget_reason"] = "Four shots correspond to approach, dialogue, interruption, and reaction."
    text = render_master_prompt(
        board,
        module_states=_states(shot_planning="Auto"),
        config={
            "aspect_ratio": "16:9",
            "target_model": "MiniMax / Hailuo",
            "generation_mode": "Reference to Video",
            "director_preset": "Full Auto Director",
        },
    )
    assert "ASSUMPTIONS" in text
    assert "SHOT BUDGET RATIONALE" in text
    assert "approach, dialogue, interruption, and reaction" in text


def test_chinese_output_localizes_master_and_shot_headings_and_keeps_keywords_verbatim():
    board = _storyboard()
    text = render_master_prompt(
        board,
        module_states=_states(story_subtext="Auto", camera_language="Auto", performance_direction="Auto"),
        config={
            "aspect_ratio": "9:16",
            "target_model": "MiniMax / Hailuo",
            "generation_mode": "Reference to Video",
            "director_preset": "Full Auto Director",
            "language": "中文",
        },
    )
    assert "制作导演提示词" in text
    assert "角色名称（原样保留）" in text
    assert "镜头 1 · 0.00–12.00s" in text
    assert "镜头技术捕捉" in text
    assert "紫衣女妖触发词, X9_LoRA" in text


def test_standalone_shot_prompts_repeat_lora_keywords_for_each_shot():
    board = _storyboard()
    board["shots"] = [dict(board["shots"][0]), dict(board["shots"][0], id=2)]
    text = render_shot_prompts(
        board,
        module_states=_states(camera_language="Auto"),
        language="中文",
        include_keywords=True,
    )
    assert text.count("LoRA 触发词 / Keywords（原样保留）") == 2
    assert text.count("紫衣女妖触发词, X9_LoRA") == 2
