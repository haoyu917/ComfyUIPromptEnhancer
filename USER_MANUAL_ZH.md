# BUFF AI · Modular Director Skill Engine V3 用户手册（中文）

## 1. 这个节点是做什么的

这个节点把你的简单想法，整理成视频模型更容易执行的专业导演提示词。

你可以只写一句：

> 妖王在石室里逼近女妖，女妖劝阻，门外突然传来婚礼宣告，妖王停住。

节点会自动补齐：

- 这场戏要表达什么；
- 人物应该站在哪里、怎么靠近、怎么停下；
- 应该分成几个 Shot；
- 每个 Shot 多长；
- 摄影机放在哪里、是否移动；
- 人物的眼神、呼吸、手部动作和结束姿势；
- 灯光从哪里来；
- 对白怎么说；
- 画外声音如何打断人物；
- 下一镜如何保持人物、服装、道具、位置和光线连续；
- 如何适配 MiniMax/Hailuo、Wan、Seedance、Kling、Veo 等视频模型。

**完全不懂导演也可以使用。** 最简单时只填写 `prompt`、视频时长和 API，然后选择 `Full Auto Director`。

---

## 2. 最快的使用方法

### 快速开始

1. `Director Preset` 选择 **Full Auto Director**。
2. 在 `prompt` 中写你想发生的事情。
3. 把外部 `Float(duration)` 接到节点的 `duration`，单位是秒。
4. 选择正确的 `generation_mode`：
   - 首帧图生视频：`Image to Video`
   - 多参考图参考生视频：`Reference to Video`
   - 纯文字生成视频：`Text to Video`
5. `aspect_ratio` 与最终视频比例保持一致。
6. `target_model` 选择最终使用的视频模型。
7. 填好 API：`api_base_url`、`api_model`，并通过环境变量保存 API Key。
8. 把 `enhanced_prompt` 接到视频节点的 Prompt 输入。
9. 运行工作流。

最简单的 `prompt` 示例：

```text
一个年轻武士在雨夜街道发现敌人，拔刀后向前冲刺，完成一次横向斩击并停住。
```

你不需要先写景别、机位、灯光或分镜。Full Auto Director 会自动安排。

---

## 3. 四种 Director Preset

### Full Auto Director

适合新手。大部分导演模块都使用 `Auto`。

你只给想法，AI 负责分析剧情、安排走位、分镜、摄影、表演、灯光、声音、连续性和模型适配。

### Professional

适合希望结果更克制、更接近正式制作流程的用户。会加载完整的专业导演模块，但不会自动加入额外的个人化导演风格镜头。

### Simple

适合快速批量生产。只启用最关键模块：剧情、节拍、走位、分镜、摄影、表演、连续性、参考图绑定、模型适配和质量检查。

### Custom

适合需要逐项控制的用户。只有在 `Custom` 下，每个模块自己的 `Off / Auto / Guided` 选择才直接决定是否加载。

---

## Basic / Advanced 界面模式

`ui_mode` 只影响界面显示，不会降低导演质量，也不会删除已经保存的数据。

### Basic

适合完全不懂导演的新手。模块的 `Off / Auto / Guided` 开关和模块专用指导框会隐藏，界面更短。你仍然可以选择 `Full Auto Director`、填写剧情、参考图、角色姓名、对白和 Keywords。

### Advanced

显示全部模块状态。某个模块设为 `Guided` 时，才显示对应的专用指导框。需要精确控制分镜、灯光、表演、声音或剪辑时使用。

建议：第一次使用保持 `Basic`；需要接管某项导演工作时，再改为 `Advanced`，并把 `Director Preset` 设为 `Custom`。

---

## 4. Off / Auto / Guided 是什么意思

每个导演模块都有三个状态：

### Off

不加载这个模块，也不要求 AI 生成这部分内容。

例如把“灯光与色彩”设为 Off，API Prompt 中不会加载灯光模块，最终 Prompt 也不会输出专门的灯光章节。

### Auto

加载这个模块，由 AI 根据已有信息自动完成。

即使是 Auto，只要你已经在相关输入框中填写了内容，AI 仍然必须尊重你的决定，并补充缺失细节。

