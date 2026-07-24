"""
LinkedIn Post Performance Matrix - Visualize page.
"""
from shared import (inject_css, linkedin_setup, INK, INK_SOFT, MUTED, LINE,
                     BG, BG_SOFT, ACCENT, ACCENT_SOFT, WARN, GOLD,
                     FEATURES, LABELS, load_csv)
import os, re
import altair as alt
import pandas as pd
import streamlit as st

import scoring
import predictor
import image_analysis

inject_css()
ctx = linkedin_setup("Visualize")

app             = "LinkedIn Post Matrix"
mode            = ctx.mode
posts_raw       = ctx.posts_raw
posts           = ctx.posts
scored          = ctx.scored
lift            = ctx.lift
live_features   = ctx.live_features
start_date      = ctx.start_date
end_date        = ctx.end_date
min_d           = ctx.min_d
max_d           = ctx.max_d
hashtag_library = ctx.hashtag_library
curated_active  = ctx.curated_active
drop_event      = ctx.drop_event
scope           = ctx.scope
drop_topics     = ctx.drop_topics
drop_asks       = ctx.drop_asks
drop_days       = ctx.drop_days
drop_lengths    = ctx.drop_lengths
drop_palettes   = ctx.drop_palettes
drop_faces      = ctx.drop_faces
drop_textimg    = ctx.drop_textimg
drop_media      = ctx.drop_media
drop_campaigns  = ctx.drop_campaigns

# ---- helper: stat tile ----
def stat_tile(label, value, delta=""):
    st.markdown(
        f'<div class="stat"><div class="k">{label}</div>'
        f'<div class="v">{value}</div>'
        f'<div class="d">{delta}</div></div>', unsafe_allow_html=True)

# ---- 9 tabs, one per analytical segment ----
tab_overview, tab_time, tab_content, tab_reach, tab_signals, \
tab_winners, tab_ab, tab_model, tab_corr = st.tabs([
    "Overview", "Time", "Content strategy", "Reach & engagement",
    "Caption signals", "What wins", "Matched pairs (A/B)",
    "Model insights", "Correlations",
])

dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]

# =======================================================================
# OVERVIEW
# =======================================================================
with tab_overview:
    st.markdown('<h3>At a glance</h3>', unsafe_allow_html=True)
    n_posts = len(scored)
    median_reach = scored["reach_index"].median()
    median_er = scored["engagement_index"].median()
    best_score = scored["post_score"].max()
    total_views = int(scored["Impressions"].sum())

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: stat_tile("Posts", f"{n_posts}", "in the window")
    with k2: stat_tile("Total views", f"{total_views:,}", "impressions")
    with k3: stat_tile("Views vs normal", f"{median_reach:.2f}x", "median")
    with k4: stat_tile("Reactions vs normal", f"{median_er:.2f}x", "median")
    with k5: stat_tile("Top score", f"{best_score:.0f}", "out of 100")

    # score distribution
    st.markdown('<h3 style="margin-top:2rem">Score distribution</h3>',
                unsafe_allow_html=True)
    st.caption("How the composite score is spread. Where the mass sits "
               "tells you whether the page has a few big hits or a broad "
               "middle.")
    hist = alt.Chart(scored).mark_bar(color=ACCENT, opacity=0.85).encode(
        x=alt.X("post_score:Q", bin=alt.Bin(maxbins=25), title="Score"),
        y=alt.Y("count():Q", title="Posts"),
        tooltip=[alt.Tooltip("post_score:Q", bin=True, title="Score bin"),
                 alt.Tooltip("count():Q", title="Posts")],
    ).properties(height=220)
    st.altair_chart(hist, use_container_width=True)

    # weekly cadence + median score
    st.markdown('<h3 style="margin-top:2rem">Post cadence and score, '
                'by week</h3>', unsafe_allow_html=True)
    st.caption("Bars = post count per week. Dotted line = weekly median "
               "score. Gaps and lulls jump out.")
    weekly = scored.copy()
    weekly["week"] = weekly["created_date"].dt.to_period("W").dt.start_time
    weekly_agg = weekly.groupby("week", as_index=False).agg(
        posts=("post_score", "count"),
        median_score=("post_score", "median"),
    )
    _bars = alt.Chart(weekly_agg).mark_bar(color=MUTED, opacity=0.6).encode(
        x=alt.X("week:T", title=None),
        y=alt.Y("posts:Q", title="Posts / week",
                axis=alt.Axis(labelColor=MUTED)),
        tooltip=[alt.Tooltip("week:T", format="%d %b %Y", title="Week"),
                 alt.Tooltip("posts:Q"),
                 alt.Tooltip("median_score:Q", format=".1f")],
    )
    _line = alt.Chart(weekly_agg).mark_line(
        color=ACCENT, strokeDash=[3, 3], strokeWidth=2).encode(
        x="week:T",
        y=alt.Y("median_score:Q", title="Median score",
                axis=alt.Axis(labelColor=ACCENT, titleColor=ACCENT)))
    st.altair_chart(alt.layer(_bars, _line).resolve_scale(y="independent"
                    ).properties(height=250), use_container_width=True)

