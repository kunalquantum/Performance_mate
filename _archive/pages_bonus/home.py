"""
Home - the first thing the sales director sees. Three plain-English
summary cards that answer "what's the state of play" without them
having to touch a filter or read a chart.
"""
from shared import (core_question, inject_css, render_status_key, onboarding_banner,
                     load_csv, INK, INK_SOFT, MUTED, LINE, BG, BG_SOFT,
                     ACCENT, GOLD, WARN)
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Overview</h1>', unsafe_allow_html=True)
core_question("What is happening across LinkedIn and Email right now, and where should attention go this week?")
st.caption("Everything happening across LinkedIn and Email at a glance. "
            "Green means we are on track, gold means look closer.")
render_status_key()
onboarding_banner()


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
emails_df   = load_csv("emails.csv")
batches_df  = load_csv("campaign_batches.csv")
posts_df    = load_csv("posts.csv")
contacts_df = load_csv("contacts.csv")

# Coerce contacts booleans
if not contacts_df.empty:
    for c in ("is_send_ready", "is_fresh", "is_verified"):
        if c in contacts_df.columns:
            contacts_df[c] = (contacts_df[c].astype(str)
                                .str.lower().isin(["true", "1", "yes"]))

# Emails week_start
if not emails_df.empty and "week_start" in emails_df.columns:
    emails_df["week_start"] = pd.to_datetime(
        emails_df["week_start"], errors="coerce")


# --------------------------------------------------------------------------
# Card builders
# --------------------------------------------------------------------------
def _card(title, big, colour, sub, action_label, action_target,
            explain):
    """Render one summary card. action_target is the page slug used by
    st.switch_page (relative path from repo root)."""
    st.markdown(
        f'<div style="border:1px solid {LINE};border-top:5px solid '
        f'{colour};border-radius:8px;padding:1.4rem 1.5rem;background:{BG};'
        f'height:100%">'
        f'<div class="eyebrow" style="margin-bottom:.4rem">{title}</div>'
        f'<div style="font-size:2rem;font-weight:700;color:{INK};'
        f'letter-spacing:-0.02em;line-height:1.1;margin-bottom:.3rem">'
        f'{big}</div>'
        f'<div style="font-size:.9rem;color:{INK_SOFT};margin-bottom:.7rem;'
        f'line-height:1.4">{sub}</div>'
        f'<div style="font-size:.78rem;color:{MUTED};line-height:1.4">'
        f'{explain}</div>'
        f'</div>', unsafe_allow_html=True)
    if action_label and action_target:
        if st.button(action_label, key=f"btn_{title}",
                       use_container_width=True):
            st.switch_page(action_target)


# --------------------------------------------------------------------------
# Card 1: How the last email send went
# --------------------------------------------------------------------------
def _card_email_last_send():
    if emails_df.empty:
        return ("How the last email send went", "-", MUTED,
                "No email data loaded.",
                "Open Email numbers", "pages/email_performance.py",
                "Run python etl/email_etl.py to populate this.")
    latest = emails_df.dropna(subset=["week_start"]).sort_values(
        "week_start", ascending=False).head(1)
    if latest.empty:
        return ("How the last email send went", "-", MUTED,
                "No dated weeks in the data.", None, None, "")
    r = latest.iloc[0]
    open_rate = r.get("open_rate")
    if pd.isna(open_rate):
        open_rate = 0
    open_pct = float(open_rate) * 100
    contacts = int(r.get("contacts", 0) or 0)
    week_lbl = str(r.get("week_label", ""))
    # Colour rule: >= 20% green, else gold
    colour = ACCENT if open_pct >= 20 else GOLD
    verdict = ("meeting the 20% benchmark" if open_pct >= 20
                else "below the 20% benchmark")
    sub = (f"Latest send ({week_lbl}) went to {contacts:,} contacts and "
            f"opened at {open_pct:.0f}% - {verdict}.")
    explain = "The 20% number is the SaaS industry average open rate."
    return ("How the last email send went",
             f"{open_pct:.0f}% open",
             colour, sub,
             "See email numbers", "pages/email_performance.py",
             explain)


