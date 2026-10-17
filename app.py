"""Streamlit dashboard. Run: streamlit run dashboard/app.py"""
import os
import sqlite3
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.insights import answer, compute_metrics, summarize  # noqa: E402

DB = os.getenv("WAREHOUSE_DB", "data/warehouse.db")
st.set_page_config(page_title="Retail Sales Dashboard", layout="wide")
st.title("Retail Sales Dashboard")

if not os.path.exists(DB):
    st.error("Warehouse not found. Run `python -m src.generate_data` then `python -m src.etl` first.")
    st.stop()

con = sqlite3.connect(DB)
all_countries = [r[0] for r in con.execute("SELECT country FROM dim_region ORDER BY country")]
picked = st.sidebar.multiselect("Country", all_countries, default=all_countries)
if not picked:
    st.warning("Select at least one country.")
    st.stop()


@st.cache_data(show_spinner=False)
def metrics_for(countries: tuple):
    return compute_metrics(DB, list(countries))


m = metrics_for(tuple(picked))
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"{m['total_revenue']:,.0f}", f"{m['latest_mom_pct']:+.1f}% MoM" if m["latest_mom_pct"] is not None else None)
c2.metric("Orders", f"{m['orders']:,}")
c3.metric("Customers", f"{m['customers']:,}")
c4.metric("Avg order value", f"{m['aov']:,.2f}")

left, right = st.columns(2)
left.subheader("Monthly revenue")
left.line_chart(pd.DataFrame(m["monthly_revenue"], columns=["month", "revenue"]).set_index("month"))
right.subheader("Top 5 products")
right.bar_chart(pd.DataFrame(m["top_products"], columns=["product", "revenue"]).set_index("product"))
st.subheader("Revenue by country")
st.bar_chart(pd.DataFrame(m["revenue_by_country"], columns=["country", "revenue"]).set_index("country"))

st.subheader("AI insights")
if st.button("Generate summary"):
    st.write(summarize(m))
q = st.text_input("Ask a question about these numbers")
if q:
    st.write(answer(q, m))
