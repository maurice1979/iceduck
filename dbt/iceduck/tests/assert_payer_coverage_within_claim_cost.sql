select
    encounter_id, total_claim_cost, payer_coverage
from
    {{ ref('fct_encounters') }}
where
    payer_coverage > total_claim_cost
