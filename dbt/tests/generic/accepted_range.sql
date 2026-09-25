{#
  Test générique : échoue pour toute ligne hors de [min_value, max_value]
  (les NULL sont ignorés). Remplace dbt_utils.accepted_range.
#}
{% test accepted_range(model, column_name, min_value, max_value) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }}
{% endtest %}
