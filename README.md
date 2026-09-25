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
- [6. Résultats](#6-résultats--run-du-25092026-5-répétitionspaire)
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

## 6. Résultats — run du 25/09/2026 (5 répétitions/paire)

**Config** : 180 matches (36 paires × `N_REPEATS=5`, résumable — les 36 parties
`r1` du run du 11/09 ont été réutilisées, seules `r2`-`r5` ont été générées) ×
100 tours = 36 000 lignes en gold. Run des 144 nouveaux matches en 1h13.
`temperature=0.2`, seed fixe.

> Ce run **remplace** celui du 11/09 (une seule répétition), qui souffrait
> justement du problème signalé dans ses propres limites : un classement serré
> issu d'un seul tirage par paire ne se tient pas. Deux agents changent de
> rang une fois le bruit moyenné — comparaison directe ci-dessous.

### Écart entre le run à 1 répétition (11/09) et à 5 répétitions (25/09)

| agent | rang (1 rép.) | score (1 rép.) | rang (5 rép.) | score (5 rép.) | Δ rang | Δ score |
|---|---:|---:|---:|---:|---:|---:|
| grim_trigger | 1 | 2,77 | 1 | 2,70 | = | −0,07 |
| tit_for_tat | 2 | 2,68 | 3 | 2,58 | ↓1 | −0,10 |
| persona_empathique | 3 | 2,54 | 4 | 2,51 | ↓1 | −0,03 |
| always_cooperate | 4 | 2,49 | 5 | 2,51 | ↓1 | +0,02 |
| **persona_calculateur** | **5** | **2,43** | **2** | **2,60** | **↑3** | **+0,17** |
| always_defect | 6 | 2,39 | 7 | 2,40 | ↓1 | +0,01 |
| **persona_rancunier** | **7** | **2,29** | **6** | **2,43** | **↑1** | **+0,14** |
| random | 8 | 2,17 | 8 | 2,15 | = | −0,02 |

Seuls le 1ᵉʳ (`grim_trigger`) et le dernier (`random`) sont stables — le reste
du classement bouge d'au moins un rang. `persona_calculateur` est le
changement le plus net (+3 rangs, +0,17 pt/tour). **Cause identifiée, pas
supposée** : sur les 8 matches de `persona_calculateur` au run à 1 répétition,
7 sont à 3,00 pt/tour pile (coopération mutuelle parfaite, y compris
l'auto-confrontation) et 1 seul dévie — `persona_calculateur` vs
`persona_rancunier`, à 1,06 pt/tour, une spirale de trahisons mutuelles sur
une bonne partie de la partie (`CCDCCCCDCCDDDDCDD...`). Ce même duel répété
4 fois de plus (`repeat` 2 à 5) reste au contraire à 3,00 à chaque fois. Un
seul tirage malchanceux (température 0,2) sur une seule paire pesait donc
~1/8 de la moyenne du run à 1 répétition et suffisait à faire perdre 3 rangs
à l'agent — démonstration concrète de pourquoi `N_REPEATS=1` n'était pas
fiable. Détail de ce qui a changé (fidélité, dérive dans le temps) dans les
sections suivantes.

### Classement (`marts.agg_agent_leaderboard`, moyenne des 5 répétitions)

| agent | type | score moyen/tour | coopération | pardon | riposte | écart-type inter-répétitions |
|---|---|---:|---:|---:|---:|---:|
| grim_trigger | codé | **2,70** | 73,8 % | 0 % | 100 % | 0,08 |
| persona_calculateur | IA | 2,60 | 87,4 % | 33,3 % | 66,7 % | 0,09 |
| tit_for_tat | codé | 2,58 | 77,6 % | 0 % | 100 % | 0,11 |
| persona_empathique | IA | 2,51 | 99,3 % | 95,8 % | 4,2 % | 0,02 |
| always_cooperate | codé | 2,51 | 100 % | 100 % | 0 % | 0,01 |
| persona_rancunier | IA | 2,43 | 66,7 % | 18,8 % | 81,2 % | 0,14 |
| always_defect | codé | 2,40 | 0 % | 0 % | 100 % | 0,04 |
| random | codé | 2,15 | 50,2 % | 49,6 % | 50,4 % | 0,03 |

**Ce qui change avec 5 répétitions plutôt qu'1** : `persona_calculateur` passe
de 5ᵉ à **2ᵉ**, il dépasse maintenant `tit_for_tat` — y compris son propre
équivalent codé (2,60 contre 2,58, voir plus bas) ; `persona_rancunier` passe
de 7ᵉ à 6ᵉ, il dépasse maintenant `always_defect`. Le podium (`grim_trigger`
en tête) et le dernier (`random`) ne bougent pas — c'était donc déjà un signal
solide au run précédent, contrairement au milieu de tableau. La colonne
écart-type le confirme : `persona_rancunier` (0,14) et `tit_for_tat` (0,11)
sont les plus dispersés d'une répétition à l'autre, `always_cooperate` (0,01)
et `persona_empathique` (0,02) les plus stables (logique : moins de dépendance
au hasard de l'adversaire quand on ne réagit presque jamais).

**Constat n°1 — résultat d'Axelrod reproduit.** Les stratégies « nice but
firm » (coopératives par défaut, jamais exploitées deux fois) dominent le haut
du classement : `grim_trigger`, `persona_calculateur` et `tit_for_tat`
occupent le podium, devant `always_cooperate` (jamais vengée) et
`always_defect` (punie par tout le monde après le premier tour). Résultat
historique d'Axelrod (1981) reproduit 40 ans plus tard, IA comprise.

**Constat n°2 — un persona IA imparfait bat son équivalent codé parfait.**
`persona_calculateur` (2,60) devance `tit_for_tat` (2,58) alors qu'il rate
33 % des ripostes que la règle stricte impose (voir fidélité plus bas). Sur ce
tournoi précis, être un peu plus indulgent qu'un TFT strict a *mieux* payé
que l'exécution mécanique de la règle — TFT strict est démonstrablement
performant chez Axelrod, mais pas insurpassable par une variante plus
généreuse sur cette composition d'adversaires. À vérifier sur un tournoi avec
une composition d'agents différente avant de généraliser.

### Persona IA vs équivalent codé (`marts.agg_llm_vs_coded`)

| persona | équivalent codé | score persona | score code | coop persona | coop code |
|---|---|---:|---:|---:|---:|
| persona_calculateur | tit_for_tat | **2,60** | 2,58 | 87,4 % | 77,6 % |
| persona_empathique | tit_for_tat | 2,51 | 2,58 | 99,3 % | 77,6 % |
| persona_rancunier | grim_trigger | 2,43 | 2,70 | 66,7 % | 73,8 % |

### Fidélité par décision (`marts.agg_persona_fidelity`, rejeu de l'historique)

| persona | équivalent | fidélité | riposte respectée* | coopération respectée** |
|---|---|---:|---:|---:|
| persona_rancunier | grim_trigger (stricte) | **93,7 %** | 84,6 % | 99,6 % |
| persona_calculateur | tit_for_tat (stricte) | 93,5 % | **66,7 %** | 99,5 % |
| persona_empathique | tit_for_tat (approchée) | 84,2 % | 4,2 % | 99,9 % |

\* part des tours où la règle impose de trahir et où le persona trahit bien.
\*\* idem pour coopérer.

**Constat n°3 — confirmé avec 5x plus de données : la seule chose qu'un LLM
3B applique mal, c'est la riposte.** Coopérer quand il le faut : ≥ 99,5 % pour
les 3 personas. Trahir quand il le faut : 66,7 % (calculateur) à 84,6 %
(rancunier) — c'est tout l'écart de fidélité. `persona_calculateur`, censé
être le plus strict des trois, reste celui qui rate le plus la riposte, et
c'est *justement* cette indulgence excédentaire qui lui fait battre son propre
équivalent codé au score (constat n°2) — fidélité imparfaite ne veut pas dire
performance dégradée.

**Réciprocité** (`marts.agg_reciprocity`, corrélation entre mon coup au tour t
et le coup adverse au tour t-1) : `tit_for_tat` 1,00 · `grim_trigger` 0,85 ·
`persona_calculateur` 0,77 · `persona_rancunier` 0,69 · `persona_empathique`
0,18 · `random` 0,01. Stable par rapport au run précédent — les personas IA
sont réactives mais moins mécaniquement que les règles codées, dans l'ordre
attendu (calculateur > rancunier > empathique).

**Limite observée** : le schéma de sortie structurée autorise un champ
`justification` optionnel, quasiment jamais rempli spontanément par le modèle
(il ne renvoie que `{"move": "..."}`) — on n'a donc pas le raisonnement
explicite de ces incohérences. Piste pour une itération suivante : rendre
`justification` obligatoire dans le schéma.

**Fiabilité du parsing** : `is_parsable = 100 %` sur les 13 500 réponses IA
(4500 par persona) — la sortie structurée LM Studio n'a jamais nécessité de
repli en texte libre sur ces deux runs (contrairement à `phi-3.5-mini-instruct`
dans le projet Trivial Pursuit).

### Comportement émergent / équilibre de Nash (`marts.agg_cooperation_over_time`)

Taux de coopération sur les 10 premiers tours vs les 10 derniers (moyenne des
5 répétitions) :

| agent | type | début | fin | tendance |
|---|---|---:|---:|---|
| persona_empathique | IA | 97,8 % | **99,3 %** | converge vers la coopération totale |
| random | codé | 49,3 % | 53,1 % | stable (bruit) |
| persona_rancunier | IA | 69,3 % | 69,1 % | **stable** (pas de dérive avec plus de données) |
| tit_for_tat | codé | 80,2 % | 77,8 % | légère érosion |
| grim_trigger | codé | 77,6 % | 73,3 % | légère érosion |
| persona_calculateur | IA | 92,4 % | 88,4 % | légère érosion |

**Ce qui change avec 5 répétitions** : au run précédent, `persona_calculateur`
et `persona_rancunier` semblaient « dériver vers plus de trahison » (-9 et
-8 points). Avec 5x plus de données, `persona_rancunier` est en réalité
**stable** (-0,2 point, dans le bruit) et `persona_calculateur` dérive
beaucoup moins qu'il n'y paraissait (-4 points contre -9). Seul
`persona_empathique` montre une tendance nette et reproductible (convergence
vers la coopération quasi totale). **Conclusion révisée** : l'horizon fini
connu (100 tours) ne produit pas de dérive marquée vers la trahison chez la
plupart des agents réactifs — la lecture « équilibre de Nash en approche »
du run à 1 répétition était en bonne partie un artefact du bruit
d'échantillonnage. Seuls `tit_for_tat` et `grim_trigger` montrent une érosion
légère mais cohérente sur les deux runs.

### Conclusion générale

1. **Le résultat d'Axelrod se reproduit** : les stratégies réactives et
   fermes (`grim_trigger`, `tit_for_tat`, et leur approximation IA
   `persona_calculateur`) occupent le podium, 40 ans après l'expérience
   originale.
2. **Un persona IA peut battre son propre équivalent codé** :
   `persona_calculateur` dépasse `tit_for_tat` au score malgré une riposte
   moins systématique — sur ce tournoi précis, un peu d'indulgence excédentaire
   a mieux payé que l'exécution mécanique de la règle.
3. **Les personas en langage naturel approximent leur règle sans l'appliquer
   mécaniquement — et c'est la *riposte* qui leur échappe**, de façon stable
   sur les deux runs : ≥ 99,5 % de fidélité pour coopérer quand il le faut,
   mais 66,7 % (calculateur) à 84,6 % (rancunier) pour sanctionner. C'est la
   mesure directe du « système d'évaluation des prompts » demandé par le sujet
   (`agg_persona_fidelity`).
4. **La plupart des dynamiques « émergentes » observées à 1 répétition ne
   résistent pas à la réplication** : la dérive vers la trahison de
   `persona_rancunier` disparaît avec plus de données (bruit
   d'échantillonnage), celle de `persona_calculateur` se réduit de moitié.
   Seule la convergence de `persona_empathique` vers la coopération quasi
   totale est confirmée. Leçon méthodologique du projet autant que résultat :
   sur un tournoi stochastique, **répéter change la lecture**, pas seulement
   sa précision.

## 7. Limites méthodologiques

- **`N_REPEATS=5`** : résout la limite du 1er run (1 seule partie/paire), mais
  reste petit pour une vraie barre d'erreur (5 tirages ≠ intervalle de
  confiance rigoureux). L'écart-type inter-répétitions (colonne du classement
  §6) sert de garde-fou informel : `persona_rancunier` et `tit_for_tat` restent
  les plus dispersés, à lire avec prudence sur un classement serré.
- **Un seul modèle (3B, Q4)** incarne les 3 personas : on mesure l'effet du
  *prompt*, pas celui du modèle. Ce que fait un modèle plus gros reste ouvert.
- **Réciprocité ↔ score calculée sur 6 agents** seulement : indicatif, pas
  une corrélation statistiquement exploitable.
- **Un seul run à `N_REPEATS=5`** : on n'a pas répété *le run lui-même* (pas de
  "répétition des répétitions") — la disparition de la dérive de
  `persona_rancunier` entre les deux runs est cohérente avec du bruit qui se
  moyenne, mais n'est pas prouvée formellement (pas de test statistique).
- **`justification` quasi jamais remplie** : le schéma JSON la laisse optionnelle,
  le modèle ne renvoie que `{"move": ...}` — on n'a pas le raisonnement derrière
  les incohérences. Piste : la rendre obligatoire.
- **Comptage `n_matches` du classement** : un match d'auto-confrontation compte
  pour 1 match mais ses deux sièges contribuent aux tours de l'agent (d'où
  4500 tours joués pour 40 matches à `N_REPEATS=5` ; toutes les métriques sont
  calculées au niveau ligne, donc non affectées).
- **Fidélité mesurée sur les équivalents `stricte` seulement** pour être
  interprétable ; `random` n'a pas de « coup attendu » déterministe.
- **Horizon non communiqué** : les agents IA ne savent pas combien de tours
  restent — l'effet d'horizon (trahison de fin de partie) n'est donc pas testé.
- **Artefact de prompt au 1er tour** : `memory.py` écrivait littéralement
  « Tour 1/N » (placeholder jamais remplacé) sur le run du 11/09 (repris tel
  quel pour les parties `r1` réutilisées dans le run du 25/09 ; les parties
  `r2`-`r5`, elles, utilisent le libellé corrigé). Ne concerne que le 1er tour
  de chaque partie IA ; effet non mesuré, mais rend les 5 répétitions d'une
  même paire légèrement hétérogènes sur ce détail précis.
