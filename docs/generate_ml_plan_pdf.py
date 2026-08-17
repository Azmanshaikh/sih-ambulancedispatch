"""Generate docs/JEEVAN-ML-Implementation-Plan.pdf — SIH technical proposal."""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- palette ---
RED = HexColor("#C81E1E")
RED_DK = HexColor("#8F1414")
INK = HexColor("#161616")
MUTED = HexColor("#5A564E")
RULE = HexColor("#D6D1C8")
PAPER = HexColor("#FAF7F2")
CREAM = HexColor("#F3EFE8")
KEEP = HexColor("#1B6B4A")
KEEP_BG = HexColor("#E6F4EC")
ML = HexColor("#1A4B8C")
ML_BG = HexColor("#E7EFFA")
AMBER = HexColor("#B45309")
AMBER_BG = HexColor("#FDECC8")
DASH = HexColor("#8E887C")
BOX_STROKE = HexColor("#2A2A2A")

PAGE_W, PAGE_H = A4
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 20 * mm
MARGIN_B = 16 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

OUT = Path(__file__).resolve().parent / "JEEVAN-ML-Implementation-Plan.pdf"


def _try_fonts() -> tuple[str, str, str]:
    candidates = [
        (
            "Segoe UI",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\segoeuii.ttf",
        ),
        (
            "Calibri",
            r"C:\Windows\Fonts\calibri.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
            r"C:\Windows\Fonts\calibrii.ttf",
        ),
    ]
    for name, r, b, i in candidates:
        rp, bp, ip = Path(r), Path(b), Path(i)
        if rp.exists() and bp.exists():
            pdfmetrics.registerFont(TTFont(f"{name}", str(rp)))
            pdfmetrics.registerFont(TTFont(f"{name}-Bold", str(bp)))
            if ip.exists():
                pdfmetrics.registerFont(TTFont(f"{name}-Italic", str(ip)))
                return name, f"{name}-Bold", f"{name}-Italic"
            return name, f"{name}-Bold", name
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


FONT, FONT_B, FONT_I = _try_fonts()


def _wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


class Diagram(Flowable):
    def __init__(self, height: float, painter, width: float | None = None):
        super().__init__()
        self._h = height
        self._w = width or CONTENT_W
        self.painter = painter

    def wrap(self, aw, ah):
        self.width = min(self._w, aw)
        self.height = self._h
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(CREAM)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, self.width, self.height, 7, fill=1, stroke=1)
        self.painter(c, self.width, self.height)


def _box(
    c,
    x,
    y,
    w,
    h,
    text: str,
    fill=white,
    stroke=BOX_STROKE,
    tc=INK,
    size=8,
    bold=True,
    radius=5,
    dashed=False,
):
    c.saveState()
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1.15)
    if dashed:
        c.setDash(3, 2.5)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    c.setDash()
    font = FONT_B if bold else FONT
    lines = _wrap(text, font, size, w - 12)
    total = len(lines) * (size + 2)
    ty = y + (h + total) / 2 - size
    c.setFillColor(tc)
    c.setFont(font, size)
    for line in lines:
        c.drawCentredString(x + w / 2, ty, line)
        ty -= size + 2
    c.restoreState()


def _diamond(c, cx, cy, w, h, text, fill=AMBER_BG, stroke=AMBER, size=7.5):
    c.saveState()
    path = c.beginPath()
    path.moveTo(cx, cy + h / 2)
    path.lineTo(cx + w / 2, cy)
    path.lineTo(cx, cy - h / 2)
    path.lineTo(cx - w / 2, cy)
    path.close()
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1.15)
    c.drawPath(path, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont(FONT_B, size)
    for i, line in enumerate(_wrap(text, FONT_B, size, w - 28)):
        c.drawCentredString(cx, cy + 6 - i * (size + 1), line)
    c.restoreState()


def _arrow(c, x1, y1, x2, y2, color=INK, dashed=False, label=None):
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(1.2)
    if dashed:
        c.setDash(3, 2.5)
    c.line(x1, y1, x2, y2)
    c.setDash()
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 6
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - ah * math.cos(ang - 0.4), y2 - ah * math.sin(ang - 0.4))
    p.lineTo(x2 - ah * math.cos(ang + 0.4), y2 - ah * math.sin(ang + 0.4))
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        c.setFont(FONT_I, 6.5)
        c.setFillColor(MUTED)
        c.drawCentredString(mx + 18, my + 3, label)
    c.restoreState()


def _v_arrow(c, x, y_top, y_bot, **kw):
    _arrow(c, x, y_top, x, y_bot, **kw)


def _caption(c, w, text):
    c.setFillColor(MUTED)
    c.setFont(FONT_I, 7)
    c.drawString(10, 8, text)


