{% macro iceberg_source(layer, entity) %}
iceberg_scan('{{ var(layer ~ "_metadata_locations")[entity] }}')
{% endmacro %}
