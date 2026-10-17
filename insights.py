"""Metrics + AI-generated plain-English insights.
Uses the Anthropic API when ANTHROPIC_API_KEY is set; otherwise falls back to a rule-based summary,
so the dashboard always works. The LLM only ever sees aggregated metrics, never raw rows."""
import json
import os
import sqlite3

SYSTEM = ("You are a retail analytics assistant. Answer ONLY from the metrics JSON provided. "
          "If the metrics cannot answer the question, say so. Be concise and quote numbers.")


def compute_metrics(db_path: str, countries: list[str] | None = None) -> dict:
    con = sqlite3.connect(db_path)
    where, params = "", []
    if countries:
        where = f"WHERE r.country IN ({','.join('?' * len(countries))})"
        params = list(countries)
    base = ("FROM fact_sales f JOIN dim_region r USING(region_key) JOIN dim_product p USING(product_key) "
            "JOIN dim_date d USING(date_key) " + where)
    q = lambda sql: con.execute(sql, params).fetchall()
    total, orders, customers = q(f"SELECT ROUND(SUM(revenue),2), COUNT(DISTINCT invoice_no), "
                                 f"COUNT(DISTINCT customer_key) {base}")[0]
    monthly = q(f"SELECT d.year||'-'||printf('%02d', d.month) m, ROUND(SUM(revenue),2) {base} GROUP BY m ORDER BY m")
    top_products = q(f"SELECT p.description, ROUND(SUM(revenue),2) rev {base} GROUP BY p.product_key ORDER BY rev DESC LIMIT 5")
    by_country = q(f"SELECT r.country, ROUND(SUM(revenue),2) rev {base} GROUP BY r.country ORDER BY rev DESC")
    con.close()
    mom = None
    if len(monthly) >= 2 and monthly[-2][1]:
        mom = round(100 * (monthly[-1][1] - monthly[-2][1]) / monthly[-2][1], 1)
    return {"total_revenue": total, "orders": orders, "customers": customers,
            "aov": round(total / orders, 2) if orders else 0, "monthly_revenue": monthly,
            "top_products": top_products, "revenue_by_country": by_country, "latest_mom_pct": mom}


def _llm(prompt: str) -> str | None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        msg = anthropic.Anthropic().messages.create(
            model=os.getenv("INSIGHTS_MODEL", "claude-sonnet-4-6"), max_tokens=500, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    except Exception as exc:  # network/key problems shouldn't break the dashboard
        return f"(AI unavailable: {exc})"


def _rule_based(m: dict) -> str:
    top = m["top_products"][0] if m["top_products"] else ("n/a", 0)
    ctry = m["revenue_by_country"][0] if m["revenue_by_country"] else ("n/a", 0)
    trend = f"{m['latest_mom_pct']:+.1f}% vs previous month" if m["latest_mom_pct"] is not None else "no trend yet"
    return (f"Revenue is {m['total_revenue']:,.0f} across {m['orders']:,} orders from {m['customers']:,} customers "
            f"(AOV {m['aov']:,.2f}). Latest month: {trend}. Top product: {top[0]} ({top[1]:,.0f}). "
            f"Top market: {ctry[0]} ({ctry[1]:,.0f}).")


def summarize(m: dict) -> str:
    return _llm("Write a 4-sentence executive summary of these retail metrics, flagging one risk "
                f"and one opportunity:\n{json.dumps(m)}") or _rule_based(m)


def answer(question: str, m: dict) -> str:
    return _llm(f"Metrics:\n{json.dumps(m)}\n\nQuestion: {question}") or \
        "Set ANTHROPIC_API_KEY to enable natural-language questions. Meanwhile: " + _rule_based(m)
