"""
Parse the 'MQL for SALES' tab of the GrantsNow Task Sheet.

Each row is one highly-engaged prospect with cumulative opens + clicks
across every email we have sent them. This is our closest thing to
per-recipient tracking:
    - We know WHO engaged
    - We know HOW MUCH they engaged (open/click counts)
    - We can infer their persona from the job title
    - We know if sales has already contacted them

Output: data/mql_engaged.csv
"""
import os
import re
import argparse
import pandas as pd

ROOT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
DEFAULT_SRC = os.path.join(SOURCES_DIR, "GrantsNow Task Sheet.xlsx")


# Persona inference rules from job title. Longest / most specific
# patterns first so "Research Finance Manager" hits Finance, not
# Research.
PERSONA_RULES = [
    # Finance-first (research finance is finance)
    (r"\b(research\s+finance|finance\s+system|finance\s+director|"
     r"finance\s+manager|cfo|chief\s+financial|head\s+of\s+finance|"
     r"deputy\s+finance|financial\s+transactions|university\s+finance|"
     r"faculty\s+finance|deputy\s+cfo|fp&a|finance)\b", "Finance"),

    # IT-Systems
    (r"\b(cio|chief\s+information|it\s+director|head\s+of\s+it|"
     r"director\s+of\s+it|deputy\s+director\s+of\s+it|"
     r"information\s+technology|digital\s+strategy|"
     r"digital\s+transformation|it\s+operations|"
     r"research\s+computing|information\s+services|"
     r"technology\s+and)\b", "IT-Systems"),

    # Research (broadest catch)
    (r"\b(research|grants?|pre[- ]?award|post[- ]?award|"
     r"innovation|pro[- ]?vice[- ]?chancellor|principal|"
     r"vice[- ]?chancellor|provost|impact|knowledge\s+exchange|"
     r"academic|professor|programme\s+management|"
     r"research\s+services|business\s+intelligence)\b", "Research"),
]


def _infer_persona(job_title):
    if not isinstance(job_title, str) or not job_title.strip():
        return "Unclassified"
    t = job_title.lower()
    for pattern, persona in PERSONA_RULES:
        if re.search(pattern, t):
            return persona
    return "Unclassified"


def _parse_engagement(text):
    """Turn '11 Opens, 1 Click' / '5 clicks' / '2 Click' / '5' into
    (opens, clicks) ints. Missing counts default to 0."""
    opens = 0
    clicks = 0
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return (opens, clicks)
    s = str(text).lower().strip()
    if not s:
        return (opens, clicks)
    # 'N open[s]' pattern
    m = re.search(r"(\d+)\s*opens?", s)
    if m:
        opens = int(m.group(1))
    # 'N click[s]' pattern
    m = re.search(r"(\d+)\s*click", s)
    if m:
        clicks = int(m.group(1))
    # Bare number: if nothing else matched, treat as clicks
    # (looking at data, bare numbers like "5" show up next to click-heavy rows)
    if opens == 0 and clicks == 0:
        m = re.search(r"(\d+)", s)
        if m:
            clicks = int(m.group(1))
    return (opens, clicks)


def parse(src, sheet="MQL for SALES"):
    df = pd.read_excel(src, sheet_name=sheet)
    df.columns = [c.strip() for c in df.columns]

    # Drop rows without a name
    df = df.dropna(subset=["First Name"]).copy()

    # Parse engagement column
    df["_eng"] = df["Engagements"].apply(_parse_engagement)
    df["opens"]  = df["_eng"].apply(lambda t: t[0])
    df["clicks"] = df["_eng"].apply(lambda t: t[1])
    df["total_engagement"] = df["opens"] + df["clicks"]

    # Infer persona from job title
    df["persona"] = df["Job title"].apply(_infer_persona)

    # Sales-contacted flag
    df["sales_touched"] = df.get(
        "Ian/Sales contacted ", df.get("Ian/Sales contacted", None))

    # Canonical output
    out = pd.DataFrame({
        "first_name":     df["First Name"],
        "last_name":      df["Surname"],
        "institution":    df["Account"],
        "job_title":      df["Job title"],
        "persona":        df["persona"],
        "opens":          df["opens"],
        "clicks":         df["clicks"],
        "total_engagement": df["total_engagement"],
        "email":          df["Email"],
        "phone":          df.get("Phone Number"),
        "office":         df.get("Office"),
        "linkedin":       df.get("Linkedin"),
        "sales_touched":  df["sales_touched"],
        "worktribe":      df.get("Worktribe?"),
        "date":           df.get("Date"),
        "notes":          df.get("Notes"),
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out",
                      default=os.path.join(DATA_DIR, "mql_engaged.csv"))
    args = ap.parse_args()

    df = parse(args.src)
    df.to_csv(args.out, index=False)

    print(f"Wrote {len(df)} MQL rows to {args.out}")
    print()
    print("By persona:")
    print(df["persona"].value_counts().to_string())
    print()
    print("Engagement totals:")
    print(f"  Total opens:  {int(df['opens'].sum())}")
    print(f"  Total clicks: {int(df['clicks'].sum())}")
    print()
    print("By persona, engagement totals:")
    grp = df.groupby("persona").agg(
        rows=("first_name", "count"),
        opens=("opens", "sum"),
        clicks=("clicks", "sum"))
    print(grp.to_string())


if __name__ == "__main__":
    main()
