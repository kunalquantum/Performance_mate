"""
Email - This week's numbers.

Text-only rebuild for Ian. Every chart replaced with a table, a KPI
tile or a plain-English observation. Same data pull; different
presentation.

Sections:
    1. Latest week headline tiles
    2. Weekly rollup table (last 12 weeks by default)
    3. Best and worst weeks tabs
    4. Batch-size analysis (spec 7) as text + small table
    5. Interest & engagement (pipeline signals) as text + tables
"""
from shared import (core_question, inject_css, render_status_key,
                     so_what, kpi_tile, load_csv,
                     INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>This week&apos;s numbers</h1>', unsafe_allow_html=True)
core_question("How is our email programme performing week by week, "
                "and is it meeting industry benchmarks?")
st.caption("Text-first view. Green tiles are meeting the 20% open / "
            "2% click / 3% bounce benchmarks. Gold means look closer.")
render_status_key()

with st.expander("What the numbers mean", expanded=False):
    st.markdown("""
- **Open rate** &mdash; opens &divide; delivered. SaaS benchmark 20%.
- **Click rate** &mdash; clicks &divide; delivered. SaaS benchmark 2-3%.
- **CTOR** &mdash; clicks &divide; opens. Isolates copy quality from
  subject-line quality. Benchmark 10-15%.
- **Bounce rate** &mdash; bounces &divide; sent. Above 3% hurts
  deliverability.
- **Delivery rate** &mdash; delivered &divide; sent. Anything below 97%
  is a list-hygiene concern.
- **Interested universities** &mdash; Cognism-provided count of
  institutions showing high intent this week. Closest thing to a
  pipeline signal from an email.
""")


emails = load_csv("emails.csv")
if emails.empty:
    st.warning("No `data/emails.csv` found. Run "
                "`python etl/email_etl.py`.")
    st.stop()

emails["week_start"] = pd.to_datetime(emails["week_start"],
                                          errors="coerce")
for c in ("emails_sent", "contacts", "delivered", "bounced",
            "opened", "clicks"):
    if c in emails.columns:
        emails[c] = pd.to_numeric(emails[c], errors="coerce").fillna(0) \
            .astype(int)


# Sort newest first
emails = emails.sort_values("week_start", ascending=False).reset_index(
    drop=True)


# ==========================================================================
# 1. Latest week headline tiles
# ==========================================================================
latest = emails.iloc[0]
prev = emails.iloc[1] if len(emails) >= 2 else None

open_rate = float(latest.get("open_rate", 0) or 0) * 100
click_rate = float(latest.get("click_rate", 0) or 0) * 100
bounce_rate = float(latest.get("bounce_rate", 0) or 0) * 100
delivery_rate = float(latest.get("delivery_rate", 0) or 0) * 100


def _delta(cur, prev_row, col, is_rate=False):
    if prev_row is None:
        return ""
    v = float(prev_row.get(col, 0) or 0)
    if is_rate:
        v = v * 100
    diff = cur - v
    if abs(diff) < 0.5:
        return "same as last week"
    return f"{'up' if diff > 0 else 'down'} " \
            f"{abs(diff):.1f} pts vs last week"


st.markdown('<h2>Latest week</h2>', unsafe_allow_html=True)
st.markdown(
    f'<div style="font-size:.95rem;color:{INK_SOFT};margin-bottom:.5rem">'
    f'Week: <strong>{latest.get("week_label", "")}</strong> &middot; '
    f'{int(latest.get("emails_sent", 0))} emails sent to '
    f'{int(latest.get("contacts", 0))} contacts</div>',
    unsafe_allow_html=True)

r1 = st.columns(4)
with r1[0]:
    kpi_tile("Open rate", f"{open_rate:.1f}%",
              sub=_delta(open_rate, prev, "open_rate", True),
              color=ACCENT if open_rate >= 20 else GOLD,
              tooltip="Opens divided by delivered. Benchmark 20%.")
with r1[1]:
    kpi_tile("Click rate", f"{click_rate:.1f}%",
              sub=_delta(click_rate, prev, "click_rate", True),
              color=ACCENT if click_rate >= 2 else GOLD,
              tooltip="Clicks divided by delivered. Benchmark 2-3%.")
with r1[2]:
    kpi_tile("Delivery rate", f"{delivery_rate:.1f}%",
              color=ACCENT if delivery_rate >= 97 else GOLD)
with r1[3]:
    kpi_tile("Bounce rate", f"{bounce_rate:.1f}%",
              color=ACCENT if bounce_rate < 3 else WARN,
              tooltip="Above 3% hurts deliverability.")

# One-sentence read
verdict = ("meeting the 20% benchmark"
            if open_rate >= 20 else "below the 20% benchmark")
so_what(
    f"Latest week ({latest.get('week_label','')}) opened at "
    f"<strong>{open_rate:.1f}%</strong> - {verdict}. "
    + (f"That is {_delta(open_rate, prev, 'open_rate', True)}. "
        if prev is not None else "") +
    f"Bounce {bounce_rate:.1f}%, delivery {delivery_rate:.1f}%.",
    tone="good" if open_rate >= 20 else "warn")


# ==========================================================================
# 2. Weekly rollup - funnel bar per week (clicked / opened / unopened / bounced)
# ==========================================================================
st.markdown('<h2>Recent weeks</h2>', unsafe_allow_html=True)
st.caption("Newest weeks first. Bar shows the funnel split of every "
            "sent email that week: clicked, opened-not-clicked, "
            "unopened, and bounced. Open % coloured green &ge; 20%, "
            "gold &ge; 10%, red otherwise.")

show_all = st.toggle("Show every tracked week", value=False,
                       key="tep_all")

view = emails if show_all else emails.head(12)

# Funnel colours
_C_CLICK  = ACCENT           # deep green - clicked
_C_OPEN   = "#7BC0BB"        # light green - opened but did not click
_C_UNOPEN = "#D9DBE0"        # grey - delivered but not opened
_C_BOUNCE = WARN             # red - bounced

# Legend
st.markdown(
    f'<div style="margin:.3rem 0 .7rem">'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'margin-right:.9rem;font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{_C_CLICK};border-radius:2px"></span>Clicked</span>'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'margin-right:.9rem;font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{_C_OPEN};border-radius:2px"></span>Opened, no click</span>'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'margin-right:.9rem;font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{_C_UNOPEN};border-radius:2px"></span>Not opened</span>'
    f'<span style="display:inline-flex;align-items:center;gap:.3rem;'
    f'font-size:.78rem;color:{INK_SOFT}">'
    f'<span style="display:inline-block;width:14px;height:14px;'
    f'background:{_C_BOUNCE};border-radius:2px"></span>Bounced</span>'
    f'</div>', unsafe_allow_html=True)

grid = "1.2fr .5fr .55fr .55fr .55fr .55fr 2.2fr"
rows_html = [
    f'<div style="display:grid;grid-template-columns:{grid};gap:.6rem;'
    f'padding:.5rem .8rem;font-size:.7rem;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.12em;font-weight:600;'
    f'border-bottom:1px solid {LINE};background:{BG_SOFT}">'
    f'<div>Week</div>'
    f'<div style="text-align:right">Sent</div>'
    f'<div style="text-align:right">Delivered</div>'
    f'<div style="text-align:right">Opens</div>'
    f'<div style="text-align:right">Open %</div>'
    f'<div style="text-align:right">Clicks</div>'
    f'<div>Funnel split of every sent email</div></div>'
]


def _funnel_bar(sent, delivered, opened, clicked, bounced):
    if sent <= 0:
        return (f'<div style="height:22px;background:{LINE};'
                f'border-radius:3px;display:flex;align-items:center;'
                f'justify-content:center;color:{MUTED};'
                f'font-size:.7rem;font-style:italic">nothing sent</div>')
    # Guard against inconsistent numbers (clicks can exceed opens in
    # some ESP exports because it counts unique-click on unopened
    # implicit-tracker recipients).
    clicked = max(0, min(clicked, opened))
    opened_only = max(0, opened - clicked)
    unopened = max(0, delivered - opened)
    bounced = max(0, bounced)
    # Anything left over (drift between sent and delivered+bounced)
    # gets folded into unopened so the bar always sums to `sent`.
    accounted = clicked + opened_only + unopened + bounced
    if accounted < sent:
        unopened += (sent - accounted)
    parts = [
        ("Clicked",         clicked,      _C_CLICK),
        ("Opened, no click", opened_only, _C_OPEN),
        ("Not opened",      unopened,     _C_UNOPEN),
        ("Bounced",         bounced,      _C_BOUNCE),
    ]
    segs = []
    total = sum(v for _, v, _ in parts) or 1
    for label, v, colour in parts:
        if v <= 0:
            continue
        pct = v / total * 100
        inner = f'{pct:.0f}%' if pct >= 8 else ""
        txt_col = "white" if colour != _C_UNOPEN else INK
        segs.append(
            f'<div style="flex:{pct};background:{colour};'
            f'display:flex;align-items:center;justify-content:center;'
            f'color:{txt_col};font-weight:700;font-size:.7rem" '
            f'title="{label}: {int(v)} ({pct:.1f}%)">{inner}</div>')
    return (f'<div style="display:flex;height:22px;'
            f'border-radius:3px;overflow:hidden">{"".join(segs)}</div>')


for _, r in view.iterrows():
    open_pct = float(r.get("open_rate", 0) or 0) * 100
    or_col = (ACCENT if open_pct >= 20
                else GOLD if open_pct >= 10 else WARN)
    sent_i = int(r.get("emails_sent") or 0)
    deliv_i = int(r.get("delivered") or 0)
    opened_i = int(r.get("opened") or 0)
    clicks_i = int(r.get("clicks") or 0)
    bounced_i = int(r.get("bounced") or 0)

    rows_html.append(
        f'<div style="display:grid;grid-template-columns:{grid};'
        f'gap:.6rem;padding:.55rem .8rem;font-size:.85rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        f'<div style="color:{INK};font-weight:600">{r["week_label"]}</div>'
        f'<div style="text-align:right;color:{INK}">{sent_i}</div>'
        f'<div style="text-align:right;color:{INK}">{deliv_i}</div>'
        f'<div style="text-align:right;color:{INK}">{opened_i}</div>'
        f'<div style="text-align:right;background:{or_col}22;'
        f'color:{INK};font-weight:700;padding:.15rem .4rem;'
        f'border-radius:3px">{open_pct:.1f}%</div>'
        f'<div style="text-align:right;color:{INK}">{clicks_i}</div>'
        f'<div>{_funnel_bar(sent_i, deliv_i, opened_i, clicks_i, bounced_i)}</div>'
        f'</div>')

st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)

