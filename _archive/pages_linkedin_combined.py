"""
LinkedIn Post Performance Matrix - all three modes on one page.

Sidebar Refine filters and hashtag playbook live here. The mode radio at
the top of the page switches Explore / Visualize / Recommend.
"""

from shared import (inject_css, load_csv, DATA_DIR, INK, INK_SOFT, MUTED,
                     LINE, BG, BG_SOFT, ACCENT, ACCENT_SOFT, WARN, GOLD,
                     FEATURES, LABELS)
import os, re
import altair as alt
import pandas as pd
import streamlit as st

import scoring
import predictor
import image_analysis

inject_css()

# The app switcher is now the sidebar navigation, so we hard-code the mode
# behaviour that used to live under `if app == "LinkedIn Post Matrix":`.
app = "LinkedIn Post Matrix"

posts_raw = load_csv("posts.csv")
if posts_raw.empty:
    st.error("No posts.csv found. Run `python etl/etl.py --src <exports>` "
             "first.")
    st.stop()

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
