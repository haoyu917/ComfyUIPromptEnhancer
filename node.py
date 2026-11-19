"""ComfyUI node orchestration for BUFF AI Modular Director Skill Engine V3."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import time
from typing import Any, Dict, Mapping, Optional

try:
    from .api_client import (
        APIClientError,
        OpenAICompatibleClient,
        TRUSTED_HOSTS_ENV,
        sanitize_url,
        validate_api_endpoint,
        validate_api_key_env_name,
    )
    from .director_modules import (
        DIRECTOR_PRESETS,
        MODULE_SPECS,
        VALID_MODULE_STATES,
        resolve_module_states,
    )
    from .director_router import (
        build_director_system_prompt,
        build_dynamic_schema,
        build_generation_mode_guidance,
        build_module_context,
        build_target_model_guidance,
        resolve_module_runtime,
        runtime_report,
    )
    from .entity_locks import apply_entity_identity_locks, build_entity_registry, canonicalize_name_list, entity_lock_instruction
    from .language_policy import (
        extract_json_object,
        parse_dialogue_source,
        resolve_user_field,
        source_language,
    )
    from .audio_control import AUDIO_POLICIES, enforce_audio_policy, parse_exact_offscreen_dialogue
    from .reference_images import (
        build_multimodal_content,
        collect_reference_assets,
        reference_summary,
    )
    from .renderer import render_director_summary, render_master_prompt, render_shot_prompts
    from .shot_planner import ShotPlanError, ShotPlanLock, parse_shot_plan
    from .storyboard import normalize_storyboard
    from .run_logger import RESEARCH_LOG_LEVELS, RunRecorder
    from .anthropic_client import DEFAULT_ANTHROPIC_BASE_URL, AnthropicClient
    from .quality_metrics import build_run_metrics
    from .storyboard import _safe_shot_count
except ImportError:  # Standalone test fallback.
    from api_client import (
        APIClientError,
        OpenAICompatibleClient,
        TRUSTED_HOSTS_ENV,
        sanitize_url,
        validate_api_endpoint,
        validate_api_key_env_name,
    )
    from director_modules import (
        DIRECTOR_PRESETS,
        MODULE_SPECS,
        VALID_MODULE_STATES,
        resolve_module_states,
    )
    from director_router import (
        build_director_system_prompt,
        build_dynamic_schema,
        build_generation_mode_guidance,
        build_module_context,
        build_target_model_guidance,
        resolve_module_runtime,
        runtime_report,
    )
    from entity_locks import apply_entity_identity_locks, build_entity_registry, canonicalize_name_list, entity_lock_instruction
    from language_policy import (
        extract_json_object,
        parse_dialogue_source,
        resolve_user_field,
        source_language,
    )
    from audio_control import AUDIO_POLICIES, enforce_audio_policy, parse_exact_offscreen_dialogue
    from reference_images import (
        build_multimodal_content,
        collect_reference_assets,
        reference_summary,
    )
    from renderer import render_director_summary, render_master_prompt, render_shot_prompts
    from shot_planner import ShotPlanError, ShotPlanLock, parse_shot_plan
    from storyboard import normalize_storyboard
    from run_logger import RESEARCH_LOG_LEVELS, RunRecorder
    from anthropic_client import DEFAULT_ANTHROPIC_BASE_URL, AnthropicClient
    from quality_metrics import build_run_metrics
    from storyboard import _safe_shot_count


class ContainsAnyDict(dict):
    """Expose dynamically-created ``reference_image_N`` sockets to ComfyUI.

    The frontend adds reference_image_2, reference_image_3, ... at runtime.
    ComfyUI validation may first check membership and then index the optional
    input schema. Returning True for every key (the old V3.1.1 behavior) made
    ``optional["reference_image_2"]`` raise KeyError during workflow
    validation. Only dynamic reference-image keys are synthesized here.
    """

    _DYNAMIC_REF_RE = re.compile(r"^reference_image_\d+$")

    def __contains__(self, key):
        return dict.__contains__(self, key) or bool(self._DYNAMIC_REF_RE.fullmatch(str(key)))

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        if self._DYNAMIC_REF_RE.fullmatch(str(key)):
            return ("IMAGE",)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


API_PROVIDERS = ("OpenAI-compatible", "Anthropic")


def resolve_api_provider(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in API_PROVIDERS else "OpenAI-compatible"


def resolve_base_url(provider: str, value: Any) -> str:
    base = str(value or "").strip() or os.getenv("BUFF_AI_API_BASE_URL", "").strip()
    if not base and provider == "Anthropic":
        return DEFAULT_ANTHROPIC_BASE_URL
    return base


class BuffAIDirectorEnhancer:
    """BUFF AI · Modular Director Skill Engine V3."""

    DESCRIPTION = (
        "Turn a simple idea into a professional, timestamped production director prompt. "
        "Director modules can be Off, Auto, or Guided; explicit user data always wins."
    )

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("enhanced_prompt", "shot_prompts", "storyboard_json", "director_summary")
    FUNCTION = "generate"
    CATEGORY = "BUFF AI/Prompt"
    # Allow BUFF AI to run as a workflow endpoint even when the user only wants to inspect prompts.
    OUTPUT_NODE = True
    # Offline experiment backends (experiments/) set this so research records
    # name the backend that really answered. The ComfyUI node never sets it.
    PROVIDER_LABEL_OVERRIDE: Optional[str] = None

    @classmethod
    def INPUT_TYPES(cls):
        # V3.1 keeps only the two true essentials in the required block so the
        # user-facing controls can be ordered cleanly. All remaining fields have
        # defaults in generate(), which also makes old/headless calls tolerant.
        required = {
            "prompt": (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "tooltip": "剧情描述：只要写清楚谁、做什么、发生什么变化、最后停在哪里。其余导演细节可以交给 AI。",
                },
            ),
            "duration": (
                "FLOAT",
                {
                    "default": 10.0,
                    "min": 1.0,
                    "max": 180.0,
                    "step": 0.5,
                    "forceInput": True,
                    "tooltip": "视频总时长，单位秒。建议连接外部 Float。",
                },
            ),
        }

        optional: ContainsAnyDict = ContainsAnyDict(
            {
                # ---- V3.1 common / simple UI ----
                "interface_mode": (["简洁模式", "专业模式"], {"default": "简洁模式", "tooltip": "简洁模式保留完整自动导演能力，只显示常用输入；专业模式按分类开放人工控制。"}),
                "professional_section": (
                    ["剧情与角色", "分镜与摄影", "连续性与灯光", "声音与剪辑", "参考图", "高级模块", "API 设置"],
                    {"default": "剧情与角色", "tooltip": "专业模式下只展开当前类别，避免节点无限变长。"},
                ),
                "generation_mode": (
                    ["Image to Video", "Reference to Video", "Text to Video"],
                    {"default": "Image to Video", "tooltip": "首帧图生视频 / 多参考图参考生视频 / 纯文字生成视频。"},
                ),
                "aspect_ratio": (["16:9", "9:16", "1:1", "4:3", "21:9", "2.39:1"], {"default": "16:9", "tooltip": "应与最终视频比例一致。"}),
                "target_model": (
                    ["Generic", "Wan", "Seedance", "Kling", "Veo", "MiniMax / Hailuo"],
                    {"default": "Generic", "tooltip": "最终生成视频所使用的模型；不是当前用于导演思考的 LLM。"},
                ),
                "language": (
                    ["中文", "English"],
                    {
                        "default": "中文",
                        "tooltip": "提示词输出语言。中文会生成中文导演提示词；English 会生成英文导演提示词。角色姓名、对白、LoRA 触发词始终保持原文。",
                    },
                ),
                "keywords": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可选。LoRA Trigger / 关键词。支持逗号或换行分隔；会原样写入 enhanced_prompt 和每个 shot_prompt，不翻译、不改大小写、不自动生成。",
                    },
                ),
                "visual_style": (
                    ["Cinematic", "Realistic", "Anime", "Commercial", "Dark Fantasy", "Sci-Fi", "Custom"],
                    {"default": "Cinematic", "tooltip": "整体画面质感，不是具体运镜。"},
                ),
                "action_level": (["Low", "Medium", "High"], {"default": "Medium", "tooltip": "动作密度：对白/微表演选 Low，普通叙事选 Medium，战斗追逐选 High。"}),
                "mode": (["Fast", "Quality"], {"default": "Fast", "tooltip": "Fast 调用一次 API；Quality 会再做一次专业检查。"}),
                "dialogue_text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可选。一行一句：@角色｜对白。对白原文会被严格保留。",
                    },
                ),
                "audio_policy": (
                    list(AUDIO_POLICIES),
                    {
                        "default": "Dialogue + Exact Offscreen",
                        "tooltip": "语音策略。短剧推荐 Dialogue + Exact Offscreen：只允许角色对白和明确填写的画外对白。",
                    },
                ),
                "strict_speech_lock": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "严格对白锁定。开启后只允许白名单台词，不允许 AI 额外发明对白、旁白或背景说话。",
                    },
                ),
                "offscreen_dialogue_text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "可选。一行一句：画外角色｜对白。这里只填写真正允许说出的画外台词。",
                    },
                ),
                "must_keep": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。绝对必须保持的内容，例如：人物服装不变；石桌始终在女妖身后。"}),
                "must_avoid": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。绝对不能出现的内容，例如：不要亲吻；不要环绕运镜。"}),
                "api_base_url": ("STRING", {"multiline": False, "default": "", "tooltip": "主机必须加入本机 BUFF_AI_TRUSTED_API_HOSTS；远程地址使用 HTTPS，本机回环可用 HTTP。选 Anthropic 时可留空。"}),
                "api_model": ("STRING", {"multiline": False, "default": "", "tooltip": "必填。用于导演分析和完善 Prompt 的语言模型 ID，可自由填写，例如中转站的模型 ID，或 Claude 的 claude-opus-5-5、claude-sonnet-5-5。也可设置 BUFF_AI_API_MODEL 环境变量。"}),
                "api_key_env_var": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "BUFF_AI_API_KEY",
                        "tooltip": "API Key 环境变量名称。默认 BUFF_AI_API_KEY；自定义名称还须加入本机 BUFF_AI_API_KEY_ENV_VARS。",
                    },
                ),

                # ---- Professional controls ----
                "project_format": (
                    ["Auto", "Scene", "Short Film", "Social Vertical", "Trailer", "Commercial", "Music Video", "Documentary"],
                    {"default": "Auto"},
                ),
                "genre": ("STRING", {"multiline": False, "default": "Auto", "tooltip": "例如：暗黑奇幻、爱情、悬疑、动作。Auto 由 AI 判断。"}),
                "directing_style": ("STRING", {"multiline": False, "default": "Auto", "tooltip": "整体导演方式，例如自然叙事、慢燃悬疑、商业质感。"}),
                "era_setting": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。用于锁定时代和世界观，避免服装、建筑、道具串时代。"}),
                "scene_objective": ("STRING", {"multiline": True, "default": "", "tooltip": "这一场戏最终要完成什么。例：建立压迫关系，并由画外婚礼宣告打断。"}),
                "character_names": (
                    "STRING",
                    {"multiline": True, "default": "", "tooltip": "可选。需要严格锁定名称时填写，例如：@铁角妖王、@紫衣女妖。"},
                ),
                "character_profiles": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。有参考图时通常可以留空；只有想额外规定人物外貌、服装、体型或道具时填写。"}),
                "character_relationships": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。描述人物之间的权力、情感、距离或冲突关系。"}),
                "scene_environment": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。描述地点、建筑、家具、天气、背景和关键道具；有场景参考图时通常可以留空。"}),
                "offscreen_audio": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。门外喊声、脚步、画外音或其他打断事件。"}),
                "extra_requirements": ("STRING", {"multiline": True, "default": "", "tooltip": "其他输入框没有覆盖的特殊要求。"}),

                "shot_mode": (["Auto", "Single Shot", "Multi Shot"], {"default": "Auto", "tooltip": "分镜数量。简洁模式保持 Auto 即可。"}),
                "camera_style": (
                    ["Auto", "Static", "Smooth", "Dynamic", "Handheld", "Cinematic"],
                    {"default": "Auto", "tooltip": "摄影机总体倾向。简洁模式建议 Auto。"},
                ),
                "story_curve": (["Auto", "Flat", "Rising", "Climax End", "Slow Burn"], {"default": "Auto"}),
                "shot_plan": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。留空由 AI 自动分镜；需要锁定 Shot 数量、顺序或时间时再填写。"}),
                "camera_requirements": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。指定景别、角度、镜头移动等，例如：中近景，两人同框，只允许轻微前移。"}),
                "performance_requirements": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。指定身体动作、眼神、表情、呼吸和微表演。"}),

                "continuity_lock": ("BOOLEAN", {"default": True, "tooltip": "保持人物位置、姿态、视线、道具和光线跨 Shot 连续。"}),
                "spatial_continuity": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。需要手动锁定人物、门口、桌子、道具的位置、方向和距离时填写。"}),
                "visual_continuity": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。需要额外锁定脸、服装、发型、颜色、物件状态时填写。"}),
                "lighting_requirements": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。指定光源方向、颜色、明暗和阴影。"}),
                "negative_constraints": ("STRING", {"multiline": True, "default": "", "tooltip": "专业负面约束，例如：人物不能换脸、服装不能变化、门口位置不能改变。"}),

                "dialogue_direction": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。指定音量、语气、停顿、吸气、重音和说话时的动作。"}),
                "sound_design": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。环境底噪、衣料声、脚步、音乐和静默等声音设计。"}),
                "transition_continuity": ("STRING", {"multiline": True, "default": "", "tooltip": "可选。当前 Shot 结束状态以及下一 Shot 如何承接。"}),

                "auto_reference_names": ("BOOLEAN", {"default": True, "tooltip": "自动读取上游参考图节点名称；若节点未命名，则尝试使用图片文件名。"}),
                "reference_manifest": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "通常无需手填。开启自动参考图命名后，会根据上游节点名称/图片文件名自动生成。专业模式可关闭自动命名后手工编辑。",
                    },
                ),
                "reference_image_1": ("IMAGE",),

                "temperature": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 2.0, "step": 0.05, "tooltip": "推荐 0.3–0.6 获得更稳定的结构化输出。"}),
                "timeout_seconds": ("INT", {"default": 90, "min": 10, "max": 300, "step": 5, "tooltip": "单次 API 请求超时秒数。"}),

                # ---- Old fields remain for workflow compatibility, but the V3.1 JS hides them. ----
                "character": ("STRING", {"multiline": True, "default": "", "tooltip": "旧版兼容字段。V3.1 新工作流通常无需填写。"}),
                "scene": ("STRING", {"multiline": True, "default": "", "tooltip": "旧版兼容字段。V3.1 新工作流通常无需填写。"}),
                "director_preset": (list(DIRECTOR_PRESETS), {"default": "Full Auto Director"}),
                "ui_mode": (["Basic", "Advanced"], {"default": "Basic"}),
            }
        )

        for key, spec in MODULE_SPECS.items():
            optional[spec.state_input] = (
                list(VALID_MODULE_STATES),
                {
                    "default": spec.default_state,
                    "tooltip": f"{spec.title_zh}：Off=关闭，Auto=AI 自动完成，Guided=以你的指导为优先。",
                },
            )
            optional.setdefault(
                spec.guidance_input,
                (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": f"{spec.title_zh}的人工指导。留空时仍由 AI 自动补全。",
                    },
                ),
            )

        # Inputs added after V3.2.1 go last: ComfyUI stores widget values by
        # position, so inserting earlier would shift every value in older
        # saved workflows.
        optional.update(
            {
                "api_provider": (
                    list(API_PROVIDERS),
                    {
                        "default": "OpenAI-compatible",
                        "tooltip": "API 类型。OpenAI-compatible：中转站或任何 /v1/chat/completions 接口；Anthropic：Claude 官方 API（需要 pip install anthropic，地址可留空，默认 https://api.anthropic.com）。",
                    },
                ),
                "research_log": (
                    list(RESEARCH_LOG_LEVELS),
                    {
                        "default": "Off",
                        "tooltip": "研究记录。Off=不记录；Metrics only=记录配置、模块状态、耗时、token 用量和结果，剧情只存哈希；Full text=另外保存剧情原文和生成结果。写入位置由本机环境变量 BUFF_AI_RESEARCH_LOG_DIR 决定，从不记录 API Key。",
                    },
                ),
                "research_tag": ("STRING", {"multiline": False, "default": "", "tooltip": "可选。研究记录标签，例如实验编号或基准剧情编号，便于之后分组分析。"}),
            }
        )

        return {"required": required, "optional": optional}

    @classmethod
    def VALIDATE_INPUTS(
        cls,
        prompt,
        api_base_url="",
        api_model="",
        api_key="",
        api_key_env_var="BUFF_AI_API_KEY",
        api_provider="OpenAI-compatible",
    ):
        """Fail before execution for common configuration mistakes.

        ComfyUI displays the returned string as a workflow validation error, so
        the user does not get a task that sits at 0% with no useful feedback.
        """
        idea = str(prompt or "").strip()
        if not idea:
            return "[BUFF AI 配置错误] 剧情描述不能为空。"

        base_url = resolve_base_url(resolve_api_provider(api_provider), api_base_url)
        model = str(api_model or "").strip() or os.getenv("BUFF_AI_API_MODEL", "").strip()
        try:
            env_name = validate_api_key_env_name(api_key_env_var)
        except APIClientError as exc:
            return str(exc)
        key = os.getenv(env_name, "").strip() or str(api_key or "").strip() or os.getenv("BUFF_AI_API_KEY", "").strip()

        if not base_url:
            return "[BUFF AI 配置错误] API 地址未填写。请填写 API 地址，例如 http://127.0.0.1:8317/v1。"
        try:
            validate_api_endpoint(base_url)
        except APIClientError as exc:
            return f"[BUFF AI 配置错误] {exc}"
        if not model:
            return "[BUFF AI 配置错误] 导演 LLM 模型未填写。请填写中转站 /v1/models 返回的准确模型 ID。"
        if not key:
            return f"[BUFF AI 配置错误] API Key 未找到。请设置环境变量 {env_name} 后完全重启 ComfyUI；旧 api_key 字段仅用于兼容。"
        return True

    @staticmethod
    def _make_progress(total: int):
        try:
            from comfy.utils import ProgressBar
            return ProgressBar(total)
        except Exception:
            return None

    @staticmethod
    def _report_progress(progress, value: int, total: int, message: str):
        print(f"[BUFF AI] [{value}/{total}] {message}", flush=True)
        if progress is not None:
            try:
                progress.update_absolute(value, total)
            except Exception:
                pass

    def generate(
        self,
        prompt: str,
        duration: float,
        shot_mode: str = "Auto",
        character: str = "",
        scene: str = "",
        visual_style: str = "Cinematic",
        camera_style: str = "Auto",
        action_level: str = "Medium",
        story_curve: str = "Auto",
        continuity_lock: bool = True,
        aspect_ratio: str = "16:9",
        target_model: str = "Generic",
        language: str = "English",
        mode: str = "Fast",
        api_base_url: str = "",
        api_model: str = "",
        api_key: str = "",
        temperature: float = 0.6,
        timeout_seconds: int = 90,
        director_preset: str = "Full Auto Director",
        generation_mode: str = "Image to Video",
        reference_manifest: str = "",
        **kwargs,
    ):
        core_idea = str(prompt or "").strip()
        if not core_idea:
            raise RuntimeError("[BUFF AI] prompt cannot be empty.")
        total_duration = float(duration)
        if not math.isfinite(total_duration) or total_duration <= 0:
            raise RuntimeError("[BUFF AI] duration must be greater than 0.")

        try:
            api_key_env_var = validate_api_key_env_name(
                str(kwargs.get("api_key_env_var", "BUFF_AI_API_KEY") or "BUFF_AI_API_KEY").strip()
            )
        except APIClientError as exc:
            raise RuntimeError(f"[BUFF AI 配置错误] {exc}") from None
        env_key = os.getenv(api_key_env_var, "").strip()
        legacy_key = str(api_key or "").strip()
        key = env_key or legacy_key or os.getenv("BUFF_AI_API_KEY", "").strip()
        api_provider = self.PROVIDER_LABEL_OVERRIDE or resolve_api_provider(kwargs.get("api_provider", "OpenAI-compatible"))
        resolved_base_url = resolve_base_url(api_provider, api_base_url)
        resolved_model = str(api_model or "").strip() or os.getenv("BUFF_AI_API_MODEL", "").strip()

        # V3.1 UI has only two real user-facing modes. Keep old director_preset
        # behavior when interface_mode is absent (tests, old/headless callers).
        interface_mode = str(kwargs.get("interface_mode", "") or "").strip()
        effective_preset = director_preset if director_preset in DIRECTOR_PRESETS else "Full Auto Director"
        if interface_mode == "简洁模式":
            effective_preset = "Full Auto Director"
        elif interface_mode == "专业模式":
            effective_preset = "Custom"

        config = {
            "prompt": core_idea,
            "duration": total_duration,
            "shot_mode": shot_mode,
            "visual_style": visual_style,
            "camera_style": camera_style,
            "action_level": action_level,
            "story_curve": story_curve,
            "continuity_lock": bool(continuity_lock),
            "aspect_ratio": aspect_ratio,
            "target_model": target_model,
            "language": language,
            "mode": mode,
            "api_provider": api_provider,
            "api_base_url": resolved_base_url,
            "api_model": resolved_model,
            "api_key": key,
            "temperature": float(temperature),
            "timeout_seconds": int(timeout_seconds),
            "director_preset": effective_preset,
            "generation_mode": generation_mode,
            "reference_manifest": str(reference_manifest or "").strip(),
            "ui_mode": str(kwargs.get("ui_mode", "Basic") or "Basic"),
            "interface_mode": interface_mode or "Legacy",
            "professional_section": str(kwargs.get("professional_section", "") or ""),
            "project_format": str(kwargs.get("project_format", "Auto") or "Auto"),
            "genre": str(kwargs.get("genre", "Auto") or "Auto"),
            "directing_style": str(kwargs.get("directing_style", "Auto") or "Auto"),
            "era_setting": str(kwargs.get("era_setting", "") or "").strip(),
            "must_keep": str(kwargs.get("must_keep", "") or "").strip(),
            "must_avoid": str(kwargs.get("must_avoid", "") or "").strip(),
            "audio_policy": str(kwargs.get("audio_policy", "Dialogue + Exact Offscreen") or "Dialogue + Exact Offscreen"),
            "strict_speech_lock": bool(kwargs.get("strict_speech_lock", True)),
            "offscreen_dialogue_text": str(kwargs.get("offscreen_dialogue_text", "") or "").strip(),
            "api_key_env_var": api_key_env_var,
            "api_key_source": "environment" if env_key else ("legacy_workflow" if legacy_key else "missing"),
            "trusted_api_hosts": os.getenv(TRUSTED_HOSTS_ENV, ""),
        }
        if config["audio_policy"] not in AUDIO_POLICIES:
            config["audio_policy"] = "Dialogue + Exact Offscreen"
        if not config["api_base_url"]:
            raise RuntimeError("[BUFF AI 配置错误] API 地址未填写。")
        try:
            validate_api_endpoint(config["api_base_url"], config["trusted_api_hosts"])
        except APIClientError as exc:
            raise RuntimeError(f"[BUFF AI 配置错误] {exc}") from None
        if not config["api_model"]:
            raise RuntimeError("[BUFF AI 配置错误] 导演 LLM 模型未填写。")
        if not config["api_key"]:
            raise RuntimeError(f"[BUFF AI 配置错误] API Key 未找到。请设置环境变量 {api_key_env_var} 后完全重启 ComfyUI。")

        recorder = RunRecorder(kwargs.get("research_log", "Off"), kwargs.get("research_tag", ""))
        stage = "prepare"
        try:
            progress_total = 7 if mode == "Quality" else 5
            progress = self._make_progress(progress_total)
            self._report_progress(progress, 1, progress_total, "输入校验通过，准备导演上下文")

            inputs: Dict[str, Any] = dict(kwargs)
            inputs.update(
                {
                    "prompt": core_idea,
                    "character": character,
                    "scene": scene,
                    "visual_style": visual_style,
                    "camera_style": camera_style,
                    "target_model": target_model,
                    "generation_mode": generation_mode,
                    "reference_manifest": config["reference_manifest"],
                    "audio_policy": config["audio_policy"],
                    "strict_speech_lock": config["strict_speech_lock"],
                    "offscreen_dialogue_text": config["offscreen_dialogue_text"],
                }
            )
            if not str(inputs.get("character_profiles", "") or "").strip() and str(character or "").strip():
                inputs["character_profiles"] = str(character).strip()
            if not str(inputs.get("scene_environment", "") or "").strip() and str(scene or "").strip():
                inputs["scene_environment"] = str(scene).strip()
            if config["genre"] not in {"", "Auto"} and not str(inputs.get("genre_guidance", "") or "").strip():
                inputs["genre_guidance"] = config["genre"]
            if config["directing_style"] not in {"", "Auto"} and not str(inputs.get("directing_style_guidance", "") or "").strip():
                inputs["directing_style_guidance"] = config["directing_style"]
            if config["era_setting"] or config["must_keep"]:
                existing = str(inputs.get("director_book_guidance", "") or "").strip()
                added = "\n".join(
                    part
                    for part in (
                        f"Era / world setting: {config['era_setting']}" if config["era_setting"] else "",
                        f"Must keep: {config['must_keep']}" if config["must_keep"] else "",
                    )
                    if part
                )
                inputs["director_book_guidance"] = "\n".join(part for part in (existing, added) if part)
            if config["must_avoid"]:
                current = str(inputs.get("negative_constraints", "") or "").strip()
                inputs["negative_constraints"] = "\n".join(part for part in (current, config["must_avoid"]) if part)

            module_states = resolve_module_states(config["director_preset"], inputs)
            runtime = resolve_module_runtime(module_states, inputs)
            module_context = build_module_context(runtime)
            module_schema = build_dynamic_schema(module_states, config["language"])
            report = runtime_report(runtime)

            shot_plan_text = str(inputs.get("shot_plan", "") or "").strip()
            if not shot_plan_text and re.search(r"(?im)^\s*(?:shot|镜头)\s*\d+", core_idea):
                shot_plan_text = core_idea
            try:
                shot_lock = parse_shot_plan(shot_plan_text, total_duration)
            except ShotPlanError as exc:
                raise RuntimeError(f"[BUFF AI] Invalid shot plan: {exc}") from exc

            dialogue_entries = parse_dialogue_source(str(inputs.get("dialogue_text", "") or ""))
            offscreen_dialogue_entries = parse_exact_offscreen_dialogue(config["offscreen_dialogue_text"])
            references = collect_reference_assets(
                manifest_text=config["reference_manifest"],
                inputs=inputs,
            )
            ref_summary = reference_summary(references)
            entity_registry = build_entity_registry(
                character_names=inputs.get("character_names", ""),
                reference_manifest=config["reference_manifest"],
                dialogue_entries=dialogue_entries,
            )
            config["entity_registry"] = entity_registry
            self._report_progress(
                progress,
                2,
                progress_total,
                f"参考图处理完成：{len(references)} 张；生成方式={generation_mode}",
            )
            config["reference_count"] = len(references)
            config["reference_summary"] = ref_summary
            config["module_states"] = module_states
            config["module_report"] = report

            desired_shots = shot_lock.shot_count or self._recommended_shot_count(
                total_duration,
                shot_mode,
                action_level,
                core_idea,
            )

            system_prompt = build_director_system_prompt(module_states, config["language"])
            system_prompt += self._build_audio_system_rules(config, dialogue_entries, offscreen_dialogue_entries)
            user_prompt = self._build_user_prompt(
                config=config,
                inputs=inputs,
                module_context=module_context,
                dynamic_schema=module_schema,
                desired_shots=desired_shots,
                shot_lock=shot_lock,
                dialogue_entries=dialogue_entries,
                offscreen_dialogue_entries=offscreen_dialogue_entries,
            )
            recorder.set_request(
                config=config,
                inputs=inputs,
                module_states=module_states,
                guidance_inputs=[spec.guidance_input for spec in MODULE_SPECS.values()],
                dialogue_count=len(dialogue_entries),
                offscreen_dialogue_count=len(offscreen_dialogue_entries),
                reference_count=len(references),
                entity_count=len(entity_registry),
                locked_shot_count=shot_lock.shot_count,
                locked_times=shot_lock.has_locked_times,
                desired_shots=desired_shots,
            )

            strict_speech = bool(config["strict_speech_lock"]) or config["audio_policy"] != "Full Auto Audio"
            metric_context = dict(
                schema_text=module_schema,
                # Under SFX Only no spoken line is allowed, so every returned line counts as invented.
                dialogue_entries=() if config["audio_policy"] == "SFX Only" else dialogue_entries,
                # Exact off-screen lines are allowed speech only under this policy.
                offscreen_entries=offscreen_dialogue_entries if config["audio_policy"] == "Dialogue + Exact Offscreen" else (),
                entities=entity_registry,
                user_keywords=str(inputs.get("keywords", "") or ""),
                target_shots=desired_shots,
                shot_count_locked=bool(shot_lock.shot_count),
                safe_max_shots=1 if shot_mode == "Single Shot" else _safe_shot_count(total_duration),
            )
            first_raw: Optional[Dict[str, Any]] = None

            def record_metrics(**extra: Any) -> None:
                if not recorder.enabled:
                    return
                try:
                    recorder.set_metrics(
                        build_run_metrics(first=first_raw, strict_speech=strict_speech, **metric_context, **extra)
                    )
                except Exception as metric_exc:  # Metrics must never break generation.
                    print(f"[BUFF AI] 质量指标计算失败（不影响提示词生成）：{type(metric_exc).__name__}", flush=True)

            client = self._make_client(config)
            user_content = build_multimodal_content(user_prompt, references)

            self._report_progress(
                progress,
                3,
                progress_total,
                f"正在请求导演 LLM：{config['api_model']}；stream=false；超时={config['timeout_seconds']}s",
            )
            print(
                f"[BUFF AI] API endpoint: {self._endpoint_label(config)} | provider={config['api_provider']} | "
                f"model={config['api_model']} | refs={len(references)} | mode={mode}",
                flush=True,
            )
            stage = "first_request"
            first_started = time.perf_counter()
            try:
                first_text = client.chat(
                    system_prompt,
                    user_prompt,
                    user_content=user_content,
                    temperature=config["temperature"],
                    prefer_json_mode=True,
                )
            except APIClientError as exc:
                recorder.add_call(
                    "first",
                    elapsed_s=time.perf_counter() - first_started,
                    ok=False,
                    system_chars=len(system_prompt),
                    user_chars=len(user_prompt),
                    error=exc,
                )
                print(f"[BUFF AI] 首次 API 请求失败：{exc}", flush=True)
                raise RuntimeError(f"[BUFF AI API 错误] {exc}") from exc
            first_elapsed = time.perf_counter() - first_started
            self._report_progress(progress, 4, progress_total, f"首次 API 响应完成：{first_elapsed:.1f}s，正在解析分镜")
            first = extract_json_object(first_text)
            recorder.add_call(
                "first",
                elapsed_s=first_elapsed,
                ok=True,
                system_chars=len(system_prompt),
                user_chars=len(user_prompt),
                response_chars=len(first_text or ""),
                usage=getattr(client, "last_usage", None),
                json_ok=bool(first),
                response_text=first_text,
            )
            stage = "parse_first_response"
            if recorder.enabled and first:
                first_raw = copy.deepcopy(first)
            if not first:
                record_metrics()
                raise RuntimeError("[BUFF AI] AI returned invalid JSON. Lower temperature or use a stronger JSON-capable model.")

            first = self._apply_user_top_level_locks(first, inputs, ref_summary, config)
            storyboard = normalize_storyboard(
                first,
                total_duration=total_duration,
                shot_mode=shot_mode,
                continuity_lock=bool(continuity_lock),
                shot_lock=shot_lock,
                dialogue_entries=dialogue_entries,
                global_dialogue_direction=str(inputs.get("dialogue_direction", "") or ""),
                module_report=report,
            )
            storyboard = self._finalize_storyboard_metadata(storyboard, inputs, config, ref_summary)
            storyboard = enforce_audio_policy(
                storyboard,
                policy=config["audio_policy"],
                dialogue_entries=dialogue_entries,
                offscreen_entries=offscreen_dialogue_entries,
                strict_speech_lock=config["strict_speech_lock"],
                global_dialogue_direction=str(inputs.get("dialogue_direction", "") or ""),
            )

            if mode != "Quality":
                self._report_progress(progress, 5, progress_total, "分镜整理完成，输出提示词")

            pre_quality_storyboard = storyboard
            second = None
            if mode == "Quality":
                self._report_progress(progress, 5, progress_total, "Quality 模式：开始第二次专业审核请求")
                quality_system = system_prompt + (
                    "\n\nQUALITY SUPERVISOR PASS\nReview the normalized storyboard. Improve only enabled-module craft detail. "
                    "Do not change shot IDs, count, locked timing, exact names, dialogue text, keywords, reference bindings, "
                    "or explicit user decisions. Keep all production/directing fields in the selected OUTPUT LANGUAGE. "
                    "Never invent spoken words outside the configured dialogue/off-screen whitelist. "
                    "Return the same dynamic JSON structure."
                )
                quality_user = (
                    f"ACTIVE MODULE CONTEXT:\n{module_context}\n\n"
                    f"DYNAMIC SCHEMA:\n{module_schema}\n\n"
                    "LOCKED NORMALIZED STORYBOARD:\n"
                    + json.dumps(storyboard, ensure_ascii=False, indent=2)
                )
                stage = "quality_request"
                quality_started = time.perf_counter()
                try:
                    second_text = client.chat(
                        quality_system,
                        quality_user,
                        temperature=min(config["temperature"] + 0.05, 0.9),
                        prefer_json_mode=True,
                    )
                    second = extract_json_object(second_text)
                    recorder.add_call(
                        "quality",
                        elapsed_s=time.perf_counter() - quality_started,
                        ok=True,
                        system_chars=len(quality_system),
                        user_chars=len(quality_user),
                        response_chars=len(second_text or ""),
                        usage=getattr(client, "last_usage", None),
                        json_ok=bool(second),
                        response_text=second_text,
                    )
                except APIClientError as exc:
                    recorder.add_call(
                        "quality",
                        elapsed_s=time.perf_counter() - quality_started,
                        ok=False,
                        system_chars=len(quality_system),
                        user_chars=len(quality_user),
                        error=exc,
                    )
                    print(f"[BUFF AI] Quality 二次审核失败，保留第一版结果：{exc}", flush=True)
                    second = None
                quality_elapsed = time.perf_counter() - quality_started
                self._report_progress(progress, 6, progress_total, f"Quality 审核阶段结束：{quality_elapsed:.1f}s")
                if second:
                    stage = "quality_merge"
                    merged = self._merge_quality_storyboard(storyboard, second)
                    merged = self._apply_user_top_level_locks(merged, inputs, ref_summary, config)
                    storyboard = normalize_storyboard(
                        merged,
                        total_duration=total_duration,
                        shot_mode=shot_mode,
                        continuity_lock=bool(continuity_lock),
                        shot_lock=shot_lock,
                        dialogue_entries=dialogue_entries,
                        global_dialogue_direction=str(inputs.get("dialogue_direction", "") or ""),
                        module_report=report,
                    )
                    storyboard = self._finalize_storyboard_metadata(storyboard, inputs, config, ref_summary)
                    storyboard = enforce_audio_policy(
                        storyboard,
                        policy=config["audio_policy"],
                        dialogue_entries=dialogue_entries,
                        offscreen_entries=offscreen_dialogue_entries,
                        strict_speech_lock=config["strict_speech_lock"],
                        global_dialogue_direction=str(inputs.get("dialogue_direction", "") or ""),
                    )

            stage = "render"
            storyboard = apply_entity_identity_locks(
                storyboard,
                entities=config.get("entity_registry", []),
                explicit_character_names=inputs.get("character_names", ""),
            )

            enhanced_prompt = render_master_prompt(storyboard, module_states=module_states, config=config)
            shot_prompts = render_shot_prompts(storyboard, module_states=module_states, language=config["language"], include_keywords=True, config=config)
            storyboard_json = json.dumps(storyboard, ensure_ascii=False, indent=2)
            director_summary = render_director_summary(
                storyboard,
                module_states=module_states,
                preset=config["director_preset"],
                language=config["language"],
            )
            if mode == "Quality":
                self._report_progress(progress, 7, progress_total, "完成：提示词已生成")
            if mode == "Quality":
                record_metrics(
                    quality=second,
                    quality_attempted=True,
                    pre_quality_storyboard=pre_quality_storyboard,
                    post_quality_storyboard=storyboard,
                )
            else:
                record_metrics()
            recorder.succeed(
                storyboard=storyboard,
                enhanced_prompt=enhanced_prompt,
                shot_prompts=shot_prompts,
                quality_applied=bool(second),
            )
            print(f"[BUFF AI] 完成：shots={len(storyboard.get('shots', []))}，输出提示词。", flush=True)
            return enhanced_prompt, shot_prompts, storyboard_json, director_summary
        except Exception as exc:
            recorder.fail(stage, exc)
            raise
        finally:
            path = recorder.write()
            if path is not None:
                print(f"[BUFF AI] 研究记录已写入：{path}", flush=True)

    @staticmethod
    def _endpoint_label(config: Mapping[str, Any]) -> str:
        if config.get("api_provider") not in API_PROVIDERS:
            # Offline experiment backends (for example the Claude Code CLI) make no HTTP call.
            return f"{config.get('api_provider')} (no HTTP endpoint)"
        if config.get("api_provider") == "Anthropic":
            return sanitize_url(str(config["api_base_url"]).rstrip("/") + "/v1/messages")
        return sanitize_url(OpenAICompatibleClient.build_chat_url(config["api_base_url"]))

    def _make_client(self, config: Mapping[str, Any]) -> Any:
        if config.get("api_provider") == "Anthropic":
            return AnthropicClient(
                config["api_base_url"],
                config["api_key"],
                config["api_model"],
                config["timeout_seconds"],
                trusted_hosts=config.get("trusted_api_hosts"),
            )
        return OpenAICompatibleClient(
            config["api_base_url"],
            config["api_key"],
            config["api_model"],
            config["timeout_seconds"],
            trusted_hosts=config.get("trusted_api_hosts"),
        )

    @staticmethod
    def _output_language_rule(language: Any) -> str:
        value = str(language or "中文").strip().lower()
        chinese = value in {"中文", "chinese", "zh", "zh-cn", "简体中文"}
        if chinese:
            return (
                "- All production/directing values must be written in natural, professional Simplified Chinese.\n"
                "- Keep JSON schema keys unchanged in English for parser compatibility.\n"
                "- Dialogue BODY text must preserve the user's original text exactly; named-entity labels follow the canonical @entity rule below.\n"
                "- Keywords / LoRA Trigger tokens are opaque literal locks: copy verbatim, never translate, rename, split, or invent them.\n"
                "- Ordinary English user guidance may be translated faithfully into Chinese; opaque tokens remain unchanged."
            )
        return (
            "- All production/directing values must be written in professional English.\n"
            "- Keep JSON schema keys unchanged in English for parser compatibility.\n"
            "- Dialogue BODY text must preserve the user's original text exactly; named-entity labels follow the canonical @entity rule below.\n"
            "- Keywords / LoRA Trigger tokens are opaque literal locks: copy verbatim, never translate, rename, split, or invent them.\n"
            "- Ordinary Chinese user guidance must be translated faithfully into professional English; opaque tokens remain unchanged."
        )

    def _build_user_prompt(
        self,
        *,
        config: Mapping[str, Any],
        inputs: Mapping[str, Any],
        module_context: str,
        dynamic_schema: str,
        desired_shots: int,
        shot_lock: ShotPlanLock,
        dialogue_entries: list[dict[str, Any]],
        offscreen_dialogue_entries: list[dict[str, Any]],
    ) -> str:
        exact = {
            "character_names": canonicalize_name_list(inputs.get("character_names", "")),
            "dialogue_text": str(inputs.get("dialogue_text", "") or "").strip(),
            "offscreen_dialogue_text": str(inputs.get("offscreen_dialogue_text", "") or "").strip(),
            "keywords": str(inputs.get("keywords", "") or "").strip(),
        }
        global_context = {
            "project_format": config.get("project_format"),
            "genre": config.get("genre"),
            "directing_style": config.get("directing_style"),
            "era_setting": config.get("era_setting"),
            "must_keep": config.get("must_keep"),
            "must_avoid": config.get("must_avoid"),
            "duration_seconds": config.get("duration"),
            "shot_mode": config.get("shot_mode"),
            "recommended_shot_count": desired_shots,
            "aspect_ratio": config.get("aspect_ratio"),
            "generation_mode": config.get("generation_mode"),
            "target_model": config.get("target_model"),
            "visual_style": config.get("visual_style"),
            "camera_style": config.get("camera_style"),
            "action_level": config.get("action_level"),
            "story_curve": config.get("story_curve"),
            "reference_summary": config.get("reference_summary"),
            "reference_manifest": config.get("reference_manifest"),
            "audio_policy": config.get("audio_policy"),
            "strict_speech_lock": config.get("strict_speech_lock"),
        }
        shot_lock_payload = [
            {
                "number": section.number,
                "start": section.start,
                "end": section.end,
                "source_text": section.source_text,
            }
            for section in shot_lock.sections
        ]
        source_mode_rules = build_generation_mode_guidance(str(config.get("generation_mode", "Image to Video")))
        model_adapter_rules = ""
        if dict(config.get("module_states", {})).get("model_adapter", "Off") != "Off":
            model_adapter_rules = build_target_model_guidance(str(config.get("target_model", "Generic")))
        model_adapter_block = (
            f"\n\nTARGET-MODEL ADAPTER RULES:\n{model_adapter_rules}"
            if model_adapter_rules
            else ""
        )
        return f"""
