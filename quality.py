"""Data-quality gate: rejects bad rows (with a reason) before they reach the warehouse."""
import pandas as pd

RULES = ["missing_customer", "non_positive_quantity", "non_positive_price", "invalid_date", "duplicate_row"]


def validate(df: pd.DataFrame):
    """Return (clean_df, rejects_df, report_dict). Each rejected row carries the first rule it failed."""
    df = df.copy()
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    checks = {
        "missing_customer": df["CustomerID"].isna(),
        "non_positive_quantity": df["Quantity"] <= 0,
        "non_positive_price": df["UnitPrice"] <= 0,
        "invalid_date": df["InvoiceDate"].isna(),
        "duplicate_row": df.duplicated(keep="first"),
    }
    reason = pd.Series("", index=df.index)
    for rule in reversed(RULES):  # earlier rules win
        reason = reason.mask(checks[rule], rule)
    bad = reason != ""
    rejects = df[bad].assign(reject_reason=reason[bad])
    clean = df[~bad]
    report = {
        "rows_in": int(len(df)),
        "rows_clean": int(len(clean)),
        "rows_rejected": int(bad.sum()),
        "by_rule": {r: int(checks[r].sum()) for r in RULES},
        "reject_rate_pct": round(100 * bad.mean(), 2) if len(df) else 0.0,
    }
    return clean, rejects, report
