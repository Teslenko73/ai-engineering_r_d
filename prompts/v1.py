"""v2 – doprecyzowane reguły pól, struktura zagnieżdżona, przykład (few-shot)."""

SUMMARY = "v2: pełna struktura (z polami zagnieżdżonymi), reguły dla daty/sygnatury/applicant, lista wartości enum, wymyślony przykład."

SYSTEM_PROMPT = (
    "Jesteś precyzyjnym asystentem prawnym wyciągającym dane z orzeczeń sądowych (polskich lub anglojęzycznych) "
    "do formatu JSON. Kopiujesz wartości z tekstu, niczego nie zgadujesz i zwracasz wyłącznie poprawny JSON, "
    "bez komentarzy i bez markdownu."
)

# UWAGA: szablon zawiera klamry JSON-a, więc tekst podstawiamy przez .replace("{ruling_text}", ...), a NIE przez .format().
RULING_EXTRACTION_TEMPLATE = """
Przeanalizuj poniższe orzeczenie sądu (polskie lub anglojęzyczne) i wyciągnij z niego dane do formatu JSON.

ZASADY:
1. Zwróć dokładnie jeden obiekt JSON o strukturze podanej niżej. Żadnego tekstu przed ani po nim, żadnych znaczników markdown.
2. Jeśli informacji nie ma w tekście, wpisz null (dla listy: []). Nie zgaduj i nie wymyślaj.
3. Nazwy, sygnatury i nazwiska kopiuj dosłownie z tekstu. Nie tłumacz ich i nie skracaj.
4. decision_date to data wydania TEGO orzeczenia (zwykle w nagłówku, np. "Dnia 5 sierpnia 2015 roku"), zapisana jako RRRR-MM-DD. Nie używaj daty zaskarżonego orzeczenia ani daty zdarzenia.
5. docket_number to sygnatura TEJ sprawy (np. "II Kp 127/15"). Sygnatury spraw powiązanych (np. postępowania prokuratorskiego "1 Ds 1391/14") wpisz do related_case.
6. document_type: dokładnie jedna z wartości: wyrok, wyrok odwoławczy, postanowienie, uzasadnienie, zarządzenie, decision, judgment, opinion, order, decree, ruling, sentence, brief, memorandum, other.
7. language: "pl" dla tekstu polskiego, "en" dla angielskiego.
8. applicant to strona, która złożyła wniosek lub środek zaskarżenia (np. "Prokurator Rejonowy", "obrońca oskarżonego"). Nie jest nim sędzia ani protokolant.
9. Wartości w rodzaju "---", "brak" lub puste miejsca oznaczają brak danych: wpisz null.
10. subject_matter: jedno zwięzłe zdanie (do 25 słów) o przedmiocie sprawy, bez cytowania całych akapitów.
11. operative_part.legal_basis: lista przepisów z sentencji, każdy jako osobny napis (np. "art. 98 § 2 kpk").

STRUKTURA:
{
  "document": {
    "document_type": "<patrz reguła 6>",
    "language": "<pl lub en>",
    "court": "<pełna nazwa sądu wydającego orzeczenie>",
    "division": "<wydział sądu>",
    "docket_number": "<sygnatura tej sprawy>",
    "decision_date": "<RRRR-MM-DD>",
    "presiding_judge": "<przewodniczący składu>",
    "applicant": "<wnioskodawca / skarżący>",
    "subject_matter": "<jedno zwięzłe zdanie>",
    "participants": {
      "court_clerk": "<protokolant>",
      "prosecutor": "<prokurator obecny na posiedzeniu>"
    },
    "related_case": {
      "docket_number": "<sygnatura sprawy powiązanej>",
      "authority": "<organ prowadzący sprawę powiązaną>"
    },
    "operative_part": {
      "decision": "<krótko: co sąd rozstrzygnął>",
      "legal_basis": ["<przepis>", "<przepis>"]
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
