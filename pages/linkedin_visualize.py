"""
LinkedIn - See the pattern (text-only rebuild).

For a director who does not want to interpret charts. Every previous
visualisation is now a table or a plain-English paragraph.

Sections:
    1. The winning recipe - what top-quartile posts look like on
       writing features
    2. Wins by attribute - one table per LinkedIn attribute
       (theme, format, day of week, CTA type, length band)
    3. Best 10 vs worst 10 posts side by side
"""
from shared import (core_question, inject_css, render_status_key,
                     kpi_tile, so_what, load_csv, linkedin_setup,
                     FEATURES, LABELS,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()
ctx = linkedin_setup("Visualize")

scored = ctx.scored


# ==========================================================================
# 1. The winning recipe (writing features)
# ==========================================================================
st.markdown('<h2>The winning recipe</h2>', unsafe_allow_html=True)
st.caption("What top-scoring posts actually look like on the writing "
            "side, next to everyone else. Bigger gap = bigger lever.")

FRIENDLY = {
    "word_count":       ("Word count",         "words per post"),
    "hashtag_count":    ("Number of hashtags", "hashtags per post"),
    "hook_len":         ("First-line length",  "characters"),
    "reach_index":      ("Reach index",        "0-1 scaled"),
    "engagement_index": ("Engagement index",   "0-1 scaled"),
}
features_present = [c for c in FRIENDLY
                      if c in scored.columns
                      and scored[c].notna().any()]

if features_present and "post_score" in scored.columns \
        and len(scored) >= 8:
    _cutoff = scored["post_score"].quantile(0.75)
    winners = scored[scored["post_score"] >= _cutoff]
    rest    = scored[scored["post_score"] <  _cutoff]

    rows = []
    for f in features_present:
        label, unit = FRIENDLY[f]
        w_avg = float(winners[f].dropna().mean()) if len(winners) else 0
        r_avg = float(rest[f].dropna().mean()) if len(rest) else 0
        rows.append({"Feature": label,
                      "Winners avg": w_avg,
                      "Rest avg":    r_avg,
                      "unit":        unit})

    # Recipe list (plain text)
    recipe_lines = []
    for row in rows:
        w, r = row["Winners avg"], row["Rest avg"]
        pct = None if r == 0 else (w - r) / r * 100
        direction = "more" if w > r else "fewer" if w < r else "same"
        magnitude = (f" ({abs(pct):.0f}% {direction})"
                      if pct is not None and abs(pct) >= 10 else "")
        recipe_lines.append(
            f'<li style="margin:.3rem 0">'
            f'<strong>{row["Feature"]}:</strong> winners average '
            f'<strong>{w:.1f}</strong>, rest average {r:.1f} '
            f'{row["unit"]}{magnitude}.</li>')
    st.markdown(
        f'<div style="background:#EBF3F2;border-left:4px solid '
        f'{ACCENT};padding:1rem 1.3rem;border-radius:6px;'
        f'margin-bottom:1.2rem">'
        f'<div class="eyebrow" style="color:{ACCENT};'
        f'margin-bottom:.5rem">The pattern for top-quartile posts'
        f'</div>'
        f'<ul style="margin:0;padding-left:1.2rem;font-size:.92rem;'
        f'line-height:1.5;color:{INK}">{"".join(recipe_lines)}</ul>'
        f'</div>', unsafe_allow_html=True)

    # A compact comparison table
    tbl = pd.DataFrame([{
        "Feature":    r["Feature"],
        "Winners avg": round(r["Winners avg"], 1),
        "Rest avg":    round(r["Rest avg"], 1),
        "Gap":         round(r["Winners avg"] - r["Rest avg"], 1),
        "Unit":        r["unit"],
    } for r in rows])
    st.dataframe(tbl, use_container_width=True, hide_index=True)
    st.caption(f"Winners = posts in the top 25% by score "
                f"({len(winners)} of {len(scored)}). Rest = everyone "
                f"else ({len(rest)}).")
else:
    st.info("Not enough scored posts in the current filter.")


# ==========================================================================
# 2. Wins by attribute - one table per LinkedIn attribute
# ==========================================================================
st.markdown('<h2>Wins by attribute</h2>', unsafe_allow_html=True)
st.caption("For each attribute, which values top-score most often. "
            "Sort each table by average score.")

# For each attribute in FEATURES that has enough non-empty rows, build
# a rollup: attribute value -> N posts, avg score, avg engagement.
def _rollup(col):
    if col not in scored.columns:
        return None
    sub = scored[[col, "post_score"]].copy()
    sub[col] = sub[col].astype(str).str.strip()
    sub = sub[~sub[col].isin(["", "nan", "None"])]
    if len(sub) < 5:
        return None
    g = (sub.groupby(col)
             .agg(posts=("post_score", "count"),
                   avg_score=("post_score", "mean"))
             .reset_index())
    if len(g) < 2:
        return None
    g["avg_score"] = g["avg_score"].round(1)
    g = g.sort_values("avg_score", ascending=False)
    g.columns = [LABELS.get(col, col.title()), "Posts", "Avg score"]
    return g


shown = 0
for feat in FEATURES:
    tbl = _rollup(feat)
    if tbl is None:
        continue
    label = LABELS.get(feat, feat.title())
    st.markdown(f'<h3 style="margin-top:1rem">By {label.lower()}</h3>',
                 unsafe_allow_html=True)
    st.dataframe(
        tbl, use_container_width=True, hide_index=True,
        column_config={
            "Posts":     st.column_config.NumberColumn(format="%d"),
            "Avg score": st.column_config.ProgressColumn(
                min_value=0,
                max_value=float(tbl["Avg score"].max()),
                format="%.1f"),
        })
    # Auto so-what: top value + gap vs bottom
    top = tbl.iloc[0]
    bot = tbl.iloc[-1]
    if float(top["Avg score"]) - float(bot["Avg score"]) >= 5:
        so_what(
            f"<strong>{top.iloc[0]}</strong> tops this attribute at "
            f"an average score of {top['Avg score']}, vs "
            f"<strong>{bot.iloc[0]}</strong> at {bot['Avg score']}. "
            f"Publish more with the pattern that wins here.",
            tone="good")
    shown += 1

if shown == 0:
    st.info("No attribute has enough non-empty values in the current "
             "filter to compare.")


# ==========================================================================
# 3. Best vs worst posts
# ==========================================================================
st.markdown('<h2>Best vs worst posts</h2>', unsafe_allow_html=True)
st.caption("Top 10 and bottom 10 by score. Read the hooks side by "
            "side to spot what winners open with.")

top10 = scored.nlargest(10, "post_score")[
    ["date", "post_score", "hook_short", "theme", "cta_type",
      "length_band"]].copy()
bot10 = scored.nsmallest(10, "post_score")[
    ["date", "post_score", "hook_short", "theme", "cta_type",
      "length_band"]].copy()
for df_ in (top10, bot10):
    df_.columns = ["Date", "Score", "First line", "Topic", "CTA",
                    "Length"]
    df_["Score"] = df_["Score"].round(1)

tab_t, tab_b = st.tabs(["Top 10 posts", "Bottom 10 posts"])
with tab_t:
    st.dataframe(top10, use_container_width=True, hide_index=True,
                  column_config={
                      "Score": st.column_config.NumberColumn(
                          format="%.1f"),
                      "First line": st.column_config.TextColumn(
                          width="large"),
                  })
with tab_b:
    st.dataframe(bot10, use_container_width=True, hide_index=True,
                  column_config={
                      "Score": st.column_config.NumberColumn(
                          format="%.1f"),
                      "First line": st.column_config.TextColumn(
                          width="large"),
                  })
