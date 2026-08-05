"""
LinkedIn - What worked.

Layout:
    1. Snapshot tiles
    2. Every post ranked - proper Streamlit table with row selection.
       Tick a row and it highlights natively; the selected rows feed
       the Compare section below.
    3. Compare - reads the ticked rows and renders them side by side.
       If nothing ticked, tells the user to pick some rows above.
"""
from shared import (inject_css, linkedin_setup, INK, INK_SOFT, MUTED,
                     LINE, BG, BG_SOFT, ACCENT, ACCENT_SOFT, WARN, GOLD)
import html as _html
import pandas as pd
import streamlit as st

inject_css()
ctx = linkedin_setup("Explore")
scored = ctx.scored


# ==========================================================================
# 1. Snapshot
# ==========================================================================
n_posts = len(scored)
top_score = float(scored["post_score"].max()) if n_posts else 0
median_score = float(scored["post_score"].median()) if n_posts else 0
above_median = int((scored["post_score"] > median_score).sum())


def _tile(col, label, value, sub, colour=INK):
    with col:
        st.markdown(
            f'<div style="border:1px solid {LINE};border-radius:8px;'
            f'padding:.9rem 1.1rem;background:{BG};height:100%">'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.14em;'
            f'margin-bottom:.35rem">{label}</div>'
            f'<div style="font-size:1.8rem;font-weight:700;color:{colour};'
            f'line-height:1.1">{value}</div>'
            f'<div style="font-size:.78rem;color:{INK_SOFT};'
            f'margin-top:.3rem">{sub}</div></div>',
            unsafe_allow_html=True)


c1, c2, c3, c4 = st.columns(4)
_tile(c1, "Posts in view", f"{n_posts}", "in the filtered window")
_tile(c2, "Top post score", f"{top_score:.0f}",
       "out of 100", colour=ACCENT)
_tile(c3, "Median post score", f"{median_score:.0f}",
       "half score higher, half lower")
_tile(c4, "Beat the median", f"{above_median}",
       f"of {n_posts} scored above {median_score:.0f}", colour=ACCENT)


# ==========================================================================
# 2. Every post ranked - selectable table
# ==========================================================================
st.markdown('<h2 style="margin-top:1.5rem">Every post, ranked</h2>',
             unsafe_allow_html=True)
st.caption("Highest-scoring at the top. **Tick one row** using the "
            "checkbox on the left - it lights up and gets compared "
            "against the top performer in the Compare panel below.")

ranked = scored.sort_values(
    ["post_score", "created_date"], ascending=[False, False]
).reset_index(drop=True)
n_ranked = len(ranked)

if n_ranked == 0:
    st.info("No posts in the current filter.")
    st.stop()

# Table view
tbl = pd.DataFrame({
    "Date":        ranked["created_date"].dt.strftime("%d %b %Y"),
    "First line":  ranked["hook_short"].fillna("").astype(str),
    "Score":       ranked["post_score"].round(0).astype(int),
    "Views":       ranked["Impressions"].fillna(0).astype(int),
    "Likes":       ranked["Likes"].fillna(0).astype(int),
    "Comments":    ranked["Comments"].fillna(0).astype(int),
    "Topic":       ranked["theme"].fillna("").astype(str),
    "Ask":         ranked["cta_type"].fillna("").astype(str),
    "Length":      ranked["length_band"].fillna("").astype(str),
    "Day":         ranked["day_of_week"].fillna("").astype(str),
})

_max_score = int(tbl["Score"].max()) if len(tbl) else 100
_max_views = int(tbl["Views"].max()) if len(tbl) else 1
_max_likes = max(int(tbl["Likes"].max()) if len(tbl) else 1, 1)
_max_comm  = max(int(tbl["Comments"].max()) if len(tbl) else 1, 1)

