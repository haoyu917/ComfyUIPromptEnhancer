# BUFF AI 版本更新记录

本文汇总 V3.0.0 至 V3.2.1 的版本更新、修复说明和历史测试指引；按版本从新到旧排列。

### 3.2.1 · BUFF AI V3.2.1 修复说明

本补丁以用户提供的真实 V3.1.8 `node.py` 与 `renderer.py` 为基线重新合并，不再使用旧核心文件整段覆盖。

#### 修复重点

1. 保留 V3.1.8 动态多参考图链路：
   - `ContainsAnyDict` 继续动态接受 `reference_image_N`。
   - `collect_reference_assets(...)` 和 `build_multimodal_content(...)` 保持原有调用路径。
   - 6 张及以上动态参考图不会因为音频补丁而回退为旧实现。

2. 新增严格语音控制：
   - `Strict Dialogue Only`
   - `Dialogue + Exact Offscreen`（推荐）
   - `SFX Only`
   - `Full Auto Audio`
   - `strict_speech_lock=true` 时，只允许白名单中的对白。

3. MiniMax / Hailuo H3：
   - 用户对白编译为 `<d>[Language]...</d>`。
   - 稳定分配 S1 / S2 / S3 speaker id。
   - 画外对白单独编译，并要求画面内人物在画外对白期间保持闭口。
   - 非语言 Sound Layers 与 spoken dialogue 分离。

4. API Key：
   - 新增 `api_key_env_var`，默认 `BUFF_AI_API_KEY`。
   - 环境变量优先。
   - 旧 `api_key` 输入仍保留用于兼容已有 workflow，但新版 UI 默认隐藏它。

5. 前端 UI：
   - 使用 V3.1.8 的真实 `interface_mode / professional_section` 逻辑。
   - 简洁模式保持简洁。
   - 专业模式按分类显示字段。
   - `专业模式 → 高级模块` 可查看所有 `Off / Auto / Guided` 模块状态。
   - `Guided` 时才显示对应人工指导输入框。
   - 修复新版 ComfyUI DOM textarea 隐藏后仍占巨大高度的问题。

#### 推荐设置

短剧 + MiniMax / Hailuo：

- 生成方式：`Reference to Video`
- 语音策略：`Dialogue + Exact Offscreen`
- 严格对白锁定：`true`
- API Key 环境变量：`BUFF_AI_API_KEY`

