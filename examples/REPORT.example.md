> **SYMULACJA — dane ilustracyjne.** Wygenerowane przez prawdziwy kod projektu, ale z *symulowanymi* modelami (`ModelZdalny-X`, `ModelLokalny-Y`) na *wymyślonych* dokumentach. Liczby nie opisują żadnego realnego modelu. Zastąp je własnymi wynikami z `python main.py`.

# Raport porównawczy: ekstrakcja danych z orzeczeń sądowych (PRZYKŁAD)

## 1. Cel i dane

Zadanie: zamienić orzeczenia sądowe (PDF) na JSON zgodny ze schematem, a następnie wybrać model i wersję promptu do produkcji.
Dane: _N_ dokumentów w `data/`, w tym 10 oznaczonych ręcznie (golden set). Dokumenty różnią się długością, jakością tekstu i językiem (polskie i anglojęzyczne). Schemat: 9 pól płaskich (w tym enum `document_type`, `language`) oraz 3 obiekty zagnieżdżone (`participants`, `related_case`, `operative_part` z listą `legal_basis`).

## 2. Metodyka

- **Modele:** model zdalny (API, structured output `json_schema`) i model lokalny (Ollama). _Wpisz konkretne modele._
- **Prompty:** v1 (baseline) i v2 (doprecyzowane reguły, pola zagnieżdżone, przykład). Zmiany: `prompts/CHANGELOG.md`.
- **Próbkowanie:** T=0 (greedy) oraz T=0,7 (top_p=0,9) dla każdego modelu.
- **Walidacja:** każda odpowiedź jest sprawdzana schematem Pydantic. Odpowiedź niepoprawna dostaje **jedną** próbę poprawy (z błędem w prompcie), potem status `failed`. Timeout i ponowienia sieciowe są w konfiguracji klienta.
- **Metryki:** dokładność per pole na golden secie (pola krytyczne `document_type`, `language`, `decision_date`, `docket_number`: dokładne dopasowanie po normalizacji; pozostałe: podobieństwo tekstu ≥ 0,8), % odpowiedzi poprawnych (po schemacie), latency p50/p95 (suma po próbach, na dokument), koszt na 1000 dokumentów (średnia z przebiegu x 1000; modele lokalne: bez opłat API).
- **Uwaga o próbie:** golden set ma 10 dokumentów, więc **jeden dokument to 10 punktów procentowych**. Różnice rzędu 10 p.p. mieszczą się w szumie.

## 3. Wyniki

### Porównanie przebiegów

| Model | Provider | Prompt | Próbkowanie | Reguły | Dok. | Pola krytyczne OK | Śr. wynik JSON | Format poprawny | Bez poprawki | Wypełnione pola | Latency p50 [s] | Latency p95 [s] | Koszt / 1000 dok. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ModelLokalny-Y | ollama | v1 | T=0 (greedy) | nie | 10 | 40.0% | 76.8% | 90.0% | 50.0% | 96% | 47.93 | 93.48 | $0 (lokalnie) |
| ModelLokalny-Y | ollama | v1 | T=0.7, top_p=0.9 | nie | 10 | 20.0% | 74.2% | 100.0% | 80.0% | 99% | 45.26 | 77.52 | $0 (lokalnie) |
| ModelLokalny-Y | ollama | v2 | T=0 (greedy) | nie | 10 | 20.0% | 75.5% | 90.0% | 80.0% | 98% | 54.04 | 96.42 | $0 (lokalnie) |
| ModelLokalny-Y | ollama | v2 | T=0.7, top_p=0.9 | nie | 10 | 50.0% | 83.0% | 100.0% | 90.0% | 97% | 56.84 | 84.27 | $0 (lokalnie) |
| ModelZdalny-X | openrouter | v1 | T=0 (greedy) | nie | 10 | 60.0% | 90.1% | 100.0% | 100.0% | 99% | 2.16 | 2.88 | $0.25 |
| ModelZdalny-X | openrouter | v1 | T=0.7, top_p=0.9 | nie | 10 | 60.0% | 89.6% | 100.0% | 80.0% | 98% | 2.58 | 5.12 | $0.30 |
| ModelZdalny-X | openrouter | v2 | T=0 (greedy) | nie | 10 | 80.0% | 96.8% | 100.0% | 100.0% | 100% | 1.99 | 3.24 | $0.56 |
| ModelZdalny-X | openrouter | v2 | T=0.7, top_p=0.9 | nie | 10 | 90.0% | 95.5% | 100.0% | 100.0% | 100% | 2.24 | 3.80 | $0.56 |

### Dokładność per pole (golden set)

Pola krytyczne (`strict`): dokładne dopasowanie po normalizacji. Pozostałe (`fuzzy`): podobieństwo tekstu ≥ próg.

| Przebieg | document_type | language | court | division | docket_number | decision_date | presiding_judge | applicant | subject_matter |
|---|---|---|---|---|---|---|---|---|---|
| ModelLokalny-Y / v1 / T=0 (greedy) | 70% | 90% | 60% | 90% | 80% | 50% | 90% | 60% | 60% |
| ModelLokalny-Y / v1 / T=0.7, top_p=0.9 | 40% | 100% | 70% | 100% | 70% | 50% | 100% | 30% | 10% |
| ModelLokalny-Y / v2 / T=0 (greedy) | 50% | 90% | 80% | 90% | 80% | 50% | 90% | 60% | 60% |
| ModelLokalny-Y / v2 / T=0.7, top_p=0.9 | 70% | 100% | 90% | 100% | 80% | 70% | 100% | 60% | 20% |
| ModelZdalny-X / v1 / T=0 (greedy) | 70% | 100% | 70% | 100% | 100% | 80% | 100% | 90% | 50% |
| ModelZdalny-X / v1 / T=0.7, top_p=0.9 | 70% | 100% | 90% | 100% | 100% | 90% | 100% | 80% | 30% |
| ModelZdalny-X / v2 / T=0 (greedy) | 100% | 100% | 80% | 100% | 90% | 90% | 100% | 100% | 90% |
| ModelZdalny-X / v2 / T=0.7, top_p=0.9 | 90% | 100% | 80% | 100% | 100% | 100% | 100% | 100% | 40% |

