"""
Email - Winners diagnostic.

Ian's spec items 5 + 6.

For each tracked email we have real open / click / reply numbers. This
page splits them into winners (top third by open rate) and rest, then
compares every measurable attribute of the copy to say WHY the winners
worked. Output is a set of rule-based recommendations you can act on
in the next send.

Attributes compared:
    Subject: length in words, whether it names a challenge or a number
    Body: word count, number of named customers, presence of a percent,
          presence of a clear CTA
    Timing: day of week sent
    Copy target persona (from vocabulary classifier)
    Content type (event / product / funding / general)
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

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Winners diagnostic</h1>', unsafe_allow_html=True)
core_question("Why did the best-performing emails work, and what "
                "should we change on the next send to turn more "
                "clicks into enquiries?")
st.caption("Compares every tracked email split into winners (top "
            "third by open rate) vs the rest. Attribute by "
            "attribute. Each row of the comparison table generates "
            "a plain-English recommendation.")
render_status_key()

with st.expander("How the split works", expanded=False):
    st.markdown("""
- **Winners** = the top third of tracked emails by open rate.
- **Rest** = the bottom two thirds.
- For every measurable attribute of the copy (subject length, body
  length, presence of named customers, presence of a concrete number,
  day sent, content type, persona targeted), the table shows the
  winners average and the rest average.
- Where the gap is meaningful, a rule-based recommendation appears
  below.
- **Enquiries note:** the tracked batches only carry open + click +
  reply counts. When Snov starts exporting form-completions and
  enquiries per send, they will feed directly into the ranking.
