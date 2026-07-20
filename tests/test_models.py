import sys
sys.path.append(".")

import sqlite3
import logging
import pandas as pd
from models import sarima_model, prophet_model, chronos_model

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")


def load_city(conn, city):
    """Helper to load cleaned data for a city from the database."""
    return pd.read_sql(f"""
        SELECT timestamp, value FROM cleaned_readings
        WHERE city='{city}'
        ORDER BY timestamp
    """, conn, parse_dates=["timestamp"], index_col="timestamp")


def test_sarima_chicago():
    """SARIMA on Chicago daily data — m=7, horizon=14 days."""
    conn = sqlite3.connect("data/aqi.db")
    
    chicago = load_city(conn, "Chicago")
    chicago_daily = chicago["value"].resample("D").mean().dropna()
    conn.close()

    model = sarima_model

    forecast = model.fit_and_forecast(chicago_daily, horizon=14, freq="D", m=7)

    # check shape
    assert len(forecast) == 14, f"expected 14 rows, got {len(forecast)}"

    # check columns
    assert all(col in forecast.columns for col in ["ds", "yhat", "lower_ci", "upper_ci"])

    # check no nulls in forecast
    assert forecast["yhat"].isna().sum() == 0

    print("\nChicago SARIMA forecast:")
    print(forecast.to_string(index=False))


def test_sarima_la():
    """SARIMA on LA hourly data — m=24, horizon=48 hours."""
    conn = sqlite3.connect("data/aqi.db")

    la = load_city(conn, "Los Angeles")
    la_hourly = la["value"].resample("h").mean().dropna()
    conn.close()

    model =sarima_model

    forecast = model.fit_and_forecast(la_hourly, horizon=48, freq="h", m=24)

    assert len(forecast) == 48
    assert all(col in forecast.columns for col in ["ds", "yhat", "lower_ci", "upper_ci"])
    assert forecast["yhat"].isna().sum() == 0

    print("\nLA SARIMA forecast:")
    print(forecast.head(10).to_string(index=False))


def test_prophet_chicago():
    """Prophet on Chicago daily data — m=7, horizon=14 days."""
    conn = sqlite3.connect("data/aqi.db")
    
    chicago = load_city(conn, "Chicago")
    chicago_daily = chicago["value"].resample("D").mean().dropna()
    conn.close()

    model = prophet_model

    forecast = model.fit_and_forecast(chicago_daily, horizon=14, freq="D", m=7, 
                                      seasonality_mode="additive",
                                      changepoint_prior_scale=0.05, add_holidays=True)

    # check shape
    assert len(forecast) == 14, f"expected 14 rows, got {len(forecast)}"

    # check columns
    assert all(col in forecast.columns for col in ["ds", "yhat", "lower_ci", "upper_ci"])

    # check no nulls in forecast
    assert forecast["yhat"].isna().sum() == 0

    print("\nChicago Prophet forecast:")
    print(forecast.to_string(index=False))


def test_prophet_la():
    """Prophet on LA hourly data — m=24, horizon=48 hours."""
    conn = sqlite3.connect("data/aqi.db")

    la = load_city(conn, "Los Angeles")
    la_hourly = la["value"].resample("h").mean().dropna()
    conn.close()

    model = prophet_model

    forecast = model.fit_and_forecast(la_hourly, horizon=48, freq="h", m=24,
                                      seasonality_mode="multiplicative", 
                                      changepoint_prior_scale=0.1, add_holidays=False)

    assert len(forecast) == 48
    assert all(col in forecast.columns for col in ["ds", "yhat", "lower_ci", "upper_ci"])
    assert forecast["yhat"].isna().sum() == 0

    print("\nLA Prophet forecast:")
    print(forecast.head(10).to_string(index=False))

def test_chronos_chicago():
    """Chronos on Chicago daily data - m=7, horizon=14 days."""
    conn = sqlite3.connect("data/aqi.db")
    
    chicago = load_city(conn, "Chicago")
    chicago_daily = chicago["value"].resample("D").mean().dropna()
    conn.close()

    model = chronos_model

    forecast = model.fit_and_forecast(chicago_daily, horizon=14, freq="D")

    # check shape
    assert len(forecast) == 14, f"expected 14 rows, got {len(forecast)}"

    # check columns
    assert all(col in forecast.columns for col in ["ds", "yhat", "lower_ci", "upper_ci"])

    # check no nulls in forecast
    assert forecast["yhat"].isna().sum() == 0

    print("\nChicago Chronos forecast:")
    print(forecast.to_string(index=False))

def test_chronos_la():
    """Chronos on LA hourly data — m=24, horizon=48 hours."""
    conn = sqlite3.connect("data/aqi.db")

    la = load_city(conn, "Los Angeles")
    la_hourly = la["value"].resample("h").mean().dropna()
    conn.close()

    model =chronos_model

    forecast = model.fit_and_forecast(la_hourly, horizon=48, freq="h")

    assert len(forecast) == 48
    assert all(col in forecast.columns for col in ["ds", "yhat", "lower_ci", "upper_ci"])
    assert forecast["yhat"].isna().sum() == 0

    print("\nLA Chronos forecast:")
    print(forecast.head(10).to_string(index=False))


if __name__ == "__main__":
    print("testing Chicago...")
    test_sarima_chicago()

    print("\ntesting LA...")
    test_sarima_la()

    print("\nall SARIMA tests passed.")

    print("testing Chicago...")
    test_prophet_chicago()

    print("\ntesting LA...")
    test_prophet_la()

    print("testing Chicago...")
    test_chronos_chicago()

    print("\ntesting LA...")
    test_chronos_la()

    print("\nall Prophet tests passed.")
    
