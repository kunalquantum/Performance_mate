"""
Parse the GrantsNow Task Sheet's 'GrantsNow Breakdown' sheet into a clean
weekly email-campaign dataframe.

The source layout is one metric per row and one week per column, with the
first 9 rows holding the email metrics. Percentages are embedded in some
cells like '3,025 (95.7%)'. The parser strips them and computes rates
consistently.

Output: data/emails.csv, one row per week, with:
    week_label, week_start, emails_sent, contacts, delivered, bounced,
    opened, clicks, delivery_rate, bounce_rate, open_rate, click_rate
"""

import os
import re
import argparse
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
OUT = os.path.join(DATA_DIR, "emails.csv")
DEFAULT_SRC = os.path.join(SOURCES_DIR, "GrantsNow Task Sheet.xlsx")


def _num(cell):
    """Extract the primary integer from a cell that may look like:
    '3,025 (95.7%)', '14', '55 + 14', 'A=3 B=3', or blank. Returns int or NaN.
    """
    if cell is None:
        return float("nan")
    s = str(cell).strip()
    if not s or s.lower() == "nan":
        return float("nan")
    m = re.search(r"([\d,]+)", s)
    if not m:
        return float("nan")
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return float("nan")


def _pct(cell):
    """Extract the percentage in a cell like '3,025 (95.7%)'. Returns
    float in [0, 1] or NaN."""
    if cell is None:
        return float("nan")
    s = str(cell)
    m = re.search(r"([\d.]+)\s*%", s)
    if not m:
        return float("nan")
    try:
        return float(m.group(1)) / 100.0
    except ValueError:
        return float("nan")


# Rough calendar mapping from the free-text week labels used in the sheet.
# The labels span December 2024 to July 2025 based on GrantsNow's cycle,
# but the year is implicit. We anchor to 2024-12-08 for the first label and
# increment approximately by week from there.
def _week_start_guess(labels):
    """Given the ordered list of week labels, produce a rough Monday for
    each. Uses an anchor and steps forward by 7 days per column.

    The Task Sheet labels are irregular ('Feb 1st-10th', 'Feb 10-13th'), so
    we do not try to parse them precisely - we just walk forward one week
    per column starting from the anchor. That gives a monotonic date axis
    which is enough for charting."""
    anchor = pd.Timestamp("2024-12-08")
    return [anchor + pd.Timedelta(days=7 * i) for i in range(len(labels))]


def _ab_split(cell):
    """Detect 'A=N B=M' patterns in a cell and return (a, b) or (nan, nan)."""
    if cell is None:
        return (float("nan"), float("nan"))
    s = str(cell)
    a = re.search(r"A\s*=\s*(\d+)", s)
    b = re.search(r"B\s*=\s*(\d+)", s)
    if a and b:
        return (int(a.group(1)), int(b.group(1)))
    return (float("nan"), float("nan"))


def _split_companies(cell):
    """Row 11 cells hold newline-separated university names, sometimes with
    trailing labels like ' - click' or '(5)'. Split on newlines and commas
    outside parentheses. Return a clean list."""
    if cell is None:
        return []
    s = str(cell).strip()
    if not s or s.lower() == "nan" or s == "0":
        return []
    # split on newline, then trim trailing ' - click', '(5)', etc.
    parts = re.split(r"[\n\r]+", s)
    out = []
    for p in parts:
        name = p.strip()
        if not name or name == "0":
            continue
        # strip parenthetical annotations like '(5)' at end
        name = re.sub(r"\s*\(\d+\)\s*$", "", name)
        # strip trailing ' - click' / ' Grant Management Software' etc.
        name = re.sub(r"\s*-\s*click\s*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+Grant Management.*$", "", name,
                        flags=re.IGNORECASE)
        # normalize casing hint: collapse extra whitespace
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            out.append(name)
    return out


def _newsletter_field(cell):
    """Row 12 mixes integer subscriber counts (later weeks) with free-text
    notes (earlier weeks). Return (count_or_nan, note_text_or_empty)."""
    if cell is None:
        return (float("nan"), "")
    s = str(cell).strip()
    if not s or s.lower() == "nan":
        return (float("nan"), "")
    if s == "0":
        return (0, "")
    # pure integer?
    if re.fullmatch(r"\d+", s):
        return (int(s), "")
    return (float("nan"), s)


