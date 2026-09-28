from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class OperationsStore:
    """Append-only audit adapter; replace SQLite with Postgres in production."""
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path
        with closing(self._connect()) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL, severity TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def record(self, event_type: str, payload: dict, actor: str = "flowmirror-system", severity: str = "info") -> None:
        with closing(self._connect()) as connection:
            connection.execute("INSERT INTO audit_events (occurred_at,event_type,actor,severity,payload) VALUES (?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), event_type, actor, severity, json.dumps(payload, default=str)))
            connection.commit()

    def recent(self, limit: int = 100) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT id,occurred_at,event_type,actor,severity,payload FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": row[0], "occurred_at": row[1], "event_type": row[2], "actor": row[3], "severity": row[4], "payload": json.loads(row[5])} for row in rows]