event = st.dataframe(
    tbl,
    use_container_width=True,
    hide_index=True,
    height=420,
    on_select="rerun",
    selection_mode="single-row",
    key="expl_table",
    column_config={
        "First line": st.column_config.TextColumn(width="large"),
        "Score": st.column_config.ProgressColumn(
            min_value=0, max_value=_max_score,
            format="%d",
            help="Composite score 0-100 for how this post performed "
                    "vs. every other post in view."),
        "Views": st.column_config.ProgressColumn(
            min_value=0, max_value=_max_views,
            format="%d",
            help="Impressions."),
        "Likes": st.column_config.ProgressColumn(
            min_value=0, max_value=_max_likes,
            format="%d"),
        "Comments": st.column_config.ProgressColumn(
            min_value=0, max_value=_max_comm,
            format="%d"),
    })

# Selected row index (into `ranked`)
sel_rows = list(event.selection.rows) if event and event.selection else []
sel_idx = sel_rows[0] if sel_rows else None

# Selection acknowledgement banner
if sel_idx is None:
    st.markdown(
        f'<div style="border:1px dashed {LINE};border-radius:6px;'
        f'padding:.7rem 1rem;background:{BG_SOFT};color:{INK_SOFT};'
        f'font-size:.9rem;margin:.6rem 0 1rem">'
        f'Nothing picked yet. Tick a row above and it will be '
        f'compared against the top performer below.'
        f'</div>', unsafe_allow_html=True)
else:
    _picked = ranked.iloc[sel_idx]
    _pick_hook = str(_picked.get("hook_short") or "").strip() or "[no copy]"
    _pick_hook_short = _html.escape(_pick_hook[:70])
    st.markdown(
        f'<div style="border:1px solid {ACCENT};border-radius:6px;'
        f'padding:.6rem 1rem;background:{ACCENT}18;color:{INK};'
        f'font-size:.88rem;margin:.6rem 0 1rem">'
        f'<strong>Picked:</strong> {_pick_hook_short} '
        f'&middot; score {int(_picked["post_score"])}. '
        f'Compared against the top performer below.'
        f'</div>', unsafe_allow_html=True)


# ==========================================================================
# 3. Compare - picked post vs top performer
# ==========================================================================
st.markdown('<h2>Compare</h2>', unsafe_allow_html=True)

# Same-topic toggle so the comparison stays fair
tc1, tc2 = st.columns([3, 2])
with tc2:
    same_topic = st.checkbox(
        "Compare against top of the same topic",
        value=True,
        key="expl_same_topic",
        help="When ticked, the top card is the highest-scoring post "
              "on the same topic as your pick. Ticked off, it is the "
              "single highest-scoring post in the whole window.")

if sel_idx is None:
    st.caption("Tick a row above to see it here alongside the top "
                "performer.")
