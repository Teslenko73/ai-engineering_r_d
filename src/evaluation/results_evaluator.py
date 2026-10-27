import io
import json
import re
import unicodedata
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

try:  # opcjonalnie: lepsze porównywanie, niewrażliwe na kolejność słów
    from rapidfuzz import fuzz

    def similarity(a: str, b: str) -> float:
        return fuzz.token_sort_ratio(a, b) / 100
except ImportError:
    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


# ---------- normalizacja ----------

def norm_text(value) -> str:
    """lowercase, bez polskich ogonków, bez interpunkcji, pojedyncze spacje."""
    s = unicodedata.normalize("NFKC", str(value)).lower().replace("ł", "l")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_id(value) -> str:
    """Sygnatury: bez spacji i kropek, wielkie litery (np. 'II Kp 127/15' == 'II KP 127/15')."""
    return re.sub(r"[\s.]", "", str(value)).upper()


def norm_date(value) -> str:
    return str(value).strip()


# ---------- konfiguracja: które pola są krytyczne ----------

# Pola, w których nie wolno się pomylić: dokładne dopasowanie po normalizacji.
STRICT_FIELDS = {
    "document_type": norm_text,
    "language": norm_text,
    "decision_date": norm_date,
    "docket_number": norm_id,
}
# Pozostałe pola (court, division, presiding_judge, applicant, subject_matter itd.)
# są porównywane "rozmyślnie" (podobieństwo tekstu 0-1).


# ---------- struktury wyników ----------

@dataclass
class FieldResult:
    name: str
    kind: str  # "strict" | "fuzzy"
    expected: object
    actual: object
    score: float  # 1.0/0.0 dla strict, 0-1 dla fuzzy
    passed: bool


@dataclass
class FileResult:
    name: str
    fields: list = field(default_factory=list)
    missing_result: bool = False
    status: str = "ok"  # "failed" = model nie zwrócił poprawnej odpowiedzi (wszystkie pola liczone jako błędy)

    @property
    def strict_fields(self):
        return [f for f in self.fields if f.kind == "strict"]

    @property
    def strict_ok(self) -> bool:
        return not self.missing_result and all(f.passed for f in self.strict_fields)

    @property
    def overall_score(self) -> float:
        """Test 2: średni wynik po wszystkich polach (cały JSON)."""
        if self.missing_result or not self.fields:
            return 0.0
        return sum(f.score for f in self.fields) / len(self.fields)


# ---------- ewaluator ----------

