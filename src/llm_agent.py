"""Agent IA : persona (config/personas.yaml) + LM Studio + mémoire résumée."""
from __future__ import annotations

import json
import re

import yaml

from common import PERSONAS_YAML
from memory import summarize_memory
from strategies import Move

MOVE_RE = re.compile(r"\b([CD])\b")
COOP_RE = re.compile(r"coop[ée]r", re.I)
DEFECT_RE = re.compile(r"trah", re.I)

MOVE_SCHEMA = {
    "type": "object",
    "properties": {
        "move": {"type": "string", "enum": ["C", "D"]},
        "justification": {"type": "string"},
    },
    "required": ["move"],
}


def extract_move(raw: str) -> str | None:
    """JSON structuré d'abord, puis lettre isolée, puis mots-clés FR en repli."""
    try:
        val = json.loads(raw).get("move", "")
        if isinstance(val, str) and val.strip().upper()[:1] in ("C", "D"):
            return val.strip().upper()[0]
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    m = MOVE_RE.search(raw.upper())
    if m:
        return m.group(1)
    coop, defect = COOP_RE.search(raw), DEFECT_RE.search(raw)
    if coop and not defect:
        return "C"
    if defect and not coop:
        return "D"
    return None


def load_personas() -> tuple[list[dict], str]:
    cfg = yaml.safe_load(PERSONAS_YAML.read_text(encoding="utf-8"))
    return [p for p in cfg["personas"] if p.get("active")], cfg["turn_template"]


class LLMAgent:
    kind = "llm"

    def __init__(self, name: str, model: str, persona: dict, turn_template: str,
                client, *, temperature: float, seed: int, max_tokens: int):
        self.name = name
        self.model = model
        self.persona = persona
        self.turn_template = turn_template
        self.client = client
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens

    def decide(self, my_history: list[str], opp_history: list[str], turn: int, rng) -> Move:
        summary = summarize_memory(my_history, opp_history)
        prompt = (self.persona["system"].strip() + "\n\n"
                  + self.turn_template.format(memory_summary=summary))
        raw, elapsed, _stats = self.client.ask(
            prompt, temperature=self.temperature, seed=self.seed,
            max_tokens=self.max_tokens, json_schema=MOVE_SCHEMA,
        )
        move = extract_move(raw)
        parsable = move is not None
        if move is None:
            move = "C"   # défaut prudent si vraiment imparsable (rare) ; is_parsable le trace
        return Move(move=move, response_time=elapsed, raw_output=raw, is_parsable=parsable)
