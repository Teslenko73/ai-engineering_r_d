"""Interfejs wiersza poleceń. Uruchamiany przez `python main.py` z katalogu głównego projektu."""
import argparse
import sys
from pathlib import Path

from env import load_env
from paths import CONFIGS_DIR, EXPERIMENTS_DIR, GOLDEN_DIR, RESULTS_DIR

DEFAULT_EXPERIMENT = "default"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Ekstrakcja danych z orzeczeń do JSON, porównanie modeli i wersji promptów.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- experiment ---
    p = sub.add_parser("experiment", help="uruchom wszystkie kombinacje model x prompt z pliku experiments/*.json, potem porównaj")
    p.add_argument("--file", default=DEFAULT_EXPERIMENT, help="nazwa pliku z experiments/ (bez .json) lub ścieżka")
    p.add_argument("--all-configs", action="store_true",
                   help="bez pliku eksperymentu: WSZYSTKIE konfiguracje z configs/ x wszystkie wersje promptów")
    p.add_argument("--configs", nargs="+", metavar="NAZWA", help="bez pliku eksperymentu: wybrane konfiguracje z configs/")
    p.add_argument("--prompts", nargs="+", metavar="WERSJA", help="wersje promptów (np. v1 v2); nadpisuje listę z pliku")
    p.add_argument("--only-provider", nargs="+", choices=["openrouter", "ollama", "local"],
                   help="uruchom tylko wybranych providerów (np. tylko openrouter)")
    p.add_argument("--scope", choices=["golden", "all"], help="nadpisuje zakres z pliku eksperymentu")
    p.add_argument("--limit", type=int, help="maks. liczba plików (do szybkich testów)")
    p.add_argument("--skip-existing", action="store_true", help="pomiń dokumenty, które mają już wynik (wznawianie)")

    # --- run ---
    p = sub.add_parser("run", help="jeden przebieg: jedna konfiguracja + jedna wersja promptu")
    p.add_argument("--config", required=True, help="nazwa pliku z configs/ (bez .json)")
    p.add_argument("--prompt", default="v2", help="wersja promptu (v1, v2, ...)")
    p.add_argument("--scope", choices=["golden", "all"], default="golden", help="golden = tylko pliki z golden setu, all = wszystkie")
    p.add_argument("--limit", type=int, help="maks. liczba plików")
    p.add_argument("--rules", action="store_true", help="reguły (regex) poprawiają sygnaturę i datę")
    p.add_argument("--skip-existing", action="store_true")

    # --- evaluate / compare / errors ---
    p = sub.add_parser("evaluate", help="szczegółowy raport jednego przebiegu (zapisuje _report.txt)")
    p.add_argument("--run", required=True, help="nazwa katalogu przebiegu w results/ (np. openrouter_t0__v2)")
    p.add_argument("--threshold", type=float, default=0.8, help="próg podobieństwa dla pól tekstowych")
    p.add_argument("--verbose", action="store_true", help="pokaż też poprawne pola")

    p = sub.add_parser("compare", help="tabela porównawcza wszystkich przebiegów (results/comparison.md i .csv)")
    p.add_argument("--threshold", type=float, default=0.8)

    p = sub.add_parser("errors", help="lista błędów przebiegu do rozbioru w raporcie (zapisuje _errors.md)")
    p.add_argument("--run", required=True)
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--threshold", type=float, default=0.8)
    return parser


def _resolve(name: str, folder: Path) -> Path:
    path = Path(name)
    if not path.suffix:
        path = folder / f"{name}.json"
    if not path.exists():
        available = ", ".join(p.stem for p in sorted(folder.glob("*.json"))) or "brak"
        raise SystemExit(f"Nie znaleziono {path}. Dostępne w {folder.name}/: {available}")
    return path


def _results_dir(run: str) -> Path:
    path = RESULTS_DIR / run
    if not path.is_dir():
        available = ", ".join(p.name for p in sorted(RESULTS_DIR.iterdir()) if p.is_dir()) if RESULTS_DIR.exists() else "brak"
        raise SystemExit(f"Nie ma wyników w {path}. Dostępne przebiegi: {available or 'brak'}")
    return path


