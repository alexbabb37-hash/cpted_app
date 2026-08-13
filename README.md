# Locivra

Locivra helps multi-location organizations identify which Toronto locations warrant deeper security review by combining historical reported-crime exposure with location context.

Locivra is decision support. It does not predict crime, determine whether a location is safe, or replace internal incident data, professional judgment, CPTED assessment, or a physical site visit.

Locivra is currently a validation-stage product and does not claim SOC 2, ISO
27001, PIPEDA certification, SSO, third-party penetration testing or enterprise
production hosting. See `docs/DATA_HANDLING_AND_SECURITY.md` for current pilot
controls, permitted data, retention/deletion rules and hosted-deployment gates.

## Current workflows

- Location assessment with score decomposition, evidence map, and radius sensitivity
- Two-location comparison using one shared methodology
- Portfolio ranking for 5-20 locations with percentiles and relative review tiers
- Branded PDF reports with data provenance and methodology boundaries
- Optional client evidence fields kept separate from the public-data exposure score
- Equal-window 6-month and 12-month historical changes plus a 24-month monthly trend
- Raw-count change and weighted-exposure change displayed as separate measures
- Consistent small-sample and unstable-baseline flags across every trend table
- Dynamic source-file coverage, row-quality warnings, and data provenance
- Portfolio ranking sensitivity across four radii and four disclosed weight profiles
- Automated score reconciliation for on-screen results, CSV outputs, and PDF reports
- Pilot-results scorecard measuring evidence support, changed priorities, overlooked locations, explanation clarity, actionability, process time and assumption sensitivity

## Data and methodology

- Source: Toronto Police Service Public Safety Data Portal
- Coverage: 2014-2026 report years
- Newest configured report date: March 31, 2026
- Geography: Toronto only
- Methodology: Locivra Methodology v1.1 — validation-stage decision support

The method uses geodesic distance, linear distance decay, a configured citywide reference baseline, and five published category weights. See `locivra_core.py` for the implemented formula, `docs/METHODOLOGY_V1_1.md` for the controlled statement, and the in-app methodology panels for interpretation.

## Run locally

```bash
cd /Users/alexbabb/Desktop/cpted_app
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically.

## Credibility checks

Run the automated calculation and report checks before a client demonstration or release:

```bash
cd /Users/alexbabb/Desktop/cpted_app
python3 -m pytest -q
```

The checks verify that category weights sum to 100%, composite scores reconcile,
raw and weighted trend percentages match their displayed inputs, sensitivity tables
contain every location and assumption, provenance is derived from the configured
files, and all three PDF generators complete successfully.

## Updating crime data safely

Never replace individual production CSV files by hand. Place a complete set of
the five configured Toronto Police CSV files in a separate staging directory,
then run a dry validation first:

```bash
cd /Users/alexbabb/Desktop/cpted_app
python3 scripts/update_crime_data.py /absolute/path/to/staged/files \
  --manifest-out data_manifests/candidate.json
```

The validation checks required files and columns, Toronto coordinate validity,
date coverage, exact duplicates, repeated event IDs, row counts and checksums. It
also recalculates the expected citywide baseline exposure for every crime category
at 250, 500, 750 and 1,000 metres. A staged release older than the active data is
blocked.

Only after reviewing a passing manifest and running the automated tests should a
release be activated:

```bash
python3 scripts/update_crime_data.py /absolute/path/to/staged/files --activate
python3 -m pytest -q
```

Activation requires all five files to pass, preserves the prior production files
in `data_backups/`, replaces the active files atomically, and writes a versioned
JSON manifest to `data_manifests/`. Keep each manifest with the corresponding
methodology version and generated client reports.

## Portfolio CSV

Download the template from the Portfolio Priority Ranking screen. Only `Address` is required. Recommended fields include Location ID, Location Name, location type, internal incident counts, loss amount, control coverage, and client notes.

Client inputs are retained for validation and reporting but do not change the Locivra Methodology v1.1 public-data exposure score.
