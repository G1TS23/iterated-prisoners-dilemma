{{ config(materialized='ephemeral') }}

-- Pour chaque décision d'un agent IA : quel coup son ÉQUIVALENT CODÉ aurait-il
-- joué avec exactement le même historique ? (base du système d'évaluation
-- des prompts demandé par le sujet : fidélité tour par tour du persona à la
-- règle qu'il est censé incarner.)
with base as (
    select
        f.*,
        -- l'adversaire a-t-il trahi à un tour STRICTEMENT antérieur ? (grim trigger)
        coalesce(max(case when f.opponent_move = 'D' then 1 else 0 end) over (
            partition by f.match_id, f.seat
            order by f.turn
            rows between unbounded preceding and 1 preceding
        ), 0) as opp_defected_before
    from {{ ref('fct_turns') }} f
    where f.player_type = 'llm'
)

select
    *,
    case player_coded_equivalent
        when 'tit_for_tat'      then case when turn = 1 then 'C' else opponent_last_move end
        when 'grim_trigger'     then case when opp_defected_before = 1 then 'D' else 'C' end
        when 'always_cooperate' then 'C'
        when 'always_defect'    then 'D'
        else null   -- 'random' : pas de coup attendu déterministe
    end as expected_move
from base
