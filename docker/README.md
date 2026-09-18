# Lokale/CI-Testinstallation (in Benutzung, verifiziert)

Status: Docker ist auf der Entwicklungsmaschine verfuegbar; die Installation
gegen einen frischen Odoo-19.0-Kernel wurde damit real durchgefuehrt und
verifiziert (bt_demo_mfg, inkl. Postgres-Gegenprobe der Company-Context-Fixes
4.5/4.7). `generator validate` (rein strukturell) bleibt die schnelle
Vorabpruefung, ersetzt aber keine echte Installation.

## Ablauf

```bash
python3 -m generator.cli generate --spec examples/muster_foerdertechnik.json --out dist
cd docker
# frische Test-DB erzwingen, sonst wird nur die bestehende geladen:
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS test_bt_demo_mfg;"
docker compose run --rm odoo \
    odoo -i bt_demo_mfg --stop-after-init -d test_bt_demo_mfg
```

Exit-Code und Log pruefen: ein Traceback im Log bedeutet Installationsfehler.
`--stop-after-init` verhindert, dass der Odoo-Server nach der Installation
weiterlaeuft (der Container soll nur den Installationslauf durchfuehren und
terminieren).

Wichtig: **kein** `--test-enable` bei diesem Smoketest verwenden - es fuehrt die
Tests *aller* Module aus (998 base-Tests etc., ~3,5 min, viele irrelevante
`ERROR`-Zeilen aus `base.tests.test_cli`) und sieht dann wie ein Haenger aus.
`bt_demo_mfg` hat keine eigenen Tests. Siehe auch [AGENTS.md](../AGENTS.md).

Verifikation nicht nur am Log, sondern direkt gegen Postgres, z.B.:

```bash
docker compose exec -T db psql -U odoo -d test_bt_demo_mfg \
    -c "SELECT id, default_code, standard_price FROM product_product;"
```

`standard_price` muss als `{"<demo_company_id>": <wert>}` vorliegen (Company-
Context-Fix 4.7), nicht gegen die Installations-Company.

## Naechster Schritt, um das produktiv zu machen

Ein kleines `test_install.py`-Skript (noch nicht gebaut), das:
1. `docker compose run` mit einer frischen DB pro Lauf startet,
2. stdout/stderr auf `Traceback` / `CRITICAL` / `ERROR` durchsucht,
3. bei Fund den vollstaendigen Log zurueckgibt statt nur "Installation fehlgeschlagen",
4. bei Erfolg die DB wieder verwirft (`docker compose down -v` oder eine
   Wegwerf-DB pro Lauf).

Nicht vorab bauen, solange niemand es tatsaechlich ausfuehren kann - siehe
"bedarfsgetriebenes Wachstum" in HANDOVER.md.
