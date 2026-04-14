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
- ✅ Source count per article
- ✅ Source type classification (official vs non-official)

### Does NOT check
- ❌ Completeness (background, context, who/what/where/when)
- ❌ Accuracy (factual correctness)
- ❌ Fact/comment separation (requires contextual reading)
- ❌ Sexism / hate speech (requires NLP or manual review)
- ❌ Sponsored content marking
- ❌ Presumption of innocence

IMI cited "parket messages" and "insufficient balance" as the specific reasons for Ukrinform's exclusion. This research checks those two signals on the full public corpus.

## File versioning

All changes are tracked in Git history. The corpus CSV has been modified through the following stages:
1. Initial collection: 42,073 records (build_study_fast.py)
2. Recovery of Jan-Feb 2024: +9,594 records → 51,667
3. Full HTML audit: 51,589 audited with source counts
4. ATO exclusion for core analysis: 39,230

Each stage is documented in Git commits with timestamps.
