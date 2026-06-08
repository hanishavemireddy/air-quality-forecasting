import pandas as pd
import numpy as np
import logging
from datetime import datetime
from pydantic import BaseModel, field_validator, ValidationError


log = logging.getLogger(__name__)


# ── schema validation ─────────────────────────────────────────

class AQIReading(BaseModel):
    city:      str
    parameter: str
    value:     float
    timestamp: str

    @field_validator("value") # ensures PM2.5 values are within a reasonable range
    @classmethod # this runs after the built-in type validation, so we know value is already a float
    def value_must_be_positive(cls, v): #v is the value of the "value" field, which is the PM2.5 reading
        if v < 0:
            raise ValueError(f"PM2.5 can't be negative, got {v}")
        if v > 1000:
            raise ValueError(f"PM2.5 over 1000 is almost certainly a sensor error, got {v}")
        return v

    @field_validator("city") # ensures city is one of the known cities in our dataset
    @classmethod
    def city_must_be_known(cls, v):
        known = {"San Jose", "Los Angeles", "Chicago"}
        if v not in known:
            raise ValueError(f"unknown city: {v}")
        return v


def validate_rows(df):
    """
    Run each row through the Pydantic model.
    Returns (clean_df, rejected_count).
    """
    good, rejected = [], 0

    for _, row in df.iterrows():
        try:
            AQIReading( 
                city=row["city"],
                parameter=row["parameter"],
                value=row["value"],
                timestamp=str(row["timestamp"]),
            )
            good.append(row)
        except ValidationError as e:
            rejected += 1
            log.warning(f"rejected row — {e.errors()[0]['msg']}")

    if not good:
        return pd.DataFrame(), rejected

    return pd.DataFrame(good).reset_index(drop=True), rejected


# ── outlier flagging ──────────────────────────────────────────

def flag_outliers(df, window=30*24, iqr_factor=3.0):
    """
    Rolling IQR outlier detection.
    Marks suspicious rows with is_outlier_flag=True but keeps them.
    Window is in hours — 30 days * 24 hours = 720.
    """
    df = df.copy()
    df["is_outlier_flag"] = False

    for city in df["city"].unique():
        mask = df["city"] == city
        values = df.loc[mask, "value"]

        # For each city, calculate a rolling 30-day window of values, with at least 10 readings to be valid. 
        # Then compute the IQR and flag any points outside of the IQR by a factor of 3.
        rolling = values.rolling(window=window, min_periods=10, center=True)
        q1 = rolling.quantile(0.25)
        q3 = rolling.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - iqr_factor * iqr
        upper = q3 + iqr_factor * iqr

        outlier_mask = mask & ((values < lower) | (values > upper))
        flagged = outlier_mask.sum()

        df.loc[outlier_mask, "is_outlier_flag"] = True

        if flagged > 0:
            log.info(f"{city}: flagged {flagged} outliers")

    return df


# ── gap imputation ────────────────────────────────────────────

#SARIMA and Prophet require continuous data without gaps to run properly, 
#so we need to fill in any missing hours.

# Cleaned rows will outnumber raw rows because this step resamples to a full hourly grid
# and fills in hours where the sensor didn't report. Those filled rows are marked
# is_imputed=True so models and analysts can treat them differently if needed.
def impute_gaps(df):
    """
    Resample to hourly, forward-fill short gaps (up to 2 hours),
    then linear interpolate anything longer.
    Marks filled rows with is_imputed=True.
    """
    frames = []

    for city in df["city"].unique():
        city_df = df[df["city"] == city].copy()
        city_df = city_df.set_index("timestamp").sort_index()

        # strip timezone info so comparisons work cleanly
        city_df.index = city_df.index.tz_localize(None)

        # remember original timestamps as a set of strings for reliable comparison
        original_times = set(city_df.index.astype(str))

        # resample to hourly — introduces NaN rows for missing hours
        city_df = city_df.resample("1h").first()

        # fill in the non-value columns for new rows
        city_df["city"]      = city
        city_df["parameter"] = "pm2_5"
        city_df["unit"]      = "µg/m³"

        # forward-fill up to 2 consecutive gaps
        city_df["value"] = city_df["value"].ffill(limit=2)
        # linear interpolation for anything longer
        city_df["value"] = city_df["value"].interpolate(method="linear")

        # mark rows that weren't in the original data using string comparison to avoid timezone issues
        city_df["is_imputed"] = ~city_df.index.astype(str).isin(original_times)


        imputed_count = city_df["is_imputed"].sum()
        if imputed_count > 0:
            log.info(f"{city}: imputed {imputed_count} missing hours")

        city_df = city_df.reset_index()
        frames.append(city_df)
        
    return pd.concat(frames, ignore_index=True)


# ── deduplication ─────────────────────────────────────────────

def deduplicate(df):
    """
    Drop exact duplicate rows on city + timestamp + value.
    Keeps the first occurrence.
    """
    before = len(df)
    df = df.drop_duplicates(subset=["city", "timestamp", "value"], keep="first")
    dropped = before - len(df) # number of duplicates dropped

    if dropped > 0:
        log.info(f"deduplication: dropped {dropped} duplicate rows")

    return df.reset_index(drop=True)


# ── main clean function ───────────────────────────────────────

def clean(df):
    """
    Runs all 4 cleaning steps in order.
    Returns (cleaned_df, rejected_count).
    """
    log.info(f"cleaning {len(df)} rows...")

    # step 1 — schema validation
    df, rejected = validate_rows(df)
    if df.empty:
        log.warning("no rows passed validation")
        return df, rejected

    # step 2 — outlier flagging
    df = flag_outliers(df)

    # step 3 — gap imputation
    df = impute_gaps(df)

    # step 4 — deduplication
    df = deduplicate(df)

    log.info(f"cleaning done: {len(df)} rows, {rejected} rejected")
    return df, rejected


# ── quick test ────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s"
    )

    # import the scraper to get some real data to test with
    import sys
    sys.path.append(".")
    from pipeline.scraper import run_scraper

    raw = run_scraper(past_days=7)

    if raw is not None:
        cleaned, rejected = clean(raw)
        print(f"\nraw rows:     {len(raw)}")
        print(f"cleaned rows: {len(cleaned)}")
        print(f"rejected:     {rejected}")
        print(f"imputed:      {cleaned['is_imputed'].sum()}")
        print(f"flagged:      {cleaned['is_outlier_flag'].sum()}")
        print("\nsample of cleaned data:")
        print(cleaned.head(10).to_string(index=False))