# ---------- diagrams ----------
def draw_current(c, w, h):
    bw, bh = 250, 28
    x = 28
    step = 42
    top = h - 36
    labels = [
        "Patient / staff opens New Request",
        "Description + narrative + age group",
        "Flags: cardiac / diabetes / epilepsy / pregnant",
        "POST /tracking/dispatch",
        "mission_priority — checkbox rules only",
        "Ambulance: haversine top-3, then emergency ETA",
        "Hospital: lowest pickup + transport time",
        "Corridor conflict / reroute + SMS + live map",
    ]
    ys = []
    for i, lab in enumerate(labels):
        y = top - i * step - bh
        ys.append(y)
        fill = white
        if i == 4:
            fill = AMBER_BG
        if i >= 5:
            fill = HexColor("#EEF2F6")
        _box(c, x, y, bw, bh, lab, fill=fill, size=7.4)
        if i:
            _v_arrow(c, x + bw / 2, ys[i - 1], y + bh)

    # unused LLM branch
    rx, rw = 300, 168
    ry = ys[2]
    _box(
        c,
        rx,
        ry + 36,
        rw,
        36,
        "Optional NVIDIA report analysis",
        fill=CREAM,
        stroke=DASH,
        tc=MUTED,
        size=7.2,
        dashed=True,
    )
    _box(
        c,
        rx,
        ry - 18,
        rw,
        36,
        "Shown in UI only — never sent to dispatch",
        fill=CREAM,
        stroke=DASH,
        tc=MUTED,
        size=7.2,
        dashed=True,
        bold=False,
    )
    _arrow(c, x + bw, ys[2] + bh / 2, rx, ry + 36 + 18, color=DASH, dashed=True)
    _v_arrow(c, rx + rw / 2, ry + 36, ry + 18, color=DASH, dashed=True)
    _caption(c, w, "Figure 1. Current dispatch path. Dashed = collected but unused.")


def draw_keep_vs_ml(c, w, h):
    col_w = (w - 48) / 2
    left, right = 16, 16 + col_w + 16
    # headers
    _box(c, left, h - 44, col_w, 24, "KEEP  —  optimisation & rules", fill=KEEP_BG, stroke=KEEP, tc=KEEP, size=8)
    _box(c, right, h - 44, col_w, 24, "ADD  —  machine learning", fill=ML_BG, stroke=ML, tc=ML, size=8)
    keep_items = [
        "NetworkX Dijkstra + TomTom / OSRM roads",
        "Emergency corridor occupancy + police SMS",
        "Hard safety rules (cardiac → capable hospital)",
        "Live GPS / fleet simulation",
    ]
    ml_items = [
        "Triage classifier from free-text + flags",
        "ETA residual: how wrong the router is",
        "Hospital ranker: ETA + beds + specialty",
        "Optional later: demand / idle positioning",
    ]
    bh = 32
    for i, t in enumerate(keep_items):
        y = h - 92 - i * 42
        _box(c, left, y, col_w, bh, t, fill=white, stroke=KEEP, size=7.3)
    for i, t in enumerate(ml_items):
        y = h - 92 - i * 42
        _box(c, right, y, col_w, bh, t, fill=white, stroke=ML, size=7.3)
    # merge
    _box(
        c,
        w / 2 - 110,
        22,
        220,
        30,
        "Existing dispatch optimizer (scoring input only)",
        fill=INK,
        stroke=INK,
        tc=white,
        size=7.5,
    )
    _arrow(c, left + col_w / 2, h - 92 - 3 * 42, w / 2 - 40, 52, color=KEEP)
    _arrow(c, right + col_w / 2, h - 92 - 3 * 42, w / 2 + 40, 52, color=ML)
    _caption(c, w, "Figure 2. ML scores and ranks. It does not invent roads.")


def draw_target(c, w, h):
    bw, bh = 280, 28
    x = (w - bw) / 2
    items = [
        ("Caller text + flags + optional report", white, BOX_STROKE),
        ("XGBoost triage  →  priority 1–5", ML_BG, ML),
        ("NetworkX / TomTom emergency route", KEEP_BG, KEEP),
        ("ETA residual model (optional correction)", ML_BG, ML),
        ("Hospital ranker: ETA + specialty + beds", ML_BG, ML),
        ("Safety constraint: capable hospital within N min", AMBER_BG, AMBER),
        ("Corridor conflict resolver + assign unit", KEEP_BG, KEEP),
    ]
    top = h - 40
    ys = []
    for i, (lab, fill, stroke) in enumerate(items):
        y = top - i * 40 - bh
        ys.append(y)
        _box(c, x, y, bw, bh, lab, fill=fill, stroke=stroke, size=7.5)
        if i:
            _v_arrow(c, x + bw / 2, ys[i - 1], y + bh)
    # fallback
    _box(
        c,
        14,
        ys[1],
        86,
        52,
        "If model file missing → keep heuristics",
        fill=CREAM,
        stroke=DASH,
        tc=MUTED,
        size=6.6,
        dashed=True,
        bold=False,
    )
    _arrow(c, 100, ys[1] + 26, x, ys[1] + bh / 2, color=DASH, dashed=True)
    _caption(c, w, "Figure 3. Target pipeline. Dispatch never fails because ML is down.")


