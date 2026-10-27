"""Punkt wejścia projektu: `python main.py` (domyślny eksperyment) lub `python main.py <komenda> --help`."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))  # moduły projektu
sys.path.insert(0, str(ROOT))          # pakiet prompts/

from cli import main  # noqa: E402

if __name__ == "__main__":
    main()
