"""
app.py — Streamlit UI for the blast-performance report.

Run with:  streamlit run app.py

User picks a start/end date + channel; the app fetches orders live from Shopify
(padded by FETCH_PAD_DAYS on each side), transforms them, and builds the
per-channel blast report for exactly that period. Heavy fetches are cached so
toggling the channel does not re-hit the API.
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from connection.shopify_api import fetch_orders_utm
from utils.transform import transform_campaign_data
from utils.report_generator import build_blast_report
from auth.token_manager import get_token
from config import settings

# Days of safety padding added to BOTH ends of the fetch range, as a margin
# against timezone/edge effects. The report itself only counts the chosen
# [start, end] period; data outside it is filtered out by build_blast_report.
FETCH_PAD_DAYS = 2

CHANNELS = {"Email": "email", "SMS": "sms"}


@st.cache_data(show_spinner=False)
def load_raw(fetch_start: str, fetch_end: str) -> pd.DataFrame:
    """Refresh the Shopify token and fetch raw order/UTM rows for a date range.

    Cached on (fetch_start, fetch_end) so changing the channel selection reuses
    the already-fetched data instead of calling the API again.
    """
    get_token()          # mint a fresh access token and write it to .env
    settings.reload()    # re-read .env so HEADERS carries the new token
    return fetch_orders_utm(fetch_start, fetch_end)


def channel_summary(report: pd.DataFrame, channel: str) -> tuple[int, float]:
    """Return (total units, total gross $) from a report's channel grand-total columns."""
    units_col = next((c for c in report.columns if c.startswith(f"{channel} Grand Total sales")), None)
    gross_col = next((c for c in report.columns if c.startswith("Grand Total Sales") and c.endswith("($)")), None)
    units = int(report[units_col].sum()) if units_col else 0
    gross = float(report[gross_col].sum()) if gross_col else 0.0
    return units, gross


st.set_page_config(page_title="Blast Performance Report", layout="wide")
st.title("📊 Blast Performance Report")
st.caption("Fetch Shopify orders live and build the per-channel blast report.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")
    today = date.today()
    start_date = st.date_input(
        "Start date",
        value=today,
        help="First day of the sales period to report on.",
    )
    end_date = st.date_input(
        "End date",
        value=today,
        help="Last day of the sales period to report on.",
    )
    channel_labels = st.multiselect(
        "Channel(s)",
        options=list(CHANNELS.keys()),
        default=list(CHANNELS.keys()),
    )
    generate = st.button("Generate Report", type="primary", use_container_width=True)

# The report covers exactly [start, end]; normalize so start <= end regardless
# of input order.
period_start, period_end = min(start_date, end_date), max(start_date, end_date)

# ── Run pipeline ────────────────────────────────────────────────────────────
if generate:
    if not channel_labels:
        st.warning("Pick at least one channel.")
        st.stop()

    fetch_start = period_start - timedelta(days=FETCH_PAD_DAYS)
    fetch_end = period_end + timedelta(days=FETCH_PAD_DAYS)

    st.info(
        f"Report period: **{period_start} → {period_end}**  ·  "
        f"fetching Shopify **{fetch_start} → {fetch_end}** (±{FETCH_PAD_DAYS}d padding)"
    )

    try:
        with st.spinner("Fetching orders from Shopify… (this can take a while)"):
            df = load_raw(str(fetch_start), str(fetch_end))
    except Exception as e:
        st.error(f"Failed to fetch data from Shopify: {e}")
        st.stop()

    if df is None or df.empty:
        st.warning("No orders returned for this date range.")
        st.stop()

    attentive_orders, all_orders = transform_campaign_data(df)
    st.success(
        f"Fetched {len(df):,} line-item rows · {len(all_orders):,} orders · "
        f"period {period_start} → {period_end}."
    )

    # ── Pipeline data downloads (the same outputs main.py writes to disk) ──────
    tag = f"{fetch_start}_to_{fetch_end}"
    with st.expander("⬇️ Download pipeline data (raw & processed)"):
        pipeline_outputs = {
            "Raw Shopify line items": (f"shopify_orders_utm_{tag}.csv", df),
            "Campaign data (attentive)": ("campaign_data.csv", attentive_orders),
            "All orders data": ("all_orders_data.csv", all_orders),
        }
        for label, (fname, frame) in pipeline_outputs.items():
            st.download_button(
                f"{label} — {len(frame):,} rows",
                data=frame.to_csv(index=False).encode("utf-8"),
                file_name=fname,
                mime="text/csv",
                key=f"dl_{fname}",
                use_container_width=True,
            )

    for label in channel_labels:
        channel = CHANNELS[label]
        st.subheader(f"{label} report")
        try:
            report = build_blast_report(
                attentive_orders, all_orders, period_start, period_end, channel=channel
            )
        except Exception as e:
            st.error(f"Failed to build the {label} report: {e}")
            continue

        if report.empty:
            st.info(f"No {label} data in this period.")
            continue

        units, gross = channel_summary(report, label if channel == "email" else "SMS")
        c1, c2, c3 = st.columns(3)
        c1.metric(f"{label} units", f"{units:,}")
        c2.metric(f"{label} gross sales", f"${gross:,.2f}")
        c3.metric("Styles × colors", f"{len(report):,}")

        st.dataframe(report, use_container_width=True, hide_index=True)
        st.download_button(
            f"Download {label} CSV",
            data=report.to_csv(index=False).encode("utf-8"),
            file_name=f"blast_report_{channel}_{period_start}_to_{period_end}.csv",
            mime="text/csv",
        )
else:
    st.info("Set the parameters in the sidebar and click **Generate Report**.")