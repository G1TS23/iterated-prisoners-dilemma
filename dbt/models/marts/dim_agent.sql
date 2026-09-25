with used as (
    select distinct player as agent_name from {{ ref('stg_turns') }}
),
meta as (
    select * from {{ ref('agent_meta') }}
)

select
    used.agent_name,
    meta.agent_type,
    meta.description,
    meta.coded_equivalent,
    meta.equivalence   -- 'stricte' : le persona est censé imiter la règle ; 'approchee' : variante volontairement différente
from used
left join meta on used.agent_name = meta.agent_name
