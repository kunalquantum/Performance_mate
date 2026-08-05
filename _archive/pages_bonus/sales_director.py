"""
Sales Director view.

One consolidated page. Numbers only, no charts. Everything a sales
director should see on Monday morning, top-to-bottom, no filters
required.

Sections (top to bottom):
    1. The list        - how much of the UK target we cover
    2. The people      - contacts by persona (with valid-email counts)
    3. The warm ones   - MQL engagement per persona
    4. The rhythm      - email cadence this month vs target
    5. Top opportunities - attack list + hottest leads + biggest gaps
    6. This week&apos;s actions - rule-based to-do list
"""
from shared import (core_question, inject_css, render_status_key,
                     kpi_tile, so_what, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Sales director view</h1>', unsafe_allow_html=True)
core_question("What do I need to see on Monday morning to know where "
                "the pipeline stands and what to do this week?")
st.caption("Every headline number from the persona and email data, "
            "on one page. No filters, no charts - scroll top to "
            "bottom, decisions ready by the end.")
render_status_key()


# --------------------------------------------------------------------------
# Load all data
# --------------------------------------------------------------------------
coverage = load_csv("persona_institution_coverage.csv")
contacts = load_csv("persona_contacts_full.csv")
mql      = load_csv("mql_engaged.csv")
activity = load_csv("persona_email_activity.csv")
gaps     = load_csv("persona_gaps.csv")

# Coerce numerics we'll use throughout
for df, cols in [
    (coverage, ("contacts", "research", "finance", "it_systems",
                  "personas_held", "valid_emails")),
    (mql,      ("opens", "clicks", "total_engagement")),
    (gaps,     ("contacts_held", "research", "finance",
                  "it_systems", "personas_held")),
]:
    if not df.empty:
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce") \
                    .fillna(0).astype(int)

# UK target subset
target = pd.DataFrame()
uk_target = pd.DataFrame()
if not coverage.empty:
    target = coverage[
        coverage["in_target"].astype(str).str.lower() == "yes"].copy()
if not contacts.empty and not target.empty:
    target_keys = set(target["institution_key"].dropna().astype(str))
    uk = contacts[contacts["country"].astype(str).str.upper() == "UK"]
    uk_target = uk[uk["institution_key"].astype(str)
                    .isin(target_keys)].copy()


# ==========================================================================
# 1. THE LIST
# ==========================================================================
st.markdown('<h2>1. The list</h2>', unsafe_allow_html=True)
st.caption("Where the UK target list stands today.")

if target.empty:
    st.info("No coverage data. Run `python etl/persona_data_etl.py`.")
else:
    n_target = len(target)
    n_with = int((target["contacts"] > 0).sum())
    n_all3 = int((target["personas_held"] >= 3).sum())
    n_two  = int((target["personas_held"] == 2).sum())
    n_one  = int((target["personas_held"] == 1).sum())
    n_zero = int((target["personas_held"] == 0).sum())
    avg    = float(target["personas_held"].mean())

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        kpi_tile("Target institutions", f"{n_target:,}",
                  sub="UK relevant institutions on the target list")
    with a2:
        kpi_tile("Have contact data", f"{n_with:,}",
                  sub=f"{n_with/max(n_target,1)*100:.0f}% of target",
                  color=ACCENT)
    with a3:
        kpi_tile("Complete coverage (3 of 3)", f"{n_all3:,}",
                  sub="attack-ready accounts",
                  color=ACCENT)
    with a4:
        kpi_tile("Avg personas / institution", f"{avg:.2f}",
                  sub="out of 3.0")

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        kpi_tile("2 of 3 personas", f"{n_two:,}",
                  sub="one persona away from complete",
                  color=GOLD)
    with b2:
        kpi_tile("1 of 3 personas", f"{n_one:,}",
                  color=GOLD)
    with b3:
        kpi_tile("0 personas held", f"{n_zero:,}",
                  sub="cold institutions",
                  color=WARN if n_zero > 20 else GOLD)
    with b4:
        # Missing per persona (across institutions that HAVE contacts)
        no_r = int(((target["research"] == 0)
                     & (target["contacts"] > 0)).sum())
        no_f = int(((target["finance"] == 0)
                     & (target["contacts"] > 0)).sum())
        no_i = int(((target["it_systems"] == 0)
                     & (target["contacts"] > 0)).sum())
        worst = max([("Research", no_r), ("Finance", no_f),
                      ("IT-Systems", no_i)], key=lambda t: t[1])
        kpi_tile("Biggest persona hole",
                  f"{worst[1]:,}",
                  sub=f"institutions with no {worst[0]}",
                  color=WARN if worst[1] > 100 else GOLD)


# ==========================================================================
# 2. THE PEOPLE (contacts by persona, with valid-email counts)
# ==========================================================================
st.markdown('<h2>2. The people</h2>', unsafe_allow_html=True)
st.caption("Contacts we hold across the target UK institutions, "
            "split by persona. &lsquo;Valid&rsquo; = safe to email today.")

if uk_target.empty:
    st.info("No contact data. Run `python etl/persona_data_etl.py`.")
else:
    def _persona_stats(mask):
        sub = uk_target[mask]
        n = len(sub)
        v = int((sub["snov_status"].astype(str).str.lower()
                  == "valid").sum())
        return (n, v)

    r_n, r_v = _persona_stats(uk_target["persona"] == "Research")
    s_n, s_v = _persona_stats(
        (uk_target["persona"] == "Research")
        & (uk_target["research_tier"].astype(str) == "Senior"))
    op_n, op_v = _persona_stats(
        (uk_target["persona"] == "Research")
        & (uk_target["research_tier"].astype(str) == "Operational"))
    ac_n, ac_v = _persona_stats(
        (uk_target["persona"] == "Research")
        & (uk_target["research_tier"].astype(str) == "Academic"))
    f_n, f_v = _persona_stats(uk_target["persona"] == "Finance")
    i_n, i_v = _persona_stats(uk_target["persona"] == "IT/Systems")

    rows = [
        ("Research - total",        r_n,  r_v),
        ("  Senior / executive",    s_n,  s_v),
        ("  Operational",           op_n, op_v),
        ("  Academic",              ac_n, ac_v),
        ("Finance",                 f_n,  f_v),
        ("IT-Systems",              i_n,  i_v),
    ]

    header = (
        f'<div style="display:grid;grid-template-columns:'
        f'2fr 1fr 1fr 1fr;gap:.5rem;padding:.5rem .8rem;'
        f'font-size:.72rem;text-transform:uppercase;'
        f'letter-spacing:.12em;color:{MUTED};font-weight:600;'
        f'border-bottom:1px solid {LINE}">'
        f'<div>Persona</div><div>Contacts</div><div>Valid emails</div>'
        f'<div>% valid</div></div>')
    rows_html = [header]
    for label, n, v in rows:
        indent = ("&nbsp;&nbsp;&nbsp;&nbsp;"
                    if label.startswith(" ") else "")
        p = v / max(n, 1) * 100
        bg = ("#DDEEEC" if p >= 65 else
                "#F7F0DA" if p >= 45 else "#FBEDED")
        rows_html.append(
            f'<div style="display:grid;grid-template-columns:'
            f'2fr 1fr 1fr 1fr;gap:.5rem;padding:.55rem .8rem;'
            f'font-size:.92rem;border-bottom:1px solid {LINE};'
            f'align-items:center">'
            f'<div style="color:{INK};font-weight:600">'
            f'{indent}{label.strip()}</div>'
            f'<div style="color:{INK}">{n:,}</div>'
            f'<div style="color:{ACCENT};font-weight:600">{v:,}</div>'
            f'<div style="background:{bg};padding:.15rem .4rem;'
            f'border-radius:4px;color:{INK};font-weight:700">'
            f'{p:.0f}%</div></div>')
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:6px;'
        f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
        unsafe_allow_html=True)

    total_contacts = len(uk_target)
    total_valid = int((uk_target["snov_status"].astype(str).str.lower()
                        == "valid").sum())
    t1, t2 = st.columns(2)
    with t1:
        kpi_tile("All UK contacts (target institutions)",
                  f"{total_contacts:,}")
    with t2:
        pct = total_valid / max(total_contacts, 1) * 100
        kpi_tile("Verified valid emails",
                  f"{total_valid:,}",
                  sub=f"{pct:.0f}% of {total_contacts:,}",
                  color=ACCENT if pct >= 60 else GOLD)


