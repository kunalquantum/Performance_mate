"""
GrantsNow LinkedIn Performance Matrix - MVP

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import etl

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# --- palette ----------------------------------------------------------------
INK = "#0B2B2A"
TEAL = "#0E6E68"
TEAL_LT = "#34A79E"
GOLD = "#C99A2E"
SAND = "#F3EFE7"
GREY = "#8A9391"
RED = "#B4462F"

# --- benchmarks (2026 published company-page figures, editable in sidebar) ---
BENCHMARKS = {
    "engagement_rate_median": 0.021,
    "engagement_rate_strong": 0.035,
    "ctr_good": 0.030,
    "posts_per_week_min": 3,
    "posts_per_week_max": 5,
    "follower_growth_monthly": 0.02,
    "prime_days": ["Tuesday", "Wednesday", "Thursday"],
}

st.set_page_config(page_title="LinkedIn Performance Matrix", layout="wide", page_icon="\u25cf")

st.markdown(
    f"""
    <style>
      .stApp {{ background: #FFFFFF; }}
      h1, h2, h3 {{ color: {INK}; letter-spacing: -0.01em; }}
      .eyebrow {{ font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
                  color: {GREY}; font-weight: 600; }}
      .kpi {{ border-left: 3px solid {TEAL}; padding: 0.35rem 0 0.35rem 0.8rem; }}
      .kpi .val {{ font-size: 1.75rem; font-weight: 700; color: {INK}; line-height: 1.1; }}
      .kpi .lbl {{ font-size: 0.78rem; color: {GREY}; }}
      .kpi .note {{ font-size: 0.75rem; font-weight: 600; }}
      .card {{ background: {SAND}; border-radius: 10px; padding: 0.9rem 1.1rem; }}
      div[data-testid="stMetricValue"] {{ color: {INK}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_csv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    for c in df.columns:
        if c.lower() in ("date", "created_date"):
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def kpi(col, label, value, note="", note_colour=GREY):
    col.markdown(
        f"""<div class="kpi"><div class="lbl">{label}</div>
        <div class="val">{value}</div>
        <div class="note" style="color:{note_colour}">{note}</div></div>""",
        unsafe_allow_html=True,
    )


def pct(x, dp=2):
    return "n/a" if pd.isna(x) else f"{x * 100:.{dp}f}%"


posts = load_csv("posts.csv")
daily = load_csv("daily_metrics.csv")
foll_daily = load_csv("followers_daily.csv")
vis_daily = load_csv("visitors_daily.csv")
comp = load_csv("competitors.csv")

if posts.empty:
    st.error("No data found. Run `python etl.py --src <folder with LinkedIn exports>` first.")
    st.stop()

# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="eyebrow">Controls</div>', unsafe_allow_html=True)

    dmin, dmax = posts["created_date"].min(), posts["created_date"].max()
    date_range = st.date_input("Post date range", (dmin.date(), dmax.date()),
                               min_value=dmin.date(), max_value=dmax.date())
    if isinstance(date_range, tuple) and len(date_range) == 2:
        posts = posts[(posts["created_date"] >= pd.Timestamp(date_range[0]))
                      & (posts["created_date"] <= pd.Timestamp(date_range[1]))]

    exclude_event = st.checkbox(
        "Exclude event-week outliers", value=False,
        help="The conference week distorts every average. Tick this to see the baseline page.",
    )
    if exclude_event:
        posts = posts[posts["theme"] != "event_presence"]

    st.divider()
    st.markdown('<div class="eyebrow">Benchmark</div>', unsafe_allow_html=True)
    BENCHMARKS["engagement_rate_median"] = st.number_input(
        "Company-page median ER", value=2.1, step=0.1, format="%.1f") / 100
    BENCHMARKS["engagement_rate_strong"] = st.number_input(
        "Strong ER threshold", value=3.5, step=0.1, format="%.1f") / 100

    st.divider()
    st.markdown('<div class="eyebrow">Enrichment</div>', unsafe_allow_html=True)
    st.caption("Time of day, image and video attributes are not in the LinkedIn export. "
               "Tag them once in the template, upload here, and the timing and creative "
               "views switch on.")
    enrich_file = st.file_uploader("post_enrichment.csv", type=["csv"])

enrich = pd.read_csv(enrich_file) if enrich_file is not None else pd.DataFrame()
if not enrich.empty and "post_id" in enrich.columns:
    posts = posts.merge(enrich.drop(columns=[c for c in ["created_date", "hook"] if c in enrich.columns]),
                        on="post_id", how="left")

# ---------------------------------------------------------------------------
# header
# ---------------------------------------------------------------------------
st.markdown('<div class="eyebrow">GrantsNow &middot; LinkedIn company page</div>', unsafe_allow_html=True)
st.title("Performance Matrix")
st.caption(f"{len(posts)} posts &middot; {posts['created_date'].min():%d %b} to "
           f"{posts['created_date'].max():%d %b %Y} &middot; organic only")

tabs = st.tabs(["Scorecard", "Post matrix", "Content DNA", "Timing", "Audience fit",
                "Competitors", "How to use"])

# ---------------------------------------------------------------------------
# 1. Scorecard
# ---------------------------------------------------------------------------
with tabs[0]:
    weeks = max((posts["created_date"].max() - posts["created_date"].min()).days / 7, 1)
    cadence = len(posts) / weeks
    med_er = posts["engagement_rate"].median()
    med_imp = posts["Impressions"].median()
    med_ctr = posts["ctr"].median()
    new_foll = foll_daily["Total followers"].sum() if not foll_daily.empty else np.nan
    page_views = vis_daily["Total page views (total)"].sum() if not vis_daily.empty else np.nan

    c = st.columns(6)
    bm = BENCHMARKS["engagement_rate_median"]
    kpi(c[0], "Median engagement rate", pct(med_er),
        f"{med_er / bm:.1f}x the {pct(bm,1)} page median",
        TEAL if med_er >= bm else RED)
    kpi(c[1], "Median impressions per post", f"{med_imp:,.0f}",
        f"top post {posts['Impressions'].max():,.0f}")
    kpi(c[2], "Median CTR", pct(med_ctr),
        "good is 3%+", TEAL if med_ctr >= BENCHMARKS["ctr_good"] else GOLD)
    kpi(c[3], "Posting cadence", f"{cadence:.1f}/wk",
        "target 3 to 5 per week",
        TEAL if BENCHMARKS["posts_per_week_min"] <= cadence <= BENCHMARKS["posts_per_week_max"] else GOLD)
    kpi(c[4], "New followers in window", f"{new_foll:,.0f}" if pd.notna(new_foll) else "n/a",
        f"{foll_daily['Organic followers'].sum():,.0f} organic" if not foll_daily.empty else "")
    kpi(c[5], "Page views in window", f"{page_views:,.0f}" if pd.notna(page_views) else "n/a",
        f"{vis_daily['Total unique visitors (total)'].sum():,.0f} unique visitors"
        if not vis_daily.empty else "")

    st.markdown("")
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Reach and engagement over time")
        if not daily.empty:
            d = daily.rename(columns={"Impressions (total)": "Impressions",
                                      "Engagement rate (total)": "Engagement rate"})
            base = alt.Chart(d).encode(x=alt.X("Date:T", title=None))
            bar = base.mark_bar(color=TEAL_LT, opacity=0.55, size=9).encode(
                y=alt.Y("Impressions:Q", title="Impressions"),
                tooltip=["Date:T", "Impressions:Q", alt.Tooltip("Engagement rate:Q", format=".2%")])
            line = base.mark_line(color=GOLD, strokeWidth=2).encode(
                y=alt.Y("Engagement rate:Q", title="Engagement rate", axis=alt.Axis(format="%")))
            st.altair_chart(alt.layer(bar, line).resolve_scale(y="independent").properties(height=280),
                            use_container_width=True)

    with right:
        st.subheader("Where the reach came from")
        theme_roll = (posts.groupby("theme")
                      .agg(posts=("post_id", "count"), impressions=("Impressions", "sum"),
                           median_er=("engagement_rate", "median"))
                      .reset_index().sort_values("impressions", ascending=False))
        st.altair_chart(
            alt.Chart(theme_roll).mark_bar(color=TEAL, cornerRadiusEnd=3).encode(
                y=alt.Y("theme:N", sort="-x", title=None),
                x=alt.X("impressions:Q", title="Impressions"),
                tooltip=["theme", "posts", "impressions",
                         alt.Tooltip("median_er:Q", format=".2%")],
            ).properties(height=280), use_container_width=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**Read this first.** Every median above is pulled upward by the conference "
                "week. Tick *Exclude event-week outliers* in the sidebar and compare the two "
                "numbers. The gap is the size of the reach the page loses when there is no "
                "event to post about.")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2. Post matrix
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Reach against engagement quality")
    st.caption("Vertical line is median reach for the window. Horizontal line is the "
               "company-page benchmark. Top right is what to make more of.")

    p = posts.copy()
    p["label"] = p["hook"].fillna("Article").str.slice(0, 55)
    med_imp = p["Impressions"].median()

    scatter = alt.Chart(p).mark_circle(opacity=0.8).encode(
        x=alt.X("Impressions:Q", title="Impressions", scale=alt.Scale(type="log")),
        y=alt.Y("engagement_rate:Q", title="Engagement rate", axis=alt.Axis(format="%")),
        size=alt.Size("engagements_total:Q", title="Engagements", scale=alt.Scale(range=[40, 700])),
        color=alt.Color("theme:N", scale=alt.Scale(scheme="tealblues"), title="Theme"),
        tooltip=["label", "created_date:T", "theme", "format_inferred", "Impressions",
                 alt.Tooltip("engagement_rate:Q", format=".2%"),
                 alt.Tooltip("ctr:Q", format=".2%"), "Likes", "Comments", "Reposts"],
    )
    vline = alt.Chart(pd.DataFrame({"x": [med_imp]})).mark_rule(
        color=GREY, strokeDash=[4, 4]).encode(x="x:Q")
    hline = alt.Chart(pd.DataFrame({"y": [BENCHMARKS["engagement_rate_median"]]})).mark_rule(
        color=GOLD, strokeDash=[4, 4]).encode(y="y:Q")
    st.altair_chart((scatter + vline + hline).properties(height=420), use_container_width=True)

    st.subheader("Post league table")
    show = p[["created_date", "day_of_week", "hook", "theme", "format_inferred", "cta_type",
              "word_count", "hashtag_count", "Impressions", "engagements_total",
              "engagement_rate", "ctr", "Likes", "Comments", "Reposts"]].sort_values(
        "engagement_rate", ascending=False)
    st.dataframe(
        show, use_container_width=True, hide_index=True,
        column_config={
            "created_date": st.column_config.DateColumn("Date", format="DD MMM"),
            "hook": st.column_config.TextColumn("Opening line", width="large"),
            "engagement_rate": st.column_config.NumberColumn("ER", format="%.2f%%"),
            "ctr": st.column_config.NumberColumn("CTR", format="%.2f%%"),
        },
    )

# ---------------------------------------------------------------------------
# 3. Content DNA
# ---------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Which content attributes move the numbers")
    st.caption("Median is used instead of mean so one viral post cannot carry a group. "
               "Groups with fewer than 3 posts are flagged, treat them as a hint only.")

    metric = st.radio("Measure by", ["engagement_rate", "Impressions", "ctr"],
                      horizontal=True, format_func=lambda x:
                      {"engagement_rate": "Engagement rate", "Impressions": "Impressions",
                       "ctr": "Click-through rate"}[x])

    cat_features = [c for c in ["format_inferred", "theme", "cta_type", "length_band",
                                "day_of_week", "media_type", "image_subject",
                                "image_colour_theme", "has_face_in_image", "text_on_image",
                                "target_region", "campaign"] if c in posts.columns]
    chosen = st.multiselect("Attributes", cat_features,
                            default=[c for c in ["format_inferred", "theme", "cta_type",
                                                 "length_band"] if c in cat_features])

    rows = []
    overall = posts[metric].median()
    for feat in chosen:
        g = posts.dropna(subset=[feat]).groupby(feat)[metric].agg(["median", "count"])
        for value, r in g.iterrows():
            if str(value).strip() in ("", "nan"):
                continue
            rows.append({"Attribute": feat, "Value": str(value), "Median": r["median"],
                         "Posts": int(r["count"]),
                         "Lift vs page median": r["median"] / overall - 1 if overall else np.nan,
                         "Reliable": "yes" if r["count"] >= 3 else "thin"})
    lift = pd.DataFrame(rows).sort_values("Median", ascending=False)

    if lift.empty:
        st.info("Pick at least one attribute.")
    else:
        fmt = "%.2f%%" if metric != "Impressions" else "%.0f"
        st.dataframe(lift, use_container_width=True, hide_index=True,
                     column_config={
                         "Median": st.column_config.NumberColumn(format=fmt),
                         "Lift vs page median": st.column_config.NumberColumn(format="%.0f%%"),
                     })
        st.altair_chart(
            alt.Chart(lift).mark_bar(cornerRadiusEnd=3).encode(
                y=alt.Y("Value:N", sort="-x", title=None),
                x=alt.X("Median:Q", title=metric,
                        axis=alt.Axis(format="%" if metric != "Impressions" else "s")),
                color=alt.Color("Reliable:N",
                                scale=alt.Scale(domain=["yes", "thin"], range=[TEAL, GREY]),
                                title="Sample"),
                row=alt.Row("Attribute:N", title=None, header=alt.Header(labelAngle=0,
                                                                        labelAlign="left")),
                tooltip=["Attribute", "Value", "Posts",
                         alt.Tooltip("Median:Q", format=".4f")],
            ).properties(height=alt.Step(20)), use_container_width=True)

    st.divider()
    st.subheader("Numeric levers")
    num_feats = [c for c in ["word_count", "hashtag_count", "hook_len", "line_breaks",
                             "emoji_count", "has_link", "has_question", "mention_count",
                             "video_length_sec"] if c in posts.columns]
    corr = []
    for f in num_feats:
        s = pd.to_numeric(posts[f], errors="coerce")
        if s.nunique(dropna=True) < 2:
            continue
        corr.append({"Feature": f,
                     "vs engagement rate": s.corr(posts["engagement_rate"], method="spearman"),
                     "vs impressions": s.corr(posts["Impressions"], method="spearman")})
    cdf = pd.DataFrame(corr)
    if not cdf.empty:
        st.dataframe(cdf.sort_values("vs engagement rate", ascending=False),
                     use_container_width=True, hide_index=True,
                     column_config={"vs engagement rate": st.column_config.NumberColumn(format="%.2f"),
                                    "vs impressions": st.column_config.NumberColumn(format="%.2f")})
        st.caption(f"Spearman rank correlation on {len(posts)} posts. Anything between "
                   "-0.4 and 0.4 at this sample size is noise. Treat these as questions "
                   "to test, not answers.")

    st.divider()
    st.subheader("Hashtags")
    tags = (posts.assign(tag=posts["hashtag_list"].fillna("").str.split(", "))
            .explode("tag"))
    tags = tags[tags["tag"].str.strip() != ""]
    if not tags.empty:
        tagroll = (tags.groupby("tag").agg(posts=("post_id", "count"),
                                           median_er=("engagement_rate", "median"),
                                           median_imp=("Impressions", "median"))
                   .reset_index().sort_values("posts", ascending=False))
        st.dataframe(tagroll, use_container_width=True, hide_index=True,
                     column_config={"median_er": st.column_config.NumberColumn("Median ER",
                                                                               format="%.2f%%"),
                                    "median_imp": st.column_config.NumberColumn("Median impressions",
                                                                                format="%.0f")})

# ---------------------------------------------------------------------------
# 4. Timing
# ---------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Day of week")
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = (posts.groupby("day_of_week")
           .agg(posts=("post_id", "count"), median_er=("engagement_rate", "median"),
                median_imp=("Impressions", "median")).reindex(order).reset_index())
    dow["prime"] = dow["day_of_week"].isin(BENCHMARKS["prime_days"])

    c1, c2 = st.columns(2)
    with c1:
        st.altair_chart(
            alt.Chart(dow.dropna(subset=["posts"])).mark_bar(cornerRadiusEnd=3).encode(
                x=alt.X("day_of_week:N", sort=order, title=None),
                y=alt.Y("median_er:Q", title="Median engagement rate", axis=alt.Axis(format="%")),
                color=alt.Color("prime:N", scale=alt.Scale(domain=[True, False],
                                                           range=[TEAL, GREY]),
                                title="Published benchmark prime day"),
                tooltip=["day_of_week", "posts", alt.Tooltip("median_er:Q", format=".2%")],
            ).properties(height=300), use_container_width=True)
    with c2:
        st.altair_chart(
            alt.Chart(dow.dropna(subset=["posts"])).mark_bar(cornerRadiusEnd=3, color=TEAL_LT).encode(
                x=alt.X("day_of_week:N", sort=order, title=None),
                y=alt.Y("median_imp:Q", title="Median impressions"),
                tooltip=["day_of_week", "posts", "median_imp"],
            ).properties(height=300), use_container_width=True)

    st.dataframe(dow, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Time of day")
    if "post_time_local" in posts.columns and posts["post_time_local"].notna().any():
        t = posts.dropna(subset=["post_time_local"]).copy()
        t["hour"] = pd.to_datetime(t["post_time_local"], format="%H:%M",
                                   errors="coerce").dt.hour
        t = t.dropna(subset=["hour"])
        heat = (t.groupby(["day_of_week", "hour"])
                .agg(median_er=("engagement_rate", "median"), posts=("post_id", "count"))
                .reset_index())
        st.altair_chart(
            alt.Chart(heat).mark_rect().encode(
                x=alt.X("hour:O", title="Hour, local"),
                y=alt.Y("day_of_week:N", sort=order, title=None),
                color=alt.Color("median_er:Q", scale=alt.Scale(scheme="teals"),
                                title="Median ER"),
                tooltip=["day_of_week", "hour", "posts",
                         alt.Tooltip("median_er:Q", format=".2%")],
            ).properties(height=260), use_container_width=True)
    else:
        st.info("LinkedIn exports the post date but not the post time. Fill "
                "`post_time_local` and `timezone` in the enrichment template, upload it in "
                "the sidebar, and the day-by-hour heatmap appears here.")

    with st.expander("Published prime-time windows to test against"):
        st.markdown(
            """
| Audience | Primary window | Secondary window |
|---|---|---|
| UK | Tue to Thu, 11:00 to 13:00 | 16:00 to 18:00 |
| US | Tue to Thu, 10:00 to 12:00 ET | 16:00 to 18:00 ET |
| India | Tue to Thu, 11:00 to 13:00 IST | 19:00 to 21:00 IST |
| Australia | Tue to Thu, 10:00 to 12:00 AEST | 18:00 to 20:00 AEST |

Weekends drop 45 to 70 percent for B2B audiences across every region. The first 60
minutes after publishing carry the most algorithmic weight, so a post that lands
when the target region is asleep rarely recovers.
""")

# ---------------------------------------------------------------------------
# 5. Audience fit
# ---------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Who follows against who visits")
    st.caption("Followers are the audience the content is served to. Visitors are the people "
               "who went looking. Where the two lists disagree, the content is reaching a "
               "different group from the one showing buying intent.")

    dim = st.selectbox("Dimension", ["industry", "seniority", "jobfunction", "companysize",
                                     "location"])
    f = load_csv(f"followers_{dim}.csv")
    v = load_csv(f"visitors_{dim}.csv")

    if f.empty and v.empty:
        st.info("No demographic export for this dimension.")
    else:
        c1, c2 = st.columns(2)
        for col, df, val, title, colour in [(c1, f, "followers", "Followers", TEAL),
                                            (c2, v, "views", "Page visitors", GOLD)]:
            if df.empty:
                continue
            top = df.nlargest(12, val)
            top["share"] = top[val] / df[val].sum()
            with col:
                st.markdown(f"**{title}**")
                st.altair_chart(
                    alt.Chart(top).mark_bar(cornerRadiusEnd=3, color=colour).encode(
                        y=alt.Y("dimension:N", sort="-x", title=None),
                        x=alt.X("share:Q", title="Share", axis=alt.Axis(format="%")),
                        tooltip=["dimension", val, alt.Tooltip("share:Q", format=".1%")],
                    ).properties(height=320), use_container_width=True)

        if not f.empty and not v.empty:
            m = f.merge(v, on="dimension", how="outer").fillna(0)
            m["follower_share"] = m["followers"] / m["followers"].sum()
            m["visitor_share"] = m["views"] / m["views"].sum()
            m["gap"] = m["visitor_share"] - m["follower_share"]
            st.markdown("**Intent gap.** Positive means the group visits the page more than "
                        "its share of the follower base. That is a group worth writing for.")
            st.dataframe(
                m.sort_values("gap", ascending=False)[
                    ["dimension", "followers", "views", "follower_share", "visitor_share", "gap"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "follower_share": st.column_config.NumberColumn(format="%.1f%%"),
                    "visitor_share": st.column_config.NumberColumn(format="%.1f%%"),
                    "gap": st.column_config.NumberColumn("Gap", format="%.1f%%"),
                })

    st.divider()
    st.subheader("Follower growth")
    if not foll_daily.empty:
        fd = foll_daily.copy()
        fd["cumulative"] = fd["Total followers"].cumsum()
        st.altair_chart(
            alt.Chart(fd).mark_area(color=TEAL, opacity=0.25, line={"color": TEAL}).encode(
                x=alt.X("Date:T", title=None), y=alt.Y("cumulative:Q", title="Net new followers"),
                tooltip=["Date:T", "Total followers", "Organic followers", "cumulative"],
            ).properties(height=240), use_container_width=True)

# ---------------------------------------------------------------------------
# 6. Competitors
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Competitor set")
    if comp.empty:
        st.info("No competitor export loaded.")
    else:
        cdf = comp.copy()
        cdf["share_of_engagement"] = cdf["engagements"] / cdf["engagements"].sum()
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(
                alt.Chart(cdf).mark_bar(cornerRadiusEnd=3).encode(
                    y=alt.Y("Page:N", sort="-x", title=None),
                    x=alt.X("share_of_engagement:Q", title="Share of engagement",
                            axis=alt.Axis(format="%")),
                    color=alt.condition(alt.datum.Page == "GrantsNow",
                                        alt.value(GOLD), alt.value(TEAL)),
                    tooltip=["Page", "Posts", "Reactions", "Comments",
                             alt.Tooltip("share_of_engagement:Q", format=".1%")],
                ).properties(height=280), use_container_width=True)
        with c2:
            st.altair_chart(
                alt.Chart(cdf).mark_circle(size=260).encode(
                    x=alt.X("Posts:Q", title="Posts published"),
                    y=alt.Y("engagements_per_post:Q", title="Engagements per post"),
                    color=alt.condition(alt.datum.Page == "GrantsNow",
                                        alt.value(GOLD), alt.value(TEAL)),
                    tooltip=["Page", "Posts", "engagements_per_post", "New Followers"],
                ).properties(height=280), use_container_width=True)
        st.dataframe(cdf, use_container_width=True, hide_index=True)
        st.caption("Volume and efficiency are different games. A page above the pack on "
                   "engagements per post with fewer posts has the stronger content and the "
                   "weaker cadence.")

# ---------------------------------------------------------------------------
# 7. How to use
# ---------------------------------------------------------------------------
with tabs[6]:
    st.subheader("What this MVP does and does not do")
    st.markdown(
        """
**Comes straight from the LinkedIn export**

Impressions, unique impressions, clicks, CTR, reactions, comments, reposts, engagement
rate, daily totals, new followers split by organic and auto-invited, page views and
unique visitors by tab and device, follower and visitor demographics across location,
job function, seniority, industry and company size, and the competitor benchmark table.

**Derived from the post copy inside this tool**

Word count, character count, line breaks, hashtag count and list, links, mentions,
emoji count, question present, call-to-action type, theme, opening hook and hook
length, length band, format, day of week.

**Needs one round of manual tagging**

Time of day, timezone, target region, media type, image subject, image colour theme,
face present, text burnt into the image, video length, video topic, captions,
campaign. LinkedIn does not export any of these. Download the template below, tag
each post once, and upload it in the sidebar.
        """)

    tpl = os.path.join(DATA_DIR, "post_enrichment_template.csv")
    if os.path.exists(tpl):
        with open(tpl, "rb") as fh:
            st.download_button("Download the enrichment template", fh,
                               file_name="post_enrichment_template.csv", mime="text/csv")

    st.divider()
    st.markdown(
        """
**Refreshing the data**

Export the four files from LinkedIn analytics, drop them in a folder, then run
`python etl.py --src <folder> --out ./data` and reload the page.

**Honest limits at this sample size**

The window holds a small number of posts across roughly five weeks, and one conference
week accounts for most of the reach. Nothing in the Content DNA tab is statistically
significant yet. Use it to form a hypothesis, then run the same post shape three or
four times and check whether the pattern holds.
        """)
