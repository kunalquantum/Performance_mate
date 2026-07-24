"""
Build the manual enrichment CSV from per-post captures.

Every post is a dict of visual + judgement fields. This script auto-computes the
text metrics (first-line chars, hook type shape, word count, sentence count,
paragraph count, reading grade, bullet/emoji counts, hashtag count) from the
caption so the human tagger never has to count by hand.

Run:
    python build_enrichment.py
"""

import re
import csv
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
OUT = os.path.join(DATA_DIR, "post_enrichment_manual.csv")

EMOJI_RE = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f1e6-\U0001f1ff" "]",
    flags=re.UNICODE,
)
HASHTAG_RE = re.compile(r"#(\w+)")
MENTION_RE = re.compile(r"@(\w+)")
URL_RE = re.compile(r"https?://\S+")
BULLET_RE = re.compile(r"(?m)^\s*[\-\*•●▪→✅✔✓☑►▶]")

SEEMORE_CUTOFF = 210  # LinkedIn feed usually shows about this much before "see more"


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _syllables(word):
    """Rough syllable count, good enough for Flesch grade."""
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _flesch_kincaid(text):
    """Approximate Flesch-Kincaid grade level."""
    body = URL_RE.sub("", text)
    body = HASHTAG_RE.sub("", body)
    words = re.findall(r"[a-zA-Z]+", body)
    sents = _sentences(body)
    if not words or not sents:
        return None
    syl = sum(_syllables(w) for w in words)
    grade = 0.39 * (len(words) / len(sents)) + 11.8 * (syl / len(words)) - 15.59
    return round(grade, 1)


def auto_text_fields(caption):
    body = caption or ""
    body_wo_url = URL_RE.sub("", body)
    body_wo_all = HASHTAG_RE.sub("", body_wo_url)

    lines = body.split("\n")
    first_line = next((ln.strip() for ln in lines if ln.strip()), "")

    first_para = body.split("\n\n", 1)[0].strip()
    pre_hook_complete = len(first_para) <= SEEMORE_CUTOFF

    words = body_wo_all.split()
    sents = _sentences(body_wo_all)
    paragraphs = [p for p in body.split("\n\n") if p.strip()]

    fl_lower = first_line.lower()
    if first_line.endswith("?"):
        first_line_type = "question"
    elif re.match(r"^\d", first_line) or re.search(r"\d+%", first_line):
        first_line_type = "stat_or_number"
    elif first_line.isupper() and len(first_line) > 4:
        first_line_type = "bold_claim_allcaps"
    elif re.match(r"^(when|imagine|last|the day|in \d)\b", fl_lower):
        first_line_type = "story_open"
    elif re.match(r"^(you|your|are you|do you|ever)\b", fl_lower):
        first_line_type = "direct_address"
    else:
        first_line_type = "statement"

    hashtags = HASHTAG_RE.findall(body)
    at_mentions = MENTION_RE.findall(body)
    bullets = len(BULLET_RE.findall(body))
    # bullets that fall in the emoji range would otherwise double-count as emojis;
    # subtract them so 'emoji_count' means decorative emojis only
    emojis = max(0, len(EMOJI_RE.findall(body)) - bullets)

    has_bold_unicode = bool(re.search(r"[\U0001D400-\U0001D7FF]", body))
    caps_words = [w for w in re.findall(r"[A-Za-z]+", body_wo_all)
                  if len(w) > 3 and w.isupper()]

    return {
        "first_line": first_line,
        "first_line_chars": len(first_line),
        "first_line_type": first_line_type,
        "pre_seemore_chars": min(len(body), SEEMORE_CUTOFF),
        "pre_seemore_hook_complete": "yes" if pre_hook_complete else "no",
        "word_count": len(words),
        "sentence_count": len(sents),
        "paragraph_count": len(paragraphs),
        "avg_sentence_words": (round(len(words) / len(sents), 1)
                               if sents else None),
        "reading_grade": _flesch_kincaid(body),
        "has_bullets": "yes" if bullets else "no",
        "bullet_count": bullets,
        "has_emojis": "yes" if emojis else "no",
        "emoji_count": emojis,
        "has_bold_or_caps_emphasis":
            "yes" if (has_bold_unicode or len(caps_words) >= 2) else "no",
        "hashtag_count": len(hashtags),
        "hashtags": ", ".join(f"#{h}" for h in hashtags),
        "at_mentions": ", ".join(f"@{m}" for m in at_mentions),
        "urls_in_caption": ", ".join(URL_RE.findall(body)),
    }


# ---------------------------------------------------------------------------
# per-post captures
# each dict = the fields I judge or see; text metrics are added by auto_text_fields.
# ---------------------------------------------------------------------------

