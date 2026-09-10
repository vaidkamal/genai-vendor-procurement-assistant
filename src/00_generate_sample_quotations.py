"""
00_generate_sample_quotations.py
--------------------------------
Creates three FICTIONAL vendor quotation PDFs for the capstone demo.
Each vendor uses a different layout, currency, and way of describing
warranty / delivery / payment, so that the standardisation step has
genuine work to do.

Run:  python src/00_generate_sample_quotations.py
Out:  data/quotations/*.pdf
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "quotations"
OUT.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
H = ParagraphStyle("h", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
SUB = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
BODY = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
SMALL = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#444444"))


def table(data, col_widths, header=True, accent="#1F3A5F"):
    t = Table(data, colWidths=col_widths)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(accent)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------- Vendor 1
def techsource():
    doc = SimpleDocTemplate(str(OUT / "Q1_TechSource_Solutions.pdf"), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    s = []
    s.append(Paragraph("TechSource Solutions Inc.", H))
    s.append(Paragraph("2210 Harbor Drive, Suite 400 · Fictional City · sales@techsource-fictional.example", SUB))
    s.append(Spacer(1, 10))
    s.append(Paragraph("<b>QUOTATION</b> &nbsp;&nbsp; Quote No: TS-Q-88231 &nbsp;&nbsp; Date: 01 September 2026", BODY))
    s.append(Paragraph("To: Procurement, Bramwell &amp; Co. Consulting &nbsp;&nbsp; Ref: PR-2026-0917 — Business laptops", BODY))
    s.append(Spacer(1, 12))
    s.append(table([
        ["Item", "Description", "Qty", "Unit Price (USD)", "Line Total (USD)"],
        ["1", "ProBook 14 G11 business laptop\nIntel Core Ultra 5, 16 GB RAM, 512 GB NVMe SSD,\n14\" FHD display, Windows 11 Pro", "40", "1,285.00", "51,400.00"],
        ["2", "Freight and insured delivery (single consignment)", "1", "450.00", "450.00"],
    ], [14 * mm, 82 * mm, 14 * mm, 30 * mm, 32 * mm]))
    s.append(Spacer(1, 8))
    s.append(table([
        ["Subtotal (excl. tax)", "USD 51,850.00"],
        ["Sales tax (8.1%)", "USD 4,199.85"],
        ["Total incl. tax", "USD 56,049.85"],
    ], [120 * mm, 52 * mm], header=False))
    s.append(Spacer(1, 14))
    s.append(Paragraph("<b>Terms and conditions</b>", BODY))
    for line in [
        "Warranty: 3-year manufacturer warranty with onsite next-business-day service included in the unit price.",
        "Lead time: 14 calendar days from receipt of purchase order. Devices are imaged with the customer's corporate build before dispatch.",
        "Payment terms: Net 30 days from invoice. A 2% early-payment discount applies if settled within 10 days.",
        "Quote validity: 30 days from the date above.",
        "Certifications: ISO 27001:2022 and ISO 9001:2015 (certificates available on request).",
        "Prices are in US dollars and exclude sales tax unless stated.",
    ]:
        s.append(Paragraph("• " + line, SMALL))
    doc.build(s)


# ---------------------------------------------------------------- Vendor 2
def alpine():
    doc = SimpleDocTemplate(str(OUT / "Q2_Alpine_IT_Supplies.pdf"), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    s = []
    s.append(Paragraph("Alpine IT Supplies GmbH", H))
    s.append(Paragraph("Angebot / Commercial Offer · Offer no. AL-2026-4471 · 02.09.2026", SUB))
    s.append(Spacer(1, 10))
    s.append(Paragraph("Dear Procurement Team,", BODY))
    s.append(Paragraph(
        "Thank you for your enquiry PR-2026-0917. We are pleased to offer the following for 40 (forty) units of the "
        "Alpine Nova 14 business notebook.", BODY))
    s.append(Spacer(1, 10))
    s.append(table([
        ["Specification", "Detail"],
        ["Processor", "AMD Ryzen 7 PRO"],
        ["Memory", "16 GB DDR5"],
        ["Storage", "512 GB SSD"],
        ["Display", "14 inch, 1920 x 1200, anti-glare"],
        ["Operating system", "Windows 11 Pro pre-installed"],
        ["Extras", "Asset tagging and corporate imaging at no charge"],
    ], [50 * mm, 120 * mm], accent="#2E5E4E"))
    s.append(Spacer(1, 10))
    s.append(Paragraph("<b>Commercial terms</b>", BODY))
    for line in [
        "Price per unit: EUR 1,190.00 net, delivered (shipping included).",
        "Quantity: 40 units. Order value: EUR 47,600.00 net.",
        "Standard warranty: 2 years carry-in. Optional 3-year extended warranty (carry-in): EUR 85.00 per unit.",
        "Delivery: within 4 weeks of order confirmation.",
        "Payment: Net 45 days.",
        "Validity of this offer: 30 days.",
        "Quality management: ISO 9001:2015 certified. Information-security certification: in progress (audit scheduled Q4 2026).",
        "All prices in EUR, excluding VAT.",
    ]:
        s.append(Paragraph("• " + line, SMALL))
    s.append(Spacer(1, 12))
    s.append(Paragraph("With kind regards,<br/>Sales Team, Alpine IT Supplies GmbH (fictional)", BODY))
    doc.build(s)


# ---------------------------------------------------------------- Vendor 3
def megabyte():
    doc = SimpleDocTemplate(str(OUT / "Q3_MegaByte_Distribution.pdf"), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    s = []
    s.append(Paragraph("MEGABYTE DISTRIBUTION LLC — BUNDLE QUOTE", H))
    s.append(Paragraph("Quote #MB-77012 · Issued 03 Sep 2026 · Prepared for Bramwell &amp; Co. Consulting (PR-2026-0917)", SUB))
    s.append(Spacer(1, 12))
    s.append(table([
        ["Bundle", "What's included", "Bundle Price (USD)"],
        ["Enterprise Laptop Pack — 40 seats",
         "40 x Velocity 14 Pro (Intel Core i7, 16GB RAM, 1TB SSD, 14\" display, Win 11 Pro)\n"
         "3-year depot warranty (mail-in repair)\n"
         "Free ground shipping\n"
         "Corporate image deployment",
         "54,900.00"],
    ], [42 * mm, 100 * mm, 36 * mm], accent="#7A2E2E"))
    s.append(Spacer(1, 8))
    s.append(Paragraph("Bundle total: <b>USD 54,900.00</b> (all-inclusive, excludes applicable taxes). "
                       "Effective per-seat price USD 1,372.50.", BODY))
    s.append(Spacer(1, 10))
    s.append(Paragraph("<b>Conditions</b>", BODY))
    for line in [
        "Ships in 10 business days after deposit is received.",
        "Payment schedule: 50% deposit with order, 50% on delivery.",
        "Volume discount: additional 3% off if quantity is 50 seats or more.",
        "Offer valid for 14 days.",
        "Warranty: 3 years depot (customer ships device to our repair centre; typical turnaround 7-10 days).",
        "MegaByte Distribution is ISO 27001 certified for its configuration and imaging services.",
    ]:
        s.append(Paragraph("• " + line, SMALL))
    doc.build(s)


if __name__ == "__main__":
    techsource()
    alpine()
    megabyte()
    for p in sorted(OUT.glob("*.pdf")):
        print("created", p.relative_to(ROOT))
