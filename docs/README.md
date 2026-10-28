# Documentation

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Internal design: hash chain, mutual signing, anchoring, trust model |
| [00_executive_summary.md](00_executive_summary.md) | Project overview and scope |
| [01_usage.md](01_usage.md) | API walkthrough |
| [02_testing_log.md](02_testing_log.md) | Recorded test runs |
| [03_known_issues.md](03_known_issues.md) | Honest disclosures from live testing |

The README covers installation, quick start, and on-chain anchoring. Start there
if you are new to the library.

## Using it with `xrpl_agent_id`

If you are also using
[`xrpl_agent_id`](https://github.com/DuNorth595/xrpl_agent_id) for agent
identity, the two fit together with no glue code:

- [`01_usage.md`](01_usage.md) — *Pairing with `xrpl_agent_id` identities*:
  a worked example that builds a `SigningPair` from two `AgentIdentity`
  objects and appends a signed entry.
- The README's *Relationship to `xrpl_agent_id`* section — what each library
  answers, and the version compatibility requirement.

`xrpl_agent_id` gives an agent an identity; `xrpl_agent_log` records what two
such agents agreed to.