# ==========================================================================
# 3. THE WARM ONES (MQLs by persona)
# ==========================================================================
st.markdown('<h2>3. The warm ones (real engagement)</h2>',
             unsafe_allow_html=True)
st.caption("People actually opening and clicking our emails. Not "
            "estimates - each row is a tracked prospect.")

if mql.empty:
    st.info("No MQL data. Run `python etl/mql_etl.py`.")
else:
    mql_r = mql[mql["persona"] == "Research"]
    mql_f = mql[mql["persona"] == "Finance"]
    mql_i = mql[mql["persona"] == "IT-Systems"]
    n_all = len(mql)

    w1, w2, w3, w4 = st.columns(4)
    with w1:
        kpi_tile("Total warm leads", f"{n_all:,}",
                  color=ACCENT)
    with w2:
        kpi_tile("Research MQLs", f"{len(mql_r):,}",
                  sub=f"{int(mql_r['opens'].sum())} opens, "
                       f"{int(mql_r['clicks'].sum())} clicks",
                  color=ACCENT)
    with w3:
        kpi_tile("Finance MQLs", f"{len(mql_f):,}",
                  sub=f"{int(mql_f['opens'].sum())} opens, "
                       f"{int(mql_f['clicks'].sum())} clicks",
                  color=GOLD if len(mql_f) < 10 else ACCENT)
    with w4:
        kpi_tile("IT-Systems MQLs", f"{len(mql_i):,}",
                  sub=f"{int(mql_i['opens'].sum())} opens, "
                       f"{int(mql_i['clicks'].sum())} clicks",
                  color=WARN if len(mql_i) < 5 else GOLD
                        if len(mql_i) < 10 else ACCENT)

    # Untouched hot leads (sales hasn't chased yet)
    if "sales_touched" in mql.columns:
        untouched = mql[mql["sales_touched"].fillna("").astype(str)
                          .str.strip().isin(["", "nan", "None"])]
        untouched = untouched.sort_values("total_engagement",
                                             ascending=False).head(5)
        if not untouched.empty:
            st.markdown('<h3 style="margin-top:1.2rem">Top 5 warm '
                         'leads sales has not chased yet</h3>',
                         unsafe_allow_html=True)
            for _, r in untouched.iterrows():
                st.markdown(
                    f'<div style="border-left:3px solid {WARN};'
                    f'padding:.5rem .9rem;margin:.35rem 0;'
                    f'background:{BG_SOFT};border-radius:4px;'
                    f'font-size:.9rem">'
                    f'<strong>{r["first_name"]} {r["last_name"]}</strong>'
                    f' &middot; {r["persona"]} &middot; '
                    f'{r["institution"]} &middot; '
                    f'<span style="color:{ACCENT};font-weight:600">'
                    f'{int(r["opens"])} opens, {int(r["clicks"])} clicks</span>'
                    f'<br><span style="color:{MUTED};font-size:.82rem">'
                    f'{str(r.get("job_title",""))[:70]}</span>'
                    f'</div>', unsafe_allow_html=True)


