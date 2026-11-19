"""Saved ComfyUI workflows store widget values by position.

These lists are the V3.2.1 input order. New inputs may only be appended after
them; inserting or reordering would shift values in users' saved workflows.
"""

from api_test import BuffAIAPITest
from node import BuffAIDirectorEnhancer

V321_MAIN_REQUIRED = ['prompt', 'duration']
V321_MAIN_OPTIONAL = ['interface_mode', 'professional_section', 'generation_mode', 'aspect_ratio', 'target_model', 'language', 'keywords', 'visual_style', 'action_level', 'mode', 'dialogue_text', 'audio_policy', 'strict_speech_lock', 'offscreen_dialogue_text', 'must_keep', 'must_avoid', 'api_base_url', 'api_model', 'api_key_env_var', 'project_format', 'genre', 'directing_style', 'era_setting', 'scene_objective', 'character_names', 'character_profiles', 'character_relationships', 'scene_environment', 'offscreen_audio', 'extra_requirements', 'shot_mode', 'camera_style', 'story_curve', 'shot_plan', 'camera_requirements', 'performance_requirements', 'continuity_lock', 'spatial_continuity', 'visual_continuity', 'lighting_requirements', 'negative_constraints', 'dialogue_direction', 'sound_design', 'transition_continuity', 'auto_reference_names', 'reference_manifest', 'reference_image_1', 'temperature', 'timeout_seconds', 'character', 'scene', 'director_preset', 'ui_mode', 'module_story_subtext', 'story_subtext_guidance', 'module_dramatic_beats', 'dramatic_beats_guidance', 'module_director_book', 'director_book_guidance', 'module_blocking_staging', 'blocking_staging_guidance', 'module_shot_planning', 'module_camera_language', 'module_performance_direction', 'module_spatial_continuity', 'module_character_continuity', 'module_lighting_color', 'module_dialogue_direction', 'module_sound_offscreen', 'module_keyframe_strategy', 'keyframe_strategy_guidance', 'module_transition_editing', 'module_genre_playbook', 'genre_guidance', 'module_directing_style', 'directing_style_guidance', 'module_reference_binding', 'reference_binding_guidance', 'module_clip_handoff', 'clip_handoff_guidance', 'module_model_adapter', 'model_adapter_guidance', 'module_qc_failure_prevention', 'qc_requirements', 'module_product_macro', 'product_macro_guidance']
V321_API_TEST_REQUIRED = ['api_base_url', 'api_model']
V321_API_TEST_OPTIONAL = ['timeout_seconds']


def test_main_node_keeps_v321_input_order_and_only_appends():
    inputs = BuffAIDirectorEnhancer.INPUT_TYPES()
    assert list(inputs["required"]) == V321_MAIN_REQUIRED
    optional = list(inputs["optional"])
    assert optional[: len(V321_MAIN_OPTIONAL)] == V321_MAIN_OPTIONAL


def test_api_test_node_keeps_v321_input_order_and_only_appends():
    inputs = BuffAIAPITest.INPUT_TYPES()
    assert list(inputs["required"]) == V321_API_TEST_REQUIRED
    assert list(inputs["optional"])[: len(V321_API_TEST_OPTIONAL)] == V321_API_TEST_OPTIONAL


def test_new_inputs_default_to_previous_behaviour():
    optional = BuffAIDirectorEnhancer.INPUT_TYPES()["optional"]
    assert optional["api_provider"][1]["default"] == "OpenAI-compatible"
    assert optional["research_log"][1]["default"] == "Off"
    assert optional["research_tag"][1]["default"] == ""
    assert BuffAIAPITest.INPUT_TYPES()["optional"]["api_provider"][1]["default"] == "OpenAI-compatible"
