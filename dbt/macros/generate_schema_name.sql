{#
  By default dbt names schemas "<target schema>_<custom schema>", e.g. "main_staging".
  This macro uses the custom name as-is, so we get "staging", "intermediate", "marts".
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}