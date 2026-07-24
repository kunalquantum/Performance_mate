"""
Post scoring and diagnosis engine.

Turns raw post metrics into three things a creative team can act on:

1. a context-normalised score, so a post is judged against the page as it was that
   week, not against a conference spike
2. a failure mode, which separates a distribution problem from a hook problem from
   an offer problem
3. the attribute evidence behind the verdict

Assumptions are declared as constants at the top and are meant to be argued with.
"""

import numpy as np
import pandas as pd

# Weighted engagement. LinkedIn's 2026 ranking leans on comment velocity and dwell,
# so a comment is worth far more than a reaction as a signal of content quality.
# These weights are a judgement, not a published figure. Change them and the whole
# league table moves, which is the point.
WEIGHTS = {"Comments": 6.0, "Reposts": 4.0, "Clicks": 2.0, "Likes": 1.0}

# Rolling window used to build the baseline the post is judged against.
BASELINE_WINDOW = 7

# Diagnosis thresholds, expressed as a ratio to the post's own baseline.
HIGH = 1.15
LOW = 0.85


def add_baselines(df, window=BASELINE_WINDOW):
    """Baseline is the centred rolling median of neighbouring posts.

    This is what removes the conference-week distortion. A post published during a
    spike is compared with the other posts published during that spike, not with the
    quiet weeks either side of it.
    """
    d = df.sort_values("created_date").reset_index(drop=True).copy()
    half = window // 2
    for col, out in [("Impressions", "baseline_impressions"),
                     ("engagement_rate", "baseline_er"),
                     ("ctr", "baseline_ctr")]:
        vals = []
        for i in range(len(d)):
            lo, hi = max(0, i - half), min(len(d), i + half + 1)
            # the post is never part of its own baseline, otherwise every index
            # collapses towards 1.0 and nothing is diagnosable
            neighbours = d[col].iloc[lo:hi].drop(index=i)
            vals.append(neighbours.median() if len(neighbours) else np.nan)
        d[out] = pd.Series(vals).fillna(d[col].median())
    return d


def add_scores(df):
    d = add_baselines(df)

    d["weighted_engagements"] = sum(d[k] * w for k, w in WEIGHTS.items() if k in d.columns)
    d["quality_rate"] = d["weighted_engagements"] / d["Impressions"].replace(0, np.nan)

    d["reach_index"] = d["Impressions"] / d["baseline_impressions"].replace(0, np.nan)
    d["engagement_index"] = d["engagement_rate"] / d["baseline_er"].replace(0, np.nan)
    d["click_index"] = d["ctr"] / d["baseline_ctr"].replace(0, np.nan)

    # engagement composition, which says what kind of reaction the post provoked
    total = d[["Likes", "Comments", "Reposts", "Clicks"]].sum(axis=1).replace(0, np.nan)
    d["share_clicks"] = d["Clicks"] / total
    d["share_reactions"] = d["Likes"] / total
    d["share_conversation"] = (d["Comments"] + d["Reposts"]) / total

    # composite score: percentile rank of reach, engagement quality and click pull
    parts = []
    for col, weight in [("reach_index", 0.35), ("quality_rate", 0.45), ("click_index", 0.20)]:
        parts.append(d[col].rank(pct=True) * weight)
    d["post_score"] = (sum(parts) * 100).round(1)

    d["tier"] = pd.cut(
        d["post_score"].rank(pct=True),
        bins=[-0.01, 0.25, 0.5, 0.75, 1.01],
        labels=["Underperformer", "Below baseline", "Above baseline", "Winner"],
    ).astype(str)

    # CTR above this is almost never link clicks. It is gallery, document or
    # "see more" expands being counted as clicks. Flagged so nobody optimises for it.
    d["click_anomaly"] = d["ctr"] > 0.35

    d["failure_mode"] = d.apply(diagnose, axis=1)
    d["fix"] = d["failure_mode"].map(FIXES)
    return d


DIAGNOSES = {
    "full_win": "Won on both reach and engagement",
    "distribution": "Content landed, distribution did not",
    "hook": "Got shown, failed to hold attention",
    "offer": "Held attention, nobody clicked",
    "click_only": "Clicks without conversation",
    "flat": "Below baseline on every axis",
    "par": "At baseline, no signal either way",
}

