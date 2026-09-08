"""
Data - Weekly ESP workbook upload.

Drop the week's Excel campaign report in. The parser reads it, shows
a preview, and on confirm appends new rows to campaign_batches.csv,
emails.csv, mql_engaged.csv and campaigns.csv. Every existing page
picks up the new data on next rerun.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from shared import (core_question, inject_css, kpi_tile, so_what,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)

# Import parser from the etl package
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from etl.weekly_upload_parser import parse_workbook  # noqa: E402


inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Data</div>',
             unsafe_allow_html=True)
st.markdown('<h1>Weekly upload</h1>', unsafe_allow_html=True)
core_question("Drop the week's ESP workbook and refresh the whole "
                "Performance Matrix in one step.")
st.caption("Accepts the standard 3-sheet ESP workbook (Summary + "
            "Opened 3+ Times + Clicked 1+ Times). Preview is always "
            "shown before anything is written.")


DATA_DIR = Path(ROOT_DIR) / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================================
# 1. File uploader
# ==========================================================================
uploaded = st.file_uploader("Upload the week's Excel file",
                              type=["xlsx"], key="weekly_upload")

if uploaded is None:
    st.info("Waiting for a workbook. Expected shape:\n\n"
             "- **Summary** sheet: campaign name, sent, delivered (%), "
             "bounced (%), opened (%), clicks (%), date + campaign "
             "copy at the bottom.\n"
             "- **Opened 3+ Times** sheet: email, company, campaign, "
             "total opens.\n"
             "- **Clicked 1+ Times** sheet: email, company, campaign, "
             "total clicks.")
    st.stop()


# ==========================================================================
# 2. Backup the raw upload straight away (audit trail)
# ==========================================================================
timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", uploaded.name)
backup_path = UPLOADS_DIR / f"{timestamp}_{safe_name}"
with open(backup_path, "wb") as f:
    f.write(uploaded.getbuffer())
st.caption(f"Raw file backed up to `data/uploads/{backup_path.name}`")


# ==========================================================================
# 3. Parse
# ==========================================================================
try:
    parsed = parse_workbook(backup_path)
except Exception as e:
    st.error(f"Parse failed: {e}. No CSVs were touched.")
    st.stop()

campaigns = parsed["campaigns"]
week_total = parsed["week_total"] or {}
openers = parsed["openers"]
clickers = parsed["clickers"]
week_ending = parsed["week_ending"]

for w in parsed["warnings"]:
    st.warning(w)


# ==========================================================================
# 4. Preview panel
# ==========================================================================
st.markdown('<h2>What the parser found</h2>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_tile("Week ending",
              week_ending.strftime("%d %b %Y") if week_ending else "-",
              sub="derived from the Date column")
with c2:
    kpi_tile("Campaigns", f"{len(campaigns)}",
              sub="rows found in Summary", color=ACCENT)
with c3:
    kpi_tile("Openers (3+)", f"{len(openers)}",
              sub="unique people this week", color=ACCENT)
with c4:
    kpi_tile("Clickers (1+)", f"{len(clickers)}",
              sub="unique people this week", color=ACCENT)


# ---- Duplicate detection against campaign_batches.csv
existing_cb = pd.DataFrame()
if (DATA_DIR / "campaign_batches.csv").exists():
    existing_cb = pd.read_csv(DATA_DIR / "campaign_batches.csv")

def _dup_key(name: str, dt) -> str:
    return f"{str(name).strip().lower()}|{dt}"

existing_keys = set()
if not existing_cb.empty:
    for _, r in existing_cb.iterrows():
        existing_keys.add(_dup_key(r.get("batch_name", ""),
                                     r.get("sent_date", "")))


# ---- Campaign rows preview
st.markdown('<h3>Campaign funnel rows</h3>', unsafe_allow_html=True)
if not campaigns:
    st.info("No campaign rows detected.")
else:
    cdf = pd.DataFrame([{
        "Campaign":  c["name"],
        "Date":      c["sent_date"].strftime("%Y-%m-%d")
                       if c.get("sent_date") else "-",
        "Sent":      c["sent"],
        "Delivered": c["delivered"],
        "Bounced":   c["bounced"],
        "Opened":    c["opened"],
        "Clicked":   c["clicked"],
        "Open %":    round((c["opened_pct"] or 0) * 100, 1),
        "Click %":   round((c["clicked_pct"] or 0) * 100, 1),
        "Subject":   (c.get("subject") or "")[:60],
        "Duplicate?": ("YES" if _dup_key(c["name"], c.get("sent_date"))
                        in existing_keys else "new"),
    } for c in campaigns])
    st.dataframe(cdf, use_container_width=True, hide_index=True,
                  column_config={
                      "Campaign":  st.column_config.TextColumn(width="large"),
                      "Subject":   st.column_config.TextColumn(width="medium"),
                      "Duplicate?": st.column_config.TextColumn(),
                  })

    dup_count = sum(1 for c in campaigns
                    if _dup_key(c["name"], c.get("sent_date"))
                    in existing_keys)
    if dup_count:
        st.markdown(
            f'<div style="background:#FBF3E5;border-left:4px solid '
            f'{GOLD};padding:.6rem 1rem;border-radius:4px;'
            f'font-size:.9rem;margin:.5rem 0">'
            f'<strong>{dup_count}</strong> of {len(campaigns)} '
            f'campaign(s) already exist in campaign_batches.csv. '
            f'By default they will be <strong>overwritten</strong> '
            f'with the new numbers. Tick the box below to skip '
            f'instead.</div>', unsafe_allow_html=True)


# ---- Week total preview
if week_total:
    st.markdown('<h3>Weekly total</h3>', unsafe_allow_html=True)
    wt_df = pd.DataFrame([{
        "Sent":      week_total.get("sent"),
        "Delivered": week_total.get("delivered"),
        "Bounced":   week_total.get("bounced"),
        "Opened":    week_total.get("opened"),
        "Clicked":   week_total.get("clicked"),
        "Open %":    round((week_total.get("opened_pct") or 0) * 100, 1),
        "Click %":   round((week_total.get("clicked_pct") or 0) * 100, 1),
        "Bounce %":  round((week_total.get("bounced_pct") or 0) * 100, 1),
    }])
    st.dataframe(wt_df, use_container_width=True, hide_index=True)


# ---- Openers / clickers preview
oc1, oc2 = st.columns(2)
with oc1:
    st.markdown('<h3>Openers 3+ (top 5)</h3>', unsafe_allow_html=True)
    if openers:
        odf = pd.DataFrame(openers[:5])
        st.dataframe(odf, use_container_width=True, hide_index=True)
    else:
        st.caption("None detected.")
with oc2:
    st.markdown('<h3>Clickers 1+ (top 5)</h3>', unsafe_allow_html=True)
    if clickers:
        cdf2 = pd.DataFrame(clickers[:5])
        st.dataframe(cdf2, use_container_width=True, hide_index=True)
    else:
        st.caption("None detected.")


# ==========================================================================
# 5. Confirm & write
# ==========================================================================
st.markdown('<h2>Confirm &amp; append</h2>', unsafe_allow_html=True)

skip_dupes = st.checkbox("Skip duplicate campaigns (default: overwrite)",
                           key="skip_dupes", value=False)

if not st.button("Append to Performance Matrix", type="primary",
                    key="do_append"):
    st.stop()


# ---- Write step ----
written = {"campaign_batches": 0, "emails": 0,
             "mql_engaged": 0, "campaigns": 0,
             "campaign_batches_overwritten": 0,
             "campaign_batches_skipped": 0}


def _atomic_write(df: pd.DataFrame, path: Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


# --- 5a. campaign_batches.csv ---
cb_path = DATA_DIR / "campaign_batches.csv"
if cb_path.exists():
    cb = pd.read_csv(cb_path)
else:
    cb = pd.DataFrame(columns=["batch_id", "batch_name", "stage",
                                 "sent_date", "subject", "body",
                                 "sent", "delivered", "opened",
                                 "clicked", "replied"])

next_batch_id = (int(cb["batch_id"].max()) + 1
                   if not cb.empty and cb["batch_id"].notna().any() else 1)

new_rows = []
for c in campaigns:
    key = _dup_key(c["name"], c.get("sent_date"))
    is_dup = key in existing_keys
    if is_dup and skip_dupes:
        written["campaign_batches_skipped"] += 1
        continue
    row = {
        "batch_id":  None,
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
    }
    if is_dup:
        # Drop the old row(s) for this key
        mask = cb.apply(
            lambda r: _dup_key(r.get("batch_name", ""),
                                 r.get("sent_date", "")) == key,
            axis=1)
        cb = cb[~mask]
        written["campaign_batches_overwritten"] += 1
    row["batch_id"] = next_batch_id
    next_batch_id += 1
    new_rows.append(row)

if new_rows:
    cb = pd.concat([cb, pd.DataFrame(new_rows)], ignore_index=True)
    _atomic_write(cb, cb_path)
    written["campaign_batches"] = len(new_rows)


# --- 5b. emails.csv (weekly rollup) ---
em_path = DATA_DIR / "emails.csv"
if week_total and week_ending:
    em = pd.read_csv(em_path) if em_path.exists() else pd.DataFrame()
    # Try to align to an existing week_start match
    week_start = (week_ending -
                    _dt.timedelta(days=week_ending.weekday()))
    week_label = f"Week of {week_start.strftime('%d %b %Y')}"
    row = {
        "week_label":     week_label,
        "week_start":     week_start.strftime("%Y-%m-%d"),
        "emails_sent":    week_total.get("sent"),
        "delivered":      week_total.get("delivered"),
        "bounced":        week_total.get("bounced"),
        "opened":         week_total.get("opened"),
        "clicks":         week_total.get("clicked"),
        "open_rate":      week_total.get("opened_pct"),
        "click_rate":     week_total.get("clicked_pct"),
        "bounce_rate":    week_total.get("bounced_pct"),
        "delivery_rate":  week_total.get("delivered_pct"),
    }
    if not em.empty and "week_start" in em.columns:
        mask = em["week_start"].astype(str) == row["week_start"]
        if mask.any():
            for k, v in row.items():
                if k in em.columns:
                    em.loc[mask, k] = v
        else:
            em = pd.concat([em, pd.DataFrame([row])], ignore_index=True)
    else:
        em = pd.DataFrame([row])
    _atomic_write(em, em_path)
    written["emails"] = 1


# --- 5c. mql_engaged.csv (openers + clickers as engagement rows) ---
mql_path = DATA_DIR / "mql_engaged.csv"
if openers or clickers:
    if mql_path.exists():
        mql = pd.read_csv(mql_path)
    else:
        mql = pd.DataFrame(columns=["first_name", "last_name",
                                      "institution", "job_title",
                                      "persona", "opens", "clicks",
                                      "total_engagement", "email",
                                      "phone", "office", "linkedin",
                                      "sales_touched", "worktribe",
                                      "date", "notes"])

    # Merge openers + clickers by email
    combined: dict = {}
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

    added = 0
    updated = 0
    for e_lower, rec in combined.items():
        # Split names from the email if we can (a.bautz@surrey -> A Bautz)
        local = rec["email"].split("@", 1)[0]
        parts = re.split(r"[\._-]", local)
        first_name = parts[0].capitalize() if parts else ""
        last_name  = parts[1].capitalize() if len(parts) > 1 else ""

        row = {
            "first_name":       first_name,
            "last_name":        last_name,
            "institution":      rec["company"],
            "job_title":        "",
            "persona":          "",
            "opens":            rec["opens"],
            "clicks":           rec["clicks"],
            "total_engagement": rec["opens"] + rec["clicks"],
            "email":            rec["email"],
            "phone":            "",
            "office":           "",
            "linkedin":         "",
            "sales_touched":    "",
            "worktribe":        "",
            "date":             (week_ending.strftime("%Y-%m-%d")
                                    if week_ending else ""),
            "notes":            f"campaign: {rec['campaign']}",
        }
        if not mql.empty and "email" in mql.columns:
            mask = mql["email"].astype(str).str.lower() == e_lower
            if mask.any():
                # Add to existing engagement counts
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
                updated += 1
                continue
        mql = pd.concat([mql, pd.DataFrame([row])], ignore_index=True)
        added += 1

    _atomic_write(mql, mql_path)
    written["mql_engaged"] = added
    written["mql_engaged_updated"] = updated


# --- 5d. campaigns.csv (subject + body library) ---
cmp_path = DATA_DIR / "campaigns.csv"
if campaigns:
    if cmp_path.exists():
        cmp = pd.read_csv(cmp_path)
    else:
        cmp = pd.DataFrame(columns=["campaign_id", "campaign_name",
                                      "objective", "persona_raw",
                                      "stage", "subject", "body",
                                      "full_text", "char_count",
                                      "word_count", "has_subject"])
    next_id = (int(cmp["campaign_id"].max()) + 1
                if not cmp.empty and cmp["campaign_id"].notna().any()
                else 1)
    for c in campaigns:
        if not c.get("subject") and not c.get("body"):
            continue
        # Skip if the same campaign_name+subject already exists
        if not cmp.empty:
            mask = ((cmp["campaign_name"].astype(str)
                       == c["name"])
                     & (cmp["subject"].astype(str).fillna("")
                         == (c.get("subject") or "")))
            if mask.any():
                continue
        body = c.get("body") or ""
        row = {
            "campaign_id":   next_id,
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
        }
        cmp = pd.concat([cmp, pd.DataFrame([row])], ignore_index=True)
        next_id += 1
        written["campaigns"] += 1
    _atomic_write(cmp, cmp_path)


# --- 5e. upload_log.csv ---
log_path = DATA_DIR / "upload_log.csv"
log_row = {
    "timestamp":         _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "filename":          uploaded.name,
    "backup_path":       str(backup_path.name),
    "week_ending":       (week_ending.strftime("%Y-%m-%d")
                             if week_ending else ""),
    "campaigns_added":   written["campaign_batches"],
    "campaigns_overwritten": written["campaign_batches_overwritten"],
    "campaigns_skipped": written["campaign_batches_skipped"],
    "emails_row_added":  written["emails"],
    "mql_added":         written.get("mql_engaged", 0),
    "mql_updated":       written.get("mql_engaged_updated", 0),
    "copy_added":        written["campaigns"],
    "skip_dupes":        skip_dupes,
}
if log_path.exists():
    log = pd.read_csv(log_path)
    log = pd.concat([log, pd.DataFrame([log_row])], ignore_index=True)
else:
    log = pd.DataFrame([log_row])
_atomic_write(log, log_path)


# ==========================================================================
# 6. Post-write summary
# ==========================================================================
# Invalidate Streamlit caches so pages re-read the new CSVs
st.cache_data.clear()

st.markdown('<h2>Done</h2>', unsafe_allow_html=True)
so_what(
    f"Appended <strong>{written['campaign_batches']}</strong> "
    f"campaign row(s), <strong>{written['emails']}</strong> "
    f"weekly rollup row, <strong>{written.get('mql_engaged', 0)}"
    f"</strong> new engaged contact(s) "
    f"(<strong>{written.get('mql_engaged_updated', 0)}</strong> "
    f"updated), <strong>{written['campaigns']}</strong> new subject/"
    f"body pair(s).",
    tone="good")

if written["campaign_batches_overwritten"]:
    so_what(
        f"Overwrote <strong>{written['campaign_batches_overwritten']}"
        f"</strong> existing campaign row(s) with the new numbers.",
        tone="info")
if written["campaign_batches_skipped"]:
    so_what(
        f"Skipped <strong>{written['campaign_batches_skipped']}"
        f"</strong> duplicate campaign row(s) as requested.",
        tone="info")

st.caption("Pages that now reflect the new data on next click: "
            "**This week's numbers**, **Rolling marketing report**, "
            "**Content x Persona impact**, **Monthly report**, "
            "**Warm leads**.")


# ==========================================================================
# 7. Upload log (audit trail)
# ==========================================================================
if log_path.exists():
    st.markdown('<h2>Upload history</h2>', unsafe_allow_html=True)
    st.caption("Every upload logged. Raw files sit in "
                "`data/uploads/`.")
    hist = pd.read_csv(log_path).sort_values("timestamp",
                                                ascending=False).head(20)
    st.dataframe(hist, use_container_width=True, hide_index=True)
