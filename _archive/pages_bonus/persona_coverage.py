"""
Persona - Institution coverage.

Which UK institutions do we have contacts inside? For each one, how many
Research / Finance / IT-Systems people, and how many personas do we
cover out of three?

Table-first, no charts. Filter, search, sort, drill.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Institution coverage</h1>', unsafe_allow_html=True)
core_question("How well do we cover each UK target institution across the three personas?")
st.caption("Every UK institution we have contacts inside, with a "
            "breakdown of which personas we cover. Green means all "
            "three personas are covered; gold means one or two "
            "missing; red means no coverage at all.")
render_status_key()

with st.expander("What the columns mean", expanded=False):
    st.markdown("""
- **Institution** &mdash; the university or research organisation.
- **In target list** &mdash; whether this institution is on our
  active target list (Yes / No).
- **Contacts** &mdash; total contacts we hold at this institution.
- **Research / Finance / IT-Systems** &mdash; how many contacts we
  have in each persona bucket.
- **Personas held** &mdash; 0-3, out of the three we care about
  (Research, Finance, IT-Systems).
- **Valid emails** &mdash; how many of those contacts have a
  verified deliverable email.
- **Coverage status** &mdash; simple traffic light:
  &lsquo;Complete&rsquo; = all 3 personas, &lsquo;Partial&rsquo; =
  1 or 2 personas, &lsquo;None&rsquo; = 0.
