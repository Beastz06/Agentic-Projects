
import os, json
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, HRFlowable)

BASE = r"C:\Users\shaur\career-ops-main\.claude\RFP\Logistics\Logistics\Vendors responses"
RUBRIC = json.load(open(os.path.join(BASE, "rubric.json")))
PROPOSAL = json.load(open(os.path.join(BASE, "proposal_data.json")))
VENDOR_DATA = json.load(open(os.path.join(BASE, "vendor_data.json")))

DATE_STR = date.today().strftime("%Y-%m-%d")
OUTPUT = os.path.join(BASE, f"proposal-analysis-{DATE_STR}.pdf")
print("OUTPUT=",OUTPUT)
