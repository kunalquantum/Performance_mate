"""
Persona - Attack list.

The institutions where we have all three personas (Research + Finance +
IT-Systems). These are the ONLY places we can currently hit the full
buying committee in one campaign. This is the outbound priority list.
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, so_what,
                     load_csv, INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Attack list</h1>', unsafe_allow_html=True)
core_question("Which target accounts can we hit the full buying committee at right now, in a single campaign week?")
st.caption("Institutions where we hold ALL THREE personas today - "
            "Research, Finance and IT-Systems. These are the only "
            "accounts where we can hit the full buying committee in "
            "one campaign. Focus outbound here first.")
render_status_key()

with st.expander("Why this list matters", expanded=False):
    st.markdown("""
Grant-management sales works when the whole buying committee sees
the value. If we can only email Research at an institution, we get
Research interest, but Finance and IT still have to be convinced
before a purchase. That takes months and often stalls.

The **attack list** below is every institution where we can email
Research, Finance AND IT-Systems in the same campaign week. That is
where the shortest sales cycles will come from - the committee is
already reachable, we just have to make the case.

Sort by institution size to prioritise biggest first, or by type to
segment the outreach.
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
attack = target[target["personas_held"] >= 3].copy()


# ==========================================================================
# Top-line tiles
# ==========================================================================
n_attack = len(attack)
n_total_target = len(target)
attack_pct = n_attack / max(n_total_target, 1) * 100
attack_contacts = int(attack["contacts"].sum())
attack_valid = int(attack["valid_emails"].sum())
# Avg contacts per attack account
avg_contacts = attack["contacts"].mean() if n_attack else 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Attack-ready institutions",
              f"{n_attack:,}",
              sub=f"{attack_pct:.0f}% of target",
              tooltip="Institutions where we hold all three main "
                      "personas today.",
              color=ACCENT)
with k2:
    kpi_tile("Total contacts",
              f"{attack_contacts:,}",
              sub="across the attack list",
              tooltip="Sum of contacts across every attack-list "
                      "institution.")
with k3:
    valid_pct = attack_valid / max(attack_contacts, 1) * 100
    kpi_tile("Valid emails",
              f"{attack_valid:,}",
              sub=f"{valid_pct:.0f}% deliverable",
              tooltip="Verified emails on the attack list. Only "
                      "these are safe to send to today.",
              color=ACCENT if valid_pct >= 60 else GOLD)
with k4:
    kpi_tile("Avg contacts per account",
              f"{avg_contacts:.0f}",
              tooltip="Average number of contacts across the attack "
                      "list. Higher = deeper coverage per account.")


# ==========================================================================
# Filter + sort
# ==========================================================================
st.markdown('<h2>Filter and sort</h2>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.3, 1.3, 1.4])
with fc1:
    types = sorted([t for t in attack["type"].fillna("Unclassified")
                      .unique() if str(t).strip()])
    pick_types = st.multiselect("Institution type", types,
                                  default=types, key="al_types")
with fc2:
    sort_by = st.selectbox(
        "Sort by",
        ["Biggest first (contacts)",
         "Most valid emails",
         "Deepest research bench",
         "Alphabetical"],
        key="al_sort")
with fc3:
    search = st.text_input("Search institution name",
                             placeholder="e.g. Manchester, Ulster",
                             key="al_search")

view = attack[attack["type"].fillna("Unclassified").isin(pick_types)]
if search:
    view = view[view["institution"].astype(str).str.contains(
        search, case=False, na=False)]

if sort_by == "Biggest first (contacts)":
    view = view.sort_values("contacts", ascending=False)
elif sort_by == "Most valid emails":
    view = view.sort_values("valid_emails", ascending=False)
elif sort_by == "Deepest research bench":
    view = view.sort_values("research", ascending=False)
elif sort_by == "Alphabetical":
    view = view.sort_values("institution")


# ==========================================================================
# The ranked table
# ==========================================================================
st.markdown(f'<h2>{len(view):,} attack-ready accounts</h2>',
             unsafe_allow_html=True)
st.caption("Every row here has Research, Finance AND IT-Systems "
            "contacts. Send a persona-tailored email to each seat in "
            "the same week for the best committee coverage.")

show = view[[
    "institution", "type", "contacts",
    "research", "finance", "it_systems",
    "valid_emails",
]].rename(columns={
    "institution":  "Institution",
    "type":         "Type",
    "contacts":     "Contacts",
    "research":     "Research",
    "finance":      "Finance",
    "it_systems":   "IT-Systems",
    "valid_emails": "Valid emails",
})
st.dataframe(
    show,
    use_container_width=True, hide_index=True, height=520,
    column_config={
        "Contacts":     st.column_config.NumberColumn(format="%d"),
        "Research":     st.column_config.NumberColumn(format="%d"),
        "Finance":      st.column_config.NumberColumn(format="%d"),
        "IT-Systems":   st.column_config.NumberColumn(format="%d"),
        "Valid emails": st.column_config.NumberColumn(format="%d"),
    })


# So-what
if len(view) >= 3:
    top3 = view.head(3)["institution"].tolist()
    so_what(
        f"Top 3 attack accounts by size: "
        f"<strong>{', '.join(top3)}</strong>. Ship "
        f"persona-tailored copy to Research, Finance and IT at each "
        f"of these before ranging wider.", tone="good")

# Download
if len(view) > 0:
    csv_bytes = show.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"Download attack list ({len(view):,} rows)",
        data=csv_bytes,
        file_name="attack_list.csv",
        mime="text/csv",
        key="al_download")


# ==========================================================================
# Drill: pick one, see the per-persona contacts
# ==========================================================================
st.markdown('<h2>Look inside an attack account</h2>',
             unsafe_allow_html=True)
opts = ["-- pick one --"] + view["institution"].astype(str).tolist()
pick = st.selectbox("Institution", opts, key="al_drill")

if pick and pick != "-- pick one --":
    contacts_df = load_csv("persona_contacts_full.csv")
    if not contacts_df.empty:
        row = view[view["institution"] == pick].iloc[0]
        inst_key = str(row["institution_key"])
        sub = contacts_df[
            contacts_df["institution_key"].astype(str) == inst_key].copy()

        # Show per-persona tiles
        dc1, dc2, dc3 = st.columns(3)
        for col, persona_label, persona_val in [
            (dc1, "Research",   "Research"),
            (dc2, "Finance",    "Finance"),
            (dc3, "IT-Systems", "IT/Systems"),
        ]:
            n = int((sub["persona"] == persona_val).sum())
            n_valid = int(((sub["persona"] == persona_val)
                            & (sub["snov_status"].astype(str).str.lower()
                                == "valid")).sum())
            with col:
                kpi_tile(persona_label, f"{n}",
                          sub=f"{n_valid} valid emails",
                          color=ACCENT if n_valid > 0 else GOLD)

        # Contact list
        show_cols = ["first_name", "last_name", "job_title",
                       "persona", "research_tier", "email",
                       "snov_status"]
        show_cols = [c for c in show_cols if c in sub.columns]
        st.dataframe(
            sub[show_cols].rename(columns={
                "first_name":    "First",
                "last_name":     "Last",
                "job_title":     "Job title",
                "persona":       "Persona",
                "research_tier": "Tier",
                "email":         "Email",
                "snov_status":   "Email status",
            }),
            use_container_width=True, hide_index=True, height=340)
