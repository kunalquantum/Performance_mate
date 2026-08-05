"""
Persona - Review queue.

Contacts the auto-tagger flagged for a human to confirm. Grouped by
reason so a data-ops person can knock through them one bucket at a
time.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Review queue</h1>', unsafe_allow_html=True)
core_question("Which contact tags still need a human eye before we can trust them?")
st.caption("Contacts the system was not fully sure how to tag. Each "
            "row needs a human eye. Group by reason and knock out one "
            "bucket at a time.")
render_status_key()

with st.expander("What the columns mean", expanded=False):
    st.markdown("""
- **Job title** &mdash; what LinkedIn / the source shows for this
  contact.
- **Institution** &mdash; where they work.
- **Persona applied** &mdash; the best-guess persona we assigned.
- **Why flagged** &mdash; the reason the auto-tagger wants human
  confirmation (e.g. &lsquo;Research/Finance hybrid - confirm&rsquo;
  means the title could fit either bucket).
- **Source sheet** &mdash; which of the underlying tabs the row came
  from (In CRM valid, In CRM unknown, etc.).
""")


df = load_csv("persona_review_queue.csv")
if df.empty:
    st.info("No review queue data. Run "
             "`python etl/persona_data_etl.py`.")
    st.stop()


# ==========================================================================
# Top-line tiles
# ==========================================================================
total_flagged = len(df)
reasons = df["why_flagged"].astype(str).value_counts()
top_reason = reasons.index[0] if len(reasons) else "-"
top_reason_n = int(reasons.iloc[0]) if len(reasons) else 0
n_reasons = len(reasons)
n_institutions = df["institution"].nunique() if "institution" in df.columns \
    else 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Flagged contacts", f"{total_flagged:,}",
              tooltip="Total contacts waiting for a human eye.",
              color=WARN if total_flagged >= 200 else GOLD)
with k2:
    kpi_tile("Distinct reasons", f"{n_reasons:,}",
              tooltip="How many different kinds of flag we have. "
                      "Fewer reasons = a smaller workflow to build.")
with k3:
    kpi_tile("Institutions affected", f"{n_institutions:,}",
              tooltip="How many institutions have at least one "
                      "flagged contact.")
with k4:
    kpi_tile("Biggest single reason", f"{top_reason_n:,}",
              sub=str(top_reason)[:40],
              tooltip="The most common flag reason. Fixing the "
                      "rule for this reason clears the biggest chunk.")


# ==========================================================================
# Reason buckets
# ==========================================================================
st.markdown('<h2>By flag reason</h2>', unsafe_allow_html=True)
st.caption("Click a reason to see the contacts in that bucket.")

for reason, count in reasons.items():
    label = str(reason)
    with st.expander(f"{label}  ({count} contacts)",
                       expanded=False):
        sub = df[df["why_flagged"].astype(str) == label]
        cols_show = [c for c in
                       ["job_title", "institution", "persona_applied",
                        "source_sheet"]
                       if c in sub.columns]
        renamed = sub[cols_show].rename(columns={
            "job_title":       "Job title",
            "institution":     "Institution",
            "persona_applied": "Persona applied",
            "source_sheet":    "Source sheet",
        })
        st.dataframe(
            renamed,
            use_container_width=True,
            hide_index=True,
            height=min(300, 45 + 35 * min(len(renamed), 8)))


# ==========================================================================
# Full filterable table (opt-in expander so page loads clean)
# ==========================================================================
with st.expander("Show the full flat table (all reasons in one view)",
                   expanded=False):
    fc1, fc2 = st.columns([1.5, 1.5])
    with fc1:
        pick_reason = st.multiselect(
            "Reason",
            reasons.index.tolist(),
            default=reasons.index.tolist(),
            key="rev_reason")
    with fc2:
        search = st.text_input(
            "Search job title or institution",
            key="rev_search")

    view = df.copy()
    if pick_reason:
        view = view[view["why_flagged"].astype(str).isin(pick_reason)]
    if search:
        mask = (view["job_title"].astype(str).str.contains(
                    search, case=False, na=False)
                | view["institution"].astype(str).str.contains(
                    search, case=False, na=False))
        view = view[mask]

    cols_show = [c for c in
                   ["job_title", "institution", "persona_applied",
                    "why_flagged", "source_sheet"]
                   if c in view.columns]
    st.dataframe(
        view[cols_show].rename(columns={
            "job_title":       "Job title",
            "institution":     "Institution",
            "persona_applied": "Persona applied",
            "why_flagged":     "Why flagged",
            "source_sheet":    "Source sheet",
        }),
        use_container_width=True,
        hide_index=True,
        height=500)


st.markdown(
    f'<div style="margin-top:2.5rem;color:{MUTED};font-size:.75rem">'
    f'Data source: <code>data/persona_review_queue.csv</code>.</div>',
    unsafe_allow_html=True)
