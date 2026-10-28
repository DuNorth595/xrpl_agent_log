"""Adversarial tests: the attacks that a hash chain alone cannot catch.

These reproduce, as executable tests, the findings recorded in
`docs/04_truncation_and_anchors.md`. Every attack here was verified to
pass verification BEFORE the fix landed.
"""

from __future__ import annotations

import sqlite3

import pytest

from xrpl_agent_log import Log
from xrpl_agent_log import SigningPair
from xrpl_agent_log import SQLiteStorage
from xrpl_agent_log import verify_chain
from xrpl_agent_log.verify import verify_on_chain_anchor


@pytest.fixture
def built(tmp_path):
    """A log with three committed entries. Returns (log, db_path, wallets)."""
    from xrpl.wallet import Wallet

    a, b = Wallet.create(), Wallet.create()
    db_path = tmp_path / "log.db"
    storage = SQLiteStorage(db_path=db_path, log_id="t")
    pair = SigningPair(
        wallet_a=a,
        wallet_b=b,
        did_a="did:xrpl:2:" + a.classic_address,
        did_b="did:xrpl:2:" + b.classic_address,
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)
    for i in range(3):
        log.append(intent=f"act{i}", params={"k": i})
    return log, str(db_path), a, b


def _delete_where(db_path: str, where: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(f"DELETE FROM entries WHERE {where}")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- truncation


def test_tail_truncation_is_detected_by_recorded_head(built):
    """Deleting the last entry must not pass verification."""
    log, db_path, _, _ = built

    _delete_where(db_path, "sequence = (SELECT MAX(sequence) FROM entries)")

    result = verify_chain(log)
    assert not result.ok, "truncating the tail passed verification"
    assert any("truncat" in e.lower() for e in result.errors)


def test_multi_entry_truncation_is_detected(built):
    log, db_path, _, _ = built

    _delete_where(db_path, "sequence > 1")

    result = verify_chain(log)
    assert not result.ok
    assert any("truncat" in e.lower() for e in result.errors)


def test_whole_log_replaced_with_a_shorter_one_is_detected(built):
    """An attacker who replaces the log with a forged short one is caught."""
    log, db_path, _, _ = built

    _delete_where(db_path, "sequence > 0")

    result = verify_chain(log)
    assert not result.ok


def test_expected_head_catches_truncation(built):
    """An independently-held expected head catches what the storage misses."""
    log, db_path, _, _ = built
    expected = log.latest().entry_hash

    _delete_where(db_path, "sequence = (SELECT MAX(sequence) FROM entries)")

    # Even if the storage's recorded head were also rewritten to match,
    # a caller holding the real head still detects the truncation.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE log_heads SET head_hash = (SELECT entry_hash FROM entries "
        "WHERE sequence = (SELECT MAX(sequence) FROM entries)) WHERE log_id = 't'"
    )
    conn.commit()
    conn.close()

    result = verify_chain(log, expected_head=expected)
    assert not result.ok
    assert any("truncat" in e.lower() for e in result.errors)


def test_intact_log_still_passes(built):
    log, _, _, _ = built
    result = verify_chain(log)
    assert result.ok, result.errors


def test_intact_log_passes_with_expected_head(built):
    log, _, _, _ = built
    expected = log.latest().entry_hash
    result = verify_chain(log, expected_head=expected)
    assert result.ok, result.errors


def test_editing_is_still_detected(built):
    """The original guarantee must not regress."""
    log, db_path, _, _ = built

    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE entries SET intent = 'tampered' WHERE sequence = 2")
    conn.commit()
    conn.close()

    result = verify_chain(log)
    assert not result.ok


# ------------------------------------------------------------------ anchors


class _FakeClient:
    """Stands in for an XRPL client that knows one transaction.

    Mirrors xrpl-py 5.x exactly: `request()` takes a single Request model,
    and `response.result` is a plain dict in which rippled reports a
    missing transaction as an `error` key.
    """

    def __init__(self, known: set[str]):
        self.known = known

    def request(self, request):
        h = request.transaction

        class _Response:
            pass

        resp = _Response()
        if h in self.known:
            resp.result = {"hash": h, "validated": True}
        else:
            resp.result = {"error": "txnNotFound", "error_code": 29}
        return resp


def test_deleting_the_anchored_entry_is_detected(tmp_path):
    """Removing the anchor must not report a clean pass."""
    from xrpl.wallet import Wallet

    a, b = Wallet.create(), Wallet.create()
    db_path = tmp_path / "anchored.db"
    storage = SQLiteStorage(db_path=db_path, log_id="t")
    pair = SigningPair(
        wallet_a=a,
        wallet_b=b,
        did_a="did:xrpl:2:" + a.classic_address,
        did_b="did:xrpl:2:" + b.classic_address,
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)
    anchor = "A" * 64
    log.append(intent="anchored", params={}, on_chain_tx_hash=anchor)
    log.append(intent="after", params={})

    client = _FakeClient({anchor})

    # Before: the anchor is present and the check passes.
    assert verify_on_chain_anchor(log, client).ok

    # Now delete the anchored entry and everything after it.
    _delete_where(str(db_path), "sequence >= 1")

    result = verify_on_chain_anchor(log, client, expect_anchors=1)
    assert not result.ok, "removing the anchored entry reported a clean pass"
    assert any("anchored entr" in e for e in result.errors)


def test_expected_anchor_hash_catches_substitution(tmp_path):
    from xrpl.wallet import Wallet

    a, b = Wallet.create(), Wallet.create()
    db_path = tmp_path / "subst.db"
    storage = SQLiteStorage(db_path=db_path, log_id="t")
    pair = SigningPair(
        wallet_a=a,
        wallet_b=b,
        did_a="did:xrpl:2:" + a.classic_address,
        did_b="did:xrpl:2:" + b.classic_address,
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)
    anchor = "A" * 64
    log.append(intent="anchored", params={}, on_chain_tx_hash=anchor)

    client = _FakeClient({anchor})
    result = verify_on_chain_anchor(log, client, expected_anchor_hash="B" * 64)
    assert not result.ok
    assert any("not present" in e for e in result.errors)


def test_anchored_log_still_passes_with_expectations(tmp_path):
    from xrpl.wallet import Wallet

    a, b = Wallet.create(), Wallet.create()
    db_path = tmp_path / "ok.db"
    storage = SQLiteStorage(db_path=db_path, log_id="t")
    pair = SigningPair(
        wallet_a=a,
        wallet_b=b,
        did_a="did:xrpl:2:" + a.classic_address,
        did_b="did:xrpl:2:" + b.classic_address,
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)
    anchor = "A" * 64
    log.append(intent="anchored", params={}, on_chain_tx_hash=anchor)

    client = _FakeClient({anchor})
    result = verify_on_chain_anchor(
        log, client, expect_anchors=1, expected_anchor_hash=anchor
    )
    assert result.ok, result.errors