# =======================================================================
# TIME
# =======================================================================
with tab_time:
    st.markdown('<h3>Calendar heatmap</h3>', unsafe_allow_html=True)
    st.caption("Every day of the year. Colour = score of the post that "
               "day. Blank cells had no post.")
    cal = scored.copy()
    cal["week_start"] = cal["created_date"].dt.to_period("W").dt.start_time
    cal["dow"] = cal["created_date"].dt.day_name()
    heat = alt.Chart(cal).mark_rect().encode(
        x=alt.X("week_start:T", title=None,
                axis=alt.Axis(labelColor=MUTED)),
        y=alt.Y("dow:N", sort=dow_order, title=None,
                axis=alt.Axis(labelColor=MUTED)),
        color=alt.Color("post_score:Q", scale=alt.Scale(scheme="teals"),
                        title="Score"),
        tooltip=[alt.Tooltip("created_date:T", format="%a %d %b %Y"),
                 alt.Tooltip("post_score:Q", format=".0f", title="Score"),
                 alt.Tooltip("hook_short:N", title="First line")],
    ).properties(height=200)
    st.altair_chart(heat, use_container_width=True)

    # 4-week rolling average score
    st.markdown('<h3 style="margin-top:2rem">Rolling 4-week average '
                'score</h3>', unsafe_allow_html=True)
    st.caption("Smooths out weekly noise. Rising line = the page is "
               "getting better; falling = the reverse.")
    roll = scored.sort_values("created_date").set_index("created_date")
    roll["rolling"] = roll["post_score"].rolling(
        window=4, min_periods=1).mean()
    roll_df = roll.reset_index()[["created_date", "post_score", "rolling"]]
    base = alt.Chart(roll_df).encode(x=alt.X("created_date:T", title=None))
    raw = base.mark_circle(color=MUTED, opacity=0.4, size=30).encode(
        y=alt.Y("post_score:Q", title="Score"))
    rl = base.mark_line(color=ACCENT, strokeWidth=2.4).encode(
        y="rolling:Q")
    st.altair_chart((raw + rl).properties(height=260),
                    use_container_width=True)

    # posts per month volume + views per month
    st.markdown('<h3 style="margin-top:2rem">Volume by month</h3>',
                unsafe_allow_html=True)
    st.caption("Posts published per month and total views earned per "
               "month.")
    m = scored.copy()
    m["month"] = m["created_date"].dt.to_period("M").dt.start_time
    month_agg = m.groupby("month", as_index=False).agg(
        posts=("post_score", "count"),
        views=("Impressions", "sum"))
    mv1, mv2 = st.columns(2)
    with mv1:
        st.altair_chart(alt.Chart(month_agg).mark_bar(
            color=ACCENT, opacity=0.85).encode(
            x=alt.X("month:T", title=None),
            y=alt.Y("posts:Q", title="Posts"),
            tooltip=[alt.Tooltip("month:T", format="%b %Y"),
                     alt.Tooltip("posts:Q")]).properties(height=240),
            use_container_width=True)
    with mv2:
        st.altair_chart(alt.Chart(month_agg).mark_bar(
            color=INK_SOFT).encode(
            x=alt.X("month:T", title=None),
            y=alt.Y("views:Q", title="Total views"),
            tooltip=[alt.Tooltip("month:T", format="%b %Y"),
                     alt.Tooltip("views:Q", format=",")]).properties(
                height=240),
            use_container_width=True)

    # day-of-week ridgeline (small multiples of density)
    st.markdown('<h3 style="margin-top:2rem">Score distribution by '
                'publish day</h3>', unsafe_allow_html=True)
    st.caption("Where does each day sit? Wider chunks = more posts. "
               "Shifts to the right = higher-scoring days.")
    st.altair_chart(alt.Chart(scored).mark_area(
        interpolate="monotone", opacity=0.85, color=ACCENT
    ).transform_density(
        "post_score", groupby=["day_of_week"], as_=["post_score", "d"],
        extent=[0, 100], steps=40
    ).encode(
        x=alt.X("post_score:Q", title="Score"),
        y=alt.Y("d:Q", title=None, axis=None),
        row=alt.Row("day_of_week:N", sort=dow_order, title=None,
                    header=alt.Header(labelFontSize=11,
                                      labelAlign="right", labelAngle=0)),
    ).properties(width="container", height=45),
                    use_container_width=True)

