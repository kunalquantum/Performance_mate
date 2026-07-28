"""
LinkedIn Post Performance - BI presenter view.

Three vertical sections, one page:
    1. The scatter. Full year. Every post one dot. Click to select.
    2. The comparison. Selected post vs the top performer, side by side.
    3. The ideal post. Recipe averaged from the top performers.

Minimalist black-and-white with a single teal accent. Backend untouched -
this file only changes how the results are displayed.

Run:
    python -m streamlit run app.py
"""

import os
import re

import altair as alt
import pandas as pd
import streamlit as st

import scoring
import predictor
import image_analysis

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# palette - deliberately minimal
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

FEATURES = ["format_inferred", "theme", "cta_type", "length_band", "day_of_week",
            "media_type", "image_subject", "image_colour_theme", "has_face_in_image",
            "text_on_image", "target_region", "campaign"]

LABELS = {"format_inferred": "Format", "theme": "Topic", "cta_type": "Ask",
          "length_band": "Length", "day_of_week": "Publish day",
          "word_count": "Word count", "hashtag_count": "Hashtags",
          "hook_len": "First line", "hashtags": "Which hashtags",
          "media_type": "Media", "image_subject": "Image subject",
          "image_colour_theme": "Image colour", "has_face_in_image": "Face in image",
          "text_on_image": "Text on image", "target_region": "Target region",
          "campaign": "Campaign"}

st.set_page_config(page_title="LinkedIn Post Performance",
                   layout="wide", page_icon="○")

