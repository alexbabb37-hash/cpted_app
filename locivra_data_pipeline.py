"""Staged validation and release controls for Locivra crime-data updates."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import shutil
from typing import Any

import pandas as pd

from locivra_core import CRIME_FILES, EARTH_RADIUS_M, TORONTO_BOUNDS

REQUIRED_COLUMNS = {
    "EVENT_UNIQUE_ID",
    "REPORT_DATE",
    "LAT_WGS84",
    "LONG_WGS84",
}
SUPPORTED_RADII = (250, 500, 750, 1000)
MANIFEST_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class FileAudit:
    category: str
    filename: str
    sha256: str
    bytes: int
    rows: int
    valid_coordinate_rows: int
    invalid_coordinate_rows: int
    missing_date_rows: int
    exact_duplicate_rows: int
    repeated_event_id_rows: int
    first_report_date: str
    last_report_date: str
    missing_columns: list[str]

    @property
    def blocking_issues(self) -> list[str]:
        issues = []
        if self.missing_columns:
            issues.append("missing required columns: " + ", ".join(self.missing_columns))
        if self.rows == 0:
            issues.append("file contains no rows")
        if self.valid_coordinate_rows == 0:
            issues.append("file contains no valid Toronto coordinates")
        if self.first_report_date == "Not available":
            issues.append("file contains no usable report dates")
        return issues


def _checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_and_audit(path: Path, category: str) -> tuple[FileAudit, pd.DataFrame]:
    frame = pd.read_csv(path, low_memory=False)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    lat = pd.to_numeric(frame.get("LAT_WGS84", pd.Series(index=frame.index, dtype=float)), errors="coerce")
    lon = pd.to_numeric(frame.get("LONG_WGS84", pd.Series(index=frame.index, dtype=float)), errors="coerce")
    valid = lat.between(TORONTO_BOUNDS[0], TORONTO_BOUNDS[1]) & lon.between(TORONTO_BOUNDS[2], TORONTO_BOUNDS[3])
    dates = pd.to_datetime(frame.get("REPORT_DATE", pd.Series(index=frame.index, dtype=object)), errors="coerce", format="mixed")
    event_ids = frame.get("EVENT_UNIQUE_ID", pd.Series(index=frame.index, dtype=object))
    repeated_event_rows = int(event_ids.notna().sum() - event_ids.dropna().nunique())
    audit = FileAudit(
        category=category,
        filename=path.name,
        sha256=_checksum(path),
        bytes=path.stat().st_size,
        rows=int(len(frame)),
        valid_coordinate_rows=int(valid.sum()),
        invalid_coordinate_rows=int((~valid).sum()),
        missing_date_rows=int(dates.isna().sum()),
        exact_duplicate_rows=int(frame.duplicated().sum()),
        repeated_event_id_rows=max(0, repeated_event_rows),
        first_report_date=dates.min().date().isoformat() if dates.notna().any() else "Not available",
        last_report_date=dates.max().date().isoformat() if dates.notna().any() else "Not available",
        missing_columns=missing,
    )
    cleaned = frame.loc[valid].copy()
    cleaned["LAT_WGS84"] = lat.loc[valid]
    cleaned["LONG_WGS84"] = lon.loc[valid]
    cleaned["CRIME_TYPE"] = category
    return audit, cleaned


def _city_area_m2(frames: list[pd.DataFrame]) -> float:
    combined = pd.concat(frames, ignore_index=True)
    lat_min, lat_max = float(combined["LAT_WGS84"].min()), float(combined["LAT_WGS84"].max())
    lon_min, lon_max = float(combined["LONG_WGS84"].min()), float(combined["LONG_WGS84"].max())
    mid_lat = math.radians((lat_min + lat_max) / 2)
    height = (lat_max - lat_min) * 111_320
    width = (lon_max - lon_min) * 111_320 * math.cos(mid_lat)
    return max(height * width, 1.0)


def _baseline_table(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    area = _city_area_m2(list(frames.values()))
    rows = []
    for category, frame in frames.items():
        for radius in SUPPORTED_RADII:
            effective_kernel_area = math.pi * radius**2 / 3
            rows.append({
                "category": category,
                "radius_metres": radius,
                "valid_records": int(len(frame)),
                "city_area_m2": round(area, 2),
                "expected_weighted_exposure": round(len(frame) * effective_kernel_area / area, 4),
            })
    return rows


def validate_release(source_dir: Path, active_dir: Path | None = None) -> dict[str, Any]:
    """Validate a complete staged release without modifying active data."""
    source_dir = Path(source_dir).resolve()
    active_dir = Path(active_dir).resolve() if active_dir else None
    audits: list[FileAudit] = []
    cleaned: dict[str, pd.DataFrame] = {}
    blockers: list[str] = []
    warnings: list[str] = []

    for category, filename in CRIME_FILES.items():
        path = source_dir / filename
        if not path.exists():
            blockers.append(f"Missing required file: {filename}")
            continue
        try:
            audit, frame = _read_and_audit(path, category)
        except Exception as error:
            blockers.append(f"{filename} could not be audited: {error}")
            continue
        audits.append(audit)
        cleaned[category] = frame
        blockers.extend(f"{filename}: {issue}" for issue in audit.blocking_issues)
        if audit.invalid_coordinate_rows:
            warnings.append(f"{filename}: {audit.invalid_coordinate_rows:,} rows have missing or out-of-range coordinates")
        if audit.missing_date_rows:
            warnings.append(f"{filename}: {audit.missing_date_rows:,} rows cannot support trend calculations")
        if audit.exact_duplicate_rows:
            warnings.append(f"{filename}: {audit.exact_duplicate_rows:,} exact duplicate rows detected")
        if audit.repeated_event_id_rows:
            warnings.append(f"{filename}: {audit.repeated_event_id_rows:,} repeated event IDs detected; these may represent multiple offences and require review")

    baselines = _baseline_table(cleaned) if len(cleaned) == len(CRIME_FILES) and not blockers else []
    valid_dates = [audit.last_report_date for audit in audits if audit.last_report_date != "Not available"]
    first_dates = [audit.first_report_date for audit in audits if audit.first_report_date != "Not available"]
    data_as_of = max(valid_dates) if valid_dates else "Not available"

    if active_dir and data_as_of != "Not available":
        active_dates = []
        for filename in CRIME_FILES.values():
            active_path = active_dir / filename
            if active_path.exists():
                active_frame = pd.read_csv(active_path, usecols=lambda name: name == "REPORT_DATE", low_memory=False)
                if "REPORT_DATE" in active_frame:
                    parsed = pd.to_datetime(active_frame["REPORT_DATE"], errors="coerce", format="mixed")
                    if parsed.notna().any():
                        active_dates.append(parsed.max().date().isoformat())
        if active_dates and data_as_of < max(active_dates):
            blockers.append(f"Staged data as-of date {data_as_of} is older than active data {max(active_dates)}")

    combined_hash = sha256("".join(sorted(audit.sha256 for audit in audits)).encode()).hexdigest()
    data_version = f"{data_as_of}-{combined_hash[:8]}" if data_as_of != "Not available" else f"undated-{combined_hash[:8]}"
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "data_version": data_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source_dir),
        "status": "PASS" if not blockers else "FAIL",
        "coverage": {
            "first_report_date": min(first_dates) if first_dates else "Not available",
            "last_report_date": data_as_of,
            "valid_coordinate_records": sum(audit.valid_coordinate_rows for audit in audits),
        },
        "files": [asdict(audit) for audit in audits],
        "baselines": baselines,
        "warnings": warnings,
        "blocking_issues": blockers,
    }


def write_manifest(manifest: dict[str, Any], destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def activate_release(source_dir: Path, active_dir: Path, manifest_dir: Path, backup_dir: Path) -> dict[str, Any]:
    """Atomically activate a passing complete release and preserve the prior files."""
    source_dir, active_dir = Path(source_dir).resolve(), Path(active_dir).resolve()
    manifest = validate_release(source_dir, active_dir=active_dir)
    if manifest["status"] != "PASS":
        raise ValueError("Data release failed validation: " + "; ".join(manifest["blocking_issues"]))

    version = manifest["data_version"]
    release_backup = Path(backup_dir).resolve() / version
    release_backup.mkdir(parents=True, exist_ok=False)
    for filename in CRIME_FILES.values():
        active_path = active_dir / filename
        if active_path.exists():
            shutil.copy2(active_path, release_backup / filename)

    for filename in CRIME_FILES.values():
        staged_copy = active_dir / f".{filename}.{version}.staged"
        shutil.copy2(source_dir / filename, staged_copy)
        os.replace(staged_copy, active_dir / filename)

    manifest_path = Path(manifest_dir).resolve() / f"{version}.json"
    write_manifest(manifest, manifest_path)
    write_manifest(manifest, Path(manifest_dir).resolve() / "active.json")
    return {**manifest, "manifest_path": str(manifest_path), "backup_path": str(release_backup)}
