"""v2 – doprecyzowane reguły pól, struktura zagnieżdżona, przykład (few-shot)."""

SUMMARY = "v2: pełna struktura (z polami zagnieżdżonymi), reguły dla daty/sygnatury/applicant, lista wartości enum, wymyślony przykład."

SYSTEM_PROMPT = (
    "Jesteś precyzyjnym asystentem prawnym wyciągającym dane z orzeczeń sądowych (polskich lub anglojęzycznych) "
    "do formatu JSON. Kopiujesz wartości z tekstu, niczego nie zgadujesz i zwracasz wyłącznie poprawny JSON, "
    "bez komentarzy i bez markdownu."
)

RULING_EXTRACTION_TEMPLATE = """
Przeanalizuj poniższe orzeczenie sądu (polskie lub anglojęzyczne) i wyciągnij z niego dane do formatu JSON.
STRUKTURA:
{
  "document": {
    "document_type": ,
    "language": ,
    "court": ,
    "division": ,
    "docket_number": ,
    "decision_date":,
    "presiding_judge": ,
    "applicant": ,
    "subject_matter": 
    "participants": {
      "court_clerk": ,
      "prosecutor": 
    },
    "related_case": {
      "docket_number": ,
      "authority": 
    },
    "operative_part": {
      "decision": ,
      "legal_basis": []
    }
  }
}

PRZYKŁAD (wymyślony, tylko ilustracja formatu):
Tekst: "Sygn. akt III K 45/20 WYROK Dnia 3 marca 2021 roku Sąd Rejonowy w Przykładowie III Wydział Karny w składzie: Przewodniczący: SSR Jan Wzorcowy Protokolant: Anna Testowa przy udziale Prokuratora Marka Próbnego po rozpoznaniu sprawy Piotra Z. oskarżonego o czyn z art. 178a § 1 kk, na podstawie art. 414 § 1 kpk orzeka: uniewinnić oskarżonego od zarzucanego mu czynu."
Wynik:
{"document": {"document_type": "wyrok", "language": "pl", "court": "Sąd Rejonowy w Przykładowie", "division": "III Wydział Karny", "docket_number": "III K 45/20", "decision_date": "2021-03-03", "presiding_judge": "SSR Jan Wzorcowy", "applicant": null, "subject_matter": "Sprawa karna o czyn z art. 178a § 1 kk zakończona uniewinnieniem oskarżonego.", "participants": {"court_clerk": "Anna Testowa", "prosecutor": "Marek Próbny"}, "related_case": {"docket_number": null, "authority": null}, "operative_part": {"decision": "uniewinnienie oskarżonego", "legal_basis": ["art. 414 § 1 kpk"]}}}

TEKST ORZECZENIA:
{ruling_text}
"""