角色对白：

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
@铁角妖王｜你怕什么？
```

画外对白：

```text
门外司仪｜吉时已到！
```

#### 安装

这是增量补丁。不要删除整个插件目录。

将压缩包内 `buff_ai_director_enhancer` 中的文件复制到现有同名插件目录并覆盖：

- `node.py`
- `renderer.py`
- `audio_control.py`
- `js/modular_director_ui.js`
- `VERSION`
- 本说明文件

其他 V3.1.8 文件继续保留。

---

### 3.2.0 · CHANGELOG

- Added `audio_policy`: `Strict Dialogue Only`, `Dialogue + Exact Offscreen`, `SFX Only`, `Full Auto Audio`.
- Added `strict_speech_lock` (default: enabled).
- Added exact `offscreen_dialogue_text` whitelist input.
- MiniMax / Hailuo prompts now compile spoken lines with stable `(S1)`, `(S2)` IDs and exact `<d>[Language]...</d>` blocks.
- Strict policies remove AI-invented dialogue, narration-like off-screen events, and verbal soundscape clauses before rendering.
- New node instances no longer expose a raw `api_key` widget. Use `BUFF_AI_API_KEY` or another environment variable configured by `api_key_env_var`.
- Legacy workflows can still pass the old key field for compatibility, but users should re-add the V3.2 node so the secret is no longer serialized.

---

### 3.1.8 · BUFF AI V3.1.8 修复说明

1. 修复 `BUFF AI · 文本预览` 与 `BUFF AI · API 连接测试` 的 DOM Widget 布局。预览区域现在向 ComfyUI 声明真实占用高度，文本框不会再超出 Node。
2. 自动参考图名称统一转换为 `@实体名`，例如 `石桌.jpg` -> `@石桌`。
3. 最终 Storyboard 增加确定性的实体名称锁：所有导演描述中，已命名角色、场景、道具必须使用完整 `@名称`；明确且无歧义的简称会自动扩展，例如 `妖王` -> `@铁角妖王`、`女妖` -> `@紫衣女妖`、`门口` -> `@石室门口`。
4. 用户对白正文和 LoRA / Keywords 不做替换，继续严格按原文保留；对白 speaker 标签会使用完整 `@名称`。

---

### 3.1.7 · BUFF AI V3.1.7 修复说明

本版只针对 ComfyUI 前端布局做修复，不改导演核心逻辑。

#### 修复内容

- 修复简洁模式和专业模式中，多行文本框与下面 Combo / 输入框发生重叠的问题。
- 修复最后一个多行文本框越过 Node 底部边界的问题。
- 多行文本框不再用 CSS 高度和 LiteGraph 逻辑高度两套互相冲突的数值。
- 改为通过 ComfyUI DOM Widget 的 `getMinHeight / getMaxHeight / getHeight` 提供统一布局高度。
- 逻辑高度包含 DOM Widget 默认上下 margin，保证下一行从文本框真正结束后再开始。
- 禁止用户拖动 textarea 自身尺寸，避免 DOM 高度超过 LiteGraph 已预留的行高。
- 隐藏字段只使用 ComfyUI 的 `widget.hidden` 参与布局，不再替换 `computeLayoutSize`。
- 简洁 / 专业 / 专业分类切换后重新 arrange，并重新计算 Node 高度。
- Legacy LiteGraph 模式精确 `setSize`；Vue Nodes 模式交给 ComfyUI 的 ResizeObserver 处理 Node 尺寸，避免双向尺寸反馈。
- 节点底部保留少量安全 padding，避免最后一个控件贴出 Node 边缘。

#### 节点名称

`BUFF AI · Modular Director Skill Engine V3.1.7`

不带 `Test` 后缀。

#### 安装测试

1. 关闭 ComfyUI。
2. 删除旧 `custom_nodes/buff_ai_director_enhancer`。
3. 放入本版同名目录。
4. 启动 ComfyUI。
5. 浏览器 `Ctrl + F5`。
6. 建议删除工作流中的旧 BUFF AI 主节点并重新添加一次。
7. 依次测试：简洁模式 → 专业模式 → 不同专业分类 → 简洁模式。

预期：所有 textarea、Combo 和普通输入框纵向不重叠，最后一个控件始终位于 Node 边界内，Node 高度随当前可见内容自动调整。

---

### 3.1.6 · BUFF AI V3.1.6 修复说明

#### 节点高度自动适配

V3.1.5 的节点高度逻辑会把“当前旧高度”和“重新计算高度”取最大值，因此节点一旦在专业模式或某个大型分类中被撑高，切回简洁模式或较小分类后无法缩回，出现大面积底部空白。

V3.1.6 改为：

- 每次模式 / 专业分类 / 高级模块状态发生变化后，重新读取当前可见 Widget。
- 直接使用 ComfyUI `node.computeSize()` 的当前可见控件最小布局高度。
- 高度允许自动增大，也允许自动缩小。
- DOM / Vue Widget 布局是异步的，因此会在当前帧、后续两帧以及 ResizeObserver 可能完成后的短延迟再次校正。
- 不再保留旧节点高度作为下限，因此不会因为曾经展开过专业模式而留下空白尾部。

节点显示名称：`BUFF AI · Modular Director Skill Engine V3.1.6`。

---

### 3.1.5 · BUFF AI V3.1.5 修复说明

本版针对 ComfyUI 新前端 / Nodes 2.0 下，`使用模式` 从「简洁模式」切换为「专业模式」后，专业字段不即时出现的问题。

修复策略：

1. 优先监听 ComfyUI 当前 `node.onWidgetChanged` 事件。
2. 保留旧版 widget callback 与 canvas redraw 兼容。
3. 增加 200ms 轻量状态检测兜底；只有模式/分类/模块状态实际变化时才执行 UI 重排。
4. DOM multiline widget 使用 `hidden + element.style.display + computeLayoutSize` 同步显隐，并在后续 animation frame 重算节点高度。
5. 删除节点标题中的 `Test` 后缀。

测试重点：无需重启 ComfyUI，直接在同一个节点中来回切换「简洁模式 / 专业模式」，专业设置分类应在约 0~0.2 秒内即时出现/隐藏。

---

### 3.1.4 · BUFF AI V3.1.4 Test 修复说明

本版专门修复新版 ComfyUI 中「专业模式」展开后多行文本框脱离节点边界、巨大 textarea 覆盖画布、字段位置错乱的问题。

#### 根因

新版 ComfyUI 将 multiline STRING 渲染为 DOM/Vue widget。V3.1.3 只通过旧 LiteGraph `computeSize()` 隐藏字段，DOM widget 仍可能保留布局高度；切换专业模式时还可能在节点完成 resize 前先显示，于是 textarea 漂到节点外。

#### 修复

- 同时处理旧 `computeSize` 与新 `computeLayoutSize`。
- 隐藏字段时 DOM widget 布局高度强制为 0，同时隐藏对应 HTML 元素。
- 显示字段时恢复原始布局函数。
- 专业模式/分类切换后执行立即 + 双 requestAnimationFrame 三次重排。
- 节点高度增加 DOM widget 的保守估算，避免依赖一次过期的 computeSize。
- 多行输入框默认高度限制为 58–120px，避免单个空输入框突然占据数百像素。
- DOM 多行字段 placeholder 改成中文，内部字段名不变，兼容旧工作流。

#### 测试

1. 完全关闭 ComfyUI。
2. 删除旧 `custom_nodes/buff_ai_director_enhancer` 后安装本版。
3. 启动后浏览器 Ctrl+F5。
4. 删除旧 BUFF 节点并重新添加 `V3.1.4 Test`。
5. 简洁/专业模式来回切换 3 次。
6. 专业模式依次切换所有专业分类，确认文本框始终在节点边界内。

---

### 3.1.3 · BUFF AI V3.1.3 Test 修复说明

本测试版基于 V3.1.2，重点修复三项用户反馈：

1. **提示词输出语言真正可选**
   - 新增/前置「提示词输出语言」：`中文` / `English`。
   - 选择中文时，导演字段、分镜字段和渲染标题使用简体中文。
   - 选择 English 时保持专业英文。
   - JSON 内部字段名继续保持英文，避免破坏解析器。
   - 角色姓名、用户对白、参考图名称、Keywords / LoRA Trigger 始终原样保留。

2. **LoRA Trigger / Keywords 变成常用输入**
   - 简洁模式与专业模式都直接显示「LoRA 触发词 / Keywords（可选）」。
   - 支持逗号或换行输入。
   - 不翻译、不改大小写、不拆词、不自动生成。
   - `enhanced_prompt` 会包含全局 Keywords。
   - `shot_prompts` 的每一个 Shot 都会携带同一组 Keywords，方便逐镜直接送入视频模型。

3. **专业模式显示修复**
   - 修复部分新版 ComfyUI 前端切换 Combo 后没有触发旧式 widget callback，导致「专业设置分类」和专业字段不刷新的问题。
   - 除 callback 外，增加 UI 状态 watcher；切换「简洁模式 / 专业模式」、切换专业分类、修改模块状态后都会自动刷新节点可见字段。
   - 专业模式继续按分类显示：剧情与角色、分镜与摄影、连续性与灯光、声音与剪辑、参考图、高级模块、API 设置。

#### 建议测试

- 删除工作流中的旧 BUFF 主节点后重新添加，避免旧 Widget Schema 缓存。
- 先选择「中文」，生成一次，确认文本预览中的标题和导演内容为中文。
- 填写例如 `purple_demoness_v2, X9_SceneTrigger`，确认 enhanced_prompt 与 shot_prompts 都原样出现。
- 切到「专业模式」，确认紧跟着出现「专业设置分类」，然后依次切换分类检查字段。

---

### 3.1.1 · BUFF AI V3.1.1 Test Fix · 测试说明

这是针对 V3.1 测试版“任务 0% 卡住 / API 配置错误不明显 / 中转站 client_gone”问题的修复版。核心导演、分镜和渲染逻辑不变。

#### 本次修复

- 新增 ComfyUI `VALIDATE_INPUTS` 预执行校验。API 地址、模型、API Key 缺失或 URL 格式错误时，工作流不会进入执行队列，而是直接显示配置错误。
- API 地址和导演 LLM 模型的默认值改为空，避免用户忘记配置中转站时误发到默认 OpenAI 地址。
- 支持 `BUFF_AI_API_BASE_URL`、`BUFF_AI_API_MODEL`、`BUFF_AI_API_KEY` 三个环境变量。
- OpenAI Chat Completions 请求现在显式发送 `stream=false`。
- 增加 SSE 兼容回退：如果某些中转仍错误地返回 `text/event-stream`，节点会读取到 `[DONE]` 后立即完成，不再一直等待连接关闭。
- 增加安全的控制台阶段日志，不打印 API Key。
- 增加 ComfyUI 进度条：准备上下文、处理参考图、首次 LLM 请求、解析、Quality 二次审核、完成。
- HTTP 401/403/404/429/5xx 等错误改成中文可读提示。
- 新增 `BUFF AI · API 连接测试` 节点，可先用一个极小的非流式请求单独验证地址、模型和 Key。
- 保留 `BUFF AI · 文本预览` 节点。

#### 推荐排查顺序

1. 完全重启 ComfyUI。
2. 先添加 `BUFF AI · API 连接测试`。
3. 填写中转 API 地址、模型 ID、API Key，运行连接测试。
4. 连接测试成功后，再运行主 Director 节点。
5. 首次调试建议主节点使用 `Fast`，确认第一阶段正常后再改 `Quality`；`Quality` 会调用两次 API。
6. 主节点 `enhanced_prompt` 接 `BUFF AI · 文本预览` 查看最终提示词。

#### 正常日志示例

```text
[BUFF AI] [1/5] 输入校验通过，准备导演上下文
[BUFF AI] [2/5] 参考图处理完成：5 张；生成方式=Reference to Video
[BUFF AI] [3/5] 正在请求导演 LLM：gpt-xxx；stream=false；超时=90s
[BUFF AI] API endpoint: https://example.com/v1/chat/completions | model=gpt-xxx | refs=5 | mode=Fast
[BUFF AI] [4/5] 首次 API 响应完成：12.4s，正在解析分镜
[BUFF AI] [5/5] 分镜整理完成，输出提示词
[BUFF AI] 完成：shots=3，输出提示词。
```

#### 配置错误示例

如果没有 API Key，应在执行前直接看到：

```text
[BUFF AI 配置错误] API Key 未填写。请填写 API Key，或设置 BUFF_AI_API_KEY 环境变量后重启 ComfyUI。
```

---

### 3.1 Test · BUFF AI V3.1 Test · 测试说明

这是基于 V3.0.0 的界面测试版，核心导演、分镜、渲染和 API 逻辑保持不变，主要用于验证更简单的 ComfyUI 使用体验。

#### 本版改动

- 新增两种用户界面模式：`简洁模式` / `专业模式`。
- 简洁模式继续使用 Full Auto Director 的完整导演能力，只隐藏不常用的专业输入。
- 专业模式使用 Custom 模块状态，并通过“专业设置分类”分组显示字段，避免节点无限变长。
- 常用输入名称和 Tooltip 改为中文说明。
- 旧 `Director Preset`、`Basic / Advanced` 和旧版 `character / scene` 字段保留用于兼容，但在 V3.1 UI 中隐藏。
- 参考图默认开启自动命名：优先读取上游节点标题；若仍是“加载图像 / Load Image”等默认标题，则尝试使用图片文件名。
- 自动生成内部 `reference_manifest`，简洁模式不需要手写 `1=角色 | ...`。
- 专业模式的“参考图”分类里可以关闭自动命名，并手工编辑 `reference_manifest`。
- BUFF AI 主节点现在可以作为 ComfyUI 工作流终点运行。
- 新增 `BUFF AI · 文本预览` 输出节点，可直接预览和复制 `enhanced_prompt`、`shot_prompts`、`storyboard_json`、`director_summary`。

#### 最简单测试方法

1. 删除工作流中的旧 BUFF AI 节点，并重新添加 `BUFF AI · Modular Director Skill Engine V3.1`。
2. 将 `duration` 接一个大于 0 的 Float，例如 `12.0`。
3. 使用 `简洁模式`。
4. 在“剧情描述”里只写剧情。
5. 如果是多参考图，选择 `Reference to Video`，把图片连接到 `reference_image_N`。
6. 建议把每个“加载图像”节点重命名成角色或场景名，例如 `@铁角妖王`、`@紫衣女妖`、`@石室`。
7. 将 `enhanced_prompt` 连接到 `BUFF AI · 文本预览` 的 `text`。
8. 运行工作流，在文本预览节点里查看结果。

#### 参考图自动命名示例

上游节点标题：

```text
@铁角妖王
@紫衣女妖
@石室
@幽光妖谷
```

V3.1 会自动生成内部绑定：

```text
1=@铁角妖王
2=@紫衣女妖
3=@石室
4=@幽光妖谷
```

如果上游节点没有自定义标题，则尝试使用图片文件名（去掉扩展名）。

---

### 3.0.0 · CHANGELOG

- Added Full Auto Director for one-line beginner ideas.
- Added 21 optional Director Skill modules with Off / Auto / Guided routing.
- Added Full Auto Director, Professional, Simple, and Custom presets.
- Added permanent story-function, blocking, camera, action-endpoint, observable-performance, and continuity rules.
- Added user-locked shot count and exact timestamp parsing.
- Added dynamic multi-reference image inputs and reference manifest binding.
- Added literal locks for character names, dialogue, and arbitrary-language keywords.
- Added English production direction with original-language names and dialogue.
- Added module-aware Fast and Quality API passes.
- Added stable Production Director Prompt rendering.
- Added Chinese and English beginner manuals.
