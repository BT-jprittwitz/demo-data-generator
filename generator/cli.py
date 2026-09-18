"""Generator-CLI: JSON-Kundenspezifikation -> installierbares Odoo-Modul-ZIP.

Nur Python-Stdlib (kein pip install noetig) - siehe README.md im Repo-Root.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from .builder import write_module_dir, zip_module_dir
from .model import SpecError
from .spec_loader import load_spec
from .validate import validate_module


def cmd_generate(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
        spec = load_spec(data)
    except SpecError as e:
        print(f"Spezifikation ungueltig: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"{spec_path}: kein gueltiges JSON ({e})", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    module_dir = write_module_dir(spec, out_dir)

    findings = validate_module(module_dir)
    errors = [f for f in findings if f.level == "error"]
    for f in findings:
        print(f, file=sys.stderr if f.level == "error" else sys.stdout)

    if errors and not args.force:
        print(
            f"\n{len(errors)} Fehler gefunden - ZIP wird NICHT gebaut. "
            f"Mit --force trotzdem bauen (nicht empfohlen).",
            file=sys.stderr,
        )
        return 1

    zip_path = zip_module_dir(module_dir, out_dir / f"{spec.module.technical_name}.zip")
    print(f"\nModul gebaut: {zip_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    target = Path(args.module)
    with TemporaryDirectory() as tmp:
        if target.is_file() and target.suffix == ".zip":
            with zipfile.ZipFile(target) as zf:
                zf.extractall(tmp)
            candidates = [p for p in Path(tmp).iterdir() if p.is_dir()]
            if len(candidates) != 1:
                print(f"{target}: erwarte genau ein Modulverzeichnis im ZIP, gefunden: {len(candidates)}", file=sys.stderr)
                return 1
            module_dir = candidates[0]
        else:
            module_dir = target

        findings = validate_module(module_dir)

    errors = [f for f in findings if f.level == "error"]
    for f in findings:
        print(f, file=sys.stderr if f.level == "error" else sys.stdout)
    if not findings:
        print("Keine Befunde.")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generator", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Kundenspezifikation (JSON) zu Modul-ZIP bauen")
    p_gen.add_argument("--spec", required=True, help="Pfad zur Kunden-JSON-Spezifikation")
    p_gen.add_argument("--out", default="dist", help="Zielverzeichnis (default: dist/)")
    p_gen.add_argument("--force", action="store_true", help="ZIP trotz Validierungsfehlern bauen")
    p_gen.set_defaults(func=cmd_generate)

    p_val = sub.add_parser("validate", help="Bestehendes Modul (Verzeichnis oder ZIP) statisch pruefen")
    p_val.add_argument("module", help="Pfad zum Modulverzeichnis oder .zip")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
