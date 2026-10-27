import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

PROVIDERS = ("openrouter", "ollama", "local")


@dataclass
class LLMConfig:
    """Jedna konfiguracja: model + parametry próbkowania + limity. Wczytywana z configs/*.json."""

    name: str                      # nazwa konfiguracji (część nazwy katalogu wyników)
    provider: str                  # "openrouter" (API) | "ollama" (lokalny serwer) | "local" (transformers)
    model_name: str

    # --- próbkowanie ---
    temperature: float = 0.0       # 0.0 = deterministycznie (greedy)
    top_p: float = 0.95            # używane tylko gdy temperature > 0
    top_k: int = 20                # tylko ollama / local
    max_tokens: int = 1024         # limit długości odpowiedzi

    # --- niezawodność ---
    timeout_s: float = 120.0       # timeout zapytania (openrouter, ollama) / max_time generowania (local)
    max_retries: int = 2           # ponowienia SDK przy błędach sieci, 429, 5xx (openrouter)

    # --- opcje modelu ---
    enable_thinking: bool | None = None   # tryb "thinking" (Qwen3); None = nie ustawiaj
    structured_output: bool = True        # wymuszanie schematu (json_schema), jeśli provider to wspiera
    num_ctx: int | None = None            # okno kontekstu (ollama; domyślnie bywa za małe)
    base_url: str | None = None           # ollama: adres serwera
    extra_body: dict = field(default_factory=dict)  # dodatkowe pola żądania (openrouter)

    # --- koszt (używane tylko, gdy API nie zwraca kosztu) ---
    price_in_per_mtok: float | None = None
    price_out_per_mtok: float | None = None

    @classmethod
    def from_file(cls, path) -> "LLMConfig":
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("name", path.stem)

        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"{path.name}: nieznane pola w konfiguracji: {sorted(unknown)}")
        config = cls(**data)
        if config.provider not in PROVIDERS:
            raise ValueError(f"{path.name}: provider musi być jednym z {PROVIDERS}, jest {config.provider!r}")
        return config

    def sampling(self) -> dict:
        """Parametry próbkowania zapisywane przy każdym wyniku."""
        out = {"temperature": self.temperature, "top_p": self.top_p, "max_tokens": self.max_tokens}
        if self.provider != "openrouter":
            out["top_k"] = self.top_k
        if self.enable_thinking is not None:
            out["enable_thinking"] = self.enable_thinking
        return out

    def to_dict(self) -> dict:
        return asdict(self)
