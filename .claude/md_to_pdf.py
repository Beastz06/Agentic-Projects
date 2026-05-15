"""Convert the logistics analysis markdown to a styled PDF using reportlab."""
import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT

SRC = Path(r"C:\Users\shaur\career-ops-main\.claude\output\logistics_proposal_analysis.md")
DST = Path(r"C:\Users\shaur\career-ops-main\.claude\output\logistics_proposal_analysis.pdf")

text = SRC.read_text(encoding="utf-8")

styles = getSampleStyleSheet()

H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                   fontSize=18, leading=22, spaceBefore=14, spaceAfter=10,
                   textColor=colors.HexColor("#0B2545"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                   fontSize=14, leading=18, spaceBefore=14, spaceAfter=8,
                   textColor=colors.HexColor("#0B2545"))
H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
                   fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=6,
                   textColor=colors.HexColor("#13315C"))
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                     fontSize=9.5, leading=13, alignment=TA_LEFT, spaceAfter=5)
BULLET = ParagraphStyle("Bullet", parent=BODY, leftIndent=14, bulletIndent=2,
                       spaceAfter=2)
QUOTE = ParagraphStyle("Quote", parent=BODY, fontName="Helvetica-Oblique",
                      textColor=colors.HexColor("#444444"), spaceBefore=8)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8, leading=10,
                      textColor=colors.HexColor("#555555"))


def md_inline(s: str) -> str:
    """Convert inline markdown to reportlab Paragraph markup."""
    # Escape XML special chars first (but keep markdown markers)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold then italic
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\*\w])\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
    # Inline code
    s = re.sub(r"`([^`]+)`", r'<font face="Courier" size="9">\1</font>', s)
    # Replace red/yellow/green emoji with colored circles (reportlab can't render emoji)
    s = s.replace("🟢", '<font color="#1B7F3B"><b>&#9679;</b></font>')
    s = s.replace("🟡", '<font color="#C99700"><b>&#9679;</b></font>')
    s = s.replace("🔴", '<font color="#B91C1C"><b>&#9679;</b></font>')
    return s


def parse_table(lines, idx):
    """Parse a github-flavored markdown table starting at idx. Returns (Table flowable, new_idx)."""
    header = [c.strip() for c in lines[idx].strip().strip("|").split("|")]
    sep = lines[idx + 1]  # separator line, skipped
    rows = [header]
    j = idx + 2
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
        # Pad/truncate to header width
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        else:
            cells = cells[: len(header)]
        rows.append(cells)
        j += 1

    # Convert each cell to a Paragraph for wrapping
    cell_style = ParagraphStyle("Cell", parent=BODY, fontSize=8.5, leading=11)
    head_style = ParagraphStyle("CellHead", parent=cell_style,
                                fontName="Helvetica-Bold",
                                textColor=colors.white)
    table_data = []
    for r_i, row in enumerate(rows):
        styled_row = []
        for cell in row:
            cell_html = md_inline(cell)
            styled_row.append(Paragraph(cell_html, head_style if r_i == 0 else cell_style))
        table_data.append(styled_row)

    # Compute column widths: scale by header text length, fit to 7.0in usable width
    avail = 7.0 * inch
    raw_widths = [max(40, min(180, len(h) * 5 + 30)) for h in header]
    total = sum(raw_widths)
    col_widths = [w / total * avail for w in raw_widths]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2545")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F2F4F7")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD2D9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl, j


flowables = []
lines = text.split("\n")
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()

    if not stripped:
        flowables.append(Spacer(1, 4))
        i += 1
        continue

    # Horizontal rule
    if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
        flowables.append(Spacer(1, 6))
        flowables.append(Table([[""]], colWidths=[7.0 * inch],
                               style=[("LINEABOVE", (0, 0), (-1, 0), 0.7,
                                       colors.HexColor("#CBD2D9"))]))
        flowables.append(Spacer(1, 6))
        i += 1
        continue

    # Headings
    m = re.match(r"^(#{1,6})\s+(.*)", stripped)
    if m:
        level = len(m.group(1))
        content = md_inline(m.group(2))
        style = {1: H1, 2: H2, 3: H3}.get(level, H3)
        flowables.append(Paragraph(content, style))
        i += 1
        continue

    # Table
    if stripped.startswith("|") and i + 1 < len(lines) and re.match(
            r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lines[i + 1]):
        tbl, i = parse_table(lines, i)
        flowables.append(KeepTogether([tbl, Spacer(1, 8)]))
        continue

    # Bullet list
    if re.match(r"^\s*[-*+]\s+", line):
        bullets = []
        while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
            content = re.sub(r"^\s*[-*+]\s+", "", lines[i])
            bullets.append(Paragraph("&#8226;&nbsp;&nbsp;" + md_inline(content), BULLET))
            i += 1
        flowables.extend(bullets)
        flowables.append(Spacer(1, 4))
        continue

    # Numbered list
    if re.match(r"^\s*\d+\.\s+", line):
        items = []
        n = 1
        while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
            content = re.sub(r"^\s*\d+\.\s+", "", lines[i])
            items.append(Paragraph(f"{n}.&nbsp;&nbsp;" + md_inline(content), BULLET))
            n += 1
            i += 1
        flowables.extend(items)
        flowables.append(Spacer(1, 4))
        continue

    # Italic-only trailing source line (single-line)
    if stripped.startswith("*") and stripped.endswith("*") and stripped.count("*") >= 2:
        inner = stripped.strip("*").strip()
        flowables.append(Paragraph(md_inline(inner), SMALL))
        i += 1
        continue

    # Plain paragraph (gather contiguous non-blank, non-special lines)
    para_lines = [stripped]
    i += 1
    while i < len(lines):
        nxt = lines[i].strip()
        if (not nxt or nxt.startswith("#") or nxt.startswith("|")
                or re.match(r"^\s*[-*+]\s+", lines[i])
                or re.match(r"^\s*\d+\.\s+", lines[i])
                or re.fullmatch(r"-{3,}|\*{3,}|_{3,}", nxt)):
            break
        para_lines.append(nxt)
        i += 1
    para = " ".join(para_lines)
    flowables.append(Paragraph(md_inline(para), BODY))


doc = SimpleDocTemplate(str(DST), pagesize=letter,
                        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                        title="Logistics 4PL — Vendor Proposal Analysis",
                        author="L'Occitane Procurement")
doc.build(flowables)
print(f"Wrote: {DST}  ({DST.stat().st_size:,} bytes)")
