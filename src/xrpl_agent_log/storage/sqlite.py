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

-- The head hash of each log, updated on every append.
--
-- A hash chain verified inward from the entries present cannot detect
-- truncation: a log with its tail removed verifies exactly as well as an
-- intact one. This table is the storage's own memory of how long the log
-- was, so a truncation leaves it ahead of the actual last entry.
--
-- It is a local memory, not an external guarantee. An attacker who can
-- write to this table can hide a truncation. That is why `verify_chain`
-- also accepts an `expected_head` the caller holds independently.
CREATE TABLE IF NOT EXISTS log_heads (
    log_id     TEXT NOT NULL,
    sequence   INTEGER NOT NULL,
    head_hash  TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (log_id)
);
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
        # Recorded before the entry is written, in the same transaction, so
        # the head and the entry it describes can never disagree.
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
        # Update the recorded head in the same transaction as the entry, so
        # the head and the entry it describes can never disagree.
        self._conn.execute(
            """
            INSERT INTO log_heads (log_id, sequence, head_hash, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(log_id) DO UPDATE SET
                sequence   = excluded.sequence,
                head_hash  = excluded.head_hash,
                updated_at = excluded.updated_at
            """,
            (self.log_id, entry.sequence, entry.entry_hash, entry.timestamp),
        )
        self._conn.commit()

    def recorded_head(self) -> "str | None":
        """The head hash this storage last committed, or None if empty.

        Read from the `log_heads` table rather than derived from the
        entries, which is the whole point: a truncated log still has
        entries, but its recorded head still names the entry that was
        removed.
        """
        cur = self._conn.execute(
            "SELECT head_hash FROM log_heads WHERE log_id = ?", (self.log_id,)
        )
        row = cur.fetchone()
        if row is not None:
            return row["head_hash"]
        # A log written before the head table existed has no recorded head.
        return None

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