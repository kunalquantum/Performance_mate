"""
Email Performance Matrix - Audience screen.
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
st.markdown('<h1>Audience &amp; Next Send</h1>', unsafe_allow_html=True)

emails_all = load_csv("emails.csv")
if not emails_all.empty:
    emails_all["week_start"] = pd.to_datetime(emails_all["week_start"],
                                                errors="coerce")

# ================== AUDIENCE + NEXT SEND BUILDER ==================
st.markdown('<div style="margin:3rem 0 0;border-top:1px solid ' + LINE
             + '"></div>', unsafe_allow_html=True)
st.markdown('<h2>Audience</h2>', unsafe_allow_html=True)
st.caption("From the cleaned UK masterlist. This is what you can send "
           "to right now, split by readiness and freshness.")

contacts_df = load_csv("contacts.csv")
if contacts_df.empty:
    st.info("No contacts data. Run `python etl/contacts_etl.py` to build "
            "data/contacts.csv.")
else:
    # Coerce derived flags in case the CSV round-trip made them strings
    for _bcol in ("is_send_ready", "is_fresh", "is_verified"):
        if _bcol in contacts_df.columns:
            contacts_df[_bcol] = (
                contacts_df[_bcol].astype(str).str.lower()
                .isin(["true", "1", "yes"]))

    total_c = len(contacts_df)
    send_ready = int(contacts_df["is_send_ready"].sum())
    needs_verify = int(
        contacts_df["send_status"].astype(str).str.startswith("2").sum())
    needs_segment = int(
        contacts_df["send_status"].astype(str).str.startswith("3").sum())
    fresh = int(contacts_df["is_fresh"].sum())
    already = total_c - fresh
    actionable = int(
        (contacts_df["is_send_ready"] & contacts_df["is_fresh"]
         & contacts_df["is_verified"]).sum())

    at1, at2, at3, at4, at5 = st.columns(5)
    with at1:
        st.markdown(f'<div class="kpi"><div class="kpi-label">'
                    f'Send ready</div><div class="kpi-value">{send_ready:,}'
                    f'</div></div>', unsafe_allow_html=True)
    with at2:
        st.markdown(f'<div class="kpi"><div class="kpi-label">'
                    f'Needs verify</div><div class="kpi-value">'
                    f'{needs_verify:,}</div></div>',
                    unsafe_allow_html=True)
    with at3:
        st.markdown(f'<div class="kpi"><div class="kpi-label">'
                    f'Needs segment</div><div class="kpi-value">'
                    f'{needs_segment:,}</div></div>',
                    unsafe_allow_html=True)
    with at4:
        st.markdown(f'<div class="kpi"><div class="kpi-label">'
                    f'Fresh</div><div class="kpi-value">{fresh:,}'
                    f'</div><div class="kpi-sub">of {total_c:,} '
                    f'total</div></div>', unsafe_allow_html=True)
    with at5:
        st.markdown(f'<div class="kpi"><div class="kpi-label">'
                    f'Actionable now</div><div class="kpi-value" '
                    f'style="color:{ACCENT}">{actionable:,}</div>'
                    f'<div class="kpi-sub">send-ready + fresh + '
                    f'verified</div></div>', unsafe_allow_html=True)

    st.caption(f"Already approached: {already:,}. "
               f"Actionable pool ({actionable:,}) is what a fresh "
               "campaign can draw from without re-hitting anyone.")

    # ---------- Next Send Builder ----------
    st.markdown('<div style="margin:2.5rem 0 0;border-top:1px solid '
                + LINE + '"></div>', unsafe_allow_html=True)
    st.markdown('<h3>Next send builder</h3>', unsafe_allow_html=True)
    st.caption("Pick who to email next. The builder samples across "
               "institutions so no single university dominates the "
               "batch. Download the CSV to hand to the ESP.")

    nsb1, nsb2, nsb3 = st.columns([1.2, 1.2, 1])
    with nsb1:
        personas = sorted([p for p in contacts_df["persona_final"]
                           .dropna().unique().tolist()
                           if p != "Unclassified"])
        picked_personas = st.multiselect(
            "Personas",
            options=personas,
            default=["Research"] if "Research" in personas else personas[:1],
            key="nsb_personas")
    with nsb2:
        tiers = sorted(contacts_df["seniority_tier"].dropna().unique().tolist())
        default_tiers = [t for t in tiers if t.startswith(("T1", "T2", "T3"))]
        picked_tiers = st.multiselect(
            "Seniority tiers",
            options=tiers,
            default=default_tiers,
            key="nsb_tiers")
    with nsb3:
        bands = sorted(contacts_df["institution_band"].dropna().unique().tolist())
        picked_bands = st.multiselect(
            "Institution bands",
            options=bands,
            default=bands,
            key="nsb_bands")

    nsb4, nsb5, nsb6 = st.columns(3)
    with nsb4:
        exclude_approached = st.toggle(
            "Exclude already approached", value=True,
            key="nsb_exclude_approached")
    with nsb5:
        exclude_unverified = st.toggle(
            "Verified only", value=True, key="nsb_exclude_unverified")
    with nsb6:
        require_send_ready = st.toggle(
            "Send ready only", value=True, key="nsb_require_ready")

    # Apply filters
    pool = contacts_df.copy()
    if picked_personas:
        pool = pool[pool["persona_final"].isin(picked_personas)]
    if picked_tiers:
        pool = pool[pool["seniority_tier"].isin(picked_tiers)]
    if picked_bands:
        pool = pool[pool["institution_band"].isin(picked_bands)]
    if exclude_approached:
        pool = pool[pool["is_fresh"]]
    if exclude_unverified:
        pool = pool[pool["is_verified"]]
    if require_send_ready:
        pool = pool[pool["is_send_ready"]]

    pool_size = len(pool)
    if pool_size == 0:
        st.warning("No contacts match those filters. Loosen a filter "
                   "to see the pool.")
    else:
        max_batch = min(pool_size, 1000)
        default_batch = min(200, max_batch)
        batch_size = st.slider(
            f"Batch size (pool: {pool_size:,} contacts)",
            min_value=10, max_value=max_batch,
            value=default_batch, step=10, key="nsb_batch_size")

        # Stratified sample: equal share per institution among top slots,
        # then remainder random from what is left.
        def _stratified_sample(df, n, strat_col="institution",
                                seed=42):
            if len(df) <= n:
                return df.copy()
            rng = df.sample(frac=1, random_state=seed).reset_index(drop=True)
            counts = rng[strat_col].value_counts()
            per_inst = max(1, n // max(len(counts), 1))
            picked_rows = []
            for inst, _cnt in counts.items():
                sub = rng[rng[strat_col] == inst].head(per_inst)
                picked_rows.append(sub)
                if sum(len(x) for x in picked_rows) >= n:
                    break
            picked = pd.concat(picked_rows).head(n)
            if len(picked) < n:
                remaining = rng.drop(picked.index)
                picked = pd.concat(
                    [picked, remaining.head(n - len(picked))])
            return picked.head(n)

        batch = _stratified_sample(pool, batch_size)

        # Composition summary
        comp_persona = batch["persona_final"].value_counts()
        comp_tier = batch["seniority_tier"].value_counts()
        n_inst = batch["institution"].nunique()
        top_inst = batch["institution"].value_counts().head(3)

        cs1, cs2, cs3 = st.columns(3)
        with cs1:
            st.markdown(f'<div class="kpi"><div class="kpi-label">'
                        f'Batch size</div><div class="kpi-value">'
                        f'{len(batch):,}</div></div>',
                        unsafe_allow_html=True)
        with cs2:
            st.markdown(f'<div class="kpi"><div class="kpi-label">'
                        f'Institutions</div><div class="kpi-value">'
                        f'{n_inst:,}</div>'
                        f'<div class="kpi-sub">across the batch</div>'
                        f'</div>', unsafe_allow_html=True)
        with cs3:
            top_share = int(top_inst.iloc[0]) if len(top_inst) else 0
            top_pct = (top_share / max(len(batch), 1)) * 100
            st.markdown(f'<div class="kpi"><div class="kpi-label">'
                        f'Top institution share</div>'
                        f'<div class="kpi-value">{top_pct:.0f}%</div>'
                        f'<div class="kpi-sub">'
                        f'{top_inst.index[0] if len(top_inst) else "-"}'
                        f'</div></div>', unsafe_allow_html=True)

        # ---------- Expected open rate band (from history) ----------
        def _wilson_local(k, n, z=1.96):
            if not n or pd.isna(k) or pd.isna(n) or n == 0:
                return (float("nan"), float("nan"))
            p = k / n
            denom = 1 + z * z / n
            centre = (p + z * z / (2 * n)) / denom
            spread = (z / denom) * ((p * (1 - p) / n
                                      + z * z / (4 * n * n)) ** 0.5)
            return max(0.0, centre - spread), min(1.0, centre + spread)

        hist = emails_all.dropna(subset=["contacts", "delivered",
                                          "opened"]).copy()
        hist = hist[hist["delivered"] > 0]
        band_lo = band_hi = band_mid = float("nan")
        bucket_label = "no history match"
        n_weeks_bucket = 0
        if len(hist) >= 4:
            # Bucket historical weeks into quartiles by contacts sent
            try:
                hist["_bucket"] = pd.qcut(hist["contacts"], q=4,
                                            duplicates="drop")
                # Find which quartile the current batch size falls into
                match = hist[hist["contacts"].apply(
                    lambda c: c >= batch_size * 0.5
                    and c <= batch_size * 2.0)]
                if len(match) < 3:
                    # Fall back to closest quartile by median contacts
                    medians = hist.groupby("_bucket", observed=True)[
                        "contacts"].median()
                    closest = (medians - batch_size).abs().idxmin()
                    match = hist[hist["_bucket"] == closest]
                    bucket_label = (f"weeks with ~{int(medians[closest])} "
                                    f"contacts (nearest bucket)")
                else:
                    bucket_label = (f"weeks with {int(batch_size*0.5)}"
                                    f"-{int(batch_size*2.0)} contacts")
                n_weeks_bucket = len(match)
                if n_weeks_bucket >= 1:
                    k = float(match["opened"].sum())
                    n = float(match["delivered"].sum())
                    if n > 0:
                        band_mid = k / n
                        band_lo, band_hi = _wilson_local(k, n)
            except Exception:
                pass

        eb1, eb2 = st.columns([1.3, 1])
        with eb1:
            if pd.notna(band_mid):
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Expected open rate (95% band)</div>'
                    f'<div class="kpi-value" style="color:{ACCENT}">'
                    f'{band_lo*100:.1f}% - {band_hi*100:.1f}%</div>'
                    f'<div class="kpi-sub">point estimate '
                    f'{band_mid*100:.1f}%, from {n_weeks_bucket} '
                    f'{bucket_label}</div></div>',
                    unsafe_allow_html=True)
            else:
                st.info("Not enough matching history to estimate a "
                         "band for this batch size.")
        with eb2:
            if pd.notna(band_mid):
                exp_lo = int(band_lo * len(batch))
                exp_hi = int(band_hi * len(batch))
                st.markdown(
                    f'<div class="kpi"><div class="kpi-label">'
                    f'Expected opens</div><div class="kpi-value">'
                    f'{exp_lo} - {exp_hi}</div>'
                    f'<div class="kpi-sub">on this {len(batch)}-contact '
                    f'batch</div></div>',
                    unsafe_allow_html=True)

        reason_lines = []
        if len(picked_personas) == 1:
            reason_lines.append(
                f"Focused on {picked_personas[0]} to keep messaging "
                f"vocabulary consistent across the send.")
        elif len(picked_personas) > 1:
            reason_lines.append(
                f"Mixed personas ({', '.join(picked_personas)}) - "
                f"consider splitting into per-persona sends for cleaner "
                f"open-rate signal.")
        if exclude_approached:
            reason_lines.append(
                "Fresh contacts only, so we do not re-hit anyone in "
                "the already-approached list.")
        if exclude_unverified:
            reason_lines.append(
                "Verified deliverability only, which cuts the bounce "
                "risk seen on unverified sends.")
        st.markdown('<div style="background:#faf7f0;border-left:3px '
                    'solid ' + ACCENT + ';padding:0.75rem 1rem;'
                    'margin:1rem 0;border-radius:4px">'
                    '<strong>Why this batch</strong><br>'
                    + '<br>'.join(reason_lines) + '</div>',
                    unsafe_allow_html=True)

        with st.expander("Preview batch (first 25 rows)"):
            preview_cols = ["first_name", "last_name", "email_clean",
                             "job_title", "institution", "persona_final",
                             "seniority_tier"]
            preview_cols = [c for c in preview_cols if c in batch.columns]
            st.dataframe(batch[preview_cols].head(25),
                          use_container_width=True, hide_index=True)

        export_cols = ["contact_id", "email_clean", "first_name",
                        "last_name", "job_title", "institution",
                        "persona_final", "seniority_tier",
                        "segment_key", "institution_band"]
        export_cols = [c for c in export_cols if c in batch.columns]
        csv_bytes = batch[export_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download batch CSV",
            data=csv_bytes,
            file_name=f"next_send_batch_{len(batch)}.csv",
            mime="text/csv",
            key="nsb_download")

st.markdown('<div style="margin:3rem 0 0;border-top:1px solid ' + LINE
             + '"></div>', unsafe_allow_html=True)
st.markdown('<h2>Compose an email</h2>', unsafe_allow_html=True)

# ================== 3. COMPOSE + ANALYSE (existing block) ==================
# House SaaS vocabulary. Weakness -> stronger phrasing, and coverage
# groups tracked by the analyser.
SAAS_VOCAB = {
    "pain_points": [
        "lack of visibility", "no single source of truth",
        "disconnected systems", "fragmented workflows",
    ],
    "manual_work": [
        "time-consuming tasks", "repetitive administration",
        "duplicate data entry", "human error",
        "operational inefficiency",
    ],
    "outcomes": [
        "reduce risk", "increase efficiency", "increase productivity",
        "accurate forecasting", "reduced risk and error",
        "improve visibility",
    ],
}
WEAK_SWAPS = {
    "many businesses": "leaders",
    "a lot of": "several",
    "in order to": "to",
    "utilise": "use",
    "utilize": "use",
    "in the process of": "while",
    "leverage": "use",
    "synergy": "alignment",
    "at the end of the day": "the point is",
    "streamline": "simplify",
    "solution": "platform",
}

def _analyse_email(subject, body):
    text = f"{subject}\n{body}"
    lower = text.lower()
    # coverage per group
    coverage = {}
    for group, phrases in SAAS_VOCAB.items():
        hits = [p for p in phrases if p in lower]
        coverage[group] = {"hits": hits, "count": len(hits),
                            "total": len(phrases)}
    # weak phrases
    weak_hits = [(w, s) for w, s in WEAK_SWAPS.items() if w in lower]
    # readability rough
    import re
    words = re.findall(r"[a-zA-Z]+", body)
    sents = re.split(r"[.!?]+", body)
    sents = [s.strip() for s in sents if s.strip()]
    avg_sent = (len(words) / len(sents)) if sents else 0
    # Flesch-Kincaid rough
    syl = 0
    for w in words:
        groups = re.findall(r"[aeiouy]+", w.lower())
        syl += max(1, len(groups))
    fk = None
    if words and sents:
        fk = round(
            0.39 * (len(words) / len(sents))
            + 11.8 * (syl / len(words)) - 15.59, 1)
    # seven-slot presence heuristic
    slots = {
        "subject": bool(subject.strip()),
        "stakeholder line": any(k in lower for k in
                                 ["board", "cfo", "finance leader",
                                  "leader", "team", "executive"]),
        "problem-cost pair": lower.count(":") >= 1
                                or lower.count(" - ") >= 2,
        "product line": any(k in lower for k in
                             ["grantsnow", "our platform",
                              "the platform"]),
        "named proof": any(k in lower for k in
                            ["university of", "college of",
                             "institute", "customer",
                             "case study"]),
        "outcome close": any(g in lower for g in
                              SAAS_VOCAB["outcomes"]),
        "single cta": lower.count("book a call") + lower.count(
                            "get in touch") + lower.count(
                            "read the whitepaper") + lower.count(
                            "download") + lower.count("register")
                            == 1,
    }
    return {
        "words": len(words),
        "sentences": len(sents),
        "avg_sentence_words": round(avg_sent, 1),
        "fk_grade": fk,
        "coverage": coverage,
        "weak_hits": weak_hits,
        "slots": slots,
    }

# ------ header ------
st.markdown('<h2>Email Matrix</h2>', unsafe_allow_html=True)
st.caption("Draft a result-driven promotional email using the house "
           "seven-slot pattern. The analyser scores readability, "
           "checks the SaaS vocabulary coverage, and flags weak "
           "phrases as you type.")

# ------ 1. the pattern reference ------
with st.expander("The seven-slot house pattern (reference)",
                 expanded=False):
    st.markdown("""
    | Slot | What it holds |
    |---|---|
    | **1. Pain-named subject** | Names the pain in the first four words. Not the product. |
    | **2. Stakeholder demand line** | One line naming who is asking for this. Finance leader, board, research director. |
    | **3. Three problem-to-cost pairs** | Each pair names one problem and the cost of ignoring it. Not features. |
    | **4. One-sentence product line** | What the product is, in one line. Not a paragraph. |
    | **5. Named proof before numbers** | Named customer or institution before any percentage. Trust before claim. |
    | **6. Outcome close in buyer language** | Close in the buyer's own words. Reduced risk. Accurate forecasting. |
    | **7. Single CTA** | One action. Not three. Book a call. Read the whitepaper. Register. |
    """)

# ------ 2. compose form ------
ecol1, ecol2 = st.columns([3, 2], gap="large")
with ecol1:
    st.markdown('<div class="eyebrow">Subject</div>',
                unsafe_allow_html=True)
    email_subject = st.text_input(
        " ", key="email_subject",
        placeholder="Pain-named subject line...",
        label_visibility="collapsed")

    st.markdown('<div class="eyebrow" style="margin-top:1rem">Body</div>',
                unsafe_allow_html=True)
    email_body = st.text_area(
        " ", height=340, key="email_body",
        placeholder=(
            "1. Stakeholder demand line\n\n"
            "2. Problem - cost pair one\n"
            "   Problem - cost pair two\n"
            "   Problem - cost pair three\n\n"
            "3. One sentence on GrantsNow\n\n"
            "4. Named proof followed by the number\n\n"
            "5. Outcome close in buyer language\n\n"
            "6. Single CTA"),
        label_visibility="collapsed")

with ecol2:
    st.markdown('<div class="eyebrow">Coverage</div>',
                unsafe_allow_html=True)
    st.caption("Live counts of the house vocabulary in your draft. "
               "Aim for at least two hits per group before shipping.")

    result = _analyse_email(email_subject or "", email_body or "")

    # coverage tiles
    for group, label in [
        ("pain_points", "Pain-point language"),
        ("manual_work", "Manual-work language"),
        ("outcomes", "Business-outcome language"),
    ]:
        c = result["coverage"][group]
        score_col = ACCENT if c["count"] >= 2 else (
            WARN if c["count"] == 0 else MUTED)
        st.markdown(
            f'<div class="card" style="padding:.7rem .9rem;'
            f'margin-bottom:.5rem">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline">'
            f'<div class="k" style="font-size:.72rem;letter-spacing:.14em;'
            f'text-transform:uppercase;color:{MUTED};font-weight:600">'
            f'{label}</div>'
            f'<div style="font-family:Georgia,serif;font-size:1.3rem;'
            f'font-weight:700;color:{score_col};line-height:1">'
            f'{c["count"]} / {c["total"]}</div></div>'
            f'<div style="font-size:.78rem;color:{INK_SOFT};'
            f'margin-top:.35rem">'
            + (", ".join(c["hits"]) if c["hits"] else "no matches yet")
            + f'</div></div>', unsafe_allow_html=True)

    # readability tile
    fk = result["fk_grade"]
    fk_label = (f"Grade {fk}" if fk is not None
                else "-")
    fk_col = ACCENT if fk and 6 <= fk <= 10 else (
        WARN if fk and fk > 13 else MUTED)
    st.markdown(
        f'<div class="card" style="padding:.7rem .9rem;'
        f'margin-bottom:.5rem">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:baseline">'
        f'<div class="k" style="font-size:.72rem;letter-spacing:.14em;'
        f'text-transform:uppercase;color:{MUTED};font-weight:600">'
        f'Readability (Flesch-Kincaid)</div>'
        f'<div style="font-family:Georgia,serif;font-size:1.3rem;'
        f'font-weight:700;color:{fk_col};line-height:1">'
        f'{fk_label}</div></div>'
        f'<div style="font-size:.78rem;color:{INK_SOFT};'
        f'margin-top:.35rem">'
        f'{result["words"]} words &middot; '
        f'{result["sentences"]} sentences &middot; '
        f'avg sentence {result["avg_sentence_words"]} words</div>'
        f'</div>', unsafe_allow_html=True)

# ------ 3. slot checklist ------
st.markdown('<h3 style="margin-top:2rem">Seven-slot checklist</h3>',
            unsafe_allow_html=True)
st.caption("Which slots does the current draft appear to cover. "
           "Heuristic, not gospel. Missing marks call for a manual "
           "check.")
slots = result["slots"]
cols = st.columns(7)
slot_labels = [
    ("subject", "Subject"), ("stakeholder line", "Stakeholder"),
    ("problem-cost pair", "Problem-cost"),
    ("product line", "Product line"),
    ("named proof", "Named proof"),
    ("outcome close", "Outcome close"),
    ("single cta", "Single CTA"),
]
for col, (key, label) in zip(cols, slot_labels):
    ok = slots.get(key, False)
    icon = "&#10003;" if ok else "&#8226;"
    colour = ACCENT if ok else MUTED
    with col:
        st.markdown(
            f'<div style="text-align:center;padding:.5rem 0">'
            f'<div style="font-size:1.5rem;color:{colour};'
            f'font-weight:700;line-height:1">{icon}</div>'
            f'<div style="font-size:.72rem;color:{MUTED};'
            f'letter-spacing:.1em;text-transform:uppercase;'
            f'margin-top:.3rem">{label}</div></div>',
            unsafe_allow_html=True)

# ------ 4. weak phrase flags ------
if result["weak_hits"]:
    st.markdown('<h3 style="margin-top:2rem">Weak phrases to swap</h3>',
                unsafe_allow_html=True)
    st.caption("House rule flags. Each row shows the weak phrase found "
               "and the recommended replacement.")
    for weak, strong in result["weak_hits"]:
        st.markdown(
            f'<div class="card" style="padding:.7rem 1rem;'
            f'margin-bottom:.4rem">'
            f'<div style="display:flex;justify-content:space-between;'
            f'gap:1rem;align-items:center">'
            f'<div style="color:{WARN};text-decoration:line-through">'
            f'{weak}</div>'
            f'<div style="color:{MUTED}">&rarr;</div>'
            f'<div style="color:{ACCENT};font-weight:600">{strong}</div>'
            f'</div></div>', unsafe_allow_html=True)

# ------ 5. copy the email ------
st.markdown('<h3 style="margin-top:2rem">Copy the email</h3>',
            unsafe_allow_html=True)
email_full = (f"Subject: {email_subject}\n\n{email_body}"
               if email_subject or email_body
               else "Draft the email above first.")
with st.expander("Show plain-text version", expanded=False):
    st.code(email_full, language="text")
    st.download_button("Download as text",
                        email_full.encode("utf-8"),
                        file_name="email_draft.txt",
                        mime="text/plain")

st.markdown(
    f'<div style="color:{MUTED};font-size:.75rem;'
    f'margin-top:2.5rem;text-align:center">'
    f'The Email Matrix does not yet score against real email '
    f'performance data. Once a mailer export is available, the same '
    f'scoring engine used for LinkedIn posts will apply here.</div>',
    unsafe_allow_html=True)


