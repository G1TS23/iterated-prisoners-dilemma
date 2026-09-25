"""Étape 1 — Génération du tournoi -> couche BRONZE (data/bronze/turns_raw.parquet).

Round-robin (avec auto-confrontation, comme Axelrod) entre :
  - 5 stratégies codées (always_cooperate, always_defect, tit_for_tat, random,
    grim_trigger) -- instantané, aucun appel réseau ;
  - 3 agents IA / personas (config/personas.yaml) -- 1 modèle LM Studio par
    défaut, sortie contrainte à {"move": "C"|"D", ...}.

Format bronze : 1 ligne = (match, tour, joueur) -- tidy/long, 2 lignes par
tour (une par joueur), pas de transformation métier au-delà de ce que la
simulation produit nativement.

Résumable : les match_id déjà présents en bronze sont sautés (un match =
quelques secondes à quelques minutes selon les agents impliqués ; on
écrit/relit le parquet après chaque match, une coupure ne perd donc qu'un
match en cours).
"""
from __future__ import annotations

import argparse
import itertools
import os
import random
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from tqdm import tqdm

from common import BRONZE_TURNS, PAYOFFS, ensure_dirs, load_dotenv
from llm_agent import LLMAgent, load_personas
from llm_client import LMStudio
from strategies import Move, build_coded_agents

load_dotenv()


def build_agents(client: LMStudio | None, model: str, *, temperature: float,
                 seed: int, max_tokens: int) -> list:
    agents = build_coded_agents()
    if client is not None:
        personas, turn_template = load_personas()
        for p in personas:
            agents.append(LLMAgent(
                name=f"persona_{p['id']}", model=model, persona=p,
                turn_template=turn_template, client=client,
                temperature=temperature, seed=seed, max_tokens=max_tokens,
            ))
    return agents


def play_match(agent_a, agent_b, n_turns: int, rng: random.Random,
               match_id: str, repeat: int, run_id: str) -> list[dict]:
    hist_a: list[str] = []
    hist_b: list[str] = []
    rows: list[dict] = []
    for turn in range(1, n_turns + 1):
        mv_a: Move = agent_a.decide(hist_a, hist_b, turn, rng)
        mv_b: Move = agent_b.decide(hist_b, hist_a, turn, rng)
        pay_a = PAYOFFS[(mv_a.move, mv_b.move)]
        pay_b = PAYOFFS[(mv_b.move, mv_a.move)]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows.append({
            "match_id": match_id, "seat": "A", "repeat": repeat, "turn": turn, "n_turns": n_turns,
            "player": agent_a.name, "player_type": agent_a.kind,
            "opponent": agent_b.name, "opponent_type": agent_b.kind,
            "move": mv_a.move, "opponent_move": mv_b.move,
            "payoff": pay_a, "opponent_payoff": pay_b,
            "response_time": mv_a.response_time, "raw_output": mv_a.raw_output,
            "is_parsable": mv_a.is_parsable, "run_id": run_id, "played_at": now,
        })
        rows.append({
            "match_id": match_id, "seat": "B", "repeat": repeat, "turn": turn, "n_turns": n_turns,
            "player": agent_b.name, "player_type": agent_b.kind,
            "opponent": agent_a.name, "opponent_type": agent_a.kind,
            "move": mv_b.move, "opponent_move": mv_a.move,
            "payoff": pay_b, "opponent_payoff": pay_a,
            "response_time": mv_b.response_time, "raw_output": mv_b.raw_output,
            "is_parsable": mv_b.is_parsable, "run_id": run_id, "played_at": now,
        })
        hist_a.append(mv_a.move)
        hist_b.append(mv_b.move)
    return rows


def existing_match_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(pl.read_parquet(path, columns=["match_id"])["match_id"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-turns", type=int, default=int(os.environ.get("N_TURNS", "100")))
    ap.add_argument("--n-repeats", type=int, default=int(os.environ.get("N_REPEATS", "1")))
    ap.add_argument("--no-llm", action="store_true",
                    help="Stratégies codées uniquement (pas de serveur LM Studio requis).")
    ap.add_argument("--model", default=os.environ.get("LLM_MODELS", "").split(",")[0].strip(),
                    help="Modèle LM Studio pour les 3 personas (défaut : 1er de $LLM_MODELS).")
    ap.add_argument("--host", default=os.environ.get("LMSTUDIO_HOST", "http://localhost:1234"))
    ap.add_argument("--max-matches", type=int, default=None, help="Plafond (smoke test).")
    ap.add_argument("--output", type=Path, default=BRONZE_TURNS,
                    help="Fichier bronze de sortie (défaut : data/bronze/turns_raw.parquet, "
                         "LIVRÉ dans le dépôt). Pour un test, écrire ailleurs afin de ne pas "
                         "contaminer les données publiées.")
    args = ap.parse_args()

    ensure_dirs()
    seed = int(os.environ.get("SEED", "42"))
    temperature = float(os.environ.get("TEMPERATURE", "0.2"))
    max_tokens = int(os.environ.get("MAX_TOKENS", "96"))

    client = None
    if not args.no_llm:
        if not args.model:
            raise SystemExit("Aucun modèle : renseigner LLM_MODELS dans .env, --model, ou --no-llm.")
        client = LMStudio(args.host)
        client.load(args.model)

    agents = build_agents(client, args.model, temperature=temperature, seed=seed, max_tokens=max_tokens)
    print(f"agents   : {[a.name for a in agents]} ({len(agents)})")

    pairs = list(itertools.combinations_with_replacement(agents, 2))
    matches = [(a, b, r) for a, b in pairs for r in range(1, args.n_repeats + 1)]
    if args.max_matches:
        matches = matches[: args.max_matches]
    out_path: Path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = existing_match_ids(out_path)
    run_id = uuid.uuid4().hex[:12]
    print(f"matches  : {len(matches)} (round-robin + auto-confrontation, "
          f"{args.n_repeats} répétition(s)) — {args.n_turns} tours chacun")
    print(f"run_id   : {run_id}")

    for a, b, repeat in tqdm(matches, desc="tournoi", unit="match"):
        # n_turns dans le match_id : sinon un run relancé avec un --n-turns
        # différent saute silencieusement les matches déjà en bronze (résumable
        # par match_id) et mélange des parties de longueurs différentes.
        match_id = f"{a.name}__vs__{b.name}__t{args.n_turns}__r{repeat}"
        if match_id in done:
            continue
        # crc32 et non hash() : hash() d'une str est randomisé à chaque processus
        # (PYTHONHASHSEED), ce qui rendait la stratégie `random` non reproductible.
        rng = random.Random(zlib.crc32(f"{seed}:{match_id}".encode()))
        rows = play_match(a, b, args.n_turns, rng, match_id, repeat, run_id)
        new_df = pl.DataFrame(rows)
        if out_path.exists():
            new_df = pl.concat([pl.read_parquet(out_path), new_df], how="diagonal_relaxed")
        new_df.write_parquet(out_path)
        done.add(match_id)

    print("terminé.")


if __name__ == "__main__":
    main()
