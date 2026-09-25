# Pipeline complet : make all
# Python : développé en 3.13 ; 3.12 à 3.14 vérifiés en CI. `make ... PYTHON=python3` si python3.13 est absent.
PYTHON ?= python3.13
VENV   := .venv
PY     := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
DBT    := $(VENV)/bin/dbt

# Toutes les cibles dbt font `cd dbt` avant d'invoquer dbt : le profil est donc
# cherché dans le dossier courant après ce cd, d'où "." et non "dbt".
export DBT_PROFILES_DIR := .
export DBT_GOLD_DB      := ../data/gold/gold.duckdb
export SILVER_DIR        := ../data/silver

.PHONY: help venv install hooks simulate clean-silver build build-full test dashboard all clean-data

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Crée le virtualenv
	$(PYTHON) -m venv $(VENV)

install: venv hooks ## Installe les dépendances + hook pre-commit
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

hooks: ## Active le hook pre-commit versionné (.githooks/)
	git config core.hooksPath .githooks
	chmod +x .githooks/*

simulate: ## Étape 1 : tournoi (stratégies codées + agents IA) -> data/bronze/turns_raw.parquet
	$(PY) src/simulate.py $(ARGS)

clean-silver: ## Étape 2 : enrichissement -> data/silver/turns.parquet
	$(PY) src/clean_silver.py

build: ## Étape 3a : construction de la couche gold avec dbt
	cd dbt && $(abspath $(DBT)) build

build-full: ## build --full-refresh (après un changement de colonnes d'un seed)
	cd dbt && $(abspath $(DBT)) build --full-refresh

test: ## Tests dbt seuls
	cd dbt && $(abspath $(DBT)) test

dashboard: ## Étape 3b : dashboard Streamlit (lecture seule de gold)
	$(VENV)/bin/streamlit run dashboard/streamlit_app.py

all: simulate clean-silver build ## Pipeline complet (hors dashboard)

clean-data: ## Supprime bronze/silver/gold, y compris les données LIVRÉES (`git checkout -- data` les restaure)
	rm -rf data/bronze/* data/silver/* data/gold/*
	@touch data/bronze/.gitkeep data/silver/.gitkeep data/gold/.gitkeep
