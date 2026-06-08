import os
from sqlalchemy import create_engine, Table, Column, MetaData
from sqlalchemy import Integer, Float, String, DateTime, Boolean, Text
from datetime import datetime


# ── engine ────────────────────────────────────────────────────

# creates the data/ folder if it doesn't exist yet
os.makedirs("data", exist_ok=True)

engine   = create_engine("sqlite:///data/aqi.db", echo=False)
metadata = MetaData()

#engine is the connection to the database,
# and metadata is the object that has list of tables put in it.


# ── table definitions ─────────────────────────────────────────

# exact API response — never modified after writing
raw_readings = Table("raw_readings", metadata,
    Column("id",          Integer,  primary_key=True, autoincrement=True),
    Column("city",        String,   nullable=False),
    Column("parameter",   String,   nullable=False),
    Column("value",       Float,    nullable=True),
    Column("unit",        String,   nullable=True),
    Column("timestamp",   DateTime, nullable=False),
    Column("fetched_at",  String,   nullable=False),
)

# pipeline output — what the models read from
cleaned_readings = Table("cleaned_readings", metadata,
    Column("id",               Integer,  primary_key=True, autoincrement=True),
    Column("city",             String,   nullable=False),
    Column("parameter",        String,   nullable=False),
    Column("value",            Float,    nullable=False),
    Column("unit",             String,   nullable=True),
    Column("timestamp",        DateTime, nullable=False),
    Column("is_imputed",       Boolean,  default=False),
    Column("is_outlier_flag",  Boolean,  default=False),
    Column("cleaned_at",       String,   nullable=False),
)

# one row per pipeline run — audit trail
pipeline_log = Table("pipeline_log", metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("run_at",        String,  nullable=False),
    Column("city",          String,  nullable=False),
    Column("rows_fetched",  Integer, default=0),
    Column("rows_rejected", Integer, default=0),
    Column("rows_stored",   Integer, default=0),
    Column("error_msg",     Text,    nullable=True),
)


# ── helpers ───────────────────────────────────────────────────

def create_tables():
    metadata.create_all(engine)


def store_raw(df):
    """Write raw rows to raw_readings, skipping duplicates."""
    if df.empty:
        return 0

    with engine.begin() as conn:
        # simple dedup: only insert rows not already in the table
        existing = conn.execute(
            raw_readings.select().with_only_columns(
                raw_readings.c.city,
                raw_readings.c.timestamp
            )
        ).fetchall()

        existing_keys = {(r.city, r.timestamp) for r in existing}

        new_rows = [
            row for _, row in df.iterrows()
            if (row["city"], row["timestamp"]) not in existing_keys
        ]

        if new_rows:
            conn.execute(raw_readings.insert(), [r.to_dict() for r in new_rows])

    return len(new_rows)


def store_cleaned(df):
    """Write cleaned rows to cleaned_readings."""
    if df.empty:
        return 0

    df["cleaned_at"] = datetime.utcnow().isoformat()

    with engine.begin() as conn:
        conn.execute(cleaned_readings.insert(), df.to_dict(orient="records"))

    return len(df)


def log_run(city, rows_fetched, rows_rejected, rows_stored, error_msg=None):
    """Write one row to pipeline_log."""
    with engine.begin() as conn:
        conn.execute(pipeline_log.insert(), [{
            "run_at":        datetime.utcnow().isoformat(),
            "city":          city,
            "rows_fetched":  rows_fetched,
            "rows_rejected": rows_rejected,
            "rows_stored":   rows_stored,
            "error_msg":     error_msg,
        }])


if __name__ == "__main__":
    create_tables()
    print("tables created — check your data/ folder for aqi.db")