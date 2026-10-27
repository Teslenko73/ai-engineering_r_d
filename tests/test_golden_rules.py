"""Test na prawdziwych danych: reguły regex (sygnatura, data) kontra golden set.

Reguła może nie znaleźć wartości (wtedy zostaje odpowiedź modelu), ale jeśli ją zwróci, MUSI być zgodna z golden setem.
Inaczej `--rules` psułoby poprawne odpowiedzi modelu. Test pomija się, gdy w data/ nie ma pasujących par PDF + golden.
Pokrycie (ile dokumentów reguły rozpoznały): `pytest tests/test_golden_rules.py -s`.
"""
import json

import _bootstrap  # noqa: F401  (ścieżki importów)
import pytest
from pypdf import PdfReader

from evaluation.results_evaluator import norm_id
from extraction.rules import extract_rule_fields
from paths import DATA_DIR, GOLDEN_DIR

PAIRS = [(g, DATA_DIR / f"{g.stem}.pdf") for g in sorted(GOLDEN_DIR.glob("*.json")) if (DATA_DIR / f"{g.stem}.pdf").exists()]

pytestmark = pytest.mark.skipif(not PAIRS, reason="brak par PDF + golden set w data/")


def _head_text(pdf, pages=2):
    return "\n".join((p.extract_text() or "") for p in PdfReader(pdf).pages[:pages])


def _gold(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("document", data)


def test_rules_never_contradict_golden_set():
    wrong, found, total = [], 0, 0
    for golden, pdf in PAIRS:
        gold, found_rules = _gold(golden), extract_rule_fields(_head_text(pdf))
        for name in ("docket_number", "decision_date"):
            total += 1
            if name not in found_rules:
                continue
            found += 1
            same = (norm_id(found_rules[name]) == norm_id(gold.get(name))) if name == "docket_number" \
                else found_rules[name] == gold.get(name)
            if not same:
                wrong.append(f"{golden.stem}.{name}: reguła={found_rules[name]!r}, golden={gold.get(name)!r}")
    print(f"\nReguły rozpoznały {found}/{total} pól (docket_number, decision_date) w {len(PAIRS)} dokumentach golden setu.")
    assert not wrong, "Reguły nadpisałyby poprawne wartości:\n  " + "\n  ".join(wrong)


if __name__ == "__main__":  # uruchomienie przyciskiem „Run” w IDE
    raise SystemExit(pytest.main([__file__, "-q"]))
