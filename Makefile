PY ?= python

.PHONY: run quick compare test install

run:        ## pełny eksperyment (experiments/default.json) + tabela porównawcza
	$(PY) main.py

quick:      ## szybki test: 2 pliki, 1 konfiguracja zdalna
	$(PY) main.py experiment --file quick

compare:    ## tabela porównawcza z istniejących wyników
	$(PY) main.py compare

test:       ## testy jednostkowe (bez internetu, bez kluczy)
	$(PY) -m pytest -q

install:
	$(PY) -m pip install -r requirements.txt
