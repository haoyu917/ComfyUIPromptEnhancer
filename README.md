# ComfyUIPromptEnhancer

A ComfyUI custom node that turns a short idea, optional reference images, and user constraints into a structured storyboard and video-generation prompts. In ComfyUI, the node is named **BUFF AI · Modular Director Skill Engine**.

[中文手册](USER_MANUAL_ZH.md) · [English manual](USER_MANUAL_EN.md) · [Version history](V3_2_1_FIX_NOTES_ZH.md) · [Security and privacy](SECURITY.md)

## 1. Project Overview

The node uses an OpenAI-compatible Chat Completions language-model endpoint to plan and refine prompts. It does not call video-generation provider APIs. The `target_model` setting adapts prompt structure for the selected video model.

The package version in `VERSION` and the registered ComfyUI display name for the main node are **3.2.1**.

## 2. Key Features

- Full Auto Director and configurable directing presets.
- 21 optional directing modules with `Off`, `Auto`, and `Guided` states.
- Simple and professional interface modes, with dynamically shown controls.
- Reference-image inputs and reference-name binding.
- User locks for character and location names, dialogue, keywords, shot count, and timing.
- Fast and Quality modes, structured storyboard output, and per-shot prompts.
- Prompt adapters for Generic, Wan, Seedance, Kling, Veo, and MiniMax / Hailuo targets. These adapt generated prompts; they are not direct API integrations with those video services.
- Optional strict dialogue and off-screen dialogue controls for MiniMax / Hailuo H3 workflows.

## 3. Installation

The documented installation method is manual installation in **ComfyUI Desktop on Windows**:

1. Fully exit ComfyUI Desktop.
2. Copy this project folder into the Desktop instance's `custom_nodes` directory:

   ```text
   C:\Users\<username>\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes\buff_ai_director_enhancer
   ```

3. Start ComfyUI Desktop again.
4. Search for `BUFF AI · Modular Director Skill Engine V3.2.1`.

The package is a ComfyUI custom node; this repository does not include an installer or a ComfyUI launcher. For other ComfyUI installations, use that instance's configured `custom_nodes` directory and its normal launch procedure.

The node relies on NumPy and Pillow supplied by ComfyUI. `requirements.txt` is empty; `requirements-dev.txt` contains the optional pytest dependency for the developer test suite.

## 4. Configuration

By default, the main node reads its API key from the ComfyUI process environment using `BUFF_AI_API_KEY`; it only accepts a legacy workflow key for compatibility after endpoint trust validation. New main-node and API-test nodes do not expose an API-key widget.

| Variable | Purpose |
| --- | --- |
| `BUFF_AI_API_KEY` | Default API credential. The API test node uses this variable. |
| `BUFF_AI_TRUSTED_API_HOSTS` | Required local allowlist of exact API hosts and ports authorized to receive credentials. |
| `BUFF_AI_API_KEY_ENV_VARS` | Optional comma-separated allowlist for additional API-key environment-variable names used by the main node. `BUFF_AI_API_KEY` is always allowed. |
| `BUFF_AI_API_BASE_URL` | Optional default API base URL; a node input value takes precedence. |
| `BUFF_AI_API_MODEL` | Optional default language-model ID; a node input value takes precedence. |
| `BUFF_AI_RESEARCH_LOG_DIR` | Optional directory for research run logs (`runs.jsonl`). Defaults to `research_logs/` in the plugin folder. Logging is off unless the node's `research_log` input is set. |

### Trusted endpoint format

Set `BUFF_AI_TRUSTED_API_HOSTS` outside the workflow. Use comma-separated host entries without a scheme, path, or credentials. A host without a port authorizes HTTPS on port 443; include non-default ports explicitly.

```text
api.example.com,api.other-provider.com:8443,127.0.0.1:8317
```

