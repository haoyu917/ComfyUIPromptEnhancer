# BUFF AI · Modular Director Skill Engine V3 User Manual (English)

## 1. What this node does

This node turns a simple idea into a professional, executable directing prompt for AI video generation.

You can enter one sentence such as:

> A demon king corners a demoness in a stone chamber. She warns him that he will marry tomorrow. An off-screen wedding announcement interrupts him.

The node can complete story purpose, beats, blocking, shot count, camera direction, performance, lighting, dialogue delivery, sound, continuity, reference binding, target-model adaptation, and quality checks.

**You do not need directing knowledge.** For the easiest workflow, use `Full Auto Director`, fill `prompt`, connect duration, configure the API, and leave advanced fields blank.

---

## 2. Quick Start

1. Set `Director Preset` to **Full Auto Director**.
2. Write your idea in `prompt`.
3. Connect a Float in seconds to `duration`.
4. Select the correct `generation_mode`:
   - `Image to Video`: the source image is the first visual state.
   - `Reference to Video`: images lock identity/design/scene roles but are not mandatory first frames.
   - `Text to Video`: everything is built from text.
5. Match `aspect_ratio` to the final video.
6. Select the correct `target_model`.
7. Configure `api_base_url` and `api_model`, then store the API key in an environment variable.
8. Connect `enhanced_prompt` to the video node's Prompt input.
9. Queue the workflow.

Basic idea example:

```text
A young swordsman notices an enemy in a rainy street, draws his katana, dashes forward, performs one horizontal slash, and stops in a guarded pose.
```

You do not need to write lenses, lighting, blocking, or shots first.

---

## 3. Director Presets

### Full Auto Director

Best for beginners. Most useful modules are loaded in Auto mode. You provide the idea; the AI Director completes the production plan.

### Professional

Loads the full professional narrative and production workflow but does not automatically add a separate personal directing-style lens.

### Simple

Best for fast batch production. It loads the essential story, beats, blocking, shots, camera, performance, continuity, reference binding, model adapter, and QC modules.

### Custom

Use this when you want direct control over every module's `Off / Auto / Guided` state.

---

## Basic / Advanced interface modes

`ui_mode` changes only what the node displays. It does not reduce directing quality or delete saved values.

### Basic

Best for beginners. Module `Off / Auto / Guided` controls and module-specific guidance boxes are hidden, making the node shorter. You can still choose a preset and fill the idea, references, names, dialogue, and Keywords.

### Advanced

Shows every module state. A module-specific guidance box appears only when that module is set to `Guided`. Use this mode when you want precise control over shots, camera, lighting, performance, sound, or editing.

Recommended first setup: keep `Basic`. Change to `Advanced` only when you need to take over part of the directing process; then set `Director Preset` to `Custom`.

---

## 4. Off / Auto / Guided

### Off

The module is not loaded into the API prompt and its dedicated output section is omitted.

### Auto

The module is loaded and the AI completes missing information. Any related user data that you already entered remains a user constraint.

### Guided

The module is loaded and its guidance field becomes a hard creative-intent lock. The AI may translate, clarify, and professionalize it, but must not contradict it.

Example:

```text
Medium close two-shot. Keep both characters in frame. Use only a subtle push-in. No orbit and no handheld camera.
```

If Guided is selected but the field is blank, AI generation still proceeds.

---

## 5. Core controls

### Director Preset

Chooses a ready-made module combination. Beginners should use `Full Auto Director`. Choose `Custom` only when you need direct control over individual modules.

### project_format

Describes the final content format: a scene, short film, social vertical video, trailer, commercial, music video, or documentary. `Auto` lets AI infer it.

### genre

The story genre, such as romance, action, thriller, horror, comedy, or dark fantasy. Use `Auto` when the AI should infer it.

### directing_style

The overall directing approach, such as natural narrative, intimate drama, slow-burn suspense, dynamic action, or commercial polish. `Auto` selects one coherent approach.

### era_setting

