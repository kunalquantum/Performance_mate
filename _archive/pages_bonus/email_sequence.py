"""
Email - Sequence matrix.

Side-by-side view of a campaign and its follow-ups. Three columns
(Base | Follow-up A | Follow-up B), each stacked as:

    1. Email card (subject + full body)
    2. Content measurement (Challenge / Result / seven-slot check)
    3. Performance (real funnel if this is a tracked batch, otherwise the
       history-derived expected open-rate band)

Two data sources:
    data/campaign_batches.csv  - real per-email sends with real funnel
                                  (Sent -> Delivered -> Opened -> Replied)
    data/campaigns.csv         - draft campaigns from the marketing calendar
"""
from shared import (core_question, inject_css, render_status_key, so_what, kpi_tile,
                     load_csv, INK, INK_SOFT, MUTED, LINE,
                     BG, BG_SOFT, ACCENT, ACCENT_SOFT, WARN, GOLD)
import re
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Compare sequences</h1>', unsafe_allow_html=True)
core_question("How does a base email and its follow-ups compare on copy quality and on actual performance?")
st.caption("Base email and its follow-ups side by side. Each column "
            "shows the actual copy, how our system scores it, and how "
            "the send actually performed (opened, clicked, replied). "
            "Green means strong, gold means look closer.")
render_status_key()

with st.expander("What the score terms mean", expanded=False):
    st.markdown("""
- **Problem framing (0-100)** &mdash; does the email name a real problem?
  Rewards a pain-named subject, a stakeholder-demand line, and a
  problem-cost chain.
- **Proof (0-100)** &mdash; does the email back the claim? Rewards named
  customer institutions, concrete percentages, and one clear CTA.
- **Overall copy (0-100)** &mdash; the blend of Problem framing + Proof,
  minus a penalty for weak phrases. 66+ is the WP5 zone (the reference
  email everything is scored against).
- **Open rate** &mdash; share of delivered emails that were opened. SaaS
  benchmark: 20%. Below 10% usually points to a subject-line or
  list-quality problem.
- **Click rate** &mdash; share of delivered emails where the reader
  clicked a link. Industry benchmark: 2-3%.
- **Reply rate** &mdash; share of delivered emails that got a reply.
  Strongest pipeline signal we have.
- **Funnel** &mdash; the drop-off from Sent &rarr; Delivered &rarr;
  Opened &rarr; Clicked/Replied. Each bar shows the count at that stage
  as a % of what was sent.
""")

batches_df   = load_csv("campaign_batches.csv")
campaigns_df = load_csv("campaigns.csv")
emails_df    = load_csv("emails.csv")

if batches_df.empty and campaigns_df.empty:
    st.info("No sequence data. Run `python etl/campaign_etl.py` for draft "
             "campaigns, or add rows to `data/campaign_batches.csv` for "
             "tracked sends.")
    st.stop()


# ==========================================================================
# House vocabulary + rules (mirrors the Contents analysis page)
# ==========================================================================
SAAS_VOCAB = {
    "pain_points": [
        "lack of visibility", "no single source of truth",
        "disconnected systems", "fragmented workflows",
        "manual tracking", "missed opportunit",
    ],
    "manual_work": [
        "time-consuming", "repetitive administration",
        "duplicate data entry", "human error",
        "operational inefficiency", "manual workload",
        "back track", "endless email",
    ],
    "outcomes": [
        "reduce risk", "increase efficiency", "productivity",
        "accurate forecasting", "reduce cost", "save time",
        "improve visibility", "single view", "end to end",
    ],
}
WEAK_SWAPS = {
    "utilise": "use", "utilize": "use",
    "leverage": "use", "streamline": "simplify",
    "solution": "platform", "synergy": "alignment",
    "in order to": "to", "at the end of the day": "the point is",
    "a lot of": "several",
}
CHALLENGE_SUBJECT_WORDS = [
    "overcoming", "manual", "delay", "delays", "hidden", "lost",
    "missed", "missing", "risk", "gap", "disconnect", "backlog",
    "burden", "reduce", "cut", "stop", "why", "how", "when",
    "without", "beyond", "fixing", "smart", "smarter",
    "capturing more", "more funding", "one system",
]
STAKEHOLDER_TERMS = [
    "leadership", "funder", "funders", "government",
    "board", "vice chancellor", "director of research",
    "principal investigator", "regulators", "auditor",
    "auditors", "research office",
]
DEMAND_VERBS = ["want", "need", "expect", "require", "ask for", "demand"]
PROBLEM_CONNECTIVES = [" because ", ", so ", " while ", " but ",
                        " however ", " which means ", " so that "]
