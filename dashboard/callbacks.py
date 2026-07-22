"""
Dashboard callbacks — handles all interactivity.
Each callback reads component inputs and updates component outputs.
"""
import sys
sys.path.append(".")

import sqlite3
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, html
from models import sarima_model, prophet_model, chronos_model
from models.anomaly import detect_anomalies
from models.evaluator import evaluate_model
from pipeline.database import DB_PATH
import dash_bootstrap_components as dbc

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

        # show last 30 days of context regardless of frequency
        if city == "Chicago":
            context_periods = 30        # 30 days
        else:
            context_periods = 30 * 24   # 30 days worth of hours

        # historical line — 30 periods before test window starts
        fig.add_trace(go.Scatter(
            x=train[-context_periods:].index,
            y=train[-context_periods:].values,
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
        context_start = train.index[-context_periods]
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
    
    
    # ── callback 3: data explorer ─────────────────────────────────────
    @app.callback(
        Output("explorer-chart",      "figure"),
        Output("explorer-total-rows", "children"),
        Output("explorer-imputed",    "children"),
        Output("explorer-flagged",    "children"),
        Output("explorer-date-range", "children"),
        Input("main-tabs",        "value"),
        Input("city-dropdown",    "value"),
        Input("explorer-toggles", "value"),
    )
    def update_explorer(active_tab, city, toggles):
        # Only for debugging
        #print(f"explorer called: active_tab={active_tab}, city={city}")

        # only run when Data Explorer tab is active
        if active_tab != "tab-explorer":
            return {}, "--", "--", "--", "--"

        # load raw and cleaned data
        conn = sqlite3.connect(DB_PATH)

        raw = pd.read_sql(f"""
            SELECT timestamp, value
            FROM raw_readings
            WHERE city = '{city}'
            ORDER BY timestamp
        """, conn, parse_dates=["timestamp"])

        cleaned = pd.read_sql(f"""
            SELECT timestamp, value, is_imputed, is_outlier_flag
            FROM cleaned_readings
            WHERE city = '{city}'
            ORDER BY timestamp
        """, conn, parse_dates=["timestamp"])

        conn.close()

        # data quality summary
        total_rows   = len(cleaned)
        pct_imputed  = f"{cleaned['is_imputed'].mean()*100:.1f}%"
        pct_flagged  = f"{cleaned['is_outlier_flag'].mean()*100:.1f}%"
        date_range   = (f"{cleaned['timestamp'].min().strftime('%b %d')} "
                        f"to {cleaned['timestamp'].max().strftime('%b %d, %Y')}")

        # build figure
        fig = go.Figure()

        # cleaned series as base line
        fig.add_trace(go.Scatter(
            x=cleaned["timestamp"],
            y=cleaned["value"],
            mode="lines",
            name="Cleaned",
            line=dict(color="#aaaaaa", width=1)
        ))

        # imputed points
        if "imputed" in (toggles or []):
            imputed = cleaned[cleaned["is_imputed"] == True]
            if not imputed.empty:
                fig.add_trace(go.Scatter(
                    x=imputed["timestamp"],
                    y=imputed["value"],
                    mode="markers",
                    name="Imputed",
                    marker=dict(color="orange", size=5, symbol="circle"),
                ))

        # flagged outliers
        if "flagged" in (toggles or []):
            flagged = cleaned[cleaned["is_outlier_flag"] == True]
            if not flagged.empty:
                fig.add_trace(go.Scatter(
                    x=flagged["timestamp"],
                    y=flagged["value"],
                    mode="markers",
                    name="Outlier flagged",
                    marker=dict(color="red", size=6, symbol="x"),
                ))

        fig.update_layout(
            title=dict(
                text=f"{city} — Raw vs Cleaned Data",
                x=0.5,
                font=dict(size=14)
            ),
            xaxis=dict(
                showgrid=False,
                showline=True,
                linecolor="#cccccc",
                tickformat="%b %d" if city == "Chicago" else "%b %d %H:%M",
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

        return fig, str(total_rows), pct_imputed, pct_flagged, date_range
    

    # ── callback 4: pipeline log ──────────────────────────────────────
    @app.callback(
        Output("pipeline-log-table", "children"),
        Output("log-last-run",       "children"),
        Output("log-rows-fetched",   "children"),
        Output("log-rows-stored",    "children"),
        Output("log-errors",         "children"),
        Input("main-tabs", "value"),
    )
    def update_pipeline_log(active_tab):

        print(f"pipeline log called: active_tab={active_tab}")
        if active_tab != "tab-pipeline":
            return None, "--", "--", "--", "--"

        # load pipeline log from database
        conn = sqlite3.connect(DB_PATH)
        log_df = pd.read_sql("""
            SELECT run_at, city, rows_fetched, rows_rejected,
                   rows_stored, error_msg
            FROM pipeline_log
            ORDER BY run_at DESC
            LIMIT 50
        """, conn)
        conn.close()

        if log_df.empty:
            return html.P("No pipeline runs found.", className="text-muted"), "--", "--", "--", "--"

        # summary cards — most recent run
        latest      = log_df.iloc[0]
        last_run    = latest["run_at"][:16]   # trim seconds
        rows_fetched = str(log_df["rows_fetched"].sum())
        rows_stored  = str(log_df["rows_stored"].sum())
        error_count  = str(log_df["error_msg"].notna().sum())

        # build table
        table = dbc.Table([
            html.Thead(html.Tr([
                html.Th("Run at"),
                html.Th("City"),
                html.Th("Fetched"),
                html.Th("Rejected"),
                html.Th("Stored"),
                html.Th("Status"),
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(row["run_at"][:16]),
                    html.Td(row["city"]),
                    html.Td(row["rows_fetched"]),
                    html.Td(row["rows_rejected"]),
                    html.Td(row["rows_stored"]),
                    html.Td(
                        html.Span("Error", className="badge bg-danger")
                        if pd.notna(row["error_msg"])
                        else html.Span("OK", className="badge bg-success")
                    ),
                ])
                for _, row in log_df.iterrows()
            ])
        ], striped=True, hover=True, size="sm", className="mt-2")

        return table, last_run, rows_fetched, rows_stored, error_count
    

    # ── callback 5: model comparison from MLflow ──────────────────────
    @app.callback(
        Output("comparison-table", "children"),
        Output("comparison-chart", "figure"),
        Input("main-tabs",    "value"),
        Input("city-dropdown", "value"),
    )
    def update_comparison(active_tab, city):

        if active_tab != "tab-comparison":
            return None, {}

        import mlflow
        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        client = mlflow.tracking.MlflowClient()
        exp    = client.get_experiment_by_name("aqi-forecasting")

        if exp is None:
            if exp is None:
            # MLflow runs locally — show static metrics from notebook results
            static_data = {
                "Chicago": [
                    {"Model": "SARIMA",  "RMSE": 5.90, "MAE": 3.70, "MAPE": 0.255, "MASE": 0.628},
                    {"Model": "Prophet", "RMSE": 5.99, "MAE": 3.89, "MAPE": 0.281, "MASE": 0.660},
                    {"Model": "Chronos", "RMSE": 8.02, "MAE": 6.18, "MAPE": 0.441, "MASE": 1.049},
                ],
                "Los Angeles": [
                    {"Model": "SARIMA",  "RMSE": 3.87, "MAE": 3.03, "MAPE": 0.212, "MASE": 2.945},
                    {"Model": "Prophet", "RMSE": 3.75, "MAE": 3.07, "MAPE": 0.162, "MASE": 2.985},
                    {"Model": "Chronos", "RMSE": 3.39, "MAE": 2.50, "MAPE": 0.165, "MASE": 2.429},
                ],
                "San Jose": [
                    {"Model": "SARIMA",  "RMSE": 2.83, "MAE": 2.23, "MAPE": 0.166, "MASE": 6.345},
                    {"Model": "Prophet", "RMSE": 4.82, "MAE": 4.57, "MAPE": 0.353, "MASE": 13.007},
                    {"Model": "Chronos", "RMSE": 2.82, "MAE": 2.43, "MAPE": 0.186, "MASE": 6.934},
                ],
            }
            metrics_df = pd.DataFrame(static_data.get(city, static_data["Chicago"]))
            note = html.P(
                "MLflow runs locally. Showing metrics from notebook evaluation.",
                className="text-muted mb-2",
                style={"fontSize": "12px"}
            )
        else:
            runs = client.search_runs(
                exp.experiment_id,
                filter_string=f"params.city = '{city}'",
                order_by=["start_time DESC"],
            )

            if not runs:
                return html.P(f"No runs found for {city}.", className="text-muted"), {}

            # get latest run per model
            latest = {}
            for run in runs:
                model = run.data.params.get("model")
                if model and model not in latest:
                    latest[model] = run

            # build metrics DataFrame
            rows = []
            for model, run in latest.items():
                rows.append({
                    "Model":    model,
                    "RMSE":     round(run.data.metrics.get("rmse", 0), 3),
                    "MAE":      round(run.data.metrics.get("mae", 0), 3),
                    "MAPE":     round(run.data.metrics.get("mape", 0), 3),
                    "MASE":     round(run.data.metrics.get("mase", 0), 3),
                })

            metrics_df = pd.DataFrame(rows)
            note = html.Div()  # no note when MLflow is available

        # highlight winner per metric
        def make_row(row):
            cells = [html.Td(row["Model"])]
            for metric in ["RMSE", "MAE", "MAPE", "MASE"]:
                best = metrics_df[metric].min()
                style = {"backgroundColor": "#d4edda", "fontWeight": "bold"} if row[metric] == best else {}
                cells.append(html.Td(str(row[metric]), style=style))
            return html.Tr(cells)

        table = dbc.Table([
            html.Thead(html.Tr([
                html.Th("Model"), html.Th("RMSE"), html.Th("MAE"),
                html.Th("MAPE"), html.Th("MASE")
            ])),
            html.Tbody([make_row(row) for _, row in metrics_df.iterrows()])
        ], striped=True, hover=True, size="sm", className="mb-3")

        # bar chart — RMSE comparison
        fig = go.Figure()
        for _, row in metrics_df.iterrows():
            fig.add_trace(go.Bar(
                name=row["Model"],
                x=["RMSE", "MAE", "MAPE", "MASE"],
                y=[row["RMSE"], row["MAE"], row["MAPE"], row["MASE"]],
            ))

        fig.update_layout(
            title=dict(text=f"{city} — Model Metrics Comparison", x=0.5),
            barmode="group",
            plot_bgcolor="white",
            paper_bgcolor="white",
            yaxis=dict(showgrid=True, gridcolor="#f5f5f5"),
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
            margin=dict(l=40, r=20, t=50, b=80),
        )

        return html.Div([note, table]), fig
