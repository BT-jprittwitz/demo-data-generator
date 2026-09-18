# Odoo Demo-Daten-Generator — Kontext & Handover

Stand: 18.09.2026 (Engine-Aufbau in Claude Code ergänzt, siehe Abschnitt 5/6/8). Zweck dieses Dokuments: gesamten Kontext, verifizierte technische Learnings und aktuellen Aufbau festhalten, damit unabhängig vom genutzten Tool (Cowork, Claude Code, o.a.) nahtlos weitergearbeitet werden kann.

Dieses Dokument liegt jetzt in einem Git-Repo (siehe [README.md](README.md) für die Engine selbst). Frühere Kopien dieses Dokuments hiessen `odoo-demo-data-generator.md` — gleicher Inhalt, hier unter dem kanonischen Namen `HANDOVER.md` weitergeführt.

## 1. Ziel

Für grosse Odoo-Sales-Demos kundenspezifische Demo-Daten generieren und als installierbares Odoo-Modul (ZIP) ausliefern — ohne manuelles Anlegen von Kontakten/Produkten/Stücklisten/Angeboten in der Zielinstanz.

Endziel (Roadmap, noch nicht gebaut):
- Julius gibt nur den Kundennamen ein.
- Claude recherchiert das Unternehmen und leitet selbst ab, welches Demo-Datenprofil sinnvoll ist (z.B. produzierend → Stücklisten/Equipment/Fertigung; SaaS → Subscriptions/Wartungsprodukte). Rückfragen nur wenn wirklich nötig.
- Aufruf über einen wiederverwendbaren Skill, minimale Friktion.
- Da Zielinstanzen oft schon ein anderes Demo-Datenpaket haben: jedes generierte Paket legt eine **eigene `res.company`** an (Kundenname, Adresse, möglichst viele echte Daten) und schlüsselt alle Demo-Daten auf diese Company.

Bewusst **ausserhalb des Scopes**: Rechnungen/Buchhaltungsdaten (zu stark abhängig vom Kontenrahmen der Zielinstanz) und Fertigungsaufträge (`mrp.production`, weil `picking_type_id` vom Warehouse-Setup der Zielinstanz abhängt — gleiche Abhängigkeitsklasse wie Kontenrahmen-Referenzen).

## 2. Formalia

- Technical Name des Moduls: kurz halten (Beispiel: `bt_demo_mfg`).
- Author: immer `"braintec"`.
- License: `LGPL-3`.
- Website: `https://www.braintec.com`.

## 3. Harte Arbeitsregel (nicht verhandelbar)

**Nie Odoo-Feldnamen oder -Verhalten raten.** Vor jeder XML-Generierung gegen den echten Odoo-Source verifizieren: `github.com/odoo/odoo`, Branch/Tag passend zur Zielversion (hier: `19.0`). Konkret heisst das: Feldnamen, `create()`/`write()`-Overrides und Business-Logik-Seiteneffekte im Source nachlesen, bevor ein Feld gesetzt wird — nicht aus der Doku oder aus Erinnerung ableiten.

Bei einem Installationsfehler: **immer den vollständigen Traceback anfordern**, bevor ein zweiter Fix-Versuch unternommen wird. Ein Fix ohne vollständigen Traceback ist Raten.

Grund: `_load_records_create()` (odoo/tools/convert.py) ruft beim Laden von Demo-/Daten-XML die **echte ORM-`create()`-Methode** auf — inklusive aller Overrides installierter Module. Das kann echte Geschäftslogik auslösen (Lagerbuchungen, Projekt-Erzeugung, etc.), abhängig von gesetzten Feldwerten, insbesondere Status-/State-Feldern.

## 4. Verifizierte technische Learnings (Odoo 19.0)

### 4.1 `product.product` — nur EIN Record pro Produkt

`product.product` erbt per `_inherits = {'product.template': 'product_tmpl_id'}` (Delegation) von `product.template`. Ein einzelner `product.product`-Record mit den Template-Feldern direkt gesetzt (`name`, `type`, `list_price`, ...) legt das Template automatisch mit an.

**Fehler, den das verursacht, wenn man es falsch macht:** separates `product.template` UND `product.product` (mit `product_tmpl_id=ref(template)`) anlegen erzeugt zwei Varianten für dieselbe attributlose Kombination → `psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "product_product_combination_unique"`.

