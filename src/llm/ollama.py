import json
import os
import time
import urllib.error
import urllib.request

from llm.base import BaseLLM
from llm.config import LLMConfig

DEFAULT_URL = "http://localhost:11434"


class LLMService(BaseLLM):
    """Lokalny model przez Ollamę (https://ollama.com). Bez dodatkowych zależności (tylko stdlib)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        url = config.base_url or os.getenv("OLLAMA_HOST") or DEFAULT_URL
        if not url.startswith("http"):
            url = "http://" + url
        self.base_url = url.rstrip("/")
        self._check_server()

    def _post_or_get(self, path: str, payload: dict | None = None, timeout: float = 10.0) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path, data=data, headers={"Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Ollama HTTP {e.code}: {body}") from e

    def _check_server(self) -> None:
        try:
            tags = self._post_or_get("/api/tags", timeout=5)
        except Exception as e:
            raise RuntimeError(
                f"Ollama nie odpowiada pod {self.base_url} ({e}). Uruchom serwer: `ollama serve`."
            ) from e
        names = {m.get("name", "") for m in tags.get("models", [])}
        wanted = self.config.model_name
        if wanted not in names and f"{wanted}:latest" not in names:
            raise RuntimeError(f"Model '{wanted}' nie jest pobrany w Ollamie. Uruchom: `ollama pull {wanted}`.")

    def generate(self, system_prompt, user_prompt, temperature=None, schema=None) -> str:
        cfg = self.config
        temp = cfg.temperature if temperature is None else temperature
        self.last_call = {}

        options = {"temperature": temp, "num_predict": cfg.max_tokens}
        if temp > 0:
            options.update(top_p=cfg.top_p, top_k=cfg.top_k)
        if cfg.num_ctx:
            options["num_ctx"] = cfg.num_ctx

        payload = {
            "model": cfg.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": schema if (schema and cfg.structured_output) else "json",  # structured output w Ollamie
            "options": options,
        }
        if cfg.enable_thinking is not None:
            payload["think"] = cfg.enable_thinking

        start = time.perf_counter()
        data = self._post_or_get("/api/chat", payload, timeout=cfg.timeout_s)
        latency = time.perf_counter() - start

        self._record_call(
            latency,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            finish_reason=data.get("done_reason"),
        )
        return (data.get("message") or {}).get("content", "") or ""
