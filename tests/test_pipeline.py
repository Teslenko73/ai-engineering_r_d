import json
from pathlib import Path

import _bootstrap  # noqa: F401  (ścieżki importów)
import pytest

from fake_llm import GOOD_DOC, FakeLLM, ollama_server, openrouter_server
from evaluation.metrics import compute_run_metrics, percentile
from extraction.extractor import RulingExtractor
from extraction.json_schema import build_response_schema
from llm.base import parse_json_object
from llm.config import LLMConfig
from pipeline.batch_runner import BatchRunner
from pipeline.experiment import load_experiment
from prompts import get_prompt, list_versions

ROOT = Path(__file__).resolve().parent.parent

HEADER = """Sygn. akt II Kp 127/15
POSTANOWIENIE
Dnia 5 sierpnia 2015 roku
Sąd Rejonowy w Siedlcach II Wydział Karny
Przewodniczący – SSR Daniel Kędzia
"""


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "orzeczenie.txt"
    path.write_text(HEADER, encoding="utf-8")
    return path


def make_extractor(llm, **kw):
    return RulingExtractor(llm, get_prompt("v2"), **kw)


# ---------- ekstraktor: walidacja, poprawka, failed ----------

def test_ok_first_try(doc):
    llm = FakeLLM([GOOD_DOC])
    r = make_extractor(llm).extract_from_file(doc)
    assert r.status == "ok" and r.attempts == 1
    assert r.document["docket_number"] == "II Kp 127/15"
    assert r.document["participants"] is None  # pola zagnieżdżone opcjonalne
    assert (r.latency_s, r.prompt_tokens, r.completion_tokens, r.cost) == (1.0, 100, 20, 0.001)
    assert llm.schemas[0] is not None  # structured output: schemat przekazany do klienta


def test_one_correction_attempt_succeeds(doc):
    llm = FakeLLM(["to nie jest json", GOOD_DOC])
    r = make_extractor(llm).extract_from_file(doc)
    assert r.status == "ok" and r.attempts == 2
    assert "to nie jest json" in llm.prompts[1]            # poprawka zawiera poprzednią odpowiedź
    assert "Błąd walidacji" in llm.prompts[1]
    assert (r.latency_s, r.prompt_tokens, r.cost) == (2.0, 200, 0.002)  # statystyki sumowane po próbach


def test_schema_violation_is_corrected(doc):
    bad = {"document": {"court": ["lista zamiast tekstu"]}}
    r = make_extractor(FakeLLM([bad, GOOD_DOC])).extract_from_file(doc)
    assert r.status == "ok" and r.attempts == 2


def test_failed_after_single_correction_never_raises(doc):
    llm = FakeLLM(["zły 1", "zły 2", GOOD_DOC])
    r = make_extractor(llm).extract_from_file(doc)
    assert r.status == "failed" and r.attempts == 2          # tylko JEDNA poprawka
    assert r.document is None and r.raw_response == "zły 2"
    assert len(llm.script) == 1                               # trzecia odpowiedź nie została użyta


def test_call_error_then_retry(doc):
    llm = FakeLLM([TimeoutError("timeout"), GOOD_DOC])
    r = make_extractor(llm).extract_from_file(doc)
    assert r.status == "ok" and r.attempts == 2
    assert "poprzednia odpowiedź" not in llm.prompts[1]       # brak odpowiedzi do poprawienia: ten sam prompt


def test_empty_file_is_failed(tmp_path):
    path = tmp_path / "pusty.txt"
    path.write_text("   ", encoding="utf-8")
    r = make_extractor(FakeLLM([])).extract_from_file(path)
    assert r.status == "failed" and "Brak tekstu" in r.error


def test_rules_override_wrong_llm_values(doc):
    wrong = json.loads(json.dumps(GOOD_DOC))
    wrong["document"]["docket_number"] = "1 Ds 1391/14"
    wrong["document"]["decision_date"] = "2014-11-25"
    r = make_extractor(FakeLLM([wrong]), use_rules=True).extract_from_file(doc)
    assert r.document["docket_number"] == "II Kp 127/15" and r.document["decision_date"] == "2015-08-05"
    assert {o["field"] for o in r.rule_overrides} == {"docket_number", "decision_date"}


def test_structured_output_can_be_disabled(doc):
    llm = FakeLLM([GOOD_DOC], structured_output=False)
    make_extractor(llm).extract_from_file(doc)
    assert llm.schemas == [None]


# ---------- schemat JSON ----------

