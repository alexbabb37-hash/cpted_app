import math

import pandas as pd

from locivra_core import (
    CRIME_WEIGHTS,
    WEIGHT_PROFILES,
    _trend_changes,
    data_provenance,
    data_quality_summary,
    portfolio_radius_sensitivity,
    reconcile_location_result,
    score_location,
    temporal_trends,
    weight_sensitivity,
    _city_area_m2,
    TORONTO_REFERENCE_AREA_M2,
)
from locivra_reports import build_comparison_report, build_portfolio_report, build_site_report


def sample_results():
    return [
        score_location("Toronto City Hall", 43.6536, -79.3840, 500, submitted_address="Toronto City Hall"),
        score_location("Harbourfront", 43.6449, -79.3859, 500, submitted_address="Harbourfront"),
        score_location("East York", 43.7083, -79.3460, 500, submitted_address="East York"),
    ]


def test_all_weight_profiles_are_complete_and_sum_to_one():
    for profile in WEIGHT_PROFILES.values():
        assert set(profile) == set(CRIME_WEIGHTS)
        assert math.isclose(sum(profile.values()), 1.0, abs_tol=1e-9)


def test_composite_scores_reconcile_to_category_scores_and_weights():
    for result in sample_results():
        audit = reconcile_location_result(result)
        assert audit["Status"] == "PASS", audit["Issues"]
        assert audit["Reported score"] == audit["Recalculated score"]
        assert abs(audit["Display rounding difference"]) <= 0.2


def test_trend_percentages_reconcile_and_share_one_stability_policy():
    expected = _trend_changes(42, 20, 12.0, 10.0)
    assert expected["Count change (%)"] == 110.0
    assert expected["Exposure change (%)"] == 20.0
    assert expected["Stability flag"] == "Low sample"
    withheld = _trend_changes(8, 5, 1.0, 0.4)
    assert withheld["Count change (%)"] is None
    assert withheld["Exposure change (%)"] is None
    assert withheld["Stability flag"] == "Insufficient baseline"

    result = sample_results()[0]
    trends = temporal_trends(result.latitude, result.longitude, result.radius_metres)
    for frame in (trends["comparisons"], trends["categories"]):
        required = {"Count change (%)", "Exposure change (%)", "Stability flag", "Stability note"}
        assert required.issubset(frame.columns)
        for row in frame.to_dict("records"):
            if row["Count change (%)"] is not None and not pd.isna(row["Count change (%)"]):
                expected_count = round((row["Current incidents"] / row["Previous incidents"] - 1) * 100, 1)
                assert row["Count change (%)"] == expected_count
            if row["Exposure change (%)"] is not None and not pd.isna(row["Exposure change (%)"]):
                expected_exposure = round((row["Current exposure"] / row["Previous exposure"] - 1) * 100, 1)
                assert abs(row["Exposure change (%)"] - expected_exposure) <= 0.1


def test_portfolio_sensitivity_reports_every_location_and_assumption():
    results = sample_results()
    weights = weight_sensitivity(results)
    radii = portfolio_radius_sensitivity(results)
    assert len(weights) == len(results) * len(WEIGHT_PROFILES)
    assert len(radii) == len(results) * 4
    assert set(weights["Weight profile"]) == set(WEIGHT_PROFILES)
    assert set(radii["Radius (m)"]) == {250, 500, 750, 1000}
    assert weights.groupby("Weight profile")["Rank"].nunique().eq(len(results)).all()
    assert radii.groupby("Radius (m)")["Rank"].nunique().eq(len(results)).all()


def test_provenance_is_derived_from_configured_files_and_warns_explicitly():
    quality = data_quality_summary()
    provenance = data_provenance()
    assert len(quality["files"]) == len(CRIME_WEIGHTS)
    assert quality["valid_records"] > 0
    assert provenance["Data as of"] == quality["last_report_date"]
    assert "Data version" in provenance
    assert "Data warnings" in provenance
    assert "Baseline geography" in provenance
    assert "Coverage lag days" in quality["files"].columns


def test_baseline_area_is_fixed_and_cannot_drift_with_source_outliers():
    ordinary = pd.DataFrame({"LAT_WGS84": [43.6, 43.7], "LONG_WGS84": [-79.5, -79.3]})
    with_outlier = pd.DataFrame({"LAT_WGS84": [43.0, 44.0], "LONG_WGS84": [-80.0, -79.0]})
    assert _city_area_m2(ordinary) == TORONTO_REFERENCE_AREA_M2
    assert _city_area_m2(with_outlier) == TORONTO_REFERENCE_AREA_M2


def test_all_pdf_generators_complete_with_audited_results():
    results = sample_results()
    assert len(build_site_report(results[0]).getvalue()) > 10_000
    assert len(build_comparison_report(results[:2]).getvalue()) > 10_000
    assert len(build_portfolio_report(results).getvalue()) > 10_000
