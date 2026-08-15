from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class DatabaseManager:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)
        self.connection.commit()

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> int:
        cursor = self.connection.execute(sql, tuple(parameters))
        self.connection.commit()
        return cursor.rowcount

    def query(self, sql: str, parameters: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(sql, tuple(parameters)).fetchall())

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "DatabaseManager": return self
    def __exit__(self, *_: object) -> None: self.close()
