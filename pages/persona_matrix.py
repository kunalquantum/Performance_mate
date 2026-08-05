"""
Persona - UK Persona & Audience Matrix.

The summary Ian asked for. Answers four questions in one page:

  1. How many UK universities are in scope, and how many do we have
     contacts for?
  2. How many contacts do we hold per persona (Research split into
     Senior / Operational / Academic)?
  3. Where are the persona gaps?
  4. How valid are the email addresses on the list?

Table-first. No line charts. Every number tied back to a single
underlying CSV so it stays honest as the source data changes.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>UK Persona &amp; Audience Matrix</h1>',
             unsafe_allow_html=True)
core_question("Where is our UK persona coverage strong, and where are the gaps we need to close?")
st.caption("The summary Ian asked for. Every number comes straight "
            "from the Contact Audit workbook via "
            "`etl/persona_data_etl.py`. If a figure looks off, fix "
            "the source spreadsheet and rerun the ETL.")
render_status_key()

with st.expander("What this page shows", expanded=False):
    st.markdown("""
- **Institution coverage** &mdash; how much of the UK target list we
  have contacts for.
- **Contacts by persona** &mdash; how many people we hold in each of
  the three persona buckets (Research, Finance, IT-Systems), with
  Research broken into Senior/executive, Operational and Academic.
- **Persona gaps** &mdash; how many institutions cover all three
  personas vs one or two vs none, and where the biggest holes are.
- **Email validity** &mdash; how many of the emails on the list are
  actually deliverable.

