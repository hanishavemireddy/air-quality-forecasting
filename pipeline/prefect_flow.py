"""
Prefect flow for the AQI data pipeline.
Replaces the manual run_pipeline.py with proper orchestration —
retries, scheduling, and a UI showing every run's task-level status.
"""

import sys
sys.path.append(".")

from prefect import task, flow
from prefect.schedules import Cron

import logging
from pipeline.scraper import fetch_aqi, parse_to_df, CITIES 
from pipeline.cleaner import clean
from pipeline.database import create_tables, store_raw, store_cleaned, log_run

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")



@task(retries=3, retry_delay_seconds=60)
def scrape_city(city):
    raw = fetch_aqi(city)
    return parse_to_df(raw, city)


@task
def clean_and_store(df, city):
    rows_fetched = len(df)
    cleaned, rejected = clean(df)
    store_raw(df)
    rows_stored = store_cleaned(cleaned)
    log_run(
        city=city,
        rows_fetched=rows_fetched,
        rows_rejected=rejected,
        rows_stored=rows_stored,
    )

@flow(name="aqi-daily-pipeline")
def run_pipeline():
    create_tables()
    for city in CITIES:
        raw = scrape_city(city)
        clean_and_store(raw, city) 

if __name__ == "__main__":
        # run once immediately
    run_pipeline()
    
    # create a scheduled deployment — runs daily at 6am
    run_pipeline.serve(
        name="aqi-daily-schedule",
        cron="0 6 * * *",  # 6am every day
    )