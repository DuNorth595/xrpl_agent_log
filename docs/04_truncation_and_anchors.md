# Truncation and Anchor-Removal: what the log cannot detect

This document records an adversarial review of `xrpl_agent_log` v0.3.1,
carried out by attempting to break the library's stated guarantees rather
than by reading its tests.

Every finding below was reproduced against the real implementation.

## The gap: truncation is not detectable

`verify_chain()` walks the entries that are present and checks each one
against the one before it. That detects **editing** — change entry 3 and
every hash after it breaks.

It does **not** detect **truncation**, because the chain is only ever
verified inward from whatever is present. Nothing outside the log holds
the expected head.

### Reproduced

| Attack | Result |
|---|---|
| Delete the last entry | `verify_chain()` returns `ok=True` |
| Delete the last two entries | `verify_chain()` returns `ok=True` |
| Replace a 3-entry log with a forged 1-entry log | `verify_chain()` returns `ok=True` |

A truncated log is indistinguishable from a shorter log.

### This is a property of a local hash chain, not a coding bug

A hash chain proves the *contents* have not been edited. It cannot prove
that *nothing was removed*, unless the head hash is committed somewhere
the verifier controls and the attacker cannot reach.

The library already has the mechanism for that: the on-chain anchor. But
see the second finding.

## The gap: deleting the anchored entry removes the only evidence

`verify_on_chain_anchor()` iterates over entries that are present and
checks the ones that have an `on_chain_tx_hash`.

If an attacker deletes the anchored entry — and everything after it — the
anchor check finds no anchored entries left to check and reports success.

Reproduced: a log whose only anchored entry was deleted passes both
`verify_chain()` and `verify_on_chain_anchor()`.

The anchor only helps if the verifier knows the anchor *should* be there.

## What is correctly implemented

Worth stating plainly, because it was checked rather than assumed:

- **Editing is detected.** Hash mismatch and parent-link break are both
  reported, with the sequence number.
- **Truncating from the front is detected.** A sequence gap is reported.
- **The signing path enforces DID-to-wallet binding.** A `SigningPair`
  whose DID does not match the wallet's address raises `ValueError` at
  append time rather than producing an unverifiable entry.
- **The on-chain error envelope is handled.** A missing transaction comes
  back from rippled as `{"error": "txnNotFound", ...}` inside `result`, and
  the verifier reports it as a failed lookup rather than passing it
  through. This was a real bug once, documented in `03_known_issues.md`.

## How to close the gap

The fix is not in the hash chain. It is in giving the verifier an
expectation that the log cannot quietly drop:

1. **An expected head hash.** `verify_chain(log, expected_head=...)` —
   if the last entry's hash does not match what the caller expected, the
   log was truncated. The caller gets that expectation from somewhere
   durable.

2. **An expected anchor count or expected anchor hash.**
   `verify_on_chain_anchor(log, client, expect_anchors=1)` — a log that
   claims to be anchored but has no anchored entries left is a failed
   check, not a pass.

3. **Documenting the limitation where it is claimed.** The README says
   "each entry commits to the one before it. Editing entry 3 breaks every
   hash after it." That is accurate. It does not say that truncation is
   undetectable, and a reader could reasonably assume the chain covers it.

Option 3 is required regardless of whether 1 and 2 are implemented.

## Status

**Implemented in v0.4.0.** The API changes are additive and
backwards-compatible: the new parameters are optional, and an existing
caller gets the previous behaviour.

| Mitigation | Status | Catches |
|---|---|---|
| `SQLiteStorage.recorded_head()` — head hash written on every append | Shipped | Truncation by a process that can only delete rows |
| `verify_chain(log, expected_head=...)` | Shipped | Truncation by anything, if the caller holds the head independently |
| `verify_on_chain_anchor(log, client, expect_anchors=N)` | Shipped | Deletion of an anchored entry |
| `verify_on_chain_anchor(log, client, expected_anchor_hash=...)` | Shipped | Substitution of an anchor |

Ten adversarial tests in `tests/test_truncation_resistance.py` reproduce
each attack and assert it is now detected. Every one of them passed
verification before the fix landed.

### What is still not covered

A single local SQLite file cannot defend against an attacker who can
write to that file *and* the recorded head, or who can delete the rows and
the head table together. Against that adversary, the head has to come
from outside the storage — an `expected_head` the caller holds, or an
on-chain anchor verified against public ledger data.

This is the standard shape of the problem: local tamper-evidence is
detectable; tamper-evidence *against a storage-level attacker* requires
an external anchor. The library now supports both and is explicit about
which one is in use.
