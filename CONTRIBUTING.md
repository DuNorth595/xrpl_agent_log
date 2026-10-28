# Contributing to xrpl_agent_log

A tamper-evident history log for AI agents on the XRP Ledger. Bug reports are as
welcome as code.

## Getting set up

```bash
git clone https://github.com/DuNorth595/xrpl_agent_log
cd xrpl_agent_log
pip install -e ".[dev]"
pre-commit install
```

`xrpl_agent_id` is not on PyPI; the dependency resolves from a pinned GitHub tag.

## Before you open a pull request

```bash
pytest tests/ -q      # 60 passed, 1 skipped (the live testnet test needs RUN_LIVE=1)
reuse lint            # enforced in CI
pre-commit run --all-files
```

## House rules

- **Documentation is executed before it ships.** The README quick-start is a real,
  runnable script — every API example must actually work against the current
  signatures. If you change an API, regenerate the affected docs in the same
  commit. Do not hand-write signatures.
- **Never commit a seed or private key.** `scripts/check_no_seeds.py` blocks them at
  commit time. Do not `--no-verify` past it.
- **Do not overstate what the library does.** It *records* an on-chain anchor hash
  and verifies it; it does **not** submit anchor transactions. Keep that distinction
  in the docs — it is the single most misrepresented claim this project has had.
- **Test counts must be measured.** The offline suite is 60 tests; the live testnet
  test self-skips without `RUN_LIVE=1`. Quote the real `pytest` output.

## Adding an SPDX header

```bash
reuse annotate --copyright "2026 Justin Douglas" --license MIT <file>
```

`.reuse/dep5` covers the tree as a fallback, and CI enforces `reuse lint`.

## Security issues

Do **not** open a public issue. See [SECURITY.md](SECURITY.md).

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