Richtiges Muster:
```xml
<record id="product_fin_conveyor" model="product.product">
    <field name="name">Foerderbandanlage FB-2000</field>
    <field name="type">consu</field>
    <field name="is_storable">True</field>
    <field name="sale_ok">True</field>
    <field name="purchase_ok">False</field>
    <field name="list_price">18500.00</field>
    <field name="standard_price">0.0</field>
    <field name="company_id" ref="demo_company" />
</record>
```

### 4.2 `mrp.bom.product_tmpl_id` aus einer `product.product`-xmlid ableiten

`mrp.bom.product_tmpl_id` braucht eine `product.template`-ID. Wenn nur eine `product.product`-xmlid existiert (siehe 4.1 — kein separates Template-Record!), liefert der offizielle `convert.py`-Mechanismus (`obj()`/`ref()`) die Lösung: das `model`-Attribut auf `<field>` bindet `obj()` an dieses Modell, danach normale Feldnavigation im `eval`.

```xml
<record id="bom_fin_conveyor" model="mrp.bom">
    <field name="product_tmpl_id" model="product.product" eval="obj(ref('product_fin_conveyor')).product_tmpl_id.id" />
    <field name="product_qty">1.0</field>
    <field name="product_uom_id" ref="uom.product_uom_unit" />
    <field name="type">normal</field>
    <field name="bom_line_ids" eval="[
        (0, 0, {'product_id': ref('product_comp_steel'), 'product_qty': 6.0, 'product_uom_id': ref('uom.product_uom_unit')}),
        (0, 0, {'product_id': ref('product_comp_motor'), 'product_qty': 1.0, 'product_uom_id': ref('uom.product_uom_unit')})
    ]" />
    <field name="company_id" ref="demo_company" />
</record>
```

### 4.3 `sale.order.state` — Vorsicht bei `state='sale'` in Demo-XML

States: `draft` (Angebot), `sent` (Angebot versendet), `sale` (Auftrag), `cancel`.

**Fehler:** `state='sale'` direkt in Demo-XML gesetzt löst für Order-Lines mit `product_id.type == 'consu'` `sale_stock`'s `_action_launch_stock_rule()` aus (echte Beschaffungslogik via ORM-`create()`-Override) → `UserError: No rule has been found to replenish "..." in "Customers"`, weil eine frisch angelegte Company kein konfiguriertes Warehouse/Route hat.

Sichere Werte für Beispielaufträge in Demo-XML: `draft` oder `sent`. `sent` wurde gewählt (wirkt für eine Demo-Pipeline realistischer als `draft`).

**Verallgemeinerte Lehre:** Jedes Status-/State-Feld, das direkt in Demo-XML gesetzt wird, kann echte Geschäftslogik aus **irgendeinem** installierten Modul triggern (nicht nur die drei bereits bekannten Abhängigkeitsklassen: Kontenrahmen, `picking_type_id`, Stock-Routen). Vor dem Setzen eines "fortgeschrittenen" Statuswerts immer prüfen, ob ein `create()`/`write()`-Override im Ziel-Modell (oder in einem abhängigen Modul) daran hängt.

### 4.4 `res.company.create()` — automatische Partner-Erzeugung

`res.company.create()` legt automatisch einen passenden `res.partner` an und übernimmt dabei `name`, `vat`, `email`, `phone`, `website`, `country_id` — **nicht** `street`/`city`/`zip` direkt (das sind compute+inverse-Felder auf `res.company`, die beim Setzen auf den Partner durchgeschrieben werden, funktionieren also trotzdem, wenn man sie auf der Company setzt).

```xml
<record id="demo_company" model="res.company">
    <field name="name">Muster Foerdertechnik AG</field>
    <field name="street">Werkstrasse 3</field>
    <field name="city">St. Gallen</field>
    <field name="zip">9000</field>
    <field name="country_id" ref="base.ch" />
    <field name="vat">CHE-100.200.300</field>
    <field name="currency_id" ref="base.CHF" />
</record>
```

### 4.5 `res.company.create()` — Company-Sichtbarkeit für den Admin-User (wichtiger Bugfix, real aufgetreten)

