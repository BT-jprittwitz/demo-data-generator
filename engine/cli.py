"""Generator CLI: JSON customer specification -> installable Odoo module ZIP.

Pure Python stdlib (no pip install needed) - see README.md in the repo root.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from .builder import write_module_dir, zip_module_dir
from .bundles import BundleError, capabilities_data, render_capabilities_markdown, validate_bundles
from .model import SpecError
from .scaffold import build_skeleton, to_json
from .schema import write_schema
from .spec_loader import load_spec
from .validate import check_spec_relatability, validate_module
from .volume import check_data_volume


def cmd_generate(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
        spec = load_spec(data)
    except SpecError as e:
        print(f"Invalid specification: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"{spec_path}: not valid JSON ({e})", file=sys.stderr)
        return 1

    for finding in check_data_volume(spec):
        print(finding, file=sys.stderr if finding.level == "error" else sys.stdout)

    out_dir = Path(args.out)
    module_dir = write_module_dir(spec, out_dir)

    findings = validate_module(module_dir)

    # Spec-level relatability guardrail (placeholders, generic catalog) - see
    # engine/validate.py check_spec_relatability.
    findings = check_spec_relatability(spec) + findings
    errors = [f for f in findings if f.level == "error"]
    for f in findings:
        print(f, file=sys.stderr if f.level == "error" else sys.stdout)

    if errors and not args.force:
        print(
            f"\n{len(errors)} errors found - ZIP will NOT be built. "
            f"Use --force to build anyway (not recommended).",
            file=sys.stderr,
        )
        return 1

    zip_path = zip_module_dir(module_dir, out_dir / f"{spec.module.technical_name}.zip")
    print(f"\nModule built: {zip_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    target = Path(args.module)
    with TemporaryDirectory() as tmp:
        if target.is_file() and target.suffix == ".zip":
            with zipfile.ZipFile(target) as zf:
                zf.extractall(tmp)
            candidates = [p for p in Path(tmp).iterdir() if p.is_dir()]
            if len(candidates) != 1:
                print(f"{target}: expected exactly one module directory in the ZIP, found: {len(candidates)}", file=sys.stderr)
                return 1
            module_dir = candidates[0]
        else:
            module_dir = target

        findings = validate_module(module_dir)

    errors = [f for f in findings if f.level == "error"]
    for f in findings:
        print(f, file=sys.stderr if f.level == "error" else sys.stdout)
    if not findings:
        print("No findings.")
    return 1 if errors else 0


def cmd_spec_schema(args: argparse.Namespace) -> int:
    path = write_schema(Path(args.out))
    print(f"Spec schema written: {path}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    selected = [b for chunk in args.bundles for b in chunk.split(",") if b]
    try:
        skeleton = build_skeleton(
            selected,
            name=args.name,
            country=args.country,
            street=args.street,
            city=args.city,
            zip_code=args.zip_code,
            vat=args.vat,
            currency_xmlid=args.currency,
            chart_template=args.chart_template,
            language=args.language,
            technical_name=args.technical_name,
        )
    except BundleError as e:
        print(f"Invalid bundle selection: {e}", file=sys.stderr)
        print("List the known bundles: python3 -m engine.cli capabilities", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else Path("examples") / f"{skeleton['module']['technical_name']}.json"
    if out.exists() and not args.force:
        print(f"{out} exists - use --force to overwrite.", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(skeleton), encoding="utf-8")
    print(f"Spec skeleton written: {out}")
    if "invoices" in skeleton and not skeleton["company"].get("chart_template"):
        print(
            "note: 'accounting' selected but no --chart-template set - invoices need a chart of accounts.",
            file=sys.stderr,
        )
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    problems = validate_bundles()
    for problem in problems:
        print(f"bundle definition problem: {problem}", file=sys.stderr)
    if problems:
        return 1
    if args.json:
        print(json.dumps({"bundles": capabilities_data()}, ensure_ascii=False, separators=(",", ":")))
        return 0
    markdown = render_capabilities_markdown()
    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"Capabilities written: {args.out}")
    else:
        print(markdown)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Build a customer specification (JSON) into a module ZIP")
    p_gen.add_argument("--spec", required=True, help="Path to the customer JSON specification")
    p_gen.add_argument("--out", default="output", help="Target directory (default: output/)")
    p_gen.add_argument("--force", action="store_true", help="Build the ZIP despite validation errors")
    p_gen.set_defaults(func=cmd_generate)

    p_val = sub.add_parser("validate", help="Statically validate an existing module (directory or ZIP)")
    p_val.add_argument("module", help="Path to the module directory or .zip")
    p_val.set_defaults(func=cmd_validate)

    p_schema = sub.add_parser("spec-schema", help="Generate the JSON schema of the customer specification")
    p_schema.add_argument("--out", default="engine/spec/spec.schema.json", help="Target file")
    p_schema.set_defaults(func=cmd_spec_schema)

    p_caps = sub.add_parser("capabilities", help="Show/generate the capability-bundle catalog (skill reference)")
    p_caps.add_argument("--out", help="Write the markdown to this file instead of stdout")
    p_caps.add_argument("--json", action="store_true", help="Emit the catalog as compact JSON")
    p_caps.set_defaults(func=cmd_capabilities)

    p_new = sub.add_parser("new", help="Scaffold a customer spec skeleton from capability bundles")
    p_new.add_argument("--with", dest="bundles", action="append", required=True,
                       help="bundle id(s); repeatable or comma-separated (see 'capabilities')")
    p_new.add_argument("--name", required=True, help="company/customer name")
    p_new.add_argument("--country", required=True, help="country xmlid (base.ch) or ISO code (ch)")
    p_new.add_argument("--street")
    p_new.add_argument("--city")
    p_new.add_argument("--zip", dest="zip_code")
    p_new.add_argument("--vat")
    p_new.add_argument("--currency", help="currency xmlid, e.g. base.CHF")
    p_new.add_argument("--chart-template", dest="chart_template", help="chart of accounts code, e.g. ch")
    p_new.add_argument("--language")
    p_new.add_argument("--technical-name", dest="technical_name")
    p_new.add_argument("--out")
    p_new.add_argument("--force", action="store_true", help="overwrite an existing file")
    p_new.set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