# Auto so-what on trend
with_rate = emails.dropna(subset=["open_rate"])
if len(with_rate) >= 4:
    last4 = with_rate.head(4)["open_rate"].tolist()
    trend_down = all(last4[i] <= last4[i-1] for i in range(1, 4))
    trend_up = all(last4[i] >= last4[i-1] for i in range(1, 4))
    if trend_down:
        so_what(
            "Open rate has been dropping for four weeks in a row. "
            "Rewrite the next subject line or shrink the list to the "
            "highest-engagement segment.", tone="warn")
    elif trend_up:
        so_what(
            "Open rate has been climbing for four weeks in a row. "
            "Keep the current rhythm.", tone="good")


# ==========================================================================
# 3. Best and worst weeks
# ==========================================================================
st.markdown('<h2>Best and worst weeks so far</h2>',
             unsafe_allow_html=True)
tab_best, tab_worst = st.tabs(["Top 5 by open rate",
                                  "Bottom 5 by open rate"])
with_rate = emails.dropna(subset=["open_rate"])

def _rank_view(df_):
    v = df_[["week_label", "emails_sent", "contacts", "delivered",
              "opened", "clicks", "open_rate", "click_rate"]].copy()
    v.columns = ["Week", "Sent", "Contacts", "Delivered",
                  "Opened", "Clicks", "Open %", "Click %"]
    v["Open %"] = (v["Open %"] * 100).round(1)
    v["Click %"] = (v["Click %"] * 100).round(1)
    return v

