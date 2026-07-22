"""
Dashboard layout — defines the UI structure.
All interactivity is handled in callbacks.py.
"""

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

# ── navbar ────────────────────────────────────────────────────────────────────

navbar = dbc.NavbarSimple(
    brand="AQI Forecasting Dashboard",
    brand_href="#",
    color="primary",
    dark=True,
    className="mb-2",
)

# ── controls ──────────────────────────────────────────────────────────────────

city_dropdown = dcc.Dropdown(
    id="city-dropdown",
    options=[
        {"label": "Chicago",      "value": "Chicago"},
        {"label": "Los Angeles",  "value": "Los Angeles"},
        {"label": "San Jose",     "value": "San Jose"},
    ],
    value="Chicago",
    clearable=False,
)

model_checklist = dcc.Checklist(
    id="model-checklist",
    options=[
        {"label": " SARIMA",  "value": "sarima"},
        {"label": " Prophet", "value": "prophet"},
        {"label": " Chronos", "value": "chronos"},
    ],
    value=["sarima"],
    labelStyle={"display": "block", "margin": "4px 0"},
)

horizon_slider = dcc.Slider(
    id="horizon-slider",
    min=7,
    max=72,
    step=None,
    marks={
        7:  "7d",
        14: "14d",
        30: "30d",
        48: "48h",
        72: "72h",
    },
    value=14,
)

run_button = dbc.Button(
    "Run Forecast",
    id="run-button",
    color="primary",
    className="mt-3 w-100",
)



# ── metric cards ──────────────────────────────────────────────────────────────

metric_cards = dbc.Row([
    dbc.Col(dbc.Card([
        dbc.CardBody([
            html.P("RMSE", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H5(id="metric-rmse", children="--", className="mb-0"),
        ])
    ], className="text-center shadow-sm"), width=3),

    dbc.Col(dbc.Card([
        dbc.CardBody([
            html.P("MAE", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H5(id="metric-mae", children="--", className="mb-0"),
        ])
    ], className="text-center shadow-sm"), width=3),

    dbc.Col(dbc.Card([
        dbc.CardBody([
            html.P("MAPE", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H5(id="metric-mape", children="--", className="mb-0"),
        ])
    ], className="text-center shadow-sm"), width=3),

    dbc.Col(dbc.Card([
        dbc.CardBody([
            html.P("Anomalies", className="text-muted mb-1", style={"fontSize": "12px"}),
            html.H5(id="metric-anomalies", children="--", className="mb-0"),
        ])
    ], className="text-center shadow-sm"), width=3),
], className="mb-3")

# ── forecast chart ────────────────────────────────────────────────────────────

forecast_chart = dcc.Loading(
    id="loading-forecast",
    type="circle",        # spinner style — circle, dot, or cube
    children=dcc.Graph(
        id="forecast-chart",
        style={"height": "420px"},
        figure={},
        config={"displayModeBar": False},
    )
)

# ── full layout ───────────────────────────────────────────────────────────────

layout = dbc.Container([

    navbar,

    dbc.Row([

        # left sidebar — controls
        dbc.Col([
            html.Div([
                html.H6("City", className="mt-3 mb-1 text-muted"),
                city_dropdown,

                html.H6("Models", className="mt-3 mb-1 text-muted"),
                model_checklist,

                html.H6("Horizon", className="mt-3 mb-1 text-muted"),
                horizon_slider,

                run_button,
            ], style={
                "backgroundColor": "#f8f9fa",
                "padding": "16px",
                "borderRadius": "8px",
                "marginTop": "16px",
            })
        ], width=3),

        # right side — metrics + chart
        dbc.Col([
            html.Div(className="mt-3"),   # spacing
            metric_cards,
            forecast_chart,
        ], width=9),

    ]),

], fluid=True)