POSTS = [
    {
        "post_id": "SS001", "batch": "batch1",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Every proposal generates questions, feedback, and approvals. When "
            "they're managed across email, finding the right information becomes "
            "difficult, especially as submission volumes grow.\n\n"
            "Learn how a single proposal record keeps every conversation in one "
            "place.\n"
            "Download the whitepaper: https://lnkd.in/e8u_9AzK\n\n"
            "#GrantsNow #Research #PreAwards #GrantsManagement"
        ),
        "value_prop_line": "A single proposal record keeps every conversation in one place.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "proposal, submissions, whitepaper, grants management, research, pre-awards",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "illustration",
        "image_subject": "envelope with red notification badge",
        "background_type": "solid",
        "background_dominant_colour": "dark teal",
        "foreground_dominant_colour": "yellow envelope + white card + red badge",
        "palette": "brand-teal + gold + accent-red",
        "contrast_level": "high",
        "texture": "flat illustration",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "envelope with red 7 notification",
        "text_on_image": "yes",
        "headline_on_image": "Still managing proposal reviews by email?",
        "headline_style": "mixed-weight bold",
        "headline_chars": 41,
        "subheadline_on_image": "There's a better way.",
        "image_cta_text": "Download the Whitepaper",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners",
        "graphic_style": "minimal flat with iconography",
        "notable_element": "red '7' notification badge - urgency + inbox metaphor",
        "campaign": "whitepaper - proposal reviews",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS002", "batch": "batch1",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "Proposal feedback, peer reviews, and approvals shouldn't disappear "
            "into inboxes. Discover how keeping every discussion linked to the "
            "proposal improves collaboration, visibility, and audit readiness.\n\n"
            "Download the whitepaper: https://lnkd.in/e8u_9AzK\n\n"
            "#GrantsNow #Research #PreAwards #GrantsManagement"
        ),
        "value_prop_line": "Keeping every discussion linked to the proposal improves collaboration, visibility, and audit readiness.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "proposal, peer reviews, approvals, audit readiness, grants management",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "mixed - photo + illustration",
        "image_subject": "laptop workspace photo (top) + product panel (bottom)",
        "background_type": "photographic (top) + solid (bottom)",
        "background_dominant_colour": "warm neutral photo + white",
        "foreground_dominant_colour": "orange envelope + teal accent",
        "palette": "brand-teal + accent-orange + neutral",
        "contrast_level": "medium",
        "texture": "mixed - photo realistic and flat",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "envelope on laptop screen + notepad and pen",
        "text_on_image": "yes",
        "headline_on_image": "Your proposal discussions belong with the proposal",
        "headline_style": "mixed-weight bold",
        "headline_chars": 50,
        "subheadline_on_image": "Not scattered across email",
        "image_cta_text": "Download the Whitepaper",
        "brand_marks": "GrantsNow logo",
        "brand_placement": "top of product panel",
        "graphic_style": "editorial photo over minimal product mock",
        "notable_element": "split composition - human workspace context above, product answer below",
        "campaign": "whitepaper - proposal reviews",
        "angle": "pain_point",
    },
    {
        "post_id": "SS003", "batch": "batch1",
        "view_completeness": "bottom-cropped", "cta_confidence": "unknown",
        "caption": (
            "GrantsNow uses AI to surface relevant funding opportunities based on "
            "your research areas, favourite funders and team preferences. The right "
            "calls find you, not the other way around.\n\n"
            "Book a demo: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsManagement #AIinResearch #Funding #ResearchOffice #HigherEducationUK"
        ),
        "value_prop_line": "The right calls find you, not the other way around.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "AI, funding opportunities, research areas, funders, higher education, research office",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "book_demo",
        "cta_verb": "Book",
        "has_question_prompt": "no",
        "hashtag_style": "niche + audience-targeted (UK higher ed)",
        "media_type": "image",
        "primary_visual": "typography",
        "image_subject": "magnifying glass illustration",
        "background_type": "solid",
        "background_dominant_colour": "cream / off-white",
        "foreground_dominant_colour": "dark teal typography + grey magnifying glass",
        "palette": "brand-teal on cream",
        "contrast_level": "medium",
        "texture": "flat with subtle drop shadow",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "magnifying glass (bottom right)",
        "text_on_image": "yes",
        "headline_on_image": "Stop manually searching for funding calls.",
        "headline_style": "mixed-weight bold (manually + searching in heavy weight)",
        "headline_chars": 43,
        "subheadline_on_image": "",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners",
        "graphic_style": "editorial minimal typography-led",
        "notable_element": "headline-only creative - no CTA button visible in the crop, quieter than SS001/SS002",
        "campaign": "demo - AI funding discovery",
        "angle": "product_capability",
    },
    {
        "post_id": "SS004", "batch": "batch1",
        "view_completeness": "top-cropped", "cta_confidence": "verified",
        "caption": (
            "[Newsletter share - caption not visible in the screenshot; "
            "renders as a LinkedIn Newsletter card]"
        ),
        "value_prop_line": "Keep proposal reviews and approvals in one place",
        "value_prop_in_first_3_sentences": "n/a",
        "industry_keywords": "proposal reviews, approvals, grant scope, newsletter",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "newsletter",
        "cta_placement": "n/a - newsletter card",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "n/a - caption cropped",
        "media_type": "newsletter",
        "primary_visual": "typography",
        "image_subject": "two-panel brand card - GrantScope mark + newsletter headline",
        "background_type": "solid",
        "background_dominant_colour": "dark teal (left) + white (right)",
        "foreground_dominant_colour": "white text (left) + dark teal text (right)",
        "palette": "brand-teal + white",
        "contrast_level": "high",
        "texture": "flat brand card",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "GrantScope wordmark (left panel)",
        "text_on_image": "yes",
        "headline_on_image": "Keep proposal reviews & approvals in one place",
        "headline_style": "mixed-weight bold",
        "headline_chars": 46,
        "subheadline_on_image": "",
        "image_cta_text": "",
        "brand_marks": "GrantScope mark + GrantsNow logo",
        "brand_placement": "split panels",
        "graphic_style": "newsletter brand card",
        "notable_element": "newsletter format - Register button in the header instead of an in-image CTA",
        "campaign": "GrantScope newsletter",
        "angle": "thought_leadership",
    },
    {
        "post_id": "SS006", "batch": "batch2",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Proposal rework can become difficult to manage when feedback, "
            "document changes, and approvals are spread across multiple email "
            "threads.\n\n"
            "Our latest whitepaper explores how keeping every discussion and "
            "decision linked to the proposal can improve collaboration, provide "
            "greater visibility, and help research teams keep submissions moving "
            "forward.\n\n"
            "Download the free whitepaper: https://lnkd.in/gZQqbfDX\n\n"
            "#GrantsNow #Whitepaper #ResearchManagement"
        ),
        "value_prop_line": "Keeping every discussion and decision linked to the proposal improves collaboration, visibility, and momentum.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "proposal rework, feedback, approvals, whitepaper, research management, submissions",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "office scene with people in background + teal product panel",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal photo tint",
        "foreground_dominant_colour": "teal card + WHITEPAPER yellow pill + white type",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes", "face_visible": "partial (background)",
        "number_of_people": 2,
        "object_of_focus": "teal card with headline + WHITEPAPER pill",
        "text_on_image": "yes",
        "headline_on_image": "Keep proposal corrections clear and on track",
        "headline_style": "mixed-weight bold (corrections in heavier weight)",
        "headline_chars": 45,
        "subheadline_on_image": "Discover a better way to manage feedback, rework, and approvals",
        "image_cta_text": "Download the Whitepaper to learn more",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + WHITEPAPER pill + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with centred teal card and full contact strip",
        "notable_element": "phone number and website in footer strip - direct sales cue on a whitepaper post",
        "campaign": "whitepaper - proposal corrections",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS007", "batch": "batch2",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Missed feedback and multiple document versions can put funding "
            "applications at risk. Explore how a structured approach to proposal "
            "corrections helps universities reduce administrative effort and "
            "improve submission quality.\n\n"
            "Download the whitepaper:\n"
            "https://lnkd.in/gZQqbfDX\n\n"
            "#GrantsNow #Whitepaper"
        ),
        "value_prop_line": "A structured approach to proposal corrections reduces administrative effort and improves submission quality.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "feedback, document versions, funding applications, proposal corrections, universities, submission quality",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "no",
        "hashtag_style": "brand only (very light)",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "woman working with laptop in background + teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal photo tint",
        "foreground_dominant_colour": "teal card + WHITEPAPER yellow pill + white type",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes", "face_visible": "yes (soft focus)",
        "number_of_people": 1,
        "object_of_focus": "teal card with question headline + WHITEPAPER pill",
        "text_on_image": "yes",
        "headline_on_image": "Are proposal reworks slowing submissions?",
        "headline_style": "mixed-weight bold (proposal reworks in heavier weight)",
        "headline_chars": 42,
        "subheadline_on_image": "Download the Whitepaper to learn more",
        "image_cta_text": "Download the Whitepaper to learn more",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + WHITEPAPER pill + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with centred teal card - question in the image",
        "notable_element": "question in the image headline - first image-headline question so far - direct challenge to the reader",
        "campaign": "whitepaper - proposal corrections",
        "angle": "pain_point",
    },
    {
        "post_id": "SS008", "batch": "batch2",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Manually pulling together proposal details from multiple sources "
            "before you have even started writing is time nobody can afford. "
            "GrantsNow auto-populates your outline proposal directly from the "
            "funding call, cutting the admin so your researchers can focus on "
            "what actually wins Grants.\n\n"
            "Would you like to know more? Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsManagement #PreAward #ResearchOffice #UKUniversities #AIinResearch"
        ),
        "value_prop_line": "GrantsNow auto-populates your outline proposal directly from the funding call, cutting admin so researchers can focus on winning grants.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "manual proposal, funding call, admin, researchers, AI, pre-award, research office, UK universities",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "niche + audience-targeted (UK higher ed)",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "team meeting photo (top) + teal panel with question (bottom)",
        "background_type": "photographic (top) + solid teal (bottom)",
        "background_dominant_colour": "dark teal + photo",
        "foreground_dominant_colour": "white type + teal checkmark + white 'We can help' pill",
        "palette": "brand-teal + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint + flat solid teal",
        "person_present": "yes", "face_visible": "partial (backs of heads)",
        "number_of_people": 3,
        "object_of_focus": "large question headline + 'We can help' response",
        "text_on_image": "yes",
        "headline_on_image": "Is your team spending more time on admin than on the actual bid?",
        "headline_style": "mixed-weight bold (more time in heavier weight)",
        "headline_chars": 64,
        "subheadline_on_image": "We can help!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "split panel photo-plus-solid teal, big question hook",
        "notable_element": "explicit question in caption AND image - hard sell with phone number as CTA",
        "campaign": "demo - AI auto-populate",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS009", "batch": "batch2",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Role-based access helps universities give researchers, reviewers, "
            "finance teams, and administrators access only to the information "
            "they need, improving security, collaboration, and governance across "
            "the research funding lifecycle.\n\n"
            "Download our whitepaper to learn more:\n"
            "https://lnkd.in/eVuMpbP2\n\n"
            "#ResearchManagement #GrantManagement #HigherEducation #ResearchFunding "
            "#DataGovernance #ResearchSupport #GrantsNow"
        ),
        "value_prop_line": "Role-based access gives each user access only to what they need, improving security, collaboration, and governance.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "role-based access, universities, researchers, reviewers, finance teams, data governance, research funding lifecycle, higher education",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad + niche - very heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "photo + white card overlay with orange border",
        "image_subject": "woman at computer in background + cream card with orange rounded border",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal photo tint",
        "foreground_dominant_colour": "cream card + orange border + teal type + yellow CTA button",
        "palette": "brand-teal + gold + accent-orange",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint + flat card",
        "person_present": "yes", "face_visible": "partial (soft focus)",
        "number_of_people": 1,
        "object_of_focus": "cream card with orange border and yellow CTA button",
        "text_on_image": "yes",
        "headline_on_image": "Role-Based Access That Simplifies Research Management",
        "headline_style": "title-case mixed-weight bold",
        "headline_chars": 53,
        "subheadline_on_image": "The Right People. The Right Access. Every Time.",
        "image_cta_text": "Download the Whitepaper to learn more",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with cream card and prominent yellow button",
        "notable_element": "yellow CTA button (only post in the set with a filled yellow button) + 7 hashtags (heaviest in the set)",
        "campaign": "whitepaper - role-based access",
        "angle": "product_capability",
    },
    {
        "post_id": "SS010", "batch": "batch2",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Are manual proposal updates across emails or spreadsheets slowing "
            "down your bid process? GrantsNow gives everyone a single dashboard "
            "with full visibility of every proposal, tailored to their "
            "dept/role.\n\n"
            "We would be happy to connect: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsManagement #ResearchOffice #PreAward #UKUniversities "
            "#HigherEducationUK"
        ),
        "value_prop_line": "GrantsNow gives everyone a single dashboard with full visibility of every proposal, tailored to their dept and role.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "manual proposal updates, emails, spreadsheets, bid process, single dashboard, research office, pre-award, UK universities",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Connect",
        "has_question_prompt": "yes",
        "hashtag_style": "niche + audience-targeted (UK higher ed)",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "woman at desk with monitor in background + teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "muted green-grey office photo",
        "foreground_dominant_colour": "teal card + cream border + white type",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with subtle desaturation",
        "person_present": "yes", "face_visible": "yes (side profile)",
        "number_of_people": 1,
        "object_of_focus": "teal card with question - manual proposal tracking phrase in bold",
        "text_on_image": "yes",
        "headline_on_image": "Is your research office held back with manual proposal tracking?",
        "headline_style": "mixed-weight bold (manual proposal tracking in heavier weight)",
        "headline_chars": 61,
        "subheadline_on_image": "",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with centred teal card, headline-only in image",
        "notable_element": "question in both caption first line and image headline - most on-message hook of the batch",
        "campaign": "demo - dashboard visibility",
        "angle": "pain_point",
    },
    {
        "post_id": "SS011", "batch": "batch3",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Still managing grants across emails, spreadsheets, and disconnected "
            "systems? Learn how universities are simplifying the grants lifecycle "
            "with a single, integrated platform.\n\n"
            "Download the whitepaper: https://lnkd.in/g8AanByU\n\n"
            "#GrantsNow #Research #Universities"
        ),
        "value_prop_line": "Universities are simplifying the grants lifecycle with a single, integrated platform.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "grants, emails, spreadsheets, disconnected systems, grants lifecycle, integrated platform, universities",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "typography on gradient",
        "image_subject": "cream-to-mint gradient with teal card and yellow CTA",
        "background_type": "gradient",
        "background_dominant_colour": "cream to soft mint",
        "foreground_dominant_colour": "dark teal card + orange border + yellow CTA",
        "palette": "brand-teal + gold + cream",
        "contrast_level": "high",
        "texture": "flat gradient with subtle grid",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "teal card with orange border and yellow CTA button",
        "text_on_image": "yes",
        "headline_on_image": "Managing Research Grants Shouldn't Mean Managing Multiple Systems",
        "headline_style": "title-case mixed-weight bold",
        "headline_chars": 63,
        "subheadline_on_image": "Want to know how we can help?",
        "image_cta_text": "Download the Whitepaper to learn more",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "no-photo poster - all typography and card",
        "notable_element": "yellow CTA pill button + orange card border (rare accent) and a sub-question inviting a reply",
        "campaign": "whitepaper - integrated platform",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS012", "batch": "batch3",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "We know every funder has different rules, manually looking this up "
            "over lots of funders takes up valuable time.\n\n"
            "GrantsNow's AI does the checking instantly, so your researchers "
            "spend their time writing, not reading guidance notes.\n\n"
            "Book a demo: https://lnkd.in/dU2Brsef\n"
            "#GrantsManagement #AIinResearch #PreAward #ResearchOffice #UKUniversities"
        ),
        "value_prop_line": "GrantsNow's AI does the eligibility checking instantly, so researchers write instead of reading guidance notes.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "funder rules, eligibility, AI, researchers, guidance notes, pre-award, research office, UK universities",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "book_demo",
        "cta_verb": "Book",
        "has_question_prompt": "no",
        "hashtag_style": "niche + audience-targeted (UK higher ed)",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "team meeting photo (four people) with teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal photo tint",
        "foreground_dominant_colour": "teal card + cream border + white type",
        "palette": "brand-teal + photographic + cream",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes", "face_visible": "yes (multiple faces)",
        "number_of_people": 4,
        "object_of_focus": "question headline + 'We can help' response with checkmark",
        "text_on_image": "yes",
        "headline_on_image": "Are your teams struggling with eligibility checks that slows everything down?",
        "headline_style": "mixed-weight bold (eligibility checks in heavier weight)",
        "headline_chars": 78,
        "subheadline_on_image": "We can help!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with centred teal card and 'We can help' response",
        "notable_element": "most people in a single image so far (4) + long question headline (78 chars)",
        "campaign": "demo - AI eligibility checks",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS013", "batch": "batch3",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Unlock more funding opportunities with less effort. Want to know how? "
            "Set up a demo - https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #Funding #GrantsManagement"
        ),
        "value_prop_line": "Increase your grant funding opportunities by 25% with the Funder Opportunity Scanner.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "funding opportunities, funder opportunity scanner, grants management, grant funding",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "book_demo",
        "cta_verb": "Set up",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "typography on dark gradient",
        "image_subject": "dark teal gradient with subtle wave lines and headline stat",
        "background_type": "gradient",
        "background_dominant_colour": "dark teal to green",
        "foreground_dominant_colour": "white type",
        "palette": "brand-teal (dark) + white",
        "contrast_level": "high",
        "texture": "flat gradient with wave line motif",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the 25% stat inside the headline",
        "text_on_image": "yes",
        "headline_on_image": "Increase your grant funding opportunities by 25% with the Funder Opportunity Scanner",
        "headline_style": "mixed-weight (numbers not visually enlarged)",
        "headline_chars": 88,
        "subheadline_on_image": "Don't believe it?",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "typography-only dark poster with stat as hook",
        "notable_element": "first stat-based hook (25%) + provocative 'Don't believe it?' closer - most distinctive tone in the set",
        "campaign": "demo - funder opportunity scanner",
        "angle": "product_capability",
    },
    {
        "post_id": "SS014", "batch": "batch3",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Post-Award management is where the real pressure begins. Reporting "
            "deadlines. Milestone tracking. Funder compliance. Miss one, and you "
            "risk more than a slap on the wrist - you risk your next award.\n\n"
            "Yet most institutions are still managing this with manual trackers "
            "and calendar reminders. It's not a system. It's a gamble.\n\n"
            "GrantsNow gives your team full control of the Post-Award lifecycle:\n"
            "✓ Automated milestone tracking\n"
            "✓ Real-time alerts and notifications\n"
            "✓ End-to-end visibility, from award to close\n\n"
            "Compliant. On track. No deadlines missed.\n\n"
            "Join our webinar to see how AI is making Post-Award management even "
            "smarter: https://lnkd.in/ei2DNPX6"
        ),
        "value_prop_line": "GrantsNow gives your team full control of the Post-Award lifecycle: automated milestone tracking, real-time alerts, end-to-end visibility.",
        "value_prop_in_first_3_sentences": "no (arrives later, after the pain setup)",
        "industry_keywords": "post-award, reporting deadlines, milestone tracking, funder compliance, automated, real-time alerts, AI, pre-awards",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "webinar",
        "cta_placement": "end",
        "cta_type_caption": "register",
        "cta_verb": "Join",
        "has_question_prompt": "no",
        "hashtag_style": "none visible in the screenshot",
        "media_type": "image",
        "primary_visual": "typography on dark gradient",
        "image_subject": "dark teal gradient with UPCOMING WEBINAR badge + question headline + date",
        "background_type": "gradient",
        "background_dominant_colour": "dark teal to green",
        "foreground_dominant_colour": "white type + cream card + green WEBINAR pill",
        "palette": "brand-teal + cream + green pill",
        "contrast_level": "high",
        "texture": "flat gradient with subtle tech graphic",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "cream card with question headline and event date",
        "text_on_image": "yes",
        "headline_on_image": "How can Pre-Awards really benefit from AI?",
        "headline_style": "mixed-weight bold",
        "headline_chars": 42,
        "subheadline_on_image": "Join us on Tuesday 19th May at 12:30pm to discuss how you can use AI to improve your Pre-Awards processes. LAST FEW SEATS LEFT!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + Research Consulting logo TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "webinar poster with badge and event date",
        "notable_element": "first co-branded post (GrantsNow + Research Consulting) + first webinar + first caption with bullet points + urgency signal 'LAST FEW SEATS LEFT'",
        "campaign": "webinar - AI in Pre-Awards",
        "angle": "thought_leadership + product_capability",
    },
    {
        "post_id": "SS015", "batch": "batch3",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "Compliance isn't optional but it is slowing teams down.\n\n"
            "Many institutions are still managing due diligence manually, across "
            "emails, spreadsheets, and disconnected systems. That's where delays "
            "and risk creep in.\n\n"
            "With GrantsNow, compliance and governance are centralised in one "
            "place, with:\n"
            "✓ Automated approval workflows\n"
            "✓ Built-in due diligence tracking\n"
            "✓ Configurable ethics and compliance forms\n\n"
            "Less admin. More confidence. Faster submissions.\n\n"
            "👉 Join our webinar to see how AI is taking this even further."
        ),
        "value_prop_line": "With GrantsNow, compliance and governance are centralised in one place, with automated workflows, due diligence tracking, and configurable ethics forms.",
        "value_prop_in_first_3_sentences": "no (arrives in fourth sentence after pain setup)",
        "industry_keywords": "compliance, due diligence, emails, spreadsheets, approval workflows, ethics, research funding applications",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "webinar",
        "cta_placement": "end",
        "cta_type_caption": "register",
        "cta_verb": "Join",
        "has_question_prompt": "no",
        "hashtag_style": "none visible in the screenshot",
        "media_type": "image",
        "primary_visual": "photo + typography with WEBINAR pill",
        "image_subject": "soft-focus person with dark purple-to-teal gradient overlay and question headline",
        "background_type": "photographic",
        "background_dominant_colour": "dark purple-pink to teal gradient",
        "foreground_dominant_colour": "white type + teal WEBINAR pill",
        "palette": "brand-teal + accent-purple + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy gradient overlay",
        "person_present": "yes", "face_visible": "partial (soft focus)",
        "number_of_people": 1,
        "object_of_focus": "large question headline + WEBINAR pill",
        "text_on_image": "yes",
        "headline_on_image": "Are compliance checks slowing down research funding applications?",
        "headline_style": "mixed-weight (some words in teal accent colour)",
        "headline_chars": 63,
        "subheadline_on_image": "Join us on Tuesday 19th May at 12:30pm to discuss how you can use AI to improve your Pre-Awards processes",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + Research Consulting logo TR + WEBINAR pill",
        "brand_placement": "corners + centered pill",
        "graphic_style": "webinar poster - photo hero with pill and question",
        "notable_element": "purple gradient is the first non-teal accent + emoji in caption (first ever) + accent colouring inside the headline",
        "campaign": "webinar - AI in Pre-Awards",
        "angle": "pain_point + thought_leadership",
    },
    {
        "post_id": "SS016", "batch": "batch4",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "Post-Award management doesn't stop at funding it's where pressure "
            "builds.\n\n"
            "Reporting deadlines. Milestone tracking. Funder requirements.\n"
            "Miss one, and it can impact future funding.\n\n"
            "Many institutions still rely on manual tracking and reminders, "
            "increasing the risk of missed deadlines.\n\n"
            "GrantsNow helps you stay in control with:\n"
            "✓ Automated milestone tracking\n"
            "✓ Real-time alerts and notifications\n"
            "✓ Full visibility across the Post-Award lifecycle\n\n"
            "Stay compliant. Stay on track. Never miss a deadline again.\n\n"
            "Join our webinar to see how AI is taking this even further."
        ),
        "value_prop_line": "GrantsNow helps you stay in control with automated milestone tracking, real-time alerts, and full visibility across the Post-Award lifecycle.",
        "value_prop_in_first_3_sentences": "no (arrives after the pain setup)",
        "industry_keywords": "post-award, reporting deadlines, milestone tracking, funder requirements, manual tracking, AI",
        "tone": "authoritative",
        "pov": "brand-and-you (mixed)",
        "offer_type": "webinar",
        "cta_placement": "end",
        "cta_type_caption": "register",
        "cta_verb": "Join",
        "has_question_prompt": "no",
        "hashtag_style": "none visible in the screenshot",
        "media_type": "image",
        "primary_visual": "photo + typography with WEBINAR pill",
        "image_subject": "soft-focus person with purple-teal gradient overlay + large question headline",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-to-purple gradient",
        "foreground_dominant_colour": "white type + teal WEBINAR pill + teal accent words in headline",
        "palette": "brand-teal + accent-purple + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy gradient overlay",
        "person_present": "yes", "face_visible": "partial (soft focus)",
        "number_of_people": 1,
        "object_of_focus": "very large question headline",
        "text_on_image": "yes",
        "headline_on_image": "What if you never missed a Post-Award submission or reporting deadline again?",
        "headline_style": "mixed-weight bold with teal accent on 'Post-Award submission or reporting deadline'",
        "headline_chars": 79,
        "subheadline_on_image": "Join us on Tuesday 19th May at 12:30pm to discuss how you can use AI to improve your Pre-Awards processes",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + Research Consulting logo TR + WEBINAR pill",
        "brand_placement": "corners + centered pill",
        "graphic_style": "webinar poster - photo hero with big question hook",
        "notable_element": "third webinar poster in a series (SS014, SS015, SS016) - purple gradient variant + accent-coloured words inside the headline",
        "campaign": "webinar - AI in Pre-Awards",
        "angle": "pain_point + thought_leadership",
    },
    {
        "post_id": "SS017", "batch": "batch4",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Many universities wait over a year for their Pre Award system to "
            "connect with finance and HR platforms. GrantsNow delivers clean, pre "
            "built integrations with Oracle cloud so you can go live in less than "
            "half the time faster. Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#University #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "GrantsNow delivers pre-built integrations with Oracle cloud so you can go live in less than half the time.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-award, integrations, finance, HR platforms, Oracle cloud, universities, research management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "action photo (MotoGP racing bike)",
        "image_subject": "MotoGP racing bike with GrantsNow branding, motion blur, rider in green leathers",
        "background_type": "photographic",
        "background_dominant_colour": "green track blur + dark racing photo",
        "foreground_dominant_colour": "green bike + white type",
        "palette": "brand-teal + racing-green + photographic",
        "contrast_level": "high",
        "texture": "action photo with speed blur",
        "person_present": "yes (rider on bike, helmet - face not visible)",
        "face_visible": "no", "number_of_people": 1,
        "object_of_focus": "the racing bike + '18+ months?' hook",
        "text_on_image": "yes",
        "headline_on_image": "Do Pre-Awards integrations really need 18+ months to build?",
        "headline_style": "mixed-weight bold with '18+ months?' enlarged",
        "headline_chars": 60,
        "subheadline_on_image": "GrantsNow does it faster",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + contact footer strip + UNIT4 Partner + Oracle Partner logos BR",
        "brand_placement": "corners + footer contact strip + partner co-brand row",
        "graphic_style": "sports action photo with typographic hook - completely off-template from the rest",
        "notable_element": "MotoGP sponsorship photo (only sports metaphor in the set) + partner logos (UNIT4, Oracle) + first stat-in-headline that argues speed",
        "campaign": "demo - Oracle integration",
        "angle": "product_capability",
    },
    {
        "post_id": "SS018", "batch": "batch4",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "GrantsNow empowers research offices to identify the right "
            "opportunities faster, streamline submissions, and increase funding "
            "success through automation and smart integrations. Find out how: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #ResearchFunding #GrantsManagement #PreAwards "
            "#HigherEducation #FundingSuccess #ResearchInnovation"
        ),
        "value_prop_line": "GrantsNow empowers research offices to identify opportunities faster, streamline submissions, and increase funding success through automation and integrations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research offices, funding opportunities, submissions, automation, integrations, higher education, funding success, research innovation",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Find out",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad - very heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "photo + cream card overlay",
        "image_subject": "professional man in suit gesturing at a data screen with team behind him",
        "background_type": "photographic",
        "background_dominant_colour": "bright white-blue office (unusual - lightest in the set)",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'Only GrantsNow!' pill",
        "palette": "brand-teal + gold + bright-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo with flat card",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 4,
        "object_of_focus": "man pointing at data screen + 'Only GrantsNow!' claim",
        "text_on_image": "yes",
        "headline_on_image": "The solution for maximising Grants funding opportunities",
        "headline_style": "mixed-weight bold with 'maximising' emphasised",
        "headline_chars": 55,
        "subheadline_on_image": "Only GrantsNow!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright corporate photo with cream card - warmer palette than the rest",
        "notable_element": "first bright-daylight photo (rest use dark-teal tinted overlays) + explicit 'Only GrantsNow' claim + 7 hashtags",
        "campaign": "demo - funding success",
        "angle": "product_capability",
    },
    {
        "post_id": "SS019", "batch": "batch4",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Join our upcoming webinar here:\n"
            "https://lnkd.in/ei2DNPX6\n\n"
            "Instead of large-scale change, leading institutions are starting "
            "with small, focused pilots:\n"
            "✓ Testing AI for compliance checks\n"
            "✓ Automating funding opportunity discovery\n"
            "✓ Supporting proposal development\n\n"
            "With platforms like GrantsNow already providing centralised data, "
            "workflows, and automation, AI becomes much easier to trial in real "
            "scenarios.\n\n"
            "We'll be discussing real use cases in our upcoming session"
        ),
        "value_prop_line": "GrantsNow already provides centralised data, workflows, and automation, making AI easier to trial in real scenarios.",
        "value_prop_in_first_3_sentences": "no (arrives after the pilot list)",
        "industry_keywords": "webinar, AI, compliance checks, funding opportunity discovery, proposal development, centralised data, pilots",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "webinar",
        "cta_placement": "start (link at top)",
        "cta_type_caption": "register",
        "cta_verb": "Join",
        "has_question_prompt": "no",
        "hashtag_style": "none visible in the screenshot",
        "media_type": "image",
        "primary_visual": "typography + two speaker headshot cards",
        "image_subject": "warm cream-to-peach gradient with 'Meet the Speakers' cards and two portrait photos",
        "background_type": "gradient",
        "background_dominant_colour": "cream to peach",
        "foreground_dominant_colour": "dark teal type + circular speaker portraits",
        "palette": "brand-teal + cream + peach",
        "contrast_level": "medium",
        "texture": "flat gradient with circular photo insets",
        "person_present": "yes", "face_visible": "yes (both speakers)",
        "number_of_people": 2,
        "object_of_focus": "speaker cards with names and credentials",
        "text_on_image": "yes",
        "headline_on_image": "Upcoming Webinar: AI in Pre-Awards: Unlocking Greater Value and Efficiency",
        "headline_style": "title-case mixed-weight bold",
        "headline_chars": 74,
        "subheadline_on_image": "Meet the Speakers - Ian McGowan (25+ yrs managing clients across IT and software) + Dr. Dan King (Research and knowledge exchange specialist with 25+ yrs across strategy, partnerships, and funding)",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "warm poster with speaker credibility cards",
        "notable_element": "first post naming individual speakers with credentials (Ian McGowan, Dr. Dan King) + first warm/cream palette + fourth webinar in the series",
        "campaign": "webinar - AI in Pre-Awards",
        "angle": "thought_leadership",
    },
    {
        "post_id": "SS020", "batch": "batch4",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Research teams deserve tools that remove complexity, not add to it. "
            "GrantsNow streamlines key Pre and Post Award tasks so your staff can "
            "focus more on delivering impactful research, not admin.\n\n"
            "#ResearchFunding #PreAwards #PostAwards #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "GrantsNow streamlines key Pre and Post Award tasks so staff can focus on impactful research, not admin.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research teams, pre-award, post-award, admin, research funding, research management",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "hands typing on keyboard with plants in background + teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "muted green-grey desk photo",
        "foreground_dominant_colour": "teal card + cream border + white all-caps type",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with subtle overlay",
        "person_present": "partial (hands only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the all-caps 'DO MORE IN LESS TIME' headline",
        "text_on_image": "yes",
        "headline_on_image": "DO MORE IN LESS TIME.",
        "headline_style": "all-caps bold",
        "headline_chars": 21,
        "subheadline_on_image": "Streamline Pre and Post-Award instantly with GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with short all-caps hook",
        "notable_element": "shortest headline in the set (21 chars) + first all-caps headline + no CTA URL in the caption (brand-awareness rather than sales-driven)",
        "campaign": "brand awareness - streamline Pre and Post-Award",
        "angle": "product_capability",
    },
    {
        "post_id": "SS021", "batch": "batch5",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "Join our upcoming webinar here:\n"
            "https://lnkd.in/ei2DNPX6\n\n"
            "Instead of large-scale change, leading institutions are starting "
            "with small, focused pilots:\n"
            "✓ Testing AI for compliance checks\n"
            "✓ Automating funding opportunity discovery\n"
            "✓ Supporting proposal development\n\n"
            "With platforms like GrantsNow already providing centralised data, "
            "workflows, and automation, AI becomes much easier to trial in real "
            "scenarios.\n\n"
            "We'll be discussing real use cases in our upcoming session"
        ),
        "value_prop_line": "GrantsNow already provides centralised data, workflows, and automation, making AI easier to trial in real scenarios.",
        "value_prop_in_first_3_sentences": "no (arrives after the pilot list)",
        "industry_keywords": "webinar, AI, compliance checks, funding opportunity discovery, proposal development, centralised data, pilots",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "webinar",
        "cta_placement": "start (link at top)",
        "cta_type_caption": "register",
        "cta_verb": "Join",
        "has_question_prompt": "no",
        "hashtag_style": "none visible in the screenshot",
        "media_type": "image",
        "primary_visual": "photo + typography with WEBINAR pill",
        "image_subject": "soft-focus person with dark teal-to-purple gradient overlay + large headline",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-to-purple gradient",
        "foreground_dominant_colour": "white type + teal WEBINAR pill + teal accent words in headline",
        "palette": "brand-teal + accent-purple + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy gradient overlay",
        "person_present": "yes", "face_visible": "partial (soft focus)",
        "number_of_people": 1,
        "object_of_focus": "large statement headline with teal accent on 'the benefits and value of AI'",
        "text_on_image": "yes",
        "headline_on_image": "Why you should create pilot tests to explore the benefits and value of AI",
        "headline_style": "mixed-weight bold with teal accent on 'the benefits and value of AI'",
        "headline_chars": 73,
        "subheadline_on_image": "Join us on Wednesday 6th May at 12:30pm to discuss how AI will help",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + Research Consulting logo TR + WEBINAR pill",
        "brand_placement": "corners + centered pill",
        "graphic_style": "webinar poster - photo hero with statement hook",
        "notable_element": "SAME CAPTION AS SS019 (verbatim) but DIFFERENT image and DIFFERENT date (Wed 6th May vs Tue 19th May). This is the natural A/B for 'does the creative alone move the numbers?'. Fifth post in the webinar series overall.",
        "campaign": "webinar - AI in Pre-Awards",
        "angle": "thought_leadership",
    },
    {
        "post_id": "SS022", "batch": "batch6",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow syncs data in real time, giving research offices and "
            "leadership instant visibility into proposal status, deadlines and "
            "workload. No more stale reports or outdated spreadsheets. Get in "
            "touch: https://lnkd.in/dU2Brsef\n\n"
            "#ResearchData #RealTimeUpdates #UniversitySystems #GrantsNow"
        ),
        "value_prop_line": "GrantsNow syncs data in real time, giving research offices and leadership instant visibility into proposal status, deadlines and workload.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "real-time data, research offices, proposal status, deadlines, workload, spreadsheets, university systems",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "hands typing on keyboard with financial charts + teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted desk photo",
        "foreground_dominant_colour": "teal card + cream border + white all-caps type",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "partial (hands only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the all-caps 'REAL TIME DATA. REAL IMPACT.' hook + 'Only possible with GrantsNow' claim",
        "text_on_image": "yes",
        "headline_on_image": "REAL TIME DATA. REAL IMPACT.",
        "headline_style": "all-caps bold",
        "headline_chars": 28,
        "subheadline_on_image": "Only possible with GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with short all-caps hook and brand-claim pill",
        "notable_element": "second all-caps headline in the set (after SS020) + 'Only possible with GrantsNow' as exclusivity claim - twinned with SS020's short-hook template",
        "campaign": "demo - real-time data",
        "angle": "product_capability",
    },
    {
        "post_id": "SS023", "batch": "batch6",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Most systems stop at submission, leaving teams to track awards "
            "manually. GrantsNow connects Pre Award to Post Award so you have "
            "visibility from idea to outcome. Get in touch: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantLifecycle #PostAward #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "GrantsNow connects Pre Award to Post Award so you have visibility from idea to outcome.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "submission, tracking, Pre Award, Post Award, grant lifecycle, research management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + light cream card overlay",
        "image_subject": "group of 5 professionals around a laptop, smiling, bright office",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral (rare - like SS018)",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'Sounds neat right?' pill",
        "palette": "brand-teal + gold + bright-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 5,
        "object_of_focus": "the cream card headline + 'Sounds neat right?' cheeky pill",
        "text_on_image": "yes",
        "headline_on_image": "A platform that supports both Pre-Award and Post-Award.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 55,
        "subheadline_on_image": "Sounds neat right?",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners (no footer strip in this one)",
        "graphic_style": "bright team photo with cream card and conversational pill",
        "notable_element": "most people in a single image (5) + conversational 'Sounds neat right?' pill (only-post using casual language on the image) + no footer contact strip",
        "campaign": "demo - full lifecycle",
        "angle": "product_capability",
    },
    {
        "post_id": "SS024", "batch": "batch6",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "Budgeting shouldn't be the bottleneck but it often is.\n\n"
            "Manual spreadsheets, outdated costing models, and disconnected "
            "finance data make it difficult to build accurate, compliant "
            "proposals.\n\n"
            "GrantsNow tackles this with:\n"
            "✓ Full economic costing (fEC) aligned to TRAC\n"
            "✓ Automated cost calculations and scenario modelling\n"
            "✓ Integration with HR & finance systems for real-time data\n\n"
            "Fewer errors. Faster approvals. Stronger proposals.\n\n"
            "Join us to explore how AI can take budgeting and validation even "
            "further."
        ),
        "value_prop_line": "GrantsNow tackles budgeting with full economic costing aligned to TRAC, automated cost calculations, and integration with HR and finance systems.",
        "value_prop_in_first_3_sentences": "no (arrives after the pain setup)",
        "industry_keywords": "budgeting, spreadsheets, costing models, finance data, full economic costing, TRAC, HR and finance systems, AI",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "webinar",
        "cta_placement": "end",
        "cta_type_caption": "register",
        "cta_verb": "Join",
        "has_question_prompt": "no",
        "hashtag_style": "none visible in the screenshot",
        "media_type": "image",
        "primary_visual": "photo + typography with WEBINAR pill",
        "image_subject": "soft-focus person with dark teal-to-purple gradient + large question headline",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-to-purple gradient",
        "foreground_dominant_colour": "white type + teal WEBINAR pill + teal accent words in headline",
        "palette": "brand-teal + accent-purple + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy gradient overlay",
        "person_present": "yes", "face_visible": "partial (soft focus)",
        "number_of_people": 1,
        "object_of_focus": "large question headline with teal accent on 'the hardest parts of Grant Applications'",
        "text_on_image": "yes",
        "headline_on_image": "Why is budget creation still one of the hardest parts of Grant Applications?",
        "headline_style": "mixed-weight bold with teal accent",
        "headline_chars": 77,
        "subheadline_on_image": "Join us on Wednesday 6th May at 12:30pm to discuss how AI will help",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + Research Consulting logo TR + WEBINAR pill",
        "brand_placement": "corners + centered pill",
        "graphic_style": "webinar poster - photo hero with question hook and teal accent inside",
        "notable_element": "sixth webinar in the series (SS014-SS016, SS019, SS021, SS024) + same Wed 6th May date as SS021 - possibly A/B for the earlier session",
        "campaign": "webinar - AI in Pre-Awards",
        "angle": "pain_point + thought_leadership",
    },
    {
        "post_id": "SS025", "batch": "batch6",
        "view_completeness": "bottom-cropped", "cta_confidence": "unknown",
        "caption": (
            "If your pre-award software requires constant workarounds, you're "
            "already wasting time. GrantsNow enables you to speed up with "
            "automation, speed, and effortless integration. Switch to our "
            "future-proof solution: https://lnkd.in/dU2Brsef\n\n"
            "#PreAwardSoftware #ResearchManagement #HigherEdTech #GrantsNow "
            "#FutureReady #Automation #UKUniversities #DigitalTransformation "
            "#TrueSaaS"
        ),
        "value_prop_line": "GrantsNow enables you to speed up with automation, speed, and effortless integration.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-award software, workarounds, automation, integration, future-proof, higher ed tech, digital transformation, True SaaS",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Switch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad + niche - heaviest in the set (9 tags)",
        "media_type": "image",
        "primary_visual": "cartoon illustration (pit stop racing scene)",
        "image_subject": "cartoon pit stop with crew changing tires on green racing car with cheering crowd and yellow rival car",
        "background_type": "illustrated",
        "background_dominant_colour": "bright blue sky + green car + colourful crowd",
        "foreground_dominant_colour": "green racing crew + white type on cream area above",
        "palette": "cartoon-multicolour + brand-teal (in the type area)",
        "contrast_level": "high",
        "texture": "flat cartoon illustration",
        "person_present": "yes (cartoon)", "face_visible": "yes (cartoon faces + crowd)",
        "number_of_people": 6,
        "object_of_focus": "the racing pit stop scene + 'Stuck racing?' hook",
        "text_on_image": "yes",
        "headline_on_image": "Stuck racing with a system that slows you down?",
        "headline_style": "handwritten-style script",
        "headline_chars": 48,
        "subheadline_on_image": "GrantsNow keeps you on track with a Future-proof, True SaaS solution.",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL (small)",
        "brand_placement": "top only (minimal branding for this creative)",
        "graphic_style": "editorial cartoon illustration - only illustrated post in the set",
        "notable_element": "second racing metaphor in the set (SS017 was photo of MotoGP, SS025 is cartoon pit stop) + heaviest hashtag load (9) + handwritten-style headline + minimal branding",
        "campaign": "demo - True SaaS speed",
        "angle": "product_capability",
    },
    {
        "post_id": "SS026", "batch": "batch6",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Many solutions claim to be SaaS, but few actually are. A TRUE SaaS "
            "platform has a single codebase, instant updates, and scalable "
            "configurations. Read the blog to know more: "
            "https://lnkd.in/eqK3_-vN\n\n"
            "#grantsnow #preawards #research #grantsmanagement #armauk #SaaS"
        ),
        "value_prop_line": "A TRUE SaaS platform has a single codebase, instant updates, and scalable configurations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "SaaS, True SaaS, single codebase, instant updates, scalable configurations, pre-awards, research management, ARMA UK",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "blog",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase (first lowercase set)",
        "media_type": "image",
        "primary_visual": "photo + typography with BLOG pill",
        "image_subject": "two women at a desk with laptop, soft-focus office background",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office photo",
        "foreground_dominant_colour": "white type + yellow highlighter on 'older' word",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes", "face_visible": "yes (soft focus)",
        "number_of_people": 2,
        "object_of_focus": "large question headline with yellow highlighter marker on 'older'",
        "text_on_image": "yes",
        "headline_on_image": "Is your platform TRUE SaaS or Just older tech, hosted on the cloud?",
        "headline_style": "mixed-weight bold with yellow highlighter marker on 'older'",
        "headline_chars": 65,
        "subheadline_on_image": "Learn how TRUE SaaS saves time and money. Read the blog.",
        "image_cta_text": "(Link in description)",
        "brand_marks": "GrantsNow logo TL + BLOG pill TR",
        "brand_placement": "corners",
        "graphic_style": "editorial photo with punchy question and highlighter mark",
        "notable_element": "first BLOG offer type in the set (rest are whitepaper/demo/webinar) + first highlighter-marker treatment on a single word + first all-lowercase hashtag set + 'Link in description' pattern (rare - LinkedIn's suggested workaround for link penalty)",
        "campaign": "blog - True SaaS",
        "angle": "thought_leadership",
    },
    {
        "post_id": "SS027", "batch": "batch7",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "The wrong Pre-Awards platform means hidden costs, manual updates, "
            "delays, and a higher total cost of ownership. GrantsNow's TRUE SaaS "
            "solution gives you full control, instant upgrades, and zero hidden "
            "fees. Read the blog to know how: https://lnkd.in/eqK3_-vN\n\n"
            "#grantsmanagement #armauk #grantsnow #preawards #research"
        ),
        "value_prop_line": "GrantsNow's TRUE SaaS solution gives you full control, instant upgrades, and zero hidden fees.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards platform, hidden costs, manual updates, total cost of ownership, TRUE SaaS, ARMA UK, grants management",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "blog",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "photo + typography with BLOG pill",
        "image_subject": "dark abstract office photo with question headline overlay",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office blur",
        "foreground_dominant_colour": "white type + yellow highlighter on 'Cost'",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the question headline with yellow highlighter marker on 'Cost'",
        "text_on_image": "yes",
        "headline_on_image": "Pre-Awards Platforms: What's the Cost of the Wrong Choice?",
        "headline_style": "mixed-weight bold with yellow highlighter marker on 'Cost'",
        "headline_chars": 57,
        "subheadline_on_image": "Learn how TRUE SaaS saves time and money. Read the blog.",
        "image_cta_text": "(Link in description) + Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + BLOG pill TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "editorial photo blog poster with highlighter accent",
        "notable_element": "SAME CAPTION AND HEADLINE AS SS031 but different background - abstract office in SS027, architectural building in SS031. Second natural A/B pair in the whole set (first was SS019/SS021).",
        "campaign": "blog - True SaaS cost",
        "angle": "thought_leadership + pain_point",
    },
    {
        "post_id": "SS028", "batch": "batch7",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Searching for the next generation in pre-awards software? GrantsNow "
            "is here now, making pre and post-award administration faster, more "
            "automated and better integrated.\n\n"
            "#GrantsNow #PreAwardSoftware #PostAwardManagement #ResearchGrants "
            "#HigherEdTech #UKUniversities #SmartFunding #FutureReady"
        ),
        "value_prop_line": "GrantsNow is here now, making pre and post-award administration faster, more automated and better integrated.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "next generation, pre-awards software, post-award management, automation, integration, higher ed tech, smart funding, future ready",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad + niche - very heavy (8 tags)",
        "media_type": "image",
        "primary_visual": "photo (space astronaut) with typography",
        "image_subject": "astronaut in white spacesuit reaching outward with earth curve visible in background",
        "background_type": "photographic",
        "background_dominant_colour": "black space + blue earth curve",
        "foreground_dominant_colour": "white all-caps type + teal accent on 'LOST'",
        "palette": "black + brand-teal + white + photographic",
        "contrast_level": "very high",
        "texture": "photo realistic with cosmic backdrop",
        "person_present": "yes (astronaut)", "face_visible": "no (helmet)",
        "number_of_people": 1,
        "object_of_focus": "the DON'T GET LOST hook + astronaut reaching hand",
        "text_on_image": "yes",
        "headline_on_image": "DON'T GET LOST",
        "headline_style": "all-caps bold with teal accent on 'LOST'",
        "headline_chars": 14,
        "subheadline_on_image": "Searching for the latest advancements in a Pre-Awards platform. GrantsNow is already here to simplify Pre & Post-Award Management",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + contact footer strip (no HM Government badge)",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "cinematic space photo with punchy short hook",
        "notable_element": "first space/aerospace visual in the set + shortest headline yet (14 chars) + teal accent on a single word inside all-caps + no G-Cloud badge (missing from this creative)",
        "campaign": "brand awareness - next generation",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS029", "batch": "batch7",
        "view_completeness": "bottom-cropped", "cta_confidence": "unknown",
        "caption": (
            "Unlock more opportunities for grants income without needing extra "
            "budget! With GrantsNow, you have multiple tools at your disposal to "
            "streamline Pre-Awards, enhance team performance, and get your "
            "organisation the funding it deserves."
        ),
        "value_prop_line": "With GrantsNow, you have multiple tools to streamline Pre-Awards, enhance team performance, and get your organisation the funding it deserves.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "grants income, budget, pre-awards, team performance, funding",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "none in the caption (they sit inside the mock tweet)",
        "media_type": "image",
        "primary_visual": "typography (fake tweet mockup)",
        "image_subject": "mock Twitter/X post with GrantsNow verified handle and heart/reply icons",
        "background_type": "solid",
        "background_dominant_colour": "dark navy-teal",
        "foreground_dominant_colour": "white tweet card + teal accent brand name + red heart",
        "palette": "brand-teal (dark) + white + accent-red heart",
        "contrast_level": "high",
        "texture": "flat tweet-card mockup",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the mock tweet card claiming 'the GrantsNow treatment'",
        "text_on_image": "yes",
        "headline_on_image": "Increase your Grants income without extending your existing budget.... Thats the GrantsNow treatment.",
        "headline_style": "tweet-body regular text",
        "headline_chars": 100,
        "subheadline_on_image": "@TheFastestGrowingPreAwardsPlatform",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + verified checkmark inside mock tweet",
        "brand_placement": "corner + inside mock tweet card",
        "graphic_style": "social-mockup embed (fake tweet) - first of its kind in the set",
        "notable_element": "fake tweet mockup treatment (never used before) + typo 'Thats' missing apostrophe (visible on the creative) + '@TheFastestGrowingPreAwardsPlatform' handle claim + no CTA URL anywhere",
        "campaign": "brand awareness - Pre-Awards positioning",
        "angle": "product_capability",
    },
    {
        "post_id": "SS030", "batch": "batch7",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Managing integrations, reports, and configurations in-house can "
            "drain valuable time and resources. With GrantsNow, you don't have "
            "to. Our team of 250+ consultants ensures seamless integration and "
            "customisation, so you can focus on what truly matters.\n\n"
            "#HigherEdTech #GrantsNow #GrantManagement #Automation #Efficiency "
            "#SeamlessIntegration"
        ),
        "value_prop_line": "Our team of 250+ consultants ensures seamless integration and customisation so you can focus on what truly matters.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "integrations, reports, configurations, 250+ consultants, seamless integration, customisation, higher ed tech, automation",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "business meeting - 5 to 6 people around a table with one standing presenter",
        "background_type": "photographic",
        "background_dominant_colour": "muted warm neutral office",
        "foreground_dominant_colour": "teal card + cream border + white type with 'IT team' in bold accent",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with subtle overlay",
        "person_present": "yes", "face_visible": "yes (multiple, partial)",
        "number_of_people": 6,
        "object_of_focus": "the IT team question + presenter in background",
        "text_on_image": "yes",
        "headline_on_image": "Is your IT team burdened with integrations, reports, and configurations?",
        "headline_style": "mixed-weight bold with 'IT team' in heavier weight",
        "headline_chars": 71,
        "subheadline_on_image": "With GrantsNow, they don't have to.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with centred teal card - IT-team specific target",
        "notable_element": "explicit stat in caption '250+ consultants' + first post specifically targeting the IT team persona rather than the research office",
        "campaign": "demo - IT team burden",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS031", "batch": "batch7",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "The wrong Pre-Awards platform means hidden costs, manual updates, "
            "delays, and a higher total cost of ownership. GrantsNow's TRUE SaaS "
            "solution gives you full control, instant upgrades, and zero hidden "
            "fees. Read the blog to know how: https://lnkd.in/eqK3_-vN\n\n"
            "#grantsmanagement #armauk #grantsnow #preawards #research"
        ),
        "value_prop_line": "GrantsNow's TRUE SaaS solution gives you full control, instant upgrades, and zero hidden fees.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards platform, hidden costs, manual updates, total cost of ownership, TRUE SaaS, ARMA UK, grants management",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "blog",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "photo + typography with BLOG pill",
        "image_subject": "architectural building (looks like a domed university building) with question headline overlay",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted architectural photo",
        "foreground_dominant_colour": "white type + yellow highlighter on 'Cost'",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the question headline with yellow highlighter marker on 'Cost'",
        "text_on_image": "yes",
        "headline_on_image": "Pre-Awards Platforms: What's the Cost of the Wrong Choice?",
        "headline_style": "mixed-weight bold with yellow highlighter marker on 'Cost'",
        "headline_chars": 57,
        "subheadline_on_image": "Learn how TRUE SaaS saves time and money. Read the blog.",
        "image_cta_text": "(Link in description) + Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + BLOG pill TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "editorial photo blog poster with highlighter accent",
        "notable_element": "SAME CAPTION AND HEADLINE AS SS027 - architectural university-style building as the only differentiator. Cleanest natural A/B in the set (SS019/SS021 was the first).",
        "campaign": "blog - True SaaS cost",
        "angle": "thought_leadership + pain_point",
    },
    {
        "post_id": "SS032", "batch": "batch8",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow is empowering research teams to work smarter, not harder. "
            "Discover why UK institutions are opting for a platform designed for "
            "outcomes, not workarounds. Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #PreAwardSoftware #ResearchManagement #HigherEdTech "
            "#TrueSaaS #UKUniversities"
        ),
        "value_prop_line": "GrantsNow is a platform designed for outcomes, not workarounds - real-time KPI reporting, self-configurable, lower cost with more opportunities.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research teams, UK institutions, pre-award software, higher ed tech, TRUE SaaS, UK universities, KPI reporting, funder templates",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + 3-column benefit cards",
        "image_subject": "dark teal-tinted architectural photo with 3 numbered benefit cards",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted architectural blur",
        "foreground_dominant_colour": "white type + yellow circle numbers + teal cards",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay + flat cards",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the three numbered benefit cards (1 analytics, 2 self-configurable, 3 lower cost)",
        "text_on_image": "yes",
        "headline_on_image": "Ready to experience the GrantsNow Treatment?",
        "headline_style": "mixed-weight bold",
        "headline_chars": 44,
        "subheadline_on_image": "1 Real time analytics for KPI reporting | 2 Completely self configurable for funder templates, approval routes etc | 3 Lower cost but more Grants opportunities | The fastest-growing True SaaS cloud pre-award platform in the UK",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo top-centre + contact footer strip + fastest-growing claim",
        "brand_placement": "top-centre (not corner) + footer contact strip",
        "graphic_style": "3-column benefit poster with question hook",
        "notable_element": "first 3-column numbered benefit card layout + fastest-growing True SaaS UK claim + GrantsNow logo placed top-centre rather than top-left (only post with this branding position)",
        "campaign": "demo - GrantsNow Treatment",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS033", "batch": "batch8",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "With GrantsNow, you can assign responsibilities, control access, "
            "and ensure data security within a fully configurable and "
            "user-friendly platform built for research offices.\n\n"
            "Learn more: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #GrantsManagement #PreAwards #ResearchFunding "
            "#DataSecurity #Compliance #HigherEducation"
        ),
        "value_prop_line": "With GrantsNow, you can assign responsibilities, control access, and ensure data security in a fully configurable platform for research offices.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "roles, permissions, responsibilities, access control, data security, configurable, research offices, pre-awards, compliance, higher education",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "learn_more",
        "cta_verb": "Learn",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "typography on light gradient",
        "image_subject": "cream-to-mint gradient with cream card and 'Imagine being able to...' headline",
        "background_type": "gradient",
        "background_dominant_colour": "cream to mint (light)",
        "foreground_dominant_colour": "cream card + orange rounded border + teal type + teal pill",
        "palette": "brand-teal + gold + cream",
        "contrast_level": "medium",
        "texture": "flat gradient with subtle wave lines",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the imagined-outcome card + 'With GrantsNow you can!' pill response",
        "text_on_image": "yes",
        "headline_on_image": "Imagine being able to define roles and permissions in your Pre-Awards system.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 77,
        "subheadline_on_image": "With GrantsNow you can!",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners (no footer strip)",
        "graphic_style": "no-photo poster - cream card with question setup and cheeky response pill",
        "notable_element": "first 'Imagine being able to...' hypothetical opener + no photo, no footer strip - lightest visual treatment in the set",
        "campaign": "demo - roles and permissions",
        "angle": "product_capability",
    },
    {
        "post_id": "SS034", "batch": "batch8",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Universities often struggle with costing consistency across "
            "faculties. GrantsNow uses a flexible, TRAC compatible engine that "
            "supports multiple scenarios and institution specific rules. Get in "
            "touch: https://lnkd.in/dU2Brsef\n\n"
            "#ResearchFinance #Costings #TRAC #GrantsNow"
        ),
        "value_prop_line": "GrantsNow uses a flexible, TRAC compatible engine that supports multiple scenarios and institution specific rules.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "universities, costing consistency, faculties, TRAC compatible, scenarios, research finance",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche (very focused)",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "close-up hands writing on paper with pen and calculator",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted desk photo",
        "foreground_dominant_colour": "white type + gold line divider",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "partial (hands only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the costing engine claim + gold divider line under the headline",
        "text_on_image": "yes",
        "headline_on_image": "A unified costing engine for consistent proposals.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 50,
        "subheadline_on_image": "Unlock Smarter Grants Management with GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with statement headline and gold divider accent",
        "notable_element": "first gold-line divider between headline and sub + tightest hashtag focus (4 finance-specific tags: TRAC, Costings, ResearchFinance, GrantsNow)",
        "campaign": "demo - unified costing",
        "angle": "product_capability",
    },
    {
        "post_id": "SS035", "batch": "batch8",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Every role in the research office sees what matters most. "
            "GrantsNow's configurable dashboards highlight tasks, deadlines and "
            "priorities so teams stay aligned without chasing information. Get "
            "in touch: https://lnkd.in/dU2Brsef\n\n"
            "#ResearchOffice #Workflows #HigherEducation #GrantsNow"
        ),
        "value_prop_line": "GrantsNow's configurable dashboards highlight tasks, deadlines and priorities so teams stay aligned without chasing information.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research office, dashboards, tasks, deadlines, priorities, workflows, higher education",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + product screenshot mockup",
        "image_subject": "dark teal background with realistic laptop showing the GrantsNow dashboard UI",
        "background_type": "solid",
        "background_dominant_colour": "dark teal",
        "foreground_dominant_colour": "white type + product screenshot (charts, KPIs)",
        "palette": "brand-teal + product-screenshot colours",
        "contrast_level": "high",
        "texture": "flat solid with realistic laptop render",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the actual product screenshot in the laptop",
        "text_on_image": "yes",
        "headline_on_image": "A dashboard that works the way your team works.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 48,
        "subheadline_on_image": "",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo top + contact footer strip",
        "brand_placement": "top + footer contact strip",
        "graphic_style": "product hero - laptop showing actual dashboard UI",
        "notable_element": "first product screenshot in the entire set (real UI shown, not a stylised card) - biggest signal of what the software actually does",
        "campaign": "demo - dashboards",
        "angle": "product_capability",
    },
    {
        "post_id": "SS036", "batch": "batch8",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Unlock more funding opportunities with less effort. Want to know how? "
            "Set up a demo - https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #Funding #GrantsManagement"
        ),
        "value_prop_line": "Increase your grant funding opportunities by 25% with the Funder Opportunity Scanner.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "funding opportunities, funder opportunity scanner, grants management, grant funding",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "book_demo",
        "cta_verb": "Set up",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "typography on dark gradient",
        "image_subject": "dark teal-to-green gradient with wave lines and 25% stat headline",
        "background_type": "gradient",
        "background_dominant_colour": "dark teal to green",
        "foreground_dominant_colour": "white type",
        "palette": "brand-teal (dark) + white",
        "contrast_level": "high",
        "texture": "flat gradient with wave line motif",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the 25% stat headline",
        "text_on_image": "yes",
        "headline_on_image": "Increase your grant funding opportunities by 25% with the Funder Opportunity Scanner",
        "headline_style": "mixed-weight (numbers not visually enlarged)",
        "headline_chars": 88,
        "subheadline_on_image": "Don't believe it?",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "typography-only dark poster with stat as hook",
        "notable_element": "IDENTICAL CAPTION, HEADLINE, URL AND VISUAL AS SS013. Either a genuine repost by the page or a re-upload in this batch. If a repost, this is direct data on whether reposts move numbers.",
        "campaign": "demo - funder opportunity scanner",
        "angle": "product_capability",
    },
    {
        "post_id": "SS037", "batch": "batch9",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Legacy Pre-Awards technology can quietly slow research teams down "
            "and limit funding success. Our latest blog explores why "
            "universities are rethinking their grants systems. Read more: "
            "https://lnkd.in/daG7f5zk\n\n"
            "#GrantsNow #LegacySoftware #GrantsManagement #PreAwards #Funding "
            "#Grants"
        ),
        "value_prop_line": "Our latest blog explores why universities are rethinking their grants systems.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "legacy pre-awards technology, research teams, funding success, universities, grants systems, legacy software",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "blog",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "typography on dark gradient with bracketed CTA button",
        "image_subject": "dark teal gradient with subtle wave lines and question headline",
        "background_type": "gradient",
        "background_dominant_colour": "dark teal with subtle green wave",
        "foreground_dominant_colour": "white type with 'Real Impact' emphasised",
        "palette": "brand-teal (dark) + white",
        "contrast_level": "high",
        "texture": "flat gradient with subtle wave line motif",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the question headline + bracketed 'Read our blog' button",
        "text_on_image": "yes",
        "headline_on_image": "What's the Real Impact of Legacy Pre-Awards Software on Universities?",
        "headline_style": "mixed-weight bold with 'Real Impact' in heavier weight",
        "headline_chars": 69,
        "subheadline_on_image": "[Read our blog to know more]",
        "image_cta_text": "Link in description + Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "typography-only dark poster with bracketed CTA treatment",
        "notable_element": "new blog URL (daG7f5zk - different from the eqK3_-vN blog used by SS026/SS027/SS031) + first bracketed '[Read our blog to know more]' treatment + Link in description signal",
        "campaign": "blog - legacy pre-awards impact",
        "angle": "thought_leadership + pain_point",
    },
    {
        "post_id": "SS038", "batch": "batch9",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Researchers, approvers, and administrators can all work within the "
            "same platform. GrantsNow enables all conversations, feedback, and "
            "changes to documents to be centralised so that no step is missed "
            "in an email trail.\n"
            "Contact us: https://lnkd.in/dU2Brsef\n\n"
            "#Collaboration #ResearchSupport #AcademicWorkflows #GrantsNow"
        ),
        "value_prop_line": "GrantsNow enables all conversations, feedback, and changes to documents to be centralised so no step is missed in an email trail.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "researchers, approvers, administrators, centralised, conversations, feedback, email trail, collaboration, academic workflows",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Contact",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "desaturated photo + cream card overlay",
        "image_subject": "black-and-white team meeting photo (5-6 people around a laptop) with cream card and speech-bubble icon",
        "background_type": "photographic",
        "background_dominant_colour": "black and white team meeting",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal speech bubble",
        "palette": "black-and-white + brand-teal + cream",
        "contrast_level": "high",
        "texture": "desaturated photo with flat card overlay",
        "person_present": "yes", "face_visible": "yes (multiple, partial)",
        "number_of_people": 6,
        "object_of_focus": "the collaboration claim + teal speech-bubble icon",
        "text_on_image": "yes",
        "headline_on_image": "Experience Seamless collaboration for every proposal with GrantsNow!",
        "headline_style": "mixed-weight bold with 'Seamless collaboration' emphasised",
        "headline_chars": 68,
        "subheadline_on_image": "",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "desaturated team photo with cream card - editorial magazine feel",
        "notable_element": "first fully desaturated / black-and-white photo treatment + speech-bubble accent icon (new visual element)",
        "campaign": "demo - collaboration",
        "angle": "product_capability",
    },
    {
        "post_id": "SS039", "batch": "batch9",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Universities require visibility into their research funding "
            "activity in order to make informed decisions. GrantsNow offers "
            "intelligent and configurable dashboards and reporting, providing "
            "research offices with real-time visibility into the entire "
            "Pre-Awards process.\n\n"
            "Universities using GrantsNow benefit from:\n"
            "• Real-time dashboards that display submissions, approvals, "
            "workloads, and pipelines\n"
            "• Configurable views that cater to different roles and "
            "responsibilities\n"
            "• Accurate data that is extracted from live grant and costing "
            "information\n"
            "• Clear reporting that enables planning, performance, and "
            "compliance\n\n"
            "This enables better decision-making, improved transparency, and "
            "enhanced oversight of research funding activity.\n\n"
            "#GrantsNow #ResearchFunding #PreAwards #GrantsManagement "
            "#HigherEducation #ResearchOffice"
        ),
        "value_prop_line": "GrantsNow offers configurable dashboards and reporting, providing research offices with real-time visibility into the entire Pre-Awards process.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "universities, research funding, informed decisions, dashboards, reporting, submissions, approvals, workloads, pipelines, compliance",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + typography with partner logos + laptop mockup",
        "image_subject": "dark teal-tinted photo of person working at desk with laptop mockup partially shown",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office scene",
        "foreground_dominant_colour": "white type + gold divider + partner logos",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes (background)", "face_visible": "no (blurred)",
        "number_of_people": 1,
        "object_of_focus": "the everything-in-one-dashboard claim + partner logos as credibility",
        "text_on_image": "yes",
        "headline_on_image": "Everything from funding opportunities to KPIs in one dashboard.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 62,
        "subheadline_on_image": "GrantsNow makes it simpler",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip + UNIT4 Partner + Oracle Partner logos BR",
        "brand_placement": "corners + footer contact strip + partner co-brand row",
        "graphic_style": "photo hero with partner logos - most badge-heavy poster in the set",
        "notable_element": "first caption using • bullets (rest used ✓) + longest structured caption yet (7 sentences) + second post with UNIT4 + Oracle partner logos (SS017 was the first, a MotoGP creative)",
        "campaign": "brand awareness - unified dashboard",
        "angle": "product_capability",
    },
    {
        "post_id": "SS040", "batch": "batch9",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow syncs data in real time, giving research offices and "
            "leadership instant visibility into proposal status, deadlines and "
            "workload. No more stale reports or outdated spreadsheets. Get in "
            "touch: https://lnkd.in/dU2Brsef\n\n"
            "#ResearchData #RealTimeUpdates #UniversitySystems #GrantsNow"
        ),
        "value_prop_line": "GrantsNow syncs data in real time, giving research offices and leadership instant visibility into proposal status, deadlines and workload.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "real-time data, research offices, proposal status, deadlines, workload, spreadsheets, university systems",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "hands typing on keyboard with financial charts + teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted desk photo",
        "foreground_dominant_colour": "teal card + cream border + white all-caps type",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "partial (hands only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the all-caps 'REAL TIME DATA. REAL IMPACT.' hook + 'Only possible with GrantsNow' claim",
        "text_on_image": "yes",
        "headline_on_image": "REAL TIME DATA. REAL IMPACT.",
        "headline_style": "all-caps bold",
        "headline_chars": 28,
        "subheadline_on_image": "Only possible with GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with short all-caps hook and brand-claim pill",
        "notable_element": "IDENTICAL CAPTION, HEADLINE, URL AND VISUAL AS SS022. Third duplicate pair after SS013/SS036 and (partial) SS027/SS031. Likely a repost - or an accidental re-upload.",
        "campaign": "demo - real-time data",
        "angle": "product_capability",
    },
    {
        "post_id": "SS041", "batch": "batch9",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Most systems stop at submission, leaving teams to track awards "
            "manually. GrantsNow connects Pre Award to Post Award so you have "
            "visibility from idea to outcome. Get in touch: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantLifecycle #PostAward #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "GrantsNow connects Pre Award to Post Award so you have visibility from idea to outcome.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "submission, tracking, Pre Award, Post Award, grant lifecycle, research management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + light cream card overlay",
        "image_subject": "group of 5 professionals around a laptop, bright office scene",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'Sounds neat right?' pill",
        "palette": "brand-teal + gold + bright-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 5,
        "object_of_focus": "the cream card headline + 'Sounds neat right?' pill",
        "text_on_image": "yes",
        "headline_on_image": "A platform that supports both Pre-Award and Post-Award.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 55,
        "subheadline_on_image": "Sounds neat right?",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners (no footer strip)",
        "graphic_style": "bright team photo with cream card and conversational pill",
        "notable_element": "IDENTICAL CAPTION, HEADLINE, URL AND VISUAL AS SS023. Fourth duplicate in the set. Same batch as SS040 which duplicates SS022 - suggesting a batch repost of the demo posts.",
        "campaign": "demo - full lifecycle",
        "angle": "product_capability",
    },
    {
        "post_id": "SS042", "batch": "batch10",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Universities are uncovering significantly more funding "
            "opportunities by using a single platform that brings searchable "
            "global grant databases, custom alerts, and automation together. "
            "Want to find out how they're doing it?\n\n"
            "#GrantsNow #GrantsManagement #ResearchFunding #PreAwards "
            "#HigherEducation #FundingOpportunities"
        ),
        "value_prop_line": "A single platform that brings searchable global grant databases, custom alerts, and automation together.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "universities, funding opportunities, global grant databases, custom alerts, automation, funding opportunities, higher education",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography",
        "image_subject": "classroom/lecture scene with presenter and students, dark teal overlay",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted lecture hall",
        "foreground_dominant_colour": "white all-caps type + bold 'how' accent + downward arrow",
        "palette": "brand-teal + white + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "yes", "face_visible": "partial (multiple)",
        "number_of_people": 4,
        "object_of_focus": "the all-caps '25%+ INCREASE' claim + question prompt",
        "text_on_image": "yes",
        "headline_on_image": "UNIVERSITIES ARE FINDING A 25%+ INCREASE IN GRANTS FUNDING OPPORTUNITIES",
        "headline_style": "all-caps bold",
        "headline_chars": 71,
        "subheadline_on_image": "? Want to know how?",
        "image_cta_text": "downward arrow indicator (no URL)",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners (no footer strip)",
        "graphic_style": "photo hero with all-caps stat and interactive question prompt",
        "notable_element": "fourth all-caps headline in the set + third 25% stat (SS013 SS036 SS045) + '? Want to know how?' prompt with arrow (invites reply / next-post continuation)",
        "campaign": "brand awareness - 25% funding lift",
        "angle": "product_capability",
    },
    {
        "post_id": "SS043", "batch": "batch10",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "ERP integrations should not take 18 months. GrantsNow delivers "
            "faster, seamless connectivity so your team can focus on winning "
            "more funding, not waiting on integrations.\n\n"
            "#GrantsNow #PreAwards #ERPIntegration #ResearchFunding "
            "#HigherEducation"
        ),
        "value_prop_line": "GrantsNow delivers faster, seamless connectivity so your team can focus on winning more funding, not waiting on integrations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "ERP integrations, 18 months, seamless connectivity, winning funding, pre-awards, higher education",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "portrait photo + typography with inner speech bubble",
        "image_subject": "frustrated businessman with head resting on hand, office in background",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office",
        "foreground_dominant_colour": "white type + yellow highlighter on '18 months' + cream speech-bubble",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with overlay",
        "person_present": "yes", "face_visible": "yes (expressive)",
        "number_of_people": 1,
        "object_of_focus": "the frustrated portrait + '18 months' highlight + inner monologue speech bubble",
        "text_on_image": "yes",
        "headline_on_image": "Should it really take 18 months to build the ERP integrations to my Pre-Awards Platform?",
        "headline_style": "mixed-weight bold with yellow highlighter on '18 months'",
        "headline_chars": 89,
        "subheadline_on_image": "Wish I'd known about GrantsNow sooner",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "character-driven portrait with inner monologue speech-bubble - most emotional creative in the set",
        "notable_element": "first single-person portrait with clear emotional expression (frustration) + first inner-monologue speech bubble ('Wish I'd known...') + yellow highlighter on the stat. This is the '18 months' theme that also drives SS017/SS044 MotoGP creatives - three variants of the same claim now.",
        "campaign": "demo - ERP integration speed",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS044", "batch": "batch10",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Many universities wait over a year for their Pre Award system to "
            "connect with finance and HR platforms. GrantsNow delivers clean, "
            "pre built integrations with Oracle cloud so you can go live in "
            "less than half the time faster. Get in touch: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#University #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "GrantsNow delivers pre-built integrations with Oracle cloud so you can go live in less than half the time.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-award, integrations, finance, HR platforms, Oracle cloud, universities, research management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "action photo (MotoGP racing bike)",
        "image_subject": "MotoGP racing bike with GrantsNow branding, motion blur, rider in green leathers",
        "background_type": "photographic",
        "background_dominant_colour": "green track blur + dark racing photo",
        "foreground_dominant_colour": "green bike + white type",
        "palette": "brand-teal + racing-green + photographic",
        "contrast_level": "high",
        "texture": "action photo with speed blur",
        "person_present": "yes (rider on bike, helmet)",
        "face_visible": "no", "number_of_people": 1,
        "object_of_focus": "the racing bike + '18+ months?' hook",
        "text_on_image": "yes",
        "headline_on_image": "Do Pre-Awards integrations really need 18+ months to build?",
        "headline_style": "mixed-weight bold with '18+ months?' enlarged",
        "headline_chars": 60,
        "subheadline_on_image": "GrantsNow does it faster",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + contact footer strip + UNIT4 Partner + Oracle Partner logos BR",
        "brand_placement": "corners + footer contact strip + partner co-brand row",
        "graphic_style": "sports action photo with typographic hook",
        "notable_element": "IDENTICAL CAPTION, HEADLINE, URL AND VISUAL AS SS017. Fifth duplicate cluster in the set. Together with SS043's frustrated-executive portrait, this is now a three-post lineage around the '18 months integration' pain.",
        "campaign": "demo - Oracle integration",
        "angle": "product_capability",
    },
    {
        "post_id": "SS045", "batch": "batch10",
        "view_completeness": "top-cropped", "cta_confidence": "inferred",
        "caption": (
            "We all know the following, finding the right funding opportunity "
            "can feel like searching for a needle in a haystack. Institutions "
            "have waited a long time for smarter alerts, in depth filtering, "
            "and the ability to pinpoint specific grants that align with their "
            "goals, so they can spend more time innovating and less time "
            "searching for funding.\n\n"
            "🎯 The good news\n"
            "Institutions are already able to access a 25% increase in funding "
            "opportunities using the Funder Opportunity Scanner tool found on "
            "GrantsNow's highly intuitive platform, taking searching for "
            "funding opportunities from a highly manual, time consuming process "
            "to a quick accurate search.\n\n"
            "🎯 Why this matters:\n"
            "In today's competitive funding landscape, being first to know "
            "about the right opportunities can make all the difference. Our "
            "centralised, AI enhanced solution, continuously scans UK, EU, and "
            "global funding landscapes and delivers relevant opportunities "
            "straight to you. No endless searches. No manual processes. Just "
            "smarter discovery and more opportunity.\n\n"
            "🎯 Features:\n"
            "Smart Search by Your Priorities: Filter funding calls by keyword, "
            "discipline, career stage, funder, award type, closing date, and "
            "more.\n"
            "AI Powered Alerts: Receive instant, personalised alerts for new "
            "funding opportunities based on your interests and expertise.\n"
            "Funding News & Policy Updates: Stay ahead of the curve with "
            "curated news and key funding policy developments from major "
            "funders.\n"
            "Collaborate and Share: Spot an ideal opportunity? Share it "
            "seamlessly with colleagues or teams.\n"
            "Automatic Template Magic: Funding call data is automatically "
            "converted into funder templates.\n\n"
            "🎯 Who's Already on the Platform?:\n"
            "The Scanner covers a wide range of leading funders, including UK "
            "Research and Innovation (UKRI), Horizon Europe, NIH, Wellcome "
            "Trust, Cancer Research UK, and global organisations such as the "
            "Bill & Melinda Gates Foundation.\n\n"
            "🎯 Final Thoughts:\n"
            "If you're serious about unlocking the right funding faster and "
            "smarter, more and more universities are finding Funder Opportunity "
            "Scanner a great advantage.\n\n"
            "#ResearchInnovation #GrantsNow #AI #GrantFunding #HigherEd "
            "#Education #Grants"
        ),
        "value_prop_line": "Institutions are already able to access a 25% increase in funding opportunities using the Funder Opportunity Scanner on GrantsNow's platform.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "funding opportunity, needle in a haystack, smarter alerts, funder opportunity scanner, UKRI, Horizon Europe, NIH, Wellcome Trust, Cancer Research UK, Bill & Melinda Gates Foundation, AI, higher education",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "article",
        "cta_placement": "throughout (sectioned)",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad - heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "illustrated card preview with product headline",
        "image_subject": "illustration of people with computers + product claim card + partner logos + arrow",
        "background_type": "solid",
        "background_dominant_colour": "dark teal card + cream area",
        "foreground_dominant_colour": "teal type + white illustration + orange accent + partner logos",
        "palette": "brand-teal + gold + illustrated",
        "contrast_level": "high",
        "texture": "flat illustration with product card",
        "person_present": "yes (illustrated)",
        "face_visible": "yes (illustrated)", "number_of_people": 2,
        "object_of_focus": "the 25% claim card with partner co-brand row",
        "text_on_image": "yes",
        "headline_on_image": "Increase your Grants Funding opportunities by 25%",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 50,
        "subheadline_on_image": "With the Funder Opportunity Scanner",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo + UNIT4 Partner + Oracle Partner (visible on the card)",
        "brand_placement": "top + partner co-brand row",
        "graphic_style": "long-form article carousel/preview - longest caption in the set",
        "notable_element": "longest caption by an order of magnitude + 🎯 target emoji as section headers (new device) + specific funder names (UKRI, Horizon Europe, NIH, Wellcome Trust, Cancer Research UK, Bill & Melinda Gates Foundation) - highest specificity in the set + first article-style long-form treatment",
        "campaign": "article - Funder Opportunity Scanner deep-dive",
        "angle": "thought_leadership + product_capability",
    },
    {
        "post_id": "SS046", "batch": "batch10",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "We know the options for Pre- and Post-Awards Management software "
            "are limited, especially when most are built on technology that's "
            "nearly a decade old. GrantsNow is different. As a true SaaS "
            "solution, it comes with modern, pre-built integrations for ERP, "
            "Finance, and HR systems, bringing unmatched efficiency and "
            "innovation.\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #grantsmanagement #preawards #postawards #SaaS"
        ),
        "value_prop_line": "GrantsNow is a true SaaS solution with modern, pre-built integrations for ERP, Finance, and HR systems.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards, post-awards management, decade-old tech, true SaaS, pre-built integrations, ERP, finance, HR systems",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "portrait photo + typography on light background",
        "image_subject": "woman sitting cross-legged with laptop, smiling (soft mono/desaturated) on cream background",
        "background_type": "solid",
        "background_dominant_colour": "cream-white with subtle wave motif",
        "foreground_dominant_colour": "dark teal type + gold star accent + soft photo",
        "palette": "brand-teal + gold + cream",
        "contrast_level": "medium",
        "texture": "flat cream with soft-focus portrait",
        "person_present": "yes", "face_visible": "yes (smiling)",
        "number_of_people": 1,
        "object_of_focus": "the punchline 'Think Again.' + the smiling person",
        "text_on_image": "yes",
        "headline_on_image": "Still investing time and money into decade-old Pre-awards tech?",
        "headline_style": "sentence-case mixed-weight with 'decade-old' emphasised",
        "headline_chars": 63,
        "subheadline_on_image": "Think Again.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "light editorial - cream background with soft portrait and two-word close",
        "notable_element": "first cream-background portrait (rest use dark-teal overlays) + 'Think Again.' two-word punchline close + gold star as micro-accent (new element)",
        "campaign": "demo - decade-old tech callout",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS047", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow's Funder Opportunity Scanner automates this process and "
            "highlights matched calls based on your research strengths. A first "
            "in UK higher education. Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#FundingCalls #ResearchSupport #GrantOpportunities #HigherEdUK "
            "#GrantsNow"
        ),
        "value_prop_line": "GrantsNow's Funder Opportunity Scanner highlights matched calls based on your research strengths - a first in UK higher education.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "funder opportunity scanner, matched calls, research strengths, UK higher education, funding calls, research support, grant opportunities",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography",
        "image_subject": "hand pointing at screen with blurred data/charts, dark teal overlay",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office",
        "foreground_dominant_colour": "white all-caps type + gold divider",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "partial (hand only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the all-caps 'WHY IS FINDING FUNDING STILL A MANUAL TASK?' hook",
        "text_on_image": "yes",
        "headline_on_image": "WHY IS FINDING FUNDING STILL A MANUAL TASK?",
        "headline_style": "all-caps bold",
        "headline_chars": 43,
        "subheadline_on_image": "Research offices spend hours searching for opportunities across multiple sites.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with all-caps question hook",
        "notable_element": "fifth all-caps headline in the set + 'A first in UK higher education' positioning claim in the caption (rarely used exclusivity language)",
        "campaign": "demo - Funder Opportunity Scanner",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS048", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Last minute deadlines, missing documents and manually creating "
            "proposal templates is slowing down the grants funding process. "
            "GrantsNow solves this with structured proposal templates, required "
            "fields and automated prompts so submissions are completed before "
            "they reach your office. Get in touch: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#ResearchAdmin #GrantPreparation #UniversityResearch #PreAward "
            "#GrantsNow"
        ),
        "value_prop_line": "GrantsNow solves this with structured proposal templates, required fields and automated prompts so submissions are completed before they reach your office.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "last minute deadlines, missing documents, proposal templates, required fields, automated prompts, research admin, grant preparation, pre-award",
        "tone": "authoritative",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography with yellow highlighter",
        "image_subject": "hand on tablet with document icons overlay, dark teal tint",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted tech photo",
        "foreground_dominant_colour": "white all-caps type + yellow highlighter on 'MISSING' + teal pill",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "partial (hand only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the all-caps 'CHASING RESEARCHERS FOR MISSING DOCUMENTS?' hook + response pill",
        "text_on_image": "yes",
        "headline_on_image": "STILL CHASING RESEARCHERS FOR MISSING DOCUMENTS?",
        "headline_style": "all-caps bold with yellow highlighter on 'MISSING'",
        "headline_chars": 48,
        "subheadline_on_image": "GrantsNow solves exactly this problem!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with all-caps hook and yellow highlighter accent",
        "notable_element": "sixth all-caps headline + yellow highlighter on a single word (like SS026 SS027 SS031 SS043) + question-plus-response pill pairing",
        "campaign": "demo - proposal templates",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS049", "batch": "batch11",
        "view_completeness": "top-cropped", "cta_confidence": "unknown",
        "caption": (
            "Merry Christmas from the GrantsNow team! Sending our best wishes "
            "to our partners across higher education and everyone has supported "
            "us this year 🎄🎁❄️👨‍💼\n\n"
            "#preawards #grantsmanagement #grantsnow #postawards"
        ),
        "value_prop_line": "n/a - seasonal greeting post",
        "value_prop_in_first_3_sentences": "n/a",
        "industry_keywords": "christmas, higher education, partners",
        "tone": "conversational",
        "pov": "brand-third-person",
        "offer_type": "seasonal",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "seasonal photo with typography",
        "image_subject": "snowy holly leaves and red berries with 'Merry Christmas' typography",
        "background_type": "photographic",
        "background_dominant_colour": "dark green holly with white snow",
        "foreground_dominant_colour": "white serif type + white script type",
        "palette": "natural-seasonal (dark green + white + red)",
        "contrast_level": "high",
        "texture": "photo realistic with snow overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the Merry Christmas serif greeting",
        "text_on_image": "yes",
        "headline_on_image": "Merry Christmas",
        "headline_style": "serif italic large + script sub",
        "headline_chars": 15,
        "subheadline_on_image": "From the GrantsNow Team",
        "image_cta_text": "",
        "brand_marks": "GrantsNow team signature in script",
        "brand_placement": "centred in headline",
        "graphic_style": "editorial holiday card - completely off-template",
        "notable_element": "first and only seasonal / holiday post in the set + first with emojis in the caption (four decorative emojis) + first serif italic type + no offer, no CTA",
        "campaign": "seasonal - Christmas greeting",
        "angle": "community_celebration",
    },
    {
        "post_id": "SS050", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Is your university struggling with inefficiencies in pre-award "
            "processes that delay submissions?\n\n"
            "GrantsNow can help streamline your workflows by centralising tasks "
            "like proposal submissions, compliance tracking, and budgeting. By "
            "automating these key elements, you will reduce processing time, "
            "eliminate errors, and ensure smoother collaboration between "
            "departments. This not only boosts efficiency but also increases "
            "your chances of securing more funding with less manual work "
            "involved.\n\n"
            "#GrantsNow #PreAwardExcellence #HigherEfficiency"
        ),
        "value_prop_line": "GrantsNow streamlines workflows by centralising tasks like proposal submissions, compliance tracking, and budgeting.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "university, pre-award inefficiencies, workflows, proposal submissions, compliance tracking, budgeting, ERP integration",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad - light (3 tags)",
        "media_type": "image",
        "primary_visual": "photo + typography with response pill",
        "image_subject": "smiling businessman at laptop, professional casual",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office with warm accent",
        "foreground_dominant_colour": "white type + white response pill",
        "palette": "brand-teal + white + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with overlay",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 1,
        "object_of_focus": "the ERP question + 'When GrantsNow does it for you' response pill",
        "text_on_image": "yes",
        "headline_on_image": "Why should you get an entire team to integrate your Pre-Award platform with your ERP?",
        "headline_style": "mixed-weight bold",
        "headline_chars": 85,
        "subheadline_on_image": "When GrantsNow does it for you",
        "image_cta_text": "",
        "brand_marks": "GrantsNow check-mark logo TR (unusual placement - only post with just the check mark)",
        "brand_placement": "TR check-mark only",
        "graphic_style": "photo hero with question and response pill - fourth ERP/18-month variant",
        "notable_element": "fourth ERP/integration campaign variant (SS017, SS043, SS044, SS050) + only post with just the check-mark logo (no full GrantsNow wordmark visible) + 3 hashtags (very light)",
        "campaign": "brand awareness - ERP integration",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS051", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Make your Pre Awards system work your way. With GrantsNow, you can "
            "quickly configure forms, fields, hierarchies and approval "
            "workflows without waiting on developers.\n\n"
            "#ResearchFunding #PreAwards #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "With GrantsNow, you can quickly configure forms, fields, hierarchies and approval workflows without waiting on developers.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards system, configure, forms, fields, hierarchies, approval workflows, developers",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "Switch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "typography on dark gradient with seasonal snowflakes",
        "image_subject": "dark teal background with subtle snowflake motif and headline claim",
        "background_type": "gradient",
        "background_dominant_colour": "dark teal with subtle snowflakes",
        "foreground_dominant_colour": "white type + teal accent italics",
        "palette": "brand-teal + white + seasonal-snow",
        "contrast_level": "high",
        "texture": "flat gradient with snowflake overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the 'in minutes not months' claim + Switch pill",
        "text_on_image": "yes",
        "headline_on_image": "Configure forms, fields, hierarchies & approvals in minutes not months",
        "headline_style": "mixed-weight bold with teal italic accent on 'forms, fields, hierarchies & approvals'",
        "headline_chars": 69,
        "subheadline_on_image": "Switch to GrantsNow",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo top-centre",
        "brand_placement": "top-centre",
        "graphic_style": "typography-only dark poster with snowflake seasonal motif",
        "notable_element": "seasonal snowflake motif on a product poster (winter campaign, not Christmas message) + teal italic accent inside the headline + no photo, no footer strip",
        "campaign": "demo - configurable Pre-Awards",
        "angle": "product_capability",
    },
    {
        "post_id": "SS052", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Managing integrations, reports, and configurations in-house can "
            "drain valuable time and resources. With GrantsNow, you don't have "
            "to. Our team of 250+ consultants ensures seamless integration and "
            "customisation, so you can focus on what truly matters.\n\n"
            "#HigherEdTech #GrantsNow #GrantManagement #Automation #Efficiency "
            "#SeamlessIntegration"
        ),
        "value_prop_line": "Our team of 250+ consultants ensures seamless integration and customisation so you can focus on what truly matters.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "integrations, reports, configurations, 250+ consultants, seamless integration, customisation, higher ed tech, automation",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "typography on dark gradient with seasonal snowflakes",
        "image_subject": "dark teal background with subtle snowflakes and IT-team question",
        "background_type": "gradient",
        "background_dominant_colour": "dark teal with subtle snowflakes",
        "foreground_dominant_colour": "white type + teal italic accent on 'burdened'",
        "palette": "brand-teal + white + seasonal-snow",
        "contrast_level": "high",
        "texture": "flat gradient with snowflake overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the IT-team question with 'burdened' italic accent + sub-claim",
        "text_on_image": "yes",
        "headline_on_image": "Is your IT team burdened with integrations, reports and configurations",
        "headline_style": "mixed-weight bold with teal italic accent on 'burdened'",
        "headline_chars": 74,
        "subheadline_on_image": "A Fully configurable & seamless Pre-Award solution integrated with your ERP",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo top-centre",
        "brand_placement": "top-centre",
        "graphic_style": "typography-only dark poster with snowflake seasonal motif",
        "notable_element": "SAME CAPTION AS SS030 but the creative is completely different - SS030 was a photo of six people in a meeting, SS052 is a snowflake typography poster. Same message, two very different visual worlds. This is the strongest signal in the set for testing whether the visual template alone changes performance when everything textual is held constant.",
        "campaign": "demo - IT team burden",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS053", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Many solutions claim to be SaaS, but few actually are. A TRUE SaaS "
            "platform has a single codebase, instant updates, and scalable "
            "configurations. Read the blog to know more: "
            "https://lnkd.in/eqK3_-vN\n\n"
            "#grantsnow #preawards #research #grantsmanagement #armauk #SaaS"
        ),
        "value_prop_line": "A TRUE SaaS platform has a single codebase, instant updates, and scalable configurations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "SaaS, True SaaS, single codebase, instant updates, scalable configurations, pre-awards, research management, ARMA UK, save 35% budget, increase grants funding by 25%",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "blog",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "typography on dark navy with sticky-note pills",
        "image_subject": "dark navy background with dotted pattern + question headline + two teal sticky-note pills with stats",
        "background_type": "solid",
        "background_dominant_colour": "dark navy with dotted pattern",
        "foreground_dominant_colour": "white type + teal sticky pills + white CTA pill",
        "palette": "brand-teal + navy + white",
        "contrast_level": "high",
        "texture": "flat with dotted pattern",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the question headline + two sticky-note stats (Save 35% Budget, Increase Grants Funding by 25%)",
        "text_on_image": "yes",
        "headline_on_image": "IS your platform TRUE SaaS or just older tech hosted on cloud",
        "headline_style": "mixed-weight bold",
        "headline_chars": 60,
        "subheadline_on_image": "Save 35% Budget + Increase Grants Funding by 25%",
        "image_cta_text": "Futureproof your university today",
        "brand_marks": "GrantsNow logo top-centre + Futureproof CTA pill",
        "brand_placement": "top-centre + centred CTA pill",
        "graphic_style": "typography poster with sticky-note stat pills",
        "notable_element": "SAME CAPTION AS SS026, SS027, SS031 (True SaaS blog cluster) but the visual is a dark navy typography poster with sticky-note stat pills - fourth visual variant of the same blog. Combined with SS027/SS031 (photo variants) and SS026 (photo with 2 women), this is the biggest visual A/B/C/D pool for one blog piece.",
        "campaign": "blog - True SaaS",
        "angle": "thought_leadership",
    },
    {
        "post_id": "SS054", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "GrantsNow empowers research offices to identify the right "
            "opportunities faster, streamline submissions, and increase funding "
            "success through automation and smart integrations. Find out how: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #ResearchFunding #GrantsManagement #PreAwards "
            "#HigherEducation #FundingSuccess #ResearchInnovation"
        ),
        "value_prop_line": "GrantsNow empowers research offices to identify opportunities faster, streamline submissions, and increase funding success through automation and integrations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research offices, funding opportunities, submissions, automation, integrations, higher education, funding success, research innovation",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Find out",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad - very heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "typography on dark solid",
        "image_subject": "dark teal solid with headline claim and sub",
        "background_type": "solid",
        "background_dominant_colour": "dark teal",
        "foreground_dominant_colour": "white type + teal italic accent on 'solution'",
        "palette": "brand-teal + white",
        "contrast_level": "high",
        "texture": "flat solid",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the solution claim + sub about Pre-Award integration",
        "text_on_image": "yes",
        "headline_on_image": "The solution for maximising Grants funding opportunities",
        "headline_style": "mixed-weight bold with teal italic accent on 'solution'",
        "headline_chars": 55,
        "subheadline_on_image": "A Fully configurable & seamless Pre-Award solution integrated with your ERP",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo bottom-centre",
        "brand_placement": "bottom-centre",
        "graphic_style": "typography-only dark poster",
        "notable_element": "SAME CAPTION AS SS018 (which was a bright photo of a businessman with team) but this is a dark typography-only poster - clean visual A/B",
        "campaign": "demo - funding success",
        "angle": "product_capability",
    },
    {
        "post_id": "SS055", "batch": "batch11",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "Imagine freeing up 35% of your team's time to work on only the "
            "most important tasks - that's what GrantsNow can do by automating "
            "manual, repetitive tasks that bog down the grant submission "
            "process.\n\n"
            "With more time available, your team can increase the number of "
            "funding applications they submit by over a third, leading to "
            "significantly more grant approvals and funding. More submissions "
            "mean more opportunities for research growth, and GrantsNow makes "
            "it happen efficiently.\n\n"
            "#GrantsNow #TimeSavings #MoreSubmissions #grantsmanagement "
            "#educationtrends"
        ),
        "value_prop_line": "GrantsNow can free up 35% of your team's time by automating manual, repetitive tasks that bog down the grant submission process.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "35% time savings, funding applications, grant approvals, grant submission process, automation, time savings, more submissions, education trends",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - mixed case",
        "media_type": "image",
        "primary_visual": "photo + typography with teal circle accent",
        "image_subject": "hand pointing at a wrist watch on another wrist, dark teal-tinted photo",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted photo",
        "foreground_dominant_colour": "white type + teal accent on '35%' + teal circle around watch",
        "palette": "brand-teal + white + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes (hands only)", "face_visible": "no",
        "number_of_people": 2,
        "object_of_focus": "the wristwatch with teal circle drawn around it + 35% claim",
        "text_on_image": "yes",
        "headline_on_image": "How does freeing up 35% more time for Grants Submissions sound",
        "headline_style": "mixed-weight bold with teal accent on '35%'",
        "headline_chars": 62,
        "subheadline_on_image": "",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo top-centre",
        "brand_placement": "top-centre",
        "graphic_style": "photo hero with wrist-watch time metaphor and hand-drawn teal circle accent",
        "notable_element": "first watch/time visual metaphor + hand-drawn teal circle as accent (new device) + 35% stat (SS053 also used 35%) + 'Imagine freeing up X%' opener (like SS033's 'Imagine being able to')",
        "campaign": "brand awareness - time savings",
        "angle": "product_capability",
    },
    {
        "post_id": "SS056", "batch": "batch11",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Looking for a single cloud platform to manage BOTH Pre & Post "
            "Awards, including Ethics & Contracts? GrantsNow delivers it "
            "all-fully integrated, highly configurable, and built on modern "
            "Oracle Cloud technology!\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #grantsmanagement #preawards #postwards #cloud #SaaS"
        ),
        "value_prop_line": "GrantsNow delivers it all - fully integrated, highly configurable, and built on modern Oracle Cloud technology.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "single cloud platform, Pre & Post Awards, Ethics & Contracts, Oracle Cloud, SaaS, grants management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase (has typo #postwards)",
        "media_type": "image",
        "primary_visual": "portrait photo + testimonial speech card",
        "image_subject": "smiling man at laptop, professional casual",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office",
        "foreground_dominant_colour": "cream speech card + teal accent + gold status pill",
        "palette": "brand-teal + gold + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with overlay",
        "person_present": "yes", "face_visible": "yes (smiling)",
        "number_of_people": 1,
        "object_of_focus": "the testimonial speech card + 'GrantsNow has it all!' pill",
        "text_on_image": "yes",
        "headline_on_image": "Thanks to GrantsNow, I have a single cloud platform to manage both Pre & Post Awards including ethics and contracts",
        "headline_style": "first-person testimonial in quote marks",
        "headline_chars": 115,
        "subheadline_on_image": "GrantsNow has it all!",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL",
        "brand_placement": "TL only",
        "graphic_style": "portrait-plus-speech-card - first testimonial in the set",
        "notable_element": "FIRST TESTIMONIAL-STYLE POST (first-person quote from a smiling user) + typo in hashtag #postwards missing an 'a' + no HM Government badge + em-dash in caption 'delivers it all-fully'",
        "campaign": "demo - single cloud platform",
        "angle": "product_capability + community_celebration",
    },
    {
        "post_id": "SS057", "batch": "batch12",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow is empowering research teams to work smarter, not harder. "
            "Discover why UK institutions are opting for a platform designed for "
            "outcomes, not workarounds. Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #PreAwardSoftware #ResearchManagement #HigherEdTech "
            "#TrueSaaS #UKUniversities"
        ),
        "value_prop_line": "GrantsNow is a platform designed for outcomes, not workarounds - 25% funding lift, 35% cost saved, fastest-growing True SaaS in the UK.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research teams, UK institutions, pre-award software, higher ed tech, True SaaS, 25% funding, 35% cost saved",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo (B&W portrait) + typography with scattered stat cards",
        "image_subject": "smiling black-and-white portrait of a man with crossed arms surrounded by three stat cards",
        "background_type": "solid",
        "background_dominant_colour": "dark teal with subtle wave pattern",
        "foreground_dominant_colour": "large teal all-caps + white stat cards + cartoon '!!!' + Visit pill",
        "palette": "brand-teal + white + black-and-white portrait",
        "contrast_level": "high",
        "texture": "flat solid with B&W portrait cut-out and flat cards",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 1,
        "object_of_focus": "the smiling portrait + three scattered stat cards (25% funding, 35% cost, fastest-growing)",
        "text_on_image": "yes",
        "headline_on_image": "NEED MORE FUNDING FOR YOUR UNIVERSITY?",
        "headline_style": "large teal all-caps sans-serif",
        "headline_chars": 39,
        "subheadline_on_image": "25% Increase in Grants Funding opportunities | 35% Cost saved when implementing GrantsNow | Fastest Growing True SaaS cloud Pre-Award platform in the UK",
        "image_cta_text": "Visit GrantsNow.co.uk",
        "brand_marks": "GrantsNow logo (implicit in Visit pill) - no HM Government badge",
        "brand_placement": "distributed on the cards",
        "graphic_style": "editorial cut-out portrait with scattered stat cards - youthful magazine feel",
        "notable_element": "SAME CAPTION AS SS032 but visually the opposite - SS032 was architectural photo with a 3-column question card, SS057 is a portrait cut-out with scattered stat cards. Direct visual A/B on the same words. Also uses same three stats (25%, 35%, fastest-growing) as SS032 sub-list.",
        "campaign": "demo - GrantsNow Treatment",
        "angle": "product_capability",
    },
    {
        "post_id": "SS058", "batch": "batch12",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Searching for the next generation in pre-awards software? "
            "GrantsNow is here, making pre and post-award administration "
            "faster, automated and easily integrated.\n\n"
            "#GrantsNow #PreAwardSoftware #PostAwardManagement #ResearchGrants "
            "#HigherEdTech #UKUniversities #SmartFunding #FutureReady"
        ),
        "value_prop_line": "GrantsNow is here, making pre and post-award administration faster, automated and easily integrated.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "next generation, pre-awards software, post-award management, automation, integration, higher ed tech, smart funding, future ready",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad + niche - very heavy (8 tags)",
        "media_type": "image",
        "primary_visual": "photo (space astronaut) with expanded typography",
        "image_subject": "astronaut in white spacesuit reaching outward with earth curve visible in background",
        "background_type": "photographic",
        "background_dominant_colour": "black space + blue earth curve",
        "foreground_dominant_colour": "white all-caps type + teal accent + green check",
        "palette": "black + brand-teal + white + photographic",
        "contrast_level": "very high",
        "texture": "photo realistic with cosmic backdrop",
        "person_present": "yes (astronaut)", "face_visible": "no (helmet)",
        "number_of_people": 1,
        "object_of_focus": "the DON'T GET LOST hook + astronaut + 25%+ claim",
        "text_on_image": "yes",
        "headline_on_image": "DONT GET LOST",
        "headline_style": "all-caps bold (no apostrophe in this variant)",
        "headline_chars": 13,
        "subheadline_on_image": "Searching for an advanced Pre-Awards Platform.... Increase funding opportunities by 25%+ with GrantsNow",
        "image_cta_text": "",
        "brand_marks": "GrantsNow check-mark BR (no HM Government badge)",
        "brand_placement": "BR check-mark only",
        "graphic_style": "cinematic space photo with punchy short hook and expanded on-image copy",
        "notable_element": "near-duplicate of SS028 but with two textual changes: (1) apostrophe missing from 'DONT' in this creative, (2) caption slightly softened ('automated and easily integrated' vs 'more automated and better integrated'). Caption is NOT byte-identical to SS028 so does not count as a hard duplicate; treat as a refinement.",
        "campaign": "brand awareness - next generation",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS059", "batch": "batch12",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "💡 Many schools miss out on valuable grants, not because they're "
            "not eligible, but because they don't have the tools or time to "
            "find and manage them.\n\n"
            "With GrantsNow, your team can:\n"
            "• Easily discover local, regional, and federal funding "
            "opportunities\n"
            "• Collaborate in one place with clear workflows\n"
            "• Track deadlines and submissions with ease\n\n"
            "#EducationGrants #K12Solutions #FundingSuccess #EdLeaders"
        ),
        "value_prop_line": "With GrantsNow, your team can easily discover local, regional, and federal funding opportunities, collaborate in one place, and track deadlines.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "K12, schools, local regional federal funding, education grants, workflows, deadlines, ed leaders",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "US K-12 audience (first non-UK targeting)",
        "media_type": "image",
        "primary_visual": "photo + massive typography with lock icon",
        "image_subject": "man with beard and glasses at laptop, teal background, large caps type framing him",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted photo",
        "foreground_dominant_colour": "white all-caps type + teal script accent + gold lock icon",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay + flat type",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 1,
        "object_of_focus": "the massive 'GRANTS FUNDING' letters + 'UNLOCK MORE' pill with lock icon",
        "text_on_image": "yes",
        "headline_on_image": "GRANTS UNLOCK MORE FUNDING",
        "headline_style": "very large all-caps sans-serif with lock icon in inline pill",
        "headline_chars": 26,
        "subheadline_on_image": "WITH LESS COST",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo top-centre",
        "brand_placement": "top-centre",
        "graphic_style": "typography-hero with portrait framed inside the letters + lock icon and script accent",
        "notable_element": "FIRST US K-12 schools audience targeting in the whole set (rest is UK higher ed) + first emoji lightbulb 💡 at the very start of a caption + first padlock icon + first handwritten script accent 'WITH LESS COST' - completely new visual and audience combination",
        "campaign": "brand awareness - K-12 schools US market",
        "angle": "product_capability",
    },
    {
        "post_id": "SS060", "batch": "batch12",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Research teams deserve tools that remove complexity, not add to it. "
            "GrantsNow streamlines key Pre and Post Award tasks so your staff can "
            "focus more on delivering impactful research, not admin.\n\n"
            "#ResearchFunding #PreAwards #PostAwards #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "GrantsNow streamlines key Pre and Post Award tasks so staff can focus on impactful research, not admin.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research teams, pre-award, post-award, admin, research funding, research management",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "hands typing on keyboard with plants in background + teal card centred",
        "background_type": "photographic",
        "background_dominant_colour": "muted green-grey desk photo",
        "foreground_dominant_colour": "teal card + cream border + white all-caps type",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with subtle overlay",
        "person_present": "partial (hands only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the all-caps 'DO MORE IN LESS TIME' headline",
        "text_on_image": "yes",
        "headline_on_image": "DO MORE IN LESS TIME.",
        "headline_style": "all-caps bold",
        "headline_chars": 21,
        "subheadline_on_image": "Streamline Pre and Post-Award instantly with GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with short all-caps hook",
        "notable_element": "IDENTICAL CAPTION, HEADLINE, URL AND VISUAL AS SS020. Sixth byte-identical duplicate in the set (after SS013/SS036, SS017/SS044, SS022/SS040, SS023/SS041).",
        "campaign": "brand awareness - streamline Pre and Post-Award",
        "angle": "product_capability",
    },
    {
        "post_id": "SS061", "batch": "batch12",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Make your Pre Awards system work your way. With GrantsNow, you can "
            "quickly configure forms, fields, hierarchies and approval "
            "workflows without waiting on developers.\n\n"
            "#ResearchFunding #PreAwards #ResearchManagement #GrantsNow"
        ),
        "value_prop_line": "With GrantsNow, you can quickly configure forms, fields, hierarchies and approval workflows without waiting on developers.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards system, configure, forms, fields, hierarchies, approval workflows, developers",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "Switch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography with response pill",
        "image_subject": "office scene with people silhouetted in background, dark teal overlay",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office silhouettes",
        "foreground_dominant_colour": "white all-caps type inside a bordered card + teal pill",
        "palette": "brand-teal + white + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "yes (silhouettes)", "face_visible": "no",
        "number_of_people": 2,
        "object_of_focus": "the all-caps 'IN MINUTES. NOT MONTHS!' hook + Switch pill",
        "text_on_image": "yes",
        "headline_on_image": "CONFIGURE FORMS, FIELDS, HIERARCHIES AND APPROVALS IN MINUTES. NOT MONTHS!",
        "headline_style": "all-caps bold with 'NOT MONTHS!' enlarged as punchline",
        "headline_chars": 74,
        "subheadline_on_image": "Switch to GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with all-caps hook - SS051 was snowflake typography, SS061 is photo overlay",
        "notable_element": "SAME CAPTION AS SS051 but the creative is completely different - SS051 was a snowflake typography poster, SS061 is an office silhouette photo hero. Another visual A/B pair on the same words.",
        "campaign": "demo - configurable Pre-Awards",
        "angle": "product_capability",
    },
    {
        "post_id": "SS062", "batch": "batch13",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "ERP integrations should not take 18 months. GrantsNow delivers "
            "faster, seamless connectivity so your team can focus on winning "
            "more funding, not waiting on integrations.\n\n"
            "#GrantsNow #PreAwards #ERPIntegration #ResearchFunding "
            "#HigherEducation"
        ),
        "value_prop_line": "GrantsNow delivers faster, seamless connectivity so your team can focus on winning more funding, not waiting on integrations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "ERP integrations, 18 months, seamless connectivity, winning funding, pre-awards, higher education",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "portrait photo + typography with inner speech bubble",
        "image_subject": "frustrated businessman with head resting on hand, office in background",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office",
        "foreground_dominant_colour": "white type + yellow highlighter on '18 months' + cream speech-bubble",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with overlay",
        "person_present": "yes", "face_visible": "yes (expressive)",
        "number_of_people": 1,
        "object_of_focus": "the frustrated portrait + '18 months' highlight + inner monologue speech bubble",
        "text_on_image": "yes",
        "headline_on_image": "Should it really take 18 months to build the ERP integrations to my Pre-Awards Platform?",
        "headline_style": "mixed-weight bold with yellow highlighter on '18 months'",
        "headline_chars": 89,
        "subheadline_on_image": "Wish I'd known about GrantsNow sooner",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "character-driven portrait with inner monologue speech bubble",
        "notable_element": "IDENTICAL CAPTION, HEADLINE, URL AND VISUAL AS SS043. Seventh byte-identical duplicate in the set. The '18 months integration' theme now has SS017, SS043, SS044, SS062 - four rows, three unique creatives (MotoGP twice + frustrated exec twice).",
        "campaign": "demo - ERP integration speed",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS063", "batch": "batch13",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Budgets are tight and research teams need tools that deliver real "
            "value. GrantsNow gives universities an affordable way to manage "
            "Pre-Awards work without the complexity. If you are looking for a "
            "smarter, budget friendly option, we can help.\n\n"
            "#GrantsNow #ResearchFunding #HigherEducation #PreAwards "
            "#GrantsManagement #UniversityResearch"
        ),
        "value_prop_line": "GrantsNow gives universities an affordable way to manage Pre-Awards work without the complexity.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "budgets, research teams, real value, affordable, budget friendly, universities, pre-awards, university research",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + quote-style typography with response pill",
        "image_subject": "person at laptop in background, dark teal overlay + quote-mark all-caps card",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office",
        "foreground_dominant_colour": "white all-caps quote + gold quotation marks + teal 'covered' pill",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "yes (background)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the quote-style headline + 'We've got you covered!' response pill",
        "text_on_image": "yes",
        "headline_on_image": "\"IN THESE TIMES OF CHALLENGING BUDGETS, WE NEED AN AFFORDABLE PRE-AWARDS SOLUTION\"",
        "headline_style": "all-caps bold inside gold quotation marks",
        "headline_chars": 82,
        "subheadline_on_image": "We've got you covered!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with quote-mark treatment - implied testimonial from a decision maker",
        "notable_element": "first quote-mark treatment on the headline (with gold opening/closing quotes) + 'affordable' / 'budget friendly' positioning - only post explicitly leading with price + eighth all-caps headline",
        "campaign": "brand awareness - affordable pre-awards",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS064", "batch": "batch13",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Most Pre-Awards systems run on outdated tech. GrantsNow is the "
            "only UK solution built on state-of-the-art SaaS Cloud, giving "
            "universities a faster and more future-ready platform for research "
            "funding.\n\n"
            "#GrantsNow #GrantsManagement #PreAwards #ResearchFunding #SaaS "
            "#HigherEducation #OracleCloud"
        ),
        "value_prop_line": "GrantsNow is the only UK solution built on state-of-the-art SaaS Cloud, giving universities a faster and more future-ready platform for research funding.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "outdated tech, only UK solution, state-of-the-art, SaaS Cloud, future-ready, universities, research funding, Oracle Cloud",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography with gold divider",
        "image_subject": "dark teal server-room/tech background with all-caps question and sub",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted server-room photo",
        "foreground_dominant_colour": "white all-caps type + gold divider line",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "partial (background)", "face_visible": "no",
        "number_of_people": 0,
        "object_of_focus": "the all-caps 'WHY BUY OUTDATED TECHNOLOGY?' question + gold divider + only-UK claim",
        "text_on_image": "yes",
        "headline_on_image": "WHY BUY A PRE-AWARD SOLUTION THAT IS ALREADY ON OUTDATED TECHNOLOGY?",
        "headline_style": "all-caps bold",
        "headline_chars": 66,
        "subheadline_on_image": "GrantsNow is the only Pre-Awards solution in the UK built on the latest state-of-the-art SaaS Cloud technology.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with all-caps question and gold divider - technology positioning",
        "notable_element": "ninth all-caps headline in the set + 'only UK solution' exclusivity claim (like SS047 'A first in UK higher education') + third variant of the decade-old / outdated / legacy tech theme (SS037, SS046, SS064)",
        "campaign": "brand awareness - outdated tech",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS065", "batch": "batch13",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Universities are uncovering significantly more funding "
            "opportunities by using a single platform that brings searchable "
            "global grant databases, custom alerts, and automation together. "
            "Want to find out how they're doing it?\n\n"
            "#GrantsNow #GrantsManagement #ResearchFunding #PreAwards "
            "#HigherEducation #FundingOpportunities"
        ),
        "value_prop_line": "A single platform that brings searchable global grant databases, custom alerts, and automation together.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "universities, funding opportunities, global grant databases, custom alerts, automation, funding opportunities, higher education",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography",
        "image_subject": "classroom/lecture scene with presenter and students, dark teal overlay",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted lecture hall",
        "foreground_dominant_colour": "white all-caps type + bold 'how' accent + downward arrow",
        "palette": "brand-teal + white + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "yes", "face_visible": "partial (multiple)",
        "number_of_people": 4,
        "object_of_focus": "the all-caps '25%+ INCREASE' claim + question prompt",
        "text_on_image": "yes",
        "headline_on_image": "UNIVERSITIES ARE FINDING A 25%+ INCREASE IN GRANTS FUNDING OPPORTUNITIES",
        "headline_style": "all-caps bold",
        "headline_chars": 71,
        "subheadline_on_image": "? Want to know how?",
        "image_cta_text": "downward arrow indicator (no URL)",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners (no footer strip)",
        "graphic_style": "photo hero with all-caps stat and interactive question prompt",
        "notable_element": "IDENTICAL CAPTION, HEADLINE AND VISUAL AS SS042. Eighth byte-identical duplicate in the set.",
        "campaign": "brand awareness - 25% funding lift",
        "angle": "product_capability",
    },
    {
        "post_id": "SS066", "batch": "batch13",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Access real-time cost comparisons with GrantsNow to make faster, "
            "more accurate funding decisions. Get in touch: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #GrantsManagement #ResearchFunding #HigherEducation"
        ),
        "value_prop_line": "Access real-time cost comparisons with GrantsNow to make faster, more accurate funding decisions.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "real-time cost comparisons, full economic costings, faster funding decisions, research funding, higher education",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche (light - 4 tags)",
        "media_type": "image",
        "primary_visual": "bright photo + all-caps typography",
        "image_subject": "smiling woman and man at a laptop, bright warm office photo",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral (like SS018, SS023)",
        "foreground_dominant_colour": "white all-caps type + gold divider + teal card border",
        "palette": "brand-teal + gold + bright-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo",
        "person_present": "yes", "face_visible": "yes (both smiling)",
        "number_of_people": 2,
        "object_of_focus": "the all-caps 'REAL-TIME COST COMPARISONS' claim + gold divider under it",
        "text_on_image": "yes",
        "headline_on_image": "GET REAL-TIME COST COMPARISONS AND FULL ECONOMIC COSTINGS AT YOUR FINGERTIPS.",
        "headline_style": "all-caps bold",
        "headline_chars": 78,
        "subheadline_on_image": "",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright team photo with all-caps hook - third bright variant (SS018, SS023, SS066)",
        "notable_element": "tenth all-caps headline in the set + third bright-daylight photo (SS018, SS023, SS066) - all three are person-plus-laptop team scenes in warm neutral tones",
        "campaign": "demo - real-time cost comparisons",
        "angle": "product_capability",
    },
    {
        "post_id": "SS067", "batch": "batch14",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Frustrated with complex pricing and approval workflows? GrantsNow "
            "simplifies your Pre-Awards process so you can focus on securing "
            "more research funding.\n\n"
            "#GrantsNow #PreAwards #ResearchFunding #GrantsManagement "
            "#HigherEducation"
        ),
        "value_prop_line": "GrantsNow simplifies your Pre-Awards process so you can focus on securing more research funding.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "complex pricing, approval workflows, pre-awards, research funding, grants management, higher education",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "portrait photo + cream card overlay with response pill",
        "image_subject": "young woman with head resting on laptop in defeat pose, warm daylight desk",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral (cream + wood tones)",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'help' pill",
        "palette": "brand-teal + gold + cream + photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo + flat card",
        "person_present": "yes", "face_visible": "partial (obscured by pose)",
        "number_of_people": 1,
        "object_of_focus": "the defeated posture + 'We can help you fix it' response pill",
        "text_on_image": "yes",
        "headline_on_image": "Managing complex pricing and approval workflows can be frustrating.",
        "headline_style": "sentence-case mixed-weight with 'complex' emphasised",
        "headline_chars": 68,
        "subheadline_on_image": "We can help you fix it with GrantsNow",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright editorial with defeated-pose portrait - shares aesthetic with SS046 (Think Again) and SS023 (Sounds neat)",
        "notable_element": "second defeated-pose portrait (after SS043 frustrated executive) but rendered in the bright cream aesthetic rather than the dark teal overlay - this pairs the emotional cue with the light-photo template",
        "campaign": "brand awareness - complex pricing",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS068", "batch": "batch14",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow empowers research offices to identify the right "
            "opportunities faster, streamline submissions, and increase funding "
            "success through automation and smart integrations. Find out how: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #ResearchFunding #GrantsManagement #PreAwards "
            "#HigherEducation #FundingSuccess #ResearchInnovation"
        ),
        "value_prop_line": "GrantsNow empowers research offices to identify opportunities faster, streamline submissions, and increase funding success through automation and integrations.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research offices, funding opportunities, submissions, automation, integrations, higher education, funding success, research innovation",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Find out",
        "has_question_prompt": "no",
        "hashtag_style": "brand + broad - very heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "photo + cream card overlay",
        "image_subject": "professional man in suit gesturing at a data screen with team behind him",
        "background_type": "photographic",
        "background_dominant_colour": "bright white-blue office",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'Only GrantsNow!' pill",
        "palette": "brand-teal + gold + bright-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo with flat card",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 4,
        "object_of_focus": "man pointing at data screen + 'Only GrantsNow!' claim",
        "text_on_image": "yes",
        "headline_on_image": "The solution for maximising Grants funding opportunities",
        "headline_style": "mixed-weight bold with 'maximising' emphasised",
        "headline_chars": 55,
        "subheadline_on_image": "Only GrantsNow!",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners",
        "graphic_style": "bright corporate photo with cream card",
        "notable_element": "IDENTICAL CAPTION, HEADLINE AND VISUAL AS SS018. Ninth byte-identical duplicate. The same caption also appears with a completely different creative in SS054 (dark typography-only) so this cluster is now a three-post visual-A/B group with two rows of the bright-photo variant and one row of the dark-typography variant.",
        "campaign": "demo - funding success",
        "angle": "product_capability",
    },
    {
        "post_id": "SS069", "batch": "batch14",
        "view_completeness": "bottom-cropped", "cta_confidence": "inferred",
        "caption": (
            "With GrantsNow, you can assign responsibilities, control access, "
            "and ensure data security within a fully configurable and "
            "user-friendly platform built for research offices.\n\n"
            "Learn more: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #GrantsManagement #PreAwards #ResearchFunding "
            "#DataSecurity #Compliance #HigherEducation"
        ),
        "value_prop_line": "With GrantsNow, you can assign responsibilities, control access, and ensure data security in a fully configurable platform for research offices.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "roles, permissions, responsibilities, access control, data security, configurable, research offices, pre-awards, compliance, higher education",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "learn_more",
        "cta_verb": "Learn",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - heavy (7 tags)",
        "media_type": "image",
        "primary_visual": "typography on light gradient",
        "image_subject": "cream-to-mint gradient with cream card and 'Imagine being able to...' headline",
        "background_type": "gradient",
        "background_dominant_colour": "cream to mint",
        "foreground_dominant_colour": "cream card + orange rounded border + teal type + teal pill",
        "palette": "brand-teal + gold + cream",
        "contrast_level": "medium",
        "texture": "flat gradient with subtle wave lines",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the imagined-outcome card + 'With GrantsNow you can!' pill response",
        "text_on_image": "yes",
        "headline_on_image": "Imagine being able to define roles and permissions in your Pre-Awards system.",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 77,
        "subheadline_on_image": "With GrantsNow you can!",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR",
        "brand_placement": "corners (no footer strip)",
        "graphic_style": "no-photo poster - cream card with question setup and cheeky response pill",
        "notable_element": "IDENTICAL CAPTION AND VISUAL AS SS033. Tenth byte-identical duplicate in the set.",
        "campaign": "demo - roles and permissions",
        "angle": "product_capability",
    },
    {
        "post_id": "SS070", "batch": "batch14",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Want to protect your reputation through ethical governance in "
            "research funding? We can help you stay compliant and manage grants "
            "ethically.\n\n"
            "Discover how GrantsNow makes it simple: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #GrantsManagement #ResearchFunding #PreAwards "
            "#PostAwards #EthicalGovernance #Compliance #HigherEducation "
            "#ResearchIntegrity #FundingSuccess"
        ),
        "value_prop_line": "GrantsNow helps you protect your reputation through ethical governance in research funding.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "reputation, ethical governance, research funding, compliance, grants ethically, research integrity, post-awards, higher education",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "learn_more",
        "cta_verb": "Discover",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - heaviest in the set (10 tags)",
        "media_type": "image",
        "primary_visual": "portrait photo + cream card overlay with response pill",
        "image_subject": "woman working at laptop in a cafe or bright office, side view",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral (like SS023, SS046, SS067)",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'help' pill",
        "palette": "brand-teal + gold + cream + photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo with flat card",
        "person_present": "yes", "face_visible": "yes (side)",
        "number_of_people": 1,
        "object_of_focus": "the ethical-governance question + 'We Can Help' pill",
        "text_on_image": "yes",
        "headline_on_image": "Want to strengthen ethical governance across your grants process?",
        "headline_style": "sentence-case mixed-weight with 'ethical governance' emphasised",
        "headline_chars": 65,
        "subheadline_on_image": "We Can Help",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright editorial portrait with question setup and response pill",
        "notable_element": "new heaviest hashtag load in the set (10 tags - beats SS025's 9 and SS028's 8) + first ethical-governance angle + fourth bright-cream portrait template (SS023 SS046 SS067 SS070)",
        "campaign": "demo - ethical governance",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS071", "batch": "batch14",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Arribatec Group and GrantsNow have partnered to transform research "
            "funding management for Unit4 customers in the UK.\n\n"
            "The partnership brings together Arribatec's deep ERP expertise and "
            "GrantsNow's modern, AI-enabled Pre and Post-Awards platform to "
            "deliver a fully integrated solution for universities and research "
            "institutions.\n\n"
            "Together, they're helping research offices streamline workflows, "
            "ensure compliance, and gain complete visibility across the funding "
            "lifecycle.\n\n"
            "#GrantsNow #Arribatec #Unit4 #GrantsManagement #ResearchFunding "
            "#HigherEducation #Innovation"
        ),
        "value_prop_line": "The partnership brings together Arribatec's ERP expertise and GrantsNow's AI-enabled Pre and Post-Awards platform for a fully integrated solution.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "Arribatec, GrantsNow, partnership, Unit4, research funding, ERP expertise, AI-enabled, pre and post-awards, universities, research institutions",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "partnership announcement",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + partner + niche",
        "media_type": "image",
        "primary_visual": "typography on light gradient with co-brand marks",
        "image_subject": "cream-to-mint gradient with announcement headline and Arribatec wordmark",
        "background_type": "gradient",
        "background_dominant_colour": "cream to soft mint",
        "foreground_dominant_colour": "dark teal type + black Arribatec wordmark",
        "palette": "brand-teal + cream + partner-black",
        "contrast_level": "medium",
        "texture": "flat gradient",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the announcement headline + Arribatec wordmark as co-brand",
        "text_on_image": "yes",
        "headline_on_image": "Arribatec and GrantsNow announce partnership to transform research funding management for Unit4 Customers in the UK.",
        "headline_style": "sentence-case mixed-weight with 'Arribatec' and 'GrantsNow' as anchor names",
        "headline_chars": 116,
        "subheadline_on_image": "",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo top-centre + Arribatec wordmark below headline",
        "brand_placement": "top-centre + centred co-brand",
        "graphic_style": "corporate announcement poster - completely off-template",
        "notable_element": "FIRST PARTNERSHIP ANNOUNCEMENT in the whole set + first co-brand of this kind (Arribatec, Unit4) + longest headline yet (116 chars) + no HM Government badge + no product claim, no CTA - pure PR/positioning",
        "campaign": "partnership - Arribatec Unit4",
        "angle": "thought_leadership + community_celebration",
    },
    {
        "post_id": "SS072", "batch": "batch15",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Unlock smarter decision-making with GrantsNow. Gain deeper "
            "insights, automate data capture, and enable advanced reporting "
            "across your Pre-Awards process, all in one modern platform.\n\n"
            "Experience GrantsNow: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #preawards #grantsmanagement #researchfunding"
        ),
        "value_prop_line": "Gain deeper insights, automate data capture, and enable advanced reporting across your Pre-Awards process, all in one modern platform.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "smarter decision-making, deeper insights, data capture, advanced reporting, pre-awards, research funding",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "learn_more",
        "cta_verb": "Experience",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "B&W portrait + cream card with response pill",
        "image_subject": "smiling bearded man at a laptop, black-and-white portrait on bright cream background",
        "background_type": "photographic",
        "background_dominant_colour": "bright cream with subtle wave motif",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'Your Search Ends Here' pill",
        "palette": "brand-teal + gold + cream + B&W portrait",
        "contrast_level": "medium",
        "texture": "flat cream with desaturated portrait",
        "person_present": "yes", "face_visible": "yes (smiling)",
        "number_of_people": 1,
        "object_of_focus": "the question card + 'Your Search Ends Here' pill",
        "text_on_image": "yes",
        "headline_on_image": "Want to unlock deeper insights and enable more complex reporting in Pre-Awards?",
        "headline_style": "sentence-case mixed-weight",
        "headline_chars": 78,
        "subheadline_on_image": "Your Search Ends Here.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright editorial with B&W portrait - fifth post in the cream-plus-orange-border cluster",
        "notable_element": "first time a recurring model appears (same bearded man in SS072 and SS073) + 'Your Search Ends Here' pill introduces a new sub-brand phrase used across the cluster + fifth bright-cream card template (SS023 SS046 SS067 SS070 SS072)",
        "campaign": "demo - deeper insights",
        "angle": "product_capability",
    },
    {
        "post_id": "SS073", "batch": "batch15",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Looking for a single cloud platform to manage both Pre- and "
            "Post-Awards, including Ethics and Contracts? GrantsNow delivers "
            "it all, fully integrated, highly configurable, and powered by "
            "modern Oracle Cloud technology.\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #grantsmanagement #preawards #postawards #cloud #SaaS"
        ),
        "value_prop_line": "GrantsNow delivers it all: fully integrated, highly configurable, and powered by modern Oracle Cloud technology.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "single cloud platform, Pre- and Post-Awards, Ethics and Contracts, Oracle Cloud, SaaS, grants management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "B&W portrait + cream card with quote-style headline",
        "image_subject": "same bearded man from SS072, hands behind head, relaxed pose",
        "background_type": "photographic",
        "background_dominant_colour": "bright cream with subtle wave motif",
        "foreground_dominant_colour": "cream card + orange border + teal type + teal 'Your Search Ends Here' pill",
        "palette": "brand-teal + gold + cream + B&W portrait",
        "contrast_level": "medium",
        "texture": "flat cream with desaturated portrait",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 1,
        "object_of_focus": "the quoted testimonial in the card + 'Your Search Ends Here' pill",
        "text_on_image": "yes",
        "headline_on_image": "\"I want a single cloud platform to handle Pre-Awards, Post-Awards, Ethics, and Contracts.\"",
        "headline_style": "sentence-case mixed-weight in quotation marks (first-person)",
        "headline_chars": 90,
        "subheadline_on_image": "Your Search Ends Here.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright editorial with B&W portrait and first-person quote",
        "notable_element": "second appearance of the same bearded man (with SS072) + first-person quote treatment (like SS056 and SS063) - near-paraphrase of SS056 caption but different visual and different pose",
        "campaign": "demo - single cloud platform",
        "angle": "product_capability",
    },
    {
        "post_id": "SS074", "batch": "batch15",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "How much time is your research development team losing by "
            "manually entering funding call information into your Pre-Awards "
            "platform? GrantsNow auto-populates funding calls and leverages AI "
            "to cut down search time.\n\n"
            "Experience GrantsNow: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #preawards #grantsmanagement #armauk"
        ),
        "value_prop_line": "GrantsNow auto-populates funding calls and leverages AI to cut down search time.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research development team, manually entering, funding calls, funder portal, auto-populates, AI, ARMA UK",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "learn_more",
        "cta_verb": "Experience",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase (light 4 tags)",
        "media_type": "image",
        "primary_visual": "B&W portrait + cream card with question",
        "image_subject": "woman at laptop in casual pose, black-and-white portrait on bright cream background",
        "background_type": "photographic",
        "background_dominant_colour": "bright cream with subtle wave motif",
        "foreground_dominant_colour": "cream card + orange border + teal type",
        "palette": "brand-teal + gold + cream + B&W portrait",
        "contrast_level": "medium",
        "texture": "flat cream with desaturated portrait",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 1,
        "object_of_focus": "the manual-entry question + portrait",
        "text_on_image": "yes",
        "headline_on_image": "Are you still Manually entering funding calls from the funder portal?",
        "headline_style": "sentence-case mixed-weight (with 'Manually' inexplicably capitalised mid-sentence)",
        "headline_chars": 69,
        "subheadline_on_image": "",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright editorial with B&W portrait",
        "notable_element": "sixth post in the bright-cream card template + 'Manually' capitalised mid-sentence (design/typing quirk, not standard title case) - worth watching whether this is a deliberate emphasis device or a mistake",
        "campaign": "demo - AI funder portal",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS075", "batch": "batch15",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "We know the options for Pre- and Post-Awards Management software "
            "are limited, especially when most are built on technology that's "
            "nearly a decade old. GrantsNow is different. As a true SaaS "
            "solution, it comes with modern, pre-built integrations for ERP, "
            "Finance, and HR systems, bringing unmatched efficiency and "
            "innovation.\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #grantsmanagement #preawards #postawards #SaaS"
        ),
        "value_prop_line": "GrantsNow is a true SaaS solution with modern, pre-built integrations for ERP, Finance, and HR systems.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards, post-awards management, decade-old tech, true SaaS, pre-built integrations, ERP, finance, HR systems",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "portrait photo + typography on light background",
        "image_subject": "woman sitting cross-legged with laptop, smiling (B&W-ish) on cream background",
        "background_type": "solid",
        "background_dominant_colour": "cream-white with subtle wave motif",
        "foreground_dominant_colour": "dark teal type + gold star accent + soft photo",
        "palette": "brand-teal + gold + cream",
        "contrast_level": "medium",
        "texture": "flat cream with soft-focus portrait",
        "person_present": "yes", "face_visible": "yes (smiling)",
        "number_of_people": 1,
        "object_of_focus": "the punchline 'Think Again.' + smiling person",
        "text_on_image": "yes",
        "headline_on_image": "Still investing time and money into decade-old Pre-awards tech?",
        "headline_style": "sentence-case mixed-weight with 'decade-old' emphasised",
        "headline_chars": 63,
        "subheadline_on_image": "Think Again.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "light editorial with cream background and soft portrait",
        "notable_element": "IDENTICAL CAPTION AND VISUAL AS SS046. Eleventh byte-identical duplicate in the set.",
        "campaign": "demo - decade-old tech callout",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS076", "batch": "batch15",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "With a team of 250+ consultants, we deliver new functionality in "
            "under 6 months, helping you stay ahead with the latest innovations "
            "quickly and efficiently.\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #Innovation #ResearchFunding #GrantManagement "
            "#TechDriven #Efficiency #SeamlessIntegration #SmartSolutions "
            "#FundingSuccess #ARMAUK"
        ),
        "value_prop_line": "With a team of 250+ consultants, GrantsNow delivers new functionality in under 6 months.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "250+ consultants, new functionality, 6 months, latest innovations, tech driven, efficiency, seamless integration, smart solutions, ARMA UK",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - heavy (10 tags, ties with SS070)",
        "media_type": "image",
        "primary_visual": "action photo (Formula 1 racing cars)",
        "image_subject": "yellow Formula 1 racing car in motion with other cars behind, track blur",
        "background_type": "photographic",
        "background_dominant_colour": "bright green track blur + yellow F1 car",
        "foreground_dominant_colour": "teal-gold gradient card + white type",
        "palette": "racing-yellow + brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "action photo with speed blur",
        "person_present": "yes (F1 driver in helmet)",
        "face_visible": "no", "number_of_people": 1,
        "object_of_focus": "the 50% faster claim card + F1 car speed metaphor",
        "text_on_image": "yes",
        "headline_on_image": "Want to know how GrantsNow delivers new features 50% faster?",
        "headline_style": "mixed-weight bold with '50% faster' emphasised",
        "headline_chars": 60,
        "subheadline_on_image": "",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "sports action photo (F1) - third racing metaphor overall",
        "notable_element": "THIRD RACING METAPHOR in the set (SS017 MotoGP photo + SS025 cartoon pit + SS076 F1 photo) - now a proper theme with three unique variants + ties SS070 for heaviest hashtag load (10) + 50% stat + 250+ consultants + 6 months delivery claim",
        "campaign": "demo - 50% faster delivery",
        "angle": "product_capability",
    },
    {
        "post_id": "SS077", "batch": "batch16",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Integration shouldn't be an afterthought!\n\n"
            "Many universities face unexpected challenges when connecting their "
            "Pre-Awards and ERP systems-no budget, no internal resources, just a "
            "complex headache.\n\n"
            "GrantsNow eliminates this burden by managing all integrations "
            "seamlessly, so you can focus on securing more funding, not fixing "
            "IT issues. Want to know how? Connect with us: "
            "https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #preawards #research #tech #armauk #ERP #grantsmanagement"
        ),
        "value_prop_line": "GrantsNow eliminates this burden by managing all integrations seamlessly, so you can focus on securing more funding.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "integration, universities, Pre-Awards, ERP systems, no budget, no internal resources, complex headache, IT issues, ARMA UK",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Connect",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - mixed case",
        "media_type": "image",
        "primary_visual": "photo + teal card with first-person quote",
        "image_subject": "two professional women at desk with tablet, other people in background, bright office",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral office",
        "foreground_dominant_colour": "teal card + white type + gold accent",
        "palette": "brand-teal + gold + bright-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo with flat teal card",
        "person_present": "yes", "face_visible": "yes (multiple)",
        "number_of_people": 4,
        "object_of_focus": "the first-person quote card + 'Not with GrantsNow, it isn't!' closer",
        "text_on_image": "yes",
        "headline_on_image": "\"We thought grants were the hard part but managing Pre-Awards and ERP integrations was harder.\"",
        "headline_style": "first-person quote in quotation marks",
        "headline_chars": 94,
        "subheadline_on_image": "Not with GrantsNow, it isn't!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright office scene with first-person quote card - testimonial with a crowd",
        "notable_element": "first multi-person testimonial (two women foreground plus two in background) + quote-in-quotes on a teal card + em-dash in caption + first exclamation-ending punchline in the set",
        "campaign": "demo - ERP integration burden",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS078", "batch": "batch16",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Remove repetitive tasks and make every resource count. GrantsNow "
            "helps your team work faster, smarter, and more efficiently. Get "
            "in touch: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #UnlockPotential #GrantsFunding #PreAwards"
        ),
        "value_prop_line": "GrantsNow helps your team work faster, smarter, and more efficiently.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "repetitive tasks, resource, faster smarter more efficient, unlock potential, grants funding, pre-awards",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad (light 4 tags)",
        "media_type": "image",
        "primary_visual": "photo + cream card overlay with lightbulb icon",
        "image_subject": "bright desk photo with laptop and hand on documents/charts",
        "background_type": "photographic",
        "background_dominant_colour": "bright warm neutral (soft teal-tinted)",
        "foreground_dominant_colour": "cream card + orange border + teal type + yellow lightbulb + gold divider",
        "palette": "brand-teal + gold + cream + soft-photographic",
        "contrast_level": "medium",
        "texture": "bright natural-light photo with flat card",
        "person_present": "partial (hand only)", "face_visible": "no",
        "number_of_people": 1,
        "object_of_focus": "the two-line 'Streamline Processes, Unlock Potential' hook + yellow lightbulb",
        "text_on_image": "yes",
        "headline_on_image": "Streamline Processes, Unlock Potential",
        "headline_style": "sentence-case bold two-line hook",
        "headline_chars": 39,
        "subheadline_on_image": "Want to know how?",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "bright editorial with lightbulb accent - short punchy hook",
        "notable_element": "short two-line hook (39 chars, among the tightest headlines) + on-image lightbulb icon that echoes SS059's caption 💡 emoji + gold divider under the hook (accent already seen on SS034 SS064 SS066)",
        "campaign": "demo - streamline processes",
        "angle": "product_capability",
    },
    {
        "post_id": "SS079", "batch": "batch16",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow and Oracle have entered a strategic partnership to "
            "deliver a fully integrated Pre & Post Awards solution for research "
            "and higher education, now available on Oracle Marketplace. Read "
            "more: https://lnkd.in/djB-zNZq\n\n"
            "#GrantsNow #Oracle #OracleCloud"
        ),
        "value_prop_line": "GrantsNow and Oracle have entered a strategic partnership to deliver a fully integrated Pre & Post Awards solution.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "Oracle, strategic partnership, Pre & Post Awards, Oracle Marketplace, research, higher education, Oracle Cloud",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "partnership announcement",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + partner (very tight - 3 tags)",
        "media_type": "image",
        "primary_visual": "photo + typography with Oracle co-brand",
        "image_subject": "dark teal-tinted urban/office scene with headline + Oracle Partner logo",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted urban blur",
        "foreground_dominant_colour": "white type + gold divider + Oracle Partner logo",
        "palette": "brand-teal + gold + Oracle-red",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the Oracle+GrantsNow partnership headline",
        "text_on_image": "yes",
        "headline_on_image": "Oracle and GrantsNow have entered a Strategic Partnership to Enhance Pre & Post Awards Management",
        "headline_style": "title-case mixed-weight bold",
        "headline_chars": 96,
        "subheadline_on_image": "Read about our partnership",
        "image_cta_text": "LINK IN DESCRIPTION + Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + ORACLE Partner co-brand TR + contact footer strip",
        "brand_placement": "corners + centred co-brand + footer contact strip",
        "graphic_style": "corporate partnership poster - dark teal with Oracle co-brand",
        "notable_element": "SECOND PARTNERSHIP ANNOUNCEMENT (SS071 Arribatec + SS079 Oracle) - Oracle is much larger + first mention of Oracle Marketplace + new blog URL djB-zNZq + only 3 hashtags (very tight for a PR post)",
        "campaign": "partnership - Oracle strategic",
        "angle": "thought_leadership + community_celebration",
    },
    {
        "post_id": "SS080", "batch": "batch16",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "GrantsNow, (A SaaS innovation for Grants management) are proud to "
            "sponsor Morley Youth U14 Stallions FC for their upcoming season. "
            "As part of our CSR policy, we are committed to supporting local "
            "initiatives that make a real impact, and our values strongly align "
            "with those of the club. Morley Youth FC fosters a positive, "
            "inclusive environment where young players can develop their "
            "skills, build confidence, and embrace being part of a team. We're "
            "excited to be part of their journey and look forward to seeing the "
            "team go from strength to strength!\n\n"
            "#GrantsNow #MorleyYouthFC #Sponsors"
        ),
        "value_prop_line": "n/a - CSR sponsorship announcement",
        "value_prop_in_first_3_sentences": "n/a",
        "industry_keywords": "Morley Youth FC, U14 Stallions, sponsor, CSR policy, local initiatives, young players, football",
        "tone": "conversational",
        "pov": "brand-first-person",
        "offer_type": "sponsorship",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + sponsored partner (very tight - 3 tags)",
        "media_type": "image",
        "primary_visual": "photo collage with orange background",
        "image_subject": "5-plus action photos of youth football players in orange kits + Morley Youth FC crest",
        "background_type": "solid",
        "background_dominant_colour": "bright orange",
        "foreground_dominant_colour": "orange + white type + football photos",
        "palette": "orange (Morley kit) + white + brand-teal (small)",
        "contrast_level": "high",
        "texture": "flat solid orange with photo tiles",
        "person_present": "yes (multiple young players)",
        "face_visible": "yes (some)", "number_of_people": 6,
        "object_of_focus": "the sponsorship announcement card + collage of players",
        "text_on_image": "yes",
        "headline_on_image": "GrantsNow sponsors the Morley Youth U14 Stallions FC",
        "headline_style": "mixed-weight bold with 'Morley Youth U14 Stallions' emphasised",
        "headline_chars": 52,
        "subheadline_on_image": "",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo top-left of card + Morley Youth FC crest",
        "brand_placement": "in-card + partner crest",
        "graphic_style": "photo collage poster - completely off-template community CSR post",
        "notable_element": "FIRST CSR sponsorship post in the whole set + only orange-first palette (rest is teal-dominant) + first collage layout + first photo of children / minors + no product claim, no CTA URL, no G-Cloud badge",
        "campaign": "CSR - Morley Youth FC sponsorship",
        "angle": "community_celebration",
    },
    {
        "post_id": "SS081", "batch": "batch16",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Stuck with outdated Pre-Awards technology that can't keep up with "
            "your institution's needs? GrantsNow offers a modern, highly "
            "configurable cloud solution built to adapt to rapid changes "
            "seamlessly.\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #grantsmanagement #armauk #preawards"
        ),
        "value_prop_line": "GrantsNow offers a modern, highly configurable cloud solution built to adapt to rapid changes seamlessly.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "outdated Pre-Awards technology, institution's needs, modern, highly configurable, cloud solution, rapid changes, ARMA UK",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase (light 4 tags)",
        "media_type": "image",
        "primary_visual": "photo + cream card overlay with cut-out portrait",
        "image_subject": "dark navy office scene with cut-out portrait of a professional woman with tablet",
        "background_type": "photographic",
        "background_dominant_colour": "dark navy office",
        "foreground_dominant_colour": "cream card + orange border + teal type + gold '8-year-old' accent",
        "palette": "brand-teal + gold + navy + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with cut-out portrait",
        "person_present": "yes", "face_visible": "yes",
        "number_of_people": 1,
        "object_of_focus": "the '8-year-old' pain question + 'Look No Further.' response",
        "text_on_image": "yes",
        "headline_on_image": "Why invest in 8-year-old Pre-Awards technology with limited flexibility for the rapid changes you need?",
        "headline_style": "sentence-case mixed-weight with gold accent on '8-year-old' + teal accent on 'Look No Further.'",
        "headline_chars": 103,
        "subheadline_on_image": "Look No Further.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + UNIT4 Partner + Oracle Partner co-brand + contact footer strip",
        "brand_placement": "corners + partner co-brand row + footer contact strip",
        "graphic_style": "dark navy poster with cream card and cut-out portrait - fourth outdated-tech variant",
        "notable_element": "fourth variant of the outdated / decade-old / 8-year-old tech theme (SS037 SS046 SS064 SS081) - each with a different specific age number + third post with both UNIT4 and Oracle partner badges together (SS017 SS039 SS081) + longest headline in this batch (103 chars)",
        "campaign": "demo - outdated 8-year-old tech callout",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS082", "batch": "batch18",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Imagine freeing up 35% of your team's time to work on only the "
            "most important tasks - that's what GrantsNow can do by automating "
            "manual, repetitive tasks that bog down the grant submission "
            "process.\n\n"
            "With more time available, your team can increase the number of "
            "funding applications they submit by over a third, leading to "
            "significantly more grant approvals and funding. More submissions "
            "mean more opportunities for research growth, and GrantsNow makes "
            "it happen efficiently.\n\n"
            "#GrantsNow #TimeSavings #MoreSubmissions #grantsmanagement "
            "#educationtrends"
        ),
        "value_prop_line": "GrantsNow can free up 35% of your team's time by automating manual, repetitive tasks that bog down the grant submission process.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "35% time savings, funding applications, grant approvals, grant submission process, automation, time savings, more submissions, education trends",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - mixed case",
        "media_type": "image",
        "primary_visual": "photo + all-caps typography with 3D illustrated stopwatch",
        "image_subject": "dark teal photo background + large 3D stopwatch illustration held by a cartoon hand",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted background",
        "foreground_dominant_colour": "white all-caps type + huge 35% + 3D white stopwatch",
        "palette": "brand-teal + white + illustration accent",
        "contrast_level": "high",
        "texture": "photo with heavy overlay + 3D illustration",
        "person_present": "no (cartoon hand only)",
        "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the very large 35% stat + 3D stopwatch illustration",
        "text_on_image": "yes",
        "headline_on_image": "HOW DOES FREEING UP 35% MORE TIME FOR GRANT SUBMISSIONS SOUND?",
        "headline_style": "all-caps bold with 35% as huge display type",
        "headline_chars": 61,
        "subheadline_on_image": "",
        "image_cta_text": "GrantsNow.co.uk",
        "brand_marks": "GrantsNow logo TL + toggle switch icon + GrantsNow.co.uk URL strip (no phone footer)",
        "brand_placement": "corners + URL strip",
        "graphic_style": "photo hero with 3D illustrated stopwatch and huge display number",
        "notable_element": "SAME CAPTION AS SS055 but the creative is completely different - SS055 was a real wristwatch photo, SS082 is a 3D illustrated stopwatch with huge 35% display type. Second time this campaign runs a visual A/B on the same 35% claim. First 3D illustration in the set + first URL-only footer (no phone number).",
        "campaign": "brand awareness - 35% time savings",
        "angle": "product_capability",
    },
    {
        "post_id": "SS083", "batch": "batch18",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Been told there's only one option for Pre-Awards software?\n\n"
            "Think again. GrantsNow offers a fully configurable, end-to-end "
            "Pre-Awards management platform with seamless ERP integration, "
            "intelligent dashboards, automated workflows, and compliance-ready "
            "reporting - all on a TRUE SaaS platform.\n\n"
            "Take a look for yourself https://lnkd.in/dU2Brsef\n\n"
            "#grantsmanagement #grantsnow #preawards #erp #integration"
        ),
        "value_prop_line": "GrantsNow is a fully configurable, end-to-end Pre-Awards management platform with seamless ERP integration, intelligent dashboards, automated workflows, and compliance-ready reporting.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "only one option, Pre-Awards software, configurable, end-to-end, seamless ERP integration, intelligent dashboards, automated workflows, compliance-ready reporting, TRUE SaaS",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "learn_more",
        "cta_verb": "Take a look",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase (light 5 tags)",
        "media_type": "image",
        "primary_visual": "photo + typography",
        "image_subject": "three graduates in teal caps and gowns from behind, marble column background",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal graduation photo",
        "foreground_dominant_colour": "white type + teal check-mark accent",
        "palette": "brand-teal + white + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with darkened tint",
        "person_present": "yes (backs of graduates)",
        "face_visible": "no", "number_of_people": 3,
        "object_of_focus": "the graduates + 'Its time you met GrantsNow' punchline",
        "text_on_image": "yes",
        "headline_on_image": "If you were told there was only one option for Pre-Awards software",
        "headline_style": "sentence-case regular weight",
        "headline_chars": 66,
        "subheadline_on_image": "Its time you met GrantsNow",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL (only, no HM Government badge, no footer contact strip)",
        "brand_placement": "TL only",
        "graphic_style": "editorial photo hero using the academic graduation moment",
        "notable_element": "first graduation-ceremony photo in the whole set + typo 'Its' missing apostrophe in the punchline + no HM Government badge and no contact footer strip + em-dash in caption 'reporting-all' + 'Think again' phrasing echoes SS046 'Think Again.' close",
        "campaign": "demo - alternative to legacy",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS084", "batch": "batch18",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Unlock more opportunities for grants income without needing extra "
            "budget! With GrantsNow, you have multiple tools at your disposal "
            "to streamline Pre-Awards, enhance team performance, and get your "
            "organisation the funding it deserves."
        ),
        "value_prop_line": "With GrantsNow, you have multiple tools to streamline Pre-Awards, enhance team performance, and get your organisation the funding it deserves.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "grants income, budget, pre-awards, team performance, funding",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "no",
        "hashtag_style": "none in the caption (they sit inside the mock tweet)",
        "media_type": "image",
        "primary_visual": "typography (fake tweet mockup)",
        "image_subject": "mock Twitter/X post with GrantsNow verified handle and heart/reply icons",
        "background_type": "solid",
        "background_dominant_colour": "dark navy-teal",
        "foreground_dominant_colour": "white tweet card + teal accent brand name + red heart",
        "palette": "brand-teal (dark) + white + accent-red heart",
        "contrast_level": "high",
        "texture": "flat tweet-card mockup",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the mock tweet card claiming 'the GrantsNow treatment'",
        "text_on_image": "yes",
        "headline_on_image": "Increase your Grants income without extending your existing budget.... Thats the GrantsNow treatment.",
        "headline_style": "tweet-body regular text",
        "headline_chars": 100,
        "subheadline_on_image": "@TheFastestGrowingPreAwardsPlatform",
        "image_cta_text": "",
        "brand_marks": "GrantsNow logo TL + verified checkmark inside mock tweet",
        "brand_placement": "corner + inside mock tweet card",
        "graphic_style": "social-mockup embed (fake tweet)",
        "notable_element": "IDENTICAL CAPTION AND VISUAL AS SS029. Twelfth byte-identical duplicate in the set.",
        "campaign": "brand awareness - Pre-Awards positioning",
        "angle": "product_capability",
    },
    {
        "post_id": "SS085", "batch": "batch18",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "GrantsNow is empowering research teams to work smarter, not harder. "
            "Discover why UK institutions are opting for a platform designed for "
            "outcomes, not workarounds. Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#GrantsNow #PreAwardSoftware #ResearchManagement #HigherEdTech "
            "#TrueSaaS #UKUniversities"
        ),
        "value_prop_line": "GrantsNow is a platform designed for outcomes, not workarounds - real-time KPI reporting, self-configurable, lower cost with more opportunities.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "research teams, UK institutions, pre-award software, higher ed tech, TRUE SaaS, UK universities, KPI reporting, funder templates",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + 3-column benefit cards",
        "image_subject": "dark teal-tinted architectural photo with 3 numbered benefit cards",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted architectural blur",
        "foreground_dominant_colour": "white type + yellow circle numbers + teal cards",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay + flat cards",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the three numbered benefit cards (1 analytics, 2 self-configurable, 3 lower cost)",
        "text_on_image": "yes",
        "headline_on_image": "Ready to experience the GrantsNow Treatment?",
        "headline_style": "mixed-weight bold",
        "headline_chars": 44,
        "subheadline_on_image": "1 Real time analytics for KPI reporting | 2 Completely self configurable for funder templates, approval routes etc | 3 Lower cost but more Grants opportunities | The fastest-growing True SaaS cloud pre-award platform in the UK",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo top-centre + contact footer strip + fastest-growing claim",
        "brand_placement": "top-centre + footer contact strip",
        "graphic_style": "3-column benefit poster with question hook",
        "notable_element": "IDENTICAL CAPTION AND VISUAL AS SS032. Thirteenth byte-identical duplicate. Same caption also appears with a different creative as SS057 (portrait cut-out).",
        "campaign": "demo - GrantsNow Treatment",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS086", "batch": "batch18",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Searching for the next generation in pre-awards software? "
            "GrantsNow is here now, making pre and post-award administration "
            "faster, more automated and better integrated.\n\n"
            "#GrantsNow #PreAwardSoftware #PostAwardManagement #ResearchGrants "
            "#HigherEdTech #UKUniversities #SmartFunding #FutureReady"
        ),
        "value_prop_line": "GrantsNow is here now, making pre and post-award administration faster, more automated and better integrated.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "next generation, pre-awards software, post-award management, automation, integration, higher ed tech, smart funding, future ready",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "brand awareness",
        "cta_placement": "none in caption",
        "cta_type_caption": "none",
        "cta_verb": "",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + broad + niche - very heavy (8 tags)",
        "media_type": "image",
        "primary_visual": "photo (space astronaut) with typography",
        "image_subject": "astronaut in white spacesuit reaching outward with earth curve visible in background",
        "background_type": "photographic",
        "background_dominant_colour": "black space + blue earth curve",
        "foreground_dominant_colour": "white all-caps type + teal accent on 'LOST'",
        "palette": "black + brand-teal + white + photographic",
        "contrast_level": "very high",
        "texture": "photo realistic with cosmic backdrop",
        "person_present": "yes (astronaut)", "face_visible": "no (helmet)",
        "number_of_people": 1,
        "object_of_focus": "the DON'T GET LOST hook + astronaut reaching hand",
        "text_on_image": "yes",
        "headline_on_image": "DON'T GET LOST",
        "headline_style": "all-caps bold with teal accent on 'LOST'",
        "headline_chars": 14,
        "subheadline_on_image": "Searching for the latest advancements in a Pre-Awards platform. GrantsNow is already here to simplify Pre & Post-Award Management",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "cinematic space photo with punchy short hook",
        "notable_element": "IDENTICAL CAPTION AND VISUAL AS SS028. Fourteenth byte-identical duplicate in the set. The 'DONT GET LOST' variant SS058 (no apostrophe, added 25%+ line) is a separate visual refinement.",
        "campaign": "brand awareness - next generation",
        "angle": "product_capability + thought_leadership",
    },
    {
        "post_id": "SS087", "batch": "batch19",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "The wrong Pre-Awards platform means hidden costs, manual updates, "
            "delays, and a higher total cost of ownership. GrantsNow's TRUE SaaS "
            "solution gives you full control, instant upgrades, and zero hidden "
            "fees. Read the blog to know how: https://lnkd.in/eqK3_-vN\n\n"
            "#grantsmanagement #armauk #grantsnow #preawards #research"
        ),
        "value_prop_line": "GrantsNow's TRUE SaaS solution gives you full control, instant upgrades, and zero hidden fees.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "pre-awards platform, hidden costs, manual updates, total cost of ownership, TRUE SaaS, ARMA UK, grants management",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "blog",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche - all lowercase",
        "media_type": "image",
        "primary_visual": "photo + typography with BLOG pill",
        "image_subject": "architectural photo (looks like an ornate palace/museum building with dome) - very similar to SS031",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted architectural photo",
        "foreground_dominant_colour": "white type + yellow highlighter on 'Cost'",
        "palette": "brand-teal + accent-yellow + photographic",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the question headline with yellow highlighter marker on 'Cost'",
        "text_on_image": "yes",
        "headline_on_image": "Pre-Awards Platforms: What's the Cost of the Wrong Choice?",
        "headline_style": "mixed-weight bold with yellow highlighter marker on 'Cost'",
        "headline_chars": 57,
        "subheadline_on_image": "Learn how TRUE SaaS saves time and money. Read the blog.",
        "image_cta_text": "(Link in description) + Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + BLOG pill TR + contact footer strip + small icon accent on the CTA line",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "editorial photo blog poster with highlighter accent",
        "notable_element": "IDENTICAL CAPTION AND ARCHITECTURAL BACKGROUND AS SS031. Fifteenth byte-identical duplicate in the set. This is the third occurrence of the True SaaS Cost-of-the-Wrong-Choice creative (SS027 dark-office variant + SS031 architectural + SS087 same architectural). The blog also has a fourth same-caption sibling in SS053 (dark navy sticky-note variant).",
        "campaign": "blog - True SaaS cost",
        "angle": "thought_leadership + pain_point",
    },
    {
        "post_id": "SS088", "batch": "batch19",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Looking for a single cloud platform to manage BOTH Pre & Post "
            "Awards, including Ethics & Contracts? GrantsNow delivers it "
            "all-fully integrated, highly configurable, and built on modern "
            "Oracle Cloud technology!\n\n"
            "Get in touch: https://lnkd.in/dU2Brsef\n\n"
            "#grantsnow #grantsmanagement #preawards #postwards #cloud #SaaS"
        ),
        "value_prop_line": "GrantsNow delivers it all - fully integrated, highly configurable, and built on modern Oracle Cloud technology.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "single cloud platform, Pre & Post Awards, Ethics & Contracts, Oracle Cloud, SaaS, grants management",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "yes",
        "hashtag_style": "brand + niche - all lowercase (has typo #postwards)",
        "media_type": "image",
        "primary_visual": "portrait photo + testimonial-style speech card",
        "image_subject": "smiling man at laptop, professional casual, teal-tinted office",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted office",
        "foreground_dominant_colour": "cream speech card + teal accent on 'Cloud Software' + gold pill",
        "palette": "brand-teal + gold + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with overlay",
        "person_present": "yes", "face_visible": "yes (smiling)",
        "number_of_people": 1,
        "object_of_focus": "the 'I need' speech card + 'GrantsNow has it ALL!' pill",
        "text_on_image": "yes",
        "headline_on_image": "\"I need a Cloud Software platform to manage BOTH Pre & Post Awards, including Ethics & Contracts\"",
        "headline_style": "first-person quote (want-framing, not testimonial thanks-framing)",
        "headline_chars": 96,
        "subheadline_on_image": "GrantsNow has it ALL!",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "portrait-plus-speech-card - want-framing variant of SS056",
        "notable_element": "SAME CAPTION AS SS056 but the on-image headline flips from testimonial ('Thanks to GrantsNow, I have...') to demand ('I need a Cloud Software...'). Same portrait template, opposite emotional framing. Cleanest before-and-after A/B in the whole set for testing whether after-the-purchase 'thanks' or before-the-purchase 'need' pulls better.",
        "campaign": "demo - single cloud platform",
        "angle": "product_capability + pain_point",
    },
    {
        "post_id": "SS089", "batch": "batch19",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Managing integrations, reports, and configurations in-house can "
            "drain valuable time and resources. With GrantsNow, you don't have "
            "to. Our team of 250+ consultants ensures seamless integration and "
            "customisation, so you can focus on what truly matters.\n\n"
            "#HigherEdTech #GrantsNow #GrantManagement #Automation #Efficiency "
            "#SeamlessIntegration"
        ),
        "value_prop_line": "Our team of 250+ consultants ensures seamless integration and customisation so you can focus on what truly matters.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "integrations, reports, configurations, 250+ consultants, seamless integration, customisation, higher ed tech, automation",
        "tone": "conversational",
        "pov": "brand-and-you (mixed)",
        "offer_type": "demo",
        "cta_placement": "end",
        "cta_type_caption": "contact",
        "cta_verb": "Get in touch",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + teal card overlay",
        "image_subject": "business meeting - 5 to 6 people around a table with one standing presenter",
        "background_type": "photographic",
        "background_dominant_colour": "muted warm neutral office",
        "foreground_dominant_colour": "teal card + cream border + white type with 'IT team' in bold accent",
        "palette": "brand-teal + cream + photographic",
        "contrast_level": "high",
        "texture": "photo realistic with subtle overlay",
        "person_present": "yes", "face_visible": "yes (multiple, partial)",
        "number_of_people": 6,
        "object_of_focus": "the IT team question + presenter in background",
        "text_on_image": "yes",
        "headline_on_image": "Is your IT team burdened with integrations, reports, and configurations?",
        "headline_style": "mixed-weight bold with 'IT team' in heavier weight",
        "headline_chars": 71,
        "subheadline_on_image": "With GrantsNow, they don't have to.",
        "image_cta_text": "Get in touch (+44) 7710 041194 | grantsnow.co.uk",
        "brand_marks": "GrantsNow logo TL + HM Government G-Cloud Supplier TR + contact footer strip",
        "brand_placement": "corners + footer contact strip",
        "graphic_style": "photo hero with centred teal card - IT-team specific target",
        "notable_element": "IDENTICAL CAPTION AND VISUAL AS SS030. Sixteenth byte-identical duplicate in the set. Same caption also appears with a different creative as SS052 (dark snowflake typography variant).",
        "campaign": "demo - IT team burden",
        "angle": "pain_point + product_capability",
    },
    {
        "post_id": "SS090", "batch": "batch19",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Just reminding you about the partnership between Fusion Practices "
            "and Unit4, which brought GrantsNow to life as a modern solution "
            "for managing the full pre-awards funding process. You can read "
            "more about it here: https://lnkd.in/dg6pjWF9"
        ),
        "value_prop_line": "The Fusion Practices + Unit4 partnership brought GrantsNow to life as a modern solution for the full pre-awards funding process.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "Fusion Practices, Unit4, GrantsNow, partnership, pre-awards funding process",
        "tone": "conversational",
        "pov": "brand-first-person",
        "offer_type": "partnership announcement",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "none in the caption",
        "media_type": "image",
        "primary_visual": "photo + triple co-brand row",
        "image_subject": "two men in suits shaking hands (professional handshake, close-up), dark teal blur background",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted urban blur",
        "foreground_dominant_colour": "white type + GrantsNow + Fusion Practices + Unit4 logos",
        "palette": "brand-teal + white + partner-branded",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "yes (2 men, from waist)",
        "face_visible": "no (side/back)", "number_of_people": 2,
        "object_of_focus": "the handshake photo + triple co-brand row",
        "text_on_image": "yes",
        "headline_on_image": "We just wanted to remind people about the partnership between Fusion Practices and Unit4 that introduced GrantsNow.",
        "headline_style": "sentence-case mixed-weight bold on partner names",
        "headline_chars": 116,
        "subheadline_on_image": "Read about our partnership",
        "image_cta_text": "LINK IN DESCRIPTION",
        "brand_marks": "GrantsNow logo top + Fusion Practices logo + Unit4 logo (triple co-brand row)",
        "brand_placement": "top row - three partner marks side by side",
        "graphic_style": "corporate partnership photo with handshake and triple co-brand row",
        "notable_element": "THIRD PARTNERSHIP ANNOUNCEMENT in the set (SS071 Arribatec + SS079 Oracle + SS090 Fusion Practices/Unit4) + first handshake visual + reveals the origin story (GrantsNow was created by Fusion Practices + Unit4 partnership) + reminder framing ('Just reminding you...') is unusual - a retrospective partnership post rather than a new announcement + new blog URL dg6pjWF9 + no hashtags",
        "campaign": "partnership - Fusion Practices + Unit4 origin reminder",
        "angle": "thought_leadership + community_celebration",
    },
    {
        "post_id": "SS091", "batch": "batch19",
        "view_completeness": "full", "cta_confidence": "unknown",
        "caption": (
            "Announcement!! GrantsNow Forms Strategic Partnership with @NGI to "
            "Transform K-12 Grant Management in the U.S.\n\n"
            "We are thrilled to announce this partnership, focused on "
            "delivering a modern, end-to-end grant management platform tailored "
            "for K-12 school districts across the United States.\n\n"
            "Read more here on our partnerships page: "
            "https://lnkd.in/dCgybfEY\n\n"
            "#GrantsNow #NGI #K12 #Grantsmanagement"
        ),
        "value_prop_line": "GrantsNow + NGI strategic partnership to deliver a modern end-to-end grant management platform for K-12 school districts across the United States.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "NGI, K-12, US market, grant management, school districts, United States, partnership",
        "tone": "conversational",
        "pov": "brand-first-person",
        "offer_type": "partnership announcement",
        "cta_placement": "end",
        "cta_type_caption": "read",
        "cta_verb": "Read",
        "has_question_prompt": "no",
        "hashtag_style": "brand + partner (light 4 tags)",
        "media_type": "image",
        "primary_visual": "photo + typography with NGI co-brand",
        "image_subject": "dark teal-tinted US urban skyline (looks like NYC-style buildings)",
        "background_type": "photographic",
        "background_dominant_colour": "dark teal-tinted urban skyline",
        "foreground_dominant_colour": "white type + yellow highlighter on 'NGI' + NGI red arrow logo",
        "palette": "brand-teal + accent-yellow + NGI-red",
        "contrast_level": "high",
        "texture": "photo with heavy overlay",
        "person_present": "no", "face_visible": "no", "number_of_people": 0,
        "object_of_focus": "the NGI partnership announcement + yellow highlight on NGI",
        "text_on_image": "yes",
        "headline_on_image": "We're excited to partner with NGI to streamline and modernise Grant management in the U.S.",
        "headline_style": "sentence-case mixed-weight bold with yellow highlighter on 'NGI'",
        "headline_chars": 90,
        "subheadline_on_image": "Read about our partnership",
        "image_cta_text": "LINK IN DESCRIPTION",
        "brand_marks": "GrantsNow logo TL + NGI red arrow logo TR",
        "brand_placement": "corners",
        "graphic_style": "corporate partnership poster with US urban skyline backdrop",
        "notable_element": "FOURTH PARTNERSHIP ANNOUNCEMENT (SS071 Arribatec + SS079 Oracle + SS090 Fusion Practices/Unit4 + SS091 NGI) + first explicit US K-12 market partnership (connects to SS059 K-12 school targeting) + double exclamation 'Announcement!!' + @NGI mention in caption (first at-mention in a caption in the whole set) + yellow highlighter on NGI (like SS013 SS026 SS027 SS081 highlighter treatment)",
        "campaign": "partnership - NGI US K-12",
        "angle": "thought_leadership + community_celebration",
    },
    {
        "post_id": "SS005", "batch": "batch1",
        "view_completeness": "full", "cta_confidence": "verified",
        "caption": (
            "Researchers, administrators, reviewers, and finance teams each need "
            "access to different information throughout the funding lifecycle.\n\n"
            "Our latest whitepaper explores how role-based access can help "
            "universities protect sensitive information, improve collaboration, and "
            "ensure every user sees the information relevant to their "
            "responsibilities.\n\n"
            "Download it here: https://lnkd.in/eVuMpbP2\n\n"
            "#GrantsNow #ResearchFunding #Whitepaper #Funding #Research"
        ),
        "value_prop_line": "Role-based access can help universities protect sensitive information, improve collaboration, and ensure every user sees the information relevant to their responsibilities.",
        "value_prop_in_first_3_sentences": "yes",
        "industry_keywords": "role-based access, universities, funding lifecycle, researchers, administrators, reviewers, finance teams",
        "tone": "authoritative",
        "pov": "brand-third-person",
        "offer_type": "whitepaper",
        "cta_placement": "end",
        "cta_type_caption": "download",
        "cta_verb": "Download",
        "has_question_prompt": "no",
        "hashtag_style": "brand + niche",
        "media_type": "image",
        "primary_visual": "photo + product panel",
        "image_subject": "professional woman working on a laptop",
        "background_type": "photographic (right) + solid (left)",
        "background_dominant_colour": "dark teal (product panel) + warm neutral (photo)",
        "foreground_dominant_colour": "dark teal typography + WHITEPAPER yellow pill",
        "palette": "brand-teal + gold + photographic",
        "contrast_level": "high",
        "texture": "mixed - photo realistic and flat panel",
        "person_present": "yes", "face_visible": "yes", "number_of_people": 1,
        "object_of_focus": "person + WHITEPAPER pill tag",
        "text_on_image": "yes",
        "headline_on_image": "Give every user the right access",
        "headline_style": "mixed-weight bold",
        "headline_chars": 33,
        "subheadline_on_image": "Improve security, visibility, and collaboration across research funding",
        "image_cta_text": "Download the Whitepaper to learn more",
        "brand_marks": "GrantsNow logo + HM Government G-Cloud Supplier + WHITEPAPER yellow pill",
        "brand_placement": "corners + label pill on product panel",
        "graphic_style": "editorial photo plus teal product panel",
        "notable_element": "human face - only post in this batch with a person - and yellow WHITEPAPER pill acting as content-type signal",
        "campaign": "whitepaper - role-based access",
        "angle": "product_capability + pain_point",
    },
]


