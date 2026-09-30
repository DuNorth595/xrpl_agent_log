# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""SQLite storage backend for xrpl_agent_log.

Append-only by construction: only INSERT statements are issued. No UPDATE,
no DELETE. The schema enforces a unique `sequence` per log (composite key
with log_id) so duplicate appends fail loudly.

Schema:
    entries (
        log_id        TEXT NOT NULL,
        sequence      INTEGER NOT NULL,
        parent_hash   TEXT,
        agent_a_did   TEXT NOT NULL,
        agent_b_did   TEXT NOT NULL,
        intent        TEXT NOT NULL,
        on_chain_tx_hash TEXT,
        params_json   TEXT NOT NULL,
        timestamp     INTEGER NOT NULL,
        entry_hash    TEXT NOT NULL,
        sig_a         TEXT NOT NULL,
        sig_b         TEXT NOT NULL,
        PRIMARY KEY (log_id, sequence)
    )
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from xrpl_agent_log.storage.base import Storage

if TYPE_CHECKING:
    from xrpl_agent_log.entry import Entry


SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    log_id            TEXT NOT NULL,
    sequence          INTEGER NOT NULL,
    parent_hash       TEXT,
    agent_a_did       TEXT NOT NULL,
    agent_b_did       TEXT NOT NULL,
    intent            TEXT NOT NULL,
    on_chain_tx_hash  TEXT,
    params_json       TEXT NOT NULL,
    timestamp         INTEGER NOT NULL,
    entry_hash        TEXT NOT NULL,
    sig_a             TEXT NOT NULL,
    sig_b             TEXT NOT NULL,
    PRIMARY KEY (log_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_entries_hash ON entries(entry_hash);
CREATE INDEX IF NOT EXISTS idx_entries_ts ON entries(timestamp);
"""


class SQLiteStorage(Storage):
    """SQLite-backed append-only storage for a single log.

    The `log_id` namespace lets multiple logs coexist in one database file.
    For typical use, one file per log is fine.
    """

    def __init__(self, db_path: str | Path, log_id: str) -> None:
        self.db_path = Path(db_path)
        self.log_id = log_id
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> "Entry":
        from xrpl_agent_log.entry import Entry

        return Entry(
            sequence=row["sequence"],
            parent_hash=row["parent_hash"],
            agent_a_did=row["agent_a_did"],
            agent_b_did=row["agent_b_did"],
            intent=row["intent"],
            on_chain_tx_hash=row["on_chain_tx_hash"],
            params=json.loads(row["params_json"]),
            timestamp=row["timestamp"],
            entry_hash=row["entry_hash"],
            sig_a=row["sig_a"],
            sig_b=row["sig_b"],
        )

    def append(self, entry: "Entry") -> None:
        if not entry.sig_a or not entry.sig_b:
            raise ValueError(
                "Cannot append an entry without both signatures "
                "(sig_a and sig_b must be populated)"
            )
        self._conn.execute(
            """
            INSERT INTO entries (
                log_id, sequence, parent_hash, agent_a_did, agent_b_did,
                intent, on_chain_tx_hash, params_json, timestamp,
                entry_hash, sig_a, sig_b
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.log_id,
                entry.sequence,
                entry.parent_hash,
                entry.agent_a_did,
                entry.agent_b_did,
                entry.intent,
                entry.on_chain_tx_hash,
                json.dumps(entry.params, sort_keys=True, separators=(",", ":")),
                entry.timestamp,
                entry.entry_hash,
                entry.sig_a,
                entry.sig_b,
            ),
        )
        self._conn.commit()

    def get(self, sequence: int) -> "Entry | None":
        cur = self._conn.execute(
            "SELECT * FROM entries WHERE log_id = ? AND sequence = ?",
            (self.log_id, sequence),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def latest(self) -> "Entry | None":
        cur = self._conn.execute(
            "SELECT * FROM entries WHERE log_id = ? "
            "ORDER BY sequence DESC LIMIT 1",
            (self.log_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def count(self) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM entries WHERE log_id = ?",
            (self.log_id,),
        )
        return int(cur.fetchone()[0])

    def all_entries(self) -> "list[Entry]":
        cur = self._conn.execute(
            "SELECT * FROM entries WHERE log_id = ? ORDER BY sequence ASC",
            (self.log_id,),
        )
        return [self._row_to_entry(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()