# --------------------------------------------------------------------------
# Card 2: Who we can reach right now
# --------------------------------------------------------------------------
def _card_reach():
    if contacts_df.empty:
        return ("Who we can reach", "-", MUTED,
                "No contacts loaded.",
                "Open audience", "pages/email_audience.py",
                "Run python etl/contacts_etl.py to populate this.")
    total = len(contacts_df)
    ready = int((contacts_df["is_send_ready"]
                  & contacts_df["is_fresh"]
                  & contacts_df["is_verified"]).sum())
    reachable_pct = ready / max(total, 1) * 100
    verify_queue = int((~contacts_df["is_verified"]).sum())
    colour = ACCENT if reachable_pct >= 30 else GOLD
    sub = (f"{ready:,} contacts are send-ready, verified and fresh - "
            f"out of {total:,} total. That is {reachable_pct:.0f}% of "
            f"the list.")
    explain = (f"{verify_queue:,} more contacts are sitting in the verify "
                f"queue. Clearing them would grow the reachable list.")
    return ("Who we can reach right now",
             f"{ready:,} contacts",
             colour, sub,
             "Build the next send", "pages/email_audience.py",
             explain)


# --------------------------------------------------------------------------
# Card 3: Best-performing tracked batch (real per-email numbers)
# --------------------------------------------------------------------------
def _card_best_batch():
    if batches_df.empty:
        return ("Best-performing tracked batch", "-", MUTED,
                "No tracked batches yet.",
                "Compare sequences", "pages/email_sequence.py",
                "Add rows to data/campaign_batches.csv to track a send.")
    dfb = batches_df.copy()
    dfb["open_rate"] = dfb["opened"] / dfb["delivered"].replace(0, 1)
    # Aggregate by batch: average open rate across stages, weighted by sent
    agg = (dfb.groupby(["batch_id", "batch_name"])
           .apply(lambda g: (g["opened"].sum() /
                              max(g["delivered"].sum(), 1)))
           .reset_index(name="agg_open"))
    agg = agg.sort_values("agg_open", ascending=False)
    top = agg.iloc[0]
    open_pct = float(top["agg_open"]) * 100
    name = str(top["batch_name"])
    colour = ACCENT if open_pct >= 20 else GOLD
    sub = (f"{name} opened at {open_pct:.0f}% across its full sequence. "
            f"That is our best tracked campaign so far.")
    n_batches = len(agg)
    worst = agg.iloc[-1]
    worst_pct = float(worst["agg_open"]) * 100
    explain = (f"Comparing {n_batches} tracked batches. Worst so far: "
                f"{str(worst['batch_name'])[:40]} at {worst_pct:.0f}%.")
    return ("Best-performing tracked campaign",
             f"{open_pct:.0f}% open",
             colour, sub,
             "Compare sequences", "pages/email_sequence.py",
             explain)


# --------------------------------------------------------------------------
# Render the three cards in a row
# --------------------------------------------------------------------------
cards = [_card_email_last_send(), _card_reach(), _card_best_batch()]
cols = st.columns(3, gap="medium")
for col, (title, big, colour, sub, action_label, action_target,
            explain) in zip(cols, cards):
    with col:
        _card(title, big, colour, sub, action_label, action_target,
                explain)


# --------------------------------------------------------------------------
# Weekly briefing - auto-written paragraph reading the current state
# --------------------------------------------------------------------------
st.markdown('<div style="margin:2.5rem 0 1rem;border-top:1px solid '
             + LINE + '"></div>', unsafe_allow_html=True)
st.markdown('<h2>This week&apos;s brief</h2>', unsafe_allow_html=True)
st.caption("Auto-generated read-out of the current state. Refreshes on "
            "every visit.")


