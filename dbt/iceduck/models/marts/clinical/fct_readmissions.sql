{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

{#
  One row per inpatient stay (the "index" stay), flagging whether the same patient was
  readmitted as an inpatient within 30 days of discharge.

  The next admission is found with an ASOF join (the first inpatient stay starting at
  or after this one's discharge), not lead(): lead() picks the next stay by start time,
  which for the ~120 stays that overlap a transfer is the overlapping one, so it
  misses the true readmission after it.

  Simplification vs. the CMS measure: Synthea has no planned-admission flag, so planned
  readmissions (e.g. repeat detox stays) count too, which inflates the rate.
#}

with inpatient as (
    select encounter_id, patient_id, started_at, stopped_at
    from {{ ref('int_encounters__enriched') }}
    where encounter_class = 'inpatient'
),

data_end as (
    select max(started_at) as last_observed_at from inpatient
),

index_stays as (
    select
        idx.encounter_id,
        idx.patient_id,
        idx.started_at                                 as admitted_at,
        idx.stopped_at                                 as discharged_at,
        nxt.encounter_id                               as next_admission_encounter_id,
        nxt.started_at                                 as next_admitted_at
    from inpatient idx
    asof left join inpatient nxt
        on idx.patient_id = nxt.patient_id
        and nxt.started_at >= idx.stopped_at
)

select
    s.encounter_id,
    s.patient_id,
    cast(s.discharged_at as date)                                          as discharge_date,
    s.admitted_at,
    s.discharged_at,
    s.next_admission_encounter_id,
    s.next_admitted_at,
    epoch(s.next_admitted_at - s.discharged_at) / 86400.0                  as days_to_next_admission,
    coalesce(s.next_admitted_at <= s.discharged_at + interval 30 day, false) as is_readmitted_30d,
    -- false for stays discharged in the last 30 days of data: their 30-day window is
    -- incomplete, so exclude them from a readmission-rate denominator.
    s.discharged_at <= d.last_observed_at - interval 30 day                as has_full_followup
from index_stays s
cross join data_end d
