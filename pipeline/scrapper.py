import requests
import pandas as pd
import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)


# ── config ────────────────────────────────────────────────────

CITIES = {
    "San Jose": {"latitude": 37.34, "longitude": -121.89},
    "Los Angeles": {"latitude": 34.05, "longitude": -118.24},
    "Chicago": {"latitude": 41.88, "longitude": -87.63},
}

BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


# ── fetch ─────────────────────────────────────────────────────

def fetch_aqi(city, past_days=7):
    """
    Pull hourly PM2.5 for a city from Open-Meteo.
    Returns a raw dict from the API, or None if something goes wrong.
    """
    coords = CITIES.get(city)
    if not coords:
        log.error(f"unknown city: {city}")
        return None

    params = {
        "latitude":  coords["latitude"],
        "longitude": coords["longitude"],
        "hourly":    "pm2_5",
        "timezone":  "America/Los_Angeles",
        "past_days": past_days,
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        log.info(f"{city}: got response ({resp.elapsed.total_seconds():.2f}s)")
        return resp.json()
    except requests.RequestException as e:
        log.error(f"{city}: request failed — {e}")
        return None


# ── parse ─────────────────────────────────────────────────────

def parse_to_df(raw, city):
    """
    Turn the Open-Meteo response into a tidy DataFrame.
    Drops rows where PM2.5 is null (sensor gaps are common).
    """
    if not raw or "hourly" not in raw:
        log.warning(f"{city}: no hourly data in response")
        return pd.DataFrame()

    df = pd.DataFrame({
        "timestamp": raw["hourly"]["time"],
        "value":     raw["hourly"]["pm2_5"],
    })

    df["city"]       = city
    df["parameter"]  = "pm2_5"
    df["unit"]       = "µg/m³"
    df["fetched_at"] = datetime.now(timezone.utc).isoformat()

    # convert timestamp string to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # drop rows with no reading — we'll impute these in cleaner.py
    before = len(df)
    df = df.dropna(subset=["value"]).reset_index(drop=True)
    dropped = before - len(df)
    if dropped > 0:
        log.info(f"{city}: dropped {dropped} null readings")

    log.info(f"{city}: {len(df)} clean rows")
    return df


# ── main ──────────────────────────────────────────────────────

def run_scraper(past_days=7):
    all_frames = []

    for city in CITIES:
        log.info(f"fetching {city}...")
        raw = fetch_aqi(city, past_days=past_days)
        df  = parse_to_df(raw, city)

        if not df.empty:
            all_frames.append(df)

    if not all_frames:
        log.error("no data collected for any city")
        return None

    combined = pd.concat(all_frames, ignore_index=True)
    log.info(f"total rows collected: {len(combined)}")
    print(combined.head(10).to_string(index=False))
    return combined


if __name__ == "__main__":
    run_scraper(past_days=7)