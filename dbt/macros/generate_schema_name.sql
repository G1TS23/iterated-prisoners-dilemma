{#
  Schémas "staging"/"marts" tout courts au lieu du "main_staging"/"main_marts"
  par défaut de dbt-duckdb (préfixés du schéma cible). Override standard
  recommandé par dbt : https://docs.getdbt.com/docs/build/custom-schemas
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
