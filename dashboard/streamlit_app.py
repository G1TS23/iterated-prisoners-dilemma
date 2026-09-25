"""Étape 3 — Dashboard interactif du tournoi (dilemme du prisonnier itératif).

Lit la couche GOLD (data/gold/gold.duckdb) EN LECTURE SEULE : dbt doit avoir
tourné avant (`make build`). Ne jamais lancer dbt et Streamlit en même temps
sur le même fichier .duckdb (verrou d'écriture DuckDB).

Lancer :  streamlit run dashboard/streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st
from packaging.version import Version

GOLD_DB = Path(__file__).resolve().parents[1] / "data" / "gold" / "gold.duckdb"

st.set_page_config(page_title="Dilemme du prisonnier itératif", layout="wide")

# --- Compatibilité Streamlit : "pleine largeur" -------------------------------
# `use_container_width` est déprécié (retiré après 2025-12-31) au profit de
# `width="stretch"`, qui n'existe pas dans toutes les versions. Seuils MESURÉS
# en installant chaque version (les notes de version se sont révélées
# inexactes, et `"width" in signature` est trompeur : st.dataframe a toujours eu
# un `width` entier, sans accepter "stretch") :
#   st.dataframe(width="stretch")    : KO en 1.48.0, OK dès 1.49.0
#   st.altair_chart(width="stretch") : paramètre absent en 1.50.0, OK dès 1.51.0
_ST_VERSION = Version(st.__version__)
STRETCH_DF = ({"width": "stretch"} if _ST_VERSION >= Version("1.49")
              else {"use_container_width": True})
STRETCH_CHART = ({"width": "stretch"} if _ST_VERSION >= Version("1.51")
                 else {"use_container_width": True})

# Plancher testé : le dashboard a été exécuté (streamlit AppTest) de 1.39 à la
# version courante. En dessous, rien n'est garanti -> message explicite plutôt
# qu'un TypeError obscur au milieu de la page.
MIN_STREAMLIT = Version("1.39")
if _ST_VERSION < MIN_STREAMLIT:
    st.error(
        f"Streamlit {st.__version__} détecté : ce dashboard est testé à partir de "
        f"la version {MIN_STREAMLIT}. Mets à jour avec `pip install -U streamlit` "
        "(ou relance `make install`)."
    )
    st.stop()


@st.cache_resource
def con() -> duckdb.DuckDBPyConnection:
    if not GOLD_DB.exists():
        st.error(f"Couche gold introuvable : {GOLD_DB}\nLance `make build` d'abord.")
        st.stop()
    return duckdb.connect(str(GOLD_DB), read_only=True)


@st.cache_data
def q(sql: str) -> pd.DataFrame:
    return con().execute(sql).fetch_df()


leaderboard = q("select * from marts.agg_agent_leaderboard")
matrix = q("select * from marts.agg_matchup_matrix")
coop_time = q("select * from marts.agg_cooperation_over_time")
llm_vs_coded = q("select * from marts.agg_llm_vs_coded")
fidelity = q("select * from marts.agg_persona_fidelity")
fidelity_opp = q("select * from marts.agg_persona_fidelity_by_opponent")
recip = q("select * from marts.agg_reciprocity")
fct = q("select * from marts.fct_turns")

st.title("🤝 Dilemme du prisonnier itératif — tournoi Axelrod")
st.caption(f"{fct.match_id.nunique():,} matches · {fct.turn.max()} tours max · "
           f"{leaderboard.shape[0]} agents "
           f"({(leaderboard.agent_type == 'llm').sum()} IA, "
           f"{(leaderboard.agent_type == 'coded').sum()} codés)")

tab1, tab2, tab3, tab_corr, tab4, tab5, tab_interp = st.tabs(
    ["Classement", "Table croisée", "Coopération dans le temps", "Corrélations",
     "IA vs codé & fidélité", "Explorateur de parties", "Interprétation"]
)

with tab1:
    lb = leaderboard.sort_values("score_moyen_par_tour", ascending=False)
    st.dataframe(
        lb.style.format({
            "score_moyen_par_tour": "{:.2f}", "taux_cooperation": "{:.1%}",
            "taux_pardon": "{:.1%}", "taux_riposte": "{:.1%}",
            "temps_moyen_reponse_s": "{:.2f} s",
        }),
        **STRETCH_DF,
    )
    st.altair_chart(
        alt.Chart(lb).mark_bar().encode(
            x=alt.X("agent:N", sort="-y", title=None),
            y=alt.Y("score_moyen_par_tour:Q", title="Score moyen / tour"),
            color=alt.Color("agent_type:N", title="Type"),
            tooltip=["agent", alt.Tooltip("score_moyen_par_tour", format=".2f"),
                     alt.Tooltip("taux_cooperation", format=".1%")],
        ).properties(height=380),
        **STRETCH_CHART,
    )

with tab2:
    st.caption("Score moyen par tour de `player` (ligne) face à `opponent` (colonne).")
    st.altair_chart(
        alt.Chart(matrix).mark_rect().encode(
            x=alt.X("opponent:N", title=None, axis=alt.Axis(labelAngle=-40)),
            y=alt.Y("player:N", title=None),
            color=alt.Color("score_moyen_par_tour:Q", title="Score moyen",
                            scale=alt.Scale(scheme="blues")),
            tooltip=["player", "opponent", alt.Tooltip("score_moyen_par_tour", format=".2f"),
                     alt.Tooltip("taux_cooperation", format=".1%")],
        ).properties(height=420),
        **STRETCH_CHART,
    )

with tab3:
    agents_sel = st.multiselect("Agents", sorted(coop_time.agent.unique()),
                                default=sorted(coop_time.agent.unique()))
    ct = coop_time[coop_time.agent.isin(agents_sel)]
    st.altair_chart(
        alt.Chart(ct).mark_line(point=False).encode(
            x=alt.X("turn:Q", title="Tour"),
            y=alt.Y("taux_cooperation:Q", title="Taux de coopération", axis=alt.Axis(format="%")),
            color=alt.Color("agent:N", title="Agent"),
            strokeDash=alt.StrokeDash("agent_type:N", title="Type"),
            tooltip=["agent", "turn", alt.Tooltip("taux_cooperation", format=".1%")],
        ).properties(height=420).interactive(),
        **STRETCH_CHART,
    )
    st.caption("Une courbe qui se stabilise proche de 100 % = équilibre coopératif "
               "émergent ; proche de 0 % = escalade vers la trahison mutuelle.")

with tab_corr:
    st.caption("Réciprocité = corrélation entre mon coup au tour t et le coup de "
               "l'adversaire au tour t-1 (+1 : miroir parfait type tit_for_tat ; "
               "0 : indifférent ; absent : agent à comportement constant).")
    rc = recip.dropna(subset=["reciprocite"])
    st.altair_chart(
        alt.Chart(rc).mark_bar().encode(
            x=alt.X("agent:N", sort="-y", title=None),
            y=alt.Y("reciprocite:Q", title="Réciprocité (corrélation)", scale=alt.Scale(domain=[-0.2, 1])),
            color=alt.Color("agent_type:N", title="Type"),
            tooltip=["agent", alt.Tooltip("reciprocite", format=".2f"),
                     alt.Tooltip("score_moyen_par_tour", format=".2f")],
        ).properties(height=320),
        **STRETCH_CHART,
    )
    st.subheader("Réciprocité vs score")
    st.altair_chart(
        alt.Chart(rc).mark_circle(size=220).encode(
            x=alt.X("reciprocite:Q", title="Réciprocité", scale=alt.Scale(zero=False)),
            y=alt.Y("score_moyen_par_tour:Q", title="Score moyen / tour", scale=alt.Scale(zero=False)),
            color=alt.Color("agent_type:N", title="Type"),
            tooltip=["agent", alt.Tooltip("reciprocite", format=".2f"),
                     alt.Tooltip("score_moyen_par_tour", format=".2f")],
        ).properties(height=340),
        **STRETCH_CHART,
    )
    if len(rc) >= 3:
        r = rc["reciprocite"].corr(rc["score_moyen_par_tour"])
        st.info(f"Corrélation réciprocité ↔ score sur les {len(rc)} agents à comportement "
                f"non constant : **{r:+.2f}** (échantillon minuscule — indicatif, pas une preuve).")

with tab4:
    st.caption("Chaque persona IA comparé à sa stratégie codée équivalente "
               "(config/personas.yaml) — l'écart mesure la fidélité du prompt.")
    disp = llm_vs_coded.copy()
    disp["ecart_score"] = disp.score_moyen_persona - disp.score_moyen_code
    disp["ecart_coop"] = disp.coop_persona - disp.coop_code
    st.dataframe(
        disp.style.format({
            "score_moyen_persona": "{:.2f}", "score_moyen_code": "{:.2f}", "ecart_score": "{:+.2f}",
            "coop_persona": "{:.1%}", "coop_code": "{:.1%}", "ecart_coop": "{:+.1%}",
            "pardon_persona": "{:.1%}", "pardon_code": "{:.1%}",
            "riposte_persona": "{:.1%}", "riposte_code": "{:.1%}",
            "temps_moyen_reponse_s": "{:.2f} s",
        }),
        **STRETCH_DF,
    )
    melt = disp.melt(id_vars=["persona"], value_vars=["coop_persona", "coop_code"],
                     var_name="source", value_name="taux_cooperation")
    st.altair_chart(
        alt.Chart(melt).mark_bar().encode(
            x=alt.X("persona:N", title=None),
            xOffset="source:N",
            y=alt.Y("taux_cooperation:Q", axis=alt.Axis(format="%")),
            color=alt.Color("source:N", title=None,
                            scale=alt.Scale(domain=["coop_persona", "coop_code"],
                                            range=["#4C78A8", "#B0B0B0"])),
            tooltip=["persona", "source", alt.Tooltip("taux_cooperation", format=".1%")],
        ).properties(height=340),
        **STRETCH_CHART,
    )

    st.subheader("Évaluation des prompts : fidélité tour par tour")
    st.caption("Pour chaque décision d'un persona, on rejoue son historique dans l'équivalent "
               "codé et on compare. `fidélité` = même coup ; `riposte respectée` = quand la règle "
               "exige de trahir, le persona trahit-il ?")
    st.dataframe(
        fidelity.style.format({"fidelite": "{:.1%}", "riposte_attendue_respectee": "{:.1%}",
                               "cooperation_attendue_respectee": "{:.1%}", "taux_parsable": "{:.1%}"}),
        **STRETCH_DF,
    )
    fo = fidelity_opp.dropna(subset=["fidelite"])
    st.altair_chart(
        alt.Chart(fo).mark_rect().encode(
            x=alt.X("opponent:N", title=None, axis=alt.Axis(labelAngle=-40)),
            y=alt.Y("persona:N", title=None),
            color=alt.Color("fidelite:Q", title="Fidélité", scale=alt.Scale(scheme="redyellowgreen", domain=[0.5, 1])),
            tooltip=["persona", "opponent", alt.Tooltip("fidelite", format=".1%")],
        ).properties(height=200, title="Fidélité par adversaire (où le persona décroche de sa règle)"),
        **STRETCH_CHART,
    )

with tab5:
    st.caption("Rejoue un match tour par tour, avec la justification du modèle si disponible.")
    match_ids = sorted(fct.match_id.unique())
    default_llm_match = next((m for m in match_ids if "persona" in m), match_ids[0])
    match_id = st.selectbox("Match", match_ids, index=match_ids.index(default_llm_match))
    m = fct[fct.match_id == match_id].sort_values(["turn", "player"])
    players = sorted(m.player.unique())
    cols = st.columns(2)
    for col, player in zip(cols, players):
        with col:
            st.subheader(player)
            pm = m[m.player == player].sort_values("turn")
            st.write("Séquence :", "".join(pm.move.tolist()))
            show_cols = ["turn", "move", "opponent_move", "payoff", "own_cum_score", "round_outcome"]
            if pm.player_type.iloc[0] == "llm":
                show_cols.append("raw_output")
            st.dataframe(pm[show_cols], **STRETCH_DF, height=360)

with tab_interp:
    best = leaderboard.sort_values("score_moyen_par_tour", ascending=False).iloc[0]
    worst = leaderboard.sort_values("score_moyen_par_tour").iloc[0]
    llm_lb = leaderboard[leaderboard.agent_type == "llm"].sort_values("score_moyen_par_tour", ascending=False)
    strict = fidelity[fidelity.equivalence == "stricte"].sort_values("fidelite", ascending=False)
    ct = coop_time.copy()
    drift = (ct[ct.turn > ct.turn.max() - 10].groupby("agent").taux_cooperation.mean()
             - ct[ct.turn <= 10].groupby("agent").taux_cooperation.mean()).dropna()
    drift = drift[[a for a in drift.index if a in set(llm_lb.agent) | {"tit_for_tat", "grim_trigger"}]]
    st.header("Ce que disent les données")
    st.markdown(
        f"""
