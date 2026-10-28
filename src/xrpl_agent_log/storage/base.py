# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Storage — pluggable backend for the append-only log.

The contract: append() is the only write operation. There is no update(),
no delete(), no reorder. Once an Entry is committed, it stays committed.

The SQLite backend is the default. It enforces append-only at the schema
level (no UPDATE/DELETE statements anywhere), and stores entries in a
single table keyed by sequence number.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xrpl_agent_log.entry import Entry


class Storage(ABC):
    """Abstract storage backend for an append-only log."""

    @abstractmethod
    def append(self, entry: "Entry") -> None:
        """Persist an entry. Must not modify or replace existing entries."""

    @abstractmethod
    def get(self, sequence: int) -> "Entry | None":
        """Fetch an entry by sequence number. Returns None if not found."""

    @abstractmethod
    def latest(self) -> "Entry | None":
        """Return the most recently committed entry, or None if log is empty."""

    @abstractmethod
    def count(self) -> int:
        """Total entries committed so far."""

    @abstractmethod
    def all_entries(self) -> "list[Entry]":
        """Return all entries in sequence order. Read-only."""

    def recorded_head(self) -> "str | None":
        """The head hash this storage last committed, or None if empty.

        A hash chain verified inward from whatever is present cannot detect
        truncation -- a shorter log looks exactly like an intact one. The
        recorded head is the storage's own memory of how long the log was,
        so a truncation that removes entries from the tail leaves the
        recorded head ahead of the actual last entry.

        This is a *local* memory of the head. An attacker who truncates
        the log and then rewrites the recorded head can still hide it, which
        is why `verify_chain` also accepts an `expected_head` that the
        caller holds independently.

        The default implementation derives the head from the entries
        themselves, which detects nothing. Backends that can store it
        should override this.
        """
        latest = self.latest()
        return latest.entry_hash if latest is not None else None

    @abstractmethod
    def close(self) -> None:
        """Release any underlying resources."""