"""SQL console tab: ad-hoc queries over every lake layer, for prototyping dbt models.

Every Glue-registered Iceberg table is exposed as a DuckDB view named
``<layer>.<table>`` (``bronze.encounters``, ``silver.stg_encounters``,
``gold.fct_readmissions``) via `iceduck.core.duckdb_session.register_lake_views`.
"""

import time

import duckdb
import pandas as pd
import streamlit as st

from iceduck.core.duckdb_session import LAKE_SCHEMAS, connect_floci, register_lake_views

# Rows fetched into the browser per query; the rest are not materialised at all.
MAX_ROWS = 10_000
DEFAULT_QUERY = "select *\nfrom gold.fct_readmissions\nlimit 100"
RESULT_KEY = "sql_console_result"


@st.cache_resource
def get_console_session() -> tuple[duckdb.DuckDBPyConnection, pd.DataFrame]:
    """Build the console's own DuckDB session with a view per lake table, cached per process.

    Separate from the dashboard's connection, so a stray ``DROP``/``SET`` typed here
    can't break the dashboard. Views are pinned to the Iceberg snapshots current when
    this runs; clearing the cache (sidebar "Refresh data") re-pins them.

    Returns
    -------
    tuple[duckdb.DuckDBPyConnection, pd.DataFrame]
        The connection, and a catalog of the registered views (schema, table, columns).
    """
    con = connect_floci()
    register_lake_views(con)
    schemas = ", ".join(f"'{schema}'" for schema in LAKE_SCHEMAS)
    catalog = con.sql(f"""
        select table_schema as schema, table_name as "table",
               string_agg(column_name, ', ' order by ordinal_position) as columns
        from information_schema.columns
        where table_schema in ({schemas})
        group by all
        order by schema, "table"
    """).df()
    return con, catalog


def run_query(con: duckdb.DuckDBPyConnection, query: str) -> dict:
    """Execute one console query and capture its outcome for rendering.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        The console session.
    query : str
        The SQL typed by the user.

    Returns
    -------
    dict
        ``error`` (str | None), ``df`` (DataFrame | None — None for statements without a
        result set), ``truncated`` (bool), and ``elapsed_ms`` (float).
    """
    started = time.perf_counter()
    try:
        relation = con.sql(query)
        df = None if relation is None else relation.limit(MAX_ROWS + 1).df()
    except duckdb.Error as exc:
        return {"error": str(exc), "df": None, "truncated": False, "elapsed_ms": 0.0}
    elapsed_ms = (time.perf_counter() - started) * 1000
    truncated = df is not None and len(df) > MAX_ROWS
    if truncated:
        df = df.head(MAX_ROWS)
    return {"error": None, "df": df, "truncated": truncated, "elapsed_ms": elapsed_ms}


def render_sql_console() -> None:
    """Render the SQL console tab: table catalog, query editor, and the last result."""
    st.caption(
        "Query any lake table as `<layer>.<table>` — e.g. `silver.stg_encounters`, `gold.fct_readmissions`. "
        "To turn a query into a dbt model, replace `silver.stg_x` with "
        "`{{ iceberg_source('silver', 'stg_x') }}` and add `{% do ref('stg_x') %}` at the top. "
        "Local dev tool: it runs any SQL you give it, in its own DuckDB session."
    )

    con, catalog = get_console_session()

    with st.expander(f"Available tables ({len(catalog)})"):
        st.dataframe(catalog, width="stretch", hide_index=True)

    with st.form("sql_console"):
        query = st.text_area("SQL", value=DEFAULT_QUERY, height=200, key="sql_console_query")
        submitted = st.form_submit_button("Run", type="primary")

    if submitted and query.strip():
        st.session_state[RESULT_KEY] = run_query(con, query)

    result = st.session_state.get(RESULT_KEY)
    if result is None:
        return
    if result["error"]:
        st.error(result["error"])
    elif result["df"] is None:
        st.success(f"OK — statement executed in {result['elapsed_ms']:.0f} ms (no result set).")
    else:
        df = result["df"]
        note = f" — truncated to the first {MAX_ROWS:,} rows" if result["truncated"] else ""
        st.caption(f"{len(df):,} rows in {result['elapsed_ms']:.0f} ms{note}")
        st.dataframe(df, width="stretch", hide_index=True)
