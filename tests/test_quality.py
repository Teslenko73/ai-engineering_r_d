"""Kontrola treści: pusta odpowiedź i szablony z promptu nie mogą być uznane za poprawne."""
import _bootstrap  # noqa: F401
import pytest

from fake_llm import GOOD_DOC, FakeLLM
from extraction.extractor import RulingExtractor
from extraction.quality import content_problem, filled_count, placeholder_fields
from prompts import get_prompt

GOOD = GOOD_DOC["document"]


@pytest.fixture
def doc(tmp_path):
    path = tmp_path / "o.txt"
    path.write_text("Sygn. akt II Kp 127/15\nPOSTANOWIENIE\nSąd Rejonowy w Siedlcach", encoding="utf-8")
    return path


def test_good_document_has_no_problem():
    assert content_problem(GOOD) is None
    assert filled_count(GOOD) == 9


def test_empty_and_null_documents_are_problems():
    assert content_problem({}) is not None
    assert content_problem({k: None for k in GOOD}) is not None
    assert content_problem({"court": "Sąd", "language": "pl"}) is not None  # tylko 2 pola


def test_placeholders_are_detected():
    bad = dict(GOOD, docket_number="<sygnatura akt sprawy>", court="null")
    assert set(placeholder_fields(bad)) == {"docket_number", "court"}
    assert content_problem(bad) is not None


@pytest.mark.parametrize("junk", [{"document": {}}, {"document": {"court": None}}])
def test_junk_then_good_is_corrected(doc, junk):
    llm = FakeLLM([junk, GOOD_DOC])
    r = RulingExtractor(llm, get_prompt("v2")).extract_from_file(doc)
    assert r.status == "ok" and r.attempts == 2
    assert "Błąd walidacji" in llm.prompts[1]


def test_junk_twice_is_failed(doc):
    llm = FakeLLM([{"document": {}}, {"document": {}}])
    r = RulingExtractor(llm, get_prompt("v2")).extract_from_file(doc)
    assert r.status == "failed" and r.attempts == 2
