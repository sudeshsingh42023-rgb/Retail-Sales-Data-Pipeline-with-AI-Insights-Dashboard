# Retail Sales Data Pipeline with AI Insights Dashboard

ETL pipeline (500K+ rows) -> data-quality gate -> SQLite star schema -> Streamlit dashboard with LLM-written summaries and natural-language Q&A. Orchestrated by an Airflow DAG.

```bash
pip install -r requirements.txt
python -m src.generate_data --rows 500000   # synthetic data (or drop a real CSV at data/raw_sales.csv)
python -m src.etl                           # validate + load; rejects go to data/rejects.csv
streamlit run dashboard/app.py
python -m pytest tests
```
Optional: `export ANTHROPIC_API_KEY=...` enables LLM summaries/Q&A (falls back to a rule-based summary otherwise). The model only sees aggregated metrics, never raw rows.

## Layout
- `src/quality.py` – 5 validation rules (missing customer, non-positive qty/price, bad date, duplicates) with per-rule report
- `src/etl.py` – extract -> transform -> load; star schema: `fact_sales` + `dim_product/customer/region/date`, indexed FKs
- `src/insights.py` – KPI/trend queries + AI layer
- `dags/retail_etl_dag.py` – nightly DAG, fails if reject rate > 10%
- `dashboard/app.py` – KPIs, monthly trend, top products, country filter, AI insights

## Note
The bundled generator creates synthetic data with injected dirt (~3.7% rejected). Say "synthetic/Kaggle-style" honestly in interviews, or swap in a real dataset.
