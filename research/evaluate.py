"""Cross-validated comparison of granular three-way classifiers and baselines.

Run from the repository root:

    python -m research.evaluate --log research_logs/runs.jsonl --out-dir research_reports/pilot1

Predicts whether a run is acceptable from its request and module
configuration. Folds are grouped by benchmark prompt, so every prompt's runs
are either all in training or all in testing.

Metric definitions (out-of-fold predictions pooled over all folds):
  coverage   committed decisions (accept or reject) / all test objects
  accuracy   correct committed decisions / committed decisions
  precision  acceptable among accepted
  recall     accepted among acceptable (a deferred acceptable run is not recalled)
  f1         harmonic mean of precision and recall
Baselines always commit, so their coverage is 1.

Baselines (SVM, decision tree, KNN, naive Bayes, as in the paper) need
scikit-learn; without it they are skipped and the report says so.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.dataset import Dataset, build_dataset, load_benchmark_tags, load_records  # noqa: E402
from research.granular_3wd import (  # noqa: E402
    ACCEPT,
    DEFER,
    REJECT,
    DistanceRelation,
    GranularThreeWayClassifier,
    InformationTable,
)

DEFAULT_BENCHMARK = ROOT / "experiments" / "benchmark_prompts.jsonl"


# ---- folds -------------------------------------------------------------------


def grouped_folds(groups: Sequence[str], n_folds: int) -> List[Tuple[List[int], List[int]]]:
    """Deterministic grouped folds; ``n_folds <= 0`` means leave one group out."""

    unique = sorted(set(groups))
    if len(unique) < 2:
        raise ValueError("Cross-validation needs runs from at least two prompts.")
    k = len(unique) if n_folds <= 0 else min(n_folds, len(unique))
    fold_of = {group: i % k for i, group in enumerate(unique)}
    folds = []
    for fold in range(k):
        test = [i for i, g in enumerate(groups) if fold_of[g] == fold]
        train = [i for i, g in enumerate(groups) if fold_of[g] != fold]
        folds.append((train, test))
    return folds


# ---- metrics -----------------------------------------------------------------


def score(truth: Sequence[bool], outcomes: Sequence[str]) -> Dict[str, Optional[float]]:
    n = len(truth)
    committed = [(t, o) for t, o in zip(truth, outcomes) if o != DEFER]
    correct = sum(1 for t, o in committed if (o == ACCEPT) == t)
    accepted = [t for t, o in zip(truth, outcomes) if o == ACCEPT]
    true_positive = sum(accepted)
    positives = sum(truth)
    precision = true_positive / len(accepted) if accepted else None
    recall = true_positive / positives if positives else None
    if precision is not None and recall is not None and precision + recall > 0:
        f1: Optional[float] = 2 * precision * recall / (precision + recall)
    elif precision is not None and recall is not None:
        f1 = 0.0
    else:
        f1 = None
    return {
        "n": n,
        "coverage": len(committed) / n if n else None,
        "accuracy": correct / len(committed) if committed else None,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accept_rate": len(accepted) / n if n else None,
        "defer_rate": (n - len(committed)) / n if n else None,
    }


# ---- methods -----------------------------------------------------------------


@dataclass
class Method:
    name: str
    family: str
    params: Dict[str, Any]
    run: Callable[[InformationTable, InformationTable], List[str]]


def granular_method(space: str, theta: Optional[float], alpha: float, beta: float, max_cliques: int) -> Method:
    label = {"neighborhood": "3WD-N", "clique": "3WD-MC", "quotient": "3WD-Q"}[space]
    params = {"alpha": alpha, "beta": beta}
    if theta is not None:
        params = {"theta": theta, **params}
    name = f"{label}(" + ",".join(f"{v:g}" for v in params.values()) + ")"

    def run(train: InformationTable, test: InformationTable) -> List[str]:
        relation = DistanceRelation(train.attributes, theta) if theta is not None else None
        clf = GranularThreeWayClassifier(space, relation, alpha=alpha, beta=beta, max_cliques=max_cliques)
        clf.fit(train)
        return clf.predict(test.rows)

    return Method(name, "granular", params, run)


def majority_method() -> Method:
    def run(train: InformationTable, test: InformationTable) -> List[str]:
        positive = sum(train.labels) * 2 >= len(train.labels)
        return [ACCEPT if positive else REJECT] * len(test)

    return Method("Majority", "baseline", {}, run)


def encode(train: InformationTable, test: InformationTable):
    """One-hot categorical, multi-hot set-valued, scaled numeric features."""

    columns: List[Tuple[int, str, Any]] = []
    for j, attribute in enumerate(train.attributes):
        if attribute.kind == "numeric":
            columns.append((j, "num", attribute.scale))
        elif attribute.kind == "set":
            values = sorted({v for row in train.rows for v in row[j]}, key=str)
            columns.extend((j, "set", v) for v in values)
        else:
            values = sorted({row[j] for row in train.rows}, key=str)
            columns.extend((j, "cat", v) for v in values)

    def matrix(table: InformationTable) -> List[List[float]]:
        out = []
        for row in table.rows:
            vector = []
            for j, kind, value in columns:
                if kind == "num":
                    vector.append(float(row[j]) / value)
                elif kind == "set":
                    vector.append(1.0 if value in row[j] else 0.0)
                else:
                    vector.append(1.0 if row[j] == value else 0.0)
            out.append(vector)
        return out

    return matrix(train), matrix(test)


def sklearn_methods() -> Tuple[List[Method], Optional[str]]:
    try:
        from sklearn.naive_bayes import GaussianNB
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.svm import SVC
        from sklearn.tree import DecisionTreeClassifier
    except ImportError:
        return [], "scikit-learn is not installed; SVM, decision tree, KNN and naive Bayes baselines were skipped."

    factories = {
        "SVM(linear)": lambda n: SVC(kernel="linear"),
        "DecisionTree(gini)": lambda n: DecisionTreeClassifier(criterion="gini", random_state=0),
        "KNN(5)": lambda n: KNeighborsClassifier(n_neighbors=max(1, min(5, n))),
        "NaiveBayes(Gaussian)": lambda n: GaussianNB(),
    }

    def make(name: str, factory: Callable[[int], Any]) -> Method:
        def run(train: InformationTable, test: InformationTable) -> List[str]:
            labels = [bool(v) for v in train.labels]
            if len(set(labels)) < 2:  # Single-class fold: predict that class.
                return [ACCEPT if labels[0] else REJECT] * len(test)
            x_train, x_test = encode(train, test)
            with warnings.catch_warnings():
                # Constant features in small folds make naive Bayes warn about
                # zero variance; predictions are still defined.
                warnings.simplefilter("ignore", RuntimeWarning)
                model = factory(len(labels)).fit(x_train, labels)
                predicted = model.predict(x_test)
            return [ACCEPT if bool(p) else REJECT for p in predicted]

        return Method(name, "baseline", {}, run)

    return [make(name, factory) for name, factory in factories.items()], None


def build_methods(
    thetas: Sequence[float],
    alphas: Sequence[float],
    betas: Sequence[float],
    *,
    spaces: Sequence[str] = ("neighborhood", "clique"),
    include_quotient: bool = True,
    include_baselines: bool = True,
    max_cliques: int = 200_000,
) -> Tuple[List[Method], List[str]]:
    notes: List[str] = []
    methods: List[Method] = []
    valid = [(a, b) for a, b in itertools.product(alphas, betas) if 0.0 <= b < a <= 1.0]
    if include_quotient:
        methods.extend(granular_method("quotient", None, a, b, max_cliques) for a, b in valid)
    for space in spaces:
        methods.extend(granular_method(space, t, a, b, max_cliques) for t in thetas for a, b in valid)
    if include_baselines:
        methods.append(majority_method())
        extra, note = sklearn_methods()
        methods.extend(extra)
        if note:
            notes.append(note)
    return methods, notes


# ---- evaluation --------------------------------------------------------------


def evaluate(dataset: Dataset, methods: Sequence[Method], n_folds: int) -> List[Dict[str, Any]]:
    folds = grouped_folds(dataset.groups, n_folds)
    truth_all = [bool(v) for v in dataset.table.labels]
    results = []
    for method in methods:
        outcomes: List[Optional[str]] = [None] * len(dataset.table)
        started = time.perf_counter()
        error = None
        try:
            for train_idx, test_idx in folds:
                predicted = method.run(dataset.table.subset(train_idx), dataset.table.subset(test_idx))
                for i, outcome in zip(test_idx, predicted):
                    outcomes[i] = outcome
        except RuntimeError as exc:  # e.g. clique enumeration cap
            error = str(exc)
        row: Dict[str, Any] = {"method": method.name, "family": method.family, "params": method.params}
        if error:
            row["error"] = error
        else:
            row.update(score(truth_all, outcomes))  # type: ignore[arg-type]
        row["seconds"] = round(time.perf_counter() - started, 3)
        results.append(row)
    return results


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_report(dataset: Dataset, results: Sequence[Dict[str, Any]], *, n_folds: int, synthetic: bool, notes: Sequence[str]) -> str:
    labels = Counter(bool(v) for v in dataset.table.labels)
    groups = sorted(set(dataset.groups))
    lines = []
    if synthetic:
        lines += [
            "> **SYNTHETIC DATA.** These records come from the simulated model (`--dry-run`).",
            "> The numbers test the pipeline only and must not be reported as results.",
            "",
        ]
    lines += [
        "# Skill-selection three-way decision evaluation",
        "",
        f"- Runs: {len(dataset.table)} ({labels[True]} acceptable, {labels[False]} not acceptable)",
        f"- Prompts (groups): {len(groups)}",
        f"- Folds: {'leave-one-prompt-out' if n_folds <= 0 else min(n_folds, len(groups))}, grouped by prompt",
        f"- Attributes: {len(dataset.module_attributes)} module states + {len(dataset.request_attributes)} request attributes",
        "",
        "| Method | Coverage | Accuracy | Precision | Recall | F1 | Defer rate | Seconds |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in results:
        if "error" in row:
            lines.append(f"| {row['method']} | error: {row['error']} | | | | | | {row['seconds']} |")
            continue
        lines.append(
            "| " + " | ".join(
                [row["method"]] + [_fmt(row[k]) for k in ("coverage", "accuracy", "precision", "recall", "f1", "defer_rate")] + [_fmt(row["seconds"])]
            ) + " |"
        )
    lines += [
        "",
        "Coverage, accuracy, precision and recall follow the definitions in `research/evaluate.py`;",
        "accuracy and precision are over committed decisions, recall is over all acceptable runs.",
    ]
    for note in notes:
        lines += ["", f"Note: {note}"]
    return "\n".join(lines) + "\n"


def _floats(text: str) -> List[float]:
    return [float(part) for part in text.replace(",", " ").split()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", type=Path, nargs="+", required=True, help="Run-record JSONL file(s).")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK, help="Benchmark prompts, for the set-valued tags attribute.")
    parser.add_argument("--experiment", nargs="*", default=None, help="Only use records from these experiment names.")
    parser.add_argument("--allow-synthetic", action="store_true", help="Include --dry-run records (report is marked synthetic).")
    parser.add_argument("--thetas", default="0.1 0.2 0.3 0.4", help="Distance thresholds for the relation R^theta.")
    parser.add_argument("--alphas", default="0.8 1.0")
    parser.add_argument("--betas", default="0.0 0.2")
    parser.add_argument("--module-weight", type=float, default=1.0)
    parser.add_argument("--request-weight", type=float, default=1.0)
    parser.add_argument("--folds", type=int, default=5, help="Grouped folds; 0 = leave one prompt out.")
    parser.add_argument("--max-cliques", type=int, default=200_000)
    parser.add_argument("--no-baselines", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=None, help="Write report.md and results.json here.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    records = load_records(args.log, allow_synthetic=args.allow_synthetic, experiments=args.experiment)
    if not records:
        print("No records found. Synthetic --dry-run records need --allow-synthetic.", file=sys.stderr)
        return 2
    synthetic = any(str(r.get("tag", "")).startswith("exp=DRYRUN-") for r in records)
    dataset = build_dataset(
        records,
        benchmark_tags=load_benchmark_tags(args.benchmark),
        module_weight=args.module_weight,
        request_weight=args.request_weight,
    )
    methods, notes = build_methods(
        _floats(args.thetas),
        _floats(args.alphas),
        _floats(args.betas),
        include_baselines=not args.no_baselines,
        max_cliques=args.max_cliques,
    )
    results = evaluate(dataset, methods, args.folds)
    report = render_report(dataset, results, n_folds=args.folds, synthetic=synthetic, notes=notes)
    print(report)
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "report.md").write_text(report, encoding="utf-8")
        payload = {"synthetic": synthetic, "runs": len(dataset.table), "folds": args.folds, "results": results, "notes": notes}
        (args.out_dir / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
