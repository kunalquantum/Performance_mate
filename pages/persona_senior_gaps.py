"""
Persona - Senior gaps.

Which universities do we hold a senior leadership contact for, and
where are the gaps?

Every contact is scored against Ian's 583-title master list
(senior_titles.py) and folded into the three persona umbrellas:
    Research  ·  Finance  ·  IT-Systems.

The page reads the same three-persona palette the rest of the app
uses so Senior gaps stays aligned with Persona Matrix, Content x
Persona and Monthly report.
"""
from shared import (core_question, inject_css, kpi_tile, so_what,
                     load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
from senior_titles import (classify_title, PERSONA_ORDER,
                             SENIOR_TITLES, CATEGORY_TO_PERSONA,
                             SECONDARY_OVERRIDES)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
             unsafe_allow_html=True)
st.markdown('<h1>Senior gaps</h1>', unsafe_allow_html=True)
core_question("Which universities do we hold a senior leadership "
                "contact for &mdash; Research, Finance and "
                "IT-Systems &mdash; and where are the gaps?")
st.caption("Every contact is matched against Ian's 583-title master "
            "list (v7) and folded into the three persona umbrellas.")


PERSONA_COL = {"Research": ACCENT, "Finance": GOLD,
                "IT-Systems": "#7A6A9A"}


# ==========================================================================
# Load data
# ==========================================================================
contacts = load_csv("persona_contacts_full.csv")
coverage = load_csv("persona_institution_coverage.csv")
if contacts.empty or coverage.empty:
    st.info("Missing `persona_contacts_full.csv` or "
             "`persona_institution_coverage.csv`.")
    st.stop()


# ==========================================================================
# Classify every contact against the umbrella persona
# ==========================================================================
def _persona(t):
    p, _ = classify_title(t)
    return p


contacts["_persona"] = contacts["job_title"].apply(_persona)
seniors = contacts[contacts["_persona"].notna()].copy()

uni_cov = coverage[coverage["type"].astype(str).str.lower()
                     .str.contains("univ", na=False)].copy()
total_uni = len(uni_cov)

# Build per-institution senior map:
#   {institution_key: {persona: [{"name","title"} ...]}}
per_inst = {}
for _, r in seniors.iterrows():
    key = str(r.get("institution_key", "")).strip().lower()
    if not key:
        continue
    persona = r["_persona"]
    name = f'{str(r.get("first_name","")).strip()} ' \
           f'{str(r.get("last_name","")).strip()}'.strip()
    if not name:
        continue
    per_inst.setdefault(key, {}).setdefault(persona, []).append({
        "name":  name,
        "title": str(r.get("job_title", "")).strip(),
    })


# ==========================================================================
# Headline coverage tiles (3 personas + no-signal)
# ==========================================================================
def _uni_with(persona):
    return sum(
        1 for _, r in uni_cov.iterrows()
        if per_inst.get(str(r["institution_key"]).strip().lower(),
                          {}).get(persona))


n_any = sum(
    1 for _, r in uni_cov.iterrows()
    if per_inst.get(str(r["institution_key"]).strip().lower()))
n_research = _uni_with("Research")
n_finance = _uni_with("Finance")
n_it = _uni_with("IT-Systems")
n_all_three = sum(
    1 for _, r in uni_cov.iterrows()
    if all(per_inst.get(str(r["institution_key"]).strip().lower(),
                          {}).get(p) for p in PERSONA_ORDER))
n_no_senior = total_uni - n_any
total_seniors = len(seniors)


k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("UK universities", f"{total_uni}",
              sub="from the coverage workbook")
with k2:
    kpi_tile("Any senior on file",
              f"{n_any}",
              sub=f"{n_any/max(total_uni,1)*100:.0f}% covered",
              color=ACCENT if n_any / max(total_uni, 1) >= 0.5
                    else GOLD)
with k3:
    kpi_tile("All three personas covered",
              f"{n_all_three}",
              sub="Research + Finance + IT-Systems",
              color=ACCENT if n_all_three >= total_uni * 0.5
                    else GOLD if n_all_three >= total_uni * 0.25
                    else WARN)
with k4:
    kpi_tile("No senior at all",
              f"{n_no_senior}",
              sub=f"{n_no_senior/max(total_uni,1)*100:.0f}% full gap",
              color=WARN if n_no_senior / max(total_uni, 1) >= 0.3
                    else GOLD)

