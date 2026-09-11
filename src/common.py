"""Chemins, constantes et helpers partagés."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BRONZE_DIR = DATA / "bronze"
SILVER_DIR = DATA / "silver"
GOLD_DIR = DATA / "gold"

BRONZE_TURNS = BRONZE_DIR / "turns_raw.parquet"
SILVER_TURNS = SILVER_DIR / "turns.parquet"
GOLD_DB = GOLD_DIR / "gold.duckdb"

CONFIG_DIR = ROOT / "config"
PERSONAS_YAML = CONFIG_DIR / "personas.yaml"

# --- Dilemme du prisonnier : matrice de gains classique -------------------
# (Coup joueur, coup adversaire) -> gain du joueur.
# Condition théorique du "vrai" dilemme : T > R > P > S et 2R > T + S.
#   R = récompense (coopération mutuelle)      T = tentation (trahir seul)
#   P = punition (trahison mutuelle)           S = dupe (coopère seul, trahi)
R, T, P, S = 3, 5, 1, 0
PAYOFFS: dict[tuple[str, str], int] = {
    ("C", "C"): R,
    ("D", "D"): P,
    ("D", "C"): T,
    ("C", "D"): S,
}
MOVES = ("C", "D")


def ensure_dirs() -> None:
    for d in (BRONZE_DIR, SILVER_DIR, GOLD_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --- .env minimal, sans dépendance --------------------------------------
def load_dotenv(path: Path | None = None) -> None:
    p = path or (ROOT / ".env")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if not (val.startswith('"') or val.startswith("'")) and " #" in val:
            val = val.split(" #", 1)[0].strip()   # commentaire en fin de ligne
        os.environ.setdefault(key.strip(), val.strip('"').strip("'"))


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
