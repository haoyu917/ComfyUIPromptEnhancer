# BUFF AI V3.2 语音控制快速指南

## 推荐设置

短剧、对白视频建议：

- `Audio Policy`：`Dialogue + Exact Offscreen`
- `Strict Speech Lock`：`true`

这样只有你明确填写的角色台词和画外台词允许成为“语言”。AI 仍然可以设计呼吸、停顿、音量、表情、环境声和动作声，但不能自己加词。

## 四种 Audio Policy

- **Strict Dialogue Only**：只允许 `dialogue_text` 里的台词。任何画外语言都禁止。
- **Dialogue + Exact Offscreen**：允许 `dialogue_text` + `offscreen_dialogue_text`，最适合短剧。
- **SFX Only**：完全禁止人类语言，只保留脚步、衣料、风雨、碰撞、环境声等。
- **Full Auto Audio**：允许 AI 自由设计声音和语言。最自由，也最容易出现额外台词。

## 正确填写角色台词

一行一条：

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
@铁角妖王｜你怕什么？
```

角色名和台词原文不会翻译。

## 正确填写画外台词

```text
门外司仪｜吉时已到！
```

不要把真正要说出来的话只写在 `sound_design` 或普通剧情描述里；需要准确说出的文字应放进对白白名单。

## API Key

V3.2 新节点不再显示 API Key 输入框。Windows PowerShell 设置：

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY", "你的新Key", "User")
```

设置后彻底退出并重新启动 ComfyUI。
