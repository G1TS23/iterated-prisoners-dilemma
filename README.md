# Le dilemme du prisonnier itératif — tournoi Axelrod, IA comprise

Projet **M2 DEV — EFREI**. Pipeline ETL complet autour d'une simulation du
dilemme du prisonnier itératif : stratégies codées + agents IA locaux
(LM Studio), architecture médaillon, gold via dbt, dashboard Streamlit.

> Sujet complet : [`docs/SUJET.md`](docs/SUJET.md).

## Sommaire

- [1. Méthodologie](#1-méthodologie)
  - [Le jeu](#le-jeu)
  - [Architecture en médaillon](#architecture-en-médaillon)
  - [Étape 1 — Génération du tournoi](#étape-1--génération-du-tournoi)
  - [Étape 2 — Enrichissement silver](#étape-2--enrichissement-silver)
  - [Étape 3 — Couche gold (dbt) + dashboard](#étape-3--couche-gold-dbt--dashboard)
- [2. Organisation du dépôt](#2-organisation-du-dépôt)
- [3. Setup complet](#3-setup-complet)
- [4. Décisions du projet](#4-décisions-du-projet)
- [5. Livrables](#5-livrables)
- [6. Résultats](#6-résultats)

## 1. Méthodologie

### Le jeu

À chaque tour, 2 joueurs choisissent **simultanément** Coopérer (`C`) ou
Trahir (`D`). Matrice de gains classique (Axelrod) :

| | L'autre coopère | L'autre trahit |
|---|---|---|
| **Je coopère** | R = 3 | S = 0 (dupe) |
| **Je trahis** | T = 5 (tentation) | P = 1 (punition) |

`T > R > P > S` et `2R > T + S` — condition théorique du "vrai" dilemme
(sinon alterner C/D serait mieux que coopérer durablement).

### Architecture en médaillon

| Couche | Contenu | Format | Producteur |
|---|---|---|---|
| **Bronze** | tours bruts du tournoi | `data/bronze/turns_raw.parquet` | `src/simulate.py` |
| **Silver** | enrichi (mémoire, streaks, pardon...) | `data/silver/turns.parquet` | `src/clean_silver.py` |
| **Gold** | indicateurs métier | `data/gold/gold.duckdb` | dbt (`dbt/`) |

### Étape 1 — Génération du tournoi

Round-robin **avec auto-confrontation** (comme Axelrod) entre :
- **5 stratégies codées** (`src/strategies.py`) : `always_cooperate`,
  `always_defect`, `tit_for_tat`, `random`, `grim_trigger` — instantané,
  aucun appel réseau.
- **3 agents IA / personas** (`config/personas.yaml`) : `empathique`,
  `calculateur`, `rancunier` — chacun a un **équivalent codé** déclaré
  (`coded_equivalent`) pour comparer langage naturel vs règle explicite.
  Un seul modèle LM Studio les incarne tous les trois (la variable étudiée
  est le *prompt*, pas le modèle).

8 agents → `C(8+1, 2) = 36` matches (round-robin + auto-confrontation) ×
`N_TURNS` tours. Sortie **résumable** : `match_id` inclut le nombre de tours
(`..._t{N_TURNS}_r{repeat}`), donc changer `N_TURNS` entre deux runs ne mélange
pas des parties de longueurs différentes — il faut alors soit relancer
(nouveaux match_id, s'ajoutent aux anciens), soit `make clean-data` pour
repartir propre.

**Mémoire de l'agent IA** : résumé compact (`src/memory.py`), pas l'historique
complet — dernier coup adverse, taux de coopération adverse, streak de
trahisons, scores cumulés. Coût en tokens constant tour après tour (décision
du projet, cf. § 4).

**Sortie contrainte** : `{"move": "C"|"D", "justification": "..."}` (sortie
structurée LM Studio, repli en texte libre + regex si le moteur refuse le
schéma — `src/llm_client.py`, `src/llm_agent.py`, repris et éprouvé sur le
projet *Trivial Pursuit*).

### Étape 2 — Enrichissement silver

`src/clean_silver.py` ajoute, par ligne (perspective causale — seulement ce
qui était connu **avant** de décider) :

- `own_cum_score` / `opp_cum_score` : score cumulé
- `own_coop_rate` / `opp_coop_rate` : taux de coopération glissant
- `opponent_last_move`, `opponent_defection_streak`
- `forgave_this_turn` / `retaliated_this_turn` : a coopéré/trahi juste après
  avoir été trahi au tour précédent — **la mesure directe de "tendance à
  pardonner"** demandée par le sujet
- `round_outcome` : `mutual_coop` / `mutual_defect` / `exploited` / `exploiter`

### Étape 3 — Couche gold (dbt) + dashboard

`dbt build` construit :
`fct_turns` (faits, 1 ligne = match×tour×joueur) · `dim_agent` (type,
description, équivalent codé — seed `dbt/seeds/agent_meta.csv`) ·
`agg_agent_leaderboard` (score, coopération, pardon, riposte par agent) ·
`agg_matchup_matrix` (table croisée façon tournoi Axelrod) ·
`agg_cooperation_over_time` (taux de coopération par tour — détecte la
convergence/l'équilibre) · `agg_llm_vs_coded` (persona vs équivalent codé,
côte à côte).

Dashboard Streamlit (lecture seule) : classement, table croisée, coopération
dans le temps, IA vs codé, explorateur de parties (rejoue un match tour par
tour avec les justifications IA).

## 2. Organisation du dépôt

```
config/personas.yaml         3 personas IA versionnés (system prompt + équivalent codé)
src/strategies.py            5 stratégies codées + interface Agent commune
src/memory.py                résumé compact de l'historique pour le prompt IA
src/llm_client.py            client LM Studio (repris de Trivial Pursuit)
src/llm_agent.py             agent IA : persona + mémoire + parsing du coup
src/simulate.py              étape 1 -> bronze (tournoi, résumable)
src/clean_silver.py          étape 2 -> silver (colonnes dérivées)
src/common.py                chemins, matrice de gains, .env
dbt/                         projet dbt-duckdb (staging + marts + tests)
dashboard/streamlit_app.py   rapport interactif
docs/SUJET.md                sujet complet
data/{bronze,silver,gold}/   data lake (gitignoré)
Makefile                     orchestration : make all
```

## 3. Setup complet

### Pré-requis

- **Python 3.13** (dbt-core ne supporte pas encore 3.14)
- **LM Studio** — https://lmstudio.ai, avec le modèle voulu déjà téléchargé
  (`lms get ...`) et le serveur démarré (`lms server start`)

### Installation

```bash
git clone <url> && cd iterated-prisoners-dilemma
cp .env.example .env          # ajuster LLM_MODELS si besoin
make install                  # venv + pip + dbt deps + hook pre-commit
```

### Exécution

```bash
make simulate                 # étape 1 : tournoi complet (voir budget ci-dessous)
make clean-silver             # étape 2
make build                    # étape 3a : dbt (ferme le dashboard avant si ouvert -- verrou DuckDB)
make dashboard                # étape 3b
```

Test à blanc rapide (stratégies codées seules, sans LM Studio) :
`make simulate ARGS="--no-llm --n-turns 20"`.
Avec IA sur un sous-ensemble : `make simulate ARGS="--n-turns 15 --max-matches 5"`.

### Budget de calcul

21 des 36 matches impliquent au moins un agent IA (15 IA-vs-codé, 6 IA-vs-IA
dont 3 auto-confrontations). À `N_TURNS=100` : ~21 × 100 × ~1,5 appel LLM
moyen ≈ 3000 appels — de l'ordre de 20-30 min sur un petit modèle 2-3B en
local (mesuré : ~10 s/match à `N_TURNS=15`, donc ~1 min/match à 100 tours en
extrapolation prudente). Gérable en une session, pas besoin de `caffeinate`
overnight comme sur Trivial Pursuit.

## 4. Décisions du projet

- **Runtime IA** : LM Studio (infra réutilisée de Trivial Pursuit — SDK,
  sortie structurée + repli, hook pre-commit, pattern Makefile).
- **Tours par partie** : 100 (`N_TURNS` dans `.env`) — assez pour observer un
  comportement stable, budget calcul raisonnable.
- **Agents IA** : 3 personas (empathique / calculateur / rancunier), chacun
  avec un équivalent codé pour comparaison directe (`agg_llm_vs_coded`).
- **Mémoire du prompt** : résumé compact plutôt qu'historique complet — coût
  en tokens constant, tenable sur 100+ tours (`src/memory.py`).
- **Système d'évaluation des personas** (demandé par le sujet) : `is_parsable`
  (taux de sorties reconnues comme C/D) + comparaison directe à l'équivalent
  codé dans `agg_llm_vs_coded` (écart de taux de coopération/pardon/riposte =
  mesure de fidélité du persona à sa description).

## 5. Livrables

1. Script de génération — `src/simulate.py` (+ `src/llm_agent.py`, `src/memory.py`).
2. Architecture bronze/silver/gold — ce dépôt.
3. Analyse finale Streamlit — `dashboard/streamlit_app.py`.

## 6. Résultats

*(à compléter après le run complet — voir `make simulate` puis les onglets du dashboard)*