CTA_PHRASES = [
    "read the whitepaper", "read the white paper",
    "download the whitepaper", "book a call", "book a demo",
    "get in touch", "reply to this email", "register",
    "come by our", "meet our team", "learn more",
    "set up a short call", "see how grantsnow",
]


def analyse(subject, body):
    text = f"{subject}\n{body}"
    lo = text.lower()
    subj_lo = subject.lower()
    words = re.findall(r"[a-zA-Z]+", body)

    slot1 = bool(subject.strip()) and any(w in subj_lo
                                             for w in CHALLENGE_SUBJECT_WORDS)
    slot2 = bool(re.match(r"^\s*(hi|hello|dear|good (morning|afternoon))",
                            body, flags=re.IGNORECASE))
    slot3 = (any(t in lo for t in STAKEHOLDER_TERMS)
              and any(v in lo for v in DEMAND_VERBS))
    conn = sum(lo.count(c) for c in PROBLEM_CONNECTIVES)
    slot4 = conn >= 2
    named_customers = re.findall(
        r"(University of [A-Z][A-Za-z ]+|"
        r"Institute of [A-Z][A-Za-z ]+|"
        r"[A-Z][A-Za-z]+ (?:College|University|Institute)"
        r"(?: of [A-Z][A-Za-z ]+)?)",
        body)
    named_customers = list(dict.fromkeys(
        [n.strip() for n in named_customers]))
    slot5 = len(named_customers) >= 1
    pct_hits = re.findall(r"\b\d{1,3}\s*%", body)
    slot6 = len(pct_hits) >= 1
    cta_hits = [c for c in CTA_PHRASES if c in lo]
    slot7 = len(cta_hits) >= 1

    slots = {
        "Pain-named subject": slot1,
        "Personal greeting":  slot2,
        "Stakeholder line":   slot3,
        "Problem-cost chain": slot4,
        "Named customer":     slot5,
        "Concrete numbers":   slot6,
        "Single CTA":         slot7,
    }
    challenge = int(100 * sum([slot1, slot3, slot4]) / 3)
    result    = int(100 * sum([slot5, slot6, slot7]) / 3)
    weak = [(w, s) for w, s in WEAK_SWAPS.items() if w in lo]
    house = max(0, min(100,
                          int(0.45 * challenge + 0.45 * result
                                + (10 if slot2 else 0)
                                - 4 * min(len(weak), 3))))
    return {
        "challenge": challenge, "result": result, "house": house,
        "slots": slots, "weak": weak,
        "named_customers": named_customers,
        "pct_hits": pct_hits, "cta_hits": cta_hits,
        "words": len(words), "connectives": conn,
    }


# ==========================================================================
# History-driven expected open-rate band (fallback when no real numbers)
# ==========================================================================
def _wilson(k, n, z=1.96):
    if not n or n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    s = (z / d) * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, c - s), p, min(1.0, c + s))


def history_prior(batch_size):
    if emails_df.empty:
        return None
    hist = emails_df.dropna(subset=["contacts", "delivered",
                                       "opened"]).copy()
    hist = hist[hist["delivered"] > 0]
    if len(hist) < 4:
        return None
    match = hist[hist["contacts"].apply(
        lambda c: batch_size * 0.5 <= c <= batch_size * 2.0)]
    label = f"weeks with {int(batch_size*0.5)}-{int(batch_size*2)} contacts"
    if len(match) < 3:
        try:
            hist["_b"] = pd.qcut(hist["contacts"], q=4,
                                    duplicates="drop")
            medians = hist.groupby("_b", observed=True)[
                "contacts"].median()
            closest = (medians - batch_size).abs().idxmin()
            match = hist[hist["_b"] == closest]
            label = (f"weeks near ~{int(medians[closest])} "
                       "contacts (nearest bucket)")
        except Exception:
            return None
    k = float(match["opened"].sum())
    n = float(match["delivered"].sum())
    if n == 0:
        return None
    lo, mid, hi = _wilson(k, n)
    return (lo, mid, hi, len(match), label)


