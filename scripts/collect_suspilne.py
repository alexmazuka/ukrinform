"""
Collect Suspilne Novyny articles from public sitemaps.
======================================================
Same methodology as Ukrinform: fetch sitemap, filter by date range,
parse HTML, count sources, classify parket/balance.

Two periods matching Ukrinform study:
  P1: 2023-11-09 → 2024-04-25 (Matsuka era equivalent)
  P2: 2025-07-01 → 2025-12-15 (before reinclusion equivalent)
"""
from __future__ import annotations

import csv
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'control_group'
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

PERIODS = [
    {'slug': 'p1_equivalent', 'label': 'P1 equivalent (Nov 2023 - Apr 2024)',
     'start': date(2023, 11, 9), 'end': date(2024, 4, 25)},
    {'slug': 'p2_equivalent', 'label': 'P2 equivalent (Jul 2025 - Dec 2025)',
     'start': date(2025, 7, 1), 'end': date(2025, 12, 15)},
]

SITEMAP_INDEX = 'https://suspilne.media/suspilne/sitemap/sitemap.xml'

# Reuse Ukrinform's source detection logic
REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала',
    'наголосив', 'наголосила', 'зауважив', 'зауважила', 'додав', 'додала',
    'підкреслив', 'підкреслила', 'відзначив', 'відзначила', 'розповів',
    'розповіла', 'написав', 'написала', 'зазначив', 'зазначила'
)
PERSON_SOURCE_RE = re.compile(
    r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b'
)
LEADING_SOURCE_RE = re.compile(
    r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|'
    r'Як зазначив|Як зазначила|Повідомляє)\s+([^,.;:\n]{1,90})'
)
OFFICIAL_MARKERS = [
    'zelensk', 'prezident', 'ofis-prezidenta', 'opu', 'yermak', 'ermak',
    'kabmin', 'uryad', 'smygal', 'premyer', 'verhovn', 'rada', 'nardep',
    'ministr', 'ministerstvo', 'mzs', 'minoboroni', 'mvs',
    'genshtab', 'zsu', 'sbu', 'gur', 'dpsu', 'dsns', 'sili-oboroni',
    'ova', 'kmda', 'oblrada', 'miskrada', 'mer',
]


def make_session():
    s = requests.Session()
    s.headers['User-Agent'] = USER_AGENT
    return s


