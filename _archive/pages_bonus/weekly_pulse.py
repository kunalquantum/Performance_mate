"""
Overview - Weekly Pulse.

One row per week, every channel side by side: email sends, LinkedIn
engagement, website traffic, branded searches, competitor rank. No
charts. Sortable table + top-line totals + drill-down for the picked
week.

Data source: data/emails.csv (parsed from the GrantsNow Task Sheet's
Breakdown tab by etl/email_etl.py).
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
st.markdown('<h1>Weekly pulse</h1>', unsafe_allow_html=True)
core_question("What happened across email, LinkedIn and the website "
                "this week - all channels on one page?")
st.caption("Every week we track, in one scrollable table. Columns "
            "group by channel. Sort or filter by any of them.")
render_status_key()

with st.expander("What each column means", expanded=False):
    st.markdown("""
- **Email columns** &mdash; Sent (emails), Opened, Clicks. Straight
  from the ESP.
- **LinkedIn columns** &mdash; Page views (impressions on the
  GrantsNow page), Individual visits (unique people who looked),
  New followers, Impressions (on our posts), Reactions (likes,
  celebrates etc.), Competitor rank (where we sit in the
  top-10 competitor comparison LinkedIn shows), GrantsNow
  searches (branded searches on LinkedIn - a brand-awareness
  proxy).
- **Web columns** &mdash; Visits (total website visits that week),
  Direct (typed URL / bookmarked), Organic search (came from Google
  results), Referral (came from another site), ChatGPT (traffic
  from chatgpt.com), Force.com (traffic from Salesforce-related
  domains).
