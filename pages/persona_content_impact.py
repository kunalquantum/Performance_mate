"""
Persona - Which persona opened this email?

One card per tracked email. Each card leads with the answer to
"which persona opened it", then the numbers (opens, clicks), then
an expander to reveal the actual subject + body.

Data used:
    campaign_batches.csv         - subject, body, funnel numbers
    persona_institution_coverage - persona contact mix per institution
    mql_engaged.csv              - REAL per-person opens + clicks + persona
"""
from shared import (core_question, inject_css, kpi_tile, so_what,
                     load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import re
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
             unsafe_allow_html=True)
st.markdown('<h1>Which persona opened this email?</h1>',
             unsafe_allow_html=True)
core_question("For every email we sent, who actually engaged with it "
                "- Research, Finance, or IT-Systems - and what was "
                "the email about?")
st.caption("Each card below is one tracked email. It answers the "
            "persona question first, then lets you open the content.")

PERSONA_COL = {"Research": ACCENT, "Finance": GOLD,
                "IT-Systems": "#7A6A9A", "General": MUTED}

with st.expander("How the persona attribution works", expanded=False):
    st.markdown(
        "- We track **which people engage** with our emails via the "
        "MQL sheet (real opens + clicks per person, with persona "
        "from their job title).\n"
        "- For each tracked send, we look at the **recipient "
        "institution** and check which personas at that institution "
        "have logged real opens / clicks in the MQL sheet.\n"
        "- Where MQL evidence exists, we mark the split "
        "**observed**. Where it does not, we fall back to a **"
        "pro-rata estimate** based on the persona mix of contacts "
        "we hold at that institution, and label it clearly.")


# ==========================================================================
# Load data
# ==========================================================================
batches = load_csv("campaign_batches.csv")
coverage = load_csv("persona_institution_coverage.csv")
mql = load_csv("mql_engaged.csv")

if batches.empty:
    st.info("No tracked batches. Populate `data/campaign_batches.csv`.")
    st.stop()

for c in ("sent", "delivered", "opened", "clicked", "replied"):
    if c in batches.columns:
        batches[c] = pd.to_numeric(batches[c], errors="coerce").fillna(0)

if not coverage.empty:
    for c in ("research", "finance", "it_systems", "contacts"):
        if c in coverage.columns:
            coverage[c] = pd.to_numeric(coverage[c],
                                          errors="coerce").fillna(0).astype(int)

if not mql.empty:
    for c in ("opens", "clicks", "total_engagement"):
        if c in mql.columns:
            mql[c] = pd.to_numeric(mql[c],
                                     errors="coerce").fillna(0).astype(int)


# ==========================================================================
# Persona vocabulary (for word-level highlighting in the body)
# ==========================================================================
PERSONA_VOCAB = {
    "Research": [
        "research", "researcher", "researchers", "grant", "grants",
        "grant management", "funder", "funders", "funding",
        "funding opportunit", "principal investigator", "pre-award",
        "post-award", "research office", "research administration",
        "ukri", "horizon", "arma", "ncura", "proposal", "proposals",
        "award", "awards", "pi", "grantsnow", "research income",
        "research portfolio", "worktribe", "bid", "bids", "submission",
    ],
    "Finance": [
        "finance", "financial", "cfo", "cost", "costs", "audit",
        "audits", "reporting", "trac", "budget", "budgets",
        "compliance", "annual cost", "reduce cost", "cost centre",
        "hefce", "value for money", "spend", "spending", "invoice",
        "invoices", "reconciliation", "vfm", "cost recovery",
        "overhead", "overheads", "financial control", "accounts",
    ],
    "IT-Systems": [
        "erp", "integration", "integrations", "integrates", "api",
        "apis", "sso", "system", "systems", "single source of truth",
        "single view", "dashboard", "dashboards", "data pipeline",
        "oracle", "unit4", "cloud-based", "cloud", "platform",
        "architecture", "workflow", "workflows", "automation",
        "automated", "database", "interface", "portal",
    ],
}
PERSONA_ORDER = ["Research", "Finance", "IT-Systems"]
HL_BG = {"Research": "#0E6E6820", "Finance": "#C99A2E30",
          "IT-Systems": "#7A6A9A25"}
HL_BORDER = {"Research": ACCENT, "Finance": GOLD,
              "IT-Systems": "#7A6A9A"}


