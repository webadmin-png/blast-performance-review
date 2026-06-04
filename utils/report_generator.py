"""
utils/report_generator.py
This module contains functions to generate reports based on campaign data, including formatting and exporting data for analysis or presentation.
It serves as a utility for creating insights and summaries from the campaign data.
"""
import pandas as pd


def _normalize_period(start, end=None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Normalize a user-chosen period into (start, end) timestamps at midnight.

    Pass one date for a single day, or two dates for a range. Dates may be
    strings ('2026-05-30') or datetime-like. Always returned ascending.
    """
    start_ts = pd.to_datetime(start, errors="coerce")
    if pd.isna(start_ts):
        raise ValueError(f"Invalid start date: {start!r}")
    start_ts = start_ts.normalize()

    if end is None:
        return start_ts, start_ts

    end_ts = pd.to_datetime(end, errors="coerce")
    if pd.isna(end_ts):
        raise ValueError(f"Invalid end date: {end!r}")
    end_ts = end_ts.normalize()

    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts
    return start_ts, end_ts


def _fmt_day(ts: pd.Timestamp) -> str:
    """Format a single day as 'May 30'."""
    return f"{ts.strftime('%b')} {ts.day}"


def _fmt_period(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """Format a period: 'May 30' / 'May 30 - 31' / 'May 30 - Jun 2'."""
    if start == end:
        return _fmt_day(start)
    if (start.year, start.month) == (end.year, end.month):
        return f"{_fmt_day(start)} - {end.day}"          # same month -> 'May 30 - 31'
    return f"{_fmt_day(start)} - {_fmt_day(end)}"          # cross month -> 'May 30 - Jun 2'


def filter_campaigns_by_campaign_date(df: pd.DataFrame, start, end=None) -> pd.DataFrame:
    """Filter to campaigns whose blast date falls within the given period."""
    start_ts, end_ts = _normalize_period(start, end)
    blast = pd.to_datetime(df["blast_date"], errors="coerce").dt.normalize()
    mask = (blast >= start_ts) & (blast <= end_ts)
    return df.loc[mask].copy()


def _channel_label(channel: str) -> str:
    """Display label for a utm_medium channel ('email' -> 'Email', 'sms' -> 'SMS')."""
    return "SMS" if channel.lower() == "sms" else channel.capitalize()


def build_blast_report(
    attentive_orders: pd.DataFrame,
    all_orders: pd.DataFrame,
    start,
    end=None,
    channel: str = "email",
) -> pd.DataFrame:
    """Build the blast-performance pivot for a chosen blast period and channel.

    `channel` selects the attentive utm_medium to report on ('email' or 'sms');
    its display label drives the channel-specific column headers.

    Rows are STYLE (title) x COLOR, driven by the attentive (channel) data.
    Columns, left to right:
        STYLE | COLOR
        All Sales {period}                  -- units from all_orders (every channel), order day in period
        {Channel} sales {b} / Gross Sales {Channel} {b} ($)            -- same-day: blast day == order day
        {Channel} sales {b} (on {o}) / Gross Sales {b} (on {o}) ($) -- carryover: order day after blast day
        {Channel} Grand Total sales {period}    -- total channel units in period
        Grand Total Sales {period} ($)      -- total channel gross_sales in period
    """
    start_ts, end_ts = _normalize_period(start, end)
    period = _fmt_period(start_ts, end_ts)
    label = _channel_label(channel)

    # --- All Sales universe (LEFT side): every product sold in the period ------
    # all_orders drives the report's rows; the channel blast metrics are
    # left-joined onto it, so products with sales but no blast still appear.
    allo = all_orders.assign(_o=pd.to_datetime(all_orders["day"], errors="coerce").dt.normalize())
    allo = allo[(allo["_o"] >= start_ts) & (allo["_o"] <= end_ts)]
    all_units = allo.groupby(["title", "color"], dropna=False).size()
    idx = all_units.index

    if idx.empty:
        return pd.DataFrame(columns=["STYLE", "COLOR", f"All Sales {period}",
                                     f"{label} Grand Total sales {period}",
                                     f"Grand Total Sales {period} ($)"])

    out = pd.DataFrame(index=idx)
    out[f"All Sales {period}"] = all_units.reindex(idx).fillna(0).astype(int)

    # --- Channel side: filter to this utm_medium, blast dates in period --------
    email = attentive_orders[attentive_orders["utm_medium"].str.lower() == channel.lower()]
    email = filter_campaigns_by_campaign_date(email, start_ts, end_ts)
    email = email.assign(
        _b=pd.to_datetime(email["blast_date"], errors="coerce").dt.normalize(),
        _o=pd.to_datetime(email["day"], errors="coerce").dt.normalize(),
    )
    # Keep orders on/after their blast day and within the period end (bounds carryover)
    email = email[(email["_o"] >= email["_b"]) & (email["_o"] <= end_ts)]

    if not email.empty:
        # Per (style, color, blast day, order day): units (line items) and gross $
        grp = email.groupby(["title", "color", "_b", "_o"], dropna=False).agg(
            units=("quantity", "sum"),
            gross=("original_unit_price", "sum"),
        ).reset_index()

        units_p = grp.pivot_table(index=["title", "color"], columns=["_b", "_o"],
                                  values="units", aggfunc="sum", fill_value=0)
        gross_p = grp.pivot_table(index=["title", "color"], columns=["_b", "_o"],
                                  values="gross", aggfunc="sum", fill_value=0)

        totals = email.groupby(["title", "color"], dropna=False).agg(
            units=("quantity", "sum"),
            gross=("original_unit_price", "sum"),
        )

        def col(piv, b_val, o_val):
            """Pull a (blast, order) column from a pivot, aligned to the row index."""
            if (b_val, o_val) in piv.columns:
                return piv[(b_val, o_val)].reindex(idx).fillna(0)
            return pd.Series(0, index=idx)

        # Same-day pairs, one per blast day in the period
        blast_days = sorted(pd.to_datetime(email["_b"].dropna().unique()))
        for bd in blast_days:
            out[f"{label} sales {_fmt_day(bd)}"] = col(units_p, bd, bd).astype(int)
            out[f"Gross Sales {label} {_fmt_day(bd)} ($)"] = col(gross_p, bd, bd).round(2)

        # Carryover pairs: only combos that actually have orders (order day after blast)
        carry = (grp.loc[grp["_o"] > grp["_b"], ["_b", "_o"]]
                    .drop_duplicates().sort_values(["_b", "_o"]))
        for bd, od in carry.itertuples(index=False):
            out[f"{label} sales {_fmt_day(bd)} (on {_fmt_day(od)})"] = col(units_p, bd, od).astype(int)
            out[f"Gross Sales {_fmt_day(bd)} (on {_fmt_day(od)}) ($)"] = col(gross_p, bd, od).round(2)

        # Grand totals (this channel only), left-joined onto the all_orders rows
        out[f"{label} Grand Total sales {period}"] = totals["units"].reindex(idx).fillna(0).astype(int)
        out[f"Grand Total Sales {period} ($)"] = totals["gross"].reindex(idx).fillna(0).round(2)
    else:
        # No blasts in this channel/period: every product still shows, blast = 0
        out[f"{label} Grand Total sales {period}"] = 0
        out[f"Grand Total Sales {period} ($)"] = 0.0

    out = out.reset_index().rename(columns={"title": "STYLE", "color": "COLOR"})
    out = out.sort_values(f"{label} Grand Total sales {period}", ascending=False).reset_index(drop=True)
    return out
