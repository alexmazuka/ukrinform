"""
Phase 0.2: Recover missing Jan-Feb 2024 data from sitemaps.
============================================================
Fetches weekly sitemaps for weeks 01-09 of 2024,
extracts URLs in primary rubrics with dates in the target range,
deduplicates against existing corpus, and saves recovered URLs.
"""
from __future__ import annotations

import csv
import json
import re
import time
from collections import defaultdict
from datetime import date
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

PERIOD_START = date(2023, 11, 9)
PERIOD_END = date(2024, 4, 25)
PERIOD_SLUG = 'before_exclusion_matsuka'
PERIOD_LABEL = 'Перед виключенням за керівництва Олексія Мацуки'

# Weeks to recover: all weeks that overlap with Jan 1 - Feb 29, 2024
RECOVERY_WEEKS = [(2024, w) for w in range(1, 10)]

OFFICIAL_CATEGORY_PATTERNS = {
    'Президент / ОП': ['zelensk', 'prezident', 'ofis-prezidenta', 'opu', 'yermak', 'ermak'],
    'Уряд / Кабмін': ['kabmin', 'uryad', 'smygal', 'premyer', 'premier'],
    'Парламент': ['verhovn', 'rada', 'nardep', 'deputat', 'komitet'],
    'Міністерства': ['ministr', 'ministerstvo', 'mzs', 'minoboroni', 'mvs', 'minekonom', 'minfin', 'mon', 'mincifri', 'minkult'],
    'Силовий блок': ['genshtab', 'zsu', 'sbu', 'gur', 'dpsu', 'dsns', 'sili-oboroni', 'armiya'],
    'Регіональна влада': ['ova', 'kmva', 'kmda', 'oblrada', 'miskrada', 'mer'],
    'Держструктури / держкомпанії': ['ukrzaliznic', 'ukrenergo', 'naftogaz', 'fond-derzmajna', 'pensijn', 'podatkov', 'mitnic'],
}


def rubric_from_url(url: str) -> str:
    match = re.search(r'ukrinform\.ua/(rubric-[a-z-]+)/', url)
    return match.group(1) if match else ''


def slug_from_url(url: str) -> str:
    path = url.rstrip('/').split('/')[-1]
    return re.sub(r'^\d+-', '', path)


def official_categories_for_slug(slug: str) -> list[str]:
    low = slug.lower()
    return [cat for cat, markers in OFFICIAL_CATEGORY_PATTERNS.items()
            if any(m in low for m in markers)]


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


def load_existing_urls(csv_path: Path) -> set[str]:
    urls = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            urls.add(row['url'])
    return urls


def main():
    print("=" * 60)
    print("RECOVERING MISSING DATA: Jan-Feb 2024")
    print("=" * 60)

    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT

    # Load existing URLs to avoid duplicates
    corpus_path = DATA_DIR / 'corpus_fast.csv'
    existing_urls = load_existing_urls(corpus_path)
    print(f"Existing corpus: {len(existing_urls)} URLs")

    recovered = {}  # url -> record dict
    monthly_counts = defaultdict(int)

    for year, week in RECOVERY_WEEKS:
        url = f'https://www.ukrinform.ua/sitemap/{year}/{week:02d}.xml'
        print(f"Fetching {url}...")

        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"  SKIP: status {resp.status_code}")
                continue

            items = parse_sitemap(resp.text)
            week_new = 0

            for item in items:
                loc = item['loc']

                # Skip if already in corpus
                if loc in existing_urls or loc in recovered:
                    continue

                rubric = rubric_from_url(loc)
                if rubric not in PRIMARY_RUBRICS:
                    continue

                lastmod = item['lastmod']
                if not lastmod:
                    continue

                try:
                    d = date.fromisoformat(lastmod[:10])
                except ValueError:
                    continue

                if not (PERIOD_START <= d <= PERIOD_END):
                    continue

                slug_text = slug_from_url(loc)
                categories = official_categories_for_slug(slug_text)

                recovered[loc] = {
                    'period_slug': PERIOD_SLUG,
                    'period_label': PERIOD_LABEL,
                    'url': loc,
                    'date_value': d.isoformat(),
                    'month': d.strftime('%Y-%m'),
                    'rubric': rubric,
                    'slug_text': slug_text,
                    'official_slug': bool(categories),
                    'official_categories': categories,
                    'audit_bucket': '',
                    'audited': False,
                    'actual_title': '',
                    'source_count': -1,
                    'official_source_count': -1,
                    'non_official_source_count': -1,
                    'likely_parket': False,
                    'balance_risk': False,
                    'excerpt': '',
                }
                monthly_counts[d.strftime('%Y-%m')] += 1
                week_new += 1

            print(f"  Found {len(items)} total, {week_new} new in-scope URLs")

        except Exception as e:
            print(f"  ERROR: {e}")

        time.sleep(0.3)

    # Save recovered data
    recovered_path = DATA_DIR / 'recovered_jan_feb_2024.json'
    recovered_list = sorted(recovered.values(), key=lambda r: (r['date_value'], r['url']))

    with open(recovered_path, 'w', encoding='utf-8') as f:
        json.dump(recovered_list, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"RECOVERED: {len(recovered_list)} new URLs")
    print(f"Saved to: {recovered_path}")
    print(f"\nBy month:")
    for month in sorted(monthly_counts):
        print(f"  {month}: {monthly_counts[month]}")

    # Now merge into corpus CSV
    print(f"\nMerging into corpus CSV...")
    fieldnames = [
        'period_slug', 'period_label', 'url', 'date_value', 'month',
        'rubric', 'slug_text', 'official_slug', 'official_categories',
        'audit_bucket', 'audited', 'actual_title', 'source_count',
        'official_source_count', 'non_official_source_count',
        'likely_parket', 'balance_risk', 'excerpt',
    ]

    # Read existing rows
    existing_rows = []
    with open(corpus_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_rows.append(row)

    # Add recovered rows
    for rec in recovered_list:
        existing_rows.append({
            'period_slug': rec['period_slug'],
            'period_label': rec['period_label'],
            'url': rec['url'],
            'date_value': rec['date_value'],
            'month': rec['month'],
            'rubric': rec['rubric'],
            'slug_text': rec['slug_text'],
            'official_slug': str(rec['official_slug']),
            'official_categories': json.dumps(rec['official_categories'], ensure_ascii=False),
            'audit_bucket': rec['audit_bucket'],
            'audited': str(rec['audited']),
            'actual_title': rec['actual_title'],
            'source_count': str(rec['source_count']),
            'official_source_count': str(rec['official_source_count']),
            'non_official_source_count': str(rec['non_official_source_count']),
            'likely_parket': str(rec['likely_parket']),
            'balance_risk': str(rec['balance_risk']),
            'excerpt': rec['excerpt'],
        })

    # Sort by date then URL
    existing_rows.sort(key=lambda r: (r['date_value'], r['url']))

    # Write updated corpus
    with open(corpus_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"Updated corpus: {len(existing_rows)} total records")
    print("DONE")


if __name__ == '__main__':
    main()
