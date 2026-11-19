import json

from director_modules import MODULE_SPECS
from node import BuffAIDirectorEnhancer
from text_preview import BuffAITextPreview
from api_test import BuffAIAPITest


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, system_prompt, user_prompt, **kwargs):
        self.calls.append({"system": system_prompt, "user": user_prompt, **kwargs})
        return json.dumps(self.responses.pop(0), ensure_ascii=False)


class MockNode(BuffAIDirectorEnhancer):
    def __init__(self, responses):
        self.fake_client = FakeClient(responses)

    def _make_client(self, config):
        return self.fake_client


def _base_kwargs(**overrides):
    values = dict(
        prompt="妖王逼近女妖，女妖劝阻，门外婚礼宣告打断。",
        duration=12.0,
        shot_mode="Auto",
        character="",
        scene="",
        visual_style="Cinematic",
        camera_style="Auto",
        action_level="Medium",
        story_curve="Rising",
        continuity_lock=True,
        aspect_ratio="16:9",
        target_model="MiniMax / Hailuo",
        language="English",
        mode="Fast",
        api_base_url="http://127.0.0.1:8317/v1",
        api_model="gpt-test",
        api_key="secret",
        temperature=0.5,
        timeout_seconds=30,
    )
    values.update(overrides)
    return values


def _minimal_response(shot_count=1):
    return {
        "title": "Stone Chamber",
        "overview": "An intimate power imbalance is interrupted.",
        "scene_objective": "Establish pressure, then interrupt it.",
        "character_names": "AI names",
        "keywords": "AI keywords",
        "shots": [
            {
                "id": i + 1,
                "purpose": f"Purpose {i + 1}",
                "duration_weight": 1,
                "camera_capture": "Stable medium close shot.",
                "visual_information": "Visible scene action.",
                "performance_action": "The action progresses and stops.",
                "facial_expression_eyeline": "A brief eyeline change.",
                "lighting_design": "Cold cyan and warm doorway light.",
                "spatial_entity_constraints": "Keep positions stable.",
                "continuity_out": f"End state {i + 1}",
                "action_beats": [{"description": "visible action", "weight": 1, "intensity": "medium"}],
                "dialogues": [],
                "offscreen_events": [],
            }
            for i in range(shot_count)
        ],
    }


def test_input_types_expose_two_mode_ui_default_full_auto_preset_all_module_states_and_guidance():
    inputs = BuffAIDirectorEnhancer.INPUT_TYPES()
    optional = inputs["optional"]
    assert optional["interface_mode"][0] == ["简洁模式", "专业模式"]
    assert optional["professional_section"][0][0] == "剧情与角色"
    assert optional["auto_reference_names"][1]["default"] is True
    assert optional["director_preset"][0][0] == "Full Auto Director"
    for key, spec in MODULE_SPECS.items():
        assert spec.state_input in optional
        assert optional[spec.state_input][0] == ["Off", "Auto", "Guided"]
        assert spec.guidance_input in optional
    assert inputs["required"]["duration"][1]["forceInput"] is True
    assert BuffAIDirectorEnhancer.OUTPUT_NODE is True






def test_api_test_node_is_registered_as_output_class():
    assert BuffAIAPITest.OUTPUT_NODE is True
    inputs = BuffAIAPITest.INPUT_TYPES()["required"]
    assert inputs["api_base_url"][1]["default"] == ""
    assert inputs["api_model"][1]["default"] == ""
    assert "api_key" not in inputs
    assert "api_key" not in BuffAIDirectorEnhancer.INPUT_TYPES()["required"]

def test_preflight_validation_rejects_missing_or_invalid_api_settings(monkeypatch):
    monkeypatch.delenv("BUFF_AI_API_BASE_URL", raising=False)
    monkeypatch.delenv("BUFF_AI_API_MODEL", raising=False)
    monkeypatch.delenv("BUFF_AI_API_KEY", raising=False)

    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "", "", "")
    assert "API 地址未填写" in msg

    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "not-a-url", "gpt-test", "secret")
    assert "API 地址格式无效" in msg

    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "http://127.0.0.1:8317/v1", "", "secret")
    assert "模型未填写" in msg

    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS("剧情", "http://127.0.0.1:8317/v1", "gpt-test", "")
    assert "API Key 未找到" in msg
    assert "BUFF_AI_API_KEY" in msg

    assert BuffAIDirectorEnhancer.VALIDATE_INPUTS(
        "剧情", "http://127.0.0.1:8317/v1", "gpt-test", "secret"
    ) is True