so_what(
    f"Of <strong>{total_uni}</strong> UK universities: "
    f"<strong>{n_research}</strong> have a Research senior, "
    f"<strong>{n_finance}</strong> a Finance senior, "
    f"<strong>{n_it}</strong> an IT-Systems senior. "
    f"<strong>{n_all_three}</strong> hold all three &mdash; the "
    f"complete-buying-committee shortlist. "
    f"<strong>{total_seniors}</strong> people across the estate "
    f"match one of the 583 senior titles.",
    tone="info")


# ==========================================================================
# Coverage strip - one tile per persona
# ==========================================================================
st.markdown('<h2>Coverage by persona</h2>', unsafe_allow_html=True)
cols = st.columns(len(PERSONA_ORDER))
for col, persona in zip(cols, PERSONA_ORDER):
    n_uni = _uni_with(persona)
    n_contacts = int((seniors["_persona"] == persona).sum())
    pct = n_uni / max(total_uni, 1) * 100
    with col:
        st.markdown(
            f'<div style="border:1px solid {LINE};border-top:4px solid '
            f'{PERSONA_COL[persona]};border-radius:8px;'
            f'padding:.9rem 1rem;background:{BG};height:100%">'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.14em">'
            f'{persona} seniors</div>'
            f'<div style="font-size:1.8rem;font-weight:700;'
            f'color:{PERSONA_COL[persona]};margin:.2rem 0 .1rem">'
            f'{n_uni}</div>'
            f'<div style="font-size:.78rem;color:{INK_SOFT}">'
            f'{pct:.0f}% of universities covered</div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'margin-top:.4rem">{n_contacts} people</div></div>',
            unsafe_allow_html=True)


# ==========================================================================
# Filter
# ==========================================================================
st.markdown('<h2 style="margin-top:1.5rem">Every university &mdash; '
             'senior coverage</h2>', unsafe_allow_html=True)
st.caption("One row per university. Green pill = we hold that "
            "persona. Red pill = gap.")

fc1, fc2, fc3 = st.columns([1.3, 1.3, 1])
with fc1:
    view_filter = st.selectbox(
        "Show",
        ["All universities",
         "Missing Research", "Missing Finance", "Missing IT-Systems",
         "Missing all three",
         "Has all three"],
        key="sg_filter")
with fc2:
    search = st.text_input("Search university name",
                             key="sg_search",
                             placeholder="e.g. Oxford, Manchester")
with fc3:
    sort_by = st.selectbox("Sort by",
                             ["Gaps first",
                              "Coverage first",
                              "Name (A-Z)"],
                             key="sg_sort")


# Build display frame
rows = []
for _, r in uni_cov.iterrows():
    key = str(r["institution_key"]).strip().lower()
    inst_name = str(r.get("institution") or r["institution_key"])
    senior_map = per_inst.get(key, {})
    row = {"University": inst_name, "_key": key}
    n_covered = 0
    for persona in PERSONA_ORDER:
        entries = senior_map.get(persona, [])
        row[persona] = entries
        if entries:
            n_covered += 1
    row["_covered"] = n_covered
    row["_all_three"] = n_covered == 3
    row["_none"] = n_covered == 0
    rows.append(row)
df = pd.DataFrame(rows)

view = df.copy()
if view_filter == "Missing Research":
    view = view[view["Research"].apply(lambda x: not x)]
elif view_filter == "Missing Finance":
    view = view[view["Finance"].apply(lambda x: not x)]
elif view_filter == "Missing IT-Systems":
    view = view[view["IT-Systems"].apply(lambda x: not x)]
elif view_filter == "Missing all three":
    view = view[view["_none"]]
elif view_filter == "Has all three":
    view = view[view["_all_three"]]

if search.strip():
    q = search.strip().lower()
    view = view[view["University"].astype(str).str.lower()
                  .str.contains(q, na=False)]

if sort_by == "Gaps first":
    view = view.sort_values(["_covered", "University"],
                              ascending=[True, True])
elif sort_by == "Coverage first":
    view = view.sort_values(["_covered", "University"],
                              ascending=[False, True])
else:
    view = view.sort_values("University")

st.caption(f"Showing **{len(view)}** of {total_uni} universities.")