**Beobachtetes Problem:** Nach fehlerfreier Installation waren fast keine Daten in der UI sichtbar (nur ein Kontakt), obwohl alles korrekt in der DB angelegt wurde. Ursache, vom User selbst diagnostiziert: der UI-Login-Admin (`base.user_admin`) hatte die neue Company nicht in `company_ids` — company-geschlüsselte Daten sind für einen User ohne passenden `company_ids`-Eintrag unsichtbar, obwohl sie existieren.

**Root Cause, verifiziert gegen `odoo/addons/base/models/res_company.py`, `create()`:**
```python
self.env.registry.clear_cache()
companies = super().create(vals_list)

# The write is made on the user to set it automatically in the multi company group.
if companies:
    (self.env.user | self.env['res.users'].browse(SUPERUSER_ID)).write({
        'company_ids': [Command.link(company.id) for company in companies],
    })
```
Odoo trägt die neue Company nur bei **`self.env.user`** (dem User, der den `create()`-Call tatsächlich ausführt — bei automatisierter/serverseitiger Installation i.d.R. ein technischer User, nicht der spätere UI-Login) und bei **`SUPERUSER_ID`** (uid=1, OdooBot) in `company_ids` ein. Der normale UI-Login-Admin (`base.user_admin`, üblicherweise uid=2) wird dabei **nicht** automatisch berücksichtigt.

**Fix:** `post_init_hook`, der `base.user_admin` explizit in `company_ids` einträgt und als aktive Company setzt.

`__manifest__.py`:
```python
"post_init_hook": "post_init_hook",
```

`__init__.py`:
```python
from .hooks import post_init_hook
```

`hooks.py`:
```python
# -*- coding: utf-8 -*-
from odoo.fields import Command


def post_init_hook(env):
    """Traegt den UI-Login-Admin (base.user_admin) explizit in company_ids der neu
    angelegten Demo-Company ein und setzt sie als seine aktive Company, damit alle
    Demo-Daten direkt nach der Installation ohne manuellen Zwischenschritt sichtbar sind."""
    company = env.ref("bt_demo_mfg.demo_company", raise_if_not_found=False)
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if not company or not admin:
        return
    admin.write({
        "company_ids": [Command.link(company.id)],
        "company_id": company.id,
    })
```

Wichtig: korrekter Import ist `from odoo.fields import Command`, **nicht** `from odoo import Command` (verifiziert — `odoo/__init__.py` exportiert `Command` nicht auf Top-Level; core-Addons importieren durchgängig aus `odoo.fields`).

`post_init_hook`-Signatur in 19.0 verifiziert gegen `odoo/modules/loading.py`:
```python
post_init = package.manifest.get('post_init_hook')
if post_init:
    getattr(py_module, post_init)(env)
```
→ Signatur ist `def post_init_hook(env):` (kein `(cr, registry)` mehr wie in älteren Versionen).

**Offener Punkt / nächster Schritt:** Falls Demo-Instanzen mit mehreren Usern getestet werden, ggf. alle internen Odoo-User statt nur `base.user_admin` in `company_ids` aufnehmen — bisher nur mit dem Standard-Admin-Login verifiziert.

### 4.6 Sackgasse: Server Actions zum Dateizugriff

Versuch, per Odoo Server Action (Execute Python Code) eine Datei serverseitig zu lesen, um Deployment-Infos zu bekommen — funktioniert nicht:
- `with`-Statements sind im `safe_eval`-Sandbox verboten (`forbidden opcode(s): WITH_EXCEPT_START, BEFORE_WITH`).
- Auch ohne `with`: `open()` ist als Builtin komplett blockiert (`NameError: name 'open' is not defined`).

→ Für Zugriff auf Deployment-Dateien/-Logs den Weg über die Coolify-Konsole/Terminal nehmen, nicht über Odoo Server Actions.

### 4.7 `standard_price` ist `company_dependent` — braucht expliziten `allowed_company_ids`-Context (kritischer, real vorhandener Bug im bisherigen `bt_demo_mfg.zip`)

**Verifiziert gegen `odoo/orm/fields.py`** (Branch 19.0 — in 19.0 liegt die Field-Basisklasse unter `odoo/orm/fields.py`, nicht mehr unter dem alten Top-Level-`odoo/fields.py`; `odoo/fields/__init__.py` re-exportiert nur noch): `product.product.standard_price` ist `company_dependent=True` (`odoo/addons/product/models/product_product.py`). Company-dependent Felder werden nicht mehr über `ir.property` gespeichert, sondern direkt als `jsonb`-Spalte, keyed per Company-ID. Entscheidend, `convert_to_column_insert()`:

