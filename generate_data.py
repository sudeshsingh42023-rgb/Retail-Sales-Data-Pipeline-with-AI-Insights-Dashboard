"""Generate a synthetic retail dataset (Online-Retail-style schema) with realistic dirt.
Swap in a real dataset (e.g. Kaggle 'Online Retail') by writing it to data/raw_sales.csv with the same columns.
Usage: python -m src.generate_data --rows 500000
"""
import argparse

import numpy as np
import pandas as pd

COUNTRIES = ["United Kingdom", "Germany", "France", "Spain", "Netherlands", "India", "USA", "Australia"]
COUNTRY_P = [0.45, 0.12, 0.10, 0.06, 0.06, 0.08, 0.08, 0.05]


def generate(rows: int = 500_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_products, n_customers = 2000, 8000
    base_price = np.round(rng.lognormal(1.5, 0.8, n_products) + 0.5, 2)
    pid = rng.zipf(1.3, rows) % n_products  # a few bestsellers, long tail
    days = rng.integers(0, 730, rows)
    dates = pd.Timestamp("2024-01-01") + pd.to_timedelta(days, unit="D") \
        + pd.to_timedelta(rng.integers(8 * 60, 20 * 60, rows), unit="m")
    seasonal = 1 + 0.4 * (pd.Series(dates).dt.month.isin([10, 11, 12])).to_numpy()
    qty = np.maximum(1, (rng.poisson(3, rows) * seasonal).astype(int))
    df = pd.DataFrame({
        "InvoiceNo": rng.integers(100000, 100000 + rows // 4, rows).astype(str),
        "StockCode": [f"P{p:05d}" for p in pid],
        "Description": [f"Product {p}" for p in pid],
        "Quantity": qty,
        "InvoiceDate": dates,
        "UnitPrice": base_price[pid],
        "CustomerID": rng.integers(10000, 10000 + n_customers, rows).astype("float"),
        "Country": rng.choice(COUNTRIES, rows, p=COUNTRY_P),
    })
    # inject data-quality problems
    df.loc[rng.random(rows) < 0.02, "CustomerID"] = np.nan
    df.loc[rng.random(rows) < 0.01, "Quantity"] *= -1          # returns
    df.loc[rng.random(rows) < 0.003, "UnitPrice"] = 0
    dup = df.sample(frac=0.005, random_state=seed)
    return pd.concat([df, dup], ignore_index=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=500_000)
    ap.add_argument("--out", default="data/raw_sales.csv")
    a = ap.parse_args()
    d = generate(a.rows)
    d.to_csv(a.out, index=False)
    print(f"wrote {len(d):,} rows -> {a.out}")
