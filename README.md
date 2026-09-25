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
- [6. Résultats](#6-résultats--run-du-11092026)
- [7. Limites méthodologiques](#7-limites-méthodologiques)

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

Diagramme du pipeline et modèle dimensionnel : [`docs/architecture.md`](docs/architecture.md).

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
docs/architecture.md         diagramme du pipeline + modèle dimensionnel
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
- **Système d'évaluation des personas/prompts** (demandé par le sujet), 3
  niveaux : (1) `is_parsable` — la sortie est-elle exploitable ? ;
  (2) `agg_llm_vs_coded` — écart de *résultat* (score, coopération, pardon)
  avec l'équivalent codé ; (3) **`agg_persona_fidelity`** — écart de
  *décision* : chaque coup de l'IA est comparé à celui que la règle codée aurait
  joué avec exactement le même historique (rejeu, sans appel LLM en plus).
  Le seed `agent_meta.csv` distingue les équivalents `stricte` (calculateur,
  rancunier) de l'équivalent `approchee` (empathique, volontairement généreux).

## 5. Livrables

1. Script de génération — `src/simulate.py` (+ `src/llm_agent.py`, `src/memory.py`).
2. Architecture bronze/silver/gold — ce dépôt.
3. Analyse finale Streamlit — `dashboard/streamlit_app.py`.

## 6. Résultats — run du 11/09/2026

**Config** : 36 matches (round-robin + auto-confrontation, 8 agents) × 100
tours = 7200 tours, 14 400 lignes en gold (2/tour). Run complet en 22 min 29 s.
`temperature=0.2`, seed fixe.

### Classement (`marts.agg_agent_leaderboard`)

| agent | type | score moyen/tour | coopération | pardon | riposte |
|---|---|---:|---:|---:|---:|
| grim_trigger | codé | **2,77** | 78,3 % | 0 % | 100 % |
| tit_for_tat | codé | 2,68 | 83,0 % | 0 % | 100 % |
| persona_empathique | IA | 2,54 | 99,1 % | 95,8 % | 4,2 % |
| always_cooperate | codé | 2,49 | 100 % | 100 % | 0 % |
| persona_calculateur | IA | 2,43 | 83,1 % | 35,8 % | 64,2 % |
| always_defect | codé | 2,39 | 0 % | 0 % | 100 % |
| persona_rancunier | IA | 2,29 | 53,8 % | 19,2 % | 80,8 % |
| random | codé | 2,17 | 49,6 % | 51,1 % | 48,9 % |

**Constat n°1 — résultat d'Axelrod reproduit.** Les deux stratégies « nice but
firm » (coopératives par défaut, mais qui ne se laissent jamais exploiter
deux fois) dominent : `grim_trigger` et `tit_for_tat` terminent 1ʳᵉ et 2ᵉ,
devant `always_cooperate` (exploitée sans jamais se venger) et `always_defect`
(punie par tout le monde après le premier tour). C'est exactement le résultat
historique d'Axelrod (1981) reproduit 40 ans plus tard, IA comprise.

**Constat n°2 — le meilleur agent IA (`persona_empathique`) bat deux
stratégies codées classiques**, `always_cooperate` et `always_defect` — la
coopération générale « avec pardon sélectif » d'un LLM peut donc surpasser des
règles fixes simples, sans les égaler face aux meilleures stratégies
réactives strictes.

### Persona IA vs équivalent codé (`marts.agg_llm_vs_coded`)

| persona | équivalent codé | score persona | score code | coop persona | coop code |
|---|---|---:|---:|---:|---:|
| persona_empathique | tit_for_tat | 2,54 | 2,68 | 99,1 % | 83,0 % |
| persona_calculateur | tit_for_tat | 2,43 | 2,68 | 83,1 % | 83,0 % |
| persona_rancunier | grim_trigger | 2,29 | 2,77 | 53,8 % | 78,3 % |

**Constat n°3 — aucune persona ne reproduit exactement son équivalent codé,
et le verdict dépend du niveau de mesure.** On a deux lectures complémentaires :

*Niveau résultat* (table ci-dessus) : `persona_rancunier` s'écarte le plus de
`grim_trigger` (-0,48 pt/tour, 53,8 % de coopération contre 78,3 %).

*Niveau décision* (`marts.agg_persona_fidelity` — on rejoue chaque décision de
l'IA dans la règle codée avec le même historique) :

| persona | équivalent | fidélité | riposte respectée* | coopération respectée** |
|---|---|---:|---:|---:|
| persona_rancunier | grim_trigger (stricte) | **91,4 %** | 84,7 % | 99,5 % |
| persona_calculateur | tit_for_tat (stricte) | 90,3 % | **64,2 %** | 99,3 % |
| persona_empathique | tit_for_tat (approchée) | 84,6 % | 4,2 % | 99,7 % |

\* part des tours où la règle impose de trahir et où le persona trahit bien.
\*\* idem pour coopérer.

**Ce que ça change à la lecture** (et corrige une première interprétation
fondée uniquement sur les agrégats) :
- Toutes les personas sont quasi parfaites sur ce qui est *facile* — coopérer
  quand la règle l'exige (≥ 99 %). L'infidélité se concentre **entièrement sur
  la riposte** : c'est la seule chose qu'un LLM 3B applique mal.
- Décision par décision, `persona_rancunier` est en fait la **plus fidèle** (91 %),
  et non la moins : elle n'échoue à ne pas pardonner que dans ~15 % des tours
  où la règle l'impose (pire face à `always_defect` : 75 % de fidélité —
  elle recoopère face à un adversaire qui n'a jamais coopéré).
- `persona_calculateur`, censé être un donnant-donnant strict, est celui qui
  **rate le plus la riposte** (36 % des trahisons non sanctionnées).
- `persona_empathique` n'est pas une imitation ratée de TFT : c'est une variante
  volontairement généreuse (riposte 4 %, pardon 96 %), et elle est la meilleure IA.
- Pourquoi le rancunier perd-il autant en score (-0,48) avec seulement ~15 %
  d'écart de décision ? **Hypothèse non vérifiée causalement** : la règle grim est
  *absorbante* — un seul pardon à tort change la suite de la partie — donc de
  petites erreurs de décision s'amplifient en grosses erreurs de trajectoire.

**Réciprocité** (`marts.agg_reciprocity`, corrélation entre mon coup au tour t
et le coup adverse au tour t-1) : `tit_for_tat` 1,00 · `grim_trigger` 0,84 ·
`persona_calculateur` 0,74 · `persona_rancunier` 0,59 · `persona_empathique` 0,17 ·
`random` −0,03 (les agents à comportement constant n'ont pas de corrélation
définie). Lecture : les personas IA sont **réactives mais moins mécaniquement**
que les règles codées, dans l'ordre attendu (calculateur > rancunier > empathique).

**Limite observée** : le schéma de sortie structurée autorise un champ
`justification` optionnel, quasiment jamais rempli spontanément par le modèle
(il ne renvoie que `{"move": "..."}`) — on n'a donc pas le raisonnement
explicite de ces incohérences. Piste pour une itération suivante : rendre
`justification` obligatoire dans le schéma.

**Fiabilité du parsing** : `is_parsable = 100 %` sur les 2700 réponses IA
(900 par persona) — la sortie structurée LM Studio n'a jamais nécessité de
repli en texte libre sur ce run (contrairement à `phi-3.5-mini-instruct` dans
le projet Trivial Pursuit).

### Comportement émergent / équilibre de Nash (`marts.agg_cooperation_over_time`)

Taux de coopération sur les 10 premiers tours vs les 10 derniers :

| agent | type | début | fin | tendance |
|---|---|---:|---:|---|
| persona_empathique | IA | 95,6 % | **98,9 %** | converge vers la coopération totale |
| tit_for_tat | codé | 84,4 % | 85,6 % | stable, équilibre coopératif |
| random | codé | 51,1 % | 54,4 % | stable (bruit) |
| grim_trigger | codé | 83,3 % | 77,8 % | légère érosion |
| persona_calculateur | IA | 91,1 % | 82,2 % | dérive vers plus de trahison |
| persona_rancunier | IA | 60,0 % | 52,2 % | dérive vers plus de trahison |

L'horizon est fini et connu (100 tours) : la théorie des jeux prédit par
récurrence à rebours que la trahison mutuelle est l'équilibre de Nash. On
observe les deux issues en parallèle sur le même tournoi : `persona_empathique`
et `tit_for_tat` **convergent vers un équilibre coopératif stable** (comme
dans l'expérience d'Axelrod), tandis que `persona_calculateur` et
`persona_rancunier` **dérivent vers la prédiction théorique** (plus de
trahison en fin de partie) — sans jamais l'atteindre complètement. Aucun
agent codé ni IA ne bascule dans la trahison systématique prédite par la
récurrence à rebours pure.

### Conclusion générale

1. **Le résultat d'Axelrod se reproduit** : les stratégies réactives et
   fermes (`grim_trigger`, `tit_for_tat`) dominent le tournoi, 40 ans après
   l'expérience originale.
2. **L'IA peut égaler des règles simples sans les dépasser** : le meilleur
   agent IA bat 2 stratégies codées basiques mais reste loin des meilleures
   stratégies réactives strictes.
3. **Les personas en langage naturel approximent leur règle sans l'appliquer
   mécaniquement — et c'est la *riposte* qui leur échappe** : ≥ 99 % de
   fidélité pour coopérer quand il le faut, mais 64 % (calculateur) à 85 %
   (rancunier) pour sanctionner quand il le faut. C'est la mesure directe du
   « système d'évaluation des prompts » demandé par le sujet (`agg_persona_fidelity`).
4. **Le comportement émergent diverge selon l'agent** : certains convergent
   vers la coopération stable (comme Axelrod), d'autres dérivent vers la
   prédiction théorique de trahison — sur le même tournoi, les deux
   dynamiques coexistent.

## 7. Limites méthodologiques

- **1 partie par paire** (`N_REPEATS=1`) : aucune barre d'erreur. Les paires
  impliquant `random` ou un LLM (température 0,2) sont stochastiques — un
  classement serré (ex. `persona_calculateur` 2,43 vs `always_defect` 2,39) ne
  doit pas être sur-interprété. Piste : `N_REPEATS≥5` et intervalles de confiance.
- **Un seul modèle (3B, Q4)** incarne les 3 personas : on mesure l'effet du
  *prompt*, pas celui du modèle. Ce que fait un modèle plus gros reste ouvert.
- **Réciprocité ↔ score calculée sur 6 agents** seulement : indicatif, pas
  une corrélation statistiquement exploitable.
- **`justification` quasi jamais remplie** : le schéma JSON la laisse optionnelle,
  le modèle ne renvoie que `{"move": ...}` — on n'a pas le raisonnement derrière
  les incohérences. Piste : la rendre obligatoire.
- **Comptage `n_matches` du classement** : un match d'auto-confrontation compte
  pour 1 match mais ses deux sièges contribuent aux tours de l'agent (d'où
  900 tours joués pour 8 matches ; toutes les métriques sont calculées au
  niveau ligne, donc non affectées).
- **Fidélité mesurée sur les équivalents `stricte` seulement** pour être
  interprétable ; `random` n'a pas de « coup attendu » déterministe.
- **Horizon non communiqué** : les agents IA ne savent pas combien de tours
  restent — l'effet d'horizon (trahison de fin de partie) n'est donc pas testé.
- **Artefact de prompt au 1er tour du run publié** : `memory.py` écrivait
  littéralement « Tour 1/N » (placeholder jamais remplacé). Corrigé dans le
  code après le run ; les données publiées ont été générées avec l'ancien
  libellé. Ne concerne que le 1er tour de chaque partie IA ; effet non mesuré.