st.markdown(f"""
<style>
  html, body, [data-testid="stApp"] {{ background:{BG}; color:{INK};
      font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
  [data-testid="stApp"] {{ padding-top:0.5rem; }}
  [data-testid="stHeader"] {{ background:transparent; }}
  [data-testid="stSidebar"] {{ background:{BG_SOFT}; border-right:1px solid {LINE}; }}

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

  .stat {{ padding:.9rem 1.1rem; border:1px solid {LINE}; border-radius:6px;
           background:{BG}; }}
  .stat .k {{ font-size:.68rem; letter-spacing:.14em; text-transform:uppercase;
              color:{MUTED}; font-weight:600; }}
  .stat .v {{ font-size:1.6rem; font-weight:700; color:{INK};
              letter-spacing:-0.02em; margin-top:.2rem; }}
  .stat .d {{ font-size:.78rem; color:{MUTED}; margin-top:.1rem; }}

  .card {{ border:1px solid {LINE}; border-radius:8px; padding:1.3rem 1.5rem;
           background:{BG}; }}
  .card.selected {{ border-color:{ACCENT}; }}
  .card .tag {{ display:inline-block; font-size:.65rem; letter-spacing:.14em;
                text-transform:uppercase; font-weight:600; padding:.15rem .5rem;
                border-radius:2px; margin-bottom:.6rem; }}
  .card .tag.a {{ color:{ACCENT}; background:#EBF3F2; border:1px solid #D2E3E1; }}
  .card .tag.b {{ color:{INK_SOFT}; background:{BG_SOFT}; border:1px solid {LINE}; }}
  .card .hook {{ font-size:1.05rem; font-weight:600; color:{INK};
                 line-height:1.35; margin-bottom:.7rem; }}
  .card .meta {{ font-size:.78rem; color:{MUTED}; margin-bottom:1rem; }}
  .card .score {{ font-size:2.4rem; font-weight:700; color:{INK};
                  letter-spacing:-0.03em; line-height:1; }}
  .card .score-lbl {{ font-size:.7rem; letter-spacing:.14em; text-transform:uppercase;
                       color:{MUTED}; font-weight:600; }}
  .card .kv {{ display:flex; justify-content:space-between;
               padding:.5rem 0; border-top:1px solid {LINE}; font-size:.85rem; }}
  .card .kv .k {{ color:{MUTED}; }}
  .card .kv .v {{ color:{INK}; font-weight:500; text-align:right;
                   max-width:60%; }}
  .card .kv.win .v {{ color:{ACCENT}; font-weight:600; }}

  .recipe {{ border:1px solid {LINE}; border-radius:8px; padding:1.6rem 1.8rem;
             background:{BG}; }}
  .recipe .row {{ display:flex; justify-content:space-between; align-items:flex-start;
                  padding:.6rem 0; border-top:1px solid {LINE}; }}
  .recipe .row:first-child {{ border-top:none; }}
  .recipe .row .k {{ font-size:.72rem; letter-spacing:.14em; text-transform:uppercase;
                     color:{MUTED}; font-weight:600; padding-top:.15rem;
                     min-width:180px; }}
  .recipe .row .v {{ font-size:1rem; color:{INK}; font-weight:500;
                     text-align:right; max-width:60%; }}

  hr {{ border:none; border-top:1px solid {LINE}; margin:0; }}
  a, a:visited {{ color:{ACCENT}; }}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
@st.cache_data
def _load_csv_cached(path, mtime):
    """Cached by (path, mtime) so re-running the ETL invalidates automatically."""
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


posts_raw = load_csv("posts.csv")
if posts_raw.empty:
    st.error("No posts.csv found. Run `python etl.py --src <exports folder>` first.")
    st.stop()


# ---------------------------------------------------------------------------
# sidebar - non-date refinements only. Date range lives on the main view.
# ---------------------------------------------------------------------------
min_d = posts_raw["created_date"].min().date()
max_d = posts_raw["created_date"].max().date()

def _unique_vals(col):
    """Sorted distinct non-empty values for a column in posts_raw."""
    if col not in posts_raw.columns:
        return []
    s = posts_raw[col].dropna().astype(str).str.strip()
    return sorted([v for v in s.unique() if v and v.lower() != "nan"])


# ---------------------------------------------------------------------------
# Top-level app switch: LinkedIn Post Matrix vs Email Performance Matrix.
# The two apps share very little chrome, so most sections below are gated
# on `app` and the LinkedIn sidebar is hidden when Email is active.
# ---------------------------------------------------------------------------
if "app" not in st.session_state:
    st.session_state.app = "LinkedIn Post Matrix"

with st.sidebar:
    st.markdown('<div class="eyebrow">App</div>', unsafe_allow_html=True)
    st.radio(" ",
             ["LinkedIn Post Matrix", "Email Performance Matrix"],
             key="app", label_visibility="collapsed")
    st.markdown("---")

app = st.session_state.app

if app == "LinkedIn Post Matrix":
    with st.sidebar:
        st.markdown('<div class="eyebrow">Refine</div>', unsafe_allow_html=True)
        st.caption("Trim the set to see what wins on a normal week. Each "
                   "'Remove' box drops posts matching those values.")

        drop_event = st.checkbox("Skip event posts (ARMA etc.)", value=False,
                                 help="Event weeks distort the ranking. Skip them "
                                      "to see the shape of a normal week.")

        scope = st.selectbox("Format scope",
                             ["Every format", "Image or text",
                              "Video or document", "Article"])

        # --- Content filters ---
        with st.expander("Content filters", expanded=True):
            drop_topics = st.multiselect(
                "Remove topics", _unique_vals("theme"),
                help="Drop posts on these topics (pain_point, event_presence, etc.).")
            drop_asks = st.multiselect(
                "Remove asks / CTAs", _unique_vals("cta_type"),
                help="Drop posts using these calls to action (download, book_demo, etc.).")
            drop_days = st.multiselect(
                "Remove publish days",
                ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"],
                help="Drop posts published on these days of the week.")
            drop_lengths = st.multiselect(
                "Remove length bands", _unique_vals("length_band"),
                help="Drop posts in these length bands.")

        # --- Visual filters (only if tagging has been merged) ---
        has_visual = any(c in posts_raw.columns for c in
                         ("image_colour_theme", "has_face_in_image",
                          "text_on_image", "media_type"))
        if has_visual:
            with st.expander("Visual filters (tagged posts)", expanded=False):
                drop_palettes = st.multiselect(
                    "Remove image palettes", _unique_vals("image_colour_theme"),
                    help="Drop posts using these image colour palettes.")
                drop_faces = st.multiselect(
                    "Remove face in image", _unique_vals("has_face_in_image"),
                    help="Drop posts based on whether a face is shown.")
                drop_textimg = st.multiselect(
                    "Remove text on image", _unique_vals("text_on_image"),
                    help="Drop posts based on whether the image has text overlay.")
                drop_media = st.multiselect(
                    "Remove media types", _unique_vals("media_type"),
                    help="Drop posts of these media types.")
        else:
            drop_palettes = drop_faces = drop_textimg = drop_media = []

        # --- Campaign filter ---
        with st.expander("Campaign filter", expanded=False):
            drop_campaigns = st.multiselect(
                "Remove campaigns", _unique_vals("campaign"),
                help="Drop posts belonging to these campaigns.")

        if any([drop_topics, drop_asks, drop_days, drop_lengths, drop_palettes,
                drop_faces, drop_textimg, drop_media, drop_campaigns, drop_event,
                scope != "Every format"]):
            if st.button("Clear all filters", width='stretch'):
                for key in ["range_start_input", "range_end_input"]:
                    st.session_state.pop(key, None)
                st.rerun()

        st.markdown("---")
        st.markdown('<div class="eyebrow">GrantsNow hashtag playbook</div>',
                    unsafe_allow_html=True)
        st.caption("Upload the GrantsNow hashtag workbook. The Recommend screen "
                   "will apply the mix rule: 1 Broad + 2 Mid-tier + 1 Targeted "
                   "+ #GrantsNow.")
        hashtag_upload = st.file_uploader(
            "Upload hashtag workbook", type=["xls", "xlsx"],
            key="hashtag_library_file", label_visibility="collapsed")
        if hashtag_upload is not None:
            lib = scoring.load_hashtag_library(hashtag_upload)
            if lib and lib.get("categories"):
                st.session_state["hashtag_library"] = lib
                n_cats = len(lib["categories"])
                n_tags = len(lib["all_hashtags"])
                st.caption(f"Loaded {n_cats} categories, {n_tags} hashtags.")
            else:
                st.caption("Could not parse a category structure from that file.")
        hashtag_library = st.session_state.get("hashtag_library", None)
        curated_active = (hashtag_library["all_hashtags"]
                           if hashtag_library else [])

        # ---- topic -> category mapping, editable per topic when a library is loaded ----
        if hashtag_library and hashtag_library.get("categories"):
            with st.expander("Topic → category mapping", expanded=False):
                st.caption("Which library categories should each topic pull "
                           "hashtags from. Change any topic's mapping and the "
                           "Recommend screen updates instantly.")
                lib_categories = list(hashtag_library["categories"].keys())
                if "topic_to_category_override" not in st.session_state:
                    st.session_state["topic_to_category_override"] = {}
                for topic_key, default_cats in scoring.TOPIC_TO_CATEGORY.items():
                    # default = intersection of the shipped defaults with what's
                    # actually available in this workbook
                    default = [c for c in default_cats if c in lib_categories]
                    existing = st.session_state["topic_to_category_override"].get(
                        topic_key, default)
                    pick = st.multiselect(
                        topic_key, lib_categories, default=existing,
                        key=f"map_{topic_key}")
                    st.session_state["topic_to_category_override"][topic_key] = pick

        st.markdown("---")
        st.markdown('<div class="eyebrow">Signal weights</div>',
                    unsafe_allow_html=True)
        st.caption("How much each reaction counts toward the score.")
        for k, default in [("Comments", 6.0), ("Reposts", 4.0),
                           ("Clicks", 2.0), ("Likes", 1.0)]:
            scoring.WEIGHTS[k] = st.slider(k, 0.0, 10.0, default, 0.5)
else:
    # Email app: LinkedIn-side filter defaults so downstream references
    # (should any leak) do not crash. The LinkedIn body is skipped via
    # st.stop() further below.
    drop_event = False
    scope = "Every format"
    drop_topics = drop_asks = drop_days = drop_lengths = []
    drop_palettes = drop_faces = drop_textimg = drop_media = []
    drop_campaigns = []
    hashtag_library = None
    curated_active = []


# ---------------------------------------------------------------------------
# Email Performance Matrix: fully separate app. Renders its own header and
# screen picker, then hands off to the existing Email Matrix block by forcing
# mode="Email Matrix". Everything after the Email block is skipped with
# st.stop() so no LinkedIn code runs.
# ---------------------------------------------------------------------------
if app == "Email Performance Matrix":
    st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
                unsafe_allow_html=True)
    st.markdown('<h1>Email Performance Matrix</h1>', unsafe_allow_html=True)

    if "email_screen" not in st.session_state:
        st.session_state.email_screen = "Performance"
    escol1, _ = st.columns([3, 2])
    with escol1:
        st.radio(" ", ["Performance", "Audience", "Contents analysis"],
                 horizontal=True,
                 key="email_screen", label_visibility="collapsed")
    st.caption("Performance shows what has landed. Audience shows who you "
               "can reach. Contents analysis reads the live email campaigns "
               "and scores them against the house pattern.")

    mode = "Email Matrix"
else:
    # ------------------------- LinkedIn app header -------------------------
    st.markdown('<div class="eyebrow">GrantsNow &middot; LinkedIn</div>',
                unsafe_allow_html=True)
    st.markdown('<h1>Post Performance Matrix</h1>', unsafe_allow_html=True)

    # mode toggle - simple radio rendered as pill row
    if "mode" not in st.session_state:
        st.session_state.mode = "Explore"
    mcol1, _ = st.columns([3, 2])
    with mcol1:
        st.radio(" ", ["Explore", "Visualize", "Recommend"],
                 horizontal=True,
                 key="mode", label_visibility="collapsed")
    mode = st.session_state.mode

if app == "LinkedIn Post Matrix":
    # -----------------------------------------------------------------------
    # date range - lives on the main view, not the sidebar
    # -----------------------------------------------------------------------
    # Widget keys are the single source of truth. Preset buttons mutate them
    # directly, so the date_input widgets re-render with the new values.
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
            start = max(min_d, end - pd.Timedelta(days=days).to_pytimedelta())
            st.session_state.range_start_input = start
            st.session_state.range_end_input = end


    # Preset buttons FIRST so that a click updates the widget state before the
    # date_input widgets read from it during this rerun.
    dr1, dr2, dr3 = st.columns([2, 2, 3], gap="small")
    with dr3:
        st.markdown(
            f'<div class="eyebrow" style="margin-bottom:.2rem">Quick range</div>',
            unsafe_allow_html=True)
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            if st.button("30 days", key="pr_30d", width='stretch'):
                _set_range(days=30); st.rerun()
        with p2:
            if st.button("90 days", key="pr_90d", width='stretch'):
                _set_range(days=90); st.rerun()
        with p3:
            if st.button("6 months", key="pr_6m", width='stretch'):
                _set_range(days=182); st.rerun()
        with p4:
            if st.button("Full year", key="pr_full", width='stretch'):
                _set_range(full=True); st.rerun()
    with dr1:
        st.markdown(f'<div class="eyebrow" style="margin-bottom:.2rem">From</div>',
                    unsafe_allow_html=True)
        start_date = st.date_input(" ", min_value=min_d, max_value=max_d,
                                   key="range_start_input",
                                   label_visibility="collapsed")
    with dr2:
        st.markdown(f'<div class="eyebrow" style="margin-bottom:.2rem">To</div>',
                    unsafe_allow_html=True)
        end_date = st.date_input("  ", min_value=min_d, max_value=max_d,
                                 key="range_end_input",
                                 label_visibility="collapsed")

    # safety: if the user inverts them, use them swapped for filtering
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # -----------------------------------------------------------------------
    # apply filters
    # -----------------------------------------------------------------------
    posts = posts_raw.copy()
    d0, d1 = pd.Timestamp(start_date), pd.Timestamp(end_date)
    posts = posts[(posts["created_date"] >= d0) & (posts["created_date"] <= d1)]

    # ---- one 'Remove X' filter per parameter ----
    def _drop_by(col, values):
        """Drop rows whose column string value is in `values`."""
        global posts
        if not values or col not in posts.columns:
            return
        posts = posts[~posts[col].astype(str).str.strip().isin(values)]


    if drop_event:
        posts = posts[posts["theme"] != "event_presence"]
    if scope != "Every format":
        posts = posts[posts["format_inferred"] == scope]

    # content filters
    _drop_by("theme", drop_topics)
    _drop_by("cta_type", drop_asks)
    _drop_by("day_of_week", drop_days)
    _drop_by("length_band", drop_lengths)
    # visual filters (may be no-ops for posts without merged tags)
    _drop_by("image_colour_theme", drop_palettes)
    _drop_by("has_face_in_image", drop_faces)
    _drop_by("text_on_image", drop_textimg)
    _drop_by("media_type", drop_media)
    # campaign
    _drop_by("campaign", drop_campaigns)

    if posts.empty:
        st.warning("No posts left after those filters. Widen the date range or "
                   "clear some of the sidebar removals.")
        st.stop()

    scored = scoring.add_scores(posts).reset_index(drop=True)
    scored["idx"] = scored.index
    scored["date"] = scored["created_date"].dt.date
    scored["hook_short"] = scored["hook"].fillna("[No copy]").astype(str).str.slice(0, 70)

    live_features = [f for f in FEATURES if f in scored.columns
                     and scored[f].astype(str).str.strip().replace("nan", "").ne("").sum() >= 3]
    lift = scoring.attribute_lift(scored, live_features)

    _lede_hint = ("Each dot below is one post. Click a dot to compare it with the "
                  "top performer."
                  if mode == "Explore"
                  else "Retrain the recommender, then predict a draft or explore "
                       "what would lift an existing post.")
    st.markdown(
        f'<div class="lede">{len(scored)} posts &middot; '
        f'{start_date:%d %b %Y} to {end_date:%d %b %Y}. {_lede_hint}</div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# EMAIL MATRIX - a companion app for drafting result-driven promotional
# emails. Uses the house seven-slot pattern and the SaaS-vocabulary
# coverage check. No email performance data yet, so this is generative and
# analytical rather than historical.
# ---------------------------------------------------------------------------
if mode == "Email Matrix":
    if st.session_state.get("email_screen", "Performance") == "Performance":

        # ================== 1. LOAD THE REAL DATA ==================
        # Email data is on its own timeline (Dec 2024 - Jul 2025) that does not
        # overlap the LinkedIn window. Email Matrix runs on its own date range
        # so switching modes never leaves you looking at nothing.
        emails_all = load_csv("emails.csv")
        if not emails_all.empty:
            emails_all["week_start"] = pd.to_datetime(emails_all["week_start"],
                                                        errors="coerce")

        # ================== 2. HEADER + PERFORMANCE ==================
        st.markdown('<h2>Email Matrix</h2>', unsafe_allow_html=True)

        if emails_all.empty:
            st.warning("No `data/emails.csv` found. Run "
                        "`python etl/email_etl.py` from the project folder and "
                        "reload the page.")
            emails_df = emails_all
        else:
            e_min = emails_all["week_start"].min().date()
            e_max = emails_all["week_start"].max().date()
            st.caption(f"Email data spans {e_min:%d %b %Y} to {e_max:%d %b %Y}. "
                        "Pick a window below (independent from the LinkedIn date "
                        "range at the top of the page).")
            # Widget keys are the single source of truth. Preset buttons render
            # BEFORE the date_input widgets in code, so a button click mutates
            # state via st.rerun() and the widgets pick up the new values on
            # the next run rather than fighting them.
            if "email_range_start" not in st.session_state:
                st.session_state.email_range_start = e_min
            if "email_range_end" not in st.session_state:
                st.session_state.email_range_end = e_max

            def _set_email_range(weeks=None, full=False):
                if full:
                    st.session_state.email_range_start = e_min
                    st.session_state.email_range_end = e_max
                elif weeks:
                    start = max(e_min,
                                 e_max - pd.Timedelta(weeks=weeks).to_pytimedelta())
                    st.session_state.email_range_start = start
                    st.session_state.email_range_end = e_max

            er1, er2, er3 = st.columns([2, 2, 3], gap="small")
            # RENDER PRESETS FIRST so a click updates widget state before the
            # date_input widgets read from it during this rerun.
            with er3:
                st.markdown('<div class="eyebrow" style="margin-bottom:.2rem">'
                             'Quick range</div>', unsafe_allow_html=True)
                ep1, ep2, ep3 = st.columns(3)
                with ep1:
                    if st.button("Last 8 weeks", key="ep_8w",
                                 width='stretch'):
                        _set_email_range(weeks=8)
                        st.rerun()
                with ep2:
                    if st.button("Last quarter", key="ep_q",
                                 width='stretch'):
                        _set_email_range(weeks=13)
                        st.rerun()
                with ep3:
                    if st.button("All weeks", key="ep_all",
                                 width='stretch'):
                        _set_email_range(full=True)
                        st.rerun()
            with er1:
                st.markdown('<div class="eyebrow" style="margin-bottom:.2rem">'
                             'From</div>', unsafe_allow_html=True)
                e_start = st.date_input(
                    " ", min_value=e_min, max_value=e_max,
                    key="email_range_start", label_visibility="collapsed")
            with er2:
                st.markdown('<div class="eyebrow" style="margin-bottom:.2rem">'
                             'To</div>', unsafe_allow_html=True)
                e_end = st.date_input(
                    "  ", min_value=e_min, max_value=e_max,
                    key="email_range_end", label_visibility="collapsed")

            if e_start > e_end:
                e_start, e_end = e_end, e_start
            emails_df = emails_all[
                (emails_all["week_start"] >= pd.Timestamp(e_start))
                & (emails_all["week_start"] <= pd.Timestamp(e_end))]

        if emails_df.empty:
            st.warning("No email data in the picked window. Widen the range "
                        "above.")
        else:
            n_weeks_email = len(emails_df)
            total_sent = int(emails_df["emails_sent"].fillna(0).sum())
            total_contacts = int(emails_df["contacts"].fillna(0).sum())
            total_delivered = int(emails_df["delivered"].fillna(0).sum())
            total_opened = int(emails_df["opened"].fillna(0).sum())
            total_clicks = int(emails_df["clicks"].fillna(0).sum())
            avg_delivery = (total_delivered / total_contacts
                             if total_contacts else 0)
            avg_open = (total_opened / total_delivered
                         if total_delivered else 0)
            avg_click = (total_clicks / total_delivered
                          if total_delivered else 0)
            avg_ctor = (total_clicks / total_opened
                         if total_opened else 0)

            st.markdown(
                f'<div class="lede">{n_weeks_email} weeks of email campaigns. '
                f'{total_sent:,} emails to {total_contacts:,} contacts. '
                f'The scoring engine reads this file. Compose and analyse '
                f'sits below.</div>', unsafe_allow_html=True)

            # KPI tiles
            def _stat(label, value, delta=""):
                st.markdown(
                    f'<div class="stat"><div class="k">{label}</div>'
                    f'<div class="v">{value}</div>'
                    f'<div class="d">{delta}</div></div>',
                    unsafe_allow_html=True)
            k1, k2, k3, k4, k5 = st.columns(5)
            with k1: _stat("Emails sent", f"{total_sent}",
                            f"across {n_weeks_email} weeks")
            with k2: _stat("Contacts reached", f"{total_contacts:,}",
                            "total audience")
            with k3: _stat("Delivery rate", f"{avg_delivery*100:.1f}%",
                            "of contacts")
            with k4: _stat("Open rate", f"{avg_open*100:.1f}%",
                            "of delivered")
            with k5: _stat("Click rate", f"{avg_click*100:.2f}%",
                            "of delivered")

            # ---- WEEKLY DIGEST ----
            # Auto-generated one-paragraph summary of the most recent week in the
            # window, with comparison to the previous week where possible.
            latest = emails_df.sort_values("week_start", ascending=False)
            latest = latest[latest["contacts"].fillna(0) > 0]
            if not latest.empty:
                L = latest.iloc[0]
                prev = latest.iloc[1] if len(latest) > 1 else None

                def _delta_note(cur, prv, is_pct=False):
                    if prv is None or pd.isna(prv) or prv == 0:
                        return ""
                    d = cur - prv
                    if is_pct:
                        return (f" (up {d*100:.1f} pts vs the week before)"
                                 if d > 0 else
                                 f" (down {abs(d)*100:.1f} pts)")
                    return (f" (up {int(d):,} vs the week before)"
                             if d > 0 else f" (down {int(abs(d)):,})")

                digest_bits = []
                digest_bits.append(f"<b>{L['week_label']}.</b>")
                digest_bits.append(
                    f"{int(L['emails_sent'] or 0)} emails to "
                    f"{int(L['contacts'] or 0):,} contacts.")
                if pd.notna(L.get("open_rate")):
                    digest_bits.append(
                        f"Open rate <b>{L['open_rate']*100:.1f}%</b>"
                        f"{_delta_note(L['open_rate'], prev['open_rate'] if prev is not None else None, is_pct=True)}.")
                if pd.notna(L.get("click_rate")):
                    digest_bits.append(
                        f"Click rate <b>{L['click_rate']*100:.2f}%</b>"
                        f"{_delta_note(L['click_rate'], prev['click_rate'] if prev is not None else None, is_pct=True)}.")
                if pd.notna(L.get("bounce_rate")) and L["bounce_rate"] > 0.03:
                    digest_bits.append(
                        f"Bounce rate <span style='color:{WARN}'>"
                        f"{L['bounce_rate']*100:.1f}%</span> is above the "
                        f"3% risk line.")
                # best week highlight
                top_wk = emails_df.dropna(subset=["open_rate"]).nlargest(
                    1, "open_rate")
                if not top_wk.empty:
                    b = top_wk.iloc[0]
                    digest_bits.append(
                        f"Best week in this range: <b>{b['week_label']}</b> "
                        f"with a {b['open_rate']*100:.1f}% open rate on "
                        f"{int(b['contacts'] or 0):,} contacts.")

                st.markdown(
                    f'<div class="callout note" style="background:{ACCENT_SOFT}22;'
                    f'border-left:3px solid {ACCENT};padding:.9rem 1.1rem;'
                    f'border-radius:6px;margin:1.5rem 0">'
                    f'<div style="font-size:.68rem;letter-spacing:.14em;'
                    f'text-transform:uppercase;color:{MUTED};font-weight:600;'
                    f'margin-bottom:.35rem">Weekly digest</div>'
                    f'<div style="color:{INK};font-size:.95rem;line-height:1.55">'
                    + " ".join(digest_bits)
                    + '</div></div>', unsafe_allow_html=True)

            # ---- OPEN + CLICK RATE OVER TIME (with rolling avg + benchmarks) ----
            st.markdown('<h3 style="margin-top:2rem">Open and click rates by '
                        'week</h3>', unsafe_allow_html=True)
            st.caption("Open rate uses delivered as the base. Click rate too. "
                       "The lighter lines are 4-week rolling averages to smooth "
                       "the weekly noise. The dashed grey rules are the SaaS "
                       "industry benchmarks (~20% open, ~2% click).")

            # add rolling means before the melt
            e_sorted = emails_df.sort_values("week_start").copy()
            e_sorted["open_rate_rolling"] = e_sorted["open_rate"].rolling(
                window=4, min_periods=2).mean()
            e_sorted["click_rate_rolling"] = e_sorted["click_rate"].rolling(
                window=4, min_periods=2).mean()

            long_df = e_sorted.melt(
                id_vars=["week_start", "week_label", "emails_sent",
                         "contacts", "opened", "clicks"],
                value_vars=["open_rate", "click_rate"],
                var_name="metric", value_name="rate")
            long_df["metric_lbl"] = long_df["metric"].map({
                "open_rate": "Open rate", "click_rate": "Click rate"})

            rolling_df = e_sorted.melt(
                id_vars=["week_start", "week_label"],
                value_vars=["open_rate_rolling", "click_rate_rolling"],
                var_name="metric", value_name="rate")
            rolling_df["metric_lbl"] = rolling_df["metric"].map({
                "open_rate_rolling": "Open rate",
                "click_rate_rolling": "Click rate"})

            base_scale = alt.Scale(domain=["Open rate", "Click rate"],
                                    range=[ACCENT, GOLD])

            raw_line = alt.Chart(long_df).mark_line(
                point=alt.OverlayMarkDef(size=55, filled=True), opacity=0.9
            ).encode(
                x=alt.X("week_start:T", title=None,
                        axis=alt.Axis(labelColor=MUTED)),
                y=alt.Y("rate:Q", title="Rate",
                        axis=alt.Axis(format=".0%", labelColor=MUTED)),
                color=alt.Color("metric_lbl:N", title=None, scale=base_scale),
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("metric_lbl:N", title="Metric"),
                    alt.Tooltip("rate:Q", format=".2%", title="Rate"),
                    alt.Tooltip("emails_sent:Q", title="Emails"),
                    alt.Tooltip("contacts:Q", title="Contacts"),
                ],
            )
            smoothed = alt.Chart(rolling_df.dropna(subset=["rate"])).mark_line(
                strokeWidth=3, opacity=0.35
            ).encode(
                x="week_start:T", y="rate:Q",
                color=alt.Color("metric_lbl:N", scale=base_scale, legend=None))

            benchmarks = alt.Chart(pd.DataFrame({
                "y": [0.20, 0.02],
                "label": ["Open rate benchmark 20%", "Click rate benchmark 2%"],
            })).mark_rule(color=MUTED, strokeDash=[3, 4], opacity=0.7).encode(
                y="y:Q")

            st.altair_chart((raw_line + smoothed + benchmarks
            ).properties(height=300), width='stretch')

            # ---- CLICK-TO-OPEN RATE (CTOR) ----
            st.markdown('<h3 style="margin-top:2rem">Click-to-open rate</h3>',
                        unsafe_allow_html=True)
            st.caption("Clicks divided by opens. Isolates content quality from "
                       "subject-line quality. If the open rate is falling but "
                       "CTOR is stable, the copy is fine and the subject "
                       "line is the problem. Industry benchmark for SaaS is "
                       "about 10 to 15 percent.")

            ctor_df = emails_df.dropna(subset=["ctor"]).sort_values("week_start")
            if not ctor_df.empty:
                ctor_line = alt.Chart(ctor_df).mark_line(
                    color=ACCENT, strokeWidth=2,
                    point=alt.OverlayMarkDef(size=60, filled=True, color=ACCENT)
                ).encode(
                    x=alt.X("week_start:T", title=None,
                            axis=alt.Axis(labelColor=MUTED)),
                    y=alt.Y("ctor:Q", title="CTOR",
                            axis=alt.Axis(format=".0%", labelColor=MUTED)),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("ctor:Q", format=".2%", title="CTOR"),
                        alt.Tooltip("opened:Q", title="Opens"),
                        alt.Tooltip("clicks:Q", title="Clicks"),
                    ],
                )
                ctor_bench = alt.Chart(pd.DataFrame({
                    "y": [0.10, 0.15],
                })).mark_rule(color=MUTED, strokeDash=[3, 4], opacity=0.6).encode(
                    y="y:Q")
                st.altair_chart((ctor_line + ctor_bench).properties(height=240),
                                width='stretch')
            else:
                st.info("Not enough data to compute CTOR in this window.")

            # ---- A/B TEST DETECTION ----
            # The ab_a_contacts / ab_b_contacts columns come from the updated
            # ETL. If the CSV was written before that update the columns will
            # be missing - fall back gracefully instead of crashing.
            if "ab_a_contacts" not in emails_df.columns:
                st.info("A/B batch detection needs a refresh. Run "
                         "`python etl/email_etl.py` again from the project folder "
                         "to add the new columns.")
                ab_weeks = pd.DataFrame()
            else:
                ab_weeks = emails_df.dropna(subset=["ab_a_contacts"])
            if not ab_weeks.empty:
                st.markdown('<h3 style="margin-top:2rem">A/B test detected</h3>',
                            unsafe_allow_html=True)
                st.caption(
                    f"{len(ab_weeks)} week(s) in this window used the A/B split "
                    f"notation from your task sheet. Side-by-side sizes shown "
                    f"below. Add opens/clicks per batch to the task sheet to "
                    f"score which side won.")
                for _, r in ab_weeks.iterrows():
                    ab1, ab2 = st.columns(2, gap="medium")
                    with ab1:
                        st.markdown(
                            f'<div class="card">'
                            f'<span class="tag a">Batch A</span>'
                            f'<div style="margin:.4rem 0">'
                            f'<b style="font-size:1.3rem">'
                            f'{int(r["ab_a_contacts"])}</b>'
                            f' contacts &middot; '
                            f'{int(r["ab_a_delivered"])} delivered</div>'
                            f'<div style="font-size:.78rem;color:{MUTED}">'
                            f'{r["week_label"]}</div>'
                            f'</div>', unsafe_allow_html=True)
                    with ab2:
                        st.markdown(
                            f'<div class="card">'
                            f'<span class="tag b">Batch B</span>'
                            f'<div style="margin:.4rem 0">'
                            f'<b style="font-size:1.3rem">'
                            f'{int(r["ab_b_contacts"])}</b>'
                            f' contacts &middot; '
                            f'{int(r["ab_b_delivered"])} delivered</div>'
                            f'<div style="font-size:.78rem;color:{MUTED}">'
                            f'{r["week_label"]}</div>'
                            f'</div>', unsafe_allow_html=True)

            # ---- CADENCE ----
            st.markdown('<h3 style="margin-top:2rem">Cadence and audience</h3>',
                        unsafe_allow_html=True)
            st.caption("Bars = emails sent that week. Line = contacts reached. "
                       "Weeks with no bars but a full audience are days when a "
                       "big campaign went out.")
            _bars = alt.Chart(emails_df).mark_bar(
                color=MUTED, opacity=0.7).encode(
                x=alt.X("week_start:T", title=None),
                y=alt.Y("emails_sent:Q", title="Emails / week",
                        axis=alt.Axis(labelColor=MUTED)),
                tooltip=[alt.Tooltip("week_label:N", title="Week"),
                         alt.Tooltip("emails_sent:Q", title="Emails"),
                         alt.Tooltip("contacts:Q", title="Contacts")],
            )
            _cline = alt.Chart(emails_df).mark_line(
                color=ACCENT, strokeWidth=2).encode(
                x="week_start:T",
                y=alt.Y("contacts:Q", title="Contacts / week",
                        axis=alt.Axis(labelColor=ACCENT, titleColor=ACCENT)))
            st.altair_chart(
                alt.layer(_bars, _cline).resolve_scale(y="independent"
                ).properties(height=260), width='stretch')

            # ---- BATCH SIZE VS OPEN RATE ----
            st.markdown('<h3 style="margin-top:2rem">Batch size vs open rate</h3>',
                        unsafe_allow_html=True)
            st.caption("Does sending to a bigger list dilute the open rate? "
                       "One dot per week. Size = clicks, colour = click rate.")
            scat = alt.Chart(emails_df.dropna(subset=["open_rate"])
            ).mark_circle(opacity=0.85, stroke=INK, strokeWidth=0.4).encode(
                x=alt.X("contacts:Q",
                        title="Contacts reached (log)",
                        scale=alt.Scale(type="log", base=10)),
                y=alt.Y("open_rate:Q", title="Open rate",
                        axis=alt.Axis(format=".0%")),
                size=alt.Size("clicks:Q",
                              scale=alt.Scale(range=[40, 400]),
                              title="Clicks"),
                color=alt.Color("click_rate:Q",
                                scale=alt.Scale(scheme="teals"),
                                title="Click rate"),
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("contacts:Q", title="Contacts"),
                    alt.Tooltip("open_rate:Q", format=".2%",
                                title="Open rate"),
                    alt.Tooltip("click_rate:Q", format=".2%",
                                title="Click rate"),
                    alt.Tooltip("clicks:Q", title="Clicks"),
                ],
            ).properties(height=320)
            st.altair_chart(scat, width='stretch')

            # ---- DELIVERY HEALTH ----
            st.markdown('<h3 style="margin-top:2rem">Delivery health</h3>',
                        unsafe_allow_html=True)
            st.caption("Bounce rate over time. Anything above 3% is a warning "
                       "sign. Above 5% and the sender reputation is at risk.")
            health = alt.Chart(emails_df.dropna(subset=["bounce_rate"])
            ).mark_area(color=WARN, opacity=0.25).encode(
                x=alt.X("week_start:T", title=None),
                y=alt.Y("bounce_rate:Q", title="Bounce rate",
                        axis=alt.Axis(format=".1%")),
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("bounce_rate:Q", format=".2%",
                                title="Bounce rate"),
                    alt.Tooltip("bounced:Q", title="Bounced"),
                    alt.Tooltip("contacts:Q", title="Contacts"),
                ],
            ) + alt.Chart(emails_df.dropna(subset=["bounce_rate"])
            ).mark_line(color=WARN, strokeWidth=1.5).encode(
                x="week_start:T", y="bounce_rate:Q") + alt.Chart(
                pd.DataFrame({"y": [0.03]})
            ).mark_rule(color=MUTED, strokeDash=[3, 3]).encode(y="y:Q")
            st.altair_chart(health.properties(height=200),
                            width='stretch')

            # ---- BEST AND WORST WEEKS ----
            st.markdown('<h3 style="margin-top:2rem">Best and worst weeks</h3>',
                        unsafe_allow_html=True)
            st.caption("By open rate. Rows read left to right: week, emails "
                       "sent, contacts, delivered, opens, clicks, open rate, "
                       "click rate.")
            table_df = emails_df.dropna(subset=["open_rate"]).copy()
            table_df["display_open"] = (table_df["open_rate"]
                                         .apply(lambda x: f"{x*100:.1f}%"))
            table_df["display_click"] = (table_df["click_rate"]
                                          .apply(lambda x: f"{x*100:.2f}%"
                                                  if pd.notna(x) else ""))
            rank_cols = ["week_label", "emails_sent", "contacts",
                          "delivered", "opened", "clicks",
                          "display_open", "display_click"]
            col_config = {
                "week_label": st.column_config.TextColumn("Week", width="medium"),
                "emails_sent": st.column_config.NumberColumn("Emails",
                                                              format="%d"),
                "contacts": st.column_config.NumberColumn("Contacts",
                                                           format="%d"),
                "delivered": st.column_config.NumberColumn("Delivered",
                                                            format="%d"),
                "opened": st.column_config.NumberColumn("Opens", format="%d"),
                "clicks": st.column_config.NumberColumn("Clicks", format="%d"),
                "display_open": st.column_config.TextColumn("Open rate"),
                "display_click": st.column_config.TextColumn("Click rate"),
            }
            top_bot = st.tabs(["Top 5 by open rate", "Bottom 5 by open rate"])
            with top_bot[0]:
                st.dataframe(
                    table_df.nlargest(5, "open_rate")[rank_cols],
                    width='stretch', hide_index=True,
                    column_config=col_config)
            with top_bot[1]:
                st.dataframe(
                    table_df.nsmallest(5, "open_rate")[rank_cols],
                    width='stretch', hide_index=True,
                    column_config=col_config)

        # ================================================================
        # 3. DEEPER ANALYSIS (statistical rigor, segmentation, forecasting,
        # diagnostics). Tabbed to keep the scroll manageable.
        # ================================================================
        if not emails_all.empty and not emails_df.empty:
            from scipy import stats as _sci_stats
            import numpy as np

            # ---- helper: Wilson score interval for a proportion ----
            def _wilson(k, n, z=1.96):
                if not n or pd.isna(k) or pd.isna(n) or n == 0:
                    return (float("nan"), float("nan"))
                p = k / n
                denom = 1 + z * z / n
                centre = (p + z * z / (2 * n)) / denom
                spread = (z / denom) * ((p * (1 - p) / n
                                           + z * z / (4 * n * n)) ** 0.5)
                return max(0.0, centre - spread), min(1.0, centre + spread)

            # ---- helper: forecast next 4 weeks using linear extrapolation ----
            def _forecast_next_4(series_dates, series_values):
                valid = pd.DataFrame({"d": series_dates,
                                        "v": series_values}).dropna()
                if len(valid) < 4:
                    return pd.DataFrame()
                valid["x"] = (valid["d"] - valid["d"].min()).dt.days
                slope, intercept, r, _, _ = _sci_stats.linregress(
                    valid["x"], valid["v"])
                future = []
                last_d = valid["d"].max()
                last_x = valid["x"].max()
                for i in range(1, 5):
                    d = last_d + pd.Timedelta(days=7 * i)
                    x = last_x + 7 * i
                    pred = intercept + slope * x
                    future.append({"d": d, "v": max(0.0, min(1.0, pred))})
                return pd.DataFrame(future)

            # ---- helper: change-point detection using rolling z-scores ----
            def _flag_anomalies(series, threshold=2.0, window=4):
                s = pd.Series(series)
                mean = s.rolling(window, min_periods=2).mean()
                std = s.rolling(window, min_periods=2).std().replace(0, np.nan)
                z = (s - mean) / std
                return z.abs() >= threshold, z

            e = emails_df.sort_values("week_start").reset_index(drop=True)

            st.markdown('<div style="margin:2.5rem 0 0;border-top:1px solid '
                         + LINE + '"></div>', unsafe_allow_html=True)
            st.markdown('<h2>Deeper analysis</h2>', unsafe_allow_html=True)

            etab1, etab2, etab3, etab4 = st.tabs([
                "Rigor", "Segmentation", "Efficiency",
                "Forecast & diagnostics"])

            # ------------------------------------------------------------
            # TAB 1. RIGOR
            # ------------------------------------------------------------
            with etab1:
                st.markdown('<h3>Confidence bands on the open rate</h3>',
                            unsafe_allow_html=True)
                st.caption("Wilson score 95% intervals. Weeks with tiny audiences "
                           "get wide bands - so a 60% open on 50 contacts is "
                           "clearly less certain than a 10% open on 3,000.")

                ci = e.dropna(subset=["opened", "delivered"]).copy()
                ci["lo"], ci["hi"] = zip(*[
                    _wilson(k, n)
                    for k, n in zip(ci["opened"], ci["delivered"])])
                band = alt.Chart(ci).mark_area(color=ACCENT, opacity=0.18).encode(
                    x=alt.X("week_start:T", title=None),
                    y=alt.Y("lo:Q", title="Open rate",
                            axis=alt.Axis(format=".0%")),
                    y2="hi:Q",
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("open_rate:Q", format=".2%",
                                    title="Open rate"),
                        alt.Tooltip("lo:Q", format=".2%", title="95% low"),
                        alt.Tooltip("hi:Q", format=".2%", title="95% high"),
                        alt.Tooltip("delivered:Q", title="Sample size")])
                centre = alt.Chart(ci).mark_line(
                    color=ACCENT, strokeWidth=2,
                    point=alt.OverlayMarkDef(size=50, filled=True)
                ).encode(x="week_start:T", y="open_rate:Q",
                         tooltip=[
                             alt.Tooltip("week_label:N", title="Week"),
                             alt.Tooltip("open_rate:Q", format=".2%",
                                         title="Open rate"),
                             alt.Tooltip("delivered:Q", title="Sample size")])
                st.altair_chart((band + centre).properties(height=280),
                                width='stretch')

                # percentile of latest week vs own history
                st.markdown('<h3 style="margin-top:2rem">Percentile against '
                            'your own history</h3>', unsafe_allow_html=True)
                st.caption("Where the most recent week sits against every "
                           "week in the data. Your own baseline, not an "
                           "industry number.")
                all_open = emails_all.dropna(subset=["open_rate"])["open_rate"]
                latest_row = e[e["contacts"].fillna(0) > 0].sort_values(
                    "week_start", ascending=False)
                if not latest_row.empty and not all_open.empty:
                    L = latest_row.iloc[0]
                    pctile = int((all_open < L["open_rate"]).mean() * 100)
                    pt1, pt2, pt3 = st.columns(3)
                    with pt1:
                        _stat("Open rate this week",
                                f"{L['open_rate']*100:.1f}%",
                                L["week_label"])
                    with pt2:
                        _stat("Percentile", f"{pctile}th",
                                "of your own 30 weeks")
                    with pt3:
                        med = all_open.median() * 100
                        _stat("Median across history", f"{med:.1f}%",
                                "the middle-of-the-pack week")

                # A/B with significance
                if "ab_a_contacts" in e.columns:
                    st.markdown('<h3 style="margin-top:2rem">A/B batches: '
                                'is the difference real?</h3>',
                                unsafe_allow_html=True)
                    ab = e.dropna(subset=["ab_a_contacts", "ab_b_contacts"])
                    if ab.empty:
                        st.info("No A/B weeks in this window.")
                    else:
                        st.caption(
                            "Fisher's exact test on delivered rates. Flags "
                            "'significant at 95%' or 'not enough sample'. "
                            "To score opens or clicks per batch, add those "
                            "to the task sheet.")
                        for _, r in ab.iterrows():
                            a_c = int(r["ab_a_contacts"] or 0)
                            b_c = int(r["ab_b_contacts"] or 0)
                            a_d = int(r["ab_a_delivered"] or 0)
                            b_d = int(r["ab_b_delivered"] or 0)
                            if a_c and b_c:
                                table = [[a_d, a_c - a_d],
                                          [b_d, b_c - b_d]]
                                try:
                                    odds, p = _sci_stats.fisher_exact(table)
                                except Exception:
                                    p = None
                                sig = ("significant at 95%"
                                        if p is not None and p < 0.05
                                        else "not significant given the sample")
                                st.markdown(
                                    f'<div class="card">'
                                    f'<b>{r["week_label"]}</b> &middot; '
                                    f'A: {a_d}/{a_c} delivered '
                                    f'&middot; B: {b_d}/{b_c} delivered '
                                    f'&middot; <span style="color:{MUTED}">'
                                    f'p={p:.3f}, {sig}</span>'
                                    f'</div>' if p is not None else
                                    f'<div class="card">'
                                    f'<b>{r["week_label"]}</b> &middot; '
                                    f'sample too small</div>',
                                    unsafe_allow_html=True)

            # ------------------------------------------------------------
            # TAB 2. SEGMENTATION
            # ------------------------------------------------------------
            with etab2:
                st.markdown('<h3>Batch size analysis</h3>',
                            unsafe_allow_html=True)
                st.caption("Weeks binned into quartiles by contact count. "
                           "Median open and click rate for each bin. Answers "
                           "whether small tight sends really outperform.")
                bs = e.dropna(subset=["contacts", "open_rate"]).copy()
                if len(bs) >= 4:
                    bs["bin"] = pd.qcut(bs["contacts"], q=4,
                                         labels=["Q1 (smallest)", "Q2", "Q3",
                                                  "Q4 (largest)"],
                                         duplicates="drop")
                    agg = bs.groupby("bin", as_index=False).agg(
                        weeks=("contacts", "count"),
                        median_contacts=("contacts", "median"),
                        median_open=("open_rate", "median"),
                        median_click=("click_rate", "median"))
                    melt = agg.melt(id_vars=["bin", "weeks", "median_contacts"],
                                     value_vars=["median_open", "median_click"],
                                     var_name="metric", value_name="rate")
                    melt["metric_lbl"] = melt["metric"].map({
                        "median_open": "Open rate",
                        "median_click": "Click rate"})
                    bs_chart = alt.Chart(melt).mark_bar(
                        cornerRadiusEnd=3).encode(
                        x=alt.X("bin:N", title=None, sort=list(agg["bin"])),
                        y=alt.Y("rate:Q", title="Median rate",
                                axis=alt.Axis(format=".0%")),
                        color=alt.Color("metric_lbl:N", title=None,
                                         scale=alt.Scale(
                                             domain=["Open rate",
                                                      "Click rate"],
                                             range=[ACCENT, GOLD])),
                        column=alt.Column("metric_lbl:N", title=None),
                        tooltip=[
                            alt.Tooltip("bin:N", title="Batch bin"),
                            alt.Tooltip("weeks:Q", title="Weeks"),
                            alt.Tooltip("median_contacts:Q",
                                        title="Median contacts", format=",.0f"),
                            alt.Tooltip("rate:Q", format=".2%",
                                        title="Median rate")])
                    st.altair_chart(bs_chart, width='stretch')
                else:
                    st.info("Need at least 4 weeks in the window.")

                st.markdown('<h3 style="margin-top:2rem">Cadence fatigue</h3>',
                            unsafe_allow_html=True)
                st.caption("Is heavy sending this week hurting next week's open "
                           "rate? Trailing 2-week send volume plotted against "
                           "the following week's open rate. A downward slope "
                           "means the list is being over-sent.")
                fatigue = e.copy()
                fatigue["send_2w"] = fatigue["emails_sent"].rolling(
                    window=2, min_periods=1).sum()
                fatigue["next_open"] = fatigue["open_rate"].shift(-1)
                fatigue = fatigue.dropna(subset=["send_2w", "next_open"])
                if not fatigue.empty:
                    base = alt.Chart(fatigue).encode(
                        x=alt.X("send_2w:Q",
                                title="Emails sent in the last 2 weeks"),
                        y=alt.Y("next_open:Q",
                                title="Following week's open rate",
                                axis=alt.Axis(format=".0%")),
                        tooltip=[
                            alt.Tooltip("week_label:N", title="This week"),
                            alt.Tooltip("send_2w:Q",
                                        title="Trailing 2w sends"),
                            alt.Tooltip("next_open:Q",
                                        title="Next week open rate",
                                        format=".2%")])
                    pts = base.mark_circle(size=100, color=ACCENT, opacity=0.8,
                                            stroke=INK, strokeWidth=0.4)
                    trend = base.transform_regression(
                        "send_2w", "next_open").mark_line(
                        color=WARN, strokeDash=[4, 3], strokeWidth=2)
                    st.altair_chart((pts + trend).properties(height=280),
                                    width='stretch')
                    # correlation
                    r_val = fatigue[["send_2w", "next_open"]].corr().iloc[0, 1]
                    verdict = ("suggests fatigue" if r_val < -0.2
                                else "no clear fatigue signal"
                                if r_val > -0.2 and r_val < 0.2
                                else "the opposite - more sends, more opens")
                    st.caption(f"Correlation: {r_val:+.2f}. "
                                f"The pattern {verdict}.")

                st.markdown('<h3 style="margin-top:2rem">Monthly cohorts</h3>',
                            unsafe_allow_html=True)
                st.caption("Aggregated to calendar month. Which months naturally "
                           "perform better and by how much.")
                month_agg = e.copy()
                month_agg["month"] = month_agg["week_start"].dt.to_period(
                    "M").dt.start_time
                m = month_agg.groupby("month").agg(
                    emails=("emails_sent", "sum"),
                    contacts=("contacts", "sum"),
                    delivered=("delivered", "sum"),
                    opened=("opened", "sum"),
                    clicks=("clicks", "sum")).reset_index()
                m["open_rate"] = m["opened"] / m["delivered"].replace(0, np.nan)
                m["click_rate"] = m["clicks"] / m["delivered"].replace(0, np.nan)
                m_melt = m.melt(id_vars=["month"],
                                 value_vars=["open_rate", "click_rate"],
                                 var_name="metric", value_name="rate")
                m_melt["metric_lbl"] = m_melt["metric"].map({
                    "open_rate": "Open rate", "click_rate": "Click rate"})
                mch = alt.Chart(m_melt).mark_bar(cornerRadiusEnd=3).encode(
                    x=alt.X("month:T", title=None),
                    y=alt.Y("rate:Q", title="Rate",
                            axis=alt.Axis(format=".0%")),
                    color=alt.Color("metric_lbl:N", title=None,
                                     scale=alt.Scale(
                                         domain=["Open rate", "Click rate"],
                                         range=[ACCENT, GOLD])),
                    xOffset="metric_lbl:N",
                    tooltip=[alt.Tooltip("month:T", format="%b %Y"),
                             alt.Tooltip("metric_lbl:N", title="Metric"),
                             alt.Tooltip("rate:Q", format=".2%")])
                st.altair_chart(mch.properties(height=260),
                                width='stretch')

                st.markdown('<h3 style="margin-top:2rem">Quarterly rollup</h3>',
                            unsafe_allow_html=True)
                month_agg["quarter"] = month_agg["week_start"].dt.to_period(
                    "Q").astype(str)
                q = month_agg.groupby("quarter").agg(
                    emails=("emails_sent", "sum"),
                    contacts=("contacts", "sum"),
                    delivered=("delivered", "sum"),
                    opened=("opened", "sum"),
                    clicks=("clicks", "sum")).reset_index()
                q["open_rate"] = q["opened"] / q["delivered"].replace(0, np.nan)
                q["click_rate"] = q["clicks"] / q["delivered"].replace(0, np.nan)
                q_disp = q[["quarter", "emails", "contacts", "delivered",
                             "opened", "clicks", "open_rate",
                             "click_rate"]].copy()
                q_disp["open_rate"] = q_disp["open_rate"].apply(
                    lambda x: f"{x*100:.1f}%" if pd.notna(x) else "")
                q_disp["click_rate"] = q_disp["click_rate"].apply(
                    lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
                st.dataframe(q_disp, width='stretch', hide_index=True,
                             column_config={
                                 "quarter": st.column_config.TextColumn(
                                     "Quarter"),
                                 "emails": st.column_config.NumberColumn(
                                     "Emails", format="%d"),
                                 "contacts": st.column_config.NumberColumn(
                                     "Contacts", format="%d"),
                                 "delivered": st.column_config.NumberColumn(
                                     "Delivered", format="%d"),
                                 "opened": st.column_config.NumberColumn(
                                     "Opens", format="%d"),
                                 "clicks": st.column_config.NumberColumn(
                                     "Clicks", format="%d"),
                                 "open_rate": st.column_config.TextColumn(
                                     "Open rate"),
                                 "click_rate": st.column_config.TextColumn(
                                     "Click rate"),
                             })

            # ------------------------------------------------------------
            # TAB 3. EFFICIENCY
            # ------------------------------------------------------------
            with etab3:
                eff = e.copy()
                eff["opens_per_email"] = eff["opened"] / eff["emails_sent"].replace(
                    0, np.nan)
                eff["clicks_per_email"] = eff["clicks"] / eff["emails_sent"].replace(
                    0, np.nan)
                eff["opens_per_contact"] = eff["opened"] / eff["contacts"].replace(
                    0, np.nan)
                eff["waste"] = (eff["contacts"] - eff["opened"]).clip(lower=0)

                st.markdown('<h3>Opens per email sent</h3>',
                            unsafe_allow_html=True)
                st.caption("A different lens on efficiency. Weeks with lots of "
                           "emails but few opens read as expensive here. "
                           "Higher is better.")
                oe = alt.Chart(eff.dropna(subset=["opens_per_email"])).mark_bar(
                    color=ACCENT, opacity=0.85).encode(
                    x=alt.X("week_start:T", title=None),
                    y=alt.Y("opens_per_email:Q", title="Opens / email sent"),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("emails_sent:Q", title="Emails"),
                        alt.Tooltip("opened:Q", title="Opens"),
                        alt.Tooltip("opens_per_email:Q", format=".1f",
                                    title="Opens / email")])
                st.altair_chart(oe.properties(height=240),
                                width='stretch')

                st.markdown('<h3 style="margin-top:2rem">Effort scatter</h3>',
                            unsafe_allow_html=True)
                st.caption("X: emails sent that week. Y: total opens that week. "
                           "Top-left is a hero week (few emails, many opens). "
                           "Bottom-right is a warning (many emails, few opens).")
                eff_scatter = alt.Chart(eff.dropna(subset=[
                    "emails_sent", "opened"])).mark_circle(
                    size=140, color=ACCENT, opacity=0.85,
                    stroke=INK, strokeWidth=0.4).encode(
                    x=alt.X("emails_sent:Q", title="Emails sent"),
                    y=alt.Y("opened:Q", title="Total opens"),
                    size=alt.Size("contacts:Q",
                                  scale=alt.Scale(range=[80, 500]),
                                  title="Contacts"),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("emails_sent:Q", title="Emails"),
                        alt.Tooltip("opened:Q", title="Opens"),
                        alt.Tooltip("contacts:Q", title="Contacts")])
                st.altair_chart(eff_scatter.properties(height=340),
                                width='stretch')

                st.markdown('<h3 style="margin-top:2rem">Waste tracker</h3>',
                            unsafe_allow_html=True)
                st.caption("Contacts that received an email but did not open it, "
                           "per week. This is the volume going out with no "
                           "return. Absolute count, not a rate.")
                waste_chart = alt.Chart(eff.dropna(subset=["waste"])).mark_area(
                    color=WARN, opacity=0.25).encode(
                    x=alt.X("week_start:T", title=None),
                    y=alt.Y("waste:Q", title="Unopened contacts",
                            axis=alt.Axis(format=",.0f")),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("waste:Q", format=",.0f",
                                    title="Unopened"),
                        alt.Tooltip("contacts:Q", format=",.0f",
                                    title="Total contacts"),
                        alt.Tooltip("opened:Q", format=",.0f",
                                    title="Opens")]) + alt.Chart(
                    eff.dropna(subset=["waste"])).mark_line(
                    color=WARN, strokeWidth=1.5).encode(
                    x="week_start:T", y="waste:Q")
                st.altair_chart(waste_chart.properties(height=220),
                                width='stretch')

            # ------------------------------------------------------------
            # TAB 4. FORECAST & DIAGNOSTICS
            # ------------------------------------------------------------
            with etab4:
                st.markdown('<h3>4-week forecast</h3>', unsafe_allow_html=True)
                st.caption("Simple linear extrapolation on the recent trend. "
                           "Solid line = actual. Dashed line = forecast. "
                           "Directional, not oracular.")
                fc_open = _forecast_next_4(e["week_start"], e["open_rate"])
                fc_click = _forecast_next_4(e["week_start"], e["click_rate"])
                if not fc_open.empty:
                    actual_o = e[["week_start", "open_rate"]].rename(
                        columns={"week_start": "d", "open_rate": "v"}).assign(
                        kind="actual", metric="Open rate")
                    actual_c = e[["week_start", "click_rate"]].rename(
                        columns={"week_start": "d", "click_rate": "v"}).assign(
                        kind="actual", metric="Click rate")
                    fc_o_lbl = fc_open.assign(kind="forecast",
                                                 metric="Open rate")
                    fc_c_lbl = fc_click.assign(kind="forecast",
                                                  metric="Click rate")
                    fc_all = pd.concat([actual_o, actual_c, fc_o_lbl,
                                         fc_c_lbl], ignore_index=True)
                    fc_chart = alt.Chart(fc_all.dropna(subset=["v"])).mark_line(
                        point=alt.OverlayMarkDef(size=45, filled=True)
                    ).encode(
                        x=alt.X("d:T", title=None),
                        y=alt.Y("v:Q", title="Rate",
                                axis=alt.Axis(format=".0%")),
                        color=alt.Color("metric:N", title=None,
                                         scale=alt.Scale(
                                             domain=["Open rate", "Click rate"],
                                             range=[ACCENT, GOLD])),
                        strokeDash=alt.StrokeDash("kind:N",
                                                    scale=alt.Scale(
                                                        domain=["actual",
                                                                 "forecast"],
                                                        range=[[1, 0],
                                                                [4, 3]])))
                    st.altair_chart(fc_chart.properties(height=280),
                                    width='stretch')
                else:
                    st.info("Need at least 4 weeks with data to forecast.")

                st.markdown('<h3 style="margin-top:2rem">Anomaly detection</h3>',
                            unsafe_allow_html=True)
                st.caption("Weeks where open rate deviated more than 2 standard "
                           "deviations from the rolling 4-week trend. Real "
                           "signals of a shift, not weekly noise.")
                flag, z = _flag_anomalies(e["open_rate"].values, threshold=2.0,
                                           window=4)
                e_anom = e.copy()
                e_anom["anomaly"] = flag
                e_anom["z"] = z
                base_line = alt.Chart(e_anom).mark_line(
                    color=MUTED, strokeWidth=1.5).encode(
                    x="week_start:T", y=alt.Y("open_rate:Q", title="Open rate",
                                              axis=alt.Axis(format=".0%")))
                normal_pts = alt.Chart(e_anom[~e_anom["anomaly"]]).mark_circle(
                    color=MUTED, size=50, opacity=0.8).encode(
                    x="week_start:T", y="open_rate:Q",
                    tooltip=[alt.Tooltip("week_label:N", title="Week"),
                             alt.Tooltip("open_rate:Q", format=".2%",
                                         title="Open rate")])
                anom_pts = alt.Chart(e_anom[e_anom["anomaly"]]).mark_circle(
                    color=WARN, size=140, opacity=0.9,
                    stroke=INK, strokeWidth=1).encode(
                    x="week_start:T", y="open_rate:Q",
                    tooltip=[alt.Tooltip("week_label:N", title="Week"),
                             alt.Tooltip("open_rate:Q", format=".2%",
                                         title="Open rate"),
                             alt.Tooltip("z:Q", format="+.2f",
                                         title="Z-score")])
                st.altair_chart(
                    (base_line + normal_pts + anom_pts).properties(height=280),
                    width='stretch')
                n_anom = int(e_anom["anomaly"].sum())
                st.caption(f"{n_anom} anomalous week(s) detected in this "
                            f"window.")

                st.markdown('<h3 style="margin-top:2rem">Correlation matrix</h3>',
                            unsafe_allow_html=True)
                st.caption("How the numeric metrics move together. Red pairs are "
                           "inversely related, teal pairs move in the same "
                           "direction.")
                corr_cols = ["emails_sent", "contacts", "delivered",
                              "bounced", "opened", "clicks", "delivery_rate",
                              "bounce_rate", "open_rate", "click_rate", "ctor"]
                corr_cols = [c for c in corr_cols if c in e.columns]
                corr = e[corr_cols].corr().round(2).reset_index().melt(
                    "index", var_name="col", value_name="corr").rename(
                    columns={"index": "row"})
                cm = alt.Chart(corr).mark_rect().encode(
                    x=alt.X("col:N", title=None,
                            axis=alt.Axis(labelAngle=-40)),
                    y=alt.Y("row:N", title=None),
                    color=alt.Color("corr:Q",
                                     scale=alt.Scale(scheme="redblue",
                                                      domain=[-1, 1]),
                                     title="Correlation"),
                    tooltip=["row", "col", "corr"])
                labels_cm = alt.Chart(corr).mark_text(fontSize=9,
                                                        color=INK).encode(
                    x="col:N", y="row:N",
                    text=alt.Text("corr:Q", format=".2f"))
                st.altair_chart((cm + labels_cm).properties(height=440),
                                width='stretch')

                st.markdown('<h3 style="margin-top:2rem">Trend decomposition</h3>',
                            unsafe_allow_html=True)
                st.caption("Loess smoother separates the underlying trajectory "
                           "from weekly noise. If the smooth line trends up, "
                           "the campaign is genuinely improving.")
                e_num = e.copy()
                e_num["week_num"] = (e_num["week_start"] -
                                        e_num["week_start"].min()).dt.days
                _pts = alt.Chart(e_num.dropna(subset=["open_rate"])).mark_circle(
                    color=MUTED, size=50, opacity=0.7).encode(
                    x=alt.X("week_start:T", title=None),
                    y=alt.Y("open_rate:Q", title="Open rate",
                            axis=alt.Axis(format=".0%")))
                _sm = alt.Chart(e_num.dropna(subset=["open_rate"])).transform_loess(
                    "week_num", "open_rate", bandwidth=0.5
                ).mark_line(color=ACCENT, strokeWidth=3).encode(
                    x=alt.X("week_num:Q", title=None,
                            axis=alt.Axis(labels=False, ticks=False)),
                    y="open_rate:Q")
                st.altair_chart((_pts + _sm).resolve_scale(
                    x="independent").properties(height=260),
                                 width='stretch')

        # ================== INTEREST & ENGAGEMENT ==================
        # Rows 10-12 of the source sheet: Replies (numeric), Most interested
        # companies from Cognism (free text list of universities), Newsletter
        # subscribers (numeric in later weeks, qualitative notes earlier).
        # These are the closest thing we have to a pipeline signal from email.
        if not emails_df.empty and {"interested_companies_count",
                                      "newsletter_subs", "replies"}.issubset(
                emails_df.columns):
            st.markdown('<div style="margin:3rem 0 0;border-top:1px solid '
                        + LINE + '"></div>', unsafe_allow_html=True)
            st.markdown('<h2>Interest &amp; engagement</h2>',
                          unsafe_allow_html=True)
            st.caption("Beyond opens and clicks: replies, universities "
                       "flagged as 'most interested' by Cognism, and "
                       "newsletter subscribers per week.")

            total_replies = int(emails_df["replies"].fillna(0).sum())
            total_interest = int(
                emails_df["interested_companies_count"].fillna(0).sum())
            n_interest_weeks = int(
                (emails_df["interested_companies_count"].fillna(0) > 0).sum())
            total_subs = int(emails_df["newsletter_subs"].fillna(0).sum())
            n_sub_weeks = int(emails_df["newsletter_subs"].notna().sum())

            it1, it2, it3, it4 = st.columns(4)
            with it1:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">Replies</div>'
                    f'<div class="kpi-value">{total_replies}</div>'
                    f'<div class="kpi-sub">across the window</div></div>',
                    unsafe_allow_html=True)
            with it2:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Interested universities</div>'
                    f'<div class="kpi-value" style="color:{ACCENT}">'
                    f'{total_interest}</div>'
                    f'<div class="kpi-sub">mentions in {n_interest_weeks} '
                    f'weeks</div></div>', unsafe_allow_html=True)
            with it3:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Newsletter subscribers</div>'
                    f'<div class="kpi-value">{total_subs}</div>'
                    f'<div class="kpi-sub">tracked in {n_sub_weeks} weeks'
                    f'</div></div>', unsafe_allow_html=True)
            with it4:
                _avg_int = (total_interest / max(n_interest_weeks, 1)) \
                    if n_interest_weeks else 0
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Avg interested / active week</div>'
                    f'<div class="kpi-value">{_avg_int:.1f}</div>'
                    f'<div class="kpi-sub">universities per week</div></div>',
                    unsafe_allow_html=True)

            # ---- Interested-companies per week (bar) ----
            _int_df = emails_df.dropna(subset=["week_start"]).copy()
            _int_df["interested_companies_count"] = \
                _int_df["interested_companies_count"].fillna(0).astype(int)
            _int_df = _int_df[_int_df["interested_companies_count"] > 0]
            if not _int_df.empty:
                st.markdown('<div class="eyebrow" '
                            'style="margin-top:1.5rem">Interested '
                            'universities per week</div>',
                            unsafe_allow_html=True)
                int_bar = alt.Chart(_int_df).mark_bar(
                    color=ACCENT, size=14).encode(
                    x=alt.X("week_start:T", title=None),
                    y=alt.Y("interested_companies_count:Q",
                            title="Universities flagged"),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("interested_companies_count:Q",
                                     title="Count"),
                        alt.Tooltip("interested_companies_raw:N",
                                     title="Names"),
                    ],
                ).properties(height=220)
                st.altair_chart(int_bar, width='stretch')

            # ---- Top interested universities across the window ----
            all_names = []
            for s in emails_df["interested_companies_raw"].dropna().astype(str):
                s = s.strip()
                if not s:
                    continue
                for n in s.split(";"):
                    n = n.strip()
                    if n:
                        all_names.append(n)
            if all_names:
                from collections import Counter as _Counter
                _counts = _Counter(all_names)
                _top = _counts.most_common(15)
                _top_df = pd.DataFrame(_top, columns=["University",
                                                        "Mentions"])
                cA, cB = st.columns([1.2, 1])
                with cA:
                    st.markdown('<div class="eyebrow" '
                                'style="margin-top:1.5rem">Top interested '
                                'universities</div>',
                                unsafe_allow_html=True)
                    st.dataframe(_top_df, width='stretch',
                                  hide_index=True)
                with cB:
                    st.markdown('<div class="eyebrow" '
                                'style="margin-top:1.5rem">Summary</div>',
                                unsafe_allow_html=True)
                    _distinct = len(_counts)
                    _repeats = sum(1 for _, c in _counts.items() if c > 1)
                    st.markdown(
                        f'<div class="card" style="padding:1rem 1.2rem">'
                        f'<div><strong>{_distinct}</strong> distinct '
                        f'universities showed interest.</div>'
                        f'<div style="margin-top:.5rem"><strong>{_repeats}'
                        f'</strong> appeared in more than one week - warm '
                        f'leads to prioritise.</div>'
                        f'<div style="margin-top:.5rem;color:{MUTED};'
                        f'font-size:.85rem">Repeat mentions are the '
                        f'strongest intent signal in this dataset.</div>'
                        f'</div>', unsafe_allow_html=True)

            # ---- Newsletter subs per week (line, only where numeric) ----
            _sub_df = emails_df.dropna(
                subset=["week_start", "newsletter_subs"]).copy()
            if not _sub_df.empty:
                st.markdown('<div class="eyebrow" '
                            'style="margin-top:1.5rem">Newsletter '
                            'subscribers per week</div>',
                            unsafe_allow_html=True)
                sub_chart = alt.Chart(_sub_df).mark_line(
                    color=GOLD, strokeWidth=3, point=alt.OverlayMarkDef(
                        color=GOLD, size=60)).encode(
                    x=alt.X("week_start:T", title=None),
                    y=alt.Y("newsletter_subs:Q", title="Subscribers"),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="Week"),
                        alt.Tooltip("newsletter_subs:Q", title="Subs"),
                    ],
                ).properties(height=220)
                st.altair_chart(sub_chart, width='stretch')

            # ---- Qualitative notes (from row 12 free text) ----
            _notes_df = emails_df[emails_df["newsletter_note"].astype(str)
                                    .str.strip().replace("nan", "").ne("")]
            _notes_df = _notes_df[[
                "week_label", "newsletter_note"]].copy()
            if not _notes_df.empty:
                with st.expander(f"Qualitative notes ({len(_notes_df)} weeks)",
                                   expanded=False):
                    for _, r in _notes_df.iterrows():
                        st.markdown(
                            f'<div style="border-left:3px solid {ACCENT};'
                            f'padding:.5rem .8rem;margin:.5rem 0;'
                            f'background:#faf7f0;border-radius:4px">'
                            f'<strong>{r["week_label"]}</strong><br>'
                            f'{r["newsletter_note"]}</div>',
                            unsafe_allow_html=True)


    if st.session_state.get("email_screen", "Performance") == "Audience":
        # ================== AUDIENCE + NEXT SEND BUILDER ==================
        st.markdown('<div style="margin:3rem 0 0;border-top:1px solid ' + LINE
                     + '"></div>', unsafe_allow_html=True)
        st.markdown('<h2>Audience</h2>', unsafe_allow_html=True)
        st.caption("From the cleaned UK masterlist. This is what you can send "
                   "to right now, split by readiness and freshness.")

        contacts_df = load_csv("contacts.csv")
        if contacts_df.empty:
            st.info("No contacts data. Run `python etl/contacts_etl.py` to build "
                    "data/contacts.csv.")
        else:
            # Coerce derived flags in case the CSV round-trip made them strings
            for _bcol in ("is_send_ready", "is_fresh", "is_verified"):
                if _bcol in contacts_df.columns:
                    contacts_df[_bcol] = (
                        contacts_df[_bcol].astype(str).str.lower()
                        .isin(["true", "1", "yes"]))

            total_c = len(contacts_df)
            send_ready = int(contacts_df["is_send_ready"].sum())
            needs_verify = int(
                contacts_df["send_status"].astype(str).str.startswith("2").sum())
            needs_segment = int(
                contacts_df["send_status"].astype(str).str.startswith("3").sum())
            fresh = int(contacts_df["is_fresh"].sum())
            already = total_c - fresh
            actionable = int(
                (contacts_df["is_send_ready"] & contacts_df["is_fresh"]
                 & contacts_df["is_verified"]).sum())

            at1, at2, at3, at4, at5 = st.columns(5)
            with at1:
                st.markdown(f'<div class="kpi"><div class="kpi-label">'
                            f'Send ready</div><div class="kpi-value">{send_ready:,}'
                            f'</div></div>', unsafe_allow_html=True)
            with at2:
                st.markdown(f'<div class="kpi"><div class="kpi-label">'
                            f'Needs verify</div><div class="kpi-value">'
                            f'{needs_verify:,}</div></div>',
                            unsafe_allow_html=True)
            with at3:
                st.markdown(f'<div class="kpi"><div class="kpi-label">'
                            f'Needs segment</div><div class="kpi-value">'
                            f'{needs_segment:,}</div></div>',
                            unsafe_allow_html=True)
            with at4:
                st.markdown(f'<div class="kpi"><div class="kpi-label">'
                            f'Fresh</div><div class="kpi-value">{fresh:,}'
                            f'</div><div class="kpi-sub">of {total_c:,} '
                            f'total</div></div>', unsafe_allow_html=True)
            with at5:
                st.markdown(f'<div class="kpi"><div class="kpi-label">'
                            f'Actionable now</div><div class="kpi-value" '
                            f'style="color:{ACCENT}">{actionable:,}</div>'
                            f'<div class="kpi-sub">send-ready + fresh + '
                            f'verified</div></div>', unsafe_allow_html=True)

            st.caption(f"Already approached: {already:,}. "
                       f"Actionable pool ({actionable:,}) is what a fresh "
                       "campaign can draw from without re-hitting anyone.")

            # ---------- Next Send Builder ----------
            st.markdown('<div style="margin:2.5rem 0 0;border-top:1px solid '
                        + LINE + '"></div>', unsafe_allow_html=True)
            st.markdown('<h3>Next send builder</h3>', unsafe_allow_html=True)
            st.caption("Pick who to email next. The builder samples across "
                       "institutions so no single university dominates the "
                       "batch. Download the CSV to hand to the ESP.")

            nsb1, nsb2, nsb3 = st.columns([1.2, 1.2, 1])
            with nsb1:
                personas = sorted([p for p in contacts_df["persona_final"]
                                   .dropna().unique().tolist()
                                   if p != "Unclassified"])
                picked_personas = st.multiselect(
                    "Personas",
                    options=personas,
                    default=["Research"] if "Research" in personas else personas[:1],
                    key="nsb_personas")
            with nsb2:
                tiers = sorted(contacts_df["seniority_tier"].dropna().unique().tolist())
                default_tiers = [t for t in tiers if t.startswith(("T1", "T2", "T3"))]
                picked_tiers = st.multiselect(
                    "Seniority tiers",
                    options=tiers,
                    default=default_tiers,
                    key="nsb_tiers")
            with nsb3:
                bands = sorted(contacts_df["institution_band"].dropna().unique().tolist())
                picked_bands = st.multiselect(
                    "Institution bands",
                    options=bands,
                    default=bands,
                    key="nsb_bands")

            nsb4, nsb5, nsb6 = st.columns(3)
            with nsb4:
                exclude_approached = st.toggle(
                    "Exclude already approached", value=True,
                    key="nsb_exclude_approached")
            with nsb5:
                exclude_unverified = st.toggle(
                    "Verified only", value=True, key="nsb_exclude_unverified")
            with nsb6:
                require_send_ready = st.toggle(
                    "Send ready only", value=True, key="nsb_require_ready")

            # Apply filters
            pool = contacts_df.copy()
            if picked_personas:
                pool = pool[pool["persona_final"].isin(picked_personas)]
            if picked_tiers:
                pool = pool[pool["seniority_tier"].isin(picked_tiers)]
            if picked_bands:
                pool = pool[pool["institution_band"].isin(picked_bands)]
            if exclude_approached:
                pool = pool[pool["is_fresh"]]
            if exclude_unverified:
                pool = pool[pool["is_verified"]]
            if require_send_ready:
                pool = pool[pool["is_send_ready"]]

            pool_size = len(pool)
            if pool_size == 0:
                st.warning("No contacts match those filters. Loosen a filter "
                           "to see the pool.")
            else:
                max_batch = min(pool_size, 1000)
                default_batch = min(200, max_batch)
                batch_size = st.slider(
                    f"Batch size (pool: {pool_size:,} contacts)",
                    min_value=10, max_value=max_batch,
                    value=default_batch, step=10, key="nsb_batch_size")

                # Stratified sample: equal share per institution among top slots,
                # then remainder random from what is left.
                def _stratified_sample(df, n, strat_col="institution",
                                        seed=42):
                    if len(df) <= n:
                        return df.copy()
                    rng = df.sample(frac=1, random_state=seed).reset_index(drop=True)
                    counts = rng[strat_col].value_counts()
                    per_inst = max(1, n // max(len(counts), 1))
                    picked_rows = []
                    for inst, _cnt in counts.items():
                        sub = rng[rng[strat_col] == inst].head(per_inst)
                        picked_rows.append(sub)
                        if sum(len(x) for x in picked_rows) >= n:
                            break
                    picked = pd.concat(picked_rows).head(n)
                    if len(picked) < n:
                        remaining = rng.drop(picked.index)
                        picked = pd.concat(
                            [picked, remaining.head(n - len(picked))])
                    return picked.head(n)

                batch = _stratified_sample(pool, batch_size)

                # Composition summary
                comp_persona = batch["persona_final"].value_counts()
                comp_tier = batch["seniority_tier"].value_counts()
                n_inst = batch["institution"].nunique()
                top_inst = batch["institution"].value_counts().head(3)

                cs1, cs2, cs3 = st.columns(3)
                with cs1:
                    st.markdown(f'<div class="kpi"><div class="kpi-label">'
                                f'Batch size</div><div class="kpi-value">'
                                f'{len(batch):,}</div></div>',
                                unsafe_allow_html=True)
                with cs2:
                    st.markdown(f'<div class="kpi"><div class="kpi-label">'
                                f'Institutions</div><div class="kpi-value">'
                                f'{n_inst:,}</div>'
                                f'<div class="kpi-sub">across the batch</div>'
                                f'</div>', unsafe_allow_html=True)
                with cs3:
                    top_share = int(top_inst.iloc[0]) if len(top_inst) else 0
                    top_pct = (top_share / max(len(batch), 1)) * 100
                    st.markdown(f'<div class="kpi"><div class="kpi-label">'
                                f'Top institution share</div>'
                                f'<div class="kpi-value">{top_pct:.0f}%</div>'
                                f'<div class="kpi-sub">'
                                f'{top_inst.index[0] if len(top_inst) else "-"}'
                                f'</div></div>', unsafe_allow_html=True)

                # ---------- Expected open rate band (from history) ----------
                def _wilson_local(k, n, z=1.96):
                    if not n or pd.isna(k) or pd.isna(n) or n == 0:
                        return (float("nan"), float("nan"))
                    p = k / n
                    denom = 1 + z * z / n
                    centre = (p + z * z / (2 * n)) / denom
                    spread = (z / denom) * ((p * (1 - p) / n
                                              + z * z / (4 * n * n)) ** 0.5)
                    return max(0.0, centre - spread), min(1.0, centre + spread)

                hist = emails_all.dropna(subset=["contacts", "delivered",
                                                  "opened"]).copy()
                hist = hist[hist["delivered"] > 0]
                band_lo = band_hi = band_mid = float("nan")
                bucket_label = "no history match"
                n_weeks_bucket = 0
                if len(hist) >= 4:
                    # Bucket historical weeks into quartiles by contacts sent
                    try:
                        hist["_bucket"] = pd.qcut(hist["contacts"], q=4,
                                                    duplicates="drop")
                        # Find which quartile the current batch size falls into
                        match = hist[hist["contacts"].apply(
                            lambda c: c >= batch_size * 0.5
                            and c <= batch_size * 2.0)]
                        if len(match) < 3:
                            # Fall back to closest quartile by median contacts
                            medians = hist.groupby("_bucket", observed=True)[
                                "contacts"].median()
                            closest = (medians - batch_size).abs().idxmin()
                            match = hist[hist["_bucket"] == closest]
                            bucket_label = (f"weeks with ~{int(medians[closest])} "
                                            f"contacts (nearest bucket)")
                        else:
                            bucket_label = (f"weeks with {int(batch_size*0.5)}"
                                            f"-{int(batch_size*2.0)} contacts")
                        n_weeks_bucket = len(match)
                        if n_weeks_bucket >= 1:
                            k = float(match["opened"].sum())
                            n = float(match["delivered"].sum())
                            if n > 0:
                                band_mid = k / n
                                band_lo, band_hi = _wilson_local(k, n)
                    except Exception:
                        pass

                eb1, eb2 = st.columns([1.3, 1])
                with eb1:
                    if pd.notna(band_mid):
                        st.markdown(
                            f'<div class="kpi"><div class="kpi-label">'
                            f'Expected open rate (95% band)</div>'
                            f'<div class="kpi-value" style="color:{ACCENT}">'
                            f'{band_lo*100:.1f}% - {band_hi*100:.1f}%</div>'
                            f'<div class="kpi-sub">point estimate '
                            f'{band_mid*100:.1f}%, from {n_weeks_bucket} '
                            f'{bucket_label}</div></div>',
                            unsafe_allow_html=True)
                    else:
                        st.info("Not enough matching history to estimate a "
                                 "band for this batch size.")
                with eb2:
                    if pd.notna(band_mid):
                        exp_lo = int(band_lo * len(batch))
                        exp_hi = int(band_hi * len(batch))
                        st.markdown(
                            f'<div class="kpi"><div class="kpi-label">'
                            f'Expected opens</div><div class="kpi-value">'
                            f'{exp_lo} - {exp_hi}</div>'
                            f'<div class="kpi-sub">on this {len(batch)}-contact '
                            f'batch</div></div>',
                            unsafe_allow_html=True)

                reason_lines = []
                if len(picked_personas) == 1:
                    reason_lines.append(
                        f"Focused on {picked_personas[0]} to keep messaging "
                        f"vocabulary consistent across the send.")
                elif len(picked_personas) > 1:
                    reason_lines.append(
                        f"Mixed personas ({', '.join(picked_personas)}) - "
                        f"consider splitting into per-persona sends for cleaner "
                        f"open-rate signal.")
                if exclude_approached:
                    reason_lines.append(
                        "Fresh contacts only, so we do not re-hit anyone in "
                        "the already-approached list.")
                if exclude_unverified:
                    reason_lines.append(
                        "Verified deliverability only, which cuts the bounce "
                        "risk seen on unverified sends.")
                st.markdown('<div style="background:#faf7f0;border-left:3px '
                            'solid ' + ACCENT + ';padding:0.75rem 1rem;'
                            'margin:1rem 0;border-radius:4px">'
                            '<strong>Why this batch</strong><br>'
                            + '<br>'.join(reason_lines) + '</div>',
                            unsafe_allow_html=True)

                with st.expander("Preview batch (first 25 rows)"):
                    preview_cols = ["first_name", "last_name", "email_clean",
                                     "job_title", "institution", "persona_final",
                                     "seniority_tier"]
                    preview_cols = [c for c in preview_cols if c in batch.columns]
                    st.dataframe(batch[preview_cols].head(25),
                                  width='stretch', hide_index=True)

                export_cols = ["contact_id", "email_clean", "first_name",
                                "last_name", "job_title", "institution",
                                "persona_final", "seniority_tier",
                                "segment_key", "institution_band"]
                export_cols = [c for c in export_cols if c in batch.columns]
                csv_bytes = batch[export_cols].to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download batch CSV",
                    data=csv_bytes,
                    file_name=f"next_send_batch_{len(batch)}.csv",
                    mime="text/csv",
                    key="nsb_download")

        st.markdown('<div style="margin:3rem 0 0;border-top:1px solid ' + LINE
                     + '"></div>', unsafe_allow_html=True)
        st.markdown('<h2>Compose an email</h2>', unsafe_allow_html=True)

        # ================== 3. COMPOSE + ANALYSE (existing block) ==================
        # House SaaS vocabulary. Weakness -> stronger phrasing, and coverage
        # groups tracked by the analyser.
        SAAS_VOCAB = {
            "pain_points": [
                "lack of visibility", "no single source of truth",
                "disconnected systems", "fragmented workflows",
            ],
            "manual_work": [
                "time-consuming tasks", "repetitive administration",
                "duplicate data entry", "human error",
                "operational inefficiency",
            ],
            "outcomes": [
                "reduce risk", "increase efficiency", "increase productivity",
                "accurate forecasting", "reduced risk and error",
                "improve visibility",
            ],
        }
        WEAK_SWAPS = {
            "many businesses": "leaders",
            "a lot of": "several",
            "in order to": "to",
            "utilise": "use",
            "utilize": "use",
            "in the process of": "while",
            "leverage": "use",
            "synergy": "alignment",
            "at the end of the day": "the point is",
            "streamline": "simplify",
            "solution": "platform",
        }

        def _analyse_email(subject, body):
            text = f"{subject}\n{body}"
            lower = text.lower()
            # coverage per group
            coverage = {}
            for group, phrases in SAAS_VOCAB.items():
                hits = [p for p in phrases if p in lower]
                coverage[group] = {"hits": hits, "count": len(hits),
                                    "total": len(phrases)}
            # weak phrases
            weak_hits = [(w, s) for w, s in WEAK_SWAPS.items() if w in lower]
            # readability rough
            import re
            words = re.findall(r"[a-zA-Z]+", body)
            sents = re.split(r"[.!?]+", body)
            sents = [s.strip() for s in sents if s.strip()]
            avg_sent = (len(words) / len(sents)) if sents else 0
            # Flesch-Kincaid rough
            syl = 0
            for w in words:
                groups = re.findall(r"[aeiouy]+", w.lower())
                syl += max(1, len(groups))
            fk = None
            if words and sents:
                fk = round(
                    0.39 * (len(words) / len(sents))
                    + 11.8 * (syl / len(words)) - 15.59, 1)
            # seven-slot presence heuristic
            slots = {
                "subject": bool(subject.strip()),
                "stakeholder line": any(k in lower for k in
                                         ["board", "cfo", "finance leader",
                                          "leader", "team", "executive"]),
                "problem-cost pair": lower.count(":") >= 1
                                        or lower.count(" - ") >= 2,
                "product line": any(k in lower for k in
                                     ["grantsnow", "our platform",
                                      "the platform"]),
                "named proof": any(k in lower for k in
                                    ["university of", "college of",
                                     "institute", "customer",
                                     "case study"]),
                "outcome close": any(g in lower for g in
                                      SAAS_VOCAB["outcomes"]),
                "single cta": lower.count("book a call") + lower.count(
                                    "get in touch") + lower.count(
                                    "read the whitepaper") + lower.count(
                                    "download") + lower.count("register")
                                    == 1,
            }
            return {
                "words": len(words),
                "sentences": len(sents),
                "avg_sentence_words": round(avg_sent, 1),
                "fk_grade": fk,
                "coverage": coverage,
                "weak_hits": weak_hits,
                "slots": slots,
            }

        # ------ header ------
        st.markdown('<h2>Email Matrix</h2>', unsafe_allow_html=True)
        st.caption("Draft a result-driven promotional email using the house "
                   "seven-slot pattern. The analyser scores readability, "
                   "checks the SaaS vocabulary coverage, and flags weak "
                   "phrases as you type.")

        # ------ 1. the pattern reference ------
        with st.expander("The seven-slot house pattern (reference)",
                         expanded=False):
            st.markdown("""
    | Slot | What it holds |
    |---|---|
    | **1. Pain-named subject** | Names the pain in the first four words. Not the product. |
    | **2. Stakeholder demand line** | One line naming who is asking for this. Finance leader, board, research director. |
    | **3. Three problem-to-cost pairs** | Each pair names one problem and the cost of ignoring it. Not features. |
    | **4. One-sentence product line** | What the product is, in one line. Not a paragraph. |
    | **5. Named proof before numbers** | Named customer or institution before any percentage. Trust before claim. |
    | **6. Outcome close in buyer language** | Close in the buyer's own words. Reduced risk. Accurate forecasting. |
    | **7. Single CTA** | One action. Not three. Book a call. Read the whitepaper. Register. |
    """)

        # ------ 2. compose form ------
        ecol1, ecol2 = st.columns([3, 2], gap="large")
        with ecol1:
            st.markdown('<div class="eyebrow">Subject</div>',
                        unsafe_allow_html=True)
            email_subject = st.text_input(
                " ", key="email_subject",
                placeholder="Pain-named subject line...",
                label_visibility="collapsed")

            st.markdown('<div class="eyebrow" style="margin-top:1rem">Body</div>',
                        unsafe_allow_html=True)
            email_body = st.text_area(
                " ", height=340, key="email_body",
                placeholder=(
                    "1. Stakeholder demand line\n\n"
                    "2. Problem - cost pair one\n"
                    "   Problem - cost pair two\n"
                    "   Problem - cost pair three\n\n"
                    "3. One sentence on GrantsNow\n\n"
                    "4. Named proof followed by the number\n\n"
                    "5. Outcome close in buyer language\n\n"
                    "6. Single CTA"),
                label_visibility="collapsed")

        with ecol2:
            st.markdown('<div class="eyebrow">Coverage</div>',
                        unsafe_allow_html=True)
            st.caption("Live counts of the house vocabulary in your draft. "
                       "Aim for at least two hits per group before shipping.")

            result = _analyse_email(email_subject or "", email_body or "")

            # coverage tiles
            for group, label in [
                ("pain_points", "Pain-point language"),
                ("manual_work", "Manual-work language"),
                ("outcomes", "Business-outcome language"),
            ]:
                c = result["coverage"][group]
                score_col = ACCENT if c["count"] >= 2 else (
                    WARN if c["count"] == 0 else MUTED)
                st.markdown(
                    f'<div class="card" style="padding:.7rem .9rem;'
                    f'margin-bottom:.5rem">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:baseline">'
                    f'<div class="k" style="font-size:.72rem;letter-spacing:.14em;'
                    f'text-transform:uppercase;color:{MUTED};font-weight:600">'
                    f'{label}</div>'
                    f'<div style="font-family:Georgia,serif;font-size:1.3rem;'
                    f'font-weight:700;color:{score_col};line-height:1">'
                    f'{c["count"]} / {c["total"]}</div></div>'
                    f'<div style="font-size:.78rem;color:{INK_SOFT};'
                    f'margin-top:.35rem">'
                    + (", ".join(c["hits"]) if c["hits"] else "no matches yet")
                    + f'</div></div>', unsafe_allow_html=True)

            # readability tile
            fk = result["fk_grade"]
            fk_label = (f"Grade {fk}" if fk is not None
                        else "-")
            fk_col = ACCENT if fk and 6 <= fk <= 10 else (
                WARN if fk and fk > 13 else MUTED)
            st.markdown(
                f'<div class="card" style="padding:.7rem .9rem;'
                f'margin-bottom:.5rem">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:baseline">'
                f'<div class="k" style="font-size:.72rem;letter-spacing:.14em;'
                f'text-transform:uppercase;color:{MUTED};font-weight:600">'
                f'Readability (Flesch-Kincaid)</div>'
                f'<div style="font-family:Georgia,serif;font-size:1.3rem;'
                f'font-weight:700;color:{fk_col};line-height:1">'
                f'{fk_label}</div></div>'
                f'<div style="font-size:.78rem;color:{INK_SOFT};'
                f'margin-top:.35rem">'
                f'{result["words"]} words &middot; '
                f'{result["sentences"]} sentences &middot; '
                f'avg sentence {result["avg_sentence_words"]} words</div>'
                f'</div>', unsafe_allow_html=True)

        # ------ 3. slot checklist ------
        st.markdown('<h3 style="margin-top:2rem">Seven-slot checklist</h3>',
                    unsafe_allow_html=True)
        st.caption("Which slots does the current draft appear to cover. "
                   "Heuristic, not gospel. Missing marks call for a manual "
                   "check.")
        slots = result["slots"]
        cols = st.columns(7)
        slot_labels = [
            ("subject", "Subject"), ("stakeholder line", "Stakeholder"),
            ("problem-cost pair", "Problem-cost"),
            ("product line", "Product line"),
            ("named proof", "Named proof"),
            ("outcome close", "Outcome close"),
            ("single cta", "Single CTA"),
        ]
        for col, (key, label) in zip(cols, slot_labels):
            ok = slots.get(key, False)
            icon = "&#10003;" if ok else "&#8226;"
            colour = ACCENT if ok else MUTED
            with col:
                st.markdown(
                    f'<div style="text-align:center;padding:.5rem 0">'
                    f'<div style="font-size:1.5rem;color:{colour};'
                    f'font-weight:700;line-height:1">{icon}</div>'
                    f'<div style="font-size:.72rem;color:{MUTED};'
                    f'letter-spacing:.1em;text-transform:uppercase;'
                    f'margin-top:.3rem">{label}</div></div>',
                    unsafe_allow_html=True)

        # ------ 4. weak phrase flags ------
        if result["weak_hits"]:
            st.markdown('<h3 style="margin-top:2rem">Weak phrases to swap</h3>',
                        unsafe_allow_html=True)
            st.caption("House rule flags. Each row shows the weak phrase found "
                       "and the recommended replacement.")
            for weak, strong in result["weak_hits"]:
                st.markdown(
                    f'<div class="card" style="padding:.7rem 1rem;'
                    f'margin-bottom:.4rem">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'gap:1rem;align-items:center">'
                    f'<div style="color:{WARN};text-decoration:line-through">'
                    f'{weak}</div>'
                    f'<div style="color:{MUTED}">&rarr;</div>'
                    f'<div style="color:{ACCENT};font-weight:600">{strong}</div>'
                    f'</div></div>', unsafe_allow_html=True)

        # ------ 5. copy the email ------
        st.markdown('<h3 style="margin-top:2rem">Copy the email</h3>',
                    unsafe_allow_html=True)
        email_full = (f"Subject: {email_subject}\n\n{email_body}"
                       if email_subject or email_body
                       else "Draft the email above first.")
        with st.expander("Show plain-text version", expanded=False):
            st.code(email_full, language="text")
            st.download_button("Download as text",
                                email_full.encode("utf-8"),
                                file_name="email_draft.txt",
                                mime="text/plain")

        st.markdown(
            f'<div style="color:{MUTED};font-size:.75rem;'
            f'margin-top:2.5rem;text-align:center">'
            f'The Email Matrix does not yet score against real email '
            f'performance data. Once a mailer export is available, the same '
            f'scoring engine used for LinkedIn posts will apply here.</div>',
            unsafe_allow_html=True)


    if st.session_state.get("email_screen", "Performance") == "Contents analysis":
        # =============== CONTENTS ANALYSIS ===============
        # Reads the Email Campaign sheet (parsed by campaign_etl.py) and
        # scores every base email + follow-up on the house pattern axes:
        # SaaS vocabulary coverage, weak-phrase count, seven-slot alignment,
        # persona fit vs the dominant blast persona (Research), readability.
        st.markdown('<h2>Contents analysis</h2>', unsafe_allow_html=True)
        st.caption("Every live campaign from the Marketing Calendar, scored "
                   "against the house pattern. Pick a campaign to see the "
                   "detail; scroll for gaps and next-content ideas.")

        campaigns_df = load_csv("campaigns.csv")
        if campaigns_df.empty:
            st.info("No campaigns loaded. Run `python etl/campaign_etl.py` to "
                    "build data/campaigns.csv from the Marketing Calendar.")
        else:
            # ---- House vocabulary + rules (shared with Compose block) ----
            SAAS_VOCAB_CA = {
                "pain_points": [
                    "lack of visibility", "no single source of truth",
                    "disconnected systems", "fragmented workflows",
                    "manual tracking", "missed opportunit",
                ],
                "manual_work": [
                    "time-consuming", "repetitive administration",
                    "duplicate data entry", "human error",
                    "operational inefficiency", "manual workload",
                    "back track", "endless email",
                ],
                "outcomes": [
                    "reduce risk", "increase efficiency", "productivity",
                    "accurate forecasting", "reduce cost", "save time",
                    "improve visibility", "single view", "end to end",
                ],
            }
            WEAK_SWAPS_CA = {
                "utilise": "use", "utilize": "use",
                "leverage": "use", "streamline": "simplify",
                "solution": "platform", "synergy": "alignment",
                "in order to": "to", "at the end of the day": "the point is",
                "a lot of": "several",
            }
            RESEARCH_TERMS = [
                "research", "grant", "grants", "funding", "arma", "ncura",
                "ukri", "horizon", "ref", "principal investigator", "pi",
                "pre-award", "post-award", "co-investigator", "proposal",
                "university", "college", "institution",
            ]
            FINANCE_TERMS = [
                "erp", "finance", "reconcile", "reporting", "audit",
                "compliance", "cost", "budget", "forecast",
            ]
            IT_TERMS = [
                "integration", "api", "system", "systems", "sso",
                "single source", "data", "platform",
            ]

            # ---- House pattern per Email_WP5 reference ----
            # Challenge signals (what pain the reader has, who wants what,
            # problem-cost chain). Result signals (named customers by name,
            # concrete numbers, single CTA after an outcome close line).
            CHALLENGE_SUBJECT_WORDS = [
                "overcoming", "manual", "delay", "delays", "hidden", "lost",
                "missed", "missing", "risk", "gap", "disconnect", "backlog",
                "burden", "reduce", "cut", "stop", "why", "how", "when",
                "without", "beyond", "fixing", "smart", "smarter",
                "capturing more", "more funding", "one system",
            ]
            STAKEHOLDER_TERMS = [
                "leadership", "funder", "funders", "government",
                "board", "vice chancellor", "director of research",
                "principal investigator", "regulators", "auditor",
                "auditors", "research office",
            ]
            DEMAND_VERBS = ["want", "need", "expect", "require", "ask for",
                              "demand"]
            PROBLEM_CONNECTIVES = [" because ", ", so ", " while ",
                                     " but ", " however ", " which means ",
                                     " so that "]
            OUTCOME_TERMS = [
                "single source of truth", "one platform", "one place",
                "one system", "single view", "end to end", "visibility",
                "accurate forecasting", "less risk", "reduce risk",
                "reduce cost", "reduce administration", "save time",
            ]
            CTA_PHRASES = [
                "read the whitepaper", "read the white paper",
                "download the whitepaper", "book a call", "book a demo",
                "get in touch", "reply to this email", "register",
                "come by our", "meet our team", "learn more",
            ]

            def _analyse(subject, body):
                text = f"{subject}\n{body}"
                lo = text.lower()
                subj_lo = subject.lower()

                # ---- Vocabulary + weak phrases (shared) ----
                vocab = {}
                for g, terms in SAAS_VOCAB_CA.items():
                    hits = [t for t in terms if t in lo]
                    vocab[g] = {"hits": hits, "count": len(hits),
                                 "total": len(terms)}
                weak = [(w, s) for w, s in WEAK_SWAPS_CA.items() if w in lo]

                # ---- Words / sentences / readability ----
                words = re.findall(r"[a-zA-Z]+", body)
                sents = [s for s in re.split(r"[.!?]+", body) if s.strip()]
                syl = 0
                for w in words:
                    syl += max(1, len(re.findall(r"[aeiouy]+", w.lower())))
                fk = None
                if words and sents:
                    fk = round(0.39 * (len(words) / len(sents))
                                + 11.8 * (syl / len(words)) - 15.59, 1)

                # ---- Persona fit ----
                total_words = max(len(words), 1)
                persona_fit = {
                    "Research":
                        sum(lo.count(t) for t in RESEARCH_TERMS) / total_words,
                    "Finance":
                        sum(lo.count(t) for t in FINANCE_TERMS) / total_words,
                    "IT-Systems":
                        sum(lo.count(t) for t in IT_TERMS) / total_words,
                }

                # ---- CHALLENGE signals (slots 1, 3, 4) ----
                # Slot 1: pain-named subject (not product-named)
                subj_has_challenge = any(w in subj_lo
                                            for w in CHALLENGE_SUBJECT_WORDS)
                subj_is_product_only = (subj_lo.strip().startswith("visit ")
                    or subj_lo.strip() in ("grantsnow", "about grantsnow"))
                slot_pain_subject = (bool(subject.strip())
                                        and subj_has_challenge
                                        and not subj_is_product_only)
                # Slot 3: stakeholder-demand line
                has_stakeholder = any(t in lo for t in STAKEHOLDER_TERMS)
                has_demand_verb = any(v in lo for v in DEMAND_VERBS)
                slot_stakeholder = has_stakeholder and has_demand_verb
                # Slot 4: problem-cost chain (2+ connectives OR 3+ sentences
                # that read as problem descriptions in first half of body)
                connective_hits = sum(lo.count(c)
                                        for c in PROBLEM_CONNECTIVES)
                slot_problem_chain = connective_hits >= 2

                # ---- RESULT signals (slots 5, 6, 7) ----
                # Slot 5: named specific customer institutions
                named_customers = re.findall(
                    r"(University of [A-Z][A-Za-z ]+|"
                    r"Institute of [A-Z][A-Za-z ]+|"
                    r"[A-Z][A-Za-z]+ (?:College|University|Institute)"
                    r"(?: of [A-Z][A-Za-z ]+)?)",
                    body)
                # dedupe
                named_customers = list(dict.fromkeys(
                    [n.strip() for n in named_customers]))
                slot_named_proof = len(named_customers) >= 1
                # Slot 6: concrete numeric result (percentage or Nx factor)
                pct_hits = re.findall(r"\b\d{1,3}\s*%", body)
                slot_numbers = len(pct_hits) >= 1
                # Slot 7: single CTA - at least one recognised call-to-action
                cta_hits = [c for c in CTA_PHRASES if c in lo]
                slot_single_cta = len(cta_hits) >= 1

                # Slot 2: personal greeting (hygiene)
                slot_greeting = bool(re.match(
                    r"^\s*(hi|hello|dear|good (morning|afternoon))",
                    body, flags=re.IGNORECASE))

                slots = {
                    "1. Pain-named subject": slot_pain_subject,
                    "2. Personal greeting": slot_greeting,
                    "3. Stakeholder-demand line": slot_stakeholder,
                    "4. Problem-cost chain": slot_problem_chain,
                    "5. Named customer proof": slot_named_proof,
                    "6. Concrete numbers": slot_numbers,
                    "7. Single CTA": slot_single_cta,
                }
                # Sub-scores that map to the drafter's mental model
                challenge_bits = [slot_pain_subject, slot_stakeholder,
                                    slot_problem_chain]
                result_bits = [slot_named_proof, slot_numbers, slot_single_cta]
                challenge_score = int(100 * sum(challenge_bits)
                                        / len(challenge_bits))
                result_score = int(100 * sum(result_bits) / len(result_bits))
                slot_score = int(100 * sum(slots.values()) / len(slots))
                vocab_score = int(100 * sum(v["count"] for v in vocab.values())
                                    / sum(v["total"] for v in vocab.values()))
                # blended house score: half challenge, half result, minus
                # weak-phrase penalty; hygiene greeting acts as a small floor
                house_score = int(0.45 * challenge_score
                                    + 0.45 * result_score
                                    + (10 if slot_greeting else 0)
                                    - 4 * min(len(weak), 3))
                house_score = max(0, min(100, house_score))
                return {
                    "vocab": vocab, "weak": weak, "fk": fk,
                    "words": len(words), "sents": len(sents),
                    "persona_fit": persona_fit, "slots": slots,
                    "challenge_score": challenge_score,
                    "result_score": result_score,
                    "slot_score": slot_score, "vocab_score": vocab_score,
                    "house_score": house_score,
                    "named_customers": named_customers,
                    "pct_hits": pct_hits,
                    "cta_hits": cta_hits,
                    "connective_hits": connective_hits,
                }

            # ---- Content-type auto-classification ----
            def _content_type(name, body):
                s = f"{name} {body}".lower()
                if "arma" in s or "ncura" in s:
                    return "Event promotion"
                if "wp4" in name.lower() or "wp5" in name.lower() \
                        or "erp" in s or "reporting numbers" in s:
                    return "Product themed"
                if "funding" in s:
                    return "Funding opportunities"
                return "General promotion"

            # ---- Overview tiles ----
            n_camps = campaigns_df["campaign_name"].nunique()
            n_emails = len(campaigns_df)
            n_with_subject = int(campaigns_df["has_subject"].astype(str)
                                 .str.lower().isin(["true", "1"]).sum())
            avg_words = int(campaigns_df["word_count"].mean())

            co1, co2, co3, co4 = st.columns(4)
            with co1:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">Campaigns</div>'
                    f'<div class="kpi-value">{n_camps}</div></div>',
                    unsafe_allow_html=True)
            with co2:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">Emails total</div>'
                    f'<div class="kpi-value">{n_emails}</div>'
                    f'<div class="kpi-sub">base + follow-ups</div></div>',
                    unsafe_allow_html=True)
            with co3:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">With subject '
                    f'line</div><div class="kpi-value">{n_with_subject}'
                    f'</div><div class="kpi-sub">of {n_emails}</div></div>',
                    unsafe_allow_html=True)
            with co4:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">Avg length</div>'
                    f'<div class="kpi-value">{avg_words}</div>'
                    f'<div class="kpi-sub">words per email</div></div>',
                    unsafe_allow_html=True)

            # ---- Score every email upfront, tag with content type ----
            scored_rows = []
            for _, r in campaigns_df.iterrows():
                a = _analyse(str(r.get("subject", "") or ""),
                              str(r.get("body", "") or ""))
                scored_rows.append({
                    "campaign_id": r["campaign_id"],
                    "campaign_name": r["campaign_name"],
                    "stage": r["stage"],
                    "persona_raw": r.get("persona_raw", ""),
                    "subject": r.get("subject", ""),
                    "body": r.get("body", ""),
                    "content_type": _content_type(
                        str(r["campaign_name"]), str(r.get("body", "") or "")),
                    "words": a["words"],
                    "fk": a["fk"],
                    "vocab_score": a["vocab_score"],
                    "slot_score": a["slot_score"],
                    "challenge_score": a["challenge_score"],
                    "result_score": a["result_score"],
                    "weak_count": len(a["weak"]),
                    "house_score": a["house_score"],
                    "persona_dominant": max(a["persona_fit"],
                                              key=a["persona_fit"].get),
                    "persona_fit": a["persona_fit"],
                    "slots": a["slots"],
                    "vocab": a["vocab"],
                    "weak": a["weak"],
                    "named_customers": a["named_customers"],
                    "pct_hits": a["pct_hits"],
                    "cta_hits": a["cta_hits"],
                    "connective_hits": a["connective_hits"],
                })
            scored_df = pd.DataFrame(scored_rows)

            # ---- Inventory table ----
            st.markdown('<h3 style="margin-top:1.5rem">Campaign inventory'
                        '</h3>', unsafe_allow_html=True)
            st.caption("Scored against the Email_WP5 reference pattern. "
                       "Challenge = pain-named subject + stakeholder line + "
                       "problem-cost chain. Result = named customers + "
                       "concrete numbers + single CTA.")
            inv = scored_df[[
                "campaign_name", "stage", "content_type",
                "persona_dominant", "words", "house_score",
                "challenge_score", "result_score", "weak_count"]].copy()
            inv.columns = ["Campaign", "Stage", "Type", "Reads for",
                            "Words", "House", "Challenge", "Result",
                            "Weak"]
            st.dataframe(inv, width='stretch', hide_index=True)

            # ---- Content-type mix chart ----
            st.markdown('<h3 style="margin-top:2rem">Content-type mix</h3>',
                        unsafe_allow_html=True)
            mix = scored_df["content_type"].value_counts().reset_index()
            mix.columns = ["Content type", "Emails"]
            mix_chart = alt.Chart(mix).mark_bar(color=ACCENT, size=28).encode(
                x=alt.X("Emails:Q", title="Emails"),
                y=alt.Y("Content type:N", sort="-x", title=None),
                tooltip=["Content type:N", "Emails:Q"],
            ).properties(height=180)
            st.altair_chart(mix_chart, width='stretch')

            # =============== SCORE ANALYSIS ===============
            # Performance-graph analogue: distributions, rankings, coverage.
            # Same feel as the Performance screen so the drafter reads them
            # the same way - each dot / bar is one email.
            st.markdown('<div style="margin:2.5rem 0 0;border-top:1px '
                        'solid ' + LINE + '"></div>', unsafe_allow_html=True)
            st.markdown('<h3>Score analysis</h3>', unsafe_allow_html=True)

            # KPI strip: portfolio-level averages
            avg_ch = int(scored_df["challenge_score"].mean())
            avg_re = int(scored_df["result_score"].mean())
            avg_ho = int(scored_df["house_score"].mean())
            n_wp5_like = int(((scored_df["challenge_score"] >= 66)
                              & (scored_df["result_score"] >= 66)).sum())
            sa1, sa2, sa3, sa4 = st.columns(4)
            with sa1:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Avg challenge</div>'
                    f'<div class="kpi-value" style="color:{ACCENT}">'
                    f'{avg_ch}</div>'
                    f'<div class="kpi-sub">across {n_emails} emails</div>'
                    f'</div>', unsafe_allow_html=True)
            with sa2:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Avg result</div>'
                    f'<div class="kpi-value" style="color:{ACCENT}">'
                    f'{avg_re}</div>'
                    f'<div class="kpi-sub">across {n_emails} emails</div>'
                    f'</div>', unsafe_allow_html=True)
            with sa3:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Avg house</div>'
                    f'<div class="kpi-value">{avg_ho}</div>'
                    f'<div class="kpi-sub">blended</div></div>',
                    unsafe_allow_html=True)
            with sa4:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'WP5-like emails</div>'
                    f'<div class="kpi-value">{n_wp5_like}</div>'
                    f'<div class="kpi-sub">both scores &ge; 66</div>'
                    f'</div>', unsafe_allow_html=True)

            # ---- Challenge vs Result scatter ----
            st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                        'Challenge vs Result</div>',
                        unsafe_allow_html=True)
            st.caption("Top-right quadrant is the WP5 zone. Bottom-left "
                       "is the redraft pile. Colour = content type.")
            scatter_df = scored_df.copy()
            scatter_df["label"] = (scatter_df["campaign_name"].astype(str)
                                    + " · " + scatter_df["stage"].astype(str))
            # jitter to prevent identical-score dots overlapping
            _jitter = pd.util.hash_pandas_object(scatter_df["label"]) % 7 - 3
            scatter_df["c_jit"] = scatter_df["challenge_score"] + _jitter * 0.6
            scatter_df["r_jit"] = scatter_df["result_score"] + (_jitter * 0.6).values[::-1]
            base = alt.Chart(scatter_df).mark_circle(
                size=180, opacity=0.85, stroke="white", strokeWidth=1
            ).encode(
                x=alt.X("c_jit:Q", title="Challenge score",
                          scale=alt.Scale(domain=[-10, 110])),
                y=alt.Y("r_jit:Q", title="Result score",
                          scale=alt.Scale(domain=[-10, 110])),
                color=alt.Color("content_type:N",
                                  scale=alt.Scale(scheme="tableau10"),
                                  legend=alt.Legend(title="Content type")),
                tooltip=[
                    alt.Tooltip("label:N", title="Email"),
                    alt.Tooltip("challenge_score:Q", title="Challenge"),
                    alt.Tooltip("result_score:Q", title="Result"),
                    alt.Tooltip("house_score:Q", title="House"),
                ],
            )
            # WP5 target zone shading
            zone = alt.Chart(pd.DataFrame({
                "x1": [66], "x2": [110], "y1": [66], "y2": [110]
            })).mark_rect(color=ACCENT, opacity=0.08).encode(
                x="x1:Q", x2="x2:Q", y="y1:Q", y2="y2:Q")
            st.altair_chart((zone + base).properties(height=340),
                             width='stretch')

            # ---- House-score ranking ----
            st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                        'House-score ranking</div>',
                        unsafe_allow_html=True)
            rank_df = scored_df.copy()
            rank_df["label"] = (rank_df["campaign_name"].astype(str)
                                 + " · " + rank_df["stage"].astype(str))
            rank_df = rank_df.sort_values("house_score", ascending=False)
            rank_chart = alt.Chart(rank_df).mark_bar(size=14).encode(
                x=alt.X("house_score:Q", title="House score",
                          scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("label:N", sort="-x", title=None),
                color=alt.condition(
                    "datum.house_score >= 66",
                    alt.value(ACCENT), alt.value("#B8B8BE")),
                tooltip=[
                    alt.Tooltip("label:N", title="Email"),
                    alt.Tooltip("house_score:Q", title="House"),
                    alt.Tooltip("challenge_score:Q", title="Challenge"),
                    alt.Tooltip("result_score:Q", title="Result"),
                ],
            ).properties(height=max(220, 22 * len(rank_df)))
            st.altair_chart(rank_chart, width='stretch')

            # ---- Slot hit-rate ----
            st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                        'Slot hit-rate across all emails</div>',
                        unsafe_allow_html=True)
            st.caption("Share of emails that hit each seven-slot signal. "
                       "Low bars point to systemic gaps to fix in the "
                       "template.")
            slot_names = list(scored_rows[0]["slots"].keys()) \
                if scored_rows else []
            slot_hit_rows = []
            for slot in slot_names:
                hits = sum(1 for r in scored_rows if r["slots"][slot])
                slot_hit_rows.append(
                    {"Slot": slot,
                      "Hit rate": (hits / len(scored_rows) * 100)
                                    if scored_rows else 0,
                      "Emails hitting": hits})
            slot_hr_df = pd.DataFrame(slot_hit_rows)
            slot_chart = alt.Chart(slot_hr_df).mark_bar(size=18).encode(
                x=alt.X("Hit rate:Q", title="Hit rate (%)",
                          scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("Slot:N", sort="-x", title=None),
                color=alt.condition(
                    "datum['Hit rate'] >= 66",
                    alt.value(ACCENT), alt.value(GOLD)),
                tooltip=["Slot:N",
                          alt.Tooltip("Hit rate:Q", format=".0f"),
                          "Emails hitting:Q"],
            ).properties(height=240)
            st.altair_chart(slot_chart, width='stretch')

            # ---- Scores by content type ----
            st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                        'Challenge vs Result by content type</div>',
                        unsafe_allow_html=True)
            grp = scored_df.groupby("content_type")[
                ["challenge_score", "result_score"]].mean().reset_index()
            grp_long = grp.melt(id_vars=["content_type"],
                                  value_vars=["challenge_score",
                                                "result_score"],
                                  var_name="Axis", value_name="Score")
            grp_long["Axis"] = grp_long["Axis"].map({
                "challenge_score": "Challenge",
                "result_score": "Result"})
            grp_chart = alt.Chart(grp_long).mark_bar(size=22).encode(
                x=alt.X("content_type:N", title=None,
                          axis=alt.Axis(labelAngle=-15)),
                xOffset="Axis:N",
                y=alt.Y("Score:Q", title="Average score",
                          scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Axis:N",
                                  scale=alt.Scale(range=[ACCENT, GOLD])),
                tooltip=["content_type:N", "Axis:N",
                          alt.Tooltip("Score:Q", format=".0f")],
            ).properties(height=260)
            st.altair_chart(grp_chart, width='stretch')

            # ---- Named-customer frequency across all emails ----
            all_named = []
            for r in scored_rows:
                for name in r.get("named_customers", []):
                    all_named.append(name.strip())
            if all_named:
                from collections import Counter as _CntCA
                nc = _CntCA(all_named).most_common(15)
                nc_df = pd.DataFrame(nc, columns=["Customer", "Mentions"])
                st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                            'Named customer proof, most cited</div>',
                            unsafe_allow_html=True)
                st.caption("How often each named customer appears across "
                           "the current campaign set. Overused names look "
                           "stale; underused names are worth surfacing.")
                nc_chart = alt.Chart(nc_df).mark_bar(color=ACCENT,
                                                        size=14).encode(
                    x=alt.X("Mentions:Q", title="Mentions"),
                    y=alt.Y("Customer:N", sort="-x", title=None),
                    tooltip=["Customer:N", "Mentions:Q"],
                ).properties(height=max(200, 22 * len(nc_df)))
                st.altair_chart(nc_chart, width='stretch')

            # ---- Word count vs house score ----
            st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                        'Length vs house score</div>',
                        unsafe_allow_html=True)
            st.caption("Does longer copy score higher, or does it just add "
                       "words? A flat cloud means length is not the lever.")
            ln_df = scored_df.copy()
            ln_df["label"] = (ln_df["campaign_name"].astype(str)
                               + " · " + ln_df["stage"].astype(str))
            len_chart = alt.Chart(ln_df).mark_circle(
                size=160, opacity=0.85, color=ACCENT).encode(
                x=alt.X("words:Q", title="Word count"),
                y=alt.Y("house_score:Q", title="House score",
                          scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip("label:N", title="Email"),
                    "words:Q",
                    alt.Tooltip("house_score:Q", title="House"),
                ],
            ).properties(height=260)
            _trend = alt.Chart(ln_df).transform_regression(
                "words", "house_score"
            ).mark_line(color=GOLD, strokeWidth=2, strokeDash=[4, 4]).encode(
                x="words:Q", y="house_score:Q")
            st.altair_chart(len_chart + _trend,
                             width='stretch')

            st.markdown('<div style="margin:2.5rem 0 0;border-top:1px '
                        'solid ' + LINE + '"></div>', unsafe_allow_html=True)

            # ---- Detail drawer: pick a campaign ----
            st.markdown('<h3 style="margin-top:2rem">Email detail</h3>',
                        unsafe_allow_html=True)
            options = [
                f"{i+1}. {r['campaign_name']} - {r['stage']}"
                for i, r in scored_df.iterrows()]
            pick = st.selectbox("Pick an email", options,
                                 key="ca_email_pick")
            pick_idx = options.index(pick)
            row = scored_rows[pick_idx]

            hs1, hs2, hs3, hs4 = st.columns(4)
            with hs1:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Challenge score</div>'
                    f'<div class="kpi-value" style="color:{ACCENT}">'
                    f'{row["challenge_score"]}</div>'
                    f'<div class="kpi-sub">pain subject + stakeholder + '
                    f'problem chain</div></div>',
                    unsafe_allow_html=True)
            with hs2:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Result score</div>'
                    f'<div class="kpi-value" style="color:{ACCENT}">'
                    f'{row["result_score"]}</div>'
                    f'<div class="kpi-sub">named proof + numbers + CTA'
                    f'</div></div>',
                    unsafe_allow_html=True)
            with hs3:
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">House score'
                    f'</div><div class="kpi-value">{row["house_score"]}</div>'
                    f'<div class="kpi-sub">blended</div></div>',
                    unsafe_allow_html=True)
            with hs4:
                fk_str = f'{row["fk"]}' if row["fk"] is not None else '-'
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">Reading grade'
                    f'</div><div class="kpi-value">{fk_str}</div>'
                    f'<div class="kpi-sub">Flesch-Kincaid, {row["words"]} '
                    f'words</div></div>', unsafe_allow_html=True)

            # Evidence strip: what the analyser actually found for each
            # result slot, so scores are auditable.
            _ev = []
            if row["named_customers"]:
                _ev.append(f'<strong>Named customers ({len(row["named_customers"])})'
                            f':</strong> ' + ", ".join(
                                row["named_customers"][:5]))
            else:
                _ev.append('<strong>Named customers:</strong> none found')
            if row["pct_hits"]:
                _ev.append('<strong>Concrete numbers:</strong> '
                            + ", ".join(row["pct_hits"]))
            else:
                _ev.append('<strong>Concrete numbers:</strong> none found')
            if row["cta_hits"]:
                _ev.append('<strong>CTA phrases:</strong> '
                            + ", ".join(row["cta_hits"]))
            else:
                _ev.append('<strong>CTA phrases:</strong> none matched')
            _ev.append(f'<strong>Problem-cost connectives:</strong> '
                        f'{row["connective_hits"]} '
                        f'({"chain detected" if row["connective_hits"]>=2 else "chain missing"})')
            st.markdown(
                '<div style="background:#faf7f0;border-left:3px solid '
                + ACCENT + ';padding:.7rem 1rem;margin:.8rem 0;'
                'border-radius:4px;font-size:.9rem">'
                + '<br>'.join(_ev) + '</div>',
                unsafe_allow_html=True)

            dc1, dc2 = st.columns([1.2, 1])
            with dc1:
                st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                            'Subject</div>', unsafe_allow_html=True)
                st.write(row["subject"] or "_no subject line_")
                st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                            'Body</div>', unsafe_allow_html=True)
                with st.expander("Show full body", expanded=False):
                    st.text(row["body"])
            with dc2:
                st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                            'Seven-slot check</div>',
                            unsafe_allow_html=True)
                for slot, ok in row["slots"].items():
                    icon = "OK" if ok else "MISS"
                    color = ACCENT if ok else "#B34747"
                    st.markdown(
                        f'<div style="padding:.3rem 0"><span style="color:'
                        f'{color};font-weight:600">{icon}</span>&nbsp;{slot}'
                        f'</div>', unsafe_allow_html=True)

            vc1, vc2 = st.columns(2)
            with vc1:
                st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                            'Vocabulary hits</div>',
                            unsafe_allow_html=True)
                for g, info in row["vocab"].items():
                    hits_txt = (", ".join(info["hits"])
                                if info["hits"] else "(none)")
                    st.markdown(
                        f'<div style="padding:.3rem 0">'
                        f'<strong>{g.replace("_", " ")}:</strong> '
                        f'{info["count"]}/{info["total"]} - {hits_txt}'
                        f'</div>', unsafe_allow_html=True)
            with vc2:
                st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                            'Weak phrases</div>',
                            unsafe_allow_html=True)
                if row["weak"]:
                    for w, s in row["weak"]:
                        st.markdown(
                            f'<div style="padding:.3rem 0">'
                            f'<span style="text-decoration:line-through;'
                            f'color:{MUTED}">{w}</span> &rarr; '
                            f'<strong>{s}</strong></div>',
                            unsafe_allow_html=True)
                else:
                    st.markdown('<div style="color:{MUTED}">None - clean copy'
                                '</div>', unsafe_allow_html=True)

            # Persona fit
            st.markdown('<div class="eyebrow" style="margin-top:1.2rem">'
                        'Persona fit (term density)</div>',
                        unsafe_allow_html=True)
            pf_df = pd.DataFrame([
                {"Persona": k, "Density": v * 100}
                for k, v in row["persona_fit"].items()])
            pf_chart = alt.Chart(pf_df).mark_bar(color=ACCENT, size=24).encode(
                x=alt.X("Density:Q",
                          title="Term density (% of body words)"),
                y=alt.Y("Persona:N", sort="-x", title=None),
                tooltip=["Persona:N",
                          alt.Tooltip("Density:Q", format=".2f")],
            ).properties(height=140)
            st.altair_chart(pf_chart, width='stretch')
            dominant = row["persona_dominant"]
            if dominant == "Research":
                st.caption("Reads Research-first. Matches the dominant "
                           "blast slot (Research T2/T3 = 68% of verified "
                           "list).")
            else:
                st.caption(f"Reads {dominant}-first. If this ships as a "
                           f"blast, the dominant Research slot may not "
                           f"engage - consider re-anchoring vocabulary.")

            # ---- Aggregate: which pain themes get covered a lot ----
            st.markdown('<h3 style="margin-top:2.5rem">Coverage across all '
                        'campaigns</h3>', unsafe_allow_html=True)
            agg_rows = []
            for group, terms in SAAS_VOCAB_CA.items():
                for term in terms:
                    count = sum(1 for _, r in scored_df.iterrows()
                                if term in str(r["body"]).lower()
                                or term in str(r["subject"]).lower())
                    agg_rows.append({"Group": group.replace("_", " "),
                                      "Phrase": term,
                                      "Emails using it": count})
            agg_df = pd.DataFrame(agg_rows).sort_values(
                "Emails using it", ascending=False)

            ac1, ac2 = st.columns(2)
            with ac1:
                st.markdown('<div class="eyebrow">Most used phrases</div>',
                            unsafe_allow_html=True)
                st.dataframe(agg_df.head(10), width='stretch',
                              hide_index=True)
            with ac2:
                st.markdown('<div class="eyebrow">Least used phrases</div>',
                            unsafe_allow_html=True)
                unused = agg_df[agg_df["Emails using it"] == 0]
                if not unused.empty:
                    st.dataframe(unused, width='stretch',
                                  hide_index=True)
                    st.caption("These pain-shape phrases are missing from "
                               "every current campaign. Each is a candidate "
                               "for a new email angle.")
                else:
                    st.info("Every house phrase appears in at least one "
                             "campaign.")

            # ---- Content ideas: gap-driven ----
            st.markdown('<h3 style="margin-top:2rem">Suggested next '
                        'content</h3>', unsafe_allow_html=True)
            type_counts = scored_df["content_type"].value_counts().to_dict()
            gaps = []
            if type_counts.get("Product themed", 0) < 4:
                gaps.append(("Product themed", "Two more WP-style emails "
                              "(pick from: audit trail, integration, "
                              "reporting, funder scanner). Low count today."))
            if type_counts.get("Event promotion", 0) >= 5:
                gaps.append(("Event promotion", "Event emails dominate. "
                              "Balance the mix with more product-outcome "
                              "campaigns."))
            if not unused.empty:
                phrases = ", ".join(unused["Phrase"].head(3).tolist())
                gaps.append(("Missing pain shape",
                              f"No campaign covers: {phrases}. Each is a "
                              "content prompt."))
            weak_avg = scored_df["weak_count"].mean()
            if weak_avg >= 1:
                gaps.append(("Cleaner copy",
                              f"Average {weak_avg:.1f} weak phrase per "
                              "email. Swap the flagged phrases in the "
                              "detail drawer above."))
            if not gaps:
                st.success("No obvious content gaps against the current "
                            "rule set.")
            else:
                for tag, msg in gaps:
                    st.markdown(
                        f'<div style="background:#faf7f0;border-left:3px '
                        f'solid {ACCENT};padding:.7rem 1rem;margin:.5rem 0;'
                        f'border-radius:4px"><strong>{tag}.</strong> {msg}'
                        f'</div>', unsafe_allow_html=True)


# Email Performance Matrix is a self-contained app. Once its block above has
# rendered, halt so none of the LinkedIn-only sections below execute.
if app == "Email Performance Matrix":
    st.stop()

# ---------------------------------------------------------------------------
# RECOMMEND mode - renders the predictor screen then stops. Everything below
# this block is Explore-only rendering.
# ---------------------------------------------------------------------------
if mode == "Recommend":
    # ------ callback used by the "Append to caption" buttons below ------
    # Streamlit forbids mutating a widget's session_state key after that
    # widget has been instantiated on the same run. Callbacks execute at the
    # start of the next rerun, before any widget renders, so setting
    # draft_caption inside them is allowed.
    def _append_pending_tags():
        tags = st.session_state.get("_pending_tags", "")
        if not tags:
            return
        current = st.session_state.get("draft_caption", "") or ""
        if tags in current:
            return
        st.session_state["draft_caption"] = (
            current.rstrip() + "\n\n" + tags).strip()

    # ------ train ------
    st.markdown('<h2>Recommender</h2>', unsafe_allow_html=True)

    tcol1, tcol2 = st.columns([1, 3])
    with tcol1:
        train_click = st.button("Retrain model", width='stretch',
                                type="primary")
    with tcol2:
        st.caption("Learns from the posts in the current date range and "
                   "filters. Retrain any time you change them.")

    if train_click or "predictor_bundle" not in st.session_state:
        with st.spinner("Training..."):
            st.session_state.predictor_bundle = predictor.train_models(scored)
            st.session_state.predictor_trained_on = len(scored)

    bundle = st.session_state.get("predictor_bundle")
    if bundle is None or not bundle["models"]:
        st.warning("Not enough posts in the current filter to train "
                   "(need at least 15). Widen the date range.")
        st.stop()

    trained_on = st.session_state.get("predictor_trained_on", len(scored))
    st.markdown(
        f'<div style="color:{MUTED};font-size:.85rem;margin:-.6rem 0 1.5rem">'
        f'Model ready. Trained on {trained_on} posts.'
        f'</div>', unsafe_allow_html=True)

    # =======================================================================
    # SECTION A - PHOTO. Upload, auto-analyse, score, suggest improvements.
    # =======================================================================
    st.markdown('<h2>1. Photo</h2>', unsafe_allow_html=True)
    st.caption("Upload the image. The tool auto-detects face, text and "
               "palette, scores it, and tells you which visual swap would "
               "lift it the most.")

    ph_col1, ph_col2 = st.columns([3, 2], gap="large")

    with ph_col1:
        draft_image = st.file_uploader(
            "Image", type=["png", "jpg", "jpeg", "webp"],
            key="draft_image", label_visibility="collapsed")
        if draft_image:
            st.image(draft_image, width='stretch')

    # auto-analyse the image and pre-fill the visual tags
    auto_detected = None
    if draft_image is not None:
        img_fingerprint = f"{draft_image.name}_{draft_image.size}"
        if st.session_state.get("last_image_fp") != img_fingerprint:
            try:
                auto = image_analysis.analyze(draft_image)
                st.session_state.draft_face = auto["has_face_in_image"]
                st.session_state.draft_text = auto["text_on_image"]
                st.session_state.draft_colour = auto["image_colour_theme"]
                st.session_state["_auto_colour"] = auto["image_colour_theme"]
                st.session_state["_auto_raw"] = auto.get("raw_colours", [])
                st.session_state.last_image_fp = img_fingerprint
                auto_detected = auto
            except Exception as e:
                st.warning(f"Could not analyse the image: {e}")
        else:
            auto_detected = {
                "has_face_in_image": st.session_state.get("draft_face", "no"),
                "text_on_image": st.session_state.get("draft_text", "no"),
                "image_colour_theme": st.session_state.get("_auto_colour", ""),
                "raw_colours": st.session_state.get("_auto_raw", []),
            }

    with ph_col2:
        st.markdown('<div class="eyebrow">What we detected</div>',
                    unsafe_allow_html=True)
        if not draft_image:
            st.caption("Upload an image on the left to auto-fill these.")
        elif auto_detected and not auto_detected.get(
                "face_detection_available", True):
            st.markdown(
                f'<div style="font-size:.75rem;color:{WARN};margin:-.3rem 0 .6rem">'
                f'Face detection unavailable in this environment '
                f'({auto_detected.get("face_detection_note","")}). '
                f'Palette and text-on-image still work. Set the '
                f'\'Face in image?\' field by hand.'
                f'</div>', unsafe_allow_html=True)

        format_options = sorted(scored["format_inferred"].dropna().unique().tolist())
        format_pick = st.selectbox("Format", format_options, key="draft_format")
        face_pick = st.selectbox("Face in image?", ["yes", "no"],
                                 key="draft_face")
        text_pick = st.selectbox("Text on image?", ["yes", "no"],
                                 key="draft_text")
        colour_options = sorted(
            [v for v in scored["image_colour_theme"].dropna().unique()
             if str(v).strip() and str(v).strip().lower() != "nan"]
            if "image_colour_theme" in scored.columns else [])
        options_list = ["(unknown)"] + colour_options
        current = st.session_state.get("draft_colour", "")
        if current and current not in options_list:
            options_list.insert(1, current)
        colour_pick = (st.selectbox("Image palette", options_list,
                                    key="draft_colour")
                       if options_list else "(unknown)")

    # =======================================================================
    # SECTION B - TEXT. Caption + form. Auto-derive metrics from the caption.
    # =======================================================================
    st.markdown('<h2>2. Text</h2>', unsafe_allow_html=True)
    st.caption("Paste the caption and pick topic, ask, and publish day. "
               "The tool derives length, hashtag count and question use "
               "from the caption itself.")

    tx_col1, tx_col2 = st.columns([3, 2], gap="large")
    with tx_col1:
        draft_caption = st.text_area(
            "Caption", height=220, key="draft_caption",
            placeholder="Paste your draft post caption here...",
            label_visibility="collapsed")

    with tx_col2:
        st.markdown('<div class="eyebrow">What we derived</div>',
                    unsafe_allow_html=True)
        st.caption("Set by the caption on the left. Topic and Ask are the "
                   "only manual picks.")
        theme_options = sorted(scored["theme"].dropna().unique().tolist())
        theme_pick = st.selectbox("Topic", theme_options, key="draft_theme")
        cta_options = sorted(scored["cta_type"].dropna().unique().tolist())
        cta_pick = st.selectbox("Ask (call to action)", cta_options,
                                key="draft_cta")
        day_pick = st.selectbox("Publish day",
                                ["Monday", "Tuesday", "Wednesday", "Thursday",
                                 "Friday", "Saturday", "Sunday"],
                                key="draft_day")

    # ---- hashtag recommender - two modes ----
    #   (a) playbook mode: workbook uploaded -> 1 Broad + 2 Mid + 1 Targeted + #GrantsNow
    #   (b) historical mode: fall back to what past posts on this topic used
    st.markdown('<h3 style="margin-top:1rem">Suggested hashtags for this '
                'topic</h3>', unsafe_allow_html=True)
    hashtag_library = st.session_state.get("hashtag_library", None)

    if hashtag_library:
        # honour any UI override the user set in the sidebar
        override_map = st.session_state.get("topic_to_category_override", {})
        playbook_categories = override_map.get(
            theme_pick, scoring.TOPIC_TO_CATEGORY.get(
                theme_pick, ["Grants Management"]))
        if not playbook_categories:
            playbook_categories = ["Grants Management"]
        # honest baseline note: what the unproven-hashtag score is set to
        topic_slice = scored[scored["theme"] == theme_pick]
        if not topic_slice.empty and topic_slice["post_score"].notna().any():
            _baseline = float(topic_slice["post_score"].median())
            baseline_note = (f"Unproven hashtags get this topic's median "
                              f"score ({_baseline:.0f}) as their neutral "
                              f"baseline, so they compete fairly with the "
                              f"proven ones.")
        else:
            baseline_note = ("No past posts on this topic yet, so unproven "
                              "hashtags fall back to a neutral 50 and "
                              "workbook tier (Large > Medium > Small) "
                              "settles ties.")
        st.caption(
            "Following the GrantsNow playbook: 1 Broad + 2 Mid-tier + "
            "1 Targeted + #GrantsNow. Pulled from categories: "
            + ", ".join(playbook_categories)
            + " (change in the sidebar's 'Topic → category mapping'). "
            + baseline_note)
        tag_suggestions = scoring.suggest_hashtags_from_library(
            hashtag_library, theme_pick, past_posts=scored,
            include_grantsnow=True,
            category_override=playbook_categories)

        if tag_suggestions.empty:
            st.info("No hashtags in the library map to this topic yet.")
        else:
            # render each pick as a row with playbook role + tier + past use
            rows_html = []
            for _, r in tag_suggestions.iterrows():
                pav = r.get("past_avg_score")
                pcnt = int(r.get("past_count", 0) or 0)
                past_txt = (f"used {pcnt}x, avg {pav:.0f}"
                             if pcnt > 0 and pd.notna(pav)
                             else "not used before")
                tier_txt = f"{r['tier']}" if r.get("tier") else ""
                cat_txt = r.get("category", "")
                rows_html.append(
                    f'<div class="kv">'
                    f'<div class="k" style="color:{ACCENT};font-weight:700">'
                    f'{r["hashtag"]}</div>'
                    f'<div class="v" style="font-size:.78rem">'
                    f'<b>{r["playbook_role"]}</b> &middot; {tier_txt} '
                    f'&middot; {cat_txt} &middot; '
                    f'<span style="color:{MUTED}">{past_txt}</span>'
                    f'</div></div>')
            st.markdown(
                f'<div class="card" style="padding:1rem 1.2rem">'
                f'{"".join(rows_html)}</div>', unsafe_allow_html=True)

            all_tags = " ".join(tag_suggestions["hashtag"].tolist())
            # stash the tags to append and use an on_click callback. Callbacks
            # run at the start of the next rerun, before any widget is
            # instantiated, so setting draft_caption there is allowed.
            st.session_state["_pending_tags"] = all_tags
            cc1, cc2 = st.columns([4, 1])
            with cc1:
                st.text_input("Copy this row into your caption",
                              value=all_tags, key="tag_row_display",
                              label_visibility="collapsed")
            with cc2:
                st.button("Append to caption", width='stretch',
                          key="append_playbook_btn",
                          on_click=_append_pending_tags)
    else:
        # historical fall-back — no playbook loaded
        tag_suggestions = scoring.suggest_hashtags_for_topic(
            scored, theme_pick, top_n=10)
        if tag_suggestions.empty:
            tag_suggestions = scoring.suggest_hashtags_global(scored, top_n=10)
            _tag_scope_note = ("Not enough posts on this topic yet. Showing "
                                "the page's best hashtags overall.")
        else:
            _tag_scope_note = (
                f"Ranked by average post score for the '{theme_pick}' topic. "
                "Upload the GrantsNow hashtag workbook in the sidebar to "
                "apply the mix rule.")
        st.caption(_tag_scope_note)

        if not tag_suggestions.empty:
            chips_html = []
            for _, r in tag_suggestions.iterrows():
                badge = ("<span style='opacity:.7;font-size:.7rem;"
                          "margin-left:.3rem'>"
                          f"&middot;&nbsp;{int(r['count'])} posts"
                          f"&nbsp;&middot;&nbsp;avg {r['avg_score']:.0f}</span>")
                chips_html.append(
                    f'<span class="chip">{r["hashtag"]}{badge}</span>')
            st.markdown(
                f'<div style="line-height:2.1">{"".join(chips_html)}</div>',
                unsafe_allow_html=True)
            all_tags = " ".join(tag_suggestions["hashtag"].tolist())
            st.session_state["_pending_tags"] = all_tags
            cc1, cc2 = st.columns([4, 1])
            with cc1:
                st.text_input("Copy this row into your caption",
                              value=all_tags, key="tag_row_display",
                              label_visibility="collapsed")
            with cc2:
                st.button("Append to caption",
                          width='stretch',
                          key="append_history_btn",
                          on_click=_append_pending_tags)

    # ---- derive text metrics + build the draft dict ----
    import re
    text_body = draft_caption or ""
    words = text_body.split()
    hooked = text_body.split("\n", 1)[0] if text_body else ""
    hashtags = re.findall(r"#\w+", text_body)

    def _length_band(n):
        if n < 25: return "Very short (<25w)"
        if n < 60: return "Short (25-60w)"
        if n < 120: return "Medium (60-120w)"
        return "Long (120w+)"

    draft = {
        "theme": theme_pick, "cta_type": cta_pick,
        "format_inferred": format_pick, "day_of_week": day_pick,
        "has_face_in_image": face_pick, "text_on_image": text_pick,
        "image_colour_theme": colour_pick if colour_pick != "(unknown)" else "",
        "media_type": "image",
        "target_region": "UK",
        "word_count": len(words),
        "hook_len": len(hooked),
        "hashtag_count": len(hashtags),
        "emoji_count": 0,
        "line_breaks": text_body.count("\n"),
        "has_link": int("http" in text_body.lower()),
        "has_question": int("?" in text_body),
        "length_band": _length_band(len(words)),
    }

    # ---- decide whether each side is actually populated by the user ----
    photo_ready = draft_image is not None
    text_ready = len(text_body.strip()) >= 20

    # ---- helpers ----
    def _score_card(title, contribution, baseline, detected_rows, swaps,
                    sub_note):
        arrow = "+" if contribution >= 0 else "−"
        c_colour = ACCENT if contribution >= 0 else WARN
        combined = baseline + contribution
        rows_html = "".join(
            f'<div class="kv"><div class="k">{k}</div>'
            f'<div class="v">{v}</div></div>'
            for k, v in detected_rows)
        swaps_html = ""
        if swaps is not None and not swaps.empty:
            swaps_html = "<div style='margin-top:1rem'>" + "".join(
                f'<div class="kv win"><div class="k">Try {r["feature"]}: '
                f'{r["from"]} &rarr; {r["to"]}</div>'
                f'<div class="v">+{r["delta"]:.1f} pts</div></div>'
                for _, r in swaps.iterrows()) + "</div>"
        st.markdown(
            f'<div class="card">'
            f'<span class="tag a">{title}</span>'
            f'<div style="display:flex;align-items:baseline;gap:.5rem;'
            f'margin:.3rem 0 .3rem">'
            f'<div class="score" style="color:{c_colour}">'
            f'{arrow}{abs(contribution):.1f}</div>'
            f'<div class="score-lbl">points added to the combined score</div>'
            f'</div>'
            f'<div style="font-size:.82rem;color:{MUTED};margin-bottom:1rem">'
            f'Takes the post from a baseline of {baseline:.0f} to '
            f'<b style="color:{INK}">{combined:.0f}</b> on its own.'
            f'</div>'
            f'{rows_html}{swaps_html}'
            f'<div style="color:{MUTED};font-size:.75rem;margin-top:.8rem">'
            f'{sub_note}</div>'
            f'</div>', unsafe_allow_html=True)

    def _placeholder(title, hint):
        st.markdown(
            f'<div class="card" style="opacity:.6;border-style:dashed">'
            f'<span class="tag b">{title}</span>'
            f'<div style="font-size:.95rem;color:{MUTED};margin-top:.6rem">'
            f'{hint}</div></div>', unsafe_allow_html=True)

    # ---- pre-compute Shapley contributions once, using both sides ----
    # This is what feeds all three cards. Because sums add up exactly, the
    # numbers displayed across the scorecards and combined tiles cohere.
    contribs = predictor.contributions(bundle, draft, target="post_score")
    baseline_score = contribs["baseline"]
    photo_contrib = contribs["photo_contribution"]
    text_contrib = contribs["text_contribution"]
    combined_score = contribs["combined"]

    # =======================================================================
    # SCORECARDS - render only for the side the user actually provided
    # =======================================================================
    st.markdown('<h2>3. Scorecards</h2>', unsafe_allow_html=True)
    st.caption("Each side is scored as its contribution to the final combined "
               "score. Photo + Text = Combined − Baseline, exactly.")

    sc1, sc2 = st.columns(2, gap="large")

    detected_photo = []
    if photo_ready:
        detected_photo.append(("Face detected", face_pick))
        detected_photo.append(("Text on image", text_pick))
        raw_c = (auto_detected or {}).get("raw_colours") or []
        detected_photo.append(("Palette",
                               colour_pick if colour_pick != "(unknown)"
                               else ", ".join(raw_c) or "—"))
        detected_photo.append(("Format", format_pick))
        photo_swaps = predictor.what_would_lift(
            bundle, draft, target="post_score", top_n=3,
            only_features=predictor.PHOTO_FEATURES)

    detected_text = [
        ("Topic", theme_pick),
        ("Ask", cta_pick),
        ("Publish day", day_pick),
        ("Length", _length_band(len(words))),
        ("Word count", str(len(words))),
        ("Hashtag count", str(len(hashtags))),
        ("Question in caption", "yes" if "?" in text_body else "no"),
        ("Link in caption", "yes" if "http" in text_body.lower() else "no"),
    ] if text_ready else []

    if text_ready:
        text_swaps = predictor.what_would_lift(
            bundle, draft, target="post_score", top_n=3,
            only_features=predictor.TEXT_FEATURES)

    with sc1:
        if photo_ready:
            _score_card(
                "Photo", photo_contrib, baseline_score, detected_photo,
                photo_swaps,
                "The photo's Shapley contribution to the combined prediction.")
        else:
            _placeholder(
                "Photo",
                "Upload an image in Section 1 to see the photo score and "
                "improvement suggestions.")

    with sc2:
        if text_ready:
            _score_card(
                "Text", text_contrib, baseline_score, detected_text,
                text_swaps,
                "The text's Shapley contribution to the combined prediction.")
        else:
            _placeholder(
                "Text",
                "Paste a caption of at least 20 characters in Section 2 to "
                "see the text score and improvement suggestions.")

    # =======================================================================
    # SECTION C - COMBINED PREDICTION - only when at least one side is real
    # =======================================================================
    st.markdown('<h2>4. Combined prediction</h2>', unsafe_allow_html=True)

    if not (photo_ready or text_ready):
        _placeholder(
            "Combined prediction",
            "Fill in Section 1 or Section 2 above and this will populate.")
    else:
        st.caption("Full model prediction. The score below equals baseline "
                   "plus the two contributions above, by construction.")

        # additive breakdown line
        p_str = f'{photo_contrib:+.1f}' if photo_ready else '(neutral)'
        t_str = f'{text_contrib:+.1f}' if text_ready else '(neutral)'
        st.markdown(
            f'<div style="font-size:.9rem;color:{INK_SOFT};margin:.5rem 0 1rem">'
            f'Baseline <b>{baseline_score:.0f}</b> + '
            f'Photo <b style="color:{ACCENT if photo_contrib>=0 else WARN}">'
            f'{p_str}</b> + '
            f'Text <b style="color:{ACCENT if text_contrib>=0 else WARN}">'
            f'{t_str}</b> = '
            f'Predicted score <b style="color:{ACCENT}">'
            f'{combined_score:.0f}</b></div>',
            unsafe_allow_html=True)

        # the full model gives us views and reaction rate too
        preds = predictor.predict(bundle, draft)

        r1, r2, r3 = st.columns(3)

        def result_tile(col, label, value, unit=""):
            with col:
                st.markdown(
                    f'<div class="stat"><div class="k">{label}</div>'
                    f'<div class="v" style="color:{ACCENT}">{value}</div>'
                    f'<div class="d">{unit}</div></div>',
                    unsafe_allow_html=True)

        result_tile(r1, "Predicted score", f"{combined_score:.0f}",
                    "out of 100")
        if "Impressions" in preds:
            result_tile(r2, "Predicted views",
                        f"{preds['Impressions']:,.0f}", "impressions")
        if "engagement_rate" in preds:
            result_tile(r3, "Predicted reaction rate",
                        f"{preds['engagement_rate']*100:.2f}%",
                        "reactions / view")

        # ---- similar past posts ----
        sim = predictor.find_similar(bundle, draft, n=3)
        st.markdown('<h3 style="margin-top:1.6rem">Similar past posts</h3>',
                    unsafe_allow_html=True)
        st.caption("The three posts closest to this draft. Sense-check the "
                   "prediction against these.")

        for _, r in sim.iterrows():
            hook = (r["hook"] if isinstance(r["hook"], str) and r["hook"].strip()
                    else "[No copy]")
            if len(hook) > 130:
                hook = hook[:127] + "..."
            dt = r["created_date"].strftime("%d %b %Y")
            st.markdown(
                f'<div class="card">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:baseline">'
                f'<div class="hook">{hook}</div>'
                f'<div class="score">{r["post_score"]:.0f}</div></div>'
                f'<div class="meta">{dt} &middot; {r["theme"]} &middot; '
                f'{int(r["Impressions"]):,} views &middot; '
                f'{int(r["Likes"])} likes &middot; '
                f'{int(r["Comments"])} comments</div>'
                f'</div>', unsafe_allow_html=True)

        # ---- combined lift suggestions ----
        combined_swaps = predictor.what_would_lift(
            bundle, draft, target="post_score", top_n=4)
        if not combined_swaps.empty:
            st.markdown('<h3 style="margin-top:1.6rem">'
                        'Top single changes to lift this</h3>',
                        unsafe_allow_html=True)
            st.caption("Across photo and text, ranked by predicted lift.")
            for _, r in combined_swaps.iterrows():
                arrow = "+" if r["delta"] > 0 else ""
                st.markdown(
                    f'<div class="card" style="padding:.9rem 1.2rem">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:center">'
                    f'<div><b>{r["feature"]}</b>: '
                    f'{r["from"]} &rarr; <span style="color:{ACCENT}">'
                    f'{r["to"]}</span></div>'
                    f'<div style="color:{ACCENT};font-weight:700">'
                    f'{arrow}{r["delta"]:.1f} pts</div>'
                    f'</div></div>', unsafe_allow_html=True)

    # tiny honest footnote
    st.markdown(
        f'<div style="color:{MUTED};font-size:.75rem;'
        f'margin-top:2rem;text-align:center">'
        f'Based on patterns from {trained_on} past posts. '
        f'Suggestions, not guarantees.</div>',
        unsafe_allow_html=True)

    st.stop()  # do not render Explore-mode content below


# ---------------------------------------------------------------------------
# VISUALIZE mode - a long-scroll gallery of every useful chart on this data.
# Backend untouched; just fresh Altair views over `scored`.
# ---------------------------------------------------------------------------
if mode == "Visualize":
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
        st.altair_chart(hist, width='stretch')

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
                        ).properties(height=250), width='stretch')

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
        st.altair_chart(heat, width='stretch')

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
                        width='stretch')

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
                width='stretch')
        with mv2:
            st.altair_chart(alt.Chart(month_agg).mark_bar(
                color=INK_SOFT).encode(
                x=alt.X("month:T", title=None),
                y=alt.Y("views:Q", title="Total views"),
                tooltip=[alt.Tooltip("month:T", format="%b %Y"),
                         alt.Tooltip("views:Q", format=",")]).properties(
                    height=240),
                width='stretch')

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
                        width='stretch')

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
        st.altair_chart(_rect + _lbl, width='stretch')

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
                            width='stretch')
        with c2:
            st.markdown("**Ask (CTA)**")
            st.altair_chart(cat_bars("cta_type", "Ask"),
                            width='stretch')
        c3, c4 = st.columns(2, gap="large")
        with c3:
            st.markdown("**Publish day**")
            st.altair_chart(cat_bars("day_of_week", "Day"),
                            width='stretch')
        with c4:
            st.markdown("**Length band**")
            st.altair_chart(cat_bars("length_band", "Length"),
                            width='stretch')
        if "image_colour_theme" in scored.columns:
            c5, c6 = st.columns(2, gap="large")
            with c5:
                st.markdown("**Image palette**")
                st.altair_chart(cat_bars("image_colour_theme", "Palette"),
                                width='stretch')
            with c6:
                if "has_face_in_image" in scored.columns:
                    st.markdown("**Face in image**")
                    st.altair_chart(cat_bars("has_face_in_image", "Face"),
                                    width='stretch')

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
            text="n:Q"), width='stretch')

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
                        width='stretch')

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
        ).properties(height=340), width='stretch')

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
        st.altair_chart(p_line + ref, width='stretch')

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
                        width='stretch')

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
                        width='stretch')

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
                            width='stretch')
        with b2:
            st.altair_chart(bool_box("has_link", "Link in caption"),
                            width='stretch')

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
                            width='stretch')

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
            st.altair_chart(lift_chart, width='stretch')
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
                width='stretch')
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
                width='stretch')

        st.markdown('<h3 style="margin-top:2rem">Top vs bottom, side by '
                    'side</h3>', unsafe_allow_html=True)
        st.caption("Every micro-detail. Rows where columns differ = recipe.")
        micro = scoring.micro_attribute_table(scored)
        st.dataframe(micro, width='stretch', hide_index=True)

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
            ).properties(height=340), width='stretch')

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
            st.dataframe(preview, width='stretch',
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
                width='stretch')

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
                            width='stretch')
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
                        width='stretch')

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
        ).properties(height=340), width='stretch')

    # tiny footnote
    st.markdown(
        f'<div style="color:{MUTED};font-size:.75rem;'
        f'margin-top:2rem;text-align:center">'
        f'{len(scored)} posts &middot; {start_date:%d %b %Y} to '
        f'{end_date:%d %b %Y}. Filters apply across all tabs.</div>',
        unsafe_allow_html=True)

    st.stop()


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
