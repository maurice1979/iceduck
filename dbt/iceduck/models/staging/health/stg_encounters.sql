{{ config(materialized='external', location='target/silver/' ~ this.identifier ~ '.parquet', format='parquet') }}

select
    "Id" as id,
    "PATIENT" as patient_id,
    "ORGANIZATION" as organization_id,
    "PROVIDER" as provider_id,
    "PAYER" as payer_id,
    "ENCOUNTERCLASS" as encounter_class,
    "CODE" as code,
    "DESCRIPTION" as description,
    "REASONCODE" as reason_code,
    "REASONDESCRIPTION" as reason_description,
    "START" as started_at,
    "STOP" as stopped_at,
    "BASE_ENCOUNTER_COST" as base_encounter_cost,
    "TOTAL_CLAIM_COST" as total_claim_cost,
    "PAYER_COVERAGE" as payer_coverage
from {{ iceberg_source('bronze', 'encounters') }}
