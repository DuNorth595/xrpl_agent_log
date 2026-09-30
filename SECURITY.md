# Security Policy

## Threat model

`xrpl_agent_log` provides a tamper-evident history log between two XRPL agents. The threat model is scoped as follows.

### In scope

- **Single-party log forgery.** An attacker who controls one agent attempts to insert log entries the other party did not sign. Mitigated by mutual attestation (both signatures required for an entry to commit).
- **Retroactive edit.** An attacker who controls storage attempts to edit a previously-committed entry without invalidating the chain. Mitigated by hash chaining: each entry references the hash of the previous entry; any edit breaks the chain.
- **Replay of stale entries.** An attacker who controls storage attempts to present an old, valid entry as a new claim. Mitigated by sequence numbers and the chain itself: a replayed entry would not have a successor in the current log, making its position detectable.

### Out of scope

- **Key compromise.** If an attacker obtains the seed for an agent's signing key, they can produce valid signatures. `xrpl_agent_log` does not protect against key compromise; that's `xrpl_agent_id`'s responsibility.
- **Availability.** If storage is destroyed, the log is gone. There is no automatic replication in v0.1.0. Operators are responsible for backups of their SQLite (or other) storage backend.
- **Witness compromise.** Witness services (planned for v0.3.0) are third-party timestamp attestors. A compromised witness can lie about timestamps. v0.1.0 has no witness; v0.3.0 will mitigate via multiple-witness schemes.
- **Compliance, legal standing, regulatory acceptance.** This library produces a structured record of agent interactions. It is not certified, audited, or reviewed for any specific regulatory regime. Do not use it as the sole evidence in legal proceedings without independent review.

### Cryptographic primitives

- **Signing:** secp-256k1 via `xrpl_agent_id` (which uses `xrpl-py`'s `Wallet`). Standard ECDSA. Same security properties as XRPL transaction signing.
- **Hash chaining:** SHA-256. Standard.
- **On-chain anchoring:** XRPL transaction hash (also SHA-256-derived). The on-chain tx itself is verified via `xrpl-py`'s standard mechanisms.

These primitives are durable and well-reviewed. The library does not introduce new cryptography.

## Reporting a vulnerability

Email S_DevLabs@outlook.com. Please include:
- Description of the vulnerability
- Reproduction steps
- Affected versions
- Any known mitigations

We aim to acknowledge within 72 hours.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). Until v1.0.0, the public API may change in breaking fashion between minor versions. After v1.0.0, breaking changes require a major version bump.

## Dependencies

- `xrpl-py` ≥ 4.5.0 — official XRPL Python library
- `xrpl_agent_id` ≥ 0.4.0 — agent identity primitives

Both dependencies are pinned to minimum versions; install with `pip install xrpl_agent_log` to get the latest compatible versions automatically.