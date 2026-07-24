"""
One-off splitter that reads the legacy single-page app.py and emits four
Streamlit page files under pages/.

Boundaries used (based on grep of app.py):
    Setup / sidebar / date-range / post filtering / scored / lift / lede
      lines 1..457   -> reused across LinkedIn pages (LinkedIn setup block)

    Email Matrix container starts at line 473 (`if mode == "Email Matrix":`)
      Performance screen guard    -> line 474
      Audience screen guard       -> line 1620
      Contents analysis guard     -> line 2199
      Email closing st.stop       -> line 2955

    LinkedIn Recommend            -> lines 2962..3482
    LinkedIn Visualize            -> lines 3487..4207
    LinkedIn Explore (default)    -> line 4208..EOF
"""

import os
import re
import sys

APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "app_singlepage_backup.py")
APP_PATH = os.path.abspath(APP_PATH)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PAGES = os.path.join(ROOT, "pages")
os.makedirs(PAGES, exist_ok=True)

with open(APP_PATH, encoding="utf-8") as f:
    src = f.readlines()

def slice_(a, b):
    """Return lines[a-1 .. b-1] joined."""
    return "".join(src[a - 1:b])

# --- Locate anchor lines by content search (robust to line drift) ---
def find_line(needle, start=1):
    for i, line in enumerate(src[start - 1:], start=start):
        if needle in line:
            return i
    raise SystemExit(f"anchor not found: {needle}")

L_setpageconfig  = find_line("st.set_page_config(")
L_css_end        = find_line("</style>", start=L_setpageconfig) + 2  # include markdown call end
L_load_csv_end   = find_line("if posts_raw.empty:") - 2
L_email_container= find_line("if mode == \"Email Matrix\":")
L_email_perf_start = find_line("== \"Performance\":", start=L_email_container)
L_email_aud_start  = find_line("== \"Audience\":", start=L_email_perf_start + 1)
L_email_con_start  = find_line("== \"Contents analysis\":", start=L_email_aud_start + 1)
L_email_stop     = find_line("if app == \"Email Performance Matrix\":",
                                start=L_email_con_start + 1)
L_recommend      = find_line("if mode == \"Recommend\":", start=L_email_stop + 1)
L_visualize      = find_line("if mode == \"Visualize\":", start=L_recommend + 1)

print(f"Anchors:")
print(f"  set_page_config    line {L_setpageconfig}")
print(f"  CSS end            line {L_css_end}")
print(f"  Email container    line {L_email_container}")
print(f"  Email Performance  line {L_email_perf_start}")
print(f"  Email Audience     line {L_email_aud_start}")
print(f"  Email Contents     line {L_email_con_start}")
print(f"  Email closing stop line {L_email_stop}")
print(f"  LinkedIn Recommend line {L_recommend}")
print(f"  LinkedIn Visualize line {L_visualize}")


# ---------- Extract raw blocks ----------
# Sidebar filters live inside `if app == "LinkedIn Post Matrix":` block
# starting shortly after CSS. We'll grab the whole LinkedIn setup section
# from just after the CSS to the Email Matrix container start.
linkedin_setup = slice_(L_css_end + 1, L_email_container - 1)

# Email screen blocks (contents at 8-space indent inside two guards)
email_perf_block = slice_(L_email_perf_start + 1, L_email_aud_start - 1)
email_aud_block  = slice_(L_email_aud_start + 1, L_email_con_start - 1)
email_con_block  = slice_(L_email_con_start + 1, L_email_stop - 1)

# LinkedIn Recommend and Visualize blocks - keep their `if mode ==` guards
linkedin_recommend = slice_(L_recommend + 1, L_visualize - 1)
linkedin_visualize = slice_(L_visualize + 1, len(src))


# ---------- Helpers to reduce indent by 8 spaces (Email screens were
# nested inside `if mode == "Email Matrix":` + `if screen == X:`) ----------
def dedent(text, spaces):
    out = []
    prefix = " " * spaces
    for line in text.splitlines(keepends=True):
        if line.strip() == "":
            out.append(line)
        elif line.startswith(prefix):
            out.append(line[spaces:])
        else:
            out.append(line)
    return "".join(out)


email_perf_dedented = dedent(email_perf_block, 8)
email_aud_dedented  = dedent(email_aud_block,  8)
email_con_dedented  = dedent(email_con_block,  8)


# ---------- Write LinkedIn setup block into linkedin.py (shared prelude) ----------
linkedin_page = '''"""
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

''' + linkedin_setup + "\n\n" + linkedin_recommend + "\n\n" + linkedin_visualize

with open(os.path.join(PAGES, "linkedin.py"), "w", encoding="utf-8") as f:
    f.write(linkedin_page)


# ---------- Write Email page files ----------
EMAIL_HEADER = '''"""
{title}
"""
from shared import (inject_css, load_csv, DATA_DIR, SOURCES_DIR, INK,
                     INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, WARN, GOLD)
import os, re
import altair as alt
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>{h1}</h1>', unsafe_allow_html=True)

emails_all = load_csv("emails.csv")
if not emails_all.empty:
    emails_all["week_start"] = pd.to_datetime(emails_all["week_start"],
                                                errors="coerce")

'''

with open(os.path.join(PAGES, "email_performance.py"), "w",
            encoding="utf-8") as f:
    f.write(EMAIL_HEADER.format(
        title="Email Performance Matrix - Performance screen.",
        h1="Email Performance") + email_perf_dedented)

with open(os.path.join(PAGES, "email_audience.py"), "w",
            encoding="utf-8") as f:
    f.write(EMAIL_HEADER.format(
        title="Email Performance Matrix - Audience screen.",
        h1="Audience &amp; Next Send") + email_aud_dedented)

with open(os.path.join(PAGES, "email_contents.py"), "w",
            encoding="utf-8") as f:
    f.write(EMAIL_HEADER.format(
        title="Email Performance Matrix - Contents analysis screen.",
        h1="Contents Analysis") + email_con_dedented)

print()
print(f"Wrote pages/linkedin.py ({len(linkedin_page.splitlines())} lines)")
print(f"Wrote pages/email_performance.py ({len(email_perf_dedented.splitlines())} lines body)")
print(f"Wrote pages/email_audience.py ({len(email_aud_dedented.splitlines())} lines body)")
print(f"Wrote pages/email_contents.py ({len(email_con_dedented.splitlines())} lines body)")
