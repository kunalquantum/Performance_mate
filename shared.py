"""
Shared bootstrap for the GrantsNow multi-page Streamlit app.

Import this from every page. It exposes constants, the cached CSV loader,
and a `inject_css()` helper that installs the house look on each page.
Nothing here mutates st.session_state on import.
"""

import os
import re

import altair as alt
import pandas as pd
import streamlit as st


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
INK = "#111318"
INK_SOFT = "#3B4046"
MUTED = "#8A8F98"
LINE = "#E7E7EA"
BG = "#FFFFFF"
BG_SOFT = "#F7F7F8"
ACCENT = "#0E6E68"
ACCENT_SOFT = "#B9D8D5"
WARN = "#B4462F"
GOLD = "#C99A2E"


# --------------------------------------------------------------------------
# LinkedIn feature/label registry (used across LinkedIn pages)
# --------------------------------------------------------------------------
FEATURES = [
    "format_inferred", "theme", "cta_type", "length_band", "day_of_week",
    "media_type", "image_subject", "image_colour_theme", "has_face_in_image",
    "text_on_image", "target_region", "campaign",
]

LABELS = {
    "format_inferred": "Format", "theme": "Topic", "cta_type": "Ask",
    "length_band": "Length", "day_of_week": "Publish day",
    "word_count": "Word count", "hashtag_count": "Hashtags",
    "hook_len": "First line", "hashtags": "Which hashtags",
    "media_type": "Media", "image_subject": "Image subject",
    "image_colour_theme": "Image colour",
    "has_face_in_image": "Face in image",
    "text_on_image": "Text on image", "target_region": "Target region",
    "campaign": "Campaign",
}