def draw_triage(c, w, h):
    feats = [
        "TF-IDF of description + narrative",
        "Age group",
        "Cardiac / diabetes / epilepsy / pregnant",
        "Hour of day + rain flag",
        "Optional LLM severity from report",
    ]
    fw, fh = 200, 24
    fx = 18
    top = h - 36
    for i, f in enumerate(feats):
        y = top - i * 32 - fh
        _box(c, fx, y, fw, fh, f, fill=white, stroke=ML, size=7.2)
        _arrow(c, fx + fw, y + fh / 2, 250, h / 2 + 8, color=ML)
    _box(c, 250, h / 2 - 18, 150, 52, "XGBoost classifier", fill=ML, stroke=ML, tc=white, size=9)
    _arrow(c, 400, h / 2 + 8, 430, h / 2 + 8, color=ML)
    outs = ["CRITICAL → 5", "HIGH → 4", "MEDIUM → 2–3", "LOW → 1"]
    for i, o in enumerate(outs):
        y = h - 70 - i * 36
        _box(c, 430, y, 78, 28, o, fill=ML_BG, stroke=ML, size=6.8)
    _box(
        c,
        250,
        18,
        258,
        28,
        "POST /tracking/dispatch  ·  DispatchRequest.priority",
        fill=INK,
        stroke=INK,
        tc=white,
        size=7.2,
    )
    _arrow(c, 469, h - 70 - 3 * 36, 380, 46, color=INK)
    _caption(c, w, "Figure 4. Model 1 — incident triage. Rule overrides stay above the model.")


def draw_eta(c, w, h):
    _box(c, 20, h - 70, 210, 40, "TomTom / OSRM / NetworkX duration", fill=KEEP_BG, stroke=KEEP, size=8)
    _box(c, 20, h - 150, 210, 56, "hour · weekday · rain · distance · corridor hits · grid cell", fill=white, stroke=ML, size=7.4)
    _box(c, 270, h - 128, 150, 56, "XGBoost / RF residual seconds", fill=ML, stroke=ML, tc=white, size=8)
    _arrow(c, 230, h - 122, 270, h - 100, color=ML)
    _box(c, 20, 36, 400, 40, "eta = router * 0.70 * rain_factor + model.predict(features)", fill=INK, stroke=INK, tc=white, size=7.6)
    _arrow(c, 125, h - 70, 125, 76, color=KEEP)
    _arrow(c, 345, h - 72, 220, 76, color=ML)
    _box(c, 430, 36, 78, 40, "Rank units + hospitals", fill=AMBER_BG, stroke=AMBER, size=7)
    _arrow(c, 420, 56, 430, 56, color=INK)
    _caption(c, w, "Figure 5. Model 2 — ETA residual. Router stays; ML only corrects the minutes.")


def draw_hospital(c, w, h):
    _box(c, w / 2 - 140, h - 50, 280, 28, "Hospitals with a valid emergency route", fill=white, size=8)
    _diamond(c, w / 2, h - 110, 200, 52, "Capable of this case?")
    _v_arrow(c, w / 2, h - 50, h - 84)
    _box(c, 18, 70, 200, 44, "No, and a capable hospital is within N min  →  drop", fill=HexColor("#F8E4E4"), stroke=RED, size=7.2)
    _box(c, w - 218, 70, 200, 44, "Yes (or no alternative)  →  score ETA + beds + specialty", fill=KEEP_BG, stroke=KEEP, size=7.2)
    _arrow(c, w / 2 - 40, h - 136, 118, 114, color=RED)
    _arrow(c, w / 2 + 40, h - 136, w - 118, 114, color=KEEP)
    _box(c, w / 2 - 110, 18, 220, 28, "Lowest score wins  ·  safety never overridden", fill=INK, stroke=INK, tc=white, size=7.4)
    _arrow(c, w - 118, 70, w / 2 + 40, 46, color=KEEP)
    _caption(c, w, "Figure 6. Model 3 — hospital ranking. Cardiac never skips ICU/Trauma if one is nearby.")