For example, configure a third-party OpenAI-compatible service with `api_base_url = https://api.example.com/v1`, `api_model` set to the model ID required by that service, and `api.example.com` in the trusted list. The plugin sends the key only to a host and port in this machine-local list. This prevents an imported workflow from authorizing a new credential destination by itself.

Set `api_model` to the exact language-model ID expected by the endpoint. It is the model used for prompt planning, not the final video-generation model.

For a local EasyCLIProxyAPI endpoint, the node values are typically:

```text
api_base_url = http://127.0.0.1:8317/v1
api_model = exact model ID returned by /v1/models
api_key_env_var = BUFF_AI_API_KEY
```

Remote endpoints must use HTTPS so credentials and request content are encrypted in transit. HTTP is accepted only for loopback addresses such as `localhost`, `*.localhost`, `127.0.0.0/8`, and `::1`; the exact host and port must still be allowlisted. For a local service at `127.0.0.1:8317`, use that exact entry. `localhost` and `127.0.0.1` are distinct names in the allowlist.

### Windows PowerShell

For a ComfyUI process launched from the current PowerShell session, set process-scoped values before starting ComfyUI:

```powershell
$env:BUFF_AI_TRUSTED_API_HOSTS = "127.0.0.1:8317"
$env:BUFF_AI_API_KEY = "YOUR_API_KEY"
# Start ComfyUI using the launch command for your installation in this same window.
```

These `$env:` values are inherited by child processes started from that PowerShell session. They do not change an already-running ComfyUI process or automatically reach an app launched separately from the Start menu.

For the ComfyUI Desktop installation documented above, use the persistent user-scoped settings below and reopen Desktop. For a ComfyUI installation normally started from a terminal, set `$env:` in that terminal and run its existing launcher there; this project does not provide a universal launcher command or executable path.

