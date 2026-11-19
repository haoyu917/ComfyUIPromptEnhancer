import { app } from "../../scripts/app.js";

const CLASS_NAME = "BUFF_AIDirectorPromptEnhancer";

const MODULE_GUIDANCE = {
  module_story_subtext: "story_subtext_guidance",
  module_dramatic_beats: "dramatic_beats_guidance",
  module_director_book: "director_book_guidance",
  module_blocking_staging: "blocking_staging_guidance",
  module_shot_planning: "shot_plan",
  module_camera_language: "camera_requirements",
  module_performance_direction: "performance_requirements",
  module_spatial_continuity: "spatial_continuity",
  module_character_continuity: "visual_continuity",
  module_lighting_color: "lighting_requirements",
  module_dialogue_direction: "dialogue_direction",
  module_sound_offscreen: "sound_design",
  module_keyframe_strategy: "keyframe_strategy_guidance",
  module_transition_editing: "transition_continuity",
  module_genre_playbook: "genre_guidance",
  module_directing_style: "directing_style_guidance",
  module_reference_binding: "reference_binding_guidance",
  module_clip_handoff: "clip_handoff_guidance",
  module_model_adapter: "model_adapter_guidance",
  module_qc_failure_prevention: "qc_requirements",
  module_product_macro: "product_macro_guidance",
};

const ALWAYS_HIDE = new Set([
  "character",
  "scene",
  "director_preset",
  "ui_mode",
  "api_key", // Legacy compatibility only. Use api_key_env_var instead.
]);

const COMMON = new Set([
  "prompt",
  "interface_mode",
  "generation_mode",
  "visual_style",
  "action_level",
  "aspect_ratio",
  "target_model",
  "language",
  "mode",
  "keywords",
  "must_keep",
  "must_avoid",
]);

const SIMPLE_EXTRA = new Set([
  "dialogue_text",
  "audio_policy",
  "strict_speech_lock",
  "offscreen_dialogue_text",
  "api_provider",
  "api_base_url",
  "api_model",
  "api_key_env_var",
  "temperature",
  "timeout_seconds",
]);

const SECTION_WIDGETS = {
  "剧情与角色": new Set([
    "project_format",
    "genre",
    "directing_style",
    "era_setting",
    "scene_objective",
    "character_names",
    "character_profiles",
    "character_relationships",
    "scene_environment",
    "extra_requirements",
  ]),
  "分镜与摄影": new Set([
    "shot_mode",
    "camera_style",
    "story_curve",
    "shot_plan",
    "camera_requirements",
    "performance_requirements",
  ]),
  "连续性与灯光": new Set([
    "continuity_lock",
    "spatial_continuity",
    "visual_continuity",
    "lighting_requirements",
    "negative_constraints",
  ]),
  "声音与剪辑": new Set([
    "audio_policy",
    "strict_speech_lock",
    "dialogue_text",
    "offscreen_dialogue_text",
    "dialogue_direction",
    "sound_design",
    "offscreen_audio",
    "transition_continuity",
  ]),
  "参考图": new Set([
    "auto_reference_names",
    "reference_manifest",
  ]),
  "API 设置": new Set([
    "api_provider",
    "api_base_url",
    "api_model",
    "api_key_env_var",
    "temperature",
    "timeout_seconds",
    "research_log",
    "research_tag",
  ]),
};

function findWidget(node, name) {
  return node.widgets?.find((widget) => widget?.name === name);
}

function domTargets(widget) {
  const candidates = [
    widget?.element,
    widget?.inputEl,
    widget?.textarea,
    widget?.container,
    widget?.domElement,
  ];
  return [...new Set(candidates.filter((el) => el && el.style))];
}

