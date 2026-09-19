# Local/CI test installation (in use, verified)

Status: Docker is available on the development machine; installation against a
fresh Odoo 19.0 kernel was really performed and verified with it (bt_demo_mfg,
incl. Postgres cross-check of the company-context fixes 4.5/4.7). `engine validate`
(purely structural) remains the quick pre-check, but does not replace a real
installation.

## Procedure

```bash
python3 -m engine.cli generate --spec examples/muster_foerdertechnik.json --out dist
cd engine/docker
# force a fresh test DB, otherwise only the existing one is loaded:
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS test_bt_demo_mfg;"
docker compose run --rm odoo \
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

## Next step to make this productive

A small `test_install.py` script (not built yet) that:
1. starts `docker compose run` with a fresh DB per run,
2. scans stdout/stderr for `Traceback` / `CRITICAL` / `ERROR`,
3. on a hit returns the complete log instead of just "installation failed",
4. on success drops the DB again (`docker compose down -v` or a
   throwaway DB per run).

Do not build it in advance as long as nobody can actually run it - see
"demand-driven growth" in [ROADMAP.md](../../ROADMAP.md).
