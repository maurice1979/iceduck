{{ config(materialized='table', catalog_name='glue_catalog') }}

select 1 as id, 'a' as label
