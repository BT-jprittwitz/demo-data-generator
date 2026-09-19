# Notes for agents (opencode/Claude Code etc.)

Guide:

- Workflow + reference knowledge: [`skills/odoo-demo-data/SKILL.md`](skills/odoo-demo-data/SKILL.md)
  (neutral Markdown folder, also readable by other LLMs).
- Mechanical usage / CLI: [README.md](README.md).
- Open items: [ROADMAP.md](ROADMAP.md).

## Hard rules

- **Never guess Odoo field names or behavior.** Verify against the
  real Odoo 19.0 source before XML generation. Recipe:
  `skills/odoo-demo-data/reference/verification-protocol.md`.
- On installation error: read/request the **complete traceback** before attempting
  a second fix. No fix without a traceback.
- **No `--test-enable`** for the installation smoke test:
  `skills/odoo-demo-data/reference/install-test-protocol.md`.
- Language of docs, skills and code comments: English. Language of the generated
  demo data: derived from the example company's country, unless the spec sets
  `language` explicitly (see `skills/odoo-demo-data/reference/verified-patterns.md`
  4.16).

## Engine tests

```bash
python3 -m unittest discover -s engine/tests -t .
```
