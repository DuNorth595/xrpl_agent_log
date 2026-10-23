# Architecture

How `xrpl_agent_log` works internally: the hash chain, mutual signing,
verification, and anchoring. Every claim here is traceable to a source file —
line references are given so you can check each one.

## Purpose

Records what two agents agreed to, in a form that cannot be edited after the
fact without detection, and that can be checked against public XRPL data
without trusting whoever runs the software.

It does **not** manage keys, hold funds, provide privacy, or replace a SIEM.

## Components

969 lines across 7 modules.

| Module | Lines | Responsibility |
|---|---|---|
| `entry.py` | 138 | Canonical serialization, hashing, the `Entry` dataclass |
| `log.py` | 145 | `Log` and `SigningPair` — append, replay, sequence |
| `signing.py` | 101 | ECDSA signing, slot assignment, signature verification |
| `verify.py` | 160 | Chain, signature, and on-chain anchor verification |
| `storage/sqlite.py` | 159 | SQLite persistence |
| `storage/base.py` | 45 | `Storage` abstract base |
| `__main__.py` | 149 | CLI and offline demo |

There is exactly one storage backend, SQLite (`storage/sqlite.py:61`).
`Storage` is an ABC (`storage/base.py:21`), so a second backend is possible but
none ships.

## The hash chain

Each entry commits to its predecessor, so altering any entry breaks every
subsequent one.

### What is hashed

`compute_entry_hash()` (`entry.py:44`) hashes exactly eight fields:

```
sequence, parent_hash, agent_a_did, agent_b_did,
intent, on_chain_tx_hash, params, timestamp
```

The digest is SHA-256 (`entry.py:66`), hex-encoded, over the canonical
serialization.

### Canonical serialization

`canonical_serialize()` (`entry.py:33`) is deterministic JSON:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"),
           ensure_ascii=False, default=str)
