# Skill-selection experiments

Tools for collecting the research dataset: which directing modules (skills) were active, and how well the model followed instructions under that configuration. Each run appends one record to the research log (see `research_log` in the user manuals); each record is one object of the information table.

## Files

- `benchmark_prompts.jsonl`: benchmark prompts, one JSON object per line. Required fields: `id`, `prompt`, `duration`, `tags` (a set-valued attribute, for example `["action", "dialogue"]`). Optional fields are passed to the node as-is: `dialogue_text`, `offscreen_dialogue_text`, `character_names`, `keywords`, `shot_plan`, `shot_mode`, `audio_policy`, `target_model`, `generation_mode`, `language`.
- `run_sweep.py`: runs every prompt under a set of module configurations.

## Configurations

For each prompt the sweep runs:

- three baselines, the presets `Full Auto Director` (`full_auto`), `Professional` (`professional`), and `Simple` (`simple`);
- `--random-configs N` random module subsets where each module is independently `Off` or `Auto` (probability 0.5). `product_macro` is only drawn for prompts tagged `product`. `Guided` is not used, because it requires human-written guidance and so measures a different question.

Random subsets are seeded by `--seed`, prompt ID, and draw index, so the same command always produces the same plan. Every record is tagged `exp=<experiment>;prompt=<id>;cfg=<config id>`; random config IDs start with `r` followed by a hash of the module states.

## Usage

Run from the repository root.

```bash
python experiments/run_sweep.py --experiment pilot1 --random-configs 3 --plan
```

Shows the plan and the number of API calls, without running anything.

```bash
python experiments/run_sweep.py --experiment pilot1 --random-configs 3 --dry-run
```

Runs the whole pipeline against a simulated model, with no API calls. Records go to `experiments/dry_run_logs/` (git-ignored) and their experiment name is prefixed `DRYRUN-`. **Simulated numbers are synthetic and must never be reported as results**; they exist only to test the pipeline and later analysis code.

```bash
python experiments/run_sweep.py --experiment pilot1 --random-configs 3 --api-base-url https://api.example.com/v1 --api-model MODEL_ID
```

A real run. It needs `BUFF_AI_API_KEY` and a `BUFF_AI_TRUSTED_API_HOSTS` entry for the endpoint host, exactly as for the ComfyUI node, and asks for confirmation before making calls (`--yes` skips the question). Useful options:

- `--max-runs N`: stop after N new runs, as a cost cap.
- `--mode Quality`: two calls per run, which also scores the Quality review pass.
- `--sleep S`: wait S seconds between runs, for rate-limited endpoints.
- `--only P01 P02`: run a subset of prompts.
- `--retry-errors`: re-run tags whose earlier run failed.

### Model backends (`--provider`)

- `openai-compatible` (the default) is any `/v1/chat/completions` endpoint, set with `--api-base-url` and `--api-model`.
- `anthropic` is the Claude API. It needs `pip install anthropic`, `BUFF_AI_API_KEY` set to a Claude Console key, and `api.anthropic.com` in `BUFF_AI_TRUSTED_API_HOSTS`. The model is whatever `--api-model` names, for example `claude-opus-5-5` or `claude-sonnet-5-5`.
- `claude-cli` runs each request through the logged-in Claude Code CLI (`claude -p`), using your own Claude subscription instead of an API key. Each call:
  - replaces Claude Code's system prompt with the node's;
  - disables all tools and MCP servers;
  - runs in an empty temporary directory and saves no session.

  `--api-model` defaults to `claude-opus-5-5`, and `--effort` is optional. Reference images are not supported. Usage counts against your subscription's limits.

**Do not pool backends.** Claude Code adds a little context of its own: about 1.3k input tokens were observed for a one-line prompt. Subscription runs are therefore a slightly different condition from API runs. Every record stores its backend in `config.api_provider`. Give each backend its own experiment name (for example `cli-pilot1`) and analyse it separately with `python -m research.evaluate --experiment cli-pilot1 ...`.

Runs already in the log are skipped, so an interrupted sweep can be restarted with the same command. The default log level is `Full text`, which keeps prompts and outputs for later content-quality scoring.
