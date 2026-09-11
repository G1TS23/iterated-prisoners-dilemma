-- Classement type "tournoi Axelrod" : score moyen par tour, taux de
-- coopération, tendance à pardonner/riposter, par agent.
select
    f.player as agent,
    a.agent_type,
    count(*)                                   as n_turns_joues,
    count(distinct f.match_id)                 as n_matches,
    avg(f.payoff)                              as score_moyen_par_tour,
    sum(f.payoff)                              as score_total,
    avg(case when f.move = 'C' then 1.0 else 0 end)          as taux_cooperation,
    -- taux de pardon/riposte : uniquement sur les tours où l'occasion se
    -- présentait (l'adversaire venait de trahir), sinon le taux est écrasé
    -- par tous les tours sans trahison adverse.
    avg(case when f.opponent_last_move = 'D' then
            case when f.forgave_this_turn then 1.0 else 0 end end)    as taux_pardon,
    avg(case when f.opponent_last_move = 'D' then
            case when f.retaliated_this_turn then 1.0 else 0 end end) as taux_riposte,
    avg(f.response_time)                       as temps_moyen_reponse_s
from {{ ref('fct_turns') }} f
left join {{ ref('dim_agent') }} a on f.player = a.agent_name
group by f.player, a.agent_type
order by score_moyen_par_tour desc
