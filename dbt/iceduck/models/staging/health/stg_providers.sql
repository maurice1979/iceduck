{{ config(materialized='external', location='target/silver/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do source('bronze', 'providers') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    "Id" as id,
    "ORGANIZATION" as organization_id,
    "NAME" as name,
    "GENDER" as gender,
    "SPECIALITY" as speciality,
    "ADDRESS" as address,
    "CITY" as city,
    "STATE" as state,
    "ZIP" as zip,
    "LAT" as latitude,
    "LON" as longitude,
    "UTILIZATION" as utilization
from {{ iceberg_source('bronze', 'providers') }}
