"""Run a module-configuration sweep over the benchmark prompts.

Each (prompt, configuration) pair is one node execution with research logging
on, so every run appends one record (one object of the information table) to
the research log. Run from the repository root:

    # Plan only: show what would run and how many API calls it needs.
    python experiments/run_sweep.py --experiment pilot1 --random-configs 3 --plan

    # Simulated model, no API calls: checks the whole pipeline end to end.
    python experiments/run_sweep.py --experiment dry1 --random-configs 3 --dry-run

    # Real run (needs BUFF_AI_API_KEY and BUFF_AI_TRUSTED_API_HOSTS set).
    python experiments/run_sweep.py --experiment pilot1 --random-configs 3 \
        --api-base-url https://api.example.com/v1 --api-model MODEL_ID

Configurations are the three non-custom presets as baselines plus N random
Off/Auto module subsets per prompt. Random subsets are seeded by experiment
seed, prompt ID, and index, so a sweep is reproducible. Already-logged runs
are skipped, so an interrupted sweep can simply be started again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from director_modules import MODULE_SPECS, PRESET_STATES  # noqa: E402
from node import BuffAIDirectorEnhancer  # noqa: E402
from run_logger import RESEARCH_LOG_DIR_ENV, RESEARCH_LOG_FILENAME  # noqa: E402

DEFAULT_PROMPTS = Path(__file__).resolve().parent / "benchmark_prompts.jsonl"
DEFAULT_DRY_RUN_DIR = Path(__file__).resolve().parent / "dry_run_logs"
BASELINES = {
    "full_auto": "Full Auto Director",
    "professional": "Professional",
    "simple": "Simple",
}
# product_macro is a product-shot specialist module; keep it out of random
# subsets unless a prompt is tagged as a product shot.
PRODUCT_ONLY_MODULES = {"product_macro"}
CASE_INPUT_FIELDS = (
    "dialogue_text",
    "offscreen_dialogue_text",
    "character_names",
    "keywords",
    "shot_plan",
    "shot_mode",
    "audio_policy",
)


@dataclass(frozen=True)
class SweepConfig:
    config_id: str
    module_states: Dict[str, str]
    source: str  # "baseline" or "random"


@dataclass(frozen=True)
class PlannedRun:
    case: Dict[str, Any]
    config: SweepConfig
    tag: str


def load_prompts(path: Path) -> List[Dict[str, Any]]:
    cases = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        for required in ("id", "prompt", "duration"):
            if required not in case:
                raise ValueError(f"{path}:{number} is missing '{required}'")
        if case["id"] in seen:
            raise ValueError(f"{path}:{number} duplicates prompt id {case['id']!r}")
        seen.add(case["id"])
        cases.append(case)
    return cases


def states_signature(states: Mapping[str, str]) -> str:
    """Short stable ID for a module configuration: one character per module."""

    code = "".join({"Off": "0", "Auto": "1", "Guided": "2"}[states[key]] for key in MODULE_SPECS)
    return hashlib.sha1(code.encode("ascii")).hexdigest()[:8]


def baseline_configs() -> List[SweepConfig]:
    return [
        SweepConfig(config_id=name, module_states=dict(PRESET_STATES[preset]), source="baseline")
        for name, preset in BASELINES.items()
    ]


def random_configs(case: Mapping[str, Any], count: int, seed: int, p_on: float = 0.5) -> List[SweepConfig]:
    """Draw ``count`` distinct random Off/Auto subsets for one prompt."""

    product = "product" in case.get("tags", [])
    eligible = [key for key in MODULE_SPECS if product or key not in PRODUCT_ONLY_MODULES]
    rng = random.Random(f"{seed}:{case['id']}")
    taken = {states_signature(cfg.module_states) for cfg in baseline_configs()}
    configs: List[SweepConfig] = []
    attempts = 0
    while len(configs) < count and attempts < count * 50:
        attempts += 1
        states = {key: "Off" for key in MODULE_SPECS}
        for key in eligible:
            if rng.random() < p_on:
                states[key] = "Auto"
        signature = states_signature(states)
        if signature in taken or all(value == "Off" for value in states.values()):
            continue
        taken.add(signature)
        configs.append(SweepConfig(config_id=f"r{signature}", module_states=states, source="random"))
    return configs


def make_tag(experiment: str, prompt_id: str, config_id: str) -> str:
    return f"exp={experiment};prompt={prompt_id};cfg={config_id}"


def parse_tag(tag: str) -> Dict[str, str]:
    parts = {}
    for item in str(tag or "").split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    return parts


def plan_runs(
    cases: Sequence[Mapping[str, Any]],
    *,
    experiment: str,
    n_random: int,
    seed: int,
    include_baselines: bool = True,
) -> List[PlannedRun]:
    runs = []
    for case in cases:
        configs = (baseline_configs() if include_baselines else []) + random_configs(case, n_random, seed)
        for config in configs:
            runs.append(PlannedRun(case=dict(case), config=config, tag=make_tag(experiment, case["id"], config.config_id)))
    return runs


def logged_tags(log_path: Path, *, include_errors: bool) -> set[str]:
    """Tags already in the log. Failed runs count only if include_errors."""

    tags = set()
    if not log_path.exists():
        return tags
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        status = (record.get("outcome") or {}).get("status")
        if status == "ok" or include_errors:
            tags.add(record.get("tag", ""))
    return tags


def node_kwargs(run: PlannedRun, *, mode: str, language: str, temperature: float, log_level: str, api_base_url: str, api_model: str, timeout: int) -> Dict[str, Any]:
    case = run.case
    kwargs: Dict[str, Any] = {
        "prompt": case["prompt"],
        "duration": float(case["duration"]),
        "director_preset": "Custom",
        "generation_mode": case.get("generation_mode", "Text to Video"),
        "target_model": case.get("target_model", "Generic"),
        "language": case.get("language", language),
        "mode": mode,
        "temperature": temperature,
        "timeout_seconds": timeout,
        "api_base_url": api_base_url,
        "api_model": api_model,
        "research_log": log_level,
        "research_tag": run.tag,
    }
    for field in CASE_INPUT_FIELDS:
        if field in case:
            kwargs[field] = case[field]
    for key, state in run.config.module_states.items():
        kwargs[MODULE_SPECS[key].state_input] = state
    return kwargs


# ---- simulated model for --dry-run --------------------------------------------


class SimulatedClient:
    """Stands in for the language model so the pipeline can be tested offline.

    It answers with JSON matching the requested schema and makes more mistakes
    as the schema grows. Its numbers are synthetic and must never be reported
    as results.
    """

    def __init__(self, rng: random.Random, case: Mapping[str, Any]):
        self.rng = rng
        self.case = case
        self.last_usage: Optional[Dict[str, int]] = None

    def chat(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str:
        marker = "RETURN ONLY JSON MATCHING THIS ACTIVE-MODULE SCHEMA:"
        schema_text = user_prompt.split(marker, 1)[1] if marker in user_prompt else ""
        if not schema_text and "DYNAMIC SCHEMA:" in user_prompt:
            # Quality pass: the schema sits between these two headings.
            schema_text = user_prompt.split("DYNAMIC SCHEMA:", 1)[1].split("LOCKED NORMALIZED STORYBOARD:", 1)[0]
        try:
            schema = json.loads(schema_text)
        except ValueError:
            schema = {"title": "", "shots": [{"id": 1}]}
        n_fields = len(schema) + len((schema.get("shots") or [{}])[0])
        p_fill = max(0.6, 1.0 - 0.002 * n_fields)
        p_lock = max(0.6, 1.0 - 0.003 * n_fields)

        def fill(template: Mapping[str, Any]) -> Dict[str, Any]:
            return {key: ("simulated text" if self.rng.random() < p_fill else "") for key in template}

        response = fill({key: None for key in schema if key != "shots"})
        response["keywords"] = self.case.get("keywords", "") if self.rng.random() < p_lock else "simulated, keywords"
        shot_template = (schema.get("shots") or [{}])[0]
        locked = re.findall(r"(?im)^\s*(?:shot|镜头)\s*\d+", str(self.case.get("shot_plan", "")))
        count = len(locked) or max(1, int(float(self.case["duration"]) // 4))
        if self.rng.random() > p_lock:
            count += 1
        shots = []
        for i in range(count):
            shot = fill(shot_template)
            shot["id"] = i + 1
            shot["dialogues"] = []
            shots.append(shot)
        lines = [line for line in str(self.case.get("dialogue_text", "")).splitlines() if line.strip()]
        for index, line in enumerate(lines, start=1):
            if self.rng.random() < p_lock:
                text = re.split(r"\s*[|｜]\s*", line, maxsplit=1)[-1].strip()
                shots[min(index - 1, len(shots) - 1)]["dialogues"].append({"source_index": index, "text": text})
        response["shots"] = shots
        names = [name.strip() for name in str(self.case.get("character_names", "")).split(",") if name.strip()]
        if names and self.rng.random() < p_lock:
            response["overview"] = " ".join(names)
        text = json.dumps(response, ensure_ascii=False)
        self.last_usage = {
            "prompt_tokens": (len(system_prompt) + len(user_prompt)) // 3,
            "completion_tokens": len(text) // 3,
            "total_tokens": (len(system_prompt) + len(user_prompt) + len(text)) // 3,
        }
        return text


class SimulatedNode(BuffAIDirectorEnhancer):
    def __init__(self, case: Mapping[str, Any], seed: int, tag: str):
        self._client = SimulatedClient(random.Random(f"{seed}:{tag}"), case)

    def _make_client(self, config: Mapping[str, Any]) -> SimulatedClient:
        return self._client


# ---- command line ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True, help="Experiment name written into every tag, e.g. pilot1.")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--only", nargs="*", default=None, help="Run only these prompt IDs.")
    parser.add_argument("--random-configs", type=int, default=3, help="Random module subsets per prompt.")
    parser.add_argument("--no-baselines", action="store_true", help="Skip the three preset baselines.")
    parser.add_argument("--seed", type=int, default=20261119)
    parser.add_argument("--mode", choices=("Fast", "Quality"), default="Fast")
    parser.add_argument("--language", choices=("中文", "English"), default="中文")
    parser.add_argument("--temperature", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--log-level", choices=("Metrics only", "Full text"), default="Full text")
    parser.add_argument("--log-dir", type=Path, default=None, help="Overrides BUFF_AI_RESEARCH_LOG_DIR for this run.")
    parser.add_argument("--api-base-url", default=os.getenv("BUFF_AI_API_BASE_URL", ""))
    parser.add_argument("--api-model", default=os.getenv("BUFF_AI_API_MODEL", ""))
    parser.add_argument("--max-runs", type=int, default=None, help="Stop after this many new runs (cost cap).")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to wait between real API runs.")
    parser.add_argument("--retry-errors", action="store_true", help="Re-run tags whose earlier run failed.")
    parser.add_argument("--plan", action="store_true", help="Print the plan and exit without running.")
    parser.add_argument("--dry-run", action="store_true", help="Use a simulated model; makes no API calls.")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation before real API runs.")
    return parser


_ENV_KEYS = (RESEARCH_LOG_DIR_ENV, "BUFF_AI_TRUSTED_API_HOSTS", "BUFF_AI_API_KEY")
DRY_RUN_HOST = "127.0.0.1:9"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the sweep; environment changes are undone when it returns."""

    saved = {key: os.environ.get(key) for key in _ENV_KEYS}
    try:
        return _main(argv)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_prompts(args.prompts)
    if args.only:
        wanted = set(args.only)
        cases = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            print(f"Unknown prompt IDs: {sorted(missing)}", file=sys.stderr)
            return 2

    experiment = f"DRYRUN-{args.experiment}" if args.dry_run else args.experiment
    if args.log_dir is not None:
        os.environ[RESEARCH_LOG_DIR_ENV] = str(args.log_dir)
    elif args.dry_run:
        # Keep synthetic records out of the real research log.
        os.environ[RESEARCH_LOG_DIR_ENV] = str(DEFAULT_DRY_RUN_DIR)
    if args.dry_run:
        # The simulated client never opens a connection; the placeholder
        # endpoint only has to pass the node's trust check in this process.
        trusted = [host for host in os.environ.get("BUFF_AI_TRUSTED_API_HOSTS", "").split(",") if host.strip()]
        os.environ["BUFF_AI_TRUSTED_API_HOSTS"] = ",".join(trusted + [DRY_RUN_HOST])
        args.api_base_url = f"http://{DRY_RUN_HOST}/v1"
        args.api_model = "simulated"
        os.environ.setdefault("BUFF_AI_API_KEY", "dry-run-placeholder")

    from run_logger import resolve_log_path

    log_path = resolve_log_path()
    runs = plan_runs(cases, experiment=experiment, n_random=args.random_configs, seed=args.seed, include_baselines=not args.no_baselines)
    done = logged_tags(log_path, include_errors=not args.retry_errors)
    pending = [run for run in runs if run.tag not in done]
    if args.max_runs is not None:
        pending = pending[: args.max_runs]
    calls_per_run = 2 if args.mode == "Quality" else 1

    print(f"Experiment:    {experiment}")
    print(f"Prompts:       {len(cases)}")
    print(f"Configs:       {len(runs)} planned ({len(runs) - len(pending)} already logged or capped)")
    print(f"To run now:    {len(pending)} runs, about {len(pending) * calls_per_run} API calls ({args.mode})")
    print(f"Log file:      {log_path}")
    if args.plan:
        for run in pending:
            active = sum(1 for value in run.config.module_states.values() if value != "Off")
            print(f"  {run.tag}  modules_on={active}")
        return 0
    if not pending:
        print("Nothing to do.")
        return 0

    if not args.dry_run:
        if not args.api_base_url or not args.api_model:
            print("Set --api-base-url and --api-model (or BUFF_AI_API_BASE_URL / BUFF_AI_API_MODEL).", file=sys.stderr)
            return 2
        if not args.yes:
            answer = input(f"Make about {len(pending) * calls_per_run} real API calls? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print("Cancelled.")
                return 1

    ok = failed = 0
    for number, run in enumerate(pending, start=1):
        node = SimulatedNode(run.case, args.seed, run.tag) if args.dry_run else BuffAIDirectorEnhancer()
        kwargs = node_kwargs(
            run,
            mode=args.mode,
            language=args.language,
            temperature=args.temperature,
            log_level=args.log_level,
            api_base_url=args.api_base_url,
            api_model=args.api_model,
            timeout=args.timeout,
        )
        started = time.perf_counter()
        try:
            node.generate(**kwargs)
            ok += 1
            status = "ok"
        except Exception as exc:  # The failure is already in the research log.
            failed += 1
            status = f"error: {type(exc).__name__}: {str(exc)[:120]}"
        print(f"[{number}/{len(pending)}] {run.tag} ({time.perf_counter() - started:.1f}s) {status}", flush=True)
        if args.sleep and not args.dry_run and number < len(pending):
            time.sleep(args.sleep)

    print(f"Done: {ok} ok, {failed} failed. Records appended to {log_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
