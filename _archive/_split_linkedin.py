"""
Split the original single-page app.py backup into three LinkedIn pages and
one shared setup function. Overwrites shared.py's linkedin_setup() section
and replaces pages/linkedin.py with three page files.

Uses the intact backup as source-of-truth to preserve the `if mode ==`
guards that got stripped in the earlier splitter.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BACKUP = os.path.join(HERE, "app_singlepage_backup.py")
PAGES = os.path.join(ROOT, "pages")

with open(BACKUP, encoding="utf-8") as f:
    src = f.readlines()


def find(needle, start=1):
    for i, line in enumerate(src[start - 1:], start=start):
        if needle in line:
            return i
    raise SystemExit(f"anchor not found: {needle!r}")


def slice_(a, b):
    """Return lines[a-1..b-1] as text."""
    return "".join(src[a - 1:b])


# --- Anchors (verified against the backup) ---
L_email_container = find("if mode == \"Email Matrix\":")
L_email_stop      = find("if app == \"Email Performance Matrix\":",
                            start=L_email_container + 1)
L_recommend       = find("if mode == \"Recommend\":", start=L_email_stop + 1)
L_visualize       = find("if mode == \"Visualize\":", start=L_recommend + 1)


# --- Text extraction ---
# Setup block: from top of file through the `st.markdown('<div class="lede">'
# ...` block near the mode-radio handling. We keep the whole LinkedIn setup
# incl. sidebar, date range, filtering, scoring, lift, lede.
#
# The setup ENDS at the last line before the "EMAIL MATRIX" comment block
# (which is at L_email_container - N). Grab everything from line 1 up to
# just before the EMAIL MATRIX section.
L_setup_end = L_email_container - 1
# walk back over comment lines and blanks that intro the EMAIL section
while src[L_setup_end - 1].strip().startswith("#") or \
        src[L_setup_end - 1].strip() == "":
    L_setup_end -= 1
setup_block = slice_(1, L_setup_end)

# Recommend content: lines from `if mode == "Recommend":` through just
# before `if mode == "Visualize":`. Includes the guard which we'll strip.
recommend_block_raw = slice_(L_recommend, L_visualize - 1)
# strip the `if mode == "Recommend":` guard line and reduce indent by 4
lines = recommend_block_raw.splitlines(keepends=True)
assert lines[0].startswith("if mode ==")
lines = lines[1:]
recommend_block = ""
for line in lines:
    if line.strip() == "":
        recommend_block += line
    elif line.startswith("    "):
        recommend_block += line[4:]
    else:
        recommend_block += line

# Visualize content
visualize_block_raw = slice_(L_visualize, len(src))
lines = visualize_block_raw.splitlines(keepends=True)
assert lines[0].startswith("if mode ==")
lines = lines[1:]
visualize_block = ""
for line in lines:
    if line.strip() == "":
        visualize_block += line
    elif line.startswith("    "):
        visualize_block += line[4:]
    else:
        visualize_block += line
# Visualize's block runs `if mode == "Visualize":` then falls through to
# Explore content (unconditional). The Visualize guard block ends where?
# Look for the first line at column 0 that's not a comment/blank after
# the guard body. In the backup, Visualize ends before the unconditional
# Explore code at the bottom (h2 "The year..." at column 0).
# So we need to split visualize_block into (visualize_only, explore_only).
# The Visualize guard body was at 4-space indent; after we stripped 4
# spaces, the body is now at col 0 mixed with the Explore content which
# was already at col 0. We need to find the visualize st.stop() which is
# where Explore content begins.
#
# Find the first "st.stop()" that terminates the Visualize block. In the
# backup that's a line "    st.stop()" at 4 spaces => now "st.stop()" at
# col 0 in visualize_block.
vlines = visualize_block.splitlines(keepends=True)
stop_idx = None
for i, line in enumerate(vlines):
    if line.rstrip() == "st.stop()":
        stop_idx = i
        break
if stop_idx is None:
    raise SystemExit("Could not find Visualize st.stop() boundary")
visualize_only = "".join(vlines[:stop_idx])  # exclude the st.stop line
explore_only   = "".join(vlines[stop_idx + 1:])

# Recommend block also ends with st.stop() before Visualize starts.
# recommend_block already contains that st.stop() as its last real line
# (or close to it). Strip trailing st.stop() so pages don't halt.
rlines = recommend_block.splitlines(keepends=True)
# find last st.stop() and drop everything from there
for i in range(len(rlines) - 1, -1, -1):
    if rlines[i].rstrip() == "st.stop()":
        rlines = rlines[:i]
        break
recommend_only = "".join(rlines)


# ---------- Assemble a common setup function to inject into shared.py -----
# The setup block references drop_event, scope, drop_topics, etc. from the
# sidebar and posts_raw / posts / scored / lift / start_date / end_date /
# min_d / max_d / hashtag_library / curated_active as outputs. We wrap it
# in a function that returns a namespace object.
setup_indented = "".join("    " + line if line.strip() else line
                          for line in setup_block.splitlines(keepends=True))

setup_function = '''
# ==========================================================================
# LinkedIn shared setup: sidebar filters + date range + scoring pipeline.
# Called once at the top of each LinkedIn page. Returns a Namespace with
# every value the mode-specific rendering needs.
# ==========================================================================
import types


def linkedin_setup(mode):
    """Build LinkedIn context for the given mode ("Explore" | "Visualize" |
    "Recommend"). Renders sidebar filters + date range + KPI lede."""
    import os, re
    import altair as alt
    import pandas as pd
    import streamlit as st

    import scoring
    import predictor
    import image_analysis

    # Behavioural constants that the original module-level code depended on
    app = "LinkedIn Post Matrix"

''' + setup_indented + '''

    # Package everything the page needs
    ns = types.SimpleNamespace()
    for name in ("app", "mode", "posts_raw", "posts", "scored", "lift",
                  "live_features", "start_date", "end_date", "min_d", "max_d",
                  "hashtag_library", "curated_active",
                  "drop_event", "scope", "drop_topics", "drop_asks",
                  "drop_days", "drop_lengths", "drop_palettes", "drop_faces",
                  "drop_textimg", "drop_media", "drop_campaigns"):
        if name in locals():
            setattr(ns, name, locals()[name])
    return ns
'''

# The setup function references `mode` as a parameter but the original code
# reads `mode = st.session_state.mode` after the radio. We need the setup
# to accept mode as an argument and NOT re-read from a radio (since nav
# handles the "which page" choice now). Also drop the mode radio.
#
# For the linkedin_setup body we've indented, patch out the mode radio and
# force `mode` to come from the function argument.

# Remove the block that creates the mode radio:
setup_function = re.sub(
    r"    # mode toggle.*?mode = st\.session_state\.mode",
    "    # mode is provided by the caller (multi-page)\n"
    "    st.session_state.mode = mode",
    setup_function, count=1, flags=re.DOTALL)


with open(os.path.join(ROOT, "shared.py"), "a", encoding="utf-8") as f:
    f.write(setup_function)


# ---------- Write three LinkedIn page files ----------
PAGE_HEADER = '''"""
LinkedIn Post Performance Matrix - {mode} screen.
"""
from shared import (inject_css, linkedin_setup, INK, INK_SOFT, MUTED, LINE,
                     BG, BG_SOFT, ACCENT, ACCENT_SOFT, WARN, GOLD,
                     FEATURES, LABELS)
import os, re
import altair as alt
import pandas as pd
import streamlit as st

import scoring
import predictor
import image_analysis

inject_css()
ctx = linkedin_setup("{mode}")

# unpack for the page body (keeps the copied code below working unchanged)
app             = ctx.app
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
    f.write(PAGE_HEADER.format(mode="Visualize") + visualize_only)

with open(os.path.join(PAGES, "linkedin_recommend.py"), "w",
            encoding="utf-8") as f:
    f.write(PAGE_HEADER.format(mode="Recommend") + recommend_only)


print(f"Setup block: lines 1..{L_setup_end} ({L_setup_end} lines)")
print(f"Recommend  : lines {L_recommend}..{L_visualize - 1}"
      f" ({L_visualize - 1 - L_recommend + 1} lines)")
print(f"Visualize  : lines {L_visualize}..{len(src)}"
      f" ({len(src) - L_visualize + 1} lines)")
print(f"Explore    : trailing {len(vlines) - stop_idx - 1} lines "
      "extracted from Visualize's tail")
print()
print("Wrote pages/linkedin_explore.py")
print("Wrote pages/linkedin_visualize.py")
print("Wrote pages/linkedin_recommend.py")
print("Appended linkedin_setup() to shared.py")
