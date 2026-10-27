import json
from abc import ABC, abstractmethod

from llm.config import LLMConfig


class BaseLLM(ABC):
    """Wspólny interfejs dla wszystkich klientów LLM (OpenRouter, Ollama, lokalny transformers)."""

    def __init__(self, config: LLMConfig):
        self.config = config
        # statystyki ostatniego wywołania: latency_s, prompt_tokens, completion_tokens, cost, finish_reason
        self.last_call: dict = {}

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        schema: dict | None = None,
    ) -> str:
        """Zwraca surowy tekst odpowiedzi modelu.
        `temperature` nadpisuje wartość z konfiguracji, `schema` (JSON Schema) włącza structured output."""

    def close(self) -> None:
        """Zwalnia zasoby (np. pamięć modelu). Domyślnie nic nie robi."""

    def _record_call(
        self,
        latency_s: float,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost: float | None = None,
        finish_reason: str | None = None,
        **extra,
    ) -> None:
        cfg = self.config
        if cost is None:
            if cfg.provider in ("local", "ollama"):
                cost = 0.0  # lokalnie brak opłat za API (prąd pomijamy)
            elif (
                cfg.price_in_per_mtok is not None
                and cfg.price_out_per_mtok is not None
                and prompt_tokens is not None
                and completion_tokens is not None
            ):
                cost = (prompt_tokens * cfg.price_in_per_mtok + completion_tokens * cfg.price_out_per_mtok) / 1e6
        self.last_call = {
            "latency_s": round(latency_s, 3),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
            "finish_reason": finish_reason,
            **extra,
        }


def parse_json_object(text: str) -> dict:
    """Wycina obiekt JSON z tekstu (od pierwszej '{' do ostatniej '}') i parsuje go."""
    if not text:
        raise ValueError("Pusta odpowiedź modelu.")
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("Odpowiedź nie zawiera obiektu JSON (brak klamer).")
    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        raise ValueError(f"Niepoprawny JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("JSON nie jest obiektem.")
    return data
