# GrantsNow Performance Matrix — current version

Every page in the app today, grouped by sidebar section, with a one-line
description and a one-line "how it helps" note.

## Overview

| Page | What it does | How it helps |
|---|---|---|
| **Sales director view** *(default)* | Single scrollable page with coverage, contacts by persona, warm leads, monthly cadence, top opportunities, next actions | Monday-morning briefing with no filters — everything you need to run the week |
| **Weekly pulse** | Week-by-week table of email + LinkedIn + web numbers with per-week drill | Cross-channel health check in one view — spot the week when something moved |
| **Home** | Three summary cards + auto-written weekly brief + rule-based action queue + first-visit onboarding | Fast landing that answers "where are we today and what should I click on" |
| **Board pack** | One-page print-ready snapshot with brief, headline numbers, open-rate line, tracked-campaign leaderboard, next actions | Ctrl-P into a PDF for board meetings — no manual formatting |

## LinkedIn — Post Performance Matrix

| Page | What it does | How it helps |
|---|---|---|
| **What worked** | Every LinkedIn post as a dot on the year, click any to compare against the top performer, sidebar to filter | See which posts landed and copy their pattern |
| **See the pattern** | Reveals what actually drives the score (writing choice, image type, day of week, hashtag mix) as plain-English "winners average X vs the rest Y" | Turns "our top posts were great" into "here's the recipe that keeps winning" |
| **Draft the next post** | Paste a draft, get a predicted score before publishing, plus a photo upload + auto-analysis | Kills bad drafts before they cost impressions |
| **Audience** | Follower and visitor demographics across industry, job function, seniority, location, company size + weekly follower growth | Know who's actually following the page — audience-fit for messaging decisions |
| **Competitors** | 6-competitor leaderboard on new followers, engagements per post, posting rhythm | Shows where GrantsNow ranks vs Cayuse / Worktribe / Smart Grant Solutions |

## Email — Performance Matrix

| Page | What it does | How it helps |
|---|---|---|
| **This week's numbers** | Weekly email metrics with open/click trend, cadence, delivery health, best/worst weeks, interested-universities pipeline signal | The main weekly health check for the email programme |
| **Rolling marketing report** | Monthly rollup with sent · delivered · opened · clicks · form completions · enquiries · bounce rate, plus content-type breakdown | Ian's spec #4 — enquiries and forms as the objective, clicks as a stepping stone |
| **Who we can reach** | Audience tiles (send-ready · needs verify · fresh · actionable) + Next Send Builder that produces a stratified CSV of who to email next | Turns 6,456 UK contacts into an actionable weekly send list |
| **Grade our copy** | Scores every marketing-calendar campaign against the GrantsNow drafting pattern (Problem framing + Proof), with scatter, ranking, and per-email drill | Shows which drafts follow the WP5 template and which need a rewrite |
| **Compare sequences** | Cross-batch leaderboard + Base/Follow-up A/Follow-up B side by side with real funnel numbers | Read across a campaign to see whether follow-ups are working |

## Persona

| Page | What it does | How it helps |
|---|---|---|
| **UK Persona Matrix** | Ian's headline deliverable — institution coverage, contacts by persona (Research split into senior/operational/academic), persona gaps, email validity | The one-page summary Ian asked for, driven live by the Contact Audit workbook |
| **Content x Persona impact** | Every tracked email with subject, funnel numbers, scaled recipient persona mix, and MATCH/MISMATCH flag vs the copy target | Answers "which persona is our content actually landing with" |
| **Content vs persona fit** | Word-level segmentation — every email scored 0-100 per persona from weighted vocabulary, with matched-word highlighting in the body | Shows which email in the library is actually right for a Research / Finance / IT seat |
| **Warm leads** | 75 MQLs with real per-person opens, clicks, and sales-contacted status, ranked hottest first | Weekly "who to chase" list for the sales team |
| **Attack list** | The 138 target institutions where we hold all 3 personas today | The full-buying-committee outreach queue — highest deal-velocity accounts |
| **Missing persona list** | For a chosen persona, ranks institutions where that persona is missing, quick wins first | Where to add one contact to complete the buying committee |
| **By institution type** | Coverage split by University / NHS Trust / Research Institute / Charity + drill into any type | Are we over-indexed on Universities and missing other segments? |
| **Deliverability** | Per-persona valid / unknown / not-valid / no-email counts with verify-queue drill | Which persona to send to Snov first for verification |
| **Monthly report** | Per-persona cadence vs Ian's 2/month target (3 cap) with inline data entry for the current month | Exposes the persona cadence gap and lets the team plan next month in the browser |
| **Institution coverage** | Full 726-row institution table with target-only filter, coverage-status filter, name search, per-institution drill | Deep dive when the summary needs auditing |
| **Priority gaps** | 308 gap institutions ranked by priority + top-10 to chase this week | Where to focus the SDR team on any given week |
| **Review queue** | 349 contacts flagged by the auto-tagger for a human eye, grouped by flag reason | Data-ops queue for cleaning up hybrid / uncertain persona tags |
| **Contact directory** | 6,456 contacts filterable by CRM bucket, persona, country, email validity, search across name/title/institution | The "find the right person" search box for anyone at GrantsNow |

---

## Data sources feeding the pages

| CSV | Source workbook | Feeds |
|---|---|---|
| `posts.csv` + LinkedIn CSVs | LinkedIn analytics export | LinkedIn pages |
| `emails.csv` | GrantsNow Task Sheet → Breakdown tab | This week's numbers, Weekly pulse, Compare sequences, Home, Board pack |
| `campaigns.csv` | GrantsNow Marketing Calendar → Email Campaign tab | Grade our copy, Compare sequences, Content vs persona fit |
| `campaign_batches.csv` | Manual entry per tracked send (from Snov PDF/screenshot) | Compare sequences, Content × Persona impact, Content vs persona fit |
| `persona_institution_coverage.csv` + `persona_gaps.csv` + `persona_contacts_full.csv` + `persona_review_queue.csv` | Contact Audit workbook (single source of truth for persona data) | Every Persona page |
| `contacts.csv` | Derived from Contact Audit | Who we can reach, Home, Board pack |
| `mql_engaged.csv` | GrantsNow Task Sheet → MQL for SALES tab | Warm leads, Content × Persona impact, Sales director view |
| `persona_email_activity.csv` | Manual entry via the Monthly report page | Monthly report, Sales director view |
| `marketing_report_monthly.csv` + `marketing_by_content_type.csv` | Manual entry via the Rolling marketing report page | Rolling marketing report |
| `competitors.csv` | LinkedIn competitor tracker export | Competitors page |

## How to refresh the data

```bash
# Persona side (Contact Audit workbook)
python etl/persona_data_etl.py    # institution coverage, gaps, review, contacts
python etl/contacts_etl.py        # derived contacts.csv for Audience/Home

# Email side (Task Sheet workbook)
python etl/email_etl.py           # weekly email + LinkedIn + web columns
python etl/mql_etl.py             # per-recipient engagement (MQLs)

# Marketing calendar
python etl/campaign_etl.py        # draft campaigns from the Marketing Calendar
```

The Streamlit loader is keyed by file mtime, so pages pick up new CSVs on the next rerun without any cache clear.
