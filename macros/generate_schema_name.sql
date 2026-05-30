{% macro generate_schema_name(custom_schema_name, node) -%}
    {#-
      dbt's default behavior can prefix custom schemas with the target schema.
      For this local DuckDB project we want literal schemas like raw_fec.
    -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
