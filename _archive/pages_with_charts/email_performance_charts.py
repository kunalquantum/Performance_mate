"""
Email Performance Matrix - Performance screen.
"""
from shared import (core_question, inject_css, render_status_key, so_what, explain_this,
                     kpi_tile, load_csv, DATA_DIR, SOURCES_DIR, INK,
                     INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, WARN, GOLD)
import os, re
import altair as alt
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>This week&apos;s numbers</h1>', unsafe_allow_html=True)
core_question("How is our email programme performing week by week, and is it meeting industry benchmarks?")
st.caption("How our emails have been performing week by week - opens, "
            "clicks, delivery, and the pipeline signals underneath. "
            "Green tiles are meeting benchmarks, gold means look closer.")
render_status_key()

with st.expander("What the metrics mean", expanded=False):
    st.markdown("""
- **Open rate** &mdash; opens divided by delivered. SaaS benchmark 20%.
  Below 10% points to a subject-line or list problem.
- **Click rate** &mdash; clicks divided by delivered. SaaS benchmark
  2-3%. Rising click rate means the copy body is landing.
- **CTOR (click-to-open rate)** &mdash; clicks divided by opens. Isolates
  copy quality from subject-line quality. Benchmark 10-15%.
- **Bounce rate** &mdash; bounces divided by contacts sent. Above 3%
  hurts deliverability for future sends; needs list hygiene.
- **Delivery rate** &mdash; delivered divided by sent. Anything below
  97% is a list-hygiene concern.
- **Interested universities** &mdash; a Cognism-provided count of
  institutions flagged as showing high intent in a given week. This is
  the closest pipeline signal we get from an email send.
- **Rolling 4-week average** &mdash; a smoothed line over the last four
  weeks; removes single-week noise so the trend is visible.
""")

emails_all = load_csv("emails.csv")
if not emails_all.empty:
    emails_all["week_start"] = pd.to_datetime(emails_all["week_start"],
                                                errors="coerce")


# ================== 1. LOAD THE REAL DATA ==================
# Email data is on its own timeline (Dec 2024 - Jul 2025) that does not
# overlap the LinkedIn window. Email Matrix runs on its own date range
# so switching modes never leaves you looking at nothing.
emails_all = load_csv("emails.csv")
if not emails_all.empty:
    emails_all["week_start"] = pd.to_datetime(emails_all["week_start"],
                                                errors="coerce")

# ================== 2. HEADER + PERFORMANCE ==================
st.markdown('<h2>Email Matrix</h2>', unsafe_allow_html=True)

if emails_all.empty:
    st.warning("No `data/emails.csv` found. Run "
                "`python etl/email_etl.py` from the project folder and "
                "reload the page.")
    emails_df = emails_all
else:
    e_min = emails_all["week_start"].min().date()
    e_max = emails_all["week_start"].max().date()
    st.caption(f"Email data spans {e_min:%d %b %Y} to {e_max:%d %b %Y}. "
                "Pick a window below (independent from the LinkedIn date "
                "range at the top of the page).")
    # Widget keys are the single source of truth. Preset buttons render
    # BEFORE the date_input widgets in code, so a button click mutates
    # state via st.rerun() and the widgets pick up the new values on
    # the next run rather than fighting them.
    if "email_range_start" not in st.session_state:
        st.session_state.email_range_start = e_min
    if "email_range_end" not in st.session_state:
        st.session_state.email_range_end = e_max

    def _set_email_range(weeks=None, full=False):
        if full:
            st.session_state.email_range_start = e_min
            st.session_state.email_range_end = e_max
        elif weeks:
            start = max(e_min,
                         e_max - pd.Timedelta(weeks=weeks).to_pytimedelta())
            st.session_state.email_range_start = start
            st.session_state.email_range_end = e_max

    er1, er2, er3 = st.columns([2, 2, 3], gap="small")
    # RENDER PRESETS FIRST so a click updates widget state before the
    # date_input widgets read from it during this rerun.
    with er3:
        st.markdown('<div class="eyebrow" style="margin-bottom:.2rem">'
                     'Quick range</div>', unsafe_allow_html=True)
        ep1, ep2, ep3 = st.columns(3)
        with ep1:
            if st.button("Last 8 weeks", key="ep_8w",
                         width='stretch'):
                _set_email_range(weeks=8)
                st.rerun()
        with ep2:
            if st.button("Last quarter", key="ep_q",
                         width='stretch'):
                _set_email_range(weeks=13)
                st.rerun()
        with ep3:
            if st.button("All weeks", key="ep_all",
                         width='stretch'):
                _set_email_range(full=True)
                st.rerun()
    with er1:
        st.markdown('<div class="eyebrow" style="margin-bottom:.2rem">'
                     'From</div>', unsafe_allow_html=True)
        e_start = st.date_input(
            " ", min_value=e_min, max_value=e_max,
            key="email_range_start", label_visibility="collapsed")
    with er2:
        st.markdown('<div class="eyebrow" style="margin-bottom:.2rem">'
                     'To</div>', unsafe_allow_html=True)
        e_end = st.date_input(
            "  ", min_value=e_min, max_value=e_max,
            key="email_range_end", label_visibility="collapsed")

    if e_start > e_end:
        e_start, e_end = e_end, e_start
    emails_df = emails_all[
        (emails_all["week_start"] >= pd.Timestamp(e_start))
        & (emails_all["week_start"] <= pd.Timestamp(e_end))]

if emails_df.empty:
    st.warning("No email data in the picked window. Widen the range "
                "above.")