# =======================================================================
# CONTENT STRATEGY
# =======================================================================
with tab_content:
    st.markdown('<h3>Day of week × format</h3>', unsafe_allow_html=True)
    st.caption("Median score at each intersection. Darker = better. "
               "Cells with fewer than 2 posts are hidden.")
    combo = (scored.groupby(["day_of_week", "format_inferred"])
                    .agg(n=("post_score", "count"),
                         med=("post_score", "median")).reset_index())
    combo = combo[combo["n"] >= 2]
    _rect = alt.Chart(combo).mark_rect(stroke=BG, strokeWidth=2).encode(
        x=alt.X("format_inferred:N", title=None),
        y=alt.Y("day_of_week:N", sort=dow_order, title=None),
        color=alt.Color("med:Q", scale=alt.Scale(scheme="teals"),
                        title="Median score"),
        tooltip=[alt.Tooltip("day_of_week:N", title="Day"),
                 alt.Tooltip("format_inferred:N", title="Format"),
                 alt.Tooltip("n:Q", title="Posts"),
                 alt.Tooltip("med:Q", format=".1f")],
    ).properties(height=260)
    _lbl = alt.Chart(combo).mark_text(color="white", fontSize=11,
                                      fontWeight="bold").encode(
        x="format_inferred:N",
        y=alt.Y("day_of_week:N", sort=dow_order),
        text=alt.Text("med:Q", format=".0f"))
    st.altair_chart(_rect + _lbl, use_container_width=True)

    st.markdown('<h3 style="margin-top:2rem">Median score by category</h3>',
                unsafe_allow_html=True)
    st.caption("Vertical line = page median. Teal = above it.")

    def cat_bars(field, title):
        s = scored.copy()
        s = s[s[field].astype(str).str.strip().replace("nan", "").ne("")]
        agg = s.groupby(field, as_index=False).agg(
            med=("post_score", "median"), n=("post_score", "count"))
        agg = agg[agg["n"] >= 2]
        overall = scored["post_score"].median()
        chart = alt.Chart(agg).mark_bar(cornerRadiusEnd=3).encode(
            y=alt.Y(f"{field}:N", sort="-x", title=None),
            x=alt.X("med:Q", title="Median score"),
            color=alt.condition(alt.datum.med >= overall,
                                alt.value(ACCENT), alt.value(MUTED)),
            tooltip=[alt.Tooltip(f"{field}:N", title=title),
                     alt.Tooltip("n:Q", title="Posts"),
                     alt.Tooltip("med:Q", format=".1f")])
        rule = alt.Chart(pd.DataFrame({"x": [overall]})).mark_rule(
            color=INK_SOFT, strokeDash=[3, 3]).encode(x="x:Q")
        return (chart + rule).properties(height=max(160, 24 * len(agg)))

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Topic**")
        st.altair_chart(cat_bars("theme", "Topic"),
                        use_container_width=True)
    with c2:
        st.markdown("**Ask (CTA)**")
        st.altair_chart(cat_bars("cta_type", "Ask"),
                        use_container_width=True)
    c3, c4 = st.columns(2, gap="large")
    with c3:
        st.markdown("**Publish day**")
        st.altair_chart(cat_bars("day_of_week", "Day"),
                        use_container_width=True)
    with c4:
        st.markdown("**Length band**")
        st.altair_chart(cat_bars("length_band", "Length"),
                        use_container_width=True)
    if "image_colour_theme" in scored.columns:
        c5, c6 = st.columns(2, gap="large")
        with c5:
            st.markdown("**Image palette**")
            st.altair_chart(cat_bars("image_colour_theme", "Palette"),
                            use_container_width=True)
        with c6:
            if "has_face_in_image" in scored.columns:
                st.markdown("**Face in image**")
                st.altair_chart(cat_bars("has_face_in_image", "Face"),
                                use_container_width=True)

    # topic x outcome heatmap
    st.markdown('<h3 style="margin-top:2rem">Topic × outcome</h3>',
                unsafe_allow_html=True)
    st.caption("Where does each topic land? Rows = topic, columns = "
               "outcome. Numbers = post count.")
    tout = (scored.groupby(["theme", "failure_mode"])
                   .size().reset_index(name="n"))
    st.altair_chart(alt.Chart(tout).mark_rect(stroke=BG, strokeWidth=2
    ).encode(
        x=alt.X("failure_mode:N", title=None,
                sort=list(scoring.DIAGNOSES.keys())),
        y=alt.Y("theme:N", title=None),
        color=alt.Color("n:Q", scale=alt.Scale(scheme="teals"),
                        title="Posts"),
        tooltip=["theme", "failure_mode", "n"]
    ).properties(height=260) + alt.Chart(tout).mark_text(
        color="white", fontSize=11
    ).encode(
        x=alt.X("failure_mode:N",
                sort=list(scoring.DIAGNOSES.keys())),
        y="theme:N",
        text="n:Q"), use_container_width=True)

