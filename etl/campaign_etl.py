"""
Parse the 'Email Campaign' sheet from the GrantsNow Marketing Calendar into
a clean per-email dataframe.

Source layout: one row per campaign, with a Base Content column and three
follow-up columns (A / B / C). We explode into one row per email (base plus
each populated follow-up) so downstream analysis operates uniformly.

Output: data/campaigns.csv
    campaign_id, campaign_name, objective, persona_raw, stage,
    subject, body, full_text, char_count, word_count, has_subject
"""

import os
import re
import argparse
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
OUT = os.path.join(DATA_DIR, "campaigns.csv")
DEFAULT_SRC = os.path.join(SOURCES_DIR, "GrantsNow Marketing Calendar (1).xlsx")


def _split_subject_body(text):
    """Given a raw cell, return (subject, body). The subject follows the
    first 'Subject:' marker if present; otherwise blank."""
    if text is None:
        return ("", "")
    s = str(text).strip()
    if not s or s.lower() == "nan":
        return ("", "")
    # First 'Subject: ...' up to newline
    m = re.search(r"subject\s*:\s*(.+)", s, flags=re.IGNORECASE)
    if not m:
        return ("", s)
    subject = m.group(1).splitlines()[0].strip()
    # Body: everything after the subject line
    body = s[m.end(1):].lstrip("\r\n ").strip()
    return (subject, body)


def _clean(text):
    """Strip control chars, collapse whitespace, return trimmed string."""
    if text is None:
        return ""
    s = str(text)
    # Common mojibake bullets used in the sheet ('�')
    s = s.replace("�", "-")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse(src, sheet="Email Campaign"):
    raw = pd.read_excel(src, sheet_name=sheet, header=None)
    # Header row is R0; data rows R1..
    rows = []
    for r in range(1, len(raw)):
        campaign_name = str(raw.iat[r, 1]).strip() \
            if pd.notna(raw.iat[r, 1]) else ""
        objective = str(raw.iat[r, 2]).strip() \
            if pd.notna(raw.iat[r, 2]) else ""
        persona = str(raw.iat[r, 3]).strip() \
            if pd.notna(raw.iat[r, 3]) else ""

        for stage_idx, stage_name in [(4, "Base"), (5, "Follow-up A"),
                                       (6, "Follow-up B"),
                                       (7, "Follow-up C")]:
            cell = raw.iat[r, stage_idx] if stage_idx < raw.shape[1] else None
            if cell is None or (isinstance(cell, float)
                                  and pd.isna(cell)):
                continue
            text = _clean(cell)
            if not text or text.lower() == "nan":
                continue
            subject, body = _split_subject_body(text)
            full_text = text
            rows.append({
                "campaign_id": r,
                "campaign_name": campaign_name or "-",
                "objective": objective,
                "persona_raw": persona,
                "stage": stage_name,
                "subject": subject,
                "body": body,
                "full_text": full_text,
                "char_count": len(full_text),
                "word_count": len(re.findall(r"\b\w+\b", full_text)),
                "has_subject": bool(subject),
            })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df = parse(args.src)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} emails to {args.out}")
    print()
    print(df[["campaign_name", "stage", "has_subject",
              "word_count"]].to_string(index=False))


if __name__ == "__main__":
    main()
