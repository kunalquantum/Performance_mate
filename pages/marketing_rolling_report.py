"""
Email - Rolling monthly marketing report.

Ian's spec item #4. Enquiries and form completions matter more than
clicks. Report reads month by month with content-type breakdown.

Two source CSVs (both editable in Excel):
    data/marketing_report_monthly.csv    (one row per month)
    data/marketing_by_content_type.csv   (per month per content type)
"""
from shared import (core_question, inject_css, render_status_key, kpi_tile, so_what,
                     load_csv, INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Rolling marketing report</h1>', unsafe_allow_html=True)
core_question("How much marketing is actually turning into enquiries and form completions, month by month?")
st.caption("Month-by-month, the numbers Ian actually cares about. "
            "Enquiries and form completions weigh more than clicks - "
            "a click on its own is a step, not the objective.")
render_status_key()

with st.expander("What each column means", expanded=False):
    st.markdown("""
- **Emails sent** &mdash; total emails released in the month.
- **Delivered** &mdash; sends that reached an inbox (not bounced).
- **Opened** &mdash; unique opens.
- **Clicks** &mdash; unique clicks on any link. Interesting but not
  the goal.
- **Form completions / downloads** &mdash; the reader filled a form
  or downloaded a whitepaper. First real intent signal.
- **Enquiries** &mdash; the reader replied or booked a call.
  **This is the marketing objective.** Every other metric matters
  only because it leads here.
- **Bounces** &mdash; undeliverable sends. Above 3% of sends hurts
  future deliverability; needs list hygiene.

**Content type buckets** &mdash; Whitepaper email, Event email,
Product email, Newsletter, Other. Different types earn different
engagement profiles; the breakdown shows which content is doing
the pipeline work.
""")


monthly = load_csv("marketing_report_monthly.csv")
by_type = load_csv("marketing_by_content_type.csv")

if monthly.empty:
    st.markdown(
        f'<div style="background:#EBF3F2;border-left:4px solid '
        f'{ACCENT};padding:1rem 1.3rem;border-radius:6px;'
        f'margin:1rem 0">'
        f'<div style="font-weight:600;color:{INK};font-size:1rem;'
        f'margin-bottom:.4rem">Start tracking this month</div>'
        f'<div style="color:{INK_SOFT};font-size:.92rem;'
        f'line-height:1.5">Type the numbers into the table below and '
        f'click Save. The report will fill in on next visit. '
        f'Enquiries and form completions matter most - that is the '
        f'marketing objective.</div>'
        f'</div>', unsafe_allow_html=True)

    import datetime as _dt
    default_month = _dt.date.today().strftime("%Y-%m")
    default_month = st.text_input(
        "Month to track", value=default_month,
        help="Format YYYY-MM, e.g. 2026-08.")

    seed = pd.DataFrame([{
        "month":            default_month,
        "emails_sent":      0,
        "emails_delivered": 0,
        "opened":           0,
        "clicks":           0,
        "form_completions": 0,
        "enquiries":        0,
        "bounces":          0,
    }])

    edited = st.data_editor(
        seed,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "month":            st.column_config.TextColumn(
                                    "Month", disabled=True),
            "emails_sent":      st.column_config.NumberColumn(
                                    "Sent", min_value=0, step=1),
            "emails_delivered": st.column_config.NumberColumn(
                                    "Delivered", min_value=0, step=1),
            "opened":           st.column_config.NumberColumn(
                                    "Opened", min_value=0, step=1),
            "clicks":           st.column_config.NumberColumn(
                                    "Clicks", min_value=0, step=1),
            "form_completions": st.column_config.NumberColumn(
                                    "Form completions",
                                    min_value=0, step=1),
            "enquiries":        st.column_config.NumberColumn(
                                    "Enquiries", min_value=0, step=1,
                                    help="The marketing objective."),
            "bounces":          st.column_config.NumberColumn(
                                    "Bounces", min_value=0, step=1),
        })

    if st.button("Save this month", type="primary",
                   key="mrr_save_empty"):
        import os as _os
        out_path = _os.path.join("data",
                                    "marketing_report_monthly.csv")
        edited.to_csv(out_path, index=False)
        st.success(f"Saved {default_month}. Reload the page to see "
                    "the report.")
        st.rerun()

    st.stop()


# Coerce numerics
for c in ("emails_sent", "emails_delivered", "opened", "clicks",
            "form_completions", "enquiries", "bounces"):
    if c in monthly.columns:
        monthly[c] = pd.to_numeric(monthly[c], errors="coerce").fillna(0) \
            .astype(int)

monthly = monthly.sort_values("month")


# ==========================================================================
# Latest month tiles
# ==========================================================================
latest = monthly.iloc[-1]
prev   = monthly.iloc[-2] if len(monthly) >= 2 else None
month_label = str(latest["month"])

