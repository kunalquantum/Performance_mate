"""
Persona - By institution type.

Are we over-indexed on Universities? How does coverage differ for NHS
Trusts vs Research Institutes vs Charities? One table, one filter, one
answer.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, so_what,
                     load_csv, INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>By institution type</h1>', unsafe_allow_html=True)
core_question("Are we over-indexed on Universities, and which segment (NHS Trust, Research Institute, etc.) is under-covered?")
st.caption("Where the target list breaks down by type of "
            "organisation, and how our persona coverage compares "
            "across those types. If one type is under-covered, that "
            "is the segment to focus on next.")
render_status_key()

with st.expander("What the columns mean", expanded=False):
    st.markdown("""
- **Type** &mdash; University, University college, NHS Trust,
  Research Institute, Charity / Foundation, and so on.
- **In target** &mdash; institutions of this type on our target list.
- **Have contacts** &mdash; how many of them we have at least one
  contact for.
- **Complete coverage** &mdash; how many hold all three personas
  (Research + Finance + IT-Systems).
- **% covered** &mdash; institutions with contacts, as a share of
  target.
""")


coverage = load_csv("persona_institution_coverage.csv")
if coverage.empty:
    st.info("No coverage data. Run `python etl/persona_data_etl.py`.")
    st.stop()

for c in ("contacts", "research", "finance", "it_systems",
            "personas_held", "valid_emails"):
    if c in coverage.columns:
        coverage[c] = pd.to_numeric(coverage[c],
                                       errors="coerce").fillna(0).astype(int)

target = coverage[
    coverage["in_target"].astype(str).str.lower() == "yes"].copy()


# ==========================================================================
# Top-line tiles
# ==========================================================================
type_counts = target["type"].fillna("Unclassified").value_counts()
n_types = len(type_counts)
top_type = type_counts.index[0] if len(type_counts) else "-"
top_type_n = int(type_counts.iloc[0]) if len(type_counts) else 0

# The type with the LOWEST coverage %
_by_type = target.copy()
_by_type["has_contacts"] = _by_type["contacts"] > 0
_cov_by = (_by_type.groupby(_by_type["type"].fillna("Unclassified"))
            .agg(target_n=("institution", "count"),
                  have=("has_contacts", "sum"))
            .reset_index()
            .rename(columns={"type": "Type"}))
_cov_by["pct"] = _cov_by["have"] / _cov_by["target_n"].replace(0, 1) * 100
weakest = _cov_by.sort_values("pct").iloc[0] if len(_cov_by) else None

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Institution types",
              f"{n_types}",
              tooltip="Distinct institution types on the target list.")
with k2:
    kpi_tile("Biggest type",
              f"{top_type_n}",
              sub=str(top_type),
              tooltip="The most common institution type in the target "
                      "list.")
with k3:
    if weakest is not None:
        kpi_tile("Worst-covered type",
                  f"{weakest['pct']:.0f}%",
                  sub=f"{str(weakest['Type'])[:32]} "
                       f"({int(weakest['have'])} of "
                       f"{int(weakest['target_n'])})",
                  color=WARN if weakest['pct'] < 40 else GOLD,
                  tooltip="Segment with the lowest share of "
                          "institutions we hold contacts for.")
with k4:
    kpi_tile("Target institutions",
              f"{len(target):,}",
              tooltip="Total across all types on the target list.")


# ==========================================================================
# Filter
# ==========================================================================
st.markdown('<h2>Coverage by type</h2>', unsafe_allow_html=True)
fc1, fc2 = st.columns([1.4, 1])
with fc1:
    types = sorted([t for t in target["type"].fillna("Unclassified")
                      .unique() if str(t).strip()])
    pick_types = st.multiselect("Filter types", types, default=types,
                                  key="pt_types")
with fc2:
    show_only_gaps = st.toggle(
        "Show types with gaps only", value=False, key="pt_gaps",
        help="Hide types where every target institution already has "
                "contacts.")

view = target[target["type"].fillna("Unclassified").isin(pick_types)].copy()


# ==========================================================================
# Type breakdown table
# ==========================================================================
by_type = (view.assign(type=view["type"].fillna("Unclassified"))
             .groupby("type")
             .agg(target_n=("institution", "count"),
                   with_contacts=("contacts",
                                   lambda s: int((s > 0).sum())),
                   complete=("personas_held",
                               lambda s: int((s >= 3).sum())),
                   partial=("personas_held",
                              lambda s: int(((s >= 1)
                                              & (s < 3)).sum())),
                   none=("personas_held",
                           lambda s: int((s == 0).sum())),
                   total_contacts=("contacts", "sum"),
                   total_valid=("valid_emails", "sum"))
             .reset_index())
by_type["% covered"] = (by_type["with_contacts"]
                          / by_type["target_n"].replace(0, 1) * 100)
by_type = by_type.sort_values("target_n", ascending=False)

if show_only_gaps:
    by_type = by_type[by_type["with_contacts"] < by_type["target_n"]]

# Custom HTML table so we can colour the %-covered cell
header = (
    f'<div style="display:grid;grid-template-columns:'
    f'2.2fr .8fr .9fr 1fr .9fr .9fr 1fr 1fr;gap:.4rem;'
    f'padding:.5rem .7rem;font-size:.72rem;'
    f'text-transform:uppercase;letter-spacing:.12em;'
    f'color:{MUTED};font-weight:600;border-bottom:1px solid {LINE}">'
    f'<div>Type</div><div>In target</div><div>Have contacts</div>'
    f'<div>% covered</div><div>Complete</div><div>Partial</div>'
    f'<div>Total contacts</div><div>Valid emails</div></div>')

rows_html = [header]
for _, r in by_type.iterrows():
    p = r["% covered"]
    bg = ("#DDEEEC" if p >= 80 else
            "#F7F0DA" if p >= 40 else "#FBEDED")
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'2.2fr .8fr .9fr 1fr .9fr .9fr 1fr 1fr;gap:.4rem;'
        f'padding:.55rem .7rem;font-size:.9rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        f'<div style="color:{INK};font-weight:600">{r["type"]}</div>'
        f'<div style="color:{INK}">{int(r["target_n"])}</div>'
        f'<div style="color:{INK}">{int(r["with_contacts"])}</div>'
        f'<div style="background:{bg};padding:.15rem .4rem;'
        f'border-radius:4px;color:{INK};font-weight:700">'
        f'{p:.0f}%</div>'
        f'<div style="color:{INK_SOFT}">{int(r["complete"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["partial"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["total_contacts"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["total_valid"])}</div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)

# So-what
if not by_type.empty:
    best = by_type.sort_values("% covered", ascending=False).iloc[0]
    worst = by_type.sort_values("% covered").iloc[0]
    if best["% covered"] - worst["% covered"] >= 30:
        so_what(
            f"<strong>{best['type']}</strong> is at "
            f"{best['% covered']:.0f}% coverage; "
            f"<strong>{worst['type']}</strong> is at "
            f"{worst['% covered']:.0f}%. That is the biggest coverage "
            f"gap by segment - worth focusing outreach there.",
            tone="warn")


# ==========================================================================
# Drill: pick a type, see the institutions in it
# ==========================================================================
st.markdown('<h2>Drill into a type</h2>', unsafe_allow_html=True)
type_options = ["-- pick one --"] + sorted(
    view["type"].fillna("Unclassified").unique().tolist())
pick = st.selectbox("Institution type", type_options,
                      key="pt_drill")

if pick and pick != "-- pick one --":
    drill = view[view["type"].fillna("Unclassified") == pick].copy()
    drill = drill.sort_values("personas_held", ascending=False)
    st.caption(f"{len(drill):,} target institutions of type "
                f"'{pick}'. Sorted by personas held.")
    show = drill[[
        "institution", "contacts",
        "research", "finance", "it_systems",
        "personas_held", "valid_emails",
    ]].rename(columns={
        "institution":    "Institution",
        "contacts":       "Contacts",
        "research":       "Research",
        "finance":        "Finance",
        "it_systems":     "IT-Systems",
        "personas_held":  "Personas (of 3)",
        "valid_emails":   "Valid emails",
    })
    st.dataframe(
        show, use_container_width=True, hide_index=True, height=420,
        column_config={
            "Personas (of 3)": st.column_config.ProgressColumn(
                min_value=0, max_value=3, format="%d",
                help="0-3 of the three main personas covered."),
        })
