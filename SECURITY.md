# Security and Privacy

## Configure a trusted API endpoint

The node sends prompt text and attached reference images to the configured OpenAI-compatible API. It sends a Bearer API key, so the endpoint must be trusted before any request is made.

Set `BUFF_AI_TRUSTED_API_HOSTS` in the ComfyUI process environment to a comma-separated allowlist of exact host and optional port entries. Do not include a scheme, path, or credentials:

```text
BUFF_AI_TRUSTED_API_HOSTS=api.example.com,api.other-provider.com:8443,127.0.0.1:8317
```

On Windows PowerShell, save the allowlist at user scope like this, then fully restart ComfyUI:

```powershell
[Environment]::SetEnvironmentVariable("BUFF_AI_TRUSTED_API_HOSTS", "api.example.com,127.0.0.1:8317", "User")
```

A hostname without a port authorizes HTTPS on port 443. Include a non-default port explicitly. Remote endpoints must use HTTPS. Plain HTTP is accepted only for loopback destinations (`localhost`, `*.localhost`, `127.0.0.0/8`, or `::1`) and only when that exact host and port is allowlisted. Restart ComfyUI after changing environment variables. The client rejects redirects so it cannot forward authorization headers to a redirect target.

The allowlist is read from the ComfyUI process environment, not the workflow. A workflow cannot add its own endpoint to the list. Use providers you trust: an allowlisted provider receives the prompts and images you submit.

## Configure API keys

Set `BUFF_AI_API_KEY` in the ComfyUI process environment. This is the default credential source. The main node's `api_key_env_var` setting can select a different environment variable only if its name is also listed in the machine-local `BUFF_AI_API_KEY_ENV_VARS` comma-separated environment variable. `BUFF_AI_API_KEY` is always permitted.

New main-node instances do not expose a raw API-key widget. The API test node also uses `BUFF_AI_API_KEY` and does not consume a key stored in a workflow. For compatibility, the main node still accepts the legacy `api_key` value from old workflows, but only after the endpoint passes the same local trust and transport checks. Old workflow files may continue to contain a serialized key: remove that value, set the environment variable, then delete and re-add the node before sharing or committing the workflow. Rotate any key that was previously exposed.

## Logs and errors

API addresses are logged with URL user information removed and all query values redacted. Service response bodies are omitted from errors and the API test result. HTTP status codes and fixed diagnostic hints remain available.

## Repository hygiene

`.gitignore` excludes local environment files, credentials directories, caches, logs, ComfyUI output folders, model weights, and databases. It intentionally does not ignore JSON or image files globally so examples, fixtures, and documentation assets remain publishable. Inspect workflow exports and the staged file list before sharing; workflows can contain prompts, references, and legacy credentials.

## Reporting a vulnerability

Do not post credentials, private prompts, or exploitable details in a public issue. Contact the repository owner through GitHub's private vulnerability reporting feature if enabled. Otherwise, ask the owner for a private reporting channel before sharing sensitive details.
