{{ config(materialized='external', location='target/silver/' ~ this.identifier ~ '.parquet', format='parquet') }}

select
    "PATIENT" as patient_id,
    "PAYER" as payer_id,
    "ENCOUNTER" as encounter_id,
    "CODE" as code,
    "DESCRIPTION" as description,
    "REASONCODE" as reason_code,
    "REASONDESCRIPTION" as reason_description,
    "START" as started_at,
    "STOP" as stopped_at,
    "BASE_COST" as base_cost,
    "PAYER_COVERAGE" as payer_coverage,
    "TOTALCOST" as total_cost,
    "DISPENSES" as dispenses
from {{ iceberg_source('bronze', 'medications') }}
