{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

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
