import os
import time

from openai import BadRequestError, NotFoundError, OpenAI

from llm.base import BaseLLM
from llm.config import LLMConfig

BASE_URL = "https://openrouter.ai/api/v1"
MODES = ("json_schema", "json_object", "plain")  # od najsilniejszego wymuszania do braku


class LLMService(BaseLLM):
    """Klient OpenRouter (API zgodne z OpenAI). Klucz: zmienna OPENROUTER_API_KEY (plik .env)."""

    def __init__(self, config: LLMConfig, api_key: str | None = None):
        super().__init__(config)
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("Brak klucza API: ustaw OPENROUTER_API_KEY w pliku .env (zobacz .env.example).")

        self.client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", BASE_URL),
            api_key=api_key,
            timeout=config.timeout_s,        # jawny timeout zapytania
            max_retries=config.max_retries,  # ponowienia SDK: błędy sieci, 429, 5xx
        )
        self.active_mode: str | None = None  # tryb, który zadziałał (zapamiętany po fallbacku)

    def _modes_to_try(self, schema: dict | None) -> list[str]:
        modes = [m for m in MODES if m != "json_schema" or (schema and self.config.structured_output)]
        if self.active_mode in modes:
            modes = modes[modes.index(self.active_mode):]
        return modes

    def _request(self, messages: list, temperature: float, mode: str, schema: dict | None):
        cfg = self.config
        extra_body = {"usage": {"include": True}}  # OpenRouter: zwróć też koszt
        kwargs = dict(model=cfg.model_name, messages=messages, max_tokens=cfg.max_tokens, temperature=temperature)
        if temperature > 0:
            kwargs["top_p"] = cfg.top_p

        if mode == "json_schema":
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "ruling_extraction", "strict": True, "schema": schema},
            }
            extra_body["provider"] = {"require_parameters": True}  # kieruj tylko do providerów z obsługą schematu
        elif mode == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        for key, value in cfg.extra_body.items():
            if isinstance(value, dict) and isinstance(extra_body.get(key), dict):
                extra_body[key] = {**extra_body[key], **value}
            else:
                extra_body[key] = value
        kwargs["extra_body"] = extra_body
        return self.client.chat.completions.create(**kwargs)

    def generate(self, system_prompt, user_prompt, temperature=None, schema=None) -> str:
        temp = self.config.temperature if temperature is None else temperature
        self.last_call = {}
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.perf_counter()
        response, last_error, used_mode = None, None, None
        for mode in self._modes_to_try(schema):
            try:
                response = self._request(messages, temp, mode, schema)
                used_mode = mode
                break
            except (BadRequestError, NotFoundError) as e:  # provider nie wspiera tego trybu
                last_error = e
                print(f"⚠️  Tryb '{mode}' niedostępny dla {self.config.model_name} ({type(e).__name__}); próbuję słabszy.")
        if response is None:
            raise last_error
        if used_mode != self.active_mode:
            self.active_mode = used_mode
            print(f"ℹ️  OpenRouter: tryb odpowiedzi '{used_mode}'")
        latency = time.perf_counter() - start

        usage = response.usage
        extra = getattr(usage, "model_extra", None) or {}
        choice = response.choices[0]
        self._record_call(
            latency,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            cost=extra.get("cost"),
            finish_reason=choice.finish_reason,
            mode=used_mode,
        )
        return choice.message.content or ""
