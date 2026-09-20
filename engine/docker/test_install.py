#!/usr/bin/env python3
"""Automated installation smoke test for a generated demo module.

Runs ``docker compose run --rm <service> odoo -i <module> --stop-after-init -d <db>``
against a fresh (uniquely named) database, analyses the log for
``Traceback``/``CRITICAL`` and the ``Module <name> loaded`` marker, and on failure
prints the *complete* log (never just "failed").

No ``--test-enable``: it would run the test suites of *all* modules (see
skills/odoo-demo-data/reference/verified-patterns.md 4.8).

Targets the local Odoo 19 Enterprise (trial) instance in ``../odoodemo-local``
by default; that repo-local instance mounts this repo's ``output/`` as
``/mnt/extra-addons``. There is no Community setup.

Stdlib only; no CLI coupling. Example:

    python3 engine/docker/test_install.py --module bt_demo_nishcom
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_TIMEOUT = 1800  # seconds; first install with many dependencies can be slow

MODULE_LOADED_MARKER = "Module {module} loaded"


def analyze_log(log: str, module: str) -> tuple[bool, list[str]]:
    """Return ``(ok, reasons)`` for an installation log.

    Success requires: no ``Traceback``, no ``CRITICAL``, and the module-loaded
    marker. Pure function, unit-tested.
    """
    reasons: list[str] = []
    if "Traceback" in log:
        reasons.append("log contains 'Traceback'")
    if "CRITICAL" in log:
        reasons.append("log contains 'CRITICAL'")
    if MODULE_LOADED_MARKER.format(module=module) not in log:
        reasons.append(f"missing success marker '{MODULE_LOADED_MARKER.format(module=module)}'")
    return (not reasons, reasons)


def _unique_db_name(module: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", module.lower())
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"test_{safe}_{stamp}"[:63]


def _find_compose_file(compose_dir: Path) -> Path | None:
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        candidate = compose_dir / name
        if candidate.exists():
            return candidate
    return None


def _detect_module() -> str | None:
    """If exactly one .zip exists in ./output, use its stem as the module name."""
    output = Path.cwd() / "output"
    if not output.is_dir():
        return None
    zips = sorted(output.glob("*.zip"))
    if len(zips) == 1:
        return zips[0].stem
    return None


def _run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def _detect_spec(module: str) -> Path | None:
    """Find the example spec whose technical_name matches the module."""
    from engine.spec_loader import load_spec

    for path in sorted((REPO_ROOT / "examples").glob("*.json")):
        try:
            spec = load_spec(json.loads(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 - non-matching/invalid specs are skipped
            continue
        if spec.module.technical_name == module:
            return path
    return None


def _load_spec(path: Path):
    from engine.spec_loader import load_spec

    return load_spec(json.loads(Path(path).read_text(encoding="utf-8")))


def _psql_scalar(compose_dir: Path, db_service: str, db: str, sql: str) -> str:
    cmd = [
        "docker", "compose", "exec", "-T", db_service,
        "psql", "-U", "odoo", "-d", db, "-tAc", sql,
    ]
    result = _run(cmd, compose_dir, 120)
    if result.returncode != 0:
        raise RuntimeError((result.stdout + result.stderr).strip() or f"psql exit {result.returncode}")
    return result.stdout.strip()


def _verify_data(compose_dir: Path, db_service: str, db: str, spec):
    """Run the spec-derived Postgres assertions. Returns (ok, report, failures)."""
    from engine.verify import company_id_query, data_checks, standard_price_check

    failures: list[str] = []
    lines: list[str] = []
    try:
        cid_raw = _psql_scalar(compose_dir, db_service, db, company_id_query(spec))
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        return False, f"could not resolve the demo company id: {exc}", ["company id query failed"]
    if not cid_raw.isdigit():
        return False, f"demo company not found (query returned {cid_raw!r})", ["demo company missing"]

    checks = data_checks(spec)
    extra = standard_price_check(spec, int(cid_raw))
    if extra is not None:
        checks.append(extra)

    lines.append("Postgres data assertions:")
    for check in checks:
        try:
            value = _psql_scalar(compose_dir, db_service, db, check.sql)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            failures.append(f"{check.label}: query failed ({exc})")
            lines.append(f"  ERROR {check.label}: query failed ({exc})")
            continue
        ok = str(value) == str(check.expected)
        mark = "ok  " if ok else "FAIL"
        lines.append(f"  {mark} {check.label}: expected {check.expected}, got {value}")
        if not ok:
            detail = f" ({check.hint})" if check.hint else ""
            failures.append(f"{check.label}: expected {check.expected}, got {value}{detail}")

    return (not failures), "\n".join(lines), failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    default_compose_dir = Path(__file__).resolve().parents[2].parent / "odoodemo-local"
    parser.add_argument("--module", help="module technical name (default: the single .zip in output/)")
    parser.add_argument("--compose-dir", default=str(default_compose_dir),
                        help="directory containing the docker-compose file "
                             "(default: the local Enterprise instance ../odoodemo-local)")
    parser.add_argument("--service", default="web", help="compose service running Odoo (default: web)")
    parser.add_argument("--db-service", default="db", help="compose service running Postgres (default: db)")
    parser.add_argument("--db", help="database name (default: fresh unique name)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="install timeout in seconds")
    parser.add_argument("--log", help="write the full log to this path")
    parser.add_argument("--keep-db", action="store_true", help="never drop the test database")
    parser.add_argument("--verbose", action="store_true", help="always print the full log")
    parser.add_argument("--spec", help="customer spec JSON for the Postgres data assertions "
                                      "(default: auto-detect in examples/ by module name)")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the Postgres data assertions")
    args = parser.parse_args(argv)

    compose_dir = Path(args.compose_dir).resolve()
    module = args.module or _detect_module() or ""
    db_name = args.db or _unique_db_name(module or "demo")

    # --- preflight -----------------------------------------------------------
    problems: list[str] = []
    if not shutil.which("docker"):
        problems.append("'docker' not found in PATH")
    if _find_compose_file(compose_dir) is None:
        problems.append(f"no docker-compose file in {compose_dir}")
    if not module:
        problems.append("no --module given and none could be detected in ./output")
    if problems:
        for problem in problems:
            print(f"preflight error: {problem}", file=sys.stderr)
        return 2

    install_cmd = [
        "docker", "compose", "run", "--rm", args.service,
        "odoo", "-i", module, "--stop-after-init", "-d", db_name,
    ]
    print(f"installing module {module!r} into fresh database {db_name!r} ...")
    print("  " + " ".join(install_cmd))

    timed_out = False
    returncode: int | None
    try:
        result = _run(install_cmd, compose_dir, args.timeout)
        log = result.stdout + result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        log = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(log, bytes):  # defensive; text=True normally yields str
            log = log.decode(errors="replace")
        returncode = None
    except OSError as exc:
        print(f"could not run docker compose: {exc}", file=sys.stderr)
        return 2

    if args.log:
        Path(args.log).write_text(log, encoding="utf-8")

    ok, reasons = analyze_log(log, module)
    if timed_out:
        ok = False
        reasons.append(f"timeout after {args.timeout}s")
    if returncode not in (0, None):
        ok = False
        reasons.append(f"non-zero exit code {returncode}")

    if ok:
        print(f"\nOK: module {module!r} installed without Traceback/CRITICAL.")
        if args.verbose:
            print(log)

        # --- Postgres data assertions (log alone is not proof) ----------------
        if not args.no_verify:
            spec_path = Path(args.spec) if args.spec else _detect_spec(module)
            if spec_path is None:
                print("note: no matching spec in examples/ - skipping Postgres data "
                      "assertions (pass --spec <path> to enable).")
            else:
                try:
                    spec = _load_spec(spec_path)
                except Exception as exc:  # noqa: BLE001
                    print(f"warning: could not load spec {spec_path}: {exc}", file=sys.stderr)
                else:
                    print(f"verifying data against spec {spec_path} ...")
                    verify_ok, report, failures = _verify_data(
                        compose_dir, args.db_service, db_name, spec
                    )
                    print(report)
                    if not verify_ok:
                        print(f"\nFAILED: module {module!r} installed, but the data "
                              f"assertions failed:", file=sys.stderr)
                        for failure in failures:
                            print(f"  - {failure}", file=sys.stderr)
                        print(f"  database {db_name!r} kept for inspection", file=sys.stderr)
                        return 1

        if args.keep_db:
            print(f"kept database {db_name!r}")
        else:
            # WITH (FORCE) terminates lingering connections (the always-on web
            # service can hold idle sessions to the test DB), otherwise
            # DROP DATABASE fails and the DB silently stays behind.
            drop = [
                "docker", "compose", "exec", "-T", args.db_service,
                "psql", "-U", "odoo", "-d", "postgres", "-c",
                f'DROP DATABASE IF EXISTS {db_name} WITH (FORCE);',
            ]
            try:
                result = _run(drop, compose_dir, 120)
                if result.returncode == 0:
                    print(f"dropped database {db_name!r}")
                else:
                    print(f"warning: could not drop database {db_name!r}: "
                          f"{(result.stderr or result.stdout).strip()}", file=sys.stderr)
            except (OSError, subprocess.TimeoutExpired) as exc:
                print(f"warning: could not drop database {db_name!r}: {exc}", file=sys.stderr)
        return 0

    # --- failure: return the complete log (hard rule) ------------------------
    print(f"\nFAILED: module {module!r} did not install cleanly.", file=sys.stderr)
    for reason in reasons:
        print(f"  - {reason}", file=sys.stderr)
    print(f"  database {db_name!r} kept for inspection", file=sys.stderr)
    if args.log:
        print(f"  full log: {args.log}", file=sys.stderr)
    print("\n----- full log -----", file=sys.stderr)
    print(log, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