def _highlight_text(text):
    """Wrap persona-vocabulary words in <mark> spans. Returns HTML.
    Also returns per-persona hit counts for the caller."""
    from html import escape
    esc = escape(text or "")
    hits = {p: 0 for p in PERSONA_ORDER}
    # Sort keywords longest-first so 'funding opportunit' wins over 'funding'
    for persona in PERSONA_ORDER:
        kws = sorted(PERSONA_VOCAB[persona], key=len, reverse=True)
        for kw in kws:
            # word-boundary match, case-insensitive
            pattern = re.compile(r"(?<![A-Za-z])" + re.escape(kw)
                                    + r"[A-Za-z]*", re.IGNORECASE)
            def _sub(m, p=persona):
                hits[p] += 1
                return (f'<mark style="background:{HL_BG[p]};'
                        f'border-bottom:2px solid {HL_BORDER[p]};'
                        f'padding:0 2px;border-radius:2px;color:{INK}">'
                        f'{m.group(0)}</mark>')
            esc = pattern.sub(_sub, esc)
    # Preserve line breaks
    esc = esc.replace("\n", "<br>")
    return esc, hits


def _legend_html():
    parts = []
    for p in PERSONA_ORDER:
        parts.append(
            f'<span style="display:inline-flex;align-items:center;'
            f'gap:.3rem;margin-right:.8rem;font-size:.75rem;'
            f'color:{INK_SOFT}">'
            f'<span style="display:inline-block;width:14px;height:14px;'
            f'background:{HL_BG[p]};border-bottom:2px solid '
            f'{HL_BORDER[p]};border-radius:2px"></span>{p} language'
            f'</span>')
    return (f'<div style="margin:.4rem 0 .6rem">{"".join(parts)}</div>')


# ==========================================================================
# Helpers
# ==========================================================================
def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _match_institution(batch_name):
    if coverage.empty:
        return None
    nl = _norm(batch_name)
    if not nl:
        return None
    for _, row in coverage.iterrows():
        key = _norm(row.get("institution_key", ""))
        if not key:
            continue
        if key in nl or nl in key:
            return row
    tokens = [t for t in nl.split() if len(t) >= 5
              and t not in ("university", "college")]
    for tok in tokens:
        m = coverage[coverage["institution_key"].astype(str).str.lower()
                       .str.contains(tok, na=False)]
        if not m.empty:
            return m.iloc[0]
    return None


def _match_mql(batch_name):
    if mql.empty:
        return mql.iloc[0:0]
    nl = _norm(batch_name)
    if not nl:
        return mql.iloc[0:0]
    mask = mql["institution"].astype(str).apply(
        lambda x: _norm(x) in nl or nl in _norm(x))
    return mql[mask]


def _persona_bar(splits, total, note):
    if total <= 0:
        return (f'<div style="color:{MUTED};font-size:.85rem;'
                f'font-style:italic">No persona signal on this send.</div>')
    segments = []
    for label, count, colour in splits:
        if count <= 0:
            continue
        pct = count / total * 100
        segments.append(
            f'<div style="flex:{pct};background:{colour};'
            f'display:flex;align-items:center;justify-content:center;'
            f'color:white;font-weight:700;font-size:.78rem;'
            f'padding:.35rem 0" title="{label}: {count} ({pct:.0f}%)">'
            f'{label} {pct:.0f}%</div>')
    return (f'<div style="display:flex;height:26px;border-radius:4px;'
            f'overflow:hidden;margin:.4rem 0 .3rem">'
            f'{"".join(segments)}</div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.1em">{note}</div>')


def _dominant(splits):
    return max(splits, key=lambda t: t[1]) if splits else None


