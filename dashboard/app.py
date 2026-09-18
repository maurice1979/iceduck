"""IceDuck analyst dashboard.

Reads the gold layer (``iceduck_gold``) directly via a fresh DuckDB session, using the
same resolve-then-``iceberg_scan`` mechanism as the rest of this project — not Athena.
"""

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

from iceduck.core.glue_lookup import resolve_metadata_locations
from iceduck.core.settings import GLUE_DATABASE_GOLD, settings

GOLD_TABLES = [
    "dim_patient",
    "dim_provider",
    "dim_organization",
    "dim_date",
    "fct_encounters",
    "fct_medications",
    "fct_conditions",
]

st.set_page_config(page_title="IceDuck", page_icon="🦆", layout="wide")


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Build a cached DuckDB session with the S3 secret needed to read Floci-hosted Iceberg tables.

    Returns
    -------
    duckdb.DuckDBPyConnection
        A DuckDB connection with ``httpfs``/``iceberg`` loaded and the ``floci_s3``
        secret configured. Cached via ``st.cache_resource`` so it's only built once
        per Streamlit process.
    """
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; INSTALL iceberg; LOAD iceberg;")
    endpoint = settings.aws_endpoint_url.replace("http://", "").replace("https://", "")
    con.sql(f"""
        CREATE SECRET floci_s3 (
            TYPE s3,
            KEY_ID '{settings.aws_access_key_id}',
            SECRET '{settings.aws_secret_access_key}',
            REGION '{settings.aws_default_region}',
            ENDPOINT '{endpoint}',
            URL_STYLE 'path',
            USE_SSL false
        );
    """)
    return con


@st.cache_data(ttl=300)
def get_locations() -> dict[str, str]:
    """Resolve every gold table's current ``metadata_location``, cached for 5 minutes.

    Returns
    -------
    dict[str, str]
        Mapping of table name to its current ``metadata_location`` S3 URI.
    """
    return resolve_metadata_locations(GLUE_DATABASE_GOLD, GOLD_TABLES)


@st.cache_data(ttl=300)
def load_table(table: str, _locations: dict[str, str]) -> pd.DataFrame:
    """Read one gold table into a DataFrame via ``iceberg_scan``, cached for 5 minutes.

    Parameters
    ----------
    table : str
        The gold table name to load (a key into `_locations`).
    _locations : dict[str, str]
        Table-name-to-``metadata_location`` mapping from `get_locations`. Leading
        underscore tells Streamlit not to hash this argument for cache-key purposes.

    Returns
    -------
    pd.DataFrame
        The table's full contents.
    """
    con = get_connection()
    return con.sql(f"SELECT * FROM iceberg_scan('{_locations[table]}')").df()


st.title("🦆 IceDuck — Synthea EHR Dashboard")
st.caption(
    "Gold layer (iceduck_gold), real Iceberg tables, read via a fresh DuckDB "
    "session — no Athena involved (ADR-0007 / ADR-0011)."
)

with st.sidebar:
    st.header("Data")
    if st.button("🔄 Refresh data"):
        get_locations.clear()
        load_table.clear()
        st.rerun()

locations = get_locations()

patients = load_table("dim_patient", locations)
providers = load_table("dim_provider", locations)
organizations = load_table("dim_organization", locations)
dim_date = load_table("dim_date", locations)
encounters = load_table("fct_encounters", locations)
medications = load_table("fct_medications", locations)
conditions = load_table("fct_conditions", locations)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Patients", f"{len(patients):,}")
col2.metric("Encounters", f"{len(encounters):,}")
col3.metric("Organizations", f"{len(organizations):,}")
col4.metric("Total claim cost", f"${encounters['total_claim_cost'].sum():,.0f}")

st.divider()

enc_by_date = encounters.merge(dim_date, left_on="encounter_date", right_on="date_day")
enc_by_month = (
    enc_by_date.groupby(["year", "month", "month_name"], as_index=False).size().sort_values(["year", "month"])
)
enc_by_month["period"] = enc_by_month["month_name"] + " " + enc_by_month["year"].astype(str)
st.plotly_chart(px.bar(enc_by_month, x="period", y="size", title="Encounters over time"), use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    by_class = encounters["encounter_class"].value_counts().reset_index()
    by_class.columns = ["encounter_class", "count"]
    st.plotly_chart(
        px.bar(by_class, x="encounter_class", y="count", title="Encounters by class"), use_container_width=True
    )

with col_b:
    cost_by_org = (
        encounters.merge(organizations, on="organization_id")
        .groupby("name", as_index=False)
        .agg(total_claim_cost=("total_claim_cost", "sum"))
        .sort_values("total_claim_cost", ascending=False)
        .head(10)
    )
    st.plotly_chart(
        px.bar(cost_by_org, x="name", y="total_claim_cost", title="Total cost by organization (top 10)"),
        use_container_width=True,
    )

col_c, col_d = st.columns(2)
with col_c:
    top_conditions = conditions["description"].value_counts().head(10).reset_index()
    top_conditions.columns = ["condition", "count"]
    st.plotly_chart(
        px.bar(top_conditions, x="count", y="condition", orientation="h", title="Top 10 conditions"),
        use_container_width=True,
    )

with col_d:
    top_meds = medications["description"].value_counts().head(10).reset_index()
    top_meds.columns = ["medication", "count"]
    st.plotly_chart(
        px.bar(top_meds, x="count", y="medication", orientation="h", title="Top 10 medications"),
        use_container_width=True,
    )

st.divider()

st.subheader("Browse raw tables")
tables = {
    "dim_patient": patients,
    "dim_provider": providers,
    "dim_organization": organizations,
    "dim_date": dim_date,
    "fct_encounters": encounters,
    "fct_medications": medications,
    "fct_conditions": conditions,
}
table_choice = st.selectbox("Table", GOLD_TABLES)
st.dataframe(tables[table_choice], use_container_width=True)
