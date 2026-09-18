# Hinweise fuer Agenten (openCode/Claude Code etc.)

Kanonischer Kontext: [HANDOVER.md](HANDOVER.md). Engine-Doku: [README.md](README.md).

## Harte Regeln

- **Nie Odoo-Feldnamen/-Verhalten raten.** Vor XML-Generierung gegen den echten
  Odoo-Source (Branch 19.0) verifizieren, siehe HANDOVER.md Abschnitt 3.
- Bei Installationsfehler: **vollstaendigen Traceback** anfordern, bevor ein
  zweiter Fix versucht wird. Kein Fix ohne Traceback.
- Sprache der Doku/Kommentare: Deutsch (wie bestehende Dateien).

## Installations-Smoketest (Gelernt, real passiert)

`--test-enable` **nicht** fuer den Installations-Smoketest verwenden. Es fuehrt
die Tests **aller** installierten Module aus (998 base-Tests + sale_mrp, ~3,5 min,
Dutzende irrelevante `ERROR`-Zeilen aus `base.tests.test_cli`) statt nur unser
Modul - das sieht wie ein Haenger aus und erzeugt Fehlalarme. `bt_demo_mfg` hat
selbst keine Tests.

Richtig (siehe `docker/`):

```bash
cd docker
docker compose run --rm odoo odoo -i bt_demo_mfg --stop-after-init -d test_bt_demo_mfg
```

Vor einem frischen Lauf die Test-DB verwerfen, sonst wird nur eine bestehende DB
geladen statt neu installiert:

```bash
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS test_bt_demo_mfg;"
```

Erfolg = `Module bt_demo_mfg loaded in ...`, exit 0, kein Traceback. Verifikation
am besten direkt gegen Postgres (Company/Company-Context, siehe HANDOVER.md
4.5/4.7), nicht nur den Log.

## Tests der Engine

```bash
python3 -m unittest discover -s tests
```