# ==========================================================================
# Build enriched rows
# ==========================================================================
enriched = []
for _, r in batches.iterrows():
    name = str(r.get("batch_name", ""))
    inst_row = _match_institution(name)
    mql_rows = _match_mql(name)

    sent = int(r.get("sent") or 0)
    delivered = int(r.get("delivered") or 0)
    opened = int(r.get("opened") or 0)
    clicked = int(r.get("clicked") or 0)
    replied = int(r.get("replied") or 0)
    open_rate = opened / max(delivered, 1) * 100

    source = None
    p_r = p_f = p_i = 0
    if not mql_rows.empty and mql_rows["opens"].sum() > 0:
        p_r = int(mql_rows[mql_rows["persona"] == "Research"]
                    ["opens"].sum())
        p_f = int(mql_rows[mql_rows["persona"] == "Finance"]
                    ["opens"].sum())
        p_i = int(mql_rows[mql_rows["persona"] == "IT-Systems"]
                    ["opens"].sum())
        if (p_r + p_f + p_i) > 0:
            source = "observed"
    if source is None and inst_row is not None:
        cr = int(inst_row.get("research", 0))
        cf = int(inst_row.get("finance", 0))
        ci = int(inst_row.get("it_systems", 0))
        cot = cr + cf + ci
        if cot > 0 and opened > 0:
            p_r = round(opened * cr / cot)
            p_f = round(opened * cf / cot)
            p_i = round(opened * ci / cot)
            source = "estimated"

    total_persona = p_r + p_f + p_i
    splits = [("Research",   p_r, ACCENT),
              ("Finance",    p_f, GOLD),
              ("IT-Systems", p_i, "#7A6A9A")]
    dom = _dominant(splits) if total_persona > 0 else None

    enriched.append({
        "batch_id":      int(r.get("batch_id") or 0),
        "batch_name":    name,
        "stage":         str(r.get("stage", "")),
        "sent_date":     str(r.get("sent_date", "")),
        "subject":       str(r.get("subject") or ""),
        "body":          str(r.get("body") or ""),
        "sent":          sent,
        "opened":        opened,
        "clicked":       clicked,
        "replied":       replied,
        "open_rate":     open_rate,
        "splits":        splits,
        "total_persona": total_persona,
        "source":        source,
        "dom":           dom,
        "mql_count":     len(mql_rows),
    })

df = pd.DataFrame(enriched)


# ==========================================================================
# Top-line tiles
# ==========================================================================
n_emails = len(df)
n_observed = int((df["source"] == "observed").sum())
n_est = int((df["source"] == "estimated").sum())
n_none = n_emails - n_observed - n_est

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Emails tracked", f"{n_emails}",
              tooltip="Every batch stage with real ESP numbers.")
with k2:
    kpi_tile("Persona answered (observed)",
              f"{n_observed}",
              sub="real MQL engagement",
              color=ACCENT,
              tooltip="Sends where we have per-person opens in the "
                      "MQL sheet at the recipient institution.")
with k3:
    kpi_tile("Persona answered (estimated)",
              f"{n_est}",
              sub="from contact mix",
              color=GOLD,
              tooltip="Sends where we estimate the persona split "
                      "from the contact mix at the institution.")
with k4:
    kpi_tile("No persona signal",
              f"{n_none}",
              sub="non-UK or missing coverage",
              color=WARN if n_none else MUTED)


# ==========================================================================
# Summary table - every email, persona bar at a glance
# ==========================================================================
st.markdown('<h2>All emails at a glance</h2>', unsafe_allow_html=True)
st.caption("One row per email. The bar shows the persona split of "
            "who opened it. Scan for red-heavy Finance/IT rows or "
            "green-heavy Research rows.")

# Legend
st.markdown(
    f'<div style="margin:.3rem 0 .7rem">'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'margin-right:.9rem;font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{ACCENT};border-radius:2px"></span>Research</span>'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'margin-right:.9rem;font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{GOLD};border-radius:2px"></span>Finance</span>'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:#7A6A9A;border-radius:2px"></span>IT-Systems</span>'
    f'</div>', unsafe_allow_html=True)


def _summary_bar(splits, total):
    if total <= 0:
        return (f'<div style="height:22px;background:{LINE};'
                f'border-radius:3px;display:flex;align-items:center;'
                f'justify-content:center;color:{MUTED};'
                f'font-size:.72rem;font-style:italic">no signal</div>')
    segs = []
    for label, count, colour in splits:
        if count <= 0:
            continue
        pct = count / total * 100
        # show label if segment is wide enough
        inner = (f'{label[0]} {pct:.0f}%' if pct >= 15 else "")
        segs.append(
            f'<div style="flex:{pct};background:{colour};'
            f'display:flex;align-items:center;justify-content:center;'
            f'color:white;font-weight:700;font-size:.7rem" '
            f'title="{label}: {count} ({pct:.0f}%)">{inner}</div>')
    return (f'<div style="display:flex;height:22px;border-radius:3px;'
            f'overflow:hidden">{"".join(segs)}</div>')


# Sort by opens desc for the summary
_summary = sorted(enriched, key=lambda x: x["opened"], reverse=True)

