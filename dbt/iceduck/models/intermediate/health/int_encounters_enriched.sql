{{ config(materialized='ephemeral') }}

{% do ref('stg_encounters') %}
{% do ref('stg_patients') %}

with encounters as (
    select id as encounter_id, patient_id, encounter_class, started_at, stopped_at, total_claim_cost, payer_coverage
    from {{ iceberg_source('silver', 'stg_encounters') }}
),

patients as (
    select id as patient_id, birthdate
    from {{ iceberg_source('silver', 'stg_patients') }}
)

select
    e.encounter_id,
    e.patient_id,
    e.encounter_class,
    e.started_at,
    e.stopped_at,
    cast(e.started_at as date)                                      as encounter_date,
    date_part('year', age(cast(e.started_at as date), p.birthdate)) as patient_age_at_encounter,
    epoch(e.stopped_at - e.started_at) / 3600.0                     as encounter_duration_hours,
    e.total_claim_cost - e.payer_coverage                           as out_of_pocket_cost
from encounters e
left join patients p on e.patient_id = p.patient_id