# =======================================================================
# REACH & ENGAGEMENT
# =======================================================================
with tab_reach:
    st.markdown('<h3>Reach vs engagement</h3>', unsafe_allow_html=True)
    st.caption("Top right = the sweet spot. Bottom left = retire the "
               "format. Size = clicks, colour = topic.")
    re_scatter = alt.Chart(scored).mark_circle(
        opacity=0.85, stroke=INK, strokeWidth=0.3).encode(
        x=alt.X("reach_index:Q", title="Views vs a normal post",
                scale=alt.Scale(
                    domain=[0, scored["reach_index"].quantile(0.98) * 1.1])),
        y=alt.Y("engagement_index:Q",
                title="Reactions vs a normal post",
                scale=alt.Scale(
                    domain=[0,
                            scored["engagement_index"].quantile(0.98) * 1.1])),
        size=alt.Size("Clicks:Q", scale=alt.Scale(range=[40, 400]),
                      title="Clicks"),
        color=alt.Color("theme:N", scale=alt.Scale(scheme="tealblues"),
                        title="Topic"),
        tooltip=[alt.Tooltip("created_date:T", format="%d %b %Y"),
                 alt.Tooltip("hook_short:N", title="First line"),
                 alt.Tooltip("theme:N", title="Topic"),
                 alt.Tooltip("reach_index:Q", format=".2f",
                             title="Views vs normal"),
                 alt.Tooltip("engagement_index:Q", format=".2f",
                             title="Reactions vs normal"),
                 alt.Tooltip("post_score:Q", format=".0f", title="Score")],
    ).properties(height=420)
    par_x = alt.Chart(pd.DataFrame({"v": [1.0]})).mark_rule(
        color=MUTED, strokeDash=[3, 3]).encode(x="v:Q")
    par_y = alt.Chart(pd.DataFrame({"v": [1.0]})).mark_rule(
        color=MUTED, strokeDash=[3, 3]).encode(y="v:Q")
    st.altair_chart(re_scatter + par_x + par_y,
                    use_container_width=True)

    # 2D density
    st.markdown('<h3 style="margin-top:2rem">Where posts cluster</h3>',
                unsafe_allow_html=True)
    st.caption("Same axes as above, but coloured by post density. "
               "Bright = many posts sit in that zone; dim = outliers.")
    st.altair_chart(alt.Chart(scored).mark_rect().encode(
        x=alt.X("reach_index:Q",
                bin=alt.Bin(maxbins=25),
                title="Views vs a normal post"),
        y=alt.Y("engagement_index:Q",
                bin=alt.Bin(maxbins=25),
                title="Reactions vs a normal post"),
        color=alt.Color("count():Q",
                        scale=alt.Scale(scheme="teals"),
                        title="Posts"),
    ).properties(height=340), use_container_width=True)

    # pareto
    st.markdown('<h3 style="margin-top:2rem">Where does the reach '
                'concentrate?</h3>', unsafe_allow_html=True)
    st.caption("Cumulative share of views by top-N% of posts. Steep = "
               "a handful of heroes carry the page.")
    pareto = scored.sort_values("Impressions",
                                ascending=False).reset_index(drop=True)
    pareto["rank"] = pareto.index + 1
    pareto["rank_pct"] = pareto["rank"] / len(pareto) * 100
    pareto["cum_share"] = (pareto["Impressions"].cumsum()
                           / pareto["Impressions"].sum() * 100)
    p_line = alt.Chart(pareto).mark_line(
        color=ACCENT, strokeWidth=2).encode(
        x=alt.X("rank_pct:Q", title="Top X% of posts"),
        y=alt.Y("cum_share:Q", title="Cumulative share of views (%)"),
        tooltip=[alt.Tooltip("rank_pct:Q", format=".0f"),
                 alt.Tooltip("cum_share:Q", format=".1f")],
    ).properties(height=260)
    ref = alt.Chart(pd.DataFrame({"x": [0, 100], "y": [0, 100]})
    ).mark_line(color=MUTED, strokeDash=[3, 3]).encode(
        x="x:Q", y="y:Q")
    st.altair_chart(p_line + ref, use_container_width=True)

