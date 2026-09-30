# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Live XRPL testnet integration test (skipped unless RUN_LIVE=1).

Exercises the full pipeline against the public XRPL testnet:
  1. Funds two testnet wallets from the faucet.
  2. Submits a real 1-drop Payment with a memo.
  3. Captures the live tx hash.
  4. Appends an entry that points at it.
  5. Re-verifies the chain, signatures, AND the on-chain anchor.

This test is gated by the ``RUN_LIVE`` env var so the default CI run
stays deterministic and offline. Run with:
    RUN_LIVE=1 pytest tests/test_integration_ledger_live.py
"""
from __future__ import annotations

import os

import pytest
from xrpl.clients import JsonRpcClient
from xrpl.models import Memo, Payment, Tx
from xrpl.transaction import submit_and_wait
from xrpl.wallet import generate_faucet_wallet

from xrpl_agent_log import (
    Log,
    SigningPair,
    SQLiteStorage,
    verify_chain,
    verify_on_chain_anchor,
    verify_signatures,
)

TESTNET_URL = "https://s.altnet.rippletest.net:51234/"

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1",
    reason="Live testnet test — set RUN_LIVE=1 to enable",
)


@pytest.fixture(scope="module")
def xrpl_client() -> JsonRpcClient:
    return JsonRpcClient(TESTNET_URL)


@pytest.fixture(scope="module")
def funded_pair(xrpl_client):
    """Two distinct testnet wallets funded by the public faucet."""
    wallet_a = generate_faucet_wallet(xrpl_client, debug=False)
    wallet_b = generate_faucet_wallet(xrpl_client, debug=False)
    return wallet_a, wallet_b


def test_end_to_end_live_anchor(tmp_path, xrpl_client, funded_pair):
    """Fund → submit Payment → anchor entry → verify all three layers."""
    wallet_a, wallet_b = funded_pair
    storage = SQLiteStorage(db_path=tmp_path / "live.db", log_id="live")
    pair = SigningPair.from_wallets_with_dids(
        wallet_a,
        wallet_b,
        f"did:xrpl:testnet:{wallet_a.classic_address}",
        f"did:xrpl:testnet:{wallet_b.classic_address}",
        network="testnet",
    )
    log = Log(pair=pair, storage=storage)

    # 1) Submit a real 1-drop Payment with a memo.
    tx = Payment(
        account=wallet_a.classic_address,
        destination=wallet_b.classic_address,
        amount="1",
        memos=[Memo(memo_data=b"xrpl_agent_log:integration-test:v1".hex().upper())],
    )
    response = submit_and_wait(tx, xrpl_client, wallet_a)
    result = response.result
    tx_json = getattr(result, "tx_json", None) or result
    anchor_hash = tx_json["hash"]
    assert len(anchor_hash) == 64

    # 2) Append three entries; sequence 2 carries the live anchor.
    log.append(intent="genesis — no anchor", params={"step": 1})
    log.append(
        intent="live-anchored event",
        on_chain_tx_hash=anchor_hash,
        params={"memo": "xrpl_agent_log:integration-test:v1"},
    )
    log.append(intent="post-anchor follow-up", params={"step": 3})
    assert log.count() == 3

    # 3) Verify all three layers.
    chain = verify_chain(log)
    sigs = verify_signatures(log, wallet_a, wallet_b)
    anchor = verify_on_chain_anchor(log, xrpl_client=xrpl_client)

    assert chain.ok, f"chain errors: {chain.errors}"
    assert sigs.ok, f"signature errors: {sigs.errors}"
    assert anchor.ok, f"anchor errors: {anchor.errors}"

    # 4) Sanity: confirm we can look up the tx independently via the public API.
    direct = xrpl_client.request(Tx(transaction=anchor_hash))
    direct_result = direct.result
    if hasattr(direct_result, "to_dict"):
        direct_result = direct_result.to_dict()
    assert "error" not in direct_result
    assert direct_result.get("hash") == anchor_hash