# --------------------------------------------------------------------------
# Cached CSV loader (mtime-keyed so ETL reruns invalidate the cache)
# --------------------------------------------------------------------------
@st.cache_data
def _load_csv_cached(path, mtime):
    df = pd.read_csv(path)
    for c in df.columns:
        if c.lower() in ("date", "created_date"):
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def load_csv(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return pd.DataFrame()
    return _load_csv_cached(p, os.path.getmtime(p))


# --------------------------------------------------------------------------
# House CSS - MUST run on every rerun. Streamlit rebuilds the DOM each
# rerun, so a "guard against double injection" would strip styles from the
# page as soon as any widget is touched. Just re-emit the <style> block;
# duplicate <style> tags in the DOM are harmless.
# --------------------------------------------------------------------------
def inject_css():
    """Install the house look. Call once at the top of every page."""
    st.markdown(f"""
<style>
  html, body, [data-testid="stApp"] {{ background:{BG}; color:{INK};
      font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue",
                    Arial, sans-serif; }}
  [data-testid="stApp"] {{ padding-top:0.5rem; }}
  [data-testid="stHeader"] {{ background:transparent; }}
  [data-testid="stSidebar"] {{ background:{BG_SOFT};
      border-right:1px solid {LINE}; }}

  h1 {{ color:{INK}; font-weight:700; letter-spacing:-0.03em;
        font-size:2.3rem; margin:0 0 .1rem; }}
  h2 {{ color:{INK}; font-weight:600; letter-spacing:-0.02em;
        font-size:1.15rem; margin:2.6rem 0 .4rem;
        padding-bottom:.5rem; border-bottom:1px solid {LINE}; }}
  h3 {{ color:{INK}; font-weight:600; font-size:.98rem; margin:.2rem 0 .4rem;
        letter-spacing:-0.01em; }}

  .eyebrow {{ font-size:.68rem; letter-spacing:.16em; text-transform:uppercase;
              color:{MUTED}; font-weight:600; }}
  .lede {{ color:{MUTED}; font-size:.98rem; margin:.25rem 0 1.8rem;
           font-weight:400; }}

  .stat, .kpi {{ padding:.9rem 1.1rem; border:1px solid {LINE};
                  border-radius:6px; background:{BG}; }}
  .stat .k, .kpi .kpi-label {{ font-size:.68rem; letter-spacing:.14em;
      text-transform:uppercase; color:{MUTED}; font-weight:600; }}
  .stat .v, .kpi .kpi-value {{ font-size:1.6rem; font-weight:700;
      color:{INK}; letter-spacing:-0.02em; margin-top:.2rem; }}
  .stat .d, .kpi .kpi-sub {{ font-size:.78rem; color:{MUTED};
      margin-top:.1rem; }}

  .card {{ border:1px solid {LINE}; border-radius:8px; padding:1.3rem 1.5rem;
           background:{BG}; }}
  .card.selected {{ border-color:{ACCENT}; }}
  .card .tag {{ display:inline-block; font-size:.65rem; letter-spacing:.14em;
                text-transform:uppercase; font-weight:600; padding:.15rem .5rem;
                border-radius:2px; margin-bottom:.6rem; }}
  .card .tag.a {{ color:{ACCENT}; background:#EBF3F2;
                   border:1px solid #D2E3E1; }}
  .card .tag.b {{ color:{INK_SOFT}; background:{BG_SOFT};
                   border:1px solid {LINE}; }}
  .card .hook {{ font-size:1.05rem; font-weight:600; color:{INK};
                 line-height:1.35; margin-bottom:.7rem; }}
  .card .meta {{ font-size:.78rem; color:{MUTED}; margin-bottom:1rem; }}
  .card .score {{ font-size:2.4rem; font-weight:700; color:{INK};
                  letter-spacing:-0.03em; line-height:1; }}
  .card .score-lbl {{ font-size:.7rem; letter-spacing:.14em;
      text-transform:uppercase; color:{MUTED}; font-weight:600; }}
  .card .kv {{ display:flex; justify-content:space-between;
               padding:.5rem 0; border-top:1px solid {LINE};
               font-size:.85rem; }}
  .card .kv .k {{ color:{MUTED}; }}
  .card .kv .v {{ color:{INK}; font-weight:500; text-align:right;
                   max-width:60%; }}
  .card .kv.win .v {{ color:{ACCENT}; font-weight:600; }}

  .recipe {{ border:1px solid {LINE}; border-radius:8px;
             padding:1.6rem 1.8rem; background:{BG}; }}
  .recipe .row {{ display:flex; justify-content:space-between;
      align-items:flex-start; padding:.6rem 0; border-top:1px solid {LINE}; }}
  .recipe .row:first-child {{ border-top:none; }}
  .recipe .row .k {{ font-size:.72rem; letter-spacing:.14em;
      text-transform:uppercase; color:{MUTED}; font-weight:600;
      padding-top:.15rem; min-width:180px; }}
  .recipe .row .v {{ font-size:1rem; color:{INK}; font-weight:500;
                     text-align:right; max-width:60%; }}

  hr {{ border:none; border-top:1px solid {LINE}; margin:0; }}
  a, a:visited {{ color:{ACCENT}; }}
</style>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Status-colour legend + KPI helper with tooltip. Call render_status_key()
# once near the top of every page so the sales director always has the key
# in view. Use kpi_tile() for KPIs so a native browser tooltip explains
# each metric on hover.
# --------------------------------------------------------------------------
def core_question(question):
    """Render the core question this page answers, as a big teal-lined
    banner directly under the h1. Keeps every page anchored to a
    single job-to-be-done so the director sees, in one glance, whether
    they are on the right screen."""
    st.markdown(
        f'<div style="background:#EBF3F2;border-left:5px solid '
        f'{ACCENT};border-radius:6px;padding:.9rem 1.2rem;'
        f'margin:.6rem 0 1rem;font-size:1.05rem;color:{INK};'
        f'font-weight:500;line-height:1.4">'
        f'<div style="font-size:.66rem;letter-spacing:.14em;'
        f'text-transform:uppercase;color:{ACCENT};font-weight:700;'
        f'margin-bottom:.3rem">The question this page answers</div>'
        f'{question}</div>',
        unsafe_allow_html=True)


def render_status_key():
    """A tiny legend strip explaining what green / gold / red mean."""
    st.markdown(
        f'<div style="display:flex;gap:1.2rem;align-items:center;'
        f'padding:.35rem .7rem;margin:.2rem 0 1rem;border:1px solid '
        f'{LINE};border-radius:6px;background:{BG_SOFT};'
        f'font-size:.78rem;color:{INK_SOFT}">'
        f'<span><span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{ACCENT};margin-right:.4rem;'
        f'vertical-align:middle"></span>On track</span>'
        f'<span><span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{GOLD};margin-right:.4rem;'
        f'vertical-align:middle"></span>Look closer</span>'
        f'<span><span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{WARN};margin-right:.4rem;'
        f'vertical-align:middle"></span>Concern</span>'
        f'<span style="margin-left:auto;color:{MUTED}">'
        f'Hover any tile for a plain-English definition.</span>'
        f'</div>', unsafe_allow_html=True)


def kpi_tile(label, value, sub="", tooltip="", color=None):
    """Render a KPI tile with a native browser tooltip. The value inherits
    the accent colour unless explicitly overridden."""
    value_style = f'color:{color};' if color else ''
    tip_attr = (f' title="{tooltip}"' if tooltip else '')
    st.markdown(
        f'<div class="kpi"{tip_attr} style="cursor:help">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value" style="{value_style}">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>',
        unsafe_allow_html=True)


def so_what(text, tone="info"):
    """Render a 'so what' observation box under a chart. tone in
    {info, good, warn}."""
    bar = {"info": ACCENT, "good": ACCENT, "warn": GOLD}.get(tone, ACCENT)
    bg  = {"info": "#faf7f0", "good": "#EBF3F2",
            "warn": "#FBF3E5"}.get(tone, "#faf7f0")
    st.markdown(
        f'<div style="background:{bg};border-left:3px solid {bar};'
        f'padding:.6rem 1rem;margin:.6rem 0 1.2rem;border-radius:4px;'
        f'font-size:.9rem;line-height:1.5">'
        f'<strong>So what:</strong> {text}</div>',
        unsafe_allow_html=True)


def explain_this(shows, good_pattern, action_hint, key=None):
    """Collapsed expander under a chart: what it shows, what good looks
    like, what to do. Static (not derived from live data)."""
    with st.expander("Explain this chart", expanded=False):
        st.markdown(
            f'<div style="font-size:.88rem;line-height:1.55">'
            f'<div style="margin-bottom:.5rem">'
            f'<strong style="color:{ACCENT}">What it shows.</strong> '
            f'{shows}</div>'
            f'<div style="margin-bottom:.5rem">'
            f'<strong style="color:{ACCENT}">What good looks like.</strong> '
            f'{good_pattern}</div>'
            f'<div>'
            f'<strong style="color:{ACCENT}">What to do.</strong> '
            f'{action_hint}</div>'
            f'</div>', unsafe_allow_html=True)


def onboarding_banner(banner_key="onboarding_home_v1"):
    """Dismissible tips banner shown on first visit. Persisted per session
    via st.session_state under `banner_key`."""
    if st.session_state.get(banner_key + "_dismissed"):
        return
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#EBF3F2 0%,'
        f'#F7F7F8 100%);border:1px solid {ACCENT_SOFT};border-left:5px '
        f'solid {ACCENT};border-radius:8px;padding:1.1rem 1.3rem;'
        f'margin:.6rem 0 1.5rem">'
        f'<div style="font-size:.72rem;letter-spacing:.14em;'
        f'text-transform:uppercase;color:{ACCENT};font-weight:700;'
        f'margin-bottom:.5rem">First time here? Read this.</div>'
        f'<div style="font-size:.92rem;line-height:1.6;color:{INK}">'
        f'<strong>1.</strong> Pick an app in the left sidebar '
        f'(<em>LinkedIn</em> or <em>Email</em>) then the screen for the '
        f'question you have.<br>'
        f'<strong>2.</strong> The colour key at the top of every page '
        f'tells you if a number is on-track (green), worth a look (gold), '
        f'or a concern (red).<br>'
        f'<strong>3.</strong> Every KPI tile has a plain-English '
        f'definition on hover.<br>'
        f'<strong>4.</strong> Below each chart, look for the '
        f'&ldquo;So what&rdquo; box (auto-observation of your data) and '
        f'the &ldquo;Explain this chart&rdquo; expander (how to read it).'
        f'<br>'
        f'<strong>5.</strong> The <em>This week&apos;s brief</em> and '
        f'<em>This week&apos;s actions</em> below give you the '
        f'summary and next steps without touching a filter.'
        f'</div></div>',
        unsafe_allow_html=True)
    if st.button("Got it, hide this", key=f"btn_{banner_key}",
                   type="primary"):
        st.session_state[banner_key + "_dismissed"] = True
        st.rerun()


# --------------------------------------------------------------------------
# LinkedIn setup: sidebar filters + date range + scoring pipeline.
# Called once at the top of each LinkedIn page. Returns a SimpleNamespace
# so page bodies can pull what they need with attribute access.
# --------------------------------------------------------------------------
import types

import scoring as _scoring


def _unique_vals_for(df, col):
    if col not in df.columns:
        return []
    s = df[col].dropna().astype(str).str.strip()
    return sorted([v for v in s.unique() if v and v.lower() != "nan"])


FRIENDLY_MODE_TITLES = {
    "Explore":   ("What worked",
                   "Every LinkedIn post as a dot. Click a dot to compare "
                   "it with the top performer. Sidebar on the left trims "
                   "what you see."),
    "Visualize": ("See the pattern",
                   "What actually drives the score - by writing choice, "
                   "image treatment, day of week, and hashtag mix."),
    "Recommend": ("Draft the next post",
                   "Predict how a new draft will land before you publish "
                   "it. The model is trained on every past post."),
}


def linkedin_setup(mode):
    """Do everything a LinkedIn page needs before mode-specific content.
    Renders the sidebar Refine + hashtag playbook + weights, the top-of-page
    date range with quick-range buttons, and computes scored / lift /
    live_features. Returns a SimpleNamespace with every variable the
    original module-level code produced."""

    st.session_state.mode = mode

    posts_raw = load_csv("posts.csv")
    if posts_raw.empty:
        st.error("No posts.csv found. Run `python etl/etl.py --src "
                 "<exports>` first.")
        st.stop()

    min_d = posts_raw["created_date"].min().date()
    max_d = posts_raw["created_date"].max().date()

    # ---------------- Sidebar: Refine, hashtag playbook, weights ----------
    with st.sidebar:
        st.markdown('<div class="eyebrow">Refine</div>',
                    unsafe_allow_html=True)
        st.caption("Trim the set to see what wins on a normal week. Each "
                   "'Remove' box drops posts matching those values.")

        drop_event = st.checkbox("Skip event posts (ARMA etc.)", value=False)
        scope = st.selectbox("Format scope",
                             ["Every format", "Image or text",
                              "Video or document", "Article"])

        with st.expander("Content filters", expanded=True):
            drop_topics = st.multiselect(
                "Remove topics", _unique_vals_for(posts_raw, "theme"))
            drop_asks = st.multiselect(
                "Remove asks / CTAs",
                _unique_vals_for(posts_raw, "cta_type"))
            drop_days = st.multiselect(
                "Remove publish days",
                ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"])
            drop_lengths = st.multiselect(
                "Remove length bands",
                _unique_vals_for(posts_raw, "length_band"))

        has_visual = any(c in posts_raw.columns for c in
                         ("image_colour_theme", "has_face_in_image",
                          "text_on_image", "media_type"))
        if has_visual:
            with st.expander("Visual filters (tagged posts)",
                              expanded=False):
                drop_palettes = st.multiselect(
                    "Remove image palettes",
                    _unique_vals_for(posts_raw, "image_colour_theme"))
                drop_faces = st.multiselect(
                    "Remove face in image",
                    _unique_vals_for(posts_raw, "has_face_in_image"))
                drop_textimg = st.multiselect(
                    "Remove text on image",
                    _unique_vals_for(posts_raw, "text_on_image"))
                drop_media = st.multiselect(
                    "Remove media types",
                    _unique_vals_for(posts_raw, "media_type"))
        else:
            drop_palettes = drop_faces = drop_textimg = drop_media = []

        with st.expander("Campaign filter", expanded=False):
            drop_campaigns = st.multiselect(
                "Remove campaigns",
                _unique_vals_for(posts_raw, "campaign"))

        if any([drop_topics, drop_asks, drop_days, drop_lengths,
                drop_palettes, drop_faces, drop_textimg, drop_media,
                drop_campaigns, drop_event, scope != "Every format"]):
            if st.button("Clear all filters", width='stretch'):
                for key in ["range_start_input", "range_end_input"]:
                    st.session_state.pop(key, None)
                st.rerun()

        st.markdown("---")
        st.markdown('<div class="eyebrow">GrantsNow hashtag playbook</div>',
                    unsafe_allow_html=True)
        hashtag_upload = st.file_uploader(
            "Upload hashtag workbook", type=["xls", "xlsx"],
            key="hashtag_library_file", label_visibility="collapsed")
        if hashtag_upload is not None:
            lib = _scoring.load_hashtag_library(hashtag_upload)
            if lib and lib.get("categories"):
                st.session_state["hashtag_library"] = lib
                st.caption(
                    f"Loaded {len(lib['categories'])} categories, "
                    f"{len(lib['all_hashtags'])} hashtags.")
            else:
                st.caption("Could not parse a category structure from "
                           "that file.")
        hashtag_library = st.session_state.get("hashtag_library", None)
        curated_active = (hashtag_library["all_hashtags"]
                           if hashtag_library else [])

        if hashtag_library and hashtag_library.get("categories"):
            with st.expander("Topic to category mapping", expanded=False):
                lib_categories = list(hashtag_library["categories"].keys())
                if "topic_to_category_override" not in st.session_state:
                    st.session_state["topic_to_category_override"] = {}
                for topic_key, default_cats in \
                        _scoring.TOPIC_TO_CATEGORY.items():
                    default = [c for c in default_cats
                                if c in lib_categories]
                    existing = st.session_state[
                        "topic_to_category_override"].get(
                            topic_key, default)
                    pick = st.multiselect(
                        topic_key, lib_categories, default=existing,
                        key=f"map_{topic_key}")
                    st.session_state["topic_to_category_override"][
                        topic_key] = pick

        st.markdown("---")
        st.markdown('<div class="eyebrow">Signal weights</div>',
                    unsafe_allow_html=True)
        for k, default in [("Comments", 6.0), ("Reposts", 4.0),
                           ("Clicks", 2.0), ("Likes", 1.0)]:
            _scoring.WEIGHTS[k] = st.slider(k, 0.0, 10.0, default, 0.5)

    # ---------------- Header ---------------------------------------------
    title, blurb = FRIENDLY_MODE_TITLES.get(mode, (mode, ""))
    st.markdown('<div class="eyebrow">GrantsNow &middot; LinkedIn</div>',
                unsafe_allow_html=True)
    st.markdown(f'<h1>{title}</h1>', unsafe_allow_html=True)
    _LINKEDIN_CORE_Q = {
        'Explore':   'Which posts worked, and which did not, over the chosen window?',
        'Visualize': 'What are the writing and image patterns that actually drive the score?',
        'Recommend': 'How will a new draft post score before I publish it?',
    }
    _q = _LINKEDIN_CORE_Q.get(mode)
    if _q:
        core_question(_q)
    if blurb:
        st.caption(blurb)
    render_status_key()

    # ---------------- Date range with quick-range buttons ----------------
    if "range_start_input" not in st.session_state:
        st.session_state.range_start_input = min_d
    if "range_end_input" not in st.session_state:
        st.session_state.range_end_input = max_d

    def _set_range(days=None, full=False):
        if full:
            st.session_state.range_start_input = min_d
            st.session_state.range_end_input = max_d
        elif days:
            end = max_d
            start = max(min_d,
                         end - pd.Timedelta(days=days).to_pytimedelta())
            st.session_state.range_start_input = start
            st.session_state.range_end_input = end

    dr1, dr2, dr3 = st.columns([2, 2, 3], gap="small")
    with dr3:
        st.markdown('<div class="eyebrow" '
                    'style="margin-bottom:.2rem">Quick range</div>',
                    unsafe_allow_html=True)
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            if st.button("30 days", key="pr_30d",
                          width='stretch'):
                _set_range(days=30); st.rerun()
        with p2:
            if st.button("90 days", key="pr_90d",
                          width='stretch'):
                _set_range(days=90); st.rerun()
        with p3:
            if st.button("6 months", key="pr_6m",
                          width='stretch'):
                _set_range(days=182); st.rerun()
        with p4:
            if st.button("Full year", key="pr_full",
                          width='stretch'):
                _set_range(full=True); st.rerun()
    with dr1:
        st.markdown('<div class="eyebrow" '
                    'style="margin-bottom:.2rem">From</div>',
                    unsafe_allow_html=True)
        start_date = st.date_input(" ", min_value=min_d, max_value=max_d,
                                     key="range_start_input",
                                     label_visibility="collapsed")
    with dr2:
        st.markdown('<div class="eyebrow" '
                    'style="margin-bottom:.2rem">To</div>',
                    unsafe_allow_html=True)
        end_date = st.date_input("  ", min_value=min_d, max_value=max_d,
                                   key="range_end_input",
                                   label_visibility="collapsed")
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # ---------------- Apply filters --------------------------------------
    posts = posts_raw.copy()
    d0, d1 = pd.Timestamp(start_date), pd.Timestamp(end_date)
    posts = posts[(posts["created_date"] >= d0)
                   & (posts["created_date"] <= d1)]

    def _drop_by(col, values):
        nonlocal posts
        if not values or col not in posts.columns:
            return
        posts = posts[~posts[col].astype(str).str.strip().isin(values)]

    if drop_event:
        posts = posts[posts["theme"] != "event_presence"]
    if scope != "Every format":
        posts = posts[posts["format_inferred"] == scope]

    _drop_by("theme", drop_topics)
    _drop_by("cta_type", drop_asks)
    _drop_by("day_of_week", drop_days)
    _drop_by("length_band", drop_lengths)
    _drop_by("image_colour_theme", drop_palettes)
    _drop_by("has_face_in_image", drop_faces)
    _drop_by("text_on_image", drop_textimg)
    _drop_by("media_type", drop_media)
    _drop_by("campaign", drop_campaigns)

    if posts.empty:
        st.warning("No posts left after those filters. Widen the date "
                   "range or clear some of the sidebar removals.")
        st.stop()

    scored = _scoring.add_scores(posts).reset_index(drop=True)
    scored["idx"] = scored.index
    scored["date"] = scored["created_date"].dt.date
    scored["hook_short"] = scored["hook"].fillna("[No copy]") \
        .astype(str).str.slice(0, 70)

    live_features = [f for f in FEATURES if f in scored.columns
                      and scored[f].astype(str).str.strip()
                      .replace("nan", "").ne("").sum() >= 3]
    lift = _scoring.attribute_lift(scored, live_features)

    _lede_hint = ("Each dot below is one post. Click a dot to compare it "
                  "with the top performer."
                  if mode == "Explore"
                  else "Retrain the recommender, then predict a draft or "
                       "explore what would lift an existing post.")
    st.markdown(
        f'<div class="lede">{len(scored)} posts &middot; '
        f'{start_date:%d %b %Y} to {end_date:%d %b %Y}. {_lede_hint}</div>',
        unsafe_allow_html=True)

    return types.SimpleNamespace(
        mode=mode, posts_raw=posts_raw, posts=posts, scored=scored,
        lift=lift, live_features=live_features,
        start_date=start_date, end_date=end_date,
        min_d=min_d, max_d=max_d,
        hashtag_library=hashtag_library, curated_active=curated_active,
        drop_event=drop_event, scope=scope,
        drop_topics=drop_topics, drop_asks=drop_asks,
        drop_days=drop_days, drop_lengths=drop_lengths,
        drop_palettes=drop_palettes, drop_faces=drop_faces,
        drop_textimg=drop_textimg, drop_media=drop_media,
        drop_campaigns=drop_campaigns,
    )
