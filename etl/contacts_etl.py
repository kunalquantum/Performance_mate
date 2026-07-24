"""
Load the cleaned UK contacts workbook and write data/contacts.csv.

The source workbook (GN_UK_Contacts_Cleaned.xlsx, sheet Master_Clean)
is already segmented and hygiene-checked, so this is essentially a
pass-through with two derived boolean columns for the Email Matrix:

    is_send_ready  -> send_status starts with '1'
    is_fresh       -> already_approached == 'No'
"""

import os
import argparse
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
OUT = os.path.join(DATA_DIR, "contacts.csv")
DEFAULT_SRC = os.path.join(SOURCES_DIR, "GN_UK_Contacts_Cleaned.xlsx")


def parse(src, sheet="Master_Clean"):
    df = pd.read_excel(src, sheet_name=sheet)
    df["is_send_ready"] = df["send_status"].astype(str).str.startswith("1")
    df["is_fresh"] = df["already_approached"].astype(str).str.strip().str.lower() == "no"
    df["is_verified"] = df["deliverability"].astype(str).str.strip().str.lower() == "verified"
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df = parse(args.src)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} contacts to {args.out}")
    print()
    print("Distribution:")
    print(f"  Send ready:         {df['is_send_ready'].sum()}")
    print(f"  Fresh:              {df['is_fresh'].sum()}")
    print(f"  Verified:           {df['is_verified'].sum()}")
    print(f"  Send-ready + fresh: {(df['is_send_ready'] & df['is_fresh']).sum()}")


if __name__ == "__main__":
    main()
