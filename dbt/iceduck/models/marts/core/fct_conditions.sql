{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

select
    patient_id,
    encounter_id,
    started_on as condition_date,
    code,
    description,
    started_on,
    stopped_on
from {{ iceberg_source('silver', 'stg_conditions') }}
