"""
LinkedIn - Competitors.

How the GrantsNow page compares to direct competitors on LinkedIn.
One row per competitor with new followers, posts published,
engagements and engagements per post.

Data source: data/competitors.csv (LinkedIn analytics export).
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
st.markdown('<h1>Competitors</h1>', unsafe_allow_html=True)
core_question("How does the GrantsNow LinkedIn page compare with "
                "the direct competition on followers, posting rhythm "
                "and engagement?")
st.caption("Every competitor LinkedIn is tracking, side by side with "
            "us. Sort by new followers, engagements per post, or "
            "raw activity.")
render_status_key()

with st.expander("What each column means", expanded=False):
    st.markdown("""
- **Page** &mdash; the competitor&apos;s LinkedIn page name.
- **New Followers** &mdash; net new follows over the tracking
  window. Bigger = growing faster.
- **Posts** &mdash; posts they published in the window. Higher =
  more air-time.
- **Comments** &mdash; total comments received on their posts.
- **Reactions** &mdash; likes, celebrates, insightful, etc.
- **Engagements** &mdash; comments + reactions combined.
- **Engagements per post** &mdash; average engagement on each post.
  A page with fewer posts but higher per-post engagement is running
  stronger content than one that posts often to little response.
""")


df = load_csv("competitors.csv")
if df.empty:
    st.info("No competitor data. Populate `data/competitors.csv`.")
    st.stop()

for c in ("New Followers", "Posts", "Comments", "Comments per day",
            "Reactions", "engagements", "engagements_per_post"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)


# ==========================================================================
# Top-line tiles
# ==========================================================================
n_pages = len(df)
top_followers = df.loc[df["New Followers"].idxmax()]
top_engpp = df.loc[df["engagements_per_post"].idxmax()] \
    if df["engagements_per_post"].notna().any() else None
top_posts = df.loc[df["Posts"].idxmax()]

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Competitors tracked", f"{n_pages}",
              tooltip="Pages in the competitor set.")
with k2:
    kpi_tile("Follower leader",
              str(top_followers["Page"])[:24],
              sub=f"{int(top_followers['New Followers']):,} new followers",
              color=ACCENT,
              tooltip="Page that added the most new followers over "
                      "the window.")
with k3:
    if top_engpp is not None:
        kpi_tile("Best engagement per post",
                  str(top_engpp["Page"])[:24],
                  sub=f"{top_engpp['engagements_per_post']:.1f} "
                       f"per post",
                  color=ACCENT,
                  tooltip="Page whose posts earn the most engagement "
                          "on average. High = content is landing.")
with k4:
    kpi_tile("Most active poster",
              str(top_posts["Page"])[:24],
              sub=f"{int(top_posts['Posts'])} posts",
              tooltip="Page that published the most posts in the "
                      "window.")


# ==========================================================================
# Sort + table
# ==========================================================================
st.markdown('<h2>Competitor leaderboard</h2>', unsafe_allow_html=True)

sort_by = st.selectbox(
    "Sort by",
    ["New Followers",
     "Engagements per post",
     "Total engagements",
     "Posts published"],
    key="c_sort")

sort_map = {
    "New Followers":         "New Followers",
    "Engagements per post":  "engagements_per_post",
    "Total engagements":     "engagements",
    "Posts published":       "Posts",
}
view = df.sort_values(sort_map[sort_by], ascending=False).copy()

show = view[[
    "Page", "New Followers", "Posts",
    "Comments", "Reactions", "engagements",
    "engagements_per_post"
]].rename(columns={
    "engagements":         "Engagements",
    "engagements_per_post": "Engagements / post",
})
show["Engagements / post"] = show["Engagements / post"].round(1)

max_followers = int(show["New Followers"].max()) or 1
max_engpp = float(show["Engagements / post"].max()) or 1.0
st.dataframe(
    show, use_container_width=True, hide_index=True, height=300,
    column_config={
        "New Followers": st.column_config.ProgressColumn(
            min_value=0, max_value=max_followers, format="%d"),
        "Posts":         st.column_config.NumberColumn(format="%d"),
        "Comments":      st.column_config.NumberColumn(format="%d"),
        "Reactions":     st.column_config.NumberColumn(format="%d"),
        "Engagements":   st.column_config.NumberColumn(format="%d"),
        "Engagements / post":
            st.column_config.ProgressColumn(
                min_value=0, max_value=max_engpp, format="%.1f"),
    })


# ==========================================================================
# So-what read on where we sit
# ==========================================================================
# If our GrantsNow page is in the list, position it explicitly
_ours = df[df["Page"].astype(str).str.contains("GrantsNow",
                                                    case=False,
                                                    na=False)]
if not _ours.empty:
    us = _ours.iloc[0]
    us_rank_fol = int(
        (df["New Followers"] > us["New Followers"]).sum()) + 1
    us_rank_engpp = int(
        (df["engagements_per_post"]
            > us["engagements_per_post"]).sum()) + 1
    so_what(
        f"GrantsNow ranks <strong>#{us_rank_fol} of {n_pages}</strong> "
        f"on new followers ({int(us['New Followers']):,}) and "
        f"<strong>#{us_rank_engpp} of {n_pages}</strong> on "
        f"engagements per post "
        f"({us['engagements_per_post']:.1f}).",
        tone="info")
else:
    # We're not in the tracked set - competitors only
    st.caption("Note: GrantsNow does not appear in this dataset, so "
                "the leaderboard shows the competitor set only. Add "
                "a &lsquo;GrantsNow&rsquo; row to `competitors.csv` "
                "to see us in the ranking.")

# Highlight the biggest gap - who is winning by the most on what?
top_pf = df.sort_values("New Followers", ascending=False).iloc[0]
top_pe = df.sort_values("engagements_per_post", ascending=False).iloc[0]
if str(top_pf["Page"]) != str(top_pe["Page"]):
    so_what(
        f"<strong>{top_pf['Page']}</strong> is winning on volume "
        f"({int(top_pf['New Followers'])} new followers), but "
        f"<strong>{top_pe['Page']}</strong> is winning on quality "
        f"({top_pe['engagements_per_post']:.1f} engagements per "
        f"post). Two different playbooks - worth deciding which one "
        f"we compete on.", tone="info")


# ==========================================================================
# Drill: pick one competitor for detail
# ==========================================================================
st.markdown('<h2>Look at one competitor</h2>', unsafe_allow_html=True)
pick = st.selectbox("Competitor",
                      df["Page"].astype(str).tolist(),
                      key="c_drill")
row = df[df["Page"] == pick].iloc[0]

dc1, dc2, dc3 = st.columns(3)
with dc1:
    kpi_tile("New followers",
              f"{int(row['New Followers']):,}")
with dc2:
    kpi_tile("Posts", f"{int(row['Posts'])}")
with dc3:
    kpi_tile("Engagements / post",
              f"{row['engagements_per_post']:.1f}",
              color=ACCENT)

# Verdict per competitor
posts = int(row["Posts"])
engpp = float(row["engagements_per_post"] or 0)
if posts >= 50 and engpp < 5:
    st.markdown(
        f'<div style="background:#FBF3E5;border-left:3px solid '
        f'{GOLD};padding:.7rem 1rem;margin-top:.8rem;'
        f'border-radius:4px;font-size:.9rem">'
        f'<strong>Read:</strong> {pick} publishes a lot ({posts} '
        f'posts) but each earns little response '
        f'({engpp:.1f}/post). Volume-first strategy that is not '
        f'landing.</div>', unsafe_allow_html=True)
elif engpp >= 15:
    st.markdown(
        f'<div style="background:#EBF3F2;border-left:3px solid '
        f'{ACCENT};padding:.7rem 1rem;margin-top:.8rem;'
        f'border-radius:4px;font-size:.9rem">'
        f'<strong>Read:</strong> {pick} earns strong engagement '
        f'per post ({engpp:.1f}). Whatever they are posting, '
        f'their audience is reacting - worth studying.</div>',
        unsafe_allow_html=True)
