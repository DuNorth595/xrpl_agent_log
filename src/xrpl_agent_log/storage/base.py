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

    @abstractmethod
    def close(self) -> None:
        """Release any underlying resources."""