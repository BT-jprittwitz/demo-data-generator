# Odoo Demo-Data Generator

Generator engine that builds an installable Odoo 20.0 demo-data module (ZIP)
from a customer specification (JSON).

- Workflow, verified patterns and protocols:
  [skills/odoo-demo-data/SKILL.md](skills/odoo-demo-data/SKILL.md)
- Open items: [ROADMAP.md](ROADMAP.md)

Pure Python stdlib, no dependencies, no `pip install` needed.

## Setup (once per clone)

This is a **public** repository. Real customer specifications (names, addresses,
VAT ids) must never be published. Enable the guard that blocks them at commit
time:

```bash
git config core.hooksPath .githooks
```

`.gitignore` additionally keeps every `examples/*.json` untracked except the
anonymized `examples/muster_*.json`; the pre-commit hook runs
`engine/tests/test_examples_anonymized.py` on any commit touching `examples/`.
Keep a real spec untracked and commit only an anonymized copy with a fictional
`Muster...` company name (see [AGENTS.md](AGENTS.md)).

## Usage

```bash
python3 -m engine.cli generate --spec examples/muster_foerdertechnik.json --out output
```

Builds `output/<technical_name>/` (module directory) and `output/<technical_name>.zip`.
Static validation (`engine/validate.py`) runs automatically before zipping; on
errors no ZIP is built (`--force` forces it anyway, not recommended). The run also
warns when a used section is below the recommended "rich demo" volume
(`engine/volume.py`, see `skills/odoo-demo-data/reference/spec-format.md`) - a
warning never blocks the build.

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

For a **real customer**, write the spec to any path under `examples/` (it is
gitignored automatically) and commit only an anonymized copy named
`examples/muster_<topic>.json` with a fictional company name.

Copy `examples/muster_foerdertechnik.json` (manufacturing customer) or
`examples/muster_handel.json` (multi-app/Enterprise) as a template. Covers the verified
object types: `res.company` (incl. chart of accounts), `res.partner`,
`product.product`, `mrp.bom`, `mrp.production`, `sale.order`,
`sale.order.template` (quotation templates), `crm.lead`, `purchase.order`,
`stock.quant`/`stock.warehouse`, `account.move`, `helpdesk.ticket`,
`project.project`/`project.task` (incl. task stages).
Complete format: `skills/odoo-demo-data/reference/spec-format.md`.
Unknown fields are rejected on load (typo protection).

Every generated module creates, besides the administrator, a demo login
`demo`/`demo` (name = company, same rights as `base.user_admin`) in the
`post_init_hook` - no manual user setup after a demo appointment. If the login
already exists, creation is skipped (verified-patterns 4.18).

## Local test instance

The installation smoke test targets a local Odoo 20 Enterprise (trial) instance
in `../odoodemo-local-20` (outside this repo). There is no official `odoo:20.0`
Docker image yet, so that instance is built from source on top of the `odoo:19.0`
base image. Setup and usage: [engine/docker/README.md](engine/docker/README.md).

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
  volume.py         recommended minimum demo-data volume per object type
  verify.py         spec-aware Postgres assertions for the install smoke test
  cli.py            CLI (generate / validate / capabilities / new / spec-schema)
  spec/spec.schema.json  generated JSON schema of the customer specification
  tests/           engine tests (no Odoo needed)
  docker/          installation smoke-test harness against the local Enterprise
                   instance ../odoodemo-local-20 (see its README)
skills/odoo-demo-data/   skill: workflow + reference (verified-patterns, spec-format, ...)
opencode.json/.opencode/ opencode adapter (registers skills/, /new-demo command)
examples/                anonymized example specifications (real specs are gitignored)
examples/reference/      historical reference modules (no longer a template)
.githooks/pre-commit     blocks committing non-anonymized specs (enable: see Setup)
```

## Known limitation

`engine/validate.py` only checks structure (well-formedness, xmlid references,
manifest consistency and the known landmines from
`skills/odoo-demo-data/reference/verified-patterns.md`). It is **no** substitute
for a real installation against an Odoo 20.0 kernel - for that see
`skills/odoo-demo-data/reference/install-test-protocol.md`.
