{{ config(materialized='external', location='target/silver/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do source('bronze', 'patients') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    "Id" as id,
    "BIRTHDATE" as birthdate,
    "DEATHDATE" as deathdate,
    "SSN" as ssn,
    "DRIVERS" as drivers,
    "PASSPORT" as passport,
    "PREFIX" as prefix,
    "FIRST" as first_name,
    "LAST" as last_name,
    "SUFFIX" as suffix,
    "MAIDEN" as maiden_name,
    "MARITAL" as marital_status,
    "RACE" as race,
    "ETHNICITY" as ethnicity,
    "GENDER" as gender,
    "BIRTHPLACE" as birthplace,
    "ADDRESS" as address,
    "CITY" as city,
    "STATE" as state,
    "COUNTY" as county,
    "ZIP" as zip,
    "LAT" as latitude,
    "LON" as longitude,
    "HEALTHCARE_EXPENSES" as healthcare_expenses,
    "HEALTHCARE_COVERAGE" as healthcare_coverage
from {{ iceberg_source('bronze', 'patients') }}
