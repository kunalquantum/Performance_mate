# LinkedIn Performance Matrix (MVP)

A Streamlit dashboard that turns the raw LinkedIn company-page exports into a working
performance matrix: macro page health, post-level performance, and micro content
attributes tested against outcomes.

## Run it

```bash
pip install -r requirements.txt
python etl.py --src /path/to/linkedin/exports --out ./data
streamlit run app.py
```

The `data` folder already holds the processed GrantsNow files, so `streamlit run app.py`
works straight away. Re-run `etl.py` whenever fresh exports arrive.

If the ETL cannot read a `.xls` file, LinkedIn shipped the old BIFF format and `xlrd`
is required. It is in `requirements.txt`. If it still fails, open each file in Excel and
save as `.xlsx`.

## The parameter framework

Three layers. The first two are automatic, the third is a one-time tagging job.

### Layer 1, macro page metrics (from LinkedIn)

| Group | Metrics |
|---|---|
| Reach | Impressions, unique impressions, organic against sponsored |
| Engagement | Reactions, comments, reposts, clicks, engagement rate, CTR |
| Audience | New followers organic, auto-invited, sponsored |
| Destination | Page views and unique visitors by tab and by device |
| Profile | Follower and visitor mix by location, job function, seniority, industry, company size |
| Market | Competitor posts, reactions, comments, new followers |

Derived on top: amplification rate (reposts over impressions), conversation rate
(comments over impressions), engagements per post, share of engagement against the
competitor set, intent gap (visitor share minus follower share).

### Layer 2, micro content attributes (derived from the post copy)

Word count, character count, line breaks, hashtag count and list, link present,
mention count, emoji count, question present, call-to-action type, theme, opening
hook, hook length, length band, format, day of week, midweek flag.

Theme and call-to-action rules live in `etl.py` under `classify_theme` and
`CTA_PATTERNS`. Edit those two blocks as the content strategy changes.

### Layer 3, manual enrichment (LinkedIn does not export these)

`data/post_enrichment_template.csv` carries one row per post and blank columns for:

post_time_local, timezone, target_region, media_type, image_subject,
image_colour_theme, has_face_in_image, text_on_image, headline_on_image,
video_length_sec, video_topic, video_has_captions, campaign, notes.

Fill it in, upload it in the sidebar, and the timing heatmap plus the image and video
attribute breakdowns switch on. Tagging 22 posts takes about 20 minutes.

## Benchmarks used

Company-page engagement rate median sits near 2.1 percent in 2026 published data, with
2 to 5 percent the normal band and above 3.5 percent counted as strong. Organic CTR
above 3 percent reads as strong. Cadence of 3 to 5 posts a week is where reach per post
holds up. Tuesday to Thursday between 10:00 and 14:00 local is the consistent prime
window, weekends drop 45 to 70 percent for B2B. All four are editable in the sidebar.

## What this MVP deliberately leaves out

Dwell time and video view-through are not in the standard export. Lead and pipeline
attribution needs the CRM joined on UTM, which is the natural phase two. Statistical
significance testing is pointless at 22 posts, so the tool flags thin samples instead
of pretending to a confidence level it does not have.
