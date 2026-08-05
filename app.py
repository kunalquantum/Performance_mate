"""
GrantsNow Performance Matrix - multi-page Streamlit entrypoint.

Trimmed to Ian's spec (items 1-8). Bonus pages moved to
_archive/pages_bonus/.

Sidebar structure:
    Persona   -> UK Persona Matrix (default) + Monthly report   [spec 1-3]
    Email     -> This week's numbers + Rolling marketing report [spec 4, 7]
    LinkedIn  -> What worked + See the pattern + Draft the next [spec 8]

Run:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="GrantsNow Performance Matrix",
                    layout="wide", page_icon="○")

pg = st.navigation({
    "Persona": [
        st.Page("pages/persona_matrix.py",
                title="UK Persona Matrix",
                icon=":material/dashboard:",
                default=True),
        st.Page("pages/persona_monthly_report.py",
                title="Monthly report",
                icon=":material/calendar_view_month:"),
        st.Page("pages/persona_content_plan.py",
                title="Content plan",
                icon=":material/edit_calendar:"),
        st.Page("pages/persona_content_impact.py",
                title="Content x Persona impact",
                icon=":material/groups:"),
        st.Page("pages/persona_senior_gaps.py",
                title="Senior gaps",
                icon=":material/account_tree:"),
    ],
    "Email": [
        st.Page("pages/email_performance.py",
                title="This week's numbers",
                icon=":material/insights:"),
        st.Page("pages/marketing_rolling_report.py",
                title="Rolling marketing report",
                icon=":material/calendar_month:"),
        st.Page("pages/email_winners_diagnostic.py",
                title="Winners diagnostic",
                icon=":material/emoji_events:"),
    ],
    "LinkedIn": [
        st.Page("pages/linkedin_explore.py",
                title="What worked",
                icon=":material/analytics:"),
        st.Page("pages/linkedin_visualize.py",
                title="See the pattern",
                icon=":material/bar_chart:"),
        st.Page("pages/linkedin_recommend.py",
                title="Draft the next post",
                icon=":material/lightbulb:"),
    ],
})
pg.run()
