{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

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
