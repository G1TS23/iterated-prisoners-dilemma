-- Évolution du taux de coopération au fil des tours, par agent et par type
-- d'agent -- sert à repérer une convergence / un équilibre émergent.
select
    player as agent,
    player_type as agent_type,
    turn,
    avg(case when move = 'C' then 1.0 else 0 end) as taux_cooperation,
    avg(payoff)                                    as score_moyen
from {{ ref('fct_turns') }}
group by player, player_type, turn
order by player, turn
