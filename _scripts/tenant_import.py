"""Compatibility wrapper for the M8 tenant bundle importer.

Prefer:
    python _scripts/tenant_bundle.py import --tenant <slug> --in <dir> [--on-conflict skip|overwrite]

Legacy usage kept working:
    python _scripts/tenant_import.py <tenant_slug> <export_dir> [--on-conflict skip|overwrite]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tenant_bundle import cmd_import


def _parse_args(argv: list[str]) -> tuple[str, Path, str]:
    if len(argv) < 2:
        raise SystemExit(
            "Usage: python _scripts/tenant_import.py <tenant_slug> <export_dir> "
            "[--on-conflict skip|overwrite]"
        )
    tenant_slug = argv[0]
    export_dir = Path(argv[1])
    on_conflict = "skip"
    if len(argv) == 4 and argv[2] == "--on-conflict":
        on_conflict = argv[3]
    elif len(argv) > 2:
        raise SystemExit(
            "Usage: python _scripts/tenant_import.py <tenant_slug> <export_dir> "
            "[--on-conflict skip|overwrite]"
        )
    return tenant_slug, export_dir, on_conflict


if __name__ == "__main__":
    slug, in_dir, strategy = _parse_args(sys.argv[1:])
    report = cmd_import(slug, in_dir, strategy)
    print(json.dumps(report, indent=2, ensure_ascii=False))