def test_strict_schema_shape():
    schema = build_response_schema()
    text = json.dumps(schema)
    assert '"default"' not in text and '"title"' not in text

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                assert node["additionalProperties"] is False
                assert sorted(node["required"]) == sorted(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    assert "participants" in schema["$defs"]["DocumentCoreSchema"]["properties"]


def test_parse_json_object():
    assert parse_json_object('tekst {"a": 1} koniec') == {"a": 1}
    for bad in ("", "brak klamer", "{zły json}", "[1, 2]"):
        with pytest.raises(ValueError):
            parse_json_object(bad)


# ---------- metryki ----------

def test_percentile():
    assert percentile([], 50) is None
    assert percentile([5], 95) == 5
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([1, 2, 3, 4, 5], 95) == pytest.approx(4.8)


def test_batch_and_metrics(tmp_path):
    data, golden, out = tmp_path / "data", tmp_path / "golden", tmp_path / "run"
    data.mkdir(); golden.mkdir()
    files = []
    for i in range(3):
        f = data / f"doc{i}.txt"
        f.write_text(HEADER, encoding="utf-8")
        files.append(f)
        (golden / f"doc{i}.json").write_text(json.dumps(GOOD_DOC, ensure_ascii=False), encoding="utf-8")

    wrong_date = json.loads(json.dumps(GOOD_DOC))
    wrong_date["document"]["decision_date"] = "2014-01-01"
    # doc0: poprawny; doc1: zła data (ok, ale błąd merytoryczny); doc2: dwa niepoprawne JSON-y -> failed
    llm = FakeLLM([GOOD_DOC, wrong_date, "zły", "też zły"])
    meta = {"run_id": "t", "config_name": "fake", "provider": "openrouter", "model": "fake-model",
            "prompt_version": "v2", "sampling": {"temperature": 0.0}, "rules": False}
    summary = BatchRunner(make_extractor(llm), out, meta).run(files)
    assert (summary["ok"], summary["failed"]) == (2, 1)

    # rekord zawiera model, wersję promptu i próbkowanie
    record = json.loads((out / "doc0.json").read_text(encoding="utf-8"))
    assert record["meta"]["model"] == "fake-model" and record["meta"]["prompt_version"] == "v2"
    assert record["meta"]["sampling"] == {"temperature": 0.0}
    assert (out / "_run_meta.json").exists()

    m = compute_run_metrics(out, golden)
    assert m["n_docs"] == 3 and m["failed"] == 1
    assert m["valid_pct"] == pytest.approx(200 / 3) and m["first_try_valid_pct"] == pytest.approx(200 / 3)
    assert m["strict_all_ok_pct"] == pytest.approx(100 / 3)          # tylko doc0 ma wszystkie pola krytyczne
    assert m["per_field_pct"]["decision_date"] == pytest.approx(100 / 3)
    assert m["latency_p50_s"] == 1.0 and m["latency_p95_s"] == pytest.approx(1.9)  # 1, 1, 2 s
    assert m["cost_per_1000_docs"] == pytest.approx((0.001 + 0.001 + 0.002) / 3 * 1000)


def test_skip_existing(tmp_path, doc):
    out = tmp_path / "run"
    llm = FakeLLM([GOOD_DOC])
    meta = {"run_id": "t", "provider": "openrouter"}
    BatchRunner(make_extractor(llm), out, meta).run([doc])
    summary = BatchRunner(make_extractor(FakeLLM([])), out, meta, skip_existing=True).run([doc])
    assert summary["skipped"] == 1 and summary["ok"] == 0


# ---------- prompty, konfiguracje, eksperymenty ----------

def test_prompt_versions():
    assert list_versions()[:2] == ["v1", "v2"]
    v1, v2 = get_prompt("v1"), get_prompt("v2")
    assert "participants" not in v1.template and "participants" in v2.template
    assert "TEKST_X" in v2.render("TEKST_X") and "{ruling_text}" not in v2.render("x")
    with pytest.raises(ValueError):
        get_prompt("v99")


def test_all_configs_and_experiments_are_valid():
    names = set()
    for path in sorted((ROOT / "configs").glob("*.json")):
        cfg = LLMConfig.from_file(path)
        names.add(cfg.name)
        assert cfg.name == path.stem
    for path in sorted((ROOT / "experiments").glob("*.json")):
        spec = load_experiment(path)
        assert set(spec["configs"]) <= names, f"{path.name}: nieistniejąca konfiguracja"
        assert set(spec["prompts"]) <= set(list_versions())


def test_config_rejects_unknown_fields(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"provider": "openrouter", "model_name": "m", "temprature": 0.1}))
    with pytest.raises(ValueError, match="nieznane pola"):
        LLMConfig.from_file(path)


# ---------- klienci: prawdziwe SDK / HTTP na lokalnym serwerze ----------

def _openrouter(url, monkeypatch, **cfg):
    pytest.importorskip("openai")
    from llm.openrouter import LLMService
    monkeypatch.setenv("OPENROUTER_BASE_URL", url)
    config = LLMConfig(name="t", provider="openrouter", model_name="vendor/model", **cfg)
    return LLMService(config, api_key="sk-test")


