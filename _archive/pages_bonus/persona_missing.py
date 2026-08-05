"""
Persona - Missing persona target list.

Pick which persona is missing (Research / Finance / IT-Systems), get
back a queue of institutions where we do NOT hold that persona,
sorted by ease-of-win (existing contact count) so an SDR knows where
to add one contact for the biggest coverage jump.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, so_what,
                     load_csv, INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Missing persona target list</h1>',
             unsafe_allow_html=True)
core_question("Where do we add ONE contact to close the biggest coverage gap, and who are the easiest wins?")
st.caption("Pick a persona. See the target institutions where we do "
            "NOT hold that persona yet. Sorted with the easiest wins "
            "at the top (institutions where we already have plenty of "
            "other contacts - adding one more seat is a quick close).")
render_status_key()

with st.expander("How the sort works", expanded=False):
    st.markdown("""
- **Contacts held** &mdash; how many people we already know at that
  institution. High = we know the place, adding one more person is
  easier.
- **Personas held** &mdash; how many of the three main personas we
  already cover. 2 = we&apos;re one away from complete coverage
  (highest-value gap). 0 = we hold nothing there at all.
- **Institution type** &mdash; University / NHS Trust / etc.
  Filterable if you want to focus on one segment.

Default sort puts institutions with 2 personas held first (biggest
coverage jump for adding one seat), then sorts by how many contacts
we already have.
""")


coverage = load_csv("persona_institution_coverage.csv")
if coverage.empty:
    st.info("No coverage data. Run `python etl/persona_data_etl.py`.")
    st.stop()

for c in ("contacts", "research", "finance", "it_systems",
            "personas_held"):
    if c in coverage.columns:
        coverage[c] = pd.to_numeric(coverage[c],
                                       errors="coerce").fillna(0).astype(int)
target = coverage[
    coverage["in_target"].astype(str).str.lower() == "yes"].copy()


# ==========================================================================
# Persona picker (the primary control)
# ==========================================================================
persona_pick = st.radio(
    "Missing persona",
    ["Research", "Finance", "IT-Systems"],
    horizontal=True, key="mp_persona")

col_lookup = {"Research": "research", "Finance": "finance",
                "IT-Systems": "it_systems"}
col = col_lookup[persona_pick]

# All institutions missing that persona
missing = target[target[col] == 0].copy()


# ==========================================================================
# Top-line tiles
# ==========================================================================
n_missing = len(missing)
n_one_away = int((missing["personas_held"] == 2).sum())
n_zero_held = int((missing["personas_held"] == 0).sum())
n_total_target = len(target)

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile(f"Missing {persona_pick}", f"{n_missing:,}",
              sub=f"of {n_total_target:,} target institutions",
              tooltip=f"Target institutions where we hold zero "
                      f"{persona_pick} contacts.",
              color=WARN if n_missing >= 100 else GOLD)
with k2:
    kpi_tile("Quick wins",
              f"{n_one_away:,}",
              sub="one persona away from complete",
              tooltip="Institutions where we already hold 2 of 3 "
                      "personas. Adding the missing one completes the "
                      "buying committee.",
              color=ACCENT)
with k3:
    kpi_tile("No contacts at all",
              f"{n_zero_held:,}",
              sub="cold institutions",
              tooltip="Institutions where we hold zero personas. "
                      "Harder to close - no warm relationship to "
                      "leverage.",
              color=GOLD)
with k4:
    gap_pct = n_missing / max(n_total_target, 1) * 100
    kpi_tile("Gap size",
              f"{gap_pct:.0f}%",
              sub="of target list has no such persona",
              tooltip="Missing institutions as a share of the entire "
                      "target list.")


# ==========================================================================
# Filter panel
# ==========================================================================
st.markdown('<h2>Filter and sort</h2>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.3, 1.3, 1.4])
with fc1:
    types = sorted([t for t in missing["type"].fillna("Unclassified")
                      .unique() if str(t).strip()])
    pick_types = st.multiselect("Institution type",
                                  types, default=types,
                                  key="mp_types")
with fc2:
    only_warm = st.toggle(
        "Warm accounts only (2 personas held)", value=False,
        key="mp_warm",
        help="Show only institutions where we already hold 2 of the 3 "
                "personas.")
with fc3:
    min_contacts = st.slider(
        "Minimum contacts we already hold",
        min_value=0,
        max_value=int(missing["contacts"].max()) if len(missing) else 0,
        value=0, step=1, key="mp_min",
        help="Skip institutions where we barely know anyone. "
                "Sliding this up focuses on wins.")

view = missing[missing["type"].fillna("Unclassified").isin(pick_types)]
view = view[view["contacts"] >= min_contacts]
if only_warm:
    view = view[view["personas_held"] == 2]

# Sort: personas_held desc, contacts desc (warm first, then well-known)
view = view.sort_values(["personas_held", "contacts"],
                          ascending=[False, False])


# ==========================================================================
# Ranked table
# ==========================================================================
st.markdown(f'<h2>{len(view):,} institutions missing '
             f'{persona_pick}</h2>', unsafe_allow_html=True)
st.caption("Easiest wins at the top. Download the list to hand to "
            "the SDR team.")

show = view[[
    "institution", "type", "contacts",
    "research", "finance", "it_systems",
    "personas_held",
]].rename(columns={
    "institution":    "Institution",
    "type":           "Type",
    "contacts":       "Contacts held",
    "research":       "Research",
    "finance":        "Finance",
    "it_systems":     "IT-Systems",
    "personas_held":  "Personas (of 3)",
})

st.dataframe(
    show,
    use_container_width=True, hide_index=True, height=520,
    column_config={
        "Personas (of 3)": st.column_config.ProgressColumn(
            min_value=0, max_value=3, format="%d"),
        "Contacts held":   st.column_config.NumberColumn(format="%d"),
    })

# So-what
if len(view) > 0:
    top = view.iloc[0]
    so_what(
        f"Top candidate to add a {persona_pick} contact: "
        f"<strong>{top['institution']}</strong> "
        f"({int(top['contacts'])} contacts already, "
        f"{int(top['personas_held'])} of 3 personas held). "
        f"Adding one seat here"
        + (" completes the coverage." if top['personas_held'] == 2
            else " starts building the committee."),
        tone="good")

# Download button
if len(view) > 0:
    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"Download this list ({len(view):,} rows)",
        data=csv_bytes,
        file_name=f"missing_{persona_pick.lower()}.csv",
        mime="text/csv",
        key="mp_download")
