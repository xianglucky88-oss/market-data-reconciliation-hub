from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

PROVIDER_PRIORITY = {"alpha": 0, "beta": 1, "gamma": 2}


def _iso(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()


def _event_key(row: dict) -> str:
    raw = "|".join(str(row[k]) for k in ("instrument_id", "as_of", "event_type", "currency"))
    return hashlib.sha256(raw.encode()).hexdigest()


def normalize(row: dict) -> dict:
    event = {
        "event_id": str(row["event_id"]),
        "provider": str(row["provider"]).lower().strip(),
        "instrument_id": str(row["instrument_id"]).upper().strip(),
        "as_of": _iso(str(row["as_of"])),
        "event_type": str(row["event_type"]).lower().strip(),
        "price": float(row["price"]),
        "currency": str(row["currency"]).upper().strip(),
        "version": int(row.get("version", 1)),
    }
    event["reconciliation_key"] = _event_key(event)
    return event


def _schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS market_events (
            event_id TEXT PRIMARY KEY, provider TEXT NOT NULL, instrument_id TEXT NOT NULL,
            as_of TEXT NOT NULL, event_type TEXT NOT NULL, price REAL NOT NULL,
            currency TEXT NOT NULL, version INTEGER NOT NULL, reconciliation_key TEXT NOT NULL,
            UNIQUE(provider, reconciliation_key, version)
        );
        CREATE TABLE IF NOT EXISTS reconciliation (
            reconciliation_key TEXT PRIMARY KEY, canonical_event_id TEXT NOT NULL,
            provider_count INTEGER NOT NULL, min_price REAL NOT NULL, max_price REAL NOT NULL,
            spread REAL NOT NULL, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rejected_records (
            event_id TEXT, reason TEXT NOT NULL, raw_json TEXT NOT NULL
        );
        """
    )


def run_pipeline(records: Iterable[dict], database: str | Path) -> dict[str, int]:
    conn = sqlite3.connect(database)
    _schema(conn)
    accepted = rejected = duplicates = 0
    grouped: dict[str, list[dict]] = {}
    for raw in records:
        try:
            event = normalize(raw)
            if event["price"] < 0 or event["version"] < 1 or event["provider"] not in PROVIDER_PRIORITY:
                raise ValueError("unsupported provider, version, or negative price")
            cur = conn.execute(
                "INSERT OR IGNORE INTO market_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(event.values()),
            )
            if cur.rowcount == 0:
                duplicates += 1
            else:
                accepted += 1
                grouped.setdefault(event["reconciliation_key"], []).append(event)
        except (KeyError, TypeError, ValueError) as exc:
            rejected += 1
            conn.execute(
                "INSERT INTO rejected_records VALUES (?, ?, ?)",
                (str(raw.get("event_id")), str(exc), json.dumps(raw, sort_keys=True)),
            )
    for key, events in grouped.items():
        stored = conn.execute(
            "SELECT event_id, provider, price FROM market_events WHERE reconciliation_key = ?",
            (key,),
        ).fetchall()
        canonical = min(stored, key=lambda item: PROVIDER_PRIORITY.get(item[1], 99))
        prices = [float(item[2]) for item in stored]
        spread = max(prices) - min(prices)
        status = "matched" if spread <= 0.01 else "mismatch"
        conn.execute(
            "INSERT OR REPLACE INTO reconciliation VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key, canonical[0], len(stored), min(prices), max(prices), spread, status),
        )
    conn.commit()
    conn.close()
    return {"accepted": accepted, "rejected": rejected, "duplicates": duplicates, "groups": len(grouped)}
