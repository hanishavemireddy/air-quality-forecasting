import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import sys
sys.path.append(".")

from pipeline.cleaner import validate_rows, flag_outliers, impute_gaps, deduplicate


# ── helpers ───────────────────────────────────────────────────

def make_df(n=48, city="San Jose", start="2026-01-01"):
    """
    Creates a simple clean DataFrame for testing.
    48 rows = 2 days of hourly data.
    """
    timestamps = [
        datetime.fromisoformat(start) + timedelta(hours=i)
        for i in range(n)
    ]
    return pd.DataFrame({
        "city":      city,
        "parameter": "pm2_5",
        "value":     [10.0] * n,
        "unit":      "µg/m³",
        "timestamp": timestamps,
        "fetched_at":  datetime.now(timezone.utc).isoformat(),
    })


# ── test 1: schema validation ─────────────────────────────────

def test_validate_rejects_negative_values():
    """Rows with negative PM2.5 should be rejected."""
    df = make_df(n=5)
    df.loc[2, "value"] = -5.0  # inject a bad row

    clean_df, rejected = validate_rows(df)

    assert rejected == 1
    assert len(clean_df) == 4
    assert -5.0 not in clean_df["value"].values


def test_validate_rejects_extreme_values():
    """PM2.5 over 1000 should be treated as a sensor error."""
    df = make_df(n=5)
    df.loc[0, "value"] = 1500.0

    clean_df, rejected = validate_rows(df)

    assert rejected == 1
    assert 1500.0 not in clean_df["value"].values


def test_validate_rejects_unknown_city():
    """Rows from cities not in our known list should be rejected."""
    df = make_df(n=3)
    df.loc[1, "city"] = "Miami"  # not in our CITIES dict

    clean_df, rejected = validate_rows(df)

    assert rejected == 1
    assert "Miami" not in clean_df["city"].values


# ── test 2: outlier flagging ──────────────────────────────────

def test_outlier_flagging_marks_spikes():
    """
    A sudden extreme spike should be flagged as an outlier.
    Everything else should remain unflagged.
    """
    df = make_df(n=200)  # need enough rows for rolling window
    df.loc[100, "value"] = 9999.0  # obvious spike

    result = flag_outliers(df, window=48, iqr_factor=3.0)

    assert result.loc[100, "is_outlier_flag"] == True
    # the rest should be clean
    assert result.loc[result.index != 100, "is_outlier_flag"].sum() == 0


def test_outlier_flagging_keeps_flagged_rows():
    """Flagged rows should stay in the DataFrame — never deleted."""
    df = make_df(n=200)
    df.loc[100, "value"] = 9999.0

    result = flag_outliers(df, window=48, iqr_factor=3.0)

    # row is still there, just flagged
    assert len(result) == len(df)
    assert 9999.0 in result["value"].values


# ── test 3: deduplication ─────────────────────────────────────

def test_deduplication_removes_exact_duplicates():
    """Exact duplicate rows on city + timestamp + value should be removed."""
    df = make_df(n=5)
    df_duped = pd.concat([df, df], ignore_index=True)  # double every row

    result = deduplicate(df_duped)

    assert len(result) == 5  # back to original count


def test_deduplication_keeps_different_values():
    """
    Two rows with same city and timestamp but different values
    are not duplicates and should both be kept.
    """
    df = make_df(n=5)
    df2 = make_df(n=5)
    df2.loc[2, "value"] = 99.0  # same timestamp, different value

    combined = pd.concat([df, df2], ignore_index=True)
    result = deduplicate(combined)

    # row 2 has two different values so both should survive
    assert len(result) == 6


# ── test 4: pipeline log ──────────────────────────────────────

def test_validate_all_good_rows_pass():
    """A perfectly clean DataFrame should have zero rejections."""
    df = make_df(n=10)

    clean_df, rejected = validate_rows(df)

    assert rejected == 0
    assert len(clean_df) == 10