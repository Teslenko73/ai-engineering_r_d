
from extraction.rules import extract_decision_date, extract_docket_number, extract_rule_fields  # noqa: E402

SIEDLCE = """Sygn. akt II Kp 127/15
POSTANOWIENIE
Dnia 5 sierpnia 2015 roku
Sąd Rejonowy w Siedlcach II Wydział Karny
Przewodniczący – SSR Daniel Kędzia
w sprawie 1 Ds 1391/14
Postanowieniem z dnia 25 listopada 2014r., które zapadło"""


def test_siedlce():
    assert extract_rule_fields(SIEDLCE) == {"docket_number": "II Kp 127/15", "decision_date": "2015-08-05"}


def test_ignores_date_of_appealed_judgment():
    text = "Sygn. akt VII Ka 152/16\nSąd po rozpoznaniu apelacji od wyroku z dnia 3 marca 2014 r."
    assert extract_decision_date(text) is None  # brak nagłówka "Dnia ..." -> zostaje wartość z LLM


def test_wyrok_z_dnia():
    assert extract_decision_date("WYROK z dnia 8 maja 2015 r.\nSygn. akt II KK 12/15") == "2015-05-08"


def test_numeric_date():
    assert extract_decision_date("POSTANOWIENIE\nDnia 05.08.2015 r.") == "2015-08-05"


def test_invalid_date_returns_none():
    assert extract_decision_date("Dnia 31 lutego 2015 roku") is None


def test_docket_variants():
    assert extract_docket_number("Sygn. akt: II AKa 12/15") == "II AKa 12/15"
    assert extract_docket_number("Sygn.akt I CSK 45/2015") == "I CSK 45/2015"
    assert extract_docket_number("Brak numeru w tym tekście") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
