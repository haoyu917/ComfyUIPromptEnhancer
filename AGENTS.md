# Repository Guidelines

## Project Structure & Module Organization

This repository is a ComfyUI custom node. Core Python modules live at the repository root: `node.py` defines the node integration, while `director_core.py`, `director_modules.py`, `director_router.py`, `renderer.py`, `storyboard.py`, `shot_planner.py`, and related modules implement directing, prompt rendering, and API behavior. Browser-side node UI assets are in `js/`. Automated tests are in `tests/`, and user manuals and exported documents are in the root and `docs/`. Keep changes near the module that owns the behavior and update relevant manuals when user-facing options or workflows change.

## Build, Test, and Development Commands

There is no separate build step. ComfyUI loads the node from its custom nodes directory after restart. For development tests, install the optional dependency and run:

```bash
python -m pip install -r requirements-dev.txt
python run_tests.py
```

`run_tests.py` invokes `pytest -q` from the repository root. You can also run one test module with `python -m pytest -q tests/test_renderer.py`. Runtime dependencies are supplied by ComfyUI; `requirements.txt` is currently empty.

## Coding Style & Naming Conventions

Use standard Python style: four spaces, `snake_case` for modules, functions, and variables, and `PascalCase` for classes. Keep JavaScript assets consistent with their existing style and use descriptive `snake_case` or `camelCase` names to match the surrounding file. Prefer focused, dependency-light changes because the node runs inside ComfyUI. Preserve compatibility among Python behavior, the JavaScript widgets, and serialized workflow inputs.

## Testing Guidelines

Tests use pytest and are named `tests/test_*.py`; test functions should describe the behavior they check. Add or update focused tests for changes to routing, rendering, node integration, API language handling, and UI assets. Run `python run_tests.py` before submitting when possible. No coverage threshold or formatter/linter is configured in the repository.

## Commit & Pull Request Guidelines

Git history was unavailable in this checkout, so no established commit-message format could be confirmed. Use short, imperative commit subjects that name the change (for example, `Fix strict dialogue filtering`). Pull requests should explain the user-visible effect, summarize implementation details, list validation commands and results, link related issues when available, and include screenshots for visible UI changes. Note any manual or workflow migration steps.

## Security & Configuration

Do not commit API keys or other credentials. The node reads its key from the configured environment variable (default `BUFF_AI_API_KEY`); document configuration changes without including real secrets. Keep generated caches and local logs out of commits.
