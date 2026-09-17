{{ config(materialized='external', location='target/silver/' ~ this.identifier ~ '.parquet', format='parquet') }}

select
    "Id" as id,
    "NAME" as name,
    "ADDRESS" as address,
    "CITY" as city,
    "STATE" as state,
    "ZIP" as zip,
    "PHONE" as phone,
    "LAT" as latitude,
    "LON" as longitude,
    "REVENUE" as revenue,
    "UTILIZATION" as utilization
from {{ bronze_scan('organizations') }}
