"""
connection/attentive_api.py
This module contains functions to interact with the Attentive API, including authentication and data retrieval.

Auth: Bearer token (an API key from a custom app in the Attentive UI).
Base URL: https://api.attentivemobile.com/v1
Verify credentials with verify_auth() -> GET /me.
"""

import logging

import requests

from config.settings import ATTENTIVE_BASE_URL, ATTENTIVE_HEADERS

logger = logging.getLogger(__name__)


def verify_auth() -> dict:
    """Confirm the API key works by calling GET /me. Returns the account info JSON."""
    resp = requests.get(f"{ATTENTIVE_BASE_URL}/me", headers=ATTENTIVE_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get(path: str, params: dict | None = None) -> dict:
    """GET an Attentive REST endpoint. `path` is relative to the base URL (e.g. '/me')."""
    url = f"{ATTENTIVE_BASE_URL}/{path.lstrip('/')}"
    resp = requests.get(url, headers=ATTENTIVE_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def post(path: str, payload: dict) -> dict:
    """POST a JSON body to an Attentive REST endpoint."""
    url = f"{ATTENTIVE_BASE_URL}/{path.lstrip('/')}"
    resp = requests.post(url, headers=ATTENTIVE_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def graphql(query: str, variables: dict | None = None) -> dict:
    """Run an Attentive GraphQL query/mutation against /graphql. Returns the `data` payload."""
    resp = requests.post(
        f"{ATTENTIVE_BASE_URL}/graphql",
        headers=ATTENTIVE_HEADERS,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise ValueError(f"Attentive GraphQL error: {body['errors']}")
    return body["data"]


if __name__ == "__main__":
    # Quick smoke test: python -m connection.attentive_api
    from config import settings
    settings.reload()  # pick up ATTENTIVE_API_KEY from .env
    print("Verifying Attentive credentials via /me ...")
    print(verify_auth())
