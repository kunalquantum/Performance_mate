"""
Email Performance Matrix - Contents analysis screen.
"""
from shared import (inject_css, load_csv, DATA_DIR, SOURCES_DIR, INK,
                     INK_SOFT, MUTED, LINE, BG, BG_SOFT, ACCENT,
                     ACCENT_SOFT, WARN, GOLD)
import os, re
import altair as alt
import pandas as pd
import streamlit as st

inject_css()

st.markdown('<div class="eyebrow">GrantsNow &middot; Email</div>',
            unsafe_allow_html=True)
st.markdown('<h1>Contents Analysis</h1>', unsafe_allow_html=True)

emails_all = load_csv("emails.csv")
if not emails_all.empty:
    emails_all["week_start"] = pd.to_datetime(emails_all["week_start"],
                                                errors="coerce")

# =============== CONTENTS ANALYSIS ===============
# Reads the Email Campaign sheet (parsed by campaign_etl.py) and
# scores every base email + follow-up on the house pattern axes:
# SaaS vocabulary coverage, weak-phrase count, seven-slot alignment,
# persona fit vs the dominant blast persona (Research), readability.
st.markdown('<h2>Contents analysis</h2>', unsafe_allow_html=True)
st.caption("Every live campaign from the Marketing Calendar, scored "
           "against the house pattern. Pick a campaign to see the "
           "detail; scroll for gaps and next-content ideas.")

campaigns_df = load_csv("campaigns.csv")
if campaigns_df.empty:
    st.info("No campaigns loaded. Run `python etl/campaign_etl.py` to "
            "build data/campaigns.csv from the Marketing Calendar.")
