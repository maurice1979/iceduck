{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

{% do ref('stg_conditions') %}  {# dependency registration only — real read is iceberg_source() below #}

select
    patient_id,
    encounter_id,
    started_on as condition_date,
    code,
    description,
    started_on,
    stopped_on
from {{ iceberg_source('silver', 'stg_conditions') }}
