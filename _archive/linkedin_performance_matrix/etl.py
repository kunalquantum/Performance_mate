"""
LinkedIn export -> clean CSV ETL for the GrantsNow performance matrix MVP.

Reads the raw LinkedIn analytics exports (content, followers, visitors, competitors)
and writes flat, analysis-ready CSVs into ./data.

Run:  python etl.py --src /path/to/raw/exports --out ./data
"""

import argparse
import glob
import os
import re
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

EMOJI_RE = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f1e6-\U0001f1ff" "]",
    flags=re.UNICODE,
)
HASHTAG_RE = re.compile(r"#(\w+)")
URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@\w+")

CTA_PATTERNS = {
    "download": r"\bdownload\b",
    "book_demo": r"\bbook a demo\b|\bschedule a demo\b|\bget a demo\b",
    "learn_more": r"\blearn (more|how)\b|\bdiscover how\b|\bfind out\b",
    "read": r"\bread (more|the)\b|\bexplore\b",
    "register": r"\bregister\b|\bsign up\b|\bjoin us\b",
    "contact": r"\bcontact us\b|\bget in touch\b|\btalk to us\b",
}


def _read(path, sheet, header):
    return pd.read_excel(path, sheet_name=sheet, header=header)


def _find(src, pattern):
    hits = sorted(glob.glob(os.path.join(src, pattern)))
    return hits


def _pick_largest(paths):
    """LinkedIn exports repeat; keep the file with the most rows of history."""
    if not paths:
        return None
    return max(paths, key=os.path.getsize)


# ----------------------------------------------------------------------------
# content: daily metrics + post level
# ----------------------------------------------------------------------------


def build_daily(paths):
    frames = []
    for p in paths:
        try:
            d = _read(p, "Metrics", 1)
        except Exception:
            continue
        d["Date"] = pd.to_datetime(d["Date"], format="%m/%d/%Y", errors="coerce")
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).dropna(subset=["Date"])
    out = out.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    out.columns = [c.strip() for c in out.columns]
    return out.reset_index(drop=True)


def classify_cta(text):
    t = text.lower()
    for name, pat in CTA_PATTERNS.items():
        if re.search(pat, t):
            return name
    return "none"


def classify_theme(text):
    """Coarse topic buckets. Edit these rules as the content strategy evolves."""
    t = text.lower()
    rules = [
        ("event_presence", r"\barma\b|\bconference\b|\bbooth\b|\bdesk\b|\bpub quiz\b|\bstand\b"),
        ("product_capability", r"\brole-based\b|\bai\b|\bsingle proposal record\b|\bdashboard\b|\bautomat"),
        ("pain_point", r"\bmanual\b|\bspreadsheet\b|\bemail\b|\brework\b|\bdisconnect|\bslowing\b|\bbottleneck\b"),
        ("thought_leadership", r"\bwhitepaper\b|\bwhite paper\b|\bresearch\b|\breport\b|\bguide\b"),
        ("community_celebration", r"\bcongratulations\b|\bwinning\b|\baward\b|\bwelcome\b|\bthank\b"),
    ]
    for name, pat in rules:
        if re.search(pat, t):
            return name
    return "other"


