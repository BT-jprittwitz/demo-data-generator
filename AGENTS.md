# Notes for agents (opencode/Claude Code etc.)

Guide:

- Workflow + reference knowledge: [`skills/odoo-demo-data/SKILL.md`](skills/odoo-demo-data/SKILL.md)
  (neutral Markdown folder, also readable by other LLMs).
- Mechanical usage / CLI: [README.md](README.md).
- Open items: [ROADMAP.md](ROADMAP.md).

## Local test instance

Installation smoke tests target the local Odoo 20 Enterprise (trial) instance in
`../odoodemo-local-20` (Docker). This repo ships no Community setup. See
`skills/odoo-demo-data/reference/install-test-protocol.md`.

## Hard rules

- **Never guess Odoo field names or behavior.** Verify against the
  real Odoo 20.0 source before XML generation. Recipe:
  `skills/odoo-demo-data/reference/verification-protocol.md`.
- On installation error: read/request the **complete traceback** before attempting
  a second fix. No fix without a traceback.
- **No `--test-enable`** for the installation smoke test:
  `skills/odoo-demo-data/reference/install-test-protocol.md`.
- **No fixed industry profiles/archetypes.** Compose each module per customer
  from the verified building blocks; there is no catalog of canned industry
  profiles. Principles: [ROADMAP.md](ROADMAP.md).
- **Committed examples are anonymized (public repo).** Real customer specs must
  not be committed (they contain customer names, addresses, VAT ids). Committed
  `examples/*.json` use a fictional identity (company name starts with `Muster`,
  e.g. "Muster Foerdertechnik AG"); enforced by
  `engine/tests/test_examples_anonymized.py`. `.gitignore` keeps every
  `examples/*.json` untracked except `examples/muster_*.json`, and
  `.githooks/pre-commit` runs the test on commits touching `examples/`. Keep a
  real spec untracked/gitignored and commit only an anonymized copy named
  `examples/muster_*.json`. Enable the hook once per clone:
  `git config core.hooksPath .githooks`.
- **Never mention a real customer/company name anywhere in the repo** - not in
  docs, commit messages, tests or file/module names - even if it is publicly
  findable (e.g. via zefix.ch). Use the fictional `Muster...` identity or a
  generic placeholder (`bt_demo_<topic>`) instead. This applies to new content;
  already-committed history is not rewritten.
- Language of docs, skills and code comments: English. Language of the generated
  demo data: derived from the example company's country, unless the spec sets
  `language` explicitly (see `skills/odoo-demo-data/reference/verified-patterns.md`
  4.16).

## Engine tests

```bash
python3 -m unittest discover -s engine/tests -t .
```
