{# Defaults to an empty location (rather than a hard var() lookup error) so
   `dbt docs generate`/`dbt parse` can compile every model without needing
   real vars — those are only supplied by iceduck build-silver/build-gold's
   --vars flag for an actual run. #}
{% macro iceberg_source(layer, entity) %}
iceberg_scan('{{ var(layer ~ "_metadata_locations", {}).get(entity, "") }}')
{% endmacro %}
