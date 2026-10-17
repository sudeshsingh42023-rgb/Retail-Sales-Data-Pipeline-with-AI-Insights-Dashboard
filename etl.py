"""Extract -> validate -> transform -> load into a SQLite star schema.
Usage: python -m src.etl --csv data/raw_sales.csv --db data/warehouse.db
"""
import argparse
import json
import sqlite3
import time

import pandas as pd

from .quality import validate

SCHEMA = """
DROP TABLE IF EXISTS fact_sales; DROP TABLE IF EXISTS dim_product; DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_region; DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_product(product_key INTEGER PRIMARY KEY, stock_code TEXT UNIQUE, description TEXT);
CREATE TABLE dim_customer(customer_key INTEGER PRIMARY KEY);
CREATE TABLE dim_region(region_key INTEGER PRIMARY KEY, country TEXT UNIQUE);
CREATE TABLE dim_date(date_key INTEGER PRIMARY KEY, date TEXT, year INT, month INT, quarter INT, day_of_week INT);
CREATE TABLE fact_sales(invoice_no TEXT, date_key INT, product_key INT, customer_key INT, region_key INT,
                        quantity INT, unit_price REAL, revenue REAL, invoice_ts TEXT);
"""
INDEXES = """
CREATE INDEX ix_fact_date ON fact_sales(date_key);
CREATE INDEX ix_fact_product ON fact_sales(product_key);
CREATE INDEX ix_fact_region ON fact_sales(region_key);
CREATE INDEX ix_fact_customer ON fact_sales(customer_key);
"""


def extract(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path, parse_dates=["InvoiceDate"])


def transform(clean: pd.DataFrame) -> dict:
    d = clean.copy()
    d["CustomerID"] = d["CustomerID"].astype(int)
    d["Description"] = d["Description"].str.strip().str.title()
    d["Country"] = d["Country"].str.strip()
    d["revenue"] = (d["Quantity"] * d["UnitPrice"]).round(2)

    dim_product = d.drop_duplicates("StockCode")[["StockCode", "Description"]].reset_index(drop=True)
    dim_product.insert(0, "product_key", dim_product.index + 1)
    dim_region = pd.DataFrame({"country": sorted(d["Country"].unique())})
    dim_region.insert(0, "region_key", dim_region.index + 1)
    dim_customer = pd.DataFrame({"customer_key": sorted(d["CustomerID"].unique())})
    day = d["InvoiceDate"].dt.normalize().drop_duplicates().sort_values()
    dim_date = pd.DataFrame({
        "date_key": day.dt.strftime("%Y%m%d").astype(int), "date": day.dt.strftime("%Y-%m-%d"),
        "year": day.dt.year, "month": day.dt.month, "quarter": day.dt.quarter, "day_of_week": day.dt.dayofweek})

    fact = (d.merge(dim_product[["product_key", "StockCode"]], on="StockCode")
             .merge(dim_region.rename(columns={"country": "Country"}), on="Country"))
    fact = pd.DataFrame({
        "invoice_no": fact["InvoiceNo"].astype(str),
        "date_key": fact["InvoiceDate"].dt.strftime("%Y%m%d").astype(int),
        "product_key": fact["product_key"], "customer_key": fact["CustomerID"], "region_key": fact["region_key"],
        "quantity": fact["Quantity"], "unit_price": fact["UnitPrice"], "revenue": fact["revenue"],
        "invoice_ts": fact["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")})
    return {"dim_product": dim_product.rename(columns={"StockCode": "stock_code", "Description": "description"}),
            "dim_region": dim_region, "dim_customer": dim_customer, "dim_date": dim_date, "fact_sales": fact}


def load(tables: dict, db_path: str) -> None:
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    for name, frame in tables.items():
        frame.to_sql(name, con, if_exists="append", index=False, chunksize=50_000)
    con.executescript(INDEXES)
    con.commit()
    con.close()


def run(csv_path: str, db_path: str, rejects_path: str | None = None) -> dict:
    t0 = time.time()
    raw = extract(csv_path)
    clean, rejects, report = validate(raw)
    if rejects_path:
        rejects.to_csv(rejects_path, index=False)
    load(transform(clean), db_path)
    report["seconds"] = round(time.time() - t0, 1)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/raw_sales.csv")
    ap.add_argument("--db", default="data/warehouse.db")
    ap.add_argument("--rejects", default="data/rejects.csv")
    a = ap.parse_args()
    print(json.dumps(run(a.csv, a.db, a.rejects), indent=2))