The period and world, such as an ancient demon realm, modern city, or steampunk future. It helps prevent incorrect wardrobe, architecture, and props.

### must_keep

Anything that must never be lost, such as “the stone table remains behind the demoness” or “the king's horns never change.”

### must_avoid

Anything that must not happen, such as “no kiss,” “no orbit camera,” or “do not change clothing.” It is merged into negative constraints.

### prompt

Describe what should happen. A simple story sentence is enough. It helps to state who acts, what changes, and the final state.

### duration

Total video time in seconds. Connect your external duration Float here. Do not connect a frame count.

### character (legacy compatibility)

Character description used by older workflows. New workflows should use `character_profiles`. If `character_profiles` is blank, this field is used as the character source.

### scene (legacy compatibility)

Scene description used by older workflows. New workflows should use `scene_environment`. If `scene_environment` is blank, this field is used.

### visual_style

The overall image treatment: cinematic, realistic, anime, commercial, dark fantasy, or science fiction. It defines visual direction rather than a specific camera move.

### camera_style

A general camera tendency: automatic, static, smooth, dynamic, handheld, or cinematic. The Camera Language module still refines individual shots.

### action_level

Controls motion density:

- `Low`: dialogue, expression, and small movement;
- `Medium`: normal narrative motion;
- `High`: fights, chases, and other action-heavy scenes.

It is not an image-quality setting.

### story_curve

Controls how intensity develops: flat, rising, climax at the end, or slow burn. `Auto` lets the AI infer it.

### continuity_lock

When enabled, the previous shot's pose, position, eyeline, prop state, and other end-state information is inherited by the next shot. It is normally recommended for narrative video.

### shot_mode

- `Auto`: AI determines shot count after beat analysis.
- `Single Shot`: forces one shot.
- `Multi Shot`: requires at least two shots.

### generation_mode

Controls how source images are interpreted.

### aspect_ratio

Match the final output: `16:9`, `9:16`, `1:1`, and so on.

### target_model

Select the final video model. When Target Model Adapter is active, the prompt structure and motion budget are adapted for that model family.

### language

This is a compatibility control. V3 writes directing and production instructions in English, while Character Names, Dialogue, and Keywords always remain in their original language. Keeping `English` is normally recommended.

### mode

- `Fast`: one API call.
- `Quality`: a second module-aware supervisor pass. It cannot change locked timing, names, user dialogue, keywords, or user constraints.

### api_base_url

The AI endpoint. For EasyCLI on the same computer, this is commonly `http://127.0.0.1:8317/v1`.

### api_model

The language model used to reason about direction and improve the prompt. It must exactly match an ID returned by `/v1/models`. It is not the final video-generation model.

### api_key_env_var

New nodes no longer expose a raw `api_key` widget. Set the credential in `BUFF_AI_API_KEY`; a server-side `BUFF_AI_TRUSTED_API_HOSTS` allowlist must also authorize the exact API host and port. Use comma-separated `host[:port]` entries without a scheme or path. A host without a port authorizes HTTPS on port 443. Remote APIs require HTTPS. HTTP is allowed only for an allowlisted loopback address such as `127.0.0.1:8317`.

Windows PowerShell example:

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY", "YOUR_NEW_KEY", "User")
[Environment]::SetEnvironmentVariable("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317", "User")
```

Fully exit and restart ComfyUI afterwards. The trusted host list is read from ComfyUI's process environment, not the workflow. A custom `api_key_env_var` name must also appear in the machine-local `BUFF_AI_API_KEY_ENV_VARS` allowlist; `BUFF_AI_API_KEY` is always allowed. For temporary shell variables and macOS/Linux launch notes, see the [README configuration guide](README.md#4-configuration). The API test node reads only `BUFF_AI_API_KEY`.

### temperature

Controls how freely the AI invents:

- `0.3–0.6`: more stable and structured;
- `0.7–1.0`: more creative but more likely to drift.

Beginners should use `0.5` or `0.6`.

### timeout_seconds

Maximum wait time for one API call. 90 seconds is a normal starting point; use 120–180 seconds for Quality mode or many reference images.

---

## 6. Language and user-data rules

Priority is:

1. Character Names, Dialogue, and Keywords;
2. explicit user guidance in enabled modules;
3. the core idea and references;
4. Director Skill completion;
5. general AI invention.

### Character Names

Character names stay exactly as entered, in the original language.

### Dialogue

Dialogue stays exactly as entered, including punctuation. Recommended format:

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
@铁角妖王｜你怕什么？
```

