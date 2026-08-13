# Locivra Methodology v1.1

**Stage:** Validation-stage decision support
**Geography:** Toronto
**Controlled owner:** Alex Babb / Locivra
**Effective date:** August 13, 2026
**Change rule:** Any change to source categories, score formula, baseline logic,
weights, supported radii, priority bands or decision claims requires a new
methodology version and regression review.

## 1. Intended decision

Locivra Methodology v1.1 helps a multi-location organization decide which
submitted locations warrant deeper security review first. It produces a relative
review sequence and explainable evidence package. It does not predict crime,
certify safety, prescribe a control or estimate loss without client outcome data.

## 2. Evidence included in the score

The score uses five configured Toronto Police Service reported-crime categories:

| Category | Published weight |
|---|---:|
| Theft Over $5,000 | 30% |
| Break & Enter | 25% |
| Robbery | 25% |
| Assault | 15% |
| Auto Theft | 5% |

TTC stations, parks, street-light poles and approximate neighbourhood context are
displayed for discussion but do not change the v1.1 score. Client internal evidence
is used to validate and interpret the result; it does not silently alter the public-
data score.

## 3. Spatial calculation

For each category and submitted location, incidents inside the selected 250, 500,
750 or 1,000 metre radius are identified using geodesic distance. Each incident
receives linear distance-decay influence:

`distance influence = max(0, 1 - incident distance / selected radius)`

The category's local weighted exposure is the sum of these influences. Raw incident
counts remain visible separately.

## 4. Configured citywide reference baseline

The reference baseline represents expected linear-decay exposure under the
configured citywide incident density:

`baseline exposure = category records × (π × radius² / 3) / configured city area`

The city area is derived from the bounding extent of valid configured crime
records. Baselines therefore recalculate when a controlled data release is
activated. Each report identifies the data version used.

## 5. Category and composite scores

Baseline exposure maps to the middle of the category scale. Zero local exposure
maps to zero. Positive exposure uses the disclosed log-relative transformation:

`category score = clip(50 + 15 × ln(local exposure / baseline exposure), 0, 100)`

The composite review-priority score is:

`overall score = Σ(category score × published category weight)`

Displayed category contributions may differ from the overall score by a small
rounding amount; automated reconciliation flags differences above 0.2 points.

## 6. Review labels and portfolio tiers

Location review-priority labels are descriptive bands:

- 75–100: Critical review priority
- 60–74.9: High review priority
- 40–59.9: Moderate review priority
- Below 40: Lower review priority

Portfolio tiers and percentiles are relative to the submitted portfolio. They are
not universal risk classes or safety thresholds.

## 7. Historical direction

Six- and twelve-month comparisons use equal rolling windows anchored to the newest
configured report date. Raw-count change and weighted-exposure change are displayed
separately. Percentages are withheld when prior incidents are below 10 or prior
weighted exposure is below 0.50. Windows with fewer than 30 incidents are flagged
as low sample and interpreted cautiously.

## 8. Sensitivity and audit controls

Results can be stress-tested across every supported radius and four disclosed
weight profiles. Alternative profiles are assumption tests, not preferred answers.
Automated checks reconcile category weights, composite scores, displayed trend
percentages, source-file provenance and report generation.

## 9. Known limitations

The method does not include unreported events, client incident narratives, sales,
foot traffic, store hours, asset values, site layout, current controls, guard
quality, camera coverage effectiveness, reporting behaviour or causal claims. It
currently supports Toronto locations only. A qualified professional review is
required before selecting site controls.

## 10. Validation-stage statement

Methodology v1.1 is controlled and reproducible. External validation remains in progress.
Pilot evidence should document confirmed, partly supported, challenged
and unresolved signals. Agreement is not predictive accuracy; disagreement can
identify missing client evidence, operating context or assumptions requiring a
future controlled version.