# =======================================================================
# CAPTION SIGNALS
# =======================================================================
with tab_signals:
    st.markdown('<h3>Word count vs score</h3>', unsafe_allow_html=True)
    st.caption("Smooth curve is a loess trend. Look for the peak.")
    wc = scored.dropna(subset=["word_count", "post_score"]).copy()
    wc_scatter = alt.Chart(wc).mark_circle(size=60, opacity=0.6,
                                            color=MUTED).encode(
        x=alt.X("word_count:Q", title="Word count"),
        y=alt.Y("post_score:Q", title="Score"),
        tooltip=[alt.Tooltip("hook_short:N", title="First line"),
                 alt.Tooltip("word_count:Q"),
                 alt.Tooltip("post_score:Q", format=".0f")])
    wc_smooth = alt.Chart(wc).transform_loess(
        "word_count", "post_score", bandwidth=0.4
    ).mark_line(color=ACCENT, strokeWidth=2).encode(
        x="word_count:Q", y="post_score:Q")
    st.altair_chart((wc_scatter + wc_smooth).properties(height=280),
                    use_container_width=True)

    st.markdown('<h3 style="margin-top:2rem">Hashtag count vs reactions</h3>',
                unsafe_allow_html=True)
    st.caption("More hashtags does not always mean more reactions.")
    ht = scored.dropna(subset=["hashtag_count", "engagement_index"]).copy()
    ht_scatter = alt.Chart(ht).mark_circle(size=60, opacity=0.6,
                                            color=MUTED).encode(
        x=alt.X("hashtag_count:Q", title="Hashtags"),
        y=alt.Y("engagement_index:Q",
                title="Reactions vs a normal post"),
        tooltip=[alt.Tooltip("hook_short:N", title="First line"),
                 alt.Tooltip("hashtag_count:Q"),
                 alt.Tooltip("engagement_index:Q", format=".2f")])
    ht_smooth = alt.Chart(ht).transform_loess(
        "hashtag_count", "engagement_index", bandwidth=0.5
    ).mark_line(color=ACCENT, strokeWidth=2).encode(
        x="hashtag_count:Q", y="engagement_index:Q")
    st.altair_chart((ht_scatter + ht_smooth).properties(height=260),
                    use_container_width=True)

    st.markdown('<h3 style="margin-top:2rem">Small text triggers</h3>',
                unsafe_allow_html=True)
    st.caption("Score distributions when the caption asks a question or "
               "includes a link. Each dot is one post.")
    b1, b2 = st.columns(2, gap="large")

    def bool_box(field, title):
        df_ = scored.copy()
        df_[field + "_lbl"] = df_[field].map(
            lambda v: "yes" if int(v or 0) else "no")
        box = alt.Chart(df_).mark_boxplot(color=ACCENT,
                                          extent="min-max",
                                          size=40).encode(
            x=alt.X(f"{field}_lbl:N", title=None, sort=["no", "yes"]),
            y=alt.Y("post_score:Q", title="Score"))
        pts = alt.Chart(df_).mark_circle(size=40, opacity=0.4,
                                          color=INK_SOFT).encode(
            x=alt.X(f"{field}_lbl:N", sort=["no", "yes"]),
            y="post_score:Q",
            tooltip=[alt.Tooltip("hook_short:N"),
                     alt.Tooltip("post_score:Q", format=".0f")])
        return (box + pts).properties(height=280, title=title)

    with b1:
        st.altair_chart(bool_box("has_question", "Question in caption"),
                        use_container_width=True)
    with b2:
        st.altair_chart(bool_box("has_link", "Link in caption"),
                        use_container_width=True)

    # emoji count vs score
    if "emoji_count" in scored.columns:
        st.markdown('<h3 style="margin-top:2rem">Emojis vs score</h3>',
                    unsafe_allow_html=True)
        st.caption("Do emojis help? Dots = posts, curve = trend.")
        em = scored.dropna(subset=["emoji_count", "post_score"]).copy()
        _es = alt.Chart(em).mark_circle(size=60, opacity=0.6,
                                         color=MUTED).encode(
            x=alt.X("emoji_count:Q", title="Emojis"),
            y=alt.Y("post_score:Q", title="Score"),
            tooltip=["hook_short", "emoji_count", "post_score"])
        _esm = alt.Chart(em).transform_loess(
            "emoji_count", "post_score", bandwidth=0.6
        ).mark_line(color=ACCENT, strokeWidth=2).encode(
            x="emoji_count:Q", y="post_score:Q")
        st.altair_chart((_es + _esm).properties(height=260),
                        use_container_width=True)

