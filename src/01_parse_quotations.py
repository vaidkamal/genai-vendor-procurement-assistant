"""
01_parse_quotations.py
----------------------
Reads every vendor quotation PDF in data/quotations/, extracts the commercial
facts, and writes ONE standardised record per vendor.

Two extraction modes:
  * rules (default)  - deterministic regex rules. Reproducible, no API needed.
  * llm              - Claude reads the raw quote text and fills the same JSON
                       schema. Better for messy real-world quotes. Requires
                       ANTHROPIC_API_KEY. Numbers are still re-validated by code.

Run:  python src/01_parse_quotations.py [--mode rules|llm]
Out:  outputs/standardised_quotations.json
      outputs/standardised_quotations.csv
"""
import argparse
import csv
import json
import math
import os
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
QUOTE_DIR = ROOT / "data" / "quotations"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

# Fixed reference rates for the demo (a real deployment would pull daily rates).
FX_TO_USD = {"USD": 1.00, "EUR": 1.08, "GBP": 1.27, "CHF": 1.12}

SCHEMA_FIELDS = [
    "vendor_name", "quote_ref", "currency", "quantity", "unit_price", "shipping_cost",
    "warranty_years_included", "warranty_type", "warranty_extension_years",
    "warranty_extension_per_unit", "delivery_days_calendar", "payment_terms_days",
    "prepayment_pct", "validity_days", "iso27001", "ram_gb", "storage_gb",
    "screen_inches", "os", "extras",
]


# ----------------------------------------------------------------- helpers
def read_pdf_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def money(s: str) -> float:
    return float(s.replace(",", ""))


def first(pattern, text, flags=re.I, group=1, default=None, cast=None):
    m = re.search(pattern, text, flags)
    if not m:
        return default
    val = m.group(group)
    return cast(val) if cast else val


