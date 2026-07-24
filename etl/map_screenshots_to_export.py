"""
Match the SS001-SS091 screenshot-tagged rows to real posted dates in the
LinkedIn content export.

Strategy:
    1. For every SS row, take the caption body without hashtags/URLs.
    2. Do the same for every LinkedIn export row.
    3. Pick the export row with the longest matching normalised prefix
       (LinkedIn truncates captions with \\n\\r artefacts, so an exact
       equality check fails, but a normalised prefix match is reliable).
    4. Fall back to token-set similarity if prefix matching finds nothing.
    5. Report matches with a confidence flag and write the merged file.

Usage:
    python map_screenshots_to_export.py
"""

import os
import re
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")

MANUAL_CSV = os.path.join(DATA_DIR, "post_enrichment_manual.csv")
EXPORT_XLS = "C:/Users/KunalSharma/Downloads/grantsnow_content_1784612401599.xls"
OUT_CSV = os.path.join(DATA_DIR, "post_enrichment_dated.csv")

URL_RE = re.compile(r"https?://\S+")
HASHTAG_RE = re.compile(r"#\w+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
WS_RE = re.compile(r"\s+")


def norm(text):
    """Lower, strip URLs and hashtags, collapse whitespace, drop punctuation."""
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = URL_RE.sub(" ", t)
    t = HASHTAG_RE.sub(" ", t)
    t = t.replace("\r", " ").replace("\n", " ")
    t = NON_ALNUM_RE.sub(" ", t)
    return WS_RE.sub(" ", t).strip()


def tokens(text):
    return set(norm(text).split())


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def prefix_len(a, b):
    """How many characters of common prefix between two normalised strings."""
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def main():
    manual = pd.read_csv(MANUAL_CSV)
    export = pd.read_excel(EXPORT_XLS, sheet_name="All posts", header=1)
    export = export.copy()
    export["Created date"] = pd.to_datetime(
        export["Created date"], format="%m/%d/%Y", errors="coerce")

    # extract 19-digit LinkedIn post id from the Post link
    export["linkedin_post_id"] = export["Post link"].astype(str).str.extract(
        r"(\d{15,})")[0]

    # normalise both sides once
    export["norm"] = export["Post title"].astype(str).apply(norm)
    export["tok"] = export["norm"].apply(lambda s: set(s.split()))

    manual["norm"] = manual["caption"].astype(str).apply(norm)
    manual["tok"] = manual["norm"].apply(lambda s: set(s.split()))

    matches = []
    for _, m in manual.iterrows():
        best = {"linkedin_post_id": None, "posted_date": None,
                "match_score": 0.0, "match_method": "none",
                "match_impressions": None}
        m_norm = m["norm"]
        m_tok = m["tok"]
        if not m_norm or len(m_norm) < 20:
            matches.append(best)
            continue

        # strategy 1: longest prefix match, normalised strings, cap 400 chars
        m_head = m_norm[:400]
        best_prefix = 0
        best_idx = None
        for j, e_norm in enumerate(export["norm"].tolist()):
            if not e_norm or len(e_norm) < 20:
                continue
            e_head = e_norm[:400]
            p = prefix_len(m_head, e_head)
            if p > best_prefix:
                best_prefix = p
                best_idx = j

        # accept if prefix >= 60 chars of normalised text
        if best_idx is not None and best_prefix >= 60:
            row = export.iloc[best_idx]
            best = {
                "linkedin_post_id": row["linkedin_post_id"],
                "posted_date": row["Created date"],
                "match_score": round(best_prefix / max(len(m_head), 1), 3),
                "match_method": f"prefix ({best_prefix} chars)",
                "match_impressions": (int(row["Impressions"])
                                       if pd.notna(row.get("Impressions"))
                                       else None),
            }
        else:
            # strategy 2: token jaccard, threshold 0.55
            scores = export["tok"].apply(lambda t: jaccard(m_tok, t))
            j_best = scores.idxmax() if not scores.empty else None
            j_score = float(scores.max()) if not scores.empty else 0.0
            if j_best is not None and j_score >= 0.55:
                row = export.iloc[j_best]
                best = {
                    "linkedin_post_id": row["linkedin_post_id"],
                    "posted_date": row["Created date"],
                    "match_score": round(j_score, 3),
                    "match_method": f"jaccard ({j_score:.2f})",
                    "match_impressions": (int(row["Impressions"])
                                           if pd.notna(row.get("Impressions"))
                                           else None),
                }
        matches.append(best)

    match_df = pd.DataFrame(matches)
    # force linkedin_post_id to a clean string (19-digit ints lose precision as floats)
    match_df["linkedin_post_id"] = match_df["linkedin_post_id"].apply(
        lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    out = pd.concat([manual.drop(columns=["norm", "tok"]).reset_index(drop=True),
                     match_df.reset_index(drop=True)], axis=1)
    out.to_csv(OUT_CSV, index=False)

    total = len(out)
    mapped = out["linkedin_post_id"].notna().sum()
    unmapped = total - mapped
    print(f"\nMANUAL rows                 : {total}")
    print(f"EXPORT rows                 : {len(export)}")
    print(f"MAPPED (found real date)    : {mapped}  ({mapped/total:.0%})")
    print(f"UNMAPPED (no match)         : {unmapped}  ({unmapped/total:.0%})")
    print(f"\nMethod breakdown:")
    print(out["match_method"].value_counts().to_string())
    print(f"\nWritten: {OUT_CSV}")

    unmapped_ids = out[out["linkedin_post_id"].isna()]["post_id"].tolist()
    if unmapped_ids:
        print(f"\nUNMAPPED SS IDs ({len(unmapped_ids)}):")
        for i in range(0, len(unmapped_ids), 10):
            print("  " + ", ".join(unmapped_ids[i:i+10]))


if __name__ == "__main__":
    main()