### Guided

加载这个模块，并把对应输入框内容当作**硬性创作意图**。

AI可以把你的文字翻译成英文、补充专业术语和可执行细节，但不能推翻你的决定。

例如：

```text
中近景，两人保持同框，只允许轻微前移，不要环绕，不要手持。
```

AI可以扩展成更专业的摄影说明，但不能改成全景、环绕或手持。

如果选择 Guided 但输入框留空，AI仍会自动生成，不会报错。

---

## 5. 最常用的基础参数

### Director Preset

决定节点采用哪套模块组合。新手直接选 `Full Auto Director`；只有需要自己逐项控制时才选 `Custom`。

### project_format

告诉导演这次内容属于什么成片形式，例如单场戏、短片、竖屏短视频、预告片、广告、MV 或纪录片。选择 `Auto` 时由 AI 判断。

### genre

故事类型，例如爱情、动作、悬疑、恐怖、喜剧、暗黑奇幻。写 `Auto` 时 AI 根据剧情判断。

### directing_style

整体导演方式，例如自然叙事、亲密关系戏、慢燃悬疑、动态动作、商业质感。写 `Auto` 时 AI自行选择一种统一方式。

### era_setting

时代与世界设定，例如古代妖界、现代都市、蒸汽朋克。用于防止服装、建筑和道具跑到错误时代。

### must_keep

绝对必须保留的内容，例如“石桌始终在女妖身后”“妖王的角不能改变”。

### must_avoid

绝对不能出现的内容，例如“不要亲吻”“不要环绕运镜”“不要改变服装”。它会并入负面约束。

### prompt

你想让视频发生什么。只写故事也可以。

建议写清楚：

- 谁；
- 做什么；
- 什么事情发生变化；
- 最后停在什么状态。

### duration

视频总时长，单位是秒。它应该直接接外部 Float 秒数。

不要把帧数接到这里。视频模型的 `length` 如果需要帧数，应由数学节点单独转换。

### character（旧版兼容）

旧工作流的人物描述输入。新工作流建议改用 `character_profiles`。如果 `character_profiles` 留空，节点会把这里的内容作为人物资料使用。

### scene（旧版兼容）

旧工作流的场景描述输入。新工作流建议改用 `scene_environment`。如果 `scene_environment` 留空，节点会使用这里的内容。

### visual_style

画面总体质感，例如电影、写实、动漫、商业、暗黑奇幻或科幻。它不是具体运镜，而是整体视觉方向。

### camera_style

给摄影机一个总体倾向：自动、固定、平滑、动态、手持或电影化。具体镜头仍由摄影机语言模块根据剧情细化。

### action_level

控制动作密度：

- `Low`：轻动作、表情和对话为主；
- `Medium`：普通叙事动作；
- `High`：战斗、追逐等高动作场景。

它不是“画质”，而是告诉导演一段时间内能安排多少动作。

### story_curve

控制情绪/强度怎样发展：平稳、逐渐增强、结尾高潮或慢燃。选择 `Auto` 时 AI 根据故事判断。

### continuity_lock

开启后，上一 Shot 的人物位置、姿态、视线、道具状态等会强制传给下一 Shot。剧情视频通常建议保持开启。

### shot_mode

- `Auto`：AI根据剧情节拍决定 Shot 数量。
- `Single Shot`：强制一个 Shot。
- `Multi Shot`：至少两个 Shot。

### generation_mode

- `Image to Video`：上传图是视频的初始画面，动作从图片当前姿势开始。
- `Reference to Video`：图片用于锁定人物、服装、场景或风格，不要求视频从参考图当前姿势开始。
- `Text to Video`：没有视觉参考，人物和场景都由文字建立。

### aspect_ratio

必须尽量与最终视频一致：

- 横屏：`16:9`
- 竖屏：`9:16`
- 方形：`1:1`

### target_model

选择最终视频模型。启用“目标模型适配”后，AI会按照该模型的动作密度、参考图方式和 Prompt 结构写作。

### language

这是兼容设置。V3 的导演/制作说明固定使用英文；角色姓名、对白和 Keywords 永远保持原始语言。通常保持 `English` 即可。

