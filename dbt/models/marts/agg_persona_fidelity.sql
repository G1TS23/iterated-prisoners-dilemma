-- Système d'évaluation des prompts : fidélité de chaque persona IA à son
-- équivalent codé, tour par tour (même historique, même décision attendue ?).
--   fidelite                       : part des tours où le persona joue le coup attendu
--   riposte_attendue_respectee     : quand la règle exige de trahir, le persona trahit-il ?
--   cooperation_attendue_respectee : quand la règle exige de coopérer, le persona coopère-t-il ?
select
    player                                              as persona,
    player_coded_equivalent                             as coded_equivalent,
    player_equivalence                                  as equivalence,
    count(*)                                            as n_tours,
    count(expected_move)                                as n_tours_evaluables,
    avg(case when expected_move is null then null
             when move = expected_move then 1.0 else 0 end)        as fidelite,
    avg(case when expected_move = 'D' then
             case when move = 'D' then 1.0 else 0 end end)         as riposte_attendue_respectee,
    avg(case when expected_move = 'C' then
             case when move = 'C' then 1.0 else 0 end end)         as cooperation_attendue_respectee,
    avg(is_parsable::int)                               as taux_parsable
from {{ ref('int_persona_expected_move') }}
group by player, player_coded_equivalent, player_equivalence
order by fidelite desc