# ==========================================================================
# CROSS-BATCH LEADERBOARD - every tracked batch on one row
# ==========================================================================
if not batches_df.empty:
    st.markdown('<h3>All tracked batches at a glance</h3>',
                 unsafe_allow_html=True)
    st.caption("Every batch we&apos;ve tracked, ranked by open rate. "
                "Green = above 20% benchmark, gold = below.")

    dfb = batches_df.copy()
    # Aggregate per batch: totals + rates
    lead = (dfb.groupby(["batch_id", "batch_name"])
             .agg(sent=("sent", "sum"),
                   delivered=("delivered", "sum"),
                   opened=("opened", "sum"),
                   clicked=("clicked", lambda s: int(
                       s.fillna(0).sum()) if s.notna().any() else None),
                   replied=("replied", lambda s: int(
                       s.fillna(0).sum()) if s.notna().any() else None),
                   stages=("stage", "count"))
             .reset_index())
    lead["open_rate"] = lead["opened"] / lead["delivered"].replace(0, 1) \
        * 100
    lead["click_rate"] = lead.apply(
        lambda r: (r["clicked"] / r["delivered"] * 100)
        if pd.notna(r["clicked"]) and r["delivered"] else None, axis=1)
    lead["reply_rate"] = lead.apply(
        lambda r: (r["replied"] / r["delivered"] * 100)
        if pd.notna(r["replied"]) and r["delivered"] else None, axis=1)
    lead = lead.sort_values("open_rate", ascending=False)

    # Render as a coloured HTML table (dataframe styling in Streamlit
    # is finicky with our house CSS, so we roll our own)
    header_html = (
        f'<div style="display:grid;grid-template-columns:'
        f'2fr .6fr .8fr .8fr .8fr .8fr;gap:.5rem;padding:.5rem .8rem;'
        f'font-size:.72rem;text-transform:uppercase;'
        f'letter-spacing:.12em;color:{MUTED};font-weight:600;'
        f'border-bottom:1px solid {LINE}">'
        f'<div>Batch</div><div>Emails</div><div>Sent</div>'
        f'<div>Open rate</div><div>Click rate</div><div>Reply rate</div>'
        f'</div>')
    rows_html = [header_html]
    for _, r in lead.iterrows():
        _open_col = ACCENT if r["open_rate"] >= 20 else GOLD
        _click = (f'<span style="color:{ACCENT}">'
                    f'{r["click_rate"]:.0f}%</span>'
                    if pd.notna(r["click_rate"]) else
                    f'<span style="color:{MUTED}">-</span>')
        _reply = (f'<span style="color:{ACCENT}">'
                    f'{r["reply_rate"]:.0f}%</span>'
                    if pd.notna(r["reply_rate"]) else
                    f'<span style="color:{MUTED}">-</span>')
        rows_html.append(
            f'<div style="display:grid;grid-template-columns:'
            f'2fr .6fr .8fr .8fr .8fr .8fr;gap:.5rem;padding:.55rem .8rem;'
            f'font-size:.88rem;border-bottom:1px solid {LINE};'
            f'align-items:center">'
            f'<div style="color:{INK};font-weight:600">'
            f'{r["batch_name"]}</div>'
            f'<div style="color:{INK_SOFT}">{int(r["stages"])}</div>'
            f'<div style="color:{INK_SOFT}">{int(r["sent"])}</div>'
            f'<div style="color:{_open_col};font-weight:700">'
            f'{r["open_rate"]:.0f}%</div>'
            f'<div>{_click}</div>'
            f'<div>{_reply}</div>'
            f'</div>')
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:6px;'
        f'background:{BG};margin-bottom:1.5rem;overflow:hidden">'
        + "".join(rows_html) + '</div>',
        unsafe_allow_html=True)

    # So-what summary across all batches
    _best  = lead.iloc[0]
    _worst = lead.iloc[-1]
    _diff  = _best["open_rate"] - _worst["open_rate"]
    if len(lead) >= 2 and _diff >= 20:
        so_what(
            f"<strong>{_best['batch_name']}</strong> opened at "
            f"{_best['open_rate']:.0f}% while "
            f"<strong>{_worst['batch_name']}</strong> opened at "
            f"{_worst['open_rate']:.0f}%. That is a "
            f"{_diff:.0f}-point spread across the same product - "
            f"audience choice is the biggest lever here, not copy.",
            tone="info")

    st.markdown('<div style="margin:1.5rem 0"></div>',
                 unsafe_allow_html=True)