### mode

- `Fast`：调用一次 API，速度快。
- `Quality`：在第一版分镜完成后，再调用一次 API 做专业检查与补全。第二次调用不能修改时间、角色姓名、用户对白、关键词或用户锁定内容。

### api_provider

API 类型，默认 `OpenAI-compatible`。

- `OpenAI-compatible`：中转站、EasyCLI 或任何提供 `/v1/chat/completions` 的服务，和以前的用法完全一样。
- `Anthropic`：直接使用 Claude 官方 API。需要先在 ComfyUI 使用的 Python 环境里运行 `pip install anthropic`；`api_base_url` 可以留空（默认 `https://api.anthropic.com`），但仍需把 `api.anthropic.com` 加入 `BUFF_AI_TRUSTED_API_HOSTS`。API Key 在 Claude Console（platform.claude.com）创建，API 按用量计费，和 claude.ai 的订阅分开。`api_model` 可自由填写，例如 `claude-opus-5-5` 或 `claude-sonnet-5-5`。Claude 当前的模型不接受 `temperature` 参数，所以选 Anthropic 时 `temperature` 不会生效。

### api_base_url

AI 接口地址。EasyCLI 同机使用时通常是 `http://127.0.0.1:8317/v1`。

### api_model

用于“导演思考和完善 Prompt”的语言模型名称，必须和 `/v1/models` 返回的模型 ID 完全一致。它不是最终生成视频的模型。

### api_key_env_var

新节点不再显示原始 `api_key` 输入框。请将密钥保存到 `BUFF_AI_API_KEY`，并在 ComfyUI 进程环境中通过 `BUFF_AI_TRUSTED_API_HOSTS` 授权准确的 API 主机和端口。使用逗号分隔的 `host[:port]`，不要写 scheme 或路径；未写端口时仅授权 HTTPS 默认端口 443。远程 API 必须使用 HTTPS；HTTP 仅允许已授权的本机回环地址，例如 `127.0.0.1:8317`。信任列表来自 ComfyUI 进程环境，工作流不能自行增加目标主机。

