"""
Persona - Senior gaps.

Which universities do we hold a senior leadership contact for, and
where are the gaps?

Uses the master 533-title taxonomy from Ian (senior_titles.py),
grouped into seven working categories:
    - Senior Executive           (PVC / VP Research / Chief Research Officer)
    - Research Leadership        (Directors / Heads of Research)
    - Research Contracts & Compliance
    - Research Finance & Accounting
    - Sponsored / Grants / Awards (pre-award, post-award, grants managers)
    - Research Systems & Digital
    - Secondary                  (VC / CFO / CIO - review only)
"""
from shared import (core_question, inject_css, kpi_tile, so_what,
                     load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
from senior_titles import (classify_title, CATEGORY_ORDER,
                             SENIOR_TITLES)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
             unsafe_allow_html=True)
st.markdown('<h1>Senior gaps</h1>', unsafe_allow_html=True)
core_question("Which universities do we hold a senior leadership "
                "contact for - and where are the executive gaps?")
st.caption("Every contact is classified against Ian's 533-title "
            "master list of research-side senior roles, grouped into "
            "seven categories.")

# The seven active categories used on-page (Senior Executive first)
DISPLAY_CATS = [c for c in CATEGORY_ORDER if c != "Secondary"]
CAT_COL = {
    "Senior Executive":                "#0E6E68",
    "Research Leadership":             "#7A6A9A",
    "Research Contracts & Compliance": "#B4462F",
    "Research Finance & Accounting":   "#C99A2E",
    "Sponsored / Grants / Awards":     "#3E7C97",
    "Research Systems & Digital":      "#5E8B58",
}

# Load
contacts = load_csv("persona_contacts_full.csv")
coverage = load_csv("persona_institution_coverage.csv")
if contacts.empty or coverage.empty:
    st.info("Missing `persona_contacts_full.csv` or "
             "`persona_institution_coverage.csv`.")
    st.stop()


# ==========================================================================
# Classify every contact against the taxonomy
# ==========================================================================
def _classify(t):
    cat, canon = classify_title(t)
    return cat


contacts["_cat"] = contacts["job_title"].apply(_classify)
seniors = contacts[contacts["_cat"].notna()].copy()

# Only universities
uni_cov = coverage[coverage["type"].astype(str).str.lower()
                     .str.contains("univ", na=False)].copy()
total_uni = len(uni_cov)

# Build per-institution: {inst_key: {cat: [{"name","title"} ...]}}
per_inst = {}
for _, r in seniors.iterrows():
    key = str(r.get("institution_key", "")).strip().lower()
    if not key:
        continue
    cat = r["_cat"]
    name = f'{str(r.get("first_name","")).strip()} ' \
           f'{str(r.get("last_name","")).strip()}'.strip()
    if not name:
        continue
    per_inst.setdefault(key, {}).setdefault(cat, []).append({
        "name":  name,
        "title": str(r.get("job_title", "")).strip(),
    })


# ==========================================================================
# Headline coverage tiles
# ==========================================================================
def _uni_with(cat):
    return sum(
        1 for _, r in uni_cov.iterrows()
        if per_inst.get(str(r["institution_key"]).strip().lower(),
                          {}).get(cat))


n_any_senior = sum(
    1 for _, r in uni_cov.iterrows()
    if per_inst.get(str(r["institution_key"]).strip().lower()))
n_exec = _uni_with("Senior Executive")
n_no_senior = total_uni - n_any_senior
total_seniors = len(seniors)

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("UK universities in view", f"{total_uni}",
              sub="from the coverage workbook")
with k2:
    kpi_tile("Any senior on file",
              f"{n_any_senior}",
              sub=f"{n_any_senior/max(total_uni,1)*100:.0f}% of universities",
              color=ACCENT if n_any_senior / max(total_uni, 1) >= 0.5
                    else GOLD)
with k3:
    kpi_tile("Senior Executive on file",
              f"{n_exec}",
              sub="Pro-VC / VP Research / Chief Research Officer",
              color=ACCENT if n_exec / max(total_uni, 1) >= 0.3
                    else GOLD if n_exec / max(total_uni, 1) >= 0.15
                    else WARN)
with k4:
    kpi_tile("No senior at all",
              f"{n_no_senior}",
              sub=f"{n_no_senior/max(total_uni,1)*100:.0f}% - full gap",
              color=WARN if n_no_senior / max(total_uni, 1) >= 0.3
                    else GOLD)

so_what(
    f"Out of <strong>{total_uni}</strong> UK universities we hold "
    f"any contact for, <strong>{n_exec}</strong> have a Senior "
    f"Executive (PVC / VP Research / CRO) on file. "
    f"<strong>{total_seniors}</strong> contacts across the estate "
    f"match one of the 533 senior titles.",
    tone="warn" if n_no_senior >= total_uni * 0.3 else "info")


# ==========================================================================
# Coverage by category strip
# ==========================================================================
st.markdown('<h2>Where the coverage sits by category</h2>',
             unsafe_allow_html=True)
st.caption("How many universities we hold at least one contact for "
            "in each category, plus the total contact count.")

