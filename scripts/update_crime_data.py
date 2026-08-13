#!/usr/bin/env python3
"""Validate or activate a complete Locivra crime-data release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from locivra_data_pipeline import activate_release, validate_release, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage, audit and version Locivra crime-data updates.")
    parser.add_argument("source_dir", type=Path, help="Directory containing all five required crime CSV files.")
    parser.add_argument("--activate", action="store_true", help="Back up active data and atomically activate a passing release.")
    parser.add_argument("--manifest-out", type=Path, help="Optional path for a dry-run JSON manifest.")
    args = parser.parse_args()

    if args.activate:
        result = activate_release(
            args.source_dir,
            PROJECT,
            PROJECT / "data_manifests",
            PROJECT / "data_backups",
        )
    else:
        result = validate_release(args.source_dir, active_dir=PROJECT)
        if args.manifest_out:
            write_manifest(result, args.manifest_out)

    summary = {
        "status": result["status"],
        "data_version": result["data_version"],
        "coverage": result["coverage"],
        "warnings": len(result["warnings"]),
        "blocking_issues": result["blocking_issues"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
