from pathlib import Path

from paths import DATA_DIR, GOLDEN_DIR

SUPPORTED = (".pdf", ".txt")


def _find_source(stem: str, data_dir: Path) -> Path | None:
    for suffix in SUPPORTED:
        candidate = data_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def collect_all_files(data_dir: Path = DATA_DIR) -> list[Path]:
    """Wszystkie dokumenty (PDF, TXT) z katalogu data/."""
    return sorted(p for p in Path(data_dir).iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)


def collect_golden_files(data_dir: Path = DATA_DIR, golden_dir: Path = GOLDEN_DIR) -> list[Path]:
    """Tylko dokumenty, które mają golden set (np. goldenset/orzeczenie.json -> orzeczenie.pdf)."""
    files = []
    for golden in sorted(Path(golden_dir).glob("*.json")):
        source = _find_source(golden.stem, Path(data_dir))
        if source:
            files.append(source)
        else:
            print(f"⚠️  Brak dokumentu dla golden setu: {golden.name}")
    return files


def collect_files(scope: str = "golden", limit: int | None = None,
                  data_dir: Path = DATA_DIR, golden_dir: Path = GOLDEN_DIR) -> list[Path]:
    if scope == "all":
        files = collect_all_files(data_dir)
    elif scope == "golden":
        files = collect_golden_files(data_dir, golden_dir)
    else:
        raise ValueError(f"scope musi być 'golden' albo 'all', jest {scope!r}")
    return files[:limit] if limit else files