The spoken text remains Chinese, while voice and performance direction is written in English.

### Keywords

Keywords are opaque literal locks in any language. The node does not assume they are English LoRA triggers.

```text
purple_demoness_v2, 妖王动作LoRA, X9_SceneTrigger
```

They are not translated, respelled, split, or case-normalized. If Keywords is blank, the node keeps it blank and does not let AI invent LoRA or trigger tokens.

### Other production fields

- Chinese input is faithfully translated into professional English.
- English input is adopted directly.
- Mixed input keeps existing English tokens and translates Chinese clauses.

---

## 7. Reference Images

Reference inputs auto-expand. Connect `reference_image_1`, and the node creates `reference_image_2`; continue as needed.

Use `reference_manifest` to define each image's role:

```text
1=@铁角妖王 | primary male identity, horns, armor, body proportions
2=@紫衣女妖 | primary female identity, purple costume, face and hairstyle
3=@石室 | stone chamber, table and doorway layout
4=@幽光妖谷 | exterior cyan atmosphere and mood
```

State whether each image controls identity, costume, prop design, geography, lighting, or atmosphere.

---

## 8. Shot Plan

Leave `shot_plan` blank when you want the AI Director to decide shots professionally.

### Lock count and order only

```text
Shot 1
Approach and establish pressure.

Shot 2
The demoness speaks.

Shot 3
The off-screen announcement interrupts.
```

### Lock count, order, and exact time

```text
Shot 1 · 0-2s
Approach.

Shot 2 · 2-10s
Dialogue.

Shot 3 · 10-11s
Interruption.

Shot 4 · 11-12s
Reaction and hold.
```

Explicit times must start at zero, remain contiguous, and end at the requested duration.

---

## 9. Main information fields

All fields are optional. If the relevant module is active and a field is blank, AI fills it.

- `scene_objective`: what the scene must accomplish.
- `character_names`: exact names or entity tags.
- `character_profiles`: identity, appearance, clothing, body, props, temperament.
- `character_relationships`: power, emotion, conflict, physical distance.
- `scene_environment`: location, architecture, props, weather, background.
- `spatial_continuity`: positions, distances, screen direction, axis, entrances and exits.
- `visual_continuity`: identity, wardrobe, palette, atmosphere, object states.
- `camera_requirements`: framing, angle, lens behavior and movement.
- `performance_requirements`: body action, eyeline, breathing and micro-performance.
- `lighting_requirements`: source, direction, color, quality, contrast and shadow.
- `dialogue_text`: exact spoken lines.
- `dialogue_direction`: voice, pacing, breath, pause, emphasis and physical delivery.
- `offscreen_audio`: off-screen voices, footsteps, announcements or interruption events.
- `sound_design`: room tone, ambience, foley, spot effects, music or silence.
- `transition_continuity`: the state carried from one shot into the next.
- `negative_constraints`: specific failures to avoid.
- `extra_requirements`: anything not covered elsewhere.

---

## 10. The 21 Director Skill modules

### Story & Subtext

Advanced control: `module_story_subtext`; Guided input: `story_subtext_guidance`.

Finds literal event, conflict, subtext, emotional movement, and a concrete visual thesis.

### Dramatic Beats

Advanced control: `module_dramatic_beats`; Guided input: `dramatic_beats_guidance`.

Finds changes in pressure, information, intention, power, emotion, or action. A beat is not a camera cut.