# ==========================================================================
# SOURCE PICKER: tracked batch vs draft campaign
# ==========================================================================
source_options = []
if not batches_df.empty:
    source_options.append("Tracked batches (real funnel)")
if not campaigns_df.empty:
    source_options.append("Draft campaigns (marketing calendar)")

source = st.radio("Source", source_options, horizontal=True,
                    key="seq_source")

# Load the right dataframe into a canonical shape:
#   seq_name, stage, subject, body, sent, delivered, opened, replied
if source.startswith("Tracked"):
    grp = (batches_df.groupby("batch_id")
            .agg(name=("batch_name", "first"),
                  stages=("stage", lambda s: list(s)),
                  sent_date=("sent_date", "first"))
            .reset_index())
    grp["label"] = grp.apply(
        lambda r: f"Batch {int(r['batch_id'])} - {r['name']}",
        axis=1)
    options = grp["label"].tolist()
    pick = st.selectbox("Batch", options, key="seq_pick_batch")
    picked_row = grp.iloc[options.index(pick)]
    picked_id = int(picked_row["batch_id"])
    seq = batches_df[batches_df["batch_id"] == picked_id].copy()
    seq_name = picked_row["name"]
    real_metrics = True
else:
    grp = (campaigns_df.groupby("campaign_id")
            .agg(name=("campaign_name", "first"),
                  stages=("stage", lambda s: list(s)))
            .reset_index())
    grp["label"] = grp.apply(
        lambda r: f"#{int(r['campaign_id'])} - {r['name']} "
                    f"({len(r['stages'])} email"
                    f"{'s' if len(r['stages'])>1 else ''})",
        axis=1)
    options = grp["label"].tolist()
    default_idx = 0
    for i, r in grp.iterrows():
        if set(["Base", "Follow-up A", "Follow-up B"]).issubset(
                set(r["stages"])):
            default_idx = i
            break
    pick = st.selectbox("Campaign", options, index=default_idx,
                         key="seq_pick_campaign")
    picked_row = grp.iloc[options.index(pick)]
    picked_id = int(picked_row["campaign_id"])
    seq = campaigns_df[campaigns_df["campaign_id"] == picked_id].copy()
    # Fill in placeholder funnel cols so downstream code is uniform
    for c in ("sent", "delivered", "opened", "replied"):
        seq[c] = pd.NA
    seq_name = picked_row["name"]
    real_metrics = False

# Canonical stage order
stage_order = ["Base", "Follow-up A", "Follow-up B", "Follow-up C"]
seq["stage_order"] = seq["stage"].map(
    {s: i for i, s in enumerate(stage_order)})
seq = seq.sort_values("stage_order").reset_index(drop=True)

st.caption(f"**{seq_name}** &middot; {len(seq)} email"
            f"{'s' if len(seq) != 1 else ''} in the sequence")


# ==========================================================================
# Render N columns (one per stage)
# ==========================================================================
if len(seq) == 0:
    st.info("No emails in this campaign.")
    st.stop()

cols = st.columns(len(seq))

STAGE_COLOR = {
    "Base": ACCENT,
    "Follow-up A": GOLD,
    "Follow-up B": "#7A6A9A",
    "Follow-up C": MUTED,
}


def _slot_row(label, ok):
    icon = "OK" if ok else "MISS"
    color = ACCENT if ok else "#B34747"
    return (f'<div style="padding:.15rem 0;font-size:.85rem">'
            f'<span style="color:{color};font-weight:600">{icon}</span>'
            f'&nbsp;{label}</div>')


def _kpi_html(label, value, sub="", color=None, tooltip=""):
    color_style = f'color:{color}' if color else ''
    tip = f' title="{tooltip}"' if tooltip else ''
    cursor = ' cursor:help;' if tooltip else ''
    return (f'<div class="kpi"{tip} style="margin-bottom:.5rem;{cursor}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="font-size:1.4rem;{color_style}">'
            f'{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')