# ==========================================================================
# 4. THE RHYTHM (email activity per persona)
# ==========================================================================
st.markdown('<h2>4. The rhythm</h2>', unsafe_allow_html=True)
st.caption("Persona-specific email activity vs the target of 2 per "
            "month per persona (3 maximum).")

TARGET_MIN, TARGET_MAX = 2, 3
PERSONAS = ["Research",
              "Finance", "IT-Systems"]

if activity.empty:
    st.markdown(
        f'<div style="background:{BG_SOFT};border-left:3px solid '
        f'{GOLD};padding:.7rem 1rem;border-radius:4px;'
        f'font-size:.9rem">'
        f'No monthly activity logged yet. Head to '
        f'<strong>Persona &rarr; Monthly report</strong> and add '
        f'this month&apos;s numbers - the table below will fill in.'
        f'</div>', unsafe_allow_html=True)
else:
    latest_months = sorted(
        activity["month"].dropna().astype(str).unique(),
        reverse=True)
    if latest_months:
        m = latest_months[0]
        current = activity[activity["month"].astype(str) == m]

        st.markdown(f'<div class="eyebrow" '
                     f'style="margin-bottom:.4rem">Month: {m}</div>',
                     unsafe_allow_html=True)

        header = (
            f'<div style="display:grid;grid-template-columns:'
            f'1.6fr .7fr .7fr .9fr 1fr;gap:.5rem;padding:.5rem .8rem;'
            f'font-size:.72rem;text-transform:uppercase;'
            f'letter-spacing:.12em;color:{MUTED};font-weight:600;'
            f'border-bottom:1px solid {LINE}">'
            f'<div>Persona</div><div>Sent</div><div>Target</div>'
            f'<div>Planned next</div><div>Verdict</div></div>')
        rows_html = [header]
        lookup = {r["persona"]: r for _, r in current.iterrows()}
        for p in PERSONAS:
            row = lookup.get(p, {})
            sent = int(pd.to_numeric(row.get("emails_sent", 0),
                                       errors="coerce") or 0)
            planned = int(pd.to_numeric(
                row.get("planned_next_month", 0),
                errors="coerce") or 0)
            if sent == 0:
                verdict, vc = "No touch", GOLD
            elif sent < TARGET_MIN:
                verdict, vc = "Under-contacted", GOLD
            elif sent > TARGET_MAX:
                verdict, vc = "Over-contacted", WARN
            else:
                verdict, vc = "On track", ACCENT
            sent_bg = ("#DDEEEC" if TARGET_MIN <= sent <= TARGET_MAX
                        else "#FBEDED" if sent > TARGET_MAX
                        else "#F7F0DA")
            rows_html.append(
                f'<div style="display:grid;grid-template-columns:'
                f'1.6fr .7fr .7fr .9fr 1fr;gap:.5rem;'
                f'padding:.55rem .8rem;font-size:.92rem;'
                f'border-bottom:1px solid {LINE};align-items:center">'
                f'<div style="color:{INK};font-weight:600">{p}</div>'
                f'<div style="background:{sent_bg};padding:.15rem .4rem;'
                f'border-radius:4px;color:{INK};font-weight:700">'
                f'{sent}</div>'
                f'<div style="color:{MUTED}">'
                f'{TARGET_MIN}-{TARGET_MAX}</div>'
                f'<div style="color:{INK}">{planned}</div>'
                f'<div style="color:{vc};font-weight:600">{verdict}</div>'
                f'</div>')
        st.markdown(
            f'<div style="border:1px solid {LINE};border-radius:6px;'
            f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
            unsafe_allow_html=True)


