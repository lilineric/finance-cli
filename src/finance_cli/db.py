from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class DailyMetric:
    asset_type: str
    code: str
    metric: str
    date: str
    value: float
    source: str


class MetricsRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    asset_type TEXT NOT NULL,
                    code TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    date TEXT NOT NULL,
                    value REAL NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (asset_type, code, metric, date)
                )
                """
            )

    def upsert_metrics(self, metrics: list[DailyMetric]) -> int:
        if not metrics:
            return 0

        updated_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO daily_metrics (asset_type, code, metric, date, value, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_type, code, metric, date) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        metric.asset_type,
                        metric.code,
                        metric.metric,
                        metric.date,
                        metric.value,
                        metric.source,
                        updated_at,
                    )
                    for metric in metrics
                ],
            )

        return len(metrics)

    def latest_date_on_or_before(
        self,
        asset_type: str,
        code: str,
        metric: str,
        query_date: str,
    ) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT date
                FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                  AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                (asset_type, code, metric, query_date),
            ).fetchone()

        return row["date"] if row else None

    def metrics_between(
        self,
        asset_type: str,
        code: str,
        metric: str,
        start_date: str,
        end_date: str,
    ) -> list[DailyMetric]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT asset_type, code, metric, date, value, source
                FROM daily_metrics
                WHERE asset_type = ?
                  AND code = ?
                  AND metric = ?
                  AND date BETWEEN ? AND ?
                ORDER BY date ASC
                """,
                (asset_type, code, metric, start_date, end_date),
            ).fetchall()

        return [DailyMetric(**row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