def _write_brief():
    parts = []

    # ---- Email latest send ----
    if not emails_df.empty:
        dated = emails_df.dropna(subset=["week_start"]).sort_values(
            "week_start", ascending=False)
        if len(dated) >= 1:
            latest = dated.iloc[0]
            prev = dated.iloc[1] if len(dated) >= 2 else None
            latest_open = float(latest.get("open_rate", 0) or 0) * 100
            latest_contacts = int(latest.get("contacts", 0) or 0)
            latest_wk = str(latest.get("week_label", ""))
            piece = (f"Latest email send ({latest_wk}) went to "
                      f"<strong>{latest_contacts:,}</strong> contacts and "
                      f"opened at <strong>{latest_open:.0f}%</strong>. ")
            if prev is not None:
                prev_open = float(prev.get("open_rate", 0) or 0) * 100
                delta = latest_open - prev_open
                dir_word = "up" if delta > 0 else ("down" if delta < 0
                                                     else "flat vs")
                piece += (f"That is {abs(delta):.0f} points "
                            f"{dir_word} the week before "
                            f"({prev_open:.0f}%). ")
            if latest_open < 20:
                piece += ("Below the 20% industry benchmark - worth a "
                            "look. ")
            else:
                piece += "Meeting the 20% industry benchmark. "
            parts.append(piece)

        # Best / worst send in the whole window
        with_rate = emails_df.dropna(subset=["open_rate", "week_label"])
        if len(with_rate) >= 2:
            best = with_rate.loc[with_rate["open_rate"].idxmax()]
            worst = with_rate.loc[with_rate["open_rate"].idxmin()]
            parts.append(
                f"Best send so far: <strong>{best['week_label']}</strong> "
                f"at {float(best['open_rate'])*100:.0f}% open. Worst: "
                f"<strong>{worst['week_label']}</strong> at "
                f"{float(worst['open_rate'])*100:.0f}%. ")

    # ---- Verify queue nudge ----
    if not contacts_df.empty:
        ready = int((contacts_df["is_send_ready"]
                      & contacts_df["is_fresh"]
                      & contacts_df["is_verified"]).sum())
        unverified = int((~contacts_df["is_verified"]).sum())
        total = len(contacts_df)
        parts.append(
            f"You can reach <strong>{ready:,}</strong> people right now "
            f"out of {total:,}. Clearing the verify queue would "
            f"unlock <strong>{unverified:,}</strong> more contacts. ")

    # ---- Best tracked batch ----
    if not batches_df.empty:
        dfb = batches_df.copy()
        agg = (dfb.groupby(["batch_id", "batch_name"])
                .apply(lambda g: (g["opened"].sum()
                                    / max(g["delivered"].sum(), 1)))
                .reset_index(name="agg_open"))
        agg = agg.sort_values("agg_open", ascending=False)
        top = agg.iloc[0]
        top_pct = float(top["agg_open"]) * 100
        parts.append(
            f"Best tracked campaign: <strong>{top['batch_name']}</strong> "
            f"at {top_pct:.0f}% open across the sequence. ")

    # ---- Next-action pointer ----
    action_bits = []
    if not contacts_df.empty:
        unverified = int((~contacts_df["is_verified"]).sum())
        if unverified > 0:
            action_bits.append(
                f"verify the {unverified:,} unverified contacts")
    if not emails_df.empty:
        try:
            recent_open = float(
                emails_df.dropna(subset=["week_start"])
                .sort_values("week_start", ascending=False)
                .iloc[0].get("open_rate", 0) or 0) * 100
            if recent_open < 15:
                action_bits.append(
                    "review the subject line on the next send - open "
                    "rate has been low")
        except Exception:
            pass
    if not batches_df.empty:
        # Look for a stage-1 (Base) that scored poorly across batches
        base_rows = batches_df[batches_df["stage"] == "Base"].copy()
        if not base_rows.empty:
            base_rows["op"] = base_rows["opened"] / \
                base_rows["delivered"].replace(0, 1)
            weakest = base_rows.loc[base_rows["op"].idxmin()]
            if float(weakest["op"]) < 0.10:
                action_bits.append(
                    f"do not repeat the "
                    f"&lsquo;{weakest['batch_name']}&rsquo; pattern - "
                    "it opened below 10%")
    if action_bits:
        parts.append("Next actions: " + "; ".join(action_bits) + ".")

    if not parts:
        return ("Not enough data yet to build a brief. Once the ETLs "
                "have run, this box fills in automatically.")
    return " ".join(parts)


st.markdown(
    f'<div style="background:{BG_SOFT};border:1px solid {LINE};'
    f'border-left:5px solid {ACCENT};border-radius:6px;'
    f'padding:1.2rem 1.4rem;font-size:.98rem;line-height:1.6;'
    f'color:{INK}">{_write_brief()}</div>',
    unsafe_allow_html=True)


# --------------------------------------------------------------------------
# This week's actions - rule-based to-do list with checkboxes
# --------------------------------------------------------------------------
st.markdown('<div style="margin:2rem 0 1rem"></div>',
             unsafe_allow_html=True)
st.markdown('<h2>This week&apos;s actions</h2>', unsafe_allow_html=True)
st.caption("Specific next steps derived from the current data. Tick "
            "off as you go - state carries through the session.")


