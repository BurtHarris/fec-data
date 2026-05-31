{% macro fec_source_path(table_name, entry_name) -%}
    {#-
      Build the DuckDB zipfs path for one FEC source entry.
      dbt renders this at compile time, so the model SQL receives a plain
      string like zip://data/2026/indiv26.zip/itcont.txt. Keep commands rooted
      at the repository directory so DuckDB resolves the relative path.
    -#}
    {%- set cycle = var('cycle') | string -%}
    {%- set yy = cycle[-2:] -%}
    {%- set zip_path = 'data/' ~ cycle ~ '/' ~ table_name ~ yy ~ '.zip' -%}
    {{ return('zip://' ~ zip_path | replace('\\', '/') ~ '/' ~ entry_name) }}
{%- endmacro %}

{% macro fec_table_alias(table_name) -%}
    {# Keep the existing naming convention: raw_fec.<table>_<cycle>. #}
    {{ return(table_name ~ '_' ~ (var('cycle') | string)) }}
{%- endmacro %}

{% macro fec_cycle_suffix() -%}
    {# Return the two-digit cycle suffix used in FEC filenames, e.g. 26. #}
    {%- set cycle = var('cycle') | string -%}
    {{ return(cycle[-2:]) }}
{%- endmacro %}
