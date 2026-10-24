"""
Regression test for datetime column compatibility.
Verifies:
- ORM default timestamp helper produces offset-naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns.
- Timestamps can be subtracted from database-returned naive timestamps without TypeError.
"""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.models.models import AuditLog, _now, utc_now_naive


def test_now_default_produces_naive_utc():
    """_now() must return an offset-naive datetime to match TIMESTAMP WITHOUT TIME ZONE schema."""
    ts = _now()
    assert ts.tzinfo is None, f"_now() returned offset-aware datetime: {ts.tzinfo}"


def test_utc_now_naive_can_be_compared_with_naive_db_timestamps():
    """utc_now_naive() must subtract from naive datetime without TypeError."""
    naive_db_val = datetime(2026, 10, 24, 12, 0, 0)
    current = utc_now_naive()
    # Must not raise TypeError: can't subtract offset-naive and offset-aware datetimes
    diff = (current - naive_db_val).total_seconds()
    assert diff > 0


def test_audit_log_model_default_is_naive():
    """AuditLog column default callable must return an offset-naive datetime."""
    col_default = AuditLog.__table__.columns["timestamp"].default.arg
    ts = col_default(None)
    assert ts.tzinfo is None
