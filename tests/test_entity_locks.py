from entity_locks import (
    apply_entity_identity_locks,
    build_entity_registry,
    canonicalize_entity_text,
    canonicalize_name_list,
)


def test_entity_registry_and_name_list_normalize_at_tokens():
    registry = build_entity_registry(
        character_names="铁角妖王, @紫衣女妖",
        reference_manifest="1=石室门口\n2=@石桌\n3=铁角妖王\n4=幽光妖谷\n5=紫衣女妖",
        dialogue_entries=[{"speaker": "@紫衣女妖", "text": "妖王，切莫如此……"}],
    )
    assert registry == ["铁角妖王", "紫衣女妖", "石室门口", "石桌", "幽光妖谷"]
    assert canonicalize_name_list("铁角妖王，紫衣女妖") == "@铁角妖王, @紫衣女妖"


def test_entity_text_expands_safe_unambiguous_aliases_and_preserves_existing_tokens():
    entities = ["铁角妖王", "紫衣女妖", "石室门口", "石桌", "幽光妖谷"]
    text = "妖王从石桌旁转头看向门口，女妖仍看着@铁角妖王。"
    out = canonicalize_entity_text(text, entities)
    assert out == "@铁角妖王从@石桌旁转头看向@石室门口，@紫衣女妖仍看着@铁角妖王。"


def test_storyboard_entity_pass_keeps_dialogue_body_and_keywords_verbatim():
    entities = ["铁角妖王", "紫衣女妖", "石室门口", "石桌"]
    board = {
        "character_names": "紫衣女妖, 铁角妖王",
        "keywords": "demon_king_lora, purple_girl_v2",
        "overview": "妖王逼近女妖，门口传来喊声。",
        "shots": [
            {
                "keyframe_note": "首帧妖王微倾，末帧妖王看向门口",
                "visual_information": "女妖背靠石桌。",
                "dialogues": [
                    {"speaker": "紫衣女妖", "text": "妖王，您明日便要大婚了，切莫如此……"}
                ],
            }
        ],
    }
    out = apply_entity_identity_locks(board, entities=entities)
    assert out["character_names"] == "@紫衣女妖, @铁角妖王"
    assert out["keywords"] == "demon_king_lora, purple_girl_v2"
    assert out["overview"] == "@铁角妖王逼近@紫衣女妖，@石室门口传来喊声。"
    assert out["shots"][0]["keyframe_note"] == "首帧@铁角妖王微倾，末帧@铁角妖王看向@石室门口"
    assert out["shots"][0]["visual_information"] == "@紫衣女妖背靠@石桌。"
    assert out["shots"][0]["dialogues"][0]["speaker"] == "@紫衣女妖"
    assert out["shots"][0]["dialogues"][0]["text"] == "妖王，您明日便要大婚了，切莫如此……"
