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
from .model import SpecError
from .schema import write_schema
from .spec_loader import load_spec
from .validate import validate_module


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

    out_dir = Path(args.out)
    module_dir = write_module_dir(spec, out_dir)

    findings = validate_module(module_dir)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engine", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Build a customer specification (JSON) into a module ZIP")
    p_gen.add_argument("--spec", required=True, help="Path to the customer JSON specification")
    p_gen.add_argument("--out", default="dist", help="Target directory (default: dist/)")
    p_gen.add_argument("--force", action="store_true", help="Build the ZIP despite validation errors")
    p_gen.set_defaults(func=cmd_generate)

    p_val = sub.add_parser("validate", help="Statically validate an existing module (directory or ZIP)")
    p_val.add_argument("module", help="Path to the module directory or .zip")
    p_val.set_defaults(func=cmd_validate)

    p_schema = sub.add_parser("spec-schema", help="Generate the JSON schema of the customer specification")
    p_schema.add_argument("--out", default="engine/spec/spec.schema.json", help="Target file")
    p_schema.set_defaults(func=cmd_spec_schema)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
