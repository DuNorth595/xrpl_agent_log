# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""End-to-end live XRPL testnet anchor verification.

This script is NOT a pytest test. It's a one-shot validation that:
  1. Creates a fresh testnet wallet.
  2. Funds it from the public XRPL testnet faucet.
  3. Submits a 0-XRP self-payment carrying a memo derived from a log entry hash.
  4. Waits for the ledger to confirm the transaction.
  5. Builds a 2-party Log on top of that real tx hash.
  6. Re-verifies the anchor by calling the XRPL testnet JSON-RPC.

Run:  python scripts/verify_live_anchor.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Make src/ importable without an editable install.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from xrpl.clients import JsonRpcClient
from xrpl.models import Memo, Payment, Tx
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from xrpl_agent_log import (
    Log,
    SigningPair,
    SQLiteStorage,
    verify_chain,
    verify_on_chain_anchor,
    verify_signatures,
)
from xrpl_agent_log.entry import make_entry
from xrpl_agent_log.signing import attach_signature

TESTNET_URL = "https://s.altnet.rippletest.net:51234/"
FAUCET_URL = "https://faucet.altnet.rippletest.net/accounts"


def _fund_testnet_wallet(client: JsonRpcClient) -> Wallet:
    """Create a wallet and fund it from the public XRPL testnet faucet.

    Uses xrpl-py testnet helper; falls back to direct faucet POST if helper
    unavailable."""
    try:
        from xrpl.wallet import generate_faucet_wallet

        return generate_faucet_wallet(client, debug=False)
    except ImportError:
        import urllib.request

        req = urllib.request.Request(
            FAUCET_URL,
            data=b'{"destination": "placeholder"}',
            headers={"Content-Type": "application/json"},
        )
        # The classic faucet endpoint takes no payload and returns a random wallet.
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            body = json.loads(r.read())
        return Wallet.from_seed(body["seed"])


def _submit_payment_with_memo(
    client: JsonRpcClient,
    sender: Wallet,
    destination_address: str,
    memo_text: str,
) -> str:
    """Submit a 0-XRP payment from sender to destination with a memo.

    Returns the tx hash (hex). The native XRPL payment type forbids
    self-payments, so we need a second funded wallet as the destination."""
    tx = Payment(
        account=sender.classic_address,
        destination=destination_address,
        # XRPL forbids 0-XRP Payments; 1 drop = 0.000001 XRP is the minimum.
        amount="1",
        memos=[Memo(memo_data=memo_text.encode("utf-8").hex().upper())],
    )
    response = submit_and_wait(tx, client, sender)
    result = response.result
    # submit_and_wait returns TransactionResult; tx_json is a dict-like.
    tx_json = getattr(result, "tx_json", None) or result
    return tx_json["hash"]


def main() -> int:
    print("=" * 72)
    print("XRPL_AGENT_LOG — Live Anchor Verification")
    print("=" * 72)

    client = JsonRpcClient(TESTNET_URL)
    print(f"\n[1/7] Connecting to XRPL testnet: {TESTNET_URL}")
    print(f"      Server info: connected (client instantiated)")

    print("\n[2/7] Creating + funding testnet wallet via public faucet...")
    t0 = time.time()
    wallet = _fund_testnet_wallet(client)
    print(f"      Wallet: {wallet.classic_address}")
    print(f"      Funding time: {time.time() - t0:.1f}s")

    print("\n[3/7] Building 2-party log infrastructure...")
    # Fund a SECOND wallet to serve as both Payment destination and Party B
    # in the mutual log. XRPL's native Payment forbids self-payments, and
    # a real mutual log requires two distinct keypairs. We need both:
    #   wallet_a (sender)  -- funds + submits the anchor Payment
    #   wallet_b (party b) -- holds a different keypair, signs sig_b
    print("      Funding Party B (second testnet wallet)...")
    t1 = time.time()
    wallet_b = _fund_testnet_wallet(client)
    print(f"      Party B wallet: {wallet_b.classic_address} ({time.time() - t1:.1f}s)")

    storage_path = REPO_ROOT / "live_anchor_verify.db"
    if storage_path.exists():
        storage_path.unlink()

    pair = SigningPair.from_wallets_with_dids(
        wallet,
        wallet_b,
        f"did:xrpl:testnet:{wallet.classic_address}",
        f"did:xrpl:testnet:{wallet_b.classic_address}",
        network="testnet",
    )
    storage = SQLiteStorage(db_path=storage_path, log_id="live-anchor")
    log = Log(pair=pair, storage=storage)
    print(f"      Storage: live_anchor_verify.db (log_id=live-anchor)")
    print(f"      Party A: {wallet.classic_address}")
    print(f"      Party B: {wallet_b.classic_address}")

    print("\n[4/7] Submitting 0-XRP Payment with anchor memo...")
    # Submit BEFORE creating any entries so the tx hash is independent.
    anchor_tx_hash = _submit_payment_with_memo(
        client, wallet, wallet_b.classic_address, "xrpl_agent_log:live-anchor:v1"
    )
    print(f"      Tx hash: {anchor_tx_hash}")

    print("\n[5/7] Appending 3 entries; sequence 2 carries the live anchor...")
    e1 = log.append(intent="genesis — no anchor", params={"step": 1})
    print(f"      seq=1 entry_hash={e1.entry_hash[:16]}...  anchor=None")

    e2 = log.append(
        intent="live-anchored event",
        on_chain_tx_hash=anchor_tx_hash,
        params={"memo": "xrpl_agent_log:live-anchor:v1"},
    )
    print(f"      seq=2 entry_hash={e2.entry_hash[:16]}...  anchor={anchor_tx_hash[:16]}...")

    e3 = log.append(intent="post-anchor follow-up", params={"step": 3})
    print(f"      seq=3 entry_hash={e3.entry_hash[:16]}...  anchor=None")

    print("\n[6/7] Running verify_chain + verify_signatures + verify_on_chain_anchor...")
    chain_result = verify_chain(log)
    sig_result = verify_signatures(log, wallet, wallet_b)
    anchor_result = verify_on_chain_anchor(log, xrpl_client=client)

    print(f"      verify_chain            -> ok={chain_result.ok}  errors={chain_result.errors}")
    print(f"      verify_signatures       -> ok={sig_result.ok}    errors={sig_result.errors}")
    print(f"      verify_on_chain_anchor  -> ok={anchor_result.ok} errors={anchor_result.errors}")

    print("\n[7/7] Replay contents:")
    for entry in log.replay():
        print(
            f"      seq={entry.sequence}  intent={entry.intent!r}  "
            f"anchor={(entry.on_chain_tx_hash or 'None')[:16]}..."
        )

    all_ok = chain_result.ok and sig_result.ok and anchor_result.ok
    print("\n" + "=" * 72)
    if all_ok:
        print("LIVE ANCHOR VERIFICATION: PASSED")
    else:
        print("LIVE ANCHOR VERIFICATION: FAILED")
    print("=" * 72)

    storage.close()
    # Cleanup the demo DB so it doesn't pollute the repo.
    db_path = REPO_ROOT / "live_anchor_verify.db"
    if db_path.exists():
        db_path.unlink()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())