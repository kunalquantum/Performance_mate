"""
Persona - Monthly persona email report.

REPORT of what actually happened, per persona, per month. Built
directly off real send data - no future planning, no manual entry.

Sources:
    campaign_batches.csv         - every send with sent/opened/clicked
    mql_engaged.csv              - real per-person engagement + persona
    persona_institution_coverage - contact mix per institution (fallback)

For each send, we resolve who the audience was - Research, Finance
or IT-Systems - using MQL evidence where we have it, else pro-rata
from the contact mix at the recipient institution. That lets us
report opens per persona per month against Ian's cadence rule of
2 per persona per month (cap at 3).
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
st.markdown('<h1>Monthly persona email report</h1>',
             unsafe_allow_html=True)
core_question("For the selected month: which personas did we email, "
                "how many sends each, and how did they engage?")
st.caption("A report of what actually went out and what happened. "
            "Driven directly by the tracked campaign data - no "
            "manual entry.")

TARGET_MIN = 2
TARGET_MAX = 3
PERSONAS = ["Research", "Finance", "IT-Systems"]
COL = {"Research": ACCENT, "Finance": GOLD, "IT-Systems": "#7A6A9A"}


# ==========================================================================
# Load data
# ==========================================================================
batches = load_csv("campaign_batches.csv")
coverage = load_csv("persona_institution_coverage.csv")
mql = load_csv("mql_engaged.csv")

if batches.empty:
    st.info("No tracked campaigns. Populate `data/campaign_batches.csv`.")
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
    for c in ("opens", "clicks"):
        if c in mql.columns:
            mql[c] = pd.to_numeric(mql[c],
                                     errors="coerce").fillna(0).astype(int)

# Month derived from sent_date
batches["month"] = pd.to_datetime(
    batches["sent_date"], errors="coerce").dt.strftime("%Y-%m")


# ==========================================================================
# Persona attribution
# ==========================================================================
def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _match_institution(name):
    if coverage.empty:
        return None
    nl = _norm(name)
    for _, row in coverage.iterrows():
        key = _norm(row.get("institution_key", ""))
        if key and (key in nl or nl in key):
            return row
    tokens = [t for t in nl.split() if len(t) >= 5
              and t not in ("university", "college")]
    for tok in tokens:
        m = coverage[coverage["institution_key"].astype(str).str.lower()
                       .str.contains(tok, na=False)]
        if not m.empty:
            return m.iloc[0]
    return None


def _match_mql(name):
    if mql.empty:
        return mql.iloc[0:0]
    nl = _norm(name)
    mask = mql["institution"].astype(str).apply(
        lambda x: _norm(x) in nl or nl in _norm(x))
    return mql[mask]


def _persona_split(row):
    """Return dict persona -> (share_of_sent, share_of_opens, source)."""
    name = str(row.get("batch_name", ""))
    mql_rows = _match_mql(name)
    inst_row = _match_institution(name)
    source = None
    weights = {p: 0.0 for p in PERSONAS}
    if not mql_rows.empty and mql_rows["opens"].sum() > 0:
        for p in PERSONAS:
            weights[p] = float(
                mql_rows[mql_rows["persona"] == p]["opens"].sum())
        if sum(weights.values()) > 0:
            source = "observed"
    if source is None and inst_row is not None:
        weights["Research"]   = float(inst_row.get("research", 0))
        weights["Finance"]    = float(inst_row.get("finance", 0))
        weights["IT-Systems"] = float(inst_row.get("it_systems", 0))
        if sum(weights.values()) > 0:
            source = "estimated"
    if source is None:
        return {p: (0.0, 0.0, None) for p in PERSONAS}
    tot = sum(weights.values())
    return {p: (weights[p] / tot, weights[p] / tot, source)
             for p in PERSONAS}


# Build persona-level rows: one row per (batch, persona) with sent/opens
per_persona = []
for _, r in batches.iterrows():
    split = _persona_split(r)
    for p in PERSONAS:
        share, _, source = split[p]
        if source is None:
            continue
        per_persona.append({
            "month":      r["month"],
            "batch_id":   int(r.get("batch_id") or 0),
            "batch_name": str(r.get("batch_name", "")),
            "stage":      str(r.get("stage", "")),
            "subject":    str(r.get("subject") or ""),
            "sent_date":  str(r.get("sent_date", "")),
            "persona":    p,
            "share":      share,
            "sent":       int(round(float(r.get("sent") or 0) * share)),
            "opens":      int(round(float(r.get("opened") or 0) * share)),
            "clicks":     int(round(float(r.get("clicked") or 0) * share)),
            "source":     source,
        })
pp = pd.DataFrame(per_persona)


# ==========================================================================
# Month picker
# ==========================================================================
months = sorted([m for m in batches["month"].dropna().unique()
                   if m], reverse=True)
if not months:
    st.info("No dated sends. Add `sent_date` to campaign_batches.csv.")
    st.stop()

pick = st.selectbox("Month", months, index=0, key="pmr_month")
month_batches = batches[batches["month"] == pick]
month_pp = pp[pp["month"] == pick] if not pp.empty else pp


# ==========================================================================
# Top-line report tiles
# ==========================================================================
n_sends = len(month_batches)
total_sent = int(month_batches["sent"].sum())
total_opens = int(month_batches["opened"].sum())
total_clicks = int(month_batches["clicked"].sum())
open_rate = total_opens / max(total_sent, 1) * 100

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Sends this month", f"{n_sends}",
              sub=f"across {month_batches['batch_name'].nunique()} "
                   f"campaigns",
              tooltip="Every batch stage that went out in the "
                      "selected month.")
with k2:
    kpi_tile("Emails delivered", f"{total_sent:,}",
              tooltip="Total recipient count across every send.")
with k3:
    kpi_tile("Total opens", f"{total_opens:,}",
              sub=f"{open_rate:.0f}% open rate",
              color=ACCENT if open_rate >= 20 else GOLD)
with k4:
    kpi_tile("Total clicks", f"{total_clicks:,}",
              sub=f"{total_clicks/max(total_opens,1)*100:.0f}% of opens",
              color=ACCENT if total_clicks > 0 else MUTED)


# ==========================================================================
# The persona report - three cards, actuals only
# ==========================================================================
st.markdown('<h2>How each persona was reached this month</h2>',
             unsafe_allow_html=True)
st.caption(f"Cadence rule: {TARGET_MIN}-{TARGET_MAX} persona-specific "
            "sends per persona per month. Numbers below are what "
            "actually happened, attributed from real send data.")

cols = st.columns(3)
persona_summary = {}
for col, p in zip(cols, PERSONAS):
    rows_p = month_pp[month_pp["persona"] == p]
    # Sends targeted at this persona = distinct batch_ids where this
    # persona had non-zero share. Count of sends, not fractional.
    n_p_sends = int(rows_p["batch_id"].nunique())
    p_sent = int(rows_p["sent"].sum())
    p_opens = int(rows_p["opens"].sum())
    p_clicks = int(rows_p["clicks"].sum())
    p_open_rate = p_opens / max(p_sent, 1) * 100
    persona_summary[p] = {
        "sends": n_p_sends, "sent": p_sent, "opens": p_opens,
        "clicks": p_clicks, "open_rate": p_open_rate}

    # Verdict against cadence
    if n_p_sends == 0:
        verdict, vcol = "No touch this month", GOLD
    elif n_p_sends < TARGET_MIN:
        verdict, vcol = f"Under target (need {TARGET_MIN}+)", GOLD
    elif n_p_sends > TARGET_MAX:
        verdict, vcol = f"Over the {TARGET_MAX}/month cap", WARN
    else:
        verdict, vcol = f"On target ({TARGET_MIN}-{TARGET_MAX})", ACCENT

    with col:
        st.markdown(
            f'<div style="border:1px solid {LINE};'
            f'border-top:4px solid {COL[p]};border-radius:8px;'
            f'padding:1rem 1.2rem;background:{BG};margin-bottom:.5rem">'
            f'<div class="eyebrow" style="color:{COL[p]};'
            f'margin-bottom:.5rem">{p}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;'
            f'gap:.4rem;margin-bottom:.5rem">'
            f'<div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.12em">Sends</div>'
            f'<div style="font-size:1.6rem;font-weight:700;color:{INK}">'
            f'{n_p_sends}</div></div>'
            f'<div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.12em">Reached</div>'
            f'<div style="font-size:1.6rem;font-weight:700;color:{INK}">'
            f'{p_sent}</div></div>'
            f'<div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.12em">Opens</div>'
            f'<div style="font-size:1.3rem;font-weight:600;'
            f'color:{COL[p]}">{p_opens}</div></div>'
            f'<div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.12em">Open %</div>'
            f'<div style="font-size:1.3rem;font-weight:600;color:{INK}">'
            f'{p_open_rate:.0f}%</div></div>'
            f'</div>'
            f'<div style="border-top:1px solid {LINE};padding-top:.5rem;'
            f'font-size:.78rem;color:{MUTED}">'
            f'<span style="text-transform:uppercase;letter-spacing:.12em">'
            f'Clicks</span> '
            f'<span style="color:{INK};font-weight:600">{p_clicks}</span> '
            f'&middot; '
            f'<span style="text-transform:uppercase;letter-spacing:.12em">'
            f'Target</span> '
            f'<span style="color:{INK};font-weight:600">'
            f'{TARGET_MIN}-{TARGET_MAX}</span></div>'
            f'<div style="margin-top:.6rem;padding-top:.5rem;'
            f'border-top:1px solid {LINE};font-size:.85rem;'
            f'color:{vcol};font-weight:600">{verdict}</div>'
            f'</div>', unsafe_allow_html=True)


# ==========================================================================
# So-whats from the actuals
# ==========================================================================
zero = [p for p in PERSONAS if persona_summary[p]["sends"] == 0]
under = [p for p in PERSONAS
          if 0 < persona_summary[p]["sends"] < TARGET_MIN]
over = [p for p in PERSONAS
         if persona_summary[p]["sends"] > TARGET_MAX]

if zero:
    so_what(
        f"<strong>{', '.join(zero)}</strong> received no attributable "
        f"email this month. That is the biggest gap in the cadence.",
        tone="warn")
if under:
    so_what(
        f"<strong>{', '.join(under)}</strong> received fewer than "
        f"{TARGET_MIN} sends. Below Ian&apos;s minimum cadence.",
        tone="warn")
if over:
    so_what(
        f"<strong>{', '.join(over)}</strong> received more than "
        f"{TARGET_MAX} sends - above the cap. Expect fatigue.",
        tone="warn")
if not zero and not under and not over:
    so_what(
        f"Every persona sits inside the "
        f"{TARGET_MIN}-{TARGET_MAX}/month cadence band for "
        f"{pick}.", tone="good")


# ==========================================================================
# Every send this month - the report line-by-line
# ==========================================================================
st.markdown('<h2>Every send this month</h2>', unsafe_allow_html=True)
st.caption("The report - one row per batch stage that went out. "
            "Dominant persona shown as a coloured pill.")

if month_batches.empty:
    st.info("No sends recorded for this month.")
else:
    rows = []
    hdr = (
        f'<div style="display:grid;grid-template-columns:'
        f'.9fr 1.6fr 2fr .6fr .6fr .6fr 1fr;gap:.5rem;'
        f'padding:.5rem .8rem;font-size:.7rem;color:{MUTED};'
        f'text-transform:uppercase;letter-spacing:.12em;'
        f'font-weight:600;border-bottom:1px solid {LINE};'
        f'background:{BG_SOFT}">'
        f'<div>Date</div><div>Campaign</div><div>Subject</div>'
        f'<div style="text-align:right">Sent</div>'
        f'<div style="text-align:right">Opens</div>'
        f'<div style="text-align:right">Open %</div>'
        f'<div>Reached mostly</div></div>')
    rows.append(hdr)

    for _, b in month_batches.sort_values("sent_date").iterrows():
        # Dominant persona for this batch
        rp = month_pp[month_pp["batch_id"] == int(b.get("batch_id") or 0)]
        if not rp.empty and rp["opens"].sum() > 0:
            dom = rp.loc[rp["opens"].idxmax()]
            dom_name = dom["persona"]
            dom_col = COL[dom_name]
            dom_share = dom["opens"] / rp["opens"].sum() * 100
            pill = (f'<span style="background:{dom_col}22;color:{INK};'
                    f'padding:.15rem .5rem;border-radius:3px;'
                    f'font-size:.78rem;font-weight:600">{dom_name} '
                    f'{dom_share:.0f}%</span>')
        else:
            pill = (f'<span style="color:{MUTED};font-size:.78rem;'
                    f'font-style:italic">no signal</span>')

        sent_i = int(b.get("sent") or 0)
        opens_i = int(b.get("opened") or 0)
        or_ = opens_i / max(int(b.get("delivered") or sent_i), 1) * 100
        or_col = (ACCENT if or_ >= 20 else GOLD if or_ >= 10 else WARN)
        rows.append(
            f'<div style="display:grid;grid-template-columns:'
            f'.9fr 1.6fr 2fr .6fr .6fr .6fr 1fr;gap:.5rem;'
            f'padding:.55rem .8rem;font-size:.85rem;'
            f'border-bottom:1px solid {LINE};align-items:center">'
            f'<div style="color:{INK_SOFT};font-size:.78rem">'
            f'{str(b.get("sent_date",""))[:10]}</div>'
            f'<div style="color:{INK};font-weight:600;line-height:1.3">'
            f'{str(b.get("batch_name",""))[:34]}<br>'
            f'<span style="color:{MUTED};font-size:.72rem;'
            f'font-weight:400">{str(b.get("stage",""))}</span></div>'
            f'<div style="color:{INK_SOFT};font-size:.82rem;'
            f'line-height:1.3">{str(b.get("subject",""))[:70]}</div>'
            f'<div style="text-align:right;color:{INK}">{sent_i}</div>'
            f'<div style="text-align:right;color:{INK}">{opens_i}</div>'
            f'<div style="text-align:right;background:{or_col}22;'
            f'color:{INK};font-weight:700;padding:.15rem .4rem;'
            f'border-radius:3px">{or_:.0f}%</div>'
            f'<div>{pill}</div>'
            f'</div>')
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:6px;'
        f'background:{BG};overflow:hidden">{"".join(rows)}</div>',
        unsafe_allow_html=True)


# ==========================================================================
# Last N months at a glance
# ==========================================================================
st.markdown('<h2>Last six months at a glance</h2>',
             unsafe_allow_html=True)
st.caption("Sends per persona per month. Green = inside cadence, "
            "gold = under, red = over.")
recent = months[:6]
if not pp.empty:
    pivot = (pp[pp["month"].isin(recent)]
             .groupby(["persona", "month"])["batch_id"]
             .nunique().unstack(fill_value=0))
    # order rows and cols
    pivot = pivot.reindex([p for p in PERSONAS if p in pivot.index])
    pivot = pivot[sorted(pivot.columns, reverse=True)]

    hdr_cells = ["Persona"] + [str(c) for c in pivot.columns] + \
                 ["Target/mo"]
    grid_cols = f'1.4fr {" ".join([".7fr"] * len(pivot.columns))} .7fr'
    hist = [
        f'<div style="display:grid;grid-template-columns:{grid_cols};'
        f'gap:.4rem;padding:.5rem .8rem;font-size:.72rem;color:{MUTED};'
        f'text-transform:uppercase;letter-spacing:.12em;font-weight:600;'
        f'border-bottom:1px solid {LINE};background:{BG_SOFT}">'
        + "".join(f'<div>{c}</div>' for c in hdr_cells) + '</div>'
    ]
    for persona, series in pivot.iterrows():
        cells = [f'<div style="color:{INK};font-weight:600">{persona}</div>']
        for c in pivot.columns:
            v = int(series[c])
            bg = ("#DDEEEC" if TARGET_MIN <= v <= TARGET_MAX
                    else "#FBEDED" if v > TARGET_MAX else "#F7F0DA")
            cells.append(
                f'<div style="background:{bg};padding:.15rem .4rem;'
                f'border-radius:3px;color:{INK};font-weight:600;'
                f'text-align:center">{v}</div>')
        cells.append(
            f'<div style="color:{MUTED};text-align:center">'
            f'{TARGET_MIN}-{TARGET_MAX}</div>')
        hist.append(
            f'<div style="display:grid;grid-template-columns:{grid_cols};'
            f'gap:.4rem;padding:.55rem .8rem;font-size:.9rem;'
            f'border-bottom:1px solid {LINE};align-items:center">'
            + "".join(cells) + '</div>')
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:6px;'
        f'background:{BG};overflow:hidden">{"".join(hist)}</div>',
        unsafe_allow_html=True)
else:
    st.info("Not enough persona-attributable sends across the "
             "recent months to draw a rolling picture.")