class ResultsEvaluator:
    def __init__(self, golden_dir: Path, results_dir: Path, fuzzy_threshold: float = 0.8):
        self.golden_dir = Path(golden_dir)
        self.results_dir = Path(results_dir)
        self.fuzzy_threshold = fuzzy_threshold

    # --- wczytywanie ---
    @staticmethod
    def _load_document(path: Path) -> tuple[dict, str]:
        """Zwraca (dokument, status). Wynik przebiegu ma strukturę {"document": ..., "status": ...};
        golden set to {"document": ...}."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}, "failed"
        status = data.get("status", "ok")
        document = data.get("document", data)
        return (document or {}), status

    # --- porównanie pojedynczego pola ---
    def _compare_field(self, name: str, expected, actual) -> FieldResult:
        is_strict = name in STRICT_FIELDS

        if expected is None and actual is None:
            return FieldResult(name, "strict" if is_strict else "fuzzy", expected, actual, 1.0, True)
        if expected is None or actual is None:
            return FieldResult(name, "strict" if is_strict else "fuzzy", expected, actual, 0.0, False)

        if is_strict:
            norm = STRICT_FIELDS[name]
            ok = norm(expected) == norm(actual)
            return FieldResult(name, "strict", expected, actual, 1.0 if ok else 0.0, ok)

        score = similarity(norm_text(expected), norm_text(actual))
        return FieldResult(name, "fuzzy", expected, actual, score, score >= self.fuzzy_threshold)

    # --- jeden plik ---
    def evaluate_file(self, golden_path: Path) -> FileResult:
        result_path = self.results_dir / golden_path.name
        if not result_path.exists():
            return FileResult(name=golden_path.stem, missing_result=True)

        gold, _ = self._load_document(golden_path)
        pred, status = self._load_document(result_path)
        failed = status == "failed"

        # pola z golden setu + pola krytyczne (nawet jeśli golden ich nie ma)
        names = list(dict.fromkeys([*gold.keys(), *STRICT_FIELDS.keys()]))
        fields = []
        for n in names:
            fr = self._compare_field(n, gold.get(n), pred.get(n))
            if failed:  # odpowiedź odrzucona: żadne pole nie jest zaliczone (także null == null)
                fr = FieldResult(fr.name, fr.kind, fr.expected, fr.actual, 0.0, False)
            fields.append(fr)
        return FileResult(name=golden_path.stem, fields=fields, status=status)

    # --- wszystkie pliki ---
    def evaluate_all(self) -> list:
        return [self.evaluate_file(p) for p in sorted(self.golden_dir.glob("*.json"))]

    # --- podsumowanie ---
    @staticmethod
    def summarize(results: list) -> dict:
        evaluated = [r for r in results if not r.missing_result]
        per_field: dict = {}
        for r in evaluated:
            for f in r.fields:
                d = per_field.setdefault(f.name, {"kind": f.kind, "n": 0, "passed": 0, "score_sum": 0.0})
                d["n"] += 1
                d["passed"] += int(f.passed)
                d["score_sum"] += f.score

        return {
            "files_total": len(results),
            "files_missing_result": len(results) - len(evaluated),
            "strict_all_ok": sum(r.strict_ok for r in evaluated),
            "mean_overall_score": (sum(r.overall_score for r in evaluated) / len(evaluated)) if evaluated else 0.0,
            "per_field": {
                n: {
                    "kind": d["kind"],
                    "pass_rate": d["passed"] / d["n"],
                    "mean_score": d["score_sum"] / d["n"],
                }
                for n, d in per_field.items()
            },
        }

    # --- raport ---
    def print_report(self, results: list, verbose: bool = False):
        print("\n" + "=" * 70)
        print("TEST 1: pola krytyczne (dokładne)  |  TEST 2: cały JSON (średni wynik)")
        print("=" * 70)

        for r in results:
            if r.missing_result:
                print(f"\n❓ {r.name}: brak pliku z wynikiem w {self.results_dir}")
                continue

            strict = r.strict_fields
            ok_count = sum(f.passed for f in strict)
            icon = "✅" if r.strict_ok else "❌"
            failed_note = " [FAILED: niepoprawna odpowiedź modelu]" if r.status == "failed" else ""
            print(f"\n{icon} {r.name}: krytyczne {ok_count}/{len(strict)} | cały JSON {r.overall_score:.0%}{failed_note}")

            for f in r.fields:
                if f.passed and not verbose:
                    continue
                mark = "✓" if f.passed else "✗"
                extra = "" if f.kind == "strict" else f" (podobieństwo {f.score:.0%})"
                print(f"   {mark} {f.name}{extra}")
                if not f.passed or verbose:
                    print(f"       oczekiwano: {f.expected!r}")
                    print(f"       otrzymano:  {f.actual!r}")

        s = self.summarize(results)
        print("\n" + "-" * 70)
        print("PODSUMOWANIE")
        print("-" * 70)
        evaluated = s["files_total"] - s["files_missing_result"]
        print(f"Pliki: {evaluated}/{s['files_total']} ocenionych")
        print(f"Test 1 – wszystkie pola krytyczne poprawne: {s['strict_all_ok']}/{evaluated}")
        print(f"Test 2 – średni wynik całego JSON: {s['mean_overall_score']:.1%}\n")
        print(f"{'pole':<18}{'typ':<8}{'trafność':>10}{'śr. wynik':>12}")
        for name, d in s["per_field"].items():
            print(f"{name:<18}{d['kind']:<8}{d['pass_rate']:>10.0%}{d['mean_score']:>12.2f}")

    def save_text_report(self, results: list, path: Path):
        """Pełny raport (wszystkie pola, nie tylko błędy) zapisany do pliku .txt."""
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.print_report(results, verbose=True)

        header = (
            f"Raport ewaluacji – {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"Golden set: {self.golden_dir}\n"
            f"Wyniki:     {self.results_dir}\n"
            f"Próg podobieństwa: {self.fuzzy_threshold}\n"
        )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header + buffer.getvalue(), encoding="utf-8")

    def save_report(self, results: list, path: Path):
        report = {
            "summary": self.summarize(results),
            "files": [asdict(r) for r in results],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
