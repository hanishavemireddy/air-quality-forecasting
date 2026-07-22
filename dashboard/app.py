"""
Main entry point for the Plotly Dash dashboard.
Run with: python dashboard/app.py
Then open http://localhost:8050
"""
print("app.py starting...")

import os
import dash
import dash_bootstrap_components as dbc

# initialise the app with a clean Bootstrap theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="AQI Forecasting Dashboard"
)

# import layout and callbacks after app is created
from dashboard.layout import layout
from dashboard.callbacks import register_callbacks

app.layout = layout

register_callbacks(app)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8050)),
        debug=False
    )