def parse(sheet_path, sheet_name="GrantsNow Breakdown"):
    raw = pd.read_excel(sheet_path, sheet_name=sheet_name, header=None)
    labels = [str(v).strip() for v in raw.iloc[0, 1:].tolist()
              if pd.notna(v)]
    n_weeks = len(labels)

    def row(name):
        # find the row whose col0 equals name
        for i in range(len(raw)):
            if str(raw.iloc[i, 0]).strip().lower() == name.lower():
                return raw.iloc[i, 1:1 + n_weeks].tolist()
        return [float("nan")] * n_weeks

    contacts_raw = row("Contacts sent")
    delivered_raw = row("Delivered")
    bounced_raw = row("Bounced")
    opened_raw = row("Opened")
    clicks_raw = row("Clicks")

    # A/B split detection (from the 'Contacts sent' row)
    ab_contacts = [_ab_split(v) for v in contacts_raw]
    ab_delivered = [_ab_split(v) for v in delivered_raw]

    # Rows 10-12: replies, interested companies (Cognism), newsletter subs
    replies_raw = row("Replies")
    interest_raw = row("Most interested companies(Cognism)")
    newsletter_raw = row("NewsLetter Subscriber")

    interest_lists = [_split_companies(v) for v in interest_raw]
    interest_counts = [len(lst) for lst in interest_lists]
    interest_joined = ["; ".join(lst) for lst in interest_lists]

    newsletter_parsed = [_newsletter_field(v) for v in newsletter_raw]
    newsletter_counts = [x[0] for x in newsletter_parsed]
    newsletter_notes = [x[1] for x in newsletter_parsed]

    out = pd.DataFrame({
        "week_label": labels,
        "week_start": _week_start_guess(labels),
        "emails_sent": [_num(v) for v in row("Emails sent")],
        "contacts": [_num(v) for v in contacts_raw],
        "delivered": [_num(v) for v in delivered_raw],
        "bounced": [_num(v) for v in bounced_raw],
        "opened": [_num(v) for v in opened_raw],
        "clicks": [_num(v) for v in clicks_raw],
        # keep any embedded percentages, we will fall back to derived rates
        "delivered_pct_reported": [_pct(v) for v in delivered_raw],
        "bounced_pct_reported": [_pct(v) for v in bounced_raw],
        "opened_pct_reported": [_pct(v) for v in opened_raw],
        "clicks_pct_reported": [_pct(v) for v in clicks_raw],
        # A/B batches when the sheet uses A=N B=M notation
        "ab_a_contacts": [x[0] for x in ab_contacts],
        "ab_b_contacts": [x[1] for x in ab_contacts],
        "ab_a_delivered": [x[0] for x in ab_delivered],
        "ab_b_delivered": [x[1] for x in ab_delivered],
        # Rows 10-12: engagement/intent signals
        "replies": [_num(v) for v in replies_raw],
        "interested_companies_count": interest_counts,
        "interested_companies_raw": interest_joined,
        "newsletter_subs": newsletter_counts,
        "newsletter_note": newsletter_notes,
    })

    # derive canonical rates
    def _safe_div(n, d):
        return (pd.to_numeric(n, errors="coerce")
                / pd.to_numeric(d, errors="coerce").replace(0, pd.NA))

    out["delivery_rate"] = out["delivered_pct_reported"].fillna(
        _safe_div(out["delivered"], out["contacts"]))
    out["bounce_rate"] = out["bounced_pct_reported"].fillna(
        _safe_div(out["bounced"], out["contacts"]))
    # opens and clicks are typically expressed against delivered
    out["open_rate"] = out["opened_pct_reported"].fillna(
        _safe_div(out["opened"], out["delivered"]))
    out["click_rate"] = out["clicks_pct_reported"].fillna(
        _safe_div(out["clicks"], out["delivered"]))
    # click-to-open rate (a common secondary metric)
    out["ctor"] = _safe_div(out["clicks"], out["opened"])

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df = parse(args.src)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} weeks to {args.out}")
    print()
    print("Sample:")
    cols = ["week_label", "emails_sent", "contacts", "delivered",
             "open_rate", "click_rate"]
    print(df[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
