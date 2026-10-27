import json
from pathlib import Path

from extraction.extractor import RulingExtractor
from llm.config import LLMConfig
from llm.factory import create_llm
from paths import CONFIGS_DIR, GOLDEN_DIR, RESULTS_DIR
from pipeline.batch_runner import BatchRunner
from pipeline.file_collector import collect_files
from prompts import get_prompt


def run_id_for(config_name: str, prompt_version: str, use_rules: bool = False) -> str:
    return f"{config_name}__{prompt_version}" + ("__rules" if use_rules else "")


def execute_run(llm, config: LLMConfig, prompt_version: str, files: list[Path], *,
                results_root: Path = RESULTS_DIR, use_rules: bool = False, skip_existing: bool = False,
                scope: str = "golden", run_id: str | None = None) -> tuple[Path, dict]:
    """Jeden przebieg: (klient LLM, wersja promptu, reguły) na liście plików. Zwraca (katalog wyników, podsumowanie)."""
    prompt = get_prompt(prompt_version)
    run_id = run_id or run_id_for(config.name, prompt_version, use_rules)
    out_dir = Path(results_root) / run_id

    meta_base = {
        "run_id": run_id,
        "config_name": config.name,
        "provider": config.provider,
        "model": config.model_name,
        "prompt_version": prompt_version,
        "sampling": config.sampling(),
        "structured_output": config.structured_output,
        "rules": use_rules,
        "scope": scope,
    }
    print(f"\n▶️  Przebieg {run_id}")
    print(f"   model: {config.model_name} ({config.provider}) | prompt: {prompt_version} | "
          f"próbkowanie: {config.sampling()} | reguły: {use_rules}")
    print(f"   wyniki: {out_dir}")

    extractor = RulingExtractor(llm, prompt, use_rules=use_rules)
    runner = BatchRunner(extractor, out_dir, meta_base, skip_existing=skip_existing)
    summary = runner.run(files)
    runner.print_summary(summary)
    return out_dir, summary


def load_experiment(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    spec.setdefault("name", Path(path).stem)
    spec.setdefault("scope", "golden")
    spec.setdefault("limit", None)
    spec.setdefault("rules", [False])
    for key in ("configs", "prompts"):
        if not spec.get(key):
            raise ValueError(f"{Path(path).name}: brak listy '{key}'")
    if isinstance(spec["rules"], bool):
        spec["rules"] = [spec["rules"]]
    return spec


def run_experiment(spec: dict, *, results_root: Path = RESULTS_DIR, configs_dir: Path = CONFIGS_DIR,
                   only_providers: list[str] | None = None, skip_existing: bool = False,
                   limit: int | None = None, scope: str | None = None,
                   data_dir: Path | None = None, golden_dir: Path = GOLDEN_DIR) -> list[Path]:
    """Uruchamia wszystkie kombinacje config x prompt x reguły. Konfiguracje, których nie da się
    uruchomić (brak klucza API, Ollama wyłączona), są pomijane z ostrzeżeniem."""
    scope = scope or spec["scope"]
    limit = limit if limit is not None else spec["limit"]
    kwargs = {"data_dir": data_dir} if data_dir else {}
    files = collect_files(scope, limit, golden_dir=golden_dir, **kwargs)
    print(f"🧪 Eksperyment '{spec['name']}': {len(files)} plików, zakres: {scope}")
    if not files:
        raise SystemExit("Brak plików do przetworzenia (sprawdź data/ i data/goldenset/).")

    out_dirs = []
    for config_name in spec["configs"]:
        config = LLMConfig.from_file(Path(configs_dir) / f"{config_name}.json")
        if only_providers and config.provider not in only_providers:
            print(f"⏭️  Pomijam {config_name} (provider {config.provider} poza --only-provider)")
            continue

        try:
            llm = create_llm(config)
        except Exception as e:
            print(f"⚠️  Pomijam konfigurację {config_name}: {e}")
            continue

        try:
            for prompt_version in spec["prompts"]:
                for use_rules in spec["rules"]:
                    out_dir, _ = execute_run(
                        llm, config, prompt_version, files, results_root=results_root,
                        use_rules=use_rules, skip_existing=skip_existing, scope=scope,
                    )
                    out_dirs.append(out_dir)
        finally:
            llm.close()
    return out_dirs
