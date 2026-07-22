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

# seed the database on first run if it doesn't exist or is empty
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000:
    print("database not found — running backfill...")
    create_tables()
    run_pipeline(past_days=90)
    print("backfill complete")

print("Getting the Data")

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