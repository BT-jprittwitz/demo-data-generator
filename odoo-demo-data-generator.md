# Odoo Demo-Daten-Generator — Kontext & Handover

Stand: 18.09.2026. Zweck dieses Dokuments: gesamten Kontext, verifizierte technische Learnings und aktuellen Aufbau festhalten, damit unabhängig vom genutzten Tool (Cowork, Claude Code, o.a.) nahtlos weitergearbeitet werden kann.

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

Das Modul wird über ein Python-Generator-Skript gebaut (aktuell: einmaliges Skript pro Iteration, kein wiederverwendbares CLI — siehe Abschnitt 7, "nächste Schritte"). Muster: Listen von Tupeln (Produkte, Partner, BOM-Zeilen, Order-Zeilen) → f-strings zu XML zusammensetzen → Dateien schreiben → zippen.

## 6. Historie der gelieferten Module

1. `bt_demo_example_skr04.zip` — erster PoC, an das SKR04-Beispiel des Kollegen angelehnt (8 Partner, 10 Produkte, Rechnungen). **Superseded**, Rechnungen/Buchhaltung inzwischen bewusst aus Scope genommen.
2. `bt_demo_example_manufacturing.zip` — zweiter PoC, produzierender Kunde. **Buggy**: enthielt den `product.template` + `product.product`-Doppel-Record-Fehler (4.1) und `state='sale'`-Fehler (4.3). Nicht mehr verwenden.
3. `bt_demo_mfg.zip` — **aktuell, funktionierend, inkl. Company-Visibility-Fix (4.5)**. Erfolgreich auf `moduletesting.odoodemo4.braintec.io` installiert (Coolify-Deployment, Repo-Pfad `bt-project-template/ext/odoo_apps/bt_demo_mfg/`).

## 7. Referenzmaterial

Als Vorbild diente ein Modul eines Kollegen (Felix Schubert) für DE-Buchhaltungs-Demodaten (SKR04-Kontenrahmen): `demo_v19_data_skr04_clean/` (45 Partner, Rechnungen) und `l10n_de_skr04_demo_assets_loans/` (Anlagen/Darlehen). Nur als Strukturvorbild verwendet, nicht verändert oder wiederverwendet — der aktuelle Ansatz lässt Buchhaltungsdaten bewusst aussen vor (siehe Abschnitt 1).

## 8. Offene Roadmap-Punkte (noch nicht gebaut)

- **Web-Recherche-Automatik:** Aus einem Kundennamen automatisch Branche/Grösse/Geschäftsmodell ableiten und daraus das passende Demo-Datenprofil bestimmen (SaaS → Subscriptions/Wartung; produzierend → Stücklisten/Equipment; weitere Archetypen nach Bedarf).
- **Multi-User-Sichtbarkeit:** `post_init_hook` ggf. auf mehrere/alle relevanten User statt nur `base.user_admin` ausweiten, falls Demo-Instanzen mit mehreren Logins getestet werden.
- **Generator als wiederverwendbares Tool statt Einweg-Skript:** aktuell wird pro Iteration ein Python-Skript neu geschrieben/angepasst. Sinnvoll wäre eine Bibliothek/CLI mit: Produktarchetypen als Bausteine (Komponente/Fertigprodukt/Service/Subscription), Partner-Generatoren pro Land, eine Test-Installation gegen eine lokale/CI-Odoo-Instanz **vor** Auslieferung (siehe Abschnitt 9).
- **SaaS-Archetyp** (Subscriptions, Wartungsprodukte) ist bisher nur konzeptionell benannt, nicht umgesetzt — nur der produzierende Archetyp (BOM/Equipment) wurde gebaut.

## 9. Einschätzung: Cowork vs. Claude Code für die nächsten Iterationen

**Für die Weiterentwicklung des Generators (Engineering-Seite) spricht einiges für einen echten Git-Repo-Workflow (Claude Code oder gleichwertig):**
- Aktuell wird jedes Modul in einem Wegwerf-Skript in einem Sandbox-Scratchpad gebaut, das nicht über Sessions hinweg persistiert — jede Iteration beginnt de facto wieder bei null, wenn man nicht wie hier ein Handover-Dokument schreibt.
- Der bisherige Fehlerzyklus (XML schreiben → auf die echte Coolify-Zielinstanz hochladen → RPC-Traceback abwarten → Nutzer bittet um Paste des Tracebacks → fixen → erneut hochladen) ist langsam und nutzt eine Kundendemo-Instanz als Testumgebung. Ein lokaler/CI-Odoo-Testcontainer, gegen den der Generator vor jeder Auslieferung automatisch installiert, hätte beide bisherigen Bugs (4.1, 4.3) sofort und ohne Umweg über den Nutzer gefunden.
- Ein echtes Repo mit Versionsgeschichte passt besser zu "wachsender Bibliothek verifizierter Odoo-Patterns", die über viele Kunden/Iterationen wiederverwendet wird, als ein Chat-Verlauf.

**Dagegen spricht:** Julius' eigentliche Rolle ist Business Development, nicht Engineering. Sein explizites Ziel ist minimale Friktion — "ich gebe den Kundennamen, fertig". Ein CLI-/Git-Tool persönlich zu bedienen widerspricht diesem Ziel eher, als es zu unterstützen. Ausserdem: lokale Maschine möglichst meiden (bestehende Präferenz) — ein containerisierter/entfernter Claude-Code-Einsatz wäre nötig, kein lokales Setup.

**Empfehlung:** Zweiteilung. Die Generator-Engine (Repo, Templates, Testautomatisierung gegen eine echte Odoo-Instanz) gehört in einen richtigen Git-Workflow — das ist eher etwas für Felix oder einen anderen Entwickler, ggf. mit Claude Code betrieben, mit diesem Dokument als Ausgangspunkt. Julius' eigene Interaktion sollte weiterhin ein einfacher Skill-Aufruf in Cowork bleiben ("generiere Demo-Paket für Kunde X"), der intern auf diese Engine zugreift oder deren Ausgabe reproduziert. Das entspricht auch der Roadmap-Anforderung aus Abschnitt 1 direkt.