""")


df = load_csv("persona_institution_coverage.csv")
if df.empty:
    st.info("No coverage data. Run "
             "`python etl/persona_data_etl.py`.")
    st.stop()

# Coerce
for c in ("contacts", "research", "finance", "it_systems",
            "unclassified", "personas_held", "valid_emails"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

df["coverage_status"] = df["personas_held"].apply(
    lambda n: "Complete" if n >= 3 else
              ("Partial"  if n >= 1 else "None"))


# ==========================================================================
# Top-line KPI tiles
# ==========================================================================
in_target    = df[df["in_target"].astype(str).str.lower() == "yes"]
n_target     = len(in_target)
n_complete   = int((in_target["personas_held"] >= 3).sum())
n_partial    = int(((in_target["personas_held"] >= 1)
                     & (in_target["personas_held"] < 3)).sum())
n_none       = int((in_target["personas_held"] == 0).sum())
total_contacts = int(in_target["contacts"].sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Target institutions", f"{n_target:,}",
              tooltip="Institutions on our active target list.")
with k2:
    kpi_tile("Complete coverage",
              f"{n_complete:,}",
              sub=f"{n_complete/max(n_target,1)*100:.0f}% of target",
              tooltip="Institutions where we have contacts across "
                      "all three personas (Research, Finance, "
                      "IT-Systems).",
              color=ACCENT)
with k3:
    kpi_tile("Partial coverage",
              f"{n_partial:,}",
              sub="1 or 2 personas held",
              tooltip="Institutions where we hold some personas but "
                      "are missing at least one. These are the "
                      "priority gaps to close.",
              color=GOLD)
with k4:
    kpi_tile("Total contacts", f"{total_contacts:,}",
              tooltip="Sum of all contacts across all target "
                      "institutions.")


# ==========================================================================
# Filter panel
# ==========================================================================
st.markdown('<h2>Filter and search</h2>', unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns([1.2, 1.2, 1.5])
with fc1:
    target_filter = st.selectbox(
        "Show", ["Target list only", "All institutions"],
        key="cov_target_filter")
with fc2:
    coverage_filter = st.multiselect(
        "Coverage status",
        ["Complete", "Partial", "None"],
        default=["Complete", "Partial", "None"],
        key="cov_status_filter")
with fc3:
    search = st.text_input("Search institution name",
                             placeholder="e.g. Manchester, King's, Sussex",
                             key="cov_search")

# Apply filters
filtered = df.copy()
if target_filter == "Target list only":
    filtered = filtered[
        filtered["in_target"].astype(str).str.lower() == "yes"]
if coverage_filter:
    filtered = filtered[filtered["coverage_status"].isin(coverage_filter)]
if search:
    filtered = filtered[
        filtered["institution"].astype(str).str.contains(
            search, case=False, na=False)]


# ==========================================================================
# Sortable table
# ==========================================================================
st.markdown('<h2>Coverage table</h2>', unsafe_allow_html=True)
st.caption(f"Showing {len(filtered):,} of {len(df):,} institutions. "
            f"Click any column header to sort.")

display = filtered[[
    "institution", "type", "in_target", "contacts",
    "research", "finance", "it_systems",
    "personas_held", "valid_emails", "coverage_status"
]].copy()
display.columns = [
    "Institution", "Type", "In target", "Contacts",
    "Research", "Finance", "IT-Systems",
    "Personas held (of 3)", "Valid emails", "Coverage",
]

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    height=500,
    column_config={
        "Coverage": st.column_config.TextColumn(
            help="Complete = all 3 personas, Partial = 1-2, None = 0"),
        "Personas held (of 3)": st.column_config.ProgressColumn(
            min_value=0, max_value=3, format="%d",
            help="How many of the three personas we cover at this "
                    "institution."),
        "Contacts": st.column_config.NumberColumn(format="%d"),
        "Valid emails": st.column_config.NumberColumn(format="%d"),
    },
)


# ==========================================================================
# Drill-down: pick an institution, see the per-persona breakdown
# ==========================================================================
st.markdown('<h2>Drill down into one institution</h2>',
             unsafe_allow_html=True)
options = ["-- pick one --"] + sorted(
    filtered["institution"].dropna().astype(str).unique().tolist())
pick = st.selectbox("Institution", options, key="cov_drill")

if pick and pick != "-- pick one --":
    row = filtered[filtered["institution"] == pick].iloc[0]
    r  = int(row["research"])
    f  = int(row["finance"])
    it = int(row["it_systems"])
    tot = int(row["contacts"])
    ve = int(row["valid_emails"])

    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        kpi_tile("Research contacts", f"{r}",
                  sub="senior + operational + academic",
                  color=ACCENT if r > 0 else GOLD)
    with dc2:
        kpi_tile("Finance contacts", f"{f}",
                  color=ACCENT if f > 0 else GOLD)
    with dc3:
        kpi_tile("IT-Systems contacts", f"{it}",
                  color=ACCENT if it > 0 else GOLD)
    with dc4:
        vpct = ve / max(tot, 1) * 100
        kpi_tile("Verified emails", f"{ve}",
                  sub=f"{vpct:.0f}% of {tot}",
                  color=ACCENT if vpct >= 60 else GOLD)

    # Per-persona coverage bar (simple, one dimension)
    st.markdown('<h3>Persona coverage</h3>', unsafe_allow_html=True)
    max_persona = max(r, f, it, 1)
    for label, count in [("Research", r), ("Finance", f),
                            ("IT-Systems", it)]:
        pct = count / max_persona * 100
        colour = ACCENT if count > 0 else GOLD
        st.markdown(
            f'<div style="margin:.5rem 0">'
            f'<div style="display:flex;justify-content:space-between;'
            f'font-size:.85rem;margin-bottom:.2rem">'
            f'<span style="color:{INK};font-weight:600">{label}</span>'
            f'<span style="color:{INK_SOFT}">{count} contacts</span>'
            f'</div>'
            f'<div style="height:8px;background:{LINE};'
            f'border-radius:4px;overflow:hidden">'
            f'<div style="height:100%;width:{pct}%;background:{colour}">'
            f'</div></div></div>',
            unsafe_allow_html=True)

    # Missing persona nudge
    missing = []
    if r == 0:  missing.append("Research")
    if f == 0:  missing.append("Finance")
    if it == 0: missing.append("IT-Systems")
    if missing:
        st.markdown(
            f'<div style="background:#FBF3E5;border-left:3px solid '
            f'{GOLD};padding:.7rem 1rem;margin-top:1rem;'
            f'border-radius:4px;font-size:.92rem">'
            f'<strong>Missing:</strong> {", ".join(missing)}. Adding '
            f'a contact in {"either" if len(missing) > 1 else "this"} '
            f'seat would complete the coverage.'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="background:#EBF3F2;border-left:3px solid '
            f'{ACCENT};padding:.7rem 1rem;margin-top:1rem;'
            f'border-radius:4px;font-size:.92rem">'
            f'<strong>Complete coverage.</strong> All three personas '
            f'held at this institution.'
            f'</div>', unsafe_allow_html=True)


st.markdown(
    f'<div style="margin-top:2.5rem;color:{MUTED};font-size:.75rem">'
    f'Data source: <code>data/persona_institution_coverage.csv</code>. '
    f'Rerun <code>python etl/persona_data_etl.py</code> after editing '
    f'the source workbook.</div>',
    unsafe_allow_html=True)
