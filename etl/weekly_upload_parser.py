"""
Weekly ESP campaign workbook parser.

Reads a workbook shaped like `30Aug-4Sept.xlsx` (three sheets:
Summary, "Opened 3+ Times", "Clicked 1+ Times") and returns a
parsed dict ready to feed campaign_batches.csv, emails.csv,
mql_engaged.csv and campaigns.csv.

Returns:
    {
        "week_ending": date,
        "campaigns":   [{name, sent_date, sent, delivered, delivered_pct,
                         bounced, bounced_pct, opened, opened_pct,
                         clicked, clicked_pct, subject, body}],
        "week_total":  {sent, delivered, bounced, opened, clicked},
        "openers":     [{email, company, campaign, opens}],
        "clickers":    [{email, company, campaign, clicks}],
        "warnings":    [str],
    }
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import openpyxl


# ==========================================================================
# Low-level helpers
# ==========================================================================
def _norm_header(s: Any) -> str:
    """Lowercase, strip whitespace + parenthetical suffixes."""
    if s is None:
        return ""
    t = str(s).lower().strip()
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)   # drop trailing "(...)"
    t = re.sub(r"\s+", " ", t)
    return t


def _split_count_pct(cell: Any):
    """Split a cell like '592 (92.9%)' into (592, 0.929).

    Handles plain integers, '2,222 (96.8%)', '176' or '6.0%'.
    Returns (count, pct_as_fraction) either of which may be None.
    """
    if cell is None:
        return None, None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return int(cell), None
    s = str(cell).strip()
    if not s:
        return None, None
    # Count part - everything before "("
    count_part = s.split("(")[0].strip().replace(",", "")
    count = None
    if count_part:
        try:
            count = int(float(count_part))
        except ValueError:
            count = None
    # Percent part - between "(" and ")"
    pct = None
    m = re.search(r"\(([\d\.]+)\s*%\)", s)
    if m:
        try:
            pct = float(m.group(1)) / 100.0
        except ValueError:
            pct = None
    else:
        # Bare percent like "6.0%"
        m2 = re.search(r"([\d\.]+)\s*%\s*$", s)
        if m2:
            try:
                pct = float(m2.group(1)) / 100.0
            except ValueError:
                pct = None
    return count, pct


def _to_date(v: Any) -> Optional[_dt.date]:
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, str) and v.strip():
        # Try a few common formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y"):
            try:
                return _dt.datetime.strptime(v.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _rows(ws) -> List[List[Any]]:
    """Return every row of the sheet as a list, trailing None trimmed."""
    out = []
    for row in ws.iter_rows(values_only=True):
        vals = list(row)
        while vals and vals[-1] is None:
            vals.pop()
        out.append(vals)
    return out


# ==========================================================================
# Section detectors on the Summary sheet
# ==========================================================================
_CAMPAIGN_HDR_TOKENS = {"campaign name", "sent", "delivered",
                          "bounced", "opened"}
_OPENERS_HDR_TOKENS  = {"email", "company", "campaign", "total opens"}
_CLICKERS_HDR_TOKENS = {"email", "company", "campaign", "total clicks"}


def _is_campaign_hdr(row: List[Any]) -> bool:
    tokens = {_norm_header(c) for c in row}
    return _CAMPAIGN_HDR_TOKENS.issubset(tokens)


def _is_openers_hdr(row: List[Any]) -> bool:
    tokens = {_norm_header(c) for c in row}
    return _OPENERS_HDR_TOKENS.issubset(tokens)


def _is_clickers_hdr(row: List[Any]) -> bool:
    tokens = {_norm_header(c) for c in row}
    return _CLICKERS_HDR_TOKENS.issubset(tokens)


def _is_blank(row: List[Any]) -> bool:
    return not any(c not in (None, "") for c in row)


# ==========================================================================
# Summary sheet parsing
# ==========================================================================
def _parse_summary_sheet(rows: List[List[Any]], warnings: List[str]):
    """
    Return (campaigns, week_total, campaign_copy_by_name).
    campaign_copy_by_name maps campaign name (loose) to {subject, body}.
    """
    # 1. Find the Campaign Name header row.
    hdr_idx = None
    for i, row in enumerate(rows):
        if _is_campaign_hdr(row):
            hdr_idx = i
            break
    if hdr_idx is None:
        raise ValueError("Could not locate the 'Campaign Name' header "
                          "row on the Summary sheet.")

    header = [_norm_header(c) for c in rows[hdr_idx]]

    def _col(name: str) -> Optional[int]:
        for j, h in enumerate(header):
            if h == name:
                return j
        return None

    idx = {n: _col(n) for n in
           ("campaign name", "sent", "delivered", "bounced",
            "opened", "clicks", "date")}
    # Clicks column may be labelled 'clicks' or 'clicked'
    if idx["clicks"] is None:
        idx["clicks"] = _col("clicked")

    campaigns: List[Dict[str, Any]] = []
    week_total: Dict[str, Any] = {}

    # 2. Walk rows after header until blank/next-section.
    i = hdr_idx + 1
    while i < len(rows):
        row = rows[i]
        if _is_blank(row):
            break
        first = str(row[0] or "").strip()
        if not first:
            break
        # Stop if we hit the next section header (Opened 3+..., etc.)
        if any(tok in first.lower() for tok in
               ("opened 3+", "clicked 3+", "clicked 1+")):
            break

        # Identify the TOTAL row
        is_total = first.upper().startswith("TOTAL")

        def cell(name):
            j = idx.get(name)
            if j is None or j >= len(row):
                return None
            return row[j]

        c_sent, _         = _split_count_pct(cell("sent"))
        c_delivered, p_d  = _split_count_pct(cell("delivered"))
        c_bounced,   p_b  = _split_count_pct(cell("bounced"))
        c_opened,    p_o  = _split_count_pct(cell("opened"))
        c_clicked,   p_c  = _split_count_pct(cell("clicks"))
        date_val = _to_date(cell("date"))

        record = {
            "name":          first,
            "sent_date":     date_val,
            "sent":          c_sent,
            "delivered":     c_delivered,
            "delivered_pct": p_d,
            "bounced":       c_bounced,
            "bounced_pct":   p_b,
            "opened":        c_opened,
            "opened_pct":    p_o,
            "clicked":       c_clicked,
            "clicked_pct":   p_c,
        }

        if is_total:
            week_total = {k: v for k, v in record.items()
                          if k != "name"}
        else:
            campaigns.append(record)
        i += 1

    if not campaigns:
        raise ValueError("Summary sheet parsed but no campaign rows "
                          "were found.")

    # 3. Look for campaign copy blocks below.
    #    Structure in the sample: a title line for the campaign, then
    #    'Hello $[UD:FIRST_NAME||]$,' opens the body. We collect until
    #    a blank double-line or another campaign title.
    #    Because the sheet has few structural signals, we use a
    #    lightweight heuristic: find rows whose first cell equals a
    #    short label such as "Finance WP 8" or "Research Email".
    #    Under each label the next non-blank row is the subject line,
    #    and body continues until the next known label or EOF.
    def _first(r):
        return str(r[0]).strip() if r and r[0] is not None else ""

    labels = []
    for i, row in enumerate(rows):
        first = _first(row)
        if not first:
            continue
        # Heuristic - short line without spaces/quirks that appears
        # ABOVE a "Hello" or "Hi" salutation within 2-4 lines.
        if len(first) <= 60 and not first.startswith(("Hello", "Hi",
                                                        "Good ")):
            for j in range(i + 1, min(i + 5, len(rows))):
                nxt = _first(rows[j])
                if nxt.startswith(("Hello", "Hi", "Good afternoon",
                                     "Good morning")):
                    labels.append((i, first))
                    break

    campaign_copy: Dict[str, Dict[str, str]] = {}
    for k, (line_idx, label) in enumerate(labels):
        # subject is the first non-blank line under the label that is
        # not the salutation
        end_idx = labels[k + 1][0] if k + 1 < len(labels) else len(rows)
        subject = ""
        body_lines: List[str] = []
        seen_salutation = False
        for j in range(line_idx + 1, end_idx):
            cell_v = _first(rows[j])
            if not cell_v:
                continue
            is_salutation = cell_v.startswith(("Hello", "Hi",
                                                 "Good "))
            # Subject: first non-salutation line ABOVE the salutation
            # AND under ~120 chars (subjects are always short).
            if (not seen_salutation and not subject
                    and not is_salutation
                    and len(cell_v) <= 120):
                subject = cell_v
                continue
            if is_salutation:
                seen_salutation = True
            body_lines.append(cell_v)
        if body_lines:
            campaign_copy[label] = {
                "subject": subject,
                "body":    "\n".join(body_lines),
            }

    return campaigns, week_total, campaign_copy


# ==========================================================================
# Openers / clickers standalone sheets
# ==========================================================================
def _parse_engagement_sheet(rows: List[List[Any]], kind: str,
                              warnings: List[str]) -> List[Dict[str, Any]]:
    """
    kind is 'opens' or 'clicks'. Header expected:
        Email | Company | Campaign | Total Opens/Clicks
    """
    hdr_idx = None
    for i, row in enumerate(rows):
        toks = {_norm_header(c) for c in row}
        need = {"email", "company", "campaign",
                "total opens" if kind == "opens" else "total clicks"}
        if need.issubset(toks):
            hdr_idx = i
            break
    if hdr_idx is None:
        # Fallback: any row with email + company + campaign
        for i, row in enumerate(rows):
            toks = {_norm_header(c) for c in row}
            if {"email", "company", "campaign"}.issubset(toks):
                hdr_idx = i
                break
    if hdr_idx is None:
        warnings.append(f"Could not locate the '{kind}' header row.")
        return []

    header = [_norm_header(c) for c in rows[hdr_idx]]

    def col(name):
        try:
            return header.index(name)
        except ValueError:
            return None

    j_email    = col("email")
    j_company  = col("company")
    j_campaign = col("campaign")
    j_count    = col("total opens" if kind == "opens" else "total clicks")

    if any(x is None for x in (j_email, j_company, j_campaign)):
        warnings.append(f"'{kind}' sheet header missing required columns.")
        return []

    out: List[Dict[str, Any]] = []
    for row in rows[hdr_idx + 1:]:
        if _is_blank(row):
            continue
        email = str(row[j_email]).strip() if j_email < len(row) and row[j_email] else ""
        if not email or "@" not in email:
            continue
        company  = str(row[j_company]).strip() if j_company < len(row) and row[j_company] else ""
        campaign = str(row[j_campaign]).strip() if j_campaign < len(row) and row[j_campaign] else ""
        count = None
        if j_count is not None and j_count < len(row):
            try:
                count = int(row[j_count]) if row[j_count] is not None else None
            except (ValueError, TypeError):
                count = None
        out.append({
            "email":    email,
            "company":  company,
            "campaign": campaign,
            kind:       count,
        })
    return out


# ==========================================================================
# Public entry point
# ==========================================================================
def parse_workbook(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    warnings: List[str] = []

    # 1. Summary
    summary_name = next(
        (n for n in wb.sheetnames if _norm_header(n) == "summary"),
        wb.sheetnames[0])
    summary_rows = _rows(wb[summary_name])
    campaigns, week_total, copy_by_label = _parse_summary_sheet(
        summary_rows, warnings)

    # 2. Match copy to campaigns by keyword overlap.
    #    Prefer the identifying "Promo_X" token in the campaign name
    #    (e.g. "Promo_Fin" -> Finance, "Promo_Research" -> Research)
    #    so the Fin/Research variants don't collide when both mention
    #    "Finance" in their descriptor text.
    _PERSONA_KEYS = {
        "fin":      "finance",
        "finance":  "finance",
        "research": "research",
        "it":       "it",
        "hr":       "hr",
    }

    def _key_of(name: str) -> str:
        m = re.search(r"promo_([A-Za-z]+)", name, flags=re.IGNORECASE)
        if m:
            k = m.group(1).lower()
            return _PERSONA_KEYS.get(k, k)
        n = name.lower()
        for k, v in _PERSONA_KEYS.items():
            if k in n:
                return v
        return ""

    def _match_copy(campaign_name: str):
        target_key = _key_of(campaign_name)
        best = (0, None)
        for label, blob in copy_by_label.items():
            label_key = _key_of(label)
            # Big bonus for exact persona-key alignment
            score = 0
            if target_key and label_key and target_key == label_key:
                score += 10
            # Fall back to token overlap
            tokens = [t for t in re.split(r"\W+", label.lower())
                      if len(t) >= 3]
            score += sum(1 for t in tokens
                         if t in campaign_name.lower())
            if score > best[0]:
                best = (score, blob)
        return best[1] or {"subject": "", "body": ""}

    for c in campaigns:
        blob = _match_copy(c["name"])
        c["subject"] = blob.get("subject", "") or ""
        c["body"]    = blob.get("body", "") or ""

    # 3. Openers
    openers_sheet = next(
        (n for n in wb.sheetnames if "opened" in n.lower()), None)
    openers: List[Dict[str, Any]] = []
    if openers_sheet:
        openers = _parse_engagement_sheet(_rows(wb[openers_sheet]),
                                            "opens", warnings)
    else:
        # Fall back to the mini-list inside Summary
        openers = _extract_engagement_from_summary(summary_rows,
                                                    kind="opens",
                                                    warnings=warnings)

    # 4. Clickers
    clickers_sheet = next(
        (n for n in wb.sheetnames if "click" in n.lower()), None)
    clickers: List[Dict[str, Any]] = []
    if clickers_sheet:
        clickers = _parse_engagement_sheet(_rows(wb[clickers_sheet]),
                                             "clicks", warnings)
    else:
        clickers = _extract_engagement_from_summary(summary_rows,
                                                    kind="clicks",
                                                    warnings=warnings)

    # 5. Week ending date - derive from the campaign date column
    week_ending = None
    for c in campaigns:
        if c.get("sent_date"):
            week_ending = max(week_ending, c["sent_date"]) \
                if week_ending else c["sent_date"]

    return {
        "week_ending": week_ending,
        "campaigns":   campaigns,
        "week_total":  week_total,
        "openers":     openers,
        "clickers":    clickers,
        "warnings":    warnings,
    }


def _extract_engagement_from_summary(rows: List[List[Any]], kind: str,
                                       warnings: List[str]
                                       ) -> List[Dict[str, Any]]:
    """When there's no standalone sheet, look inside Summary for the
    'Opened/Clicked 3+' block and read those rows."""
    marker = "opened 3+" if kind == "opens" else "clicked"
    hdr_idx = None
    for i, row in enumerate(rows):
        first = str(row[0] or "").lower() if row else ""
        if marker in first:
            # Header is the next non-blank row
            for j in range(i + 1, min(i + 4, len(rows))):
                if any(_norm_header(c) == "email" for c in rows[j]):
                    hdr_idx = j
                    break
            break
    if hdr_idx is None:
        return []
    # Slice a small window and parse
    return _parse_engagement_sheet(rows[hdr_idx:], kind, warnings)


# ==========================================================================
# Convenience CLI
# ==========================================================================
if __name__ == "__main__":
    import sys, json
    p = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Users\KunalSharma\Downloads\30Aug-4Sept.xlsx"
    r = parse_workbook(p)
    print(f"week_ending: {r['week_ending']}")
    print(f"campaigns:   {len(r['campaigns'])}")
    print(f"week_total:  {r['week_total']}")
    print(f"openers:     {len(r['openers'])}")
    print(f"clickers:    {len(r['clickers'])}")
    print(f"warnings:    {r['warnings']}")
    for c in r["campaigns"]:
        print(f"  - {c['name'][:60]!r} sent={c['sent']} "
              f"delivered={c['delivered']} opened={c['opened']} "
              f"clicked={c['clicked']} subj={c['subject'][:40]!r}")
