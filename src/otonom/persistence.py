from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PersistenceConfig:
    database_url: str | None


class PersistenceStore:
    def upsert_job(self, job: dict[str, Any]) -> None:
        raise NotImplementedError

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def append_stop_event(self, event: dict[str, Any]) -> None:
        raise NotImplementedError

    def list_stop_events(self, limit: int = 200) -> list[dict[str, Any]]:
        raise NotImplementedError


class NoopStore(PersistenceStore):
    def upsert_job(self, job: dict[str, Any]) -> None:
        return None

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        _ = job_id
        return None

    def append_stop_event(self, event: dict[str, Any]) -> None:
        _ = event
        return None

    def list_stop_events(self, limit: int = 200) -> list[dict[str, Any]]:
        _ = limit
        return []


class SqliteStore(PersistenceStore):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mission_jobs (
                        job_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        total_parcels INTEGER NOT NULL,
                        completed_parcels INTEGER NOT NULL,
                        active_parcel_id TEXT,
                        next_parcel_id TEXT,
                        result_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stop_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operator_id TEXT NOT NULL,
                        requested_at TEXT NOT NULL,
                        job_id TEXT,
                        parcel_id TEXT,
                        reason TEXT NOT NULL
                    )
                    """
                )

    def upsert_job(self, job: dict[str, Any]) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO mission_jobs (
                        job_id, status, message, created_at, updated_at,
                        total_parcels, completed_parcels, active_parcel_id,
                        next_parcel_id, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        status=excluded.status,
                        message=excluded.message,
                        updated_at=excluded.updated_at,
                        completed_parcels=excluded.completed_parcels,
                        active_parcel_id=excluded.active_parcel_id,
                        next_parcel_id=excluded.next_parcel_id,
                        result_json=excluded.result_json
                    """,
                    (
                        job["job_id"],
                        job["status"],
                        job["message"],
                        job["created_at"],
                        job["updated_at"],
                        int(job["total_parcels"]),
                        int(job["completed_parcels"]),
                        job.get("active_parcel_id"),
                        job.get("next_parcel_id"),
                        json.dumps(job.get("result")) if job.get("result") is not None else None,
                    ),
                )

    def _job_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        result_obj = None
        if row["result_json"]:
            result_obj = json.loads(row["result_json"])
        return {
            "job_id": row["job_id"],
            "status": row["status"],
            "message": row["message"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "total_parcels": int(row["total_parcels"]),
            "completed_parcels": int(row["completed_parcels"]),
            "active_parcel_id": row["active_parcel_id"],
            "next_parcel_id": row["next_parcel_id"],
            "stop_events": [],
            "result": result_obj,
        }

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM mission_jobs WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                if not row:
                    return None
                job = self._job_row_to_dict(row)
                events = conn.execute(
                    """
                    SELECT operator_id, requested_at, job_id, parcel_id, reason
                    FROM stop_events
                    WHERE job_id = ?
                    ORDER BY id ASC
                    """,
                    (job_id,),
                ).fetchall()
                job["stop_events"] = [dict(e) for e in events]
                return job

    def append_stop_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO stop_events (operator_id, requested_at, job_id, parcel_id, reason)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event["operator_id"],
                        event["requested_at"],
                        event.get("job_id"),
                        event.get("parcel_id"),
                        event["reason"],
                    ),
                )

    def list_stop_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT operator_id, requested_at, job_id, parcel_id, reason
                    FROM stop_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()
                # Return oldest->newest order for consistent UI rendering.
                return [dict(r) for r in reversed(rows)]


class PostgresStore(PersistenceStore):
    def __init__(self, database_url: str) -> None:
        try:
            import psycopg  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("psycopg is required for Postgres persistence") from exc

        self._psycopg = psycopg
        self._database_url = database_url
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self):
        return self._psycopg.connect(self._database_url)

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS mission_jobs (
                            job_id TEXT PRIMARY KEY,
                            status TEXT NOT NULL,
                            message TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            total_parcels INTEGER NOT NULL,
                            completed_parcels INTEGER NOT NULL,
                            active_parcel_id TEXT,
                            next_parcel_id TEXT,
                            result_json JSONB
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS stop_events (
                            id BIGSERIAL PRIMARY KEY,
                            operator_id TEXT NOT NULL,
                            requested_at TEXT NOT NULL,
                            job_id TEXT,
                            parcel_id TEXT,
                            reason TEXT NOT NULL
                        )
                        """
                    )

    def upsert_job(self, job: dict[str, Any]) -> None:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO mission_jobs (
                            job_id, status, message, created_at, updated_at,
                            total_parcels, completed_parcels, active_parcel_id,
                            next_parcel_id, result_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (job_id) DO UPDATE SET
                            status=EXCLUDED.status,
                            message=EXCLUDED.message,
                            updated_at=EXCLUDED.updated_at,
                            completed_parcels=EXCLUDED.completed_parcels,
                            active_parcel_id=EXCLUDED.active_parcel_id,
                            next_parcel_id=EXCLUDED.next_parcel_id,
                            result_json=EXCLUDED.result_json
                        """,
                        (
                            job["job_id"],
                            job["status"],
                            job["message"],
                            job["created_at"],
                            job["updated_at"],
                            int(job["total_parcels"]),
                            int(job["completed_parcels"]),
                            job.get("active_parcel_id"),
                            job.get("next_parcel_id"),
                            self._psycopg.types.json.Json(job.get("result")),
                        ),
                    )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT job_id, status, message, created_at, updated_at,
                               total_parcels, completed_parcels, active_parcel_id,
                               next_parcel_id, result_json
                        FROM mission_jobs
                        WHERE job_id = %s
                        """,
                        (job_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    cur.execute(
                        """
                        SELECT operator_id, requested_at, job_id, parcel_id, reason
                        FROM stop_events
                        WHERE job_id = %s
                        ORDER BY id ASC
                        """,
                        (job_id,),
                    )
                    events = cur.fetchall()

        return {
            "job_id": row[0],
            "status": row[1],
            "message": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "total_parcels": int(row[5]),
            "completed_parcels": int(row[6]),
            "active_parcel_id": row[7],
            "next_parcel_id": row[8],
            "result": row[9],
            "stop_events": [
                {
                    "operator_id": e[0],
                    "requested_at": e[1],
                    "job_id": e[2],
                    "parcel_id": e[3],
                    "reason": e[4],
                }
                for e in events
            ],
        }

    def append_stop_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO stop_events (operator_id, requested_at, job_id, parcel_id, reason)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            event["operator_id"],
                            event["requested_at"],
                            event.get("job_id"),
                            event.get("parcel_id"),
                            event["reason"],
                        ),
                    )

    def list_stop_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT operator_id, requested_at, job_id, parcel_id, reason
                        FROM stop_events
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (int(limit),),
                    )
                    rows = cur.fetchall()
        rows = list(reversed(rows))
        return [
            {
                "operator_id": r[0],
                "requested_at": r[1],
                "job_id": r[2],
                "parcel_id": r[3],
                "reason": r[4],
            }
            for r in rows
        ]


def make_persistence_store(config: PersistenceConfig | None = None) -> PersistenceStore:
    cfg = config or PersistenceConfig(database_url=os.getenv("DATABASE_URL"))
    if cfg.database_url:
        if cfg.database_url.startswith("postgresql://") or cfg.database_url.startswith("postgres://"):
            try:
                return PostgresStore(cfg.database_url)
            except Exception:
                return NoopStore()
        if cfg.database_url.startswith("sqlite:///"):
            db_path = Path(cfg.database_url.replace("sqlite:///", "", 1))
            return SqliteStore(db_path)
    return NoopStore()