Windows PowerShell 设置示例：

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY", "你的新密钥", "User")
[Environment]::SetEnvironmentVariable("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317", "User")
```

设置后需要彻底退出并重新启动 ComfyUI。若使用自定义 `api_key_env_var` 名称，还必须将该名称加入本机的 `BUFF_AI_API_KEY_ENV_VARS` 逗号分隔白名单；`BUFF_AI_API_KEY` 始终允许。PowerShell 临时变量及 macOS/Linux 启动说明见 [README 配置指南](README.md#4-configuration)。API 测试节点只读取 `BUFF_AI_API_KEY`。

### temperature

控制 AI 的发挥程度。建议：

- `0.3–0.6`：更稳定、格式更规整；
- `0.7–1.0`：更有创意，但更容易偏离要求。

新手建议 `0.5` 或 `0.6`。

### timeout_seconds

一次 API 请求最多等待多少秒。普通模式建议 90 秒；Quality 或输入很多参考图时可提高到 120–180 秒。

### research_log / research_tag（研究记录，可选）

位于「专业模式 → API 设置」。用于记录每次运行的配置和结果，供之后分析"哪些导演模块组合效果更好"。默认 `Off`，不记录任何内容。

- `Off`：不记录。
- `Metrics only`：记录全部模块状态、主要参数、请求特征（剧情长度、是否中文、对白数、参考图数、填写了哪些指导框等）、每次 API 调用的耗时和 token 用量、运行结果（成功或失败阶段）。剧情只保存 SHA-256 哈希，不保存原文。
- `Full text`：在上面基础上，另外保存剧情原文、storyboard 和生成的提示词。

`research_tag` 是自由标签，例如实验编号或基准剧情编号。

开启记录后，每条记录还带有 `metrics`（自动质量指标）。注意：节点在模型返回后会自动修复输出（补齐或截断镜头、补回漏掉的对白、恢复 Keywords、统一 @实体 名称），所以最终提示词总是"合规"的。`metrics` 评估的是**修复之前**模型的原始返回，用来衡量某组模块配置让模型遵守要求的程度：

- 结构：JSON 是否合法；当前启用模块要求的顶层字段和每个镜头字段的填写比例（覆盖率），以及缺了哪些字段。
- 锁定遵守：用户对白是否全部出现、是否逐字保留、是否重复、是否编造了白名单以外的台词（仅在严格语音策略下算违规）；Keywords 留空时模型不能自行添加；锁定的 @实体 是否以完整 `@名称` 出现。
- 镜头数：用户锁定了 Shot Plan 时必须完全一致；未锁定时推荐数只是建议，只检查是否超出节点的安全上限。
- Quality 模式：单独记录第二次审核返回的指标，以及审核前后镜头内容的改动比例 `quality_change_ratio`。

`acceptable` 是由以上指标得出的"合格"标签：没有任何锁定违规，且字段覆盖率和实体名称保留率都不低于 0.8。阈值也写在记录里，所有原始测量值都会保留，之后可以用不同阈值重新计算。只有开启研究记录时才计算指标，不影响正常使用的速度。

记录写入 `research_logs/runs.jsonl`（插件文件夹内，已加入 .gitignore），每次运行一行 JSON。要换位置，请在 ComfyUI 进程环境里设置 `BUFF_AI_RESEARCH_LOG_DIR`；写入位置不能由工作流指定，避免导入的工作流在你的电脑上任意写文件。记录中从不包含 API Key、API 地址或信任主机列表。写入失败只会在控制台提示，不会影响提示词生成。在请求发出前就因输入错误（如 Shot Plan 编号不连续）而失败的运行不会被记录。

---

## 6. 用户内容的优先级和语言规则

节点遵守以下优先级：

1. 用户填写的角色姓名、对白、Keywords；
2. 用户在启用模块中填写的要求；
3. 用户的核心想法和参考图；
4. Director Skill 自动补全；
5. 普通 AI 自由发挥。

### 角色姓名

角色姓名保持原始语言。例如：

```text
@铁角妖王
@紫衣女妖
```

不会自动改成英文名称。

### 对白

对白保持用户原文和标点。推荐一行一句：

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
@铁角妖王｜你怕什么？
```

对白正文保持中文，但配音、停顿、呼吸、眼神和表演指导会写成英文。

### Keywords

Keywords 是完全不透明的字面锁。用户输入什么，最终就使用什么，不假设它一定是英文 LoRA Trigger Word。

例如：

```text
purple_demoness_v2, 妖王动作LoRA, X9_SceneTrigger
```

不会翻译、拆词、改大小写或改下划线。Keywords 留空时，节点也会保持为空，不会让 AI 猜测或发明 Trigger Word。

### 其他导演信息

- 输入中文：AI翻译成专业英文并补充细节。
- 输入英文：直接采用，只补充缺失内容。
- 中英混合：英文 Token 保留，中文部分翻译。

---

## 7. 多参考图怎么连接

V3继续支持动态参考图接口。

开始只有：

```text
reference_image_1
```

接上一张图后，会自动出现：

```text
reference_image_2
```

继续连接就会出现 `reference_image_3`、`reference_image_4`，理论上不固定数量。

### reference_manifest

使用编号说明每张参考图负责什么：

```text
1=@铁角妖王 | 主男性角色，锁定角、肩甲、体型和服装
2=@紫衣女妖 | 主女性角色，锁定脸、紫衣、发型和体型
3=@石室 | 石室、石桌、门口空间布局
4=@幽光妖谷 | 门外冷青环境和整体氛围
```

不要只写“参考图1、参考图2”。尽量说明：

- 这张图是谁或是什么；
- 负责身份、服装、道具、场景、布局还是氛围；
- 哪些信息必须保持。

---

## 8. Shot Plan 怎么使用

完全不懂分镜时，把 `shot_plan` 留空，AI会先分析剧情节拍，再决定 Shot 数量。

### 只锁定 Shot 数量和顺序

```text
Shot 1
妖王逼近女妖

Shot 2
女妖说话劝阻

Shot 3
画外婚礼宣告打断

Shot 4
两人停顿反应
```

