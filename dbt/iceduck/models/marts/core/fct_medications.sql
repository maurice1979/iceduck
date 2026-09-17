{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

select
    patient_id,
    encounter_id,
    payer_id,
    cast(started_at as date) as medication_date,
    code,
    description,
    reason_code,
    reason_description,
    started_at,
    stopped_at,
    base_cost,
    payer_coverage,
    total_cost,
    dispenses
from {{ iceberg_source('silver', 'stg_medications') }}
