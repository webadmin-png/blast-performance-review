"""
app.py — Streamlit UI for the blast-performance report.

Run with:  streamlit run app.py

User picks a blast period + channel; the app fetches orders live from Shopify,
transforms them, and builds the per-channel blast report with a configurable
carryover window. Heavy fetches are cached so toggling the channel does not
re-hit the API.
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from connection.shopify_api import fetch_orders_utm
from utils.transform import transform_campaign_data
from utils.report_generator import build_blast_report
from auth.token_manager import get_token
from config import settings

# Days of safety padding added to BOTH ends of the fetch range. Backward padding
# does not change the report (data before the blast start is filtered out) but is
# kept as a margin against timezone/edge effects.
FETCH_PAD_DAYS = 7

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


def filter_to_blast_dates(attentive: pd.DataFrame, blast_dates, carryover_days: int) -> pd.DataFrame:
    """Keep only attentive rows for the chosen blast day(s), each bounded by its own carryover window.

    A row is kept if its blast_date is one of `blast_dates` AND its order day falls in
    [blast_date, blast_date + carryover_days]. This excludes any other blasts that fall
    between the chosen dates, and stops one blast's carryover from bleeding into another.
    """
    bd = pd.to_datetime(attentive["blast_date"], errors="coerce").dt.normalize()
    od = pd.to_datetime(attentive["day"], errors="coerce").dt.normalize()
    keep = pd.Series(False, index=attentive.index)
    for d in blast_dates:
        t = pd.Timestamp(d)
        keep |= (bd == t) & (od >= t) & (od <= t + pd.Timedelta(days=int(carryover_days)))
    return attentive[keep].copy()


st.set_page_config(page_title="Blast Performance Report", layout="wide")
st.title("📊 Blast Performance Report")
st.caption("Fetch Shopify orders live and build the per-channel blast report.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")
    today = date.today()
    blast_date_1 = st.date_input(
        "Blast date 1",
        value=today,
        help="The (first) blast day to analyze.",
    )
    use_two = st.checkbox("Add a 2nd blast date")
    blast_date_2 = st.date_input(
        "Blast date 2",
        value=today,
        help="A second, independent blast day (need not be adjacent to the first).",
        disabled=not use_two,
    )
    carryover_days = st.number_input(
        "Carryover window (days)",
        min_value=0, max_value=60, value=2,
        help="Days after the blast to keep counting attributed orders.",
    )
    channel_labels = st.multiselect(
        "Channel(s)",
        options=list(CHANNELS.keys()),
        default=list(CHANNELS.keys()),
    )
    generate = st.button("Generate Report", type="primary", use_container_width=True)

# One or two distinct blast days (deduped, sorted). Each is analyzed with its own
# carryover window; days between them are NOT pulled in.
blast_dates = sorted({blast_date_1, blast_date_2} if use_two else {blast_date_1})
blast_start, blast_end = blast_dates[0], blast_dates[-1]

# ── Run pipeline ────────────────────────────────────────────────────────────
if generate:
    if not channel_labels:
        st.warning("Pick at least one channel.")
        st.stop()

    report_end = blast_end + timedelta(days=int(carryover_days))
    fetch_start = blast_start - timedelta(days=FETCH_PAD_DAYS)
    fetch_end = report_end + timedelta(days=FETCH_PAD_DAYS)

    st.info(
        f"Blast day(s): **{' & '.join(str(d) for d in blast_dates)}**  ·  "
        f"carryover **{int(carryover_days)}d** (to {report_end})  ·  "
        f"fetching Shopify **{fetch_start} → {fetch_end}**"
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
    # Restrict blast attribution to the chosen day(s), each with its own carryover window.
    attentive_orders = filter_to_blast_dates(attentive_orders, blast_dates, carryover_days)
    dates_str = " & ".join(str(d) for d in blast_dates)
    st.success(
        f"Fetched {len(df):,} line-item rows · {len(all_orders):,} orders · "
        f"blast day(s): {dates_str}."
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
                attentive_orders, all_orders, blast_start, report_end, channel=channel
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
            file_name=f"blast_report_{channel}_{blast_start}_to_{report_end}.csv",
            mime="text/csv",
        )
else:
    st.info("Set the parameters in the sidebar and click **Generate Report**.")
