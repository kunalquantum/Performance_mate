"""
Ingest a Zoho CRM sync workbook (Accounts / Leads / Contacts / masterlist).

Each sheet is normalised to a CSV under `data/crm_sync/` so downstream
Persona pages can read it fresh. The workbook itself is backed up
raw under `data/uploads/`. A small summary row is appended to
`data/upload_log.csv`.

Also refreshes an "in_zoho_crm" flag on the top-level `contacts.csv`
so any UK contact whose email appears in the CRM export is marked
present. Non-destructive: existing columns are preserved.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CRM_DIR = DATA_DIR / "crm_sync"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CRM_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _read_sheet(wb, sheet_name: str) -> pd.DataFrame:
    """Read one sheet into a DataFrame respecting the first row as
    the header. Uses read_only=True workbooks so this scales."""
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return pd.DataFrame()
    header = [str(c) if c is not None else f"col_{i}"
              for i, c in enumerate(rows[0])]
    return pd.DataFrame(rows[1:], columns=header)


def preview(xlsx_path: str | Path) -> Dict[str, int]:
    """Return {sheet_name: row_count} without touching disk."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True,
                                  read_only=True)
    out = {}
    for name in wb.sheetnames:
        ws = wb[name]
        # max_row includes the header
        out[name] = max(ws.max_row - 1, 0)
    return out


def ingest(xlsx_path: str | Path) -> Dict:
    src = Path(xlsx_path)
    if not src.exists():
        raise FileNotFoundError(src)

    # 1. Backup raw
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", src.name)
    backup = UPLOADS_DIR / f"{ts}_{safe}"
    shutil.copy2(src, backup)

    # 2. Load workbook (read_only for scale)
    wb = openpyxl.load_workbook(backup, data_only=True, read_only=True)

    written: Dict[str, int] = {}
    per_sheet: Dict[str, str] = {}

    # 3. Save each recognised sheet to its own CSV under data/crm_sync/
    known = {"accounts": "crm_accounts.csv",
             "leads":    "crm_leads.csv",
             "contacts": "crm_contacts.csv",
             "masterlist": "crm_masterlist.csv"}
    lower_map = {n.lower(): n for n in wb.sheetnames}
    for key, out_name in known.items():
        actual = lower_map.get(key)
        if not actual:
            continue
        df = _read_sheet(wb, actual)
        out_path = CRM_DIR / out_name
        _atomic_write(df, out_path)
        written[key] = len(df)
        per_sheet[key] = str(out_path)

    # 4. Refresh in_zoho_crm flag on top-level contacts.csv
    #    (non-destructive - only touches the flag column)
    flag_updated = 0
    contacts_path = DATA_DIR / "contacts.csv"
    if contacts_path.exists():
        contacts = pd.read_csv(contacts_path)
        if "email" in contacts.columns:
            crm_emails: set = set()
            for k in ("leads", "contacts"):
                p = CRM_DIR / known[k] if k in written else None
                if p and p.exists():
                    df = pd.read_csv(p)
                    for col in ("Email", "email"):
                        if col in df.columns:
                            crm_emails.update(
                                df[col].dropna().astype(str).str.strip()
                                .str.lower().tolist())
                            break
            if crm_emails:
                if "in_zoho_crm" not in contacts.columns:
                    contacts["in_zoho_crm"] = ""
                mask = contacts["email"].astype(str).str.strip() \
                    .str.lower().isin(crm_emails)
                prev = contacts["in_zoho_crm"].astype(str).fillna("")
                new_val = mask.map({True: "Yes", False: "No"})
                # Only overwrite where different, count changes
                flag_updated = int((prev != new_val).sum())
                contacts["in_zoho_crm"] = new_val
                _atomic_write(contacts, contacts_path)

    # 5. Append audit log
    log_path = DATA_DIR / "upload_log.csv"
    log_row = {
        "timestamp":         _dt.datetime.now().strftime(
                                 "%Y-%m-%d %H:%M:%S"),
        "filename":          src.name,
        "backup_path":       backup.name,
        "week_ending":       "",
        "campaigns_added":   0,
        "campaigns_overwritten": 0,
        "campaigns_skipped": 0,
        "emails_row_added":  0,
        "mql_added":         0,
        "mql_updated":       0,
        "copy_added":        0,
        "skip_dupes":        False,
        "file_type":         "crm_sync",
        "accounts":          written.get("accounts", 0),
        "leads":             written.get("leads", 0),
        "contacts_rows":     written.get("contacts", 0),
        "masterlist":        written.get("masterlist", 0),
        "in_zoho_crm_flag_changes": flag_updated,
    }
    if log_path.exists():
        log = pd.read_csv(log_path)
        # add any missing columns before concat
        for col in log_row.keys():
            if col not in log.columns:
                log[col] = pd.NA
        log = pd.concat([log, pd.DataFrame([log_row])],
                          ignore_index=True)
    else:
        log = pd.DataFrame([log_row])
    _atomic_write(log, log_path)

    return {
        "type":       "crm_sync",
        "written":    written,
        "outputs":    per_sheet,
        "backup":     str(backup),
        "flag_updated_on_contacts": flag_updated,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    args = ap.parse_args()
    r = ingest(args.xlsx)
    print("INGESTED (CRM SYNC)")
    for k, v in r["written"].items():
        print(f"  {k}: {v} rows -> {r['outputs'][k]}")
    print(f"  contacts flag updates: {r['flag_updated_on_contacts']}")
    print(f"  backup: {r['backup']}")
