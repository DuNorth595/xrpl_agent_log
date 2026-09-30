# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Shared pytest fixtures for xrpl_agent_log tests.

Each test gets two ephemeral xrpl-py Wallets (Alice and Bob), a fresh
in-memory SQLite storage, and a configured Log. Tests must not share state
— every test should be runnable in isolation and in any order.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from xrpl.wallet import Wallet

from xrpl_agent_log import Log, SigningPair, SQLiteStorage


@pytest.fixture
def alice_wallet() -> Wallet:
    return Wallet.create()


@pytest.fixture
def bob_wallet() -> Wallet:
    return Wallet.create()


@pytest.fixture
def did_alice(alice_wallet: Wallet) -> str:
    return f"did:xrpl:testnet:{alice_wallet.classic_address}"


@pytest.fixture
def did_bob(bob_wallet: Wallet) -> str:
    return f"did:xrpl:testnet:{bob_wallet.classic_address}"


@pytest.fixture
def pair(
    alice_wallet: Wallet, bob_wallet: Wallet, did_alice: str, did_bob: str
) -> SigningPair:
    return SigningPair.from_wallets_with_dids(
        alice_wallet, bob_wallet, did_alice, did_bob, network="testnet"
    )


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteStorage:
    """File-backed SQLite (not :memory:) so multiple operations on the same
    connection actually see each other — in-memory SQLite with one
    connection per test is fine here, but file-backed mirrors production."""
    db = tmp_path / "test.db"
    return SQLiteStorage(db_path=db, log_id="test-log-v1")


@pytest.fixture
def log(pair: SigningPair, storage: SQLiteStorage) -> Log:
    return Log(pair=pair, storage=storage)