def build_spec(args) -> dict:
    """Specyfikacja eksperymentu: z flag (--all-configs / --configs) albo z pliku experiments/*.json."""
    from pipeline.experiment import load_experiment
    from prompts import get_prompt, list_versions

    if args.all_configs or args.configs:
        names = args.configs or sorted(p.stem for p in CONFIGS_DIR.glob("*.json"))
        for name in names:
            _resolve(name, CONFIGS_DIR)  # czytelny błąd, gdy konfiguracji nie ma
        spec = {"name": "all" if args.all_configs else "custom", "scope": "golden", "limit": None,
                "configs": names, "prompts": list_versions(), "rules": [False]}
    else:
        spec = load_experiment(_resolve(args.file, EXPERIMENTS_DIR))

    if args.prompts:
        for version in args.prompts:
            get_prompt(version)  # błąd z listą dostępnych wersji, gdy wersji nie ma
        spec["prompts"] = args.prompts
    return spec


def cmd_experiment(args) -> None:
    from evaluation.comparison import compare_all
    from pipeline.experiment import run_experiment

    spec = build_spec(args)
    run_experiment(spec, only_providers=args.only_provider, skip_existing=args.skip_existing,
                   limit=args.limit, scope=args.scope)
    table = compare_all(RESULTS_DIR, GOLDEN_DIR)
    print("\n" + table)
    if not table.startswith("Brak przebiegów"):
        print(f"💾 Tabela zapisana: {RESULTS_DIR / 'comparison.md'} oraz comparison.csv")


def cmd_run(args) -> None:
    from evaluation.comparison import render_markdown
    from evaluation.metrics import compute_run_metrics
    from llm.config import LLMConfig
    from llm.factory import create_llm
    from pipeline.experiment import execute_run
    from pipeline.file_collector import collect_files

    config = LLMConfig.from_file(_resolve(args.config, CONFIGS_DIR))
    files = collect_files(args.scope, args.limit)
    if not files:
        raise SystemExit("Brak plików do przetworzenia (sprawdź data/ i data/goldenset/).")
    print(f"📂 Plików: {len(files)} (zakres: {args.scope})")

    llm = create_llm(config)
    try:
        out_dir, _ = execute_run(llm, config, args.prompt, files, use_rules=args.rules,
                                 skip_existing=args.skip_existing, scope=args.scope)
    finally:
        llm.close()

    metrics = compute_run_metrics(out_dir, GOLDEN_DIR)
    if metrics["n_golden"]:
        print("\n" + render_markdown([metrics]))
    print(f"Szczegóły: python main.py evaluate --run {out_dir.name}")


def cmd_evaluate(args) -> None:
    from evaluation.results_evaluator import ResultsEvaluator

    run_dir = _results_dir(args.run)
    evaluator = ResultsEvaluator(GOLDEN_DIR, run_dir, fuzzy_threshold=args.threshold)
    results = evaluator.evaluate_all()
    evaluator.print_report(results, verbose=args.verbose)
    path = run_dir / "_report.txt"
    evaluator.save_text_report(results, path)
    print(f"\n📄 Raport tekstowy: {path}")


def cmd_compare(args) -> None:
    from evaluation.comparison import compare_all

    table = compare_all(RESULTS_DIR, GOLDEN_DIR, args.threshold)
    print(table)
    if not table.startswith("Brak przebiegów"):
        print(f"💾 Zapisano: {RESULTS_DIR / 'comparison.md'} oraz comparison.csv")


def cmd_errors(args) -> None:
    from evaluation.errors import write_error_report

    path, text = write_error_report(_results_dir(args.run), GOLDEN_DIR, args.top, args.threshold)
    print(text)
    print(f"💾 Zapisano: {path}")


COMMANDS = {"experiment": cmd_experiment, "run": cmd_run, "evaluate": cmd_evaluate,
            "compare": cmd_compare, "errors": cmd_errors}