FIXES = {
    "full_win": "Rebuild this shape. Same theme, same length band, same day and slot. "
                "This is the template for the next three posts.",
    "distribution": "The writing is fine. Move the publish slot into the prime window "
                    "for the target region, and get the team reacting inside the first "
                    "60 minutes. Check whether it went out on a day the page already "
                    "posted on.",
    "hook": "The first line is doing no work. Rewrite the opening so it names a "
            "specific situation the reader recognises before the scroll. Also check "
            "the image, a generic graphic kills a good post.",
    "offer": "People read it and stopped. The call to action is either buried, vague, "
             "or asking for too much. Make it one clear action and put it on its own "
             "line.",
    "click_only": "Clicks came without comments or reposts, which the algorithm barely "
                  "rewards. Add one open question at the end so there is something to "
                  "reply to.",
    "flat": "Nothing worked. Do not iterate on this one, retire the format and the "
            "angle.",
    "par": "Sat at baseline. Not a failure, not a lesson. Needs a sharper angle to "
           "produce a readable result.",
}


def diagnose(r):
    reach, eng, click = r["reach_index"], r["engagement_index"], r["click_index"]
    if any(pd.isna(x) for x in (reach, eng)):
        return "par"
    if reach >= HIGH and eng >= HIGH:
        return "full_win"
    if reach <= LOW and eng >= HIGH:
        return "distribution"
    if reach >= HIGH and eng <= LOW:
        return "hook"
    if eng >= HIGH and not pd.isna(click) and click <= LOW:
        return "offer"
    if not pd.isna(click) and click >= HIGH and r.get("share_conversation", 0) < 0.05:
        return "click_only"
    if reach <= LOW and eng <= LOW:
        return "flat"
    return "par"


# ---------------------------------------------------------------------------
# attribute evidence
# ---------------------------------------------------------------------------

def attribute_lift(df, features, metric="post_score", min_n=1):
    """Median outcome per attribute value, against the page median.

    Returns a frame with an explicit confidence flag. At small sample sizes the flag
    matters more than the number.
    """
    overall = df[metric].median()
    rows = []
    for f in features:
        if f not in df.columns:
            continue
        s = df.dropna(subset=[f])
        s = s[s[f].astype(str).str.strip().replace("nan", "") != ""]
        for value, grp in s.groupby(f):
            n = len(grp)
            if n < min_n:
                continue
            med = grp[metric].median()
            rows.append({
                "attribute": f,
                "value": str(value),
                "posts": n,
                "median": med,
                "lift": (med / overall - 1) if overall else np.nan,
                "confidence": "solid" if n >= 5 else ("worth a test" if n >= 3 else "one-off"),
            })
    return pd.DataFrame(rows).sort_values("lift", ascending=False)


def explain_post(row, lift_table, features):
    """Plain-language reasons a specific post scored where it did."""
    reasons = []
    for f in features:
        if f not in row.index:
            continue
        val = str(row[f])
        hit = lift_table[(lift_table["attribute"] == f) & (lift_table["value"] == val)]
        if hit.empty:
            continue
        h = hit.iloc[0]
        if abs(h["lift"]) < 0.15:
            continue
        direction = "helped" if h["lift"] > 0 else "hurt"
        reasons.append({
            "factor": f,
            "value": val,
            "effect": direction,
            "lift": h["lift"],
            "posts": int(h["posts"]),
            "confidence": h["confidence"],
        })
    return sorted(reasons, key=lambda r: -abs(r["lift"]))


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "can", "may", "might", "must", "shall", "this", "that", "these",
    "those", "it", "its", "we", "our", "us", "you", "your", "yours", "they",
    "their", "them", "he", "she", "his", "her", "who", "what", "when", "where",
    "why", "how", "which", "so", "than", "then", "just", "not", "no", "up",
    "out", "over", "under", "into", "about", "any", "all", "each", "every",
    "one", "two", "three", "more", "most", "some", "such", "only", "own",
    "same", "very", "s", "t", "d", "ll", "re", "ve", "m", "am", "i", "get",
    "got", "make", "made", "take", "took", "put", "let", "also", "here",
    "there", "now", "new", "still",
}