else:
    # ---- House vocabulary + rules (shared with Compose block) ----
    SAAS_VOCAB_CA = {
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
    WEAK_SWAPS_CA = {
        "utilise": "use", "utilize": "use",
        "leverage": "use", "streamline": "simplify",
        "solution": "platform", "synergy": "alignment",
        "in order to": "to", "at the end of the day": "the point is",
        "a lot of": "several",
    }
    RESEARCH_TERMS = [
        "research", "grant", "grants", "funding", "arma", "ncura",
        "ukri", "horizon", "ref", "principal investigator", "pi",
        "pre-award", "post-award", "co-investigator", "proposal",
        "university", "college", "institution",
    ]
    FINANCE_TERMS = [
        "erp", "finance", "reconcile", "reporting", "audit",
        "compliance", "cost", "budget", "forecast",
    ]
    IT_TERMS = [
        "integration", "api", "system", "systems", "sso",
        "single source", "data", "platform",
    ]

    # ---- House pattern per Email_WP5 reference ----
    # Challenge signals (what pain the reader has, who wants what,
    # problem-cost chain). Result signals (named customers by name,
    # concrete numbers, single CTA after an outcome close line).
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
    DEMAND_VERBS = ["want", "need", "expect", "require", "ask for",
                      "demand"]
    PROBLEM_CONNECTIVES = [" because ", ", so ", " while ",
                             " but ", " however ", " which means ",
                             " so that "]
    OUTCOME_TERMS = [
        "single source of truth", "one platform", "one place",
        "one system", "single view", "end to end", "visibility",
        "accurate forecasting", "less risk", "reduce risk",
        "reduce cost", "reduce administration", "save time",
    ]
    CTA_PHRASES = [
        "read the whitepaper", "read the white paper",
        "download the whitepaper", "book a call", "book a demo",
        "get in touch", "reply to this email", "register",
        "come by our", "meet our team", "learn more",
    ]

    def _analyse(subject, body):
        text = f"{subject}\n{body}"
        lo = text.lower()
        subj_lo = subject.lower()

        # ---- Vocabulary + weak phrases (shared) ----
        vocab = {}
        for g, terms in SAAS_VOCAB_CA.items():
            hits = [t for t in terms if t in lo]
            vocab[g] = {"hits": hits, "count": len(hits),
                         "total": len(terms)}
        weak = [(w, s) for w, s in WEAK_SWAPS_CA.items() if w in lo]

        # ---- Words / sentences / readability ----
        words = re.findall(r"[a-zA-Z]+", body)
        sents = [s for s in re.split(r"[.!?]+", body) if s.strip()]
        syl = 0
        for w in words:
            syl += max(1, len(re.findall(r"[aeiouy]+", w.lower())))
        fk = None
        if words and sents:
            fk = round(0.39 * (len(words) / len(sents))
                        + 11.8 * (syl / len(words)) - 15.59, 1)

        # ---- Persona fit ----
        total_words = max(len(words), 1)
        persona_fit = {
            "Research":
                sum(lo.count(t) for t in RESEARCH_TERMS) / total_words,
            "Finance":
                sum(lo.count(t) for t in FINANCE_TERMS) / total_words,
            "IT-Systems":
                sum(lo.count(t) for t in IT_TERMS) / total_words,
        }

        # ---- CHALLENGE signals (slots 1, 3, 4) ----
        # Slot 1: pain-named subject (not product-named)
        subj_has_challenge = any(w in subj_lo
                                    for w in CHALLENGE_SUBJECT_WORDS)
        subj_is_product_only = (subj_lo.strip().startswith("visit ")
            or subj_lo.strip() in ("grantsnow", "about grantsnow"))
        slot_pain_subject = (bool(subject.strip())
                                and subj_has_challenge
                                and not subj_is_product_only)
        # Slot 3: stakeholder-demand line
        has_stakeholder = any(t in lo for t in STAKEHOLDER_TERMS)
        has_demand_verb = any(v in lo for v in DEMAND_VERBS)
        slot_stakeholder = has_stakeholder and has_demand_verb
        # Slot 4: problem-cost chain (2+ connectives OR 3+ sentences
        # that read as problem descriptions in first half of body)
        connective_hits = sum(lo.count(c)
                                for c in PROBLEM_CONNECTIVES)
        slot_problem_chain = connective_hits >= 2

        # ---- RESULT signals (slots 5, 6, 7) ----
        # Slot 5: named specific customer institutions
        named_customers = re.findall(
            r"(University of [A-Z][A-Za-z ]+|"
            r"Institute of [A-Z][A-Za-z ]+|"
            r"[A-Z][A-Za-z]+ (?:College|University|Institute)"
            r"(?: of [A-Z][A-Za-z ]+)?)",
            body)
        # dedupe
        named_customers = list(dict.fromkeys(
            [n.strip() for n in named_customers]))
        slot_named_proof = len(named_customers) >= 1
        # Slot 6: concrete numeric result (percentage or Nx factor)
        pct_hits = re.findall(r"\b\d{1,3}\s*%", body)
        slot_numbers = len(pct_hits) >= 1
        # Slot 7: single CTA - at least one recognised call-to-action
        cta_hits = [c for c in CTA_PHRASES if c in lo]
        slot_single_cta = len(cta_hits) >= 1

        # Slot 2: personal greeting (hygiene)
        slot_greeting = bool(re.match(
            r"^\s*(hi|hello|dear|good (morning|afternoon))",
            body, flags=re.IGNORECASE))

        slots = {
            "1. Pain-named subject": slot_pain_subject,
            "2. Personal greeting": slot_greeting,
            "3. Stakeholder-demand line": slot_stakeholder,
            "4. Problem-cost chain": slot_problem_chain,
            "5. Named customer proof": slot_named_proof,
            "6. Concrete numbers": slot_numbers,
            "7. Single CTA": slot_single_cta,
        }
        # Sub-scores that map to the drafter's mental model
        challenge_bits = [slot_pain_subject, slot_stakeholder,
                            slot_problem_chain]
        result_bits = [slot_named_proof, slot_numbers, slot_single_cta]
        challenge_score = int(100 * sum(challenge_bits)
                                / len(challenge_bits))
        result_score = int(100 * sum(result_bits) / len(result_bits))
        slot_score = int(100 * sum(slots.values()) / len(slots))
        vocab_score = int(100 * sum(v["count"] for v in vocab.values())
                            / sum(v["total"] for v in vocab.values()))
        # blended house score: half challenge, half result, minus
        # weak-phrase penalty; hygiene greeting acts as a small floor
        house_score = int(0.45 * challenge_score
                            + 0.45 * result_score
                            + (10 if slot_greeting else 0)
                            - 4 * min(len(weak), 3))
        house_score = max(0, min(100, house_score))
        return {
            "vocab": vocab, "weak": weak, "fk": fk,
            "words": len(words), "sents": len(sents),
            "persona_fit": persona_fit, "slots": slots,
            "challenge_score": challenge_score,
            "result_score": result_score,
            "slot_score": slot_score, "vocab_score": vocab_score,
            "house_score": house_score,
            "named_customers": named_customers,
            "pct_hits": pct_hits,
            "cta_hits": cta_hits,
            "connective_hits": connective_hits,
        }

    # ---- Content-type auto-classification ----
    def _content_type(name, body):
        s = f"{name} {body}".lower()
        if "arma" in s or "ncura" in s:
            return "Event promotion"
        if "wp4" in name.lower() or "wp5" in name.lower() \
                or "erp" in s or "reporting numbers" in s:
            return "Product themed"
        if "funding" in s:
            return "Funding opportunities"
        return "General promotion"

    # ---- Overview tiles ----
    n_camps = campaigns_df["campaign_name"].nunique()
    n_emails = len(campaigns_df)
    n_with_subject = int(campaigns_df["has_subject"].astype(str)
                         .str.lower().isin(["true", "1"]).sum())
    avg_words = int(campaigns_df["word_count"].mean())

    co1, co2, co3, co4 = st.columns(4)
    with co1:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Campaigns</div>'
            f'<div class="kpi-value">{n_camps}</div></div>',
            unsafe_allow_html=True)
    with co2:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Emails total</div>'
            f'<div class="kpi-value">{n_emails}</div>'
            f'<div class="kpi-sub">base + follow-ups</div></div>',
            unsafe_allow_html=True)
    with co3:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">With subject '
            f'line</div><div class="kpi-value">{n_with_subject}'
            f'</div><div class="kpi-sub">of {n_emails}</div></div>',
            unsafe_allow_html=True)
    with co4:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Avg length</div>'
            f'<div class="kpi-value">{avg_words}</div>'
            f'<div class="kpi-sub">words per email</div></div>',
            unsafe_allow_html=True)

    # ---- Score every email upfront, tag with content type ----
    scored_rows = []
    for _, r in campaigns_df.iterrows():
        a = _analyse(str(r.get("subject", "") or ""),
                      str(r.get("body", "") or ""))
        scored_rows.append({
            "campaign_id": r["campaign_id"],
            "campaign_name": r["campaign_name"],
            "stage": r["stage"],
            "persona_raw": r.get("persona_raw", ""),
            "subject": r.get("subject", ""),
            "body": r.get("body", ""),
            "content_type": _content_type(
                str(r["campaign_name"]), str(r.get("body", "") or "")),
            "words": a["words"],
            "fk": a["fk"],
            "vocab_score": a["vocab_score"],
            "slot_score": a["slot_score"],
            "challenge_score": a["challenge_score"],
            "result_score": a["result_score"],
            "weak_count": len(a["weak"]),
            "house_score": a["house_score"],
            "persona_dominant": max(a["persona_fit"],
                                      key=a["persona_fit"].get),
            "persona_fit": a["persona_fit"],
            "slots": a["slots"],
            "vocab": a["vocab"],
            "weak": a["weak"],
            "named_customers": a["named_customers"],
            "pct_hits": a["pct_hits"],
            "cta_hits": a["cta_hits"],
            "connective_hits": a["connective_hits"],
        })
    scored_df = pd.DataFrame(scored_rows)

    # ---- Inventory table ----
    st.markdown('<h3 style="margin-top:1.5rem">Campaign inventory'
                '</h3>', unsafe_allow_html=True)
    st.caption("Scored against the Email_WP5 reference pattern. "
               "Challenge = pain-named subject + stakeholder line + "
               "problem-cost chain. Result = named customers + "
               "concrete numbers + single CTA.")
    inv = scored_df[[
        "campaign_name", "stage", "content_type",
        "persona_dominant", "words", "house_score",
        "challenge_score", "result_score", "weak_count"]].copy()
    inv.columns = ["Campaign", "Stage", "Type", "Reads for",
                    "Words", "House", "Challenge", "Result",
                    "Weak"]
    st.dataframe(inv, use_container_width=True, hide_index=True)

    # ---- Content-type mix chart ----
    st.markdown('<h3 style="margin-top:2rem">Content-type mix</h3>',
                unsafe_allow_html=True)
    mix = scored_df["content_type"].value_counts().reset_index()
    mix.columns = ["Content type", "Emails"]
    mix_chart = alt.Chart(mix).mark_bar(color=ACCENT, size=28).encode(
        x=alt.X("Emails:Q", title="Emails"),
        y=alt.Y("Content type:N", sort="-x", title=None),
        tooltip=["Content type:N", "Emails:Q"],
    ).properties(height=180)
    st.altair_chart(mix_chart, use_container_width=True)

    # =============== SCORE ANALYSIS ===============
    # Performance-graph analogue: distributions, rankings, coverage.
    # Same feel as the Performance screen so the drafter reads them
    # the same way - each dot / bar is one email.
    st.markdown('<div style="margin:2.5rem 0 0;border-top:1px '
                'solid ' + LINE + '"></div>', unsafe_allow_html=True)
    st.markdown('<h3>Score analysis</h3>', unsafe_allow_html=True)

    # KPI strip: portfolio-level averages
    avg_ch = int(scored_df["challenge_score"].mean())
    avg_re = int(scored_df["result_score"].mean())
    avg_ho = int(scored_df["house_score"].mean())
    n_wp5_like = int(((scored_df["challenge_score"] >= 66)
                      & (scored_df["result_score"] >= 66)).sum())
    sa1, sa2, sa3, sa4 = st.columns(4)
    with sa1:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Avg challenge</div>'
            f'<div class="kpi-value" style="color:{ACCENT}">'
            f'{avg_ch}</div>'
            f'<div class="kpi-sub">across {n_emails} emails</div>'
            f'</div>', unsafe_allow_html=True)
    with sa2:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Avg result</div>'
            f'<div class="kpi-value" style="color:{ACCENT}">'
            f'{avg_re}</div>'
            f'<div class="kpi-sub">across {n_emails} emails</div>'
            f'</div>', unsafe_allow_html=True)
    with sa3:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Avg house</div>'
            f'<div class="kpi-value">{avg_ho}</div>'
            f'<div class="kpi-sub">blended</div></div>',
            unsafe_allow_html=True)
    with sa4:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'WP5-like emails</div>'
            f'<div class="kpi-value">{n_wp5_like}</div>'
            f'<div class="kpi-sub">both scores &ge; 66</div>'
            f'</div>', unsafe_allow_html=True)

    # ---- Challenge vs Result scatter ----
    st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                'Challenge vs Result</div>',
                unsafe_allow_html=True)
    st.caption("Top-right quadrant is the WP5 zone. Bottom-left "
               "is the redraft pile. Colour = content type.")
    scatter_df = scored_df.copy()
    scatter_df["label"] = (scatter_df["campaign_name"].astype(str)
                            + " · " + scatter_df["stage"].astype(str))
    # jitter to prevent identical-score dots overlapping
    _jitter = pd.util.hash_pandas_object(scatter_df["label"]) % 7 - 3
    scatter_df["c_jit"] = scatter_df["challenge_score"] + _jitter * 0.6
    scatter_df["r_jit"] = scatter_df["result_score"] + (_jitter * 0.6).values[::-1]
    base = alt.Chart(scatter_df).mark_circle(
        size=180, opacity=0.85, stroke="white", strokeWidth=1
    ).encode(
        x=alt.X("c_jit:Q", title="Challenge score",
                  scale=alt.Scale(domain=[-10, 110])),
        y=alt.Y("r_jit:Q", title="Result score",
                  scale=alt.Scale(domain=[-10, 110])),
        color=alt.Color("content_type:N",
                          scale=alt.Scale(scheme="tableau10"),
                          legend=alt.Legend(title="Content type")),
        tooltip=[
            alt.Tooltip("label:N", title="Email"),
            alt.Tooltip("challenge_score:Q", title="Challenge"),
            alt.Tooltip("result_score:Q", title="Result"),
            alt.Tooltip("house_score:Q", title="House"),
        ],
    )
    # WP5 target zone shading
    zone = alt.Chart(pd.DataFrame({
        "x1": [66], "x2": [110], "y1": [66], "y2": [110]
    })).mark_rect(color=ACCENT, opacity=0.08).encode(
        x="x1:Q", x2="x2:Q", y="y1:Q", y2="y2:Q")
    st.altair_chart((zone + base).properties(height=340),
                     use_container_width=True)

    # ---- House-score ranking ----
    st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                'House-score ranking</div>',
                unsafe_allow_html=True)
    rank_df = scored_df.copy()
    rank_df["label"] = (rank_df["campaign_name"].astype(str)
                         + " · " + rank_df["stage"].astype(str))
    rank_df = rank_df.sort_values("house_score", ascending=False)
    rank_chart = alt.Chart(rank_df).mark_bar(size=14).encode(
        x=alt.X("house_score:Q", title="House score",
                  scale=alt.Scale(domain=[0, 100])),
        y=alt.Y("label:N", sort="-x", title=None),
        color=alt.condition(
            "datum.house_score >= 66",
            alt.value(ACCENT), alt.value("#B8B8BE")),
        tooltip=[
            alt.Tooltip("label:N", title="Email"),
            alt.Tooltip("house_score:Q", title="House"),
            alt.Tooltip("challenge_score:Q", title="Challenge"),
            alt.Tooltip("result_score:Q", title="Result"),
        ],
    ).properties(height=max(220, 22 * len(rank_df)))
    st.altair_chart(rank_chart, use_container_width=True)

    # ---- Slot hit-rate ----
    st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                'Slot hit-rate across all emails</div>',
                unsafe_allow_html=True)
    st.caption("Share of emails that hit each seven-slot signal. "
               "Low bars point to systemic gaps to fix in the "
               "template.")
    slot_names = list(scored_rows[0]["slots"].keys()) \
        if scored_rows else []
    slot_hit_rows = []
    for slot in slot_names:
        hits = sum(1 for r in scored_rows if r["slots"][slot])
        slot_hit_rows.append(
            {"Slot": slot,
              "Hit rate": (hits / len(scored_rows) * 100)
                            if scored_rows else 0,
              "Emails hitting": hits})
    slot_hr_df = pd.DataFrame(slot_hit_rows)
    slot_chart = alt.Chart(slot_hr_df).mark_bar(size=18).encode(
        x=alt.X("Hit rate:Q", title="Hit rate (%)",
                  scale=alt.Scale(domain=[0, 100])),
        y=alt.Y("Slot:N", sort="-x", title=None),
        color=alt.condition(
            "datum['Hit rate'] >= 66",
            alt.value(ACCENT), alt.value(GOLD)),
        tooltip=["Slot:N",
                  alt.Tooltip("Hit rate:Q", format=".0f"),
                  "Emails hitting:Q"],
    ).properties(height=240)
    st.altair_chart(slot_chart, use_container_width=True)

    # ---- Scores by content type ----
    st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                'Challenge vs Result by content type</div>',
                unsafe_allow_html=True)
    grp = scored_df.groupby("content_type")[
        ["challenge_score", "result_score"]].mean().reset_index()
    grp_long = grp.melt(id_vars=["content_type"],
                          value_vars=["challenge_score",
                                        "result_score"],
                          var_name="Axis", value_name="Score")
    grp_long["Axis"] = grp_long["Axis"].map({
        "challenge_score": "Challenge",
        "result_score": "Result"})
    grp_chart = alt.Chart(grp_long).mark_bar(size=22).encode(
        x=alt.X("content_type:N", title=None,
                  axis=alt.Axis(labelAngle=-15)),
        xOffset="Axis:N",
        y=alt.Y("Score:Q", title="Average score",
                  scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("Axis:N",
                          scale=alt.Scale(range=[ACCENT, GOLD])),
        tooltip=["content_type:N", "Axis:N",
                  alt.Tooltip("Score:Q", format=".0f")],
    ).properties(height=260)
    st.altair_chart(grp_chart, use_container_width=True)

    # ---- Named-customer frequency across all emails ----
    all_named = []
    for r in scored_rows:
        for name in r.get("named_customers", []):
            all_named.append(name.strip())
    if all_named:
        from collections import Counter as _CntCA
        nc = _CntCA(all_named).most_common(15)
        nc_df = pd.DataFrame(nc, columns=["Customer", "Mentions"])
        st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                    'Named customer proof, most cited</div>',
                    unsafe_allow_html=True)
        st.caption("How often each named customer appears across "
                   "the current campaign set. Overused names look "
                   "stale; underused names are worth surfacing.")
        nc_chart = alt.Chart(nc_df).mark_bar(color=ACCENT,
                                                size=14).encode(
            x=alt.X("Mentions:Q", title="Mentions"),
            y=alt.Y("Customer:N", sort="-x", title=None),
            tooltip=["Customer:N", "Mentions:Q"],
        ).properties(height=max(200, 22 * len(nc_df)))
        st.altair_chart(nc_chart, use_container_width=True)

    # ---- Word count vs house score ----
    st.markdown('<div class="eyebrow" style="margin-top:1.5rem">'
                'Length vs house score</div>',
                unsafe_allow_html=True)
    st.caption("Does longer copy score higher, or does it just add "
               "words? A flat cloud means length is not the lever.")
    ln_df = scored_df.copy()
    ln_df["label"] = (ln_df["campaign_name"].astype(str)
                       + " · " + ln_df["stage"].astype(str))
    len_chart = alt.Chart(ln_df).mark_circle(
        size=160, opacity=0.85, color=ACCENT).encode(
        x=alt.X("words:Q", title="Word count"),
        y=alt.Y("house_score:Q", title="House score",
                  scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip("label:N", title="Email"),
            "words:Q",
            alt.Tooltip("house_score:Q", title="House"),
        ],
    ).properties(height=260)
    _trend = alt.Chart(ln_df).transform_regression(
        "words", "house_score"
    ).mark_line(color=GOLD, strokeWidth=2, strokeDash=[4, 4]).encode(
        x="words:Q", y="house_score:Q")
    st.altair_chart(len_chart + _trend,
                     use_container_width=True)

    st.markdown('<div style="margin:2.5rem 0 0;border-top:1px '
                'solid ' + LINE + '"></div>', unsafe_allow_html=True)

    # ---- Detail drawer: pick a campaign ----
    st.markdown('<h3 style="margin-top:2rem">Email detail</h3>',
                unsafe_allow_html=True)
    options = [
        f"{i+1}. {r['campaign_name']} - {r['stage']}"
        for i, r in scored_df.iterrows()]
    pick = st.selectbox("Pick an email", options,
                         key="ca_email_pick")
    pick_idx = options.index(pick)
    row = scored_rows[pick_idx]

    hs1, hs2, hs3, hs4 = st.columns(4)
    with hs1:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Challenge score</div>'
            f'<div class="kpi-value" style="color:{ACCENT}">'
            f'{row["challenge_score"]}</div>'
            f'<div class="kpi-sub">pain subject + stakeholder + '
            f'problem chain</div></div>',
            unsafe_allow_html=True)
    with hs2:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">'
            f'Result score</div>'
            f'<div class="kpi-value" style="color:{ACCENT}">'
            f'{row["result_score"]}</div>'
            f'<div class="kpi-sub">named proof + numbers + CTA'
            f'</div></div>',
            unsafe_allow_html=True)
    with hs3:
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">House score'
            f'</div><div class="kpi-value">{row["house_score"]}</div>'
            f'<div class="kpi-sub">blended</div></div>',
            unsafe_allow_html=True)
    with hs4:
        fk_str = f'{row["fk"]}' if row["fk"] is not None else '-'
        st.markdown(
            f'<div class="kpi"><div class="kpi-label">Reading grade'
            f'</div><div class="kpi-value">{fk_str}</div>'
            f'<div class="kpi-sub">Flesch-Kincaid, {row["words"]} '
            f'words</div></div>', unsafe_allow_html=True)

    # Evidence strip: what the analyser actually found for each
    # result slot, so scores are auditable.
    _ev = []
    if row["named_customers"]:
        _ev.append(f'<strong>Named customers ({len(row["named_customers"])})'
                    f':</strong> ' + ", ".join(
                        row["named_customers"][:5]))
    else:
        _ev.append('<strong>Named customers:</strong> none found')
    if row["pct_hits"]:
        _ev.append('<strong>Concrete numbers:</strong> '
                    + ", ".join(row["pct_hits"]))
    else:
        _ev.append('<strong>Concrete numbers:</strong> none found')
    if row["cta_hits"]:
        _ev.append('<strong>CTA phrases:</strong> '
                    + ", ".join(row["cta_hits"]))
    else:
        _ev.append('<strong>CTA phrases:</strong> none matched')
    _ev.append(f'<strong>Problem-cost connectives:</strong> '
                f'{row["connective_hits"]} '
                f'({"chain detected" if row["connective_hits"]>=2 else "chain missing"})')
    st.markdown(
        '<div style="background:#faf7f0;border-left:3px solid '
        + ACCENT + ';padding:.7rem 1rem;margin:.8rem 0;'
        'border-radius:4px;font-size:.9rem">'
        + '<br>'.join(_ev) + '</div>',
        unsafe_allow_html=True)

    dc1, dc2 = st.columns([1.2, 1])
    with dc1:
        st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                    'Subject</div>', unsafe_allow_html=True)
        st.write(row["subject"] or "_no subject line_")
        st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                    'Body</div>', unsafe_allow_html=True)
        with st.expander("Show full body", expanded=False):
            st.text(row["body"])
    with dc2:
        st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                    'Seven-slot check</div>',
                    unsafe_allow_html=True)
        for slot, ok in row["slots"].items():
            icon = "OK" if ok else "MISS"
            color = ACCENT if ok else "#B34747"
            st.markdown(
                f'<div style="padding:.3rem 0"><span style="color:'
                f'{color};font-weight:600">{icon}</span>&nbsp;{slot}'
                f'</div>', unsafe_allow_html=True)

    vc1, vc2 = st.columns(2)
    with vc1:
        st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                    'Vocabulary hits</div>',
                    unsafe_allow_html=True)
        for g, info in row["vocab"].items():
            hits_txt = (", ".join(info["hits"])
                        if info["hits"] else "(none)")
            st.markdown(
                f'<div style="padding:.3rem 0">'
                f'<strong>{g.replace("_", " ")}:</strong> '
                f'{info["count"]}/{info["total"]} - {hits_txt}'
                f'</div>', unsafe_allow_html=True)
    with vc2:
        st.markdown('<div class="eyebrow" style="margin-top:1rem">'
                    'Weak phrases</div>',
                    unsafe_allow_html=True)
        if row["weak"]:
            for w, s in row["weak"]:
                st.markdown(
                    f'<div style="padding:.3rem 0">'
                    f'<span style="text-decoration:line-through;'
                    f'color:{MUTED}">{w}</span> &rarr; '
                    f'<strong>{s}</strong></div>',
                    unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:{MUTED}">None - clean copy'
                        '</div>', unsafe_allow_html=True)

    # Persona fit
    st.markdown('<div class="eyebrow" style="margin-top:1.2rem">'
                'Persona fit (term density)</div>',
                unsafe_allow_html=True)
    pf_df = pd.DataFrame([
        {"Persona": k, "Density": v * 100}
        for k, v in row["persona_fit"].items()])
    pf_chart = alt.Chart(pf_df).mark_bar(color=ACCENT, size=24).encode(
        x=alt.X("Density:Q",
                  title="Term density (% of body words)"),
        y=alt.Y("Persona:N", sort="-x", title=None),
        tooltip=["Persona:N",
                  alt.Tooltip("Density:Q", format=".2f")],
    ).properties(height=140)
    st.altair_chart(pf_chart, use_container_width=True)
    dominant = row["persona_dominant"]
    if dominant == "Research":
        st.caption("Reads Research-first. Matches the dominant "
                   "blast slot (Research T2/T3 = 68% of verified "
                   "list).")
    else:
        st.caption(f"Reads {dominant}-first. If this ships as a "
                   f"blast, the dominant Research slot may not "
                   f"engage - consider re-anchoring vocabulary.")

    # ---- Aggregate: which pain themes get covered a lot ----
    st.markdown('<h3 style="margin-top:2.5rem">Coverage across all '
                'campaigns</h3>', unsafe_allow_html=True)
    agg_rows = []
    for group, terms in SAAS_VOCAB_CA.items():
        for term in terms:
            count = sum(1 for _, r in scored_df.iterrows()
                        if term in str(r["body"]).lower()
                        or term in str(r["subject"]).lower())
            agg_rows.append({"Group": group.replace("_", " "),
                              "Phrase": term,
                              "Emails using it": count})
    agg_df = pd.DataFrame(agg_rows).sort_values(
        "Emails using it", ascending=False)

    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown('<div class="eyebrow">Most used phrases</div>',
                    unsafe_allow_html=True)
        st.dataframe(agg_df.head(10), use_container_width=True,
                      hide_index=True)
    with ac2:
        st.markdown('<div class="eyebrow">Least used phrases</div>',
                    unsafe_allow_html=True)
        unused = agg_df[agg_df["Emails using it"] == 0]
        if not unused.empty:
            st.dataframe(unused, use_container_width=True,
                          hide_index=True)
            st.caption("These pain-shape phrases are missing from "
                       "every current campaign. Each is a candidate "
                       "for a new email angle.")
        else:
            st.info("Every house phrase appears in at least one "
                     "campaign.")

    # ---- Content ideas: gap-driven ----
    st.markdown('<h3 style="margin-top:2rem">Suggested next '
                'content</h3>', unsafe_allow_html=True)
    type_counts = scored_df["content_type"].value_counts().to_dict()
    gaps = []
    if type_counts.get("Product themed", 0) < 4:
        gaps.append(("Product themed", "Two more WP-style emails "
                      "(pick from: audit trail, integration, "
                      "reporting, funder scanner). Low count today."))
    if type_counts.get("Event promotion", 0) >= 5:
        gaps.append(("Event promotion", "Event emails dominate. "
                      "Balance the mix with more product-outcome "
                      "campaigns."))
    if not unused.empty:
        phrases = ", ".join(unused["Phrase"].head(3).tolist())
        gaps.append(("Missing pain shape",
                      f"No campaign covers: {phrases}. Each is a "
                      "content prompt."))
    weak_avg = scored_df["weak_count"].mean()
    if weak_avg >= 1:
        gaps.append(("Cleaner copy",
                      f"Average {weak_avg:.1f} weak phrase per "
                      "email. Swap the flagged phrases in the "
                      "detail drawer above."))
    if not gaps:
        st.success("No obvious content gaps against the current "
                    "rule set.")
    else:
        for tag, msg in gaps:
            st.markdown(
                f'<div style="background:#faf7f0;border-left:3px '
                f'solid {ACCENT};padding:.7rem 1rem;margin:.5rem 0;'
                f'border-radius:4px"><strong>{tag}.</strong> {msg}'
                f'</div>', unsafe_allow_html=True)


# Email Performance Matrix is a self-contained app. Once its block above has
# rendered, halt so none of the LinkedIn-only sections below execute.
