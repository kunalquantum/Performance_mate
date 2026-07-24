# Project Plan: LinkedIn Post Performance Matrix

Build brief for Claude Code. Read this file first, then build in the phase order given.

---

## 1. The business requirement

The business needs to answer one question about the LinkedIn company page:

**Which posts performed, which did not, and what attributes explain the difference.**

The output goes to two people. The copywriter needs to know what to write. The designer
needs to know what to put in the image. Neither of them wants to read an analytics
report and work it out themselves.

Everything in this build is judged against that. If a screen does not help someone
decide what to publish next, it does not get built.

### Out of scope

Page-level reporting, follower growth charts, competitor share of voice, visitor
traffic dashboards, ad performance. LinkedIn already reports all of it. Adding it here
buries the one thing the business actually asked for.

---

## 2. The interface decision

**One page. No tabs.** A multi-tab tool makes the reader hunt for the answer. The page
scrolls in the order a person actually thinks:

```
[ Filter bar ]  date range | exclude one-off event posts | scope selector

SECTION 1   What worked and what did not
            Every post as a row, ranked, with a verdict and the reason.
            This is the screen people will spend their time on.

SECTION 2   The attributes behind the results
            Which content attributes track with strong posts, ranked by
            effect, each carrying a sample size and a confidence flag.

SECTION 3   The brief for the next post
            The specification derived from the winning posts, plus what
            the losing posts have in common. Copyable as text.
```

Three sections, one scroll. Method notes and the parameter catalogue go in a
collapsed expander at the bottom, not in a tab.

---

## 3. Why a post needs a baseline, not an average

Raw engagement rate is not comparable across weeks. A post published during a
conference and a post published on a quiet Tuesday are not competing under the same
conditions. Ranking them on raw engagement rate says the conference week was good
content, which tells the copywriter nothing they can use.

So every post is compared with the posts published around it, excluding itself, using a
rolling median of 7 neighbours. That produces three ratios:

- **reach index**, impressions against baseline
- **engagement index**, engagement rate against baseline
- **click index**, click-through rate against baseline

A value of 1.00 means the post did exactly what the posts around it did.

---

## 4. The verdict logic

The three indices are read separately, not blended, because different combinations mean
different problems and go to different people.

| Reach | Engagement | Clicks | Verdict | Fix owner |
|---|---|---|---|---|
| up | up | any | Won on both | Repeat the shape |
| down | up | any | Distribution failure | Scheduling. The writing worked, the slot did not |
| up | down | any | Hook failure | Copywriter and designer |
| any | up | down | Offer failure | Whoever owns the call to action |
| any | any | up, no comments | Shallow engagement | Copywriter, add something to reply to |
| down | down | any | Retire it | Nobody, drop the format |
| otherwise | | | At baseline | No signal, needs a sharper angle |

Thresholds: up means 1.15 or above, down means 0.85 or below. Put these in a constants
block so they can be argued with.

**This split is the product.** A distribution failure and a hook failure look identical
in a normal engagement report and they need opposite responses. Any build that loses
this distinction has failed the brief.

A separate composite score out of 100 gives the ranking: percentile rank of reach
index, weighted engagement quality and click index, blended 35, 45 and 20 percent.
Weighted engagement counts a comment as 6, a repost as 4, a click as 2 and a reaction
as 1, because LinkedIn ranking leans on comment velocity in the first hour. Expose
those four weights as sliders.

---

## 5. The attribute layers

Three layers. Two are automatic. The third is the one that unlocks the designer.

### Layer 1, outcome metrics, straight from the LinkedIn export

Impressions, unique impressions, clicks, click-through rate, reactions, comments,
reposts, engagement rate, post type, content type, created date.

### Layer 2, content attributes, derived from the post copy in code

Word count, character count, opening hook, hook length, length band, line breaks,
hashtag count, hashtag set, link present, mention count, emoji count, question present,
call to action type, angle or theme, day of week.

Angle and call to action are regex rule sets. Keep them in one editable block so the
taxonomy can change as the content strategy changes. Starting rules:

Angle: event presence, product capability, pain point, thought leadership, community
celebration, other.
Call to action: download, book demo, learn more, read, register, contact, none.

### Layer 3, creative attributes, manual tagging

LinkedIn exports none of this and it is the entire reason the designer currently gets
no answer:

post time local, timezone, target region, media type, image subject, image colour
theme, face in image, text on image, headline on image, video length, video topic,
video captions, campaign.

Ship a CSV template with one row per post and these columns blank. The tool merges an
uploaded tagging file on post id. Once merged, these attributes flow through the same
attribute analysis as everything else with no extra code.