# ----------------------------------------------------------- rule extraction
def extract_rules(text: str, filename: str) -> dict:
    t = text
    rec = {k: None for k in SCHEMA_FIELDS}
    rec["source_file"] = filename
    rec["extraction_mode"] = "rules"

    # Vendor + reference
    name = t.strip().splitlines()[0].split(" — ")[0].strip()
    if name.isupper():  # normalise shouty letterheads
        name = " ".join(w.upper() if w.lower() in ("llc", "gmbh", "inc", "ltd", "ag") else w.capitalize() for w in name.split())
    rec["vendor_name"] = name
    rec["quote_ref"] = first(r"(?:Quote No|Offer no\.?|Quote #)[:\s]*([A-Z0-9\-]+)", t)

    # Currency
    if re.search(r"\bEUR\b", t):
        rec["currency"] = "EUR"
    elif re.search(r"\bGBP\b|£", t):
        rec["currency"] = "GBP"
    else:
        rec["currency"] = "USD"

    # Quantity
    rec["quantity"] = (
        first(r"Quantity:\s*(\d{2,4})\s*units", t, cast=int)
        or first(r"(\d{2,4})\s*(?:\(\w+\)\s*)?(?:units|seats)", t, cast=int)
        or first(r"\b(\d{2,4})\s+x\s", t, cast=int)
        # line-item table row: "... <qty> <unit price> <line total>"
        or first(r"\s(\d{2,4})\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}", t, cast=int)
    )

    # Unit price / bundle price
    unit = first(r"Price per unit:\s*[A-Z]{3}\s*([\d,]+\.\d{2})", t, cast=money)
    if unit is None:
        # line-item table: "... 40 1,285.00 51,400.00"
        unit = first(r"\n1\s.*?\s(\d{2,3})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})", t, flags=re.S, group=2, cast=money)
    if unit is None:
        bundle = first(r"Bundle total:\s*USD\s*([\d,]+\.\d{2})", t, cast=money)
        if bundle and rec["quantity"]:
            unit = round(bundle / rec["quantity"], 2)
            rec["extras"] = ["Bundle price split evenly across seats"]
    rec["unit_price"] = unit

    # Shipping
    ship = first(r"(?:Freight|Shipping|Delivery)[^\n]*?\s1\s+([\d,]+\.\d{2})\s+[\d,]+\.\d{2}", t, cast=money)
    if ship is None and re.search(r"shipping included|Free ground shipping|delivered \(shipping included\)", t, re.I):
        ship = 0.0
    rec["shipping_cost"] = ship if ship is not None else 0.0

    # Warranty
    w = re.search(r"(\d)[\s-]*years?\s+(?:manufacturer\s+)?warranty\s+with\s+(onsite)", t, re.I) \
        or re.search(r"Standard warranty:\s*(\d)\s*years?\s+(carry-in|onsite|depot)", t, re.I) \
        or re.search(r"(\d)[\s-]*years?\s+(depot|onsite|carry-in)\s+warranty", t, re.I)
    if w:
        rec["warranty_years_included"] = int(w.group(1))
        rec["warranty_type"] = w.group(2).lower()
    ext = re.search(r"Optional\s+(\d)-year extended warranty\s*\((\w[\w-]*)\):\s*[A-Z]{3}\s*([\d,]+\.\d{2})\s*per unit", t, re.I)
    if ext:
        rec["warranty_extension_years"] = int(ext.group(1))
        rec["warranty_extension_per_unit"] = money(ext.group(3))
        rec["warranty_type"] = ext.group(2).lower()
    else:
        rec["warranty_extension_years"] = rec["warranty_years_included"]
        rec["warranty_extension_per_unit"] = 0.0

    # Delivery -> calendar days
    d = re.search(r"(\d+)\s*(calendar days|business days|working days|weeks|days)", t, re.I)
    if d:
        n, unit_word = int(d.group(1)), d.group(2).lower()
        if "week" in unit_word:
            rec["delivery_days_calendar"] = n * 7
        elif "business" in unit_word or "working" in unit_word:
            rec["delivery_days_calendar"] = math.ceil(n * 7 / 5)
        else:
            rec["delivery_days_calendar"] = n

    # Payment terms
    net = first(r"Net\s*(\d+)", t, cast=int)
    dep = first(r"(\d{1,3})%\s*deposit", t, cast=int)
    rec["payment_terms_days"] = net if net is not None else 0
    rec["prepayment_pct"] = dep if dep is not None else 0

    # Validity
    rec["validity_days"] = first(r"valid(?:ity)?[^\d\n]*?(\d+)\s*days", t, cast=int)

    # ISO 27001
    if re.search(r"ISO 27001", t) and not re.search(r"security certification:\s*in progress", t, re.I):
        rec["iso27001"] = "yes"
    elif re.search(r"in progress", t, re.I):
        rec["iso27001"] = "in progress"
    else:
        rec["iso27001"] = "no"

    # Specs
    rec["ram_gb"] = first(r"(\d{1,3})\s*GB\s*(?:DDR5\s*)?(?:RAM|DDR)", t, cast=int) or first(r"Memory\s+(\d{1,3})\s*GB", t, cast=int)
    st = re.search(r"(\d+)\s*(TB|GB)\s*(?:NVMe\s*)?SSD", t, re.I)
    if st:
        rec["storage_gb"] = int(st.group(1)) * (1024 if st.group(2).upper() == "TB" else 1)
    rec["screen_inches"] = first(r"(\d{2})(?:\"|\s*inch)", t, cast=int)
    rec["os"] = "Windows 11 Pro" if re.search(r"Win(?:dows)?\s*11\s*Pro", t, re.I) else None

    extras = rec.get("extras") or []
    if re.search(r"early-payment discount", t, re.I):
        extras.append("2% early-payment discount (10 days)")
    if re.search(r"asset tagging", t, re.I):
        extras.append("Free asset tagging")
    if re.search(r"Volume discount", t, re.I):
        extras.append("3% volume discount at 50+ seats")
    rec["extras"] = extras
    return rec


