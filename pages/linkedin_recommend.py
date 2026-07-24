"""
LinkedIn Post Performance Matrix - Recommend page.
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
ctx = linkedin_setup("Recommend")

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
    train_click = st.button("Retrain model", use_container_width=True,
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
        st.image(draft_image, use_container_width=True)

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
            st.button("Append to caption", use_container_width=True,
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
                      use_container_width=True,
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
