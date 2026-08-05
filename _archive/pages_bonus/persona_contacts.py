"""
Persona - Contact directory.

Every contact in the audit, filterable by CRM status, persona,
institution, country and email validity. Table-first, no charts.
Designed for the sales director / SDR who wants to answer:
&ldquo;who at Manchester is a valid Research contact and in our CRM?&rdquo;
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Contact directory</h1>', unsafe_allow_html=True)
core_question("Who exactly is in our list, and how do I find the right person by name, title or institution?")
st.caption("Every contact in the audit. Split by CRM status. Search "
            "and filter to find who to reach next.")
render_status_key()

with st.expander("What the CRM buckets mean", expanded=False):
    st.markdown("""
- **In CRM valid** &mdash; already in the ZOHO CRM AND has a
  verified email. Highest-confidence group.
- **In CRM unknown** &mdash; in the CRM, but email deliverability
  is unknown. Verify before sending.
- **In NOW CRM valid** &mdash; more recent additions to the CRM,
  with a verified email.
- **In NOW CRM unknown** &mdash; recent additions with unknown
  email status.
- **Not CRM not valid** &mdash; not in the CRM AND the email
  bounced or is undeliverable. Skip unless you can find a new
  email.
- **In CRM not valid** &mdash; in the CRM but email is undeliverable.
  Either update the record or drop it.
""")


df = load_csv("persona_contacts_full.csv")
if df.empty:
    st.info("No contacts data. Run "
             "`python etl/persona_data_etl.py`.")
    st.stop()


# ==========================================================================
# Bucket tiles - one KPI per CRM bucket
# ==========================================================================
bucket_counts = df["bucket"].value_counts()
bucket_order = ["In CRM valid", "In NOW CRM valid",
                  "In CRM unknown", "In NOW CRM unknown",
                  "Not CRM not valid", "In CRM not valid"]
bucket_meta = {
    "In CRM valid":       ("Highest confidence", ACCENT),
    "In NOW CRM valid":   ("Recent + valid",     ACCENT),
    "In CRM unknown":     ("Verify first",       GOLD),
    "In NOW CRM unknown": ("Verify first",       GOLD),
    "Not CRM not valid":  ("Skip / rework",      WARN),
    "In CRM not valid":   ("Update or drop",     WARN),
}

# Row 1 of tiles
r1 = st.columns(3)
r2 = st.columns(3)
for i, name in enumerate(bucket_order):
    count = int(bucket_counts.get(name, 0))
    sub, colour = bucket_meta.get(name, ("", ACCENT))
    target_col = r1[i] if i < 3 else r2[i - 3]
    with target_col:
        kpi_tile(name, f"{count:,}", sub=sub,
                  color=colour,
                  tooltip=f"Contacts in the &lsquo;{name}&rsquo; "
                          f"bucket.")


# ==========================================================================
# Filter panel
# ==========================================================================
st.markdown('<h2>Filter and search</h2>', unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns([1.5, 1.2, 1.2])
with fc1:
    all_buckets = bucket_order
    pick_bucket = st.multiselect(
        "CRM bucket", all_buckets,
        default=["In CRM valid", "In NOW CRM valid"],
        key="dir_bucket",
        help="Pick one or more CRM buckets to include. Defaults to "
                "the two valid buckets - the ones you can email today.")
with fc2:
    personas = sorted([p for p in df["persona"].dropna()
                         .astype(str).unique() if p and p != "nan"])
    pick_persona = st.multiselect(
        "Persona", personas,
        default=personas,
        key="dir_persona")
with fc3:
    countries = sorted([c for c in df["country"].dropna()
                          .astype(str).unique() if c and c != "nan"])
    default_country = ["UK"] if "UK" in countries else countries[:1]
    pick_country = st.multiselect(
        "Country", countries,
        default=default_country,
        key="dir_country")

fc4, fc5 = st.columns([2, 1])
with fc4:
    search = st.text_input(
        "Search name, job title, institution or email",
        placeholder="e.g. Head of Research, Manchester, .ac.uk",
        key="dir_search")
with fc5:
    only_verified = st.toggle(
        "Verified email only", value=True,
        key="dir_verified",
        help="Restrict to rows where Snov marked the email valid.")


# Apply filters
view = df.copy()
if pick_bucket:
    view = view[view["bucket"].isin(pick_bucket)]
if pick_persona:
    view = view[view["persona"].astype(str).isin(pick_persona)]
if pick_country:
    view = view[view["country"].astype(str).isin(pick_country)]
if only_verified and "snov_status" in view.columns:
    view = view[view["snov_status"].astype(str).str.lower() == "valid"]
if search:
    mask = pd.Series(False, index=view.index)
    for col in ("first_name", "last_name", "job_title",
                  "company", "email"):
        if col in view.columns:
            mask = mask | view[col].astype(str).str.contains(
                search, case=False, na=False)
    view = view[mask]


# ==========================================================================
# Results
# ==========================================================================
st.markdown('<h2>Contacts</h2>', unsafe_allow_html=True)
st.caption(f"Showing {len(view):,} of {len(df):,} contacts.")

# Columns to show (only those present)
_col_map = {
    "first_name":    "First name",
    "last_name":     "Last name",
    "job_title":     "Job title",
    "company":       "Institution",
    "country":       "Country",
    "email":         "Email",
    "persona":       "Persona",
    "band":          "Band",
    "snov_status":   "Email status",
    "bucket":        "CRM bucket",
}
show_cols = [c for c in _col_map if c in view.columns]
display = view[show_cols].rename(columns=_col_map)
st.dataframe(display, use_container_width=True, hide_index=True,
              height=500)


# ==========================================================================
# Export
# ==========================================================================
if len(view) > 0:
    csv_bytes = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"Download this filtered list ({len(view):,} rows)",
        data=csv_bytes,
        file_name="filtered_contacts.csv",
        mime="text/csv")


st.markdown(
    f'<div style="margin-top:2.5rem;color:{MUTED};font-size:.75rem">'
    f'Data source: <code>data/persona_contacts_full.csv</code>. Rerun '
    f'<code>python etl/persona_data_etl.py</code> to refresh from '
    f'the source workbook.</div>',
    unsafe_allow_html=True)
