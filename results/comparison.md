## Porównanie przebiegów

| Model | Provider | Prompt | Próbkowanie | Reguły | Dok. | Poprawne | Bez poprawki | Pola krytyczne OK | Śr. wynik JSON | Latency p50 [s] | Latency p95 [s] | Koszt / 1000 dok. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-0.6B | local | v1 | T=0 (greedy) | nie | 10 | 70.0% | 70.0% | 0.0% | 38.7% | 259.17 | 600.63 | $0 (lokalnie) |
| Qwen/Qwen3-0.6B | local | v1 | T=0.6, top_p=0.95, thinking | nie | 10 | 100.0% | 100.0% | 0.0% | 54.2% | 360.86 | 499.70 | $0 (lokalnie) |
| Qwen/Qwen3-0.6B | local | v1 | T=0.7, top_p=0.8 | nie | 10 | 90.0% | 90.0% | 0.0% | 46.4% | 256.12 | 461.98 | $0 (lokalnie) |
| Qwen/Qwen3-0.6B | local | v2 | T=0 (greedy) | nie | 10 | 90.0% | 90.0% | 0.0% | 42.8% | 210.78 | 461.32 | $0 (lokalnie) |
| Qwen/Qwen3-0.6B | local | v2 | T=0.6, top_p=0.95, thinking | nie | 10 | 100.0% | 100.0% | 0.0% | 46.5% | 331.65 | 487.54 | $0 (lokalnie) |
| Qwen/Qwen3-0.6B | local | v2 | T=0.7, top_p=0.8 | nie | 10 | 80.0% | 80.0% | 0.0% | 35.2% | 214.02 | 600.48 | $0 (lokalnie) |
| z-ai/glm-5.2 | openrouter | v1 | T=0 (greedy) | nie | 40 | 92.5% | 85.0% | 60.0% | 76.8% | 3.14 | 7.87 | $4.43 |
| z-ai/glm-5.2 | openrouter | v1 | T=0.7, top_p=0.9 | nie | 40 | 97.5% | 72.5% | 70.0% | 77.1% | 3.12 | 7.95 | $3.93 |
| z-ai/glm-5.2 | openrouter | v2 | T=0 (greedy) | nie | 40 | 95.0% | 67.5% | 40.0% | 71.8% | 3.61 | 7.78 | $5.27 |
| z-ai/glm-5.2 | openrouter | v2 | T=0.7, top_p=0.9 | nie | 40 | 85.0% | 72.5% | 40.0% | 58.4% | 3.83 | 8.56 | $4.52 |

## Dokładność per pole (golden set)

Pola krytyczne (`strict`): dokładne dopasowanie po normalizacji. Pozostałe (`fuzzy`): podobieństwo tekstu ≥ próg.

| Przebieg | document_type | language | court | division | docket_number | decision_date | presiding_judge | applicant | subject_matter | participants | related_case | operative_part |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen/Qwen3-0.6B / v1 / T=0 (greedy) | 20% | 60% | 20% | 30% | 60% | 0% | 40% | 10% | 10% | 0% | 40% | 0% |
| Qwen/Qwen3-0.6B / v1 / T=0.6, top_p=0.95, thinking | 20% | 90% | 20% | 50% | 60% | 30% | 60% | 0% | 0% | 20% | 10% | 0% |
| Qwen/Qwen3-0.6B / v1 / T=0.7, top_p=0.8 | 20% | 80% | 20% | 40% | 60% | 0% | 40% | 20% | 10% | 10% | 10% | 0% |
| Qwen/Qwen3-0.6B / v2 / T=0 (greedy) | 10% | 80% | 30% | 40% | 50% | 10% | 40% | 0% | 0% | 0% | 0% | 0% |
| Qwen/Qwen3-0.6B / v2 / T=0.6, top_p=0.95, thinking | 10% | 80% | 30% | 40% | 40% | 30% | 40% | 0% | 0% | 20% | 10% | 0% |
| Qwen/Qwen3-0.6B / v2 / T=0.7, top_p=0.8 | 0% | 60% | 20% | 30% | 40% | 0% | 30% | 0% | 0% | 0% | 10% | 0% |
| z-ai/glm-5.2 / v1 / T=0 (greedy) | 70% | 90% | 80% | 70% | 90% | 80% | 70% | 70% | 10% | 70% | 90% | 10% |
| z-ai/glm-5.2 / v1 / T=0.7, top_p=0.9 | 90% | 90% | 80% | 70% | 90% | 70% | 70% | 60% | 20% | 70% | 90% | 30% |
| z-ai/glm-5.2 / v2 / T=0 (greedy) | 50% | 90% | 80% | 70% | 80% | 80% | 60% | 50% | 20% | 80% | 80% | 20% |
| z-ai/glm-5.2 / v2 / T=0.7, top_p=0.9 | 50% | 70% | 70% | 60% | 60% | 70% | 30% | 40% | 30% | 60% | 60% | 20% |

Objaśnienia: **Poprawne** = odpowiedź zwalidowana po schemacie (po co najwyżej jednej próbie poprawy), reszta ma status `failed`; **Bez poprawki** = zwalidowana od razu; **Pola krytyczne OK** = odsetek dokumentów, w których wszystkie pola krytyczne są poprawne; **Koszt / 1000 dok.** = średni koszt dokumentu x 1000 (modele lokalne: bez kosztu API).
