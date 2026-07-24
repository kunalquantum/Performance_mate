# GrantsNow Performance Matrix

Two apps in one Streamlit page:

- **LinkedIn Post Performance Matrix** — every post scored, compared, and
  used to inform the next draft.
- **Email Performance Matrix** — weekly email metrics, list audience, and
  content analysis against the house drafting pattern.

Switch between the two apps from the sidebar radio at the top.

---

## Folder layout

```
post_performance_matrix/
├── app.py                      # the Streamlit entrypoint
├── scoring.py                  # LinkedIn scoring engine (imported by app)
├── predictor.py                # LinkedIn Recommend mode (imported by app)
├── image_analysis.py           # photo tagging helpers (imported by app)
├── requirements.txt            # pip dependencies
├── README.md
│
├── etl/                        # data-preparation scripts, run on demand
│   ├── email_etl.py            # GrantsNow Task Sheet -> data/emails.csv
│   ├── contacts_etl.py         # GN_UK_Contacts_Cleaned  -> data/contacts.csv
│   ├── campaign_etl.py         # Marketing Calendar      -> data/campaigns.csv
│   ├── etl.py                  # LinkedIn analytics exports -> data/posts.csv
│   ├── build_enrichment.py     # LinkedIn post enrichment helpers
│   ├── merge_enrichment.py
│   └── map_screenshots_to_export.py
│
├── sources/                    # source spreadsheets the ETLs read
│   ├── GrantsNow Task Sheet.xlsx
│   ├── GN_UK_Contacts_Cleaned.xlsx
│   ├── GrantsNow Marketing Calendar (1).xlsx
│   ├── GrantsNow_LinkedIn_Hashtags.xlsx
│   └── LinkedIn_Hashtags_Library.xlsx
│
├── references/                 # reference material for pattern calibration
│   └── Contents/Emails/*.docx  # WP5 house pattern reference
│
├── data/                       # generated CSVs the app reads at runtime
│   ├── posts.csv
│   ├── emails.csv
│   ├── contacts.csv
│   ├── campaigns.csv
│   └── ...                     # LinkedIn diagnostics + enrichment CSVs
│
├── _archive/                   # quarantined stale material, safe to delete
│   ├── linkedin_performance_matrix/
│   ├── PROJECT_PLAN_post_performance_matrix.md
│   ├── docs.html
│   └── GN_UK_Contacts_Cleaned_2.xlsx
│
└── venv/                       # local virtualenv (not committed)
```

---

## Setup

From `post_performance_matrix/`:

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# or: source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

---

## Regenerating the data

Every ETL reads a file from `sources/` and writes a CSV into `data/`. The
Streamlit `@st.cache_data` on the loader is keyed by file mtime, so running
an ETL and re-running the app is enough. No manual cache clear needed.

```bash
python etl/email_etl.py         # rebuild data/emails.csv
python etl/contacts_etl.py      # rebuild data/contacts.csv
python etl/campaign_etl.py      # rebuild data/campaigns.csv
python etl/etl.py --src <path>  # rebuild LinkedIn CSVs from a raw export
```

To point an ETL at a different source file, pass `--src`:

```bash
python etl/contacts_etl.py --src sources/GN_UK_Contacts_Cleaned_v2.xlsx
```

---

## Running the app

```bash
streamlit run app.py
```

Then in the browser:

1. **Sidebar** — pick the app: *LinkedIn Post Matrix* or *Email Performance Matrix*.
2. **Top of page** — pick the screen for that app.

The LinkedIn app has three screens: **Explore**, **Visualize**,
**Recommend**. The Email app has three screens: **Performance**,
**Audience**, **Contents analysis**.

---

## How this earns its keep

Both apps follow the same rule: if a chart, tile, or panel does not help
someone decide what to publish next, it does not get built. Every screen is
judged against whether it changes the next action.