# Header
sum_rows = [
    f'<div style="display:grid;grid-template-columns:2.2fr 2fr .5fr .6fr;'
    f'gap:.7rem;padding:.5rem .8rem;font-size:.7rem;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.12em;font-weight:600;'
    f'border-bottom:1px solid {LINE};background:{BG_SOFT}">'
    f'<div>Email</div><div>Who opened it</div>'
    f'<div style="text-align:right">Opens</div>'
    f'<div style="text-align:right">Open %</div></div>'
]
for r in _summary:
    open_col = (ACCENT if r["open_rate"] >= 20
                  else GOLD if r["open_rate"] >= 10 else WARN)
    sum_rows.append(
        f'<div style="display:grid;grid-template-columns:2.2fr 2fr .5fr .6fr;'
        f'gap:.7rem;padding:.55rem .8rem;font-size:.85rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        f'<div style="color:{INK};line-height:1.3">'
        f'<div style="font-weight:600">{r["batch_name"][:38]}</div>'
        f'<div style="color:{MUTED};font-size:.72rem">{r["stage"]}'
        f'{" &middot; observed" if r["source"]=="observed" else " &middot; estimated" if r["source"]=="estimated" else ""}'
        f'</div></div>'
        f'<div>{_summary_bar(r["splits"], r["total_persona"])}</div>'
        f'<div style="text-align:right;color:{INK};font-weight:600">'
        f'{r["opened"]}</div>'
        f'<div style="text-align:right;background:{open_col}22;'
        f'color:{INK};font-weight:700;padding:.15rem .4rem;'
        f'border-radius:3px">{r["open_rate"]:.0f}%</div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden;margin-bottom:1.5rem">'
    f'{"".join(sum_rows)}</div>', unsafe_allow_html=True)


# ==========================================================================
# Filter bar
# ==========================================================================
st.markdown('<h2>Every email &mdash; who opened it</h2>',
             unsafe_allow_html=True)
st.caption("One card per email. Persona bar answers 'who opened this'. "
            "Click the row to read the content.")

f1, f2, f3 = st.columns([1.3, 1.3, 1])
with f1:
    persona_filter = st.selectbox(
        "Show emails opened mostly by",
        ["All", "Research", "Finance", "IT-Systems", "No signal"],
        key="cpi_persona")
with f2:
    source_filter = st.selectbox(
        "Persona signal",
        ["All", "Observed only", "Estimated only", "No signal"],
        key="cpi_source")
with f3:
    sort_by = st.selectbox("Sort by",
                             ["Opens (high to low)",
                              "Open rate (high to low)",
                              "Most recent"],
                             key="cpi_sort")

view = df.copy()
if persona_filter == "No signal":
    view = view[view["dom"].isna()]
elif persona_filter != "All":
    view = view[view["dom"].apply(
        lambda d: d is not None and d[0] == persona_filter)]

if source_filter == "Observed only":
    view = view[view["source"] == "observed"]
elif source_filter == "Estimated only":
    view = view[view["source"] == "estimated"]
elif source_filter == "No signal":
    view = view[view["source"].isna()]

if sort_by == "Opens (high to low)":
    view = view.sort_values("opened", ascending=False)
elif sort_by == "Open rate (high to low)":
    view = view.sort_values("open_rate", ascending=False)
else:
    view = view.sort_values("sent_date", ascending=False)

st.caption(f"Showing **{len(view)}** of {n_emails} emails.")


# ==========================================================================
# Cards
# ==========================================================================
if view.empty:
    st.info("No emails match the current filter.")
