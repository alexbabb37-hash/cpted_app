from pathlib import Path

from locivra_core import METHODOLOGY_STAGE, METHODOLOGY_VERSION, contextual_features, load_crime_data


PROJECT = Path(__file__).resolve().parents[1]
CLIENT_FILES = [
    PROJECT / "app.py",
    PROJECT / "locivra_reports.py",
    PROJECT / "pages" / "Retail_Safety_Score.py",
    PROJECT / "pages" / "Compare_Locations.py",
    PROJECT / "pages" / "Batch_Score.py",
    PROJECT / "pages" / "Pilot_Scorecard.py",
    PROJECT / "README.md",
]


def test_controlled_methodology_name_and_stage():
    assert METHODOLOGY_VERSION == "Locivra Methodology v1.1"
    assert METHODOLOGY_STAGE == "Validation-stage decision support"


def test_client_facing_files_do_not_use_prototype_label():
    for path in CLIENT_FILES:
        assert "prototype" not in path.read_text(encoding="utf-8").casefold(), path


def test_controlled_methodology_statement_exists():
    statement = PROJECT / "docs" / "METHODOLOGY_V1_1.md"
    text = statement.read_text(encoding="utf-8")
    assert "Locivra Methodology v1.1" in text
    assert "does not predict crime" in text
    assert "validation remains in progress" in text
