-- Comparaison directe persona IA <-> stratégie codée équivalente (§ sujet :
-- "confronter les deux approches"). Une ligne par persona.
with llm as (
    select l.agent as persona, a.coded_equivalent, l.*
    from {{ ref('agg_agent_leaderboard') }} l
    join {{ ref('dim_agent') }} a on l.agent = a.agent_name
    where a.agent_type = 'llm'
),
coded as (
    select agent as coded_equivalent, * exclude (agent)
    from {{ ref('agg_agent_leaderboard') }}
)

select
    llm.persona,
    llm.coded_equivalent,
    llm.score_moyen_par_tour     as score_moyen_persona,
    coded.score_moyen_par_tour   as score_moyen_code,
    llm.taux_cooperation         as coop_persona,
    coded.taux_cooperation       as coop_code,
    llm.taux_pardon              as pardon_persona,
    coded.taux_pardon            as pardon_code,
    llm.taux_riposte             as riposte_persona,
    coded.taux_riposte           as riposte_code,
    llm.temps_moyen_reponse_s
from llm
left join coded using (coded_equivalent)