```python
return PsycopgJson({record.env.company.id: value})
```

Der Key ist **`record.env.company.id`** — das ist **nicht** das `company_id`-Feld, das man auf dem Record selbst setzt, sondern die *aktuell aktive Company der Umgebung*, in der der `create()`-Call läuft. `env.company` (verifiziert gegen `odoo/orm/environments.py`) fällt ohne `allowed_company_ids`-Context-Key auf `self.user.company_id` zurück — beim Laden von Demo-XML also auf die Company der ausführenden Installationsumgebung, **nicht** auf die neu angelegte Demo-Company.

**Fehler, den das verursacht:** `<field name="standard_price">38.5</field>` auf einem `product.product`-Record ohne weiteren Kontext speichert `38.5` gegen die *falsche* Company. Beim Betrachten des Produkts unter der neuen Demo-Company (nach dem Company-Visibility-Fix aus 4.5!) erscheint der Cost-Wert als nicht gesetzt/Fallback — der Wert scheint zu "verschwinden", obwohl der Insert fehlerfrei durchlief. **Das bisher ausgelieferte `bt_demo_mfg.zip` hat diesen Bug** (alle 7 Produkte setzen `standard_price` ohne Context) — ist nie aufgefallen, weil 4 der 7 Produkte `standard_price=0.0` gesetzt hatten (Zufallstreffer mit dem Fallback-Wert) und die übrigen 3 (Fertigprodukte/Service) ebenfalls `0.0`. Erst mit *echten* Kosten-Werten (Priorität 1, s. Abschnitt 8) wird der Bug sichtbar.

**Fix, verifiziert gegen `odoo/tools/convert.py`:** Ein `context="..."`-Attribut direkt auf dem `<record>`-Tag wird von `xml_import.get_env()` ausgewertet (inkl. `ref()` im `safe_eval`-Kontext) und auf die für diesen Record verwendete `env` angewendet, *bevor* `create()` aufgerufen wird:

```xml
<record id="product_comp_steel" model="product.product"
        context="{'allowed_company_ids': [ref('demo_company')]}">
    <field name="standard_price">38.5</field>
    ...
</record>
```

`env.company` liest `allowed_company_ids` ohne Sudo-Check (`env.company`-Docstring: *"No sanity checks applied in sudo mode"*) — die Demo-XML-Ladeumgebung läuft mit Sudo, also kein `AccessError`, obwohl die neue Company zu diesem Zeitpunkt noch nicht in `company_ids` des installierenden Users steht.

**Verallgemeinerte Lehre:** Jedes `company_dependent=True`-Feld (nicht nur `standard_price` — z.B. potenziell Steuer-/Pricing-bezogene Felder in anderen Modulen) muss beim Setzen in Demo-XML mit `context="{'allowed_company_ids': [ref('<company_xmlid>')]}"` auf dem `<record>` gewrappt werden, sonst landet der Wert gegen die falsche Company. `list_price` (auf `product.template`) ist **nicht** company_dependent — dort ist kein Wrapping nötig (verifiziert: plain `fields.Float`, kein `company_dependent`-Flag).

Die Generator-Engine (siehe Abschnitt 5) macht dieses Wrapping automatisch, sobald `standard_price` in der Produkt-Spezifikation gesetzt ist, und `generator/validate.py` schlägt fehl, falls ein `product.product`-Record `standard_price` ohne diesen Context enthält.

### 4.8 `--test-enable` NICHT für den Installations-Smoketest (real passiert)

**Beobachtetes Problem:** Der erste echte Installationslauf gegen den lokalen Docker-Kernel (`docker compose run --rm odoo odoo -i bt_demo_mfg --stop-after-init --test-enable -d test_bt_demo_mfg`) wirkte wie ein Hänger und wurde abgebrochen. Ursache: `--test-enable` führt die Test-Suites **aller** installierten Module aus, nicht nur die des angegebenen Moduls — im Log 998 base-Tests (`odoo.addons.base.tests.*`) plus `sale_mrp`-Tests, Laufzeit ~3,5 min, inkl. Dutzender `ERROR`-Zeilen aus `odoo.addons.base.tests.test_cli` (Docker-/CLI-Umgebungsartefakt). Das sind **keine** Fehler unseres Moduls.

