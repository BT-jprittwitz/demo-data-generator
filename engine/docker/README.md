# Installation smoke test against the local Enterprise instance

Generated modules are tested against the local Odoo 19 Enterprise (trial)
instance in `../odoodemo-local` (Docker). This repo ships **no Community setup**.

Status: the procedure is in use and verified (bt_demo_mfg, incl. the Postgres
cross-check of the company-context fixes 4.5/4.7). `engine validate` (purely
structural) remains the quick pre-check, but does not replace a real
installation.

## Prerequisite

The Enterprise instance must be running; it mounts this repo's `output/` as
`/mnt/extra-addons`:

```bash
docker compose -f ../odoodemo-local/docker-compose.yml up -d
```

## Procedure

Automated (recommended) - `test_install.py` uses a fresh DB, analyses the log and
returns the complete log on failure. It targets `../odoodemo-local` (compose
service `web`) by default:

```bash
python3 -m engine.cli generate --spec examples/muster_foerdertechnik.json --out output
python3 engine/docker/test_install.py --module bt_demo_mfg
```

Manual alternative (run from the repo root):

```bash
python3 -m engine.cli generate --spec examples/muster_foerdertechnik.json --out output
cd ../odoodemo-local
# force a fresh test DB, otherwise only the existing one is loaded:
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS test_bt_demo_mfg;"
docker compose run --rm web \
    odoo -i bt_demo_mfg --stop-after-init -d test_bt_demo_mfg
```

Check exit code and log: a traceback in the log means installation error.
`--stop-after-init` prevents the Odoo server from continuing to run after
installation (the container should only perform the installation run and
terminate).

Important: **do not** use `--test-enable` for this smoke test - it runs the
tests of *all* modules (998 base tests etc., ~3.5 min, many irrelevant
`ERROR` lines from `base.tests.test_cli`) and then looks like a hang.
`bt_demo_mfg` has no tests of its own. See also [AGENTS.md](../../AGENTS.md).

Verify not only via the log, but directly against Postgres, e.g.:

```bash
docker compose exec -T db psql -U odoo -d test_bt_demo_mfg \
    -c "SELECT id, default_code, standard_price FROM product_product;"
```

`standard_price` must be present as `{"<demo_company_id>": <value>}` (company-
context fix 4.7), not against the installation company.

## Automated smoke test (`test_install.py`)

`test_install.py` (stdlib only) starts `docker compose run` against a fresh,
uniquely named DB, scans the log for `Traceback` / `CRITICAL` and the
`Module <name> loaded` marker, prints the complete log on failure, and drops the
DB on success. Defaults: `--compose-dir ../odoodemo-local`, `--service web`
(override both for a different instance).