""")


batches = load_csv("campaign_batches.csv")
if batches.empty:
    st.info("No tracked email data. Populate "
             "`data/campaign_batches.csv` (via the Snov export).")
    st.stop()

# Coerce
for c in ("sent", "delivered", "opened", "clicked", "replied"):
    if c in batches.columns:
        batches[c] = pd.to_numeric(batches[c], errors="coerce")


# ==========================================================================
# Compute attributes per email
# ==========================================================================
_CHALLENGE_WORDS = ["overcoming", "manual", "delay", "delays", "hidden",
                     "lost", "missed", "missing", "risk", "gap",
                     "disconnect", "backlog", "burden", "reduce", "cut",
                     "why", "how", "when", "smarter"]

_CTA_PHRASES = ["read the whitepaper", "read the white paper",
                  "download", "book a call", "book a demo",
                  "get in touch", "reply to this email",
                  "come by our", "meet our team", "set up a short call",
                  "connect with us"]

_NAMED_RE = re.compile(
    r"University of [A-Z][A-Za-z ]+|Institute of [A-Z][A-Za-z ]+|"
    r"[A-Z][A-Za-z]+ (?:College|University|Institute)"
    r"(?: of [A-Z][A-Za-z ]+)?")
_PCT_RE = re.compile(r"\b\d{1,3}\s*%")


def _attrs(subject, body, sent_date):
    subj = str(subject or "")
    b = str(body or "")
    subj_lo = subj.lower()
    b_lo = b.lower()
    subj_words = len(re.findall(r"\b\w+\b", subj))
    body_words = len(re.findall(r"\b\w+\b", b))
    subj_challenge = any(w in subj_lo for w in _CHALLENGE_WORDS)
    subj_has_number = bool(re.search(r"\d", subj))
    named_count = len(set(_NAMED_RE.findall(b)))
    pct_count = len(_PCT_RE.findall(b))
    has_cta = any(c in b_lo for c in _CTA_PHRASES)
    # Day sent
    try:
        d = pd.to_datetime(sent_date, errors="coerce")
        day = d.day_name() if pd.notna(d) else "?"
    except Exception:
        day = "?"
    return {
        "subject_words": subj_words,
        "body_words":    body_words,
        "subj_challenge": subj_challenge,
        "subj_has_number": subj_has_number,
        "named_count":   named_count,
        "pct_count":     pct_count,
        "has_cta":       has_cta,
        "day_sent":      day,
    }


def _classify_content(name, body):
    s = f"{name} {body}".lower()
    if any(k in s for k in ("arma", "ncura", "conference",
                              "come by our booth")):
        return "Event"
    if any(k in s for k in ("funder scanner", "funding opportunit",
                              "grants funding")):
        return "Funding"
    if any(k in s for k in ("erp", "reporting", "audit",
                              "single source", "compliance")):
        return "Product"
    return "General"


rows = []
for _, r in batches.iterrows():
    sent = int(r["sent"]) if pd.notna(r.get("sent")) else 0
    opened = int(r["opened"]) if pd.notna(r.get("opened")) else 0
    delivered = int(r["delivered"]) if pd.notna(r.get("delivered")) else 0
    open_rate = opened / max(delivered, 1) * 100
    a = _attrs(r.get("subject"), r.get("body"), r.get("sent_date"))
    rows.append({
        "batch_name":     str(r.get("batch_name", "")),
        "stage":          str(r.get("stage", "")),
        "subject":        str(r.get("subject", "")),
        "sent":           sent,
        "opened":         opened,
        "delivered":      delivered,
        "open_rate":      open_rate,
        "content_type":   _classify_content(
                              str(r.get("batch_name", "")),
                              str(r.get("body", ""))),
        **a,
    })

df = pd.DataFrame(rows)
if df.empty or df["open_rate"].max() == 0:
    st.info("No open-rate data on any tracked send yet.")
    st.stop()


# ==========================================================================
# Split winners vs rest
# ==========================================================================
df = df.sort_values("open_rate", ascending=False).reset_index(drop=True)
n_total = len(df)
n_winners = max(1, n_total // 3)
winners = df.head(n_winners)
rest    = df.tail(n_total - n_winners)


# ==========================================================================
# Top-line
# ==========================================================================
avg_win  = float(winners["open_rate"].mean())
avg_rest = float(rest["open_rate"].mean()) if not rest.empty else 0
best_row = df.iloc[0]
worst_row = df.iloc[-1]

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Tracked emails", f"{n_total}",
              sub=f"top {n_winners} are winners",
              tooltip="Every send in campaign_batches.csv.")
with k2:
    kpi_tile("Winners avg open rate", f"{avg_win:.0f}%",
              color=ACCENT,
              tooltip="Average open rate among the top-third emails.")
with k3:
    kpi_tile("Rest avg open rate", f"{avg_rest:.0f}%",
              color=GOLD if avg_win - avg_rest >= 10 else ACCENT,
              tooltip="Average open rate for everyone else.")
with k4:
    gap = avg_win - avg_rest
    kpi_tile("Gap", f"{gap:.0f} pts",
              sub="winner vs rest",
              color=WARN if gap >= 25 else GOLD if gap >= 10 else ACCENT,
              tooltip="If this gap is big, the winners are doing "
                      "something specific we can copy.")


# ==========================================================================
# Best and worst as cards
# ==========================================================================
st.markdown('<h2>The best and the worst</h2>', unsafe_allow_html=True)

bw1, bw2 = st.columns(2)
with bw1:
    st.markdown(
        f'<div style="border:1px solid {LINE};border-top:5px solid '
        f'{ACCENT};border-radius:8px;padding:1rem 1.2rem;'
        f'background:{BG}">'
        f'<div class="eyebrow" style="color:{ACCENT};'
        f'margin-bottom:.4rem">Best-performing send</div>'
        f'<div style="font-weight:600;color:{INK};font-size:1rem;'
        f'margin-bottom:.4rem">{best_row["batch_name"]} &middot; '
        f'{best_row["stage"]}</div>'
        f'<div style="color:{INK_SOFT};font-size:.9rem;'
        f'line-height:1.4;margin-bottom:.4rem">'
        f'{html.escape(best_row["subject"])}</div>'
        f'<div style="color:{ACCENT};font-weight:700;'
        f'font-size:1.4rem">{best_row["open_rate"]:.0f}% open</div>'
        f'<div style="color:{MUTED};font-size:.78rem">'
        f'{best_row["opened"]} of {best_row["delivered"]} delivered '
        f'&middot; sent {best_row.get("day_sent","?")}</div>'
        f'</div>', unsafe_allow_html=True)
with bw2:
    st.markdown(
        f'<div style="border:1px solid {LINE};border-top:5px solid '
        f'{WARN};border-radius:8px;padding:1rem 1.2rem;'
        f'background:{BG}">'
        f'<div class="eyebrow" style="color:{WARN};'
        f'margin-bottom:.4rem">Worst-performing send</div>'
        f'<div style="font-weight:600;color:{INK};font-size:1rem;'
        f'margin-bottom:.4rem">{worst_row["batch_name"]} &middot; '
        f'{worst_row["stage"]}</div>'
        f'<div style="color:{INK_SOFT};font-size:.9rem;'
        f'line-height:1.4;margin-bottom:.4rem">'
        f'{html.escape(worst_row["subject"])}</div>'
        f'<div style="color:{WARN};font-weight:700;'
        f'font-size:1.4rem">{worst_row["open_rate"]:.0f}% open</div>'
        f'<div style="color:{MUTED};font-size:.78rem">'
        f'{worst_row["opened"]} of {worst_row["delivered"]} delivered '
        f'&middot; sent {worst_row.get("day_sent","?")}</div>'
        f'</div>', unsafe_allow_html=True)


# ==========================================================================
# Attribute-by-attribute comparison
# ==========================================================================
st.markdown('<h2>What the winners do differently</h2>',
             unsafe_allow_html=True)

# Numeric attributes: mean per group
def _mean(df_, col):
    v = pd.to_numeric(df_[col], errors="coerce").dropna()
    return float(v.mean()) if len(v) else 0.0

# Categorical shares: proportion True per group
def _share(df_, col):
    v = df_[col].astype(bool)
    return float(v.sum()) / max(len(v), 1) * 100

comparisons = [
    ("Subject word count",
     _mean(winners, "subject_words"), _mean(rest, "subject_words"),
     "avg words in the subject line"),
    ("Body word count",
     _mean(winners, "body_words"), _mean(rest, "body_words"),
     "avg words in the body"),
    ("Named customers in body",
     _mean(winners, "named_count"), _mean(rest, "named_count"),
     "avg number of specific institution names dropped"),
    ("Concrete numbers (%) in body",
     _mean(winners, "pct_count"), _mean(rest, "pct_count"),
     "avg number of percentage figures used"),
    ("Subject names a challenge",
     _share(winners, "subj_challenge"),
     _share(rest, "subj_challenge"),
     "% of subjects that use pain / challenge words"),
    ("Subject contains a number",
     _share(winners, "subj_has_number"),
     _share(rest, "subj_has_number"),
     "% of subjects with a digit"),
    ("Clear CTA in body",
     _share(winners, "has_cta"), _share(rest, "has_cta"),
     "% of bodies with a recognised CTA phrase"),
]

header = (
    f'<div style="display:grid;grid-template-columns:'
    f'1.8fr 1fr 1fr 1fr 2fr;gap:.5rem;padding:.5rem .8rem;'
    f'font-size:.72rem;text-transform:uppercase;'
    f'letter-spacing:.12em;color:{MUTED};font-weight:600;'
    f'border-bottom:1px solid {LINE}">'
    f'<div>Attribute</div><div>Winners avg</div><div>Rest avg</div>'
    f'<div>Gap</div><div>Recommendation</div></div>')

rows_html = [header]
recommendations = []
for label, w, r, note in comparisons:
    gap = w - r
    # Format value depending on whether it's a % or a count
    if "%" in note or "%" in label:
        w_disp, r_disp, gap_disp = (f"{w:.0f}%", f"{r:.0f}%",
                                        f"{gap:+.0f} pts")
    else:
        w_disp, r_disp, gap_disp = (f"{w:.1f}", f"{r:.1f}",
                                        f"{gap:+.1f}")

    # Colour and recommendation
    if abs(gap) < max(0.5, r * 0.10):
        rec = "No meaningful difference."
        rec_col = MUTED
    else:
        if label == "Subject word count":
            if w < r:
                rec = (f"Winners keep subjects <strong>shorter</strong> "
                       f"({w:.0f} vs {r:.0f} words). Cut the next "
                       f"subject to under {int(w)} words.")
            else:
                rec = (f"Winners run <strong>longer</strong> subjects "
                       f"({w:.0f} vs {r:.0f}).")
            rec_col = ACCENT
        elif label == "Body word count":
            if w < r:
                rec = (f"Winners write <strong>tighter</strong> bodies "
                       f"({w:.0f} vs {r:.0f} words). Tighten the next "
                       f"draft to around {int(w)} words.")
            else:
                rec = (f"Winners write <strong>longer</strong> bodies "
                       f"({w:.0f} vs {r:.0f}).")
            rec_col = ACCENT
        elif label == "Named customers in body":
            if w > r:
                rec = (f"Winners name <strong>{w:.1f} customers</strong> "
                       f"per email vs {r:.1f} for the rest. Drop at "
                       f"least {int(round(w))} named institutions in "
                       f"the next draft.")
                rec_col = ACCENT
            else:
                rec = ("Rest emails name more customers than winners "
                       "- named proof is not the differentiator here.")
                rec_col = GOLD
        elif label == "Concrete numbers (%) in body":
            if w > r:
                rec = (f"Winners use <strong>{w:.1f}% figures</strong> "
                       f"per email vs {r:.1f}. Include at least "
                       f"{int(round(w))} concrete numbers next time.")
                rec_col = ACCENT
            else:
                rec = "Numbers are not the differentiator here."
                rec_col = MUTED
        elif label == "Subject names a challenge":
            if w > r:
                rec = (f"Winners lead the subject with a challenge "
                       f"word <strong>{w:.0f}% of the time</strong> vs "
                       f"{r:.0f}% for the rest. Rewrite next subject "
                       f"to name the pain.")
                rec_col = ACCENT
            else:
                rec = "Challenge-word subjects underperform here."
                rec_col = GOLD
        elif label == "Subject contains a number":
            if w > r:
                rec = (f"Winners include a number in the subject "
                       f"<strong>{w:.0f}% of the time</strong> vs "
                       f"{r:.0f}%. Add a concrete stat to the subject.")
                rec_col = ACCENT
            else:
                rec = "Numbers in subjects are not the driver."
                rec_col = MUTED
        elif label == "Clear CTA in body":
            if w > r:
                rec = (f"Winners have a recognisable CTA "
                       f"<strong>{w:.0f}% of the time</strong> vs "
                       f"{r:.0f}%. Add a single clear ask to the next "
                       f"body.")
                rec_col = ACCENT
            else:
                rec = ("Rest emails include CTAs more than winners - "
                       "CTA presence is not the lever.")
                rec_col = GOLD
        else:
            rec = f"Winners: {w_disp}. Rest: {r_disp}."
            rec_col = INK_SOFT
        recommendations.append(rec)

    rows_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'1.8fr 1fr 1fr 1fr 2fr;gap:.5rem;padding:.55rem .8rem;'
        f'font-size:.88rem;border-bottom:1px solid {LINE};'
        f'align-items:center">'
        f'<div style="color:{INK};font-weight:600">{label}</div>'
        f'<div style="color:{ACCENT};font-weight:600">{w_disp}</div>'
        f'<div style="color:{INK_SOFT}">{r_disp}</div>'
        f'<div style="color:{INK};font-weight:600">{gap_disp}</div>'
        f'<div style="color:{rec_col};font-size:.82rem;'
        f'line-height:1.4">{rec}</div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)


# ==========================================================================
# Content type + day-of-week rollups
# ==========================================================================
st.markdown('<h2>Which content type / day works best</h2>',
             unsafe_allow_html=True)

cc1, cc2 = st.columns(2)
with cc1:
    ct = (df.groupby("content_type")
             .agg(sends=("open_rate", "count"),
                   avg_open=("open_rate", "mean"))
             .reset_index()
             .sort_values("avg_open", ascending=False))
    ct.columns = ["Content type", "Sends", "Avg open %"]
    ct["Avg open %"] = ct["Avg open %"].round(0)
    st.markdown('<h3>By content type</h3>', unsafe_allow_html=True)
    st.dataframe(ct, use_container_width=True, hide_index=True,
                  column_config={
                      "Sends": st.column_config.NumberColumn(format="%d"),
                      "Avg open %":
                          st.column_config.NumberColumn(format="%.0f%%"),
                  })
    if len(ct):
        top_ct = ct.iloc[0]
        so_what(
            f"<strong>{top_ct['Content type']}</strong> emails open at "
            f"{top_ct['Avg open %']:.0f}% on average - the strongest "
            f"content type in the tracked set.", tone="good")

with cc2:
    day = (df.groupby("day_sent")
              .agg(sends=("open_rate", "count"),
                    avg_open=("open_rate", "mean"))
              .reset_index()
              .sort_values("avg_open", ascending=False))
    day.columns = ["Day sent", "Sends", "Avg open %"]
    day["Avg open %"] = day["Avg open %"].round(0)
    st.markdown('<h3>By day sent</h3>', unsafe_allow_html=True)
    st.dataframe(day, use_container_width=True, hide_index=True,
                  column_config={
                      "Sends": st.column_config.NumberColumn(format="%d"),
                      "Avg open %":
                          st.column_config.NumberColumn(format="%.0f%%"),
                  })
    if len(day) and day.iloc[0]["Day sent"] != "?":
        top_day = day.iloc[0]
        so_what(
            f"<strong>{top_day['Day sent']}</strong> sends average "
            f"{top_day['Avg open %']:.0f}% open. Prefer that day for "
            f"the next release if the audience allows.",
            tone="good")


# ==========================================================================
# Consolidated recommendations to apply next
# ==========================================================================
st.markdown('<h2>Apply these on the next send</h2>',
             unsafe_allow_html=True)
if recommendations:
    for i, rec in enumerate(recommendations, 1):
        st.markdown(
            f'<div style="border-left:4px solid {ACCENT};'
            f'padding:.6rem 1rem;margin:.4rem 0;background:{BG_SOFT};'
            f'border-radius:4px;font-size:.95rem;line-height:1.5">'
            f'<strong style="color:{ACCENT}">{i}.</strong> {rec}</div>',
            unsafe_allow_html=True)
else:
    st.markdown(
        f'<div style="color:{INK_SOFT};font-size:.9rem">'
        f'No meaningful attribute gaps yet - either the sample is too '
        f'small or the winners and rest are structurally similar.</div>',
        unsafe_allow_html=True)


# ==========================================================================
# Enquiries note (per Ian's spec, enquiries > clicks)
# ==========================================================================
st.markdown(
    f'<div style="margin-top:2rem;padding:1rem 1.2rem;'
    f'background:#FBF3E5;border-left:4px solid {GOLD};'
    f'border-radius:6px;font-size:.9rem;line-height:1.5">'
    f'<strong>What is missing:</strong> per-send form completions '
    f'and enquiries. When the ESP exports those fields into '
    f'<code>campaign_batches.csv</code> (columns '
    f'<code>form_completions</code> and <code>enquiries</code>), '
    f'the winners split will re-rank by enquiries not opens - which '
    f'is Ian&apos;s actual objective.</div>',
    unsafe_allow_html=True)
