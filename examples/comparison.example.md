> **SYMULACJA — dane ilustracyjne.** Wygenerowane przez prawdziwy kod projektu, ale z *symulowanymi* modelami (`ModelZdalny-X`, `ModelLokalny-Y`) na *wymyślonych* dokumentach. Liczby nie opisują żadnego realnego modelu. Zastąp je własnymi wynikami z `python main.py`.

## Porównanie przebiegów

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

## Dokładność per pole (golden set)

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
