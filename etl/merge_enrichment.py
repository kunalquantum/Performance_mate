"""
Collapse the 91 SS rows into one row per real LinkedIn post, then merge those
tags into posts.csv so the matrix picks up the visual dimensions.

Pipeline:
    1. Read post_enrichment_dated.csv (91 rows, tagged from screenshots).
    2. Collapse by linkedin_post_id -> 66 unique posts. Duplicate SS rows for
       the same LinkedIn post become one merged row with slide_count.
    3. Read posts.csv (from etl.py, one row per LinkedIn post).
    4. Left-merge the collapsed enrichment onto posts.csv by post_id.
    5. Back up posts.csv first, then write the merged file back in place.

Fields the app expects (from FEATURES / LABELS in app.py) get normalised so
they slot into the existing attribute analysis without any app changes.

Usage:
    python merge_enrichment.py
"""

import os
import shutil
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DATED_CSV = os.path.join(DATA_DIR, "post_enrichment_dated.csv")
POSTS_CSV = os.path.join(DATA_DIR, "posts.csv")
BACKUP_CSV = os.path.join(DATA_DIR, "posts_before_visual_merge.csv")


def _yn(value):
    """Normalise 'yes'/'no'/'partial' -> yes/no; the app's FEATURES flag expects
    a clean binary. 'partial' collapses to 'yes' - if a face is visible at all,
    it counts."""
    if not isinstance(value, str):
        return ""
    v = value.strip().lower()
    if v.startswith("y"):
        return "yes"
    if v.startswith("n"):
        return "no"
    if v.startswith("partial"):
        return "yes"
    return v


def _region_from_campaign(campaign, angle):
    """Derive target_region from the campaign string. Keeps the app's target_region
    FEATURE column populated even though we tagged it inconsistently."""
    c = (str(campaign) + " " + str(angle)).lower()
    if any(k in c for k in ("k-12", "k12", "u.s.", " us ", "united states", "ngi")):
        return "US"
    if any(k in c for k in ("uk", "arma", "united kingdom", "higher ed")):
        return "UK"
    return ""


def collapse(dated):
    """One row per linkedin_post_id, slide-level fields joined into one."""
    dated = dated.dropna(subset=["linkedin_post_id"]).copy()
    dated["linkedin_post_id"] = dated["linkedin_post_id"].astype(str)

    # Fields where we take the first non-empty value (they should agree across
    # slides of the same post, or the first slide is the primary one).
    take_first = [
        "view_completeness", "cta_confidence",
        "value_prop_line", "value_prop_in_first_3_sentences",
        "industry_keywords", "tone", "pov",
        "offer_type", "cta_placement", "cta_type_caption", "cta_verb",
        "has_question_prompt", "hashtag_style",
        "media_type", "primary_visual", "image_subject",
        "person_present", "face_visible", "number_of_people",
        "object_of_focus",
        "background_type", "background_dominant_colour",
        "foreground_dominant_colour", "palette", "contrast_level", "texture",
        "text_on_image", "headline_on_image", "headline_style", "headline_chars",
        "subheadline_on_image", "image_cta_text",
        "brand_marks", "brand_placement", "graphic_style",
        "campaign", "angle",
    ]

    # Fields where we concatenate distinct values across slides.
    join_distinct = ["notable_element"]

    def first_nonempty(series):
        for v in series:
            if isinstance(v, str) and v.strip() and v.strip().lower() != "nan":
                return v
            if pd.notna(v) and not isinstance(v, str):
                return v
        return ""

    def join_distinct_values(series):
        seen = []
        for v in series:
            if isinstance(v, str) and v.strip():
                if v not in seen:
                    seen.append(v)
        return " || ".join(seen)

    agg = {c: first_nonempty for c in take_first if c in dated.columns}
    agg.update({c: join_distinct_values for c in join_distinct if c in dated.columns})
    agg["post_id"] = lambda s: ", ".join(sorted(s.astype(str).unique()))
    agg["batch"] = lambda s: ", ".join(sorted(s.astype(str).unique()))

    collapsed = dated.groupby("linkedin_post_id", as_index=False).agg(agg)
    collapsed = collapsed.rename(columns={"post_id": "ss_ids", "batch": "ss_batches"})
    collapsed["slide_count"] = dated.groupby("linkedin_post_id").size().values

    # Normalise for the app's FEATURES columns.
    collapsed["has_face_in_image"] = collapsed["face_visible"].apply(_yn)
    collapsed["text_on_image"] = collapsed["text_on_image"].apply(_yn)
    collapsed["target_region"] = collapsed.apply(
        lambda r: _region_from_campaign(r.get("campaign", ""), r.get("angle", "")),
        axis=1)
    # image_colour_theme is what the app looks for; palette is our tag.
    collapsed["image_colour_theme"] = collapsed["palette"]

    return collapsed


def main():
    dated = pd.read_csv(DATED_CSV, dtype={"linkedin_post_id": str})
    print(f"Read {len(dated)} rows from post_enrichment_dated.csv")

    collapsed = collapse(dated)
    print(f"Collapsed to {len(collapsed)} unique LinkedIn posts")
    print(f"  slide_count distribution:")
    print(collapsed["slide_count"].value_counts().sort_index().to_string())

    posts = pd.read_csv(POSTS_CSV, dtype={"post_id": str})
    posts["post_id"] = posts["post_id"].str.strip()
    collapsed["linkedin_post_id"] = collapsed["linkedin_post_id"].astype(str).str.strip()

    # Left-merge on the LinkedIn post id.
    merged = posts.merge(
        collapsed.rename(columns={"linkedin_post_id": "post_id"}),
        on="post_id", how="left", suffixes=("", "_visual"))

    covered = merged["ss_ids"].notna().sum()
    print(f"\nposts.csv rows                  : {len(posts)}")
    print(f"posts.csv rows with visual tags : {covered}  ({covered/len(posts):.0%})")
    print(f"posts.csv rows without visuals  : {len(posts) - covered}")

    # Back up posts.csv before overwriting
    if not os.path.exists(BACKUP_CSV):
        shutil.copy(POSTS_CSV, BACKUP_CSV)
        print(f"\nBacked up original posts.csv -> {os.path.basename(BACKUP_CSV)}")
    else:
        print(f"\nBackup already exists at {os.path.basename(BACKUP_CSV)} (not overwriting)")

    merged.to_csv(POSTS_CSV, index=False)
    print(f"Wrote merged posts.csv          : {len(merged.columns)} columns")

    # Show a few sample matches with the new visual columns
    print("\nSample of newly-visible visual attributes on posts.csv:")
    sample_cols = ["post_id", "created_date", "hook", "campaign",
                   "primary_visual", "has_face_in_image", "image_colour_theme",
                   "target_region", "slide_count"]
    sample_cols = [c for c in sample_cols if c in merged.columns]
    with_visuals = merged.dropna(subset=["ss_ids"])
    print(with_visuals[sample_cols].head(6).to_string(index=False))


if __name__ == "__main__":
    main()