else:
    for _, r in view.iterrows():
        if r["dom"] is not None and r["total_persona"] > 0:
            dom_label, dom_count, dom_col = r["dom"]
            dom_pct = dom_count / r["total_persona"] * 100
            headline = (
                f'<span style="color:{MUTED};font-size:.75rem;'
                f'text-transform:uppercase;letter-spacing:.14em">'
                f'Opened mostly by</span> '
                f'<span style="background:{dom_col}22;color:{INK};'
                f'padding:.2rem .55rem;border-radius:4px;'
                f'font-weight:700;font-size:1rem">{dom_label}</span> '
                f'<span style="color:{INK_SOFT};font-size:.9rem">'
                f'&mdash; {dom_pct:.0f}% of persona-attributed opens'
                f'</span>')
            source_tag = (
                f'<span style="background:{ACCENT}18;color:{ACCENT};'
                f'padding:.1rem .4rem;border-radius:3px;font-size:.7rem;'
                f'font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;margin-left:.4rem">observed</span>'
                if r["source"] == "observed"
                else
                f'<span style="background:{GOLD}22;color:#7A5F1E;'
                f'padding:.1rem .4rem;border-radius:3px;font-size:.7rem;'
                f'font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;margin-left:.4rem">estimated</span>')
            note = (f"Real opens from {r['mql_count']} tracked "
                    f"people at this institution."
                    if r["source"] == "observed"
                    else "Opens distributed pro-rata to the contact "
                          "mix at this institution.")
        else:
            headline = (
                f'<span style="color:{MUTED};font-size:.9rem;'
                f'font-style:italic">No persona signal for this send</span>')
            source_tag = ""
            note = ""

        exp_label = (f"{r['batch_name']}  ·  {r['stage']}  "
                       f"·  {r['opened']} opens  "
                       f"·  {r['open_rate']:.0f}% open rate")
        with st.expander(exp_label, expanded=False):
            l, right = st.columns([1.6, 1])
            with l:
                st.markdown(
                    f'<div style="margin-bottom:.3rem">{headline}'
                    f'{source_tag}</div>',
                    unsafe_allow_html=True)
                st.markdown(
                    _persona_bar(r["splits"], r["total_persona"], note),
                    unsafe_allow_html=True)
                if r["total_persona"] > 0:
                    parts = []
                    for label, count, col in r["splits"]:
                        pct = count / r["total_persona"] * 100
                        parts.append(
                            f'<span style="color:{INK};font-weight:600">'
                            f'{label}</span> '
                            f'<span style="color:{INK_SOFT}">{count} '
                            f'({pct:.0f}%)</span>')
                    st.markdown(
                        f'<div style="font-size:.85rem;margin-top:.3rem">'
                        f'{" &middot; ".join(parts)}</div>',
                        unsafe_allow_html=True)
            with right:
                open_col = (ACCENT if r["open_rate"] >= 20
                              else GOLD if r["open_rate"] >= 10 else WARN)
                st.markdown(
                    f'<div style="display:grid;grid-template-columns:'
                    f'1fr 1fr;gap:.5rem">'
                    f'<div style="background:{BG_SOFT};padding:.5rem;'
                    f'border-radius:4px;text-align:center">'
                    f'<div style="font-size:.7rem;color:{MUTED};'
                    f'text-transform:uppercase;letter-spacing:.1em">'
                    f'Sent</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;'
                    f'color:{INK}">{r["sent"]}</div></div>'
                    f'<div style="background:{BG_SOFT};padding:.5rem;'
                    f'border-radius:4px;text-align:center">'
                    f'<div style="font-size:.7rem;color:{MUTED};'
                    f'text-transform:uppercase;letter-spacing:.1em">'
                    f'Opens</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;'
                    f'color:{INK}">{r["opened"]}</div></div>'
                    f'<div style="background:{open_col}22;padding:.5rem;'
                    f'border-radius:4px;text-align:center">'
                    f'<div style="font-size:.7rem;color:{MUTED};'
                    f'text-transform:uppercase;letter-spacing:.1em">'
                    f'Open rate</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;'
                    f'color:{INK}">{r["open_rate"]:.0f}%</div></div>'
                    f'<div style="background:{BG_SOFT};padding:.5rem;'
                    f'border-radius:4px;text-align:center">'
                    f'<div style="font-size:.7rem;color:{MUTED};'
                    f'text-transform:uppercase;letter-spacing:.1em">'
                    f'Clicks</div>'
                    f'<div style="font-size:1.3rem;font-weight:700;'
                    f'color:{INK}">{r["clicked"]}</div></div>'
                    f'</div>', unsafe_allow_html=True)

            st.markdown(
                f'<hr style="border:none;border-top:1px solid {LINE};'
                f'margin:1rem 0 .8rem">', unsafe_allow_html=True)

            subj_html, subj_hits = _highlight_text(r["subject"])
            body_html, body_hits = _highlight_text(r["body"])
            all_hits = {p: subj_hits[p] + body_hits[p]
                          for p in PERSONA_ORDER}
            total_hits = sum(all_hits.values())

            st.markdown(
                f'<div style="font-size:.72rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.14em;'
                f'margin-bottom:.3rem">Email content '
                f'&mdash; words coloured by the persona they speak to'
                f'</div>',
                unsafe_allow_html=True)
            st.markdown(_legend_html(), unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-weight:600;font-size:1rem;color:{INK};'
                f'margin-bottom:.5rem">Subject: {subj_html}</div>'
                f'<div style="font-size:.92rem;color:{INK};line-height:1.6;'
                f'background:{BG_SOFT};padding:.9rem 1.1rem;'
                f'border-radius:6px;border-left:3px solid {LINE}">'
                f'{body_html}</div>',
                unsafe_allow_html=True)

            if total_hits > 0:
                copy_dom = max(all_hits.items(), key=lambda t: t[1])
                bits = [f"{p} {all_hits[p]}" for p in PERSONA_ORDER
                         if all_hits[p] > 0]
                # Compare copy vs actual openers
                open_dom = (r["dom"][0] if r["dom"] is not None else None)
                match_line = ""
                if open_dom and copy_dom[1] > 0:
                    if copy_dom[0] == open_dom:
                        match_line = (
                            f' &middot; <span style="color:{ACCENT};'
                            f'font-weight:700">MATCH</span> &mdash; '
                            f'copy language and top openers agree')
                    else:
                        match_line = (
                            f' &middot; <span style="color:{WARN};'
                            f'font-weight:700">MISMATCH</span> &mdash; '
                            f'copy speaks to <strong>{copy_dom[0]}'
                            f'</strong> but <strong>{open_dom}</strong> '
                            f'is the persona actually opening')
                st.markdown(
                    f'<div style="font-size:.8rem;color:{INK_SOFT};'
                    f'margin-top:.5rem">'
                    f'<strong>Copy language:</strong> '
                    f'{" &middot; ".join(bits)} hits &middot; '
                    f'speaks mostly to <strong>{copy_dom[0]}</strong>'
                    f'{match_line}</div>',
                    unsafe_allow_html=True)
            else:
                st.caption("No persona vocabulary detected in this "
                            "email - the copy reads as generic.")

            if r["source"] == "observed":
                mql_rows = _match_mql(r["batch_name"])
                if not mql_rows.empty:
                    st.markdown(
                        f'<div style="font-size:.72rem;color:{MUTED};'
                        f'text-transform:uppercase;letter-spacing:.14em;'
                        f'margin:.9rem 0 .3rem">Real people who engaged '
                        f'from this institution</div>',
                        unsafe_allow_html=True)
                    show = mql_rows[["first_name", "last_name",
                                       "job_title", "persona",
                                       "opens", "clicks"]].copy()
                    show.columns = ["First", "Last", "Job title",
                                     "Persona", "Opens", "Clicks"]
                    st.dataframe(show, use_container_width=True,
                                  hide_index=True)


