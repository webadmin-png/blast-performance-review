# ===================================================================
# config/settings.py
# -------------------------------------------------------------------
# This module contains configuration settings for the application, including
# API credentials, file paths, and other constants. It centralizes the configuration to make it easier to manage and update as needed.
# ===================================================================

import os
from charset_normalizer import VERSION
from dotenv import load_dotenv
from pathlib import Path


# ------------------------------------------------------------------
# Load environment variables from .env file
# ------------------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------------------------
# PROJECT PATHS
# Central path definitions — use these instead of hardcoding paths elsewhere.
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
CONFIG_DIR = BASE_DIR / 'config'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'
RAW_DATA_DIR = DATA_DIR / 'raw'
REPORT_DIR = BASE_DIR / 'reports'


# ------------------------------------------------------------------
# GOOGLE SHEETS CONFIGURATION
# ------------------------------------------------------------------
# Path to the Google service-account JSON. Override via .env (CREDS_PATH) so the
# location is portable across host and container.
CREDS_PATH = os.getenv("CREDS_PATH", str(BASE_DIR / "credentials" / "service_account.json"))



# ------------------------------------------------------------------
# GOOGLE SHEETS CONFIGURATION
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# GOOGLE SHEETS CONFIGURATION
# ------------------------------------------------------------------
ORDER_SHEET_ID = os.getenv("ORDER_SHEET_ID", "")
ORDER_SHEET_NAME = os.getenv("ORDER_SHEET_NAME", "Sheet1")
RETURN_SHEET_ID = os.getenv("RETURN_SHEET_ID", "")
RETURN_SHEET_NAME = os.getenv("RETURN_SHEET_NAME", "Sheet1")
SUMMARY_SHEET_ID = os.getenv("SUMMARY_SHEET_ID", "")
MASTER_DATA_SHEET_NAME = os.getenv("MASTER_DATA_SHEET_NAME", "Sheet1")
SUMMARY_SHEET_NAME = os.getenv("SUMMARY_SHEET_NAME", "SUMMARY")

STOCK_BALI_SHEET_ID = os.getenv("STOCK_BALI_SHEET_ID", "")
STOCK_BALI_SHEET_NAME = os.getenv("STOCK_BALI_SHEET_NAME", "Master Sheets")

# -----------------------------------------------------------------------------
# SHOPIFY API CONFIGURATION
# -----------------------------------------------------------------------------
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE', "wooden-ships.myshopify.com")
SHOPIFY_CLIENT_ID = os.getenv('SHOPIFY_CLIENT_ID')
SHOPIFY_CLIENT_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
SHOPIFY_API_VERSION = os.getenv('SHOPIFY_API_VERSION', '2026-01')  # Default to latest stable version
SHOPIFY_ADMIN_TOKEN = os.getenv('SHOPIFY_ADMIN_TOKEN')  # Optional: separate token for admin API if needed
URL = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
HEADERS = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"}
REDO_BAREER_TOKEN = os.getenv('BAREER_TOKEN')
REDO_STORE_ID = os.getenv('STORE_ID')
REDO_URL = f"https://api.getredo.com/v2.2/stores/{REDO_STORE_ID}/returns"

# -----------------------------------------------------------------------------
# ATTENTIVE API CONFIGURATION
# Bearer auth with an API key from a custom app:
#   https://ui.attentivemobile.com/integrations/custom-app/management
# -----------------------------------------------------------------------------
ATTENTIVE_API_KEY = os.getenv('ATTENTIVE_API_KEY')
ATTENTIVE_BASE_URL = os.getenv('ATTENTIVE_BASE_URL', 'https://api.attentivemobile.com/v1')
ATTENTIVE_HEADERS = {
    "Authorization": f"Bearer {ATTENTIVE_API_KEY}",
    "Content-Type": "application/json",
}


def reload():
    # Re-read .env and refresh the Shopify token without restarting the kernel.
    # HEADERS is mutated in place so modules that did `from config.settings import HEADERS`
    # keep seeing the same dict object with the updated token.
    global SHOPIFY_ACCESS_TOKEN, SHOPIFY_ADMIN_TOKEN, REDO_BAREER_TOKEN, ATTENTIVE_API_KEY
    load_dotenv(override=True)
    SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
    SHOPIFY_ADMIN_TOKEN = os.getenv('SHOPIFY_ADMIN_TOKEN')
    REDO_BAREER_TOKEN = os.getenv('BAREER_TOKEN')
    ATTENTIVE_API_KEY = os.getenv('ATTENTIVE_API_KEY')
    HEADERS["X-Shopify-Access-Token"] = SHOPIFY_ACCESS_TOKEN
    ATTENTIVE_HEADERS["Authorization"] = f"Bearer {ATTENTIVE_API_KEY}"