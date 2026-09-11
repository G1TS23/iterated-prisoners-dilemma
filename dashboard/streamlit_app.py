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

GOLD_DB = Path(__file__).resolve().parents[1] / "data" / "gold" / "gold.duckdb"

st.set_page_config(page_title="Dilemme du prisonnier itératif", layout="wide")


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
fct = q("select * from marts.fct_turns")

st.title("🤝 Dilemme du prisonnier itératif — tournoi Axelrod")
st.caption(f"{fct.match_id.nunique():,} matches · {fct.turn.max()} tours max · "
           f"{leaderboard.shape[0]} agents "
           f"({(leaderboard.agent_type == 'llm').sum()} IA, "
           f"{(leaderboard.agent_type == 'coded').sum()} codés)")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Classement", "Table croisée", "Coopération dans le temps", "IA vs codé", "Explorateur de parties"]
)

with tab1:
    lb = leaderboard.sort_values("score_moyen_par_tour", ascending=False)
    st.dataframe(
        lb.style.format({
            "score_moyen_par_tour": "{:.2f}", "taux_cooperation": "{:.1%}",
            "taux_pardon": "{:.1%}", "taux_riposte": "{:.1%}",
            "temps_moyen_reponse_s": "{:.2f} s",
        }),
        use_container_width=True,
    )
    st.altair_chart(
        alt.Chart(lb).mark_bar().encode(
            x=alt.X("agent:N", sort="-y", title=None),
            y=alt.Y("score_moyen_par_tour:Q", title="Score moyen / tour"),
            color=alt.Color("agent_type:N", title="Type"),
            tooltip=["agent", alt.Tooltip("score_moyen_par_tour", format=".2f"),
                     alt.Tooltip("taux_cooperation", format=".1%")],
        ).properties(height=380),
        use_container_width=True,
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
        use_container_width=True,
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
        use_container_width=True,
    )
    st.caption("Une courbe qui se stabilise proche de 100 % = équilibre coopératif "
               "émergent ; proche de 0 % = escalade vers la trahison mutuelle.")

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
        use_container_width=True,
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
        use_container_width=True,
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
            st.dataframe(pm[show_cols], use_container_width=True, height=360)
