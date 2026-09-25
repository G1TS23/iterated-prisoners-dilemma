-- Corrélation de réciprocité : à quel point mon coup au tour t est-il corrélé
-- au coup de l'adversaire au tour t-1 ?  (+1 = miroir parfait type
-- tit_for_tat ; 0 = indifférent ; NULL = variance nulle, ex. always_*).
select
    player as agent,
    player_type as agent_type,
    count(*)                                                        as n_tours,
    corr(case when move = 'C' then 1.0 else 0.0 end,
         case when opponent_last_move = 'C' then 1.0 else 0.0 end)  as reciprocite,
    avg(payoff)                                                     as score_moyen_par_tour,
    avg(case when move = 'C' then 1.0 else 0 end)                   as taux_cooperation
from {{ ref('fct_turns') }}
where opponent_last_move is not null
group by player, player_type
order by reciprocite desc nulls last