这样 Python 强制保留 4 个 Shot，但每个 Shot 的时间由 AI 权重和 Python分配。

### 锁定 Shot 数量、顺序和时间

```text
Shot 1 · 0–2 秒
妖王逼近女妖

Shot 2 · 2–10 秒
女妖说话劝阻

Shot 3 · 10–11 秒
画外婚礼宣告打断

Shot 4 · 11–12 秒
两人停顿反应
```

这时 Shot 数和时间都被锁定。所有时间必须：

- 从 0 秒开始；
- 连续，无空隙和重叠；
- 最后一镜结束时间必须等于 `duration`。

---

## 9. 每个专业输入框大致做什么

下面这些输入框都可以留空。留空时，只要对应模块启用，AI会生成。

### scene_objective

这一场戏最终要完成什么。例如“建立压迫关系，并由画外婚礼宣告打断”。

### character_names

角色或关键实体的准确名称，保持原语言。

### character_profiles

人物长相、服装、身份、体型、道具和性格。

### character_relationships

人物之间的权力、情感、距离或冲突关系。

### scene_environment

场景地点、建筑、家具、天气、背景和关键道具。

### spatial_continuity

人物、门口、桌子、道具的位置、方向和距离怎样保持不变。

### visual_continuity

脸、服装、发型、颜色、氛围和物件状态怎样保持一致。

### camera_requirements

景别、角度、镜头是否移动、是否手持、是否允许环绕。

### performance_requirements

身体动作、眼神、表情、呼吸、手部动作和微表演。

### lighting_requirements

光从哪里来、什么颜色、明暗关系、阴影如何落下。

### dialogue_text

准确对白，原文锁定。

### dialogue_direction

音量、语气、停顿、吸气、重音、说话时的身体和眼神。

### offscreen_audio

画外音、门外喊声、脚步、撞击或声音打断事件。

### sound_design

环境底噪、雨声、衣料声、脚步、兵器声、音乐和静默。

### transition_continuity

当前 Shot 结束时留下什么状态，下一 Shot 如何接上。

### negative_constraints

明确不能出现什么，例如人物换脸、服装变化、刀突然回鞘、门口位置改变。

### extra_requirements

其他输入框没有覆盖的要求。

---

## 10. 21 个 Director Skill 模块

### 剧情与潜台词

高级控件：`module_story_subtext`；Guided 输入框：`story_subtext_guidance`。

分析表面事件、冲突、潜台词、情绪变化和可以被拍出来的视觉核心。

### 戏剧节拍

高级控件：`module_dramatic_beats`；Guided 输入框：`dramatic_beats_guidance`。

找出压力、信息、意图、权力或情绪发生变化的时刻。节拍不是切镜。

### 导演书与视觉统筹

高级控件：`module_director_book`；Guided 输入框：`director_book_guidance`。

建立整场戏统一的色调、摄影规则、表演尺度、剪辑节奏和视觉不变量。

### 人物走位与调度

高级控件：`module_blocking_staging`；Guided 输入框：`blocking_staging_guidance`。

先安排人物站在哪里、怎样移动、距离如何变化、最后停在哪里，再决定摄影机。

### 分镜规划

高级控件：`module_shot_planning`；Guided 输入框：`shot_plan`。

根据剧情功能决定几个 Shot、在哪里切镜、每一镜负责什么。

### 摄影机语言

高级控件：`module_camera_language`；Guided 输入框：`camera_requirements`。

决定景别、镜头角度、焦段感觉、机位和主要运镜。每个 Clip 最多一个主要摄影机行为。

### 人物表演指导

高级控件：`module_performance_direction`；Guided 输入框：`performance_requirements`。

把“害怕、害羞、愤怒”等抽象情绪变成眼神、呼吸、重心、表情和手部动作。

### 空间连续性

高级控件：`module_spatial_continuity`；Guided 输入框：`spatial_continuity`。

保持动作轴线、左右方向、人物距离、门窗位置、道具位置和运动方向。

### 角色连续性

高级控件：`module_character_continuity`；Guided 输入框：`visual_continuity`。

保持脸、发型、服装、体型、饰品、武器、左右手和物件状态。