function setWidgetVisible(widget, visible) {
  if (!widget) return;

  if (!widget.__buffVisibilityInit) {
    widget.__buffVisibilityInit = true;
    widget.__buffOriginalComputeSize = widget.computeSize;
    widget.__buffDomDisplay = new Map();
    for (const el of domTargets(widget)) {
      widget.__buffDomDisplay.set(el, el.style.display || "");
    }
  }

  widget.hidden = !visible;
  widget.options = widget.options || {};
  widget.options.hidden = !visible;

  if (visible) {
    if (widget.__buffOriginalComputeSize) widget.computeSize = widget.__buffOriginalComputeSize;
    else delete widget.computeSize;
    for (const el of domTargets(widget)) {
      const previous = widget.__buffDomDisplay?.get(el);
      el.style.display = previous ?? "";
      el.style.visibility = "";
      el.style.pointerEvents = "";
    }
  } else {
    widget.computeSize = () => [0, -4];
    for (const el of domTargets(widget)) {
      if (!widget.__buffDomDisplay?.has(el)) widget.__buffDomDisplay?.set(el, el.style.display || "");
      el.style.display = "none";
      el.style.visibility = "hidden";
      el.style.pointerEvents = "none";
    }
  }
}

function resizeNode(node) {
  try {
    const computed = node.computeSize?.();
    if (computed && node.setSize) {
      node.setSize([Math.max(node.size?.[0] || 430, 430), Math.max(computed[1], 160)]);
    }
  } catch (error) {
    console.debug("BUFF AI UI resize skipped", error);
  }
  node.setDirtyCanvas?.(true, true);
}

function isModuleState(name) {
  return Object.prototype.hasOwnProperty.call(MODULE_GUIDANCE, name);
}

function isGuidance(name) {
  return Object.values(MODULE_GUIDANCE).includes(name);
}

function shouldShowAdvancedModuleWidget(node, widget) {
  const name = widget?.name;
  if (isModuleState(name)) return true;
  const stateName = Object.entries(MODULE_GUIDANCE).find(([, guidance]) => guidance === name)?.[0];
  if (!stateName) return false;
  return findWidget(node, stateName)?.value === "Guided";
}

function refreshVisibility(node) {
  const interfaceWidget = findWidget(node, "interface_mode");
  const sectionWidget = findWidget(node, "professional_section");
  const professional = interfaceWidget?.value === "专业模式";
  const section = sectionWidget?.value || "剧情与角色";

  for (const widget of node.widgets || []) {
    const name = widget?.name;
    if (!name) continue;

    let visible = true;
    if (ALWAYS_HIDE.has(name)) {
      visible = false;
    } else if (name === "professional_section") {
      visible = professional;
    } else if (COMMON.has(name)) {
      visible = true;
    } else if (!professional) {
      visible = SIMPLE_EXTRA.has(name);
    } else if (section === "高级模块") {
      visible = shouldShowAdvancedModuleWidget(node, widget);
    } else {
      visible = SECTION_WIDGETS[section]?.has(name) || false;
    }

    setWidgetVisible(widget, visible);
  }

  // Audio safety controls are always visible in simple mode and in the sound section.
  if (!professional || section === "声音与剪辑") {
    for (const name of ["audio_policy", "strict_speech_lock", "dialogue_text", "offscreen_dialogue_text"]) {
      setWidgetVisible(findWidget(node, name), true);
    }
  }

  // API environment-variable control is always visible in simple mode and API settings.
  if (!professional || section === "API 设置") {
    setWidgetVisible(findWidget(node, "api_key_env_var"), true);
  }

  resizeNode(node);
}

function wrapCallback(widget, fn) {
  if (!widget || widget.__buffV321Wrapped) return;
  const original = widget.callback;
  widget.callback = function (...args) {
    const result = original?.apply(this, args);
    queueMicrotask(fn);
    return result;
  };
  widget.__buffV321Wrapped = true;
}

app.registerExtension({
  name: "buff_ai.v321_ui_compat",
  async nodeCreated(node) {
    if (node.comfyClass !== CLASS_NAME) return;

    node.title = "BUFF AI · Modular Director Skill Engine V3.2.1";

    wrapCallback(findWidget(node, "interface_mode"), () => refreshVisibility(node));
    wrapCallback(findWidget(node, "professional_section"), () => refreshVisibility(node));
    for (const stateName of Object.keys(MODULE_GUIDANCE)) {
      wrapCallback(findWidget(node, stateName), () => refreshVisibility(node));
    }

    const originalConfigure = node.onConfigure?.bind(node);
    node.onConfigure = function (...args) {
      const result = originalConfigure?.(...args);
      queueMicrotask(() => refreshVisibility(node));
      return result;
    };

    queueMicrotask(() => refreshVisibility(node));
  },
});
