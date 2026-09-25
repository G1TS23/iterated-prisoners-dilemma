# Architecture

## Pipeline de bout en bout

```
   config/personas.yaml            src/strategies.py
   (3 personas IA + équivalent      (5 stratégies codées)
    codé + prompt)                          │
            │                               │
            ▼                               ▼
        LLMAgent  ◄── src/memory.py     CodedAgent
   (persona + résumé compact)            (règle pure)
            │  src/llm_client.py                │
            ▼                                    │
   LM Studio (:1234, sortie                      │
   structurée {"move": C|D})                     │
            │                                    │
            └──────────────┬─────────────────────┘
                           ▼   src/simulate.py  (round-robin + auto-confrontation,
                           │   8 agents -> 36 matches x N_TURNS, résumable)
                           ▼
┌────────────────────────────────────────────────┐
│ BRONZE   data/bronze/turns_raw.parquet          │  brut, 1 ligne = match x tour x siège
└────────────────────────────────────────────────┘
                           │  src/clean_silver.py  (colonnes dérivées causales :
                           │   score cumulé, coop rate glissant, streak,
                           │   pardon/riposte, round_outcome)
                           ▼
┌────────────────────────────────────────────────┐
│ SILVER   data/silver/turns.parquet              │  observations enrichies
└────────────────────────────────────────────────┘
                           │  dbt build  (dbt-duckdb)  +  seed agent_meta.csv
                           ▼
┌────────────────────────────────────────────────┐
│ GOLD     data/gold/gold.duckdb                  │  1 table = 1 question métier
│   staging.stg_turns                             │
│   marts.fct_turns            (faits)            │
│   marts.dim_agent            (dimension)        │
│   marts.agg_agent_leaderboard                   │  qui gagne ?
│   marts.agg_matchup_matrix                      │  qui bat qui ?
│   marts.agg_cooperation_over_time               │  convergence / équilibre ?
│   marts.agg_reciprocity                         │  corrélation coup t / coup adverse t-1
│   marts.agg_llm_vs_coded                        │  persona vs équivalent codé (agrégats)
│   marts.agg_persona_fidelity(_by_opponent)      │  évaluation des prompts, tour par tour
└────────────────────────────────────────────────┘
                           │  lecture seule
                           ▼
                  Streamlit dashboard (7 onglets, dont Interprétation)
```

## Modèle dimensionnel (couche gold)

**Fait** `fct_turns` — grain : une ligne = `(match_id, turn, seat)`

| colonne | rôle |
|---|---|
| `turn_key` | clé de substitution sur `(match_id, turn, seat)` |
| `match_id` | `<A>__vs__<B>__t<N_TURNS>__r<repeat>` |
| `seat` | `A` / `B` — **nécessaire** : en auto-confrontation les deux sièges portent le même nom de joueur |
| `player`, `opponent`, `player_type` | qui joue, contre qui, codé/IA |
| `move`, `opponent_move`, `payoff` | mesures du tour |
| `own_cum_score`, `opp_cum_score`, `own_coop_rate`, `opp_coop_rate` | état cumulé (causal) |
| `opponent_last_move`, `opponent_defection_streak` | ce que le joueur « voyait » en décidant |
| `forgave_this_turn`, `retaliated_this_turn`, `round_outcome` | comportement dérivé |
| `response_time`, `raw_output`, `is_parsable` | traçabilité IA (NULL pour les agents codés) |

**Dimension** `dim_agent` : `agent_type`, `description`, `coded_equivalent`,
`equivalence` (`stricte` = le persona est censé imiter la règle ; `approchee` =
variante volontairement différente) — issue du seed `dbt/seeds/agent_meta.csv`.

## Choix structurants

- **Format tidy 1 ligne / siège / tour** : simplifie toutes les agrégations par
  agent (pas d'auto-jointure) au prix d'un doublement des lignes.
- **`seat` et non `player`** comme identifiant de perspective (clé, état
  courant en silver) : bug réel rencontré en auto-confrontation (clé dupliquée).
- **`match_id` contient `N_TURNS`** : rend le mode résumable sûr — changer le
  nombre de tours ne réutilise pas silencieusement d'anciennes parties.
- **Silver causal** : chaque colonne dérivée n'utilise que l'information
  disponible *avant* la décision du tour (pas de fuite du futur).
- **Mémoire de l'IA = résumé compact** (`src/memory.py`) : coût en tokens
  constant sur 100+ tours.
- **Évaluation des prompts par rejeu** (`int_persona_expected_move`) : pour
  chaque décision IA on calcule le coup que l'équivalent codé aurait joué avec
  le même historique → fidélité mesurable sans appel LLM supplémentaire.
- **Verrou DuckDB** : dbt écrit `gold.duckdb`, Streamlit l'ouvre en `read_only` ;
  jamais les deux en même temps.
