{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do ref('stg_encounters') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    id as encounter_id,
    patient_id,
    organization_id,
    provider_id,
    payer_id,
    cast(started_at as date) as encounter_date,
    encounter_class,
    code,
    description,
    reason_code,
    reason_description,
    started_at,
    stopped_at,
    base_encounter_cost,
    total_claim_cost,
    payer_coverage
from {{ iceberg_source('silver', 'stg_encounters') }}
