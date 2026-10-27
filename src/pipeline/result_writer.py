import json
from pathlib import Path


def result_path(out_dir: Path, source_file) -> Path:
    return Path(out_dir) / f"{Path(source_file).stem}.json"


def build_record(source_file, result, meta: dict) -> dict:
    """Rekord wyniku: dokument + status + metryki + metadane przebiegu (model, wersja promptu, próbkowanie)."""
    record = {
        "file": Path(source_file).name,
        "status": result.status,
        "error": result.error,
        "attempts": result.attempts,
        "metrics": {
            "latency_s": result.latency_s,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost": result.cost,
        },
        "meta": meta,
        "rule_overrides": result.rule_overrides,
        "document": result.document,
    }
    if result.status == "failed":
        record["raw_response"] = result.raw_response
    return record


def save_record(record: dict, out_dir: Path, source_file) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = result_path(out_dir, source_file)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=str)
    return path


def load_record(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