def test_openrouter_uses_json_schema(monkeypatch):
    schema = build_response_schema()
    with openrouter_server() as srv:
        llm = _openrouter(srv.url, monkeypatch, temperature=0.7, top_p=0.9)
        text = llm.generate("sys", "user", schema=schema)
        body = srv.requests[0]
    assert parse_json_object(text)["document"]["court"] == "Sąd Rejonowy w Siedlcach"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["temperature"] == 0.7 and body["top_p"] == 0.9
    assert body["provider"] == {"require_parameters": True} and body["usage"] == {"include": True}
    assert llm.last_call["prompt_tokens"] == 1000 and llm.last_call["cost"] == 0.0004
    assert llm.last_call["mode"] == "json_schema"


def test_openrouter_falls_back_and_remembers_mode(monkeypatch):
    schema = build_response_schema()
    with openrouter_server(reject_modes=("json_schema",)) as srv:
        llm = _openrouter(srv.url, monkeypatch, max_retries=0)
        llm.generate("sys", "user", schema=schema)
        first = [(r.get("response_format") or {}).get("type") for r in srv.requests]
        llm.generate("sys", "user", schema=schema)
        second = [(r.get("response_format") or {}).get("type") for r in srv.requests][len(first):]
    assert first == ["json_schema", "json_object"]
    assert second == ["json_object"]          # po fallbacku nie próbujemy ponownie json_schema


def test_openrouter_greedy_has_no_top_p(monkeypatch):
    with openrouter_server() as srv:
        _openrouter(srv.url, monkeypatch).generate("s", "u")
        body = srv.requests[0]
    assert body["temperature"] == 0.0 and "top_p" not in body and "response_format" in body  # json_object


def test_openrouter_requires_key(monkeypatch):
    pytest.importorskip("openai")
    from llm.openrouter import LLMService
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        LLMService(LLMConfig(name="t", provider="openrouter", model_name="m"))


def test_ollama_client():
    from llm.ollama import LLMService
    schema = build_response_schema()
    with ollama_server() as srv:
        config = LLMConfig(name="o", provider="ollama", model_name="qwen3:4b", base_url=srv.url,
                           temperature=0.7, top_p=0.8, top_k=20, num_ctx=8192, enable_thinking=False)
        llm = LLMService(config)
        text = llm.generate("sys", "user", schema=schema)
        body = srv.requests[0]
    assert parse_json_object(text)["document"]["docket_number"] == "II Kp 127/15"
    assert body["format"] == schema and body["stream"] is False and body["think"] is False
    assert body["options"] == {"temperature": 0.7, "num_predict": 1024, "top_p": 0.8, "top_k": 20, "num_ctx": 8192}
    assert llm.last_call["prompt_tokens"] == 900 and llm.last_call["completion_tokens"] == 150
    assert llm.last_call["cost"] == 0.0


def test_ollama_missing_model_and_server():
    from llm.ollama import LLMService
    with ollama_server(models=("inny:1b",)) as srv:
        with pytest.raises(RuntimeError, match="ollama pull qwen3:4b"):
            LLMService(LLMConfig(name="o", provider="ollama", model_name="qwen3:4b", base_url=srv.url))
    with pytest.raises(RuntimeError, match="ollama serve"):
        LLMService(LLMConfig(name="o", provider="ollama", model_name="m", base_url="http://127.0.0.1:1"))


# ---------- statystyki przebiegu i log eksperymentu ----------

class _StubExtractor:
    """Ekstraktor-atrapa: dla każdego pliku wykonuje akcję z listy (wynik albo wyjątek)."""
    def __init__(self, actions):
        self.actions = list(actions)

    def extract_from_file(self, path):
        action = self.actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action


def _ok_result():
    from extraction.extractor import ExtractionResult
    return ExtractionResult(status="ok", document=GOOD_DOC["document"], attempts=1, latency_s=1.5,
                            prompt_tokens=100, completion_tokens=20, cost=0.001)


def _failed_result():
    from extraction.extractor import ExtractionResult
    return ExtractionResult(status="failed", error="zły JSON", attempts=2, latency_s=3.0, raw_response="x")


def _txt_files(tmp_path, n):
    files = []
    for i in range(n):
        f = tmp_path / f"doc{i}.txt"
        f.write_text(HEADER, encoding="utf-8")
        files.append(f)
    return files


