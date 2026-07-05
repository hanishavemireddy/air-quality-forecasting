"""
This module contains the function to fit a SARIMA model to a time series and forecast future values.
We use the pmdarima library to automatically select the best SARIMA model parameters based on the provided time series data.
"""


import pandas as pd
from pmdarima import auto_arima
import logging

log = logging.getLogger(__name__)

def fit_and_forecast(series, horizon, freq, m) -> pd.DataFrame:
    """
    Fit a SARIMA model to the provided time series and forecast future values.
    Handles both daily and hourly data, as well as different seasonalities.

    Parameters:
    series (pd.Series): The time series data to fit the model on.
    horizon (int): The number of future periods to forecast.
    freq (str): The frequency of the time series data (e.g., 'D' for daily, 'M' for monthly, 'h' for hourly).
    m (int): The number of periods in each season (e.g., 12 for monthly data with yearly seasonality).

    - use freq='D' for Chicago and freq='h' for LA and SJ
    - use m = 7 (weekly seasonality) for Chicago and m = 24 (daily seasonality) for LA and SJ

    Returns:
    pd.DataFrame: A DataFrame containing the forecasted values and their confidence intervals.
    """

    series = series.asfreq(freq)  # Ensure the series has the correct frequency
    horizon_times = pd.date_range(start=series.index[-1] +
                                  # pd.Timedelta(1, unit=freq), #won't work for hourly data, so we use the following instead
                                  pd.tseries.frequencies.to_offset(freq), # convert freq string to a Timedelta object
                                  periods=horizon, freq=freq)  # Create a date range for the forecast horizon
    # Fit the SARIMA model
    model = auto_arima(series, 
                       seasonal=True, # there is seasonality in the data, so we set seasonal=True
                       start_p=1, max_p=3, # Our models looked like they're AR(1) or AR(2) so we can limit the search space to p=1,2,3
                       start_q=0, max_q=2, # EDA says not required, but just in case, we can limit the search space to q=1,2
                       d=0,  #we know d=0 from EDA
                       D =0, #the series is stationary seasonally, so D=0
                       m=m, stepwise=True,
                       information_criterion='aic', #AIC is a good measure of model fit, lower is better
                       suppress_warnings=True)
    
    log.info(f"SARIMA order selected: {model.order}, seasonal: {model.seasonal_order}")

    # Forecast future values and get confidence intervals
    forecast_df, conf_int = model.predict(n_periods=horizon,return_conf_int=True)

    forecast_df_with_ci = pd.DataFrame({
        'ds': horizon_times,
        'yhat': forecast_df,
        'lower_ci': conf_int[:, 0],
        'upper_ci': conf_int[:, 1]
    }, index=horizon_times)

    return forecast_df_with_ci