with tab_best:
    top = with_rate.nlargest(5, "open_rate")
    st.dataframe(_rank_view(top), use_container_width=True,
                  hide_index=True)
with tab_worst:
    bot = with_rate.nsmallest(5, "open_rate")
    st.dataframe(_rank_view(bot), use_container_width=True,
                  hide_index=True)


# ==========================================================================
# 4. Batch size analysis (spec 7) - text-first
# ==========================================================================
st.markdown('<h2>Batch size vs open rate</h2>',
             unsafe_allow_html=True)
st.caption("Is a bigger blast still opening well, or does list size "
            "hurt engagement?")

bs = with_rate.dropna(subset=["contacts"]).copy()
if len(bs) >= 6:
    _med = int(bs["contacts"].median())
    small = bs[bs["contacts"] < _med]
    big   = bs[bs["contacts"] >= _med]

    b1, b2, b3 = st.columns(3)
    with b1:
        kpi_tile("Median batch size", f"{_med}",
                  sub="the split point",
                  tooltip="Half your weeks send more than this, "
                          "half send less.")
    with b2:
        s_avg = float(small["open_rate"].mean()) * 100
        kpi_tile(f"Small sends (< {_med})",
                  f"{s_avg:.1f}% open",
                  sub=f"{len(small)} weeks",
                  color=ACCENT)
    with b3:
        l_avg = float(big["open_rate"].mean()) * 100
        kpi_tile(f"Bigger sends (&ge; {_med})",
                  f"{l_avg:.1f}% open",
                  sub=f"{len(big)} weeks",
                  color=GOLD if l_avg < s_avg - 2 else ACCENT)

    diff = s_avg - l_avg
    if diff >= 2:
        so_what(
            f"Smaller sends open at <strong>{s_avg:.1f}%</strong> vs "
            f"<strong>{l_avg:.1f}%</strong> for bigger sends - a "
            f"{diff:.1f} point gap. Tighter targeting is the biggest "
            f"lever in the data. Split future blasts into "
            f"persona-tighter batches under {_med} contacts.",
            tone="good")
    elif diff <= -2:
        so_what(
            f"Bigger sends open at <strong>{l_avg:.1f}%</strong> vs "
            f"<strong>{s_avg:.1f}%</strong> for smaller sends. "
            f"Volume is not hurting open rate here.", tone="info")
    else:
        so_what(
            f"Batch size does not meaningfully affect open rate in "
            f"the current data (small {s_avg:.1f}% vs big "
            f"{l_avg:.1f}%).", tone="info")

    # Buckets table
    def _bucket(n):
        if n < 100:  return "1) Under 100"
        if n < 500:  return "2) 100-499"
        if n < 1000: return "3) 500-999"
        return "4) 1,000+"
    bs["bucket"] = bs["contacts"].apply(_bucket)
    rollup = (bs.groupby("bucket")
                .agg(weeks=("open_rate", "count"),
                      avg_contacts=("contacts", "mean"),
                      avg_open=("open_rate", "mean"))
                .reset_index()
                .sort_values("bucket"))
    rollup.columns = ["Batch size band", "Weeks",
                        "Avg contacts", "Avg open %"]
    rollup["Avg contacts"] = rollup["Avg contacts"].round(0).astype(int)
    rollup["Avg open %"] = (rollup["Avg open %"] * 100).round(1)
    st.markdown('<h3 style="margin-top:1rem">By batch-size band</h3>',
                 unsafe_allow_html=True)
    st.dataframe(rollup, use_container_width=True, hide_index=True,
                  column_config={
                      "Weeks":
                          st.column_config.NumberColumn(format="%d"),
                      "Avg contacts":
                          st.column_config.NumberColumn(format="%d"),
                      "Avg open %":
                          st.column_config.NumberColumn(format="%.1f%%"),
                  })
