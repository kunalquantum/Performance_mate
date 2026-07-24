"""
V2: Split the three LinkedIn modes into standalone pages, using the intact
original app.py backup so the `if mode ==` guards are preserved.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BACKUP = os.path.join(HERE, "app_singlepage_backup.py")
PAGES = os.path.join(ROOT, "pages")
os.makedirs(PAGES, exist_ok=True)

with open(BACKUP, encoding="utf-8") as f:
    src = f.readlines()


def find(needle, start=1):
    for i, line in enumerate(src[start - 1:], start=start):
        if needle in line:
            return i
    raise SystemExit(f"anchor not found: {needle!r}")


def slice_(a, b):
    return "".join(src[a - 1:b])


L_email_container = find("if mode == \"Email Matrix\":")
L_email_stop      = find("if app == \"Email Performance Matrix\":",
                            start=L_email_container + 1)
L_recommend       = find("if mode == \"Recommend\":", start=L_email_stop + 1)
L_visualize       = find("if mode == \"Visualize\":", start=L_recommend + 1)


def dedent_body(text_lines):
    """Drop the first `if mode ==` line and reduce 4-space indent."""
    assert text_lines[0].startswith("if mode ==")
    out = []
    for line in text_lines[1:]:
        if line.strip() == "":
            out.append(line)
        elif line.startswith("    "):
            out.append(line[4:])
        else:
            out.append(line)
    return "".join(out)


recommend_raw = slice_(L_recommend, L_visualize - 1).splitlines(keepends=True)
recommend_body = dedent_body(recommend_raw)
# Strip trailing st.stop() so page doesn't halt on completion
rlines = recommend_body.splitlines(keepends=True)
for i in range(len(rlines) - 1, -1, -1):
    if rlines[i].rstrip() == "st.stop()":
        rlines = rlines[:i]
        break
recommend_body = "".join(rlines)

# Visualize block is at 4-space indent under `if mode == "Visualize":`.
# Explore content follows at column 0 (unconditional). Find the col-4
# `    st.stop()` line in the RAW backup that terminates the Visualize
# block, split there, dedent only the Visualize portion.
v_stop_line = None
for i in range(L_visualize, len(src) + 1):
    if src[i - 1].rstrip() == "    st.stop()":
        v_stop_line = i
        break
if v_stop_line is None:
    raise SystemExit("Could not find Visualize `    st.stop()` boundary")

visualize_raw = src[L_visualize - 1:v_stop_line - 1]  # excludes st.stop
visualize_body = dedent_body(visualize_raw)

# Explore content = everything AFTER the Visualize st.stop, verbatim
explore_only = "".join(src[v_stop_line:])


PAGE_HEADER = '''"""
LinkedIn Post Performance Matrix - {mode} page.
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
ctx = linkedin_setup("{mode}")

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

'''

with open(os.path.join(PAGES, "linkedin_explore.py"), "w",
            encoding="utf-8") as f:
    f.write(PAGE_HEADER.format(mode="Explore") + explore_only)

with open(os.path.join(PAGES, "linkedin_visualize.py"), "w",
            encoding="utf-8") as f:
    f.write(PAGE_HEADER.format(mode="Visualize") + visualize_body)

with open(os.path.join(PAGES, "linkedin_recommend.py"), "w",
            encoding="utf-8") as f:
    f.write(PAGE_HEADER.format(mode="Recommend") + recommend_body)


print(f"Recommend body lines: {len(recommend_body.splitlines())}")
print(f"Visualize body lines: {len(visualize_body.splitlines())}")
print(f"Explore body lines:   {len(explore_only.splitlines())}")