else:
    n_weeks_email = len(emails_df)
    total_sent = int(emails_df["emails_sent"].fillna(0).sum())
    total_contacts = int(emails_df["contacts"].fillna(0).sum())
    total_delivered = int(emails_df["delivered"].fillna(0).sum())
    total_opened = int(emails_df["opened"].fillna(0).sum())
    total_clicks = int(emails_df["clicks"].fillna(0).sum())
    avg_delivery = (total_delivered / total_contacts
                     if total_contacts else 0)
    avg_open = (total_opened / total_delivered
                 if total_delivered else 0)
    avg_click = (total_clicks / total_delivered
                  if total_delivered else 0)
    avg_ctor = (total_clicks / total_opened
                 if total_opened else 0)

    st.markdown(
        f'<div class="lede">{n_weeks_email} weeks of email campaigns. '
        f'{total_sent:,} emails to {total_contacts:,} contacts. '
        f'The scoring engine reads this file. Compose and analyse '
        f'sits below.</div>', unsafe_allow_html=True)

    # KPI tiles
    def _stat(label, value, delta=""):
        st.markdown(
            f'<div class="stat"><div class="k">{label}</div>'
            f'<div class="v">{value}</div>'
            f'<div class="d">{delta}</div></div>',
            unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: _stat("Emails sent", f"{total_sent}",
                    f"across {n_weeks_email} weeks")
    with k2: _stat("Contacts reached", f"{total_contacts:,}",
                    "total audience")
    with k3: _stat("Delivery rate", f"{avg_delivery*100:.1f}%",
                    "of contacts")
    with k4: _stat("Open rate", f"{avg_open*100:.1f}%",
                    "of delivered")
    with k5: _stat("Click rate", f"{avg_click*100:.2f}%",
                    "of delivered")

    # ---- WEEKLY DIGEST ----
    # Auto-generated one-paragraph summary of the most recent week in the
    # window, with comparison to the previous week where possible.
    latest = emails_df.sort_values("week_start", ascending=False)
    latest = latest[latest["contacts"].fillna(0) > 0]
    if not latest.empty:
        L = latest.iloc[0]
        prev = latest.iloc[1] if len(latest) > 1 else None

        def _delta_note(cur, prv, is_pct=False):
            if prv is None or pd.isna(prv) or prv == 0:
                return ""
            d = cur - prv
            if is_pct:
                return (f" (up {d*100:.1f} pts vs the week before)"
                         if d > 0 else
                         f" (down {abs(d)*100:.1f} pts)")
            return (f" (up {int(d):,} vs the week before)"
                     if d > 0 else f" (down {int(abs(d)):,})")

        digest_bits = []
        digest_bits.append(f"<b>{L['week_label']}.</b>")
        digest_bits.append(
            f"{int(L['emails_sent'] or 0)} emails to "
            f"{int(L['contacts'] or 0):,} contacts.")
        if pd.notna(L.get("open_rate")):
            digest_bits.append(
                f"Open rate <b>{L['open_rate']*100:.1f}%</b>"
                f"{_delta_note(L['open_rate'], prev['open_rate'] if prev is not None else None, is_pct=True)}.")
        if pd.notna(L.get("click_rate")):
            digest_bits.append(
                f"Click rate <b>{L['click_rate']*100:.2f}%</b>"
                f"{_delta_note(L['click_rate'], prev['click_rate'] if prev is not None else None, is_pct=True)}.")
        if pd.notna(L.get("bounce_rate")) and L["bounce_rate"] > 0.03:
            digest_bits.append(
                f"Bounce rate <span style='color:{WARN}'>"
                f"{L['bounce_rate']*100:.1f}%</span> is above the "
                f"3% risk line.")
        # best week highlight
        top_wk = emails_df.dropna(subset=["open_rate"]).nlargest(
            1, "open_rate")
        if not top_wk.empty:
            b = top_wk.iloc[0]
            digest_bits.append(
                f"Best week in this range: <b>{b['week_label']}</b> "
                f"with a {b['open_rate']*100:.1f}% open rate on "
                f"{int(b['contacts'] or 0):,} contacts.")

        st.markdown(
            f'<div class="callout note" style="background:{ACCENT_SOFT}22;'
            f'border-left:3px solid {ACCENT};padding:.9rem 1.1rem;'
            f'border-radius:6px;margin:1.5rem 0">'
            f'<div style="font-size:.68rem;letter-spacing:.14em;'
            f'text-transform:uppercase;color:{MUTED};font-weight:600;'
            f'margin-bottom:.35rem">Weekly digest</div>'
            f'<div style="color:{INK};font-size:.95rem;line-height:1.55">'
            + " ".join(digest_bits)
            + '</div></div>', unsafe_allow_html=True)

    # ---- OPEN + CLICK RATE OVER TIME (with rolling avg + benchmarks) ----
    st.markdown('<h3 style="margin-top:2rem">Open and click rates by '
                'week</h3>', unsafe_allow_html=True)
    st.caption("Open rate uses delivered as the base. Click rate too. "
               "The lighter lines are 4-week rolling averages to smooth "
               "the weekly noise. The dashed grey rules are the SaaS "
               "industry benchmarks (~20% open, ~2% click).")

    # add rolling means before the melt
    e_sorted = emails_df.sort_values("week_start").copy()
    e_sorted["open_rate_rolling"] = e_sorted["open_rate"].rolling(
        window=4, min_periods=2).mean()
    e_sorted["click_rate_rolling"] = e_sorted["click_rate"].rolling(
        window=4, min_periods=2).mean()

    long_df = e_sorted.melt(
        id_vars=["week_start", "week_label", "emails_sent",
                 "contacts", "opened", "clicks"],
        value_vars=["open_rate", "click_rate"],
        var_name="metric", value_name="rate")
    long_df["metric_lbl"] = long_df["metric"].map({
        "open_rate": "Open rate", "click_rate": "Click rate"})

    rolling_df = e_sorted.melt(
        id_vars=["week_start", "week_label"],
        value_vars=["open_rate_rolling", "click_rate_rolling"],
        var_name="metric", value_name="rate")
    rolling_df["metric_lbl"] = rolling_df["metric"].map({
        "open_rate_rolling": "Open rate",
        "click_rate_rolling": "Click rate"})

    base_scale = alt.Scale(domain=["Open rate", "Click rate"],
                            range=[ACCENT, GOLD])

    raw_line = alt.Chart(long_df).mark_line(
        point=alt.OverlayMarkDef(size=55, filled=True), opacity=0.9
    ).encode(
        x=alt.X("week_start:T", title=None,
                axis=alt.Axis(labelColor=MUTED)),
        y=alt.Y("rate:Q", title="Rate",
                axis=alt.Axis(format=".0%", labelColor=MUTED)),
        color=alt.Color("metric_lbl:N", title=None, scale=base_scale),
        tooltip=[
            alt.Tooltip("week_label:N", title="Week"),
            alt.Tooltip("metric_lbl:N", title="Metric"),
            alt.Tooltip("rate:Q", format=".2%", title="Rate"),
            alt.Tooltip("emails_sent:Q", title="Emails"),
            alt.Tooltip("contacts:Q", title="Contacts"),
        ],
    )
    smoothed = alt.Chart(rolling_df.dropna(subset=["rate"])).mark_line(
        strokeWidth=3, opacity=0.35
    ).encode(
        x="week_start:T", y="rate:Q",
        color=alt.Color("metric_lbl:N", scale=base_scale, legend=None))

    benchmarks = alt.Chart(pd.DataFrame({
        "y": [0.20, 0.02],
        "label": ["Open rate benchmark 20%", "Click rate benchmark 2%"],
    })).mark_rule(color=MUTED, strokeDash=[3, 4], opacity=0.7).encode(
        y="y:Q")

    st.altair_chart((raw_line + smoothed + benchmarks
    ).properties(height=300), width='stretch')

    # So-what for the open-rate trend
    _rate_hist = emails_df.dropna(subset=["open_rate", "week_start"]) \
        .sort_values("week_start")
    if len(_rate_hist) >= 4:
        _last = float(_rate_hist["open_rate"].iloc[-1]) * 100
        _prev4 = _rate_hist["open_rate"].tail(4).tolist()
        _trend_down = all(_prev4[i] >= _prev4[i+1]
                            for i in range(len(_prev4)-1))
        _trend_up = all(_prev4[i] <= _prev4[i+1]
                          for i in range(len(_prev4)-1))
        _avg = float(_rate_hist["open_rate"].mean()) * 100
        if _trend_down and _last < _avg:
            so_what(f"Open rate has been declining for 4 weeks in a row. "
                     f"Latest at {_last:.0f}% is below the "
                     f"{_avg:.0f}% average. Time to review the subject "
                     f"line or the list.", tone="warn")
        elif _trend_up:
            so_what(f"Open rate is climbing 4 weeks in a row - latest "
                     f"at {_last:.0f}%. Whatever changed recently is "
                     f"working, keep doing it.", tone="good")
        elif _last >= 20:
            so_what(f"Latest week at {_last:.0f}% is meeting the 20% "
                     f"industry benchmark.", tone="good")
        else:
            so_what(f"Latest week at {_last:.0f}% is below the 20% "
                     f"industry benchmark - the copy or the list are "
                     f"the likely levers.", tone="warn")

    explain_this(
        shows="Weekly open rate (dots) with a rolling smoothed line "
                "(teal). Dashed lines mark the SaaS industry benchmarks: "
                "20% for opens, 2% for clicks.",
        good_pattern="A stable or climbing trend at or above 20%. "
                        "Occasional dips are fine, but four weeks in a "
                        "row heading down is a signal.",
        action_hint="If the trend is dropping: rewrite the next subject "
                     "line, or shrink the list to the highest-engagement "
                     "segment. If it is climbing: repeat whatever you "
                     "changed recently.")

    # ---- CLICK-TO-OPEN RATE (CTOR) ----
    st.markdown('<h3 style="margin-top:2rem">Click-to-open rate</h3>',
                unsafe_allow_html=True)
    st.caption("Clicks divided by opens. Isolates content quality from "
               "subject-line quality. If the open rate is falling but "
               "CTOR is stable, the copy is fine and the subject "
               "line is the problem. Industry benchmark for SaaS is "
               "about 10 to 15 percent.")

    ctor_df = emails_df.dropna(subset=["ctor"]).sort_values("week_start")
    if not ctor_df.empty:
        ctor_line = alt.Chart(ctor_df).mark_line(
            color=ACCENT, strokeWidth=2,
            point=alt.OverlayMarkDef(size=60, filled=True, color=ACCENT)
        ).encode(
            x=alt.X("week_start:T", title=None,
                    axis=alt.Axis(labelColor=MUTED)),
            y=alt.Y("ctor:Q", title="CTOR",
                    axis=alt.Axis(format=".0%", labelColor=MUTED)),
            tooltip=[
                alt.Tooltip("week_label:N", title="Week"),
                alt.Tooltip("ctor:Q", format=".2%", title="CTOR"),
                alt.Tooltip("opened:Q", title="Opens"),
                alt.Tooltip("clicks:Q", title="Clicks"),
            ],
        )
        ctor_bench = alt.Chart(pd.DataFrame({
            "y": [0.10, 0.15],
        })).mark_rule(color=MUTED, strokeDash=[3, 4], opacity=0.6).encode(
            y="y:Q")
        st.altair_chart((ctor_line + ctor_bench).properties(height=240),
                        width='stretch')
    else:
        st.info("Not enough data to compute CTOR in this window.")

    # ---- A/B TEST DETECTION ----
    # The ab_a_contacts / ab_b_contacts columns come from the updated
    # ETL. If the CSV was written before that update the columns will
    # be missing - fall back gracefully instead of crashing.
    if "ab_a_contacts" not in emails_df.columns:
        st.info("A/B batch detection needs a refresh. Run "
                 "`python etl/email_etl.py` again from the project folder "
                 "to add the new columns.")
        ab_weeks = pd.DataFrame()
    else:
        ab_weeks = emails_df.dropna(subset=["ab_a_contacts"])
    if not ab_weeks.empty:
        st.markdown('<h3 style="margin-top:2rem">A/B test detected</h3>',
                    unsafe_allow_html=True)
        st.caption(
            f"{len(ab_weeks)} week(s) in this window used the A/B split "
            f"notation from your task sheet. Side-by-side sizes shown "
            f"below. Add opens/clicks per batch to the task sheet to "
            f"score which side won.")
        for _, r in ab_weeks.iterrows():
            ab1, ab2 = st.columns(2, gap="medium")
            with ab1:
                st.markdown(
                    f'<div class="card">'
                    f'<span class="tag a">Batch A</span>'
                    f'<div style="margin:.4rem 0">'
                    f'<b style="font-size:1.3rem">'
                    f'{int(r["ab_a_contacts"])}</b>'
                    f' contacts &middot; '
                    f'{int(r["ab_a_delivered"])} delivered</div>'
                    f'<div style="font-size:.78rem;color:{MUTED}">'
                    f'{r["week_label"]}</div>'
                    f'</div>', unsafe_allow_html=True)
            with ab2:
                st.markdown(
                    f'<div class="card">'
                    f'<span class="tag b">Batch B</span>'
                    f'<div style="margin:.4rem 0">'
                    f'<b style="font-size:1.3rem">'
                    f'{int(r["ab_b_contacts"])}</b>'
                    f' contacts &middot; '
                    f'{int(r["ab_b_delivered"])} delivered</div>'
                    f'<div style="font-size:.78rem;color:{MUTED}">'
                    f'{r["week_label"]}</div>'
                    f'</div>', unsafe_allow_html=True)

    # ---- CADENCE ----
    st.markdown('<h3 style="margin-top:2rem">Cadence and audience</h3>',
                unsafe_allow_html=True)
    st.caption("Bars = emails sent that week. Line = contacts reached. "
               "Weeks with no bars but a full audience are days when a "
               "big campaign went out.")
    _bars = alt.Chart(emails_df).mark_bar(
        color=MUTED, opacity=0.7).encode(
        x=alt.X("week_start:T", title=None),
        y=alt.Y("emails_sent:Q", title="Emails / week",
                axis=alt.Axis(labelColor=MUTED)),
        tooltip=[alt.Tooltip("week_label:N", title="Week"),
                 alt.Tooltip("emails_sent:Q", title="Emails"),
                 alt.Tooltip("contacts:Q", title="Contacts")],
    )
    _cline = alt.Chart(emails_df).mark_line(
        color=ACCENT, strokeWidth=2).encode(
        x="week_start:T",
        y=alt.Y("contacts:Q", title="Contacts / week",
                axis=alt.Axis(labelColor=ACCENT, titleColor=ACCENT)))
    st.altair_chart(
        alt.layer(_bars, _cline).resolve_scale(y="independent"
        ).properties(height=260), width='stretch')

    # ---- BATCH SIZE VS OPEN RATE ----
    st.markdown('<h3 style="margin-top:2rem">Batch size vs open rate</h3>',
                unsafe_allow_html=True)
    st.caption("Does sending to a bigger list dilute the open rate? "
               "One dot per week. Size = clicks, colour = click rate.")
    scat = alt.Chart(emails_df.dropna(subset=["open_rate"])
    ).mark_circle(opacity=0.85, stroke=INK, strokeWidth=0.4).encode(
        x=alt.X("contacts:Q",
                title="Contacts reached (log)",
                scale=alt.Scale(type="log", base=10)),
        y=alt.Y("open_rate:Q", title="Open rate",
                axis=alt.Axis(format=".0%")),
        size=alt.Size("clicks:Q",
                      scale=alt.Scale(range=[40, 400]),
                      title="Clicks"),
        color=alt.Color("click_rate:Q",
                        scale=alt.Scale(scheme="teals"),
                        title="Click rate"),
        tooltip=[
            alt.Tooltip("week_label:N", title="Week"),
            alt.Tooltip("contacts:Q", title="Contacts"),
            alt.Tooltip("open_rate:Q", format=".2%",
                        title="Open rate"),
            alt.Tooltip("click_rate:Q", format=".2%",
                        title="Click rate"),
            alt.Tooltip("clicks:Q", title="Clicks"),
        ],
    ).properties(height=320)
    st.altair_chart(scat, width='stretch')

    # So-what: small vs large batch open rate
    _by = emails_df.dropna(subset=["contacts", "open_rate"]).copy()
    if len(_by) >= 6:
        _med = _by["contacts"].median()
        _small = _by[_by["contacts"] < _med]["open_rate"].mean() * 100
        _large = _by[_by["contacts"] >= _med]["open_rate"].mean() * 100
        if _small > _large + 2:
            so_what(f"Smaller sends (under {int(_med)} contacts) open at "
                     f"{_small:.0f}% vs {_large:.0f}% for larger sends. "
                     f"Tighter targeting is the biggest lever in the "
                     f"data.", tone="good")
        elif _large > _small + 2:
            so_what(f"Bigger sends (over {int(_med)} contacts) open at "
                     f"{_large:.0f}% vs {_small:.0f}% for smaller ones. "
                     f"Volume is not hurting open rate here.",
                     tone="info")

    explain_this(
        shows="One dot per weekly send. X = how many contacts you sent "
                "to. Y = the open rate you got. Dot size = clicks. "
                "Colour = click rate.",
        good_pattern="A flat cloud (open rate independent of list size) "
                        "is neutral. A downward cloud means big blasts "
                        "hurt engagement; an upward cloud means bigger "
                        "sends are OK.",
        action_hint="If bigger sends open worse: split the list into "
                     "tighter persona-based batches. The Audience page "
                     "helps you draw a small targeted batch.")

    # ---- DELIVERY HEALTH ----
    st.markdown('<h3 style="margin-top:2rem">Delivery health</h3>',
                unsafe_allow_html=True)
    st.caption("Bounce rate over time. Anything above 3% is a warning "
               "sign. Above 5% and the sender reputation is at risk.")
    health = alt.Chart(emails_df.dropna(subset=["bounce_rate"])
    ).mark_area(color=WARN, opacity=0.25).encode(
        x=alt.X("week_start:T", title=None),
        y=alt.Y("bounce_rate:Q", title="Bounce rate",
                axis=alt.Axis(format=".1%")),
        tooltip=[
            alt.Tooltip("week_label:N", title="Week"),
            alt.Tooltip("bounce_rate:Q", format=".2%",
                        title="Bounce rate"),
            alt.Tooltip("bounced:Q", title="Bounced"),
            alt.Tooltip("contacts:Q", title="Contacts"),
        ],
    ) + alt.Chart(emails_df.dropna(subset=["bounce_rate"])
    ).mark_line(color=WARN, strokeWidth=1.5).encode(
        x="week_start:T", y="bounce_rate:Q") + alt.Chart(
        pd.DataFrame({"y": [0.03]})
    ).mark_rule(color=MUTED, strokeDash=[3, 3]).encode(y="y:Q")
    st.altair_chart(health.properties(height=200),
                    width='stretch')

    # ---- BEST AND WORST WEEKS ----
    st.markdown('<h3 style="margin-top:2rem">Best and worst weeks</h3>',
                unsafe_allow_html=True)
    st.caption("By open rate. Rows read left to right: week, emails "
               "sent, contacts, delivered, opens, clicks, open rate, "
               "click rate.")
    table_df = emails_df.dropna(subset=["open_rate"]).copy()
    table_df["display_open"] = (table_df["open_rate"]
                                 .apply(lambda x: f"{x*100:.1f}%"))
    table_df["display_click"] = (table_df["click_rate"]
                                  .apply(lambda x: f"{x*100:.2f}%"
                                          if pd.notna(x) else ""))
    rank_cols = ["week_label", "emails_sent", "contacts",
                  "delivered", "opened", "clicks",
                  "display_open", "display_click"]
    col_config = {
        "week_label": st.column_config.TextColumn("Week", width="medium"),
        "emails_sent": st.column_config.NumberColumn("Emails",
                                                      format="%d"),
        "contacts": st.column_config.NumberColumn("Contacts",
                                                   format="%d"),
        "delivered": st.column_config.NumberColumn("Delivered",
                                                    format="%d"),
        "opened": st.column_config.NumberColumn("Opens", format="%d"),
        "clicks": st.column_config.NumberColumn("Clicks", format="%d"),
        "display_open": st.column_config.TextColumn("Open rate"),
        "display_click": st.column_config.TextColumn("Click rate"),
    }
    top_bot = st.tabs(["Top 5 by open rate", "Bottom 5 by open rate"])
    with top_bot[0]:
        st.dataframe(
            table_df.nlargest(5, "open_rate")[rank_cols],
            width='stretch', hide_index=True,
            column_config=col_config)
    with top_bot[1]:
        st.dataframe(
            table_df.nsmallest(5, "open_rate")[rank_cols],
            width='stretch', hide_index=True,
            column_config=col_config)

# ================================================================
# 3. DEEPER ANALYSIS (statistical rigor, segmentation, forecasting,
# diagnostics). Tabbed to keep the scroll manageable.
# ================================================================
if not emails_all.empty and not emails_df.empty:
    from scipy import stats as _sci_stats
    import numpy as np

    # ---- helper: Wilson score interval for a proportion ----
    def _wilson(k, n, z=1.96):
        if not n or pd.isna(k) or pd.isna(n) or n == 0:
            return (float("nan"), float("nan"))
        p = k / n
        denom = 1 + z * z / n
        centre = (p + z * z / (2 * n)) / denom
        spread = (z / denom) * ((p * (1 - p) / n
                                   + z * z / (4 * n * n)) ** 0.5)
        return max(0.0, centre - spread), min(1.0, centre + spread)

    # ---- helper: forecast next 4 weeks using linear extrapolation ----
    def _forecast_next_4(series_dates, series_values):
        valid = pd.DataFrame({"d": series_dates,
                                "v": series_values}).dropna()
        if len(valid) < 4:
            return pd.DataFrame()
        valid["x"] = (valid["d"] - valid["d"].min()).dt.days
        slope, intercept, r, _, _ = _sci_stats.linregress(
            valid["x"], valid["v"])
        future = []
        last_d = valid["d"].max()
        last_x = valid["x"].max()
        for i in range(1, 5):
            d = last_d + pd.Timedelta(days=7 * i)
            x = last_x + 7 * i
            pred = intercept + slope * x
            future.append({"d": d, "v": max(0.0, min(1.0, pred))})
        return pd.DataFrame(future)

    # ---- helper: change-point detection using rolling z-scores ----
    def _flag_anomalies(series, threshold=2.0, window=4):
        s = pd.Series(series)
        mean = s.rolling(window, min_periods=2).mean()
        std = s.rolling(window, min_periods=2).std().replace(0, np.nan)
        z = (s - mean) / std
        return z.abs() >= threshold, z

    e = emails_df.sort_values("week_start").reset_index(drop=True)

    with st.expander("For the analyst - deeper statistical analysis", expanded=False):
        st.caption("Confidence bands, batch-size segmentation, efficiency, and short forecasts. Skip this unless you want the detailed stats.")

        st.markdown('<div style="margin:2.5rem 0 0;border-top:1px solid '
                     + LINE + '"></div>', unsafe_allow_html=True)
        st.markdown('<h2>Deeper analysis</h2>', unsafe_allow_html=True)

        etab1, etab2, etab3, etab4 = st.tabs([
            "Rigor", "Segmentation", "Efficiency",
            "Forecast & diagnostics"])

        # ------------------------------------------------------------
        # TAB 1. RIGOR
        # ------------------------------------------------------------
        with etab1:
            st.markdown('<h3>Confidence bands on the open rate</h3>',
                        unsafe_allow_html=True)
            st.caption("Wilson score 95% intervals. Weeks with tiny audiences "
                       "get wide bands - so a 60% open on 50 contacts is "
                       "clearly less certain than a 10% open on 3,000.")

            ci = e.dropna(subset=["opened", "delivered"]).copy()
            ci["lo"], ci["hi"] = zip(*[
                _wilson(k, n)
                for k, n in zip(ci["opened"], ci["delivered"])])
            band = alt.Chart(ci).mark_area(color=ACCENT, opacity=0.18).encode(
                x=alt.X("week_start:T", title=None),
                y=alt.Y("lo:Q", title="Open rate",
                        axis=alt.Axis(format=".0%")),
                y2="hi:Q",
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("open_rate:Q", format=".2%",
                                title="Open rate"),
                    alt.Tooltip("lo:Q", format=".2%", title="95% low"),
                    alt.Tooltip("hi:Q", format=".2%", title="95% high"),
                    alt.Tooltip("delivered:Q", title="Sample size")])
            centre = alt.Chart(ci).mark_line(
                color=ACCENT, strokeWidth=2,
                point=alt.OverlayMarkDef(size=50, filled=True)
            ).encode(x="week_start:T", y="open_rate:Q",
                     tooltip=[
                         alt.Tooltip("week_label:N", title="Week"),
                         alt.Tooltip("open_rate:Q", format=".2%",
                                     title="Open rate"),
                         alt.Tooltip("delivered:Q", title="Sample size")])
            st.altair_chart((band + centre).properties(height=280),
                            width='stretch')

            # percentile of latest week vs own history
            st.markdown('<h3 style="margin-top:2rem">Percentile against '
                        'your own history</h3>', unsafe_allow_html=True)
            st.caption("Where the most recent week sits against every "
                       "week in the data. Your own baseline, not an "
                       "industry number.")
            all_open = emails_all.dropna(subset=["open_rate"])["open_rate"]
            latest_row = e[e["contacts"].fillna(0) > 0].sort_values(
                "week_start", ascending=False)
            if not latest_row.empty and not all_open.empty:
                L = latest_row.iloc[0]
                pctile = int((all_open < L["open_rate"]).mean() * 100)
                pt1, pt2, pt3 = st.columns(3)
                with pt1:
                    _stat("Open rate this week",
                            f"{L['open_rate']*100:.1f}%",
                            L["week_label"])
                with pt2:
                    _stat("Percentile", f"{pctile}th",
                            "of your own 30 weeks")
                with pt3:
                    med = all_open.median() * 100
                    _stat("Median across history", f"{med:.1f}%",
                            "the middle-of-the-pack week")

            # A/B with significance
            if "ab_a_contacts" in e.columns:
                st.markdown('<h3 style="margin-top:2rem">A/B batches: '
                            'is the difference real?</h3>',
                            unsafe_allow_html=True)
                ab = e.dropna(subset=["ab_a_contacts", "ab_b_contacts"])
                if ab.empty:
                    st.info("No A/B weeks in this window.")
                else:
                    st.caption(
                        "Fisher's exact test on delivered rates. Flags "
                        "'significant at 95%' or 'not enough sample'. "
                        "To score opens or clicks per batch, add those "
                        "to the task sheet.")
                    for _, r in ab.iterrows():
                        a_c = int(r["ab_a_contacts"] or 0)
                        b_c = int(r["ab_b_contacts"] or 0)
                        a_d = int(r["ab_a_delivered"] or 0)
                        b_d = int(r["ab_b_delivered"] or 0)
                        if a_c and b_c:
                            table = [[a_d, a_c - a_d],
                                      [b_d, b_c - b_d]]
                            try:
                                odds, p = _sci_stats.fisher_exact(table)
                            except Exception:
                                p = None
                            sig = ("significant at 95%"
                                    if p is not None and p < 0.05
                                    else "not significant given the sample")
                            st.markdown(
                                f'<div class="card">'
                                f'<b>{r["week_label"]}</b> &middot; '
                                f'A: {a_d}/{a_c} delivered '
                                f'&middot; B: {b_d}/{b_c} delivered '
                                f'&middot; <span style="color:{MUTED}">'
                                f'p={p:.3f}, {sig}</span>'
                                f'</div>' if p is not None else
                                f'<div class="card">'
                                f'<b>{r["week_label"]}</b> &middot; '
                                f'sample too small</div>',
                                unsafe_allow_html=True)

        # ------------------------------------------------------------
        # TAB 2. SEGMENTATION
        # ------------------------------------------------------------
        with etab2:
            st.markdown('<h3>Batch size analysis</h3>',
                        unsafe_allow_html=True)
            st.caption("Weeks binned into quartiles by contact count. "
                       "Median open and click rate for each bin. Answers "
                       "whether small tight sends really outperform.")
            bs = e.dropna(subset=["contacts", "open_rate"]).copy()
            if len(bs) >= 4:
                bs["bin"] = pd.qcut(bs["contacts"], q=4,
                                     labels=["Q1 (smallest)", "Q2", "Q3",
                                              "Q4 (largest)"],
                                     duplicates="drop")
                agg = bs.groupby("bin", as_index=False).agg(
                    weeks=("contacts", "count"),
                    median_contacts=("contacts", "median"),
                    median_open=("open_rate", "median"),
                    median_click=("click_rate", "median"))
                melt = agg.melt(id_vars=["bin", "weeks", "median_contacts"],
                                 value_vars=["median_open", "median_click"],
                                 var_name="metric", value_name="rate")
                melt["metric_lbl"] = melt["metric"].map({
                    "median_open": "Open rate",
                    "median_click": "Click rate"})
                bs_chart = alt.Chart(melt).mark_bar(
                    cornerRadiusEnd=3).encode(
                    x=alt.X("bin:N", title=None, sort=list(agg["bin"])),
                    y=alt.Y("rate:Q", title="Median rate",
                            axis=alt.Axis(format=".0%")),
                    color=alt.Color("metric_lbl:N", title=None,
                                     scale=alt.Scale(
                                         domain=["Open rate",
                                                  "Click rate"],
                                         range=[ACCENT, GOLD])),
                    column=alt.Column("metric_lbl:N", title=None),
                    tooltip=[
                        alt.Tooltip("bin:N", title="Batch bin"),
                        alt.Tooltip("weeks:Q", title="Weeks"),
                        alt.Tooltip("median_contacts:Q",
                                    title="Median contacts", format=",.0f"),
                        alt.Tooltip("rate:Q", format=".2%",
                                    title="Median rate")])
                st.altair_chart(bs_chart, width='stretch')
            else:
                st.info("Need at least 4 weeks in the window.")

            st.markdown('<h3 style="margin-top:2rem">Cadence fatigue</h3>',
                        unsafe_allow_html=True)
            st.caption("Is heavy sending this week hurting next week's open "
                       "rate? Trailing 2-week send volume plotted against "
                       "the following week's open rate. A downward slope "
                       "means the list is being over-sent.")
            fatigue = e.copy()
            fatigue["send_2w"] = fatigue["emails_sent"].rolling(
                window=2, min_periods=1).sum()
            fatigue["next_open"] = fatigue["open_rate"].shift(-1)
            fatigue = fatigue.dropna(subset=["send_2w", "next_open"])
            if not fatigue.empty:
                base = alt.Chart(fatigue).encode(
                    x=alt.X("send_2w:Q",
                            title="Emails sent in the last 2 weeks"),
                    y=alt.Y("next_open:Q",
                            title="Following week's open rate",
                            axis=alt.Axis(format=".0%")),
                    tooltip=[
                        alt.Tooltip("week_label:N", title="This week"),
                        alt.Tooltip("send_2w:Q",
                                    title="Trailing 2w sends"),
                        alt.Tooltip("next_open:Q",
                                    title="Next week open rate",
                                    format=".2%")])
                pts = base.mark_circle(size=100, color=ACCENT, opacity=0.8,
                                        stroke=INK, strokeWidth=0.4)
                trend = base.transform_regression(
                    "send_2w", "next_open").mark_line(
                    color=WARN, strokeDash=[4, 3], strokeWidth=2)
                st.altair_chart((pts + trend).properties(height=280),
                                width='stretch')
                # correlation
                r_val = fatigue[["send_2w", "next_open"]].corr().iloc[0, 1]
                verdict = ("suggests fatigue" if r_val < -0.2
                            else "no clear fatigue signal"
                            if r_val > -0.2 and r_val < 0.2
                            else "the opposite - more sends, more opens")
                st.caption(f"Correlation: {r_val:+.2f}. "
                            f"The pattern {verdict}.")

            st.markdown('<h3 style="margin-top:2rem">Monthly cohorts</h3>',
                        unsafe_allow_html=True)
            st.caption("Aggregated to calendar month. Which months naturally "
                       "perform better and by how much.")
            month_agg = e.copy()
            month_agg["month"] = month_agg["week_start"].dt.to_period(
                "M").dt.start_time
            m = month_agg.groupby("month").agg(
                emails=("emails_sent", "sum"),
                contacts=("contacts", "sum"),
                delivered=("delivered", "sum"),
                opened=("opened", "sum"),
                clicks=("clicks", "sum")).reset_index()
            m["open_rate"] = m["opened"] / m["delivered"].replace(0, np.nan)
            m["click_rate"] = m["clicks"] / m["delivered"].replace(0, np.nan)
            m_melt = m.melt(id_vars=["month"],
                             value_vars=["open_rate", "click_rate"],
                             var_name="metric", value_name="rate")
            m_melt["metric_lbl"] = m_melt["metric"].map({
                "open_rate": "Open rate", "click_rate": "Click rate"})
            mch = alt.Chart(m_melt).mark_bar(cornerRadiusEnd=3).encode(
                x=alt.X("month:T", title=None),
                y=alt.Y("rate:Q", title="Rate",
                        axis=alt.Axis(format=".0%")),
                color=alt.Color("metric_lbl:N", title=None,
                                 scale=alt.Scale(
                                     domain=["Open rate", "Click rate"],
                                     range=[ACCENT, GOLD])),
                xOffset="metric_lbl:N",
                tooltip=[alt.Tooltip("month:T", format="%b %Y"),
                         alt.Tooltip("metric_lbl:N", title="Metric"),
                         alt.Tooltip("rate:Q", format=".2%")])
            st.altair_chart(mch.properties(height=260),
                            width='stretch')

            st.markdown('<h3 style="margin-top:2rem">Quarterly rollup</h3>',
                        unsafe_allow_html=True)
            month_agg["quarter"] = month_agg["week_start"].dt.to_period(
                "Q").astype(str)
            q = month_agg.groupby("quarter").agg(
                emails=("emails_sent", "sum"),
                contacts=("contacts", "sum"),
                delivered=("delivered", "sum"),
                opened=("opened", "sum"),
                clicks=("clicks", "sum")).reset_index()
            q["open_rate"] = q["opened"] / q["delivered"].replace(0, np.nan)
            q["click_rate"] = q["clicks"] / q["delivered"].replace(0, np.nan)
            q_disp = q[["quarter", "emails", "contacts", "delivered",
                         "opened", "clicks", "open_rate",
                         "click_rate"]].copy()
            q_disp["open_rate"] = q_disp["open_rate"].apply(
                lambda x: f"{x*100:.1f}%" if pd.notna(x) else "")
            q_disp["click_rate"] = q_disp["click_rate"].apply(
                lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
            st.dataframe(q_disp, width='stretch', hide_index=True,
                         column_config={
                             "quarter": st.column_config.TextColumn(
                                 "Quarter"),
                             "emails": st.column_config.NumberColumn(
                                 "Emails", format="%d"),
                             "contacts": st.column_config.NumberColumn(
                                 "Contacts", format="%d"),
                             "delivered": st.column_config.NumberColumn(
                                 "Delivered", format="%d"),
                             "opened": st.column_config.NumberColumn(
                                 "Opens", format="%d"),
                             "clicks": st.column_config.NumberColumn(
                                 "Clicks", format="%d"),
                             "open_rate": st.column_config.TextColumn(
                                 "Open rate"),
                             "click_rate": st.column_config.TextColumn(
                                 "Click rate"),
                         })

        # ------------------------------------------------------------
        # TAB 3. EFFICIENCY
        # ------------------------------------------------------------
        with etab3:
            eff = e.copy()
            eff["opens_per_email"] = eff["opened"] / eff["emails_sent"].replace(
                0, np.nan)
            eff["clicks_per_email"] = eff["clicks"] / eff["emails_sent"].replace(
                0, np.nan)
            eff["opens_per_contact"] = eff["opened"] / eff["contacts"].replace(
                0, np.nan)
            eff["waste"] = (eff["contacts"] - eff["opened"]).clip(lower=0)

            st.markdown('<h3>Opens per email sent</h3>',
                        unsafe_allow_html=True)
            st.caption("A different lens on efficiency. Weeks with lots of "
                       "emails but few opens read as expensive here. "
                       "Higher is better.")
            oe = alt.Chart(eff.dropna(subset=["opens_per_email"])).mark_bar(
                color=ACCENT, opacity=0.85).encode(
                x=alt.X("week_start:T", title=None),
                y=alt.Y("opens_per_email:Q", title="Opens / email sent"),
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("emails_sent:Q", title="Emails"),
                    alt.Tooltip("opened:Q", title="Opens"),
                    alt.Tooltip("opens_per_email:Q", format=".1f",
                                title="Opens / email")])
            st.altair_chart(oe.properties(height=240),
                            width='stretch')

            st.markdown('<h3 style="margin-top:2rem">Effort scatter</h3>',
                        unsafe_allow_html=True)
            st.caption("X: emails sent that week. Y: total opens that week. "
                       "Top-left is a hero week (few emails, many opens). "
                       "Bottom-right is a warning (many emails, few opens).")
            eff_scatter = alt.Chart(eff.dropna(subset=[
                "emails_sent", "opened"])).mark_circle(
                size=140, color=ACCENT, opacity=0.85,
                stroke=INK, strokeWidth=0.4).encode(
                x=alt.X("emails_sent:Q", title="Emails sent"),
                y=alt.Y("opened:Q", title="Total opens"),
                size=alt.Size("contacts:Q",
                              scale=alt.Scale(range=[80, 500]),
                              title="Contacts"),
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("emails_sent:Q", title="Emails"),
                    alt.Tooltip("opened:Q", title="Opens"),
                    alt.Tooltip("contacts:Q", title="Contacts")])
            st.altair_chart(eff_scatter.properties(height=340),
                            width='stretch')

            st.markdown('<h3 style="margin-top:2rem">Waste tracker</h3>',
                        unsafe_allow_html=True)
            st.caption("Contacts that received an email but did not open it, "
                       "per week. This is the volume going out with no "
                       "return. Absolute count, not a rate.")
            waste_chart = alt.Chart(eff.dropna(subset=["waste"])).mark_area(
                color=WARN, opacity=0.25).encode(
                x=alt.X("week_start:T", title=None),
                y=alt.Y("waste:Q", title="Unopened contacts",
                        axis=alt.Axis(format=",.0f")),
                tooltip=[
                    alt.Tooltip("week_label:N", title="Week"),
                    alt.Tooltip("waste:Q", format=",.0f",
                                title="Unopened"),
                    alt.Tooltip("contacts:Q", format=",.0f",
                                title="Total contacts"),
                    alt.Tooltip("opened:Q", format=",.0f",
                                title="Opens")]) + alt.Chart(
                eff.dropna(subset=["waste"])).mark_line(
                color=WARN, strokeWidth=1.5).encode(
                x="week_start:T", y="waste:Q")
            st.altair_chart(waste_chart.properties(height=220),
                            width='stretch')

        # ------------------------------------------------------------
        # TAB 4. FORECAST & DIAGNOSTICS
        # ------------------------------------------------------------
        with etab4:
            st.markdown('<h3>4-week forecast</h3>', unsafe_allow_html=True)
            st.caption("Simple linear extrapolation on the recent trend. "
                       "Solid line = actual. Dashed line = forecast. "
                       "Directional, not oracular.")
            fc_open = _forecast_next_4(e["week_start"], e["open_rate"])
            fc_click = _forecast_next_4(e["week_start"], e["click_rate"])
            if not fc_open.empty:
                actual_o = e[["week_start", "open_rate"]].rename(
                    columns={"week_start": "d", "open_rate": "v"}).assign(
                    kind="actual", metric="Open rate")
                actual_c = e[["week_start", "click_rate"]].rename(
                    columns={"week_start": "d", "click_rate": "v"}).assign(
                    kind="actual", metric="Click rate")
                fc_o_lbl = fc_open.assign(kind="forecast",
                                             metric="Open rate")
                fc_c_lbl = fc_click.assign(kind="forecast",
                                              metric="Click rate")
                fc_all = pd.concat([actual_o, actual_c, fc_o_lbl,
                                     fc_c_lbl], ignore_index=True)
                fc_chart = alt.Chart(fc_all.dropna(subset=["v"])).mark_line(
                    point=alt.OverlayMarkDef(size=45, filled=True)
                ).encode(
                    x=alt.X("d:T", title=None),
                    y=alt.Y("v:Q", title="Rate",
                            axis=alt.Axis(format=".0%")),
                    color=alt.Color("metric:N", title=None,
                                     scale=alt.Scale(
                                         domain=["Open rate", "Click rate"],
                                         range=[ACCENT, GOLD])),
                    strokeDash=alt.StrokeDash("kind:N",
                                                scale=alt.Scale(
                                                    domain=["actual",
                                                             "forecast"],
                                                    range=[[1, 0],
                                                            [4, 3]])))
                st.altair_chart(fc_chart.properties(height=280),
                                width='stretch')
            else:
                st.info("Need at least 4 weeks with data to forecast.")

            st.markdown('<h3 style="margin-top:2rem">Anomaly detection</h3>',
                        unsafe_allow_html=True)
            st.caption("Weeks where open rate deviated more than 2 standard "
                       "deviations from the rolling 4-week trend. Real "
                       "signals of a shift, not weekly noise.")
            flag, z = _flag_anomalies(e["open_rate"].values, threshold=2.0,
                                       window=4)
            e_anom = e.copy()
            e_anom["anomaly"] = flag
            e_anom["z"] = z
            base_line = alt.Chart(e_anom).mark_line(
                color=MUTED, strokeWidth=1.5).encode(
                x="week_start:T", y=alt.Y("open_rate:Q", title="Open rate",
                                          axis=alt.Axis(format=".0%")))
            normal_pts = alt.Chart(e_anom[~e_anom["anomaly"]]).mark_circle(
                color=MUTED, size=50, opacity=0.8).encode(
                x="week_start:T", y="open_rate:Q",
                tooltip=[alt.Tooltip("week_label:N", title="Week"),
                         alt.Tooltip("open_rate:Q", format=".2%",
                                     title="Open rate")])
            anom_pts = alt.Chart(e_anom[e_anom["anomaly"]]).mark_circle(
                color=WARN, size=140, opacity=0.9,
                stroke=INK, strokeWidth=1).encode(
                x="week_start:T", y="open_rate:Q",
                tooltip=[alt.Tooltip("week_label:N", title="Week"),
                         alt.Tooltip("open_rate:Q", format=".2%",
                                     title="Open rate"),
                         alt.Tooltip("z:Q", format="+.2f",
                                     title="Z-score")])
            st.altair_chart(
                (base_line + normal_pts + anom_pts).properties(height=280),
                width='stretch')
            n_anom = int(e_anom["anomaly"].sum())
            st.caption(f"{n_anom} anomalous week(s) detected in this "
                        f"window.")

            st.markdown('<h3 style="margin-top:2rem">Correlation matrix</h3>',
                        unsafe_allow_html=True)
            st.caption("How the numeric metrics move together. Red pairs are "
                       "inversely related, teal pairs move in the same "
                       "direction.")
            corr_cols = ["emails_sent", "contacts", "delivered",
                          "bounced", "opened", "clicks", "delivery_rate",
                          "bounce_rate", "open_rate", "click_rate", "ctor"]
            corr_cols = [c for c in corr_cols if c in e.columns]
            corr = e[corr_cols].corr().round(2).reset_index().melt(
                "index", var_name="col", value_name="corr").rename(
                columns={"index": "row"})
            cm = alt.Chart(corr).mark_rect().encode(
                x=alt.X("col:N", title=None,
                        axis=alt.Axis(labelAngle=-40)),
                y=alt.Y("row:N", title=None),
                color=alt.Color("corr:Q",
                                 scale=alt.Scale(scheme="redblue",
                                                  domain=[-1, 1]),
                                 title="Correlation"),
                tooltip=["row", "col", "corr"])
            labels_cm = alt.Chart(corr).mark_text(fontSize=9,
                                                    color=INK).encode(
                x="col:N", y="row:N",
                text=alt.Text("corr:Q", format=".2f"))
            st.altair_chart((cm + labels_cm).properties(height=440),
                            width='stretch')

            st.markdown('<h3 style="margin-top:2rem">Trend decomposition</h3>',
                        unsafe_allow_html=True)
            st.caption("Loess smoother separates the underlying trajectory "
                       "from weekly noise. If the smooth line trends up, "
                       "the campaign is genuinely improving.")
            e_num = e.copy()
            e_num["week_num"] = (e_num["week_start"] -
                                    e_num["week_start"].min()).dt.days
            _pts = alt.Chart(e_num.dropna(subset=["open_rate"])).mark_circle(
                color=MUTED, size=50, opacity=0.7).encode(
                x=alt.X("week_start:T", title=None),
                y=alt.Y("open_rate:Q", title="Open rate",
                        axis=alt.Axis(format=".0%")))
            _sm = alt.Chart(e_num.dropna(subset=["open_rate"])).transform_loess(
                "week_num", "open_rate", bandwidth=0.5
            ).mark_line(color=ACCENT, strokeWidth=3).encode(
                x=alt.X("week_num:Q", title=None,
                        axis=alt.Axis(labels=False, ticks=False)),
                y="open_rate:Q")
            st.altair_chart((_pts + _sm).resolve_scale(
                x="independent").properties(height=260),
                             width='stretch')

