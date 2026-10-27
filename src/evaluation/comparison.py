"""Tabela porównawcza: model x wersja promptu x próbkowanie, ze wszystkimi metrykami."""
import csv
from pathlib import Path

from evaluation.metrics import compute_run_metrics


def collect_run_dirs(results_dir: Path) -> list[Path]:
    results_dir = Path(results_dir)
    if not results_dir.exists():
        return []
    return [d for d in sorted(results_dir.iterdir()) if d.is_dir() and (d / "_run_meta.json").exists()]


def _pct(x, digits=1):
    return "n/a" if x is None else f"{x:.{digits}f}%"


def _sec(x):
    return "n/a" if x is None else f"{x:.2f}"


def _sampling(row) -> str:
    s = row["sampling"]
    t = s.get("temperature")
    if t is None:
        return "n/a"
    text = "T=0 (greedy)" if t == 0 else f"T={t}, top_p={s.get('top_p')}"
    if s.get("enable_thinking"):
        text += ", thinking"
    return text


def _cost(row) -> str:
    cost = row["cost_per_1000_docs"]
    if cost is None:
        return "n/a"
    if row["provider"] in ("local", "ollama"):
        return "$0 (lokalnie)"
    return f"${cost:.2f}"


def build_rows(results_dir: Path, golden_dir: Path, fuzzy_threshold: float = 0.8) -> list[dict]:
    rows = [compute_run_metrics(d, golden_dir, fuzzy_threshold) for d in collect_run_dirs(results_dir)]
    rows.sort(key=lambda r: (r["provider"] or "", r["model"] or "", r["prompt_version"] or "", r["sampling"].get("temperature", 0)))
    return rows


def render_markdown(rows: list[dict]) -> str:
    if not rows:
        return "Brak przebiegów w katalogu wyników. Uruchom: `python main.py`.\n"

    lines = ["## Porównanie przebiegów", "",
             "| Model | Provider | Prompt | Próbkowanie | Reguły | Dok. | Poprawne | Bez poprawki | Pola krytyczne OK | Śr. wynik JSON | Latency p50 [s] | Latency p95 [s] | Koszt / 1000 dok. |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['model']} | {r['provider']} | {r['prompt_version']} | {_sampling(r)} | {'tak' if r['rules'] else 'nie'} "
            f"| {r['n_docs']} | {_pct(r['valid_pct'])} | {_pct(r['first_try_valid_pct'])} | {_pct(r['strict_all_ok_pct'])} "
            f"| {_pct(r['mean_overall_pct'])} | {_sec(r['latency_p50_s'])} | {_sec(r['latency_p95_s'])} | {_cost(r)} |"
        )

    fields = list(dict.fromkeys(f for r in rows for f in r["per_field_pct"]))
    lines += ["", "## Dokładność per pole (golden set)", "",
              "Pola krytyczne (`strict`): dokładne dopasowanie po normalizacji. Pozostałe (`fuzzy`): podobieństwo tekstu ≥ próg.", "",
              "| Przebieg | " + " | ".join(fields) + " |",
              "|---|" + "---|" * len(fields)]
    for r in rows:
        label = f"{r['model']} / {r['prompt_version']} / {_sampling(r)}" + (" / reguły" if r["rules"] else "")
        cells = [_pct(r["per_field_pct"].get(f), 0) for f in fields]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += ["", "Objaśnienia: **Poprawne** = odpowiedź zwalidowana po schemacie (po co najwyżej jednej próbie poprawy), "
                  "reszta ma status `failed`; **Bez poprawki** = zwalidowana od razu; **Pola krytyczne OK** = odsetek dokumentów, "
                  "w których wszystkie pola krytyczne są poprawne; **Koszt / 1000 dok.** = średni koszt dokumentu x 1000 "
                  "(modele lokalne: bez kosztu API).", ""]
    return "\n".join(lines)


def write_csv(rows: list[dict], path: Path) -> None:
    columns = ["run_id", "model", "provider", "prompt_version", "rules", "n_docs", "n_golden", "valid_pct",
               "first_try_valid_pct", "failed", "strict_all_ok_pct", "mean_overall_pct", "latency_p50_s",
               "latency_p95_s", "latency_mean_s", "avg_prompt_tokens", "avg_completion_tokens",
               "cost_per_1000_docs", "wall_time_s"]
    fields = list(dict.fromkeys(f for r in rows for f in r["per_field_pct"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns + ["temperature", "top_p"] + [f"acc_{x}" for x in fields])
        for r in rows:
            s = r["sampling"]
            writer.writerow([r.get(c) for c in columns] + [s.get("temperature"), s.get("top_p")]
                            + [r["per_field_pct"].get(x) for x in fields])


def compare_all(results_dir: Path, golden_dir: Path, fuzzy_threshold: float = 0.8, write: bool = True) -> str:
    rows = build_rows(results_dir, golden_dir, fuzzy_threshold)
    text = render_markdown(rows)
    if write and rows:
        Path(results_dir).mkdir(parents=True, exist_ok=True)
        (Path(results_dir) / "comparison.md").write_text(text, encoding="utf-8")
        write_csv(rows, Path(results_dir) / "comparison.csv")
    return text
