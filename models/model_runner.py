# # model_runner.py

# configs = [
#     {
#         "city":                    "Chicago",
#         "series":                  chicago_train,
#         "horizon":                 14,
#         "freq":                    "D",
#         "m":                       7,
#         "seasonality_mode":        "additive",
#         "changepoint_prior_scale": 0.05,
#         "add_holidays":            True,
#     },
#     {
#         "city":                    "Los Angeles",
#         "series":                  la_train,
#         "horizon":                 48,
#         "freq":                    "h",
#         "m":                       24,
#         "seasonality_mode":        "multiplicative",
#         "changepoint_prior_scale": 0.1,
#         "add_holidays":            False,
#     },
#     {
#         "city":                    "San Jose",
#         "series":                  sj_train,
#         "horizon":                 48,
#         "freq":                    "h",
#         "m":                       24,
#         "seasonality_mode":        "multiplicative",
#         "changepoint_prior_scale": 0.05,
#         "add_holidays":            False,
#     }
# ]

# def run_all_models_parallel(configs, models=None, cities=None) -> dict:
#     """
#     models=None means run all three
#     cities=None means run all cities
#     models=['sarima'] runs only SARIMA for all cities
#     cities=['Chicago'] runs all models for Chicago only

#     configs,e.g., 
#      {
#         "city": "Chicago",
#         "series": chicago_train,
#         "model": sarima_model,
#         "horizon": 14,
#         "freq": "D",
#         "m": 7,
#         ...
#     }
#     Returns a dict of {city: {model_name: forecast_df}}
#     """
    