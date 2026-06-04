# 📊 Blast Performance Report — Project Summary

🏬 **Store:** Wooden Ships (`wooden-ships.myshopify.com`)
🚦 **Status:** Core report implemented (Shopify side) — Attentive recipients & orchestration still in progress
👤 **Owner / stakeholder:** Paola — has directed that this reporting task be automated by the AI team starting **June 2026**.

---

## 🎯 1. Purpose

Automate the monthly **Email & SMS Blast Performance** report, currently maintained by hand in the
Google Sheet *"Email & SMS Blast Performance - 2026"*. The deliverable is a per-campaign **Revenue
Summary Grid** (one row per email/SMS blast), produced monthly. 📅

This repo replaces the manual spreadsheet step with a script that pulls the numbers automatically and
writes the summary grid. 🤖

---

## 🔌 2. Data Sources (confirmed)

| Metric | Source | Notes |
|---|---|---|
| 💰 **$ Revenue** | **Shopify** | Attributed to each campaign via **UTM parameters** on the campaign links (not from Attentive). |
| 👥 **# Recipients** | **Attentive** | Number of recipients the blast was sent to. |
| 🏷️ Campaign metadata (name, description, send time, AI flags, A/B) | Attentive / campaign log | Name, products featured, send time, AI Time / AI Audience / A/B test flags. |

> ⚠️ Key clarification: **Revenue comes from Shopify (UTM-attributed), recipients come from Attentive.**
> Only revenue is sourced from Shopify.

---

## 📋 3. Output — Summary Grid Columns

| Column | Source / Formula |
|---|---|
| 📆 Date | Campaign send date |
| 🗓️ DOW | Day of week |
| ✉️ Email Campaign Name | From campaign (e.g. "Beach + Lake (RELEASE)") |
| 📝 Email Campaign Description | Products featured in the blast |
| ⏰ Send Time (ET) | Send time / "AI Time" |
| 🧠 AI Time (Y/N) | Was send time AI-optimized |
| 🎯 AI Audience (Y/N) | Was audience AI-optimized |
| 🔀 A/B Test? (Y/N) | Was an A/B test run |
| 💰 **$ Revenue** | Shopify, UTM-attributed |
| 💸 **$ Spend** | Per-campaign cost (≈ $139 each in May — *confirm what this represents*) |
| 👥 **# Recipients** | Attentive |
| 📈 **% ROI** | `(Revenue − Spend) / Spend × 100` |
| 🔁 **x ROAS** | `Revenue / Spend` |
| 🧮 **$ RPR** | `Revenue / Recipients` (Revenue Per Recipient) |

✅ Formulas verified against May 2026 data (May 02: Rev $2,479, Spend $139, Recipients 67,682 →
ROAS 17.8x, ROI 1684.9%, RPR $0.037).

---

## 🧱 3b. Implemented So Far — Blast-Performance Pivot

The Shopify side is built end-to-end in code. `main.py` pulls UTM-tagged orders, transforms them, and
writes a **STYLE × COLOR blast-performance pivot** per channel for a chosen blast period.

**One report per channel.** Attentive blasts carry `utm_medium` of either `email` or `sms`, so the
script emits **two separate files** — e.g. `reports/blast_report_email_<period>.csv` and
`reports/blast_report_sms_<period>.csv` — via `build_blast_report(..., channel="email"|"sms")`.

**Row universe = `all_orders` (left side).** Rows are every `(STYLE, COLOR)` sold in the period across
**all** channels; the channel's blast metrics are left-joined on, so products with sales but no blast
still appear (blast columns = 0). Columns, left to right:

| Column | Meaning |
|---|---|
| `STYLE` / `COLOR` | Product title + color (color parsed from SKU) |
| `All Sales {period}` | Units sold every channel, order day in period |
| `{Channel} sales {b}` / `Gross Sales {Channel} {b} ($)` | Same-day: order day == blast day |
| `{Channel} sales {b} (on {o})` / `Gross Sales {b} (on {o}) ($)` | Carryover: order day after blast day |
| `{Channel} Grand Total sales {period}` | Total channel units in period |
| `Grand Total Sales {period} ($)` | Total channel gross sales in period |