- **Classement** : `{best.agent}` domine ({best.score_moyen_par_tour:.2f} pt/tour), `{worst.agent}` ferme la marche
  ({worst.score_moyen_par_tour:.2f}). Les stratégies *gentilles mais fermes* (coopèrent d'abord, ripostent
  aux trahisons) devancent les stratégies inconditionnelles — le résultat d'Axelrod (1981).
- **Meilleur agent IA** : `{llm_lb.iloc[0].agent}` ({llm_lb.iloc[0].score_moyen_par_tour:.2f} pt/tour,
  coopération {llm_lb.iloc[0].taux_cooperation:.0%}).
- **Fidélité des personas** (équivalents *stricts* uniquement — `empathique` est une variante
  volontairement généreuse de TFT) : décision par décision, la plus fidèle est
  `{strict.iloc[0].persona}` ({strict.iloc[0].fidelite:.0%}) ; celle qui respecte le moins
  l'obligation de riposter est `{strict.sort_values('riposte_attendue_respectee').iloc[0].persona}`
  ({strict.riposte_attendue_respectee.min():.0%} des tours où la règle impose de trahir).
- **Dynamique** (coopération, 10 derniers tours vs 10 premiers) : """
        + ", ".join(f"`{a}` {v:+.0%}" for a, v in drift.sort_values().items()) + "."
    )
    st.header("Lecture théorique")
    st.markdown(
        """
- **Équilibre de Nash** : horizon fini et connu ⇒ par récurrence à rebours, la trahison mutuelle est
  l'unique équilibre de Nash. On n'observe pourtant **aucune** bascule générale vers la trahison :
  les agents réactifs maintiennent la coopération (résultat empirique d'Axelrod).
- **Effet de l'IA** : un persona en langage naturel *approxime* une règle mais ne l'applique pas
  mécaniquement — de petits écarts de décision (riposte manquée) changent la trajectoire de toute la
  partie, surtout pour une règle *absorbante* comme le grim trigger. Un LLM local apporte donc de la
  **variabilité comportementale** absente des stratégies codées.
- **Limites** : 1 partie par paire (pas de barre d'erreur), un seul modèle 3B, température 0,2,
  champ `justification` quasi jamais rempli — voir le README pour le détail.
"""
    )
