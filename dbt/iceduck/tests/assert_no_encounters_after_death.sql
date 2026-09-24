{{ config(severity='warn') }}

select
    e.encounter_id, e.patient_id, e.encounter_date, p.deathdate
from
    {{ ref('fct_encounters') }} e
join
    {{ ref('dim_patient') }} p
    on e.patient_id = p.patient_id
where
    p.deathdate is not null
and
    e.encounter_date > p.deathdate