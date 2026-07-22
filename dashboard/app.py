"""
Main entry point for the Plotly Dash dashboard.
Run with: python -m dashboard.app
Then open http://localhost:8050
"""

import os
import sys
sys.path.append(".")

from pipeline.database import create_tables, DB_PATH
from pipeline.run_pipeline import run_pipeline

# seed the database on first run if it doesn't exist or is empty
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000:
    print("database not found — running backfill...")
    create_tables()
    run_pipeline(past_days=90)
    print("backfill complete")

import dash
import dash_bootstrap_components as dbc

print("app.py starting...")

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="AQI Forecasting Dashboard"
)

server = app.server  # needed for gunicorn

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