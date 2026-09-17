{{ config(materialized='external', location='target/silver/' ~ this.identifier ~ '.parquet', format='parquet') }}

select
    "PATIENT" as patient_id,
    "ENCOUNTER" as encounter_id,
    "CODE" as code,
    "DESCRIPTION" as description,
    "START" as started_on,
    "STOP" as stopped_on
from {{ iceberg_source('bronze', 'conditions') }}