def test_preflight_requires_https_for_remote_and_local_trust(monkeypatch):
    monkeypatch.setenv("BUFF_AI_API_KEY", "test-only-dummy")
    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", "api.example.com")
    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS(
        "剧情", "http://api.example.com/v1", "gpt-test", ""
    )
    assert "HTTPS" in msg
    assert BuffAIDirectorEnhancer.VALIDATE_INPUTS(
        "剧情", "https://api.example.com/v1", "gpt-test", ""
    ) is True
    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS(
        "剧情", "https://attacker.example/v1", "gpt-test", ""
    )
    assert "未获本机信任" in msg


def test_workflow_cannot_select_unapproved_environment_secret(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "not-a-real-key")
    monkeypatch.setenv("BUFF_AI_API_KEY_ENV_VARS", "BUFF_AI_API_KEY")
    msg = BuffAIDirectorEnhancer.VALIDATE_INPUTS(
        "剧情", "http://127.0.0.1:8317/v1", "gpt-test", "",
        api_key_env_var="AWS_SECRET_ACCESS_KEY",
    )
    assert "未获本机授权" in msg
    assert "not-a-real-key" not in msg


def test_custom_key_env_name_requires_local_allowlist(monkeypatch):
    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", "api.example.com")
    monkeypatch.setenv("BUFF_AI_API_KEY_ENV_VARS", "BUFF_AI_API_KEY,MY_PROVIDER_KEY")
    monkeypatch.setenv("MY_PROVIDER_KEY", "test-only-dummy")
    assert BuffAIDirectorEnhancer.VALIDATE_INPUTS(
        "剧情", "https://api.example.com/v1", "gpt-test", "",
        api_key_env_var="MY_PROVIDER_KEY",
    ) is True


def test_api_test_node_ignores_legacy_workflow_key_and_sanitizes_output(monkeypatch, capsys):
    import api_test

    monkeypatch.delenv("BUFF_AI_API_KEY", raising=False)
    assert "API Key 未填写" in BuffAIAPITest.VALIDATE_INPUTS(
        "http://127.0.0.1:8317/v1", "test-model", "legacy-workflow-key"
    )
    monkeypatch.setenv("BUFF_AI_API_KEY", "test-only-env-key")
    monkeypatch.setenv("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317")
    captured = {}
    real_api_client = api_test.OpenAICompatibleClient

    class FakeAPIClient:
        def __init__(self, base_url, api_key, model, timeout):
            captured["key"] = api_key

        @staticmethod
        def build_chat_url(base_url):
            return real_api_client.build_chat_url(base_url)

        def chat(self, *args, **kwargs):
            return "private provider response text"

    monkeypatch.setattr(api_test, "OpenAICompatibleClient", FakeAPIClient)
    result = BuffAIAPITest().test_api(
        "http://127.0.0.1:8317/v1?api_key=query-secret", "test-model", "legacy-workflow-key"
    )
    assert captured["key"] == "test-only-env-key"
    assert "private provider response text" not in result["result"][0]
    assert "legacy-workflow-key" not in result["result"][0]
    assert "query-secret" not in result["result"][0]
    assert "query-secret" not in capsys.readouterr().out

def test_builtin_text_preview_is_an_output_and_passes_text_through():
    node = BuffAITextPreview()
    result = node.preview("hello prompt")
    assert BuffAITextPreview.OUTPUT_NODE is True
    assert result["result"] == ("hello prompt",)
    assert result["ui"]["text"] == ["hello prompt"]
    assert result["ui"]["preview_title"] == ["提示词预览"]



def test_v31_interface_mode_maps_simple_to_full_auto_and_professional_to_custom():
    simple_node = MockNode([_minimal_response(1)])
    simple_node.generate(
        **_base_kwargs(shot_mode="Single Shot"),
        interface_mode="简洁模式",
        director_preset="Simple",
    )
    assert "MODULE: LIGHTING & COLOR" in simple_node.fake_client.calls[0]["system"]

    professional_node = MockNode([_minimal_response(1)])
    professional_node.generate(
        **_base_kwargs(shot_mode="Single Shot"),
        interface_mode="专业模式",
        director_preset="Full Auto Director",
        module_story_subtext="Auto",
        module_shot_planning="Auto",
        module_camera_language="Auto",
        module_lighting_color="Off",
    )
    assert "MODULE: LIGHTING & COLOR" not in professional_node.fake_client.calls[0]["system"]

