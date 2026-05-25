"""Compatibility wrapper for the M8 tenant bundle exporter.

Prefer:
    python _scripts/tenant_bundle.py export --tenant <slug> --out <dir>

Legacy usage kept working:
    python _scripts/tenant_export.py <tenant_slug> [--output-dir ./exports]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tenant_bundle import cmd_export


def _parse_args(argv: list[str]) -> tuple[str, Path]:
    if not argv:
        raise SystemExit("Usage: python _scripts/tenant_export.py <tenant_slug> [--output-dir ./exports]")
    tenant_slug = argv[0]
    output_dir = Path(f"./exports/{tenant_slug}")
    if len(argv) == 3 and argv[1] == "--output-dir":
        output_dir = Path(argv[2])
    elif len(argv) > 1:
        raise SystemExit("Usage: python _scripts/tenant_export.py <tenant_slug> [--output-dir ./exports]")
    return tenant_slug, output_dir


if __name__ == "__main__":
    slug, out_dir = _parse_args(sys.argv[1:])
    manifest = cmd_export(slug, out_dir)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