st.markdown(f'<h2>Latest month: {month_label}</h2>',
             unsafe_allow_html=True)


def _delta_sub(cur, prev_row, col):
    if prev_row is None:
        return ""
    prev_v = int(prev_row.get(col, 0) or 0)
    diff = cur - prev_v
    if diff > 0:
        return f"up {diff} from last month"
    if diff < 0:
        return f"down {abs(diff)} from last month"
    return "same as last month"


sent      = int(latest["emails_sent"])
delivered = int(latest["emails_delivered"])
opened    = int(latest["opened"])
clicks    = int(latest["clicks"])
forms     = int(latest["form_completions"])
enquiries = int(latest["enquiries"])
bounces   = int(latest["bounces"])

open_pct = opened / max(delivered, 1) * 100
click_pct = clicks / max(delivered, 1) * 100
bounce_pct = bounces / max(sent, 1) * 100

# Row 1: the volume tiles
v1, v2, v3, v4 = st.columns(4)
with v1:
    kpi_tile("Emails sent", f"{sent:,}",
              sub=_delta_sub(sent, prev, "emails_sent"),
              tooltip="Total emails released in the month.")
with v2:
    kpi_tile("Delivered", f"{delivered:,}",
              sub=f"{delivered/max(sent,1)*100:.0f}% delivery",
              tooltip="Sends that reached an inbox. Should be 97%+.",
              color=ACCENT if delivered/max(sent,1) >= 0.97 else GOLD)
with v3:
    kpi_tile("Opened", f"{opened:,}",
              sub=f"{open_pct:.0f}% open rate",
              tooltip="Unique opens. SaaS benchmark 20%.",
              color=ACCENT if open_pct >= 20 else GOLD)
with v4:
    kpi_tile("Clicks", f"{clicks:,}",
              sub=f"{click_pct:.1f}% click rate",
              tooltip="Unique clicks. A step, not the objective.")

# Row 2: the objective tiles (highlighted)
o1, o2, o3, o4 = st.columns(4)
with o1:
    kpi_tile("Form completions / downloads",
              f"{forms:,}",
              sub=_delta_sub(forms, prev, "form_completions"),
              tooltip="Readers who filled a form or downloaded a "
                      "whitepaper. First real intent signal.",
              color=ACCENT if forms > 0 else GOLD)
with o2:
    kpi_tile("Enquiries",
              f"{enquiries:,}",
              sub="the marketing objective",
              tooltip="Readers who replied or booked a call. This "
                      "is the number that matters. Everything else "
                      "in the funnel exists to produce this.",
              color=ACCENT if enquiries > 0 else WARN)
with o3:
    kpi_tile("Bounce rate",
              f"{bounce_pct:.1f}%",
              sub=f"{bounces} bounces",
              tooltip="Undeliverable sends as a share of total. "
                      "Above 3% hurts deliverability.",
              color=ACCENT if bounce_pct < 3 else WARN)
with o4:
    ct_rate = clicks / max(opened, 1) * 100
    kpi_tile("Click-to-open rate",
              f"{ct_rate:.0f}%",
              sub="clicks / opens",
              tooltip="Of the people who opened, how many clicked. "
                      "Isolates copy quality from subject-line quality. "
                      "Benchmark 10-15%.",
              color=ACCENT if ct_rate >= 10 else GOLD)

so_what(
    f"This month produced <strong>{enquiries}</strong> enquiries "
    f"and <strong>{forms}</strong> form completions from "
    f"<strong>{sent}</strong> emails. The clicks and opens are only "
    f"there to feed those two numbers. If enquiries are flat, the "
    f"copy is not moving the reader from &lsquo;interesting&rsquo; "
    f"to &lsquo;let&apos;s talk&rsquo;.",
    tone="info" if enquiries > 0 else "warn")


# ==========================================================================
# Rolling monthly table
# ==========================================================================
st.markdown('<h2>Rolling monthly history</h2>',
             unsafe_allow_html=True)
st.caption("Every month tracked, newest first. Sort or scan for the "
            "months where enquiries actually moved.")

view = monthly.sort_values("month", ascending=False)
view["Open rate"]   = (view["opened"] / view["emails_delivered"]
                         .replace(0, 1) * 100).round(1)
view["Click rate"]  = (view["clicks"] / view["emails_delivered"]
                         .replace(0, 1) * 100).round(1)
view["Bounce rate"] = (view["bounces"] / view["emails_sent"]
                         .replace(0, 1) * 100).round(1)