def test_fast_full_auto_call_loads_modules_and_preserves_names_dialogue_keywords():
    node = MockNode([_minimal_response(1)])
    result = node.generate(
        **_base_kwargs(),
        director_preset="Full Auto Director",
        generation_mode="Reference to Video",
        character_names="@铁角妖王, @紫衣女妖",
        dialogue_text="@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……",
        keywords="紫衣女妖触发词, X9_LoRA",
        scene_objective="建立压迫关系并被婚礼宣告打断",
    )
    enhanced, shots, storyboard_json, summary = result
    assert "@铁角妖王, @紫衣女妖" in enhanced
    assert "妖王，您明日便要大婚了，切莫如此……" in enhanced
    assert "紫衣女妖触发词, X9_LoRA" in enhanced
    assert "Full Auto Director" in enhanced
    data = json.loads(storyboard_json)
    assert data["character_names"] == "@铁角妖王, @紫衣女妖"
    assert data["keywords"] == "紫衣女妖触发词, X9_LoRA"
    assert data["module_report"]
    assert "MODULE: STORY & SUBTEXT" in node.fake_client.calls[0]["system"]
    assert "MODULE: PRODUCT / MACRO DIRECTION" not in node.fake_client.calls[0]["system"]
    assert "Story & Subtext: Auto" in summary


def test_custom_off_module_is_not_sent_or_rendered():
    node = MockNode([_minimal_response(1)])
    kwargs = _base_kwargs()
    kwargs.update({
        "director_preset": "Custom",
        "module_story_subtext": "Auto",
        "module_lighting_color": "Off",
        "module_shot_planning": "Auto",
        "module_camera_language": "Auto",
        "lighting_requirements": "左后冷青光",
    })
    enhanced, _, _, _ = node.generate(**kwargs)
    system = node.fake_client.calls[0]["system"]
    assert "MODULE: LIGHTING & COLOR" not in system
    assert "GLOBAL LIGHTING & COLOR" not in enhanced
    assert "LIGHTING DESIGN" not in enhanced


def test_explicit_shot_plan_hard_locks_count_and_timing_in_end_to_end_flow():
    node = MockNode([_minimal_response(1)])
    shot_plan = "Shot 1 · 0-2s\nApproach\nShot 2 · 2-10s\nDialogue\nShot 3 · 10-11s\nInterruption\nShot 4 · 11-12s\nReaction"
    _, _, storyboard_json, _ = node.generate(
        **_base_kwargs(),
        director_preset="Full Auto Director",
        shot_plan=shot_plan,
    )
    data = json.loads(storyboard_json)
    assert data["shot_count"] == 4
    assert data["shot_timing_locked"] is True
    assert [(s["start_time"], s["end_time"]) for s in data["shots"]] == [
        (0.0, 2.0), (2.0, 10.0), (10.0, 11.0), (11.0, 12.0)
    ]


def test_quality_mode_uses_same_module_router_and_cannot_change_literal_locks_or_times():
    first = _minimal_response(1)
    second = _minimal_response(1)
    second["character_names"] = "@PurpleDemoness"
    second["keywords"] = "changed"
    second["shots"][0]["start_time"] = 99
    second["shots"][0]["dialogues"] = [{"source_index": 1, "speaker": "translated", "text": "translated"}]
    node = MockNode([first, second])
    _, _, storyboard_json, _ = node.generate(
        **_base_kwargs(mode="Quality", shot_mode="Single Shot"),
        director_preset="Simple",
        character_names="@紫衣女妖",
        dialogue_text="@紫衣女妖｜切莫如此……",
        keywords="中文关键词_X9",
    )
    data = json.loads(storyboard_json)
    assert len(node.fake_client.calls) == 2
    assert "MODULE: LIGHTING & COLOR" not in node.fake_client.calls[1]["system"]
    assert data["character_names"] == "@紫衣女妖"
    assert data["keywords"] == "中文关键词_X9"
    assert data["shots"][0]["start_time"] == 0.0
    assert data["shots"][0]["dialogues"][0]["speaker"] == "@紫衣女妖"
    assert data["shots"][0]["dialogues"][0]["text"] == "切莫如此……"


