import time
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from extraction.json_schema import build_response_schema
from extraction.quality import content_problem
from extraction.rules import extract_rule_fields
from extraction.schemas import UnifiedRulingSchema
from llm.base import parse_json_object
from prompts import PromptVersion

MAX_ATTEMPTS = 2  # oryginalne zapytanie + JEDNA próba poprawy; potem status "failed"


@dataclass
class ExtractionResult:
    status: str                       # "ok" | "failed"
    document: dict | None = None      # zwalidowany wynik (None dla failed)
    error: str | None = None
    attempts: int = 0
    latency_s: float | None = None    # suma po próbach
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost: float | None = None
    rule_overrides: list = field(default_factory=list)
    raw_response: str | None = None   # ostatnia odpowiedź modelu (zapisywana tylko dla failed)


def _correction_prompt(user_prompt: str, raw: str, error: str) -> str:
    return (
        f"{user_prompt}\n\n---\n"
        "Twoja poprzednia odpowiedź była niepoprawna.\n"
        f"Poprzednia odpowiedź:\n{raw[:3000]}\n\n"
        f"Błąd walidacji: {error}\n\n"
        "Popraw odpowiedź: zwróć wyłącznie jeden poprawny obiekt JSON zgodny ze strukturą, "
        "bez komentarzy i bez markdownu."
    )


class RulingExtractor:
    def __init__(
        self,
        llm,
        prompt: PromptVersion,
        max_chars: int = 8000,
        use_rules: bool = False,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self.llm = llm
        self.prompt = prompt
        self.max_chars = max_chars  # dane z nagłówka są na początku orzeczenia
        self.use_rules = use_rules  # reguły (regex) poprawiają sygnaturę i datę
        self.max_attempts = max_attempts
        self.schema = build_response_schema() if llm.config.structured_output else None

    # ---------- odczyt tekstu ----------

    def _read_text(self, file_path) -> str:
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(path)
            parts, total = [], 0
            for page in reader.pages:
                page_text = page.extract_text() or ""
                parts.append(page_text)
                total += len(page_text)
                if total >= self.max_chars:  # reszta i tak zostanie obcięta
                    break
            text = "\n".join(parts)
        else:
            text = path.read_text(encoding="utf-8")
        return text.strip()

    # ---------- główna logika ----------

    def extract_from_file(self, file_path) -> ExtractionResult:
        """Nigdy nie rzuca wyjątku z powodu błędu modelu: zwraca status "failed"."""
        try:
            text = self._read_text(file_path)
        except Exception as e:
            return ExtractionResult(status="failed", error=f"Nie można odczytać pliku: {e}")
        if not text:
            return ExtractionResult(status="failed", error="Brak tekstu w pliku (skan wymagający OCR?)")

        text = text[: self.max_chars]
        user_prompt = self.prompt.render(text)

        totals = {"latency_s": None, "prompt_tokens": None, "completion_tokens": None, "cost": None}
        raw, error, document = None, None, None
        attempts = 0

        for attempt in range(1, self.max_attempts + 1):
            attempts = attempt
            prompt_to_send = user_prompt if (attempt == 1 or raw is None) else _correction_prompt(user_prompt, raw, error)

            self.llm.last_call = {}
            wall_start = time.perf_counter()
            try:
                raw = self.llm.generate(self.prompt.system, prompt_to_send, schema=self.schema)
                call_error = None
            except Exception as e:  # timeout, błąd sieci, błąd API
                raw, call_error = None, f"Błąd wywołania modelu: {type(e).__name__}: {e}"
            wall = time.perf_counter() - wall_start

            self._accumulate(totals, self.llm.last_call, wall)

            if call_error:
                error = call_error
                print(f"           ⚠️  próba {attempt}/{self.max_attempts}: {call_error[:200]}")
                continue

            try:
                data = parse_json_object(raw)
                validated = UnifiedRulingSchema(**data)
                candidate = validated.model_dump(mode="json")["document"]
                problem = content_problem(candidate)  # schemat sprawdza tylko format, tu sprawdzamy treść
                if problem:
                    raise ValueError(problem)
                document = candidate
                error = None
                break
            except Exception as e:
                error = str(e)[:500]
                print(f"           ⚠️  próba {attempt}/{self.max_attempts}: odpowiedź niepoprawna ({error[:120]!r})")

        if document is None:
            return ExtractionResult(
                status="failed", error=error, attempts=attempts, raw_response=raw, **totals
            )

        overrides = self._apply_rules(document, text) if self.use_rules else []
        return ExtractionResult(
            status="ok", document=document, attempts=attempts, rule_overrides=overrides, **totals
        )

    # ---------- pomocnicze ----------

    @staticmethod
    def _accumulate(totals: dict, call: dict, wall: float) -> None:
        latency = call.get("latency_s")
        latency = wall if latency is None else latency
        totals["latency_s"] = round((totals["latency_s"] or 0) + latency, 3)
        for key in ("prompt_tokens", "completion_tokens", "cost"):
            value = call.get(key)
            if value is not None:
                totals[key] = (totals[key] or 0) + value

    @staticmethod
    def _apply_rules(document: dict, text: str) -> list:
        """Reguły nadpisują sygnaturę i datę, gdy są pewne. Zwraca listę zmian (do analizy)."""
        overrides = []
        for name, rule_value in extract_rule_fields(text).items():
            if document.get(name) != rule_value:
                overrides.append({"field": name, "llm": document.get(name), "rule": rule_value})
                document[name] = rule_value
        return overrides
