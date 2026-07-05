"""
This module provides a function to evaluate the performance of regression models using various metrics.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (
  mean_absolute_error, mean_absolute_percentage_error, 
  mean_squared_error, r2_score)


def evaluate_model(y_true, y_pred, lower_CI=None, upper_CI=None) -> dict:
    """
    Evaluate the performance of a regression model.
    Calculates coverage if lower and upper confidence intervals are provided.

    Parameters:
    y_true (array-like): True target values.
    y_pred (array-like): Predicted target values.
    lower_CI (array-like, optional): Lower bounds of the confidence interval.
    upper_CI (array-like, optional): Upper bounds of the confidence interval.

    Returns:
    dict: A dictionary containing evaluation metrics 
    including MSE, RMSE, MAE, MAPE, MASE, R2, and Coverage (if applicable).
    """
    mse = mean_squared_error(y_true, y_pred) # Mean Squared Error
    rmse = np.sqrt(mse) #Root Mean Squared Error
    mae = mean_absolute_error(y_true, y_pred) #Mean Absolute Error
    r2 = r2_score(y_true, y_pred) #R2y

    mask = y_true != 0 # Create a mask for non-zero true values
    #Compute MAPE only for non-zero true values to avoid division by zero
    # np.array(y) is used to ensure mask is applied correctly to both y_true and y_pred
    mape = mean_absolute_percentage_error(np.array(y_true)[mask], np.array(y_pred)[mask]) #Mean Absolute Percentage Error
    
    naive_mae = np.mean(np.abs(np.diff(y_true))) # Mean Absolute Error of naive forecast
    mase = mae / (naive_mae + 1e-10)  # Mean Absolute Scaled Error, added small value to avoid division by zero

    if lower_CI is not None and upper_CI is not None:
        coverage = np.mean((y_true >= lower_CI) & (y_true <= upper_CI))*100 # Calculate coverage %
    else:
        coverage = None

    return {
        "MSE": mse,
        "RMSE": rmse,
        "MAE": mae,
        "MAPE": mape,
        "MASE": mase,
        "R2": r2,
        "Coverage": coverage  
    }