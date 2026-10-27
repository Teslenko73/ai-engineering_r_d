"""Kontrola treści odpowiedzi. Schemat Pydantic sprawdza tylko FORMAT (wszystkie pola są opcjonalne),
więc pusty obiekt, same nulle albo szablony skopiowane z promptu też go przechodzą.
Tutaj odrzucamy takie odpowiedzi, żeby nie liczyły się jako poprawne."""
import re

CORE_FIELDS = (
    "document_type", "language", "court", "division", "docket_number",
    "decision_date", "presiding_judge", "applicant", "subject_matter",
)
MIN_FILLED = 3  # tyle z 9 pól głównych musi mieć wartość, żeby odpowiedź nie była uznana za pustą

_TEMPLATE = re.compile(r"^\s*<[^<>]{2,}>\s*$")        # np. "<pełna nazwa sądu wydającego orzeczenie>"
_LITERAL_NULLS = {"null", "none", "n/a"}               # tekst "null" zamiast prawdziwego null


def _is_filled(value) -> bool:
    return value not in (None, "", [], {})


def filled_count(document: dict) -> int:
    return sum(_is_filled(document.get(f)) for f in CORE_FIELDS)


def placeholder_fields(document: dict) -> list[str]:
    """Pola, których wartość to szablon z promptu albo napis 'null' zamiast wartości."""
    bad = []
    for name, value in document.items():
        if isinstance(value, str) and (_TEMPLATE.match(value) or value.strip().lower() in _LITERAL_NULLS):
            bad.append(name)
    return bad


def content_problem(document: dict) -> str | None:
    """Opis problemu z treścią odpowiedzi albo None, gdy treść wygląda na realną."""
    placeholders = placeholder_fields(document)
    if placeholders:
        return f"Pola zawierają szablon z promptu lub tekst 'null' zamiast wartości: {', '.join(placeholders)}."
    if filled_count(document) < MIN_FILLED:
        return (f"Odpowiedź jest pusta: wypełnione {filled_count(document)} z {len(CORE_FIELDS)} pól głównych "
                f"(minimum {MIN_FILLED}). Jeśli informacji nie ma w tekście, pole ma być null, ale dokument zawiera "
                f"sygnaturę, sąd i datę.")
    return None
