"""
Board pack - a single scrollable summary page designed to be printed
straight to PDF (Ctrl/Cmd + P). No interactive widgets, no filters -
just a snapshot of the current state for board packs and Monday reviews.
"""
from shared import (core_question, inject_css, load_csv, INK, INK_SOFT, MUTED, LINE,
                     BG, BG_SOFT, ACCENT, ACCENT_SOFT, GOLD, WARN)
import pandas as pd
import altair as alt
import streamlit as st
import datetime as _dt

inject_css()

# Print-friendly overrides: hide sidebar + Streamlit chrome when printing,
# force white background, expand any expanders.
st.markdown("""
<style>
  @media print {
    [data-testid="stSidebar"], [data-testid="stHeader"],
    [data-testid="stToolbar"], .stButton, .stDownloadButton {
        display: none !important;
    }
    [data-testid="stApp"] {
        padding: 0 !important;
        background: white !important;
    }
    section.main > div { max-width: 100% !important; padding: 0 !important; }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.1rem !important; margin-top: 1.2rem !important; }
    h3 { font-size: .95rem !important; }
    .print-hide { display: none !important; }
    .kpi, .stat, .card { break-inside: avoid; }
  }
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="eyebrow">GrantsNow &middot; Board pack</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Board pack</h1>', unsafe_allow_html=True)
core_question("What do I take to the board this week?")
st.caption("A one-page snapshot for board reviews. Press Ctrl+P (Cmd+P "
            "on Mac) to save as a PDF. The sidebar and buttons will be "
            "hidden in the printed output.")

# --- Print button (Streamlit has no native print, so we use a tiny JS
# button that calls window.print()) ---
st.markdown(
    f'<button onclick="window.print()" class="print-hide" '
    f'style="padding:.5rem 1rem;border:1px solid {ACCENT};'
    f'background:{ACCENT};color:white;border-radius:6px;'
    f'font-weight:600;cursor:pointer;margin:.4rem 0 1.2rem">'
    f'Print / Save as PDF</button>',
    unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
emails_df   = load_csv("emails.csv")
batches_df  = load_csv("campaign_batches.csv")
contacts_df = load_csv("contacts.csv")
posts_df    = load_csv("posts.csv")

if not contacts_df.empty:
    for c in ("is_send_ready", "is_fresh", "is_verified"):
        if c in contacts_df.columns:
            contacts_df[c] = (contacts_df[c].astype(str)
                                .str.lower().isin(["true", "1", "yes"]))

if not emails_df.empty and "week_start" in emails_df.columns:
    emails_df["week_start"] = pd.to_datetime(
        emails_df["week_start"], errors="coerce")


# --------------------------------------------------------------------------
# Section 1 - The one-paragraph brief
# --------------------------------------------------------------------------
st.markdown('<h2>Where we are</h2>', unsafe_allow_html=True)

def _brief():
    parts = []
    if not emails_df.empty:
        dated = emails_df.dropna(subset=["week_start"]).sort_values(
            "week_start", ascending=False)
        if len(dated) >= 1:
            r = dated.iloc[0]
            open_pct = float(r.get("open_rate", 0) or 0) * 100
            parts.append(
                f"Last email send ({r.get('week_label','')}) went to "
                f"<strong>{int(r.get('contacts',0) or 0):,}</strong> "
                f"contacts and opened at "
                f"<strong>{open_pct:.0f}%</strong> "
                f"({'meeting' if open_pct >= 20 else 'below'} the "
                f"20% benchmark).")
        with_rate = emails_df.dropna(subset=["open_rate", "week_label"])
        if len(with_rate) >= 2:
            best  = with_rate.loc[with_rate["open_rate"].idxmax()]
            worst = with_rate.loc[with_rate["open_rate"].idxmin()]
            parts.append(
                f"Best week: <strong>{best['week_label']}</strong> "
                f"({float(best['open_rate'])*100:.0f}%). Worst: "
                f"<strong>{worst['week_label']}</strong> "
                f"({float(worst['open_rate'])*100:.0f}%).")
    if not contacts_df.empty:
        ready = int((contacts_df["is_send_ready"]
                      & contacts_df["is_fresh"]
                      & contacts_df["is_verified"]).sum())
        total = len(contacts_df)
        unverified = int((~contacts_df["is_verified"]).sum())
        parts.append(
            f"List reach: <strong>{ready:,}</strong> of "
            f"{total:,} contacts are actionable today. "
            f"<strong>{unverified:,}</strong> are in the verify "
            f"queue.")
    if not batches_df.empty:
        agg = (batches_df.groupby(["batch_id", "batch_name"])
                .apply(lambda g: (g["opened"].sum()
                                    / max(g["delivered"].sum(), 1)))
                .reset_index(name="open"))
        top = agg.loc[agg["open"].idxmax()]
        parts.append(
            f"Best tracked campaign: "
            f"<strong>{top['batch_name']}</strong> at "
            f"{float(top['open'])*100:.0f}% open across the "
            f"sequence.")
    return " ".join(parts) if parts else \
        "Not enough data loaded to build the brief."

st.markdown(
    f'<div style="background:{BG_SOFT};border:1px solid {LINE};'
    f'border-left:5px solid {ACCENT};border-radius:6px;'
    f'padding:1.2rem 1.4rem;font-size:1rem;line-height:1.65;'
    f'color:{INK}">{_brief()}</div>',
    unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Section 2 - The headline numbers
# --------------------------------------------------------------------------
st.markdown('<h2>The headline numbers</h2>', unsafe_allow_html=True)


def _tile(col, label, value, sub, colour):
    with col:
        st.markdown(
            f'<div class="kpi" style="border-top:4px solid {colour}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="color:{colour}">{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>',
            unsafe_allow_html=True)


hcols = st.columns(4)

# Tile 1 - latest open rate
if not emails_df.empty:
    dated = emails_df.dropna(subset=["week_start"]).sort_values(
        "week_start", ascending=False)
    if len(dated) >= 1:
        v = float(dated.iloc[0].get("open_rate", 0) or 0) * 100
        col = ACCENT if v >= 20 else GOLD
        _tile(hcols[0], "Latest open rate", f"{v:.0f}%",
                f"vs 20% benchmark", col)

# Tile 2 - reachable pool
if not contacts_df.empty:
    ready = int((contacts_df["is_send_ready"]
                  & contacts_df["is_fresh"]
                  & contacts_df["is_verified"]).sum())
    total = len(contacts_df)
    pct = ready / max(total, 1) * 100
    col = ACCENT if pct >= 30 else GOLD
    _tile(hcols[1], "Reachable now", f"{ready:,}",
            f"of {total:,} total ({pct:.0f}%)", col)

# Tile 3 - verify queue
if not contacts_df.empty:
    unv = int((~contacts_df["is_verified"]).sum())
    col = WARN if unv >= 1000 else GOLD if unv >= 200 else ACCENT
    _tile(hcols[2], "Verify queue", f"{unv:,}",
            "unlock these to grow reach", col)

# Tile 4 - best tracked batch
if not batches_df.empty:
    agg = (batches_df.groupby(["batch_id", "batch_name"])
            .apply(lambda g: (g["opened"].sum()
                                / max(g["delivered"].sum(), 1)))
            .reset_index(name="open"))
    top = agg.loc[agg["open"].idxmax()]
    v = float(top["open"]) * 100
    col = ACCENT if v >= 20 else GOLD
    _tile(hcols[3], "Best campaign",
            f"{v:.0f}%",
            str(top["batch_name"])[:38], col)


# --------------------------------------------------------------------------
# Section 3 - Open-rate trend
# --------------------------------------------------------------------------
if not emails_df.empty:
    st.markdown('<h2>Open rate trend</h2>', unsafe_allow_html=True)
    trend = emails_df.dropna(subset=["week_start", "open_rate"]) \
        .sort_values("week_start")
    if len(trend) >= 3:
        line = alt.Chart(trend).mark_line(
            color=ACCENT, strokeWidth=3, point=alt.OverlayMarkDef(
                color=ACCENT, size=60)).encode(
            x=alt.X("week_start:T", title=None),
            y=alt.Y("open_rate:Q",
                      title="Open rate",
                      axis=alt.Axis(format=".0%")))
        bench = alt.Chart(pd.DataFrame({"y": [0.20]})).mark_rule(
            color=MUTED, strokeDash=[4, 4]).encode(y="y:Q")
        st.altair_chart((line + bench).properties(height=240),
                         width='stretch')


# --------------------------------------------------------------------------
# Section 4 - Cross-batch leaderboard
# --------------------------------------------------------------------------
if not batches_df.empty:
    st.markdown('<h2>Tracked campaign leaderboard</h2>',
                 unsafe_allow_html=True)
    dfb = batches_df.copy()
    lead = (dfb.groupby(["batch_id", "batch_name"])
             .agg(sent=("sent", "sum"),
                   delivered=("delivered", "sum"),
                   opened=("opened", "sum"),
                   stages=("stage", "count"))
             .reset_index())
    lead["open_rate"] = lead["opened"] / lead["delivered"].replace(0, 1) \
        * 100
    lead = lead.sort_values("open_rate", ascending=False)
    rows = []
    for _, r in lead.iterrows():
        c = ACCENT if r["open_rate"] >= 20 else GOLD
        rows.append(
            f'<div style="display:grid;grid-template-columns:'
            f'3fr .8fr .8fr .8fr;gap:.5rem;padding:.5rem .8rem;'
            f'font-size:.9rem;border-bottom:1px solid {LINE}">'
            f'<div style="color:{INK};font-weight:600">'
            f'{r["batch_name"]}</div>'
            f'<div style="color:{INK_SOFT}">{int(r["stages"])} emails'
            f'</div>'
            f'<div style="color:{INK_SOFT}">'
            f'{int(r["sent"])} sent</div>'
            f'<div style="color:{c};font-weight:700">'
            f'{r["open_rate"]:.0f}% open</div>'
            f'</div>')
    header = (
        f'<div style="display:grid;grid-template-columns:'
        f'3fr .8fr .8fr .8fr;gap:.5rem;padding:.4rem .8rem;'
        f'font-size:.7rem;text-transform:uppercase;letter-spacing:.12em;'
        f'color:{MUTED};font-weight:600;border-bottom:1px solid {LINE}">'
        f'<div>Campaign</div><div>Stages</div><div>Total sent</div>'
        f'<div>Open rate</div></div>')
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:6px;'
        f'background:{BG}">{header}{"".join(rows)}</div>',
        unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Section 5 - Interest pipeline
# --------------------------------------------------------------------------
if not emails_df.empty and "interested_companies_count" in emails_df.columns:
    intents = emails_df.dropna(subset=["interested_companies_count"])
    intents = intents[intents["interested_companies_count"] > 0]
    if not intents.empty:
        st.markdown('<h2>Interest pipeline</h2>', unsafe_allow_html=True)
        total_intent = int(intents["interested_companies_count"].sum())
        n_weeks = len(intents)
        avg = total_intent / max(n_weeks, 1)
        st.markdown(
            f'<div style="font-size:.95rem;line-height:1.6;color:{INK}">'
            f'<strong>{total_intent}</strong> university-level '
            f'&lsquo;most interested&rsquo; flags across '
            f'<strong>{n_weeks}</strong> active weeks. Average '
            f'<strong>{avg:.1f}</strong> per active week. '
            f'This is the closest signal we have to pipeline heat '
            f'from the email programme.'
            f'</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Section 6 - Next actions
# --------------------------------------------------------------------------
st.markdown('<h2>Next actions</h2>', unsafe_allow_html=True)
actions = []
if not contacts_df.empty:
    unv = int((~contacts_df["is_verified"]).sum())
    if unv >= 100:
        actions.append(f"Verify the {unv:,} unverified contacts to "
                        f"grow the reachable pool.")
if not emails_df.empty:
    dated = emails_df.dropna(subset=["week_start"]).sort_values(
        "week_start", ascending=False)
    if len(dated) >= 1:
        v = float(dated.iloc[0].get("open_rate", 0) or 0) * 100
        if v < 15:
            actions.append("Rewrite the subject line on the next send "
                            f"- last week opened at {v:.0f}%.")
if not batches_df.empty:
    base_rows = batches_df[batches_df["stage"] == "Base"].copy()
    if not base_rows.empty:
        base_rows["op"] = base_rows["opened"] / \
            base_rows["delivered"].replace(0, 1)
        w = base_rows.loc[base_rows["op"].idxmin()]
        if float(w["op"]) < 0.10:
            actions.append(
                f"Do NOT repeat the &lsquo;{w['batch_name']}&rsquo; "
                f"pattern - it opened at {float(w['op'])*100:.0f}%.")

if not actions:
    st.markdown(
        f'<div style="color:{INK_SOFT};font-size:.95rem">'
        f'Nothing urgent. Keep the current cadence.</div>',
        unsafe_allow_html=True)
else:
    for a in actions:
        st.markdown(
            f'<div style="border-left:3px solid {ACCENT};'
            f'padding:.5rem 1rem;margin:.4rem 0;background:{BG_SOFT};'
            f'font-size:.95rem;line-height:1.5">{a}</div>',
            unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Footer - snapshot timestamp
# --------------------------------------------------------------------------
st.markdown(
    f'<div style="margin-top:2.5rem;padding-top:1rem;'
    f'border-top:1px solid {LINE};color:{MUTED};font-size:.75rem">'
    f'Snapshot generated {_dt.datetime.now().strftime("%d %b %Y at %H:%M")}. '
    f'Data pulled live from the ETL outputs in /data.'
    f'</div>', unsafe_allow_html=True)
