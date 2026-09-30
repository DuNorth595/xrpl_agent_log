# xrpl_agent_log — Usage Guide

## Concepts

- **`Entry`** — one row in the log. Holds: `sequence`, `payload` (dict),
  `prev_hash`, `canonical_hash`, `signatures` (party_a, party_b),
  optional `anchor_tx_hash`, `timestamp`.
- **`Log`** — owns a `SQLiteStorage` and a `SigningPair`. The `append()`
  method chains, signs, persists, and (optionally) anchors in one call.
- **`SigningPair`** — the two parties who sign every entry. Constructed
  from `(wallet, did)` tuples via `from_wallets_with_dids()`.
- **`SQLiteStorage`** — append-only backend. `(log_id, sequence)` is the
  composite primary key. No UPDATE, no DELETE; the file system is the
  only realistic tamper surface.

## Three layers of tamper-evidence

| Layer | What it proves | What it costs |
|---|---|---|
| Hash chain (`prev_hash` field) | No entry was modified or inserted/deleted in the middle | Free (SHA-256) |
| Mutual ECDSA signatures | Both parties actually saw and signed this entry | One secp256k1 sig per party per entry |
| On-chain anchor (optional) | Entry existed at this point in real time | 1-drop Payment (~12 drops fee) |

A verifier can check **any layer independently**. The strongest
guarantee comes from using all three together.

## Mutating a log (verifier-visible signals)

| Attack | Caught by |
|---|---|
| Modify entry N's `payload` | Hash chain (next `prev_hash` mismatches) |
| Insert a fake entry | Hash chain (`prev_hash` doesn't match) |
| Delete entry N | Hash chain (subsequent `prev_hash` references a removed entry) |
| Re-sign with stolen key | Public key doesn't match the original `party_a` / `party_b` |
| Forge a party B signature without their key | ECDSA verification fails |
| Lie about an anchor tx hash | `verify_on_chain_anchor` does a JSON-RPC `Tx` lookup; mismatch caught |
| Pretend an anchor was at a different time | `tx.Date` is on the ledger; lies are caught by comparison |

## API reference

### `Log`

```python
Log(storage: SQLiteStorage, signers: SigningPair) -> Log
```

#### `log.append(payload: dict, *, anchor_with: Wallet | None = None) -> Entry`

Append one entry. Returns the persisted `Entry` with all fields
populated.

- `payload` — any JSON-serializable dict. Stored verbatim.
- `anchor_with` — optional `xrpl.wallet.Wallet`. If provided, submits a
  1-drop Payment whose memo encodes the entry's `canonical_hash`. The
  resulting transaction hash is stored in `entry.anchor_tx_hash`.
  Requires the wallet to be funded (on testnet: use the faucet).

#### `log[i: int | slice] -> Entry | list[Entry]`

Read-only indexed access.

### `SigningPair`

```python
SigningPair(party_a: Party, party_b: Party) -> SigningPair
SigningPair.from_wallets_with_dids(
    party_a: tuple[Wallet, str],   # (wallet, did)
    party_b: tuple[Wallet, str],
) -> SigningPair
```

Each `Party` knows its `(wallet, did, public_key_hex)`. The signing
operation pulls the private key only at sign-time and drops it.

### `SQLiteStorage`

```python
SQLiteStorage(path: str | Path, *, log_id: str) -> SQLiteStorage
```

`log_id` is a namespace — multiple logs can coexist in one SQLite file.

#### `storage.append(entry: Entry) -> None`

Inserts a row. If `(log_id, sequence)` already exists, raises
`DuplicateSequenceError`. **No UPDATE, no DELETE.**

### Verification

```python
from xrpl_agent_log import (
    verify_chain,
    verify_signatures,
    verify_on_chain_anchor,
)

verify_chain(log) -> bool
# Walks every entry, recomputes canonical_hash from payload + prev_hash,
# confirms each prev_hash equals the previous entry's canonical_hash.

verify_signatures(log) -> bool
# For each entry, checks both party_a and party_b ECDSA signatures
# against the entry's canonical bytes.

verify_on_chain_anchor(log, index: int) -> bool
# For entry at `index`, performs a JSON-RPC `Tx` lookup against the
# configured network. Returns True iff the stored `anchor_tx_hash`
# matches the live ledger AND the memo payload round-trips.
```

All three return `bool`. For richer error info, use the lower-level
`*_with_report()` variants that return `(bool, list[Issue])`.

### CLI

```bash
python -m xrpl_agent_log --version
python -m xrpl_agent_log --demo    # 5-entry demo log, all three verify_* layers
```

## What an entry looks like on disk

```
sqlite> SELECT sequence, canonical_hash, anchor_tx_hash FROM log WHERE log_id = 'demo';
0|7f83b1657ff1fc53...|NULL
1|2c624232cdd22177...|NULL
2|48a39f28825b90d6...|NULL
3|d18c8b31e6b40d6c...|AD947C0EC316E8536A39C44DCD33B3373387DE5886692474A0FEA378ED5EE715  ← XRPL testnet anchor
4|e8c33d50a4b30a4d...|NULL
```

## What an entry looks like on-chain

```
{
  "tx": {
    "TransactionType": "Payment",
    "Account": "rPartyA...",
    "Destination": "rPartyB...",
    "Amount": "1",          // 1 drop, the minimum native amount
    "Memos": [{
      "Memo": {
        "MemoData": "d18c8b31e6b40d6c..."  // hex-encoded canonical_hash
      }
    }]
  }
}
```

## Auditing without the library

A complete audit requires only:

1. The SQLite file (or any equivalent row store)
2. Both parties' public keys
3. The XRPL network URL (default `https://s.altnet.rippletest.net:51234`)
4. The Python standard library + `xrpl-py` (just for JSON-RPC + ECDSA verify)

A 200-line auditor script is enough. We provide one at
`scripts/verify_live_anchor.py` and `scripts/verify_live_extended.py`.