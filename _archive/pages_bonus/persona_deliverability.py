"""
Persona - Deliverability per persona.

For each persona: how many contacts, how many with a verified
deliverable email, and how many still sitting in the verify queue?
The persona with the lowest valid-email share is where verification
investment should go first.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, so_what,
                     load_csv, INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Deliverability by persona</h1>',
             unsafe_allow_html=True)
core_question("Which persona&apos;s emails need verification investment first?")
st.caption("For every persona bucket: how many contacts, how many "
            "with a verified email, how many still need checking. If "
            "one persona is much worse than the others, that is where "
            "verification effort pays off first.")
render_status_key()

with st.expander("What each column means", expanded=False):
    st.markdown("""
- **Contacts** &mdash; UK contacts at target institutions in this
  persona bucket.
- **Valid** &mdash; Snov marked the email deliverable. Safe to send
  to today.
- **Unknown** &mdash; Snov could not verify. Verify before sending.
- **Not valid** &mdash; Snov marked as undeliverable. Do not send.
- **No email** &mdash; row has no email address at all.
- **% valid** &mdash; valid divided by total contacts. Higher =
  more of that persona is reachable today.
""")


contacts = load_csv("persona_contacts_full.csv")
coverage = load_csv("persona_institution_coverage.csv")
if contacts.empty or coverage.empty:
    st.info("No data. Run `python etl/persona_data_etl.py`.")
    st.stop()

# UK contacts at target institutions
target_keys = set(
    coverage[coverage["in_target"].astype(str).str.lower() == "yes"]
    ["institution_key"].dropna().astype(str))
uk = contacts[contacts["country"].astype(str).str.upper() == "UK"]
uk = uk[uk["institution_key"].astype(str).isin(target_keys)].copy()


# ==========================================================================
# Build the per-persona breakdown
# ==========================================================================
def _row(label, mask):
    sub = uk[mask]
    n_total = len(sub)
    ss = sub["snov_status"].astype(str).str.lower()
    n_valid = int((ss == "valid").sum())
    n_unknown = int((ss == "unknown").sum())
    n_not_valid = int((ss == "not valid").sum())
    n_no_email = int(sub["email"].astype(str).str.strip()
                       .isin(["", "nan", "None"]).sum())
    n_other = max(0, n_total - n_valid - n_unknown - n_not_valid - n_no_email)
    pct_valid = n_valid / max(n_total, 1) * 100
    return {
        "Persona":   label,
        "Contacts":  n_total,
        "Valid":     n_valid,
        "Unknown":   n_unknown,
        "Not valid": n_not_valid,
        "No email":  n_no_email,
        "Other":     n_other,
        "pct_valid": pct_valid,
    }


rows = [
    _row("Research - total",     uk["persona"] == "Research"),
    _row("  Senior / executive",
          (uk["persona"] == "Research")
          & (uk["research_tier"].astype(str) == "Senior")),
    _row("  Operational",
          (uk["persona"] == "Research")
          & (uk["research_tier"].astype(str) == "Operational")),
    _row("  Academic",
          (uk["persona"] == "Research")
          & (uk["research_tier"].astype(str) == "Academic")),
    _row("Finance",              uk["persona"] == "Finance"),
    _row("IT-Systems",           uk["persona"] == "IT/Systems"),
]


# ==========================================================================
# Top-line tiles
# ==========================================================================
_top_rows = [r for r in rows if not r["Persona"].startswith(" ")
              and r["Contacts"] > 0]
best = max(_top_rows, key=lambda r: r["pct_valid"]) if _top_rows else None
worst = min(_top_rows, key=lambda r: r["pct_valid"]) if _top_rows else None
total_valid = sum(r["Valid"] for r in _top_rows)
total_unknown = sum(r["Unknown"] for r in _top_rows)

k1, k2, k3, k4 = st.columns(4)
with k1:
    if best is not None:
        kpi_tile("Best-verified persona",
                  f"{best['pct_valid']:.0f}%",
                  sub=best["Persona"],
                  color=ACCENT,
                  tooltip="Persona bucket with the highest share of "
                          "verified emails.")
with k2:
    if worst is not None:
        kpi_tile("Worst-verified persona",
                  f"{worst['pct_valid']:.0f}%",
                  sub=worst["Persona"],
                  color=GOLD if worst['pct_valid'] < 60 else ACCENT,
                  tooltip="Persona bucket with the lowest share of "
                          "verified emails. Verify these first.")
with k3:
    kpi_tile("Total valid emails",
              f"{total_valid:,}",
              tooltip="Sum of verified emails across the three main "
                      "personas.",
              color=ACCENT)
with k4:
    kpi_tile("Sitting in verify queue",
              f"{total_unknown:,}",
              sub="unknown status",
              tooltip="Contacts where Snov could not verify. "
                      "Clearing these grows the reachable list.",
              color=GOLD if total_unknown >= 500 else ACCENT)


# ==========================================================================
# Table with coloured % valid cells
# ==========================================================================
st.markdown('<h2>Deliverability breakdown</h2>', unsafe_allow_html=True)
st.caption("Only UK contacts at target institutions. Research is "
            "split into senior / operational / academic.")

header = (
    f'<div style="display:grid;grid-template-columns:'
    f'2fr .8fr .8fr .9fr .9fr .8fr 1fr;gap:.4rem;'
    f'padding:.5rem .7rem;font-size:.72rem;'
    f'text-transform:uppercase;letter-spacing:.12em;color:{MUTED};'
    f'font-weight:600;border-bottom:1px solid {LINE}">'
    f'<div>Persona</div><div>Contacts</div><div>Valid</div>'
    f'<div>Unknown</div><div>Not valid</div><div>No email</div>'
    f'<div>% valid</div></div>')

rows_html = [header]
for r in rows:
    indent = ("&nbsp;&nbsp;&nbsp;&nbsp;"
                if r["Persona"].startswith(" ") else "")
    label = r["Persona"].strip()
    p = r["pct_valid"]
    bg = ("#DDEEEC" if p >= 65 else
            "#F7F0DA" if p >= 45 else "#FBEDED")
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'2fr .8fr .8fr .9fr .9fr .8fr 1fr;gap:.4rem;'
        f'padding:.55rem .7rem;font-size:.9rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        f'<div style="color:{INK};font-weight:600">{indent}{label}</div>'
        f'<div style="color:{INK}">{r["Contacts"]:,}</div>'
        f'<div style="color:{ACCENT};font-weight:600">'
        f'{r["Valid"]:,}</div>'
        f'<div style="color:{GOLD}">{r["Unknown"]:,}</div>'
        f'<div style="color:{WARN}">{r["Not valid"]:,}</div>'
        f'<div style="color:{MUTED}">{r["No email"]:,}</div>'
        f'<div style="background:{bg};padding:.15rem .4rem;'
        f'border-radius:4px;color:{INK};font-weight:700">'
        f'{p:.0f}%</div></div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)

# So-what
if _top_rows:
    spread = best["pct_valid"] - worst["pct_valid"]
    if spread >= 10:
        so_what(
            f"<strong>{best['Persona']}</strong> is at "
            f"{best['pct_valid']:.0f}% valid; "
            f"<strong>{worst['Persona']}</strong> is at "
            f"{worst['pct_valid']:.0f}%. That is a "
            f"{spread:.0f}-point gap. Verify the "
            f"{worst['Unknown']:,} unknown emails in "
            f"{worst['Persona']} first - biggest single lift.",
            tone="warn")
    else:
        so_what(
            f"All three personas sit within {spread:.0f} points of "
            f"each other on % valid. Deliverability effort should "
            f"be spread evenly across personas.",
            tone="info")


# ==========================================================================
# Drill: pick a persona, see the unknown queue for it
# ==========================================================================
st.markdown('<h2>Verify queue drill</h2>', unsafe_allow_html=True)
persona_pick = st.selectbox(
    "Pick a persona to see its unknown-email queue",
    ["Research", "Finance", "IT/Systems"],
    key="dv_persona")

queue = uk[
    (uk["persona"] == persona_pick)
    & (uk["snov_status"].astype(str).str.lower() == "unknown")].copy()

st.caption(f"{len(queue):,} contacts in {persona_pick} with unknown "
            "email status. Send these to Snov to verify.")

if len(queue) > 0:
    # Group by institution so we can prioritise verification runs
    grp = (queue.groupby("company")
                 .size().reset_index(name="unverified")
                 .sort_values("unverified", ascending=False))
    top20 = grp.head(20)
    st.markdown('<div class="eyebrow" style="margin-top:.8rem">'
                'Top institutions by verify-queue size</div>',
                unsafe_allow_html=True)
    st.dataframe(top20.rename(columns={
        "company": "Institution",
        "unverified": "Unknown emails",
    }), use_container_width=True, hide_index=True, height=350,
        column_config={
            "Unknown emails":
                st.column_config.NumberColumn(format="%d"),
        })

    # Download
    cols_show = ["first_name", "last_name", "job_title", "company",
                   "email", "research_tier"]
    cols_show = [c for c in cols_show if c in queue.columns]
    csv_bytes = queue[cols_show].rename(columns={
        "first_name":    "First",
        "last_name":     "Last",
        "job_title":     "Job title",
        "company":       "Institution",
        "email":         "Email",
        "research_tier": "Tier",
    }).to_csv(index=False).encode("utf-8")
    st.download_button(
        f"Download {persona_pick} verify list ({len(queue):,} rows)",
        data=csv_bytes,
        file_name=f"verify_{persona_pick.lower().replace('/', '_')}.csv",
        mime="text/csv",
        key="dv_download")
