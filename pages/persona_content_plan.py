"""
Persona - Content plan (spec 9 + 10 + 11).

Auto-detects which personas are being under-served (from Monthly
report activity), then proposes a 12-week rotating content plan
weighted toward the gaps.

Topic library is persona-specific:
    IT-Systems (from Ian's list): Integrations, Data flows, System
        architecture, Security, Compatibility, Reporting & data access,
        Implementation & support
    Finance: Cost recovery, TRAC, Audit trail, Reconciliation,
        Compliance, Budget forecasting, Value for money
    Research: (Ian said keep going but rotate) Grant admin burden,
        Funding opportunity match, Pre-award workflow, Post-award
        reporting, Impact narrative

Output can be downloaded as CSV and sent to Ian for approval.
"""
import datetime as _dt
import pandas as pd
import streamlit as st

from shared import (core_question, inject_css, render_status_key,
                     kpi_tile, so_what, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Content plan</h1>', unsafe_allow_html=True)
core_question("What should we publish over the next two-to-three "
                "months, and how do we make sure Finance and IT stop "
                "being neglected?")
st.caption("Auto-proposes a 12-week rotating plan. Skews toward the "
            "under-served personas (Finance and IT are Ian&apos;s "
            "priority). Every slot has a topic, format, angle and "
            "CTA. Download the CSV to send to Ian.")
render_status_key()

with st.expander("How the plan is built", expanded=False):
    st.markdown("""
1. Read the last month of persona email activity from the Monthly
   report page.
2. Any persona with fewer than 2 sends is flagged as under-served.
3. The 12-week plan is a rotation weighted 2:1:1 toward under-served
   personas vs already-served ones (with a cap of no more than 3
   consecutive slots for any persona).
4. Each slot picks the next unused topic from the persona&apos;s
   topic library, with a format that rotates through email &rarr;
   LinkedIn post &rarr; whitepaper &rarr; article.
5. Edit the table below to change any slot. Save to overwrite
   `data/content_plan.csv`. Download to hand to Ian.

**Topic libraries used** (drawn from Ian&apos;s spec):
- **IT-Systems**: Integrations, Data flows, System architecture,
  Security, Compatibility with existing systems, Reporting and data
  access, Implementation and support.
- **Finance**: Cost recovery, TRAC, Audit trail, Reconciliation,
  Compliance, Budget forecasting, Value for money.
- **Research**: Grant admin burden, Funding opportunity matching,
  Pre-award workflow, Post-award reporting, Impact narrative.
""")


# ==========================================================================
# 1. Detect under-served personas
# ==========================================================================
activity = load_csv("persona_email_activity.csv")

def _sent_last_month(persona):
    """Return the sent count for the most recent month, or 0."""
    if activity.empty:
        return 0
    months = sorted(activity["month"].dropna().astype(str).unique(),
                     reverse=True)
    if not months:
        return 0
    latest = activity[activity["month"].astype(str) == months[0]]
    row = latest[latest["persona"] == persona]
    if row.empty:
        return 0
    return int(pd.to_numeric(row.iloc[0].get("emails_sent", 0),
                               errors="coerce") or 0)


PERSONAS = ["Research", "Finance", "IT-Systems"]
TARGET_MIN = 2

sent_by = {p: _sent_last_month(p) for p in PERSONAS}
under_served = [p for p, n in sent_by.items() if n < TARGET_MIN]
zero_touch = [p for p, n in sent_by.items() if n == 0]

t1, t2, t3, t4 = st.columns(4)
with t1:
    kpi_tile("Personas tracked", f"{len(PERSONAS)}",
              tooltip="Research, Finance, IT-Systems.")
with t2:
    kpi_tile("Zero-touch personas",
              f"{len(zero_touch)}",
              sub=", ".join(zero_touch) if zero_touch else "-",
              color=WARN if zero_touch else ACCENT,
              tooltip="Personas that got no emails last month.")
with t3:
    kpi_tile("Under-served",
              f"{len(under_served)}",
              sub="below 2/month target",
              color=GOLD if under_served else ACCENT)
with t4:
    kpi_tile("Plan length", "12 weeks",
              sub="editable below")


# ==========================================================================
# 2. Topic library (from Ian's spec + reasonable fill-in for Finance
#    and Research)
# ==========================================================================
TOPICS = {
    "IT-Systems": [
        ("Integrations with ERP",
          "How GrantsNow slots into Oracle / Unit4 without a 12-month "
          "integration project."),
        ("Data flows between systems",
          "Where research, finance and HR data actually connect - and "
          "where they don't."),
        ("System architecture",
          "AI-driven, cloud-based, and what that means for the IT team "
          "who has to support it."),
        ("Security posture",
          "How research data is protected inside GrantsNow (encryption, "
          "SSO, access controls)."),
        ("Compatibility with existing systems",
          "Sitting alongside your current RMS / CRIS without ripping "
          "anything out."),
        ("Reporting and data access",
          "Self-configurable dashboards vs waiting on IT to build a "
          "report."),
        ("Implementation and support",
          "What a rollout actually looks like, week by week, and what "
          "IT owns vs what we own."),
    ],
    "Finance": [
        ("Cost recovery on grants",
          "Where the money leaks in the current pre-award process."),
        ("TRAC reporting",
          "How GrantsNow makes the TRAC return less of a spreadsheet "
          "exercise."),
        ("Audit trail",
          "A single record of every proposal change, approval and "
          "conversation."),
        ("Reconciliation",
          "Grants data reconciled to finance system numbers without "
          "manual exports."),
        ("Compliance",
          "Reducing audit and funder-return risk with automated "
          "checks."),
        ("Budget forecasting",
          "Accurate research income forecasts without a copy of the "
          "grants data."),
        ("Value for money",
          "35% lower grants management costs at institutions using "
          "GrantsNow."),
    ],
    "Research": [
        ("Grant admin burden",
          "Freeing PIs and Research Office from repetitive admin."),
        ("Funding opportunity matching",
          "25% more relevant opportunities through the AI Funder "
          "Scanner."),
        ("Pre-award workflow",
          "Single source of truth from bid to submission."),
        ("Post-award reporting",
          "Every funder report generated from live grant data."),
        ("Impact narrative",
          "Capturing outputs and impact for REF / KEF returns."),
    ],
}

FORMATS = ["Email", "LinkedIn post", "Whitepaper", "Article"]

# CTA suggestions per format
_CTA = {
    "Email":         "Read the whitepaper / Book a short call",
    "LinkedIn post": "See how universities are using GrantsNow",
    "Whitepaper":    "Download the whitepaper",
    "Article":       "Read the full article",
}


# ==========================================================================
# 3. Build the rotation (weighted 2:1:1 toward under-served)
# ==========================================================================
def _build_rotation(under, all_p, weeks=12):
    """Create a persona sequence of length `weeks`, weighting under-
    served personas twice as heavily. Cap 3 consecutive of the same."""
    # Base weights
    weights = {p: 2 if p in under else 1 for p in all_p}
    total_weight = sum(weights.values())
    # How many slots per persona
    counts = {p: max(1, round(weeks * weights[p] / total_weight))
                for p in all_p}
    # Trim / pad to exact `weeks`
    while sum(counts.values()) > weeks:
        # Reduce the persona with the most slots (that is not zero-
        # touch, to protect the priority)
        target = max(counts, key=lambda p: (counts[p], p not in under))
        if counts[target] > 1:
            counts[target] -= 1
        else:
            break
    while sum(counts.values()) < weeks:
        target = min(counts, key=lambda p: (counts[p], p in under))
        counts[target] += 1
    # Interleave to avoid 3+ in a row
    pool = []
    for p, n in counts.items():
        pool.extend([p] * n)
    # Simple round-robin: alternate under-served with rest
    priority = [p for p in pool if p in under]
    others   = [p for p in pool if p not in under]
    seq = []
    i, j = 0, 0
    while i < len(priority) or j < len(others):
        # 2 under-served, 1 other
        for _ in range(2):
            if i < len(priority):
                seq.append(priority[i]); i += 1
        if j < len(others):
            seq.append(others[j]); j += 1
    # Ensure no run of 4+
    for k in range(3, len(seq)):
        if seq[k] == seq[k-1] == seq[k-2] == seq[k-3]:
            # Swap with the next different persona
            for m in range(k+1, len(seq)):
                if seq[m] != seq[k]:
                    seq[k], seq[m] = seq[m], seq[k]
                    break
    return seq[:weeks]


sequence = _build_rotation(under_served, PERSONAS, weeks=12)

# Build the plan rows
_topic_cursor = {p: 0 for p in PERSONAS}
today = _dt.date.today()
plan_rows = []
for i, persona in enumerate(sequence):
    week_start = today + _dt.timedelta(days=7 * i)
    topic_lib = TOPICS[persona]
    topic, angle = topic_lib[_topic_cursor[persona] % len(topic_lib)]
    _topic_cursor[persona] += 1
    fmt = FORMATS[i % len(FORMATS)]
    plan_rows.append({
        "Week starting": week_start.strftime("%d %b %Y"),
        "Persona":       persona,
        "Format":        fmt,
        "Topic":         topic,
        "Angle":         angle,
        "CTA":           _CTA[fmt],
    })

plan_df = pd.DataFrame(plan_rows)


# ==========================================================================
# 4. Show / edit the plan
# ==========================================================================
st.markdown('<h2>Proposed 12-week plan</h2>', unsafe_allow_html=True)
if zero_touch:
    so_what(
        f"Weighting the plan toward <strong>{', '.join(zero_touch)}"
        f"</strong> because those personas got zero targeted email "
        f"last month. Ian&apos;s priority.", tone="warn")
elif under_served:
    so_what(
        f"Weighting toward <strong>{', '.join(under_served)}</strong> "
        f"(under the 2/month target).", tone="info")
else:
    so_what(
        "All three personas are at or above the 2/month target. "
        "The plan below is an even rotation.", tone="good")

st.caption("Edit any cell. Save writes to "
            "`data/content_plan.csv` and re-renders. Download to "
            "send to Ian.")

# Load saved plan if one exists (respects user edits between visits)
saved = load_csv("content_plan.csv")
if not saved.empty and len(saved) == 12:
    plan_df = saved

edited = st.data_editor(
    plan_df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="cp_editor",
    column_config={
        "Week starting": st.column_config.TextColumn(disabled=True),
        "Persona":       st.column_config.SelectboxColumn(
                            options=PERSONAS),
        "Format":        st.column_config.SelectboxColumn(
                            options=FORMATS),
    })

save_col, dl_col = st.columns(2)
with save_col:
    if st.button("Save plan", type="primary", key="cp_save"):
        import os as _os
        out_path = _os.path.join("data", "content_plan.csv")
        edited.to_csv(out_path, index=False)
        st.success(f"Saved to {out_path}.")
        st.rerun()
with dl_col:
    csv_bytes = edited.to_csv(index=False).encode("utf-8")
    st.download_button("Download plan (CSV)", data=csv_bytes,
                         file_name="content_plan.csv",
                         mime="text/csv", key="cp_download")


# ==========================================================================
# 5. Ready-to-write briefs per persona (spec 11)
# ==========================================================================
st.markdown('<h2>Ready-to-write briefs for the priority personas</h2>',
             unsafe_allow_html=True)
st.caption("Ian said Finance and IT need dedicated content. Here is "
            "a brief per topic - hand any of these to the writer.")

focus = zero_touch if zero_touch else (under_served or [])
if not focus:
    focus = ["Finance", "IT-Systems"]  # spec 11 defaults

for persona in focus:
    if persona == "Research":
        continue  # Ian said other personas need focus
    if persona not in TOPICS:
        continue
    with st.expander(f"{persona} - {len(TOPICS[persona])} topic briefs",
                       expanded=(persona == focus[0])):
        for topic, angle in TOPICS[persona]:
            st.markdown(
                f'<div style="border-left:3px solid '
                f'{ACCENT if persona == "IT-Systems" else GOLD};'
                f'padding:.6rem 1rem;margin:.5rem 0;background:{BG_SOFT};'
                f'border-radius:4px">'
                f'<div style="font-weight:600;color:{INK};font-size:.95rem;'
                f'margin-bottom:.3rem">{topic}</div>'
                f'<div style="color:{INK_SOFT};font-size:.85rem;'
                f'line-height:1.5">{angle}</div>'
                f'<div style="margin-top:.4rem;font-size:.78rem;'
                f'color:{MUTED}"><strong>Audience:</strong> {persona} '
                f'seat &middot; <strong>Formats:</strong> Email, '
                f'LinkedIn post, Whitepaper.</div>'
                f'</div>', unsafe_allow_html=True)
