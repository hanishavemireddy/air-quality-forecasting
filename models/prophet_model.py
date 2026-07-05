"""
This module contains the implementation of the Prophet model for time series forecasting.
We use the Prophet library to fit a model to the provided time series data and forecast future values.
"""

import pandas as pd
from prophet import Prophet
import logging


log = logging.getLogger(__name__)

def fit_and_forecast(series, horizon, freq, m, seasonality_mode = "additive", changepoint_prior_scale = 0.05, add_holidays=False) -> pd.DataFrame:
    """
    Fit a Prophet model to the provided time series and forecast future values.
    
    Parameters:
    series (pd.Series): The time series data to fit the model on.
    horizon (int): The number of future periods to forecast.
    freq (str): The frequency of the time series data (e.g., 'D' for daily, 'M' for monthly, 'h' for hourly).
    m (int): The number of periods in each season (e.g., 12 for monthly data with yearly seasonality).
    seasonality_mode (str): The seasonality mode for the Prophet model ('additive' or 'multiplicative'). Default is 'additive'.
    change_point_prior_scale (float): The scale for the change point prior. Default is 0.05.
    add_holidays (bool): Whether to add US holidays to the model. Default is False.

    - use freq='D' for Chicago and freq='h' for LA and SJ
    - use m = 7 (weekly seasonality) for Chicago and m = 24 (daily seasonality) for LA and SJ
    - use seasonality_mode='additive' for Chicago and seasonality_mode='multiplicative' for LA and SJ
    - use higher change_point_prior_scale for LA as there is a downward trend in the data, 
    and we'd be able to detect it better
    - we only want to add holidays for Chicago (based on EDA)
    Returns:
    pd.DataFrame: A DataFrame containing the forecasted values and their confidence intervals.
    """

    series = series.asfreq(freq)  # Ensure the series has the correct frequency

    # Prophet requires a DataFrame with columns 'ds' (datestamp) and 'y' (value)
    # So, prepare the DataFrame accordingly
    df = pd.DataFrame({
        'ds': series.index,
        'y': series.values
    })

    if add_holidays:
        # Do this if custom events are to be added. For example, July 4th fireworks can affect AQI readings for a few days before and after the event.
        # More useful when the event is multi-day, like a festival or wildfire
        # For single day, include days not mentioned in US Federal holidays
        custom_events = pd.DataFrame({
            'holiday': 'july4_fireworks',  # 'event_name' describes the event, can be anything
            'ds': pd.to_datetime(['2026-07-04']),
            'lower_window': -1,
            'upper_window': 2,
        })
    else:
        custom_events = None


    # Fit the Prophet model
    model = Prophet(seasonality_mode=seasonality_mode, 
                    yearly_seasonality=False, 
                    weekly_seasonality= (m == 7), 
                    daily_seasonality= (m == 24),
                    interval_width=0.95, #default is 0.8, but we want 95% confidence intervals
                    changepoint_prior_scale=changepoint_prior_scale, #default is 0.05, higher values make the trend more flexible, lower values make it more rigid
                    holidays= custom_events 
                    )
    if add_holidays:
        model.add_country_holidays(country_name='US')
    
    #for LA, we probably want a higher change_point_prior_scale
    model.fit(df) 

    #Making sure the model ran correctly by checking if the model has been fitted and has the necessary attributes
    log.info(f"Prophet fitted — seasonality_mode={seasonality_mode}, changepoint_prior_scale={changepoint_prior_scale}")


    # Forecast future values and get confidence intervals
    future = model.make_future_dataframe(periods=horizon, freq=freq)
    forecast = model.predict(future) # prophet model does not have return_conf_int parameter

    forecast_tail = forecast.tail(horizon) #

    forecast_df_with_ci = pd.DataFrame({
        'ds': forecast_tail['ds'].values,
        'yhat': forecast_tail['yhat'].values,
        'lower_ci': forecast_tail['yhat_lower'].values,
        'upper_ci': forecast_tail['yhat_upper'].values
    })

    return forecast_df_with_ci