def main(argv: list[str] | None = None) -> None:
    load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        # `python main.py` bez argumentów = domyślny eksperyment + porównanie
        args = parser.parse_args(["experiment", "--file", DEFAULT_EXPERIMENT])
    try:
        COMMANDS[args.command](args)
    except KeyboardInterrupt:
        print("\nPrzerwano. Wznów komendą z flagą --skip-existing.")
        sys.exit(130)
# """Interfejs wiersza poleceń. Uruchamiany przez `python main.py` z katalogu głównego projektu."""
# import argparse
# import sys
# from pathlib import Path
#
# from env import load_env
# from paths import CONFIGS_DIR, EXPERIMENTS_DIR, GOLDEN_DIR, RESULTS_DIR
#
# DEFAULT_EXPERIMENT = "default"
#
#
# def build_parser() -> argparse.ArgumentParser:
#     parser = argparse.ArgumentParser(
#         prog="python main.py",
#         description="Ekstrakcja danych z orzeczeń do JSON, porównanie modeli i wersji promptów.",
#     )
#     sub = parser.add_subparsers(dest="command")
#
#     # --- experiment ---
#     p = sub.add_parser("experiment", help="uruchom wszystkie kombinacje model x prompt z pliku experiments/*.json, potem porównaj")
#     p.add_argument("--file", default=DEFAULT_EXPERIMENT, help="nazwa pliku z experiments/ (bez .json) lub ścieżka")
#     p.add_argument("--only-provider", nargs="+", choices=["openrouter", "ollama", "local"],
#                    help="uruchom tylko wybranych providerów (np. tylko openrouter)")
#     p.add_argument("--scope", choices=["golden", "all"], help="nadpisuje zakres z pliku eksperymentu")
#     p.add_argument("--limit", type=int, help="maks. liczba plików (do szybkich testów)")
#     p.add_argument("--skip-existing", action="store_true", help="pomiń dokumenty, które mają już wynik (wznawianie)")
#
#     # --- run ---
#     p = sub.add_parser("run", help="jeden przebieg: jedna konfiguracja + jedna wersja promptu")
#     p.add_argument("--config", required=True, help="nazwa pliku z configs/ (bez .json)")
#     p.add_argument("--prompt", default="v2", help="wersja promptu (v1, v2, ...)")
#     p.add_argument("--scope", choices=["golden", "all"], default="golden", help="golden = tylko pliki z golden setu, all = wszystkie")
#     p.add_argument("--limit", type=int, help="maks. liczba plików")
#     p.add_argument("--rules", action="store_true", help="reguły (regex) poprawiają sygnaturę i datę")
#     p.add_argument("--skip-existing", action="store_true")
#
#     # --- evaluate / compare / errors ---
#     p = sub.add_parser("evaluate", help="szczegółowy raport jednego przebiegu (zapisuje _report.txt)")
#     p.add_argument("--run", required=True, help="nazwa katalogu przebiegu w results/ (np. openrouter_t0__v2)")
#     p.add_argument("--threshold", type=float, default=0.8, help="próg podobieństwa dla pól tekstowych")
#     p.add_argument("--verbose", action="store_true", help="pokaż też poprawne pola")
#
#     p = sub.add_parser("compare", help="tabela porównawcza wszystkich przebiegów (results/comparison.md i .csv)")
#     p.add_argument("--threshold", type=float, default=0.8)
#
#     p = sub.add_parser("errors", help="lista błędów przebiegu do rozbioru w raporcie (zapisuje _errors.md)")
#     p.add_argument("--run", required=True)
#     p.add_argument("--top", type=int, default=10)
#     p.add_argument("--threshold", type=float, default=0.8)
#     return parser
#
#
# def _resolve(name: str, folder: Path) -> Path:
#     path = Path(name)
#     if not path.suffix:
#         path = folder / f"{name}.json"
#     if not path.exists():
#         available = ", ".join(p.stem for p in sorted(folder.glob("*.json"))) or "brak"
#         raise SystemExit(f"Nie znaleziono {path}. Dostępne w {folder.name}/: {available}")
#     return path
#
#
# def _results_dir(run: str) -> Path:
#     path = RESULTS_DIR / run
#     if not path.is_dir():
#         available = ", ".join(p.name for p in sorted(RESULTS_DIR.iterdir()) if p.is_dir()) if RESULTS_DIR.exists() else "brak"
#         raise SystemExit(f"Nie ma wyników w {path}. Dostępne przebiegi: {available or 'brak'}")
#     return path
#
#
# def cmd_experiment(args) -> None:
#     from evaluation.comparison import compare_all
#     from pipeline.experiment import load_experiment, run_experiment
#
#     spec = load_experiment(_resolve(args.file, EXPERIMENTS_DIR))
#     run_experiment(spec, only_providers=args.only_provider, skip_existing=args.skip_existing,
#                    limit=args.limit, scope=args.scope)
#     table = compare_all(RESULTS_DIR, GOLDEN_DIR)
#     print("\n" + table)
#     if not table.startswith("Brak przebiegów"):
#         print(f"💾 Tabela zapisana: {RESULTS_DIR / 'comparison.md'} oraz comparison.csv")
#
#
# def cmd_run(args) -> None:
#     from evaluation.comparison import render_markdown
#     from evaluation.metrics import compute_run_metrics
#     from llm.config import LLMConfig
#     from llm.factory import create_llm
#     from pipeline.experiment import execute_run
#     from pipeline.file_collector import collect_files
#
#     config = LLMConfig.from_file(_resolve(args.config, CONFIGS_DIR))
#     files = collect_files(args.scope, args.limit)
#     if not files:
#         raise SystemExit("Brak plików do przetworzenia (sprawdź data/ i data/goldenset/).")
#     print(f"📂 Plików: {len(files)} (zakres: {args.scope})")
#
#     llm = create_llm(config)
#     try:
#         out_dir, _ = execute_run(llm, config, args.prompt, files, use_rules=args.rules,
#                                  skip_existing=args.skip_existing, scope=args.scope)
#     finally:
#         llm.close()
#
#     metrics = compute_run_metrics(out_dir, GOLDEN_DIR)
#     if metrics["n_golden"]:
#         print("\n" + render_markdown([metrics]))
#     print(f"Szczegóły: python main.py evaluate --run {out_dir.name}")
#
#
# def cmd_evaluate(args) -> None:
#     from evaluation.results_evaluator import ResultsEvaluator
#
#     run_dir = _results_dir(args.run)
#     evaluator = ResultsEvaluator(GOLDEN_DIR, run_dir, fuzzy_threshold=args.threshold)
#     results = evaluator.evaluate_all()
#     evaluator.print_report(results, verbose=args.verbose)
#     path = run_dir / "_report.txt"
#     evaluator.save_text_report(results, path)
#     print(f"\n📄 Raport tekstowy: {path}")
#
#
# def cmd_compare(args) -> None:
#     from evaluation.comparison import compare_all
#
#     table = compare_all(RESULTS_DIR, GOLDEN_DIR, args.threshold)
#     print(table)
#     if not table.startswith("Brak przebiegów"):
#         print(f"💾 Zapisano: {RESULTS_DIR / 'comparison.md'} oraz comparison.csv")
#
#
# def cmd_errors(args) -> None:
#     from evaluation.errors import write_error_report
#
#     path, text = write_error_report(_results_dir(args.run), GOLDEN_DIR, args.top, args.threshold)
#     print(text)
#     print(f"💾 Zapisano: {path}")
#
#
# COMMANDS = {"experiment": cmd_experiment, "run": cmd_run, "evaluate": cmd_evaluate,
#             "compare": cmd_compare, "errors": cmd_errors}
#
#
# def main(argv: list[str] | None = None) -> None:
#     load_env()
#     parser = build_parser()
#     args = parser.parse_args(argv)
#     if args.command is None:
#         # `python main.py` bez argumentów = domyślny eksperyment + porównanie
#         args = parser.parse_args(["experiment", "--file", DEFAULT_EXPERIMENT])
#     try:
#         COMMANDS[args.command](args)
#     except KeyboardInterrupt:
#         print("\nPrzerwano. Wznów komendą z flagą --skip-existing.")
#         sys.exit(130)
