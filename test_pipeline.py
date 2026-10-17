import sqlite3
import pandas as pd
from src.etl import load, transform
from src.insights import compute_metrics
from src.quality import validate


def sample():
    return pd.DataFrame({
        "InvoiceNo": ["1", "1", "2", "3", "4", "5"],
        "StockCode": ["A", "A", "B", "A", "B", "A"],
        "Description": ["  mug", "  mug", "pen", "mug", "pen", "mug"],
        "Quantity": [2, 2, -1, 3, 4, 1],
        "InvoiceDate": ["2025-01-05 10:00"] * 3 + ["2025-02-07 11:00", "bad-date", "2025-02-08 09:00"],
        "UnitPrice": [5.0, 5.0, 2.0, 5.0, 2.0, 0.0],
        "CustomerID": [1.0, 1.0, 2.0, None, 2.0, 3.0],
        "Country": ["India", "India", "India", "USA", "USA", "USA"]})


def test_quality_rules_and_counts():
    clean, rejects, rep = validate(sample())
    assert rep["rows_in"] == 6 and rep["rows_clean"] == 1 and rep["rows_rejected"] == 5
    assert set(rejects["reject_reason"]) == {"duplicate_row", "non_positive_quantity", "missing_customer",
                                              "invalid_date", "non_positive_price"}


def test_star_schema_and_metrics(tmp_path):
    good = sample().iloc[[0, 3]].copy()
    good["CustomerID"] = [1.0, 2.0]
    good["InvoiceDate"] = pd.to_datetime(good["InvoiceDate"])
    tables = transform(good)
    assert list(tables["fact_sales"]["revenue"]) == [10.0, 15.0]
    db = str(tmp_path / "w.db")
    load(tables, db)
    m = compute_metrics(db)
    assert m["total_revenue"] == 25.0 and m["orders"] == 2
    assert compute_metrics(db, ["India"])["total_revenue"] == 10.0
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0] == 2