else:
    st.info("Need at least 6 weeks with a batch size to run this "
             "analysis.")


# ==========================================================================
# 5. Pipeline signals: interested universities + newsletter subs
# ==========================================================================
if "interested_companies_count" in emails.columns:
    st.markdown('<h2>Interest &amp; engagement</h2>',
                 unsafe_allow_html=True)
    st.caption("Beyond opens and clicks: replies, universities "
                "flagged as &lsquo;most interested&rsquo; by Cognism, "
                "and newsletter subscribers per week.")

    for c in ("interested_companies_count", "newsletter_subs",
                "replies"):
        if c in emails.columns:
            emails[c] = pd.to_numeric(emails[c], errors="coerce") \
                .fillna(0).astype(int)

    total_intent = int(emails["interested_companies_count"].sum())
    n_intent_weeks = int((emails["interested_companies_count"] > 0).sum())
    total_subs = int(emails["newsletter_subs"].sum())
    total_replies = int(emails["replies"].sum())

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        kpi_tile("Replies (all weeks)", f"{total_replies}",
                  tooltip="Total replies logged.")
    with p2:
        kpi_tile("Interested universities",
                  f"{total_intent}",
                  sub=f"{n_intent_weeks} weeks with signal",
                  color=ACCENT)
    with p3:
        kpi_tile("Newsletter subs", f"{total_subs}")
    with p4:
        avg = (total_intent / max(n_intent_weeks, 1)) if n_intent_weeks \
            else 0
        kpi_tile("Avg interested / active week",
                  f"{avg:.1f}")

    # Interest per week table
    intent = emails[emails["interested_companies_count"] > 0][[
        "week_label", "interested_companies_count",
        "interested_companies_raw"]].copy()
    intent.columns = ["Week", "Interested count", "Names"]
    if not intent.empty:
        st.markdown('<h3 style="margin-top:1rem">Interested '
                     'universities per week</h3>',
                     unsafe_allow_html=True)
        st.dataframe(
            intent, use_container_width=True, hide_index=True,
            column_config={
                "Interested count":
                    st.column_config.NumberColumn(format="%d"),
                "Names": st.column_config.TextColumn(width="large"),
            })

    # Top named companies
    all_names = []
    for s in emails["interested_companies_raw"].dropna().astype(str):
        for n in s.split(";"):
            n = n.strip()
            if n:
                all_names.append(n)
    if all_names:
        from collections import Counter as _C
        top = _C(all_names).most_common(15)
        top_df = pd.DataFrame(top,
                                columns=["University", "Mentions"])
        st.markdown('<h3 style="margin-top:1rem">Top interested '
                     'universities across the window</h3>',
                     unsafe_allow_html=True)
        st.dataframe(top_df, use_container_width=True,
                      hide_index=True,
                      column_config={
                          "Mentions": st.column_config.ProgressColumn(
                              min_value=0,
                              max_value=int(top_df["Mentions"].max()),
                              format="%d",
                              help="How many weeks this university "
                                      "appeared as an interested lead."),
                      })

    # Qualitative notes
    _notes = emails[emails["newsletter_note"].astype(str).str.strip()
                     .replace("nan", "").ne("")]
    if not _notes.empty:
        st.markdown('<h3 style="margin-top:1rem">Qualitative notes'
                     '</h3>', unsafe_allow_html=True)
        for _, r in _notes.iterrows():
            st.markdown(
                f'<div style="border-left:3px solid {ACCENT};'
                f'padding:.5rem 1rem;margin:.4rem 0;'
                f'background:{BG_SOFT};border-radius:4px;'
                f'font-size:.9rem">'
                f'<strong>{r["week_label"]}</strong><br>'
                f'{r["newsletter_note"]}</div>',
                unsafe_allow_html=True)
