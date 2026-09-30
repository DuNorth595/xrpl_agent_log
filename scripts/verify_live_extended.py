# SPDX-FileCopyrightText: 2026 Justin Douglas
# SPDX-License-Identifier: MIT
"""Expanded live XRPL testnet verification — beyond the single-anchor case.

This script runs four test phases against ``s.altnet.rippletest.net:51234``:

  Phase 1: Multi-anchor chain
    - Funds two testnet wallets from the public faucet.
    - Submits three independent 1-drop Payments (each with its own memo).
    - Anchors entries 2, 5, and 8 of a 10-entry log to those three real txs.
    - Verifies chain + signatures + on-chain anchors all pass.

  Phase 2: Independent round-trip lookup
    - For each anchored entry, performs a direct ``Tx`` lookup via JSON-RPC
      and confirms the returned ``hash`` field equals the stored anchor.
    - Pulls the memo payload from the live tx and confirms it round-trips.

  Phase 3: Tampered-anchor detection
    - Anchors an entry to a real tx hash but flips the trailing byte before
      verification. Confirms ``verify_on_chain_anchor`` rejects the
      divergence.

  Phase 4: Scale test
    - Appends 50 unanchored entries (10 at a time, measure each batch).
    - Verifies chain integrity holds at the end.

Each phase records its wall-clock time so we can see where the 22s goes.

Run:  python scripts/verify_live_extended.py
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


def _phase(label: str) -> float:
    """Print phase label and return start time."""
    print(f"\n{'-' * 72}")
    print(f"PHASE: {label}")
    print(f"{'-' * 72}")
    return time.time()


def _elapsed(t0: float) -> str:
    return f"{time.time() - t0:.2f}s"


def _submit_payment(
    client: JsonRpcClient,
    sender,
    dest_address: str,
    memo_text: str,
) -> tuple[str, dict]:
    """Submit a 1-drop Payment with a memo. Returns (tx_hash, response_dict)."""
    tx = Payment(
        account=sender.classic_address,
        destination=dest_address,
        amount="1",
        memos=[Memo(memo_data=memo_text.encode("utf-8").hex().upper())],
    )
    response = submit_and_wait(tx, client, sender)
    result = response.result
    tx_json = getattr(result, "tx_json", None) or result
    if hasattr(tx_json, "to_dict"):
        tx_json = tx_json.to_dict()
    return tx_json["hash"], tx_json


def phase1_multi_anchor(client: JsonRpcClient) -> dict:
    """Build a 10-entry log with 3 entries anchored to 3 real testnet txs."""
    t = _phase("1 — Multi-anchor chain (10 entries, 3 live anchors)")
    wallet_a = generate_faucet_wallet(client, debug=False)
    wallet_b = generate_faucet_wallet(client, debug=False)
    print(f"   Party A: {wallet_a.classic_address}")
    print(f"   Party B: {wallet_b.classic_address}")
    print(f"   [1.1] Both wallets funded: {_elapsed(t)}")

    # Submit three real payments; capture tx hashes + memos.
    anchor_data: list[dict[str, str]] = []
    for i, memo in enumerate(
        ["xrpl_agent_log:phase1:anchor-a", "xrpl_agent_log:phase1:anchor-b", "xrpl_agent_log:phase1:anchor-c"]
    ):
        ts = time.time()
        tx_hash, _ = _submit_payment(client, wallet_a, wallet_b.classic_address, memo)
        print(f"   [1.2.{i + 1}] Submitted anchor tx #{i + 1}: {tx_hash[:16]}... ({time.time() - ts:.2f}s)")
        anchor_data.append({"tx_hash": tx_hash, "memo": memo})
    print(f"   [1.3] 3 anchors captured: {_elapsed(t)}")

    # Assign anchors to log sequences 2, 5, 8.
    seq_to_anchor: dict[int, str] = {2: anchor_data[0]["tx_hash"], 5: anchor_data[1]["tx_hash"], 8: anchor_data[2]["tx_hash"]}

    storage_path = REPO_ROOT / "live_phase1.db"
    if storage_path.exists():
        storage_path.unlink()
    pair = SigningPair.from_wallets_with_dids(
        wallet_a,
        wallet_b,
        f"did:xrpl:testnet:{wallet_a.classic_address}",
        f"did:xrpl:testnet:{wallet_b.classic_address}",
        network="testnet",
    )
    storage = SQLiteStorage(db_path=storage_path, log_id="phase1")
    log = Log(pair=pair, storage=storage)

    print("   [1.4] Appending 10 entries...")
    for seq in range(1, 11):
        anchor_hash = seq_to_anchor.get(seq)
        e = log.append(
            intent=f"event-{seq}",
            on_chain_tx_hash=anchor_hash,
            params={"seq": seq},
        )
        anchor_short = anchor_hash[:12] if anchor_hash else "None"
        print(f"         seq={seq}  hash={e.entry_hash[:12]}...  anchor={anchor_short}...")

    print(f"   [1.5] 10 entries committed: {_elapsed(t)}")

    # Verify all three layers.
    chain = verify_chain(log)
    sigs = verify_signatures(log, wallet_a, wallet_b)
    anchor_check = verify_on_chain_anchor(log, xrpl_client=client)

    print(f"   [1.6] verify_chain            -> ok={chain.ok}  errors={chain.errors}")
    print(f"   [1.7] verify_signatures       -> ok={sigs.ok}    errors={sigs.errors}")
    print(f"   [1.8] verify_on_chain_anchor  -> ok={anchor_check.ok}  errors={anchor_check.errors}")

    storage.close()
    storage_path.unlink()
    all_ok = chain.ok and sigs.ok and anchor_check.ok
    return {
        "phase": "1-multi-anchor",
        "ok": all_ok,
        "elapsed_total": _elapsed(t),
        "entries_committed": 10,
        "anchored_entries": 3,
        "anchor_hashes": [a["tx_hash"] for a in anchor_data],
        "party_a": wallet_a.classic_address,
        "party_b": wallet_b.classic_address,
    }


def phase2_round_trip(client: JsonRpcClient) -> dict:
    """Anchor an entry, then independently look up the tx and verify the memo round-trips."""
    t = _phase("2 — Independent round-trip lookup")
    wallet_a = generate_faucet_wallet(client, debug=False)
    wallet_b = generate_faucet_wallet(client, debug=False)
    print(f"   Party A: {wallet_a.classic_address}")
    print(f"   Party B: {wallet_b.classic_address}")
    print(f"   [2.1] Wallets funded: {_elapsed(t)}")

    memo_text = "xrpl_agent_log:phase2:round-trip-memo-12345"
    tx_hash, _ = _submit_payment(client, wallet_a, wallet_b.classic_address, memo_text)
    print(f"   [2.2] Submitted tx {tx_hash[:16]}... ({_elapsed(t)} since phase start)")

    # Build log with one anchored entry.
    storage_path = REPO_ROOT / "live_phase2.db"
    if storage_path.exists():
        storage_path.unlink()
    pair = SigningPair.from_wallets_with_dids(
        wallet_a,
        wallet_b,
        f"did:xrpl:testnet:{wallet_a.classic_address}",
        f"did:xrpl:testnet:{wallet_b.classic_address}",
        network="testnet",
    )
    storage = SQLiteStorage(db_path=storage_path, log_id="phase2")
    log = Log(pair=pair, storage=storage)
    log.append(
        intent="round-trip-anchor",
        on_chain_tx_hash=tx_hash,
        params={"memo_text": memo_text},
    )
    print(f"   [2.3] Log entry committed: {_elapsed(t)}")

    # Independent lookup: query the ledger directly.
    t_lookup = time.time()
    response = client.request(Tx(transaction=tx_hash))
    lookup_elapsed = time.time() - t_lookup
    result = response.result
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    print(f"   [2.4] Independent tx lookup: {lookup_elapsed:.2f}s")

    # Verify round-trip.
    round_trip_ok = (
        result.get("hash") == tx_hash
        and "error" not in result
    )
    # Inspect memos. rippled nests memos under tx_json, not at the top.
    memos: list = []
    for path in (("tx_json", "Memos"), ("tx_json", "memos"), ("Memos",), ("memos",)):
        cur: object = result
        try:
            for key in path:
                cur = cur[key]  # type: ignore[index]
            if isinstance(cur, list):
                memos = cur
                break
        except (KeyError, TypeError):
            continue
    found_memo = False
    decoded: str = ""
    memo_path_used = ""
    for m in memos:
        m_data = m.get("Memo", m)
        m_hex = m_data.get("MemoData", m_data.get("memo_data", ""))
        try:
            decoded = bytes.fromhex(m_hex).decode("utf-8", errors="replace")
            if decoded == memo_text:
                found_memo = True
                break
        except Exception:
            pass
    print(f"   [2.5] Hash round-trip: {round_trip_ok}")
    print(f"   [2.6] Memo round-trip: {found_memo}  (decoded memo: {decoded if memos else 'NONE — no memos found in result'})")

    storage.close()
    storage_path.unlink()
    return {
        "phase": "2-round-trip",
        "ok": round_trip_ok and found_memo,
        "elapsed_total": _elapsed(t),
        "tx_hash": tx_hash,
        "hash_round_trip": round_trip_ok,
        "memo_round_trip": found_memo,
        "memo_in_ledger": decoded if memos else None,
        "lookup_latency": lookup_elapsed,
    }


def phase3_tampered_anchor(client: JsonRpcClient) -> dict:
    """Anchor an entry to a real tx, then flip the last byte and confirm rejection."""
    t = _phase("3 — Tampered-anchor detection")
    wallet_a = generate_faucet_wallet(client, debug=False)
    wallet_b = generate_faucet_wallet(client, debug=False)
    print(f"   Party A: {wallet_a.classic_address}")
    print(f"   Party B: {wallet_b.classic_address}")

    # Submit a real tx.
    tx_hash, _ = _submit_payment(client, wallet_a, wallet_b.classic_address, "xrpl_agent_log:phase3")
    print(f"   [3.1] Real tx: {tx_hash[:16]}...")

    # Flip the last byte (case toggle: hex chars).
    if tx_hash[-1].lower() in "0123456789abcdef":
        last = int(tx_hash[-1], 16)
        flipped = f"{last ^ 1:x}".upper()
    else:
        flipped = "0"
    tampered_hash = tx_hash[:-1] + flipped
    print(f"   [3.2] Tampered (last byte flipped): {tampered_hash[:16]}...{tampered_hash[-4:]}")

    storage_path = REPO_ROOT / "live_phase3.db"
    if storage_path.exists():
        storage_path.unlink()
    pair = SigningPair.from_wallets_with_dids(
        wallet_a,
        wallet_b,
        f"did:xrpl:testnet:{wallet_a.classic_address}",
        f"did:xrpl:testnet:{wallet_b.classic_address}",
        network="testnet",
    )
    storage = SQLiteStorage(db_path=storage_path, log_id="phase3")
    log = Log(pair=pair, storage=storage)
    log.append(
        intent="will-be-tampered",
        on_chain_tx_hash=tampered_hash,
        params={},
    )
    print(f"   [3.3] Entry anchored to tampered hash: {_elapsed(t)}")

    # Verify on-chain: should FAIL.
    result = verify_on_chain_anchor(log, xrpl_client=client)
    expected_failure = not result.ok
    found_expected_error = any(
        "On-chain" in err for err in result.errors
    )
    print(f"   [3.4] verify_on_chain_anchor: ok={result.ok}  errors={result.errors}")
    print(f"   [3.5] Tamper detected: {expected_failure}")
    print(f"   [3.6] Error message informative: {found_expected_error}")

    storage.close()
    storage_path.unlink()
    return {
        "phase": "3-tampered-anchor",
        "ok": expected_failure and found_expected_error,
        "elapsed_total": _elapsed(t),
        "real_tx_hash": tx_hash,
        "tampered_tx_hash": tampered_hash,
        "verifier_rejected": expected_failure,
        "error_message_present": found_expected_error,
        "verifier_errors": result.errors,
    }


def phase4_scale(client: JsonRpcClient) -> dict:
    """Append 50 unanchored entries and verify chain integrity at scale."""
    t = _phase("4 — Scale test (50 entries, no anchors)")
    wallet_a = generate_faucet_wallet(client, debug=False)
    wallet_b = generate_faucet_wallet(client, debug=False)
    print(f"   Party A: {wallet_a.classic_address}")
    print(f"   Party B: {wallet_b.classic_address}")
    print(f"   [4.1] Wallets funded: {_elapsed(t)}")

    storage_path = REPO_ROOT / "live_phase4.db"
    if storage_path.exists():
        storage_path.unlink()
    pair = SigningPair.from_wallets_with_dids(
        wallet_a,
        wallet_b,
        f"did:xrpl:testnet:{wallet_a.classic_address}",
        f"did:xrpl:testnet:{wallet_b.classic_address}",
        network="testnet",
    )
    storage = SQLiteStorage(db_path=storage_path, log_id="phase4")
    log = Log(pair=pair, storage=storage)

    batch_start = time.time()
    batch_sizes = []
    for batch in range(5):
        batch_t = time.time()
        for i in range(10):
            log.append(
                intent=f"event-{batch * 10 + i + 1}",
                params={"batch": batch, "i": i},
            )
        batch_elapsed = time.time() - batch_t
        batch_sizes.append(batch_elapsed)
        print(f"   [4.2.{batch + 1}] Batch {batch + 1} (entries {batch * 10 + 1}-{(batch + 1) * 10}): {batch_elapsed:.2f}s")

    print(f"   [4.3] 50 entries committed: {_elapsed(t)}  (total append: {sum(batch_sizes):.2f}s)")

    t_verify = time.time()
    chain = verify_chain(log)
    chain_verify_time = time.time() - t_verify
    t_verify = time.time()
    sigs = verify_signatures(log, wallet_a, wallet_b)
    sigs_verify_time = time.time() - t_verify

    print(f"   [4.4] verify_chain (50 entries): ok={chain.ok}  ({chain_verify_time:.2f}s)")
    print(f"   [4.5] verify_signatures (50 entries): ok={sigs.ok}  ({sigs_verify_time:.2f}s)")
    print(f"   [4.6] Total phase 4 time: {_elapsed(t)}")

    storage.close()
    storage_path.unlink()
    return {
        "phase": "4-scale",
        "ok": chain.ok and sigs.ok,
        "elapsed_total": _elapsed(t),
        "entries_committed": 50,
        "chain_verify_time": chain_verify_time,
        "sigs_verify_time": sigs_verify_time,
        "batch_times": batch_sizes,
        "append_total_time": sum(batch_sizes),
    }


def main() -> int:
    print("=" * 72)
    print("XRPL_AGENT_LOG — Extended Live XRPL Testnet Verification")
    print("Network: s.altnet.rippletest.net:51234")
    print("=" * 72)

    client = JsonRpcClient(TESTNET_URL)
    overall_t = time.time()
    results: list[dict] = []

    for phase_fn in (phase1_multi_anchor, phase2_round_trip, phase3_tampered_anchor, phase4_scale):
        try:
            r = phase_fn(client)
        except Exception as exc:  # noqa: BLE001
            print(f"   !!! PHASE FAILED WITH EXCEPTION: {exc}")
            r = {"phase": phase_fn.__name__, "ok": False, "error": str(exc)}
        results.append(r)

    total_elapsed = time.time() - overall_t

    print("\n" + "=" * 72)
    print("EXTENDED LIVE VERIFICATION SUMMARY")
    print("=" * 72)
    for r in results:
        status = "PASS" if r.get("ok") else "FAIL"
        phase = r.get("phase", "?")
        elapsed = r.get("elapsed_total", "?")
        print(f"  [{status}] {phase:20s}  {elapsed}")
    print(f"\nTotal wall-clock: {total_elapsed:.2f}s")
    print("=" * 72)

    # Persist JSON for the PDF builder.
    json_path = REPO_ROOT / "live_extended_results.json"
    json_path.write_text(
        json.dumps(
            {
                "results": results,
                "total_elapsed": total_elapsed,
                "timestamp": time.time(),
                "iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            },
            indent=2,
            default=str,
        )
    )
    print(f"\nJSON results written to {json_path}")
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())