"""
generate_data.py
-----------------
Generates a realistic, synthetic retail sales dataset (Superstore-style)
with intentional data-quality issues baked in (missing values, duplicates,
inconsistent date formats) so the cleaning script has real work to do.

Output: data/raw/superstore_sales_raw.csv
"""

import numpy as np
import pandas as pd
from datetime import timedelta
import random

# ----------------------------------------------------------------------
# Reproducibility
# ----------------------------------------------------------------------
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

N_ROWS = 5600  # will drop some to duplicates/nulls to land >5000 clean rows

# ----------------------------------------------------------------------
# Reference lists
# ----------------------------------------------------------------------
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
SEGMENT_WEIGHTS = [0.52, 0.30, 0.18]

REGIONS = ["East", "West", "Central", "South"]
REGION_WEIGHTS = [0.30, 0.28, 0.24, 0.18]

CATEGORY_SUBCATS = {
    "Furniture": ["Bookcases", "Chairs", "Tables", "Furnishings"],
    "Office Supplies": ["Storage", "Appliances", "Binders", "Paper",
                         "Envelopes", "Labels", "Art", "Fasteners", "Supplies"],
    "Technology": ["Phones", "Machines", "Accessories", "Copiers"],
}

# base unit-economics per sub-category: (avg unit price, cost ratio, list of product name stems)
SUBCAT_PROFILE = {
    "Bookcases":     (280, 0.72, ["Sauder Bookcase", "Bush Classic Bookcase", "O'Sullivan Bookcase"]),
    "Chairs":        (210, 0.68, ["Hon Task Chair", "Global Deluxe Chair", "Harbour Creations Chair"]),
    "Tables":        (390, 0.75, ["Bretford Conference Table", "Chromcraft Round Table", "Bevis Table"]),
    "Furnishings":   (55,  0.55, ["Eldon Desk Lamp", "Tenex Chairmat", "Fellowes Wall Clock"]),
    "Storage":       (95,  0.58, ["Fellowes File Cart", "SAFCO Storage Bin", "IRIS Storage Box"]),
    "Appliances":    (140, 0.60, ["Hoover Vacuum", "Honeywell Fan", "Avanti Refrigerator"]),
    "Binders":       (18,  0.40, ["Acco Binder", "GBC Binding System", "Wilson Jones Binder"]),
    "Paper":         (12,  0.35, ["Xerox Multipurpose Paper", "HP Premium Paper", "Boise Copy Paper"]),
    "Envelopes":     (14,  0.38, ["Poly String Envelope", "Kraft Clasp Envelope"]),
    "Labels":        (9,   0.33, ["Avery Label Set", "Sharpie Label Tape"]),
    "Art":           (16,  0.42, ["Newell Scissors", "Sharpie Marker Set", "Prismacolor Pencils"]),
    "Fasteners":     (7,   0.30, ["ACCO Fasteners", "Bostitch Staples"]),
    "Supplies":      (25,  0.45, ["Stanley Hole Punch", "Elmer's Glue Pack"]),
    "Phones":        (330, 0.70, ["Apple iPhone Accessory", "Samsung Galaxy Dock", "Cisco IP Phone"]),
    "Machines":      (750, 0.78, ["Cubify 3D Printer", "Lexmark Printer", "Zebra Label Printer"]),
    "Accessories":   (48,  0.50, ["Logitech Mouse", "SanDisk USB Drive", "Belkin Cable"]),
    "Copiers":       (1450,0.80, ["Canon imageCLASS Copier", "Hewlett Packard Copier"]),
}

FIRST_NAMES = ["James", "Maria", "Wei", "Ananya", "Liam", "Sofia", "Noah", "Emma",
               "Arjun", "Olivia", "Mateo", "Chloe", "Ravi", "Isabella", "Ethan",
               "Priya", "Lucas", "Mia", "Kavya", "Daniel", "Grace", "Yusuf",
               "Hannah", "Carlos", "Nina", "Omar", "Zoe", "Amit", "Laura", "Kenji"]
LAST_NAMES = ["Smith", "Johnson", "Chen", "Patel", "Garcia", "Kumar", "Brown",
              "Davis", "Wilson", "Anderson", "Thomas", "Martinez", "Lee",
              "Clark", "Rodriguez", "Nair", "Walker", "Young", "King", "Wright"]

# ----------------------------------------------------------------------
# Order-level generation (multiple line items can share an Order ID)
# ----------------------------------------------------------------------
def random_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

start_date = pd.Timestamp("2021-01-01")
end_date = pd.Timestamp("2024-12-31")

rows = []
order_counter = 1
row_id = 1

