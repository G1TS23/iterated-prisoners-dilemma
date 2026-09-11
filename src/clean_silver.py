"""Étape 2 — Nettoyage/enrichissement BRONZE -> SILVER (data/silver/turns.parquet).

Colonnes dérivées ajoutées par ligne (perspective du joueur `player`, causales :
ne regardent que les tours <= tour courant, comme le sujet le demande
"mémoire des tours précédents, fréquence de trahison, tendance à pardonner") :

    own_cum_score / opp_cum_score      score cumulé (joueur / adversaire)
    own_coop_rate / opp_coop_rate      taux de coopération glissant (y compris ce tour)
    opponent_last_move                 coup de l'adversaire au tour précédent (null au tour 1)
    opponent_defection_streak          trahisons consécutives de l'adversaire menant à CE tour
                                        (donc l'info telle que le joueur la "voyait" en décidant)
    forgave_this_turn                  a coopéré alors que l'adversaire l'avait trahi au tour précédent
    retaliated_this_turn               a trahi juste après avoir été trahi au tour précédent
    round_outcome                      mutual_coop / mutual_defect / exploited / exploiter
"""
from __future__ import annotations

import polars as pl

from common import BRONZE_TURNS, SILVER_TURNS, ensure_dirs


def _round_outcome(move: str, opp_move: str) -> str:
    if move == "C" and opp_move == "C":
        return "mutual_coop"
    if move == "D" and opp_move == "D":
        return "mutual_defect"
    if move == "C" and opp_move == "D":
        return "exploited"       # le joueur s'est fait avoir
    return "exploiter"           # move == "D" and opp_move == "C" : le joueur a trahi le coopérant


def enrich(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort(["match_id", "seat", "turn"])
    out_rows: list[dict] = []
    # (match_id, seat) et non (match_id, player) : en auto-confrontation
    # (agent contre lui-même) les deux sièges partagent le même nom de joueur,
    # `seat` (A/B) est le seul identifiant qui les distingue de façon fiable.
    state: dict[tuple[str, str], dict] = {}

    for row in df.iter_rows(named=True):
        key = (row["match_id"], row["seat"])
        st = state.setdefault(key, {
            "own_score": 0, "opp_score": 0, "own_coop": 0, "opp_coop": 0,
            "opp_streak": 0, "prev_opp_move": None,
        })

        row = dict(row)
        row["own_cum_score"] = st["own_score"] + row["payoff"]
        row["opp_cum_score"] = st["opp_score"] + row["opponent_payoff"]
        own_coop = st["own_coop"] + (row["move"] == "C")
        opp_coop = st["opp_coop"] + (row["opponent_move"] == "C")
        row["own_coop_rate"] = own_coop / row["turn"]
        row["opp_coop_rate"] = opp_coop / row["turn"]
        row["opponent_last_move"] = st["prev_opp_move"]
        row["opponent_defection_streak"] = st["opp_streak"]
        row["forgave_this_turn"] = (row["move"] == "C" and st["prev_opp_move"] == "D")
        row["retaliated_this_turn"] = (row["move"] == "D" and st["prev_opp_move"] == "D")
        row["round_outcome"] = _round_outcome(row["move"], row["opponent_move"])
        out_rows.append(row)

        st["own_score"] = row["own_cum_score"]
        st["opp_score"] = row["opp_cum_score"]
        st["own_coop"] = own_coop
        st["opp_coop"] = opp_coop
        st["opp_streak"] = st["opp_streak"] + 1 if row["opponent_move"] == "D" else 0
        st["prev_opp_move"] = row["opponent_move"]

    # infer_schema_length=None : scanne toutes les lignes avant d'inférer les
    # types. Sans ça, `response_time`/`raw_output` (None pour les agents codés,
    # valeurs réelles pour les agents IA) peuvent être mal typées si les
    # premières lignes triées sont toutes des agents codés (None en rafale).
    return pl.DataFrame(out_rows, infer_schema_length=None)


def main() -> None:
    ensure_dirs()
    df = pl.read_parquet(BRONZE_TURNS)
    out = enrich(df)
    out.write_parquet(SILVER_TURNS)
    print(f"écrit : {SILVER_TURNS}  ({len(out)} lignes, {out['match_id'].n_unique()} matches)")
    print(out.group_by("round_outcome").len().sort("round_outcome"))


if __name__ == "__main__":
    main()