### 灯光与色彩

高级控件：`module_lighting_color`；Guided 输入框：`lighting_requirements`。

安排光源方向、颜色、明暗、轮廓光、阴影、色调和光线连续。

### 对白与配音指导

高级控件：`module_dialogue_direction`；Guided 输入框：`dialogue_direction`。

安排说话音量、速度、停顿、呼吸、重音、口型起止和说话时的表演。

### 声音与画外事件

高级控件：`module_sound_offscreen`；Guided 输入框：`sound_design`。

安排环境声、动作声、音乐、静默、画外音和声音造成的可见人物反应。

### 关键帧策略

高级控件：`module_keyframe_strategy`；Guided 输入框：`keyframe_strategy_guidance`。

决定使用单首帧、首尾帧、逐镜关键帧还是故事板格来控制生成。

### 转场与剪辑

高级控件：`module_transition_editing`；Guided 输入框：`transition_continuity`。

安排剪辑点、出入点、视觉桥、声音桥和 Shot 之间的承接。

### 类型片手法

高级控件：`module_genre_playbook`；Guided 输入框：`genre_guidance`。

按照爱情、动作、悬疑、恐怖、喜剧、商业广告等类型的观众预期来控制节奏和镜头。

### 导演风格镜头

高级控件：`module_directing_style`；Guided 输入框：`directing_style_guidance`。

使用一种统一的高级导演方法控制构图、镜头、灯光、剪辑和声音，但不会复制已有电影的具体镜头或剧情。

### 参考图绑定

高级控件：`module_reference_binding`；Guided 输入框：`reference_binding_guidance`。

明确每张参考图负责哪个人物、道具、场景、布局或氛围，避免角色和参考图互换。

### 多片段交接

高级控件：`module_clip_handoff`；Guided 输入框：`clip_handoff_guidance`。

为多个生成 Clip 设计上一段结束状态和下一段开始状态，包括动作方向、眼神、道具和声音桥。

### 目标模型适配

高级控件：`module_model_adapter`；Guided 输入框：`model_adapter_guidance`。

根据 MiniMax/Hailuo、Wan、Seedance、Kling、Veo 等模型的控制方式调整 Prompt 结构和动作复杂度。

### 质量检查与失败预防

高级控件：`module_qc_failure_prevention`；Guided 输入框：`qc_requirements`。

检查参考图冲突、动作过载、动作没有终点、镜头逻辑错误、连续性断裂和模型能力不匹配。

### 产品与微距导演

高级控件：`module_product_macro`；Guided 输入框：`product_macro_guidance`。

用于商品、食物、化妆品、包装、材质和微距镜头。普通剧情默认关闭。

---

## 11. EasyCLI API 示例

如果 EasyCLI 和 ComfyUI 在同一台电脑：

```text
api_base_url = http://127.0.0.1:8317/v1
api_model = 你的 /v1/models 返回的准确模型名
api_key_env_var = BUFF_AI_API_KEY
```

例如：

```text
api_model = gpt-5.5
```

模型名称必须和 `/v1/models` 返回内容完全一致。

不要把 Codex OAuth JSON 文件里的 Token 当成节点 API Key。节点需要的是 EasyCLIProxyAPI 自己的访问密钥。

V3.2 新节点不会显示明文 API Key 输入框。把 EasyCLIProxyAPI 的访问密钥保存到 Windows 用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY", "你的新密钥", "User")
```

另外，为同机 EasyCLI 设置 `BUFF_AI_TRUSTED_API_HOSTS=127.0.0.1:8317`，再彻底退出并重新启动 ComfyUI。如果旧工作流曾经把密钥直接填进节点，应删除该值；若工作流已分享，则先撤销并更换该 Key，再删除旧节点并重新添加 V3.2 节点。API 测试节点只读取 `BUFF_AI_API_KEY`，不会使用工作流里遗留的 Key。

---

## 12. 一个完整的新手示例

### prompt

```text
铁角妖王在石室里逐渐逼近紫衣女妖。紫衣女妖娇羞但克制地劝阻他，因为妖王明天就要成婚。这时门外突然传来婚礼准备完成的喊声，妖王停止动作并看向门口。
```

### duration

```text
12
```

### Director Preset

```text
Full Auto Director
```

### generation_mode

```text
Reference to Video
```

### character_names

```text
@铁角妖王
@紫衣女妖
@石桌
@石室门口
@幽光妖谷
```

### dialogue_text

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
```