To save user-scoped settings on Windows, use PowerShell and then fully exit and reopen ComfyUI Desktop:

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_TRUSTED_API_HOSTS", "127.0.0.1:8317", "User")
$secureKey = Read-Host "API key" -AsSecureString
$plainKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY", $plainKey, "User")
Remove-Variable plainKey, secureKey
```

If the Desktop app does not see newly saved values, sign out and back in to Windows or launch the app from a process with the configured environment. User-scoped environment variables are not an encrypted secret store: processes running as your account can read them. Avoid shared Windows accounts, and use a revocable API key with only the access you need. Do not type a real key directly into a command that may be saved in PowerShell history.

For an additional key variable, allow its *name* locally and set `api_key_env_var` to that name:

```powershell
$env:BUFF_AI_API_KEY_ENV_VARS = "MY_PROVIDER_KEY"
$env:MY_PROVIDER_KEY = "YOUR_API_KEY"
[Environment]::SetEnvironmentVariable("BUFF_AI_API_KEY_ENV_VARS", "MY_PROVIDER_KEY", "User")
```

Set the node's `api_key_env_var` input to `MY_PROVIDER_KEY`. The environment-variable name allowlist is also read by the ComfyUI process; after changing it at user scope, restart ComfyUI.

### macOS and Linux (Bash or Zsh)

Set variables in the same terminal session used to launch ComfyUI:

```bash
export BUFF_AI_TRUSTED_API_HOSTS="127.0.0.1:8317"
export BUFF_AI_API_KEY="YOUR_API_KEY"
# Start ComfyUI using the launch command for your installation in this same terminal.
```

Shell variables are inherited by processes launched from that shell. A ComfyUI app started separately from Finder, the Dock, or another desktop launcher may not inherit variables from `.zshrc` or `.bashrc`; launch it from the configured terminal or use that installation's user-level launch environment. Do not put real keys in a shared shell profile or checked-in script. If you persist `BUFF_AI_API_KEY_ENV_VARS`, make sure it is available to the ComfyUI process too.

To use a custom key variable name, for example `MY_PROVIDER_KEY`, authorize its name in the process environment and select it in the node's `api_key_env_var` input:

```bash
export BUFF_AI_API_KEY_ENV_VARS="MY_PROVIDER_KEY"
export MY_PROVIDER_KEY="YOUR_API_KEY"
```

Do not put a real key in a command that your shell may save in its history.

## 5. Usage

1. Add the main `BUFF AI · Modular Director Skill Engine V3.2.1` node and choose a preset such as `Full Auto Director`.
2. Enter a prompt, connect a duration value, and set `api_base_url` and `api_model` (or their optional environment defaults).
3. Add reference images and constraints as needed, then run the workflow.
4. Connect `enhanced_prompt` to a video-generation node. `shot_prompts`, `storyboard_json`, and `director_summary` are additional outputs. The `BUFF AI · 文本预览` node can display and copy text outputs.

`Fast` makes one language-model request. `Quality` makes a second review request. The `BUFF AI · API 连接测试` node sends a small `ping` request to check connectivity; it uses `BUFF_AI_API_KEY` and returns a success status without showing the model response.

For strict short-drama dialogue, the audio controls support `Strict Dialogue Only`, `Dialogue + Exact Offscreen`, `SFX Only`, and `Full Auto Audio`. The exact whitelist inputs are `dialogue_text` and `offscreen_dialogue_text`.

Example on-screen and off-screen lines:

```text
@紫衣女妖｜妖王，您明日便要大婚了，切莫如此……
@铁角妖王｜你怕什么？
门外司仪｜吉时已到！
```

## 6. Security and Privacy

The plugin sends the prompt and any attached reference images to the configured trusted language-model endpoint. Review that provider's privacy and retention terms before sending sensitive material. It rejects redirects, redacts URL query values in logs, and omits response bodies from API errors.

Do not store API credentials in shared ComfyUI workflows. Older main-node workflows may retain a legacy serialized `api_key` value; remove it, configure the environment variable, and delete/re-add the node before sharing. The main node accepts that legacy value for compatibility only after the endpoint passes local trust checks. The API-test node ignores legacy workflow key values. See [SECURITY.md](SECURITY.md) for details.

## 7. Project Structure

- Root Python modules: node registration, API client, directing modules, routing, rendering, storyboard planning, and reference-image handling.
- `js/`: ComfyUI browser-side node controls.
- `tests/`: pytest unit and integration tests. Run with `python run_tests.py` in an environment with pytest, NumPy, and Pillow; `requirements-dev.txt` installs pytest only, while ComfyUI supplies the runtime image dependencies.
- `USER_MANUAL_EN.md` and `USER_MANUAL_ZH.md`: current manuals. `docs/` contains older V3.0 PDF/DOCX exports.
- `V3_2_1_FIX_NOTES_ZH.md`: consolidated version history and fixes.
- `THIRD_PARTY_NOTICES.md` and `LICENSES/`: third-party attribution and license text.

The directing methodology includes a compact adaptation of material from Cinematic Director Skill v2.0; attribution details are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The repository does not currently declare a project-wide license for BUFF AI's original code and documentation. The MIT notice in `LICENSES/` applies to the credited third-party material only.

## 8. Troubleshooting

- **Endpoint is not trusted:** add the exact hostname and port to `BUFF_AI_TRUSTED_API_HOSTS`; do not include `https://` or a path. `localhost` and `127.0.0.1` must be listed separately.
- **Remote HTTP is rejected:** use the provider's HTTPS base URL. HTTP is limited to explicitly trusted loopback endpoints.
- **A custom key variable is rejected:** add its variable name to `BUFF_AI_API_KEY_ENV_VARS` in the ComfyUI process environment.
- **API key is missing:** confirm `BUFF_AI_API_KEY` is set in the environment inherited by ComfyUI, then restart the app. The API-test node does not read the key from a workflow.
- **New controls do not appear:** fully restart ComfyUI, refresh the browser, and remove/re-add the old node instance.
For detailed setup and feature instructions, see the [English](USER_MANUAL_EN.md) and [Chinese](USER_MANUAL_ZH.md) manuals. For third-party attribution, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