# ------------------------------------------------------------ LLM extraction
def extract_llm(text: str, filename: str) -> dict:
    """Ask Claude to fill the schema. Same output shape as extract_rules()."""
    import anthropic  # pip install anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    prompt = f"""You are a procurement analyst. Read the vendor quotation below and return ONLY a JSON object
with exactly these keys: {json.dumps(SCHEMA_FIELDS)}.
Rules:
- unit_price, shipping_cost, warranty_extension_per_unit are numbers in the quote's own currency (no symbols).
- delivery_days_calendar: convert weeks x7, business days x7/5 rounded up.
- payment_terms_days: the Net-N number, or 0 if payment is on/before delivery.
- prepayment_pct: percentage required before delivery, 0 if none.
- warranty_extension_years: the warranty length reachable by buying the extension (or the included years if none).
- iso27001: "yes", "no" or "in progress".
- storage_gb: convert TB to GB (1 TB = 1024 GB). extras: list of strings.
- Use null when the quote does not say. No prose, no markdown fences.

QUOTATION TEXT:
{text}"""
    msg = client.messages.create(model="claude-sonnet-4-5", max_tokens=1200,
                                 messages=[{"role": "user", "content": prompt}])
    raw = msg.content[0].text.strip().strip("`").removeprefix("json").strip()
    rec = json.loads(raw)
    rec["source_file"] = filename
    rec["extraction_mode"] = "llm"
    return rec


# ------------------------------------------------------------ standardise
def standardise(rec: dict) -> dict:
    """Deterministic normalisation and derived totals (never left to the LLM)."""
    fx = FX_TO_USD[rec["currency"]]
    qty = rec["quantity"] or 0
    unit = rec["unit_price"] or 0.0
    ship = rec["shipping_cost"] or 0.0
    ext = rec["warranty_extension_per_unit"] or 0.0
    rec["fx_rate_to_usd"] = fx
    rec["goods_total_native"] = round(qty * unit, 2)
    rec["warranty_extension_total_native"] = round(qty * ext, 2)
    rec["total_cost_native"] = round(qty * unit + ship + qty * ext, 2)
    rec["total_cost_usd"] = round(rec["total_cost_native"] * fx, 2)
    rec["unit_cost_usd_all_in"] = round(rec["total_cost_usd"] / qty, 2) if qty else None
    rec["effective_warranty_years"] = rec["warranty_extension_years"] or rec["warranty_years_included"]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["rules", "llm"], default="rules")
    args = ap.parse_args()
    if args.mode == "llm" and not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set - falling back to rule-based extraction.")
        args.mode = "rules"

    records = []
    for pdf in sorted(QUOTE_DIR.glob("*.pdf")):
        text = read_pdf_text(pdf)
        rec = extract_llm(text, pdf.name) if args.mode == "llm" else extract_rules(text, pdf.name)
        rec = standardise(rec)
        records.append(rec)
        print(f"{pdf.name:38s} -> {rec['vendor_name']:28s} total USD {rec['total_cost_usd']:>10,.2f}")

    (OUT_DIR / "standardised_quotations.json").write_text(json.dumps(records, indent=2))
    cols = ["vendor_name", "quote_ref", "currency", "quantity", "unit_price", "shipping_cost",
            "warranty_years_included", "warranty_type", "effective_warranty_years", "warranty_extension_per_unit",
            "delivery_days_calendar", "payment_terms_days", "prepayment_pct", "validity_days", "iso27001",
            "ram_gb", "storage_gb", "screen_inches", "os", "fx_rate_to_usd", "total_cost_usd", "unit_cost_usd_all_in"]
    with open(OUT_DIR / "standardised_quotations.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)
    print("wrote outputs/standardised_quotations.json and .csv")


if __name__ == "__main__":
    main()