# ==========================================================================
# 5. TOP OPPORTUNITIES
# ==========================================================================
st.markdown('<h2>5. Top opportunities</h2>', unsafe_allow_html=True)

o1, o2 = st.columns(2)

# Left: attack-ready accounts
with o1:
    st.markdown('<h3 style="margin-top:.4rem">Top 5 attack-ready '
                 'accounts</h3>', unsafe_allow_html=True)
    st.caption("Institutions where we hold Research + Finance + "
                "IT-Systems today - ready for full-committee outreach.")
    if not target.empty:
        attack = (target[target["personas_held"] >= 3]
                   .sort_values("contacts", ascending=False).head(5))
        for _, r in attack.iterrows():
            st.markdown(
                f'<div style="border-left:3px solid {ACCENT};'
                f'padding:.45rem .8rem;margin:.3rem 0;'
                f'background:{BG_SOFT};border-radius:4px;'
                f'font-size:.9rem;display:flex;justify-content:space-between">'
                f'<span style="color:{INK};font-weight:600">'
                f'{r["institution"]}</span>'
                f'<span style="color:{INK_SOFT}">'
                f'{int(r["contacts"])} contacts</span>'
                f'</div>', unsafe_allow_html=True)

# Right: biggest quick-win gaps (institutions with 2 of 3 personas)
with o2:
    st.markdown('<h3 style="margin-top:.4rem">Top 5 quick-win '
                 'coverage gaps</h3>', unsafe_allow_html=True)
    st.caption("Institutions where we already hold 2 personas - "
                "adding one contact completes the buying committee.")
    if not target.empty:
        one_away = (target[target["personas_held"] == 2]
                     .sort_values("contacts", ascending=False).head(5))
        for _, r in one_away.iterrows():
            missing = []
            if int(r.get("research", 0)) == 0:  missing.append("Research")
            if int(r.get("finance", 0)) == 0:   missing.append("Finance")
            if int(r.get("it_systems", 0)) == 0: missing.append("IT")
            miss_str = ", ".join(missing) if missing else "one persona"
            st.markdown(
                f'<div style="border-left:3px solid {GOLD};'
                f'padding:.45rem .8rem;margin:.3rem 0;'
                f'background:{BG_SOFT};border-radius:4px;'
                f'font-size:.9rem;display:flex;justify-content:space-between">'
                f'<span style="color:{INK};font-weight:600">'
                f'{r["institution"]}</span>'
                f'<span style="color:{INK_SOFT}">'
                f'add {miss_str}</span>'
                f'</div>', unsafe_allow_html=True)


