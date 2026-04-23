# Data Version Note

## Canonical Numbers (single source of truth)

| Stage | Count | Explanation |
|-------|-------|-------------|
| **Collected from sitemaps** | 51,667 | URLs extracted from 50 weekly Ukrinform sitemaps |
| **Audited (HTML parsed)** | 51,589 | Successfully fetched and parsed article HTML |
| **Excluded from audit** | 78 | Server returned error/timeout during HTML fetch (0.15%) |
| **Core analysis (no ATO)** | 39,230 | Excluding military bulletins rubric |
| **ATO/Defense rubric** | 12,359 | Shown separately — inherently single-source official content |

### By Period

| Period | In CSV | Audited | Without ATO |
|--------|--------|---------|-------------|
| P1: Matsuka (2023-11-09 → 2024-04-25) | 26,380 | 26,342 | 18,375 |
| P2: Before reinclusion (2025-07-01 → 2025-12-15) | 25,287 | 25,247 | 20,855 |

### Why 51,667 ≠ 51,589?
78 articles (0.15%) could not be fetched from Ukrinform's server during the HTML parsing phase. Their URLs exist in `corpus_fast.csv` but `audited` = False. This does not affect analytical conclusions.

### Why two analysis scenarios?
The ATO/Defense rubric contains military bulletins (Genshtab reports) that by definition have a single official source. This is not a journalism quality issue — it is the nature of wartime military communication. We present both scenarios for full transparency.

### Deprecated files
- `data/study_fast.json` — **ARCHIVED.** Contains pre-recovery sample analysis (3,600 articles) from the original corpus of 42,073. This file predates the January-February 2024 data recovery and uses outdated numbers. It is preserved for audit trail purposes only. **Do not use for current analysis.**

## What this research checks and what it does not

### Checks (proxy metrics for two IMI-cited criteria)
- ✅ "Parket" content — official source + ≤1 source + 0 non-official sources
- ✅ Balance risk — official source + 0 non-official sources
- ✅ Source count per article (via regex on reporting verbs)
- ✅ Source type classification (official vs non-official, via URL slug keywords)

### ⚠️ KNOWN METHODOLOGICAL LIMITATION: "Parket" via source_count == 0

**Critical finding from second-pass audit (April 2026):**

Of all articles flagged as `likely_parket=True`, **99.9% have `source_count == 0`** — meaning our regex parser found zero cited sources in the article text. This does not mean they are "parket" in the journalistic sense; it means one of three things:

1. **Legitimate short briefings** — e.g. Genshtab daily reports: "За добу 82 зіткнення" — by nature have no quoted sources
2. **Source mentioned in title only** — e.g. "Russia continues terror — Genshtab" — source is in headline but our parser only reads body text
3. **Technical parsing limits** — regex catches common reporting verbs (заявив, повідомив) but misses some constructions

**Strict definition** (official source + exactly 1 source + 0 non-official): flags <0.01% of articles in both periods. Too strict to be useful.

**Current definition** (≤1 source incl. zero): flags 7.86% P1 / 7.98% P2 (with ATO) or 7.98% P1 / 7.55% P2 (without ATO). Technically includes many short briefings that are not true "parket."

**Why the main conclusion still holds:** Both definitions produce **essentially identical rates across the two periods**. Any parser imperfection affects P1 and P2 equally. The core finding — no significant difference between Matsuka era and post-Matsuka period — is robust against this limitation.

**What this means practically:** Our metric is best read as "share of articles with an official-slug URL and no quoted sources found in body text." This is a relevant proxy for "parket" but not identical to IMI's manual assessment.

### Does NOT check
- ❌ Completeness (background, context, who/what/where/when)
- ❌ Accuracy (factual correctness)
- ❌ Fact/comment separation (requires contextual reading)
- ❌ Sexism / hate speech (requires NLP or manual review)
- ❌ Sponsored content marking
- ❌ Presumption of innocence

IMI cited "parket messages" and "insufficient balance" as the specific reasons for Ukrinform's exclusion. This research checks those two signals on the full public corpus — subject to the methodological limitation disclosed above.

## File versioning

All changes are tracked in Git history. The corpus CSV has been modified through the following stages:
1. Initial collection: 42,073 records (build_study_fast.py)
2. Recovery of Jan-Feb 2024: +9,594 records → 51,667
3. Full HTML audit: 51,589 audited with source counts
4. ATO exclusion for core analysis: 39,230

Each stage is documented in Git commits with timestamps.
