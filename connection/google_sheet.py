# ===================================================================
# Google Sheets Connector
# ------------------------------------------------------------------
# This module provides functions to connect to Google Sheets, read data, and write data.
# It uses the gspread library to interact with the Google Sheets API and pandas for data manipulation.
# ===================================================================
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os
import requests
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1
import sys
from config.settings import CREDS_PATH


# -------------------------------------------------------------------
# MAIN FUNCTIONS
# -------------------------------------------------------------------
def load_sheet(spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """
    Load data from a Google Sheets worksheet into a pandas DataFrame.
    Handles duplicate or empty column headers gracefully.
    """
    client = gs_client()
    ss = open_spreadsheet(client, spreadsheet_id)
    ws = ss.worksheet(sheet_name)

    data = ws.get_all_values()  # Returns raw list of lists, no header parsing

    if not data:
        print(f"⚠️ Sheet '{sheet_name}' is empty.")
        return pd.DataFrame()

    headers = data[0]
    rows    = data[1:]

    # Deduplicate empty/duplicate headers by appending index
    seen = {}
    clean_headers = []
    for i, h in enumerate(headers):
        h = h.strip() if h.strip() else f"unnamed_{i}"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
        clean_headers.append(h)

    df = pd.DataFrame(rows, columns=clean_headers)

    print(f"✅ Loaded {len(df)} rows from sheet '{sheet_name}' in spreadsheet '{spreadsheet_id}'")
    return df



# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------
# 1) Auth client
def gs_client() -> gspread.Client:
    """
    Create gspread client using service account JSON.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
    return gspread.authorize(creds)

# 2) Open spreadsheet
def open_spreadsheet(client: gspread.Client, spreadsheet_id: str) -> gspread.Spreadsheet:
    """
    Open a Google Spreadsheet by its ID.
    """
    return client.open_by_key(spreadsheet_id)

# 3) Get or create worksheet
def get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet,
    title: str,
    rows: int = 2000,
    cols: int = 30
) -> gspread.Worksheet:
    """
    Get worksheet by title. If not exists, create it.
    """
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

# 4) Write dataframe to worksheet
def write_df_to_worksheet(
    ws,
    df: pd.DataFrame,
    mode: str = "replace",          # "replace" or "append"
    include_header: bool = True,
    start_row: int = 1,
    start_col: int = 1,
    clear_before_replace: bool = True
) -> None:
    """
    Write a DataFrame to a Google Sheets worksheet with options for replacing or appending data.
        - mode: "replace" will overwrite existing data, "append" will add below existing data.
        - include_header: whether to include the DataFrame's column names as the first row.
        - start_row, start_col: where to start writing the data (1-indexed).
        - clear_before_replace: if True, will clear the worksheet before replacing data (only applies when mode="replace").
    """
    if df is None:
        raise ValueError("df is None")
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if mode not in ["replace", "append"]:
        raise ValueError("mode must be 'replace' or 'append'")

    safe_df = df.copy().where(pd.notnull(df), "")  # NaN -> ""

    values = []
    if include_header:
        values.append(list(safe_df.columns))
    values.extend(safe_df.values.tolist())

    if mode == "replace":
        if clear_before_replace:
            ws.clear()

        nrows = len(values)
        ncols = len(values[0]) if nrows else 0
        if nrows == 0 or ncols == 0:
            return

        start_a1 = rowcol_to_a1(start_row, start_col)
        end_a1 = rowcol_to_a1(start_row + nrows - 1, start_col + ncols - 1)
        rng = f"{start_a1}:{end_a1}"

        # keyword args (lebih aman lintas versi gspread)
        ws.update(range_name=rng, values=values)

    else:  # append
        existing = ws.get_all_values()
        next_row = len(existing) + 1

        if len(existing) > 0 and include_header:
            values_to_append = values[1:]  # skip header
        else:
            values_to_append = values

        if len(values_to_append) == 0:
            return

        start_cell = rowcol_to_a1(next_row, start_col)
        ws.update(range_name=start_cell, values=values_to_append)

# 5) Helper: export daily (sheet per date)
def export_daily_report(
    df: pd.DataFrame,
    spreadsheet_id: str,
    sheet_name: str,  # contoh: "2026-01-30"
    service_account_json_path: str,
    mode: str = "replace"
) -> None:
    """
    One-call helper to export df into a date-named worksheet.
    """
    client = gs_client(service_account_json_path)
    ss = open_spreadsheet(client, spreadsheet_id)
    ws = get_or_create_worksheet(ss, sheet_name)
    write_df_to_worksheet(ws, df, mode=mode, include_header=True)

def read_worksheet_to_df(
    spreadsheet_id: str,
    sheet_name: str,
    header_row: int = 1,
    start_row: int = None,
    end_row: int = None,
    start_col: int = None,
    end_col: int = None,
) -> pd.DataFrame:
    """
    Read worksheet to DataFrame with custom header and data range.

    Args:
        spreadsheet_id: Google Spreadsheet ID
        sheet_name: nama sheet
        header_row: row untuk header (1-based), default 1
        start_row: row mulai data (1-based), default header_row + 1
        end_row: row akhir data (1-based), default sampai habis
        start_col: kolom mulai (1-based), default 1
        end_col: kolom akhir (1-based), default sampai habis

    Returns:
        pd.DataFrame
    """
    client = gs_client()
    ss = client.open_by_key(spreadsheet_id)
    ws = ss.worksheet(sheet_name)

    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()

    # Default start_row = header_row + 1
    if start_row is None:
        start_row = header_row + 1

    # Get header (convert to 0-based index)
    header_idx = header_row - 1
    if header_idx >= len(rows):
        return pd.DataFrame()

    headers = rows[header_idx]

    # Get data rows (convert to 0-based index)
    data_start = start_row - 1
    data_end = end_row if end_row else len(rows)
    data = rows[data_start:data_end]

    # Filter columns
    if start_col or end_col:
        col_start = (start_col - 1) if start_col else 0
        col_end = end_col if end_col else len(headers)
        headers = headers[col_start:col_end]
        data = [row[col_start:col_end] for row in data]

    # Remove empty rows
    data = [row for row in data if any(cell.strip() for cell in row)]

    df = pd.DataFrame(data, columns=headers)
    return df


def format_cells(
    ws,
    range_notation: str,
    background_color: tuple = None,
    bold: bool = False,
    text_color: tuple = None,
    font_size: int = None,
) -> None:
    """
    Apply formatting to a cell range.

    Args:
        ws: gspread Worksheet object
        range_notation: A1 notation, e.g. "A1:Z1" or "A2"
        background_color: RGB tuple 0-255, e.g. (255, 230, 153) for yellow
        bold: whether to bold the text
        text_color: RGB tuple 0-255, e.g. (0, 0, 0) for black
        font_size: font size in points
    """
    fmt = {}

    if background_color:
        r, g, b = background_color
        fmt["backgroundColor"] = {"red": r / 255, "green": g / 255, "blue": b / 255}

    cell_format = {}
    if bold:
        cell_format["bold"] = True
    if text_color:
        r, g, b = text_color
        cell_format["foregroundColor"] = {"red": r / 255, "green": g / 255, "blue": b / 255}
    if font_size:
        cell_format["fontSize"] = font_size
    if cell_format:
        fmt["textFormat"] = cell_format

    if fmt:
        ws.format(range_notation, fmt)


def highlight_rows(
    ws,
    row_numbers: list,
    background_color: tuple,
    num_cols: int,
    bold: bool = False,
    start_col: int = 1,
) -> None:
    """
    Highlight specific rows by row number (1-based).

    Args:
        ws: gspread Worksheet object
        row_numbers: list of row numbers to highlight (1-based)
        background_color: RGB tuple 0-255
        num_cols: number of columns to format
        bold: whether to bold the text
        start_col: starting column (1-based, default 1)
    """
    from gspread.utils import rowcol_to_a1

    requests_body = []
    r, g, b = background_color

    for row in row_numbers:
        start_a1 = rowcol_to_a1(row, start_col)
        end_a1 = rowcol_to_a1(row, start_col + num_cols - 1)
        cell_fmt = {
            "backgroundColor": {"red": r / 255, "green": g / 255, "blue": b / 255},
        }
        if bold:
            cell_fmt["textFormat"] = {"bold": True}
        requests_body.append({
            "range": f"{start_a1}:{end_a1}",
            "format": cell_fmt,
        })

    if requests_body:
        ws.batch_format(requests_body)