**Key transforms** (`utils/transform.py`): filter attentive blast campaigns by `utm_campaign` naming
convention (email `m/d/yyyy …`, sms `Month-D-yyyy-…`), extract blast date + description, collapse
audience-variant suffixes (`_base`, `_audiences_ai`), and parse color from the variant SKU.

> 🔜 Not yet wired in: Attentive recipients/metadata and the ROI/ROAS/RPR Summary Grid above — the
> implemented pivot is units & gross revenue from Shopify only.

---

## 🗂️ 4. Repo Layout

```
blast-performance-report/
├── main.py                       # entry point: fetch → transform → build per-channel reports
├── auth/
│   └── token_manager.py          # token refresh (get_token) before settings.reload()
├── config/
│   └── settings.py               # paths (DATA_DIR, RAW/PROCESSED_DATA_DIR, REPORT_DIR) + creds
├── connection/
│   ├── shopify_api.py            # Shopify Admin API — fetch_orders_utm (revenue by UTM)
│   ├── attentive_api.py          # Attentive API — recipients & campaign metadata (not yet wired)
│   └── google_sheet.py           # Google Sheets I/O
├── utils/
│   ├── transform.py              # transform_campaign_data → (attentive_orders, all_orders)
│   └── report_generator.py       # build_blast_report — STYLE×COLOR pivot per channel
├── data/
│   ├── raw/                      # raw Shopify UTM pulls
│   └── processed/                # campaign_data.csv, all_orders_data.csv
├── reports/                      # generated per-channel pivots (blast_report_{channel}_{period}.csv)
├── requirements.txt
└── .env                          # credentials (see below)
```

### 🔑 Credentials (in `.env`)
- 📲 `ATTENTIVE_TOKEN`, `BAREER_TOKEN`, `STORE_ID` — Attentive
- 🛒 `SHOPIFY_STORE`, `SHOPIFY_API_VERSION` (2026-01), `SHOPIFY_ADMIN_TOKEN` / `SHOPIFY_ACCESS_TOKEN`
- 📄 Google Sheets: `*_SHEET_ID` / `*_SHEET_NAME` (ORDER, RETURN, SUMMARY, MASTER_DATA, STOCK_BALI), `CREDS_PATH`
- ☁️ Salesforce + 🤗 Hugging Face tokens (present, not yet known to be used by this report)

---

## 🔄 5. Data Flow (target automation)

```
Shopify API ──► fetch_orders_utm(start, end)  ──► data/raw/*.csv
                       │
                       ▼
        transform_campaign_data()  ──► attentive_orders (blast campaigns)
                       │                  all_orders (every channel)
                       ▼
        build_blast_report(channel="email")  ──► reports/blast_report_email_*.csv   ✅ built
        build_blast_report(channel="sms")    ──► reports/blast_report_sms_*.csv      ✅ built
                       │
                       ▼  (target — not yet wired)
Attentive API ──► recipients + metadata ──► join → compute ROI / ROAS / RPR
                       │
                       ▼
                 write Summary Grid → Google Sheet
```

---

## ❓ 6. Open Questions (for the AI team)

1. 💸 **$ Spend** — is it a fixed per-campaign cost (~$139), the AI tool cost, or platform send cost? Confirm source.
2. 🪟 **UTM attribution window** — over what period are Shopify orders credited to a campaign (e.g. 1-day / 7-day click)?
3. 🔗 **Campaign ⇄ UTM mapping** — how is each Attentive campaign matched to its Shopify UTM (utm_campaign value, naming convention)?
4. ⏱️ **Run cadence & trigger** — monthly run; manual, scheduled, or n8n?
5. 🧾 **Totals row** — the May grid's total revenue ($15,492) does not equal the sum of the campaign rows
   (≈ $41,871), and total ROI shows −99.5%. Automation should compute totals correctly.
6. ✅ **SMS vs Email** — *resolved.* Email and SMS are split by `utm_medium` into two separate reports
   (`build_blast_report(channel=…)`).