def build_posts(paths):
    frames = []
    for p in paths:
        try:
            d = _read(p, "All posts", 1)
        except Exception:
            continue
        frames.append(d)
    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames)
    df.columns = [c.strip() for c in df.columns]
    df = df.drop_duplicates(subset=["Post link"], keep="first").reset_index(drop=True)

    df["created_date"] = pd.to_datetime(df["Created date"], format="%m/%d/%Y", errors="coerce")
    df["post_text"] = df["Post title"].fillna("").astype(str)

    # ---- macro engagement fields -------------------------------------------
    for col in ["Impressions", "Clicks", "Likes", "Comments", "Reposts"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["reactions_total"] = df["Likes"] + df["Comments"] + df["Reposts"]
    df["engagements_total"] = df["reactions_total"] + df["Clicks"]
    df["engagement_rate"] = pd.to_numeric(df["engagements_total"] / df["Impressions"].replace(0, pd.NA), errors="coerce")
    df["ctr"] = pd.to_numeric(df["Clicks"] / df["Impressions"].replace(0, pd.NA), errors="coerce")
    df["amplification_rate"] = pd.to_numeric(df["Reposts"] / df["Impressions"].replace(0, pd.NA), errors="coerce")
    df["conversation_rate"] = pd.to_numeric(df["Comments"] / df["Impressions"].replace(0, pd.NA), errors="coerce")

    # ---- micro content features (derived from the post copy) ---------------
    df["char_count"] = df["post_text"].str.len()
    df["word_count"] = df["post_text"].str.split().str.len().fillna(0).astype(int)
    df["line_breaks"] = df["post_text"].str.count("\n")
    df["hashtags"] = df["post_text"].apply(lambda t: HASHTAG_RE.findall(t))
    df["hashtag_count"] = df["hashtags"].str.len()
    df["hashtag_list"] = df["hashtags"].apply(lambda h: ", ".join(h))
    df["has_link"] = df["post_text"].str.contains(URL_RE).astype(int)
    df["mention_count"] = df["post_text"].apply(lambda t: len(MENTION_RE.findall(t)))
    df["emoji_count"] = df["post_text"].apply(lambda t: len(EMOJI_RE.findall(t)))
    df["has_question"] = df["post_text"].str.contains(r"\?").astype(int)
    df["cta_type"] = df["post_text"].apply(classify_cta)
    df["theme"] = df["post_text"].apply(classify_theme)
    df["hook"] = df["post_text"].str.split("\n").str[0].str.slice(0, 120)
    df["hook_len"] = df["hook"].str.len()

    # length bands used across the dashboard
    df["length_band"] = pd.cut(
        df["word_count"],
        bins=[-1, 25, 60, 120, 10000],
        labels=["Very short (<25w)", "Short (25-60w)", "Medium (60-120w)", "Long (120w+)"],
    ).astype(str)

    # format: LinkedIn only labels articles, so infer the rest
    def fmt(row):
        if str(row.get("Content Type", "")).strip().lower() == "article":
            return "Article"
        if pd.notna(row.get("Views")) and row.get("Views", 0) > 0:
            return "Video or document"
        return "Image or text"

    df["format_inferred"] = df.apply(fmt, axis=1)

    # timing: the export carries date only, hour comes from the enrichment file
    df["day_of_week"] = df["created_date"].dt.day_name()
    df["week"] = df["created_date"].dt.to_period("W").astype(str)
    df["is_midweek"] = df["day_of_week"].isin(["Tuesday", "Wednesday", "Thursday"]).astype(int)

    df["post_id"] = df["Post link"].str.extract(r"(\d{15,})")[0]
    df["post_id"] = df["post_id"].fillna(pd.Series(df.index).astype(str))

    keep = [
        "post_id", "Post link", "post_text", "hook", "hook_len", "created_date",
        "day_of_week", "week", "is_midweek", "Post type", "format_inferred",
        "Content Type", "Impressions", "Views", "Clicks", "Likes", "Comments",
        "Reposts", "reactions_total", "engagements_total", "engagement_rate",
        "ctr", "amplification_rate", "conversation_rate", "char_count",
        "word_count", "line_breaks", "hashtag_count", "hashtag_list", "has_link",
        "mention_count", "emoji_count", "has_question", "cta_type", "theme",
        "length_band",
    ]
    keep = [c for c in keep if c in df.columns]
    return df[keep].sort_values("created_date").reset_index(drop=True)


# ----------------------------------------------------------------------------
# followers / visitors / competitors
# ----------------------------------------------------------------------------


def build_followers(path):
    out = {}
    daily = _read(path, "New followers", 0)
    daily["Date"] = pd.to_datetime(daily["Date"], format="%m/%d/%Y", errors="coerce")
    out["followers_daily"] = daily.dropna(subset=["Date"])
    for sheet, key in [
        ("Location", "followers_location"),
        ("Job function", "followers_jobfunction"),
        ("Seniority", "followers_seniority"),
        ("Industry", "followers_industry"),
        ("Company size", "followers_companysize"),
    ]:
        d = _read(path, sheet, 0)
        d.columns = ["dimension", "followers"]
        out[key] = d.dropna()
    return out


def build_visitors(path):
    out = {}
    daily = _read(path, "Visitor metrics", 0)
    daily["Date"] = pd.to_datetime(daily["Date"], format="%m/%d/%Y", errors="coerce")
    out["visitors_daily"] = daily.dropna(subset=["Date"])
    for sheet, key in [
        ("Location", "visitors_location"),
        ("Job function", "visitors_jobfunction"),
        ("Seniority", "visitors_seniority"),
        ("Industry", "visitors_industry"),
        ("Company size", "visitors_companysize"),
    ]:
        d = _read(path, sheet, 0)
        d.columns = ["dimension", "views"]
        out[key] = d.dropna()
    return out


def build_competitors(path):
    d = _read(path, "COMPETITORS", 1)
    d = d.dropna(subset=["Page"])
    for c in ["New Followers", "Posts", "Comments", "Reactions"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    d["engagements"] = d.get("Reactions", 0) + d.get("Comments", 0)
    d["engagements_per_post"] = pd.to_numeric(d["engagements"] / d["Posts"].replace(0, pd.NA), errors="coerce")
    return d


def build_enrichment_template(posts, out_dir):
    """Blank tagging sheet for the parameters LinkedIn does not export."""
    t = posts[["post_id", "created_date", "hook"]].copy()
    t["post_time_local"] = ""          # HH:MM the post actually went out
    t["timezone"] = ""                 # e.g. Europe/London, Asia/Kolkata
    t["target_region"] = ""            # UK, India, US, Global
    t["media_type"] = ""               # image, carousel, video, document, text, poll
    t["image_subject"] = ""            # people, product screenshot, event photo, abstract, quote card
    t["image_colour_theme"] = ""       # brand teal, gold, dark, light, photographic
    t["has_face_in_image"] = ""        # yes / no
    t["text_on_image"] = ""            # yes / no
    t["headline_on_image"] = ""        # the exact headline burnt into the graphic
    t["video_length_sec"] = ""
    t["video_topic"] = ""
    t["video_has_captions"] = ""       # yes / no
    t["campaign"] = ""                 # whitepaper, ARMA, demo push
    t["notes"] = ""
    path = os.path.join(out_dir, "post_enrichment_template.csv")
    t.to_csv(path, index=False)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/mnt/user-data/uploads")
    ap.add_argument("--out", default="./data")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    content_paths = _find(args.src, "*content*.xls*")
    follower_path = _pick_largest(_find(args.src, "*follower*.xls*"))
    visitor_path = _pick_largest(_find(args.src, "*visitor*.xls*"))
    comp_path = _pick_largest(_find(args.src, "*competitor*.xls*"))

    written = []

    daily = build_daily(content_paths)
    if not daily.empty:
        daily.to_csv(os.path.join(args.out, "daily_metrics.csv"), index=False)
        written.append(("daily_metrics.csv", len(daily)))

    posts = build_posts(content_paths)
    if not posts.empty:
        posts.to_csv(os.path.join(args.out, "posts.csv"), index=False)
        written.append(("posts.csv", len(posts)))
        p = build_enrichment_template(posts, args.out)
        written.append((os.path.basename(p), len(posts)))

    if follower_path:
        for k, v in build_followers(follower_path).items():
            v.to_csv(os.path.join(args.out, f"{k}.csv"), index=False)
            written.append((f"{k}.csv", len(v)))

    if visitor_path:
        for k, v in build_visitors(visitor_path).items():
            v.to_csv(os.path.join(args.out, f"{k}.csv"), index=False)
            written.append((f"{k}.csv", len(v)))

    if comp_path:
        c = build_competitors(comp_path)
        c.to_csv(os.path.join(args.out, "competitors.csv"), index=False)
        written.append(("competitors.csv", len(c)))

    print("Written to", os.path.abspath(args.out))
    for name, n in written:
        print(f"  {name:38s} {n:5d} rows")


if __name__ == "__main__":
    main()