**Tagging the existing posts is the highest-value hour of work in this project.** Until
it is done the tool advises the copywriter and stays silent on the visuals.

---

## 6. Confidence handling

The dataset is small. The tool must never present a pattern as a finding when it rests
on two posts.

Every attribute result carries a flag based on sample size:

- **usable**, 5 or more posts, act on it
- **thin**, 3 or 4 posts, test it
- **anecdote**, 1 or 2 posts, ignore until it repeats

Show the flag next to every number. Do not compute p-values, do not show confidence
intervals, do not imply significance that does not exist.

---

## 7. Known data traps to handle in code

**Conference weeks distort everything.** One week of event posts carries most of the
reach in the current data. Provide a filter to exclude them, and when the top quartile
is more than 40 percent event content, show a warning on the brief saying the
recommendation cannot be executed on a normal week.

**Click counts on multi-image and document posts are not link clicks.** They include
gallery and document expands. One post in the current data shows a click-through rate
above 80 percent, which is not real. Flag any post above 35 percent rather than scoring
it.

**Articles carry no post copy in the export.** The post title field comes through
empty. Do not let them score as zero-word posts, label them clearly.

**LinkedIn exports .xls in the old BIFF format.** Requires xlrd 2.0.1 or later. If the
import fails, convert with LibreOffice before parsing.

**Post date has no time component.** Time of day analysis is impossible until the
tagging layer exists. Say so in the interface rather than showing an empty chart.

---

## 8. File structure

```
post_performance_matrix/
  app.py            single page interface, no tabs
  scoring.py        baselines, indices, verdicts, attribute lift, brief builder
  etl.py            reads LinkedIn exports, derives layer 2 attributes, writes CSVs
  requirements.txt
  README.md
  data/
    posts.csv                       one row per post, all layer 1 and 2 attributes
    post_enrichment_template.csv    blank layer 3 tagging sheet
    followers_*.csv                 audience mix, used only in the brief section
    visitors_*.csv                  audience mix, used only in the brief section
```

Keep all thresholds, weights and regex rules in named constants at the top of the file
they belong to. No values buried in function bodies.

---

## 9. Build phases

### Phase 1, data layer

Parse the four LinkedIn export types. Derive every layer 2 attribute. Write posts.csv
and the tagging template.

Acceptance: posts.csv has one row per post with no nulls in the derived attribute
columns, and re-running the ETL on new exports appends without duplicating.

### Phase 2, scoring engine

Baselines, three indices, weighted engagement, composite score, verdict assignment,
anomaly flags.

Acceptance: no post is part of its own baseline, at least 70 percent of posts receive a
verdict other than at baseline, and the anomalous click post is flagged rather than
ranked first.

### Phase 3, attribute analysis

Median outcome per attribute value against the page median, with sample size and
confidence flag. Per-post explanation that names which of its attributes helped or
hurt.

Acceptance: every post row can state at least one reason, or state plainly that no
attribute stands out. Never leave the reason blank.

### Phase 4, single-page interface

Section 1 post list with verdicts. Section 2 attribute evidence. Section 3 next-post
brief with a copy button. Filters at the top. Method and parameter catalogue in a
collapsed expander.

Acceptance: a person who has never seen the tool can name the three best posts, say why
they worked, and read the next-post specification without clicking anything except the
filters.

### Phase 5, creative layer

Tagging upload, merge on post id, layer 3 attributes flowing into section 2 and section
3 automatically.

Acceptance: after uploading a tagged file, image and timing attributes appear in the
attribute evidence with the same confidence treatment, and the brief starts naming the
image specification.

---

## 10. What this does not attempt

Dwell time is not in the export and it is one of the strongest ranking signals, so a
post read slowly and a post scrolled past look the same here. Say this in the method
notes rather than hiding it.

Lead and pipeline attribution needs the CRM joined on the campaign field. That is a
separate project once the campaign column is being filled in reliably.

Causal claims. The tool shows which attributes travel with strong posts. It does not
prove they caused anything, and the copy in the interface must not suggest otherwise.

The matrix becomes trustworthy at roughly 60 to 80 posts with the creative layer
tagged. Until then it is a structured way to argue about content, which still beats the
alternative.

---

## 11. Writing rules for all interface copy

No em dashes anywhere, in code comments, interface text, README or generated output.
Run a check before shipping.

No metaphors. No idioms. Use the word manually instead of the phrase meaning the same
thing with hands. Do not join two sentences with a semicolon. Name the specific thing
rather than using a vague word that assumes the reader already knows. No italics.

Interface copy is written for the copywriter and the designer, not for an analyst. Say
what to do, not what the number is.