Create a production-ready storyboard for the BUFF Production Director renderer.

CORE IDEA ({source_language(str(config.get('prompt', '')))} source):
{config.get('prompt', '')}

DIRECTOR PRESET:
{config.get('director_preset')}

GLOBAL CONTEXT:
{json.dumps(global_context, ensure_ascii=False, indent=2)}

SOURCE-MODE RULES:
{source_mode_rules}{model_adapter_block}

EXACT LITERAL LOCKS — COPY VERBATIM IN ANY LANGUAGE:
{json.dumps(exact, ensure_ascii=False, indent=2)}

PARSED DIALOGUE ENTRIES — assign each user entry exactly once whenever possible:
{json.dumps(dialogue_entries, ensure_ascii=False, indent=2)}

EXACT OFF-SCREEN DIALOGUE ENTRIES — these are the only allowed spoken off-screen lines when the policy permits them:
{json.dumps(offscreen_dialogue_entries, ensure_ascii=False, indent=2)}

AUDIO POLICY:
- Policy: {config.get('audio_policy')}
- Strict speech lock: {config.get('strict_speech_lock')}
- The AI may improve delivery, breathing, timing, facial reaction and performance direction, but must not invent spoken words outside the allowed lists.

EXPLICIT SHOT LOCKS:
{json.dumps(shot_lock_payload, ensure_ascii=False, indent=2)}