**Fix:** Für den Smoketest `--test-enable` weglassen. `bt_demo_mfg` hat selbst keine Tests. Richtig (siehe `docker/README.md`, `AGENTS.md`):

```bash
docker compose run --rm odoo odoo -i bt_demo_mfg --stop-after-init -d test_bt_demo_mfg
```

**Verifiziert (18.09.2026, Odoo 19.0-20260908):** Lauf ohne `--test-enable` → `Module bt_demo_mfg loaded in 0.29s`, exit 0, kein Traceback. Postgres-Gegenprobe: Company `Muster Foerdertechnik AG` (id 156) angelegt; `standard_price` liegt als `{"156": 38.5}` etc. (4.7-Fix wirkt); `base.user_admin` hat `company_ids = {1,156}` und aktive Company 156 (4.5-Fix wirkt); 4 `sale.order` (1 `draft`, 3 `sent`, company 156), 2 `mrp.bom`, 7 `product.product`. Wichtig: vor einem frischen Lauf die Test-DB verwerfen (`DROP DATABASE IF EXISTS test_bt_demo_mfg;`), sonst lädt Odoo nur die bestehende DB und installiert nicht neu.

**Verallgemeinerte Lehre:** `--test-enable` ist ein CI-Werkzeug für die Testsuche, nicht für Installations-Smoketests. "Hängt scheinbar" zuerst gegen das Log prüfen, bevor abgebrochen wird — der Modul-Install-Teil ist daran erkennbar (`Loading module <name>`, `Module <name> loaded in ...`).

## 5. Aktueller Modul-Aufbau (Referenz: `bt_demo_mfg`, "produzierender Kunde")

```
bt_demo_mfg/
  __init__.py                     # from .hooks import post_init_hook
  __manifest__.py
  hooks.py                        # post_init_hook (siehe 4.5)
  data/
    res_company_data.xml          # 1x res.company (Kunde)
    res_partner_data.xml          # 3x res.partner, company_id=demo_company
    product_data.xml              # 7x product.product (4 Komponenten, 2 Fertigprodukte, 1 Dienstleistung)
    mrp_bom_data.xml              # 2x mrp.bom fuer die Fertigprodukte
    sale_order_quotation_data.xml # 1x sale.order state=draft, 1 Zeile je Produktart, ausfuehrliche Beschreibungstexte
    sale_order_examples_data.xml  # 3x sale.order state=sent, unterschiedliche Partner/Produkte
```

`__manifest__.py`:
```python
# -*- coding: utf-8 -*-
{
    "name": "Demo Data - Produzierender Kunde (Company, Stueckliste, Angebote, Auftraege)",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "summary": "Proof-of-concept: eigene Company, Kontakte, Produkte, Stuecklisten, Angebotsvorlage, Beispielauftraege",
    "description": """...""",
    "author": "braintec",
    "website": "https://www.braintec.com",
    "depends": ["sale_management", "mrp"],
    "data": [
        "data/res_company_data.xml",
        "data/res_partner_data.xml",
        "data/product_data.xml",
        "data/mrp_bom_data.xml",
        "data/sale_order_quotation_data.xml",
        "data/sale_order_examples_data.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}
```

**Update (Engine-Aufbau, siehe README.md):** Das Modul wird nicht mehr über ein Wegwerf-Skript pro Iteration gebaut, sondern über eine wiederverwendbare Generator-Engine in diesem Repo (`generator/`, reines Python-Stdlib, kein `pip install` nötig):

```bash
python3 -m generator.cli generate --spec examples/muster_foerdertechnik.json --out dist
python3 -m generator.cli validate reference/bt_demo_mfg.zip
```

Ablauf: JSON-Kundenspezifikation (`examples/muster_foerdertechnik.json` als Vorlage) → `generator/spec_loader.py` lädt sie in Dataclasses (`generator/model.py`, inkl. Validierung der Spezifikation selbst: unsichere `sale.order`-States, unbekannte `product.type`-Werte, doppelte Barcodes, hängende Referenzen werden mit klarer Fehlermeldung abgelehnt) → `generator/records.py` baut daraus die XML-Record-Elemente exakt nach den in Abschnitt 4 verifizierten Mustern (inkl. automatischem `allowed_company_ids`-Context-Wrapping für `standard_price`, siehe 4.7) → `generator/builder.py` schreibt Modulverzeichnis + ZIP → `generator/validate.py` prüft vor dem Ausliefern statisch (XML-Wohlgeformtheit, Manifest-Konsistenz, xmlid-Referenzen, die drei bekannten Landminen aus 4.1/4.3/4.7).

