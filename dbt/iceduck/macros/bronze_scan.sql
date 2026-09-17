{% macro bronze_scan(entity) %}
iceberg_scan('{{ var("bronze_metadata_locations")[entity] }}')
{% endmacro %}