def test_v23_style_call_without_new_optional_arguments_remains_valid():
    node = MockNode([_minimal_response(1)])
    enhanced, _, data, summary = node.generate(**_base_kwargs(shot_mode="Single Shot"))
    parsed = json.loads(data)
    assert parsed["shot_count"] == 1
    assert "Full Auto Director" in enhanced
    assert "Preset: Full Auto Director" in summary


def test_package_import_path_works_like_comfyui_package_loading():
    """Load the repository as a package the same way ComfyUI loads custom nodes.

    ComfyUI imports a custom-node folder through its ``__init__.py`` with the
    folder as the package search location, so relative imports must work
    regardless of what the checkout directory is called.
    """
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    name = "buff_ai_director_enhancer_pkg_test"
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    try:
        spec.loader.exec_module(package)
        assert "BUFF_AIDirectorPromptEnhancer" in package.NODE_CLASS_MAPPINGS
        assert "BUFF_AITextPreview" in package.NODE_CLASS_MAPPINGS
        assert "BUFF_AIAPITest" in package.NODE_CLASS_MAPPINGS
        assert package.WEB_DIRECTORY == "./js"
    finally:
        for key in [key for key in sys.modules if key == name or key.startswith(name + ".")]:
            del sys.modules[key]


def test_api_prompt_includes_generation_mode_and_enabled_model_specific_guidance():
    node = MockNode([_minimal_response(1)])
    node.generate(
        **_base_kwargs(target_model="MiniMax / Hailuo"),
        director_preset="Full Auto Director",
        generation_mode="Reference to Video",
    )
    user = node.fake_client.calls[0]["user"]
    assert "SOURCE-MODE RULES" in user
    assert "not a mandatory first frame" in user
    assert "TARGET-MODEL ADAPTER RULES" in user
    assert "restrained camera" in user


def test_api_prompt_omits_model_specific_guidance_when_model_adapter_is_off():
    node = MockNode([_minimal_response(1)])
    node.generate(
        **_base_kwargs(target_model="MiniMax / Hailuo"),
        director_preset="Custom",
        generation_mode="Reference to Video",
        module_story_subtext="Auto",
        module_shot_planning="Auto",
        module_model_adapter="Off",
    )
    user = node.fake_client.calls[0]["user"]
    assert "SOURCE-MODE RULES" in user
    assert "TARGET-MODEL ADAPTER RULES" not in user


def test_blank_user_keywords_do_not_allow_ai_to_invent_trigger_tokens():
    response = _minimal_response(1)
    response["keywords"] = "invented_trigger, fake_lora"
    node = MockNode([response])
    enhanced, _, storyboard_json, _ = node.generate(
        **_base_kwargs(shot_mode="Single Shot"),
        director_preset="Full Auto Director",
        keywords="",
    )
    data = json.loads(storyboard_json)
    assert data["keywords"] == ""
    assert "invented_trigger" not in enhanced
    assert "fake_lora" not in enhanced


def test_dynamic_reference_input_schema_supports_runtime_sockets():
    optional = BuffAIDirectorEnhancer.INPUT_TYPES()["optional"]
    assert "reference_image_2" in optional
    assert optional["reference_image_2"] == ("IMAGE",)
    assert "reference_image_99" in optional
    assert optional["reference_image_99"] == ("IMAGE",)
    assert "totally_unknown_input" not in optional



def test_selected_chinese_output_language_is_sent_to_llm_and_lora_keywords_are_literal_locks():
    node = MockNode([_minimal_response(1)])
    enhanced, shots, _, _ = node.generate(
        **_base_kwargs(language="中文", shot_mode="Single Shot"),
        interface_mode="简洁模式",
        keywords="purple_demoness_v2, X9_SceneTrigger",
    )
    call = node.fake_client.calls[0]
    assert "OUTPUT LANGUAGE: Simplified Chinese" in call["system"]
    assert "All production/directing values must be written in natural, professional Simplified Chinese" in call["user"]
    assert '"keywords": "purple_demoness_v2, X9_SceneTrigger"' in call["user"]
    assert "制作导演提示词" in enhanced
    assert "purple_demoness_v2, X9_SceneTrigger" in enhanced
    assert "purple_demoness_v2, X9_SceneTrigger" in shots


def test_input_types_put_output_language_and_lora_keywords_in_common_ui():
    optional = BuffAIDirectorEnhancer.INPUT_TYPES()["optional"]
    assert optional["language"][0] == ["中文", "English"]
    assert optional["language"][1]["default"] == "中文"
    assert "LoRA" in optional["keywords"][1]["tooltip"]
