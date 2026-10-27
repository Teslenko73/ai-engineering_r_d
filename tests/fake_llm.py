"""Atrapy do testów: model z zadanym scenariuszem odpowiedzi oraz serwery HTTP udające OpenRouter i Ollamę."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from llm.base import BaseLLM
from llm.config import LLMConfig

GOOD_DOC = {
    "document": {
        "document_type": "postanowienie", "language": "pl", "court": "Sąd Rejonowy w Siedlcach",
        "division": "II Wydział Karny", "docket_number": "II Kp 127/15", "decision_date": "2015-08-05",
        "presiding_judge": "SSR Daniel Kędzia", "applicant": "Prokurator Rejonowy",
        "subject_matter": "wniosek o orzeczenie przepadku dowodów rzeczowych",
    }
}


class FakeLLM(BaseLLM):
    """Zwraca kolejne elementy scenariusza: tekst (odpowiedź) albo wyjątek (błąd wywołania)."""

    def __init__(self, script, provider="openrouter", temperature=0.0, structured_output=True):
        super().__init__(LLMConfig(name="fake", provider=provider, model_name="fake-model",
                                   temperature=temperature, structured_output=structured_output))
        self.script = list(script)
        self.prompts = []   # user_prompty z kolejnych wywołań
        self.schemas = []

    def generate(self, system_prompt, user_prompt, temperature=None, schema=None):
        self.prompts.append(user_prompt)
        self.schemas.append(schema)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        self._record_call(1.0, prompt_tokens=100, completion_tokens=20, cost=0.001)
        return item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)


# ---------- serwery HTTP ----------

class _Server:
    def __init__(self, handler_cls):
        self.httpd = HTTPServer(("127.0.0.1", 0), handler_cls)
        self.httpd.requests = []
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    @property
    def requests(self):
        return self.httpd.requests

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def openrouter_server(reject_modes=()):
    """Udaje /chat/completions. `reject_modes`: typy response_format, na które serwer odpowiada 400."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.requests.append(body)
            rf_type = (body.get("response_format") or {}).get("type", "plain")
            if rf_type in reject_modes:
                payload, status = {"error": {"message": f"response_format {rf_type} not supported", "code": 400}}, 400
            else:
                content = json.dumps(GOOD_DOC, ensure_ascii=False)
                payload = {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                           "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                           "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200, "cost": 0.0004}}
                status = 200
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return _Server(Handler)


def ollama_server(models=("qwen3:4b",)):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, payload):
            raw = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self._send({"models": [{"name": m} for m in models]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.server.requests.append(body)
            self._send({"message": {"role": "assistant", "content": json.dumps(GOOD_DOC, ensure_ascii=False)},
                        "done_reason": "stop", "prompt_eval_count": 900, "eval_count": 150})

    return _Server(Handler)