def _funnel_row(label, num, denom, colour):
    pct = (num / denom * 100) if denom else 0
    bar_pct = min(100, pct)
    return (f'<div style="margin:.35rem 0">'
            f'<div style="display:flex;justify-content:space-between;'
            f'font-size:.78rem;margin-bottom:.15rem">'
            f'<span style="color:{MUTED};text-transform:uppercase;'
            f'letter-spacing:.1em">{label}</span>'
            f'<span style="color:{INK};font-weight:600">'
            f'{int(num)} &middot; {pct:.0f}%</span>'
            f'</div>'
            f'<div style="height:6px;background:{LINE};border-radius:3px;'
            f'overflow:hidden">'
            f'<div style="height:100%;width:{bar_pct}%;background:{colour}">'
            f'</div></div></div>')


for col, (_, row) in zip(cols, seq.iterrows()):
    stage = row["stage"]
    subject = str(row.get("subject") or "").strip()
    body    = str(row.get("body") or "").strip()
    colour  = STAGE_COLOR.get(stage, ACCENT)
    a = analyse(subject, body)

    with col:
        # ---------- Section 1: EMAIL CARD ----------
        st.markdown(
            f'<div style="border:1px solid {LINE};border-top:4px solid '
            f'{colour};border-radius:8px;padding:1rem 1.1rem;'
            f'background:{BG};margin-bottom:1rem">'
            f'<div class="eyebrow" style="color:{colour};margin-bottom:.4rem">'
            f'{stage}</div>'
            f'<div style="font-weight:600;font-size:.98rem;color:{INK};'
            f'line-height:1.35;margin-bottom:.5rem">'
            f'{subject or "(no subject line)"}</div>'
            f'<div style="font-size:.75rem;color:{MUTED};'
            f'text-transform:uppercase;letter-spacing:.14em">'
            f'Body &middot; {a["words"]} words</div>'
            f'</div>', unsafe_allow_html=True)
        with st.expander("Show body", expanded=False):
            st.text(body if body else "(no body)")

        # ---------- Section 2: CONTENT MEASUREMENT ----------
        st.markdown(
            '<div class="eyebrow" style="margin-top:.5rem">'
            'Content measurement</div>', unsafe_allow_html=True)
        st.markdown(_kpi_html(
            "Problem framing", f"{a['challenge']}",
            "does the email name a real problem?",
            tooltip="0-100 score. Rewards a pain-named subject, a "
                     "line about who wants what (leadership, funders...) "
                     "and a chain of problem-cost sentences. Higher = "
                     "the reader recognises their situation earlier."),
                     unsafe_allow_html=True)
        st.markdown(_kpi_html(
            "Proof", f"{a['result']}",
            "named customers, real numbers, one CTA",
            tooltip="0-100 score. Rewards specific customer names "
                     "(Institute of X, University of Y), concrete "
                     "percentages, and one clear call to action."),
                     unsafe_allow_html=True)
        st.markdown(_kpi_html(
            "Overall copy", f"{a['house']}",
            "blended 0-100",
            tooltip="Blended score of Problem framing + Proof, minus "
                     "a penalty for weak phrases (utilise, leverage, "
                     "streamline, solution). 66+ is the WP5 zone."),
                     unsafe_allow_html=True)

        st.markdown(
            f'<div style="border:1px solid {LINE};border-radius:6px;'
            f'padding:.6rem .8rem;background:{BG_SOFT};margin-top:.4rem">'
            f'<div class="eyebrow" style="margin-bottom:.3rem">'
            f'Seven-slot check</div>'
            + "".join(_slot_row(k, v) for k, v in a["slots"].items())
            + '</div>', unsafe_allow_html=True)

        _evidence = []
        if a["named_customers"]:
            _evidence.append(
                f'<strong>Named:</strong> '
                f'{", ".join(a["named_customers"][:3])}'
                + (" ..." if len(a["named_customers"]) > 3 else ""))
        if a["pct_hits"]:
            _evidence.append(
                f'<strong>Numbers:</strong> '
                f'{", ".join(a["pct_hits"])}')
        if a["cta_hits"]:
            _evidence.append(
                f'<strong>CTA:</strong> {a["cta_hits"][0]}')
        if a["weak"]:
            _evidence.append(
                f'<strong style="color:#B34747">Weak:</strong> '
                + ", ".join(w for w, _ in a["weak"]))
        if _evidence:
            st.markdown(
                f'<div style="font-size:.78rem;color:{INK_SOFT};'
                f'margin-top:.5rem;line-height:1.5">'
                + "<br>".join(_evidence)
                + '</div>', unsafe_allow_html=True)

        # ---------- Section 3: PERFORMANCE ----------
        st.markdown(
            '<div class="eyebrow" style="margin-top:1rem">'
            'Performance</div>', unsafe_allow_html=True)

        if real_metrics and pd.notna(row.get("sent")):
            sent      = int(row["sent"])
            delivered = int(row["delivered"])
            opened    = int(row["opened"])
            clicked   = int(row["clicked"]) if pd.notna(
                row.get("clicked")) else None
            replied   = int(row["replied"]) if pd.notna(
                row.get("replied")) else None
            sent_date = row.get("sent_date", "")

            open_rate  = opened / max(delivered, 1) * 100

            # Headline open-rate tile
            _color_open = ACCENT if open_rate >= 20 else GOLD
            st.markdown(_kpi_html(
                "Open rate",
                f"{open_rate:.0f}%",
                f"{opened} of {delivered} delivered",
                color=_color_open,
                tooltip="Share of delivered emails that were opened. "
                         "SaaS industry benchmark: 20%. Below 10% "
                         "usually points to a subject-line or list-"
                         "quality problem."),
                unsafe_allow_html=True)

            # Secondary tile: whichever downstream signal this batch tracks
            if replied is not None and replied > 0:
                reply_rate = replied / max(delivered, 1) * 100
                st.markdown(_kpi_html(
                    "Reply rate",
                    f"{reply_rate:.0f}%",
                    f"{replied} replied", color=ACCENT,
                    tooltip="Share of delivered emails that got a "
                             "reply. This is the strongest pipeline "
                             "signal - a reply means the copy earned "
                             "a conversation."),
                             unsafe_allow_html=True)
            elif clicked is not None and clicked > 0:
                click_rate = clicked / max(delivered, 1) * 100
                st.markdown(_kpi_html(
                    "Click rate",
                    f"{click_rate:.0f}%",
                    f"{clicked} clicked", color=ACCENT,
                    tooltip="Share of delivered emails where the "
                             "reader clicked a link. Industry "
                             "benchmark: 2-3%."),
                             unsafe_allow_html=True)

            # Funnel bars: Sent -> Delivered -> Opened -> [Clicked] -> [Replied]
            funnel_rows = (
                _funnel_row("Sent",      sent,      sent, colour)
                + _funnel_row("Delivered", delivered, sent, colour)
                + _funnel_row("Opened",    opened,    sent, colour)
            )
            if clicked is not None:
                funnel_rows += _funnel_row("Clicked", clicked, sent, colour)
            if replied is not None:
                funnel_rows += _funnel_row("Replied", replied, sent, colour)
            st.markdown(
                f'<div style="border:1px solid {LINE};border-radius:6px;'
                f'padding:.6rem .8rem;background:{BG};margin-top:.4rem">'
                f'<div class="eyebrow" style="margin-bottom:.3rem">'
                f'Funnel</div>' + funnel_rows + '</div>',
                unsafe_allow_html=True)

            _bench_ok = open_rate >= 20
            _bench_color = ACCENT if _bench_ok else GOLD
            st.markdown(
                f'<div style="font-size:.78rem;margin-top:.5rem;'
                f'color:{INK_SOFT}">'
                f'<strong>SaaS benchmark 20%:</strong> '
                f'<span style="color:{_bench_color};font-weight:600">'
                f'{"met" if _bench_ok else "below"}</span>'
                f'{f" &middot; sent {sent_date}" if sent_date else ""}'
                f'</div>', unsafe_allow_html=True)
        else:
            # Fallback: history-derived expected band
            avg_contacts = 500
            if not emails_df.empty:
                try:
                    avg_contacts = int(
                        emails_df["contacts"].dropna().median())
                except Exception:
                    pass
            prior = history_prior(avg_contacts)
            if prior is None:
                st.info("No history baseline available yet.")
            else:
                lo, mid, hi, n_weeks, label = prior
                st.markdown(_kpi_html(
                    "Likely open rate",
                    f"{lo*100:.0f}% - {hi*100:.0f}%",
                    f"typical {mid*100:.1f}% on {n_weeks} similar sends"),
                             unsafe_allow_html=True)
                _bench_ok = mid >= 0.20
                _bench_color = ACCENT if _bench_ok else GOLD
                st.markdown(
                    f'<div style="border:1px solid {LINE};'
                    f'border-radius:6px;padding:.5rem .8rem;'
                    f'background:{BG_SOFT};font-size:.82rem">'
                    f'<strong>SaaS benchmark:</strong> 20% open. '
                    f'<span style="color:{_bench_color};font-weight:600">'
                    f'{"Meeting" if _bench_ok else "Below"}</span> today.'
                    f'</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:.72rem;color:{MUTED};'
                f'margin-top:.5rem;line-height:1.4">'
                f'This is a draft campaign - no send yet. The band above '
                f'is a portfolio prior from history.</div>',
                unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Cross-column takeaway
# --------------------------------------------------------------------------
st.markdown('<div style="margin:2.5rem 0 0;border-top:1px solid '
             + LINE + '"></div>', unsafe_allow_html=True)
st.markdown('<h3>Sequence read-across</h3>', unsafe_allow_html=True)

scores = [analyse(str(r.get("subject") or ""),
                     str(r.get("body") or ""))
             for _, r in seq.iterrows()]

lines = []
if len(scores) >= 2:
    ch_series = [s["challenge"] for s in scores]
    re_series = [s["result"]    for s in scores]
    if ch_series[0] > ch_series[-1]:
        lines.append("Challenge framing weakens as the sequence "
                      "progresses - follow-ups drop the pain hook.")
    elif ch_series[-1] > ch_series[0]:
        lines.append("Follow-ups strengthen the challenge framing vs "
                      "the base.")
    else:
        lines.append("Challenge framing is stable across the sequence.")
    if re_series[0] < re_series[-1]:
        lines.append("Result framing (named customers, numbers, CTA) "
                      "gets stronger across the follow-ups.")
    elif re_series[0] > re_series[-1]:
        lines.append("Result framing weakens across the follow-ups - "
                      "consider carrying named proof into every touch.")
    else:
        lines.append("Result framing is stable across the sequence.")

# If real numbers, also read-across on the funnel
if real_metrics and seq["opened"].notna().sum() >= 2:
    open_rates = (seq["opened"] / seq["delivered"].replace(0, 1)
                    * 100).tolist()
    best_open_idx = int(pd.Series(open_rates).idxmax())
    best_open_stage = seq.iloc[best_open_idx]["stage"]

    # Pick downstream metric this batch tracks: replied preferred,
    # otherwise clicked.
    downstream_col = None
    downstream_label = None
    if "replied" in seq.columns and seq["replied"].notna().sum() >= 2:
        downstream_col = "replied"
        downstream_label = "reply"
    elif "clicked" in seq.columns and seq["clicked"].notna().sum() >= 2:
        downstream_col = "clicked"
        downstream_label = "click"

    if downstream_col:
        rates = (seq[downstream_col] / seq["delivered"].replace(0, 1)
                  * 100).tolist()
        best_idx = int(pd.Series(rates).idxmax())
        best_stage = seq.iloc[best_idx]["stage"]
        lines.append(
            f"Best open rate: **{best_open_stage}** at "
            f"{open_rates[best_open_idx]:.0f}%. "
            f"Best {downstream_label} rate: **{best_stage}** at "
            f"{rates[best_idx]:.0f}%.")
        total_sent = int(seq["sent"].sum())
        total_opened = int(seq["opened"].sum())
        total_down = int(seq[downstream_col].fillna(0).sum())
        lines.append(
            f"Sequence funnel: **{total_sent}** sent &rarr; "
            f"**{total_opened}** opened &rarr; **{total_down}** "
            f"{downstream_label}ed. Across the whole sequence, "
            f"{downstream_label} rate is "
            f"{total_down/max(total_sent,1)*100:.0f}%.")
    else:
        lines.append(
            f"Best open rate: **{best_open_stage}** at "
            f"{open_rates[best_open_idx]:.0f}%.")
        total_sent   = int(seq["sent"].sum())
        total_opened = int(seq["opened"].sum())
        lines.append(
            f"Sequence funnel: **{total_sent}** sent &rarr; "
            f"**{total_opened}** opened. Across the whole sequence, "
            f"open rate is "
            f"{total_opened/max(total_sent,1)*100:.0f}%.")

for line in lines:
    st.markdown(
        f'<div style="background:#faf7f0;border-left:3px solid '
        f'{ACCENT};padding:.5rem 1rem;margin:.4rem 0;border-radius:4px">'
        f'{line}</div>', unsafe_allow_html=True)
if not lines:
    st.caption("Only one email in this sequence, no read-across to show.")
