"""
utils/recipients.py
Load per-campaign recipient counts from an Attentive UI campaign-report export
(CSV/XLSX) and normalize them into a join key that matches the blast report.

The Attentive campaign name is the same string used in Shopify's utm_campaign,
so we reuse transform.py's extractors to derive (blast_date, campaign_description)
exactly the way the report groups campaigns.
"""

import pandas as pd

from utils.transform import _extract_campaign_date, _extract_campaign_description

# Candidate header substrings for auto-detection (matched case-insensitively).
_NAME_HINTS = ("campaign name", "message name", "campaign", "message", "name")
_RECIPIENTS_HINTS = ("recipients", "messages sent", "total sent", "sent", "sends",
                     "delivered", "audience")
_CHANNEL_HINTS = ("channel", "message type", "type")
_DATE_HINTS = ("send date", "sent date", "send time", "date")


def _detect(columns, hints, label):
    """Return the first column whose lowercased name contains any hint, else None."""
    lowered = {c: str(c).strip().lower() for c in columns}
    for hint in hints:                       # hints ordered most- to least-specific
        for col, low in lowered.items():
            if hint in low:
                return col
    return None


def load_campaign_recipients(
    path,
    *,
    name_col=None,
    recipients_col=None,
    channel_col=None,
    date_col=None,
    verbose=True,
) -> pd.DataFrame:
    """Load an Attentive campaign-report export into a normalized recipients table.

    Pass explicit *_col names to override auto-detection (recommended once the
    export format is known).

    Returns a DataFrame with columns:
        campaign_name | blast_date | campaign_description | channel | recipients
    keyed so it can be joined to the blast report on (blast_date, campaign_description).
    """
    path = str(path)
    df = pd.read_excel(path) if path.lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)

    name_col = name_col or _detect(df.columns, _NAME_HINTS, "name")
    recipients_col = recipients_col or _detect(df.columns, _RECIPIENTS_HINTS, "recipients")
    channel_col = channel_col or _detect(df.columns, _CHANNEL_HINTS, "channel")
    date_col = date_col or _detect(df.columns, _DATE_HINTS, "date")

    if verbose:
        print("Detected columns ->",
              f"name={name_col!r}, recipients={recipients_col!r}, "
              f"channel={channel_col!r}, date={date_col!r}")

    if name_col is None or recipients_col is None:
        raise ValueError(
            "Could not auto-detect the campaign-name and/or recipients columns. "
            f"Available columns: {list(df.columns)}. "
            "Pass name_col=... and recipients_col=... explicitly."
        )

    names = df[name_col].astype(str)
    out = pd.DataFrame({
        "campaign_name": names,
        # Same extraction the report uses, so the keys line up with utm_campaign.
        "blast_date": _extract_campaign_date(names),
        "campaign_description": _extract_campaign_description(names),
        "recipients": pd.to_numeric(
            df[recipients_col].astype(str).str.replace(r"[,\s]", "", regex=True),
            errors="coerce",
        ).astype("Int64"),
    })

    if channel_col is not None:
        # Normalize to 'email' / 'sms' to match utm_medium.
        ch = df[channel_col].astype(str).str.strip().str.lower()
        out["channel"] = ch.where(ch.isin(["email", "sms"]), ch)
    else:
        out["channel"] = pd.NA

    # Prefer a real date column when present and the name didn't yield a date.
    if date_col is not None:
        from_date = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
        out["blast_date"] = out["blast_date"].fillna(from_date)

    unmatched = out["blast_date"].isna().sum()
    if verbose and unmatched:
        print(f"WARNING: {unmatched} row(s) have no parseable blast_date "
              "(campaign name not in the expected date format).")

    return out


def recipients_for_campaign(table: pd.DataFrame, query=None, *, blast_date=None,
                            channel=None) -> pd.DataFrame:
    """Look up recipient counts for the campaign(s) you want.

    Args:
        table: output of load_campaign_recipients().
        query: case-insensitive substring matched against campaign_name /
            campaign_description (e.g. "MDW", "Beach Drop").
        blast_date: optional exact blast date (string or datetime) to filter on.
        channel: optional 'email' or 'sms'.

    Returns the matching rows (campaign_name, blast_date, channel, recipients).
    """
    mask = pd.Series(True, index=table.index)
    if query:
        q = str(query).lower()
        mask &= (table["campaign_name"].str.lower().str.contains(q, na=False) |
                 table["campaign_description"].str.lower().str.contains(q, na=False))
    if blast_date is not None:
        mask &= table["blast_date"].eq(pd.to_datetime(blast_date).normalize())
    if channel is not None:
        mask &= table["channel"].eq(channel.lower())
    return table.loc[mask, ["campaign_name", "blast_date", "channel", "recipients"]]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m utils.recipients <path-to-attentive-export.csv>")
        raise SystemExit(1)
    result = load_campaign_recipients(sys.argv[1])
    print(f"\nLoaded {len(result)} campaign row(s):")
    print(result.head(15).to_string(index=False))