### Director Book / Visual Treatment

Advanced control: `module_director_book`; Guided input: `director_book_guidance`.

Creates global tone, palette, camera grammar, performance register, editing rhythm, sound direction, and visual invariants.

### Blocking & Staging

Advanced control: `module_blocking_staging`; Guided input: `blocking_staging_guidance`.

Plans where bodies start, move, interact with props and space, change distance, and end before framing is chosen.

### Shot Planning

Advanced control: `module_shot_planning`; Guided input: `shot_plan`.

Determines how many shots are dramatically useful, where cuts occur, and what each shot accomplishes.

### Camera Language

Advanced control: `module_camera_language`; Guided input: `camera_requirements`.

Controls framing, angle, lens behavior, camera position, and one dominant camera behavior per clip.

### Performance Direction

Advanced control: `module_performance_direction`; Guided input: `performance_requirements`.

Turns abstract emotion into observable posture, breathing, facial tension, eyeline, hands, body weight, hesitation, and reaction.

### Spatial Continuity

Advanced control: `module_spatial_continuity`; Guided input: `spatial_continuity`.

Maintains axis, screen direction, geography, positions, distances, prop placement, entrances, exits, and motion vectors.

### Character Continuity

Advanced control: `module_character_continuity`; Guided input: `visual_continuity`.

Maintains face, hairstyle, clothing, proportions, accessories, weapon, handedness, injuries, and object state.

### Lighting & Color

Advanced control: `module_lighting_color`; Guided input: `lighting_requirements`.

Plans motivated sources, direction, color, contrast, rim/key/fill behavior, shadows, palette, and lighting continuity.

### Dialogue Direction

Advanced control: `module_dialogue_direction`; Guided input: `dialogue_direction`.

Plans volume, pace, pause, breath, stress, mouth start/end state, eyeline, and physical speech performance.

### Sound & Off-screen Events

Advanced control: `module_sound_offscreen`; Guided input: `sound_design`.

Plans room tone, ambience, foley, effects, music, silence, off-screen events, and visible reactions caused by sound.

### Keyframe Strategy

Advanced control: `module_keyframe_strategy`; Guided input: `keyframe_strategy_guidance`.

Chooses a single first frame, first/last frame pair, per-shot keyframes, or storyboard panels based on continuity risk.

### Transition & Editing

Advanced control: `module_transition_editing`; Guided input: `transition_continuity`.

Plans cut points, trim handles, visual/audio bridges, and the state handed into the next shot.

### Genre Playbook

Advanced control: `module_genre_playbook`; Guided input: `genre_guidance`.

Uses genre audience expectations to control pacing, reveal strategy, performance, lighting, sound, and shot duration.

### Directing Style Lens

Advanced control: `module_directing_style`; Guided input: `directing_style_guidance`.

Applies one coherent high-level directing method without copying a specific existing film shot, character, dialogue, or plot.

### Reference Binding

Advanced control: `module_reference_binding`; Guided input: `reference_binding_guidance`.

Assigns each reference image to a distinct character, prop, location, layout, lighting, or atmosphere role.

### Clip Handoff

Advanced control: `module_clip_handoff`; Guided input: `clip_handoff_guidance`.

Defines receiver-in and handoff-out pose, motion vector, screen direction, eyeline, prop state, lighting, and audio bridge for multiple clips.

### Target Model Adapter

Advanced control: `module_model_adapter`; Guided input: `model_adapter_guidance`.

Matches prompt shape and motion complexity to MiniMax/Hailuo, Wan, Seedance, Kling, Veo, or another target model.

### QC & Failure Prevention

Advanced control: `module_qc_failure_prevention`; Guided input: `qc_requirements`.

Checks reference mismatch, prompt overload, weak motion, missing endpoint, bad camera logic, continuity gaps, and tool mismatch.

### Product / Macro Direction

Advanced control: `module_product_macro`; Guided input: `product_macro_guidance`.

