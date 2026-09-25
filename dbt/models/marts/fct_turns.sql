-- Table de faits. Grain : une ligne = (match, tour, joueur).
select
    -- seat (A/B), pas player : en auto-confrontation les deux sièges
    -- partagent le même nom de joueur.
    {{ dbt_utils.generate_surrogate_key(['match_id', 'turn', 'seat']) }} as turn_key,
    t.*,
    a.coded_equivalent as player_coded_equivalent,   -- utile pour agg_llm_vs_coded
    a.equivalence as player_equivalence
from {{ ref('stg_turns') }} t
left join {{ ref('dim_agent') }} a on t.player = a.agent_name
