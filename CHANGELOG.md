# Changelog

All notable changes to `xrpl_agent_log` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-30

First public release. **Alpha** — APIs may change before 1.0.0.

### Added
- `Log` — append-only history log requiring both parties' signatures per entry.
- `Entry` — single signed record; SHA-256 hash-chained to prior entry.
- `SigningPair.from_identities(...)` — construct from two `xrpl_agent_id.AgentIdentity` objects.
- `SQLiteStorage` (default backend), `Storage` ABC for pluggable persistence.
- `verify_chain`, `verify_signatures`, `verify_on_chain_anchor` — pure-function integrity checks.
- CLI: `python -m xrpl_agent_log --version`, `--demo` (offline end-to-end run).
- Hash chain: SHA-256 over `(prev_hash, seq, timestamp, intent, params)`.
- Signatures: ECDSA secp256k1 via `xrpl.core.keypairs.sign` / `is_valid_message`.
- Optional on-chain anchor: 1-drop XRPL Payment with memo = entry hash.
- Documentation: `README.md`, `docs/00_executive_summary.md`, `docs/01_usage.md`, `docs/02_testing_log.md`, `docs/03_known_issues.md`, `SECURITY.md`, `SESSION_2026-09-30.md`.
- CI matrix: Python 3.9–3.12 on ubuntu-24.04.
- Pre-commit seed scanner (`scripts/check_no_seeds.py`).

### Security
- Seed-scanner in CI + pre-commit prevents accidental commit of family seeds.
- PII scrub performed: ephemeral testnet wallet addresses redacted; build artifacts (HTML/CSS print templates containing home path) untracked.

### Known limitations
- **No PyPI package.** Both `xrpl_agent_id` and `xrpl_agent_log` install from GitHub via `git+https://...` URLs (PyPI account under S_DevLabs@outlook.com not available).
- **`xrpl_agent_log` requires `xrpl_agent_id` ≥ 0.4.1** installed via `git+https://github.com/DuNorth595/xrpl_agent_id.git@v0.4.1`.
- Two-party signing only — no N-party witness scheme yet.
- Single SQLite file per log — no horizontal sharding.
- MPT-specific anchoring not yet supported (Payment-only).

### See also
- Sibling project: [`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) v0.4.1.
- Roadmap: v0.3.0 (ObservationLog + ProposedLog + witness), v0.4.0 multi-party, v0.5.0 cross-log verify, v1.0.0 stable + post-quantum.

[Unreleased]: https://github.com/DuNorth595/xrpl_agent_log/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/DuNorth595/xrpl_agent_log/releases/tag/v0.2.0