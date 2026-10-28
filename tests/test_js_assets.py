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


def test_modular_ui_contains_two_mode_shell_and_guidance_maps_for_every_module():
    path = ROOT / "js" / "modular_director_ui.js"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'name: "buff_ai.modular_director_ui"' in text
    assert "PRESET_STATES" in text
    assert "MODULE_GUIDANCE" in text
    assert "简洁模式" in text
    assert "专业模式" in text
    assert "PROFESSIONAL_COMMON" in text
    assert "SECTION_FIELDS" in text
    for key, spec in MODULE_SPECS.items():
        assert f'module_{key}' in text
        assert spec.guidance_input in text


def test_modular_ui_hides_legacy_controls_and_only_shows_guidance_when_guided():
    text = (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")
    assert "setWidgetVisible" in text
    assert 'stateWidget?.value === "Guided"' in text
    assert "setPresetForInterface" in text
    assert 'presetWidget.value = "Full Auto Director"' in text
    assert 'presetWidget.value = "Custom"' in text
    assert "ALWAYS_HIDDEN" in text
    assert "director_preset" in text
    assert "ui_mode" in text
    assert "setDirtyCanvas" in text


def test_modular_ui_applies_chinese_labels_and_professional_sections():
    text = (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")
    assert "applyChineseLabels" in text
    assert 'interface_mode: "使用模式"' in text
    assert 'prompt: "剧情描述"' in text
    assert 'reference_manifest: "参考图绑定（自动生成 / 可手改）"' in text
    assert 'section === "高级模块"' in text
    assert '"API 设置"' in text


def test_text_preview_extension_is_registered_and_handles_ui_text():
    path = ROOT / "js" / "text_preview.js"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'name: "buff_ai.text_preview"' in text
    assert '"BUFF_AITextPreview", "BUFF_AIAPITest"' in text
    assert "addDOMWidget" in text
    assert "node.onExecuted" in text
    assert "navigator.clipboard.writeText" in text


def test_modular_ui_has_robust_professional_mode_watcher_and_common_language_keywords():
    text = (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")
    assert "uiStateSignature" in text
    assert "refreshWhenStateChanged" in text
    assert "node.onWidgetChanged" in text
    assert "node.onDrawForeground" in text
    assert "window.setInterval" in text
    assert "window.clearInterval" in text
    assert 'language: "提示词输出语言"' in text
    assert 'keywords: "LoRA 触发词 / Keywords（可选）"' in text


def test_modular_ui_handles_dom_multiline_visibility_and_reflow():
    text = (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")
    assert "widget.hidden = !visible" in text
    assert "widget.computedHeight = visible ? undefined : 0" in text
    assert "widgetElement(widget)" in text
    assert 'el.style.display = visible ? widget.__buffOriginalDisplay : "none"' in text
    assert "requestAnimationFrame" in text
    assert "computeAutoNodeSize" in text
    assert "node.computeSize" in text
    assert "NODE_BOTTOM_PADDING" in text
    assert "node.arrange?.()" in text
    assert "Math.abs(currentHeight - targetHeight)" in text


def test_modular_ui_uses_comfy_dom_layout_height_for_multiline_textareas():
    text = (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")
    assert "tuneMultilineDomWidget" in text
    assert 'el.tagName !== "TEXTAREA"' in text
    assert "TEXTAREA_CONTENT_HEIGHT = 76" in text
    assert "TEXTAREA_FALLBACK_MARGIN = 10" in text
    assert "const rowHeight = TEXTAREA_CONTENT_HEIGHT + margin * 2" in text
    assert "widget.options.getMinHeight = () => rowHeight" in text
    assert "widget.options.getMaxHeight = () => rowHeight" in text
    assert "widget.options.getHeight = () => rowHeight" in text
    assert 'el.style.removeProperty(property)' in text
    assert 'el.style.resize = "none"' in text
    assert "el.placeholder = display" in text


def test_modular_ui_does_not_force_setsize_in_vue_nodes_mode():
    text = (ROOT / "js" / "modular_director_ui.js").read_text(encoding="utf-8")
    assert "isVueNodesMode" in text
    assert "vueNodesMode" in text
    assert "if (isVueNodesMode())" in text
    assert "node.arrange?.()" in text


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
