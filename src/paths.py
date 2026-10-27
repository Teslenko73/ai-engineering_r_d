from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
GOLDEN_DIR = DATA_DIR / "goldenset"
RESULTS_DIR = ROOT_DIR / "results"
CONFIGS_DIR = ROOT_DIR / "configs"
EXPERIMENTS_DIR = ROOT_DIR / "experiments"
