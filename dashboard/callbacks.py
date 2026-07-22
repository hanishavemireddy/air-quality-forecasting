"""
Dashboard callbacks — handles all interactivity.
Each callback reads component inputs and updates component outputs.
"""
import sys
sys.path.append(".")

import sqlite3
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State
from models import sarima_model, prophet_model, chronos_model
from models.anomaly import detect_anomalies
from models.evaluator import evaluate_model
from pipeline.database import DB_PATH


def register_callbacks(app):

    # ── callback 1: update slider marks based on city ────────────────
    @app.callback(
        Output("horizon-slider", "marks"),
        Output("horizon-slider", "value"),
        Input("city-dropdown",   "value"),
    )
    def update_slider(city):
        if city == "Chicago":
            marks   = {7: "7d", 14: "14d", 30: "30d"}
            default = 14
        else:
            marks   = {24: "24h", 48: "48h", 72: "72h"}
            default = 48
        return marks, default


    # ── callback 2: run forecast on button click ──────────────────────
    @app.callback(
        Output("forecast-chart",   "figure"),
        Output("metric-rmse",      "children"),
        Output("metric-mae",       "children"),
        Output("metric-mape",      "children"),
        Output("metric-anomalies", "children"),
        Input("run-button",        "n_clicks"),
        State("city-dropdown",     "value"),
        State("model-checklist",   "value"),
        State("horizon-slider",    "value"),
        prevent_initial_call=True,
    )
    def update_forecast(n_clicks, city, selected_models, horizon):

        # step 1 — load data from database
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(f"""
            SELECT timestamp, value
            FROM cleaned_readings
            WHERE city = '{city}'
            ORDER BY timestamp
        """, conn, parse_dates=["timestamp"], index_col="timestamp")
        conn.close()

        # step 2 — prepare series based on city frequency
        if city == "Chicago":
            series = df["value"].resample("D").mean().dropna()
            freq, m = "D", 7
        else:
            series = df["value"].resample("h").mean().dropna()
            freq, m = "h", 24

        # step 3 — train/test split
        # use last 30 days of training data for all cities
        # keeps SARIMA fast on hourly data
        if city == "Chicago":
            train = series[:-horizon]
        else:
            train = series[-30*24-horizon:-horizon]

        test = series[-horizon:]

        # step 4 — fit selected models
        forecasts = {}

        if "sarima" in selected_models:
            forecast, _ = sarima_model.fit_and_forecast(
                train, horizon=horizon, freq=freq, m=m
            )
            forecasts["SARIMA"] = forecast

        if "prophet" in selected_models:
            seasonality_mode = "additive" if city == "Chicago" else "multiplicative"
            forecast = prophet_model.fit_and_forecast(
                train, horizon=horizon, freq=freq, m=m,
                seasonality_mode=seasonality_mode,
                add_holidays=(city == "Chicago")
            )
            forecasts["Prophet"] = forecast

        if "chronos" in selected_models:
            forecast = chronos_model.fit_and_forecast(
                train, horizon=horizon, freq=freq
            )
            forecasts["Chronos"] = forecast

        # step 5 — detect anomalies on full series
        anomalies      = detect_anomalies(series, period=m)
        anomaly_points = anomalies[anomalies["is_anomaly"] == True]

        # step 6 — build figure
        fig = go.Figure()

        # historical line — 30 periods before test window starts
        fig.add_trace(go.Scatter(
            x=train[-30:].index,
            y=train[-30:].values,
            mode="lines",
            name="Historical",
            line=dict(color="#aaaaaa", width=1)
        ))

        # actual test values — dotted line + markers
        fig.add_trace(go.Scatter(
            x=test.index,
            y=test.values,
            mode="lines+markers",
            name="Actual (test)",
            line=dict(color="black", width=1.5, dash="dot"),
            marker=dict(color="black", size=5)
        ))

        # anomaly markers — only within visible window
        context_start = train.index[-30]
        visible_anomalies = anomaly_points[
            anomaly_points["timestamp"] >= pd.to_datetime(context_start)
        ]
        if not visible_anomalies.empty:
            fig.add_trace(go.Scatter(
                x=visible_anomalies["timestamp"],
                y=visible_anomalies["value"],
                mode="markers",
                name="Anomaly",
                marker=dict(color="red", size=8, symbol="x")
            ))

        # model colors
        ci_colors = {
            "SARIMA":  "rgba(0, 0, 255, 0.08)",
            "Prophet": "rgba(0, 150, 0, 0.08)",
            "Chronos": "rgba(200, 0, 0, 0.08)",
        }
        line_colors = {
            "SARIMA":  "#0000ff",
            "Prophet": "#009600",
            "Chronos": "#cc0000",
        }

        for model_name, forecast_df in forecasts.items():
            forecast_df["ds"] = pd.to_datetime(forecast_df["ds"])

            # ensure comparison is datetime
            last_train_date = pd.to_datetime(train.index[-1])

            # only show CI for future dates — not historical
            future_mask     = forecast_df["ds"] > last_train_date
            forecast_future = forecast_df[future_mask]

            # CI band — future only
            if not forecast_future.empty:
                fig.add_trace(go.Scatter(
                    x=pd.concat([
                        forecast_future["ds"],
                        forecast_future["ds"][::-1]
                    ]),
                    y=pd.concat([
                        forecast_future["upper_ci"],
                        forecast_future["lower_ci"][::-1]
                    ]),
                    fill="toself",
                    fillcolor=ci_colors[model_name],
                    line=dict(color="rgba(255,255,255,0)"),
                    showlegend=False,
                    hoverinfo="skip",
                ))

            # forecast line + dots — future only
            fig.add_trace(go.Scatter(
                x=forecast_future["ds"],
                y=forecast_future["yhat"],
                mode="lines+markers",
                name=f"{model_name}",
                line=dict(color=line_colors[model_name], width=2),
                marker=dict(size=4)
            ))

        # x-axis range
        x_end = (
            list(forecasts.values())[-1]["ds"].iloc[-1]
            if forecasts
            else test.index[-1]
        )

        # tick format
        tick_format = "%b %d" if city == "Chicago" else "%b %d %H:%M"

        # clean minimal layout
        fig.update_layout(
            title=dict(
                text=f"{city} — PM2.5 Forecast",
                x=0.5,
                font=dict(size=14)
            ),
            xaxis=dict(
                range=[context_start, x_end],
                showgrid=False,
                showline=True,
                linecolor="#cccccc",
                tickformat=tick_format,
                tickangle=-45,
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#f5f5f5",
                showline=False,
                zeroline=False,
                title="PM2.5 (µg/m³)",
            ),
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5,
                font=dict(size=11)
            ),
            margin=dict(l=50, r=20, t=50, b=80),
            hovermode="x unified",
        )

        # step 7 — metrics on first selected model
        if forecasts:
            first_forecast = list(forecasts.values())[0]
            first_future = first_forecast[
                first_forecast["ds"] > pd.to_datetime(train.index[-1])
            ]
            min_len  = min(len(test), len(first_future))
            metrics  = evaluate_model(
                test.values[:min_len],
                first_future["yhat"].values[:min_len]
            )
            rmse        = f"{metrics['RMSE']:.2f}"
            mae         = f"{metrics['MAE']:.2f}"
            mape        = f"{metrics['MAPE']:.1f}%"
            n_anomalies = str(len(visible_anomalies))
        else:
            rmse = mae = mape = n_anomalies = "--"

        return fig, rmse, mae, mape, n_anomalies