# =======================================================================
# WHAT WINS
# =======================================================================
with tab_winners:
    st.markdown('<h3>Attribute lift vs the page median</h3>',
                unsafe_allow_html=True)
    st.caption("Each row is one attribute value. Positive = beats a "
               "normal post. Opacity = certainty.")
    lv = lift.copy()
    lv = lv[lv["confidence"].isin(["solid", "worth a test"])]
    if not lv.empty:
        lv["group"] = lv["attribute"].map(LABELS).fillna(lv["attribute"])
        lift_chart = alt.Chart(lv.head(25)).mark_bar(
            cornerRadiusEnd=3).encode(
            y=alt.Y("value:N", sort="-x", title=None),
            x=alt.X("lift:Q", title="Lift vs a normal post",
                    axis=alt.Axis(format="+%")),
            color=alt.condition(alt.datum.lift > 0,
                                alt.value(ACCENT), alt.value(WARN)),
            opacity=alt.Opacity(
                "confidence:N",
                scale=alt.Scale(
                    domain=["solid", "worth a test", "one-off"],
                    range=[1.0, 0.6, 0.35]), title="How sure"),
            row=alt.Row("group:N", title=None,
                        header=alt.Header(labelAngle=0,
                                          labelAlign="left",
                                          labelFontWeight="bold")),
            tooltip=[alt.Tooltip("group:N", title="Attribute"),
                     alt.Tooltip("value:N", title="Value"),
                     alt.Tooltip("posts:Q", title="Posts"),
                     alt.Tooltip("lift:Q", format="+.0%")],
        ).properties(height=alt.Step(19))
        st.altair_chart(lift_chart, use_container_width=True)
    else:
        st.info("Not enough posts at solid or worth-a-test confidence "
                "yet.")

    st.markdown('<h3 style="margin-top:2rem">Distinctive words and '
                'hashtags</h3>', unsafe_allow_html=True)
    st.caption("Words and hashtags that appear more in top posts than "
               "in bottom posts.")
    wcol1, wcol2 = st.columns(2, gap="large")
    kw = scoring.top_keywords(scored, n=15)
    with wcol1:
        st.markdown("**Words**")
        if kw.empty:
            st.caption("No caption text yet.")
        else:
            st.altair_chart(alt.Chart(kw).mark_bar(color=ACCENT).encode(
                y=alt.Y("word:N", sort="-x", title=None),
                x=alt.X("distinctiveness:Q",
                        title="Distinctiveness",
                        axis=alt.Axis(format="+.0%")),
                tooltip=["word", "top posts", "bottom posts",
                         alt.Tooltip("distinctiveness:Q",
                                     format="+.0%")]
            ).properties(height=max(200, 24 * len(kw))),
            use_container_width=True)
    ht_tbl = scoring.top_hashtags(scored, n=15)
    with wcol2:
        st.markdown("**Hashtags**")
        if ht_tbl.empty:
            st.caption("No hashtag data yet.")
        else:
            st.altair_chart(alt.Chart(ht_tbl).mark_bar(color=ACCENT
            ).encode(
                y=alt.Y("hashtag:N", sort="-x", title=None),
                x=alt.X("distinctiveness:Q",
                        title="Distinctiveness",
                        axis=alt.Axis(format="+.0%")),
                tooltip=["hashtag", "top posts", "bottom posts",
                         alt.Tooltip("distinctiveness:Q",
                                     format="+.0%")]
            ).properties(height=max(200, 24 * len(ht_tbl))),
            use_container_width=True)

    st.markdown('<h3 style="margin-top:2rem">Top vs bottom, side by '
                'side</h3>', unsafe_allow_html=True)
    st.caption("Every micro-detail. Rows where columns differ = recipe.")
    micro = scoring.micro_attribute_table(scored)
    st.dataframe(micro, use_container_width=True, hide_index=True)