def draw_phases(c, w, h):
    phases = [
        ("A", "Triage classifier\nwired to priority", "1–2 days", "HIGH", ML),
        ("B", "Hospital score:\nETA + specialty + beds", "~½ day", "HIGH", KEEP),
        ("D", "Log predicted vs\nactual ETAs", "1 day", "enables C", AMBER),
        ("C", "ETA residual\nmodel", "2–3 days", "MEDIUM", ML),
        ("E", "Demand / idle\npositioning", "skip", "LOW", DASH),
    ]
    n = len(phases)
    bw = (w - 32 - (n - 1) * 8) / n
    y = 48
    bh = h - 80
    for i, (letter, title, effort, impact, col) in enumerate(phases):
        x = 16 + i * (bw + 8)
        _box(c, x, y, bw, bh, "", fill=white, stroke=col, size=8)
        c.setFillColor(col)
        c.circle(x + bw / 2, y + bh - 22, 12, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(FONT_B, 10)
        c.drawCentredString(x + bw / 2, y + bh - 26, letter)
        c.setFillColor(INK)
        c.setFont(FONT_B, 7)
        ty = y + bh - 48
        for line in title.split("\n"):
            c.drawCentredString(x + bw / 2, ty, line)
            ty -= 11
        c.setFillColor(MUTED)
        c.setFont(FONT, 6.5)
        c.drawCentredString(x + bw / 2, y + 28, effort)
        c.setFillColor(col)
        c.setFont(FONT_B, 6.5)
        c.drawCentredString(x + bw / 2, y + 14, f"impact {impact}")
        if i < n - 1:
            _arrow(c, x + bw, y + bh / 2, x + bw + 8, y + bh / 2, color=RULE)
    _caption(c, w, "Figure 7. Ship A + B for the demo. C is the technical-depth slide. Skip E unless time remains.")


# ---------- styles / chrome ----------
def styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("CoverKicker", fontName=FONT_B, fontSize=9, textColor=RED, spaceAfter=8))
    ss.add(ParagraphStyle("CoverTitle", fontName=FONT_B, fontSize=26, leading=30, textColor=INK, spaceAfter=8))
    ss.add(ParagraphStyle("CoverSub", fontName=FONT, fontSize=12, leading=16, textColor=MUTED, spaceAfter=4))
    ss.add(ParagraphStyle("H1", fontName=FONT_B, fontSize=14, leading=18, textColor=INK, spaceBefore=4, spaceAfter=8))
    ss.add(ParagraphStyle("H2", fontName=FONT_B, fontSize=11, leading=14, textColor=RED_DK, spaceBefore=10, spaceAfter=6))
    ss.add(ParagraphStyle("Body", fontName=FONT, fontSize=9.2, leading=13.2, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=7))
    ss.add(ParagraphStyle("BodyLeft", fontName=FONT, fontSize=9.2, leading=13.2, textColor=INK, alignment=TA_LEFT, spaceAfter=7))
    ss.add(ParagraphStyle("Callout", fontName=FONT, fontSize=9, leading=12.5, textColor=INK, alignment=TA_LEFT))
    ss.add(ParagraphStyle("FigNote", fontName=FONT_I, fontSize=8, leading=11, textColor=MUTED, spaceBefore=3, spaceAfter=10))
    ss.add(ParagraphStyle("Item", fontName=FONT, fontSize=9.2, leading=12.8, textColor=INK, leftIndent=8))
    ss.add(ParagraphStyle("Cell", fontName=FONT, fontSize=8, leading=11, textColor=INK))
    ss.add(ParagraphStyle("CellB", fontName=FONT_B, fontSize=8, leading=11, textColor=INK))
    ss.add(ParagraphStyle("Th", fontName=FONT_B, fontSize=8, leading=11, textColor=white))
    ss.add(ParagraphStyle("Footer", fontName=FONT, fontSize=7.5, textColor=MUTED))
    ss.add(ParagraphStyle("TOC", fontName=FONT, fontSize=10, leading=16, textColor=INK))
    ss.add(ParagraphStyle("MonoBlock", fontName="Courier", fontSize=7.6, leading=10.4, textColor=INK, backColor=CREAM, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=8))
    return ss


S = styles()


def _header_footer(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFillColor(RED)
    canvas.rect(0, PAGE_H - 6, PAGE_W, 6, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 7.5)
    canvas.drawString(MARGIN_L, PAGE_H - 14 * mm, "JEEVAN  ·  Machine Learning Implementation Plan")
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 14 * mm, "North Bangalore dispatch prototype")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_L, PAGE_H - 16 * mm, PAGE_W - MARGIN_R, PAGE_H - 16 * mm)
    canvas.line(MARGIN_L, 12 * mm, PAGE_W - MARGIN_R, 12 * mm)
    canvas.setFont(FONT, 7.5)
    canvas.drawString(MARGIN_L, 7 * mm, "Internal technical proposal  ·  not a clinical device")
    canvas.drawRightString(PAGE_W - MARGIN_R, 7 * mm, str(doc.page))
    canvas.restoreState()