def _build_actions():
    """Rule-based action items. Each is a dict with an id (stable),
    label, and detail note."""
    items = []

    # Rule: clear the verify queue
    if not contacts_df.empty:
        unverified = int((~contacts_df["is_verified"]).sum())
        if unverified >= 100:
            items.append({
                "id": "verify_queue",
                "label": f"Verify the {unverified:,} unverified contacts",
                "detail": (f"That is {unverified/max(len(contacts_df),1)*100:.0f}% "
                            f"of your total list. Handing them to a "
                            f"verification tool would grow the reachable "
                            f"pool by the same share."),
                "urgency": "high" if unverified >= 500 else "medium",
            })

    # Rule: low recent open rate -> subject line review
    if not emails_df.empty:
        try:
            dated = emails_df.dropna(subset=["week_start"]).sort_values(
                "week_start", ascending=False)
            if len(dated) >= 1:
                latest_open = float(
                    dated.iloc[0].get("open_rate", 0) or 0) * 100
                if latest_open < 15:
                    items.append({
                        "id": "subject_review",
                        "label": ("Rewrite the subject line for the "
                                    "next email send"),
                        "detail": (f"Latest week opened at "
                                    f"{latest_open:.0f}% - well below "
                                    f"the 20% benchmark. A pain-named "
                                    f"subject usually lifts open rate "
                                    f"more than any other change."),
                        "urgency": "high",
                    })
        except Exception:
            pass

    # Rule: batch with sub-10% open -> mark as pattern to avoid
    if not batches_df.empty:
        base_rows = batches_df[batches_df["stage"] == "Base"].copy()
        if not base_rows.empty:
            base_rows["op"] = (base_rows["opened"]
                                / base_rows["delivered"].replace(0, 1))
            weakest = base_rows.loc[base_rows["op"].idxmin()]
            if float(weakest["op"]) < 0.10:
                items.append({
                    "id": "avoid_bad_pattern",
                    "label": (f"Do NOT repeat the "
                                f"&lsquo;{weakest['batch_name']}&rsquo; "
                                f"pattern"),
                    "detail": (f"That base email opened at "
                                f"{float(weakest['op'])*100:.0f}% - "
                                f"below the 10% floor. Likely a "
                                f"copy-audience mismatch (check "
                                f"geography or list source)."),
                    "urgency": "medium",
                })

    # Rule: interested-companies present -> follow up
    if not emails_df.empty and \
            "interested_companies_count" in emails_df.columns:
        try:
            recent = emails_df.dropna(subset=["week_start"]).sort_values(
                "week_start", ascending=False).head(4)
            recent_intent = int(
                recent["interested_companies_count"].fillna(0).sum())
            if recent_intent >= 5:
                items.append({
                    "id": "follow_intent",
                    "label": (f"Follow up individually with the "
                                f"{recent_intent} interested "
                                f"universities from the last 4 weeks"),
                    "detail": ("Cognism flagged these as most "
                                "interested. Personalised outreach on "
                                "warm leads converts far higher than a "
                                "cold blast."),
                    "urgency": "high",
                })
        except Exception:
            pass

    # Rule: WP5 zone empty -> template retrofit
    if not batches_df.empty:
        # Use a simple check: any base with subject naming a pain word
        pain_words = ("overcoming", "manual", "delay", "missing",
                       "burden", "reduce")
        has_wp5 = any(
            any(w in str(r.get("subject", "")).lower() for w in pain_words)
            for _, r in batches_df.iterrows())
        if not has_wp5:
            items.append({
                "id": "wp5_template",
                "label": ("Rewrite one email using the WP5 "
                            "&lsquo;overcoming...&rsquo; template"),
                "detail": ("No current campaign uses a pain-named "
                            "subject. WP5 is our reference for the "
                            "pattern that works - copy its structure "
                            "into the next draft."),
                "urgency": "medium",
            })

    # Rule: reachable pool tiny -> segment expansion
    if not contacts_df.empty:
        ready = int((contacts_df["is_send_ready"]
                      & contacts_df["is_fresh"]
                      & contacts_df["is_verified"]).sum())
        if ready < 500:
            items.append({
                "id": "reachable_low",
                "label": (f"Only {ready:,} contacts reachable right "
                            f"now - expand the segment"),
                "detail": ("Once the actionable pool drops below 500, "
                            "your next-send options narrow fast. Widen "
                            "persona filters on the Audience page or "
                            "clear more verify-queue contacts."),
                "urgency": "medium" if ready >= 200 else "high",
            })

    return items[:5]  # cap at 5 to keep the surface honest


