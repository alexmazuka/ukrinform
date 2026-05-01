# CensorZero: Audit of IMI's Assessment of Ukrinform

> Public version: **79,505 audited articles across 3 periods**  
> Source-audit subset: **51,589 audited articles across 2 post-appointment periods**

This repository contains an open research project about IMI's public reasoning for excluding and later re-including Ukrinform in the White List.

The project now keeps **both research layers visible**:

1. `docs/` and `data/explorer_data.json`
   Main public comparison across three periods:
   - `P0` before Matsuka, when Ukrinform was still in the White List
   - `P1` Matsuka period, when Ukrinform was excluded
   - `P2` later period before re-inclusion

2. `data/corpus_fast.csv` and `dashboard/`
   Two-period audited source-analysis subset:
   - `P1` Matsuka period
   - `P2` later period before re-inclusion

Method corrections made on `2026-04-30` are documented in [CORRECTIONS.md](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/CORRECTIONS.md).

## Canonical Results

### Three periods, without ATO

| Period | Audited | Parket | Balance |
| --- | ---: | ---: | ---: |
| P0: 2023-05-01 -> 2023-10-31 | 18,369 | 5.80% | 6.60% |
| P1: 2023-11-09 -> 2024-04-25 | 18,375 | 4.97% | 5.77% |
| P2: 2025-07-01 -> 2025-12-15 | 20,855 | 4.14% | 4.87% |

Pairwise parket comparison without ATO:
- `P0 vs P1`: `p=0.00047`, Cohen's `h=0.0365`
- `P0 vs P2`: `p=3.27e-14`, Cohen's `h=0.0766`
- `P1 vs P2`: `p=7.08e-05`, Cohen's `h=0.0401`

### Three periods, with ATO

| Period | Audited | Parket | Balance |
| --- | ---: | ---: | ---: |
| P0: 2023-05-01 -> 2023-10-31 | 27,916 | 5.87% | 6.72% |
| P1: 2023-11-09 -> 2024-04-25 | 26,342 | 5.12% | 6.01% |
| P2: 2025-07-01 -> 2025-12-15 | 25,247 | 4.67% | 5.57% |

### Two-period audited subset

| Scenario | P1 Parket | P2 Parket | P1 Balance | P2 Balance |
| --- | ---: | ---: | ---: | ---: |
| Without ATO | 4.97% | 4.14% | 5.77% | 4.87% |
| With ATO | 5.12% | 4.67% | 6.01% | 5.57% |

## What Changed

The current canonical rebuild fixes three repo-wide problems:

1. Official sources in article text are now classified against Ukrainian/Cyrillic entity markers, not transliterated URL markers.
2. Official URL classification now uses word boundaries and known prefixes instead of naive substring matching.
3. `parket` and `balance` are no longer computed with the same formula.

The shared implementation lives in [`canonical_metrics.py`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/canonical_metrics.py).

## Main Files

| File | Scope |
| --- | --- |
| [`docs/index.html`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/docs/index.html) | Main three-period public page |
| [`docs/explorer_data.json`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/docs/explorer_data.json) | Explorer dataset for `79,505` audited articles |
| [`docs/graph_data.json`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/docs/graph_data.json) | Monthly/rubric aggregates for 3 periods |
| [`data/corpus_fast.csv`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/corpus_fast.csv) | Canonical two-period audited corpus (`51,667` rows, `51,589` audited) |
| [`data/statistical_tests_v3.json`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/statistical_tests_v3.json) | Canonical two-period statistical summary |
| [`data/statistical_tests_v3_three_periods.json`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/statistical_tests_v3_three_periods.json) | Canonical three-period statistical summary |
| [`data/period_zero/p0_audited.json`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/period_zero/p0_audited.json) | Audited period-zero source data |
| [`dashboard/index.html`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/dashboard/index.html) | Two-period dashboard view kept for transparency |

## Rebuild

```bash
git clone https://github.com/alexmazuka/ukrinform.git
cd ukrinform
python3 scripts/rebuild_public_assets.py
```

To re-run collectors/parsers instead of only rebuilding published assets:

```bash
python3 scripts/recover_missing.py
python3 scripts/audit_full_corpus.py
python3 scripts/reparse_improved.py
python3 scripts/fix_official_classification.py
python3 scripts/collect_p0_pre_matsuka.py
python3 scripts/rebuild_public_assets.py
```

## Metric Definitions

- `parket`: official URL classification + `source_count <= 1` + `non_official_source_count == 0`
- `balance`: official URL classification + `non_official_source_count == 0`
- `source_count`: extracted cited sources in article text using the improved parser

## Notes

- `data/corpus_v1_backup.csv`, `data/corpus_v2_parsed.csv`, and older public claims remain in Git history and backup files for auditability.
- `data/corpus_fast.csv` is still a **two-period** corpus; the public **three-period** layer is assembled from that corpus plus `data/period_zero/p0_audited.json`.