def test_summary_lists_failures_time_and_cost(tmp_path):
    files = _txt_files(tmp_path, 3)
    out = tmp_path / "run"
    runner = BatchRunner(_StubExtractor([_ok_result(), _failed_result(), RuntimeError("bug w kodzie")]), out,
                         {"run_id": "t", "model": "m", "provider": "openrouter"})
    summary = runner.run(files)

    assert (summary["ok"], summary["failed"], summary["not_processed"]) == (1, 2, 0)
    assert [f["file"] for f in summary["failed_files"]] == ["doc1.txt", "doc2.txt"]
    assert "Nieoczekiwany błąd: RuntimeError" in summary["failed_files"][1]["error"]   # batch jedzie dalej
    assert summary["total_cost"] == pytest.approx(0.001) and summary["total_prompt_tokens"] == 100

    text = (out / "_run_summary.txt").read_text(encoding="utf-8")
    assert "doc1.txt" in text and "zły JSON" in text and "NIEPRZETWORZONE:   0" in text
    meta = json.loads((out / "_run_meta.json").read_text(encoding="utf-8"))
    assert meta["failed"] == 2 and meta["wall_time_s"] >= 0 and len(meta["per_file"]) == 3
    # plik z błędem nieoczekiwanym też ma rekord, więc ewaluator nie traktuje go jako "brak wyniku"
    assert json.loads((out / "doc2.json").read_text(encoding="utf-8"))["status"] == "failed"


def test_interrupted_run_reports_unprocessed_files(tmp_path):
    files = _txt_files(tmp_path, 4)
    out = tmp_path / "run"
    runner = BatchRunner(_StubExtractor([_ok_result(), KeyboardInterrupt()]), out, {"run_id": "t"})
    with pytest.raises(KeyboardInterrupt):
        runner.run(files)

    meta = json.loads((out / "_run_meta.json").read_text(encoding="utf-8"))   # zapisane mimo przerwania
    assert meta["interrupted"] is True and meta["ok"] == 1
    assert meta["not_processed_files"] == ["doc1.txt", "doc2.txt", "doc3.txt"]
    text = (out / "_run_summary.txt").read_text(encoding="utf-8")
    assert "PRZERWANY" in text and "doc3.txt" in text and "--skip-existing" in text


def test_experiment_log_records_skipped_config(tmp_path, monkeypatch):
    from pipeline.experiment import run_experiment
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    data, golden, configs, results = (tmp_path / n for n in ("data", "golden", "configs", "results"))
    for d in (data, golden, configs):
        d.mkdir()
    (data / "doc0.txt").write_text(HEADER, encoding="utf-8")
    (golden / "doc0.json").write_text(json.dumps(GOOD_DOC), encoding="utf-8")
    (configs / "bez_klucza.json").write_text(json.dumps({"provider": "openrouter", "model_name": "m"}), encoding="utf-8")

    spec = {"name": "t", "scope": "golden", "limit": None, "configs": ["bez_klucza"], "prompts": ["v1"], "rules": [False]}
    assert run_experiment(spec, results_root=results, configs_dir=configs, data_dir=data, golden_dir=golden) == []

    text = (results / "_experiment_t.txt").read_text(encoding="utf-8")
    assert "POMINIĘTE" in text and "bez_klucza" in text and "brak: żaden przebieg" in text
    assert json.loads((results / "_experiment_t.json").read_text(encoding="utf-8"))["skipped_configs"][0]["config"] == "bez_klucza"


def test_execute_run_writes_report_automatically(tmp_path, doc):
    from pipeline.experiment import execute_run
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "orzeczenie.json").write_text(json.dumps(GOOD_DOC, ensure_ascii=False), encoding="utf-8")
    llm = FakeLLM([GOOD_DOC])
    out_dir, summary = execute_run(llm, llm.config, "v2", [doc], results_root=tmp_path / "res", golden_dir=golden)
    assert summary["ok"] == 1
    for name in ("_report.txt", "_run_summary.txt", "_run_meta.json", "orzeczenie.json"):
        assert (out_dir / name).exists(), name


def test_build_spec_from_flags_without_experiment_file():
    from cli import build_parser, build_spec
    parser = build_parser()
    spec = build_spec(parser.parse_args(["experiment", "--all-configs"]))
    on_disk = {p.stem for p in (ROOT / "configs").glob("*.json")}
    assert set(spec["configs"]) == on_disk and spec["prompts"] == list_versions()

    spec = build_spec(parser.parse_args(["experiment", "--configs", "openrouter_t0", "--prompts", "v2"]))
    assert spec["configs"] == ["openrouter_t0"] and spec["prompts"] == ["v2"]

    with pytest.raises(SystemExit):  # nieistniejąca konfiguracja
        build_spec(parser.parse_args(["experiment", "--configs", "nie_ma_takiej"]))
    with pytest.raises(ValueError):  # nieistniejąca wersja promptu
        build_spec(parser.parse_args(["experiment", "--all-configs", "--prompts", "v99"]))


if __name__ == "__main__":  # uruchomienie przyciskiem „Run” w IDE
    raise SystemExit(pytest.main([__file__, "-q"]))
