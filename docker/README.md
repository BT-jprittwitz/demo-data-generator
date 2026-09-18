# Lokale/CI-Testinstallation (vorbereitet, noch nicht aktiv genutzt)

Status: Auf der aktuellen Entwicklungsmaschine ist kein Docker installiert. Dieses
Setup ist vorbereitet fuer den Einsatz auf einer Maschine mit Docker (z.B. ein
CI-Runner), damit vor jeder Auslieferung eine echte Installation gegen einen
frischen Odoo-19.0-Kernel laufen kann - nicht nur die statische Pruefung aus
`generator/validate.py`.

Bis dieses Setup produktiv genutzt wird, bleibt `generator validate` (rein
strukturell, siehe dortige Docstrings fuer die Grenzen) die einzige automatische
Pruefung. Ein echter Installationstest gegen eine erreichbare Instanz (z.B.
`moduletesting.odoodemo4.braintec.io`, siehe HANDOVER.md 6) bleibt bis dahin
manuell: Modul hochladen, bei Fehler den **vollstaendigen Traceback** anfordern
(harte Arbeitsregel, HANDOVER.md Abschnitt 3), erst dann fixen.

## Vorgesehener Ablauf, sobald Docker verfuegbar ist

```bash
python3 -m generator.cli generate --spec examples/muster_foerdertechnik.json --out dist
cd docker
docker compose run --rm odoo \
    odoo -i bt_demo_mfg --stop-after-init --test-enable -d test_bt_demo_mfg
```

Exit-Code und Log pruefen: ein Traceback im Log bedeutet Installationsfehler.
`--stop-after-init` verhindert, dass der Odoo-Server nach der Installation
weiterlaeuft (der Container soll nur den Installationslauf durchfuehren und
terminieren).

## Naechster Schritt, um das produktiv zu machen

Ein kleines `test_install.py`-Skript (noch nicht gebaut), das:
1. `docker compose run` mit einer frischen DB pro Lauf startet,
2. stdout/stderr auf `Traceback` / `CRITICAL` / `ERROR` durchsucht,
3. bei Fund den vollstaendigen Log zurueckgibt statt nur "Installation fehlgeschlagen",
4. bei Erfolg die DB wieder verwirft (`docker compose down -v` oder eine
   Wegwerf-DB pro Lauf).

Nicht vorab bauen, solange niemand es tatsaechlich ausfuehren kann - siehe
"bedarfsgetriebenes Wachstum" in HANDOVER.md.
