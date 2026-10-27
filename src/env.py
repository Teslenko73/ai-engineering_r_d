import os
from pathlib import Path

from paths import ROOT_DIR


def load_env(path: Path | None = None) -> None:
    """Wczytuje plik .env (KEY=VALUE) do zmiennych środowiskowych.
    Nie nadpisuje zmiennych, które już są ustawione w systemie."""
    path = Path(path) if path else ROOT_DIR / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)
