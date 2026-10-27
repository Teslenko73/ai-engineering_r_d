"""Metryki jednego przebiegu: dokładność per pole, % poprawnych odpowiedzi, latency p50/p95, koszt na 1000 dokumentów."""
import json
import math
from pathlib import Path

from evaluation.results_evaluator import ResultsEvaluator


def percentile(values: list[float], q: float) -> float | None:
    """Percentyl z interpolacją liniową (q w zakresie 0–100)."""
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * q / 100
    lower, upper = math.floor(k), math.ceil(k)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (k - lower)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def load_records(run_dir: Path) -> list[dict]:
    """Wszystkie rekordy wyników w katalogu przebiegu (pomija pliki zaczynające się od '_')."""
    records = []
    for path in sorted(Path(run_dir).glob("*.json")):
        if path.name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "status" in data:
            records.append(data)
    return records


def load_run_meta(run_dir: Path) -> dict:
    path = Path(run_dir) / "_run_meta.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_run_metrics(run_dir: Path, golden_dir: Path, fuzzy_threshold: float = 0.8) -> dict:
    run_dir = Path(run_dir)
    meta = load_run_meta(run_dir)
    records = load_records(run_dir)

    n = len(records)
    ok = [r for r in records if r["status"] == "ok"]
    first_try = [r for r in ok if r.get("attempts") == 1]

    latencies = [r["metrics"]["latency_s"] for r in records if r.get("metrics", {}).get("latency_s") is not None]
    costs = [r["metrics"]["cost"] for r in records if r.get("metrics", {}).get("cost") is not None]
    prompt_tokens = [r["metrics"]["prompt_tokens"] for r in records if r.get("metrics", {}).get("prompt_tokens") is not None]
    completion_tokens = [r["metrics"]["completion_tokens"] for r in records if r.get("metrics", {}).get("completion_tokens") is not None]

    # dokładność: tylko dokumenty, które mają golden set
    evaluator = ResultsEvaluator(golden_dir, run_dir, fuzzy_threshold)
    results = evaluator.evaluate_all()
    summary = evaluator.summarize(results)
    n_golden = summary["files_total"] - summary["files_missing_result"]

    mean_cost = _mean(costs)
    return {
        "run_id": run_dir.name,
        "model": meta.get("model"),
        "provider": meta.get("provider"),
        "config_name": meta.get("config_name"),
        "prompt_version": meta.get("prompt_version"),
        "sampling": meta.get("sampling", {}),
        "rules": meta.get("rules", False),
        "n_docs": n,
        "n_golden": n_golden,
        "valid_pct": 100 * len(ok) / n if n else None,                 # odpowiedź zwalidowana (po ≤1 poprawce)
        "first_try_valid_pct": 100 * len(first_try) / n if n else None,  # zwalidowana bez poprawki
        "failed": n - len(ok),
        "strict_all_ok_pct": 100 * summary["strict_all_ok"] / n_golden if n_golden else None,
        "mean_overall_pct": 100 * summary["mean_overall_score"] if n_golden else None,
        "per_field_pct": {name: 100 * d["pass_rate"] for name, d in summary["per_field"].items()},
        "per_field_kind": {name: d["kind"] for name, d in summary["per_field"].items()},
        "latency_p50_s": percentile(latencies, 50),
        "latency_p95_s": percentile(latencies, 95),
        "latency_mean_s": _mean(latencies),
        "avg_prompt_tokens": _mean(prompt_tokens),
        "avg_completion_tokens": _mean(completion_tokens),
        "cost_per_1000_docs": mean_cost * 1000 if mean_cost is not None else None,
        "wall_time_s": meta.get("wall_time_s"),
    }
