# Odoo Demo-Data Generator

Generator engine that builds an installable Odoo 19.0 demo-data module (ZIP)
from a customer specification (JSON).

- Workflow, verified patterns and protocols:
  [skills/odoo-demo-data/SKILL.md](skills/odoo-demo-data/SKILL.md)
- Open items: [ROADMAP.md](ROADMAP.md)

Pure Python stdlib, no dependencies, no `pip install` needed.

## Usage

```bash
python3 -m engine.cli generate --spec examples/muster_foerdertechnik.json --out output
```

Builds `output/<technical_name>/` (module directory) and `output/<technical_name>.zip`.
Static validation (`engine/validate.py`) runs automatically before zipping; on
errors no ZIP is built (`--force` forces it anyway, not recommended).

Check an existing module (directory or ZIP) independently:

```bash
python3 -m engine.cli validate examples/reference/bt_demo_mfg.zip
```

Generate the JSON schema of the specification (new):

```bash
python3 -m engine.cli spec-schema --out engine/spec/spec.schema.json
```

List the capability bundles / scaffold a spec skeleton (see
`skills/odoo-demo-data/reference/capabilities.md`):

```bash
python3 -m engine.cli capabilities
python3 -m engine.cli new --with mrp,sales --name "Muster AG" --country ch --out examples/muster.json
```

## Writing a new customer specification

Copy `examples/muster_foerdertechnik.json` (manufacturing customer) or
`examples/nishcom_ag.json` (multi-app/Enterprise) as a template. Covers the verified
object types: `res.company` (incl. chart of accounts), `res.partner`,
`product.product`, `mrp.bom`, `mrp.production`, `sale.order`, `crm.lead`,
`purchase.order`, `stock.quant`/`stock.warehouse`, `account.move` and
`helpdesk.ticket`.
Complete format: `skills/odoo-demo-data/reference/spec-format.md`.
Unknown fields are rejected on load (typo protection).

Every generated module creates, besides the administrator, a demo login
`demo`/`demo` (name = company, same rights as `base.user_admin`) in the
`post_init_hook` - no manual user setup after a demo appointment. If the login
already exists, creation is skipped (verified-patterns 4.18).

## Tests

```bash
python3 -m unittest discover -s engine/tests -t .
```

## Repo structure

```
engine/
  model.py         data model (dataclasses) + validation of the specification itself
  spec_loader.py    JSON -> dataclasses (rejects unknown fields)
  schema.py         JSON schema from the dataclasses (single source of truth)
  records.py        dataclasses -> Odoo XML record elements (verified patterns)
  xmlgen.py         low-level XML helpers (ElementTree, guaranteed well-formed)
  manifest.py       __manifest__.py / hooks.py rendering
  builder.py        assemble module directory + ZIP
  validate.py       static check of a built module (no Odoo kernel needed)
  cli.py            CLI (generate / validate / spec-schema)
  spec/spec.schema.json  generated JSON schema of the customer specification
  tests/           engine tests (no Odoo needed)
  docker/          installation smoke-test harness against the local Enterprise
                   instance ../odoodemo-local (see its README)
skills/odoo-demo-data/   skill: workflow + reference (verified-patterns, spec-format, ...)
opencode.json/.opencode/ opencode adapter (registers skills/, /new-demo command)
examples/                example specifications
examples/reference/      historical reference modules (no longer a template)
```

## Known limitation

`engine/validate.py` only checks structure (well-formedness, xmlid references,
manifest consistency and the known landmines from
`skills/odoo-demo-data/reference/verified-patterns.md`). It is **no** substitute
for a real installation against an Odoo 19.0 kernel - for that see
`skills/odoo-demo-data/reference/install-test-protocol.md`.