ACTIVE MODULES AND USER DATA:
{module_context}

OUTPUT LANGUAGE RULE:
{self._output_language_rule(config.get("language", "中文"))}

CANONICAL @ENTITY NAME RULE:
{entity_lock_instruction(config.get("entity_registry", []))}

SHOT DECISION RULE:
- If explicit Shot sections exist, return exactly their count and order. When all ranges are supplied, respect the locked timing semantics.
- Otherwise determine the final nearby count from story function, beats, blocking, dialogue time, action complexity, reactions, duration, and target-model motion budget.
- Every shot needs a start state, visible progression, clear end state, and no more than one dominant camera behavior.

RETURN ONLY JSON MATCHING THIS ACTIVE-MODULE SCHEMA:
{dynamic_schema}
""".strip()

    @staticmethod
    def _build_audio_system_rules(
        config: Mapping[str, Any],
        dialogue_entries: list[dict[str, Any]],
        offscreen_dialogue_entries: list[dict[str, Any]],
    ) -> str:
        policy = str(config.get("audio_policy", "Dialogue + Exact Offscreen"))
        strict = bool(config.get("strict_speech_lock", True))
        if policy == "Full Auto Audio" and not strict:
            return "\n\nAUDIO CONTROL\nFull Auto Audio: spoken content may be designed by the enabled director modules."
        if policy == "SFX Only":
            return (
                "\n\nAUDIO CONTROL — SFX ONLY\n"
                "Do not create dialogue, narration, chants, background conversations, announcements, or any intelligible spoken words. "
                "Only non-verbal ambience, Foley, impacts, breathing and music may be designed."
            )
        offscreen_rule = (
            "Only the exact supplied off-screen lines may be spoken off-screen."
            if policy == "Dialogue + Exact Offscreen"
            else "Do not create any spoken off-screen lines."
        )
        return (
            "\n\nAUDIO CONTROL — STRICT SPEECH WHITELIST\n"
            "User dialogue text is an immutable speech whitelist. The AI may decide HOW each line is performed but never add WHAT is spoken. "
            f"{offscreen_rule} "
            "Never invent narration, ad-lib, muttering, whispers with words, crowd speech, background conversation, chants, or extra announcements. "
            f"Allowed on-screen dialogue entries: {json.dumps(dialogue_entries, ensure_ascii=False)}. "
            f"Allowed off-screen dialogue entries: {json.dumps(offscreen_dialogue_entries, ensure_ascii=False)}."
        )

    def _apply_user_top_level_locks(
        self,
        raw: Mapping[str, Any],
        inputs: Mapping[str, Any],
        ref_summary: str,
        config: Mapping[str, Any],
    ) -> Dict[str, Any]:
        out = copy.deepcopy(dict(raw or {}))
        names = canonicalize_name_list(inputs.get("character_names", ""))
        if names:
            out["character_names"] = names
        # Keywords are user-owned opaque tokens. Never invent them when blank.
        out["keywords"] = str(inputs.get("keywords", "") or "").strip()

        field_map = {
            "scene_objective": "scene_objective",
            "character_profiles": "character_profiles",
            "character_relationships": "character_relationships",
            "scene_environment": "scene_environment",
            "spatial_continuity": "spatial_continuity",
            "visual_continuity": "visual_continuity",
            "camera_requirements": "camera_requirements",
            "performance_requirements": "performance_requirements",
            "lighting_requirements": "lighting_requirements",
            "dialogue_direction": "dialogue_direction",
            "offscreen_audio": "offscreen_audio",
            "sound_design": "sound_design",
            "transition_continuity": "transition_continuity",
            "negative_constraints": "negative_constraints",
            "extra_requirements": "extra_requirements",
        }
        for source_name, field in field_map.items():
            user = str(inputs.get(source_name, "") or "").strip()
            ai = str(out.get(field, "") or "").strip()
            out[field] = resolve_user_field(user, ai, exact=False)

        out["reference_summary"] = ref_summary
        out["aspect_ratio"] = config.get("aspect_ratio")
        out["generation_mode"] = config.get("generation_mode")
        out["target_model"] = config.get("target_model")
        out["director_preset"] = config.get("director_preset")
        return out

    def _finalize_storyboard_metadata(
        self,
        storyboard: Mapping[str, Any],
        inputs: Mapping[str, Any],
        config: Mapping[str, Any],
        ref_summary: str,
    ) -> Dict[str, Any]:
        out = copy.deepcopy(dict(storyboard))
        names = str(inputs.get("character_names", "") or "").strip()
        keywords = str(inputs.get("keywords", "") or "").strip()
        if names:
            out["character_names"] = names
        out["keywords"] = keywords
        out["reference_summary"] = ref_summary
        out["director_preset"] = config.get("director_preset")
        out["generation_mode"] = config.get("generation_mode")
        out["target_model"] = config.get("target_model")
        out["aspect_ratio"] = config.get("aspect_ratio")
        out["audio_policy"] = config.get("audio_policy")
        out["strict_speech_lock"] = config.get("strict_speech_lock")
        out["module_states"] = dict(config.get("module_states", {}))
        out["module_report"] = list(config.get("module_report", []))
        return out

    def _merge_quality_storyboard(
        self,
        base: Mapping[str, Any],
        rewrite: Mapping[str, Any],
    ) -> Dict[str, Any]:
        merged = copy.deepcopy(dict(base))
        for key, value in rewrite.items():
            if key == "shots":
                continue
            if value not in (None, "", [], {}):
                merged[key] = copy.deepcopy(value)

        by_id = {}
        for row in rewrite.get("shots", []) if isinstance(rewrite.get("shots"), list) else []:
            if isinstance(row, Mapping):
                try:
                    by_id[int(row.get("id", 0) or 0)] = row
                except Exception:
                    pass
        shots = []
        for base_shot in base.get("shots", []) if isinstance(base.get("shots"), list) else []:
            current = copy.deepcopy(dict(base_shot))
            row = by_id.get(int(current.get("id", 0) or 0))
            if row:
                for key, value in row.items():
                    if key in {"id", "start_time", "end_time", "duration", "source_index"}:
                        continue
                    if value not in (None, "", [], {}):
                        current[key] = copy.deepcopy(value)
            shots.append(current)
        merged["shots"] = shots
        return merged

    def _recommended_shot_count(
        self,
        duration: float,
        shot_mode: str,
        action_level: str,
        prompt: str,
    ) -> int:
        if shot_mode == "Single Shot":
            return 1
        if duration <= 4:
            base = 1
        elif duration <= 8:
            base = 2
        elif duration <= 15:
            base = 3
        elif duration <= 30:
            base = 5
        else:
            base = min(12, max(6, round(duration / 6.0)))

        text = str(prompt or "").lower()
        action_terms = (
            "fight", "attack", "run", "jump", "chase", "explode", "draw sword",
            "战斗", "攻击", "冲刺", "奔跑", "跳跃", "追逐", "爆炸", "拔刀",
        )
        complexity = sum(1 for term in action_terms if term in text)
        if action_level == "Low":
            base -= 1
        elif action_level == "High":
            base += 1
        if complexity >= 3:
            base += 1
        if shot_mode == "Multi Shot":
            base = max(2, base)
        safe_max = max(1, int(max(duration, 1.0) / 1.25))
        return max(1, min(base, safe_max, 12))
