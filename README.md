# AQI Time Series Forecasting Dashboard

A full-stack data science project that scrapes live air quality data, runs it through a cleaning pipeline, stores it in a database, and serves forecasts from three models through an interactive dashboard.

**Live dashboard:** https://web-production-134ad.up.railway.app

---

## What it does

Every day, a scheduled pipeline pulls hourly PM2.5 readings for Chicago, Los Angeles, and San Jose from the Open-Meteo API. The data gets validated, cleaned, and stored in SQLite. A Plotly Dash dashboard lets you pick a city, choose one or more models, set a forecast horizon, and see the results with confidence intervals, anomaly flags, and evaluation metrics.

---

## Cities

- Chicago, IL
- Los Angeles, CA
- San Jose, CA

---

## Models

All three models share the same interface and were configured based on EDA findings:

| City | Frequency | Seasonal period | Prophet mode |
|---|---|---|---|
| Chicago | Daily | m=7 (weekly) | Additive |
| Los Angeles | Hourly | m=24 (daily) | Multiplicative |
| San Jose | Hourly | m=24 (daily) | Multiplicative |

**SARIMA** uses pmdarima's auto_arima to pick the best order automatically. EDA confirmed d=0 (all series are stationary).

**Prophet** uses city-specific seasonality mode and changepoint flexibility. US holidays and a July 4th event window are added for Chicago.

**Chronos** is Amazon's pre-trained foundation model (chronos-t5-small). Zero-shot, no training on your data required.

**Anomaly detection** combines two methods: rolling IQR on raw values and IQR on STL residuals. A point gets flagged if either method catches it.

---

## Stack

| Layer | Tools |
|---|---|
| Data ingestion | Open-Meteo API, requests, tenacity |
| Data cleaning | Pydantic, pandas |
| Storage | SQLite, SQLAlchemy |
| Models | pmdarima, prophet, chronos-forecasting, torch |
| Experiment tracking | MLflow |
| Orchestration | Prefect |
| Dashboard | Plotly Dash, dash-bootstrap-components |
| Containerization | Docker |
| CI/CD | GitHub Actions |
| Deployment | Railway |

---

## Project structure

```
air-quality-forecasting/
├── pipeline/
│   ├── scraper.py           # Open-Meteo API + retry logic
│   ├── cleaner.py           # validation, outlier flagging, imputation, dedup
│   ├── database.py          # SQLAlchemy table definitions
│   ├── run_pipeline.py      # scrape -> clean -> store
│   └── prefect_flow.py      # Prefect orchestration with daily schedule
├── models/
│   ├── sarima_model.py
│   ├── prophet_model.py
│   ├── chronos_model.py
│   ├── anomaly.py
│   └── evaluator.py         # RMSE, MAE, MAPE, MASE, coverage
├── dashboard/
│   ├── app.py
│   ├── layout.py
│   └── callbacks.py
├── notebooks/
│   ├── 01_eda.ipynb         # 7-section EDA
│   └── 02_models.ipynb      # model comparison and anomaly plots
├── tests/
│   ├── test_cleaner.py
│   └── test_models.py
├── Dockerfile
├── docker-compose.yml
├── Procfile
└── requirements-prod.txt
```

---

## Running locally

```bash
git clone https://github.com/hanishavemireddy/air-quality-forecasting.git
cd air-quality-forecasting

python -m venv venv311
venv311\Scripts\activate

pip install -r requirements-prod.txt

# seed the database
python pipeline/run_pipeline.py --backfill 90

# start the dashboard
python -m dashboard.app
# open http://localhost:8050
```

Other services:

```bash
# MLflow experiment tracking
mlflow ui
# open http://localhost:5000

# Prefect orchestration UI
prefect server start
# open http://localhost:4200
```

---

## What's been built

- [x] Live API scraping with retry logic
- [x] 4-step cleaning pipeline (validation, outlier flagging, imputation, dedup)
- [x] SQLite database with raw, cleaned, and audit log tables
- [x] 90-day historical backfill
- [x] EDA notebook (stationarity, ACF/PACF, STL, distributions, anomalies)
- [x] SARIMA, Prophet, and Chronos with shared interface
- [x] Anomaly detection (raw IQR + STL residuals)
- [x] MLflow experiment tracking for all 9 model/city combinations
- [x] Prefect orchestration with daily 6am schedule
- [x] Docker + docker-compose
- [x] GitHub Actions CI/CD (tests run on every push)
- [x] Plotly Dash dashboard deployed on Railway

## What's next

- [ ] Model comparison tab
- [ ] Data explorer tab
- [ ] Pipeline log tab
- [ ] Postgres instead of SQLite for persistent storage on Railway

---

## A few design decisions worth noting

Raw and cleaned data are stored separately so the cleaning pipeline is re-runnable without losing anything. Flagged outlier rows are kept with an is_outlier_flag column rather than deleted. Every database write is idempotent so running the pipeline twice gives the same result as running it once. Model settings (seasonality mode, seasonal period) were chosen based on EDA findings, not defaults.