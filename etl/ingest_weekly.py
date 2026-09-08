"""
Headless ingest of a weekly ESP workbook.

Same append logic as pages/data_upload.py, callable from the CLI so
data can be loaded without spinning up Streamlit.

    python etl/ingest_weekly.py "C:/path/to/week.xlsx" [--skip-dupes]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from etl.weekly_upload_parser import parse_workbook  # noqa: E402

DATA_DIR = ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _dup_key(name, dt) -> str:
    return f"{str(name).strip().lower()}|{dt}"


def ingest(xlsx_path: str, skip_dupes: bool = False) -> dict:
    src = Path(xlsx_path)
    if not src.exists():
        raise FileNotFoundError(src)

    # 1. Backup raw file
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", src.name)
    backup = UPLOADS_DIR / f"{ts}_{safe}"
    shutil.copy2(src, backup)

    # 2. Parse
    parsed = parse_workbook(backup)
    campaigns  = parsed["campaigns"]
    week_total = parsed["week_total"] or {}
    openers    = parsed["openers"]
    clickers   = parsed["clickers"]
    week_end   = parsed["week_ending"]

    written = {"campaign_batches": 0, "campaign_batches_overwritten": 0,
               "campaign_batches_skipped": 0,
               "emails": 0, "mql_added": 0, "mql_updated": 0,
               "campaigns": 0}

    # 3. campaign_batches.csv
    cb_path = DATA_DIR / "campaign_batches.csv"
    cb = pd.read_csv(cb_path) if cb_path.exists() else pd.DataFrame(
        columns=["batch_id", "batch_name", "stage", "sent_date",
                 "subject", "body", "sent", "delivered", "opened",
                 "clicked", "replied"])
    existing_keys = {
        _dup_key(r.get("batch_name", ""), r.get("sent_date", ""))
        for _, r in cb.iterrows()}
    next_id = (int(cb["batch_id"].max()) + 1
               if not cb.empty and cb["batch_id"].notna().any() else 1)
    new_rows = []
    for c in campaigns:
        key = _dup_key(c["name"], c.get("sent_date"))
        dup = key in existing_keys
        if dup and skip_dupes:
            written["campaign_batches_skipped"] += 1
            continue
        if dup:
            mask = cb.apply(lambda r: _dup_key(r.get("batch_name", ""),
                                                r.get("sent_date", ""))
                            == key, axis=1)
            cb = cb[~mask]
            written["campaign_batches_overwritten"] += 1
        new_rows.append({
            "batch_id":  next_id,
            "batch_name": c["name"],
            "stage":     "Base",
            "sent_date": (c["sent_date"].strftime("%Y-%m-%d")
                          if c.get("sent_date") else ""),
            "subject":   c.get("subject") or "",
            "body":      c.get("body") or "",
            "sent":      c.get("sent"),
            "delivered": c.get("delivered"),
            "opened":    c.get("opened"),
            "clicked":   c.get("clicked"),
            "replied":   None,
        })
        next_id += 1
    if new_rows:
        cb = pd.concat([cb, pd.DataFrame(new_rows)], ignore_index=True)
        _atomic_write(cb, cb_path)
        written["campaign_batches"] = len(new_rows)

    # 4. emails.csv weekly rollup
    em_path = DATA_DIR / "emails.csv"
    if week_total and week_end:
        em = pd.read_csv(em_path) if em_path.exists() else pd.DataFrame()
        ws = week_end - _dt.timedelta(days=week_end.weekday())
        row = {
            "week_label":    f"Week of {ws.strftime('%d %b %Y')}",
            "week_start":    ws.strftime("%Y-%m-%d"),
            "emails_sent":   week_total.get("sent"),
            "delivered":     week_total.get("delivered"),
            "bounced":       week_total.get("bounced"),
            "opened":        week_total.get("opened"),
            "clicks":        week_total.get("clicked"),
            "open_rate":     week_total.get("opened_pct"),
            "click_rate":    week_total.get("clicked_pct"),
            "bounce_rate":   week_total.get("bounced_pct"),
            "delivery_rate": week_total.get("delivered_pct"),
        }
        if not em.empty and "week_start" in em.columns:
            mask = em["week_start"].astype(str) == row["week_start"]
            if mask.any():
                for k, v in row.items():
                    if k in em.columns:
                        em.loc[mask, k] = v
            else:
                em = pd.concat([em, pd.DataFrame([row])],
                                ignore_index=True)
        else:
            em = pd.DataFrame([row])
        _atomic_write(em, em_path)
        written["emails"] = 1

    # 5. mql_engaged.csv - openers + clickers
    mql_path = DATA_DIR / "mql_engaged.csv"
    if openers or clickers:
        mql = pd.read_csv(mql_path) if mql_path.exists() else pd.DataFrame(
            columns=["first_name", "last_name", "institution",
                     "job_title", "persona", "opens", "clicks",
                     "total_engagement", "email", "phone", "office",
                     "linkedin", "sales_touched", "worktribe",
                     "date", "notes"])
        combined = {}
        for o in openers:
            e = o["email"].strip().lower()
            combined.setdefault(e, {"email": o["email"],
                                      "company": o["company"],
                                      "campaign": o["campaign"],
                                      "opens": 0, "clicks": 0})
            combined[e]["opens"] += int(o.get("opens") or 0)
        for c in clickers:
            e = c["email"].strip().lower()
            combined.setdefault(e, {"email": c["email"],
                                      "company": c["company"],
                                      "campaign": c["campaign"],
                                      "opens": 0, "clicks": 0})
            combined[e]["clicks"] += int(c.get("clicks") or 0)

        for e_lower, rec in combined.items():
            local = rec["email"].split("@", 1)[0]
            parts = re.split(r"[\._-]", local)
            fn = parts[0].capitalize() if parts else ""
            ln = parts[1].capitalize() if len(parts) > 1 else ""
            row = {
                "first_name": fn, "last_name": ln,
                "institution": rec["company"], "job_title": "",
                "persona": "",
                "opens": rec["opens"], "clicks": rec["clicks"],
                "total_engagement": rec["opens"] + rec["clicks"],
                "email": rec["email"], "phone": "", "office": "",
                "linkedin": "", "sales_touched": "", "worktribe": "",
                "date": week_end.strftime("%Y-%m-%d") if week_end else "",
                "notes": f"campaign: {rec['campaign']}",
            }
            if not mql.empty and "email" in mql.columns:
                mask = mql["email"].astype(str).str.lower() == e_lower
                if mask.any():
                    for k in ("opens", "clicks"):
                        prev = pd.to_numeric(mql.loc[mask, k],
                                               errors="coerce").fillna(0)
                        mql.loc[mask, k] = prev + row[k]
                    mql.loc[mask, "total_engagement"] = (
                        pd.to_numeric(mql.loc[mask, "opens"],
                                       errors="coerce").fillna(0)
                        + pd.to_numeric(mql.loc[mask, "clicks"],
                                          errors="coerce").fillna(0))
                    mql.loc[mask, "date"] = row["date"]
                    if row["notes"]:
                        mql.loc[mask, "notes"] = row["notes"]
                    written["mql_updated"] += 1
                    continue
            mql = pd.concat([mql, pd.DataFrame([row])],
                              ignore_index=True)
            written["mql_added"] += 1
        _atomic_write(mql, mql_path)

    # 6. campaigns.csv - subject/body library
    cmp_path = DATA_DIR / "campaigns.csv"
    if campaigns:
        cmp = pd.read_csv(cmp_path) if cmp_path.exists() else pd.DataFrame(
            columns=["campaign_id", "campaign_name", "objective",
                     "persona_raw", "stage", "subject", "body",
                     "full_text", "char_count", "word_count",
                     "has_subject"])
        next_cid = (int(cmp["campaign_id"].max()) + 1
                     if not cmp.empty and cmp["campaign_id"].notna().any()
                     else 1)
        for c in campaigns:
            if not c.get("subject") and not c.get("body"):
                continue
            if not cmp.empty:
                mask = ((cmp["campaign_name"].astype(str) == c["name"])
                          & (cmp["subject"].astype(str).fillna("")
                              == (c.get("subject") or "")))
                if mask.any():
                    continue
            body = c.get("body") or ""
            cmp = pd.concat([cmp, pd.DataFrame([{
                "campaign_id":   next_cid,
                "campaign_name": c["name"],
                "objective":     "",
                "persona_raw":   "",
                "stage":         "Base",
                "subject":       c.get("subject") or "",
                "body":          body,
                "full_text":     (c.get("subject") or "") + "\n" + body,
                "char_count":    len(body),
                "word_count":    len(body.split()),
                "has_subject":   bool(c.get("subject")),
            }])], ignore_index=True)
            next_cid += 1
            written["campaigns"] += 1
        _atomic_write(cmp, cmp_path)

    # 7. upload_log.csv
    log_path = DATA_DIR / "upload_log.csv"
    log_row = {
        "timestamp":             _dt.datetime.now().strftime(
                                     "%Y-%m-%d %H:%M:%S"),
        "filename":              src.name,
        "backup_path":           backup.name,
        "week_ending":           (week_end.strftime("%Y-%m-%d")
                                     if week_end else ""),
        "campaigns_added":       written["campaign_batches"],
        "campaigns_overwritten": written["campaign_batches_overwritten"],
        "campaigns_skipped":     written["campaign_batches_skipped"],
        "emails_row_added":      written["emails"],
        "mql_added":             written["mql_added"],
        "mql_updated":           written["mql_updated"],
        "copy_added":            written["campaigns"],
        "skip_dupes":            skip_dupes,
    }
    if log_path.exists():
        log = pd.read_csv(log_path)
        log = pd.concat([log, pd.DataFrame([log_row])],
                          ignore_index=True)
    else:
        log = pd.DataFrame([log_row])
    _atomic_write(log, log_path)

    return {"written": written,
             "backup": str(backup),
             "week_ending": str(week_end) if week_end else None}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--skip-dupes", action="store_true")
    args = ap.parse_args()
    r = ingest(args.xlsx, skip_dupes=args.skip_dupes)
    print("INGESTED")
    for k, v in r["written"].items():
        print(f"  {k}: {v}")
    print(f"  backup: {r['backup']}")
    print(f"  week_ending: {r['week_ending']}")
