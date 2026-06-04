"""
utils/transform.py
This module contains functions for transforming and processing data, including cleaning, formatting, and preparing data for
analysis or reporting. It serves as a utility for data manipulation tasks across the application.
"""


import re

import pandas as pd

CAMPAIGN_FORMAT_RE = r"^(?:\d{1,2}/\d{1,2}/\d{4}|[A-Za-z]+-\d{1,2}-\d{4})"


def _filter_blast_campaigns(df: pd.DataFrame, pattern: str = CAMPAIGN_FORMAT_RE) -> pd.DataFrame:
    """Keep rows whose utm_campaign starts with the email (d/m/yyyy) or sms (Mon-D-yyyy) format."""
    return df[df["utm_campaign"].str.match(pattern, na=False)].reset_index(drop=True)


def _extract_campaign_date(series: pd.Series) -> pd.Series:
    """Extract the blast date embedded in utm_campaign.

    Email format: 'm/d/yyyy ...'      e.g. '5/11/2026 - MDW CUT OFF_base'  -> 2026-05-11
    SMS format:   'Month-D-yyyy-...'  e.g. 'May-11-2026-MDW-Cut Off_base'  -> 2026-05-11
    Returns NaT for anything that doesn't match.
    """
    # Email m/d/yyyy
    email_str = series.str.extract(r"^(\d{1,2}/\d{1,2}/\d{4})", expand=False)
    email_dt = pd.to_datetime(email_str, format="%m/%d/%Y", errors="coerce")

    # SMS Month-D-yyyy (try full month name first, then abbreviated)
    sms_str = series.str.extract(r"^([A-Za-z]+-\d{1,2}-\d{4})", expand=False)
    sms_normalized = sms_str.str.replace("-", " ", regex=False)
    sms_dt = pd.to_datetime(sms_normalized, format="%B %d %Y", errors="coerce")
    sms_dt = sms_dt.fillna(pd.to_datetime(sms_normalized, format="%b %d %Y", errors="coerce"))

    return email_dt.fillna(sms_dt)

def _strip_campaign_variant_suffix(series: pd.Series) -> pd.Series:
    """Strip trailing audience-variant suffixes so variants of the same campaign group together.

    'Rewards_audiences_ai' -> 'Rewards'
    'Rewards_base'         -> 'Rewards'
    Anything else is returned unchanged.
    """
    return series.str.replace(r"(?:_audiences_ai|_base)$", "", regex=True).str.strip()       

# Audience-variant suffixes that should collapse for grouping
# (e.g. 'Rewards_base' and 'Rewards_audiences_ai' both become 'Rewards')
CAMPAIGN_VARIANT_SUFFIXES = ("_audiences_ai", "_base")


def _extract_campaign_description(series: pd.Series) -> pd.Series:
    """Extract the description text following the blast date in utm_campaign.

    Email format: 'm/d/yyyy ...'      e.g. '5/11/2026 - MDW CUT OFF_base'  -> 'MDW CUT OFF'
    SMS format:   'Month-D-yyyy-...'  e.g. 'May-11-2026-MDW-Cut Off_base'  -> 'MDW-Cut Off'
    Trailing audience-variant suffixes ('_base', '_audiences_ai') are stripped so variants of
    the same campaign group together. Internal hyphens are preserved.
    Returns NaN for anything that doesn't start with a recognized date prefix.
    """
    # Email: strip 'm/d/yyyy' then optional ' - ' separator
    email_desc = series.str.extract(r"^\d{1,2}/\d{1,2}/\d{4}\s*-?\s*(.*)$", expand=False)
    email_has_date = series.str.match(r"^\d{1,2}/\d{1,2}/\d{4}", na=False)
    email_desc = email_desc.where(email_has_date)

    # SMS: strip 'Month-D-yyyy' then exactly one '-' separator
    sms_desc = series.str.extract(r"^[A-Za-z]+-\d{1,2}-\d{4}-?(.*)$", expand=False)
    sms_has_date = series.str.match(r"^[A-Za-z]+-\d{1,2}-\d{4}", na=False)
    sms_desc = sms_desc.where(sms_has_date)

    desc = email_desc.fillna(sms_desc).str.strip()
    suffix_pattern = "|".join(re.escape(s) for s in CAMPAIGN_VARIANT_SUFFIXES)
    return desc.str.replace(rf"(?:{suffix_pattern})$", "", regex=True).str.strip()

def _extract_color(sku: str) -> str:
    """
    Extract color from SKU based on its structure.

    SKU formats:
        4 parts, ends with 'S'  → STYLE-COLOR-SIZE-S  → return COLOR (index 1)
        4 parts, no 'S' suffix  → STYLE-COLOR-SIZE-?  → return SIZE  (index 2)
        3 parts                 → STYLE-COLOR-SIZE    → return COLOR (index 1)

    Args:
        sku: Variant SKU string e.g. 'K56C3W338-PRETTY PINK-S/M-S'.

    Returns:
        Extracted color string, or '' if null/unrecognised format.
    """
    if not isinstance(sku, str) or not sku:
        return ""

    parts = sku.split("-")
    n     = len(parts)

    if n == 4 and parts[-1] == "S":
        return parts[1]   # STYLE-COLOR-SIZE-S
    if n == 4:
        return parts[2]   # STYLE-COLOR-SIZE-? (review if correct)
    if n == 3:
        return parts[1]   # STYLE-COLOR-SIZE

    return ""

def _apply_transforms(df: pd.DataFrame, filter_blasts: bool = True) -> pd.DataFrame:
    """Clean and extract structured info from utm_campaign for a single DataFrame."""
    # Keep only blast campaigns when requested (attentive only)
    if filter_blasts:
        df = _filter_blast_campaigns(df)
    # Strip audience-variant suffixes from utm_campaign for grouping
    df["utm_campaign"] = _strip_campaign_variant_suffix(df["utm_campaign"])
    # Extract blast date and campaign description from utm_campaign
    df["blast_date"] = _extract_campaign_date(df["utm_campaign"])
    df["campaign_description"] = _extract_campaign_description(df["utm_campaign"])
    # Extract color from SKU
    df["color"] = df["sku"].apply(_extract_color)
    return df

def transform_campaign_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply transforms to attentive-only and all orders, returning both."""
    attentive_orders = df[df['utm_source'] == 'attentive'].copy()
    all_orders = df.copy()

    # (DataFrame, filter_blasts) pairs — same transform chain, blast filter only for attentive
    subsets = [(attentive_orders, True), (all_orders, False)]
    attentive_orders, all_orders = [
        _apply_transforms(subset, filter_blasts=flt) for subset, flt in subsets
    ]
    return attentive_orders, all_orders