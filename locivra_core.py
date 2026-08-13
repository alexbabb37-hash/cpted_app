"""Shared data, geospatial, and scoring logic for Locivra.

Version 1.0 is a transparent prototype. Crime history determines the priority
score. Environmental datasets are returned as context only and do not alter the
score until their influence is separately validated.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from functools import lru_cache
from pathlib import Path
import json
import math
import time
from typing import Any

import numpy as np
import pandas as pd
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim

ROOT = Path(__file__).resolve().parent
CRIME_FILES = {
    "Assault": "toronto_crime.csv",
    "Break & Enter": "breakenter.csv",
    "Robbery": "robbery.csv",
    "Auto Theft": "autotheft.csv",
    "Theft Over $5000": "theft_over.csv",
}
CRIME_WEIGHTS = {
    "Theft Over $5000": 0.30,
    "Break & Enter": 0.25,
    "Robbery": 0.25,
    "Assault": 0.15,
    "Auto Theft": 0.05,
}
WEIGHT_PROFILES = {
    "Published retail profile": CRIME_WEIGHTS,
    "Balanced categories": {
        "Theft Over $5000": 0.20, "Break & Enter": 0.20, "Robbery": 0.20,
        "Assault": 0.20, "Auto Theft": 0.20,
    },
    "People-harm emphasis": {
        "Theft Over $5000": 0.15, "Break & Enter": 0.15, "Robbery": 0.30,
        "Assault": 0.30, "Auto Theft": 0.10,
    },
    "Property-loss emphasis": {
        "Theft Over $5000": 0.30, "Break & Enter": 0.30, "Robbery": 0.15,
        "Assault": 0.05, "Auto Theft": 0.20,
    },
}
MIN_PRIOR_INCIDENTS_FOR_PERCENT = 10
LOW_SAMPLE_INCIDENTS = 30
MIN_PRIOR_WEIGHTED_EXPOSURE = 0.50
SCORE_BANDS = ((75, "Critical review priority"), (60, "High review priority"), (40, "Moderate review priority"), (0, "Lower review priority"))
METHODOLOGY_VERSION = "1.1 prototype"
DATA_SOURCE = "Toronto Police Service Public Safety Data Portal"
DATA_COVERAGE = "2014-2026 report years"
DATA_AS_OF = "March 31, 2026 (newest report date in the configured files)"
TORONTO_BOUNDS = (43.0, 44.0, -80.0, -79.0)
EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class CategoryResult:
    category: str
    raw_incidents: int
    weighted_exposure: float
    baseline_exposure: float
    score: float
    weight: float

    @property
    def contribution(self) -> float:
        """Points this category contributes to the 0-100 overall score."""
        return round(self.score * self.weight, 1)


@dataclass(frozen=True)
class LocationResult:
    address: str
    latitude: float
    longitude: float
    radius_metres: int
    overall_score: float
    priority_label: str
    categories: dict[str, CategoryResult]
    context: dict[str, Any]
    methodology_version: str = METHODOLOGY_VERSION
    submitted_address: str = ""
    location_id: str = ""
    client_data: dict[str, Any] = field(default_factory=dict)

    def flat_row(self) -> dict[str, Any]:
        row = {
            "Address": self.address,
            "Submitted Address": self.submitted_address or self.address,
            "Location ID": self.location_id,
            "Latitude": round(self.latitude, 6),
            "Longitude": round(self.longitude, 6),
            "Radius (m)": self.radius_metres,
            "Overall Score": self.overall_score,
            "Review Priority": self.priority_label,
        }
        for name, result in self.categories.items():
            row[f"{name} Score"] = result.score
            row[f"{name} Raw Incidents"] = result.raw_incidents
            row[f"{name} Weighted Exposure"] = result.weighted_exposure
        return row


def priority_label(score: float) -> str:
    return next(label for threshold, label in SCORE_BANDS if score >= threshold)


def comparison_interpretation(first: LocationResult, second: LocationResult) -> dict[str, str | float]:
    """Use restrained language when two prototype scores are close."""
    difference = round(abs(first.overall_score - second.overall_score), 1)
    higher = first if first.overall_score >= second.overall_score else second
    if difference < 3:
        strength = "No meaningful separation"
        guidance = "Treat the locations as the same practical review tier and use internal evidence to set the order."
    elif difference < 8:
        strength = "Moderate separation"
        guidance = "Use the higher score as a provisional review order, then validate the difference with internal and site-level evidence."
    else:
        strength = "Clearer first-pass separation"
        guidance = "Review the higher-scoring location first, subject to internal and site-level validation."
    return {"difference": difference, "strength": strength, "guidance": guidance, "higher_address": higher.address}


def comparison_explanation(first: LocationResult, second: LocationResult) -> dict[str, Any]:
    """Explain the score difference with the exact category-level evidence."""
    if first.overall_score >= second.overall_score:
        higher, lower = first, second
        higher_label, lower_label = "Location 1", "Location 2"
    else:
        higher, lower = second, first
        higher_label, lower_label = "Location 2", "Location 1"

    differences = []
    for category in CRIME_WEIGHTS:
        high_item = higher.categories[category]
        low_item = lower.categories[category]
        differences.append({
            "category": category,
            "contribution_difference": round(high_item.contribution - low_item.contribution, 1),
            "higher_contribution": high_item.contribution,
            "lower_contribution": low_item.contribution,
            "higher_score": high_item.score,
            "lower_score": low_item.score,
            "higher_incidents": high_item.raw_incidents,
            "lower_incidents": low_item.raw_incidents,
            "higher_exposure": high_item.weighted_exposure,
            "lower_exposure": low_item.weighted_exposure,
        })
    positive_drivers = sorted(
        (item for item in differences if item["contribution_difference"] > 0),
        key=lambda item: item["contribution_difference"],
        reverse=True,
    )
    leading = positive_drivers[:2] or sorted(differences, key=lambda item: abs(item["contribution_difference"]), reverse=True)[:2]
    gap = round(higher.overall_score - lower.overall_score, 1)
    driver_text = " and ".join(
        f"{item['category']} (+{item['contribution_difference']:.1f} points)"
        for item in leading
    )
    summary = (
        f"{higher_label} ranks ahead of {lower_label} by {gap:.1f} points. "
        f"The largest reasons for the difference are {driver_text}. "
        "This means it should be reviewed first under the current method; it does not mean the other location is safe or that a future incident is predicted."
    )
    return {
        "higher": higher,
        "lower": lower,
        "higher_label": higher_label,
        "lower_label": lower_label,
        "gap": gap,
        "drivers": differences,
        "leading_drivers": leading,
        "summary": summary,
    }


def _read_crime_file(path: Path, crime_type: str) -> pd.DataFrame:
    required = ["LAT_WGS84", "LONG_WGS84"]
    df = pd.read_csv(path, low_memory=False)
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
    df = df.copy()
    df["CRIME_TYPE"] = crime_type
    df["LAT_WGS84"] = pd.to_numeric(df["LAT_WGS84"], errors="coerce")
    df["LONG_WGS84"] = pd.to_numeric(df["LONG_WGS84"], errors="coerce")
    if "REPORT_DATE" in df.columns:
        df["REPORT_DATETIME"] = pd.to_datetime(df["REPORT_DATE"], errors="coerce", format="mixed")
    lat_min, lat_max, lon_min, lon_max = TORONTO_BOUNDS
    return df[df["LAT_WGS84"].between(lat_min, lat_max) & df["LONG_WGS84"].between(lon_min, lon_max)]


@lru_cache(maxsize=1)
def load_crime_data() -> pd.DataFrame:
    _validate_weight_profiles()
    frames = [_read_crime_file(ROOT / filename, crime_type) for crime_type, filename in CRIME_FILES.items()]
    return pd.concat(frames, ignore_index=True)


def _validate_weight_profiles() -> None:
    expected = set(CRIME_FILES)
    for name, profile in WEIGHT_PROFILES.items():
        if set(profile) != expected:
            raise ValueError(f"Weight profile '{name}' does not contain exactly the configured crime categories.")
        if not math.isclose(sum(profile.values()), 1.0, abs_tol=1e-9):
            raise ValueError(f"Weight profile '{name}' must sum to 100%.")
        if any(value < 0 for value in profile.values()):
            raise ValueError(f"Weight profile '{name}' cannot contain a negative weight.")


@lru_cache(maxsize=1)
def data_quality_summary() -> dict[str, Any]:
    """Audit configured source files without silently hiding rejected rows."""
    rows, warnings = [], []
    for category, filename in CRIME_FILES.items():
        path = ROOT / filename
        if not path.exists():
            rows.append({"Category": category, "File": filename, "Rows": 0, "Valid coordinates": 0, "Invalid coordinates": 0, "Missing dates": 0})
            warnings.append(f"Missing source file: {filename}")
            continue
        frame = pd.read_csv(path, low_memory=False)
        required = {"LAT_WGS84", "LONG_WGS84", "REPORT_DATE"}
        missing_columns = sorted(required - set(frame.columns))
        if missing_columns:
            warnings.append(f"{filename} is missing columns: {', '.join(missing_columns)}")
        lat = pd.to_numeric(frame.get("LAT_WGS84", pd.Series(index=frame.index, dtype=float)), errors="coerce")
        lon = pd.to_numeric(frame.get("LONG_WGS84", pd.Series(index=frame.index, dtype=float)), errors="coerce")
        valid_coordinates = lat.between(TORONTO_BOUNDS[0], TORONTO_BOUNDS[1]) & lon.between(TORONTO_BOUNDS[2], TORONTO_BOUNDS[3])
        dates = pd.to_datetime(frame.get("REPORT_DATE", pd.Series(index=frame.index, dtype=object)), errors="coerce", format="mixed")
        invalid_coordinates = int((~valid_coordinates).sum())
        missing_dates = int(dates.isna().sum())
        if invalid_coordinates:
            warnings.append(f"{filename}: {invalid_coordinates:,} rows excluded for missing or out-of-range coordinates")
        if missing_dates:
            warnings.append(f"{filename}: {missing_dates:,} rows cannot be used in historical trend calculations")
        rows.append({
            "Category": category,
            "File": filename,
            "Rows": int(len(frame)),
            "Valid coordinates": int(valid_coordinates.sum()),
            "Invalid coordinates": invalid_coordinates,
            "Missing dates": missing_dates,
            "First report date": dates.min().date().isoformat() if dates.notna().any() else "Not available",
            "Last report date": dates.max().date().isoformat() if dates.notna().any() else "Not available",
        })
    valid_dates = [row["Last report date"] for row in rows if row.get("Last report date") not in (None, "Not available")]
    first_dates = [row["First report date"] for row in rows if row.get("First report date") not in (None, "Not available")]
    return {
        "files": pd.DataFrame(rows),
        "warnings": warnings,
        "first_report_date": min(first_dates) if first_dates else "Not available",
        "last_report_date": max(valid_dates) if valid_dates else "Not available",
        "valid_records": sum(row.get("Valid coordinates", 0) for row in rows),
    }


def _extract_point(value: Any) -> tuple[float, float] | None:
    try:
        obj = json.loads(value) if isinstance(value, str) else value
        coords = obj["coordinates"]
        while isinstance(coords[0], list):
            coords = coords[0]
        return float(coords[1]), float(coords[0])
    except (TypeError, ValueError, KeyError, IndexError, json.JSONDecodeError):
        return None


@lru_cache(maxsize=1)
def load_context_data() -> dict[str, pd.DataFrame]:
    stations = pd.read_csv(ROOT / "ttc_stations.csv")
    parks = pd.read_csv(ROOT / "parks.csv", low_memory=False)
    poles = pd.read_csv(ROOT / "poles.csv", low_memory=False)
    population = pd.read_csv(ROOT / "population_clean.csv")
    for frame in (parks, poles):
        points = frame["geometry"].map(_extract_point)
        frame["LAT"] = points.map(lambda point: point[0] if point else np.nan)
        frame["LONG"] = points.map(lambda point: point[1] if point else np.nan)
    population["Neighbourhood"] = population["Neighbourhood"].astype(str).str.replace("`", "'", regex=False)
    return {"stations": stations, "parks": parks.dropna(subset=["LAT", "LONG"]), "poles": poles.dropna(subset=["LAT", "LONG"]), "population": population}


def haversine_metres(lat: float, lon: float, latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = np.radians(latitudes.astype(float))
    lon2 = np.radians(longitudes.astype(float))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _city_area_m2(df: pd.DataFrame) -> float:
    lat_min, lat_max = float(df["LAT_WGS84"].min()), float(df["LAT_WGS84"].max())
    lon_min, lon_max = float(df["LONG_WGS84"].min()), float(df["LONG_WGS84"].max())
    mid_lat = math.radians((lat_min + lat_max) / 2)
    height = (lat_max - lat_min) * 111_320
    width = (lon_max - lon_min) * 111_320 * math.cos(mid_lat)
    return max(height * width, 1.0)


def _category_score(category_df: pd.DataFrame, lat: float, lon: float, radius_metres: int, all_city_area: float) -> CategoryResult:
    distances = haversine_metres(lat, lon, category_df["LAT_WGS84"].to_numpy(), category_df["LONG_WGS84"].to_numpy())
    nearby = distances < radius_metres
    local_distances = distances[nearby]
    weighted_exposure = float(np.maximum(0, 1 - local_distances / radius_metres).sum())
    # Expected linear-decay exposure under a citywide uniform-density baseline.
    effective_kernel_area = math.pi * radius_metres**2 / 3
    baseline = len(category_df) * effective_kernel_area / all_city_area
    # A log-relative scale preserves differences in dense areas instead of
    # allowing a few large incident clusters to make every result equal 100.
    # Baseline exposure maps to 50; zero exposure maps to zero.
    ratio = weighted_exposure / max(baseline, 0.01)
    score = 0.0 if weighted_exposure == 0 else float(np.clip(50.0 + 15.0 * math.log(ratio), 0.0, 100.0))
    category = str(category_df["CRIME_TYPE"].iloc[0])
    return CategoryResult(category, int(nearby.sum()), round(weighted_exposure, 2), round(baseline, 2), round(score, 1), CRIME_WEIGHTS[category])


def _nearest_neighbourhood(crimes: pd.DataFrame, lat: float, lon: float) -> str | None:
    if "NEIGHBOURHOOD_158" not in crimes.columns:
        return None
    sample = crimes.dropna(subset=["NEIGHBOURHOOD_158"])
    distances = haversine_metres(lat, lon, sample["LAT_WGS84"].to_numpy(), sample["LONG_WGS84"].to_numpy())
    if len(distances) == 0:
        return None
    value = str(sample.iloc[int(np.argmin(distances))]["NEIGHBOURHOOD_158"])
    return value.rsplit(" (", 1)[0].replace("`", "'")


def contextual_features(crimes: pd.DataFrame, lat: float, lon: float, radius_metres: int) -> dict[str, Any]:
    data = load_context_data()
    result: dict[str, Any] = {"note": "Context only; these values do not affect the Version 1.0 score."}
    stations = data["stations"]
    station_distances = haversine_metres(lat, lon, stations["latitude"].to_numpy(), stations["longitude"].to_numpy())
    if len(station_distances):
        index = int(np.argmin(station_distances))
        result["nearest_ttc_station"] = str(stations.iloc[index]["STATION"])
        result["ttc_distance_metres"] = int(round(station_distances[index]))
    for key, frame in (("parks_within_radius", data["parks"]), ("street_light_poles_within_radius", data["poles"])):
        distances = haversine_metres(lat, lon, frame["LAT"].to_numpy(), frame["LONG"].to_numpy())
        result[key] = int((distances < radius_metres).sum())
    neighbourhood = _nearest_neighbourhood(crimes, lat, lon)
    if neighbourhood:
        result["approximate_neighbourhood"] = neighbourhood
        pop = data["population"]
        matched = pop[pop["Neighbourhood"].str.casefold() == neighbourhood.casefold()]
        if not matched.empty:
            result["approximate_neighbourhood_population"] = int(matched.iloc[0]["Population"])
    return result


def score_location(address: str, lat: float, lon: float, radius_metres: int = 500, include_context: bool = True, submitted_address: str = "", location_id: str = "", client_data: dict[str, Any] | None = None) -> LocationResult:
    if radius_metres not in {250, 500, 750, 1000}:
        raise ValueError("Radius must be one of 250, 500, 750, or 1000 metres.")
    crimes = load_crime_data()
    city_area = _city_area_m2(crimes)
    category_results: dict[str, CategoryResult] = {}
    for category in CRIME_WEIGHTS:
        category_results[category] = _category_score(crimes[crimes["CRIME_TYPE"] == category], lat, lon, radius_metres, city_area)
    overall = round(sum(result.score * result.weight for result in category_results.values()), 1)
    context = contextual_features(crimes, lat, lon, radius_metres) if include_context else {}
    return LocationResult(address.strip(), lat, lon, radius_metres, overall, priority_label(overall), category_results, context, METHODOLOGY_VERSION, submitted_address.strip(), str(location_id).strip(), client_data or {})


def nearby_incidents(lat: float, lon: float, radius_metres: int, limit: int = 2500) -> pd.DataFrame:
    """Return real incident coordinates for display, deterministically sampled if dense."""
    crimes = load_crime_data()
    distances = haversine_metres(lat, lon, crimes["LAT_WGS84"].to_numpy(), crimes["LONG_WGS84"].to_numpy())
    nearby = crimes.loc[distances < radius_metres, ["LAT_WGS84", "LONG_WGS84", "CRIME_TYPE"]].copy()
    nearby.columns = ["latitude", "longitude", "category"]
    if len(nearby) > limit:
        nearby = nearby.sample(limit, random_state=42)
    return nearby.reset_index(drop=True)


def radius_sensitivity(address: str, lat: float, lon: float) -> pd.DataFrame:
    rows = []
    for radius in (250, 500, 750, 1000):
        result = score_location(address, lat, lon, radius, include_context=False)
        rows.append({"Radius (m)": radius, "Priority score": result.overall_score, "Review label": result.priority_label})
    return pd.DataFrame(rows)


def score_under_weights(result: LocationResult, weights: dict[str, float]) -> float:
    """Recombine fixed category scores under a disclosed alternative profile."""
    if set(weights) != set(result.categories) or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("Alternative weights must contain every category and sum to 100%.")
    return round(sum(result.categories[category].score * weights[category] for category in weights), 1)


def weight_sensitivity(results: list[LocationResult]) -> pd.DataFrame:
    """Show whether portfolio rank order survives reasonable weighting profiles."""
    if not results:
        return pd.DataFrame(columns=["Weight profile", "Location", "Score", "Rank", "Rank change"])
    rows = []
    base_order = sorted(results, key=lambda item: score_under_weights(item, CRIME_WEIGHTS), reverse=True)
    base_ranks = {id(result): rank for rank, result in enumerate(base_order, 1)}
    for profile_name, profile in WEIGHT_PROFILES.items():
        scored = sorted(((result, score_under_weights(result, profile)) for result in results), key=lambda pair: pair[1], reverse=True)
        for rank, (result, score) in enumerate(scored, 1):
            rows.append({
                "Weight profile": profile_name,
                "Location": result.submitted_address or result.address,
                "Score": score,
                "Rank": rank,
                "Rank change": base_ranks[id(result)] - rank,
            })
    return pd.DataFrame(rows)


def portfolio_radius_sensitivity(results: list[LocationResult]) -> pd.DataFrame:
    """Re-score and re-rank a portfolio at each supported boundary."""
    rows = []
    base = sorted(results, key=lambda item: item.overall_score, reverse=True)
    base_ranks = {(result.submitted_address or result.address): rank for rank, result in enumerate(base, 1)}
    for radius in (250, 500, 750, 1000):
        rescored = [score_location(result.address, result.latitude, result.longitude, radius, include_context=False, submitted_address=result.submitted_address, location_id=result.location_id) for result in results]
        for rank, result in enumerate(sorted(rescored, key=lambda item: item.overall_score, reverse=True), 1):
            label = result.submitted_address or result.address
            rows.append({"Radius (m)": radius, "Location": label, "Score": result.overall_score, "Rank": rank, "Rank change": base_ranks[label] - rank})
    return pd.DataFrame(rows)


def reconcile_location_result(result: LocationResult) -> dict[str, Any]:
    """Return a visible audit record for the composite score and displayed points."""
    calculated = round(sum(item.score * item.weight for item in result.categories.values()), 1)
    displayed_points = round(sum(item.contribution for item in result.categories.values()), 1)
    issues = []
    if set(result.categories) != set(CRIME_WEIGHTS):
        issues.append("Category set does not match the configured model")
    if not math.isclose(sum(item.weight for item in result.categories.values()), 1.0, abs_tol=1e-9):
        issues.append("Category weights do not sum to 100%")
    if not math.isclose(calculated, result.overall_score, abs_tol=0.05):
        issues.append("Overall score does not reconcile to category score x weight")
    rounding_difference = round(displayed_points - result.overall_score, 1)
    if abs(rounding_difference) > 0.2:
        issues.append("Displayed contribution rounding exceeds 0.2 points")
    return {
        "Location": result.submitted_address or result.address,
        "Reported score": result.overall_score,
        "Recalculated score": calculated,
        "Displayed contribution sum": displayed_points,
        "Display rounding difference": rounding_difference,
        "Status": "PASS" if not issues else "CHECK",
        "Issues": "; ".join(issues) if issues else "None",
    }


def reconcile_results(results: list[LocationResult]) -> pd.DataFrame:
    return pd.DataFrame([reconcile_location_result(result) for result in results])


def result_warnings(result: LocationResult) -> list[str]:
    warnings = list(data_quality_summary()["warnings"])
    zero_categories = [item.category for item in result.categories.values() if item.raw_incidents == 0]
    if zero_categories:
        warnings.append("No incidents were found inside the selected radius for: " + ", ".join(zero_categories))
    if result.context and not result.context.get("nearest_ttc_station"):
        warnings.append("TTC proximity context is unavailable for this location")
    return warnings


def _trend_changes(current_count: int, previous_count: int, current_exposure: float, previous_exposure: float) -> dict[str, Any]:
    insufficient = previous_count < MIN_PRIOR_INCIDENTS_FOR_PERCENT or previous_exposure < MIN_PRIOR_WEIGHTED_EXPOSURE
    count_change = None if previous_count < MIN_PRIOR_INCIDENTS_FOR_PERCENT else (current_count / previous_count - 1) * 100
    exposure_change = None if insufficient else (current_exposure / previous_exposure - 1) * 100
    if insufficient:
        note = f"Unstable baseline - percentages withheld when prior incidents < {MIN_PRIOR_INCIDENTS_FOR_PERCENT} or prior weighted exposure < {MIN_PRIOR_WEIGHTED_EXPOSURE:.2f}"
        flag = "Insufficient baseline"
    elif min(current_count, previous_count) < LOW_SAMPLE_INCIDENTS:
        note = f"Low sample - interpret cautiously (fewer than {LOW_SAMPLE_INCIDENTS} incidents in at least one window)"
        flag = "Low sample"
    else:
        note = "Sufficient volume for descriptive comparison"
        flag = "Standard"
    return {
        "Count change (%)": None if count_change is None else round(count_change, 1),
        "Exposure change (%)": None if exposure_change is None else round(exposure_change, 1),
        "Stability flag": flag,
        "Stability note": note,
    }


def temporal_trends(lat: float, lon: float, radius_metres: int) -> dict[str, Any]:
    """Historical rolling comparisons anchored to the newest available record.

    Exposure combines distance decay and the published category weights. Equal
    rolling windows are compared; this is descriptive history, not forecasting.
    """
    crimes = load_crime_data()
    if "REPORT_DATETIME" not in crimes.columns:
        raise ValueError("Trend analysis requires REPORT_DATE in the crime files.")
    distances = haversine_metres(lat, lon, crimes["LAT_WGS84"].to_numpy(), crimes["LONG_WGS84"].to_numpy())
    nearby_mask = distances < radius_metres
    local = crimes.loc[nearby_mask, ["REPORT_DATETIME", "CRIME_TYPE"]].copy()
    local["distance_weight"] = np.maximum(0, 1 - distances[nearby_mask] / radius_metres)
    local = local.dropna(subset=["REPORT_DATETIME"])
    local["category_weight"] = local["CRIME_TYPE"].map(CRIME_WEIGHTS)
    local["weighted_signal"] = local["distance_weight"] * local["category_weight"]
    cutoff = pd.Timestamp(crimes["REPORT_DATETIME"].max()).normalize()

    comparison_rows = []
    for months in (6, 12):
        current_start = cutoff - pd.DateOffset(months=months)
        previous_start = current_start - pd.DateOffset(months=months)
        current = local[(local["REPORT_DATETIME"] > current_start) & (local["REPORT_DATETIME"] <= cutoff + pd.Timedelta(days=1))]
        previous = local[(local["REPORT_DATETIME"] > previous_start) & (local["REPORT_DATETIME"] <= current_start)]
        current_signal = round(float(current["weighted_signal"].sum()), 2)
        previous_signal = round(float(previous["weighted_signal"].sum()), 2)
        metrics = _trend_changes(len(current), len(previous), current_signal, previous_signal)
        comparison_rows.append({"Period": f"Latest {months} months", "Current exposure": current_signal, "Previous exposure": previous_signal, "Current incidents": len(current), "Previous incidents": len(previous), **metrics})

    twelve_start = cutoff - pd.DateOffset(months=12)
    prior_start = twelve_start - pd.DateOffset(months=12)
    category_rows = []
    for category in CRIME_WEIGHTS:
        current = local[(local["CRIME_TYPE"] == category) & (local["REPORT_DATETIME"] > twelve_start) & (local["REPORT_DATETIME"] <= cutoff + pd.Timedelta(days=1))]
        previous = local[(local["CRIME_TYPE"] == category) & (local["REPORT_DATETIME"] > prior_start) & (local["REPORT_DATETIME"] <= twelve_start)]
        current_signal = round(float(current["weighted_signal"].sum()), 2)
        previous_signal = round(float(previous["weighted_signal"].sum()), 2)
        metrics = _trend_changes(len(current), len(previous), current_signal, previous_signal)
        category_rows.append({"Category": category, "Current incidents": len(current), "Previous incidents": len(previous), "Current exposure": current_signal, "Previous exposure": previous_signal, **metrics})

    monthly_start = cutoff - pd.DateOffset(months=24)
    monthly = local[local["REPORT_DATETIME"] > monthly_start].copy()
    monthly["Month"] = monthly["REPORT_DATETIME"].dt.to_period("M").dt.to_timestamp()
    monthly = monthly.groupby("Month", as_index=False).agg(Exposure=("weighted_signal", "sum"), Incidents=("CRIME_TYPE", "size"))
    all_months = pd.DataFrame({"Month": pd.date_range(monthly_start.to_period("M").to_timestamp(), cutoff.to_period("M").to_timestamp(), freq="MS")})
    monthly = all_months.merge(monthly, on="Month", how="left").fillna({"Exposure": 0, "Incidents": 0})
    monthly["Exposure"] = monthly["Exposure"].round(2)
    monthly["Incidents"] = monthly["Incidents"].astype(int)
    return {"cutoff": cutoff.date().isoformat(), "comparisons": pd.DataFrame(comparison_rows), "categories": pd.DataFrame(category_rows), "monthly": monthly}


def data_provenance() -> dict[str, str]:
    quality = data_quality_summary()
    return {"Source": DATA_SOURCE, "Coverage": f"{quality['first_report_date']} to {quality['last_report_date']}", "Data as of": quality["last_report_date"], "Valid coordinate records": f"{quality['valid_records']:,}", "Methodology": METHODOLOGY_VERSION, "Geography": "Toronto only", "Data warnings": str(len(quality["warnings"]))}


@lru_cache(maxsize=512)
def geocode_address(address: str) -> tuple[float, float, str]:
    clean = " ".join(str(address).split())
    if not clean:
        raise ValueError("Address is empty.")
    geolocator = Nominatim(user_agent="locivra-location-prioritization/1.0", timeout=10)
    for attempt in range(2):
        try:
            location = geolocator.geocode(clean, country_codes="ca", exactly_one=True)
            if not location:
                raise ValueError("Address could not be found. Add Toronto, Ontario and try again.")
            if not (TORONTO_BOUNDS[0] < location.latitude < TORONTO_BOUNDS[1] and TORONTO_BOUNDS[2] < location.longitude < TORONTO_BOUNDS[3]):
                raise ValueError("The current prototype supports Toronto locations only.")
            return float(location.latitude), float(location.longitude), str(location.address)
        except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError):
            if attempt == 1:
                raise RuntimeError("The address service is temporarily unavailable. Please try again.")
            time.sleep(1.0)
    raise RuntimeError("Address lookup failed.")


def result_as_dict(result: LocationResult) -> dict[str, Any]:
    return asdict(result)