Objaśnienia. **Jakość treści** (liczona na dokumentach golden setu): **Pola krytyczne OK** = odsetek dokumentów, w których wszystkie pola krytyczne są poprawne; **Śr. wynik JSON** = średnia po wszystkich polach. **Format** (liczony na wszystkich dokumentach przebiegu): **Format poprawny** = odpowiedź przeszła schemat i kontrolę treści (nie jest pusta ani nie zawiera szablonów), po co najwyżej jednej poprawce, reszta ma status `failed`; to NIE znaczy, że wartości są dobre; **Bez poprawki** = od razu; **Wypełnione pola** = średni odsetek wypełnionych pól głównych (w nawiasie: dokumenty z szablonami z promptu). **Koszt / 1000 dok.** = średni koszt dokumentu x 1000 (modele lokalne: bez kosztu API). Wysoki „Format poprawny” przy niskich polach krytycznych oznacza model, który trzyma format, ale myli treść.


## 4. Wpływ wersji promptu

Dla modelu zdalnego (T=0) prompt v2 podniósł odsetek dokumentów z poprawnymi polami krytycznymi z 60% do 80%, a średni wynik JSON z 90% do 97%. Dla modelu lokalnego (T=0): pola krytyczne 40% → 20%, średni wynik JSON 77% → 76%. Koszt zdalnego: $0.25 → $0.56 na 1000 dokumentów (dłuższy prompt), latency p50 modelu lokalnego: 48 s → 54 s. _W prawdziwym raporcie wskaż, które zmiany z changelogu zadziałały (por. kolumnę „Zaobserwowano”)._

## 5. Rozbiór błędów

Przykłady z przebiegu `lokalny_t00__v1` (pełna lista: `python main.py errors --run <przebieg>`).

**1. `decision_date`, plik `doc0`**

- Oczekiwano: `2014-01-01`
- Otrzymano: `2013-11-25`
- Dlaczego: model wziął datę **wcześniejszego orzeczenia** wspomnianego w uzasadnieniu zamiast daty z nagłówka „Dnia ...”. Dwie daty w tekście, brak wskazówki, którą wybrać.

**2. `docket_number`, plik `doc4`**

- Oczekiwano: `II K 168/18`
- Otrzymano: `1 Ds 1391/14`
- Dlaczego: model wpisał sygnaturę **sprawy powiązanej** (postępowanie prokuratorskie) zamiast sygnatury tej sprawy z nagłówka.

**3. `document_type`, plik `doc2`**

- Oczekiwano: `postanowienie`
- Otrzymano: `other`
- Dlaczego: model zwrócił wartość spoza listy (np. „Postanowienie karne”), którą walidator zamienia na `other`. Prompt v1 nie podaje dozwolonych wartości.

**4. `applicant`, plik `doc0`**

- Oczekiwano: `obrońca oskarżonego`
- Otrzymano: `None`
- Dlaczego: model pomylił skarżącego z inną rolą w dokumencie (protokolant) albo zostawił pole puste, choć wnioskodawca jest wymieniony.

**5. `subject_matter`, plik `doc9`**

- Oczekiwano: `wniosek o zasiedzenie nieruchomości`
- Otrzymano: `None`
- Dlaczego: model dopisał długie rozwinięcie. Treść jest poprawna, ale wynik podobieństwa tekstu spada poniżej progu 0,8 (**błąd metryki, nie modelu**).

_W symulacji przyczyny są znane z konstrukcji danych. W prawdziwym raporcie ustal je, czytając fragment dokumentu i surową odpowiedź modelu._

## 6. Wybór do produkcji

Wybieram **ModelZdalny-X, prompt v2, T=0**: 80% dokumentów z kompletem poprawnych pól krytycznych, 100% odpowiedzi poprawnych, latency p95 3.2 s, koszt ok. $0.56 za 1000 dokumentów. Wariant T=0,7 dał 90% na polach krytycznych, ale różnica to jeden dokument (szum), a T=0 daje powtarzalne wyniki, więc jest bezpieczniejszy. Model lokalny (20% na polach krytycznych, p50 ok. 54 s na dokument) nie nadaje się jako główny, ale jest uzasadnioną opcją tam, gdzie dokumenty nie mogą opuszczać infrastruktury.

**Kiedy zmieniłbym decyzję:** (1) przy wymogu prywatności danych: model lokalny większy niż testowany, z regułami (regex) dla sygnatury i daty; (2) przy wolumenie rzędu milionów dokumentów, gdy koszt zdalnego przestaje być pomijalny; (3) po rozszerzeniu golden setu (np. do 50 dokumentów), jeśli ranking konfiguracji się zmieni; (4) gdy pojawi się tańszy model zdalny o podobnej dokładności.

## 7. Ograniczenia

- Mały golden set (10 dokumentów): wyniki mają szeroki przedział niepewności.
- Pola zagnieżdżone nie są oceniane, bo golden set ich nie zawiera. Warto je dopisać do golden setu.
- Metryka tekstowa karze poprawne, ale dłuższe sformułowania (por. błąd z `subject_matter`).
- Koszt lokalnego modelu pominięto (sprzęt, prąd).
