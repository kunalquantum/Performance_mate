"""
Persona - Content vs persona fit (word-level).

Every email in the library scored against each persona using a
weighted vocabulary (strong / medium / weak signals). Answers:
which email in our stack is actually right for a Research seat,
a Finance seat, or an IT seat?

Sources:
    campaign_batches.csv  - tracked sends (real body + real numbers)
    campaigns.csv         - draft campaigns from the marketing calendar
"""
import re
import html
import pandas as pd
import streamlit as st

from shared import (core_question, inject_css, render_status_key,
                     kpi_tile, so_what, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Content vs persona fit</h1>', unsafe_allow_html=True)
core_question("Which email in our library is actually right for a "
                "Research seat, a Finance seat, or an IT seat - "
                "word for word?")
st.caption("Every email scored against three persona vocabularies. "
            "Strong signals (like &lsquo;Chief Financial Officer&rsquo; "
            "for Finance) count more than weak ones (like "
            "&lsquo;budget&rsquo;). Green cells mean strong fit; gold "
            "means the copy needs a rewrite for that seat.")
render_status_key()


# ==========================================================================
# Weighted vocabulary per persona
# ==========================================================================
# weight 3 = named-role / high-specificity term
# weight 2 = domain-clear term
# weight 1 = general term that leans this way
PERSONA_VOCAB = {
    "Research": {
        3: [
            "principal investigator", "pi", "pre-award", "post-award",
            "research office", "grant management", "grants management",
            "ukri", "horizon europe", "research council",
            "director of research", "vice chancellor",
            "pro vice chancellor", "wellcome", "epsrc", "esrc",
            "research administration", "arma", "ncura",
        ],
        2: [
            "research", "researcher", "grant", "grants", "funder",
            "funding opportunity", "funding opportunities",
            "impact", "ref", "kef", "proposal", "proposals",
            "research income", "research portfolio", "grant portfolio",
            "grant admin", "research services", "peer review",
        ],
        1: [
            "academic", "university", "institution", "innovation",
            "knowledge exchange", "faculty", "principal",
            "application", "award", "project",
        ],
    },
    "Finance": {
        3: [
            "cfo", "chief financial officer", "finance director",
            "director of finance", "finance systems", "tract",
            "cost recovery", "annual cost", "cost centre",
            "faculty finance", "hefce", "reconciliation",
            "reconcile", "audit trail", "financial reporting",
            "financial control",
        ],
        2: [
            "finance", "budget", "cost", "audit", "reporting",
            "compliance", "reconcile", "financial",
            "value for money", "cost saving", "spend",
            "reduce costs", "annual costs", "cost model",
            "roi", "cost recovery",
        ],
        1: [
            "efficiency", "savings", "value", "expense",
            "invoice", "procurement",
        ],
    },
    "IT-Systems": {
        3: [
            "cio", "chief information officer", "it director",
            "head of it", "digital transformation",
            "single source of truth", "erp integration",
            "system integration", "systems integration",
            "sso", "api", "middleware", "integrations",
            "digital strategy", "information services",
        ],
        2: [
            "system", "systems", "erp", "cloud", "cloud-based",
            "dashboard", "dashboards", "data pipeline",
            "oracle", "unit4", "workday", "integrate",
            "integrates", "integration", "data model",
            "one platform", "single view",
        ],
        1: [
            "digital", "software", "platform", "data",
            "technology", "it", "reporting tool",
        ],
    },
}

# Colours for highlighting per persona
PERSONA_COL = {"Research": ACCENT, "Finance": GOLD,
                 "IT-Systems": "#7A6A9A"}


def score_text(subject, body):
    """Return dict {persona: {'score': int, 'matches': [(term, weight)]}}
    for the combined subject + body."""
    text = f"{subject}\n{body}".lower()
    out = {}
    for persona, tiers in PERSONA_VOCAB.items():
        score = 0
        matches = []
        for weight, terms in tiers.items():
            for term in terms:
                # Use a word-boundary-ish match to avoid partial hits
                # inside longer words (e.g., "it" inside "committee").
                pattern = r"(?<![a-z])" + re.escape(term) + r"(?![a-z])"
                found = re.findall(pattern, text)
                n = len(found)
                if n:
                    score += n * weight
                    matches.append((term, weight, n))
        out[persona] = {"score": score, "matches": matches}
    return out


def fit_pcts(scores):
    """Turn absolute scores into shares (%) per persona so we can rank."""
    total = sum(s["score"] for s in scores.values())
    if total == 0:
        return {p: 0 for p in scores}
    return {p: (s["score"] / total * 100) for p, s in scores.items()}


def highlight_body(body, matched_terms_by_persona):
    """Return HTML with matched terms wrapped in <mark> tags colour-
    coded by persona. matched_terms_by_persona = {persona: set(term)}."""
    # Escape HTML first, then insert markers
    safe = html.escape(body)
    # Build a single sorted list of (start, end, colour, term) via regex
    replacements = []
    for persona, terms in matched_terms_by_persona.items():
        colour = PERSONA_COL.get(persona, MUTED)
        for term in terms:
            pattern = re.compile(
                r"(?<![a-zA-Z])" + re.escape(term) + r"(?![a-zA-Z])",
                re.IGNORECASE)
            for m in pattern.finditer(safe):
                replacements.append((m.start(), m.end(), colour,
                                       m.group(0)))
    # Sort by start, resolve overlaps by keeping the first
    replacements.sort(key=lambda t: (t[0], -t[1]))
    non_overlap = []
    last_end = -1
    for s, e, c, txt in replacements:
        if s >= last_end:
            non_overlap.append((s, e, c, txt))
            last_end = e
    # Assemble
    out = []
    cursor = 0
    for s, e, c, txt in non_overlap:
        out.append(safe[cursor:s])
        out.append(
            f'<mark style="background:{c}22;color:{INK};'
            f'padding:0 .15rem;border-radius:3px;border-bottom:2px '
            f'solid {c}">{safe[s:e]}</mark>')
        cursor = e
    out.append(safe[cursor:])
    return "".join(out).replace("\n", "<br>")


# ==========================================================================
# Load the email library (tracked batches + draft campaigns)
# ==========================================================================
batches = load_csv("campaign_batches.csv")
campaigns = load_csv("campaigns.csv")

def _n(v):
    """int-or-None helper for optional funnel columns."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


emails = []
if not batches.empty:
    for _, r in batches.iterrows():
        emails.append({
            "source":    "Tracked send",
            "campaign":  str(r.get("batch_name", "")),
            "stage":     str(r.get("stage", "")),
            "subject":   str(r.get("subject", "")),
            "body":      str(r.get("body", "")),
            "sent":      _n(r.get("sent")),
            "delivered": _n(r.get("delivered")),
            "opened":    _n(r.get("opened")),
            "clicked":   _n(r.get("clicked")),
            "replied":   _n(r.get("replied")),
        })
if not campaigns.empty:
    for _, r in campaigns.iterrows():
        emails.append({
            "source":    "Draft campaign",
            "campaign":  str(r.get("campaign_name", "")),
            "stage":     str(r.get("stage", "")),
            "subject":   str(r.get("subject", "")),
            "body":      str(r.get("body", "")),
            "sent":      None,
            "delivered": None,
            "opened":    None,
            "clicked":   None,
            "replied":   None,
        })

if not emails:
    st.info("No emails loaded. Run `python etl/campaign_etl.py` "
             "and/or add rows to `data/campaign_batches.csv`.")
    st.stop()

emails_df = pd.DataFrame(emails)

# Score every email
scores_list = []
for _, r in emails_df.iterrows():
    sc = score_text(r["subject"], r["body"])
    pct = fit_pcts(sc)
    delivered = r["delivered"]
    opened = r["opened"]
    open_rate = (opened / delivered * 100) \
        if (delivered and opened is not None) else None
    scores_list.append({
        "campaign":       r["campaign"],
        "stage":          r["stage"],
        "source":         r["source"],
        "subject":        r["subject"],
        "body":           r["body"],
        "sent":           r["sent"],
        "delivered":      r["delivered"],
        "opened":         r["opened"],
        "clicked":        r["clicked"],
        "replied":        r["replied"],
        "open_rate":      open_rate,
        "research_score": sc["Research"]["score"],
        "finance_score":  sc["Finance"]["score"],
        "it_score":       sc["IT-Systems"]["score"],
        "research_pct":   pct["Research"],
        "finance_pct":    pct["Finance"],
        "it_pct":         pct["IT-Systems"],
        "best_persona":   max(pct, key=pct.get) if sum(pct.values()) > 0
                            else "General",
        "matches":        sc,
    })
scored = pd.DataFrame(scores_list)


# ==========================================================================
# Top-line
# ==========================================================================
n_emails = len(scored)
n_general = int((scored["best_persona"] == "General").sum())
n_research = int((scored["best_persona"] == "Research").sum())
n_finance  = int((scored["best_persona"] == "Finance").sum())
n_it       = int((scored["best_persona"] == "IT-Systems").sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Emails in library", f"{n_emails}",
              sub="tracked sends + draft campaigns")
with k2:
    kpi_tile("Best fit: Research", f"{n_research}",
              sub=f"{n_research/max(n_emails,1)*100:.0f}% of library",
              color=ACCENT)
with k3:
    kpi_tile("Best fit: Finance", f"{n_finance}",
              sub=f"{n_finance/max(n_emails,1)*100:.0f}% of library",
              color=GOLD if n_finance < 3 else ACCENT)
with k4:
    kpi_tile("Best fit: IT-Systems", f"{n_it}",
              sub=f"{n_it/max(n_emails,1)*100:.0f}% of library",
              color=WARN if n_it == 0 else GOLD if n_it < 3 else ACCENT)

# Auto so-what
if n_finance == 0 and n_it == 0:
    so_what(
        f"<strong>Zero</strong> emails in the library speak to "
        f"Finance or IT-Systems as their dominant persona. Every "
        f"single piece of content is written for Research. That is "
        f"why Finance and IT are under-engaged - we&apos;ve never "
        f"actually shipped copy for them.", tone="warn")
elif n_finance < 3 or n_it < 3:
    so_what(
        f"Content library is heavily Research-tilted. Only "
        f"{n_finance} email(s) speak to Finance and {n_it} to IT "
        f"as the dominant persona. This is the biggest content "
        f"gap.", tone="warn")


# ==========================================================================
# The big fit matrix
# ==========================================================================
st.markdown('<h2>Every email x every persona (fit %)</h2>',
             unsafe_allow_html=True)
st.caption("Green cells = strong fit (40%+ of the copy&apos;s persona "
            "vocabulary belongs to that seat). Gold = moderate. "
            "Faint = weak. Sort by any column.")

# Sort dropdown
sort_by = st.selectbox(
    "Sort by",
    ["Research fit", "Finance fit", "IT-Systems fit",
     "Opens (most first)", "Open rate (highest first)",
     "Campaign name"], key="pcf_sort")
sort_map = {"Research fit": "research_pct",
              "Finance fit": "finance_pct",
              "IT-Systems fit": "it_pct",
              "Opens (most first)": "opened",
              "Open rate (highest first)": "open_rate",
              "Campaign name": "campaign"}
view = scored.sort_values(
    sort_map[sort_by],
    ascending=(sort_by == "Campaign name"),
    na_position="last")

# Column header strip (aligns with the expander rows below)
st.markdown(
    f'<div style="display:grid;grid-template-columns:'
    f'2.2fr 2.4fr .6fr .6fr .6fr .6fr .7fr .7fr .7fr .9fr;'
    f'gap:.4rem;padding:.5rem .8rem;font-size:.7rem;'
    f'text-transform:uppercase;letter-spacing:.12em;color:{MUTED};'
    f'font-weight:600;border-bottom:1px solid {LINE}">'
    f'<div>Campaign (click to read the body)</div>'
    f'<div>Subject</div>'
    f'<div>Sent</div><div>Opened</div><div>Clicked</div>'
    f'<div>Open %</div>'
    f'<div>Research</div><div>Finance</div><div>IT-Sys</div>'
    f'<div>Best fit</div></div>',
    unsafe_allow_html=True)


def _pct_span(pct):
    """Inline coloured fit-percentage pill for the expander header."""
    if pct >= 40:  bg = "#DDEEEC"
    elif pct >= 20: bg = "#F7F0DA"
    elif pct >= 5:  bg = "#FBF3E5"
    else: bg = BG_SOFT
    return (f'<span style="background:{bg};padding:.1rem .45rem;'
            f'border-radius:3px;color:{INK};font-weight:700;'
            f'font-size:.78rem">{pct:.0f}%</span>')


def _num_cell(v):
    """Render a plain integer, or an em-dash if missing."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return f'<span style="color:{MUTED}">&mdash;</span>'
    try:
        return f'<span style="color:{INK}">{int(v)}</span>'
    except (ValueError, TypeError):
        return f'<span style="color:{MUTED}">&mdash;</span>'


def _open_rate_cell(rate):
    """Coloured open-rate cell, green >= 20%, else gold, dash if none."""
    if rate is None or pd.isna(rate):
        return f'<span style="color:{MUTED}">&mdash;</span>'
    bg = "#DDEEEC" if rate >= 20 else "#FBF3E5"
    return (f'<span style="background:{bg};padding:.1rem .4rem;'
            f'border-radius:3px;color:{INK};font-weight:700;'
            f'font-size:.78rem">{rate:.0f}%</span>')


# One expander per email. Header shows compact fit + funnel info;
# expanded shows the full subject and body.
for _, r in view.iterrows():
    bp = r["best_persona"]
    bp_col = PERSONA_COL.get(bp, MUTED)

    # Plain-text label Streamlit accepts (widget label)
    def _lbl(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        try:
            return str(int(v))
        except (ValueError, TypeError):
            return "-"

    sent_lbl  = _lbl(r["sent"])
    open_lbl  = _lbl(r["opened"])
    click_lbl = _lbl(r["clicked"])
    rate_lbl = "-" if (r["open_rate"] is None
                        or pd.isna(r["open_rate"])) \
        else f"{r['open_rate']:.0f}%"
    label = (f"{r['campaign']} - {r['stage']}   |   "
              f"Sent {sent_lbl}  Opens {open_lbl}  Clicks {click_lbl}  "
              f"({rate_lbl})   |   "
              f"R {r['research_pct']:.0f}% "
              f"F {r['finance_pct']:.0f}% "
              f"IT {r['it_pct']:.0f}%   |   Best fit: {bp}")
    with st.expander(label, expanded=False):
        # Rendered header strip inside the expander for visual polish
        st.markdown(
            f'<div style="display:grid;grid-template-columns:'
            f'2.2fr 2.4fr .6fr .6fr .6fr .6fr .7fr .7fr .7fr .9fr;'
            f'gap:.4rem;padding:.3rem .3rem .7rem;font-size:.86rem;'
            f'align-items:center;border-bottom:1px solid {LINE};'
            f'margin-bottom:.6rem">'
            f'<div style="color:{INK};font-weight:600">'
            f'{r["campaign"]}<br>'
            f'<span style="color:{MUTED};font-size:.75rem;'
            f'font-weight:400">{r["stage"]}</span></div>'
            f'<div style="color:{INK};font-size:.82rem;'
            f'line-height:1.4">{html.escape(r["subject"])}</div>'
            f'<div>{_num_cell(r["sent"])}</div>'
            f'<div>{_num_cell(r["opened"])}</div>'
            f'<div>{_num_cell(r["clicked"])}</div>'
            f'<div>{_open_rate_cell(r["open_rate"])}</div>'
            f'<div>{_pct_span(r["research_pct"])}</div>'
            f'<div>{_pct_span(r["finance_pct"])}</div>'
            f'<div>{_pct_span(r["it_pct"])}</div>'
            f'<div><span style="background:{bp_col}22;'
            f'padding:.15rem .4rem;border-radius:3px;color:{INK};'
            f'font-weight:600;font-size:.82rem">{bp}</span></div>'
            f'</div>', unsafe_allow_html=True)

        # Reply row if we tracked replies
        _replies = r["replied"]
        _has_replies = (_replies is not None
                          and not (isinstance(_replies, float)
                                    and pd.isna(_replies)))
        if _has_replies:
            try:
                _rn = int(_replies)
            except (ValueError, TypeError):
                _rn = 0
            if _rn > 0:
                st.markdown(
                    f'<div style="color:{ACCENT};font-size:.85rem;'
                    f'margin-bottom:.5rem"><strong>'
                    f'{_rn} replies</strong> tracked on this send.'
                    f'</div>', unsafe_allow_html=True)

        # Full body content
        st.text(r["body"] if str(r["body"]).strip() else "(no body)")


# ==========================================================================
# Best emails per persona (ranked)
# ==========================================================================
st.markdown('<h2>Best emails for each persona seat</h2>',
             unsafe_allow_html=True)
st.caption("Top 5 emails per persona, ranked by vocabulary fit %. Use "
            "these as your default sends for that seat.")

pcol1, pcol2, pcol3 = st.columns(3)

for col, persona, pct_col, colour in [
    (pcol1, "Research",   "research_pct", ACCENT),
    (pcol2, "Finance",    "finance_pct",  GOLD),
    (pcol3, "IT-Systems", "it_pct",       "#7A6A9A"),
]:
    with col:
        st.markdown(
            f'<div class="eyebrow" style="color:{colour};'
            f'margin-bottom:.3rem">Top 5 for {persona}</div>',
            unsafe_allow_html=True)
        top5 = scored.sort_values(pct_col, ascending=False).head(5)
        if top5[pct_col].max() == 0:
            st.markdown(
                f'<div style="font-size:.85rem;color:{MUTED};'
                f'padding:.5rem 0;font-style:italic">No emails hit '
                f'this persona&apos;s vocabulary. Content gap.</div>',
                unsafe_allow_html=True)
        else:
            for _, r in top5.iterrows():
                if r[pct_col] == 0:
                    break
                st.markdown(
                    f'<div style="border-left:3px solid {colour};'
                    f'padding:.45rem .7rem;margin:.3rem 0;'
                    f'background:{BG_SOFT};border-radius:4px;'
                    f'font-size:.85rem">'
                    f'<div style="color:{INK};font-weight:600">'
                    f'{r["campaign"][:35]}</div>'
                    f'<div style="color:{MUTED};font-size:.75rem">'
                    f'{r["stage"]}</div>'
                    f'<div style="color:{colour};font-weight:700;'
                    f'font-size:.9rem;margin-top:.2rem">'
                    f'{r[pct_col]:.0f}% fit</div>'
                    f'</div>', unsafe_allow_html=True)


# ==========================================================================
# Drill: pick an email, see the body with matched words highlighted
# ==========================================================================
st.markdown('<h2>Look at one email - matched words highlighted</h2>',
             unsafe_allow_html=True)
st.caption("Pick an email. The body is shown with every persona-"
            "specific word coloured by which persona it belongs to. "
            "Toggle personas on/off with the checkboxes.")

opts = [f"{r['campaign']} - {r['stage']} ({r['source']})"
         for _, r in scored.iterrows()]
pick = st.selectbox("Email", opts, key="pcf_drill")
pick_idx = opts.index(pick)
row = scored.iloc[pick_idx]

# Toggles
tc1, tc2, tc3 = st.columns(3)
with tc1:
    show_r = st.toggle("Show Research words", value=True,
                          key="pcf_r")
with tc2:
    show_f = st.toggle("Show Finance words", value=True,
                          key="pcf_f")
with tc3:
    show_i = st.toggle("Show IT-Systems words", value=True,
                          key="pcf_i")

# Fit percentages
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    kpi_tile("Research fit", f"{row['research_pct']:.0f}%",
              sub=f"score {row['research_score']}",
              color=ACCENT if row["research_pct"] >= 40
                    else GOLD if row["research_pct"] >= 20 else MUTED)
with fc2:
    kpi_tile("Finance fit", f"{row['finance_pct']:.0f}%",
              sub=f"score {row['finance_score']}",
              color=ACCENT if row["finance_pct"] >= 40
                    else GOLD if row["finance_pct"] >= 20 else MUTED)
with fc3:
    kpi_tile("IT-Systems fit", f"{row['it_pct']:.0f}%",
              sub=f"score {row['it_score']}",
              color=ACCENT if row["it_pct"] >= 40
                    else GOLD if row["it_pct"] >= 20 else MUTED)
with fc4:
    kpi_tile("Best fit", row["best_persona"],
              color=PERSONA_COL.get(row["best_persona"], MUTED))

# Match evidence
st.markdown('<h3 style="margin-top:1rem">Which words matched</h3>',
             unsafe_allow_html=True)
mc1, mc2, mc3 = st.columns(3)
active_terms = {"Research": set(), "Finance": set(),
                  "IT-Systems": set()}
_WEIGHT_LABEL = {3: "strong", 2: "medium", 1: "weak"}
for col, persona, show in [
    (mc1, "Research",   show_r),
    (mc2, "Finance",    show_f),
    (mc3, "IT-Systems", show_i),
]:
    matches = row["matches"][persona]["matches"]
    with col:
        st.markdown(
            f'<div class="eyebrow" style="color:'
            f'{PERSONA_COL[persona]};margin-bottom:.3rem">'
            f'{persona} words matched</div>',
            unsafe_allow_html=True)
        if not matches:
            st.markdown(
                f'<div style="font-size:.85rem;color:{MUTED};'
                f'font-style:italic">no matches</div>',
                unsafe_allow_html=True)
        else:
            for term, weight, n in sorted(matches,
                                            key=lambda t: (-t[1], -t[2])):
                st.markdown(
                    f'<div style="font-size:.82rem;color:{INK_SOFT};'
                    f'padding:.15rem 0">'
                    f'<span style="background:'
                    f'{PERSONA_COL[persona]}22;padding:.05rem .3rem;'
                    f'border-radius:3px;color:{INK};font-weight:600">'
                    f'{term}</span> &middot; {_WEIGHT_LABEL[weight]} '
                    f'&middot; hit {n}x</div>',
                    unsafe_allow_html=True)
                if show:
                    active_terms[persona].add(term)

# Highlighted body
st.markdown('<h3 style="margin-top:1rem">Body (with matched words)'
             '</h3>', unsafe_allow_html=True)
st.markdown(f'<div style="font-weight:600;color:{INK};font-size:1rem;'
             f'margin-bottom:.4rem">Subject: '
             f'{html.escape(row["subject"])}</div>',
             unsafe_allow_html=True)
highlighted = highlight_body(row["body"], active_terms)
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'padding:1rem 1.2rem;background:{BG};line-height:1.6;'
    f'font-size:.92rem;color:{INK}">{highlighted}</div>',
    unsafe_allow_html=True)


