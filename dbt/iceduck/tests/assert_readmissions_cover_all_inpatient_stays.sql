with expected as (
    select count(*) as n from {{ ref('fct_encounters') }}
    where encounter_class = 'inpatient'
),
actual as (
    select count(*) as n from {{ ref('fct_readmissions') }}
)
select e.n as expected_rows, a.n as actual_rows
from expected e cross join actual a
where e.n != a.n