**The long-term goal**: for every relevant UK institution, we hold
every persona with a valid up-to-date email. This page shows the gap
between today and that goal.
""")


coverage = load_csv("persona_institution_coverage.csv")
contacts = load_csv("persona_contacts_full.csv")
if coverage.empty or contacts.empty:
    st.info("Persona data not loaded. Run "
             "`python etl/persona_data_etl.py`.")
    st.stop()

# Restrict to the UK target list
target = coverage[
    coverage["in_target"].astype(str).str.lower() == "yes"].copy()
target_keys = set(target["institution_key"].dropna().astype(str))

uk_contacts = contacts[
    contacts["country"].astype(str).str.upper() == "UK"].copy()
uk_target_contacts = uk_contacts[
    uk_contacts["institution_key"].astype(str).isin(target_keys)].copy()


# ==========================================================================
# 1. INSTITUTION COVERAGE
# ==========================================================================
st.markdown('<h2>Institution coverage</h2>', unsafe_allow_html=True)
st.caption("The size of the target list and how much of it we have "
            "contact data for.")

n_target        = len(target)
n_with_contacts = int((target["contacts"].fillna(0) > 0).sum())
n_no_contacts   = n_target - n_with_contacts
coverage_pct    = n_with_contacts / max(n_target, 1) * 100
n_unclassified  = int((coverage["in_target"].astype(str).str.lower()
                        .isin(["nan", "", "none"])).sum())

ic1, ic2, ic3, ic4 = st.columns(4)
with ic1:
    kpi_tile("Relevant UK institutions", f"{n_target:,}",
              sub="on the target list",
              tooltip="Institutions marked &lsquo;Yes&rsquo; in the "
                      "target list column of the source workbook.")
with ic2:
    kpi_tile("Have contact data",
              f"{n_with_contacts:,}",
              sub=f"{coverage_pct:.0f}% of target",
              tooltip="Target institutions where we hold at least "
                      "one contact.",
              color=ACCENT if coverage_pct >= 80 else GOLD)
with ic3:
    kpi_tile("No contacts at all", f"{n_no_contacts:,}",
              tooltip="Target institutions where we hold zero "
                      "contacts. First step is to add any contact.",
              color=WARN if n_no_contacts >= 20 else GOLD)
with ic4:
    kpi_tile("Still to classify", f"{n_unclassified:,}",
              sub="target Yes/No not set",
              tooltip="Institutions where we have not yet decided "
                      "if they belong on the target list. Fill "
                      "column D in the source workbook.")


# ==========================================================================
# 2. CONTACTS BY PERSONA (with Research broken down)
# ==========================================================================
st.markdown('<h2>Contacts by persona</h2>', unsafe_allow_html=True)
st.caption("Only counting UK contacts inside target institutions. "
            "Research is split into senior/executive, operational, "
            "and academic. &lsquo;% of target&rsquo; = fraction of "
            "the target institution list where we hold at least one "
            "contact in that persona bucket.")


def _persona_row(label, mask):
    sub = uk_target_contacts[mask]
    n_contacts = len(sub)
    n_institutions = sub["institution_key"].dropna().nunique()
    n_valid = int((sub["snov_status"].astype(str).str.lower()
                    == "valid").sum())
    pct_target = n_institutions / max(n_target, 1) * 100
    return {
        "Persona":         label,
        "Contacts":        n_contacts,
        "Institutions":    n_institutions,
        "% of target":     pct_target,
        "Valid emails":    n_valid,
    }


research_mask   = uk_target_contacts["persona"] == "Research"
finance_mask    = uk_target_contacts["persona"] == "Finance"
it_mask         = uk_target_contacts["persona"] == "IT/Systems"
unclass_mask    = uk_target_contacts["persona"].astype(str).isin(
    ["Other / not targeted", "nan", ""])

tier_col = uk_target_contacts["research_tier"].astype(str)
senior_mask     = research_mask & (tier_col == "Senior")
operational_mask= research_mask & (tier_col == "Operational")
academic_mask   = research_mask & (tier_col == "Academic")

rows = [
    _persona_row("Research - total",             research_mask),
    _persona_row("  Senior / executive",         senior_mask),
    _persona_row("  Operational",                operational_mask),
    _persona_row("  Academic",                   academic_mask),
    _persona_row("Finance",                      finance_mask),
    _persona_row("IT-Systems",                   it_mask),
    _persona_row("Other / not targeted",         unclass_mask),
]

# Render as a coloured HTML table (Streamlit dataframe cannot colour
# per-cell without pandas Styler which is fussy inside our layout)
header_html = (
    f'<div style="display:grid;grid-template-columns:'
    f'2fr 1fr 1fr 1fr 1fr;gap:.5rem;padding:.5rem .8rem;'
    f'font-size:.72rem;text-transform:uppercase;'
    f'letter-spacing:.12em;color:{MUTED};font-weight:600;'
    f'border-bottom:1px solid {LINE}">'
    f'<div>Persona</div><div>Contacts</div><div>Institutions</div>'
    f'<div>% of target</div><div>Valid emails</div></div>')
body_html = []
for r in rows:
    indent = "&nbsp;&nbsp;&nbsp;&nbsp;" if r["Persona"].startswith("  ") \
        else ""
    label = r["Persona"].strip()
    pct = r["% of target"]
    pct_bg = ("#DDEEEC" if pct >= 70 else
                "#F7F0DA" if pct >= 40 else "#FBEDED")
    pct_col = INK
    body_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'2fr 1fr 1fr 1fr 1fr;gap:.5rem;padding:.55rem .8rem;'
        f'font-size:.9rem;border-bottom:1px solid {LINE};'
        f'align-items:center">'
        f'<div style="color:{INK};font-weight:600">{indent}{label}</div>'
        f'<div style="color:{INK}">{r["Contacts"]:,}</div>'
        f'<div style="color:{INK_SOFT}">{r["Institutions"]:,}</div>'
        f'<div style="background:{pct_bg};padding:.15rem .4rem;'
        f'border-radius:4px;color:{pct_col};font-weight:600">'
        f'{pct:.0f}%</div>'
        f'<div style="color:{INK_SOFT}">{r["Valid emails"]:,}</div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">'
    f'{header_html}{"".join(body_html)}</div>',
    unsafe_allow_html=True)

# Totals row
total_contacts = len(uk_target_contacts)
total_valid    = int((uk_target_contacts["snov_status"].astype(str)
                        .str.lower() == "valid").sum())
tc1, tc2 = st.columns(2)
with tc1:
    kpi_tile("All UK contacts at target institutions",
              f"{total_contacts:,}",
              tooltip="Every contact in every persona bucket, "
                      "including unclassified.")
with tc2:
    valid_pct = total_valid / max(total_contacts, 1) * 100
    kpi_tile("Verified valid emails among them",
              f"{total_valid:,}",
              sub=f"{valid_pct:.0f}% of {total_contacts:,}",
              color=ACCENT if valid_pct >= 60 else GOLD,
              tooltip="Contacts where Snov marked the email valid. "
                      "These are the only ones safe to send to "
                      "today.")


# ==========================================================================
# 3. PERSONA GAPS
# ==========================================================================
st.markdown('<h2>Persona gaps</h2>', unsafe_allow_html=True)
st.caption("Coverage completeness across the three main personas "
            "(Research, Finance, IT-Systems). The long-term goal is "
            "&ldquo;all three at every target institution&rdquo;.")

# personas_held from the coverage sheet is calculated across the three
# main persona buckets already
n_all_three = int((target["personas_held"] >= 3).sum())
n_two       = int((target["personas_held"] == 2).sum())
n_one       = int((target["personas_held"] == 1).sum())
n_zero      = int((target["personas_held"] == 0).sum())
avg_personas = float(target["personas_held"].mean())

no_research  = int(((target["research"].fillna(0)   == 0)
                     & (target["contacts"].fillna(0) > 0)).sum())
no_finance   = int(((target["finance"].fillna(0)    == 0)
                     & (target["contacts"].fillna(0) > 0)).sum())
no_it        = int(((target["it_systems"].fillna(0) == 0)
                     & (target["contacts"].fillna(0) > 0)).sum())

pg1, pg2, pg3, pg4 = st.columns(4)
with pg1:
    kpi_tile("Complete coverage", f"{n_all_three:,}",
              sub="all 3 personas",
              tooltip="Institutions where we cover Research, Finance "
                      "AND IT-Systems.",
              color=ACCENT)
with pg2:
    kpi_tile("Two personas held", f"{n_two:,}",
              tooltip="One persona missing at this institution.")
with pg3:
    kpi_tile("One persona held", f"{n_one:,}",
              tooltip="Two personas missing.",
              color=GOLD)
with pg4:
    kpi_tile("Avg personas per institution",
              f"{avg_personas:.2f}",
              sub="out of 3.0",
              tooltip="Average number of the three main personas "
                      "held per target institution.")

gap_rows = [
    ("No Research contact",   no_research),
    ("No Finance contact",    no_finance),
    ("No IT-Systems contact", no_it),
]
st.markdown('<div class="eyebrow" style="margin-top:1rem">'
             'Where the holes are</div>',
             unsafe_allow_html=True)
for label, count in gap_rows:
    bar_pct = count / max(n_target, 1) * 100
    bar_col = WARN if count >= 100 else GOLD if count >= 30 else ACCENT
    st.markdown(
        f'<div style="margin:.5rem 0">'
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:.88rem;margin-bottom:.2rem">'
        f'<span style="color:{INK};font-weight:600">{label}</span>'
        f'<span style="color:{INK_SOFT}">'
        f'<strong>{count}</strong> of {n_target} target institutions '
        f'({bar_pct:.0f}%)</span>'
        f'</div>'
        f'<div style="height:8px;background:{LINE};'
        f'border-radius:4px;overflow:hidden">'
        f'<div style="height:100%;width:{bar_pct}%;background:{bar_col}">'
        f'</div></div></div>',
        unsafe_allow_html=True)


# ==========================================================================
# 4. EMAIL VALIDITY
# ==========================================================================
st.markdown('<h2>Are the emails current and valid?</h2>',
             unsafe_allow_html=True)
st.caption("Deliverability check on every UK contact at a target "
            "institution. Bounce risk sits mostly in &lsquo;not "
            "valid&rsquo; and &lsquo;unknown&rsquo;.")

_ss = uk_target_contacts["snov_status"].astype(str).str.lower()
n_valid     = int((_ss == "valid").sum())
n_unknown   = int((_ss == "unknown").sum())
n_not_valid = int((_ss == "not valid").sum())
n_no_email  = int(uk_target_contacts["email"].astype(str).str.strip()
                    .isin(["", "nan", "None"]).sum())
n_other     = total_contacts - n_valid - n_unknown - n_not_valid - n_no_email
n_other     = max(0, n_other)

ev1, ev2, ev3, ev4, ev5 = st.columns(5)
with ev1:
    kpi_tile("Verified valid", f"{n_valid:,}",
              tooltip="Snov marked the address deliverable.",
              color=ACCENT)
with ev2:
    kpi_tile("Unknown", f"{n_unknown:,}",
              tooltip="Snov could not verify. Should be verified "
                      "before a send.",
              color=GOLD)
with ev3:
    kpi_tile("Not valid", f"{n_not_valid:,}",
              tooltip="Snov marked as undeliverable. Do not send.",
              color=WARN)
with ev4:
    kpi_tile("No status recorded", f"{n_other:,}",
              tooltip="No Snov status set on the row.")
with ev5:
    kpi_tile("No email address", f"{n_no_email:,}",
              tooltip="Row has no email at all - find one before "
                      "trying to contact.")


# Email activity lives on its own page (Persona -> Monthly report) so
# the matrix stays focused on the coverage story.
st.markdown(
    f'<div style="margin-top:2rem;color:{INK_SOFT};font-size:.9rem;'
    f'padding:.8rem 1rem;background:{BG_SOFT};border-radius:6px">'
    f'Looking for the persona email cadence and monthly targets? '
    f'That lives on the <strong>Monthly report</strong> page in the '
    f'Persona group.</div>', unsafe_allow_html=True)