# import json
# from pathlib import Path
#
# import pytest
#
# from fake_llm import GOOD_DOC, FakeLLM, ollama_server, openrouter_server
# from evaluation.metrics import compute_run_metrics, percentile
# from extraction.extractor import RulingExtractor
# from extraction.json_schema import build_response_schema
# from llm.base import parse_json_object
# from llm.config import LLMConfig
# from pipeline.batch_runner import BatchRunner
# from pipeline.experiment import load_experiment
# from prompts import get_prompt, list_versions
#
# ROOT = Path(__file__).resolve().parent.parent
#
# HEADER = """Sygn. akt II Kp 127/15
# POSTANOWIENIE
# Dnia 5 sierpnia 2015 roku
# Sąd Rejonowy w Siedlcach II Wydział Karny
# Przewodniczący – SSR Daniel Kędzia
# """
#
#
# @pytest.fixture
# def doc(tmp_path):
#     path = tmp_path / "orzeczenie.txt"
#     path.write_text(HEADER, encoding="utf-8")
#     return path
#
#
# def make_extractor(llm, **kw):
#     return RulingExtractor(llm, get_prompt("v2"), **kw)
#
#
# # ---------- ekstraktor: walidacja, poprawka, failed ----------
#
# def test_ok_first_try(doc):
#     llm = FakeLLM([GOOD_DOC])
#     r = make_extractor(llm).extract_from_file(doc)
#     assert r.status == "ok" and r.attempts == 1
#     assert r.document["docket_number"] == "II Kp 127/15"
#     assert r.document["participants"] is None  # pola zagnieżdżone opcjonalne
#     assert (r.latency_s, r.prompt_tokens, r.completion_tokens, r.cost) == (1.0, 100, 20, 0.001)
#     assert llm.schemas[0] is not None  # structured output: schemat przekazany do klienta
#
#
# def test_one_correction_attempt_succeeds(doc):
#     llm = FakeLLM(["to nie jest json", GOOD_DOC])
#     r = make_extractor(llm).extract_from_file(doc)
#     assert r.status == "ok" and r.attempts == 2
#     assert "to nie jest json" in llm.prompts[1]            # poprawka zawiera poprzednią odpowiedź
#     assert "Błąd walidacji" in llm.prompts[1]
#     assert (r.latency_s, r.prompt_tokens, r.cost) == (2.0, 200, 0.002)  # statystyki sumowane po próbach
#
#
# def test_schema_violation_is_corrected(doc):
#     bad = {"document": {"court": ["lista zamiast tekstu"]}}
#     r = make_extractor(FakeLLM([bad, GOOD_DOC])).extract_from_file(doc)
#     assert r.status == "ok" and r.attempts == 2
#
#
# def test_failed_after_single_correction_never_raises(doc):
#     llm = FakeLLM(["zły 1", "zły 2", GOOD_DOC])
#     r = make_extractor(llm).extract_from_file(doc)
#     assert r.status == "failed" and r.attempts == 2          # tylko JEDNA poprawka
#     assert r.document is None and r.raw_response == "zły 2"
#     assert len(llm.script) == 1                               # trzecia odpowiedź nie została użyta
#
#
# def test_call_error_then_retry(doc):
#     llm = FakeLLM([TimeoutError("timeout"), GOOD_DOC])
#     r = make_extractor(llm).extract_from_file(doc)
#     assert r.status == "ok" and r.attempts == 2
#     assert "poprzednia odpowiedź" not in llm.prompts[1]       # brak odpowiedzi do poprawienia: ten sam prompt
#
#
# def test_empty_file_is_failed(tmp_path):
#     path = tmp_path / "pusty.txt"
#     path.write_text("   ", encoding="utf-8")
#     r = make_extractor(FakeLLM([])).extract_from_file(path)
#     assert r.status == "failed" and "Brak tekstu" in r.error
#
#
# def test_rules_override_wrong_llm_values(doc):
#     wrong = json.loads(json.dumps(GOOD_DOC))
#     wrong["document"]["docket_number"] = "1 Ds 1391/14"
#     wrong["document"]["decision_date"] = "2014-11-25"
#     r = make_extractor(FakeLLM([wrong]), use_rules=True).extract_from_file(doc)
#     assert r.document["docket_number"] == "II Kp 127/15" and r.document["decision_date"] == "2015-08-05"
#     assert {o["field"] for o in r.rule_overrides} == {"docket_number", "decision_date"}
#
#
# def test_structured_output_can_be_disabled(doc):
#     llm = FakeLLM([GOOD_DOC], structured_output=False)
#     make_extractor(llm).extract_from_file(doc)
#     assert llm.schemas == [None]
#
#
# # ---------- schemat JSON ----------
#
# def test_strict_schema_shape():
#     schema = build_response_schema()
#     text = json.dumps(schema)
#     assert '"default"' not in text and '"title"' not in text
#
#     def walk(node):
#         if isinstance(node, dict):
#             if node.get("type") == "object" and "properties" in node:
#                 assert node["additionalProperties"] is False
#                 assert sorted(node["required"]) == sorted(node["properties"])
#             for v in node.values():
#                 walk(v)
#         elif isinstance(node, list):
#             for v in node:
#                 walk(v)
#     walk(schema)
#     assert "participants" in schema["$defs"]["DocumentCoreSchema"]["properties"]
#
#
# def test_parse_json_object():
#     assert parse_json_object('tekst {"a": 1} koniec') == {"a": 1}
#     for bad in ("", "brak klamer", "{zły json}", "[1, 2]"):
#         with pytest.raises(ValueError):
#             parse_json_object(bad)
#
#
# # ---------- metryki ----------
#
# def test_percentile():
#     assert percentile([], 50) is None
#     assert percentile([5], 95) == 5
#     assert percentile([1, 2, 3, 4], 50) == 2.5
#     assert percentile([1, 2, 3, 4, 5], 95) == pytest.approx(4.8)
#
#
# def test_batch_and_metrics(tmp_path):
#     data, golden, out = tmp_path / "data", tmp_path / "golden", tmp_path / "run"
#     data.mkdir(); golden.mkdir()
#     files = []
#     for i in range(3):
#         f = data / f"doc{i}.txt"
#         f.write_text(HEADER, encoding="utf-8")
#         files.append(f)
#         (golden / f"doc{i}.json").write_text(json.dumps(GOOD_DOC, ensure_ascii=False), encoding="utf-8")
#
#     wrong_date = json.loads(json.dumps(GOOD_DOC))
#     wrong_date["document"]["decision_date"] = "2014-01-01"
#     # doc0: poprawny; doc1: zła data (ok, ale błąd merytoryczny); doc2: dwa niepoprawne JSON-y -> failed
#     llm = FakeLLM([GOOD_DOC, wrong_date, "zły", "też zły"])
#     meta = {"run_id": "t", "config_name": "fake", "provider": "openrouter", "model": "fake-model",
#             "prompt_version": "v2", "sampling": {"temperature": 0.0}, "rules": False}
#     summary = BatchRunner(make_extractor(llm), out, meta).run(files)
#     assert (summary["ok"], summary["failed"]) == (2, 1)
#
#     # rekord zawiera model, wersję promptu i próbkowanie
#     record = json.loads((out / "doc0.json").read_text(encoding="utf-8"))
#     assert record["meta"]["model"] == "fake-model" and record["meta"]["prompt_version"] == "v2"
#     assert record["meta"]["sampling"] == {"temperature": 0.0}
#     assert (out / "_run_meta.json").exists()
#
#     m = compute_run_metrics(out, golden)
#     assert m["n_docs"] == 3 and m["failed"] == 1
#     assert m["valid_pct"] == pytest.approx(200 / 3) and m["first_try_valid_pct"] == pytest.approx(200 / 3)
#     assert m["strict_all_ok_pct"] == pytest.approx(100 / 3)          # tylko doc0 ma wszystkie pola krytyczne
#     assert m["per_field_pct"]["decision_date"] == pytest.approx(100 / 3)
#     assert m["latency_p50_s"] == 1.0 and m["latency_p95_s"] == pytest.approx(1.9)  # 1, 1, 2 s
#     assert m["cost_per_1000_docs"] == pytest.approx((0.001 + 0.001 + 0.002) / 3 * 1000)
#
#
# def test_skip_existing(tmp_path, doc):
#     out = tmp_path / "run"
#     llm = FakeLLM([GOOD_DOC])
#     meta = {"run_id": "t", "provider": "openrouter"}
#     BatchRunner(make_extractor(llm), out, meta).run([doc])
#     summary = BatchRunner(make_extractor(FakeLLM([])), out, meta, skip_existing=True).run([doc])
#     assert summary["skipped"] == 1 and summary["ok"] == 0
#
#
# # ---------- prompty, konfiguracje, eksperymenty ----------
#
# def test_prompt_versions():
#     assert list_versions()[:2] == ["v1", "v2"]
#     v1, v2 = get_prompt("v1"), get_prompt("v2")
#     assert "participants" not in v1.template and "participants" in v2.template
#     assert "TEKST_X" in v2.render("TEKST_X") and "{ruling_text}" not in v2.render("x")
#     with pytest.raises(ValueError):
#         get_prompt("v99")
#
#
# def test_all_configs_and_experiments_are_valid():
#     names = set()
#     for path in sorted((ROOT / "configs").glob("*.json")):
#         cfg = LLMConfig.from_file(path)
#         names.add(cfg.name)
#         assert cfg.name == path.stem
#     for path in sorted((ROOT / "experiments").glob("*.json")):
#         spec = load_experiment(path)
#         assert set(spec["configs"]) <= names, f"{path.name}: nieistniejąca konfiguracja"
#         assert set(spec["prompts"]) <= set(list_versions())
#
#
# def test_config_rejects_unknown_fields(tmp_path):
#     path = tmp_path / "x.json"
#     path.write_text(json.dumps({"provider": "openrouter", "model_name": "m", "temprature": 0.1}))
#     with pytest.raises(ValueError, match="nieznane pola"):
#         LLMConfig.from_file(path)
#
#
# # ---------- klienci: prawdziwe SDK / HTTP na lokalnym serwerze ----------
#
# def _openrouter(url, monkeypatch, **cfg):
#     pytest.importorskip("openai")
#     from llm.openrouter import LLMService
#     monkeypatch.setenv("OPENROUTER_BASE_URL", url)
#     config = LLMConfig(name="t", provider="openrouter", model_name="vendor/model", **cfg)
#     return LLMService(config, api_key="sk-test")
#
#
# def test_openrouter_uses_json_schema(monkeypatch):
#     schema = build_response_schema()
#     with openrouter_server() as srv:
#         llm = _openrouter(srv.url, monkeypatch, temperature=0.7, top_p=0.9)
#         text = llm.generate("sys", "user", schema=schema)
#         body = srv.requests[0]
#     assert parse_json_object(text)["document"]["court"] == "Sąd Rejonowy w Siedlcach"
#     assert body["response_format"]["type"] == "json_schema"
#     assert body["response_format"]["json_schema"]["strict"] is True
#     assert body["temperature"] == 0.7 and body["top_p"] == 0.9
#     assert body["provider"] == {"require_parameters": True} and body["usage"] == {"include": True}
#     assert llm.last_call["prompt_tokens"] == 1000 and llm.last_call["cost"] == 0.0004
#     assert llm.last_call["mode"] == "json_schema"
#
#
# def test_openrouter_falls_back_and_remembers_mode(monkeypatch):
#     schema = build_response_schema()
#     with openrouter_server(reject_modes=("json_schema",)) as srv:
#         llm = _openrouter(srv.url, monkeypatch, max_retries=0)
#         llm.generate("sys", "user", schema=schema)
#         first = [(r.get("response_format") or {}).get("type") for r in srv.requests]
#         llm.generate("sys", "user", schema=schema)
#         second = [(r.get("response_format") or {}).get("type") for r in srv.requests][len(first):]
#     assert first == ["json_schema", "json_object"]
#     assert second == ["json_object"]          # po fallbacku nie próbujemy ponownie json_schema
#
#
# def test_openrouter_greedy_has_no_top_p(monkeypatch):
#     with openrouter_server() as srv:
#         _openrouter(srv.url, monkeypatch).generate("s", "u")
#         body = srv.requests[0]
#     assert body["temperature"] == 0.0 and "top_p" not in body and "response_format" in body  # json_object
#
#
# def test_openrouter_requires_key(monkeypatch):
#     pytest.importorskip("openai")
#     from llm.openrouter import LLMService
#     monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
#     with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
#         LLMService(LLMConfig(name="t", provider="openrouter", model_name="m"))
#
#
# def test_ollama_client():
#     from llm.ollama import LLMService
#     schema = build_response_schema()
#     with ollama_server() as srv:
#         config = LLMConfig(name="o", provider="ollama", model_name="qwen3:4b", base_url=srv.url,
#                            temperature=0.7, top_p=0.8, top_k=20, num_ctx=8192, enable_thinking=False)
#         llm = LLMService(config)
#         text = llm.generate("sys", "user", schema=schema)
#         body = srv.requests[0]
#     assert parse_json_object(text)["document"]["docket_number"] == "II Kp 127/15"
#     assert body["format"] == schema and body["stream"] is False and body["think"] is False
#     assert body["options"] == {"temperature": 0.7, "num_predict": 1024, "top_p": 0.8, "top_k": 20, "num_ctx": 8192}
#     assert llm.last_call["prompt_tokens"] == 900 and llm.last_call["completion_tokens"] == 150
#     assert llm.last_call["cost"] == 0.0
#
#
# def test_ollama_missing_model_and_server():
#     from llm.ollama import LLMService
#     with ollama_server(models=("inny:1b",)) as srv:
#         with pytest.raises(RuntimeError, match="ollama pull qwen3:4b"):
#             LLMService(LLMConfig(name="o", provider="ollama", model_name="qwen3:4b", base_url=srv.url))
#     with pytest.raises(RuntimeError, match="ollama serve"):
#         LLMService(LLMConfig(name="o", provider="ollama", model_name="m", base_url="http://127.0.0.1:1"))
#
#
# # ---------- statystyki przebiegu i log eksperymentu ----------
#
# class _StubExtractor:
#     """Ekstraktor-atrapa: dla każdego pliku wykonuje akcję z listy (wynik albo wyjątek)."""
#     def __init__(self, actions):
#         self.actions = list(actions)
#
#     def extract_from_file(self, path):
#         action = self.actions.pop(0)
#         if isinstance(action, BaseException):
#             raise action
#         return action
#
#
# def _ok_result():
#     from extraction.extractor import ExtractionResult
#     return ExtractionResult(status="ok", document=GOOD_DOC["document"], attempts=1, latency_s=1.5,
#                             prompt_tokens=100, completion_tokens=20, cost=0.001)
#
#
# def _failed_result():
#     from extraction.extractor import ExtractionResult
#     return ExtractionResult(status="failed", error="zły JSON", attempts=2, latency_s=3.0, raw_response="x")
#
#
# def _txt_files(tmp_path, n):
#     files = []
#     for i in range(n):
#         f = tmp_path / f"doc{i}.txt"
#         f.write_text(HEADER, encoding="utf-8")
#         files.append(f)
#     return files
#
#
# def test_summary_lists_failures_time_and_cost(tmp_path):
#     files = _txt_files(tmp_path, 3)
#     out = tmp_path / "run"
#     runner = BatchRunner(_StubExtractor([_ok_result(), _failed_result(), RuntimeError("bug w kodzie")]), out,
#                          {"run_id": "t", "model": "m", "provider": "openrouter"})
#     summary = runner.run(files)
#
#     assert (summary["ok"], summary["failed"], summary["not_processed"]) == (1, 2, 0)
#     assert [f["file"] for f in summary["failed_files"]] == ["doc1.txt", "doc2.txt"]
#     assert "Nieoczekiwany błąd: RuntimeError" in summary["failed_files"][1]["error"]   # batch jedzie dalej
#     assert summary["total_cost"] == pytest.approx(0.001) and summary["total_prompt_tokens"] == 100
#
#     text = (out / "_run_summary.txt").read_text(encoding="utf-8")
#     assert "doc1.txt" in text and "zły JSON" in text and "NIEPRZETWORZONE:   0" in text
#     meta = json.loads((out / "_run_meta.json").read_text(encoding="utf-8"))
#     assert meta["failed"] == 2 and meta["wall_time_s"] >= 0 and len(meta["per_file"]) == 3
#     # plik z błędem nieoczekiwanym też ma rekord, więc ewaluator nie traktuje go jako "brak wyniku"
#     assert json.loads((out / "doc2.json").read_text(encoding="utf-8"))["status"] == "failed"
#
#
# def test_interrupted_run_reports_unprocessed_files(tmp_path):
#     files = _txt_files(tmp_path, 4)
#     out = tmp_path / "run"
#     runner = BatchRunner(_StubExtractor([_ok_result(), KeyboardInterrupt()]), out, {"run_id": "t"})
#     with pytest.raises(KeyboardInterrupt):
#         runner.run(files)
#
#     meta = json.loads((out / "_run_meta.json").read_text(encoding="utf-8"))   # zapisane mimo przerwania
#     assert meta["interrupted"] is True and meta["ok"] == 1
#     assert meta["not_processed_files"] == ["doc1.txt", "doc2.txt", "doc3.txt"]
#     text = (out / "_run_summary.txt").read_text(encoding="utf-8")
#     assert "PRZERWANY" in text and "doc3.txt" in text and "--skip-existing" in text
#
#
# def test_experiment_log_records_skipped_config(tmp_path, monkeypatch):
#     from pipeline.experiment import run_experiment
#     monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
#     data, golden, configs, results = (tmp_path / n for n in ("data", "golden", "configs", "results"))
#     for d in (data, golden, configs):
#         d.mkdir()
#     (data / "doc0.txt").write_text(HEADER, encoding="utf-8")
#     (golden / "doc0.json").write_text(json.dumps(GOOD_DOC), encoding="utf-8")
#     (configs / "bez_klucza.json").write_text(json.dumps({"provider": "openrouter", "model_name": "m"}), encoding="utf-8")
#
#     spec = {"name": "t", "scope": "golden", "limit": None, "configs": ["bez_klucza"], "prompts": ["v1"], "rules": [False]}
#     assert run_experiment(spec, results_root=results, configs_dir=configs, data_dir=data, golden_dir=golden) == []
#
#     text = (results / "_experiment_t.txt").read_text(encoding="utf-8")
#     assert "POMINIĘTE" in text and "bez_klucza" in text and "brak: żaden przebieg" in text
#     assert json.loads((results / "_experiment_t.json").read_text(encoding="utf-8"))["skipped_configs"][0]["config"] == "bez_klucza"
#
#
# def test_execute_run_writes_report_automatically(tmp_path, doc):
#     from pipeline.experiment import execute_run
#     golden = tmp_path / "golden"
#     golden.mkdir()
#     (golden / "orzeczenie.json").write_text(json.dumps(GOOD_DOC, ensure_ascii=False), encoding="utf-8")
#     llm = FakeLLM([GOOD_DOC])
#     out_dir, summary = execute_run(llm, llm.config, "v2", [doc], results_root=tmp_path / "res", golden_dir=golden)
#     assert summary["ok"] == 1
#     for name in ("_report.txt", "_run_summary.txt", "_run_meta.json", "orzeczenie.json"):
#         assert (out_dir / name).exists(), name