def _tokens(text):
    import re as _re
    if not isinstance(text, str):
        return []
    text = _re.sub(r"https?://\S+", " ", text.lower())
    text = _re.sub(r"[^a-z0-9\s]", " ", text)
    return [w for w in text.split() if len(w) > 2 and w not in STOPWORDS]


def top_keywords(df, top_share=0.25, n=20):
    """Words that appear more in the top posts than the bottom posts.

    Returns a frame with the count in the top group, count in the bottom group,
    and a distinctiveness figure that is simply top rate minus bottom rate. A
    positive figure means the word is more common in winners than losers.
    """
    if "post_text" not in df.columns:
        return pd.DataFrame()
    k = max(int(len(df) * top_share), 3)
    top = df.nlargest(k, "post_score")
    bot = df.nsmallest(k, "post_score")

    def counts(frame):
        c = {}
        for t in frame["post_text"].fillna(""):
            for w in set(_tokens(t)):  # count posts containing the word, not raw freq
                c[w] = c.get(w, 0) + 1
        return c

    tc, bc = counts(top), counts(bot)
    rows = []
    for w, ct in tc.items():
        cb = bc.get(w, 0)
        rows.append({
            "word": w,
            "top posts": ct,
            "bottom posts": cb,
            "top rate": ct / len(top),
            "bottom rate": cb / len(bot),
            "distinctiveness": ct / len(top) - cb / len(bot),
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out = out[out["distinctiveness"] > 0].sort_values("distinctiveness", ascending=False)
    return out.head(n).reset_index(drop=True)


def suggest_hashtags_for_topic(df, topic, top_n=10, curated=None,
                                min_posts=2):
    """Recommend hashtags for a specific topic.

    Score = mean_post_score * log(count + 1). Rewards hashtags that both
    appear in high-scoring posts and appear multiple times (not one-offs).
    Optional curated list gets a 1.5x score boost.

    Returns a DataFrame with columns: hashtag, count, avg_score,
    recommendation_score, in_curated (if curated provided).
    """
    if "hashtag_list" not in df.columns or "theme" not in df.columns:
        return pd.DataFrame()

    topic_posts = df[df["theme"] == topic].copy()
    if topic_posts.empty:
        return pd.DataFrame()

    rows = []
    for _, r in topic_posts.iterrows():
        tags_raw = str(r.get("hashtag_list", ""))
        if tags_raw in ("nan", "", "None"):
            continue
        for t in tags_raw.split(","):
            t = t.strip().lstrip("#").strip()
            if t and t.lower() != "nan":
                rows.append({
                    "hashtag": "#" + t,
                    "post_score": float(r.get("post_score", 0) or 0),
                })
    if not rows:
        return pd.DataFrame()

    tag_df = pd.DataFrame(rows)
    agg = (tag_df.groupby("hashtag")
                  .agg(count=("hashtag", "count"),
                       avg_score=("post_score", "mean"))
                  .reset_index())
    agg = agg[agg["count"] >= min_posts]
    if agg.empty:
        return pd.DataFrame()

    agg["recommendation_score"] = (
        agg["avg_score"] * np.log(agg["count"] + 1))

    if curated is not None and len(curated) > 0:
        curated_lower = {c.strip().lstrip("#").lower() for c in curated
                          if str(c).strip()}
        agg["in_curated"] = agg["hashtag"].str.lstrip("#").str.lower().isin(
            curated_lower)
        agg["recommendation_score"] = agg["recommendation_score"] * (
            agg["in_curated"].map({True: 1.5, False: 1.0}))
    else:
        agg["in_curated"] = False

    return (agg.sort_values("recommendation_score", ascending=False)
               .head(top_n)
               .reset_index(drop=True))


def suggest_hashtags_global(df, top_n=15, curated=None, min_posts=3):
    """Cross-topic recommender used when no topic is picked. Same scoring."""
    if "hashtag_list" not in df.columns:
        return pd.DataFrame()

    rows = []
    for _, r in df.iterrows():
        tags_raw = str(r.get("hashtag_list", ""))
        if tags_raw in ("nan", "", "None"):
            continue
        for t in tags_raw.split(","):
            t = t.strip().lstrip("#").strip()
            if t and t.lower() != "nan":
                rows.append({
                    "hashtag": "#" + t,
                    "post_score": float(r.get("post_score", 0) or 0),
                })
    if not rows:
        return pd.DataFrame()

    tag_df = pd.DataFrame(rows)
    agg = (tag_df.groupby("hashtag")
                  .agg(count=("hashtag", "count"),
                       avg_score=("post_score", "mean"))
                  .reset_index())
    agg = agg[agg["count"] >= min_posts]
    if agg.empty:
        return pd.DataFrame()

    agg["recommendation_score"] = (
        agg["avg_score"] * np.log(agg["count"] + 1))

    if curated is not None and len(curated) > 0:
        curated_lower = {c.strip().lstrip("#").lower() for c in curated
                          if str(c).strip()}
        agg["in_curated"] = agg["hashtag"].str.lstrip("#").str.lower().isin(
            curated_lower)
        agg["recommendation_score"] = agg["recommendation_score"] * (
            agg["in_curated"].map({True: 1.5, False: 1.0}))
    else:
        agg["in_curated"] = False

    return (agg.sort_values("recommendation_score", ascending=False)
               .head(top_n)
               .reset_index(drop=True))


def load_hashtag_library(uploaded_file):
    """Read the structured GrantsNow hashtag workbook.

    Expected layout: one sheet per category (plus a How-To sheet that gets
    skipped). Each category sheet has header row 'Hashtag | Reach Tier | Segment'
    (possibly with extra columns like Evergreen/Trending, Notes) and rows below
    with '#tag', tier ('Large' / 'Medium' / 'Small'), and segment
    ('Broad reach' / 'Mid-tier niche' / 'Highly targeted').

    Returns:
        {
            "categories": {
                "Grants Management": [
                    {"hashtag": "#Funding", "tier": "Large",
                     "segment": "Broad reach"},
                    ...
                ],
                ...
            },
            "all_hashtags": ["Funding", "Grants", ...],   # for backward compat
        }
    """
    if uploaded_file is None:
        return {"categories": {}, "all_hashtags": []}
    try:
        xl = pd.read_excel(uploaded_file, sheet_name=None, header=None)
    except Exception:
        return {"categories": {}, "all_hashtags": []}

    SKIP_SHEETS = {"how to use", "read me & best practice", "readme",
                   "how_to_use", "instructions"}
    categories = {}
    all_tags = []

    for sheet_name, df_raw in xl.items():
        if sheet_name.strip().lower() in SKIP_SHEETS:
            continue
        # find header row (first row where the first column reads "Hashtag")
        header_idx = None
        for i, row in df_raw.iterrows():
            if str(row.iloc[0]).strip().lower() == "hashtag":
                header_idx = i
                break
        if header_idx is None:
            continue
        header = [str(v).strip() for v in df_raw.iloc[header_idx].tolist()]
        body = df_raw.iloc[header_idx + 1:].copy()
        body.columns = header + [f"_extra_{i}" for i in range(len(body.columns)
                                                                - len(header))]
        # keep rows whose first column is a real hashtag
        body = body[body["Hashtag"].astype(str).str.strip().str.startswith("#")]
        if body.empty:
            continue
        entries = []
        for _, r in body.iterrows():
            tag = str(r["Hashtag"]).strip()
            tier = str(r.get("Reach Tier", "")).strip()
            segment = str(r.get("Segment", "")).strip()
            if tag.lower() == "nan" or not tag.startswith("#"):
                continue
            entries.append({
                "hashtag": tag, "tier": tier, "segment": segment,
                "category": sheet_name,
            })
            all_tags.append(tag.lstrip("#"))
        if entries:
            categories[sheet_name] = entries

    # dedupe all_tags preserving order
    seen = set()
    unique_all = []
    for t in all_tags:
        low = t.lower()
        if low not in seen:
            seen.add(low)
            unique_all.append(t)

    return {"categories": categories, "all_hashtags": unique_all}


# Map from our topic classifier to the categories in the workbook. Multiple
# categories can back one topic; the suggester pools their hashtags.
TOPIC_TO_CATEGORY = {
    "pain_point": ["Grants Management", "Research Administration",
                    "Research Impact & Compliance"],
    "product_capability": ["GrantsTech & Research Software",
                           "Grants Management"],
    "event_presence": ["Higher Ed & Universities", "Research Administration",
                        "General B2B & Thought Lead"],
    "thought_leadership": ["General B2B & Thought Lead", "Research Funding",
                            "Research Impact & Compliance"],
    "community_celebration": ["Higher Ed & Universities",
                                "General B2B & Thought Lead"],
    "other": ["Grants Management"],
}


def _norm_segment(s):
    s = (s or "").strip().lower()
    if "broad" in s:
        return "Broad reach"
    if "mid" in s or "niche" in s:
        return "Mid-tier niche"
    if "target" in s or "highly" in s:
        return "Highly targeted"
    return ""


_TIER_PRIORITY = {"large": 3, "medium": 2, "small": 1}


def suggest_hashtags_from_library(library, topic, past_posts=None,
                                   include_grantsnow=True,
                                   category_override=None):
    """Apply the GrantsNow playbook: 1 Broad + 2 Mid-tier + 1 Targeted + #GrantsNow.

    library : dict from load_hashtag_library
    topic   : one of the theme values (pain_point, product_capability, ...)
    past_posts : optional scored dataframe. Hashtags used by higher-scoring
                 past posts float up in their segment. Unproven hashtags use
                 the topic's own median score as the neutral baseline, so
                 they compete fairly rather than getting an arbitrary boost.
    category_override : list of category names to use instead of the default
                        TOPIC_TO_CATEGORY mapping. Set from the UI.
    """
    if not library or not library.get("categories"):
        return pd.DataFrame()

    categories_for_topic = (category_override if category_override
                             else TOPIC_TO_CATEGORY.get(
                                 topic, ["Grants Management"]))
    # pool of candidate hashtags from the mapped categories
    pool = []
    seen = set()
    for cat in categories_for_topic:
        for entry in library["categories"].get(cat, []):
            key = entry["hashtag"].lower()
            if key in seen:
                continue
            seen.add(key)
            pool.append({
                "hashtag": entry["hashtag"],
                "segment": _norm_segment(entry.get("segment", "")),
                "tier": entry.get("tier", ""),
                "category": entry.get("category", ""),
                "past_avg_score": np.nan,
                "past_count": 0,
            })
    if not pool:
        return pd.DataFrame()

    # compute the topic-specific baseline: median score of past posts on this
    # topic. Unproven hashtags get this baseline rather than an arbitrary 50.
    topic_baseline = 50.0
    if past_posts is not None and "post_score" in past_posts.columns \
            and "theme" in past_posts.columns:
        topic_rows = past_posts[past_posts["theme"] == topic]
        if not topic_rows.empty and topic_rows["post_score"].notna().any():
            topic_baseline = float(topic_rows["post_score"].median())

    # add historical performance if available
    if past_posts is not None and "hashtag_list" in past_posts.columns:
        rows = []
        for _, r in past_posts.iterrows():
            tags_raw = str(r.get("hashtag_list", ""))
            if tags_raw in ("nan", "", "None"):
                continue
            for t in tags_raw.split(","):
                t = t.strip().lstrip("#").strip().lower()
                if t and t != "nan":
                    rows.append({"key": t,
                                 "post_score": float(r.get("post_score", 0)
                                                      or 0)})
        if rows:
            past = pd.DataFrame(rows).groupby("key").agg(
                past_avg_score=("post_score", "mean"),
                past_count=("post_score", "count"),
            ).reset_index()
            for p in pool:
                key = p["hashtag"].lstrip("#").lower()
                hit = past[past["key"] == key]
                if not hit.empty:
                    p["past_avg_score"] = float(hit.iloc[0]["past_avg_score"])
                    p["past_count"] = int(hit.iloc[0]["past_count"])

    df = pd.DataFrame(pool)
    # primary rank: past avg where available, else topic baseline.
    df["_primary_rank"] = df["past_avg_score"].fillna(topic_baseline)
    # secondary rank: workbook tier (Large > Medium > Small). Acts as a
    # tiebreaker among unproven tags at the same primary score.
    df["_tier_rank"] = df["tier"].astype(str).str.strip().str.lower().map(
        _TIER_PRIORITY).fillna(0).astype(int)

    picked = []

    def _take_top(segment_name, n):
        sub = df[df["segment"] == segment_name].sort_values(
            ["_primary_rank", "_tier_rank"], ascending=[False, False])
        # never repeat what we've already picked
        sub = sub[~sub["hashtag"].str.lower().isin(
            {p["hashtag"].lower() for p in picked})]
        return sub.head(n).to_dict("records")

    for h in _take_top("Broad reach", 1):
        h["playbook_role"] = "Broad reach"
        picked.append(h)
    for h in _take_top("Mid-tier niche", 2):
        h["playbook_role"] = "Mid-tier niche"
        picked.append(h)
    for h in _take_top("Highly targeted", 1):
        h["playbook_role"] = "Highly targeted"
        picked.append(h)

    if include_grantsnow:
        if not any(p["hashtag"].lower() == "#grantsnow" for p in picked):
            picked.append({
                "hashtag": "#GrantsNow", "segment": "Brand",
                "tier": "", "category": "brand-anchor",
                "past_avg_score": np.nan, "past_count": 0,
                "_primary_rank": 0.0, "_tier_rank": 0,
                "playbook_role": "Brand anchor",
            })

    result = pd.DataFrame(picked)
    if result.empty:
        return result
    result = result.drop(columns=["_primary_rank", "_tier_rank"],
                         errors="ignore")
    return result[["hashtag", "playbook_role", "segment", "tier",
                    "category", "past_avg_score", "past_count"]]


def load_curated_hashtags(uploaded_file):
    """Read a curated hashtag list from CSV or Excel. Auto-detects the column
    (first column with strings containing '#' or all rows starting with '#').
    Returns a list of hashtag strings (without leading #)."""
    import io
    if uploaded_file is None:
        return []
    name = getattr(uploaded_file, "name", "").lower()
    try:
        if name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
    except Exception:
        return []
    if df.empty:
        return []
    # find the column that looks like it holds hashtags
    for col in df.columns:
        vals = df[col].dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        if vals.empty:
            continue
        with_hash = vals.str.startswith("#").sum()
        alpha_word = vals.str.match(r"^[A-Za-z0-9_]+$").sum()
        if with_hash >= len(vals) * 0.5 or alpha_word >= len(vals) * 0.5:
            return [v.lstrip("#").strip() for v in vals.tolist()
                    if v.lstrip("#").strip()]
    # fallback: use the first non-empty column
    for col in df.columns:
        vals = df[col].dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        if not vals.empty:
            return [v.lstrip("#").strip() for v in vals.tolist()
                    if v.lstrip("#").strip()]
    return []


def top_hashtags(df, top_share=0.25, n=15):
    if "hashtag_list" not in df.columns:
        return pd.DataFrame()
    k = max(int(len(df) * top_share), 3)
    top = df.nlargest(k, "post_score")
    bot = df.nsmallest(k, "post_score")

    def counts(frame):
        c = {}
        for h in frame["hashtag_list"].fillna(""):
            for tag in [t.strip() for t in str(h).split(",") if t.strip()]:
                c[tag] = c.get(tag, 0) + 1
        return c

    tc, bc = counts(top), counts(bot)
    rows = []
    for tag, ct in tc.items():
        cb = bc.get(tag, 0)
        rows.append({
            "hashtag": "#" + tag,
            "top posts": ct,
            "bottom posts": cb,
            "distinctiveness": ct / len(top) - cb / len(bot),
        })
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows).sort_values("distinctiveness", ascending=False)
            .head(n).reset_index(drop=True))