# =======================================================================
# MATCHED PAIRS (A/B)
# =======================================================================
with tab_ab:
    st.markdown('<h3>Same first line, different posts</h3>',
                unsafe_allow_html=True)
    st.caption("Groups of posts that open with the same first line. "
               "Real reposts show up here. The bars compare views and "
               "reactions across the copies.")

    pairs = scored.copy()
    pairs["hook_key"] = pairs["hook"].astype(str).str.strip().str.lower(
    ).str[:80]
    pairs = pairs[pairs["hook_key"].str.len() >= 20]
    grouped = pairs.groupby("hook_key").filter(lambda g: len(g) >= 2)

    if grouped.empty:
        st.info("No repeated first lines in the current filter. "
                "Widen the date range and try again.")
    else:
        n_groups = grouped["hook_key"].nunique()
        st.caption(f"Found {n_groups} clusters covering "
                   f"{len(grouped)} posts.")
        plot_df = grouped[["hook_key", "created_date", "hook_short",
                            "post_score", "reach_index",
                            "engagement_index", "Impressions"]].copy()
        plot_df["variant"] = (plot_df.groupby("hook_key").cumcount() + 1
                               ).astype(str)
        st.altair_chart(alt.Chart(plot_df).mark_line(
            color=MUTED, strokeWidth=1).encode(
            x=alt.X("variant:N", title="Variant"),
            y=alt.Y("post_score:Q", title="Score"),
            detail="hook_key:N",
        ) + alt.Chart(plot_df).mark_circle(
            size=140, color=ACCENT, opacity=0.85).encode(
            x=alt.X("variant:N"),
            y=alt.Y("post_score:Q"),
            tooltip=[alt.Tooltip("hook_short:N", title="First line"),
                     alt.Tooltip("created_date:T",
                                 format="%d %b %Y", title="Date"),
                     alt.Tooltip("post_score:Q", format=".0f",
                                 title="Score"),
                     alt.Tooltip("Impressions:Q", title="Views",
                                 format=",")],
        ).properties(height=340), use_container_width=True)

        st.markdown("**Every cluster, side by side**")
        preview = (grouped.sort_values(["hook_key", "created_date"])
                          [["hook_key", "created_date", "hook",
                            "post_score", "Impressions", "Likes",
                            "Comments", "theme"]])
        preview = preview.rename(columns={"hook": "First line",
                                          "hook_key": "Cluster key",
                                          "post_score": "Score",
                                          "Impressions": "Views",
                                          "created_date": "Date",
                                          "theme": "Topic"})
        st.dataframe(preview, use_container_width=True,
                     hide_index=True)

# =======================================================================
# MODEL INSIGHTS
# =======================================================================
with tab_model:
    st.markdown('<h3>Feature importance</h3>', unsafe_allow_html=True)
    st.caption("Which features carry the most weight in the model's "
               "score prediction. Train on the current filter.")
    train_click_v = st.button("Train model on current filter",
                               key="viz_train", type="primary")
    if train_click_v or "viz_bundle" not in st.session_state:
        with st.spinner("Training..."):
            st.session_state.viz_bundle = predictor.train_models(scored)
    v_bundle = st.session_state.get("viz_bundle")
    if v_bundle and v_bundle["models"]:
        imp = predictor.feature_importance(v_bundle, target="post_score")
        if not imp.empty:
            imp["nice"] = imp["feature"].map(LABELS).fillna(imp["feature"])
            st.altair_chart(alt.Chart(imp.head(15)).mark_bar(
                color=ACCENT).encode(
                y=alt.Y("nice:N", sort="-x", title=None),
                x=alt.X("importance:Q", title="Importance"),
                tooltip=["nice", alt.Tooltip("importance:Q",
                                             format=".3f")]
            ).properties(height=max(220, 24 * min(15, len(imp)))),
            use_container_width=True)

        # per-post breakdown
        st.markdown('<h3 style="margin-top:2rem">Per-post feature '
                    'contribution</h3>', unsafe_allow_html=True)
        st.caption("For a specific post, how does each visible feature "
                   "push the model's predicted score up or down?")

        options = [(int(r["idx"]),
                    f'{r["created_date"].strftime("%d %b %Y")} — '
                    f'{r["hook_short"]}')
                   for _, r in scored.sort_values(
                       "post_score", ascending=False).iterrows()]
        pick = st.selectbox("Choose a post",
                            options=[o[0] for o in options],
                            format_func=lambda i:
                                next(x[1] for x in options if x[0] == i),
                            key="viz_post_pick")
        row = scored[scored["idx"] == pick].iloc[0]
        draft = {c: row[c] for c in v_bundle["cat"] + v_bundle["num"]
                 if c in row.index}

        # leave-one-out contribution per categorical feature
        base = predictor.predict(v_bundle, draft)["post_score"]
        baseline_draft = predictor._baseline_draft(v_bundle)
        contribs = []
        for f in v_bundle["cat"]:
            trial = dict(draft)
            trial[f] = baseline_draft[f]
            new = predictor.predict(v_bundle, trial)["post_score"]
            contribs.append({
                "feature": LABELS.get(f, f),
                "current_value": str(draft.get(f, "")),
                "contribution": base - new,
            })
        cdf = (pd.DataFrame(contribs)
                 .sort_values("contribution", ascending=False)
                 .head(12))
        st.altair_chart(alt.Chart(cdf).mark_bar().encode(
            y=alt.Y("feature:N", sort="-x", title=None),
            x=alt.X("contribution:Q", title="Contribution to the score",
                    axis=alt.Axis(format="+.1f")),
            color=alt.condition(alt.datum.contribution > 0,
                                alt.value(ACCENT), alt.value(WARN)),
            tooltip=["feature", "current_value",
                     alt.Tooltip("contribution:Q", format="+.2f")],
        ).properties(height=max(220, 24 * len(cdf))),
                        use_container_width=True)
    else:
        st.warning("Not enough posts to train (need at least 15). "
                   "Widen the date range.")