```

Key sorting removes dictionary-ordering ambiguity; explicit separators remove
whitespace variance. This is what makes the hash reproducible by an independent
implementation — a verifier does not need this library to recompute a hash.

### Linking

`parent_hash` of entry *n* is the `entry_hash` of entry *n−1*. The genesis entry
has `parent_hash = None`.

## Signing

Both parties sign every entry. This is mutual attestation: neither party can
record a claim alone.

### What is signed

The signing payload is `entry_hash` (`entry.py:93-95`) — not the entry
contents. Signing the digest means verification needs only the 32-byte digest.

### How

```python
message     = entry.entry_hash.encode("utf-8")   # signing.py:40
private_key = wallet.private_key                # signing.py:30
signature   = kp_sign(message, private_key)     # signing.py:42
```

`kp_sign` is `xrpl.core.keypairs.sign` (`signing.py:17`) — secp256k1, the XRPL
curve. Signatures are hex-encoded and stored in `sig_a` / `sig_b`.

**Precision worth stating:** the signature covers the UTF-8 bytes of the *hex
string*, not the 32 raw digest bytes. An independent verifier must reproduce
that exactly (`entry_hash.encode("utf-8")`) or verification fails.

### Slot assignment

`_which_slot()` (`signing.py:45`) matches by DID suffix:

```python
if entry.agent_a_did.endswith(addr):  return "a"
if entry.agent_b_did.endswith(addr):  return "b"
```

A wallet matching neither party raises `ValueError` (`signing.py:63`). This is a
string-suffix comparison, not a parsed DID-document resolution.

## Verification

Three independent checks, each usable alone.

### 1. Chain integrity — `verify_chain()` (`verify.py:42`)

Walks entries in sequence order and accumulates all errors rather than raising
on the first. Checks:

- `sequence` increments by exactly 1 from 1 — gaps reported
- `parent_hash` equals the previous entry's hash
- recomputed hash matches the stored `entry_hash`
- both signature slots are populated

### 2. Signatures — `verify_signatures()` (`verify.py:89`)

Cryptographically verifies `sig_a` against `wallet_a` and `sig_b` against
`wallet_b` on every entry.

### 3. On-chain anchors — `verify_on_chain_anchor()` (`verify.py:110`)

Optional. For each entry with a non-null `on_chain_tx_hash`, looks the hash up
via `xrpl_client.request(Tx, {...})` and confirms a real transaction exists.

**If `xrpl_client` is `None` the check is skipped and returns `ok=True`**
(`verify.py:121-122`). A skipped check is not a passing check — callers that
need it must pass a client.

## On-chain anchoring — what actually happens

**The library never submits a transaction.** No code path in `src/` constructs,
signs, or sends one. `submit`, `Transaction(`, `autofill`, and `Payment(` appear
nowhere in the package.

`on_chain_tx_hash` is a caller-supplied opaque string. The library:

1. stores it on the entry
2. folds it into the entry hash, so it is tamper-evident like any other field
3. optionally verifies it resolves to a real transaction

The intended workflow is: the caller submits whatever transaction they need for
their own reasons, then records its hash. Agent Log makes that record provable
afterwards. It does not decide what — or whether — to anchor.

## Storage

`SQLiteStorage` (`storage/sqlite.py:61`) persists entries and returns them in
sequence order. The chain is reconstructable from storage alone — which is the
property that makes verification independent of trust in the running process.

## Relationship to `xrpl_agent_id`

Two libraries, layered:

| | Agent ID | Agent Log |
|---|---|---|
| Question | Who is this agent? | What has it done? |
| Produces | identity, credentials, authorization | signed, chained history |
| Needed by the other | no | optional |

`xrpl_agent_log` depends on `xrpl_agent_id` for identity, but its core — hashing,
chaining, signing, verification — does not require it. `xrpl_agent_id` has no
dependency on `xrpl_agent_log`.

The `agent_a_did` / `agent_b_did` fields reference agent identities. They are
carried as strings; Agent Log does not resolve them and does not require them to
come from Agent ID.

## Trust model

**What the design protects against**

- Editing, reordering, or deleting entries after the fact — detectable by hash
  chain and sequence checks
- One party recording an agreement the other did not make — detectable because
  both signatures are required
- Claims about history invented later — detectable against public XRPL data when
  anchored

**What it does not protect against**

- A party refusing to log something. Absence of a record is not evidence.
- Compromise of both private keys. The chain is only as strong as the keys.
- Verification *skipped* — `verify_on_chain_anchor` returns `ok=True` when no
  client is passed.

Logs containing anchors are public by design. Entries not anchored are private
to whoever holds the storage.

## Verification checklist

Every claim in this document, traced to source:

```
SHA-256 over sorted-key, whitespace-free JSON   entry.py:33,66
Hash covers exactly 8 fields                    entry.py:44-66
Signing payload is entry_hash                   entry.py:93-95
secp256k1 via xrpl.core.keypairs.sign           signing.py:17,42
Signature over UTF-8 bytes of the hex digest    signing.py:40
Slot assignment by DID suffix                   signing.py:45-51
Chain verifies seq AND parent AND recompute    verify.py:50-81
Anchor check skips to ok=True without a client  verify.py:121-122
No transaction submission anywhere in src/      verified by search
SQLite is the only shipped backend              storage/sqlite.py:61
```

## Design decisions worth knowing

Three behaviours are deliberate but easy to mistake for oversights:

1. **Genesis uses `parent_hash = None`.** Not a sentinel string. Entry 1 has no
   predecessor, so there is nothing to point at.
2. **DIDs are matched by string suffix, not parsed.** `did:...:rAcct` is matched
   with `endswith`. Cheap and sufficient for two-party logs; it does not
   resolve or validate a DID document.
3. **A skipped anchor check reports `ok=True`.** So callers that ignore the
   client argument see a pass. If you rely on anchor verification, pass a
   client — and check that you did.