def _cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(RED)
    canvas.rect(0, 0, 14, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(HexColor("#F5C518"))
    canvas.rect(14, 0, 5, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont(FONT_B, 9)
    canvas.drawString(48, PAGE_H - 42 * mm, "SMART INDIA HACKATHON  ·  TECHNICAL PROPOSAL")
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(2)
    canvas.line(48, PAGE_H - 45 * mm, 120, PAGE_H - 45 * mm)
    canvas.setFont(FONT_B, 13)
    canvas.setFillColor(RED)
    canvas.drawString(48, PAGE_H - 62 * mm, "JEEVAN")
    canvas.setFillColor(white)
    canvas.setFont(FONT_B, 28)
    canvas.drawString(48, PAGE_H - 78 * mm, "Adding machine learning")
    canvas.drawString(48, PAGE_H - 90 * mm, "to ambulance dispatch")
    canvas.setFont(FONT, 11)
    canvas.setFillColor(HexColor("#C8C4BC"))
    canvas.drawString(48, PAGE_H - 104 * mm, "Can it be implemented?  Yes.  Here is exactly where, and how.")
    y = 78 * mm
    for line in [
        "FastAPI + SvelteKit prototype  ·  Yelahanka / BMSIT corridor",
        "Stack already includes scikit-learn, XGBoost, NumPy, pandas",
        "Keep Dijkstra / TomTom routing.  Use ML to score, rank, and correct.",
    ]:
        canvas.setFillColor(HexColor("#9A958C"))
        canvas.circle(52, y + 2, 2.2, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#E8E4DC"))
        canvas.setFont(FONT, 9.5)
        canvas.drawString(62, y, line)
        y -= 8 * mm
    canvas.setFillColor(HexColor("#5A564E"))
    canvas.setFont(FONT, 8)
    canvas.drawString(48, 22 * mm, "Confidential to the project team  ·  diagrams describe the current repo, not a live EMS")
    canvas.restoreState()


def callout(text: str, fill, stroke) -> Table:
    inner = Paragraph(text, S["Callout"])
    t = Table([[inner]], colWidths=[CONTENT_W - 8])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 1.2, stroke),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def table(headers, rows, col_w=None):
    head = [Paragraph(h, S["Th"]) for h in headers]
    body = [[Paragraph(c, S["CellB"] if i == 0 else S["Cell"]) for i, c in enumerate(r)] for r in rows]
    data = [head] + body
    t = Table(data, colWidths=col_w or [CONTENT_W / len(headers)] * len(headers), repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("BACKGROUND", (0, 1), (-1, -1), white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, CREAM]),
                ("GRID", (0, 0), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(i, S["Item"]), leftIndent=12, bulletColor=RED) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=14,
        spaceBefore=2,
        spaceAfter=8,
        bulletFontName=FONT_B,
        bulletFontSize=9,
    )


def build():
    story = []

    # cover is drawn by first-page template; still need a blank flow to consume page 1
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    # TOC
    story.append(Paragraph("Contents", S["H1"]))
    toc = [
        "1.  Verdict — yes, and the hooks already exist",
        "2.  What the system does today",
        "3.  Gaps that ML should fill",
        "4.  Where ML belongs (and where it does not)",
        "5.  Target pipeline after ML",
        "6.  Model 1 — incident triage",
        "7.  Model 2 — ETA residual",
        "8.  Model 3 — hospital ranking",
        "9.  Files, runtime rules, and what not to do",
        "10. Phased plan and honest constraints",
    ]
    for line in toc:
        story.append(Paragraph(line, S["TOC"]))
    story.append(Spacer(1, 8))
    story.append(
        callout(
            "<b>One-line answer.</b> Implementable. Do not replace routing with a neural net. "
            "Plug a trained model into triage, ETA correction, and hospital ranking — the three "
            "places the current pipeline still uses rules and constants.",
            ML_BG,
            ML,
        )
    )
    story.append(PageBreak())

    # 1
    story.append(Paragraph("1.  Verdict", S["H1"]))
    story.append(
        Paragraph(
            "Machine learning can be added to JEEVAN. The useful work is not replacing NetworkX "
            "Dijkstra or TomTom / OSRM with a neural net. It is plugging a trained model into the "
            "gaps the current pipeline still fills with checkbox rules and fixed multipliers.",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "The Python stack already lists <b>scikit-learn</b>, <b>xgboost</b>, <b>numpy</b>, and "
            "<b>pandas</b> in <font face='Courier'>backend/requirements.txt</font>. "
            "<font face='Courier'>ortools</font> is also declared and unused — that is an assignment "
            "solver, not ML, and should stay that way for multi-call matching.",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "There is already a stub at <font face='Courier'>backend/app/services/ml_triage.py</font>. "
            "It imports XGBoost, then ignores it and keyword-matches “fire” / “accident”. "
            "<font face='Courier'>ARCHITECTURE.md</font> describes a Random Forest ETA pipeline that "
            "is <b>not in the current code</b>. The “AI” on the request page is NVIDIA LLMs for chat "
            "and report analysis — generative AI, not a trained dispatch model — and that analysis "
            "is never sent to <font face='Courier'>POST /tracking/dispatch</font>.",
            S["Body"],
        )
    )
    story.append(
        callout(
            "<b>So the question is not “can we add ML?”</b> It is “which model actually improves "
            "this prototype, given there is almost no real trip history?” The rest of this document "
            "answers that with the current code as the source of truth.",
            AMBER_BG,
            AMBER,
        )
    )

    # 2
    story.append(Paragraph("2.  What the system does today", S["H1"]))
    story.append(
        Paragraph(
            "Dispatch is optimisation plus heuristics. A staff or patient request on "
            "<font face='Courier'>/request</font> collects a description, narrative, age group, "
            "optional medical-report image, and four history flags. Only the flags and a hardcoded "
            "BMSIT coordinate reach the backend.",
            S["Body"],
        )
    )
    story.append(Diagram(430, draw_current))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Ambulance pick (<font face='Courier'>dispatch_optimizer._pick_ambulance</font>) "
            "shortlists three units by haversine distance, then scores them with an emergency route. "
            "Hospital pick (<font face='Courier'>optimize_hospital_dispatch</font>) is the lowest "
            "pickup-plus-transport time. Beds and specialisations are stored on each hospital seed "
            "in <font face='Courier'>fleet.py</font> and returned in the candidate list, but they "
            "<b>do not change who wins</b>. Priority is "
            "<font face='Courier'>corridor.mission_priority</font>: cardiac=5, pregnant=4, epilepsy=3, "
            "diabetes=2, else 1. ETA is live routing × a fixed 0.70 emergency factor × 1.08 if raining. "
            "<font face='Courier'>_peak_traffic_factor</font> exists and is unused. Confidence is a "
            "heuristic gap between the winner and runner-up, not a model probability.",
            S["Body"],
        )
    )

    # 3
    story.append(Paragraph("3.  Gaps that ML should fill", S["H1"]))
    story.append(
        table(
            ["Piece", "Current behaviour", "Unused / stub"],
            [
                [
                    "Priority",
                    "Four medical checkboxes only",
                    "Free-text, age, and report analysis never change dispatch",
                ],
                [
                    "Ambulance",
                    "Nearest 3 by distance, then fastest emergency route",
                    "No learned correction of that ETA",
                ],
                [
                    "Hospital",
                    "Fastest ETA only",
                    "available_beds and specializations stored, not scored",
                ],
                [
                    "ETA",
                    "Router seconds × 0.70 × optional rain 1.08",
                    "_peak_traffic_factor unused",
                ],
                [
                    "ML file",
                    "Dummy keyword matcher in ml_triage.py",
                    "XGBoost never trained or loaded",
                ],
                [
                    "Persistence",
                    "dispatch_cases / dispatches tables",
                    "Not enough real trip history to train on",
                ],
            ],
            [78, 200, 221],
        )
    )
    story.append(Spacer(1, 8))

    # 4
    story.append(Paragraph("4.  Where ML belongs (and where it does not)", S["H1"]))
    story.append(
        Paragraph(
            "Treat ML as a scorer sitting in front of the optimiser you already have. Live routing, "
            "corridor occupancy, and hard medical constraints stay deterministic. That is also the "
            "honest story for judges: you are not claiming a self-driving ambulance.",
            S["Body"],
        )
    )
    story.append(Diagram(310, draw_keep_vs_ml))
    story.append(Spacer(1, 8))
    story.append(
        table(
            ["Keep as-is", "Add ML"],
            [
                ["Which roads to drive (Dijkstra / TomTom / OSRM)", "How severe the call is (triage)"],
                ["Corridor conflict + police / rescue SMS", "How wrong the router ETA is for this hour / weather"],
                [
                    "Cardiac must reach Cardiac / ICU / Trauma if a capable hospital is nearby",
                    "Rank hospitals by ETA + beds + specialty match",
                ],
                ["Live GPS simulation", "Demand / idle positioning (later only)"],
            ],
            [249, 250],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        callout(
            "<b>Do not</b> train a model to invent routes. The graph already does that. "
            "ML should score, rank, or correct numbers the optimiser already produces.",
            HexColor("#F8E4E4"),
            RED,
        )
    )

    # 5
    story.append(Paragraph("5.  Target pipeline after ML", S["H1"]))
    story.append(
        Paragraph(
            "The request page already collects everything a triage model needs. The dispatch endpoint "
            "already accepts <font face='Courier'>notes</font> and an optional "
            "<font face='Courier'>priority</font> override. The missing piece is a load-once model "
            "call between those two.",
            S["Body"],
        )
    )
    story.append(Diagram(360, draw_target))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "<b>Runtime rule.</b> Load models at API process start. If a <font face='Courier'>.ubj</font> "
            "or <font face='Courier'>.json</font> file is missing, keep today’s heuristics. Dispatch "
            "must never 500 because ML is down.",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Do not call NVIDIA on the hot path for every SOS.</b> LLMs are slow, costly, and "
            "non-deterministic. Use them only to enrich features (a report summary), then let "
            "XGBoost decide. That keeps the “AI analysis” button as a feature source, not as the "
            "dispatcher.",
            S["Body"],
        )
    )

    # 6
    story.append(Paragraph("6.  Model 1 — incident triage (ship first)", S["H1"]))
    story.append(
        Paragraph(
            "<b>Problem.</b> Description, age, and report analysis never change dispatch. Priority "
            "is only four checkboxes. A “severe bleeding, unresponsive” narrative is treated the "
            "same as a stable fever if the flags are empty.",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Model.</b> Gradient boosting (XGBoost — already a dependency) classifying "
            "LOW / MEDIUM / HIGH / CRITICAL, mapped onto the existing 1–5 "
            "<font face='Courier'>mission_priority</font> scale so corridor conflict resolution "
            "does not need a new type.",
            S["Body"],
        )
    )
    story.append(Diagram(250, draw_triage))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Features", S["H2"]))
    story.append(
        bullets(
            [
                "Text: TF-IDF (or a small embedding) of description + narrative",
                "Age group already collected on the request page (infant → elderly)",
                "Cardiac / diabetes / epilepsy / pregnant flags",
                "Hour of day and the existing is_raining flag",
                "Optional: parsed severity from /ai/analyze-report — LLM as a <i>feature</i>, not the decision",
            ]
        )
    )
    story.append(Paragraph("Labels and training (hackathon-honest)", S["H2"]))
    story.append(
        Paragraph(
            "There is no 108-call archive in this repo. Judges will accept a synthetic set if you "
            "can defend the rules, show held-out accuracy, and keep a fallback. Example label policy:",
            S["Body"],
        )
    )
    story.append(
        table(
            ["Pattern in caller text / context", "Label", "Priority"],
            [
                ["Unresponsive, not breathing, severe bleeding, chest pain + collapse", "CRITICAL", "5"],
                ["Accident / fracture, conscious; major trauma flags", "HIGH", "4"],
                ["Fever, fall, stable vitals language; chronic flags only", "MEDIUM", "2–3"],
                ["Non-urgent transport language", "LOW", "1"],
            ],
            [280, 110, 109],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Train offline in <font face='Courier'>backend/app/ml/train_triage.py</font>, dump "
            "<font face='Courier'>backend/app/ml/models/triage.ubj</font>, load once in "
            "<font face='Courier'>ml_triage.py</font> replacing DummyTriageModel. "
            "<b>Safety:</b> keyword / rule overrides stay above the model (unresponsive → always CRITICAL). "
            "On the request page, show a severity chip with confidence <i>before</i> Auto-assign, and "
            "send the predicted priority in the dispatch body.",
            S["Body"],
        )
    )
    story.append(
        callout(
            "<b>Why this is the first model.</b> Highest demo value, smallest data need, and it "
            "completes a file the repo already pretends exists. It also matches what ARCHITECTURE.md "
            "promised (“rule-based triage → ML severity adjustment”).",
            ML_BG,
            ML,
        )
    )

    # 7
    story.append(Paragraph("7.  Model 2 — ETA residual (technical depth)", S["H1"]))
    story.append(
        Paragraph(
            "<b>Problem.</b> TomTom / OSRM duration × 0.70 is a guess. Real ambulance time in North "
            "Bangalore depends on hour, rain, corridor occupancy, and road class. The peak-hour "
            "factor is written and never applied.",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Model.</b> Regression (XGBoost or sklearn Random Forest) predicting a "
            "<b>residual in seconds</b>:",
            S["Body"],
        )
    )
    story.append(
        Paragraph("actual_travel_s  -  router_duration_s", S["MonoBlock"])
    )
    story.append(
        Paragraph(
            "At inference: <font face='Courier'>eta = router_duration * 0.70 * rain_factor + "
            "model.predict(features)</font>. Wire this into "
            "<font face='Courier'>_apply_emergency_eta</font> / "
            "<font face='Courier'>optimize_hospital_dispatch</font> so hospital ranking uses the "
            "corrected minutes. If the model file is missing, keep the current constants.",
            S["Body"],
        )
    )
    story.append(Diagram(200, draw_eta))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "<b>Data problem.</b> Simulated fleet ticks are not ground truth. For SIH: (1) log every "
            "dispatch — predicted ETA, route source, weather, hour, hospital, ambulance; (2) when a "
            "simulated trip completes, log actual seconds from phase_started_at → complete; "
            "(3) optionally synthesise thousands of origin–destination pairs with a noisy “truth” "
            "(router time × random 0.85–1.35 by hour and rain). Say “trained on simulated Yelahanka "
            "missions + router residuals,” not “production EMS model.” This is the piece "
            "ARCHITECTURE.md called <font face='Courier'>ml_engine.py</font>.",
            S["Body"],
        )
    )

    # 8
    story.append(Paragraph("8.  Model 3 — hospital ranking", S["H1"]))
    story.append(
        Paragraph(
            "<b>Problem.</b> Lowest ETA can send a cardiac patient to Yelahanka Government Hospital "
            "if it is two minutes closer than Aster CMI or M.S. Ramaiah — both of which list Cardiac "
            "/ Trauma / ICU on the seed data. Beds never enter the score.",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>You do not need a neural net first.</b> A weighted score on the existing candidate "
            "list is enough, and it is easier to defend:",
            S["Body"],
        )
    )
    story.append(
        Paragraph(
            "score = w1 * eta_min  +  w2 * (0 if specialty matches else 15)\n"
            "      +  w3 * max(0, 4 - available_beds)  +  w4 * (0 if ICU else 10)",
            S["MonoBlock"],
        )
    )
    story.append(
        Paragraph(
            "If you want ML later: an XGBoost ranker on synthetic “good destination” labels "
            "(cardiac → Cardiac/ICU even if slightly slower; pediatric + child → pediatric; "
            "trauma + HIGH → trauma with beds). Either way, keep a <b>hard constraint</b> in front "
            "of the scorer.",
            S["Body"],
        )
    )
    story.append(Diagram(230, draw_hospital))
    story.append(Spacer(1, 8))
    story.append(
        callout(
            "<b>Hard constraint.</b> Never send cardiac to a hospital with no Cardiac / ICU / Trauma "
            "if a capable one is within N minutes. ML reranks the feasible set. It does not override "
            "safety. That sentence belongs on the demo slide.",
            AMBER_BG,
            AMBER,
        )
    )

    # 9
    story.append(Paragraph("9.  Files, runtime rules, and what not to do", S["H1"]))
    story.append(Paragraph("Suggested layout", S["H2"]))
    story.append(
        Paragraph(
            "backend/app/ml/train_triage.py          generate synthetic data, train, dump model<br/>"
            "backend/app/ml/train_eta.py             optional, phase C<br/>"
            "backend/app/ml/models/triage.ubj        committed artefact for the demo<br/>"
            "backend/app/services/ml_triage.py      load-once + predict(); delete dummy keywords<br/>"
            "backend/app/api/tracking.py            call triage, set priority<br/>"
            "frontend/src/routes/request/+page.svelte  severity chip before Auto-assign",
            S["MonoBlock"],
        )
    )
    story.append(Paragraph("Later, not ML", S["H2"]))
    story.append(
        bullets(
            [
                "<b>OR-Tools assignment</b> when several SOS events arrive at once — already in requirements, unused. Use it instead of a neural matcher.",
                "<b>Demand heatmap / idle positioning</b> needs weeks of logs; fake Bangalore peak patterns only if time remains.",
                "<b>Vitals deterioration</b> — tick_vitals is random noise; a small “unstable” classifier is an easy demo and weak science. Do not lead with it.",
            ]
        )
    )
    story.append(
        callout(
            "<b>A stub that imports unused XGBoost looks worse than no ML file.</b> Either train "
            "ml_triage.py or remove the dead import. Judges will open that file.",
            HexColor("#F8E4E4"),
            RED,
        )
    )

    # 10
    story.append(Paragraph("10.  Phased plan and honest constraints", S["H1"]))
    story.append(Diagram(175, draw_phases))
    story.append(Spacer(1, 8))
    story.append(
        table(
            ["Phase", "What", "Effort", "Demo impact"],
            [
                ["A", "Text + flags → XGBoost → priority on dispatch", "1–2 days", "High — “AI triage” becomes real"],
                ["B", "Hospital score: ETA + specialty + beds (rules first)", "~½ day", "High — cardiac goes to Aster / Ramaiah"],
                ["D", "Log predicted vs actual on dispatch_cases", "1 day", "Needed before C is real"],
                ["C", "Synthetic ETA residual model on logged trips", "2–3 days", "Medium-high — technical depth"],
                ["E", "Demand / idle positioning", "skip unless time", "Low for SIH"],
            ],
            [48, 210, 90, 151],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "For a hackathon, <b>A + B is the honest win</b>. C is the technical-depth slide. "
            "Do not start with deep learning or reinforcement learning for routing.",
            S["Body"],
        )
    )
    story.append(Paragraph("Constraints to say out loud", S["H2"]))
    story.append(
        bullets(
            [
                "<b>No real 108/EMS dataset</b> in the repo. Synthetic training is acceptable if you show the feature list, held-out accuracy, and the fallback path.",
                "<b>Simulated fleet time is not Bangalore traffic.</b> Caption C as simulated Yelahanka residuals, not a production travel-time model.",
                "<b>Medical ML is high-stakes.</b> Rule overrides (unresponsive → CRITICAL; cardiac → capable hospital) stay above the model.",
                "The current “AI” features (Nemotron chat, Tavus intake, vision report analysis) can stay as product UX. They are not the dispatch brain.",
            ]
        )
    )

    story.append(Paragraph("Bottom line", S["H1"]))
    story.append(
        callout(
            "Implementable, and the hooks already exist: <font face='Courier'>ml_triage.py</font>, "
            "sklearn / xgboost, <font face='Courier'>priority</font> on dispatch, unused hospital "
            "beds and specialisations. Start by making triage a real classifier and hospital pick "
            "specialty-aware. Add ETA residual ML only after those two are visible in the UI. "
            "Keep Dijkstra. Keep the corridor. Keep the safety rules.",
            KEEP_BG,
            KEEP,
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "This document describes the JEEVAN prototype in this repository. It is not a medical "
            "device specification and must not be used to dispatch real emergency vehicles without "
            "a clinically validated protocol and live EMS data.",
            S["FigNote"],
        )
    )

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 4 * mm,
        bottomMargin=MARGIN_B + 2 * mm,
        title="JEEVAN — Machine Learning Implementation Plan",
        author="JEEVAN project",
        subject="Where and how to add ML to the ambulance dispatch prototype",
    )
    doc.build(story, onFirstPage=_cover, onLaterPages=_header_footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