Deckt bewusst nur die hier in Abschnitt 4 verifizierten Objektarten ab (`res.company`, `res.partner`, `product.product`, `mrp.bom`, `sale.order`) — kein Baustein für weitere Objektarten, solange kein konkreter Kunde das braucht (siehe Abschnitt 8).

Echte Installationstests gegen einen laufenden Odoo-19.0-Kernel sind vorbereitet (`docker/`), auf der Entwicklungsmaschine aber mangels Docker noch nicht ausführbar — siehe `docker/README.md` für den vorgesehenen Ablauf, sobald eine Maschine mit Docker (z.B. CI-Runner) zur Verfügung steht. Bis dahin bleibt eine echte Installation manuell (Upload + vollständiger Traceback bei Fehlern, harte Arbeitsregel Abschnitt 3).

## 6. Historie der gelieferten Module

1. `bt_demo_example_skr04.zip` — erster PoC, an das SKR04-Beispiel des Kollegen angelehnt (8 Partner, 10 Produkte, Rechnungen). **Superseded**, Rechnungen/Buchhaltung inzwischen bewusst aus Scope genommen.
2. `bt_demo_example_manufacturing.zip` — zweiter PoC, produzierender Kunde. **Buggy**: enthielt den `product.template` + `product.product`-Doppel-Record-Fehler (4.1) und `state='sale'`-Fehler (4.3). Nicht mehr verwenden.
3. `bt_demo_mfg.zip` — installierbar, inkl. Company-Visibility-Fix (4.5). Erfolgreich auf `moduletesting.odoodemo4.braintec.io` installiert (Coolify-Deployment, Repo-Pfad `bt-project-template/ext/odoo_apps/bt_demo_mfg/`). **Nachträglich gefundener Bug (4.7):** alle 7 Produkte setzen `standard_price` ohne `allowed_company_ids`-Context — die Cost-Werte der 4 Komponenten (38.5/410.0/620.0/22.0) landen dadurch vermutlich gegen die falsche Company. Als historische Referenz im Repo belassen (`reference/bt_demo_mfg.zip`), aber **nicht mehr als Vorlage verwenden** — `python3 -m generator.cli validate reference/bt_demo_mfg.zip` zeigt den Fehler.
4. Ab hier: Generator-Engine in diesem Repo (siehe Abschnitt 5, README.md). `examples/muster_foerdertechnik.json` reproduziert denselben Kunden wie `bt_demo_mfg.zip`, korrigiert den 4.7-Bug und ergänzt Stammdaten-Tiefe (interne Referenz, Barcode, Gewicht, Verkaufsbeschreibung) gemäss Priorität 1 (Abschnitt 8).

## 7. Referenzmaterial

Als Vorbild diente ein Modul eines Kollegen (Felix Schubert) für DE-Buchhaltungs-Demodaten (SKR04-Kontenrahmen): `demo_v19_data_skr04_clean/` (45 Partner, Rechnungen) und `l10n_de_skr04_demo_assets_loans/` (Anlagen/Darlehen). Nur als Strukturvorbild verwendet, nicht verändert oder wiederverwendet — der aktuelle Ansatz lässt Buchhaltungsdaten bewusst aussen vor (siehe Abschnitt 1).

## 8. Priorisierung & offene Roadmap-Punkte

**Priorität 1 (erledigt, siehe Abschnitt 5):** Stammdaten-Tiefe der bestehenden Produkte — Kosten (`standard_price`, korrekt mit Company-Context, siehe 4.7), interne Referenz (`default_code`), sowie Barcode, Gewicht (`weight`), Volumen (`volume`) und Verkaufsbeschreibung (`description_sale`) als weitere verifizierte, optionale Felder in `generator/model.py`. Bewusst **keine** neuen Objektarten dafür (kein `product.category`, keine neuen Record-Typen) — "bedarfsgetriebenes Wachstum": ein Baustein für eine Objektart entsteht erst, wenn ein konkreter Kunde ihn braucht, nicht auf Vorrat.

