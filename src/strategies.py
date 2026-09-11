"""Stratégies codées + interface commune Agent (codée ou IA).

Chaque agent expose `decide(my_history, opp_history, turn, rng) -> Move`.
`my_history`/`opp_history` sont les séquences de coups ("C"/"D") des tours
*précédents* (le tour courant n'y figure pas encore).
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Move:
    move: str                       # "C" ou "D"
    response_time: float | None = None   # None pour un agent codé (instantané)
    raw_output: str | None = None        # sortie brute / justification (agents IA)
    is_parsable: bool = True             # False si la lettre a dû être défaultée (agents IA)


class CodedAgent:
    """Enrobe une fonction de stratégie pure en agent."""

    kind = "coded"

    def __init__(self, name: str, fn):
        self.name = name
        self._fn = fn

    def decide(self, my_history: list[str], opp_history: list[str],
              turn: int, rng: random.Random) -> Move:
        return Move(move=self._fn(my_history, opp_history, rng))


def _always_cooperate(my_h, opp_h, rng) -> str:
    return "C"


def _always_defect(my_h, opp_h, rng) -> str:
    return "D"


def _tit_for_tat(my_h, opp_h, rng) -> str:
    """Coopère au 1er tour, puis rejoue le dernier coup de l'adversaire."""
    return "C" if not opp_h else opp_h[-1]


def _random_strategy(my_h, opp_h, rng) -> str:
    return rng.choice(("C", "D"))


def _grim_trigger(my_h, opp_h, rng) -> str:
    """Coopère jusqu'à la 1re trahison adverse, puis ne pardonne jamais."""
    return "D" if "D" in opp_h else "C"


CODED_STRATEGIES: dict[str, callable] = {
    "always_cooperate": _always_cooperate,
    "always_defect": _always_defect,
    "tit_for_tat": _tit_for_tat,
    "random": _random_strategy,
    "grim_trigger": _grim_trigger,
}


def build_coded_agents() -> list[CodedAgent]:
    return [CodedAgent(name, fn) for name, fn in CODED_STRATEGIES.items()]