""")


df = load_csv("emails.csv")
if df.empty:
    st.info("No weekly data. Run `python etl/email_etl.py`.")
    st.stop()

# Coerce
for c in ("emails_sent", "opened", "clicks",
            "li_page_views", "li_individual_visits", "li_new_followers",
            "li_impressions", "li_reactions", "gn_searches",
            "web_visits", "web_direct", "web_organic",
            "web_referral", "web_chatgpt", "web_forcecom"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")


# ==========================================================================
# Top-line rolling totals
# ==========================================================================
st.markdown('<h2>Rolling totals across the tracked window</h2>',
             unsafe_allow_html=True)
st.caption("Sum of every week we have data for.")

t_sent    = int(df["emails_sent"].sum())
t_opens   = int(df["opened"].sum())
t_li_imp  = int(df["li_impressions"].sum())
t_li_fol  = int(df["li_new_followers"].sum())
t_web     = int(df["web_visits"].sum())
t_srch    = int(df["gn_searches"].sum())

row1 = st.columns(3)
with row1[0]:
    kpi_tile("Emails sent (all weeks)", f"{t_sent:,}",
              sub=f"{t_opens:,} opens across the window",
              tooltip="Total email sends across every tracked week.")
with row1[1]:
    kpi_tile("LinkedIn impressions", f"{t_li_imp:,}",
              sub=f"{t_li_fol} new followers",
              color=ACCENT,
              tooltip="Total impressions on GrantsNow LinkedIn posts.")
with row1[2]:
    kpi_tile("Website visits", f"{t_web:,}",
              sub="all sources combined",
              color=ACCENT,
              tooltip="Total unique website visits across every week.")

row2 = st.columns(3)
with row2[0]:
    kpi_tile("Branded searches", f"{t_srch:,}",
              sub="on LinkedIn for &lsquo;GrantsNow&rsquo;",
              tooltip="How many people searched for GrantsNow by "
                      "name on LinkedIn - a brand-awareness proxy.",
              color=ACCENT if t_srch > 5000 else GOLD)
with row2[1]:
    # Best rank frequency (how often we hit 1st)
    ranks = df["li_competitor_rank"].astype(str).str.lower()
    n_first = int(ranks.str.contains("1st", na=False).sum())
    n_wks = int((ranks.replace("nan", "").ne("")).sum())
    kpi_tile("Weeks at #1 vs competitors",
              f"{n_first}",
              sub=f"of {n_wks} weeks ranked",
              color=ACCENT if n_first >= n_wks / 2 else GOLD,
              tooltip="Weeks where GrantsNow topped the LinkedIn "
                      "competitor comparison.")
with row2[2]:
    t_chatgpt = int(df["web_chatgpt"].sum())
    kpi_tile("Website visits from ChatGPT",
              f"{t_chatgpt}",
              sub="AI-referral traffic",
              tooltip="Website visits that came from chatgpt.com. "
                      "New channel worth tracking.")


# ==========================================================================
# Filter + sort
# ==========================================================================
st.markdown('<h2>Every week, every channel</h2>', unsafe_allow_html=True)

fc1, fc2 = st.columns([1, 2])
with fc1:
    sort_by = st.selectbox(
        "Sort by",
        ["Week (newest first)", "Emails sent", "LinkedIn impressions",
         "Website visits", "GrantsNow searches"],
        key="wp_sort")
with fc2:
    search = st.text_input(
        "Search a week label (e.g. 'June', 'March')",
        key="wp_search")

view = df.copy()
if search:
    view = view[view["week_label"].astype(str).str.contains(
        search, case=False, na=False)]

sort_map = {
    "Week (newest first)":  "week_start",
    "Emails sent":          "emails_sent",
    "LinkedIn impressions": "li_impressions",
    "Website visits":       "web_visits",
    "GrantsNow searches":   "gn_searches",
}
view = view.sort_values(sort_map[sort_by], ascending=False)


# ==========================================================================
# The main table
# ==========================================================================
show = view[[
    "week_label",
    "emails_sent", "opened", "clicks",
    "li_page_views", "li_new_followers", "li_impressions",
    "li_reactions", "li_competitor_rank", "gn_searches",
    "web_visits", "web_direct", "web_organic",
    "web_referral", "web_chatgpt", "web_forcecom",
]].rename(columns={
    "week_label":         "Week",
    "emails_sent":        "Email sent",
    "opened":             "Email opens",
    "clicks":             "Email clicks",
    "li_page_views":      "LI page views",
    "li_new_followers":   "LI new followers",
    "li_impressions":     "LI post impressions",
    "li_reactions":       "LI reactions",
    "li_competitor_rank": "LI rank vs comp",
    "gn_searches":        "GrantsNow searches",
    "web_visits":         "Web visits",
    "web_direct":         "Web direct",
    "web_organic":        "Web organic",
    "web_referral":       "Web referral",
    "web_chatgpt":        "Web from ChatGPT",
    "web_forcecom":       "Web from Force.com",
})

st.dataframe(
    show, use_container_width=True, hide_index=True, height=520,
    column_config={
        "Email sent":         st.column_config.NumberColumn(format="%d"),
        "Email opens":        st.column_config.NumberColumn(format="%d"),
        "Email clicks":       st.column_config.NumberColumn(format="%d"),
        "LI page views":      st.column_config.NumberColumn(format="%d"),
        "LI new followers":   st.column_config.NumberColumn(format="%d"),
        "LI post impressions": st.column_config.NumberColumn(format="%d"),
        "LI reactions":       st.column_config.NumberColumn(format="%d"),
        "GrantsNow searches": st.column_config.NumberColumn(format="%d"),
        "Web visits":         st.column_config.NumberColumn(format="%d"),
        "Web direct":         st.column_config.NumberColumn(format="%d"),
        "Web organic":        st.column_config.NumberColumn(format="%d"),
        "Web referral":       st.column_config.NumberColumn(format="%d"),
        "Web from ChatGPT":   st.column_config.NumberColumn(format="%d"),
        "Web from Force.com": st.column_config.NumberColumn(format="%d"),
    })


# ==========================================================================
# So-what observations across the whole window
# ==========================================================================
# Best week for each channel
def _best(col, label):
    if col not in df.columns or df[col].isna().all():
        return None
    idx = df[col].idxmax()
    return (str(df.loc[idx, "week_label"]), int(df.loc[idx, col]))


best_email = _best("emails_sent", "email")
best_li = _best("li_impressions", "LinkedIn")
best_web = _best("web_visits", "web")

bits = []
if best_email:
    bits.append(f"biggest email week was <strong>{best_email[0]}</strong> "
                f"({best_email[1]:,} emails)")
if best_li:
    bits.append(f"biggest LinkedIn week was <strong>{best_li[0]}</strong> "
                f"({best_li[1]:,} impressions)")
if best_web:
    bits.append(f"biggest web week was <strong>{best_web[0]}</strong> "
                f"({best_web[1]:,} visits)")
if bits:
    so_what("Peak weeks: " + "; ".join(bits) + ".", tone="info")

# Competitor rank read
ranks = df["li_competitor_rank"].astype(str).str.lower()
n_first = int(ranks.str.contains("1st", na=False).sum())
n_second = int(ranks.str.contains("2nd", na=False).sum())
n_wks = int(ranks.replace("nan", "").ne("").sum())
if n_wks:
    if n_first >= n_wks * 0.4:
        so_what(f"Ranked #1 vs competitors <strong>{n_first} of "
                 f"{n_wks}</strong> tracked weeks - we lead the "
                 f"segment on LinkedIn more often than any single "
                 f"competitor.", tone="good")
    elif n_first + n_second >= n_wks * 0.7:
        so_what(f"Ranked #1 or #2 in <strong>{n_first + n_second} "
                 f"of {n_wks}</strong> weeks. Consistent top-two "
                 f"presence.", tone="good")


# ==========================================================================
# Web traffic source rollup
# ==========================================================================
st.markdown('<h2>Web traffic by source (all weeks)</h2>',
             unsafe_allow_html=True)
st.caption("Where our website visits actually come from. Highest "
            "share first.")

sources = {
    "Direct":           int(df["web_direct"].sum()),
    "Organic search":   int(df["web_organic"].sum()),
    "Referral":         int(df["web_referral"].sum()),
    "ChatGPT":          int(df["web_chatgpt"].sum()),
    "Force.com":        int(df["web_forcecom"].sum()),
}
total_web = int(df["web_visits"].sum())

header = (
    f'<div style="display:grid;grid-template-columns:'
    f'1.5fr .8fr .8fr 2fr;gap:.5rem;padding:.5rem .8rem;'
    f'font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;'
    f'color:{MUTED};font-weight:600;border-bottom:1px solid {LINE}">'
    f'<div>Source</div><div>Visits</div><div>% of total</div>'
    f'<div></div></div>')
rows_html = [header]
for src, n in sorted(sources.items(), key=lambda t: -t[1]):
    pct = n / max(total_web, 1) * 100
    bar_col = ACCENT if pct >= 30 else GOLD if pct >= 5 else MUTED
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'1.5fr .8fr .8fr 2fr;gap:.5rem;padding:.55rem .8rem;'
        f'font-size:.9rem;border-bottom:1px solid {LINE};'
        f'align-items:center">'
        f'<div style="color:{INK};font-weight:600">{src}</div>'
        f'<div style="color:{INK}">{n:,}</div>'
        f'<div style="color:{INK}">{pct:.0f}%</div>'
        f'<div><div style="width:{pct}%;height:8px;background:{bar_col};'
        f'border-radius:4px"></div></div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)

# Insight on AI traffic
ai_pct = sources["ChatGPT"] / max(total_web, 1) * 100
if sources["ChatGPT"] > 0:
    so_what(
        f"<strong>{sources['ChatGPT']}</strong> visits came from "
        f"chatgpt.com ({ai_pct:.1f}% of all web traffic). AI "
        f"referral is a real channel now - worth checking how "
        f"GrantsNow shows up in ChatGPT answers about grant "
        f"management software.", tone="info")


# ==========================================================================
# Drill: pick a week for the full detail + notes
# ==========================================================================
st.markdown('<h2>Look inside one week</h2>', unsafe_allow_html=True)
opts = ["-- pick one --"] + df.sort_values(
    "week_start", ascending=False)["week_label"].astype(str).tolist()
pick = st.selectbox("Week", opts, key="wp_drill")

if pick and pick != "-- pick one --":
    r = df[df["week_label"] == pick].iloc[0]

    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        kpi_tile("Emails sent", f"{int(r['emails_sent']):,}",
                  sub=f"{int(r['opened'])} opens, {int(r['clicks'])} clicks")
    with dc2:
        kpi_tile("LinkedIn impressions",
                  f"{int(r['li_impressions']):,}",
                  sub=f"{int(r['li_new_followers'])} new followers")
    with dc3:
        kpi_tile("Web visits", f"{int(r['web_visits']):,}",
                  sub=f"{int(r['gn_searches'])} branded searches")

    # Rank + competitors watch
    rank = str(r.get("li_competitor_rank", "") or "").strip()
    comps = str(r.get("li_competitors_watch", "") or "").strip()
    if rank or comps:
        st.markdown(
            f'<div style="border:1px solid {LINE};border-radius:6px;'
            f'padding:.7rem 1rem;background:{BG_SOFT};margin-top:.6rem;'
            f'font-size:.9rem">'
            f'<strong>Competitor context.</strong> Rank: '
            f'<span style="color:{ACCENT};font-weight:600">'
            f'{rank or "-"}</span>. '
            f'Watch: <span style="color:{INK_SOFT}">{comps or "-"}</span>.'
            f'</div>', unsafe_allow_html=True)

    # Notes and interested people
    _bits = []
    _notes = str(r.get("li_notes", "") or "").strip()
    if _notes:
        _bits.append(("LinkedIn notes / learnings", _notes))
    _ppl = str(r.get("li_interested_people", "") or "").strip()
    if _ppl:
        _bits.append(("Most interested (LinkedIn)", _ppl))
    _web_int = str(r.get("web_interested", "") or "").strip()
    if _web_int:
        _bits.append(("Most interested (Web/Whois)", _web_int))
    _news = str(r.get("newsletter_note", "") or "").strip()
    if _news:
        _bits.append(("Newsletter note", _news))

    for label, text in _bits:
        st.markdown(
            f'<div style="border-left:3px solid {ACCENT};padding:.6rem 1rem;'
            f'margin:.4rem 0;background:{BG_SOFT};font-size:.88rem;'
            f'line-height:1.5;border-radius:4px">'
            f'<strong>{label}:</strong><br>'
            f'<span style="color:{INK_SOFT};white-space:pre-line">'
            f'{text}</span></div>',
            unsafe_allow_html=True)

    # Top post link
    top_post = str(r.get("li_top_post_url", "") or "").strip()
    if top_post and top_post.startswith("http"):
        st.markdown(f"**Top post that week:** [{top_post[:60]}...]"
                     f"({top_post})")