### reference_manifest

```text
1=@铁角妖王 | 锁定角、肩甲、体型和服装
2=@紫衣女妖 | 锁定脸、紫衣、发型和体型
3=@石室 | 锁定石室、石桌、门口空间布局
4=@幽光妖谷 | 锁定门外冷青环境氛围
```

其他输入框全部可以留空。

---

## 13. 四个输出口

### enhanced_prompt

完整 Production Director Prompt。通常接最终视频模型的 Prompt。

### shot_prompts

逐 Shot 分开的提示词，适合后续逐镜生成。

### storyboard_json

结构化数据，包含模块状态、Shot 时间、对白、动作节拍和连续性。适合自动化处理。

### director_summary

给人看的简短摘要，包括加载了哪些模块、Shot 数和时间。

---

## 14. 常见问题

### 为什么我的 Guided 输入框没有显示

只有模块状态为 `Guided` 时，对应输入框才显示。Preset 不是 Custom 时，Preset 会自动覆盖模块状态。

### 为什么我改了模块状态但没有生效

先把 `Director Preset` 改成 `Custom`。

### 为什么节点很长

V3提供完整导演模块。使用 Full Auto 时，大部分 Guided 输入框会隐藏。仍然建议把节点放在单独的 Prompt/Director 区域。

### 为什么 Prompt 是英文，但角色姓名和对白是中文

这是设计规则：导演指令使用英文，角色姓名和对白保持原始语言，Keywords 保持用户原文。

### 为什么 API 返回 JSON 错误

降低 `temperature` 到 0.3–0.6，换一个更擅长结构化 JSON 的模型，并确认代理支持 `/v1/chat/completions`。

### 为什么模型不知道多张参考图分别是谁

检查 `reference_manifest` 编号是否与实际连接顺序一致，并启用“参考图绑定”。同时确认 `api_model` 是支持图片理解的多模态模型；只支持文字的模型无法真正查看参考图。

### 为什么 12 秒被切成太多镜头

使用 `Simple` 或 `Custom`，把“分镜规划”设为 Guided，然后填写 Shot Plan；也可以选择 `Single Shot`。

### 为什么用户写的明确时间报错

显式时间必须从 0 开始、连续，并且最后结束时间等于 `duration`。

### 为什么人物动作太多导致崩坏

降低 `action_level`，启用“质量检查与失败预防”，或把复杂动作拆成多个 Shot/Clip。

### 为什么升级后新字段没有出现

删除工作流里的旧 BUFF 节点，然后重新搜索添加。ComfyUI 有时会保存旧节点实例的 Widget Schema。



## V3.2 语音控制

MiniMax H3 会把视频和声音一起生成，所以“声音描述”有可能被模型理解成额外台词。V3.2 把允许说出的文字改成白名单。

### Audio Policy

- `Strict Dialogue Only`：只允许 `dialogue_text` 中的角色台词。
- `Dialogue + Exact Offscreen`：允许角色台词 + `offscreen_dialogue_text` 中明确填写的画外台词。短剧推荐。
- `SFX Only`：禁止所有人类语言，只保留环境声、脚步、衣料、碰撞、风雨等。此时即使填写了 `dialogue_text` 或 `offscreen_dialogue_text`，台词也不会发送给模型。
- `Full Auto Audio`：允许 AI 自由设计语言和声音，风险最高。

### strict_speech_lock

建议保持 `true`。MiniMax / Hailuo 会收到明确的“只允许 `<d>...</d>` 里的文字被说出来”的规则。

### dialogue_text

一行一条，角色名和台词保持原文：

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
@铁角妖王｜你怕什么？
```

### offscreen_dialogue_text

只填写真正需要说出来的画外台词：

```text
门外司仪｜吉时已到！
```

如果只是门声、脚步声、风声，不要放这里，放进 `sound_design`。