# =======================================================================
# CORRELATIONS & ARCHETYPES
# =======================================================================
with tab_corr:
    st.markdown('<h3>Correlation matrix</h3>', unsafe_allow_html=True)
    st.caption("Which numeric features move together. 1 = perfect match, "
               "0 = unrelated, -1 = opposite.")
    num_cols = [c for c in ["post_score", "Impressions", "Clicks",
                             "Likes", "Comments", "Reposts",
                             "engagement_rate", "ctr", "reach_index",
                             "engagement_index", "click_index",
                             "word_count", "hook_len", "hashtag_count",
                             "emoji_count", "line_breaks", "has_link",
                             "has_question"] if c in scored.columns]
    cm = scored[num_cols].corr().round(2).reset_index(
        ).melt("index", var_name="col", value_name="corr")
    cm = cm.rename(columns={"index": "row"})
    st.altair_chart(alt.Chart(cm).mark_rect().encode(
        x=alt.X("col:N", title=None,
                axis=alt.Axis(labelAngle=-40)),
        y=alt.Y("row:N", title=None),
        color=alt.Color("corr:Q",
                        scale=alt.Scale(scheme="redblue",
                                         domain=[-1, 1]),
                        title="Correlation"),
        tooltip=["row", "col", "corr"],
    ).properties(height=520) + alt.Chart(cm).mark_text(
        fontSize=10, color=INK).encode(
        x="col:N", y="row:N",
        text=alt.Text("corr:Q", format=".2f")),
                    use_container_width=True)

    st.markdown('<h3 style="margin-top:2rem">Parallel coordinates</h3>',
                unsafe_allow_html=True)
    st.caption("Every post is a line across the numeric features. "
               "Coloured teal for winners, muted for the rest. Look "
               "for the polyline shapes that hold the top band.")
    pc_features = ["reach_index", "engagement_index", "word_count",
                   "hashtag_count", "hook_len", "post_score"]
    pc_features = [c for c in pc_features if c in scored.columns]
    pc = scored[pc_features + ["idx"]].copy().dropna()
    # normalise each column to [0, 1] for comparability
    for c in pc_features:
        lo, hi = pc[c].min(), pc[c].max()
        pc[c] = (pc[c] - lo) / (hi - lo + 1e-6)
    pc_melt = pc.melt(id_vars=["idx", "post_score"],
                      var_name="feature", value_name="value")
    st.altair_chart(alt.Chart(pc_melt).mark_line(opacity=0.5).encode(
        x=alt.X("feature:N", title=None, sort=pc_features),
        y=alt.Y("value:Q", title="Scaled 0-1"),
        detail="idx:N",
        color=alt.condition("datum.post_score > 0.6",
                             alt.value(ACCENT), alt.value(MUTED)),
        tooltip=["idx"],
    ).properties(height=340), use_container_width=True)

# tiny footnote
st.markdown(
    f'<div style="color:{MUTED};font-size:.75rem;'
    f'margin-top:2rem;text-align:center">'
    f'{len(scored)} posts &middot; {start_date:%d %b %Y} to '
    f'{end_date:%d %b %Y}. Filters apply across all tabs.</div>',
    unsafe_allow_html=True)

