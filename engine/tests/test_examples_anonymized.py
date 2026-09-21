"""Structural guard: committed example specifications must be anonymized.

Real customer specifications must not be committed (they contain customer names,
addresses and VAT ids). Committed examples use a clearly fictional identity:
the company name starts with ``Muster`` (e.g. "Muster Foerdertechnik AG",
"Musterkraftwerke GmbH"). This keeps customer data out of the repository while
the real spec is still used to build the delivered module.

Only *tracked* files are checked, so a real spec that is being worked on locally
(untracked, or kept in a gitignored directory) does not fail the suite - but it
cannot be committed unnoticed. See AGENTS.md ("Committed examples are
anonymized").
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FICTIONAL_PREFIX = "Muster"


def _tracked_example_specs() -> list[Path]:
    """Example specs that are tracked by git (i.e. would be published)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "examples/*.json"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        # No git available (e.g. a source tarball): fall back to the directory.
        return sorted((REPO_ROOT / "examples").glob("*.json"))
    # Skip paths that are tracked but deleted in the working tree (rename in
    # progress) so the check does not fail on a transient state.
    return [p for line in out.split() if (p := REPO_ROOT / line).is_file()]


class ExampleAnonymizationTests(unittest.TestCase):
    def test_committed_examples_use_fictional_company_names(self) -> None:
        specs = _tracked_example_specs()
        self.assertTrue(specs, "no tracked example specs found")
        for path in specs:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("company", {}).get("name", "")
            self.assertTrue(
                name.startswith(FICTIONAL_PREFIX),
                f"{path.relative_to(REPO_ROOT)}: company name {name!r} is not a "
                f"fictional {FICTIONAL_PREFIX!r} example. Real customer specs must "
                f"not be committed - keep them untracked/gitignored and commit an "
                f"anonymized copy instead.",
            )


if __name__ == "__main__":
    unittest.main()