COLUMNS = [
    # identity + capture confidence
    "post_id", "batch", "view_completeness", "cta_confidence",
    # caption verbatim + auto-derived text metrics
    "caption",
    "first_line", "first_line_chars", "first_line_type",
    "pre_seemore_chars", "pre_seemore_hook_complete",
    "word_count", "sentence_count", "paragraph_count",
    "avg_sentence_words", "reading_grade",
    "has_bullets", "bullet_count",
    "has_emojis", "emoji_count",
    "has_bold_or_caps_emphasis",
    # content + messaging (judged)
    "value_prop_line", "value_prop_in_first_3_sentences",
    "industry_keywords", "tone", "pov",
    # cta + engagement drivers
    "offer_type", "cta_placement", "cta_type_caption", "cta_verb",
    "has_question_prompt",
    "hashtag_count", "hashtags", "hashtag_style",
    "at_mentions", "urls_in_caption",
    # visual - subject and composition
    "media_type", "primary_visual", "image_subject",
    "person_present", "face_visible", "number_of_people",
    "object_of_focus",
    # visual - colour and texture
    "background_type", "background_dominant_colour",
    "foreground_dominant_colour", "palette", "contrast_level", "texture",
    # visual - text on image
    "text_on_image", "headline_on_image", "headline_style",
    "headline_chars", "subheadline_on_image", "image_cta_text",
    # visual - brand + notable pattern
    "brand_marks", "brand_placement", "graphic_style", "notable_element",
    # cross-cut
    "campaign", "angle",
]


def build():
    rows = []
    for p in POSTS:
        row = {}
        auto = auto_text_fields(p.get("caption", ""))
        # start with all manual fields, then overlay auto-derived ones
        for k in COLUMNS:
            if k in p:
                row[k] = p[k]
            elif k in auto:
                row[k] = auto[k]
            else:
                row[k] = ""
        rows.append(row)

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows, {len(COLUMNS)} cols -> {OUT}")


if __name__ == "__main__":
    build()