def fetch_sitemap_index(session):
    """Get all post-sitemap URLs from the index."""
    resp = session.get(SITEMAP_INDEX, timeout=15)
    root = ET.fromstring(resp.text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = []
    for sitemap in root.findall('sm:sitemap', ns):
        loc = sitemap.findtext('sm:loc', default='', namespaces=ns).strip()
        if 'post-sitemap' in loc:
            urls.append(loc)
    return urls


def parse_sitemap(session, url):
    """Parse a single sitemap file and return URLs with dates."""
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        items = []
        for url_el in root.findall('sm:url', ns):
            loc = url_el.findtext('sm:loc', default='', namespaces=ns).strip()
            lastmod = url_el.findtext('sm:lastmod', default='', namespaces=ns).strip()
            if loc and lastmod:
                items.append({'loc': loc, 'lastmod': lastmod})
        return items
    except Exception as e:
        print(f"  Error parsing {url}: {e}")
        return []


def normalize_entity(text):
    cleaned = re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip(' ,;:.!?"""«»()[]')
    return cleaned if len(cleaned.split()) <= 10 else ''


def extract_sources(text):
    candidates = []
    for raw in PERSON_SOURCE_RE.findall(text):
        e = normalize_entity(raw)
        if e: candidates.append(e)
    for raw in LEADING_SOURCE_RE.findall(text):
        e = normalize_entity(raw)
        if e: candidates.append(e)
    seen = set()
    deduped = []
    for e in candidates:
        k = e.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(e)
    official = sum(1 for e in deduped if any(m in e.lower() for m in OFFICIAL_MARKERS))
    return len(deduped), official, max(len(deduped) - official, 0)


def is_official_url(url):
    slug = url.rstrip('/').split('/')[-1].lower()
    return any(m in slug for m in OFFICIAL_MARKERS)


def parse_article(session, url):
    """Fetch and parse a single article."""
    try:
        resp = session.get(url, timeout=12)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = ''
        og = soup.find('meta', attrs={'property': 'og:title'})
        if og and og.get('content'):
            title = og['content'].strip()
        body = soup.select_one('div.c-article-content') or soup.select_one('article') or soup.find('main')
        text = ''
        if body:
            paragraphs = [p.get_text(' ', strip=True) for p in body.find_all('p') if p.get_text(' ', strip=True)]
            text = '\n'.join(paragraphs)
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            return None
        sc, oc, noc = extract_sources(text)
        official = is_official_url(url)
        return {
            'title': title,
            'source_count': sc,
            'official_source_count': oc,
            'non_official_source_count': noc,
            'likely_parket': official and sc <= 1 and noc == 0,
            'balance_risk': official and noc == 0 and sc <= 1,
        }
    except Exception:
        return None


def main():
    print("=" * 60)
    print("COLLECTING SUSPILNE NOVYNY DATA")
    print("=" * 60)

    session = make_session()

    # Step 1: Get all sitemap URLs
    print("\nFetching sitemap index...")
    sitemap_urls = fetch_sitemap_index(session)
    print(f"Found {len(sitemap_urls)} post-sitemap files")

    # Step 2: Collect all URLs from sitemaps
    all_items = []
    for i, smap_url in enumerate(sitemap_urls):
        print(f"  Parsing {i+1}/{len(sitemap_urls)}: {smap_url.split('/')[-1]}")
        items = parse_sitemap(session, smap_url)
        all_items.extend(items)
        time.sleep(0.3)

    print(f"\nTotal URLs from sitemaps: {len(all_items):,}")

    # Step 3: Filter by periods
    records = []
    for item in all_items:
        try:
            d = date.fromisoformat(item['lastmod'][:10])
        except ValueError:
            continue
        for period in PERIODS:
            if period['start'] <= d <= period['end']:
                records.append({
                    'period': period['slug'],
                    'url': item['loc'],
                    'date': d.isoformat(),
                    'month': d.strftime('%Y-%m'),
                })
                break

    print(f"In study periods: {len(records):,}")
    for period in PERIODS:
        n = sum(1 for r in records if r['period'] == period['slug'])
        print(f"  {period['slug']}: {n:,}")

    # Step 4: Audit sample (first 2000 per period for speed, or all if less)
    SAMPLE_SIZE = 2000
    to_audit = []
    for period in PERIODS:
        period_records = [r for r in records if r['period'] == period['slug']]
        sample = period_records[:SAMPLE_SIZE]
        to_audit.extend(sample)

    print(f"\nAuditing {len(to_audit):,} articles (HTML parsing)...")

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(parse_article, session, r['url']): r for r in to_audit}
        done = 0
        for future in as_completed(futures):
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(to_audit)}")
            rec = futures[future]
            parsed = future.result()
            if parsed:
                rec.update(parsed)
                rec['audited'] = True
                results.append(rec)
            else:
                rec['audited'] = False
                results.append(rec)

    # Step 5: Save and report
    output_path = DATA_DIR / 'suspilne_study.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    audited = [r for r in results if r.get('audited')]
    print(f"\n{'=' * 60}")
    print(f"SUSPILNE RESULTS")
    print(f"Total collected: {len(records):,}")
    print(f"Audited: {len(audited):,}")

    for period in PERIODS:
        pa = [r for r in audited if r['period'] == period['slug']]
        pk = sum(1 for r in pa if r.get('likely_parket'))
        br = sum(1 for r in pa if r.get('balance_risk'))
        avg_src = sum(r.get('source_count', 0) for r in pa) / len(pa) if pa else 0
        print(f"\n  {period['slug']}:")
        print(f"    Audited: {len(pa):,}")
        print(f"    Parket: {pk} ({pk/len(pa)*100:.2f}%)" if pa else "    Parket: N/A")
        print(f"    Balance risk: {br} ({br/len(pa)*100:.2f}%)" if pa else "    Balance: N/A")
        print(f"    Avg sources: {avg_src:.2f}")

    print(f"\nSaved: {output_path}")


if __name__ == '__main__':
    main()