actions = _build_actions()

if not actions:
    st.markdown(
        f'<div style="background:#EBF3F2;border:1px solid '
        f'{ACCENT_SOFT};border-left:5px solid {ACCENT};'
        f'border-radius:6px;padding:1rem 1.3rem;'
        f'color:{INK_SOFT};font-size:.92rem">'
        f'Nothing urgent from the current data. All benchmarks met, '
        f'no obvious gaps. Keep the current cadence.'
        f'</div>', unsafe_allow_html=True)
else:
    for i, item in enumerate(actions):
        state_key = f"action_done_{item['id']}"
        if state_key not in st.session_state:
            st.session_state[state_key] = False
        done = st.session_state[state_key]
        urgency_color = {"high": WARN, "medium": GOLD,
                           "low": ACCENT}.get(item["urgency"], ACCENT)
        opacity = "0.55" if done else "1"
        strike = ("text-decoration:line-through;color:" + MUTED
                    if done else "color:" + INK)
        st.markdown(
            f'<div style="border:1px solid {LINE};border-left:4px solid '
            f'{urgency_color};border-radius:6px;padding:.7rem 1rem;'
            f'margin:.4rem 0;background:{BG};opacity:{opacity}">'
            f'<div style="{strike};font-weight:600;font-size:.95rem;'
            f'line-height:1.4">{item["label"]}</div>'
            f'<div style="color:{MUTED};font-size:.82rem;'
            f'margin-top:.2rem;line-height:1.5">{item["detail"]}</div>'
            f'</div>', unsafe_allow_html=True)
        c1, _ = st.columns([1, 6])
        with c1:
            btn_label = "Undo" if done else "Mark done"
            if st.button(btn_label, key=f"btn_{state_key}"):
                st.session_state[state_key] = not done
                st.rerun()


# --------------------------------------------------------------------------
# Second row - quick pointers to the deeper apps
# --------------------------------------------------------------------------
st.markdown('<div style="margin:2.5rem 0 1rem;border-top:1px solid '
             + LINE + '"></div>', unsafe_allow_html=True)
st.markdown('<h2>Jump into the detail</h2>', unsafe_allow_html=True)
st.caption("Two apps on the left: LinkedIn Post Performance and Email "
            "Performance. Each app has three or four screens. Pick the "
            "one that matches the question you have.")

qc1, qc2 = st.columns(2, gap="medium")
with qc1:
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:8px;'
        f'padding:1.2rem 1.4rem;background:{BG}">'
        f'<div class="eyebrow" style="color:{ACCENT}">LinkedIn</div>'
        f'<div style="font-size:1.1rem;font-weight:600;color:{INK};'
        f'margin:.4rem 0 .8rem">Post Performance Matrix</div>'
        f'<div style="font-size:.88rem;color:{INK_SOFT};line-height:1.5">'
        f'<strong>What worked</strong> - every post as a dot, click one to '
        f'compare against the top performer.<br>'
        f'<strong>See the pattern</strong> - what wins on writing, image, '
        f'day of week, hashtag choice.<br>'
        f'<strong>Draft the next post</strong> - predict the score of a '
        f'new draft before it goes live.'
        f'</div></div>', unsafe_allow_html=True)
with qc2:
    st.markdown(
        f'<div style="border:1px solid {LINE};border-radius:8px;'
        f'padding:1.2rem 1.4rem;background:{BG}">'
        f'<div class="eyebrow" style="color:{ACCENT}">Email</div>'
        f'<div style="font-size:1.1rem;font-weight:600;color:{INK};'
        f'margin:.4rem 0 .8rem">Email Performance Matrix</div>'
        f'<div style="font-size:.88rem;color:{INK_SOFT};line-height:1.5">'
        f'<strong>This week&apos;s numbers</strong> - opens, clicks, replies, '
        f'trends and industry benchmarks.<br>'
        f'<strong>Who we can reach</strong> - the 4,400-contact list, who '
        f'is ready to send to, who needs verifying.<br>'
        f'<strong>Grade our copy</strong> - every marketing-calendar '
        f'email scored against the GrantsNow pattern (WP5 template).<br>'
        f'<strong>Compare sequences</strong> - base and follow-ups side '
        f'by side, with real funnel numbers per email.'
        f'</div></div>', unsafe_allow_html=True)
