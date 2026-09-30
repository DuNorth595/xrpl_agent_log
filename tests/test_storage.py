# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Tests for the SQLite storage backend."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from xrpl_agent_log.entry import make_entry
from xrpl_agent_log.signing import attach_signature
from xrpl_agent_log.storage.sqlite import SQLiteStorage


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteStorage:
    return SQLiteStorage(db_path=tmp_path / "test.db", log_id="t-log")


def _signed_entry(wallet_a, wallet_b, *, seq: int, parent: str | None):
    e = make_entry(
        sequence=seq,
        parent_hash=parent,
        agent_a_did=f"did:xrpl:testnet:{wallet_a.classic_address}",
        agent_b_did=f"did:xrpl:testnet:{wallet_b.classic_address}",
        intent="test",
        on_chain_tx_hash=None,
        params={},
    )
    attach_signature(e, wallet_a)
    attach_signature(e, wallet_b)
    return e


def test_storage_starts_empty(storage: SQLiteStorage):
    assert storage.count() == 0
    assert storage.latest() is None
    assert storage.all_entries() == []


def test_storage_appends_and_retrieves(storage, alice_wallet, bob_wallet):
    e1 = _signed_entry(
        alice_wallet, bob_wallet, seq=1, parent=None
    )
    storage.append(e1)

    assert storage.count() == 1
    assert storage.latest().sequence == 1
    fetched = storage.get(1)
    assert fetched is not None
    assert fetched.entry_hash == e1.entry_hash


def test_storage_rejects_unsigned_entry(storage, alice_wallet, bob_wallet):
    """An entry lacking both signatures must be refused."""
    e = _signed_entry(alice_wallet, bob_wallet, seq=1, parent=None)
    e.sig_a = ""
    e.sig_b = ""
    with pytest.raises(ValueError, match="both signatures"):
        storage.append(e)


def test_storage_chain_in_sequence(storage, alice_wallet, bob_wallet):
    """Multiple appends land in sequence order."""
    parents: list[str | None] = []
    for i in range(1, 4):
        latest = storage.latest()
        parents.append(latest.entry_hash if latest else None)
        e = _signed_entry(
            alice_wallet, bob_wallet, seq=i, parent=parents[-1]
        )
        storage.append(e)

    entries = storage.all_entries()
    assert [e.sequence for e in entries] == [1, 2, 3]
    # Each entry's parent_hash must match the previous entry's entry_hash.
    for i in range(1, len(entries)):
        assert entries[i].parent_hash == entries[i - 1].entry_hash


def test_storage_rejects_duplicate_sequence(
    storage, alice_wallet, bob_wallet
):
    """Appending two entries with the same sequence must fail."""
    e1 = _signed_entry(
        alice_wallet, bob_wallet, seq=1, parent=None
    )
    storage.append(e1)

    # Try to append another entry with the same (log_id, sequence).
    e_dup = _signed_entry(
        alice_wallet, bob_wallet, seq=1, parent=None
    )
    with pytest.raises(sqlite3.IntegrityError):
        storage.append(e_dup)


def test_storage_distinguishes_log_ids(tmp_path, alice_wallet, bob_wallet):
    """Two SQLiteStorage instances with different log_ids coexist in one DB."""
    db = tmp_path / "shared.db"
    s1 = SQLiteStorage(db_path=db, log_id="alpha")
    s2 = SQLiteStorage(db_path=db, log_id="beta")

    e1 = _signed_entry(
        alice_wallet, bob_wallet, seq=1, parent=None
    )
    e2 = _signed_entry(
        alice_wallet, bob_wallet, seq=1, parent=None
    )
    s1.append(e1)
    s2.append(e2)

    assert s1.count() == 1
    assert s2.count() == 1
    s1_latest = s1.latest()
    s2_latest = s2.latest()
    assert s1_latest is not None and s2_latest is not None
    # The entry hashes are identical (log_id is a storage namespace, not
    # part of the cryptographic content). What differs is the storage view:
    # s1 (alpha) must not see beta's row, and vice versa. The shared DB file
    # contains both rows; each Storage instance queries by its own log_id.
    rows_visible_to_alpha = s1._conn.execute(  # noqa: SLF001
        "SELECT COUNT(*) FROM entries WHERE log_id = 'alpha'"
    ).fetchone()[0]
    rows_visible_to_beta = s2._conn.execute(  # noqa: SLF001
        "SELECT COUNT(*) FROM entries WHERE log_id = 'beta'"
    ).fetchone()[0]
    assert rows_visible_to_alpha == 1
    assert rows_visible_to_beta == 1


def test_storage_close_is_idempotent(tmp_path):
    storage = SQLiteStorage(db_path=tmp_path / "test.db", log_id="t")
    storage.close()
    storage.close()  # must not raise