cols = st.columns(len(DISPLAY_CATS))
for col, cat in zip(cols, DISPLAY_CATS):
    n_uni = _uni_with(cat)
    n_contacts = int((seniors["_cat"] == cat).sum())
    pct = n_uni / max(total_uni, 1) * 100
    with col:
        st.markdown(
            f'<div style="border:1px solid {LINE};border-top:4px solid '
            f'{CAT_COL[cat]};border-radius:8px;padding:.8rem .9rem;'
            f'background:{BG};height:100%">'
            f'<div style="font-size:.7rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.12em;'
            f'line-height:1.3;min-height:2.4rem">{cat}</div>'
            f'<div style="font-size:1.6rem;font-weight:700;'
            f'color:{CAT_COL[cat]};margin:.3rem 0 .1rem">'
            f'{n_uni}</div>'
            f'<div style="font-size:.75rem;color:{INK_SOFT}">'
            f'{pct:.0f}% of universities</div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'margin-top:.4rem">{n_contacts} people</div></div>',
            unsafe_allow_html=True)


# ==========================================================================
# Filter
# ==========================================================================
st.markdown('<h2 style="margin-top:1.5rem">Every university &mdash; '
             'senior coverage</h2>', unsafe_allow_html=True)
st.caption("One row per university. Green pill = we hold that role. "
            "Red pill = gap.")

fc1, fc2, fc3 = st.columns([1.3, 1.3, 1])
with fc1:
    view_filter = st.selectbox(
        "Show",
        ["All universities",
         "Missing Senior Executive",
         "Has Senior Executive",
         "No senior at all"],
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

# Build the display frame
rows = []
for _, r in uni_cov.iterrows():
    key = str(r["institution_key"]).strip().lower()
    inst_name = str(r.get("institution") or r["institution_key"])
    senior_map = per_inst.get(key, {})
    row = {"University": inst_name, "_key": key}
    n_covered = 0
    for cat in DISPLAY_CATS:
        entries = senior_map.get(cat, [])
        row[cat] = entries
        if entries:
            n_covered += 1
    row["_covered"] = n_covered
    row["_has_exec"] = bool(senior_map.get("Senior Executive"))
    row["_has_any"] = bool(senior_map)
    rows.append(row)
df = pd.DataFrame(rows)

view = df.copy()
if view_filter == "Missing Senior Executive":
    view = view[~view["_has_exec"]]
elif view_filter == "Has Senior Executive":
    view = view[view["_has_exec"]]
elif view_filter == "No senior at all":
    view = view[~view["_has_any"]]

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
        f'border-left:3px solid {colour};padding:.25rem .45rem;'
        f'border-radius:2px;font-size:.75rem;line-height:1.3">'
        f'<div style="color:{INK};font-weight:600">'
        f'{top["name"]}{extra}</div>'
        f'<div style="color:{MUTED};font-size:.66rem">'
        f'{top["title"][:44]}</div></div>')


# Grid template: University + 6 category columns + score
grid = "1.8fr " + " ".join(["1.1fr"] * len(DISPLAY_CATS)) + " .55fr"
header_cells = ['<div>University</div>'] + [
    f'<div>{cat}</div>' for cat in DISPLAY_CATS
] + ['<div style="text-align:center">Score</div>']
header = (
    f'<div style="display:grid;grid-template-columns:{grid};gap:.45rem;'
    f'padding:.5rem .8rem;font-size:.66rem;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.1em;font-weight:600;'
    f'border-bottom:1px solid {LINE};background:{BG_SOFT}">'
    + "".join(header_cells) + '</div>')

rows_html = [header]
for _, r in view.iterrows():
    covered = int(r["_covered"])
    max_cats = len(DISPLAY_CATS)
    score_col = (ACCENT if covered >= 3 else GOLD if covered >= 1 else WARN)
    cells = [f'<div style="color:{INK};font-weight:600;line-height:1.25">'
             f'{r["University"]}</div>']
    for cat in DISPLAY_CATS:
        cells.append(f'<div>{_cell(r[cat], CAT_COL[cat])}</div>')
    cells.append(
        f'<div style="text-align:center;background:{score_col}22;'
        f'color:{INK};font-weight:700;padding:.15rem;'
        f'border-radius:3px;font-size:.85rem">{covered}/{max_cats}</div>')
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:{grid};'
        f'gap:.45rem;padding:.55rem .8rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        + "".join(cells) + '</div>')

st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)


# ==========================================================================
# Download
# ==========================================================================
csv_df = view[["University"] + list(DISPLAY_CATS)].copy()
for cat in DISPLAY_CATS:
    csv_df[cat] = csv_df[cat].apply(
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
st.caption("How many of the six senior categories each university "
            "has at least one person for.")

depth = df["_covered"].value_counts().sort_index()
cols_depth = st.columns(len(DISPLAY_CATS) + 1)
for col, n in zip(cols_depth, range(len(DISPLAY_CATS) + 1)):
    with col:
        count = int(depth.get(n, 0))
        pct = count / max(total_uni, 1) * 100
        colour = (WARN if n == 0
                    else GOLD if n <= 2
                    else ACCENT)
        kpi_tile(f"{n} of {len(DISPLAY_CATS)}",
                  f"{count}",
                  sub=f"{pct:.0f}% of universities",
                  color=colour)


# ==========================================================================
# Which titles feed each category (reference)
# ==========================================================================
with st.expander("Titles included in each category (from Ian's "
                    "533-title master list)", expanded=False):
    for cat in DISPLAY_CATS:
        titles = SENIOR_TITLES.get(cat, [])
        st.markdown(
            f'<div style="margin:.8rem 0 .3rem;font-weight:700;'
            f'color:{CAT_COL[cat]}">{cat} '
            f'<span style="color:{MUTED};font-weight:400">'
            f'&mdash; {len(titles)} titles</span></div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:.78rem;color:{INK_SOFT};'
            f'line-height:1.6">{" &middot; ".join(titles[:40])}'
            + (f' &middot; <em>+{len(titles)-40} more</em>'
                if len(titles) > 40 else "")
            + '</div>', unsafe_allow_html=True)
