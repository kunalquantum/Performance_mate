"""
LinkedIn Post Performance Matrix - Explore page.
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
ctx = linkedin_setup("Explore")

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



# ---------------------------------------------------------------------------
# EXPLORE mode continues below
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# stage-one KPIs
# ---------------------------------------------------------------------------
n_posts = len(scored)
median_reach = scored["reach_index"].median()
median_er = scored["engagement_index"].median()
best_score = scored["post_score"].max()


def stat_tile(label, value, delta=""):
    st.markdown(
        f'<div class="stat"><div class="k">{label}</div>'
        f'<div class="v">{value}</div>'
        f'<div class="d">{delta}</div></div>', unsafe_allow_html=True)


kcol1, kcol2, kcol3, kcol4 = st.columns(4)
with kcol1:
    stat_tile("Posts in view", f"{n_posts}", "in the filtered window")
with kcol2:
    stat_tile("Median views vs normal", f"{median_reach:.2f}x",
              "1.00 = a normal post")
with kcol3:
    stat_tile("Median reactions vs normal", f"{median_er:.2f}x",
              "1.00 = a normal post")
with kcol4:
    stat_tile("Top score", f"{best_score:.0f}", "out of 100")


# ---------------------------------------------------------------------------
# SECTION 1 - the scatter
# ---------------------------------------------------------------------------
st.markdown('<h2>The year, post by post</h2>', unsafe_allow_html=True)
st.caption("Score on the vertical, date on the horizontal. Higher is better. "
           "Click any dot to inspect it below.")

click_sel = alt.selection_point(name="pt", on="click", fields=["idx"],
                                empty=False)

chart = alt.Chart(scored).mark_circle(
    stroke=INK, strokeWidth=0.4
).encode(
    x=alt.X("created_date:T", title=None,
            axis=alt.Axis(labelColor=MUTED, tickColor=LINE, domainColor=LINE,
                          grid=False, labelFontSize=11)),
    y=alt.Y("post_score:Q", title="Score",
            scale=alt.Scale(domain=[0, 100]),
            axis=alt.Axis(labelColor=MUTED, tickColor=LINE, domainColor=LINE,
                          gridColor=LINE, gridDash=[2, 3],
                          titleColor=MUTED, titleFontSize=11, labelFontSize=11)),
    color=alt.condition(
        alt.datum.post_score >= 60,
        alt.value(ACCENT),
        alt.value(MUTED)),
    size=alt.condition(click_sel, alt.value(280), alt.value(140)),
    opacity=alt.condition(click_sel, alt.value(1.0), alt.value(0.85)),
    tooltip=[
        alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
        alt.Tooltip("post_score:Q", title="Score", format=".0f"),
        alt.Tooltip("hook_short:N", title="First line"),
        alt.Tooltip("theme:N", title="Topic"),
    ],
).add_params(click_sel).properties(height=340)

# Median reference line is rendered above the scatter as a caption instead
# of a layered rule, because Streamlit does not permit on_select="rerun"
# on multi-view (layered) Altair charts.
_median_score = float(scored["post_score"].median())
st.caption(f"Median post score in this window: {_median_score:.0f}. "
           "Click any dot to select it for the comparison below.")

event = st.altair_chart(chart,
                        width='stretch',
                        on_select="rerun", key="scatter")

# build the score-ranked view once - prev/next buttons walk through this
ranked = scored.sort_values(
    ["post_score", "created_date"], ascending=[False, False]
).reset_index(drop=True)
n_ranked = len(ranked)
idx_to_rank = {int(r["idx"]): i for i, r in ranked.iterrows()}

# resolve scatter click (may be sticky across reruns, so we only act when it changes)
click_idx = None
try:
    pts = event.selection.get("pt") if event and getattr(event, "selection", None) else None
    if pts:
        click_idx = int(pts[0].get("idx"))
except Exception:
    click_idx = None

# cursor state - independent left and right, both walk the ranked list
if "left_rank" not in st.session_state:
    # default left = most recent post's rank
    latest = scored.sort_values("created_date", ascending=False).iloc[0]
    st.session_state.left_rank = idx_to_rank.get(int(latest["idx"]), 0)
if "right_rank" not in st.session_state:
    # default right = top performer
    st.session_state.right_rank = 0
if "last_click_idx" not in st.session_state:
    st.session_state.last_click_idx = None

# only override left cursor when a NEW dot was clicked (not on every rerun)
if click_idx is not None and click_idx != st.session_state.last_click_idx:
    st.session_state.last_click_idx = click_idx
    if click_idx in idx_to_rank:
        st.session_state.left_rank = idx_to_rank[click_idx]

# clamp left in case the filter reduced the number of posts
st.session_state.left_rank = min(st.session_state.left_rank, n_ranked - 1)
selected = ranked.iloc[st.session_state.left_rank]


# ---------------------------------------------------------------------------
# SECTION 2 - compare
# ---------------------------------------------------------------------------
st.markdown('<h2>Compare</h2>', unsafe_allow_html=True)

_tcol1, _tcol2 = st.columns([3, 1])
with _tcol1:
    st.caption("Left = the post you picked. Right = top performer to compare "
               "against. Prev/next walks the ranking under each card.")
with _tcol2:
    same_topic = st.checkbox("Same topic only", value=True,
                             help="When ticked, the right card only shows "
                                  "posts on the same topic as the left card. "
                                  "That makes the comparison fair.")

# determine the peer pool for the right card
selected_theme = str(selected.get("theme", ""))
if same_topic and selected_theme:
    peers = ranked[ranked["theme"] == selected_theme].reset_index(drop=True)
    # if the left post's topic changed, reset right cursor to the top of the peer list
    if st.session_state.get("last_left_theme") != selected_theme:
        st.session_state.right_rank = 0
        st.session_state.last_left_theme = selected_theme
else:
    peers = ranked
    st.session_state.last_left_theme = None

n_peers = len(peers)
st.session_state.right_rank = min(st.session_state.right_rank, max(0, n_peers - 1))
best = peers.iloc[st.session_state.right_rank] if n_peers > 0 else selected


COMPARE_ATTRS = [
    ("theme", "Topic"),
    ("cta_type", "Ask"),
    ("length_band", "Length"),
    ("day_of_week", "Publish day"),
    ("format_inferred", "Format"),
    ("has_face_in_image", "Face in image"),
    ("image_colour_theme", "Image colour"),
    ("campaign", "Campaign"),
]


def render_card(col, row, tag, tag_class="a", is_selected=False):
    hook = (row["hook"] if isinstance(row["hook"], str) and row["hook"].strip()
            else "[No post copy]")
    if len(hook) > 130:
        hook = hook[:127] + "..."
    dt = row["created_date"].strftime("%a %d %b %Y")

    kvs = []
    for f, label in COMPARE_ATTRS:
        if f not in row.index:
            continue
        val = str(row[f]) if pd.notna(row[f]) else ""
        val = val.strip()
        if val in ("", "nan"):
            val = "—"
        if len(val) > 60:
            val = val[:57] + "..."
        cls = "kv"
        kvs.append(f'<div class="{cls}"><div class="k">{label}</div>'
                   f'<div class="v">{val}</div></div>')

    reach = row.get("reach_index")
    eng = row.get("engagement_index")
    click = row.get("click_index")

    with col:
        st.markdown(
            f'<div class="card {"selected" if is_selected else ""}">'
            f'<span class="tag {tag_class}">{tag}</span>'
            f'<div class="hook">{hook}</div>'
            f'<div class="meta">{dt} &middot; '
            f'{int(row["Impressions"]):,} views &middot; '
            f'{int(row["Likes"])} likes &middot; '
            f'{int(row["Comments"])} comments</div>'
            f'<div style="display:flex;align-items:baseline;gap:.5rem;'
            f'margin-bottom:1rem">'
            f'<div class="score">{row["post_score"]:.0f}</div>'
            f'<div class="score-lbl">score / 100</div></div>'
            f'<div style="display:flex;gap:1.4rem;font-size:.78rem;'
            f'color:{MUTED};margin-bottom:1rem">'
            f'<span>Views {reach:.2f}x</span>'
            f'<span>Reactions {eng:.2f}x</span>'
            f'<span>Clicks {click:.2f}x</span></div>'
            + "".join(kvs) +
            f'</div>', unsafe_allow_html=True)


def render_nav(side_key, rank_state_key, total, scope_label=""):
    """Prev/next/counter row under a card."""
    rank_now = st.session_state[rank_state_key]
    b1, b2, b3 = st.columns([1, 2, 1])
    with b1:
        if st.button("← Previous", key=f"{side_key}_prev",
                     width='stretch',
                     disabled=(rank_now <= 0),
                     help="Move to the next-higher-ranked post"):
            st.session_state[rank_state_key] = max(0, rank_now - 1)
            st.rerun()
    with b2:
        cap = (f'Rank <b style="color:{INK}">{rank_now + 1}</b> of {total}'
               if total > 0 else "no posts")
        if scope_label:
            cap += f'<span style="opacity:.75"> &middot; {scope_label}</span>'
        st.markdown(
            f'<div style="text-align:center;padding-top:.45rem;'
            f'font-size:.78rem;color:{MUTED};letter-spacing:.06em;">'
            f'{cap}</div>', unsafe_allow_html=True)
    with b3:
        if st.button("Next →", key=f"{side_key}_next",
                     width='stretch',
                     disabled=(rank_now >= total - 1),
                     help="Move to the next-lower-ranked post"):
            st.session_state[rank_state_key] = min(total - 1, rank_now + 1)
            st.rerun()


ccol1, ccol2 = st.columns(2, gap="large")

with ccol1:
    same = int(best["idx"]) == int(selected["idx"])
    tag = ("Your selection = top performer" if same and same_topic
           else "Your selection")
    render_card(st.container(), selected, tag=tag,
                tag_class="a", is_selected=True)
    render_nav("left", "left_rank", n_ranked, scope_label="all posts")

with ccol2:
    if same_topic:
        right_tag = f"Top in this topic ({selected_theme})"
        right_scope = f"topic: {selected_theme}"
    else:
        right_tag = "Top performer"
        right_scope = "all posts"
    render_card(st.container(), best, tag=right_tag, tag_class="b")
    render_nav("right", "right_rank", n_peers, scope_label=right_scope)


# ---------------------------------------------------------------------------
# SECTION 3 - the ideal post
# ---------------------------------------------------------------------------
st.markdown('<h2>The ideal post</h2>', unsafe_allow_html=True)
st.caption("Averaged across the top-scoring quarter of posts in the current "
           "filter. This is the recipe. Not a formula, a starting point.")

spec, avoid, top_full, bottom_full = scoring.build_brief(scored, live_features)

RECIPE_ORDER = [
    ("theme", "Topic to write on"),
    ("cta_type", "Ask (call to action)"),
    ("length_band", "Length band"),
    ("word_count", "Word count"),
    ("hook_len", "First line length"),
    ("day_of_week", "Publish day"),
    ("format_inferred", "Format"),
    ("media_type", "Media type"),
    ("image_subject", "Image subject"),
    ("image_colour_theme", "Image colour palette"),
    ("has_face_in_image", "Show a face"),
    ("text_on_image", "Text on image"),
    ("target_region", "Target region"),
    ("hashtag_count", "Number of hashtags"),
    ("hashtags", "Hashtag set"),
    ("campaign", "Campaign angle"),
]

rows_html = []
for key, label in RECIPE_ORDER:
    v = spec.get(key)
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        continue
    v_str = str(v)
    if len(v_str) > 90:
        v_str = v_str[:87] + "..."
    rows_html.append(
        f'<div class="row"><div class="k">{label}</div>'
        f'<div class="v">{v_str}</div></div>')

st.markdown(
    f'<div class="recipe">{"".join(rows_html)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# copy-as-text
# ---------------------------------------------------------------------------
brief_lines = ["NEXT POST RECIPE", ""]
for key, label in RECIPE_ORDER:
    v = spec.get(key)
    if v in (None, "") or (isinstance(v, float) and pd.isna(v)):
        continue
    brief_lines.append(f"  {label}: {v}")
brief_lines += ["", "Averaged from the top posts in the current filter."]
brief_lines += ["", "Posts to copy the shape of:"]
for _, r in top_full.head(3).iterrows():
    d = r["created_date"].strftime("%d %b %Y")
    h = r["hook"] if isinstance(r["hook"], str) and r["hook"].strip() else "[no copy]"
    brief_lines.append(f"  {d} — score {r['post_score']:.0f} — {h[:90]}")
brief_text = "\n".join(brief_lines)

with st.expander("Copy the recipe as text", expanded=False):
    st.code(brief_text, language="text")
    st.download_button("Download recipe as text", brief_text.encode("utf-8"),
                       file_name="post_performance_recipe.txt",
                       mime="text/plain")


# ---------------------------------------------------------------------------
# spacer at the bottom so the last card breathes
# ---------------------------------------------------------------------------
st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
