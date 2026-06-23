"""
connection/attentive_api.py
This module contains functions to interact with the Attentive API, including authentication and data retrieval.

Auth: Bearer token (an API key from a custom app in the Attentive UI).
Base URL: https://api.attentivemobile.com/v1
Verify credentials with verify_auth() -> GET /me.
"""

import logging
import time

import pandas as pd
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


# ─── Recipient / subscriber data ────────────────────────────────────────────
# Subscribers ("recipients") are read via Company.usersExperimental, a paginated
# connection reached through viewer → installedApplication → installerCompany.
# Filter by segment, opt-in date, click/purchase events, status, or location.
#
# ⚠️ REQUIRES USER-READ PERMISSION on the Attentive app. A write-only key (the
# default public scopes are all `*:write`) gets `PERMISSION_DENIED`. Enable the
# read permission for the custom app in the Attentive UI (may need Attentive's
# help) before this returns data.
_LIST_USERS_QUERY = """
query ListUsers($first: Int, $after: String, $filter: ListUsersFilter) {
  viewer {
    installedApplication {
      installerCompany {
        usersExperimental(first: $first, after: $after, filter: $filter) {
          edges {
            cursor
            node { id email subscribedPhone firstName lastName }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
  }
}
""".strip()


def opt_in_completed_filter(start, end, has: bool = True) -> dict:
    """Build a ListUsersFilter selecting users whose subscription opt-in completed in [start, end].

    `start`/`end` may be date strings or datetimes. Use this to count recipients
    that subscribed within a blast period.
    """
    return {
        "subscriptionOptInCompletedFilter": {
            "hasVerb": "HAS_VERB_HAS" if has else "HAS_VERB_HAS_NOT",
            "timeCondition": {
                "comparator": "TIME_COMPARATOR_BETWEEN",
                "time": pd.Timestamp(start).isoformat(),
                "endTime": pd.Timestamp(end).isoformat(),
            },
        }
    }


def fetch_recipients(user_filter: dict | None = None, page_size: int = 100,
                     max_pages: int | None = None) -> pd.DataFrame:
    """Fetch subscriber ("recipient") records via Company.usersExperimental, paginated.

    Args:
        user_filter: a ListUsersFilter dict, e.g. {"segmentId": "<id>"} or the
            output of opt_in_completed_filter(...). None returns the full base.
        page_size: users per page (GraphQL `first`).
        max_pages: stop after this many pages (None = fetch all).

    Returns:
        DataFrame with columns: id, email, subscribed_phone, first_name, last_name.

    Raises:
        ValueError('Attentive GraphQL error: ... PERMISSION_DENIED ...') if the
        key lacks user-read permission (see note above).
    """
    rows = []
    cursor = None
    pages = 0
    while True:
        data = graphql(_LIST_USERS_QUERY,
                       {"first": page_size, "after": cursor, "filter": user_filter})
        conn = (data["viewer"]["installedApplication"]["installerCompany"]
                ["usersExperimental"])
        for edge in conn["edges"]:
            n = edge["node"]
            rows.append({
                "id": n.get("id"),
                "email": n.get("email"),
                "subscribed_phone": n.get("subscribedPhone"),
                "first_name": n.get("firstName"),
                "last_name": n.get("lastName"),
            })
        pages += 1
        info = conn["pageInfo"]
        if not info["hasNextPage"] or (max_pages is not None and pages >= max_pages):
            break
        cursor = info["endCursor"]
        time.sleep(0.25)

    return pd.DataFrame(rows, columns=["id", "email", "subscribed_phone",
                                       "first_name", "last_name"])


if __name__ == "__main__":
    # Quick smoke test: python -m connection.attentive_api
    from config import settings
    settings.reload()  # pick up ATTENTIVE_API_KEY from .env
    print("Verifying Attentive credentials via /me ...")
    print(verify_auth())
    print("\nFetching first page of recipients ...")
    try:
        df = fetch_recipients(page_size=5, max_pages=1)
        print(f"Got {len(df)} recipient row(s). Columns: {list(df.columns)}")
    except ValueError as e:
        print(f"Recipient fetch unavailable: {e}")
