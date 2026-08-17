"""Polished PDF reports shared by all Locivra scoring pages."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import math
import hashlib

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String

from locivra_core import LocationResult, CRIME_WEIGHTS, DATA_SOURCE, METHODOLOGY_VERSION, comparison_explanation, comparison_interpretation, data_provenance, data_quality_summary, nearby_incidents, portfolio_radius_sensitivity, radius_sensitivity, reconcile_location_result, reconcile_results, result_warnings, temporal_trends, weight_sensitivity
from locivra_pilot import PilotScorecard

ROOT = Path(__file__).resolve().parent
NAVY = colors.HexColor("#081A33")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#3EC6C4")
INK = colors.HexColor("#102A43")
MUTED = colors.HexColor("#60758A")
MIST = colors.HexColor("#F2F7FA")
LINE = colors.HexColor("#D5E1E8")


def _styles():
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=s["Title"], fontName="Helvetica-Bold", fontSize=23, leading=28, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8),
        "subtitle": ParagraphStyle("Subtitle", parent=s["Normal"], fontName="Helvetica", fontSize=11, leading=16, textColor=BLUE, spaceAfter=16),
        "h1": ParagraphStyle("H1", parent=s["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=12, spaceAfter=9),
        "h2": ParagraphStyle("H2", parent=s["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=BLUE, spaceBefore=8, spaceAfter=6),
        "body": ParagraphStyle("Body", parent=s["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=INK, spaceAfter=7),
        "small": ParagraphStyle("Small", parent=s["BodyText"], fontName="Helvetica", fontSize=7.7, leading=10.5, textColor=MUTED, spaceAfter=4),
        "white": ParagraphStyle("White", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.white, alignment=TA_CENTER),
        "white_small": ParagraphStyle("WhiteSmall", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=6.4, leading=7.2, textColor=colors.white, alignment=TA_CENTER),
    }


def _page(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 24, width, 24, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(colors.white)
    classification = getattr(doc, "report_classification", "CLIENT CONFIDENTIAL")
    canvas.drawString(doc.leftMargin, height - 16, f"LOCIVRA  /  DECISION SUPPORT  /  {classification}")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    provenance = data_provenance()
    canvas.drawString(doc.leftMargin, 22, f"{DATA_SOURCE} | {provenance['Coverage']} | Data {provenance['Data version']}")
    canvas.drawRightString(width - doc.rightMargin, 22, f"Page {doc.page}")
    logo_path = ROOT / "locivra_logo_report.png"
    if logo_path.exists():
        canvas.drawImage(
            str(logo_path),
            width / 2 - .24 * inch,
            3,
            width=.48 * inch,
            height=.32 * inch,
            preserveAspectRatio=True,
            mask="auto",
        )
    canvas.restoreState()


def _doc(buffer, classification: str = "CLIENT CONFIDENTIAL"):
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=.62*inch, rightMargin=.62*inch, topMargin=.58*inch, bottomMargin=.55*inch, title="Locivra Report", author="Alex Babb / Locivra")
    doc.report_classification = classification.strip().upper() or "CLIENT CONFIDENTIAL"
    return doc


def _logo_story(story):
    logo_path = ROOT / "locivra_logo_report.png"
    if logo_path.exists():
        logo = Image(str(logo_path), width=1.35*inch, height=.9*inch)
        story.append(logo)
    else:
        story.append(Paragraph("LOCIVRA", _styles()["title"]))


def _metadata(report_type: str, count: int | None = None, analysis_key: str = ""):
    provenance = data_provenance()
    seed = "|".join((report_type, str(count or ""), analysis_key, provenance["Data version"], METHODOLOGY_VERSION))
    analysis_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = [["REPORT", report_type], ["GENERATED", generated], ["ANALYSIS ID", f"LOC-{analysis_id}"]]
    if count is not None:
        rows.append(["LOCATIONS", str(count)])
    table = Table(rows, colWidths=[.95*inch, 5.65*inch])
    table.setStyle(TableStyle([("FONTNAME", (0,0),(0,-1), "Helvetica-Bold"), ("TEXTCOLOR",(0,0),(0,-1),MUTED), ("TEXTCOLOR",(1,0),(1,-1),INK), ("FONTSIZE",(0,0),(-1,-1),8), ("BOTTOMPADDING",(0,0),(-1,-1),4), ("LINEBELOW",(0,-1),(-1,-1),.5,LINE)]))
    return table


def _score_table(result: LocationResult, styles):
    rows = [["Crime category", "Raw", "Weighted exposure", "Score", "Weight", "Contribution"]]
    for category, item in result.categories.items():
        rows.append([category, str(item.raw_incidents), f"{item.weighted_exposure:.2f}", f"{item.score:.1f}", f"{item.weight:.0%}", f"{item.contribution:.1f}"])
    table = Table(rows, colWidths=[1.75*inch, .62*inch, 1.05*inch, .62*inch, .65*inch, .9*inch], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("ALIGN",(1,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.4,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    return table


def _limitations(styles):
    text = f"<b>Responsible-use boundary.</b> This report applies {METHODOLOGY_VERSION} to historical police-reported incidents. It does not predict that crime will occur, certify a location as safe or unsafe, or replace internal incident data, operational knowledge, professional judgment, CPTED assessment, or a physical site visit."
    table = Table([[Paragraph(text, styles["small"])]], colWidths=[6.65*inch])
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FFF8E8")), ("BOX",(0,0),(-1,-1),.7,colors.HexColor("#D6A83E")), ("LEFTPADDING",(0,0),(-1,-1),11), ("RIGHTPADDING",(0,0),(-1,-1),11), ("TOPPADDING",(0,0),(-1,-1),9), ("BOTTOMPADDING",(0,0),(-1,-1),9)]))
    return table


def _compact_limitations(styles):
    text = "<b>Use boundary:</b> Historical reported-crime decision support only. This is not crime prediction, a safety certification, or a substitute for internal evidence, professional judgment, CPTED assessment, or a physical site visit."
    return Paragraph(text, styles["small"])


def _pct(value, withheld="Not shown"):
    return withheld if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:+.1f}%"


def _audit_note(results: list[LocationResult], styles):
    audit = reconcile_results(results)
    passed = int((audit["Status"] == "PASS").sum())
    rounding = float(audit["Display rounding difference"].abs().max()) if len(audit) else 0.0
    return Paragraph(
        f"<b>Automated reconciliation:</b> {passed} of {len(audit)} location calculations passed. "
        f"Largest display-only rounding difference: {rounding:.1f} points.",
        styles["small"],
    )


def _source_warning_note(results: list[LocationResult], styles):
    quality = data_quality_summary()
    invalid_coordinates = int(quality["files"]["Invalid coordinates"].sum())
    missing_dates = int(quality["files"]["Missing dates"].sum())
    location_warnings = []
    for result in results:
        zero_categories = [item.category for item in result.categories.values() if item.raw_incidents == 0]
        if zero_categories:
            location_warnings.append(f"No local incidents for {', '.join(zero_categories)}")
    coverage_warnings = [warning for warning in quality["warnings"] if "latest record is" in warning]
    if invalid_coordinates or missing_dates or location_warnings or coverage_warnings:
        text = f"{invalid_coordinates:,} source rows excluded for missing or out-of-range coordinates; {missing_dates:,} rows excluded from trend calculations for missing dates."
        if coverage_warnings:
            text += " Category coverage warning: " + " | ".join(coverage_warnings)
        if location_warnings:
            text += " " + " | ".join(location_warnings[:2])
    else:
        text = "No configured missing-data warnings were detected."
    return Paragraph(f"<b>Data-quality warnings:</b> {escape(text)}", styles["small"])


def _short_address(address: str, limit: int = 54) -> str:
    """Keep decision tables readable when geocoders return full regional names."""
    parts = [part.strip() for part in address.split(",") if part.strip()]
    shortened = ", ".join(parts[:3])
    return shortened if len(shortened) <= limit else shortened[: limit - 1].rstrip() + "..."


def _band_color(score: float):
    if score >= 75:
        return colors.HexColor("#D95C5C")
    if score >= 60:
        return colors.HexColor("#E59B42")
    if score >= 40:
        return colors.HexColor("#D6B84B")
    return colors.HexColor("#55A985")


def _portfolio_tier(rank: int, total: int) -> str:
    if rank <= max(1, round(total * .25)):
        return "Tier 1 - Review first"
    if rank <= max(2, round(total * .60)):
        return "Tier 2 - Secondary review"
    return "Tier 3 - Monitor"


def build_pilot_scorecard_report(scorecard: PilotScorecard, review_frame, targets: dict[str, float], classification: str = "CLIENT CONFIDENTIAL") -> BytesIO:
    """Create a bounded executive pilot-results brief from the shared formulas."""
    b, styles, story = BytesIO(), _styles(), []
    _logo_story(story)
    story += [
        Paragraph("Pilot Results Scorecard", styles["title"]),
        Paragraph("Measured usefulness, decision impact and evidence boundaries", styles["subtitle"]),
        _metadata("Pilot validation scorecard", scorecard.completed_reviews),
        Spacer(1, 10),
    ]
    recommendation_color = colors.HexColor("#EAF6F6") if scorecard.recommendation == "EXPANSION CASE" else colors.HexColor("#FFF8E8")
    recommendation = Table([[Paragraph(f"<b>{escape(scorecard.recommendation)}</b><br/>{escape(scorecard.recommendation_reason)}", styles["body"])]], colWidths=[6.55*inch])
    recommendation.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),recommendation_color), ("BOX",(0,0),(-1,-1),1,CYAN), ("LEFTPADDING",(0,0),(-1,-1),14), ("RIGHTPADDING",(0,0),(-1,-1),14), ("TOPPADDING",(0,0),(-1,-1),12), ("BOTTOMPADDING",(0,0),(-1,-1),9)]))
    story += [recommendation, Paragraph("Executive measures", styles["h1"])]
    minutes = "Not measured" if scorecard.minutes_returned is None else f"{scorecard.minutes_returned:.0f} min"
    kpis = [[
        Paragraph(f"<b>Reviewed</b><br/><font size='18'>{scorecard.completed_reviews}</font>", styles["body"]),
        Paragraph(f"<b>Evidence support</b><br/><font size='18'>{scorecard.weighted_evidence_support_rate:.0%}</font>", styles["body"]),
        Paragraph(f"<b>Priorities changed</b><br/><font size='18'>{scorecard.priorities_changed}</font>", styles["body"]),
        Paragraph(f"<b>Overlooked surfaced</b><br/><font size='18'>{scorecard.overlooked_sites_surfaced}</font>", styles["body"]),
        Paragraph(f"<b>Minutes returned</b><br/><font size='18'>{minutes}</font>", styles["body"]),
    ]]
    kpi_table = Table(kpis, colWidths=[1.31*inch]*5)
    kpi_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),MIST), ("BOX",(0,0),(-1,-1),.6,LINE), ("INNERGRID",(0,0),(-1,-1),.4,LINE), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),8), ("RIGHTPADDING",(0,0),(-1,-1),8), ("TOPPADDING",(0,0),(-1,-1),8), ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story += [kpi_table, Paragraph("Agreed targets and results", styles["h1"])]
    rows = [["Measure", "Result", "Target", "Status"]]
    rows += [
        ["Completed evidence reviews", str(scorecard.completed_reviews), str(int(targets["minimum_completed_reviews"])), scorecard.completed_review_status],
        ["Weighted evidence support", f"{scorecard.weighted_evidence_support_rate:.0%}", f"{targets['weighted_evidence_support_rate']:.0%}", scorecard.evidence_support_status],
        ["Explanation clarity", f"{scorecard.explanation_clarity_rate:.0%}", f"{targets['explanation_clarity_rate']:.0%}", scorecard.explanation_clarity_status],
        ["Actionability", f"{scorecard.actionability_rate:.0%}", f"{targets['actionability_rate']:.0%}", scorecard.actionability_status],
        ["Median sensitivity rank move", "Not assessed" if scorecard.median_sensitivity_move is None else f"{scorecard.median_sensitivity_move:.1f}", f"≤ {targets['maximum_median_sensitivity_move']:.1f}", scorecard.sensitivity_status],
    ]
    target_table = Table(rows, colWidths=[2.75*inch,1.15*inch,1.15*inch,1.5*inch], repeatRows=1)
    target_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(-1,1),(-1,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("ALIGN",(1,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.4,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [target_table, PageBreak(), Paragraph("Evidence review and boundaries", styles["title"]), Paragraph("The observations behind the executive scorecard", styles["subtitle"]), Paragraph("Evidence outcomes", styles["h1"])]
    evidence_rows = [["Confirmed", "Partly supported", "Challenged", "Unresolved"], [scorecard.confirmed, scorecard.partly_supported, scorecard.challenged, scorecard.unresolved]]
    evidence_table = Table(evidence_rows, colWidths=[1.64*inch]*4)
    evidence_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),9), ("ALIGN",(0,0),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.4,LINE), ("BACKGROUND",(0,1),(-1,1),MIST), ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story += [evidence_table, Paragraph("Location-level evidence register", styles["h1"])]
    detail_rows = [["Location", "Evidence outcome", "Priority changed", "Overlooked surfaced", "Clear", "Actionable"]]
    used = review_frame[review_frame.get("Location ID", "").fillna("").astype(str).str.strip().ne("")]
    for _, row in used.head(20).iterrows():
        detail_rows.append([
            Paragraph(escape(str(row.get("Location ID", ""))), styles["small"]),
            Paragraph(escape(str(row.get("Evidence outcome", ""))), styles["small"]),
            str(row.get("Priority changed?", "")),
            str(row.get("Overlooked site surfaced?", "")),
            str(row.get("Explanation clear?", "")),
            str(row.get("Next action clear?", "")),
        ])
    detail_table = Table(detail_rows, colWidths=[1.05*inch,1.45*inch,1.05*inch,1.25*inch,.9*inch,.95*inch], repeatRows=1)
    detail_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7), ("ALIGN",(2,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story += [detail_table, Paragraph("How to interpret this result", styles["h1"]), Paragraph("Weighted evidence support gives full credit to confirmed signals and half credit to partly supported signals. It is a pilot-usefulness measure—not predictive accuracy. Challenged and unresolved cases should be retained because they identify missing client evidence, unclear explanations, operating context or model assumptions that require refinement.", styles["body"])]
    if scorecard.baseline_triage_minutes is not None:
        story.append(Paragraph(f"<b>Process-time evidence:</b> Current process {scorecard.baseline_triage_minutes:.0f} minutes; Locivra-assisted process {scorecard.locivra_triage_minutes:.0f} minutes; difference {scorecard.minutes_returned:+.0f} minutes ({scorecard.time_reduction_rate:+.0%}). This is measured staff time only, not a dollar-savings or loss-reduction claim.", styles["body"]))
    provenance = data_provenance()
    story += [Paragraph("Evidence and use boundary", styles["h1"]), Paragraph(f"<b>Data version:</b> {escape(provenance['Data version'])}<br/><b>Methodology:</b> {escape(METHODOLOGY_VERSION)}<br/><b>Reviewed locations:</b> {scorecard.completed_reviews}<br/><b>Decision claims:</b> Priorities changed and overlooked locations surfaced are recorded observations from this pilot—not proof that incidents were prevented.", styles["body"]), _compact_limitations(styles)]
    doc = _doc(b, classification); doc.build(story, onFirstPage=_page, onLaterPages=_page); b.seek(0); return b


def _incident_map(result: LocationResult) -> Drawing:
    """Scaled local evidence plot with a true site centre and analysis boundary."""
    points = nearby_incidents(result.latitude, result.longitude, result.radius_metres, limit=1200)
    width, height = 475, 190
    drawing = Drawing(width, height)
    plot_x, plot_y, plot_size = 18, 14, 165
    centre_x = plot_x + plot_size / 2
    centre_y = plot_y + plot_size / 2
    boundary_radius = plot_size * .45
    drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#F7FAFC"), strokeColor=LINE))
    drawing.add(Rect(plot_x, plot_y, plot_size, plot_size, fillColor=colors.white, strokeColor=LINE))
    drawing.add(Line(centre_x, plot_y + 6, centre_x, plot_y + plot_size - 6, strokeColor=colors.HexColor("#E5EDF2"), strokeWidth=.5))
    drawing.add(Line(plot_x + 6, centre_y, plot_x + plot_size - 6, centre_y, strokeColor=colors.HexColor("#E5EDF2"), strokeWidth=.5))
    drawing.add(Circle(centre_x, centre_y, boundary_radius / 2, fillColor=None, strokeColor=colors.HexColor("#B9CAD5"), strokeWidth=.7, strokeDashArray=[3, 3]))
    drawing.add(Circle(centre_x, centre_y, boundary_radius, fillColor=None, strokeColor=BLUE, strokeWidth=1.1))
    palette = {
        "Theft Over $5000": colors.HexColor("#D95C5C"),
        "Break & Enter": colors.HexColor("#E59B42"),
        "Robbery": colors.HexColor("#7A5AA6"),
        "Assault": colors.HexColor("#2563EB"),
        "Auto Theft": colors.HexColor("#3EC6C4"),
    }
    if not points.empty:
        for row in points.itertuples(index=False):
            dx = (row.longitude - result.longitude) * 111_320 * math.cos(math.radians(result.latitude))
            dy = (row.latitude - result.latitude) * 111_320
            x = centre_x + dx / result.radius_metres * boundary_radius
            y = centre_y + dy / result.radius_metres * boundary_radius
            drawing.add(Circle(x, y, 1.15, fillColor=palette.get(row.category, MUTED), strokeColor=None))
    drawing.add(Circle(centre_x, centre_y, 4.2, fillColor=NAVY, strokeColor=colors.white, strokeWidth=1.2))
    drawing.add(String(plot_x + 5, plot_y + plot_size - 13, "N", fontName="Helvetica-Bold", fontSize=7, fillColor=NAVY))
    drawing.add(String(plot_x + 5, plot_y + 7, f"Outer ring: {result.radius_metres} m", fontName="Helvetica", fontSize=6.5, fillColor=MUTED))
    drawing.add(String(plot_x + 5, plot_y + 17, f"Inner ring: {result.radius_metres // 2} m", fontName="Helvetica", fontSize=6.5, fillColor=MUTED))

    legend_x = 230
    drawing.add(String(legend_x, 168, "INCIDENT CATEGORIES", fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY))
    for index, category in enumerate(CRIME_WEIGHTS):
        y = 148 - index * 22
        drawing.add(Circle(legend_x + 4, y + 3, 3, fillColor=palette[category], strokeColor=None))
        drawing.add(String(legend_x + 14, y, category, fontName="Helvetica", fontSize=7.3, fillColor=INK))
        drawing.add(String(452, y, f"{result.categories[category].raw_incidents:,}", fontName="Helvetica-Bold", fontSize=7.3, fillColor=INK, textAnchor="end"))
    drawing.add(Line(legend_x, 38, 455, 38, strokeColor=LINE, strokeWidth=.7))
    drawing.add(Circle(legend_x + 4, 24, 4, fillColor=NAVY, strokeColor=colors.white, strokeWidth=.8))
    drawing.add(String(legend_x + 14, 21, "Submitted location", fontName="Helvetica-Bold", fontSize=7.3, fillColor=INK))
    drawing.add(String(legend_x, 7, "Counts use all records; plotted points may be sampled.", fontName="Helvetica", fontSize=6.4, fillColor=MUTED))
    return drawing


def _monthly_trend_chart(trends: dict) -> Drawing:
    monthly = trends["monthly"]
    width, height = 475, 145
    left, bottom, chart_w, chart_h = 34, 27, 425, 96
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#F7FAFC"), strokeColor=LINE))
    maximum = max(float(monthly["Exposure"].max()), 1.0)
    bar_gap = 2
    bar_width = chart_w / max(len(monthly), 1) - bar_gap
    for index, row in enumerate(monthly.itertuples(index=False)):
        x = left + index * chart_w / len(monthly)
        bar_height = float(row.Exposure) / maximum * chart_h
        drawing.add(Rect(x, bottom, max(bar_width, 2), bar_height, fillColor=BLUE, strokeColor=None))
        if index % 6 == 0 or index == len(monthly) - 1:
            drawing.add(String(x, 10, row.Month.strftime("%b %y"), fontName="Helvetica", fontSize=6.3, fillColor=MUTED))
    drawing.add(Line(left, bottom, left + chart_w, bottom, strokeColor=INK, strokeWidth=.7))
    drawing.add(String(4, bottom + chart_h - 2, f"{maximum:.1f}", fontName="Helvetica", fontSize=6.2, fillColor=MUTED))
    drawing.add(String(13, bottom - 2, "0", fontName="Helvetica", fontSize=6.2, fillColor=MUTED))
    drawing.add(String(left, 131, "Monthly distance- and category-weighted historical exposure", fontName="Helvetica-Bold", fontSize=7.5, fillColor=NAVY))
    return drawing


def _trend_interpretation(trends: dict) -> str:
    rows = trends["comparisons"].to_dict("records")
    six, twelve = rows
    if six["Exposure change (%)"] is None or twelve["Exposure change (%)"] is None:
        return "At least one comparison window has too little prior exposure for a stable percentage. Review incident counts and the monthly pattern rather than relying on a single change figure."
    six_change, twelve_change = six["Exposure change (%)"], twelve["Exposure change (%)"]
    if six_change > 0 and twelve_change > 0:
        direction = "Both comparison windows are higher than their prior periods, indicating a broadly rising historical signal."
    elif six_change < 0 and twelve_change < 0:
        direction = "Both comparison windows are lower than their prior periods, indicating a broadly declining historical signal."
    else:
        direction = "The six- and twelve-month comparisons move in different directions, so the historical signal is mixed rather than clearly rising or falling."
    caution = " Low incident volume makes the percentage less stable." if any(row["Stability flag"] == "Low sample" for row in rows) else ""
    return direction + caution


def _ranking_chart(results: list[LocationResult]) -> Drawing:
    """Compact editable vector chart; no raster screenshots or invented data."""
    width, row_h, label_w, bar_w = 475, 15, 186, 225
    drawing = Drawing(width, row_h * len(results) + 20)
    drawing.add(String(label_w, row_h * len(results) + 11, "0", fontName="Helvetica", fontSize=6.5, fillColor=MUTED))
    drawing.add(String(label_w + bar_w - 12, row_h * len(results) + 11, "100", fontName="Helvetica", fontSize=6.5, fillColor=MUTED))
    for index, result in enumerate(results):
        y = row_h * (len(results) - index - 1) + 2
        drawing.add(String(0, y + 2, f"{index + 1}. {_short_address(result.address, 34)}", fontName="Helvetica", fontSize=6.6, fillColor=INK))
        drawing.add(Rect(label_w, y, bar_w, 8, fillColor=colors.HexColor("#E8EFF4"), strokeColor=None))
        drawing.add(Rect(label_w, y, bar_w * result.overall_score / 100, 8, fillColor=_band_color(result.overall_score), strokeColor=None))
        drawing.add(String(label_w + bar_w + 8, y + 1, f"{result.overall_score:.1f}", fontName="Helvetica-Bold", fontSize=6.8, fillColor=INK))
    return drawing


def _heatmap(results: list[LocationResult], styles) -> Table:
    categories = list(CRIME_WEIGHTS)
    rows = [["Location"] + [Paragraph(category.replace("Theft Over $5000", "Theft >$5K"), styles["small"]) for category in categories]]
    for index, result in enumerate(results, 1):
        rows.append([Paragraph(f"{index}. {_short_address(result.address, 30)}", styles["small"])] + [f"{result.categories[category].score:.0f}" for category in categories])
    table = Table(rows, colWidths=[2.55*inch] + [.77*inch] * len(categories), repeatRows=1)
    commands = [("BACKGROUND", (0,0), (-1,0), NAVY), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 6.6), ("ALIGN", (1,1), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("GRID", (0,0), (-1,-1), .35, LINE), ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]
    for row_index, result in enumerate(results, 1):
        for column_index, category in enumerate(categories, 1):
            score = result.categories[category].score
            shade = colors.Color(1, 1 - .30 * score / 100, 1 - .36 * score / 100)
            commands.append(("BACKGROUND", (column_index,row_index), (column_index,row_index), shade))
    table.setStyle(TableStyle(commands))
    return table


def build_site_report(result: LocationResult, classification: str = "CLIENT CONFIDENTIAL") -> BytesIO:
    b, styles, story = BytesIO(), _styles(), []
    trends = temporal_trends(result.latitude, result.longitude, result.radius_metres)
    drivers = sorted(result.categories.values(), key=lambda item: item.contribution, reverse=True)[:3]
    total_incidents = sum(item.raw_incidents for item in result.categories.values())
    dominant = drivers[0]

    # Page 1 - executive interpretation and score construction.
    _logo_story(story)
    story += [
        Paragraph("Location Priority Assessment", styles["title"]),
        Paragraph("What the score means, why the location ranks here, and what to validate next", styles["subtitle"]),
        _metadata("Location assessment", analysis_key=f"{result.latitude:.6f}|{result.longitude:.6f}|{result.radius_metres}|{result.overall_score:.1f}"),
        Spacer(1, 10),
    ]
    summary = Table([[Paragraph("OVERALL PRIORITY SCORE", styles["small"]), Paragraph(f"<b>{result.overall_score:.1f}/100</b>", styles["h1"]), Paragraph(escape(result.priority_label), styles["h2"])]], colWidths=[2.5*inch, 1.5*inch, 2.65*inch])
    summary.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF6F6")), ("BOX",(0,0),(-1,-1),1,CYAN), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),12), ("TOPPADDING",(0,0),(-1,-1),10), ("BOTTOMPADDING",(0,0),(-1,-1),10)]))
    quick_read = (
        f"This location is a <b>{escape(result.priority_label.lower())}</b> under {METHODOLOGY_VERSION}. "
        f"Its largest weighted contributor is <b>{escape(dominant.category)}</b>, adding <b>{dominant.contribution:.1f} points</b> to the overall score. "
        f"The result is based on {total_incidents:,} category incident records inside the selected radius across the configured data period. "
        "Use the ranking to set review order, then test it against internal incidents, loss information, existing controls and observed site conditions."
    )
    quick_box = Table([[Paragraph(quick_read, styles["body"])]], colWidths=[6.55*inch])
    quick_box.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),MIST), ("BOX",(0,0),(-1,-1),.6,LINE), ("LEFTPADDING",(0,0),(-1,-1),13), ("RIGHTPADDING",(0,0),(-1,-1),13), ("TOPPADDING",(0,0),(-1,-1),10), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [
        Paragraph("The 30-second read", styles["h1"]),
        summary,
        Spacer(1, 8),
        quick_box,
        Paragraph("Assessment scope", styles["h1"]),
        Paragraph(
            f"<b>Submitted location:</b> {escape(result.submitted_address or result.address)}<br/>"
            f"<b>Matched location:</b> {escape(result.address)}<br/>"
            f"<b>Analysis boundary:</b> {result.radius_metres} metres from the matched point<br/>"
            f"<b>Data:</b> {DATA_SOURCE}; {escape(data_provenance()['Coverage'])}; version {escape(data_provenance()['Data version'])}<br/>"
            f"<b>Methodology:</b> {result.methodology_version}",
            styles["body"],
        ),
        Paragraph("How the score is built", styles["h1"]),
        _score_table(result, styles),
        _audit_note([result], styles),
    ]
    driver_rows = [["Leading contributor", "Score", "Weight", "Points", "Evidence"]]
    for item in drivers:
        driver_rows.append([
            Paragraph(escape(item.category), styles["small"]),
            f"{item.score:.1f}",
            f"{item.weight:.0%}",
            f"{item.contribution:.1f}",
            Paragraph(f"{item.raw_incidents:,} incidents; {item.weighted_exposure:.2f} weighted exposure", styles["small"]),
        ])
    driver_table = Table(driver_rows, colWidths=[1.35*inch, .65*inch, .65*inch, .65*inch, 3.0*inch], repeatRows=1)
    driver_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.6),
        ("ALIGN",(1,1),(3,-1),"CENTER"), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]),
        ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]))

    # Page 2 - spatial evidence and assumption sensitivity.
    story += [PageBreak(), Paragraph("Spatial evidence", styles["title"]), Paragraph("Where the historical incident evidence sits relative to the submitted location", styles["subtitle"]), _incident_map(result)]
    story.append(Paragraph("How to read the evidence plot", styles["h1"]))
    story.append(Paragraph(
        f"The navy point marks the submitted location. The blue outer ring is the selected {result.radius_metres}-metre analysis boundary and the dashed ring is {result.radius_metres // 2} metres. "
        "Incidents closer to the centre receive more influence through linear distance decay. The plot is a scaled local evidence view, not a street map or a prediction of where a future event will occur.",
        styles["body"],
    ))
    context = result.context
    story += [Paragraph("Environmental and neighbourhood context", styles["h1"]), Paragraph(escape(context.get("note", "Context only; not included in the score.")), styles["small"])]
    context_rows = [["Nearest TTC station", f"{context.get('nearest_ttc_station','Not available')} ({context.get('ttc_distance_metres','-')} m)"], ["Parks in radius", str(context.get("parks_within_radius", "-"))], ["Street-light poles in radius", str(context.get("street_light_poles_within_radius", "-"))], ["Approximate neighbourhood", str(context.get("approximate_neighbourhood", "Not available"))], ["Approximate population", f"{context.get('approximate_neighbourhood_population', 0):,}" if context.get("approximate_neighbourhood_population") else "Not available"]]
    ct = Table(context_rows, colWidths=[2.2*inch, 4.45*inch])
    ct.setStyle(TableStyle([("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,MIST]), ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("GRID",(0,0),(-1,-1),.35,LINE), ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story += [ct, Spacer(1, 3)]
    sensitivity = radius_sensitivity(result.address, result.latitude, result.longitude)
    sensitivity_rows = [["Radius", "Priority score", "Review label"]]
    for row in sensitivity.to_dict("records"):
        sensitivity_rows.append([f"{row['Radius (m)']} m", f"{row['Priority score']:.1f}", Paragraph(escape(row["Review label"]), styles["small"])])
    sensitivity_table = Table(sensitivity_rows, colWidths=[1.25*inch,1.35*inch,3.65*inch], repeatRows=1)
    sensitivity_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.6), ("ALIGN",(0,1),(1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    score_range = sensitivity["Priority score"].max() - sensitivity["Priority score"].min()
    sensitivity_text = (
        f"The score changes by {score_range:.1f} points across the tested 250- to 1,000-metre boundaries. "
        + ("That is a relatively stable signal across radius assumptions." if score_range < 8 else "That spread is material, so the selected boundary should be discussed before making a review decision.")
    )
    story += [Paragraph("Radius sensitivity", styles["h1"]), Paragraph(sensitivity_text, styles["small"]), sensitivity_table]

    # Page 3 - historical direction and validation plan.
    story += [PageBreak(), Paragraph("Historical direction", styles["title"]), Paragraph("What changed, over what period, and how stable the change appears", styles["subtitle"])]
    interpretation_box = Table([[Paragraph(_trend_interpretation(trends), styles["body"])]], colWidths=[6.55*inch])
    interpretation_box.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF6F6")), ("BOX",(0,0),(-1,-1),1,CYAN), ("LEFTPADDING",(0,0),(-1,-1),13), ("RIGHTPADDING",(0,0),(-1,-1),13), ("TOPPADDING",(0,0),(-1,-1),10), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [Paragraph("Direction summary", styles["h1"]), interpretation_box, Spacer(1, 8), _monthly_trend_chart(trends)]

    trend_rows = [[Paragraph(label, styles["white_small"]) for label in ("Window", "Incidents<br/>now / prior", "Raw count<br/>change", "Exposure<br/>now / prior", "Weighted exposure<br/>change", "Stability")]]
    for row in trends["comparisons"].to_dict("records"):
        trend_rows.append([row["Period"], f"{row['Current incidents']} / {row['Previous incidents']}", _pct(row["Count change (%)"]), f"{row['Current exposure']:.1f} / {row['Previous exposure']:.1f}", _pct(row["Exposure change (%)"]), Paragraph(escape(row["Stability note"]), styles["small"])])
    trend_table = Table(trend_rows, colWidths=[.85*inch,.9*inch,.78*inch,1.0*inch,.92*inch,2.2*inch], repeatRows=1)
    trend_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,1),(-1,-1),7.2), ("ALIGN",(1,1),(-2,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [Paragraph("Equal-window comparisons", styles["h1"]), Paragraph(f"Windows are anchored to the newest configured report date ({trends['cutoff']}). Exposure combines distance decay and published category weights.", styles["body"]), trend_table]

    category_rows = [[Paragraph(label, styles["white_small"]) for label in ("Category", "Incidents<br/>now / prior", "Raw count<br/>change", "Exposure<br/>now / prior", "Weighted exposure<br/>change", "Stability")]]
    for row in trends["categories"].to_dict("records"):
        category_rows.append([row["Category"], f"{row['Current incidents']} / {row['Previous incidents']}", _pct(row["Count change (%)"]), f"{row['Current exposure']:.2f} / {row['Previous exposure']:.2f}", _pct(row["Exposure change (%)"]), Paragraph(escape(row["Stability note"]), styles["small"])])
    category_table = Table(category_rows, colWidths=[1.12*inch,.88*inch,.82*inch,1.02*inch,.86*inch,1.95*inch], repeatRows=1)
    category_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.4), ("ALIGN",(1,1),(3,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [Paragraph("Category-level 12-month direction", styles["h1"]), category_table]

    # Page 4 - decision guidance, validation and method boundaries.
    story += [
        PageBreak(),
        Paragraph("Decision and validation plan", styles["title"]),
        Paragraph("How to use the evidence without treating the score as a final answer", styles["subtitle"]),
        Paragraph("Why this location ranks here", styles["h1"]),
        Paragraph("Contributors are ordered by their weighted impact on the overall score.", styles["small"]),
        driver_table,
        Paragraph("Recommended validation questions", styles["h1"]),
    ]
    for item in drivers:
        story.append(Paragraph(f"- Do internal incidents, loss records and staff observations support the <b>{escape(item.category.lower())}</b> signal?", styles["body"]))
    story += [
        Paragraph("What should happen next", styles["h1"]),
        Paragraph("Validate the leading contributors against internal evidence and current operating conditions. If the location remains a priority, conduct a qualified site-level security or CPTED assessment before selecting controls. Record agreements and disagreements so the model can be refined rather than treated as final.", styles["body"]),
        Paragraph("Method in plain language", styles["h1"]),
        Paragraph(
            "Incidents inside the selected boundary are measured using geodesic distance. Events closer to the submitted location receive more influence through linear distance decay. "
            "Each category is compared with the configured citywide reference baseline and combined using the published category weights. The radius sensitivity table shows how much the result depends on the selected boundary.",
            styles["body"],
        ),
        Paragraph("What is not included", styles["h1"]),
        Paragraph(
            "The score does not include unreported events, internal company incidents, store hours, sales volume, foot traffic, existing controls, site layout or current operating conditions. "
            "TTC, parks, lighting and neighbourhood information are shown as context and are not currently included in the score.",
            styles["body"],
        ),
        Paragraph("Data provenance and calculation audit", styles["h1"]),
        Paragraph("<b>Source:</b> " + escape(DATA_SOURCE) + "<br/><b>Coverage:</b> " + escape(data_provenance()["Coverage"]) + "<br/><b>Data as of:</b> " + escape(data_provenance()["Data as of"]) + "<br/><b>Data version:</b> " + escape(data_provenance()["Data version"]) + "<br/><b>Methodology:</b> " + escape(METHODOLOGY_VERSION), styles["body"]),
        _audit_note([result], styles),
        _source_warning_note([result], styles),
    ]
    doc = _doc(b, classification); doc.build(story, onFirstPage=_page, onLaterPages=_page); b.seek(0); return b


def build_comparison_report(results: list[LocationResult], classification: str = "CLIENT CONFIDENTIAL") -> BytesIO:
    if len(results) != 2:
        raise ValueError("The comparison report requires exactly two scored locations.")
    b, styles, story = BytesIO(), _styles(), []
    first, second = results
    decision = comparison_interpretation(first, second)
    explanation = comparison_explanation(first, second)
    higher = explanation["higher"]
    higher_label = explanation["higher_label"]
    lower_label = explanation["lower_label"]
    location_names = [
        _short_address(first.submitted_address or first.address, 34),
        _short_address(second.submitted_address or second.address, 34),
    ]
    higher_name = location_names[0] if higher_label == "Location 1" else location_names[1]
    lower_name = location_names[1] if higher_label == "Location 1" else location_names[0]
    first_sensitivity = radius_sensitivity(first.address, first.latitude, first.longitude)
    second_sensitivity = radius_sensitivity(second.address, second.latitude, second.longitude)
    initial_gaps = [
        left["Priority score"] - right["Priority score"]
        for left, right in zip(first_sensitivity.to_dict("records"), second_sensitivity.to_dict("records"))
    ]
    order_is_stable = all(gap >= 3 for gap in initial_gaps) or all(gap <= -3 for gap in initial_gaps)
    leading_categories = " and ".join(item["category"] for item in explanation["leading_drivers"])

    # Page 1 - answer first, then show the most decision-relevant numbers.
    _logo_story(story)
    story += [
        Paragraph("Location Comparison Report", styles["title"]),
        Paragraph("Which location should be reviewed first, what creates the difference, and how stable the result is", styles["subtitle"]),
        _metadata("Location comparison", len(results), "|".join(f"{r.latitude:.6f},{r.longitude:.6f},{r.radius_metres},{r.overall_score:.1f}" for r in results)),
        Spacer(1, 10),
        Paragraph("Executive recommendation", styles["h1"]),
    ]
    decision_box = Table([[
        Paragraph(f"<b>REVIEW FIRST</b><br/><font size='15'>{escape(higher_name)}</font>", styles["body"]),
        Paragraph(
            f"<b>{escape(higher_name)} scores {higher.overall_score:.1f}, compared with {explanation['lower'].overall_score:.1f} for {escape(lower_name)}.</b><br/>"
            f"The {decision['difference']:.1f}-point difference is driven mainly by {escape(leading_categories)}. "
            f"The ordering is {'consistent across every tested radius' if order_is_stable else 'sensitive to the analysis radius and should be treated cautiously'}.",
            styles["body"],
        ),
    ]], colWidths=[2.15*inch, 4.35*inch])
    decision_box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EAF6F6")),
        ("BOX", (0,0), (-1,-1), 1, CYAN),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 13),
        ("RIGHTPADDING", (0,0), (-1,-1), 13),
        ("TOPPADDING", (0,0), (-1,-1), 11),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story += [decision_box, Spacer(1, 9)]

    rows = [
        ["Measure", "Location 1", "Location 2"],
        ["Submitted address"] + [Paragraph(escape(r.submitted_address or r.address), styles["small"]) for r in results],
        ["Matched address"] + [Paragraph(escape(r.address), styles["small"]) for r in results],
        ["Overall score"] + [f"{r.overall_score:.1f}/100" for r in results],
        ["Review priority"] + [Paragraph(escape(r.priority_label), styles["small"]) for r in results],
        ["Analysis radius"] + [f"{r.radius_metres} m" for r in results],
        ["Latitude / longitude"] + [f"{r.latitude:.5f}, {r.longitude:.5f}" for r in results],
    ]
    widths = [1.55*inch, 2.55*inch, 2.55*inch]
    table = Table(rows, colWidths=widths)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("ALIGN",(1,3),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.4,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [table, Spacer(1, 7), Paragraph("Why this location comes first", styles["h1"]), Paragraph(
        f"In simple terms, the historical evidence around <b>{escape(higher_name)}</b> is stronger in the categories that carry the most influence in the model. "
        "That creates a higher review priority - not a prediction that an incident will happen.",
        styles["body"],
    )]
    lead_parts = [
        f"<b>{escape(item['category'])}</b> ({item['contribution_difference']:+.1f} points)"
        for item in explanation["leading_drivers"][:2]
    ]
    story.append(Paragraph(
        f"The largest score differences are {' and '.join(lead_parts)}. "
        "The complete counts, exposure values and calculations are shown on the next page.",
        styles["body"],
    ))
    story += [Paragraph(
        f"<b>Decision:</b> Review {escape(higher_name)} first under the current method. "
        "Validate the result against internal loss, incident and operating information before selecting an intervention.",
        styles["body"],
    ), PageBreak()]

    # Page 2 - every scoring input and output for both locations.
    story += [Paragraph("Complete score evidence", styles["title"]), Paragraph("All category numbers used to construct both composite scores", styles["subtitle"]), Paragraph(
        f"<b>Location 1:</b> {escape(location_names[0])}<br/><b>Location 2:</b> {escape(location_names[1])}<br/>"
        "Raw incidents show volume. Weighted exposure gives closer incidents more influence. Baseline is the citywide comparison value. Points are what each category adds to the final score.",
        styles["body"],
    )]
    full_rows = [[Paragraph(label, styles["white"]) for label in ("Category", "Raw incidents", "Weighted exposure", "Baseline", "Category score", "Weight", "Points")]]
    for label, result in (("LOCATION 1", first), ("LOCATION 2", second)):
        full_rows.append([Paragraph(f"<b>{label}</b>", styles["small"]), "", "", "", "", "", ""])
        for category in CRIME_WEIGHTS:
            item = result.categories[category]
            full_rows.append([
                Paragraph(escape(category), styles["small"]),
                f"{item.raw_incidents:,}",
                f"{item.weighted_exposure:.2f}",
                f"{item.baseline_exposure:.2f}",
                f"{item.score:.1f}",
                f"{item.weight:.0%}",
                f"{item.contribution:.1f}",
            ])
    full_table = Table(full_rows, colWidths=[1.55*inch,.62*inch,.82*inch,.75*inch,.58*inch,.58*inch,.62*inch], repeatRows=1)
    full_commands = [
        ("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.3),
        ("ALIGN",(1,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#EAF6F6")),
        ("BACKGROUND",(0,7),(-1,7),colors.HexColor("#EAF6F6")),
        ("SPAN",(0,1),(-1,1)), ("SPAN",(0,7),(-1,7)),
    ]
    full_table.setStyle(TableStyle(full_commands))
    story += [full_table, Spacer(1, 10), Paragraph("Category differences", styles["h1"]), Paragraph("A positive contribution difference means Location 1 receives more composite-score points in that category. A negative number means Location 2 receives more.", styles["small"])]
    contribution_rows = [["Crime category", "Weight", "L1 points", "L2 points", "L1 - L2", "Raw incidents L1 / L2"]]
    for category in CRIME_WEIGHTS:
        a, z = first.categories[category], second.categories[category]
        contribution_rows.append([category, f"{CRIME_WEIGHTS[category]:.0%}", f"{a.contribution:.1f}", f"{z.contribution:.1f}", f"{a.contribution-z.contribution:+.1f}", f"{a.raw_incidents:,} / {z.raw_incidents:,}"])
    contributions = Table(contribution_rows, colWidths=[1.4*inch,.52*inch,.72*inch,.72*inch,.72*inch,1.35*inch], repeatRows=1)
    contributions.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.4), ("ALIGN",(1,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [contributions, Spacer(1, 8), Paragraph("Calculation", styles["h1"]), Paragraph(
        "The category score places local weighted exposure on the 0-100 review-priority scale. Points equal category score multiplied by the published weight; the points sum to the overall score before display rounding.",
        styles["body"],
    ), PageBreak()]

    # Page 3 - historical counts and weighted exposure, shown separately.
    story += [Paragraph("Historical comparison", styles["title"]), Paragraph("Raw incident direction and weighted-exposure direction are displayed separately", styles["subtitle"])]
    trends = [temporal_trends(r.latitude, r.longitude, r.radius_metres) for r in results]
    trend_rows = [[Paragraph(label, styles["white_small"]) for label in ("Location", "Window", "Now<br/>incidents", "Prior<br/>incidents", "Count<br/>change", "Now<br/>exposure", "Prior<br/>exposure", "Exposure<br/>change", "Stability")]]
    for label, trend in zip(("Location 1", "Location 2"), trends):
        for row in trend["comparisons"].to_dict("records"):
            trend_rows.append([label, row["Period"], str(row["Current incidents"]), str(row["Previous incidents"]), _pct(row["Count change (%)"]), f"{row['Current exposure']:.2f}", f"{row['Previous exposure']:.2f}", _pct(row["Exposure change (%)"]), Paragraph(escape(row["Stability flag"]), styles["small"])])
    trend_table = Table(trend_rows, colWidths=[.7*inch,.8*inch,.68*inch,.68*inch,.65*inch,.68*inch,.68*inch,.68*inch,.95*inch], repeatRows=1)
    trend_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),6.2), ("ALIGN",(0,1),(7,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [Paragraph("Overall rolling windows", styles["h1"]), Paragraph(f"Equal windows are anchored to {trends[0]['cutoff']}. Exposure change is based on distance- and category-weighted exposure, not the raw incident counts beside it.", styles["body"]), trend_table, Spacer(1, 9)]

    category_trend_rows = [[Paragraph(label, styles["white_small"]) for label in ("Location", "Category", "Now<br/>incidents", "Prior<br/>incidents", "Count<br/>change", "Exposure<br/>change", "Interpretation")]]
    for label, trend in zip(("Location 1", "Location 2"), trends):
        for row in trend["categories"].to_dict("records"):
            category_trend_rows.append([label, row["Category"], str(row["Current incidents"]), str(row["Previous incidents"]), _pct(row["Count change (%)"]), _pct(row["Exposure change (%)"]), Paragraph(escape(row["Stability flag"]), styles["small"])])
    category_trend_table = Table(category_trend_rows, colWidths=[.65*inch,1.12*inch,.75*inch,.75*inch,.75*inch,.78*inch,1.7*inch], repeatRows=1)
    category_trend_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),6.4), ("ALIGN",(0,1),(5,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story += [Paragraph("Category-level 12-month direction", styles["h1"]), category_trend_table, Spacer(1, 7), Paragraph(
        "A location can have fewer incidents but higher weighted exposure if its recent incidents occurred closer to the site or in more heavily weighted categories. The two measures should therefore be interpreted together.",
        styles["small"],
    ), PageBreak()]

    # Page 4 - assumption stability, context and action.
    # Sensitivity was computed above so the executive recommendation can state whether the order is stable.
    sensitivity_rows = [["Radius", "Location 1", "Location 2", "Point difference"]]
    gaps = []
    for left_row, right_row in zip(first_sensitivity.to_dict("records"), second_sensitivity.to_dict("records")):
        gap = left_row["Priority score"] - right_row["Priority score"]
        gaps.append(gap)
        sensitivity_rows.append([f"{left_row['Radius (m)']} m", f"{left_row['Priority score']:.1f}", f"{right_row['Priority score']:.1f}", f"{gap:+.1f}"])
    sensitive = any(abs(gap) < 3 for gap in gaps) or (min(gaps) < 0 < max(gaps))
    sensitivity_text = "Assumption-dependent comparison: the ordering becomes close or changes across tested radii." if sensitive else "More stable comparison: the ordering remains consistent across the tested radii."
    sensitivity_table = Table(sensitivity_rows, colWidths=[1.1*inch,1.35*inch,1.35*inch,1.4*inch], repeatRows=1)
    sensitivity_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.8), ("ALIGN",(0,0),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [Paragraph("Evidence stability and context", styles["title"]), Paragraph("Whether the decision survives a boundary change, plus context that may guide validation", styles["subtitle"]), Paragraph("Radius sensitivity", styles["h1"]), Paragraph(sensitivity_text, styles["body"]), sensitivity_table, Spacer(1, 10)]

    weight_rows = [["Weight profile", "Location 1 score", "Location 2 score", "Review first"]]
    weight_frame = weight_sensitivity(results)
    for profile, group in weight_frame.groupby("Weight profile", sort=False):
        scores = {row["Location"]: row["Score"] for row in group.to_dict("records")}
        first_name, second_name = first.submitted_address or first.address, second.submitted_address or second.address
        first_score, second_score = scores[first_name], scores[second_name]
        order = "Location 1" if first_score > second_score else ("Location 2" if second_score > first_score else "Same tier")
        weight_rows.append([Paragraph(escape(profile), styles["small"]), f"{first_score:.1f}", f"{second_score:.1f}", order])
    weight_table = Table(weight_rows, colWidths=[2.45*inch,1.15*inch,1.15*inch,1.3*inch], repeatRows=1)
    weight_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.5), ("ALIGN",(1,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [Paragraph("Weight-profile sensitivity", styles["h1"]), Paragraph("Alternative profiles are stress tests, not replacement recommendations.", styles["small"]), weight_table, Spacer(1, 8)]

    context_rows = [["Context", "Location 1", "Location 2"]]
    context_rows += [
        ["Nearest TTC"] + [Paragraph(escape(str(r.context.get("nearest_ttc_station", "Not available"))), styles["small"]) for r in results],
        ["TTC distance"] + [f"{r.context.get('ttc_distance_metres', '-')} m" for r in results],
        ["Parks in radius"] + [str(r.context.get("parks_within_radius", "-")) for r in results],
        ["Street-light poles"] + [str(r.context.get("street_light_poles_within_radius", "-")) for r in results],
        ["Approx. neighbourhood"] + [Paragraph(escape(str(r.context.get("approximate_neighbourhood", "Not available"))), styles["small"]) for r in results],
    ]
    context_table = Table(context_rows, colWidths=[1.55*inch,2.55*inch,2.55*inch], repeatRows=1)
    context_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.7), ("ALIGN",(1,2),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [Paragraph("Environmental context", styles["h1"]), Paragraph("These values support discussion only and do not affect the current score.", styles["small"]), context_table]
    story += [
        PageBreak(),
        Paragraph("Decision, provenance and calculation audit", styles["title"]),
        Paragraph("How to validate the result and document the evidence boundary", styles["subtitle"]),
        Paragraph("Recommended validation", styles["h1"]),
    ]
    for item in explanation["leading_drivers"]:
        story.append(Paragraph(f"- Do internal incidents, loss records and staff observations support the difference in <b>{escape(item['category'].lower())}</b>?", styles["body"]))
    story += [Paragraph(
        f"Begin with {escape(higher_label)} because it has the higher current review-priority score. Confirm the leading category differences, check whether existing controls explain any mismatch, and use a qualified site review before selecting physical or operational controls.",
        styles["body"],
    ), Paragraph("Data and use boundary", styles["h1"]), Paragraph(
        f"<b>Source:</b> {DATA_SOURCE}<br/><b>Coverage:</b> {escape(data_provenance()['Coverage'])}<br/><b>Data as of:</b> {escape(data_provenance()['Data as of'])}<br/><b>Data version:</b> {escape(data_provenance()['Data version'])}<br/><b>Methodology:</b> {METHODOLOGY_VERSION}",
        styles["body"],
    ), _audit_note(results, styles), _source_warning_note(results, styles), _compact_limitations(styles)]
    doc=_doc(b, classification); doc.build(story,onFirstPage=_page,onLaterPages=_page); b.seek(0); return b


def build_portfolio_report(results: list[LocationResult], classification: str = "CLIENT CONFIDENTIAL") -> BytesIO:
    if not results:
        raise ValueError("At least one scored location is required.")
    b, styles, story = BytesIO(), _styles(), []
    ranked = sorted(results, key=lambda result: result.overall_score, reverse=True)
    average = sum(result.overall_score for result in ranked) / len(ranked)
    spread = ranked[0].overall_score - ranked[-1].overall_score
    top_count = max(1, min(3, len(ranked)))
    bands = [sum(result.overall_score >= 75 for result in ranked), sum(60 <= result.overall_score < 75 for result in ranked), sum(40 <= result.overall_score < 60 for result in ranked), sum(result.overall_score < 40 for result in ranked)]
    driver_counts = {category: 0 for category in CRIME_WEIGHTS}
    for result in ranked:
        driver_counts[max(result.categories.values(), key=lambda item: item.score).category] += 1
    dominant_driver = max(driver_counts, key=driver_counts.get)
    portfolio_trends = {id(result): temporal_trends(result.latitude, result.longitude, result.radius_metres) for result in ranked}
    weight_frame = weight_sensitivity(ranked)
    radius_frame = portfolio_radius_sensitivity(ranked)

    # Page 1 - fast executive read.
    _logo_story(story)
    analysis_key = "|".join(f"{r.latitude:.6f},{r.longitude:.6f},{r.radius_metres},{r.overall_score:.1f}" for r in ranked)
    story += [Paragraph("Portfolio Security Prioritization Report", styles["title"]), Paragraph("Executive decision brief - what the ranking means and why", styles["subtitle"]), _metadata("Portfolio prioritization", len(ranked), analysis_key), Spacer(1, 10), Paragraph("The 30-second summary", styles["h1"])]
    simple_summary = (f"The portfolio is concentrated toward the upper end of Locivra's review-priority scale: <b>{bands[0] + bands[1]} of {len(ranked)} locations</b> are High or Critical priority. "
                      f"The average score is <b>{average:.1f}/100</b>, and the difference between the first and last location is <b>{spread:.1f} points</b>. "
                      f"The most common primary contributor is <b>{escape(dominant_driver)}</b>. Start by validating the top {top_count} locations against internal incidents and site knowledge before deciding on interventions.")
    summary_box = Table([[Paragraph(simple_summary, styles["body"])]], colWidths=[6.55*inch])
    summary_box.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF6F6")), ("BOX",(0,0),(-1,-1),1,CYAN), ("LEFTPADDING",(0,0),(-1,-1),14), ("RIGHTPADDING",(0,0),(-1,-1),14), ("TOPPADDING",(0,0),(-1,-1),12), ("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [summary_box, Spacer(1, 11)]
    kpis = [[Paragraph(f"<b>Highest score</b><br/><font size='18'>{ranked[0].overall_score:.1f}</font>", styles["body"]), Paragraph(f"<b>Portfolio average</b><br/><font size='18'>{average:.1f}</font>", styles["body"]), Paragraph(f"<b>High/Critical</b><br/><font size='18'>{bands[0] + bands[1]} of {len(ranked)}</font>", styles["body"]), Paragraph(f"<b>Score spread</b><br/><font size='18'>{spread:.1f}</font>", styles["body"])]]
    kpi_table = Table(kpis, colWidths=[1.64*inch]*4)
    kpi_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),MIST), ("BOX",(0,0),(-1,-1),.6,LINE), ("INNERGRID",(0,0),(-1,-1),.4,LINE), ("ALIGN",(0,0),(-1,-1),"CENTER"), ("TOPPADDING",(0,0),(-1,-1),10), ("BOTTOMPADDING",(0,0),(-1,-1),10)]))
    story += [kpi_table, Spacer(1, 11), Paragraph("What is driving the result", styles["h1"])]
    top = ranked[0]
    top_drivers = sorted(top.categories.values(), key=lambda item: item.score * item.weight, reverse=True)[:2]
    why = (f"<b>{escape(_short_address(top.address, 75))}</b> ranks first because its strongest weighted contributors are "
           f"<b>{escape(top_drivers[0].category)}</b> ({top_drivers[0].score:.1f}/100; {top_drivers[0].raw_incidents:,} nearby incidents) and "
           f"<b>{escape(top_drivers[1].category)}</b> ({top_drivers[1].score:.1f}/100; {top_drivers[1].raw_incidents:,} nearby incidents). "
           "The composite is high because several categories are elevated at once, not because of a single isolated count.")
    story += [Paragraph(why, styles["body"]), Paragraph("Recommended decision", styles["h2"]), Paragraph(f"Advance the top {top_count} locations to validation first. Compare these findings with internal loss, safety and incident records; then use a site review to determine whether physical or operational controls are warranted.", styles["body"]), _limitations(styles), PageBreak()]

    # Page 2 - portfolio visual pattern.
    story += [Paragraph("Portfolio landscape", styles["title"]), Paragraph("Scores show review sequence; category patterns explain the sequence", styles["subtitle"]), Paragraph("Overall priority ranking", styles["h1"]), _ranking_chart(ranked), Spacer(1, 8), Paragraph("How to read this chart", styles["h2"]), Paragraph("Longer bars indicate stronger historical exposure relative to the configured citywide reference baseline. The gap between adjacent bars matters: small gaps suggest a practical tier, while large gaps support a clearer review sequence.", styles["body"]), Paragraph("Category score heatmap", styles["h1"]), _heatmap(ranked, styles), Spacer(1, 7), Paragraph("Darker cells identify the categories creating each location's score. A location with several dark cells has a broad exposure pattern; one dark cell suggests a more concentrated issue to validate.", styles["small"]), PageBreak()]

    story += [Paragraph("Historical direction", styles["title"]), Paragraph("Equal rolling windows reveal whether the recent signal is rising, falling or mixed", styles["subtitle"])]
    trend_rows = [["Rank", "Location", "Latest 6 months", "Latest 12 months", "12-month incidents"]]
    for index, result in enumerate(ranked, 1):
        trend = portfolio_trends[id(result)]
        six, twelve = trend["comparisons"].to_dict("records")
        six_text = _pct(six["Exposure change (%)"], "Withheld")
        twelve_text = _pct(twelve["Exposure change (%)"], "Withheld")
        trend_rows.append([str(index), Paragraph(escape(_short_address(result.submitted_address or result.address)), styles["small"]), six_text, twelve_text, str(twelve["Current incidents"])])
    trend_table = Table(trend_rows, colWidths=[.45*inch,3.15*inch,1.05*inch,1.05*inch,1.0*inch], repeatRows=1)
    trend_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.8), ("ALIGN",(0,1),(0,-1),"CENTER"), ("ALIGN",(2,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [trend_table, Spacer(1,10), Paragraph(f"Windows are anchored to the newest configured report date ({next(iter(portfolio_trends.values()))['cutoff']}). Positive and negative percentages describe change in distance- and category-weighted historical exposure. Mixed six- and twelve-month directions should be discussed rather than reduced to one trend claim.", styles["body"]), _limitations(styles), PageBreak()]

    # Page 3 - decision table with the why visible.
    story += [Paragraph("Decision table", styles["title"]), Paragraph("Ranking plus the evidence behind each position", styles["subtitle"])]
    rows = [["Rank", "Location", "Score", "Portfolio tier", "Why it ranks here", "Next validation question"]]
    for index, result in enumerate(ranked, 1):
        contributors = sorted(result.categories.values(), key=lambda item: item.score * item.weight, reverse=True)[:2]
        evidence = f"{contributors[0].category} {contributors[0].score:.0f}; {contributors[1].category} {contributors[1].score:.0f}"
        question = f"Do internal records support the {contributors[0].category.lower()} signal?"
        rows.append([str(index), Paragraph(escape(_short_address(result.submitted_address or result.address)), styles["small"]), f"{result.overall_score:.1f}", Paragraph(_portfolio_tier(index, len(ranked)), styles["small"]), Paragraph(escape(evidence), styles["small"]), Paragraph(escape(question), styles["small"])])
    decision_table = Table(rows, colWidths=[.34*inch,1.55*inch,.48*inch,1.15*inch,1.45*inch,1.68*inch], repeatRows=1)
    decision_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.3), ("ALIGN",(0,1),(0,-1),"CENTER"), ("ALIGN",(2,1),(2,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [decision_table, Spacer(1, 10), Paragraph("Portfolio-level findings", styles["h1"])]
    for category, count in sorted(driver_counts.items(), key=lambda item: item[1], reverse=True):
        if count:
            story.append(Paragraph(f"<b>{escape(category)}:</b> primary contributor at {count} of {len(ranked)} locations. This suggests a shared validation theme across that portion of the portfolio, while still requiring location-specific review.", styles["body"]))
    story.append(PageBreak())

    # Portfolio-level assumption testing and automated reconciliation.
    story += [Paragraph("Assumption sensitivity and calculation audit", styles["title"]), Paragraph("Whether the review order survives reasonable radius and weighting choices", styles["subtitle"])]
    weight_rows = [["Weight profile", "Top-ranked location", "Largest rank movement"]]
    for profile, group in weight_frame.groupby("Weight profile", sort=False):
        top = group.sort_values("Rank").iloc[0]
        movement = int(group["Rank change"].abs().max())
        weight_rows.append([Paragraph(escape(profile), styles["small"]), Paragraph(escape(_short_address(str(top["Location"]))), styles["small"]), str(movement)])
    weight_table = Table(weight_rows, colWidths=[2.1*inch,3.65*inch,.9*inch], repeatRows=1)
    weight_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.7), ("ALIGN",(2,1),(2,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    radius_rows = [["Radius", "Top-ranked location", "Largest rank movement"]]
    for radius, group in radius_frame.groupby("Radius (m)", sort=True):
        top = group.sort_values("Rank").iloc[0]
        movement = int(group["Rank change"].abs().max())
        radius_rows.append([f"{radius} m", Paragraph(escape(_short_address(str(top["Location"]))), styles["small"]), str(movement)])
    radius_table = Table(radius_rows, colWidths=[1.0*inch,4.75*inch,.9*inch], repeatRows=1)
    radius_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.7), ("ALIGN",(0,1),(0,-1),"CENTER"), ("ALIGN",(2,1),(2,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [Paragraph("Weight-profile sensitivity", styles["h1"]), Paragraph("Four disclosed profiles test whether weighting assumptions materially change the review sequence.", styles["body"]), weight_table, Paragraph("Radius sensitivity", styles["h1"]), Paragraph("Every location is rescored and reranked at 250, 500, 750 and 1,000 metres.", styles["body"]), radius_table, Paragraph("Automated score reconciliation", styles["h1"]), _audit_note(ranked, styles), _source_warning_note(ranked, styles), PageBreak()]

    # Detailed profiles - two locations per page.
    for start in range(0, len(ranked), 2):
        story += [Paragraph("Location evidence profiles", styles["title"]), Paragraph(f"Locations {start + 1}-{min(start + 2, len(ranked))} of {len(ranked)}", styles["subtitle"])]
        for index, result in enumerate(ranked[start:start+2], start + 1):
            contributors = sorted(result.categories.values(), key=lambda item: item.score * item.weight, reverse=True)
            explanation = (f"This location ranks <b>#{index}</b> because its largest weighted contributions come from <b>{escape(contributors[0].category)}</b> and <b>{escape(contributors[1].category)}</b>. "
                           f"Its score is {result.overall_score - average:+.1f} points versus the portfolio average. Raw incidents show volume; distance-weighted exposure gives closer incidents more influence.")
            profile_rows = [["Category", "Raw", "Weighted", "Score", "Weight", "Contribution"]]
            for item in contributors:
                profile_rows.append([item.category, str(item.raw_incidents), f"{item.weighted_exposure:.1f}", f"{item.score:.1f}", f"{item.weight:.0%}", f"{item.score * item.weight:.1f}"])
            profile = Table(profile_rows, colWidths=[1.55*inch,.55*inch,.75*inch,.55*inch,.55*inch,.78*inch], repeatRows=1)
            profile.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.1), ("ALIGN",(1,1),(-1,-1),"CENTER"), ("GRID",(0,0),(-1,-1),.3,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("TOPPADDING",(0,0),(-1,-1),4), ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            client_note = "Client operational evidence was not supplied; this profile reflects public-data exposure only."
            if result.client_data:
                supplied = [key for key, value in result.client_data.items() if str(value).strip() and str(value).strip().lower() != "unknown"]
                client_note = f"Client evidence supplied: {', '.join(supplied) if supplied else 'control status fields only'}. These inputs are displayed for validation and are not included in the exposure score."
            block = [Paragraph(f"#{index} - {escape(_short_address(result.submitted_address or result.address, 90))}", styles["h1"]), Paragraph(f"<b>{result.overall_score:.1f}/100 - {_portfolio_tier(index, len(ranked))}</b>", styles["h2"]), Paragraph(explanation, styles["body"]), profile, Spacer(1, 6), Paragraph(f"<b>Evidence boundary:</b> {escape(client_note)}", styles["small"]), Paragraph(f"<b>Validation focus:</b> Test whether internal records and observed site conditions support the {escape(contributors[0].category.lower())} and {escape(contributors[1].category.lower())} signals.", styles["small"]), Spacer(1, 8)]
            story.append(KeepTogether(block))
        if start + 2 < len(ranked):
            story.append(PageBreak())

    # Final methodology and action page.
    provenance = data_provenance()
    story += [PageBreak(), Paragraph("Methodology and action plan", styles["title"]), Paragraph("Transparent enough to challenge, bounded enough to use responsibly", styles["subtitle"]), Paragraph("Data provenance", styles["h1"]), Paragraph(f"<b>Source:</b> {escape(provenance['Source'])}<br/><b>Coverage:</b> {escape(provenance['Coverage'])}<br/><b>Data as of:</b> {escape(provenance['Data as of'])}<br/><b>Data version:</b> {escape(provenance['Data version'])}<br/><b>Valid coordinate records:</b> {escape(provenance['Valid coordinate records'])}<br/><b>Geography:</b> Toronto only<br/><b>Methodology version:</b> {METHODOLOGY_VERSION}", styles["body"]), _source_warning_note(ranked, styles), Paragraph("How the score works", styles["h1"]), Paragraph("1. Incidents inside the selected radius are measured using geodesic distance. 2. Incidents closer to the location receive more influence through linear distance decay. 3. Each category is compared with a configured citywide reference baseline; baseline exposure maps to the middle of the scale. 4. Category scores are combined using published weights: Theft Over $5,000 30%, Break & Enter 25%, Robbery 25%, Assault 15%, and Auto Theft 5%. Portfolio tiers are relative to the submitted locations and do not claim universal risk boundaries.", styles["body"]), Paragraph("What the score does not explain", styles["h1"]), Paragraph("The model does not include unreported events, internal company incidents, store hours, sales volume, foot traffic, existing controls, site layout, current operating conditions, or causal claims. Environmental datasets are contextual until their influence is separately validated.", styles["body"]), Paragraph("Suggested pilot workflow", styles["h1"])]
    workflow = [["Step", "Action", "Output"], ["1", "Review this portfolio brief with Security/Loss Prevention leadership.", "Agreed priority tier"], ["2", "Compare top-location drivers with internal incidents and local knowledge.", "Confirmed or challenged signals"], ["3", "Select 5-20 locations for bounded professional review.", "Pilot cohort"], ["4", "Conduct site review before selecting controls.", "Evidence-based recommendations"], ["5", "Record disagreements and outcomes to refine the method.", "Validation log and roadmap"]]
    workflow_table = Table(workflow, colWidths=[.45*inch,4.15*inch,2.05*inch])
    workflow_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("GRID",(0,0),(-1,-1),.35,LINE), ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,MIST]), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story += [workflow_table, Spacer(1, 14), _limitations(styles)]
    doc = _doc(b, classification); doc.build(story, onFirstPage=_page, onLaterPages=_page); b.seek(0); return b
