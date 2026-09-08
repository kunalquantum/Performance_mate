"""
Data - Universal upload.

Drop any of the recognised workbooks. The page detects the file type
and routes to the right ingestion path:

    * weekly_esp -> the ESP campaign report
      (campaign_batches.csv, emails.csv, mql_engaged.csv, campaigns.csv)
    * crm_sync   -> a Zoho CRM sync dump
      (data/crm_sync/*.csv + refreshes in_zoho_crm flag on contacts.csv)

Preview is always shown before any CSV is written.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from shared import (core_question, inject_css, kpi_tile, so_what,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from etl.file_detect import detect                          # noqa: E402
from etl.weekly_upload_parser import parse_workbook          # noqa: E402
from etl.ingest_crm_sync import preview as crm_preview, \
    ingest as crm_ingest                                    # noqa: E402


inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Data</div>',
             unsafe_allow_html=True)
st.markdown('<h1>Weekly upload</h1>', unsafe_allow_html=True)
core_question("Drop any recognised workbook - the page detects the "
                "type and updates the Performance Matrix.")
st.caption("Two types supported today: the weekly ESP campaign "
            "report (Summary + Openers + Clickers) and the Zoho CRM "
            "sync dump (Accounts + Leads + Contacts + masterlist).")

DATA_DIR = Path(ROOT_DIR) / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================================
# 1. Uploader
# ==========================================================================
uploaded = st.file_uploader("Upload an Excel file",
                              type=["xlsx"], key="weekly_upload")
if uploaded is None:
    st.info("Waiting for a workbook. Two shapes recognised:\n\n"
             "**Weekly ESP report** - sheets: `Summary`, `Opened 3+ "
             "Times`, `Clicked 1+ Times`.\n\n"
             "**CRM sync dump** - sheets: `Accounts`, `Leads`, "
             "`Contacts`, `masterlist`.")
    st.stop()


# ==========================================================================
# 2. Backup the raw file for audit
# ==========================================================================
ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", uploaded.name)
backup_path = UPLOADS_DIR / f"{ts}_{safe_name}"
with open(backup_path, "wb") as f:
    f.write(uploaded.getbuffer())
st.caption(f"Raw file backed up to `data/uploads/{backup_path.name}`")


# ==========================================================================
# 3. Detect
# ==========================================================================
try:
    det = detect(backup_path)
except Exception as e:
    st.error(f"Could not open file: {e}")
    st.stop()

file_type = det["type"]

badge_color = {"weekly_esp": ACCENT, "crm_sync": "#7A6A9A",
                "unknown": WARN}[file_type]
badge_text = {"weekly_esp": "Weekly ESP report",
                "crm_sync":   "CRM sync dump",
                "unknown":    "Unknown format"}[file_type]

st.markdown(
    f'<div style="display:inline-flex;align-items:center;gap:.6rem;'
    f'padding:.4rem .8rem;background:{badge_color}22;color:{INK};'
    f'border-radius:6px;border-left:4px solid {badge_color};'
    f'font-size:.9rem;margin:.6rem 0 1rem">'
    f'<span style="font-weight:700">Detected: {badge_text}</span>'
    f'<span style="color:{MUTED};font-size:.8rem">'
    f'&mdash; {det["reason"]}</span></div>',
    unsafe_allow_html=True)

if file_type == "unknown":
    st.error("This file does not match either recognised shape. "
              "Sheets found: " + ", ".join(det["signals"]["sheets"]) +
              ". Nothing was ingested.")
    st.stop()


# ==========================================================================
# 4a. ROUTE - Weekly ESP report
# ==========================================================================
if file_type == "weekly_esp":
    try:
        parsed = parse_workbook(backup_path)
    except Exception as e:
        st.error(f"Parse failed: {e}. No CSVs were touched.")
        st.stop()

    campaigns  = parsed["campaigns"]
    week_total = parsed["week_total"] or {}
    openers    = parsed["openers"]
    clickers   = parsed["clickers"]
    week_end   = parsed["week_ending"]

    for w in parsed["warnings"]:
        st.warning(w)

    st.markdown('<h2>What the parser found</h2>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_tile("Week ending",
                  week_end.strftime("%d %b %Y") if week_end else "-",
                  sub="from the Date column")
    with c2:
        kpi_tile("Campaigns", f"{len(campaigns)}",
                  sub="rows found", color=ACCENT)
    with c3:
        kpi_tile("Openers (3+)", f"{len(openers)}",
                  sub="unique people", color=ACCENT)
    with c4:
        kpi_tile("Clickers (1+)", f"{len(clickers)}",
                  sub="unique people", color=ACCENT)

    # Duplicate check
    existing_cb = (pd.read_csv(DATA_DIR / "campaign_batches.csv")
                    if (DATA_DIR / "campaign_batches.csv").exists()
                    else pd.DataFrame())

    def _dup_key(name, dt) -> str:
        return f"{str(name).strip().lower()}|{dt}"

    existing_keys = set()
    if not existing_cb.empty:
        for _, r in existing_cb.iterrows():
            existing_keys.add(_dup_key(r.get("batch_name", ""),
                                         r.get("sent_date", "")))

    if campaigns:
        st.markdown('<h3>Campaign funnel rows</h3>',
                     unsafe_allow_html=True)
        cdf = pd.DataFrame([{
            "Campaign":  c["name"],
            "Date":      c["sent_date"].strftime("%Y-%m-%d")
                           if c.get("sent_date") else "-",
            "Sent":      c["sent"],
            "Delivered": c["delivered"],
            "Opened":    c["opened"],
            "Clicked":   c["clicked"],
            "Subject":   (c.get("subject") or "")[:60],
            "Duplicate?": ("YES" if _dup_key(c["name"],
                                              c.get("sent_date"))
                            in existing_keys else "new"),
        } for c in campaigns])
        st.dataframe(cdf, use_container_width=True, hide_index=True,
                      column_config={
                          "Campaign": st.column_config.TextColumn(
                              width="large"),
                          "Subject": st.column_config.TextColumn(
                              width="medium"),
                      })
        dup_count = sum(1 for c in campaigns
                        if _dup_key(c["name"], c.get("sent_date"))
                        in existing_keys)
        if dup_count:
            st.markdown(
                f'<div style="background:#FBF3E5;border-left:4px solid '
                f'{GOLD};padding:.6rem 1rem;border-radius:4px;'
                f'font-size:.9rem;margin:.5rem 0">'
                f'<strong>{dup_count}</strong> already exist. '
                f'By default they will be <strong>overwritten</strong>.'
                f'</div>', unsafe_allow_html=True)

    if week_total:
        st.markdown('<h3>Weekly total</h3>', unsafe_allow_html=True)
        wt_df = pd.DataFrame([{
            "Sent":      week_total.get("sent"),
            "Delivered": week_total.get("delivered"),
            "Bounced":   week_total.get("bounced"),
            "Opened":    week_total.get("opened"),
            "Clicked":   week_total.get("clicked"),
        }])
        st.dataframe(wt_df, use_container_width=True, hide_index=True)

    oc1, oc2 = st.columns(2)
    with oc1:
        st.markdown('<h3>Openers 3+ (top 5)</h3>',
                     unsafe_allow_html=True)
        if openers:
            st.dataframe(pd.DataFrame(openers[:5]),
                          use_container_width=True, hide_index=True)
        else:
            st.caption("None detected.")
    with oc2:
        st.markdown('<h3>Clickers 1+ (top 5)</h3>',
                     unsafe_allow_html=True)
        if clickers:
            st.dataframe(pd.DataFrame(clickers[:5]),
                          use_container_width=True, hide_index=True)
        else:
            st.caption("None detected.")

    st.markdown('<h2>Confirm &amp; append</h2>', unsafe_allow_html=True)
    skip_dupes = st.checkbox(
        "Skip duplicate campaigns (default: overwrite)",
        key="skip_dupes", value=False)
    if not st.button("Append to Performance Matrix",
                        type="primary", key="do_append_esp"):
        st.stop()

    # Reuse the shared ESP ingest logic
    from etl.ingest_weekly import ingest as esp_ingest
    result = esp_ingest(str(backup_path), skip_dupes=skip_dupes)
    w = result["written"]

    st.cache_data.clear()
    st.markdown('<h2>Done</h2>', unsafe_allow_html=True)
    so_what(
        f"Appended <strong>{w['campaign_batches']}</strong> campaign "
        f"row(s), <strong>{w['emails']}</strong> weekly rollup, "
        f"<strong>{w['mql_added']}</strong> new engaged contact(s) "
        f"(<strong>{w['mql_updated']}</strong> updated), "
        f"<strong>{w['campaigns']}</strong> new subject/body pair(s).",
        tone="good")
    if w["campaign_batches_overwritten"]:
        so_what(
            f"Overwrote <strong>{w['campaign_batches_overwritten']}"
            f"</strong> existing campaign row(s).", tone="info")
    st.caption("Pages that now reflect the new data on next click: "
                "**This week's numbers · Rolling report · Content x "
                "Persona impact · Monthly report · Warm leads**.")


# ==========================================================================
# 4b. ROUTE - CRM sync dump
# ==========================================================================
elif file_type == "crm_sync":
    # Preview (row counts per sheet, no writes yet)
    try:
        counts = crm_preview(backup_path)
    except Exception as e:
        st.error(f"Preview failed: {e}. No CSVs were touched.")
        st.stop()

    st.markdown('<h2>What the CRM dump contains</h2>',
                 unsafe_allow_html=True)
    known = ["Accounts", "Leads", "Contacts", "masterlist"]
    tiles = st.columns(max(len(known), 4))
    for tile, name in zip(tiles, known):
        with tile:
            n = counts.get(name, counts.get(name.lower(), 0))
            kpi_tile(name, f"{n:,}", sub="rows in the sheet",
                      color=ACCENT if n else MUTED)

    other = [n for n in counts if n.lower() not in
             {"accounts", "leads", "contacts", "masterlist"}]
    if other:
        st.caption("Other sheets in the workbook (not ingested): "
                    + ", ".join(other))

    # Warn about overwrite behaviour
    st.markdown(
        f'<div style="background:#FBF3E5;border-left:4px solid '
        f'{GOLD};padding:.6rem 1rem;border-radius:4px;'
        f'font-size:.9rem;margin:.6rem 0">'
        f'On append: each recognised sheet will <strong>replace</strong> '
        f'its corresponding CSV under <code>data/crm_sync/</code>. '
        f'The top-level <code>contacts.csv</code> will have its '
        f'<code>in_zoho_crm</code> flag refreshed from the new export '
        f'(non-destructive).</div>', unsafe_allow_html=True)

    st.markdown('<h2>Confirm &amp; append</h2>', unsafe_allow_html=True)
    if not st.button("Refresh CRM sync data", type="primary",
                        key="do_append_crm"):
        st.stop()

    try:
        result = crm_ingest(backup_path)
    except Exception as e:
        st.error(f"Ingest failed: {e}")
        st.stop()

    st.cache_data.clear()
    st.markdown('<h2>Done</h2>', unsafe_allow_html=True)
    w = result["written"]
    so_what(
        f"Refreshed CRM sync data: "
        f"<strong>{w.get('accounts', 0):,}</strong> accounts, "
        f"<strong>{w.get('leads', 0):,}</strong> leads, "
        f"<strong>{w.get('contacts', 0):,}</strong> contacts, "
        f"<strong>{w.get('masterlist', 0):,}</strong> masterlist rows. "
        f"Updated <strong>{result['flag_updated_on_contacts']}</strong> "
        f"in_zoho_crm flag(s) on the top-level contacts table.",
        tone="good")
    st.caption("Files written under `data/crm_sync/` "
                "(crm_accounts · crm_leads · crm_contacts · "
                "crm_masterlist). Downstream Persona pages will read "
                "these on next click.")


# ==========================================================================
# 5. Upload history (always shown)
# ==========================================================================
log_path = DATA_DIR / "upload_log.csv"
if log_path.exists():
    st.markdown('<h2>Upload history</h2>', unsafe_allow_html=True)
    hist = pd.read_csv(log_path).sort_values(
        "timestamp", ascending=False).head(20)
    # Keep only the most useful columns
    keep = [c for c in ["timestamp", "filename", "file_type",
                          "week_ending", "campaigns_added",
                          "campaigns_overwritten", "mql_added",
                          "mql_updated", "copy_added",
                          "accounts", "leads", "contacts_rows",
                          "masterlist", "in_zoho_crm_flag_changes"]
             if c in hist.columns]
    st.dataframe(hist[keep], use_container_width=True, hide_index=True)
