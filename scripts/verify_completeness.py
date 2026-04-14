"""
Phase 0: Data Completeness Verification
========================================
Independently verifies the corpus by checking all weekly sitemaps
for both periods, counting URLs per week/month, and identifying gaps.

Outputs: data/COMPLETENESS_REPORT.json with full audit trail.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

PRIMARY_RUBRICS = {
    'rubric-polytics', 'rubric-economy', 'rubric-society',
    'rubric-regions', 'rubric-ato', 'rubric-tymchasovo-okupovani',
    'rubric-vidbudova',
}

PERIODS = {
    'before_exclusion_matsuka': {
        'label': 'Period 1: Matsuka era (before IMI exclusion)',
        'start': date(2023, 11, 9),
        'end': date(2024, 4, 25),
    },
    'before_reinclusion_after_departure': {
        'label': 'Period 2: Before reinclusion (after Matsuka departure)',
        'start': date(2025, 7, 1),
        'end': date(2025, 12, 15),
    },
}


def iso_weeks_between(start: date, end: date) -> list[tuple[int, int]]:
    current = start
    weeks: set[tuple[int, int]] = set()
    while current <= end:
        iso = current.isocalendar()
        weeks.add((iso.year, iso.week))
        current += timedelta(days=1)
    return sorted(weeks)


def rubric_from_url(url: str) -> str:
    match = re.search(r'ukrinform\.ua/(rubric-[a-z-]+)/', url)
    return match.group(1) if match else ''


def parse_sitemap(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    items = []
    for url_el in root.findall('sm:url', ns):
        loc = url_el.findtext('sm:loc', default='', namespaces=ns).strip()
        lastmod = url_el.findtext('sm:lastmod', default='', namespaces=ns).strip()
        if loc:
            items.append({'loc': loc, 'lastmod': lastmod})
    return items


def check_sitemaps_for_period(period_slug: str, period: dict) -> dict:
    """Fetch every weekly sitemap for a period and count URLs."""
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT

    weeks = iso_weeks_between(period['start'], period['end'])
    result = {
        'period_slug': period_slug,
        'label': period['label'],
        'start': period['start'].isoformat(),
        'end': period['end'].isoformat(),
        'weeks_expected': len(weeks),
        'weeks_checked': [],
        'monthly_counts': defaultdict(int),
        'total_urls_in_rubrics': 0,
        'total_urls_all': 0,
        'errors': [],
    }

    for year, week in weeks:
        url = f'https://www.ukrinform.ua/sitemap/{year}/{week:02d}.xml'
        week_info = {
            'url': url,
            'year': year,
            'week': week,
            'status': None,
            'total_urls': 0,
            'urls_in_rubrics': 0,
            'urls_in_date_range': 0,
        }

        try:
            resp = session.get(url, timeout=15)
            week_info['status'] = resp.status_code

            if resp.status_code == 200:
                items = parse_sitemap(resp.text)
                week_info['total_urls'] = len(items)

                for item in items:
                    rubric = rubric_from_url(item['loc'])
                    if rubric not in PRIMARY_RUBRICS:
                        continue
                    week_info['urls_in_rubrics'] += 1

                    # Parse date from lastmod
                    lastmod = item['lastmod']
                    if lastmod:
                        d_str = lastmod[:10]  # YYYY-MM-DD
                        try:
                            d = date.fromisoformat(d_str)
                            if period['start'] <= d <= period['end']:
                                week_info['urls_in_date_range'] += 1
                                month_key = d.strftime('%Y-%m')
                                result['monthly_counts'][month_key] += 1
                        except ValueError:
                            pass

                result['total_urls_in_rubrics'] += week_info['urls_in_rubrics']
                result['total_urls_all'] += week_info['total_urls']
            else:
                result['errors'].append(f'{url} returned {resp.status_code}')
        except Exception as e:
            week_info['status'] = 'error'
            result['errors'].append(f'{url}: {e}')

        result['weeks_checked'].append(week_info)
        print(f"  [{period_slug}] {year}/w{week:02d} -> status={week_info['status']}, "
              f"in_rubrics={week_info['urls_in_rubrics']}, in_date_range={week_info['urls_in_date_range']}")
        time.sleep(0.3)  # Be polite to server

    result['monthly_counts'] = dict(sorted(result['monthly_counts'].items()))
    return result


def compare_with_corpus(sitemap_counts: dict, corpus_path: Path) -> dict:
    """Compare sitemap URL counts with existing corpus CSV."""
    import csv
    corpus_monthly = defaultdict(int)
    corpus_total = 0

    with open(corpus_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            corpus_total += 1
            month = row.get('month', '')
            if month:
                corpus_monthly[month] += 1

    comparison = {
        'corpus_total': corpus_total,
        'corpus_monthly': dict(sorted(corpus_monthly.items())),
        'sitemap_monthly': sitemap_counts,
        'gaps': {},
    }

    all_months = sorted(set(list(corpus_monthly.keys()) + list(sitemap_counts.keys())))
    for month in all_months:
        corpus_n = corpus_monthly.get(month, 0)
        sitemap_n = sitemap_counts.get(month, 0)
        if sitemap_n > 0 and corpus_n < sitemap_n * 0.8:  # >20% missing
            comparison['gaps'][month] = {
                'corpus': corpus_n,
                'sitemap': sitemap_n,
                'missing_approx': sitemap_n - corpus_n,
                'coverage_pct': round(corpus_n / sitemap_n * 100, 1) if sitemap_n else 0,
            }

    return comparison


def main():
    print("=" * 60)
    print("PHASE 0: DATA COMPLETENESS VERIFICATION")
    print("=" * 60)

    all_sitemap_monthly = {}
    period_reports = {}

    for slug, period in PERIODS.items():
        print(f"\nChecking {slug} ({period['start']} to {period['end']})...")
        report = check_sitemaps_for_period(slug, period)
        period_reports[slug] = report
        for month, count in report['monthly_counts'].items():
            all_sitemap_monthly[month] = all_sitemap_monthly.get(month, 0) + count

    # Compare with existing corpus
    corpus_path = DATA_DIR / 'corpus_fast.csv'
    print(f"\nComparing with existing corpus ({corpus_path})...")
    comparison = compare_with_corpus(all_sitemap_monthly, corpus_path)

    # Build final report
    report = {
        'generated_at': date.today().isoformat(),
        'description': 'Independent verification of corpus completeness via sitemap audit',
        'periods': period_reports,
        'comparison_with_corpus': comparison,
        'verdict': None,
    }

    # Determine verdict
    gaps = comparison.get('gaps', {})
    if not gaps:
        report['verdict'] = {
            'code': 'A',
            'label': 'FULL CORPUS',
            'detail': 'No significant gaps detected. All months have adequate coverage.',
        }
    elif len(gaps) <= 2:
        report['verdict'] = {
            'code': 'B',
            'label': 'PARTIAL COVERAGE',
            'detail': f'Gaps detected in {len(gaps)} month(s): {", ".join(gaps.keys())}. '
                      'Comparison should use only complete months.',
            'gap_months': list(gaps.keys()),
        }
    else:
        report['verdict'] = {
            'code': 'C',
            'label': 'CRITICAL INCOMPLETENESS',
            'detail': f'Major gaps in {len(gaps)} months. Dashboard must include strong disclaimer.',
            'gap_months': list(gaps.keys()),
        }

    # Save report
    report_path = DATA_DIR / 'COMPLETENESS_REPORT.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"VERDICT: [{report['verdict']['code']}] {report['verdict']['label']}")
    print(report['verdict']['detail'])
    print(f"\nReport saved: {report_path}")

    # Print summary table
    print(f"\n{'Month':<10} {'Sitemap':>8} {'Corpus':>8} {'Status':>10}")
    print('-' * 40)
    all_months = sorted(set(list(all_sitemap_monthly.keys()) + list(comparison['corpus_monthly'].keys())))
    for month in all_months:
        sm = all_sitemap_monthly.get(month, 0)
        cp = comparison['corpus_monthly'].get(month, 0)
        status = 'OK' if month not in gaps else f'GAP ({gaps[month]["coverage_pct"]}%)'
        print(f"{month:<10} {sm:>8} {cp:>8} {status:>10}")

    return report


if __name__ == '__main__':
    main()
