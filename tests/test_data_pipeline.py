from pathlib import Path
import shutil

import pandas as pd

from locivra_core import CRIME_FILES
from locivra_data_pipeline import validate_release, write_manifest


def _write_release(directory: Path, last_date: str = "2026-03-31") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, filename in enumerate(CRIME_FILES.values(), 1):
        pd.DataFrame({
            "EVENT_UNIQUE_ID": [f"E-{index}-1", f"E-{index}-2"],
            "REPORT_DATE": ["2026-01-01", last_date],
            "LAT_WGS84": [43.65, 43.70],
            "LONG_WGS84": [-79.38, -79.40],
        }).to_csv(directory / filename, index=False)


def test_complete_release_passes_and_produces_baselines(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    result = validate_release(release)
    assert result["status"] == "PASS"
    assert len(result["files"]) == len(CRIME_FILES)
    assert len(result["baselines"]) == len(CRIME_FILES) * 4
    assert result["coverage"]["last_report_date"] == "2026-03-31"


def test_missing_file_and_schema_fail_without_activation(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    (release / next(iter(CRIME_FILES.values()))).unlink()
    result = validate_release(release)
    assert result["status"] == "FAIL"
    assert any("Missing required file" in issue for issue in result["blocking_issues"])


def test_older_release_is_blocked(tmp_path):
    active, staged = tmp_path / "active", tmp_path / "staged"
    _write_release(active, "2026-03-31")
    _write_release(staged, "2025-12-31")
    result = validate_release(staged, active_dir=active)
    assert result["status"] == "FAIL"
    assert any("older than active data" in issue for issue in result["blocking_issues"])


def test_manifest_is_written_as_valid_json(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    result = validate_release(release)
    destination = write_manifest(result, tmp_path / "manifest.json")
    assert destination.exists()
    assert '"status": "PASS"' in destination.read_text()
