"""Résumé compact de l'historique pour le prompt d'un agent IA.

Décision du projet : résumé plutôt qu'historique complet (coût en tokens
constant, tenable sur N_TURNS=100+ — voir README § Méthodologie). Contient
tout ce dont une stratégie réactive (type Tit-for-Tat/Grim Trigger) a besoin :
dernier coup adverse, taux de coopération adverse, streak de trahisons,
score cumulé des deux joueurs.
"""
from __future__ import annotations

from common import PAYOFFS


def _defection_streak(history: list[str]) -> int:
    streak = 0
    for m in reversed(history):
        if m == "D":
            streak += 1
        else:
            break
    return streak


def _cumulative_score(my_h: list[str], opp_h: list[str]) -> int:
    return sum(PAYOFFS[(a, b)] for a, b in zip(my_h, opp_h))


def summarize_memory(my_history: list[str], opp_history: list[str]) -> str:
    turn = len(opp_history) + 1
    if not opp_history:
        return f"Tour {turn} — première interaction, aucun historique disponible."

    n = len(opp_history)
    opp_coop = opp_history.count("C")
    my_coop = my_history.count("C")
    last_opp = "a coopéré" if opp_history[-1] == "C" else "t'a trahi"
    streak = _defection_streak(opp_history)
    my_score = _cumulative_score(my_history, opp_history)
    opp_score = _cumulative_score(opp_history, my_history)

    parts = [
        f"Tour {turn} — {n} tour(s) joué(s).",
        f"L'adversaire a coopéré {opp_coop}/{n} fois ({opp_coop / n:.0%}).",
        f"Toi-même as coopéré {my_coop}/{n} fois ({my_coop / n:.0%}).",
        f"Au dernier tour, l'adversaire {last_opp}.",
    ]
    if streak > 0:
        parts.append(f"Trahisons consécutives actuelles de l'adversaire : {streak}.")
    parts.append(f"Score cumulé — toi : {my_score}, adversaire : {opp_score}.")
    return " ".join(parts)
