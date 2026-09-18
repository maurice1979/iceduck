{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do ref('stg_patients') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    id as patient_id,
    birthdate,
    deathdate,
    ssn,
    drivers,
    passport,
    prefix,
    first_name,
    last_name,
    suffix,
    maiden_name,
    marital_status,
    race,
    ethnicity,
    gender,
    birthplace,
    address,
    city,
    state,
    county,
    zip,
    latitude,
    longitude,
    healthcare_expenses,
    healthcare_coverage
from {{ iceberg_source('silver', 'stg_patients') }}