def micro_attribute_table(df, top_share=0.25):
    """Side-by-side comparison of micro-level details, top posts vs bottom posts."""
    k = max(int(len(df) * top_share), 3)
    top = df.nlargest(k, "post_score")
    bot = df.nsmallest(k, "post_score")

    def num(frame, col):
        return frame[col].median() if col in frame.columns else None

    def rate(frame, col):
        if col not in frame.columns:
            return None
        s = pd.to_numeric(frame[col], errors="coerce")
        return s.fillna(0).astype(bool).mean()

    def mode(frame, col):
        if col not in frame.columns:
            return None
        s = frame[col].astype(str).str.strip().replace("nan", "")
        s = s[s != ""]
        return s.mode().iloc[0] if not s.empty else None

    def band(frame, col):
        if col not in frame.columns:
            return None
        s = frame[col].dropna()
        if s.empty:
            return None
        return f"{int(s.quantile(0.25))} to {int(s.quantile(0.75))}"

    rows = [
        ("Word count (median)",       num(top, "word_count"),      num(bot, "word_count")),
        ("Word count (middle range)", band(top, "word_count"),     band(bot, "word_count")),
        ("First line length (chars)", num(top, "hook_len"),        num(bot, "hook_len")),
        ("Hashtags (median)",         num(top, "hashtag_count"),   num(bot, "hashtag_count")),
        ("Emojis (median)",           num(top, "emoji_count"),     num(bot, "emoji_count")),
        ("Mentions (median)",         num(top, "mention_count"),   num(bot, "mention_count")),
        ("Line breaks (median)",      num(top, "line_breaks"),     num(bot, "line_breaks")),
        ("Ask a question",            rate(top, "has_question"),   rate(bot, "has_question")),
        ("Include a link",            rate(top, "has_link"),       rate(bot, "has_link")),
        ("Most common topic",         mode(top, "theme"),          mode(bot, "theme")),
        ("Most common format",        mode(top, "format_inferred"), mode(bot, "format_inferred")),
        ("Most common ask",           mode(top, "cta_type"),       mode(bot, "cta_type")),
        ("Most common length band",   mode(top, "length_band"),    mode(bot, "length_band")),
        ("Most common publish day",   mode(top, "day_of_week"),    mode(bot, "day_of_week")),
    ]

    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            if 0 <= v <= 1 and v != int(v):
                return f"{v * 100:.0f}%"
            return f"{v:.1f}"
        return str(v)

    return pd.DataFrame([{"Detail": r[0], "Top posts": fmt(r[1]), "Bottom posts": fmt(r[2])}
                         for r in rows])


