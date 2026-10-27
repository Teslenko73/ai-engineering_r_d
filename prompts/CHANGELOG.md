# Changelog promptów

Wersje to pliki `prompts/v<N>.py`. Numer wersji jest zapisywany przy każdym wyniku (`meta.prompt_version`),
a w katalogu wyników widać go w nazwie przebiegu (`<konfiguracja>__v<N>`).

Kolumna **Zaobserwowano** uzupełnij po przebiegu eksperymentu: `python main.py compare`
(tabela w `results/comparison.md`) oraz `python main.py errors --run <przebieg>`.

---

## v1 – baseline

Pierwotny prompt projektu.

- 9 pól płaskich zgodnych z golden setem (`document_type`, `language`, `court`, `division`, `docket_number`,
  `decision_date`, `presiding_judge`, `applicant`, `subject_matter`).
- Ogólne zasady: zwróć JSON, wpisz `null` gdy brak danych, data jako RRRR-MM-DD.
- Bez przykładu, bez listy dozwolonych wartości `document_type`.
- Opisuje wyłącznie polskie orzeczenia.

---

## v2

Cel: ograniczyć spodziewane błędy z v1 i wypełnić zagnieżdżone pola schematu.
Przyczyny w tabeli to **hipotezy** sprzed pierwszego przebiegu; kolumna „Zaobserwowano” je potwierdza albo obala.

| Zmiana | Dlaczego (hipoteza) | Oczekiwany efekt | Zaobserwowano |
|---|---|---|---|
| Struktura rozszerzona o `participants`, `related_case`, `operative_part` (z listą `legal_basis`) | W v1 model nie znał pól zagnieżdżonych, więc nigdy ich nie wypełniał, choć schemat je ma | Pola zagnieżdżone są wypełniane; dokładność pól płaskich bez zmian | _do uzupełnienia_ |
| Reguła 4: `decision_date` to data wydania TEGO orzeczenia, nie zaskarżonego | Orzeczenia zawierają kilka dat (zaskarżone orzeczenie, zdarzenie); model może wybrać niewłaściwą | Mniej błędów w polu krytycznym `decision_date` | _do uzupełnienia_ |
| Reguła 5: sygnatura TEJ sprawy, powiązane trafiają do `related_case` | Tekst zawiera też sygnatury spraw powiązanych (np. `1 Ds 1391/14`), które łatwo pomylić z główną | Mniej pomyłek w `docket_number` | _do uzupełnienia_ |
| Reguła 6: jawna lista wartości `document_type` | Wartości spoza enum są zamieniane przez walidator na `other`, więc model powinien znać dozwolone wartości | Mniej `other`, trafniejszy `document_type` | _do uzupełnienia_ |
| Reguły 8 i 9: kim jest `applicant`, `---` oznacza brak danych | Protokolant i znaki `---` (placeholder w dokumencie) mogą zostać wzięte za wartości | Poprawniejsze `applicant` i `participants.prosecutor` | _do uzupełnienia_ |
| Reguła 10: `subject_matter` w jednym zdaniu (≤ 25 słów) | Długie opisy mogą obniżać podobieństwo tekstu względem golden setu i zużywają tokeny | Wyższy wynik fuzzy dla `subject_matter`, mniej tokenów wyjścia | _do uzupełnienia_ |
| Dodany wymyślony przykład (few-shot) | Pokazuje format oraz zachowanie dla pól nieobecnych w tekście (`null`, `[]`), co może zmniejszyć liczbę błędnych odpowiedzi | Mniej błędów formatu JSON i mniej niepoprawnych odpowiedzi | _do uzupełnienia_ |
| Prompt obejmuje też orzeczenia anglojęzyczne | W `data/` są też orzeczenia amerykańskie | Poprawne `language` i `document_type` dla tekstów angielskich | _do uzupełnienia_ |

Uwaga metodologiczna: przykład w v2 jest **wymyślony**. Nie wolno wstawiać do promptu fragmentów dokumentów
z golden setu, bo zawyżyłoby to wyniki ewaluacji (wyciek danych).

Koszt zmian: v2 jest dłuższy (ok. 1000 tokenów więcej na zapytanie), co zwiększa koszt i czas, szczególnie
dla modelu lokalnego na CPU. Ten koszt trzeba zestawić z poprawą dokładności w raporcie.