else:
    row_pick = ranked.iloc[sel_idx]
    selected_theme = str(row_pick.get("theme", "")).strip()

    # Determine the top card
    if same_topic and selected_theme:
        peers = ranked[ranked["theme"] == selected_theme]
        if peers.empty:
            peers = ranked
            top_scope = "all posts"
        else:
            top_scope = f"topic: {selected_theme}"
    else:
        peers = ranked
        top_scope = "all posts"
    row_top = peers.iloc[0]

    same_row = (int(row_top.get("idx", -1)) == int(row_pick.get("idx", -2)))

    COMPARE_ATTRS = [
        ("theme",              "Topic"),
        ("cta_type",           "Ask"),
        ("length_band",        "Length"),
        ("day_of_week",        "Publish day"),
        ("format_inferred",    "Format"),
        ("has_face_in_image",  "Face in image"),
        ("image_colour_theme", "Image colour"),
        ("campaign",           "Campaign"),
    ]

    def _card(col, row, tag, tag_colour):
        hook = str(row.get("hook") or "").strip() or "[no copy]"
        if len(hook) > 260:
            hook = hook[:257] + "..."
        hook = _html.escape(hook)
        dt = row["created_date"].strftime("%a %d %b %Y") \
            if pd.notna(row["created_date"]) else ""
        views = int(row.get("Impressions", 0) or 0)
        likes = int(row.get("Likes", 0) or 0)
        comments = int(row.get("Comments", 0) or 0)
        score = float(row["post_score"])

        kv = []
        for f, label in COMPARE_ATTRS:
            v = str(row.get(f, "") or "").strip()
            if v in ("", "nan"):
                v = "—"
            v = _html.escape(v[:60])
            kv.append(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:.3rem 0;border-bottom:1px dashed {LINE};'
                f'font-size:.82rem">'
                f'<span style="color:{MUTED}">{label}</span>'
                f'<span style="color:{INK};font-weight:600;'
                f'text-align:right">{v}</span></div>')

        with col:
            st.markdown(
                f'<div style="border:1px solid {LINE};'
                f'border-top:4px solid {tag_colour};border-radius:8px;'
                f'padding:1rem 1.2rem;background:{BG};height:100%">'
                f'<div style="display:flex;align-items:center;gap:.5rem;'
                f'margin-bottom:.5rem">'
                f'<span style="background:{tag_colour};color:white;'
                f'padding:.1rem .5rem;border-radius:3px;font-size:.68rem;'
                f'font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.1em">{tag}</span>'
                f'<span style="color:{MUTED};font-size:.75rem">{dt}</span>'
                f'</div>'
                f'<div style="color:{INK};font-size:.95rem;'
                f'line-height:1.55;margin:.3rem 0 .7rem">{hook}</div>'
                f'<div style="display:flex;align-items:baseline;gap:.5rem;'
                f'margin-bottom:.8rem">'
                f'<div style="font-size:2.2rem;font-weight:700;'
                f'color:{tag_colour};line-height:1">{score:.0f}</div>'
                f'<div style="font-size:.75rem;color:{MUTED}">'
                f'score / 100</div></div>'
                f'<div style="display:grid;grid-template-columns:'
                f'1fr 1fr 1fr;gap:.5rem;margin-bottom:.9rem">'
                f'<div style="background:{BG_SOFT};padding:.5rem;'
                f'border-radius:5px;text-align:center">'
                f'<div style="font-size:.68rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.1em">Views</div>'
                f'<div style="font-weight:700;color:{INK};font-size:1rem">'
                f'{views:,}</div></div>'
                f'<div style="background:{BG_SOFT};padding:.5rem;'
                f'border-radius:5px;text-align:center">'
                f'<div style="font-size:.68rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.1em">Likes</div>'
                f'<div style="font-weight:700;color:{INK};font-size:1rem">'
                f'{likes:,}</div></div>'
                f'<div style="background:{BG_SOFT};padding:.5rem;'
                f'border-radius:5px;text-align:center">'
                f'<div style="font-size:.68rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.1em">Comments'
                f'</div>'
                f'<div style="font-weight:700;color:{INK};font-size:1rem">'
                f'{comments:,}</div></div>'
                f'</div>'
                + "".join(kv) +
                f'</div>', unsafe_allow_html=True)

    lc, rc = st.columns(2, gap="large")
    _card(lc, row_pick, "Your pick", ACCENT)
    if same_row:
        top_tag = f"Your pick is the top ({top_scope})"
    else:
        top_tag = f"Top performer ({top_scope})"
    _card(rc, row_top, top_tag, GOLD)

    # ==================================================================
    # Why the top wins - rule-based diagnostic
    # ==================================================================
    if not same_row:
        import re as _re
        from collections import Counter as _Counter

        _STOP = {
            "the","a","an","and","or","of","to","in","on","for","is",
            "are","was","were","be","been","being","have","has","had",
            "do","does","did","this","that","these","those","it","its",
            "you","your","we","our","us","i","me","my","he","she","him",
            "her","they","them","their","as","at","by","with","from",
            "but","if","so","not","no","yes","can","will","would",
            "should","may","might","just","only","also","than","then",
            "when","where","which","who","what","how","why","because",
        }

        def _txt(row):
            hook = str(row.get("hook") or "")
            return hook.strip()

        def _tokens(text):
            text = text.lower()
            return [t for t in _re.findall(r"[a-z][a-z\-']+", text)
                     if t not in _STOP and len(t) > 2]

        def _first_line(text):
            return text.split("\n", 1)[0].strip() if text else ""

        def _has_question(text):
            return "?" in text

        def _has_number(text):
            return bool(_re.search(r"\b\d[\d,\.]*%?\b", text))

        def _hashtag_count(text):
            return len(_re.findall(r"#\w+", text))

        def _mentions(text):
            return len(_re.findall(r"@\w+", text))

        def _sentences(text):
            return [s for s in _re.split(r"(?<=[\.\!\?])\s+", text)
                     if s.strip()]

        def _profile(text):
            words = _re.findall(r"[A-Za-z\-']+", text)
            first = _first_line(text)
            return {
                "chars":         len(text),
                "words":         len(words),
                "sentences":     len(_sentences(text)),
                "first_line":    first,
                "first_line_len": len(first),
                "first_line_words": len(first.split()),
                "first_is_q":    _has_question(first),
                "first_has_num": _has_number(first),
                "body_has_q":    _has_question(text),
                "body_has_num":  _has_number(text),
                "hashtags":      _hashtag_count(text),
                "mentions":      _mentions(text),
                "exclaim":       text.count("!"),
                "avg_sent_len":  (len(words) /
                                    max(len(_sentences(text)), 1)),
                "tokens":        _tokens(text),
            }

        pick_text = _txt(row_pick)
        top_text  = _txt(row_top)
        pick = _profile(pick_text)
        top  = _profile(top_text)

        top_toks = _Counter(top["tokens"])
        pick_toks = _Counter(pick["tokens"])
        # Words the top uses that the pick doesn't
        unique_to_top = [(w, n) for w, n in top_toks.most_common(30)
                          if pick_toks.get(w, 0) == 0]
        shared = set(top_toks) & set(pick_toks)

        # -------- Build observations --------
        observations = []
        recos = []

        # First-line style
        if top["first_is_q"] and not pick["first_is_q"]:
            observations.append(
                "The top opens with a <strong>question</strong>. "
                "Yours opens with a statement.")
            recos.append("Rewrite the first line as a question - "
                          "questions pull the eye down the feed.")
        elif pick["first_is_q"] and not top["first_is_q"]:
            observations.append(
                "You open with a question; the top opens with a "
                "statement. Both can work in this dataset.")

        if top["first_has_num"] and not pick["first_has_num"]:
            observations.append(
                "The top puts a <strong>number in the first line</strong> "
                "(a percentage or count). Yours does not.")
            recos.append("Add a concrete number or % to the first "
                          "line - it out-scrolls plain text.")

        # First-line length
        fl_diff = pick["first_line_words"] - top["first_line_words"]
        if abs(fl_diff) >= 5:
            if fl_diff > 0:
                observations.append(
                    f"Your first line runs "
                    f"<strong>{pick['first_line_words']} words</strong>; "
                    f"the top opens with only "
                    f"<strong>{top['first_line_words']}</strong>.")
                recos.append(
                    f"Tighten the first line to "
                    f"~{top['first_line_words']} words - short openers "
                    f"beat the &lsquo;see more&rsquo; cut-off.")
            else:
                observations.append(
                    f"Your first line is shorter "
                    f"({pick['first_line_words']} words) than the top "
                    f"({top['first_line_words']}).")

        # Overall length
        w_diff = pick["words"] - top["words"]
        if abs(w_diff) >= 40:
            if w_diff > 0:
                observations.append(
                    f"Your post runs <strong>{pick['words']} words</strong>; "
                    f"the top is <strong>{top['words']}</strong>. That is "
                    f"~{w_diff} extra words to scroll past.")
                recos.append(
                    f"Cut around {w_diff} words. Anything after the "
                    f"first two sentences the reader will not see "
                    f"unless the hook lands.")
            else:
                observations.append(
                    f"Your post is shorter ({pick['words']} words) than "
                    f"the top ({top['words']}).")

        # Body number
        if top["body_has_num"] and not pick["body_has_num"]:
            observations.append(
                "The top backs claims with <strong>concrete numbers</strong> "
                "(a stat or percentage). Yours has none.")
            recos.append("Add one hard number - readers trust posts "
                          "with a stat over posts without one.")

        # Questions in the body
        if top["body_has_q"] and not pick["body_has_q"]:
            observations.append(
                "The top asks a <strong>question inside the body</strong> "
                "to invite replies. Yours does not.")
            recos.append("Insert one question near the end - it "
                          "cues comments.")

        # Hashtags
        h_diff = pick["hashtags"] - top["hashtags"]
        if abs(h_diff) >= 3:
            if h_diff > 0:
                observations.append(
                    f"You used <strong>{pick['hashtags']} hashtags</strong>; "
                    f"the top used <strong>{top['hashtags']}</strong>.")
                recos.append(
                    f"Drop to {top['hashtags']} hashtags. More than "
                    f"5-6 dilutes rather than reaches.")
            else:
                observations.append(
                    f"You used only {pick['hashtags']} hashtags vs the "
                    f"top&apos;s {top['hashtags']}.")

        # Sentence length
        if pick["avg_sent_len"] > top["avg_sent_len"] * 1.5 \
                and pick["avg_sent_len"] > 20:
            observations.append(
                f"Your average sentence is "
                f"<strong>{pick['avg_sent_len']:.0f} words</strong>; "
                f"the top averages <strong>{top['avg_sent_len']:.0f}</strong>. "
                f"Long sentences slow scroll-readers down.")
            recos.append("Break the longest sentences into two.")

        # Exclamation over-use
        if pick["exclaim"] >= 3 and top["exclaim"] <= 1:
            observations.append(
                f"You use <strong>{pick['exclaim']} exclamation marks</strong>; "
                f"the top uses {top['exclaim']}. Feed readers see !!! "
                f"as noise.")
            recos.append("Cut the exclamation marks.")

        # Attribute diffs (structured)
        attr_flips = []
        for f, label in [
            ("cta_type",           "Ask"),
            ("length_band",        "Length band"),
            ("day_of_week",        "Publish day"),
            ("format_inferred",    "Format"),
            ("has_face_in_image",  "Face in image"),
            ("image_colour_theme", "Image colour"),
        ]:
            vp = str(row_pick.get(f, "") or "").strip()
            vt = str(row_top.get(f, "") or "").strip()
            if vp and vt and vp != vt and vp.lower() != "nan" \
                    and vt.lower() != "nan":
                attr_flips.append((label, vp, vt))

        # Word-level: what the top emphasises that you don't
        top_words_html = ""
        if unique_to_top:
            _show = unique_to_top[:12]
            chips = "".join(
                f'<span style="background:{GOLD}22;color:{INK};'
                f'padding:.15rem .45rem;border-radius:3px;'
                f'font-size:.75rem;font-weight:600;'
                f'margin:.15rem .2rem .15rem 0;'
                f'display:inline-block">{_html.escape(w)}'
                + (f' <span style="color:{MUTED};font-weight:400">'
                   f'&times;{n}</span>' if n > 1 else "")
                + '</span>'
                for w, n in _show)
            top_words_html = (
                f'<div style="margin-top:.9rem">'
                f'<div style="font-size:.72rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.14em;'
                f'margin-bottom:.35rem">Words the top uses that '
                f'yours does not</div>'
                f'<div>{chips}</div></div>')

        # -------- Render the analysis card --------
        st.markdown(
            f'<div style="border:1px solid {LINE};border-radius:8px;'
            f'padding:1rem 1.3rem;background:{BG};margin-top:1.1rem">'
            f'<div style="display:flex;align-items:baseline;'
            f'justify-content:space-between;margin-bottom:.6rem">'
            f'<div style="font-weight:700;color:{INK};font-size:1.05rem">'
            f'Why the top wins</div>'
            f'<div style="font-size:.75rem;color:{MUTED}">'
            f'rule-based pattern read</div></div>',
            unsafe_allow_html=True)

        # Small stat strip
        st.markdown(
            f'<div style="display:grid;grid-template-columns:'
            f'repeat(4,1fr);gap:.5rem;margin-bottom:.9rem">'
            + "".join(
                f'<div style="background:{BG_SOFT};padding:.5rem .6rem;'
                f'border-radius:5px">'
                f'<div style="font-size:.68rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.1em">'
                f'{label}</div>'
                f'<div style="font-size:.9rem;color:{INK};'
                f'margin-top:.2rem">'
                f'<span style="color:{ACCENT};font-weight:700">'
                f'{pv}</span>'
                f'<span style="color:{MUTED}"> &rarr; </span>'
                f'<span style="color:{GOLD};font-weight:700">'
                f'{tv}</span></div></div>'
                for label, pv, tv in [
                    ("Words",     pick["words"],     top["words"]),
                    ("First line", f'{pick["first_line_words"]}w',
                                    f'{top["first_line_words"]}w'),
                    ("Hashtags",  pick["hashtags"],  top["hashtags"]),
                    ("Sentences", pick["sentences"], top["sentences"]),
                ]) +
            f'</div>', unsafe_allow_html=True)

        if observations:
            obs_html = "".join(
                f'<li style="margin:.3rem 0;line-height:1.5;'
                f'color:{INK}">{o}</li>' for o in observations)
            st.markdown(
                f'<div style="font-size:.72rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.14em;'
                f'margin-bottom:.3rem">What is different</div>'
                f'<ul style="margin:0 0 .8rem 0;padding-left:1.2rem;'
                f'font-size:.9rem">{obs_html}</ul>',
                unsafe_allow_html=True)

        if attr_flips:
            flips = "".join(
                f'<span style="display:inline-block;background:{BG_SOFT};'
                f'padding:.25rem .55rem;border-radius:4px;'
                f'font-size:.78rem;color:{INK};margin:.15rem .2rem .15rem 0">'
                f'<span style="color:{MUTED}">{lbl}:</span> '
                f'<span style="color:{ACCENT};font-weight:600">{pv}</span> '
                f'<span style="color:{MUTED}">&rarr;</span> '
                f'<span style="color:{GOLD};font-weight:600">{tv}</span>'
                f'</span>'
                for lbl, pv, tv in attr_flips)
            st.markdown(
                f'<div style="font-size:.72rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.14em;'
                f'margin-bottom:.35rem">Attribute swaps to try</div>'
                f'<div style="margin-bottom:.8rem">{flips}</div>',
                unsafe_allow_html=True)

        if top_words_html:
            st.markdown(top_words_html, unsafe_allow_html=True)

        if recos:
            reco_html = "".join(
                f'<li style="margin:.35rem 0;line-height:1.5;'
                f'color:{INK}">{r}</li>' for r in recos)
            st.markdown(
                f'<div style="margin-top:1rem;padding-top:.8rem;'
                f'border-top:1px solid {LINE}">'
                f'<div style="font-size:.72rem;color:{ACCENT};'
                f'text-transform:uppercase;letter-spacing:.14em;'
                f'font-weight:700;margin-bottom:.3rem">'
                f'Try this on the next post</div>'
                f'<ul style="margin:0;padding-left:1.2rem;'
                f'font-size:.9rem">{reco_html}</ul></div>',
                unsafe_allow_html=True)

        if not observations and not attr_flips and not unique_to_top:
            st.caption("The two posts are structurally very similar. "
                        "The gap is likely down to timing or reach "
                        "rather than the writing.")

        st.markdown('</div>', unsafe_allow_html=True)

    # Delta strip
    if same_row:
        st.markdown(
            f'<div style="border:1px solid {ACCENT};border-radius:6px;'
            f'padding:.8rem 1.1rem;background:{ACCENT}18;'
            f'margin-top:1rem;font-size:.9rem;color:{INK}">'
            f'The post you picked <strong>is</strong> the top '
            f'performer in the {top_scope}. Nothing to beat here.'
            f'</div>', unsafe_allow_html=True)
    else:
        d_score = float(row_top["post_score"]) - float(row_pick["post_score"])
        d_views = int(row_top.get("Impressions", 0) or 0) - \
                     int(row_pick.get("Impressions", 0) or 0)
        d_likes = int(row_top.get("Likes", 0) or 0) - \
                     int(row_pick.get("Likes", 0) or 0)
        st.markdown(
            f'<div style="border:1px solid {LINE};border-radius:6px;'
            f'padding:.8rem 1.1rem;background:{BG_SOFT};'
            f'margin-top:1rem;font-size:.9rem;color:{INK_SOFT}">'
            f'Top performer beats your pick by '
            f'<strong>{abs(d_score):.0f}</strong> score points '
            f'&middot; <strong>{d_views:,}</strong> more views '
            f'&middot; <strong>{d_likes:,}</strong> more likes.'
            f'</div>', unsafe_allow_html=True)
