{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do ref('stg_organizations') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    id as organization_id,
    name,
    address,
    city,
    state,
    zip,
    phone,
    latitude,
    longitude,
    revenue,
    utilization
from {{ iceberg_source('silver', 'stg_organizations') }}
