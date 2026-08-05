"""
Persona - Warm leads (MQLs).

Every prospect who has engaged with our emails enough to be a Marketing
Qualified Lead. Per-recipient counts of opens + clicks, persona
inferred from job title, sales-contacted status.

Data source: data/mql_engaged.csv (parsed from the GrantsNow Task
Sheet's 'MQL for SALES' tab by etl/mql_etl.py).
"""
from shared import (core_question, inject_css, render_status_key,
                     kpi_tile, so_what, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Warm leads</h1>', unsafe_allow_html=True)
core_question("Who is engaging with our emails right now, which "
                "persona are they, and has sales chased them yet?")
st.caption("Every marketing-qualified lead - people whose open and "
            "click counts tell us they are paying attention. Sorted "
            "so the hottest leads sit at the top.")
render_status_key()

with st.expander("What each column means", expanded=False):
    st.markdown("""
- **Name / Institution / Job title** &mdash; who the person is and
  where they work.
- **Persona** &mdash; inferred from the job title. Research /
  Finance / IT-Systems / Unclassified.
- **Opens** &mdash; total email opens across every send. Cumulative.
- **Clicks** &mdash; total clicks on links in our emails. A click is
  a stronger signal than an open.
- **Engagement score** &mdash; opens + clicks. Rough
  &lsquo;temperature&rsquo; of the lead.
- **Sales contacted** &mdash; whether Ian or the sales team have
  already reached out (usually via a LinkedIn connection request).
""")


df = load_csv("mql_engaged.csv")
if df.empty:
    st.info("No MQL data. Run `python etl/mql_etl.py`.")
    st.stop()

for c in ("opens", "clicks", "total_engagement"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)


# ==========================================================================
# Top-line tiles
# ==========================================================================
n_leads = len(df)
n_r = int((df["persona"] == "Research").sum())
n_f = int((df["persona"] == "Finance").sum())
n_i = int((df["persona"] == "IT-Systems").sum())

n_untouched = int(df["sales_touched"].fillna("").astype(str)
                     .str.strip().isin(["", "nan", "None"]).sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Warm leads", f"{n_leads:,}",
              sub="engaged enough to become MQL",
              tooltip="People whose open + click history flagged them "
                      "as a lead worth passing to sales.",
              color=ACCENT)
with k2:
    kpi_tile("Research MQLs", f"{n_r:,}",
              sub=f"{n_r/max(n_leads,1)*100:.0f}% of leads",
              color=ACCENT,
              tooltip="Warm leads whose job title reads as Research.")
with k3:
    kpi_tile("Finance MQLs", f"{n_f:,}",
              sub=f"{n_f/max(n_leads,1)*100:.0f}% of leads",
              color=GOLD if n_f < 10 else ACCENT,
              tooltip="Warm leads whose job title reads as Finance.")
with k4:
    kpi_tile("IT-Systems MQLs", f"{n_i:,}",
              sub=f"{n_i/max(n_leads,1)*100:.0f}% of leads",
              color=WARN if n_i < 5 else GOLD if n_i < 10 else ACCENT,
              tooltip="Warm leads whose job title reads as IT-Systems.")

# A honest read on the persona spread
if n_r > (n_f + n_i) * 2:
    so_what(
        f"<strong>{n_r}</strong> Research MQLs vs "
        f"<strong>{n_f}</strong> Finance and <strong>{n_i}</strong> "
        f"IT-Systems combined. Ian&apos;s hunch is confirmed by real "
        f"data: Finance and IT are dramatically under-engaged. To "
        f"fix this, ship persona-specific email content for those two "
        f"seats (see the Monthly report page for cadence targets).",
        tone="warn")


# ==========================================================================
# Filter panel
# ==========================================================================
st.markdown('<h2>Filter and search</h2>', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns([1.2, 1.2, 1.2, 1.4])
with fc1:
    personas = sorted(df["persona"].dropna().astype(str).unique().tolist())
    pick_p = st.multiselect("Persona", personas, default=personas,
                              key="wl_p")
with fc2:
    min_eng = st.slider(
        "Min engagement score",
        min_value=0,
        max_value=int(df["total_engagement"].max()) if len(df) else 0,
        value=0, step=1, key="wl_min",
        help="Slide up to see only the hottest leads.")
with fc3:
    sales_filter = st.selectbox(
        "Sales chase status",
        ["Any", "Already contacted", "Not yet contacted"],
        key="wl_sales")
with fc4:
    search = st.text_input(
        "Search name / title / institution",
        key="wl_search")


view = df[df["persona"].isin(pick_p)]
view = view[view["total_engagement"] >= min_eng]
if sales_filter == "Already contacted":
    view = view[~view["sales_touched"].fillna("").astype(str)
                  .str.strip().isin(["", "nan", "None"])]
elif sales_filter == "Not yet contacted":
    view = view[view["sales_touched"].fillna("").astype(str)
                  .str.strip().isin(["", "nan", "None"])]
if search:
    mask = (view["first_name"].astype(str).str.contains(
                search, case=False, na=False)
            | view["last_name"].astype(str).str.contains(
                search, case=False, na=False)
            | view["institution"].astype(str).str.contains(
                search, case=False, na=False)
            | view["job_title"].astype(str).str.contains(
                search, case=False, na=False))
    view = view[mask]


view = view.sort_values("total_engagement", ascending=False)


# ==========================================================================
# The lead table
# ==========================================================================
st.markdown(f'<h2>{len(view):,} warm leads (hottest first)</h2>',
             unsafe_allow_html=True)

show = view[[
    "first_name", "last_name", "institution", "job_title",
    "persona", "opens", "clicks", "total_engagement",
    "sales_touched", "email",
]].rename(columns={
    "first_name":       "First",
    "last_name":        "Last",
    "institution":      "Institution",
    "job_title":        "Job title",
    "persona":          "Persona",
    "opens":            "Opens",
    "clicks":           "Clicks",
    "total_engagement": "Engagement",
    "sales_touched":    "Sales contacted",
    "email":            "Email",
})

st.dataframe(
    show,
    use_container_width=True, hide_index=True, height=540,
    column_config={
        "Opens":      st.column_config.NumberColumn(format="%d"),
        "Clicks":     st.column_config.NumberColumn(format="%d"),
        "Engagement": st.column_config.ProgressColumn(
            min_value=0,
            max_value=int(view["total_engagement"].max())
                        if len(view) else 1,
            format="%d",
            help="Opens + clicks combined. Bar is relative to the "
                    "hottest lead in the current filter."),
    })

# Download filtered list
if len(view) > 0:
    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"Download this list ({len(view):,} rows)",
        data=csv_bytes,
        file_name="warm_leads.csv",
        mime="text/csv",
        key="wl_download")


# ==========================================================================
# Engagement rollup by persona
# ==========================================================================
st.markdown('<h2>Engagement totals by persona</h2>',
             unsafe_allow_html=True)
st.caption("Real per-recipient counts. Not estimates. If Finance and "
            "IT bars are much shorter than Research, that is the "
            "actual gap - not our guess.")

rollup = (df.groupby("persona")
            .agg(leads=("first_name", "count"),
                  opens=("opens", "sum"),
                  clicks=("clicks", "sum"),
                  engagement=("total_engagement", "sum"))
            .reset_index()
            .sort_values("engagement", ascending=False))

header = (
    f'<div style="display:grid;grid-template-columns:'
    f'1.5fr .8fr .8fr .8fr 1fr;gap:.5rem;padding:.5rem .8rem;'
    f'font-size:.72rem;text-transform:uppercase;'
    f'letter-spacing:.12em;color:{MUTED};font-weight:600;'
    f'border-bottom:1px solid {LINE}">'
    f'<div>Persona</div><div>Leads</div><div>Opens</div>'
    f'<div>Clicks</div><div>Engagement</div></div>')
rows_html = [header]
max_eng = rollup["engagement"].max() if len(rollup) else 1
for _, r in rollup.iterrows():
    bar_pct = (r["engagement"] / max_eng * 100) if max_eng else 0
    bar_col = ACCENT if r["persona"] == "Research" else (
        GOLD if r["persona"] == "Finance" else (
            "#7A6A9A" if r["persona"] == "IT-Systems" else MUTED))
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'1.5fr .8fr .8fr .8fr 1fr;gap:.5rem;padding:.55rem .8rem;'
        f'font-size:.9rem;border-bottom:1px solid {LINE};'
        f'align-items:center">'
        f'<div style="color:{INK};font-weight:600">{r["persona"]}</div>'
        f'<div style="color:{INK}">{int(r["leads"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["opens"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["clicks"])}</div>'
        f'<div>'
        f'<div style="display:inline-block;width:60%;height:8px;'
        f'background:{LINE};border-radius:4px;vertical-align:middle;'
        f'margin-right:.5rem"><div style="height:100%;width:{bar_pct}%;'
        f'background:{bar_col};border-radius:4px"></div></div>'
        f'<span style="color:{INK};font-weight:600">'
        f'{int(r["engagement"])}</span></div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)
