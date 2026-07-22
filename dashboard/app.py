"""
Main entry point for the Plotly Dash dashboard.
Run with: python -m dashboard.app
Then open http://localhost:8050
"""

import os
import sys
sys.path.append(".")

import dash
import dash_bootstrap_components as dbc

print("app.py starting...")

# initialise the app with a clean Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="AQI Forecasting Dashboard"
)

print("app initialized")

# import layout and callbacks after app is created
from dashboard.layout import layout
from dashboard.callbacks import register_callbacks

print("importing done")

app.layout = layout

print("app layout read")

register_callbacks(app)

print("app callbacks received")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8050)),
        debug=False
    )