**Noch offen / nicht gebaut:**

- **Web-Recherche-Automatik:** Aus einem Kundennamen automatisch Branche/Grösse/Geschäftsmodell ableiten und daraus das passende Demo-Datenprofil bestimmen (SaaS → Subscriptions/Wartung; produzierend → Stücklisten/Equipment; weitere Archetypen nach Bedarf).
- **Multi-User-Sichtbarkeit:** `post_init_hook` ggf. auf mehrere/alle relevanten User statt nur `base.user_admin` ausweiten, falls Demo-Instanzen mit mehreren Logins getestet werden.
- **Echte Installationstests vor Auslieferung:** `docker/` ist vorbereitet (Odoo 19.0 + Postgres via docker-compose), aber auf der Entwicklungsmaschine mangels Docker nicht ausführbar. Nächster Schritt, sobald eine Maschine mit Docker verfügbar ist: das in `docker/README.md` skizzierte `test_install.py`-Skript, das die Installation automatisiert und bei Fehlern den vollständigen Traceback liefert.
- **SaaS-Archetyp** (Subscriptions, Wartungsprodukte) ist bisher nur konzeptionell benannt, nicht umgesetzt — nur der produzierende Archetyp (BOM/Equipment) wurde gebaut. Nicht vorbauen, bis ein SaaS-Kunde ansteht (bedarfsgetriebenes Wachstum).

## 9. Einschätzung: Cowork vs. Claude Code für die nächsten Iterationen

**Für die Weiterentwicklung des Generators (Engineering-Seite) spricht einiges für einen echten Git-Repo-Workflow (Claude Code oder gleichwertig):**
- Aktuell wird jedes Modul in einem Wegwerf-Skript in einem Sandbox-Scratchpad gebaut, das nicht über Sessions hinweg persistiert — jede Iteration beginnt de facto wieder bei null, wenn man nicht wie hier ein Handover-Dokument schreibt.
- Der bisherige Fehlerzyklus (XML schreiben → auf die echte Coolify-Zielinstanz hochladen → RPC-Traceback abwarten → Nutzer bittet um Paste des Tracebacks → fixen → erneut hochladen) ist langsam und nutzt eine Kundendemo-Instanz als Testumgebung. Ein lokaler/CI-Odoo-Testcontainer, gegen den der Generator vor jeder Auslieferung automatisch installiert, hätte beide bisherigen Bugs (4.1, 4.3) sofort und ohne Umweg über den Nutzer gefunden.
- Ein echtes Repo mit Versionsgeschichte passt besser zu "wachsender Bibliothek verifizierter Odoo-Patterns", die über viele Kunden/Iterationen wiederverwendet wird, als ein Chat-Verlauf.

**Dagegen spricht:** Julius' eigentliche Rolle ist Business Development, nicht Engineering. Sein explizites Ziel ist minimale Friktion — "ich gebe den Kundennamen, fertig". Ein CLI-/Git-Tool persönlich zu bedienen widerspricht diesem Ziel eher, als es zu unterstützen. Ausserdem: lokale Maschine möglichst meiden (bestehende Präferenz) — ein containerisierter/entfernter Claude-Code-Einsatz wäre nötig, kein lokales Setup.

**Empfehlung:** Zweiteilung. Die Generator-Engine (Repo, Templates, Testautomatisierung gegen eine echte Odoo-Instanz) gehört in einen richtigen Git-Workflow — das ist eher etwas für Felix oder einen anderen Entwickler, ggf. mit Claude Code betrieben, mit diesem Dokument als Ausgangspunkt. Julius' eigene Interaktion sollte weiterhin ein einfacher Skill-Aufruf in Cowork bleiben ("generiere Demo-Paket für Kunde X"), der intern auf diese Engine zugreift oder deren Ausgabe reproduziert. Das entspricht auch der Roadmap-Anforderung aus Abschnitt 1 direkt.

**Update:** Diese Empfehlung wurde umgesetzt — die Engine liegt jetzt in diesem Git-Repo (siehe README.md), aufgebaut in Claude Code auf Basis dieses Dokuments. Julius' eigene Interaktion (Skill-Aufruf in Cowork o.ä.) ist weiterhin ein separater, noch offener Schritt (siehe Abschnitt 8, "Web-Recherche-Automatik" als Voraussetzung dafür).