# ==========================================================================
# 6. THIS WEEK&apos;S ACTIONS
# ==========================================================================
st.markdown('<h2>6. This week&apos;s actions</h2>',
             unsafe_allow_html=True)
st.caption("Rule-based next steps derived from the numbers above.")

actions = []

# Rule: chase untouched warm leads
if not mql.empty and "sales_touched" in mql.columns:
    untouched_n = int(mql["sales_touched"].fillna("").astype(str)
                         .str.strip().isin(["", "nan", "None"]).sum())
    if untouched_n >= 3:
        actions.append(
            f"Chase the <strong>{untouched_n}</strong> warm leads "
            f"sales has not touched yet. See the list in section 3 "
            f"or the Warm leads page for the full ranking.")

# Rule: verify queue
if not uk_target.empty:
    unknown_n = int((uk_target["snov_status"].astype(str).str.lower()
                       == "unknown").sum())
    if unknown_n >= 100:
        actions.append(
            f"Send the <strong>{unknown_n:,}</strong> unknown-status "
            f"emails to Snov for verification. Grows the "
            f"send-ready list.")

# Rule: persona hole
if not target.empty:
    no_f = int(((target["finance"] == 0)
                 & (target["contacts"] > 0)).sum())
    no_i = int(((target["it_systems"] == 0)
                 & (target["contacts"] > 0)).sum())
    if no_i >= no_f and no_i > 50:
        actions.append(
            f"Add IT-Systems contacts at the "
            f"<strong>{no_i}</strong> institutions where we hold "
            f"none. See the Missing persona list page - IT is our "
            f"biggest hole.")
    elif no_f > 50:
        actions.append(
            f"Add Finance contacts at the <strong>{no_f}</strong> "
            f"institutions where we hold none. See the Missing "
            f"persona list.")

# Rule: cadence gap
if not activity.empty:
    latest_months = sorted(
        activity["month"].dropna().astype(str).unique(),
        reverse=True)
    if latest_months:
        current = activity[activity["month"].astype(str)
                             == latest_months[0]]
        zero_touch = []
        for _, r in current.iterrows():
            sent = int(pd.to_numeric(r.get("emails_sent", 0),
                                       errors="coerce") or 0)
            if sent == 0:
                zero_touch.append(str(r["persona"]))
        if zero_touch:
            actions.append(
                f"Plan persona-specific content for: "
                f"<strong>{', '.join(zero_touch)}</strong>. "
                f"These got zero touches this month.")

# Rule: pattern to avoid (best MQL persona is under-served)
if not mql.empty:
    n_f_mql = int((mql["persona"] == "Finance").sum())
    n_r_mql = int((mql["persona"] == "Research").sum())
    if n_f_mql >= 15 and not activity.empty:
        # If Finance MQL is strong but Finance cadence is 0, flag it
        latest_months = sorted(
            activity["month"].dropna().astype(str).unique(),
            reverse=True)
        if latest_months:
            fin_row = activity[
                (activity["month"].astype(str) == latest_months[0])
                & (activity["persona"] == "Finance")]
            if not fin_row.empty:
                fin_sent = int(pd.to_numeric(
                    fin_row.iloc[0].get("emails_sent", 0),
                    errors="coerce") or 0)
                if fin_sent == 0:
                    actions.append(
                        f"Finance is producing "
                        f"<strong>{n_f_mql}</strong> MQLs but got "
                        f"zero persona-specific email this month. "
                        f"That is the biggest content-mix mismatch "
                        f"right now.")

if not actions:
    st.markdown(
        f'<div style="color:{INK_SOFT};font-size:.95rem;'
        f'background:{BG_SOFT};padding:.8rem 1rem;'
        f'border-radius:4px">Nothing urgent flagged this week. '
        f'Coverage, verification queue and cadence are all inside '
        f'sensible thresholds.</div>', unsafe_allow_html=True)
else:
    for i, a in enumerate(actions, 1):
        st.markdown(
            f'<div style="border-left:4px solid {ACCENT};'
            f'padding:.6rem 1rem;margin:.4rem 0;background:{BG_SOFT};'
            f'font-size:.95rem;line-height:1.5;border-radius:4px">'
            f'<strong style="color:{ACCENT}">{i}.</strong> {a}</div>',
            unsafe_allow_html=True)
