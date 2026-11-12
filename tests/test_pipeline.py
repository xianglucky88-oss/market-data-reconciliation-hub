import sqlite3

from market_data_reconciliation.pipeline import run_pipeline


def test_reconciles_and_rejects(tmp_path):
    db = tmp_path / "market.sqlite3"
    rows = [
        {"event_id": "a", "provider": "alpha", "instrument_id": "abc", "as_of": "2026-01-01T00:00:00Z", "event_type": "quote", "price": 10, "currency": "usd"},
        {"event_id": "b", "provider": "beta", "instrument_id": "ABC", "as_of": "2026-01-01T00:00:00Z", "event_type": "quote", "price": 11, "currency": "USD"},
        {"event_id": "bad", "provider": "alpha", "instrument_id": "ABC", "as_of": "2026-01-01T00:00:00Z", "event_type": "quote", "price": -1, "currency": "USD"},
    ]
    assert run_pipeline(rows, db) == {"accepted": 2, "rejected": 1, "duplicates": 0, "groups": 1}
    with sqlite3.connect(db) as conn:
        assert conn.execute("select status from reconciliation").fetchone()[0] == "mismatch"