# ==========================================================================
# Table
# ==========================================================================
def _cell(entries, colour):
    if not entries:
        return (f'<div style="background:#FBEDED;color:{WARN};'
                f'padding:.2rem .4rem;border-radius:3px;'
                f'font-size:.72rem;font-weight:700;text-align:center">'
                f'gap</div>')
    top = entries[0]
    extra = (f' <span style="color:{MUTED};font-weight:400">'
             f'+{len(entries)-1} more</span>' if len(entries) > 1 else "")
    return (
        f'<div style="background:{colour}18;'
        f'border-left:3px solid {colour};padding:.3rem .55rem;'
        f'border-radius:2px;font-size:.8rem;line-height:1.35">'
        f'<div style="color:{INK};font-weight:600">'
        f'{top["name"]}{extra}</div>'
        f'<div style="color:{MUTED};font-size:.7rem">'
        f'{top["title"][:52]}</div></div>')


grid = "1.8fr 1.5fr 1.5fr 1.5fr .6fr"
hdr_cells = ['<div>University</div>'] + [
    f'<div>{p}</div>' for p in PERSONA_ORDER
] + ['<div style="text-align:center">Score</div>']
header = (
    f'<div style="display:grid;grid-template-columns:{grid};gap:.5rem;'
    f'padding:.55rem .85rem;font-size:.68rem;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.11em;font-weight:600;'
    f'border-bottom:1px solid {LINE};background:{BG_SOFT}">'
    + "".join(hdr_cells) + '</div>')

rows_html = [header]
for _, r in view.iterrows():
    covered = int(r["_covered"])
    score_col = (ACCENT if covered == 3 else GOLD if covered >= 1
                    else WARN)
    cells = [f'<div style="color:{INK};font-weight:600;line-height:1.3">'
             f'{r["University"]}</div>']
    for persona in PERSONA_ORDER:
        cells.append(f'<div>{_cell(r[persona], PERSONA_COL[persona])}</div>')
    cells.append(
        f'<div style="text-align:center;background:{score_col}22;'
        f'color:{INK};font-weight:700;padding:.2rem;'
        f'border-radius:3px;font-size:.85rem">{covered}/3</div>')
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:{grid};'
        f'gap:.5rem;padding:.6rem .85rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        + "".join(cells) + '</div>')

st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)


# ==========================================================================
# Download
# ==========================================================================
csv_df = view[["University"] + list(PERSONA_ORDER)].copy()
for persona in PERSONA_ORDER:
    csv_df[persona] = csv_df[persona].apply(
        lambda es: "; ".join(f'{e["name"]} ({e["title"]})' for e in es)
        if es else "")
st.download_button(
    "Download this list as CSV",
    csv_df.to_csv(index=False).encode("utf-8"),
    file_name="senior_gaps.csv", mime="text/csv")


# ==========================================================================
# Coverage-depth strip
# ==========================================================================
st.markdown('<h2>Coverage depth across the estate</h2>',
             unsafe_allow_html=True)
st.caption("How many of the three personas each university has at "
            "least one senior for.")

depth = df["_covered"].value_counts().sort_index()
cols_depth = st.columns(4)
for col, n in zip(cols_depth, range(4)):
    with col:
        count = int(depth.get(n, 0))
        pct = count / max(total_uni, 1) * 100
        colour = (WARN if n == 0
                    else GOLD if n <= 1
                    else ACCENT_SOFT if n == 2
                    else ACCENT)
        kpi_tile(f"{n} of 3", f"{count}",
                  sub=f"{pct:.0f}% of universities",
                  color=colour)


# ==========================================================================
# Reference expander - the taxonomy behind the classification
# ==========================================================================
with st.expander("How each title is bucketed (Ian's 583-title master "
                    "list, v7)", expanded=False):
    st.caption("Ten fine-grained categories from the source list "
                "collapse into the three persona umbrellas.")
    for cat, titles in SENIOR_TITLES.items():
        umbrella = CATEGORY_TO_PERSONA.get(cat) or "mixed"
        col = PERSONA_COL.get(umbrella, MUTED)
        st.markdown(
            f'<div style="margin:.8rem 0 .3rem;font-weight:700;'
            f'color:{col}">{cat} '
            f'<span style="color:{MUTED};font-weight:400">'
            f'&mdash; {len(titles)} titles &middot; umbrella: '
            f'<strong>{umbrella}</strong></span></div>',
            unsafe_allow_html=True)
        preview = titles[:30]
        st.markdown(
            f'<div style="font-size:.78rem;color:{INK_SOFT};'
            f'line-height:1.55">{" &middot; ".join(preview)}'
            + (f' &middot; <em>+{len(titles)-30} more</em>'
                if len(titles) > 30 else "")
            + '</div>', unsafe_allow_html=True)
    st.caption("Secondary titles (VC / CFO / CIO / Kanzler) are "
                "mapped explicitly per title (SECONDARY_OVERRIDES) "
                "so they land in the right umbrella.")
