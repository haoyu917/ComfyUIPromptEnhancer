"""Small built-in text preview/output node for BUFF AI prompt debugging."""

from __future__ import annotations


class BuffAITextPreview:
    """Display a STRING in the ComfyUI node and keep it as a workflow output."""

    DESCRIPTION = "Preview BUFF AI prompt text directly inside ComfyUI."
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "preview"
    CATEGORY = "BUFF AI/Debug"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "forceInput": True,
                        "multiline": True,
                        "tooltip": "连接 enhanced_prompt、shot_prompts、storyboard_json 或 director_summary，用于直接预览文本。",
                    },
                ),
            },
        }

    def preview(self, text: str):
        value = str(text or "")
        # `ui` is consumed by the companion JS extension; result keeps this node
        # usable as a STRING pass-through when desired.
        return {
            "ui": {
                "text": [value],
                "preview_title": ["提示词预览"],
            },
            "result": (value,),
        }