# ==========================================================================
# Rollup: opens by persona across the whole tracked set
# ==========================================================================
st.markdown('<h2>Across all emails &mdash; who opens most?</h2>',
             unsafe_allow_html=True)
st.caption("Sum of persona-attributed opens across every tracked send. "
            "Observed and estimated combined.")

tot_r = int(sum(r["splits"][0][1] for r in enriched))
tot_f = int(sum(r["splits"][1][1] for r in enriched))
tot_i = int(sum(r["splits"][2][1] for r in enriched))
tot_all = tot_r + tot_f + tot_i

pc1, pc2, pc3 = st.columns(3)
with pc1:
    kpi_tile("Research opens", f"{tot_r}",
              sub=f"{tot_r/max(tot_all,1)*100:.0f}% of the total",
              color=ACCENT)
with pc2:
    kpi_tile("Finance opens", f"{tot_f}",
              sub=f"{tot_f/max(tot_all,1)*100:.0f}% of the total",
              color=GOLD)
with pc3:
    kpi_tile("IT-Systems opens", f"{tot_i}",
              sub=f"{tot_i/max(tot_all,1)*100:.0f}% of the total",
              color="#7A6A9A")

if tot_all > 0:
    ordered = sorted([("Research", tot_r), ("Finance", tot_f),
                        ("IT-Systems", tot_i)],
                       key=lambda t: t[1], reverse=True)
    dom_name, dom_v = ordered[0]
    weak_name, weak_v = ordered[-1]
    so_what(
        f"<strong>{dom_name}</strong> opens most of our email "
        f"({dom_v} of {tot_all} persona-attributed opens). "
        f"<strong>{weak_name}</strong> is the quietest with only "
        f"{weak_v}. If you want more of that persona, either send "
        f"them more email or rewrite subject lines in their language.",
        tone="info")
