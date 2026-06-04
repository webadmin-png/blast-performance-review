# ===================================================================
# auth/token_manager.py
# -------------------------------------------------------------------
# Manages Shopify authentication tokens.
# Shopify uses permanent (non-expiring) access tokens for private/custom apps.
# This module validates the current token and reloads it from .env if needed.
# ===================================================================

import os
import requests
from dotenv import load_dotenv, set_key
from datetime import datetime

import os
import time
import requests
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv, set_key
 
# ------------------------------------------------------------------
# ENV + CONFIG
# ------------------------------------------------------------------
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(ENV_PATH)
 
SHOPIFY_STORE        = os.getenv("SHOPIFY_STORE", "")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_CLIENT_ID    = os.getenv("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET= os.getenv("SHOPIFY_CLIENT_SECRET", "")
 
URL = f"https://{SHOPIFY_STORE}/admin/api/2025-01/graphql.json"
TOKEN_URL = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
}
 
 
# ===================================================================
# TOKEN MANAGEMENT
# ===================================================================
 
def get_token():
    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": SHOPIFY_CLIENT_ID,
                "client_secret": SHOPIFY_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        r.raise_for_status()
        token_data = r.json()

        # Save token to credentials file as JSON for later use
        set_key(ENV_PATH, "SHOPIFY_ACCESS_TOKEN", token_data["access_token"])
        return token_data["access_token"]
    except Exception as e:
        raise RuntimeError(f"Failed to obtain access token: {e}")