"""
clean_data.py
-------------
Loads the raw Superstore-style sales export, resolves data-quality issues,
engineers analysis-ready features, and writes a clean CSV formatted for
both the Python EDA notebook and a direct Power BI import.

Run:
    python scripts/clean_data.py

Input:  data/raw/superstore_sales_raw.csv
Output: data/cleaned/superstore_sales_cleaned.csv
"""

import numpy as np
import pandas as pd

RAW_PATH = "/home/claude/sales-performance-analysis/data/raw/superstore_sales_raw.csv"
CLEAN_PATH = "/home/claude/sales-performance-analysis/data/cleaned/superstore_sales_cleaned.csv"


def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"[load] {len(df):,} rows loaded from {path}")
    return df


def clean_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and normalize casing on categorical text fields."""
    text_cols = ["Segment", "Region", "Category", "Sub-Category",
                 "Product Name", "Customer Name"]
    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()
        df.loc[df[col].isin(["nan", "NaN", "None", ""]), col] = np.nan

    # Title-case the controlled-vocabulary columns so "EAST", "east", "East"
    # all collapse to one canonical value.
    for col in ["Segment", "Region", "Category"]:
        df[col] = df[col].str.title()

    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Order Date / Ship Date arrive in five different formats. Parse them
    all to real datetimes without losing rows."""
    for col in ["Order Date", "Ship Date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)

    # Rows with no usable Sales figure or no dates can't be analyzed — drop.
    df = df.dropna(subset=["Order Date", "Ship Date", "Sales"]).copy()

    # Customer Name: unknown but the row is still valid financial data.
    df["Customer Name"] = df["Customer Name"].fillna("Unknown Customer")

    # Region: impute with the most common region for that Order ID's other
    # line items if available, else the global mode.
    region_mode = df["Region"].mode(dropna=True)[0]
    df["Region"] = df.groupby("Order ID")["Region"].transform(
        lambda s: s.fillna(s.mode().iloc[0]) if s.notna().any() else s
    )
    df["Region"] = df["Region"].fillna(region_mode)

    # Quantity: impute with the median quantity for that Sub-Category.
    df["Quantity"] = df.groupby("Sub-Category")["Quantity"].transform(
        lambda s: s.fillna(s.median())
    )
    df["Quantity"] = df["Quantity"].fillna(df["Quantity"].median()).round().astype(int)

    # Discount: assume no discount when missing (0.0 is the modal value anyway).
    df["Discount"] = df["Discount"].fillna(0.0)

    # Profit: reconstruct from Sales using the average profit-margin for that
    # Sub-Category + Discount bucket rather than dropping the row.
    df["_discount_bucket_tmp"] = pd.cut(
        df["Discount"], bins=[-0.01, 0.0, 0.3, 1.0], labels=["None", "Low-Mid", "High"]
    )
    margin_lookup = (
        df.dropna(subset=["Profit"])
        .assign(_margin=lambda d: d["Profit"] / d["Sales"])
        .groupby(["Sub-Category", "_discount_bucket_tmp"], observed=True)["_margin"]
        .mean()
    )
    global_margin = (df["Profit"] / df["Sales"]).mean()

    def fill_profit(row):
        if pd.notna(row["Profit"]):
            return row["Profit"]
        key = (row["Sub-Category"], row["_discount_bucket_tmp"])
        est_margin = margin_lookup.get(key, global_margin)
        return round(row["Sales"] * est_margin, 2)

    df["Profit"] = df.apply(fill_profit, axis=1)
    df = df.drop(columns=["_discount_bucket_tmp"])

    after = len(df)
    print(f"[missing] dropped {before - after:,} unrecoverable rows; "
          f"imputed remaining nulls in Customer Name, Region, Quantity, Discount, Profit")
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    dedup_cols = [c for c in df.columns if c != "Row ID"]
    df = df.drop_duplicates(subset=dedup_cols, keep="first").copy()
    after = len(df)
    print(f"[dupes] removed {before - after:,} exact duplicate rows")
    return df


def fix_invalid_records(df: pd.DataFrame) -> pd.DataFrame:
    """Guard against structurally invalid rows (negative quantity/sales,
    ship date before order date)."""
    before = len(df)
    df = df[(df["Sales"] > 0) & (df["Quantity"] > 0)]
    # A ship date can't precede its order date — if it does, swap them
    # (most likely a data-entry mix-up) rather than dropping good sales data.
    bad_order = df["Ship Date"] < df["Order Date"]
    df.loc[bad_order, ["Order Date", "Ship Date"]] = df.loc[bad_order, ["Ship Date", "Order Date"]].values
    after = len(df)
    print(f"[invalid] removed {before - after:,} rows with non-positive Sales/Quantity; "
          f"corrected {bad_order.sum():,} inverted ship/order dates")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    # Profit Margin (%)
    df["Profit Margin (%)"] = np.where(
        df["Sales"] > 0, round(df["Profit"] / df["Sales"] * 100, 2), 0.0
    )

    # Order Processing Time (days) = Ship Date - Order Date
    df["Order Processing Time (Days)"] = (df["Ship Date"] - df["Order Date"]).dt.days

    # Month-Year for time-series grouping (Power-BI-friendly text + a true date)
    df["Order Month"] = df["Order Date"].values.astype("datetime64[M]")
    df["Month-Year"] = df["Order Date"].dt.strftime("%b-%Y")
    df["Year"] = df["Order Date"].dt.year
    df["Quarter"] = df["Order Date"].dt.to_period("Q").astype(str)

    # Discount Bucket (Low / Medium / High)
    def bucket_discount(d):
        if d <= 0.10:
            return "Low"
        elif d <= 0.30:
            return "Medium"
        else:
            return "High"
    df["Discount Bucket"] = df["Discount"].apply(bucket_discount)

    # Helpful flags for downstream analysis / Power BI measures
    df["Is Loss Making"] = df["Profit"] < 0
    df["Unit Price"] = round(df["Sales"] / df["Quantity"], 2)

    return df


def enforce_schema_and_order(df: pd.DataFrame) -> pd.DataFrame:
    ordered_cols = [
        "Row ID", "Order ID", "Order Date", "Ship Date", "Month-Year", "Order Month",
        "Year", "Quarter", "Customer Name", "Segment", "Region", "Category",
        "Sub-Category", "Product Name", "Quantity", "Unit Price", "Discount",
        "Discount Bucket", "Sales", "Profit", "Profit Margin (%)",
        "Order Processing Time (Days)", "Is Loss Making",
    ]
    df = df[ordered_cols].sort_values("Order Date").reset_index(drop=True)
    df["Row ID"] = range(1, len(df) + 1)

    # Power BI imports date columns most reliably as ISO strings.
    df["Order Date"] = df["Order Date"].dt.strftime("%Y-%m-%d")
    df["Ship Date"] = df["Ship Date"].dt.strftime("%Y-%m-%d")
    df["Order Month"] = df["Order Month"].astype(str).str[:7]  # YYYY-MM

    return df


def main():
    df = load_raw(RAW_PATH)
    df = clean_text_columns(df)
    df = parse_dates(df)
    df = handle_missing_values(df)
    df = remove_duplicates(df)
    df = fix_invalid_records(df)
    df = engineer_features(df)
    df = enforce_schema_and_order(df)

    df.to_csv(CLEAN_PATH, index=False)
    print(f"[save] {len(df):,} clean rows written to {CLEAN_PATH}")
    print(df.dtypes)
    print(df.isna().sum().sum(), "remaining nulls")


if __name__ == "__main__":
    main()
