"""
Persona - Priority gaps.

The 308 institutions where we know a persona is missing, ranked so the
sales director can see which gaps are worth chasing first.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Priority gaps</h1>', unsafe_allow_html=True)
core_question("Which persona gaps should we close first, and where should the SDR team focus this week?")
st.caption("Institutions where we know a persona is missing. Sorted "
            "by priority. Close the top of this list first - each "
            "missing persona is a hole in the buying committee.")
render_status_key()

with st.expander("What the columns mean", expanded=False):
    st.markdown("""
- **Institution** &mdash; the university or research org.
- **Contacts held** &mdash; how many contacts we have there today.
- **Research / Finance / IT-Systems** &mdash; contacts per persona.
- **What is missing** &mdash; the personas we don&apos;t have yet.
- **Priority** &mdash; the workbook&apos;s judgement:
  &lsquo;High&rsquo; = big account or strategic, worth chasing.
  &lsquo;Medium&rsquo; / &lsquo;Low&rsquo; = still worth closing but
  further down the queue. &lsquo;-&rsquo; means complete coverage
  already (no gap to chase).
""")


df = load_csv("persona_gaps.csv")
if df.empty:
    st.info("No gaps data. Run `python etl/persona_data_etl.py`.")
    st.stop()

for c in ("contacts_held", "research", "finance", "it_systems",
            "personas_held"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)


# Only rows that actually have a gap (skip complete-coverage rows)
gaps = df[df["what_is_missing"].astype(str).str.lower() != "complete"].copy()


# ==========================================================================
# Top-line tiles
# ==========================================================================
n_gaps  = len(gaps)
n_high  = int((gaps["priority"].astype(str).str.lower() == "high").sum())
n_med   = int((gaps["priority"].astype(str).str.lower() == "medium").sum())
# Most common missing persona
_all_missing = []
for m in gaps["what_is_missing"].dropna().astype(str):
    for p in m.split(","):
        p = p.strip()
        if p and p.lower() not in ("complete", "-"):
            _all_missing.append(p)
_top_missing = pd.Series(_all_missing).value_counts()
top_missing_name = _top_missing.index[0] if len(_top_missing) else "-"
top_missing_n    = int(_top_missing.iloc[0]) if len(_top_missing) else 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Total gaps", f"{n_gaps:,}",
              tooltip="Institutions with at least one persona missing.")
with k2:
    kpi_tile("High priority", f"{n_high:,}",
              tooltip="Big or strategic accounts flagged as worth "
                      "chasing first.",
              color=WARN if n_high >= 10 else GOLD)
with k3:
    kpi_tile("Medium priority", f"{n_med:,}",
              tooltip="Still worth closing but further down the "
                      "queue.")
with k4:
    kpi_tile("Most-missing persona", top_missing_name,
              sub=f"missing at {top_missing_n:,} institutions",
              tooltip="The persona bucket where we have the most "
                      "gaps overall.",
              color=GOLD)


# ==========================================================================
# Filter panel
# ==========================================================================
st.markdown('<h2>Filter and search</h2>', unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns([1.2, 1.2, 1.5])
with fc1:
    priorities = sorted([p for p in gaps["priority"].dropna()
                           .astype(str).unique() if p not in ("-", "nan")])
    pick_prio = st.multiselect("Priority", priorities,
                                 default=priorities,
                                 key="gap_prio")
with fc2:
    missing_choices = ["Research", "Finance", "IT/Systems"]
    pick_missing = st.multiselect(
        "Missing persona",
        missing_choices,
        default=missing_choices,
        key="gap_missing",
        help="Show only rows where the selected persona is missing.")
with fc3:
    search = st.text_input("Search institution name",
                             placeholder="e.g. Cambridge, Bristol",
                             key="gap_search")

filtered = gaps.copy()
if pick_prio:
    filtered = filtered[filtered["priority"].astype(str).isin(pick_prio)]
if pick_missing and len(pick_missing) < len(missing_choices):
    def _matches(row):
        m = str(row.get("what_is_missing", ""))
        return any(p in m for p in pick_missing)
    filtered = filtered[filtered.apply(_matches, axis=1)]
if search:
    filtered = filtered[
        filtered["institution"].astype(str).str.contains(
            search, case=False, na=False)]


# ==========================================================================
# The priority queue table
# ==========================================================================
st.markdown('<h2>Priority queue</h2>', unsafe_allow_html=True)
st.caption(f"Showing {len(filtered):,} of {len(gaps):,} gaps. "
            "Sort by any column.")

# Priority sort order: High > Medium > Low > blank
_priority_rank = {"High": 0, "Medium": 1, "Low": 2}
filtered["_prio_rank"] = filtered["priority"].map(
    lambda p: _priority_rank.get(str(p).strip(), 9))
filtered = filtered.sort_values(
    ["_prio_rank", "contacts_held"], ascending=[True, False])

display = filtered[[
    "institution", "contacts_held",
    "research", "finance", "it_systems",
    "what_is_missing", "priority",
]].copy()
display.columns = [
    "Institution", "Contacts held",
    "Research", "Finance", "IT-Systems",
    "What is missing", "Priority",
]

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    height=500,
    column_config={
        "Contacts held": st.column_config.NumberColumn(format="%d"),
        "Research": st.column_config.NumberColumn(format="%d"),
        "Finance": st.column_config.NumberColumn(format="%d"),
        "IT-Systems": st.column_config.NumberColumn(format="%d"),
        "What is missing": st.column_config.TextColumn(
            width="medium",
            help="Comma-separated list of the personas we do not "
                    "yet cover at this institution."),
        "Priority": st.column_config.TextColumn(
            help="High priority = close this gap first."),
    },
)


# ==========================================================================
# Grouped view - the top 10 High-priority gaps as a card list
# ==========================================================================
st.markdown('<h2>Top 10 to chase this week</h2>',
             unsafe_allow_html=True)
top10 = filtered[filtered["priority"].astype(str).str.strip().str.lower()
                    == "high"].head(10)
if top10.empty:
    st.markdown(
        f'<div style="color:{INK_SOFT};font-size:.92rem">'
        f'No high-priority gaps in the current filter.</div>',
        unsafe_allow_html=True)
else:
    for _, r in top10.iterrows():
        miss = str(r.get("what_is_missing", "")).strip()
        st.markdown(
            f'<div style="border:1px solid {LINE};border-left:4px '
            f'solid {WARN};background:{BG};padding:.7rem 1rem;'
            f'margin:.5rem 0;border-radius:6px;'
            f'display:flex;justify-content:space-between;'
            f'align-items:center">'
            f'<div>'
            f'<div style="color:{INK};font-weight:600;font-size:.98rem">'
            f'{r["institution"]}</div>'
            f'<div style="color:{INK_SOFT};font-size:.82rem;'
            f'margin-top:.2rem">'
            f'Have <strong>{int(r["contacts_held"])}</strong> contacts. '
            f'Missing: <strong>{miss}</strong>.'
            f'</div>'
            f'</div>'
            f'<div style="font-size:.72rem;text-transform:uppercase;'
            f'letter-spacing:.14em;color:{WARN};font-weight:700">'
            f'High priority</div>'
            f'</div>', unsafe_allow_html=True)


st.markdown(
    f'<div style="margin-top:2.5rem;color:{MUTED};font-size:.75rem">'
    f'Data source: <code>data/persona_gaps.csv</code>.</div>',
    unsafe_allow_html=True)
