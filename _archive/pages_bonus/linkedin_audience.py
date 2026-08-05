"""
LinkedIn - Audience.

Who follows the GrantsNow LinkedIn page (followers) and who is just
looking (visitors). Breakdown across five dimensions: industry, job
function, seniority, location, company size. Plus recent follower
growth.

Data sources:
    followers_industry.csv  followers_jobfunction.csv
    followers_seniority.csv followers_location.csv
    followers_companysize.csv followers_daily.csv
    visitors_industry.csv   visitors_jobfunction.csv
    visitors_seniority.csv  visitors_location.csv
    visitors_companysize.csv visitors_daily.csv
"""
from shared import (core_question, inject_css, render_status_key,
                     kpi_tile, so_what, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; LinkedIn</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Audience</h1>', unsafe_allow_html=True)
core_question("Who is our LinkedIn audience - who follows us, who "
                "visits the page, and what jobs and industries are "
                "they in?")
st.caption("Every slice of who our LinkedIn page reaches, from "
            "industry to seniority to location. Switch between "
            "Followers (people who committed) and Visitors (people "
            "looking but not yet following).")
render_status_key()

with st.expander("What these mean", expanded=False):
    st.markdown("""
- **Followers** &mdash; people who clicked Follow on the GrantsNow
  LinkedIn page. They see our posts in their feed.
- **Visitors** &mdash; people who looked at the page in the last
  window (usually last 12 months). They have not followed yet.
- **Industry / Job function / Seniority / Location / Company size**
  &mdash; five ways of slicing the audience. LinkedIn categorises
  each follower / visitor into one bucket per dimension.
- **Sponsored vs Organic vs Auto-invited followers** &mdash; source
  of the follow. Organic is the strongest signal (they chose to
  follow); sponsored comes from a paid campaign; auto-invited comes
  from LinkedIn&apos;s connection-suggestion invites.
""")


mode = st.radio("View", ["Followers", "Visitors"],
                  horizontal=True, key="la_mode")

is_followers = (mode == "Followers")
value_col = "followers" if is_followers else "views"
prefix = "followers" if is_followers else "visitors"


def _load(dim):
    return load_csv(f"{prefix}_{dim}.csv")


ind    = _load("industry")
job    = _load("jobfunction")
sen    = _load("seniority")
loc    = _load("location")
size   = _load("companysize")
daily  = _load("daily")

for df in (ind, job, sen, loc, size):
    if not df.empty and value_col in df.columns:
        df[value_col] = pd.to_numeric(df[value_col], errors="coerce") \
            .fillna(0).astype(int)


# ==========================================================================
# Top-line tiles
# ==========================================================================
total = int(sum(df[value_col].sum() for df in (ind, job, sen, loc, size)
                  if not df.empty and value_col in df.columns) / 5) \
    if any(not df.empty for df in (ind, job, sen, loc, size)) else 0
# Note: each dimension sums to roughly the total audience, so we average

def _top(df):
    if df.empty or value_col not in df.columns:
        return ("-", 0)
    r = df.sort_values(value_col, ascending=False).iloc[0]
    return (str(r["dimension"]), int(r[value_col]))

top_ind = _top(ind)
top_job = _top(job)
top_sen = _top(sen)

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile(f"Total {mode.lower()}", f"{total:,}",
              tooltip=f"Rough total {mode.lower()} across all "
                      f"dimensions. LinkedIn assigns each person to "
                      f"one bucket per dimension.")
with k2:
    kpi_tile("Biggest industry", top_ind[0][:28],
              sub=f"{top_ind[1]:,} {mode.lower()}",
              color=ACCENT,
              tooltip="Industry with the largest share of our "
                      "audience.")
with k3:
    kpi_tile("Top job function", top_job[0][:28],
              sub=f"{top_job[1]:,} {mode.lower()}",
              color=ACCENT,
              tooltip="Job function with the largest share.")
with k4:
    kpi_tile("Top seniority", top_sen[0][:28],
              sub=f"{top_sen[1]:,} {mode.lower()}",
              color=ACCENT,
              tooltip="Seniority tier with the largest share.")


# ==========================================================================
# Dimension picker
# ==========================================================================
st.markdown('<h2>Breakdown</h2>', unsafe_allow_html=True)
st.caption("Pick a dimension. Ranked biggest first with progress "
            "bars for scale.")
dim_pick = st.selectbox(
    "Dimension",
    ["Industry", "Job function", "Seniority", "Location",
     "Company size"], key="la_dim")

dim_map = {"Industry": ind, "Job function": job, "Seniority": sen,
             "Location": loc, "Company size": size}
active = dim_map[dim_pick]

if active.empty:
    st.info(f"No data for {dim_pick.lower()} in the current view.")
else:
    show = active.rename(columns={
        "dimension": dim_pick,
        value_col: mode.title(),
    }).sort_values(mode.title(), ascending=False)
    max_v = int(show[mode.title()].max())
    st.dataframe(
        show, use_container_width=True, hide_index=True, height=440,
        column_config={
            mode.title(): st.column_config.ProgressColumn(
                min_value=0, max_value=max_v, format="%d",
                help="Progress bar relative to the largest bucket."),
        })

    # So-what: how concentrated is the top bucket?
    top_val = int(show[mode.title()].iloc[0])
    total_col = int(show[mode.title()].sum())
    top_share = top_val / max(total_col, 1) * 100
    if top_share >= 40:
        so_what(
            f"<strong>{show[dim_pick].iloc[0]}</strong> alone is "
            f"{top_share:.0f}% of the {mode.lower()}. Concentrated "
            f"audience - one segment dominates.", tone="info")
    elif top_share <= 15:
        so_what(
            f"No single {dim_pick.lower()} bucket owns more than "
            f"{top_share:.0f}%. Very spread out - a general-interest "
            f"audience.", tone="info")


# ==========================================================================
# Follower growth (only shown on Followers view)
# ==========================================================================
if is_followers and not daily.empty:
    st.markdown('<h2>Follower growth</h2>', unsafe_allow_html=True)
    st.caption("Weekly rollup of new followers by source. Organic = "
                "chose to follow; sponsored = came from a paid "
                "campaign; auto-invited = LinkedIn suggested us.")

    d = daily.copy()
    for c in ("Sponsored followers", "Organic followers",
                "Auto-invited followers", "Total followers"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int)
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")

    total_new = int(d["Total followers"].sum())
    total_organic = int(d["Organic followers"].sum())
    total_sponsored = int(d["Sponsored followers"].sum())
    total_auto = int(d["Auto-invited followers"].sum())

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        kpi_tile("New followers (window)",
                  f"{total_new:,}",
                  tooltip="Sum of new followers across every day "
                          "in the dataset.")
    with g2:
        organic_pct = total_organic / max(total_new, 1) * 100
        kpi_tile("Organic",
                  f"{total_organic:,}",
                  sub=f"{organic_pct:.0f}% of new followers",
                  color=ACCENT,
                  tooltip="Followers who found us and chose to "
                          "follow. Strongest signal.")
    with g3:
        kpi_tile("Sponsored",
                  f"{total_sponsored:,}",
                  sub="from paid campaigns",
                  color=GOLD if total_sponsored > total_organic
                        else INK_SOFT,
                  tooltip="Followers acquired via LinkedIn paid ads. "
                          "Cost per follow tracked in the ad "
                          "platform.")
    with g4:
        kpi_tile("Auto-invited",
                  f"{total_auto:,}",
                  sub="from LinkedIn invites",
                  tooltip="Followers who arrived via LinkedIn&apos;s "
                          "automated invite system.")

    # Weekly rollup table (no line chart per user preference)
    d["week"] = d["Date"].dt.to_period("W").apply(
        lambda p: p.start_time.date())
    weekly = (d.groupby("week")
               .agg(organic=("Organic followers", "sum"),
                     sponsored=("Sponsored followers", "sum"),
                     auto_invited=("Auto-invited followers", "sum"),
                     total=("Total followers", "sum"))
               .reset_index()
               .sort_values("week", ascending=False))
    weekly.columns = ["Week starting", "Organic", "Sponsored",
                        "Auto-invited", "Total new"]
    st.markdown('<h3 style="margin-top:1.5rem">Recent weeks</h3>',
                 unsafe_allow_html=True)
    st.dataframe(
        weekly.head(20), use_container_width=True, hide_index=True,
        height=380,
        column_config={
            "Organic":      st.column_config.NumberColumn(format="%d"),
            "Sponsored":    st.column_config.NumberColumn(format="%d"),
            "Auto-invited": st.column_config.NumberColumn(format="%d"),
            "Total new":    st.column_config.NumberColumn(format="%d"),
        })

    if total_organic == 0 and total_new > 0:
        so_what(
            "Zero organic follows in the window - every new follower "
            "came from paid or auto-invite. Content is not pulling "
            "people in on its own. Worth reviewing what a follower "
            "actually gets in their feed from us.", tone="warn")
    elif total_organic / max(total_new, 1) >= 0.5:
        so_what(
            f"Organic is <strong>{organic_pct:.0f}%</strong> of new "
            f"followers - the content is doing the work on its own. "
            f"Keep the current posting rhythm.", tone="good")
