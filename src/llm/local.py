import gc
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from llm.base import BaseLLM
from llm.config import LLMConfig


class LLMService(BaseLLM):
    """Lokalny model przez biblioteki transformers (domyślnie Qwen3). Nie wspiera wymuszania schematu:
    format JSON wymusza prompt, a poprawność sprawdza walidacja Pydantic."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            config.model_name,
            torch_dtype="auto",
            device_map="auto",
        )
        # id tokenu </think> pobieramy z tokenizera zamiast wpisywać liczbę na sztywno
        think_id = self.tokenizer.convert_tokens_to_ids("</think>")
        unk = self.tokenizer.unk_token_id
        self.think_end_id = None if think_id is None or think_id == unk else think_id
        print(f"🧠 Model: {config.model_name} | urządzenie: {self.model.device}")

    def _answer_from_ids(self, output_ids: list) -> tuple[str, bool]:
        """Zwraca (odpowiedź bez części 'thinking', czy odpowiedź jest kompletna)."""
        index = 0
        if self.think_end_id is not None and self.think_end_id in output_ids:
            index = len(output_ids) - output_ids[::-1].index(self.think_end_id)
        elif self.config.enable_thinking:
            return "", False  # model nie skończył myśleć przed limitem tokenów/czasu
        return self.tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip(), True

    def generate(self, system_prompt, user_prompt, temperature=None, schema=None) -> str:
        cfg = self.config
        temp = cfg.temperature if temperature is None else temperature
        self.last_call = {}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=bool(cfg.enable_thinking),
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

        gen_kwargs = {"max_new_tokens": cfg.max_tokens, "max_time": cfg.timeout_s}
        if temp > 0:
            gen_kwargs.update(do_sample=True, temperature=temp, top_p=cfg.top_p, top_k=cfg.top_k)
        else:
            gen_kwargs.update(do_sample=False)

        start = time.perf_counter()
        with torch.inference_mode():
            generated = self.model.generate(**inputs, **gen_kwargs)
        latency = time.perf_counter() - start

        prompt_len = inputs.input_ids.shape[1]
        output_ids = generated[0][prompt_len:].tolist()
        answer, complete = self._answer_from_ids(output_ids)

        hit_limit = len(output_ids) >= cfg.max_tokens or latency >= cfg.timeout_s
        self._record_call(
            latency,
            prompt_tokens=prompt_len,
            completion_tokens=len(output_ids),
            finish_reason="length" if (hit_limit or not complete) else "stop",
        )
        return answer

    def close(self) -> None:
        self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
