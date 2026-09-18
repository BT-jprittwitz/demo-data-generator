# Odoo Demo-Daten-Generator

Generator-Engine, die aus einer Kunden-Spezifikation (JSON) ein installierbares
Odoo-19.0-Demo-Datenmodul (ZIP) baut. Voller Kontext, verifizierte technische
Learnings und Roadmap: [HANDOVER.md](HANDOVER.md).

Nur Python-Stdlib, keine Abhaengigkeiten, kein `pip install` noetig.

## Verwendung

```bash
python3 -m generator.cli generate --spec examples/muster_foerdertechnik.json --out dist
```

Baut `dist/<technical_name>/` (Modulverzeichnis) und `dist/<technical_name>.zip`.
Vor dem Zippen laeuft automatisch die statische Validierung
(`generator/validate.py`); bei Fehlern wird kein ZIP gebaut (`--force` erzwingt
es trotzdem, nicht empfohlen).

Ein bestehendes Modul (Verzeichnis oder ZIP) unabhaengig pruefen:

```bash
python3 -m generator.cli validate reference/bt_demo_mfg.zip
```

## Eine neue Kunden-Spezifikation schreiben

`examples/muster_foerdertechnik.json` als Vorlage kopieren. Deckt die in
HANDOVER.md Abschnitt 4 verifizierten Objektarten ab: `res.company`,
`res.partner`, `product.product`, `mrp.bom`, `sale.order`. Keine anderen
Objektarten - siehe "bedarfsgetriebenes Wachstum" in HANDOVER.md: neue
Archetypen (z.B. Subscriptions fuer SaaS-Kunden) brauchen zuerst eine eigene
Verifikation gegen den Odoo-Source, bevor dafuer ein Baustein entsteht.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Repo-Struktur

```
generator/
  model.py         Datenmodell (Dataclasses) + Validierung der Spezifikation selbst
  spec_loader.py    JSON -> Dataclasses
  records.py        Dataclasses -> Odoo-XML-Record-Elemente (verifizierte Muster)
  xmlgen.py         Low-Level-XML-Helfer (ElementTree, garantiert wohlgeformt)
  manifest.py       __manifest__.py / hooks.py Rendering
  builder.py        Modulverzeichnis + ZIP zusammenbauen
  validate.py       Statische Pruefung eines gebauten Moduls (kein Odoo-Kernel noetig)
  cli.py            CLI (generate / validate)
examples/
  muster_foerdertechnik.json   Beispiel-Spezifikation (produzierender Kunde)
  tests/                          Tests fuer die Engine selbst (kein Odoo noetig)
  docker/                         Community-Installations-Smoketest (siehe dortige README)
  reference/                      Historische Referenzmodule (nicht mehr Vorlage, siehe HANDOVER.md 6)
    bt_demo_mfg.zip
```

## Bekannte Grenze

`generator/validate.py` prueft nur Struktur (Wohlgeformtheit, xmlid-Referenzen,
Manifest-Konsistenz, die drei bisher bekannten Landminen aus HANDOVER.md 4.1/4.3/4.7).
Es ist **kein** Ersatz fuer eine echte Installation gegen einen Odoo-19.0-Kernel -
das deckt nur `docker/` ab, sobald eine Maschine mit Docker verfuegbar ist.
