"""Zestawienie błędów jednego przebiegu: materiał do rozbioru 3–5 charakterystycznych błędów w raporcie."""
from pathlib import Path

from evaluation.results_evaluator import ResultsEvaluator


def _category(item: dict) -> str:
    if item["status"] == "failed":
        return "odpowiedź odrzucona (failed)"
    if item["expected"] is not None and item["actual"] is None:
        return "pominięte pole (null zamiast wartości)"
    if item["expected"] is None and item["actual"] is not None:
        return "zmyślona wartość (powinno być null)"
    if item["kind"] == "fuzzy":
        return "inne sformułowanie / częściowa zgodność"
    return "błędna wartość"


def collect_errors(run_dir: Path, golden_dir: Path, fuzzy_threshold: float = 0.8) -> list[dict]:
    evaluator = ResultsEvaluator(golden_dir, run_dir, fuzzy_threshold)
    errors = []
    for result in evaluator.evaluate_all():
        if result.missing_result:
            continue
        for f in result.fields:
            if f.passed:
                continue
            item = {"file": result.name, "field": f.name, "kind": f.kind, "expected": f.expected,
                    "actual": f.actual, "score": f.score, "status": result.status}
            item["category"] = _category(item)
            errors.append(item)
    # najpierw pola krytyczne, potem najniższe podobieństwo
    errors.sort(key=lambda e: (e["kind"] != "strict", e["score"]))
    return errors


def render_errors(run_id: str, errors: list[dict], top: int = 10) -> str:
    lines = [f"# Błędy przebiegu `{run_id}`", ""]
    if not errors:
        return "\n".join(lines + ["Brak błędów na golden secie."])

    from collections import Counter
    by_cat = Counter(e["category"] for e in errors)
    lines += ["Liczba błędnych pól: " + str(len(errors)) + ". Podział: "
              + ", ".join(f"{k}: {v}" for k, v in by_cat.most_common()) + ".", "",
              f"## {min(top, len(errors))} najpoważniejszych (pola krytyczne najpierw)", "",
              "| # | Plik | Pole | Kategoria | Oczekiwano (golden) | Otrzymano (model) |", "|---|---|---|---|---|---|"]
    for i, e in enumerate(errors[:top], start=1):
        exp, act = (str(x).replace("|", "\\|").replace("\n", " ")[:90] for x in (e["expected"], e["actual"]))
        lines.append(f"| {i} | {e['file']} | `{e['field']}` | {e['category']} | {exp} | {act} |")
    lines += ["", "Do raportu wybierz 3–5 przykładów i dla każdego opisz: **co zamiast czego** oraz **dlaczego** "
                  "(np. model wziął datę zaskarżonego wyroku, pomylił sygnaturę sprawy powiązanej, sparafrazował nazwę sądu). "
                  "Przyczynę ustalisz, czytając fragment dokumentu w `data/` oraz surową odpowiedź (`raw_response` dla `failed`).", ""]
    return "\n".join(lines)


def write_error_report(run_dir: Path, golden_dir: Path, top: int = 10, fuzzy_threshold: float = 0.8) -> tuple[Path, str]:
    run_dir = Path(run_dir)
    text = render_errors(run_dir.name, collect_errors(run_dir, golden_dir, fuzzy_threshold), top)
    path = run_dir / "_errors.md"
    path.write_text(text, encoding="utf-8")
    return path, text
