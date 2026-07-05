# air-quality-forecasting

# AQI Time Series Forecasting Dashboard

A full-stack data science project that pulls live air quality data from the internet,
cleans it through an automated pipeline, stores it in a database, and serves
forecasts from three models (SARIMA, Prophet, Chronos) through a Plotly Dash dashboard.

> **Status:** Data pipeline complete ✓ | EDA complete ✓ | Forecasting models complete ✓ | Dashboard and MLOps in progress.

---

## Project Description

Every day, a pipeline scrapes hourly PM2.5 air quality readings for three US cities
from the [Open-Meteo Air Quality API](https://open-meteo.com/). The raw data is validated,
cleaned, and stored in a SQLite database — keeping the original and cleaned versions
separate so the pipeline is always re-runnable without losing anything.

Three forecasting models — SARIMA, Prophet, and Chronos — are fitted on the cleaned
data with city-specific configurations informed by EDA. An anomaly detection module
flags unusual readings using both raw IQR and STL residual methods.

The end goal is a Plotly Dash dashboard where you can compare forecasts from all three
models side by side, with anomaly flags, confidence intervals, and model evaluation metrics.

---

## Cities tracked

- San Jose, CA
- Los Angeles, CA
- Chicago, IL

---

## Project structure

```
air-quality-forecasting/
├── pipeline/
│   ├── scraper.py              # pulls hourly PM2.5 from Open-Meteo API
│   ├── cleaner.py              # validates, flags outliers, imputes gaps, deduplicates
│   ├── database.py             # SQLAlchemy table definitions and write helpers
│   └── run_pipeline.py         # orchestrates scrape → clean → store end to end
├── models/
│   ├── sarima_model.py         # SARIMA via pmdarima auto_arima
│   ├── prophet_model.py        # Prophet with city-specific seasonality and holidays
│   ├── chronos_model.py        # Amazon Chronos-small zero-shot foundation model
│   ├── anomaly.py              # STL + IQR anomaly detection
│   └── evaluator.py            # shared evaluation metrics (RMSE, MAE, MAPE, MASE, coverage)
├── dashboard/                  # Plotly Dash app (in progress)
├── tests/
│   ├── test_cleaner.py         # unit tests for the cleaning pipeline
│   └── test_models.py          # tests for all three forecasting models
├── notebooks/
│   └── 01_eda.ipynb            # EDA — stationarity, ACF/PACF, STL, distributions, anomalies
├── requirements.txt
└── .gitignore
```

---

## Data pipeline

The pipeline runs in four steps:

**1. Scrape** — `scraper.py` calls the Open-Meteo API for each city and returns
a tidy DataFrame of hourly PM2.5 readings. Requests use automatic retry logic
(up to 3 attempts with exponential backoff) so transient network failures don't
crash the run.

**2. Validate and clean** — `cleaner.py` runs four steps in order:
- Schema validation with Pydantic — rejects rows with negative values, readings
  over 1000 µg/m³, or unrecognised city names
- Outlier flagging — rolling 30-day IQR (factor 3.0) marks suspicious readings
  `is_outlier_flag=True` without deleting them
- Gap imputation — resamples to hourly, forward-fills up to 2 consecutive gaps,
  then linear interpolation for anything longer; filled rows marked `is_imputed=True`
- Deduplication — drops exact duplicates on (city, timestamp, value)

**3. Store** — raw rows go into `raw_readings` untouched. Cleaned rows go into
`cleaned_readings`. Both writes are idempotent — running the pipeline multiple
times won't create duplicates.

**4. Log** — every run writes one row to `pipeline_log` recording the timestamp,
city, rows fetched, rows rejected, rows stored, and any errors.

---

## Forecasting models

All three models share a consistent interface: `fit_and_forecast(series, horizon, freq, ...)`
returning a DataFrame with `ds`, `yhat`, `lower_ci`, `upper_ci`.
City-specific configurations were informed by EDA findings:

| City | Data frequency | Model seasonal period | Prophet mode |
|---|---|---|---|
| Chicago | Daily | m=7 (weekly) | Additive |
| Los Angeles | Hourly | m=24 (daily) | Multiplicative |
| San Jose | Hourly | m=24 (daily) | Multiplicative |

**SARIMA** — uses `pmdarima`'s `auto_arima` to automatically select the best
(p,d,q)(P,D,Q) order using AIC. EDA confirmed d=0 (stationary series) for all cities.

**Prophet** — decomposition model with city-specific seasonality mode and
changepoint flexibility. US holidays and a custom July 4th fireworks event
added for Chicago based on EDA anomaly findings.

**Chronos** — Amazon's pre-trained foundation model (`chronos-t5-small`).
Zero-shot — no training on your data required. Loaded once at module level
to avoid 30-second reload on every forecast call.

**Anomaly detection** — `anomaly.py` combines two methods: rolling IQR on raw
values and IQR on STL residuals. A point is flagged if either method catches it.
Anomaly scores computed using both standard Z-score and modified Z-score (MAD-based).

---

## Database schema

| Table | Purpose |
|---|---|
| `raw_readings` | Exact API response — never modified after writing |
| `cleaned_readings` | Pipeline output — what the models read from |
| `pipeline_log` | One audit row per run — tracks what happened and when |

---

## How to run locally

**1. Clone the repo**
```bash
git clone https://github.com/hanishavemireddy/air-quality-forecasting.git
cd air-quality-forecasting
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv311
venv311\Scripts\activate        # Windows
source venv311/bin/activate     # Mac/Linux
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Seed the database with 90 days of historical data**
```bash
python pipeline/run_pipeline.py --backfill 90
```

**5. Run the daily pipeline manually**
```bash
python pipeline/run_pipeline.py
```

**6. Run tests**
```bash
pytest tests/ -v
```

---

## What's been built

✅ Live API scraping from Open-Meteo with retry logic
✅ 4-step data cleaning pipeline (validation, outlier flagging, imputation, dedup)
✅ SQLite database with raw, cleaned, and audit log tables
✅ 90-day historical backfill
✅ EDA notebook — stationarity tests, ACF/PACF, STL decomposition, distribution fitting
✅ SARIMA, Prophet, and Chronos forecasting models with shared interface
✅ Anomaly detection — raw IQR + STL residual methods combined
✅ Shared evaluator — RMSE, MAE, MAPE, MASE, coverage
✅ Unit and integration tests

## What's coming next

- [ ] **Docker** — containerise with Docker Compose for reproducible deployment
- [ ] **MLflow** — experiment tracking and model registry for the three-model comparison
- [ ] **CI/CD** — GitHub Actions running tests on every push, deploy on green
- [ ] **Prefect** — replacing the manual pipeline run with proper orchestration
- [ ] **Plotly Dash dashboard** — forecast charts, anomaly flags, model comparison, pipeline log
- [ ] **Railway deployment** — live URL

---

## Design decisions worth noting

**Raw and cleaned data are stored separately.** This means the cleaning pipeline is
re-runnable — changing the IQR threshold or adding a new cleaning step just means
re-running `cleaner.py` against `raw_readings`. The original data is never lost.

**Flagged rows are kept, not deleted.** Outliers are marked `is_outlier_flag=True`
so the model layer can decide how to handle them. Deleting would destroy the audit
trail and make the pipeline non-reproducible.

**Every write is idempotent.** Running the pipeline multiple times produces the same
result as running it once. This matters when a pipeline fails halfway through and
needs to restart cleanly.

**EDA-informed model configuration.** Each city uses different model settings based
on what the EDA revealed — Chicago uses daily data with additive seasonality, while
LA and San Jose use hourly data with multiplicative seasonality. These aren't defaults;
they're deliberate decisions backed by stationarity tests, ACF/PACF plots, and STL decomposition.

**Consistent model interface.** All three models expose the same `fit_and_forecast()`
signature and return the same DataFrame schema. The dashboard and evaluator don't
need to know which model they're calling.