while row_id <= N_ROWS:
    # each "order" has 1-4 line items
    n_items = np.random.choice([1, 2, 3, 4], p=[0.55, 0.27, 0.12, 0.06])
    order_date = random_date(start_date, end_date)

    # ship mode influences processing time
    ship_mode_days = np.random.choice([1, 2, 3, 4, 5, 6, 7], p=[0.05, 0.1, 0.25, 0.25, 0.15, 0.1, 0.1])
    ship_date = order_date + timedelta(days=int(ship_mode_days))

    customer = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    segment = np.random.choice(SEGMENTS, p=SEGMENT_WEIGHTS)
    region = np.random.choice(REGIONS, p=REGION_WEIGHTS)

    order_id = f"US-{order_date.year}-{100000 + order_counter}"
    order_counter += 1

    for _ in range(n_items):
        if row_id > N_ROWS:
            break

        category = np.random.choice(list(CATEGORY_SUBCATS.keys()), p=[0.22, 0.60, 0.18])
        subcat = random.choice(CATEGORY_SUBCATS[category])
        base_price, cost_ratio, name_stems = SUBCAT_PROFILE[subcat]

        product_name = f"{random.choice(name_stems)} {random.choice(['Standard','Deluxe','Pro','Classic','Value'])}"

        quantity = int(np.random.choice([1, 2, 3, 4, 5, 6], p=[0.35, 0.25, 0.16, 0.12, 0.07, 0.05]))
        unit_price = max(3, np.random.normal(base_price, base_price * 0.25))

        # discount distribution: many at 0, some promo tiers
        discount = np.random.choice(
            [0.0, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            p=[0.38, 0.14, 0.10, 0.12, 0.10, 0.07, 0.04, 0.02, 0.02, 0.01]
        )

        sales = round(unit_price * quantity * (1 - 0), 2)  # gross list sales for the line (pre-discount reference)
        sales = round(unit_price * quantity, 2)
        discounted_sales = round(sales * (1 - discount), 2)

        # cost model: cost scales with cost_ratio of *undiscounted* sales;
        # profit erodes (and goes negative) as discount rises past a point
        cost = sales * cost_ratio
        profit = round(discounted_sales - cost, 2)

        # small noise on profit to feel organic
        profit = round(profit + np.random.normal(0, sales * 0.02), 2)

        rows.append({
            "Row ID": row_id,
            "Order ID": order_id,
            "Order Date": order_date,
            "Ship Date": ship_date,
            "Customer Name": customer,
            "Segment": segment,
            "Region": region,
            "Category": category,
            "Sub-Category": subcat,
            "Product Name": product_name,
            "Sales": discounted_sales,
            "Quantity": quantity,
            "Discount": discount,
            "Profit": profit,
        })
        row_id += 1

df = pd.DataFrame(rows)

# ----------------------------------------------------------------------
# Inject realistic data-quality problems for the cleaning step to solve
# ----------------------------------------------------------------------

# 1) Inconsistent date formats (mix of formats as strings)
def format_date_messy(d, idx):
    fmt_choice = idx % 5
    if fmt_choice == 0:
        return d.strftime("%Y-%m-%d")
    elif fmt_choice == 1:
        return d.strftime("%m/%d/%Y")
    elif fmt_choice == 2:
        return d.strftime("%d-%b-%Y")
    elif fmt_choice == 3:
        return d.strftime("%B %d, %Y")
    else:
        return d.strftime("%d/%m/%Y")

df["Order Date"] = [format_date_messy(d, i) for i, d in enumerate(df["Order Date"])]
df["Ship Date"] = [format_date_messy(d, i + 3) for i, d in enumerate(df["Ship Date"])]

# 2) Missing values scattered across several columns
rng = np.random.default_rng(SEED)
missing_frac = {
    "Customer Name": 0.01,
    "Sales": 0.008,
    "Profit": 0.01,
    "Discount": 0.006,
    "Region": 0.004,
    "Quantity": 0.005,
}
for col, frac in missing_frac.items():
    n_missing = int(len(df) * frac)
    idxs = rng.choice(df.index, size=n_missing, replace=False)
    df.loc[idxs, col] = np.nan

# 3) Duplicate rows (exact dupes of a few existing rows)
dupe_rows = df.sample(n=60, random_state=SEED)
df = pd.concat([df, dupe_rows], ignore_index=True)

# 4) A few whitespace / casing inconsistencies in categorical text
messy_idx = rng.choice(df.index, size=25, replace=False)
for i in messy_idx:
    col = rng.choice(["Segment", "Region", "Category"])
    val = df.loc[i, col]
    if isinstance(val, str):
        df.loc[i, col] = f" {val.upper()} " if rng.random() > 0.5 else val.lower()

# 5) Shuffle rows so it doesn't look artificially ordered
df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
df["Row ID"] = range(1, len(df) + 1)

# Reorder columns to the required schema
df = df[["Row ID", "Order ID", "Order Date", "Ship Date", "Customer Name",
         "Segment", "Region", "Category", "Sub-Category", "Product Name",
         "Sales", "Quantity", "Discount", "Profit"]]

out_path = "/home/claude/sales-performance-analysis/data/raw/superstore_sales_raw.csv"
df.to_csv(out_path, index=False)
print(f"Saved {len(df)} rows to {out_path}")
print(df.isna().sum())
print("Duplicate rows:", df.duplicated().sum())