def build_brief(df, features, top_share=0.25):
    """Derive the next-post spec from what is actually winning."""
    n = max(int(len(df) * top_share), 3)
    top = df.nlargest(n, "post_score")
    bottom = df.nsmallest(n, "post_score")

    spec = {}
    for f in features:
        if f not in df.columns:
            continue
        s = top[f].astype(str)
        s = s[s.str.strip().replace("nan", "") != ""]
        if s.empty:
            continue
        m = s.mode()
        if m.empty:
            continue
        spec[f] = m.iloc[0]

    spec["word_count"] = f"{int(top['word_count'].quantile(0.25))} to {int(top['word_count'].quantile(0.75))}"
    spec["hashtag_count"] = int(round(top["hashtag_count"].median()))
    spec["hook_len"] = f"under {int(top['hook_len'].quantile(0.75))} characters"

    tags = (top.assign(t=top["hashtag_list"].fillna("").str.split(", ")).explode("t"))
    tags = tags[tags["t"].str.strip() != ""]
    spec["hashtags"] = ", ".join(tags["t"].value_counts().head(5).index)

    avoid = {}
    for f in features:
        if f not in df.columns:
            continue
        s = bottom[f].astype(str)
        s = s[s.str.strip().replace("nan", "") != ""]
        if s.empty:
            continue
        m = s.mode()
        if m.empty:
            continue
        v = m.iloc[0]
        if spec.get(f) != v:
            avoid[f] = v

    return spec, avoid, top, bottom
