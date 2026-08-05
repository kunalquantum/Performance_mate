"""
Parse the Contact Audit & Masterlist workbook into a set of clean CSVs
the Persona pages read.

Output files (all under data/):
    persona_institution_coverage.csv   (institution x persona counts)
    persona_gaps.csv                    (missing personas + priority)
    persona_review_queue.csv            (contacts flagged for review)
    persona_contacts_full.csv           (all Relevant tabs concatenated
                                         with a `bucket` column)
"""
import os
import argparse
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
DEFAULT_SRC = os.path.join(SOURCES_DIR,
                             "Contact_Audit_and_Masterlist__3_.xlsx")


def _clean_col(c):
    """Strip the mojibake bullet ('�') and collapse whitespace in a
    column name so we can safely rename with normal ASCII."""
    if not isinstance(c, str):
        return c
    return (c.replace("�", "-")
             .replace("  ", " ")
             .strip())


def parse_coverage(xl):
    df = pd.read_excel(xl, sheet_name="UK Institution Coverage")
    df.columns = [_clean_col(c) for c in df.columns]
    # rename the awkward sub-columns
    ren = {
        "- Senior":      "research_senior",
        "- Operational": "research_operational",
        "- Academic":    "research_academic",
    }
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    df = df.rename(columns={
        "Institution (canonical)": "institution_key",
        "Name as it appears":      "institution",
        "Type":                    "type",
        "In target list":          "in_target",
        "Contacts":                "contacts",
        "Research":                "research",
        "Finance":                 "finance",
        "IT/Systems":              "it_systems",
        "Unclassified":            "unclassified",
        "Personas held":           "personas_held",
        "Valid emails":            "valid_emails",
        "Missing personas":        "missing_personas",
    })
    return df


def parse_gaps(xl):
    df = pd.read_excel(xl, sheet_name="Persona Gaps & Priorities")
    df.columns = [_clean_col(c) for c in df.columns]
    df = df.rename(columns={
        "Institution":            "institution",
        "Contacts held":          "contacts_held",
        "Research":               "research",
        "Finance":                "finance",
        "IT/Systems":             "it_systems",
        "Personas held":          "personas_held",
        "What is missing":        "what_is_missing",
        "Priority":               "priority",
        "Lookup key (canonical)": "institution_key",
    })
    return df


def parse_review(xl):
    df = pd.read_excel(xl, sheet_name="Persona - To Review")
    df.columns = [_clean_col(c) for c in df.columns]
    df = df.rename(columns={
        "Sheet":           "source_sheet",
        "Row":             "source_row",
        "Job Title":       "job_title",
        "Institution":     "institution",
        "Persona applied": "persona_applied",
        "Why flagged":     "why_flagged",
    })
    return df


def parse_contacts(xl):
    """Concatenate the four Relevant tabs into a single dataframe with a
    `bucket` column marking which one the row came from."""
    tabs = {
        "In CRM valid":         "Relevant - In CRM valid",
        "In CRM unknown":       "Relevant - In CRM unknown",
        "In NOW CRM valid":     "Relevant - IN NOW CRM valid",
        "In NOW CRM unknown":   "Relevant - IN NOW CRM unknown",
        "Not CRM not valid":    "Relevant - Not CRM not valid",
        "In CRM not valid":     "Relevant - In CRM not valid",
    }
    frames = []
    for bucket, sheet in tabs.items():
        try:
            df = pd.read_excel(xl, sheet_name=sheet)
        except Exception:
            continue
        df.columns = [_clean_col(c) for c in df.columns]
        df["bucket"] = bucket
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    # Normalise columns we care about
    out = out.rename(columns={
        "First Name":              "first_name",
        "Last Name":               "last_name",
        "Company / Account Name":  "company",
        "Account In ZOHO CRM":     "in_zoho_crm",
        "Job Title":               "job_title",
        "Country":                 "country",
        "Email":                   "email",
        "Persona":                 "persona",
        "Band":                    "band",
        "Reason":                  "reason",
        "Snov Status":             "snov_status",
        "Research Tier":           "research_tier",
        "Institution (canonical)": "institution_key",
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DATA_DIR)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    xl = pd.ExcelFile(args.src)

    coverage = parse_coverage(xl)
    gaps     = parse_gaps(xl)
    review   = parse_review(xl)
    contacts = parse_contacts(xl)

    coverage.to_csv(os.path.join(args.out,
                                    "persona_institution_coverage.csv"),
                       index=False)
    gaps.to_csv(os.path.join(args.out, "persona_gaps.csv"), index=False)
    review.to_csv(os.path.join(args.out, "persona_review_queue.csv"),
                    index=False)
    contacts.to_csv(os.path.join(args.out, "persona_contacts_full.csv"),
                       index=False)

    print(f"Wrote coverage      : {len(coverage)} rows")
    print(f"Wrote gaps          : {len(gaps)} rows")
    print(f"Wrote review queue  : {len(review)} rows")
    print(f"Wrote contacts full : {len(contacts)} rows")


if __name__ == "__main__":
    main()
