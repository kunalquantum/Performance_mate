"""
GrantsNow Performance Matrix - multi-page Streamlit entrypoint.

Two apps grouped in the sidebar navigation:
    LinkedIn Post Performance Matrix   (Explore / Visualize / Recommend)
    Email Performance Matrix           (Performance / Audience / Contents)

Run:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="GrantsNow Performance Matrix",
                    layout="wide", page_icon="○")

pg = st.navigation({
    "LinkedIn": [
        st.Page("pages/linkedin_explore.py",
                title="Explore",
                icon=":material/analytics:",
                default=True),
        st.Page("pages/linkedin_visualize.py",
                title="Visualize",
                icon=":material/bar_chart:"),
        st.Page("pages/linkedin_recommend.py",
                title="Recommend",
                icon=":material/lightbulb:"),
    ],
    "Email": [
        st.Page("pages/email_performance.py",
                title="Performance",
                icon=":material/insights:"),
        st.Page("pages/email_audience.py",
                title="Audience",
                icon=":material/group:"),
        st.Page("pages/email_contents.py",
                title="Contents analysis",
                icon=":material/rate_review:"),
    ],
})
pg.run()
