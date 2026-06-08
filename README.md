# air-quality-forecasting
Playing around with time series forecasting models

# AQI Time Series Forecasting Dashboard

I'm trying to build a full-stack data science project that pulls live air quality data from the internet, cleans it through an automated pipeline, stores it in a database, and will serve forecasts from three models (SARIMA, Prophet, Chronos) through a Plotly Dash dashboard.

> **Status so far:** Data pipeline completed Forecasting models and dashboard in progress.

---

## Project Description

Every day, a pipeline scrapes hourly PM2.5 air quality readings for three US cities
from the [Open-Meteo Air Quality API](https://open-meteo.com/). The raw data is validated,
cleaned, and stored in a SQLite database — keeping the original and cleaned versions
separate so the pipeline is always re-runnable without losing anything.

The end goal is a Plotly Dash dashboard where you can compare forecasts from SARIMA,
Prophet, and Chronos side by side, with anomaly flags and model evaluation metrics.

---

## Cities tracked

- San Jose, CA
- Los Angeles, CA
- Chicago, IL

---

## Project structure

```
ts-forecast-dashboard/
├── pipeline/
│   ├── scraper.py              # pulls hourly PM2.5 from Open-Meteo API
│   ├── cleaner.py              # validates, flags outliers, imputes gaps, deduplicates
│   ├── database.py             # SQLAlchemy table definitions and write helpers
│   └── run_pipeline.py         # orchestrates scrape → clean → store end to end
├── models/                     # forecasting models (in progress)
├── dashboard/                  # Plotly Dash app (in progress)
├── tests/
│   └── test_cleaner.py         # unit tests for the cleaning pipeline
├── notebooks/                  
│   └── eda_geospatial.ipynb                # EDA notebook
│   └── missing_data_imputation.ipynb       # Ways to deal with missing notebook(TBD)
│   └── classical_models_sarima_ets.ipynb   # (for future)
│   └── ml_dl_models_prophet_xgb_lstm.ipynb # (for future)
│   └── model_comparison.ipynb              # (for future)
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
cd air-quality-forecasting-dashboard
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

## Requirements

```
requests
tenacity
pandas
pydantic
sqlalchemy
python-dotenv
pytest
```

---

## What's coming next

- **EDA notebook** — stationarity tests, ACF/PACF, STL decomposition, distribution fitting
- **Forecasting models** — SARIMA, Prophet, and Chronos with a shared evaluation interface
- **Docker** — containerised with Docker Compose for reproducible deployment
- **MLflow** — experiment tracking and model registry for the three-model comparison
- **CI/CD** — GitHub Actions running tests on every push
- **Prefect** — replacing the manual pipeline run with proper orchestration
- **Plotly Dash dashboard** — forecast charts, anomaly flags, model comparison, pipeline log

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