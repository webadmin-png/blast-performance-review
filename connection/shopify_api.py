# ─── Order-level UTM via Admin GraphQL ──────────────────────────────
# subtotal_price is ORDER-LEVEL = subtotalPriceSet — the total the customer paid, excluding shipping & tax.
# Line items are capped at 250 per order (no nested pagination); a warning is printed if any order hits the cap.
# fetch_orders_utm returns ONE ROW PER LINE ITEM (for title/sku/quantity detail). Order-level
# context (id, name, dates, status, UTM) repeats on each row, while subtotal_price is recorded only
# on the FIRST line-item row of each order (0.0 elsewhere) so per-column sums equal true order
# totals and never double-count.
# `customerJourneySummary.lastVisit.utmParameters` is the last-click UTM attribution Shopify
# records on each order at checkout.

import requests
import pandas as pd
import time

from config.settings import URL, HEADERS

ORDERS_UTM_QUERY = """
query OrdersWithUTM($cursor: String, $query: String!) {
  orders(first: 250, after: $cursor, query: $query, sortKey: CREATED_AT) {
    edges {
      cursor
      node {
        id
        name
        createdAt
        displayFinancialStatus
        displayFulfillmentStatus
        subtotalPriceSet { shopMoney { amount } }
        lineItems(first: 250) {
          edges {
            node {
              title
              sku
              quantity
              originalUnitPriceSet { shopMoney { amount } }
            }
          }
          pageInfo { hasNextPage }
        }
        customerJourneySummary {
          lastVisit { utmParameters { source medium campaign content term } }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
""".strip()


def fetch_orders_utm(start_date: str, end_date: str) -> pd.DataFrame:
    """Paginate Admin GraphQL orders in the date range; return one row per order with UTM + gross sales."""
    rows = []
    cursor = None
    truncated_orders = []
    search = f"created_at:>={start_date} created_at:<={end_date}"
    while True:
        resp = requests.post(
            URL,
            json={"query": ORDERS_UTM_QUERY, "variables": {"cursor": cursor, "query": search}},
            headers=HEADERS,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            raise ValueError(f"GraphQL error: {body['errors']}")

        data = body["data"]["orders"]
        for edge in data["edges"]:
            n = edge["node"]
            last_visit = (n.get("customerJourneySummary") or {}).get("lastVisit") or {}
            params = last_visit.get("utmParameters") or {}
            line_items = (n.get("lineItems") or {}).get("edges") or []
            if (n.get("lineItems") or {}).get("pageInfo", {}).get("hasNextPage"):
                truncated_orders.append(n["name"])

            # Order-level context shared by every line-item row of this order.
            order_ctx = {
                "order_id": n["id"],
                "order_name": n["name"],
                "created_at": n["createdAt"],
                "display_financial_status": n.get("displayFinancialStatus") or "",
                "display_fulfillment_status": n.get("displayFulfillmentStatus") or "",
                "utm_source": params.get("source") or "",
                "utm_medium": params.get("medium") or "",
                "utm_campaign": params.get("campaign") or "",
                "utm_content": params.get("content") or "",
                "utm_term": params.get("term") or "",
            }

            # Emit one row per line item for title/sku/quantity detail. The money fields are
            # ORDER-LEVEL (gross_sales = subtotalPriceSet incl. shipping & tax) and are recorded only
            # on the FIRST line-item row of each order (0.0 elsewhere) so per-column sums equal true order totals and never double-count.
            order_gross = float(n["subtotalPriceSet"]["shopMoney"]["amount"])      # total paid incl. shipping & tax
            order_money = {
                "gross_sales": order_gross,
            }
            zero_money = {k: 0.0 for k in order_money}

            if not line_items:
                rows.append({**order_ctx, "title": "", "sku": "", "quantity": 0, **order_money})
                continue
            for i, li in enumerate(line_items):
                node = li["node"]
                rows.append({
                    **order_ctx,
                    "title": node["title"],
                    "sku": node["sku"],
                    "quantity": node["quantity"],
                    "original_unit_price": float(node["originalUnitPriceSet"]["shopMoney"]["amount"]),
                    **(order_money if i == 0 else zero_money),
                })
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
        time.sleep(0.25)

    if truncated_orders:
        print(f"WARNING: {len(truncated_orders)} order(s) had >250 line items; gross_sales is undercounted for: {truncated_orders[:5]}{'...' if len(truncated_orders) > 5 else ''}")

    df = pd.DataFrame(rows)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True) - pd.Timedelta(hours=5)
        df["day"] = df["created_at"].dt.tz_convert(None).dt.normalize()
    return df