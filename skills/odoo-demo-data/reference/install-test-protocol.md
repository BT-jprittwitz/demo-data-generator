# Installation smoke test (real Odoo 19.0 kernel)

Static validation (`engine/validate.py`) does **not** replace a real
installation. Install against a real kernel before every delivery.

## Basic rules

- **No `--test-enable`.** It runs the tests of *all* modules (~3.5 min,
  many irrelevant `ERROR` lines) and looks like a hang.
- Drop the test DB before every run, otherwise only the existing DB is loaded.
- Success = `Module <name> loaded in ...`, exit 0, **no traceback**.
- Do not check the log only, but directly against Postgres.
- On error: read the complete traceback, then fix.

## Automated smoke test (recommended)

`engine/docker/test_install.py` (stdlib only) automates all of the above: fresh
(uniquely named) DB per run, install, log analysis (`Traceback`/`CRITICAL` and the
`Module <name> loaded` marker), full log on failure, DB dropped on success. Success
= exit 0; failure = exit 1 with the complete log; preflight problem = exit 2.

It targets the local Enterprise instance `../odoodemo-local` (compose service
`web`) by default:

```bash
python3 -m engine.cli generate --spec examples/<customer>.json --out output
python3 engine/docker/test_install.py --module <technical_name>
```

Useful flags: `--log <path>` (write the full log), `--keep-db` (keep the DB even
on success), `--verbose` (always print the log), `--timeout <s>`, and
`--compose-dir` / `--service` for a different instance. If `--module` is omitted
and exactly one `.zip` is in `./output`, that module is used.

## Enterprise (the only supporting setup)

Prerequisite: local setup `../odoodemo-local` (Odoo 19.0 Enterprise trial via
Docker, mounts `<this repo>/output` as `/mnt/extra-addons`). There is no Community
setup; Enterprise modules (e.g. `helpdesk`, `account_accountant`) are always
available.

```bash
cd ../odoodemo-local
# fresh DB
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS test_<name>;"
# install
docker compose run --rm web odoo -i <technical_name> --stop-after-init -d test_<name> 2>&1 \
    | tee /tmp/<name>_install.log
grep -nE "Traceback|CRITICAL|Module <technical_name> loaded" /tmp/<name>_install.log
```

After installing into a *running* trial DB (`odoodemo_trial`), restart the server
so the UI sees the module/company:
`docker compose restart web` (then `http://localhost:8069`).

## Postgres cross-check (examples)

```bash
docker compose exec -T db psql -U odoo -d test_<name> -c "
SELECT id, name, chart_template FROM res_company ORDER BY id;

SELECT 'products' k, count(*) v FROM product_template WHERE company_id=2
UNION ALL SELECT 'invoices_posted', count(*) FROM account_move WHERE state='posted' AND company_id=2
UNION ALL SELECT 'helpdesk_tickets', count(*) FROM helpdesk_ticket WHERE company_id=2
UNION ALL SELECT 'purchase_orders', count(*) FROM purchase_order WHERE company_id=2;

SELECT 'admin_company_ids' k, string_agg(cid::text, ',' ORDER BY cid) v
  FROM res_company_users_rel WHERE user_id=2
UNION ALL SELECT 'admin_active_company', (SELECT company_id::text FROM res_users WHERE id=2);

SELECT id, default_code, standard_price FROM product_product
  JOIN product_template pt ON product_product.product_tmpl_id=pt.id
  WHERE pt.company_id=2 LIMIT 3;
"
```

Expectation: `standard_price` as `{"<demo_company_id>": <value>}` (not against the
installation company), `base.user_admin` (`user_id=2`) has both companies in
`res_company_users_rel` and its active company is the demo company.

Note: `product.product` has no own `company_id` column (delegation to
`product_template`); `SELECT * FROM product_product WHERE company_id=...` fails.
