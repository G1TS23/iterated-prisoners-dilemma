-- Même mesure de fidélité, ventilée par adversaire : contre qui le persona
-- « décroche »-t-il de sa règle ? (ex. un rancunier qui recoopère face à
-- always_defect.)
select
    player                                              as persona,
    opponent,
    count(*)                                            as n_tours,
    avg(case when expected_move is null then null
             when move = expected_move then 1.0 else 0 end) as fidelite
from {{ ref('int_persona_expected_move') }}
group by player, opponent
order by persona, fidelite
