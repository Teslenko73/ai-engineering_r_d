> **SYMULACJA — dane ilustracyjne.** Wygenerowane przez prawdziwy kod projektu, ale z *symulowanymi* modelami (`ModelZdalny-X`, `ModelLokalny-Y`) na *wymyślonych* dokumentach. Liczby nie opisują żadnego realnego modelu. Zastąp je własnymi wynikami z `python main.py`.

# Błędy przebiegu `lokalny_t07__v1`

Liczba błędnych pól: 33. Podział: inne sformułowanie / częściowa zgodność: 18, błędna wartość: 14, pominięte pole (null zamiast wartości): 1.

## 12 najpoważniejszych (pola krytyczne najpierw)

| # | Plik | Pole | Kategoria | Oczekiwano (golden) | Otrzymano (model) |
|---|---|---|---|---|---|
| 1 | doc0 | `document_type` | błędna wartość | wyrok | other |
| 2 | doc0 | `docket_number` | błędna wartość | II Kp 100/14 | 1 Ds 1391/14 |
| 3 | doc1 | `document_type` | błędna wartość | postanowienie | other |
| 4 | doc2 | `document_type` | błędna wartość | postanowienie | other |
| 5 | doc2 | `docket_number` | błędna wartość | I C 134/16 | 1 Ds 1391/14 |
| 6 | doc4 | `document_type` | błędna wartość | uzasadnienie | other |
| 7 | doc4 | `decision_date` | błędna wartość | 2018-01-21 | 2013-11-25 |
| 8 | doc6 | `document_type` | błędna wartość | postanowienie | other |
| 9 | doc6 | `decision_date` | błędna wartość | 2014-07-04 | 2013-11-25 |
| 10 | doc7 | `document_type` | błędna wartość | postanowienie | other |
| 11 | doc7 | `decision_date` | błędna wartość | 2015-10-09 | 2013-11-25 |
| 12 | doc8 | `docket_number` | błędna wartość | VII Ka 236/16 | 1 Ds 1391/14 |

Do raportu wybierz 3–5 przykładów i dla każdego opisz: **co zamiast czego** oraz **dlaczego** (np. model wziął datę zaskarżonego wyroku, pomylił sygnaturę sprawy powiązanej, sparafrazował nazwę sądu). Przyczynę ustalisz, czytając fragment dokumentu w `data/` oraz surową odpowiedź (`raw_response` dla `failed`).