Directs products, food, cosmetics, packaging, materials, hero angles, and macro motion. It is off by default for narrative scenes.

---

## 11. EasyCLI API example

For EasyCLI and ComfyUI on the same computer:

```text
api_base_url = http://127.0.0.1:8317/v1
api_model = exact model ID returned by /v1/models
api_key_env_var = BUFF_AI_API_KEY
```

Do not paste the Codex OAuth JSON token. Use the EasyCLIProxyAPI access key.

Store the EasyCLIProxyAPI access key in the Windows user environment:

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY", "YOUR_NEW_KEY", "User")
[Environment]::SetEnvironmentVariable("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317", "User")
```

Set `BUFF_AI_TRUSTED_API_HOSTS` to `127.0.0.1:8317` for this local HTTP endpoint, then restart ComfyUI completely. If an older workflow already serialized a key, remove the value, rotate that key if it was shared, and delete/re-add the V3.2 node. The API test node reads its key from `BUFF_AI_API_KEY`; it ignores legacy workflow key values.

---

## 12. Beginner example

Only fill:

```text
prompt:
The demon king approaches the demoness in a stone chamber. She quietly warns him that he will marry tomorrow. A wedding announcement from outside interrupts him, and he stops and looks toward the doorway.

duration: 12
Director Preset: Full Auto Director
generation_mode: Reference to Video
```

Optional literal fields:

```text
Character Names:
@铁角妖王
@紫衣女妖

Dialogue:
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
```

The remaining fields can stay blank.

---

## 13. Outputs

- `enhanced_prompt`: complete production prompt for the video model.
- `shot_prompts`: separate prompt block for each shot.
- `storyboard_json`: structured data for automation.
- `director_summary`: human-readable module and shot summary.

---

## 14. Troubleshooting

### Guided field is not visible

Set the module state to Guided. Non-Custom presets automatically control module states.

### Manual module choices do not take effect

Set `Director Preset` to Custom.

### New controls are missing after upgrade

Delete the old node instance and add a new V3 node. ComfyUI can retain an old widget schema in an existing workflow node.

### API returns invalid JSON

Use temperature 0.3–0.6, select a model with good structured-output behavior, and confirm `/v1/chat/completions` compatibility.

### The model confuses reference images

Make sure reference_manifest numbering matches connection order and enable Reference Binding. Also confirm that `api_model` is vision-capable; a text-only language model cannot inspect connected images.

### Too many shots

Use Simple or Custom, set Shot Planning to Guided, enter a shot plan, or select Single Shot.

### Explicit shot timing is rejected

Times must begin at 0, remain contiguous, and end exactly at duration.

### Character motion breaks

Lower Action Level, enable QC & Failure Prevention, shorten the clip, simplify the camera, or split the action into multiple shots.



## V3.2 Audio Control

MiniMax H3 generates video and native audio together. A loose sound description can therefore be interpreted as extra speech. V3.2 uses a spoken-content whitelist.

### Audio Policy

- `Strict Dialogue Only`: only lines in `dialogue_text` may be spoken.
- `Dialogue + Exact Offscreen`: allows `dialogue_text` plus exact lines in `offscreen_dialogue_text`. Recommended for short drama.
- `SFX Only`: no human language; keep only ambience, footsteps, cloth, impacts, weather, etc.
- `Full Auto Audio`: AI may freely design speech and sound. Highest risk of extra dialogue.

### strict_speech_lock

Keep this `true` for controlled dialogue. MiniMax / Hailuo receives an explicit rule that only text inside `<d>...</d>` may be spoken.

### dialogue_text

One exact line per row:

```text
@PurpleDemoness｜Do not do this.
@DemonKing｜What are you afraid of?
```

### offscreen_dialogue_text

Use only for exact off-screen spoken words:

```text
WeddingAttendant｜The auspicious hour has arrived!
```

Put non-verbal events such as doors, footsteps, wind, or cloth movement in `sound_design`, not here.
