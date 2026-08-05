"""
Email - Persona Performance matrix.

Outbound activity + conversion by buying-committee persona. Answers:
which persona is opening / replying / booking meetings / winning?
Where is the funnel drying up?

Data lives in:
    data/persona_performance.csv   (per-persona engagement metrics)
    data/persona_funnel.csv        (per-persona pipeline funnel)

Seeded from the Grant_Management_Sales_Performance_Matrix.docx spec.
Replace those CSVs with real numbers when the ESP + CRM feed lights up.
"""
from shared import (inject_css, render_status_key, so_what, explain_this,
                     kpi_tile, load_csv, INK, INK_SOFT, MUTED, LINE,
                     BG, BG_SOFT, ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import altair as alt
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Persona</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Persona performance matrix</h1>', unsafe_allow_html=True)
st.caption("How each buying-committee persona is engaging with our "
            "email programme, from opens through to closed-won. Use "
            "this to see which personas are carrying the funnel and "
            "which need a fresh messaging angle.")
render_status_key()

with st.expander("What the terms mean", expanded=False):
    st.markdown("""
- **Persona** &mdash; the role of the person we&apos;re emailing:
  Principal Investigator (PI), Research Office, Grant Administrator,
  Finance, Dean / HOD, Research Director. In grant-management sales
  these are the six seats on the buying committee at a university or
  research institution.
- **Open rate** &mdash; opens divided by delivered. SaaS benchmark: 20%.
- **CTR (click-through rate)** &mdash; clicks divided by delivered.
  SaaS benchmark: 2-3%. In persona sales copy 15%+ is strong.
- **Replies** &mdash; how many personas wrote back. Strongest signal.
- **Meetings** &mdash; how many booked a call or demo.
- **Opportunities** &mdash; deals opened in the CRM.
- **Win rate** &mdash; closed-won opportunities divided by opportunities
  created. Answers &lsquo;when this persona buys, how often do we win?&rsquo;
- **Funnel** &mdash; target accounts &rarr; contacted &rarr; engaged
  &rarr; demo booked &rarr; opportunity &rarr; closed-won. Each step is
  a drop-off; big drops flag the weak link.
""")


pp = load_csv("persona_performance.csv")
pf = load_csv("persona_funnel.csv")

if pp.empty:
    st.info("No persona data loaded. Populate "
             "`data/persona_performance.csv` to build this page.")
    st.stop()


# ==========================================================================
# Top-line summary tiles
# ==========================================================================
best_open   = pp.loc[pp["open_rate"].idxmax()]
worst_open  = pp.loc[pp["open_rate"].idxmin()]
best_win    = pp.loc[pp["win_rate"].idxmax()]
top_meets   = pp.loc[pp["meetings"].idxmax()]

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_tile("Best open rate",
              f"{best_open['open_rate']*100:.0f}%",
              str(best_open["persona"]),
              tooltip="Persona with the highest email open rate. "
                      "Points to which pain framing is landing best.",
              color=ACCENT)
with k2:
    kpi_tile("Weakest persona",
              f"{worst_open['open_rate']*100:.0f}%",
              str(worst_open["persona"]),
              tooltip="Persona with the lowest open rate. The "
                      "messaging for this seat on the buying "
                      "committee likely needs rework.",
              color=GOLD)
with k3:
    kpi_tile("Best win rate",
              f"{best_win['win_rate']*100:.0f}%",
              str(best_win["persona"]),
              tooltip="Persona with the highest win rate on "
                      "opportunities created. When they buy, they buy.",
              color=ACCENT)
with k4:
    kpi_tile("Most meetings",
              f"{int(top_meets['meetings'])}",
              str(top_meets["persona"]),
              tooltip="Persona that has agreed to the most demo or "
                      "discovery calls.")


# ==========================================================================
# Full persona table with coloured cells
# ==========================================================================
st.markdown('<h2>Persona scorecard</h2>', unsafe_allow_html=True)
st.caption("Every persona, every metric. Green cells are strong, gold "
            "means look closer.")


def _cell_bg(value, kind):
    """Colour a table cell based on the metric it holds. Returns a
    background colour hex."""
    if kind == "open":
        if value >= 0.55: return "#DDEEEC"
        if value >= 0.35: return "#F7F0DA"
        return "#FBEDED"
    if kind == "ctr":
        if value >= 0.20: return "#DDEEEC"
        if value >= 0.10: return "#F7F0DA"
        return "#FBEDED"
    if kind == "win":
        if value >= 0.30: return "#DDEEEC"
        if value >= 0.20: return "#F7F0DA"
        return "#FBEDED"
    return BG


rows_html = []
header = (
    f'<div style="display:grid;grid-template-columns:'
    f'2fr .8fr .9fr .8fr .8fr .8fr .9fr .8fr;gap:.4rem;'
    f'padding:.5rem .7rem;font-size:.72rem;'
    f'text-transform:uppercase;letter-spacing:.12em;color:{MUTED};'
    f'font-weight:600;border-bottom:1px solid {LINE}">'
    f'<div>Persona</div><div>Sent</div><div>Open rate</div>'
    f'<div>CTR</div><div>Replies</div><div>Meetings</div>'
    f'<div>Opportunities</div><div>Win rate</div></div>')
rows_html.append(header)

for _, r in pp.sort_values("open_rate", ascending=False).iterrows():
    _open_bg = _cell_bg(r["open_rate"], "open")
    _ctr_bg  = _cell_bg(r["ctr"],       "ctr")
    _win_bg  = _cell_bg(r["win_rate"],  "win")
    rows_html.append(
        f'<div style="display:grid;grid-template-columns:'
        f'2fr .8fr .9fr .8fr .8fr .8fr .9fr .8fr;gap:.4rem;'
        f'padding:.55rem .7rem;font-size:.9rem;'
        f'border-bottom:1px solid {LINE};align-items:center">'
        f'<div style="color:{INK};font-weight:600">{r["persona"]}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["emails_sent"])}</div>'
        f'<div style="background:{_open_bg};padding:.15rem .4rem;'
        f'border-radius:4px;color:{INK};font-weight:600">'
        f'{r["open_rate"]*100:.0f}%</div>'
        f'<div style="background:{_ctr_bg};padding:.15rem .4rem;'
        f'border-radius:4px;color:{INK};font-weight:600">'
        f'{r["ctr"]*100:.0f}%</div>'
        f'<div style="color:{INK_SOFT}">{int(r["replies"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["meetings"])}</div>'
        f'<div style="color:{INK_SOFT}">{int(r["opportunities"])}</div>'
        f'<div style="background:{_win_bg};padding:.15rem .4rem;'
        f'border-radius:4px;color:{INK};font-weight:600">'
        f'{r["win_rate"]*100:.0f}%</div>'
        f'</div>')
st.markdown(
    f'<div style="border:1px solid {LINE};border-radius:6px;'
    f'background:{BG};overflow:hidden">{"".join(rows_html)}</div>',
    unsafe_allow_html=True)


# So-what for the scorecard
_span_open = (best_open["open_rate"] - worst_open["open_rate"]) * 100
so_what(
    f"<strong>{best_open['persona']}</strong> is opening at "
    f"{best_open['open_rate']*100:.0f}%, "
    f"<strong>{worst_open['persona']}</strong> at "
    f"{worst_open['open_rate']*100:.0f}%. That is a "
    f"{_span_open:.0f}-point spread across the buying committee. "
    f"The weak persona&apos;s messaging is the biggest single lever "
    f"in the funnel.", tone="info")


# ==========================================================================
# Open rate + Win rate paired bar chart
# ==========================================================================
st.markdown('<h2>Open rate vs win rate by persona</h2>',
             unsafe_allow_html=True)
st.caption("A persona that opens AND wins is a persona to double down "
            "on. A persona that opens but does not win needs a better "
            "hand-off. A persona that neither opens nor wins needs a "
            "fresh angle.")

_paired = pd.melt(
    pp[["persona", "open_rate", "win_rate"]].assign(
        open_rate=pp["open_rate"] * 100,
        win_rate=pp["win_rate"] * 100),
    id_vars=["persona"], var_name="Metric", value_name="Value")
_paired["Metric"] = _paired["Metric"].map({
    "open_rate": "Open rate %", "win_rate": "Win rate %"})

pair_chart = alt.Chart(_paired).mark_bar(size=18).encode(
    y=alt.Y("persona:N", sort=alt.EncodingSortField(
        field="Value", op="mean", order="descending"), title=None),
    x=alt.X("Value:Q", title="Percent", scale=alt.Scale(domain=[0, 80])),
    yOffset="Metric:N",
    color=alt.Color("Metric:N",
                      scale=alt.Scale(range=[ACCENT, GOLD]),
                      legend=alt.Legend(orient="top")),
    tooltip=["persona:N", "Metric:N",
              alt.Tooltip("Value:Q", format=".1f")],
).properties(height=max(260, 60 * len(pp)))
st.altair_chart(pair_chart, width='stretch')

explain_this(
    shows="Two bars per persona - teal is open rate, gold is win rate. "
            "Both on a 0-80% scale so you can eyeball whether opens "
            "translate into wins.",
    good_pattern="Both bars long for the same persona = the messaging "
                    "AND the sales handover are working. If teal is "
                    "long but gold is short, the copy is landing but "
                    "the pitch after isn&apos;t.",
    action_hint="For any persona with a short teal bar, rewrite the "
                 "email angle. For any persona with a short gold bar "
                 "(despite long teal), review the sales conversation "
                 "for that seat.")


# ==========================================================================
# Funnel by persona (if data present)
# ==========================================================================
if not pf.empty:
    st.markdown('<h2>Pipeline funnel by persona</h2>',
                 unsafe_allow_html=True)
    st.caption("End-to-end progression from target account to "
                "closed-won. The width of each stage shows the count. "
                "Look for the stage where each persona&apos;s funnel "
                "narrows sharply.")

    # Build one horizontal funnel per persona as stacked bars
    funnel_stages = ["target_accounts", "contacted", "engaged",
                       "demo_booked", "opportunity", "closed_won"]
    stage_labels = {
        "target_accounts": "Target",
        "contacted":       "Contacted",
        "engaged":         "Engaged",
        "demo_booked":     "Demo booked",
        "opportunity":     "Opportunity",
        "closed_won":      "Closed-won",
    }

    for _, r in pf.iterrows():
        persona = str(r["persona"])
        target  = int(r["target_accounts"]) or 1

        st.markdown(
            f'<div style="margin-top:1.2rem;font-size:.85rem;'
            f'color:{INK};font-weight:600">{persona}</div>',
            unsafe_allow_html=True)

        # Render as one row of bars with a shared max width
        stages_html = []
        for stage in funnel_stages:
            count = int(r[stage])
            pct = count / target * 100
            _colour = ACCENT if stage == "closed_won" else \
                (GOLD if pct < 20 and stage != "target_accounts"
                  else ACCENT)
            stages_html.append(
                f'<div style="flex:1;text-align:center;padding:.35rem 0;'
                f'margin:0 .15rem;background:{BG_SOFT};'
                f'border-top:3px solid {_colour};border-radius:4px">'
                f'<div style="font-size:.7rem;color:{MUTED};'
                f'text-transform:uppercase;letter-spacing:.1em">'
                f'{stage_labels[stage]}</div>'
                f'<div style="font-size:1.1rem;color:{INK};'
                f'font-weight:700">{count}</div>'
                f'<div style="font-size:.72rem;color:{MUTED}">'
                f'{pct:.0f}% of target</div>'
                f'</div>')
        st.markdown(
            f'<div style="display:flex;align-items:stretch">'
            f'{"".join(stages_html)}</div>', unsafe_allow_html=True)

    # So-what: biggest drop-off across the funnel per persona
    pf_calc = pf.copy()
    pf_calc["contact_pct"] = pf_calc["contacted"] / \
        pf_calc["target_accounts"] * 100
    pf_calc["engage_pct"]  = pf_calc["engaged"] / \
        pf_calc["contacted"].replace(0, 1) * 100
    pf_calc["demo_pct"]    = pf_calc["demo_booked"] / \
        pf_calc["engaged"].replace(0, 1) * 100
    pf_calc["opp_pct"]     = pf_calc["opportunity"] / \
        pf_calc["demo_booked"].replace(0, 1) * 100
    pf_calc["win_pct"]     = pf_calc["closed_won"] / \
        pf_calc["opportunity"].replace(0, 1) * 100

    weakest_bits = []
    for _, r in pf_calc.iterrows():
        drop = {
            "target -> contact": 100 - r["contact_pct"],
            "contact -> engage": 100 - r["engage_pct"],
            "engage -> demo":    100 - r["demo_pct"],
            "demo -> opp":       100 - r["opp_pct"],
            "opp -> won":        100 - r["win_pct"],
        }
        weakest = max(drop, key=drop.get)
        weakest_bits.append(
            f"<strong>{r['persona']}</strong>: biggest leak is "
            f"<em>{weakest}</em> ({drop[weakest]:.0f}% drop).")
    so_what("<br>".join(weakest_bits), tone="warn")


# ==========================================================================
# Suggested next action
# ==========================================================================
st.markdown('<h2>Next actions</h2>', unsafe_allow_html=True)

actions = []
# Rule: any persona with open rate below 40% needs a rewrite
weak_personas = pp[pp["open_rate"] < 0.40]["persona"].tolist()
if weak_personas:
    actions.append(
        f"Rewrite the messaging angle for: "
        f"<strong>{', '.join(weak_personas)}</strong>. Their open "
        f"rate is below 40% - the current subject line and opening "
        f"are not landing for these seats.")

# Rule: personas with strong CTR but low win rate need better hand-off
_mismatch = pp[(pp["ctr"] >= 0.20) & (pp["win_rate"] < 0.25)]
for _, r in _mismatch.iterrows():
    actions.append(
        f"<strong>{r['persona']}</strong> clicks at "
        f"{r['ctr']*100:.0f}% but wins at only "
        f"{r['win_rate']*100:.0f}%. The copy is doing its job - "
        f"review the sales conversation after the click.")

# Rule: personas with high open + high win are the growth engine
_star = pp[(pp["open_rate"] >= 0.55) & (pp["win_rate"] >= 0.30)]
for _, r in _star.iterrows():
    actions.append(
        f"Double down on <strong>{r['persona']}</strong>: opens at "
        f"{r['open_rate']*100:.0f}% AND wins at "
        f"{r['win_rate']*100:.0f}%. Ship more emails to this seat.")

if not actions:
    st.markdown(
        f'<div style="color:{INK_SOFT};font-size:.95rem">'
        f'No urgent actions. Cadence is healthy.</div>',
        unsafe_allow_html=True)
else:
    for a in actions:
        st.markdown(
            f'<div style="background:{BG_SOFT};border-left:3px solid '
            f'{ACCENT};padding:.6rem 1rem;margin:.5rem 0;'
            f'border-radius:4px;font-size:.92rem;line-height:1.5">'
            f'{a}</div>', unsafe_allow_html=True)


st.markdown(
    f'<div style="margin-top:2.5rem;color:{MUTED};font-size:.75rem">'
    f'Data source: <code>data/persona_performance.csv</code> and '
    f'<code>data/persona_funnel.csv</code>. Currently seeded from the '
    f'spec doc; replace with real ESP + CRM extract when available.'
    f'</div>', unsafe_allow_html=True)