# ================== INTEREST & ENGAGEMENT ==================
# Rows 10-12 of the source sheet: Replies (numeric), Most interested
# companies from Cognism (free text list of universities), Newsletter
# subscribers (numeric in later weeks, qualitative notes earlier).
# These are the closest thing we have to a pipeline signal from email.
if not emails_df.empty and {"interested_companies_count",
                              "newsletter_subs", "replies"}.issubset(
        emails_df.columns):
    st.markdown('<div style="margin:3rem 0 0;border-top:1px solid '
                + LINE + '"></div>', unsafe_allow_html=True)
    st.markdown('<h2>Interest &amp; engagement</h2>',
                  unsafe_allow_html=True)
    st.caption("Beyond opens and clicks: replies, universities "
               "flagged as 'most interested' by Cognism, and "
               "newsletter subscribers per week.")

    total_replies = int(emails_df["replies"].fillna(0).sum())
    total_interest = int(
        emails_df["interested_companies_count"].fillna(0).sum())
    n_interest_weeks = int(
        (emails_df["interested_companies_count"].fillna(0) > 0).sum())
    total_subs = int(emails_df["newsletter_subs"].fillna(0).sum())
    n_sub_weeks = int(emails_df["newsletter_subs"].notna().sum())

    it1, it2, it3, it4 = st.columns(4)
    with it1:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Replies</div>'
            f'<div class="kpi-value">{total_replies}</div>'
            f'<div class="kpi-sub">across the window</div></div>',
            unsafe_allow_html=True)
    with it2:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Interested universities</div>'
            f'<div class="kpi-value" style="color:{ACCENT}">'
            f'{total_interest}</div>'
            f'<div class="kpi-sub">mentions in {n_interest_weeks} '
            f'weeks</div></div>', unsafe_allow_html=True)
    with it3:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Newsletter subscribers</div>'
            f'<div class="kpi-value">{total_subs}</div>'
            f'<div class="kpi-sub">tracked in {n_sub_weeks} weeks'
            f'</div></div>', unsafe_allow_html=True)
    with it4:
        _avg_int = (total_interest / max(n_interest_weeks, 1)) \
            if n_interest_weeks else 0
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Avg interested / active week</div>'
            f'<div class="kpi-value">{_avg_int:.1f}</div>'
            f'<div class="kpi-sub">universities per week</div></div>',
            unsafe_allow_html=True)

    # ---- Interested-companies per week (bar) ----
    _int_df = emails_df.dropna(subset=["week_start"]).copy()
    _int_df["interested_companies_count"] = \
        _int_df["interested_companies_count"].fillna(0).astype(int)
    _int_df = _int_df[_int_df["interested_companies_count"] > 0]
    if not _int_df.empty:
        st.markdown('<div class="eyebrow" '
                    'style="margin-top:1.5rem">Interested '
                    'universities per week</div>',
                    unsafe_allow_html=True)
        int_bar = alt.Chart(_int_df).mark_bar(
            color=ACCENT, size=14).encode(
            x=alt.X("week_start:T", title=None),
            y=alt.Y("interested_companies_count:Q",
                    title="Universities flagged"),
            tooltip=[
                alt.Tooltip("week_label:N", title="Week"),
                alt.Tooltip("interested_companies_count:Q",
                             title="Count"),
                alt.Tooltip("interested_companies_raw:N",
                             title="Names"),
            ],
        ).properties(height=220)
        st.altair_chart(int_bar, width='stretch')

        # So-what for interested-companies chart
        _peak = _int_df.loc[
            _int_df["interested_companies_count"].idxmax()]
        _peak_n = int(_peak["interested_companies_count"])
        _peak_wk = str(_peak.get("week_label", ""))
        _weeks_active = len(_int_df)
        so_what(f"Peak intent week: <strong>{_peak_wk}</strong> with "
                 f"{_peak_n} interested universities flagged. "
                 f"{_weeks_active} weeks showed real intent signal "
                 f"in the current window.", tone="good")

    explain_this(
        shows="Number of universities Cognism flagged as &lsquo;most "
                "interested&rsquo; per week. This is the closest thing "
                "we have to pipeline signal from an email send.",
        good_pattern="A count of 3+ per week is healthy for our list "
                        "size. Peaks matter more than the raw average - "
                        "they mark which content angles hit.",
        action_hint="For any week with 5+ interested universities, "
                     "note which subject / campaign ran that week and "
                     "reuse the pattern. Follow up individually with "
                     "any name that appears in more than one week.")

    # ---- Top interested universities across the window ----
    all_names = []
    for s in emails_df["interested_companies_raw"].dropna().astype(str):
        s = s.strip()
        if not s:
            continue
        for n in s.split(";"):
            n = n.strip()
            if n:
                all_names.append(n)
    if all_names:
        from collections import Counter as _Counter
        _counts = _Counter(all_names)
        _top = _counts.most_common(15)
        _top_df = pd.DataFrame(_top, columns=["University",
                                                "Mentions"])
        cA, cB = st.columns([1.2, 1])
        with cA:
            st.markdown('<div class="eyebrow" '
                        'style="margin-top:1.5rem">Top interested '
                        'universities</div>',
                        unsafe_allow_html=True)
            st.dataframe(_top_df, width='stretch',
                          hide_index=True)
        with cB:
            st.markdown('<div class="eyebrow" '
                        'style="margin-top:1.5rem">Summary</div>',
                        unsafe_allow_html=True)
            _distinct = len(_counts)
            _repeats = sum(1 for _, c in _counts.items() if c > 1)
            st.markdown(
                f'<div class="card" style="padding:1rem 1.2rem">'
                f'<div><strong>{_distinct}</strong> distinct '
                f'universities showed interest.</div>'
                f'<div style="margin-top:.5rem"><strong>{_repeats}'
                f'</strong> appeared in more than one week - warm '
                f'leads to prioritise.</div>'
                f'<div style="margin-top:.5rem;color:{MUTED};'
                f'font-size:.85rem">Repeat mentions are the '
                f'strongest intent signal in this dataset.</div>'
                f'</div>', unsafe_allow_html=True)

    # ---- Newsletter subs per week (line, only where numeric) ----
    _sub_df = emails_df.dropna(
        subset=["week_start", "newsletter_subs"]).copy()
    if not _sub_df.empty:
        st.markdown('<div class="eyebrow" '
                    'style="margin-top:1.5rem">Newsletter '
                    'subscribers per week</div>',
                    unsafe_allow_html=True)
        sub_chart = alt.Chart(_sub_df).mark_line(
            color=GOLD, strokeWidth=3, point=alt.OverlayMarkDef(
                color=GOLD, size=60)).encode(
            x=alt.X("week_start:T", title=None),
            y=alt.Y("newsletter_subs:Q", title="Subscribers"),
            tooltip=[
                alt.Tooltip("week_label:N", title="Week"),
                alt.Tooltip("newsletter_subs:Q", title="Subs"),
            ],
        ).properties(height=220)
        st.altair_chart(sub_chart, width='stretch')

    # ---- Qualitative notes (from row 12 free text) ----
    _notes_df = emails_df[emails_df["newsletter_note"].astype(str)
                            .str.strip().replace("nan", "").ne("")]
    _notes_df = _notes_df[[
        "week_label", "newsletter_note"]].copy()
    if not _notes_df.empty:
        with st.expander(f"Qualitative notes ({len(_notes_df)} weeks)",
                           expanded=False):
            for _, r in _notes_df.iterrows():
                st.markdown(
                    f'<div style="border-left:3px solid {ACCENT};'
                    f'padding:.5rem .8rem;margin:.5rem 0;'
                    f'background:#faf7f0;border-radius:4px">'
                    f'<strong>{r["week_label"]}</strong><br>'
                    f'{r["newsletter_note"]}</div>',
                    unsafe_allow_html=True)


