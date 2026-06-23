from connection.shopify_api import fetch_orders_utm
from config.settings import DATA_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, REPORT_DIR
from utils.transform import transform_campaign_data
from utils.report_generator import build_blast_report
import argparse
import os
import pandas as pd
from auth.token_manager import get_token
from config import settings
get_token()
settings.reload()


def get_campaign_data(sample: bool = False, start_date: str = None, end_date: str = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch orders with UTM data from Shopify, transform it, and return (attentive_orders, all_orders).

    If sample=True, returns a small sample of the data for testing purposes.
    """
    if sample:
        # For development/testing, load a sample CSV instead of hitting the Shopify API.
        sample_path = RAW_DATA_DIR / "shopify_orders_utm_2026-01-01_to_2026-06-01.csv"
        print(f"Loading sample data from {sample_path}")
        df = pd.read_csv(sample_path)
        # Transform the sample data to match the structure of the real API response.
        attentive_orders, all_orders = transform_campaign_data(df)

        return attentive_orders, all_orders
    else:
        print(f"Fetching orders with UTM data from Shopify for {start_date} to {end_date}...")
        df = fetch_orders_utm(start_date, end_date)
        # Transform the fetched data to match the structure of the real API response.
        attentive_orders, all_orders = transform_campaign_data(df)

        # Save the raw fetched data for reference
        os.makedirs(RAW_DATA_DIR, exist_ok=True)
        raw_path = RAW_DATA_DIR / f"shopify_orders_utm_{start_date}_to_{end_date}.csv"
        df.to_csv(raw_path, index=False)
        print(f"Fetched {df.shape[0]} rows of raw data saved to {raw_path}")

        return attentive_orders, all_orders
    
if __name__ == "__main__":
    start = "2026-01-01"
    end = "2026-06-30"

    attentive_orders, all_orders = get_campaign_data(sample=False, start_date=start, end_date=end)

    # Persist the transformed source data
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    for filename, frame in {
        "campaign_data.csv": attentive_orders,
        "all_orders_data.csv": all_orders,
    }.items():
        frame.to_csv(PROCESSED_DATA_DIR / filename, index=False)
        print(f"Saved {filename} to {PROCESSED_DATA_DIR / filename}")

    # Build and export one blast-performance report per channel (email + sms)
    os.makedirs(REPORT_DIR, exist_ok=True)
    period_tag = "2026-06-22_to_2026-06-22"
    for channel in ("email", "sms"):
        report = build_blast_report(
            attentive_orders, all_orders, "2026-06-22", "2026-06-22", channel=channel
        )
        report_path = REPORT_DIR / f"blast_report_{channel}_{period_tag}.csv"
        report.to_csv(report_path, index=False)
        print(f"\n{channel.upper()} blast report ({report.shape[0]} rows x {report.shape[1]} cols) saved to {report_path}")
        print(report.head())
