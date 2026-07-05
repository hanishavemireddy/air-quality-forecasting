"""
This module contains different functions that help in detecting and scoring anomalies in the time series data.
"""

import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import STL
import logging

log = logging.getLogger(__name__)

def detect_raw_outliers(series, iqr_factor=3.0, window=None) -> pd.Series:
    """
    Detect raw outliers in a time series using the IQR method.
    
    Parameters:
    series (pd.Series): The time series data to analyze.
    iqr_factor (float): The factor to multiply the IQR by to determine outlier thresholds. Default is 3.0.
    window (int): The size of the rolling window for calculating the IQR. If None, the entire series is used. Default is None.
    Returns:
    pd.Series: A boolean series indicating whether each point is an outlier (True) or not (False).
    """
    if window:
        # rolling IQR
        q1 = series.rolling(window, center=True, min_periods=14).quantile(0.25)
        q3 = series.rolling(window, center=True, min_periods=14).quantile(0.75)
    else:
        # global IQR
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)

    iqr = q3 - q1
    lower_bound = q1 - iqr_factor * iqr
    upper_bound = q3 + iqr_factor * iqr
    
    return (series < lower_bound) | (series > upper_bound)

def detect_residual_anomalies(series, period, iqr_factor=3.0, window=None) -> pd.Series:
    """
    Detect anomalies in the residuals of a time series using STL decomposition and the IQR method.
    
    Parameters:
    series (pd.Series): The time series data to analyze.
    period (int): The seasonal period of the time series (e.g., 24 for hourly data with daily seasonality).
    iqr_factor (float): The factor to multiply the IQR by to determine outlier thresholds. Default is 3.0.
    
    Returns:
    pd.Series: A boolean series indicating whether each point is an anomaly (True) or not (False).
    """
    # Perform STL decomposition
    stl = STL(series.dropna(), period=period, robust=True)
    result = stl.fit()
    
    # Get the residuals
    residuals = result.resid
    
    # Detect anomalies in the residuals using the IQR method
    anomalies = detect_raw_outliers(residuals, iqr_factor=iqr_factor, window=window)
    
    return anomalies


def anomaly_score(series, window=None) -> pd.DataFrame:
    """
    Calculates the anomaly score for each of the points in the series

    Parameters:
    series (pd.Series): The time series data to analyze
    window (int): The size of the rolling window for calculating the IQR. If None, the entire series is used. Default is None.

    Returns:
    pd.DataFrame that outputs the series Standard Z-value, Modified Z-value
    """

    if window:
        # rolling window summaries
        median = series.rolling(window, center=True, min_periods=14).quantile(0.5)
        mad = (series - median).abs().rolling(window, center=True, min_periods=14).median()

        mean = series.rolling(window, center=True, min_periods=14).mean()
        std = series.rolling(window, center=True, min_periods=14).std()
    else:
        median = series.quantile(0.5)
        mad = (series - median).abs().median()

        mean = series.mean()
        std = series.std()

    z = (series - mean) / std

    mz = 0.6745 * (series - median) / mad

    return pd.DataFrame({"z_score": z,
                         "modified_z_score": mz})


def detect_anomalies(series, period, iqr_factor=3.0, window = None) -> pd.DataFrame:
    """
    Detects outliers/ anomalies and scores them for the series

    Parameters:
    series (pd.Series): The time series data to analyze
    window (int): The size of the rolling window for calculating the IQR. If None, the entire series is used. Default is None.
    period (int): The seasonal period of the time series (e.g., 24 for hourly data with daily seasonality).
    iqr_factor (float): The factor to multiply the IQR by to determine outlier thresholds. Default is 3.0.
    
    Returns:
    pd.DataFrame that outputs the series Standard Z-value, Modified Z-value
    """

    raw_outlier = detect_raw_outliers(series, iqr_factor=iqr_factor, window=window)
    res_anomaly = detect_residual_anomalies(series, period, iqr_factor, window=window)

    anomaly_scores = anomaly_score(series, window=14)

    return pd.DataFrame({"timestamp": series.index,
                         "value": series.values,
                        "is_raw_outlier": raw_outlier,
                        "is_res_anomaly": res_anomaly,
                        "is_anomaly": raw_outlier|res_anomaly,
                        "anomaly_score_standard": anomaly_scores['z_score'],
                        "anomaly_score_modified": anomaly_scores['modified_z_score']})