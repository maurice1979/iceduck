{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do ref('stg_providers') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    id as provider_id,
    organization_id,
    name,
    gender,
    speciality,
    address,
    city,
    state,
    zip,
    latitude,
    longitude,
    utilization
from {{ iceberg_source('silver', 'stg_providers') }}
