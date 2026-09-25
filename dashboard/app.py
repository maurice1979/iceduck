"""IceDuck analyst dashboard.

Reads the gold layer (``iceduck_gold``) directly via a fresh DuckDB session, using the
same resolve-then-``iceberg_scan`` mechanism as the rest of this project — not Athena.
Two tabs: the dashboard itself, and a SQL console over every lake layer (``sql_console.py``,
imported as a sibling module since ``streamlit run`` puts this directory on ``sys.path``).
"""

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from sql_console import get_console_session, render_sql_console

from iceduck.core.duckdb_session import connect_floci
from iceduck.core.glue_lookup import resolve_metadata_locations
from iceduck.core.settings import GLUE_DATABASE_GOLD

GOLD_TABLES = [
    "dim_patient",
    "dim_provider",
    "dim_organization",
    "dim_date",
    "fct_encounters",
    "fct_medications",
    "fct_conditions",
    "fct_readmissions",
]

# Years with fewer eligible inpatient stays than this are left off the rate-over-time
# chart: a yearly rate over a handful of stays is noise (many pre-2010 years have 1-10).
MIN_STAYS_PER_YEAR = 30

st.set_page_config(page_title="IceDuck", page_icon="🦆", layout="wide")


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Build the dashboard's DuckDB session, cached so it's only built once per Streamlit process.

    Returns
    -------
    duckdb.DuckDBPyConnection
        A connection from `connect_floci` (``httpfs``/``iceberg`` + the ``floci_s3`` secret).
    """
    return connect_floci()


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


def render_dashboard() -> None:
    """Render the dashboard tab: KPIs and charts over the gold tables, plus a raw-table browser."""
    locations = get_locations()

    patients = load_table("dim_patient", locations)
    providers = load_table("dim_provider", locations)
    organizations = load_table("dim_organization", locations)
    dim_date = load_table("dim_date", locations)
    encounters = load_table("fct_encounters", locations)
    medications = load_table("fct_medications", locations)
    conditions = load_table("fct_conditions", locations)
    readmissions = load_table("fct_readmissions", locations)

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
    st.plotly_chart(px.bar(enc_by_month, x="period", y="size", title="Encounters over time"), width="stretch")

    col_a, col_b = st.columns(2)
    with col_a:
        by_class = encounters["encounter_class"].value_counts().reset_index()
        by_class.columns = ["encounter_class", "count"]
        st.plotly_chart(px.bar(by_class, x="encounter_class", y="count", title="Encounters by class"), width="stretch")

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
            width="stretch",
        )

    col_c, col_d = st.columns(2)
    with col_c:
        top_conditions = conditions["description"].value_counts().head(10).reset_index()
        top_conditions.columns = ["condition", "count"]
        st.plotly_chart(
            px.bar(top_conditions, x="count", y="condition", orientation="h", title="Top 10 conditions"),
            width="stretch",
        )

    with col_d:
        top_meds = medications["description"].value_counts().head(10).reset_index()
        top_meds.columns = ["medication", "count"]
        st.plotly_chart(
            px.bar(top_meds, x="count", y="medication", orientation="h", title="Top 10 medications"),
            width="stretch",
        )

    st.divider()

    st.subheader("30-day inpatient readmissions")
    st.caption(
        "Rates count only stays with a full 30-day follow-up window (has_full_followup). "
        "Planned readmissions are included — Synthea has no planned-admission flag — so rates "
        "run well above the ~15% typical of real-world data."
    )

    eligible = readmissions[readmissions["has_full_followup"]]
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Inpatient stays", f"{len(readmissions):,}")
    col_r2.metric("Readmitted within 30 days", f"{int(readmissions['is_readmitted_30d'].sum()):,}")
    col_r3.metric("Readmission rate", f"{eligible['is_readmitted_30d'].mean():.1%}")

    col_e, col_f = st.columns(2)
    with col_e:
        rate_by_type = (
            eligible.merge(encounters[["encounter_id", "description"]], on="encounter_id")
            .groupby("description", as_index=False)
            .agg(stays=("encounter_id", "size"), readmission_rate=("is_readmitted_30d", "mean"))
            .sort_values("readmission_rate")
        )
        st.plotly_chart(
            px.bar(
                rate_by_type,
                x="readmission_rate",
                y="description",
                orientation="h",
                hover_data={"stays": True},
                title="Readmission rate by admission type",
            ).update_xaxes(tickformat=".0%", title="readmission rate"),
            width="stretch",
        )

    with col_f:
        readmitted = readmissions[readmissions["is_readmitted_30d"]]
        st.plotly_chart(
            px.histogram(
                readmitted,
                x="days_to_next_admission",
                nbins=30,
                title="Days from discharge to readmission",
            ).update_layout(xaxis_title="days after discharge", yaxis_title="readmissions", bargap=0.1),
            width="stretch",
        )

    rate_by_year = (
        eligible.assign(year=pd.to_datetime(eligible["discharge_date"]).dt.year)
        .groupby("year", as_index=False)
        .agg(stays=("encounter_id", "size"), readmission_rate=("is_readmitted_30d", "mean"))
        .query("stays >= @MIN_STAYS_PER_YEAR")
    )
    st.plotly_chart(
        px.line(
            rate_by_year,
            x="year",
            y="readmission_rate",
            markers=True,
            hover_data={"stays": True},
            title=f"Readmission rate by discharge year (years with ≥ {MIN_STAYS_PER_YEAR} eligible stays)",
        ).update_yaxes(tickformat=".0%", title="readmission rate", rangemode="tozero"),
        width="stretch",
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
        "fct_readmissions": readmissions,
    }
    table_choice = st.selectbox("Table", GOLD_TABLES)
    st.dataframe(tables[table_choice], width="stretch")


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
        get_console_session.clear()
        st.rerun()

tab_dashboard, tab_sql = st.tabs(["Dashboard", "SQL console"])
with tab_dashboard:
    render_dashboard()
with tab_sql:
    render_sql_console()
