from pathlib import Path

from director_modules import MODULE_SPECS


ROOT = Path(__file__).resolve().parents[1]


def test_chinese_beginner_manual_contains_required_beginner_sections_and_every_module():
    path = ROOT / "USER_MANUAL_ZH.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    for phrase in (
        "完全不懂导演",
        "快速开始",
        "Full Auto Director",
        "Off / Auto / Guided",
        "参考图",
        "reference_manifest",
        "角色姓名",
        "对白",
        "Keywords",
        "EasyCLI",
        "常见问题",
        "Basic / Advanced",
        "project_format",
        "visual_style",
        "camera_style",
        "action_level",
        "story_curve",
        "continuity_lock",
        "temperature",
        "timeout_seconds",
        "must_keep",
        "must_avoid",
    ):
        assert phrase in text
    for spec in MODULE_SPECS.values():
        assert spec.title_zh in text


def test_english_beginner_manual_contains_required_sections_and_every_module():
    path = ROOT / "USER_MANUAL_EN.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    for phrase in (
        "You do not need directing knowledge",
        "Quick Start",
        "Full Auto Director",
        "Off / Auto / Guided",
        "Reference Images",
        "reference_manifest",
        "Character Names",
        "Dialogue",
        "Keywords",
        "EasyCLI",
        "Troubleshooting",
        "Basic / Advanced",
        "project_format",
        "visual_style",
        "camera_style",
        "action_level",
        "story_curve",
        "continuity_lock",
        "temperature",
        "timeout_seconds",
        "must_keep",
        "must_avoid",
    ):
        assert phrase in text
    for spec in MODULE_SPECS.values():
        assert spec.title_en in text


def test_readme_and_third_party_attribution_are_present():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSES" / "CINEMATIC_DIRECTOR_SKILL_MIT.txt").read_text(encoding="utf-8")
    assert "BUFF AI · Modular Director Skill Engine V3" in readme
    assert "ComfyUI-Installs" in readme
    assert "USER_MANUAL_ZH.md" in readme
    assert "USER_MANUAL_EN.md" in readme
    assert "Cinematic Director Skill v2.0" in notices
    assert "wangzhang-wu" in notices
    assert "MIT" in notices
    assert "Copyright (c) 2026 wangzhang-wu" in license_text
    assert "Permission is hereby granted" in license_text


def test_version_file_matches_current_release():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "3.2.1"
