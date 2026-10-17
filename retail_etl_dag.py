"""Airflow DAG: nightly refresh of the retail warehouse (extract -> validate -> load)."""
from datetime import datetime, timedelta

from airflow.decorators import dag, task

RAW, DB, REJECTS = "/opt/data/raw_sales.csv", "/opt/data/warehouse.db", "/opt/data/rejects.csv"


@dag(schedule="0 2 * * *", start_date=datetime(2026, 1, 1), catchup=False,
     default_args={"retries": 2, "retry_delay": timedelta(minutes=5)}, tags=["retail"])
def retail_sales_etl():
    @task
    def extract_validate() -> dict:
        from src.etl import extract
        from src.quality import validate
        clean, rejects, report = validate(extract(RAW))
        rejects.to_csv(REJECTS, index=False)
        if report["reject_rate_pct"] > 10:  # fail loudly on bad upstream data
            raise ValueError(f"Reject rate too high: {report['reject_rate_pct']}%")
        return report

    @task
    def load_warehouse(report: dict) -> dict:
        from src.etl import run
        return run(RAW, DB, REJECTS)

    load_warehouse(extract_validate())


retail_sales_etl()
