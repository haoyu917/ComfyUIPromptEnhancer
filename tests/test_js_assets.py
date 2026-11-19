from pathlib import Path

from director_modules import MODULE_SPECS


ROOT = Path(__file__).resolve().parents[1]


def test_dynamic_reference_extension_remains_registered_and_auto_names_refs():
    text = (ROOT / "js" / "dynamic_reference_inputs.js").read_text(encoding="utf-8")
    assert 'name: "buff_ai.dynamic_reference_inputs"' in text
    assert 'const REF_PREFIX = "reference_image_"' in text
    assert "ensureOneSpareRefInput" in text
    assert "syncAutoReferenceManifest" in text
    assert "sourceReferenceName" in text
    assert 'findWidget(node, "auto_reference_names")' in text
    assert 'findWidget(node, "reference_manifest")' in text
    assert "originNode.title" in text


def _modular_ui_text() -> str:
    return (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")


def test_modular_ui_registers_extension_for_main_node():
    text = _modular_ui_text()
    assert "app.registerExtension" in text
    assert 'const CLASS_NAME = "BUFF_AIDirectorPromptEnhancer"' in text
    assert "node.comfyClass !== CLASS_NAME" in text


def test_modular_ui_maps_every_module_state_to_its_guidance_input():
    text = _modular_ui_text()
    assert "MODULE_GUIDANCE" in text
    for key, spec in MODULE_SPECS.items():
        assert f"module_{key}: \"{spec.guidance_input}\"" in text


def test_modular_ui_has_simple_and_professional_modes_with_sections():
    text = _modular_ui_text()
    assert '"专业模式"' in text
    assert "SECTION_WIDGETS" in text
    for section in ("剧情与角色", "分镜与摄影", "连续性与灯光", "声音与剪辑", "参考图", "API 设置"):
        assert f'"{section}"' in text
    api_section = text[text.index('"API 设置": new Set(['):]
    api_section = api_section[: api_section.index("]),")]
    assert '"research_log"' in api_section
    assert '"research_tag"' in api_section
    assert 'section === "高级模块"' in text


def test_modular_ui_hides_legacy_controls_and_shows_guidance_only_when_guided():
    text = _modular_ui_text()
    assert "ALWAYS_HIDE" in text
    for legacy in ("character", "scene", "director_preset", "ui_mode", "api_key"):
        assert f'"{legacy}"' in text
    assert '?.value === "Guided"' in text


def test_modular_ui_hides_dom_widgets_and_refreshes_on_state_changes():
    text = _modular_ui_text()
    assert "function setWidgetVisible" in text
    assert "widget.hidden = !visible" in text
    assert 'el.style.display = "none"' in text
    assert "node.onConfigure" in text
    assert "wrapCallback" in text
    assert "setDirtyCanvas" in text


def test_text_preview_extension_is_registered_and_handles_ui_text():
    path = ROOT / "js" / "text_preview.js"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'name: "buff_ai.text_preview"' in text
    assert '"BUFF_AITextPreview", "BUFF_AIAPITest"' in text
    assert "addDOMWidget" in text
    assert "node.onExecuted" in text
    assert "navigator.clipboard.writeText" in text


def test_text_preview_reserves_comfy_dom_row_height_and_stays_inside_node():
    text = (ROOT / "js" / "text_preview.js").read_text(encoding="utf-8")
    assert "getMinHeight: () => rowHeight" in text
    assert "getMaxHeight: () => rowHeight" in text
    assert "getHeight: () => rowHeight" in text
    assert 'root.style.overflow = "hidden"' in text
    assert 'textarea.style.resize = "none"' in text
    assert "fitNode(node" in text


def test_dynamic_reference_auto_names_are_at_entity_tokens():
    text = (ROOT / "js" / "dynamic_reference_inputs.js").read_text(encoding="utf-8")
    assert "function asEntityToken" in text
    assert 'return `@${text}`' in text
