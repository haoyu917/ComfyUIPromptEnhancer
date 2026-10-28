from .node import BuffAIDirectorEnhancer
from .text_preview import BuffAITextPreview
from .api_test import BuffAIAPITest

NODE_CLASS_MAPPINGS = {
    "BUFF_AIDirectorPromptEnhancer": BuffAIDirectorEnhancer,
    "BUFF_AITextPreview": BuffAITextPreview,
    "BUFF_AIAPITest": BuffAIAPITest,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BUFF_AIDirectorPromptEnhancer": "BUFF AI · Modular Director Skill Engine V3.2.1",
    "BUFF_AITextPreview": "BUFF AI · 文本预览",
    "BUFF_AIAPITest": "BUFF AI · API 连接测试",
}

WEB_DIRECTORY = "./js"

__all__ = [
    "BuffAIDirectorEnhancer",
    "BuffAITextPreview",
    "BuffAIAPITest",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
