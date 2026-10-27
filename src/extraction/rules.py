"""Reguły (regex) dla pól o stałym wzorcu: sygnatura akt i data orzeczenia.

Zasada: jeśli nie jesteśmy pewni, zwracamy None – wtedy zostaje wartość z LLM.
"""
import re
from datetime import date
from typing import Optional

HEAD_CHARS = 1500  # nagłówek orzeczenia jest na samym początku

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
}
_MONTH_RE = "|".join(MONTHS)

# "Dnia 5 sierpnia 2015 roku"  /  "WYROK z dnia 5 sierpnia 2015 r."
# (wielkie "Dnia" celowo, żeby nie łapać "z dnia 25 listopada 2014" z opisu zaskarżonego orzeczenia)
_PREFIX = r"(?:\b(?:Dnia|DNIA)|\b(?i:wyrok|postanowienie|uchwała|zarządzenie|nakaz)\s+z\s+dnia)\s+"
_RE_DATE_WORDS = re.compile(_PREFIX + rf"(\d{{1,2}})\s+((?i:{_MONTH_RE}))\s+(\d{{4}})")
_RE_DATE_NUM = re.compile(_PREFIX + r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})")

# "II Kp 127/15", "VII Ka 152/16", "II AKa 12/15", "I CSK 45/2015"
_DOCKET_CORE = r"[IVXLC]+\s+[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźż]{0,7}\s+\d+/\d{2,4}"
_RE_DOCKET_LABELLED = re.compile(r"(?i:sygn(?:atura|\.)?\s*akt)\s*:?\s*(" + _DOCKET_CORE + ")")
_RE_DOCKET_BARE = re.compile(r"\b(" + _DOCKET_CORE + ")")


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _safe_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def extract_decision_date(text: str) -> Optional[str]:
    head = _clean(text)[:HEAD_CHARS]

    m = _RE_DATE_WORDS.search(head)
    if m:
        day, month_name, year = m.groups()
        return _safe_date(int(year), MONTHS[month_name.lower()], int(day))

    m = _RE_DATE_NUM.search(head)
    if m:
        day, month, year = m.groups()
        return _safe_date(int(year), int(month), int(day))

    return None


def extract_docket_number(text: str) -> Optional[str]:
    head = _clean(text)[:HEAD_CHARS]

    m = _RE_DOCKET_LABELLED.search(head)
    if m:
        return m.group(1)

    # brak etykiety "Sygn. akt" – akceptujemy tylko sygnaturę na samym początku dokumentu
    m = _RE_DOCKET_BARE.search(head[:300])
    return m.group(1) if m else None


def extract_rule_fields(text: str) -> dict:
    """Zwraca tylko te pola, które udało się pewnie wyciągnąć."""
    found = {
        "docket_number": extract_docket_number(text),
        "decision_date": extract_decision_date(text),
    }
    return {k: v for k, v in found.items() if v}
