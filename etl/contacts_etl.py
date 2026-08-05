"""
Build data/contacts.csv from the Contact Audit & Masterlist workbook.

This is the single source of truth for persona/contact data across the
whole app. It reads the same Contact_Audit_and_Masterlist workbook that
persona_data_etl.py uses, keeps only UK contacts on target institutions,
and produces a Boolean-flagged CSV the Home / Board pack / Audience
pages can consume.

Column mapping from Contact Audit -> contacts.csv:
    bucket             ->  is_send_ready  (True for the "valid" buckets)
    snov_status        ->  is_verified    (True when marked valid)
    persona            ->  persona_final
    research_tier      ->  seniority_tier
    company            ->  institution
    institution_key    ->  institution_key (for join with coverage)

We DO NOT carry an `is_fresh` flag because the Contact Audit workbook
does not track whether a contact has been approached before. The
audience page treats all contacts as fresh; add a tracking column to
the workbook if we want to distinguish approached vs not.
"""
import os
import argparse
import pandas as pd

ROOT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR    = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
DEFAULT_SRC = os.path.join(SOURCES_DIR,
                             "Contact_Audit_and_Masterlist__3_.xlsx")

SEND_READY_BUCKETS = {"In CRM valid", "In NOW CRM valid"}


def _clean(c):
    if not isinstance(c, str):
        return c
    return c.replace("�", "-").replace("  ", " ").strip()


def _read_bucket(xl, sheet, bucket_name):
    try:
        df = pd.read_excel(xl, sheet_name=sheet)
    except Exception:
        return pd.DataFrame()
    df.columns = [_clean(c) for c in df.columns]
    df["bucket"] = bucket_name
    return df


def build(src_path):
    xl = pd.ExcelFile(src_path)
    frames = []
    for bucket, sheet in [
        ("In CRM valid",         "Relevant - In CRM valid"),
        ("In CRM unknown",       "Relevant - In CRM unknown"),
        ("In NOW CRM valid",     "Relevant - IN NOW CRM valid"),
        ("In NOW CRM unknown",   "Relevant - IN NOW CRM unknown"),
        ("Not CRM not valid",    "Relevant - Not CRM not valid"),
        ("In CRM not valid",     "Relevant - In CRM not valid"),
    ]:
        f = _read_bucket(xl, sheet, bucket)
        if not f.empty:
            frames.append(f)
    if not frames:
        raise SystemExit("no Relevant tabs found in workbook")
    raw = pd.concat(frames, ignore_index=True, sort=False)

    # Restrict to UK rows
    raw = raw[raw["Country"].astype(str).str.upper() == "UK"].copy()

    # Coverage sheet gives us the target-institution flag
    cov = pd.read_excel(xl, sheet_name="UK Institution Coverage")
    cov.columns = [_clean(c) for c in cov.columns]
    cov = cov.rename(columns={
        "Institution (canonical)": "institution_key",
        "In target list":          "in_target",
    })
    target_keys = set(
        cov[cov["in_target"].astype(str).str.lower() == "yes"]
        ["institution_key"].dropna().astype(str))

    # Rename core cols
    df = raw.rename(columns={
        "First Name":              "first_name",
        "Last Name":               "last_name",
        "Company / Account Name":  "institution",
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

    # Derived flags
    df["is_send_ready"] = df["bucket"].isin(SEND_READY_BUCKETS)
    df["is_verified"]   = (df["snov_status"].astype(str).str.lower()
                             == "valid")
    df["in_target"]     = df["institution_key"].astype(str).isin(target_keys)
    # No approached tracking in this workbook -> default all True so the
    # existing "exclude approached" toggle is a no-op rather than a lie.
    df["is_fresh"]      = True

    # Names / joins the pages already expect
    df["persona_final"] = df["persona"].fillna("Unclassified")
    df["seniority_tier"]= df["research_tier"].fillna("Unspecified")
    df["email_clean"]   = df["email"].astype(str).str.strip()

    # segment_key for the Next Send Builder
    df["segment_key"] = (df["persona_final"].astype(str) + " | "
                          + df["seniority_tier"].astype(str))

    # Contacts count per institution (for the Audience persona-band tile)
    inst_counts = df.groupby("institution_key")["email"].count() \
        .rename("institution_contacts")
    df = df.merge(inst_counts, on="institution_key", how="left")

    # A rough band from institution_contacts for the sidebar filter
    def _band(n):
        if n >= 21:  return "D 21 plus"
        if n >= 6:   return "C 6 to 20"
        if n >= 2:   return "B 2 to 5"
        return "A Single contact"
    df["institution_band"] = df["institution_contacts"].apply(_band)

    # Contact id (row-order based; stable across ETL runs given input order)
    df = df.reset_index(drop=True)
    df["contact_id"] = "GN-" + (df.index + 1).astype(str).str.zfill(6)

    # Final column selection - keep only what the pages actually use
    out_cols = [
        "contact_id", "first_name", "last_name", "email_clean",
        "job_title", "institution", "institution_key",
        "persona_final", "seniority_tier", "segment_key",
        "band", "reason", "country",
        "institution_contacts", "institution_band",
        "bucket", "snov_status", "in_zoho_crm",
        "is_send_ready", "is_verified", "is_fresh", "in_target",
    ]
    out = df[[c for c in out_cols if c in df.columns]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out",
                      default=os.path.join(DATA_DIR, "contacts.csv"))
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df = build(args.src)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} UK contacts to {args.out}")
    print()
    print("Distribution:")
    print(f"  Send ready:                {int(df['is_send_ready'].sum()):,}")
    print(f"  Verified emails:           {int(df['is_verified'].sum()):,}")
    print(f"  On target institutions:    {int(df['in_target'].sum()):,}")
    print(f"  Send-ready + verified + target: "
          f"{int((df['is_send_ready'] & df['is_verified'] & df['in_target']).sum()):,}")
    print()
    print("By persona:")
    print(df["persona_final"].value_counts().to_string())


if __name__ == "__main__":
    main()
