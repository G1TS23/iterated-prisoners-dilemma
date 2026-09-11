-- Table croisée façon tournoi Axelrod : score moyen par tour de `player`
-- face à `opponent` (asymétrique si l'un des deux est stochastique).
select
    player,
    opponent,
    count(distinct match_id)         as n_matches,
    avg(payoff)                      as score_moyen_par_tour,
    avg(case when move = 'C' then 1.0 else 0 end) as taux_cooperation
from {{ ref('fct_turns') }}
group by player, opponent
order by player, score_moyen_par_tour desc