display = view[[
    "month", "emails_sent", "emails_delivered", "opened", "clicks",
    "form_completions", "enquiries", "bounces",
    "Open rate", "Click rate", "Bounce rate",
]].rename(columns={
    "month":             "Month",
    "emails_sent":       "Sent",
    "emails_delivered":  "Delivered",
    "opened":            "Opened",
    "clicks":            "Clicks",
    "form_completions":  "Forms",
    "enquiries":         "Enquiries",
    "bounces":           "Bounces",
})

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Sent":      st.column_config.NumberColumn(format="%d"),
        "Delivered": st.column_config.NumberColumn(format="%d"),
        "Opened":    st.column_config.NumberColumn(format="%d"),
        "Clicks":    st.column_config.NumberColumn(format="%d"),
        "Forms":     st.column_config.NumberColumn(
            format="%d",
            help="Form completions / downloads. First intent "
                    "signal."),
        "Enquiries": st.column_config.NumberColumn(
            format="%d",
            help="The marketing objective. Replies + calls booked."),
        "Bounces":   st.column_config.NumberColumn(format="%d"),
        "Open rate":   st.column_config.NumberColumn(format="%.1f%%"),
        "Click rate":  st.column_config.NumberColumn(format="%.1f%%"),
        "Bounce rate": st.column_config.NumberColumn(format="%.1f%%"),
    })


# ==========================================================================
# Content-type breakdown (latest month)
# ==========================================================================
st.markdown('<h2>Performance by content type</h2>',
             unsafe_allow_html=True)
if by_type.empty:
    st.info("Content-type breakdown not populated. Fill "
             "`data/marketing_by_content_type.csv` (columns: "
             "`month, content_type, emails_sent, delivered, opened, "
             "clicks, form_completions, enquiries`).")
else:
    for c in ("emails_sent", "delivered", "opened", "clicks",
                "form_completions", "enquiries"):
        if c in by_type.columns:
            by_type[c] = pd.to_numeric(by_type[c],
                                         errors="coerce").fillna(0).astype(int)

    ct_month_options = sorted(
        by_type["month"].dropna().astype(str).unique(),
        reverse=True)
    default_idx = ct_month_options.index(month_label) \
        if month_label in ct_month_options else 0
    ct_pick = st.selectbox("Month", ct_month_options,
                            index=default_idx,
                            key="ct_month")
    ct_view = by_type[by_type["month"].astype(str) == ct_pick].copy()

    if ct_view.empty:
        st.caption("No content-type rows for that month yet.")
    else:
        ct_view["Open rate"] = (ct_view["opened"] / ct_view["delivered"]
                                  .replace(0, 1) * 100).round(1)
        ct_view["Click rate"] = (ct_view["clicks"] / ct_view["delivered"]
                                   .replace(0, 1) * 100).round(1)
        ct_view = ct_view.sort_values("enquiries", ascending=False)
        display_ct = ct_view[[
            "content_type", "emails_sent", "opened", "clicks",
            "form_completions", "enquiries",
            "Open rate", "Click rate",
        ]].rename(columns={
            "content_type":     "Content type",
            "emails_sent":      "Sent",
            "opened":           "Opened",
            "clicks":           "Clicks",
            "form_completions": "Forms",
            "enquiries":        "Enquiries",
        })
        st.dataframe(
            display_ct,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Enquiries": st.column_config.NumberColumn(
                    format="%d",
                    help="The marketing objective. If a content type "
                            "has zero enquiries across several months, "
                            "cut it or rework the CTA."),
                "Open rate":  st.column_config.NumberColumn(format="%.1f%%"),
                "Click rate": st.column_config.NumberColumn(format="%.1f%%"),
            })

        # So-what for content-type
        top = ct_view.iloc[0]
        zero = ct_view[ct_view["enquiries"] == 0]["content_type"] \
            .tolist()
        if int(top["enquiries"]) > 0:
            so_what(
                f"Best content type in {ct_pick}: "
                f"<strong>{top['content_type']}</strong> with "
                f"{int(top['enquiries'])} enquiries from "
                f"{int(top['emails_sent'])} sends. Ship more of this.",
                tone="good")
        if zero:
            so_what(
                f"Zero enquiries this month from: "
                f"<strong>{', '.join(zero)}</strong>. If the same "
                f"buckets stay at zero next month, cut them or rework "
                f"the CTA.", tone="warn")


with st.expander("How to update this each month", expanded=False):
    st.markdown("""
Two files to edit in Excel:

**`data/marketing_report_monthly.csv`** &mdash; one row per month:
```
month, emails_sent, emails_delivered, opened, clicks, form_completions, enquiries, bounces
2026-08, 120, 116, 32, 8, 4, 2, 4
```

**`data/marketing_by_content_type.csv`** &mdash; one row per
(month, content type):
```
month, content_type, emails_sent, delivered, opened, clicks, form_completions, enquiries
2026-08, Whitepaper email, 40, 39, 15, 5, 3, 2
2026-08, Event email, 30, 30, 8, 1, 0, 0
2026-08, Product email, 30, 28, 6, 1, 1, 0
2026-08, Newsletter, 20, 19, 3, 1, 0, 0
2026-08, Other, 0, 0, 0, 0, 0, 0
```

Save. Both files are picked up automatically on next rerun.
""")
