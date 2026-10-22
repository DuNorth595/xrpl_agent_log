# xrpl_agent_log — Usage Guide

## Concepts

- **`Entry`** — one row in the log. Holds: `sequence`, `payload` (dict),
  `parent_hash`, `entry_hash`, `sig_a` / `sig_b`, optional `on_chain_tx_hash`,
  `timestamp`. (Field names are the real ones — see the `Entry` dataclass below.)
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

Signatures below are exact — generated from the source, not from prose.

### `Log`

```python
Log(pair: SigningPair, storage: Storage) -> Log
```
The constructor is positional: `Log(pair, storage)`.

```python
append(self, *, intent: 'str', on_chain_tx_hash: 'str | None' = None, params: 'dict[str, Any] | None' = None) -> 'Entry'
count(self) -> 'int'
latest(self) -> "'Entry | None'"
replay(self) -> "'list[Entry]'"
agent_a_did  # property -> str
agent_b_did  # property -> str
```

`append()` is keyword-only: `intent` is required, the rest optional.

### `SigningPair`

```python
@dataclass
class SigningPair:
    wallet_a: Any
    wallet_b: Any
    did_a: str
    did_b: str
    network: str
```

Constructors: `SigningPair.from_wallets_with_dids(...)`, `SigningPair.from_identities(...)`.
Each DID must end in the matching wallet's classic address — `attach_signature`
raises `ValueError` if they do not match.

### `Entry`

```python
@dataclass
class Entry:
    sequence: int
    parent_hash: str | None
    agent_a_did: str
    agent_b_did: str
    intent: str
    on_chain_tx_hash: str | None
    params: dict[str, Any]
    timestamp: int
    entry_hash: str
    sig_a: str
    sig_b: str
```

The hash field is `entry_hash`. There is no `canonical_hash`.

### `SQLiteStorage`

```python
SQLiteStorage(self, db_path: 'str | Path', log_id: 'str') -> 'None'
```

### Verification

```python
verify_chain(log: "'Log'") -> 'VerificationResult' -> VerificationResult
verify_signatures(log: "'Log'", wallet_a: 'Wallet', wallet_b: 'Wallet') -> 'VerificationResult' -> VerificationResult
verify_on_chain_anchor(log: "'Log'", xrpl_client=None) -> 'VerificationResult' -> VerificationResult

`VerificationResult(ok: bool, errors: list[str])`. Check `.ok`, read `.errors`.
There is no `*_with_report()` variant — these already return the report.

### On-chain anchoring

This library does **not** submit transactions. `append(on_chain_tx_hash=...)`
records a hash you already produced; `verify_on_chain_anchor()` looks it up
over JSON-RPC and checks the memo round-trips.

### CLI


```bash
python -m xrpl_agent_log --version
python -m xrpl_agent_log --demo    # 5-entry demo log, all three verify_* layers
```

## What an entry looks like on disk

```
sqlite> SELECT sequence, entry_hash, on_chain_tx_hash FROM log WHERE log_id = 'demo';
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
        "MemoData": "d18c8b31e6b40d6c..."  // hex-encoded entry_hash
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