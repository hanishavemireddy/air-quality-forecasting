import logging
import sys
sys.path.append(".")

from pipeline.scraper import run_scraper
from pipeline.cleaner import clean
from pipeline.database import create_tables, store_raw, store_cleaned, log_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)


def run_pipeline(past_days=7):
    # make sure tables exist
    create_tables()

    # scrape all cities
    raw_df = run_scraper(past_days=past_days)
    if raw_df is None:
        log.error("scraper returned nothing — aborting")
        return

    # process each city separately so we can log them individually
    for city in raw_df["city"].unique():
        log.info(f"--- processing {city} ---")

        city_raw = raw_df[raw_df["city"] == city].copy()
        rows_fetched = len(city_raw)

        try:
            # store the raw rows first — always, before anything else
            store_raw(city_raw)

            # clean
            city_cleaned, rejected = clean(city_raw)

            # store cleaned
            rows_stored = store_cleaned(city_cleaned)

            # log the run
            log_run(
                city=city,
                rows_fetched=rows_fetched,
                rows_rejected=rejected,
                rows_stored=rows_stored,
            )

            log.info(f"{city}: fetched={rows_fetched}, rejected={rejected}, stored={rows_stored}")

        except Exception as e:
            log.error(f"{city}: pipeline failed — {e}")
            log_run(
                city=city,
                rows_fetched=rows_fetched,
                rows_rejected=0,
                rows_stored=0,
                error_msg=str(e),
            )


# if __name__ == "__main__":
#     run_pipeline(past_days=7)

# Adding a backfill to ensure SARIMA (mainly) and Prophet have enough data to capture seasonality.
# By default, it fetches 7 days of data, but you can specify up to 90 days for a backfill.
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backfill",
        type=int,
        default=7,
        help="number of past days to fetch (default 7, use 90 for backfill)"
    )
    args = parser.parse_args()

    run_pipeline(past_days=args.backfill)

    ### Use this command on terminal to run with a backfill of 90 days:
    # python pipeline/run_pipeline.py --backfill 90