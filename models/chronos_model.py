"""
- This module contains the implementation of the Chronos model for time series forecasting.
- In Chronos, there is no learning step. 
- Based on recent history (our series) as contextm it predicts what comes next based on everything 
it already learned during pre-training on millions of other series.
"""

import torch
import pandas as pd
import numpy as np
import logging
from chronos import ChronosPipeline

log = logging.getLogger(__name__)

# load once when the module is imported — takes 15-30s on first run
# subsequent calls to fit_and_forecast() will reuse this pipeline
pipeline = ChronosPipeline.from_pretrained(
    "amazon/chronos-t5-small",
    device_map="cpu",        # we're running on CPU, not GPU
    dtype=torch.float32
)

log.info("Chronos pipeline loaded")

def fit_and_forecast(series, horizon, freq) -> pd.DataFrame:
    """
    Fit a Chronos model to the provided time series and forecast future values.
    Handles both daily and hourly data, as well as different seasonalities.


    Parameters:
    series (pd.Series): The time series data to fit the model on.
    horizon (int): The number of future periods to forecast.
    freq (str): The frequency of the time series data (e.g., 'D' for daily, 'M' for monthly, 'h' for hourly).

    - use freq='D' for Chicago and freq='h' for LA and SJ

    Returns:
    pd.DataFrame: A DataFrame containing the forecasted values and their confidence intervals.
    """

    # convert series to a PyTorch tensor — Chronos expects a batch of series as context, so we add a batch dimension
    # unsqueeze(0) adds a batch dimension: shape goes from [n] to [1, n]
    context = torch.tensor(series.values, dtype=torch.float32).unsqueeze(0)

    # generate forecast samples
    # num_samples = number of possible futures Chronos generates internally
    # more samples = more stable quantile estimates but slower
    # mean is based on the 20 samples, but we don't use it here — we use the quantiles instead
    quantiles, mean = pipeline.predict_quantiles(
        inputs=context,
        prediction_length=horizon,
        quantile_levels=[0.1, 0.5, 0.9],  # lower_ci, median, upper_ci
        num_samples=20
    ) 
    # note: in Python, use _ instead of a variable name when you don't need the value
    # e.g. quantiles, _ = pipeline.predict_quantiles(...) — signals intent clearly
    # keeping 'mean' here for reference/debugging purposes

    # build future date index starting from the day/hour after the last observation
    horizon_times = pd.date_range(
        start=series.index[-1] + pd.tseries.frequencies.to_offset(freq),
        periods=horizon,
        freq=freq
    )

    # extract quantiles — shape is [1, horizon, 3] so we index [0] to get [horizon, 3]
    low  = quantiles[0, :, 0].numpy()  # 10th percentile → lower_ci
    mid  = quantiles[0, :, 1].numpy()  # 50th percentile → yhat
    high = quantiles[0, :, 2].numpy()  # 90th percentile → upper_ci
    #  the 0 at the start selects the first (only) series in the batch, 
    # : selects all horizon steps, and 0/1/2 selects the quantile level


    forecast_df = pd.DataFrame({
        "ds":      horizon_times,
        "yhat":     mid,
        "lower_ci": low,
        "upper_ci": high,
    })

    log.info(f"Chronos forecast generated — horizon={horizon}, freq={freq}")

    return forecast_df

def log_run(city, freq, horizon, forecast_df, y_test):
    """Log a Chronos experiment run to MLflow."""
    import mlflow
    from models.evaluator import evaluate_model

    with mlflow.start_run(run_name=f"chronos_{city}"):
        mlflow.log_param("model",   "Chronos")
        mlflow.log_param("city",    city)
        mlflow.log_param("freq",    freq)
        mlflow.log_param("horizon", horizon)

        metrics = evaluate_model(y_test, forecast_df["yhat"].values)
        mlflow.log_metric("rmse", metrics["RMSE"])
        mlflow.log_metric("mae",  metrics["MAE"])
        mlflow.log_metric("mape", metrics["MAPE"])
        mlflow.log_metric("mase", metrics["MASE"])

        log.info(f"MLflow run logged — Chronos {city}")
        # mlflow.sklearn.log_model()

