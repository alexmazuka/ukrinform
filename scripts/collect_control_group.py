"""
Collect control group data: Suspilne + Ukrainska Pravda.
=========================================================
Same methodology and periods as Ukrinform study.
Suspilne: via sitemap (post-sitemap0..20.xml)
UP: via archive page scraping (pravda.com.ua/news/YYYY/MM/DD/)

Periods:
  P1: 2023-11-09 → 2024-04-25
  P2: 2025-07-01 → 2025-12-15
"""
from __future__ import annotations

import csv
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'control_group'
DATA_DIR.mkdir(parents=True, exist_ok=True)

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'

P1_START, P1_END = date(2023, 11, 9), date(2024, 4, 25)
P2_START, P2_END = date(2025, 7, 1), date(2025, 12, 15)

REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала',
    'наголосив', 'наголосила', 'зауважив', 'зауважила', 'додав', 'додала',
    'підкреслив', 'підкреслила', 'відзначив', 'відзначила', 'розповів',
    'розповіла', 'написав', 'написала', 'зазначив', 'зазначила'
)
PERSON_RE = re.compile(r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b')
LEADING_RE = re.compile(r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|Як зазначив|Як зазначила|Повідомляє)\s+([^,.;:\n]{1,90})')
OFFICIAL = ['zelensk','prezident','ofis-prezidenta','opu','kabmin','uryad','smygal','verhovn','rada','ministr','mzs','minoboroni','genshtab','zsu','sbu','gur','ova','kmda']


def session():
    s = requests.Session()
    s.headers['User-Agent'] = UA
    return s


def normalize(text):
    c = re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip(' ,;:.!?"""«»()[]')
    return c if len(c.split()) <= 10 else ''


def extract_sources(text):
    cands = []
    for raw in PERSON_RE.findall(text):
        e = normalize(raw)
        if e: cands.append(e)
    for raw in LEADING_RE.findall(text):
        e = normalize(raw)
        if e: cands.append(e)
    seen, deduped = set(), []
    for e in cands:
        k = e.lower()
        if k not in seen: seen.add(k); deduped.append(e)
    official = sum(1 for e in deduped if any(m in e.lower() for m in OFFICIAL))
    return len(deduped), official, max(len(deduped) - official, 0)


def is_official_url(url):
    slug = url.rstrip('/').split('/')[-1].lower()
    return any(m in slug for m in OFFICIAL)


def in_period(d):
    if P1_START <= d <= P1_END: return 'p1'
    if P2_START <= d <= P2_END: return 'p2'
    return None


# ============================================================
# SUSPILNE: sitemap-based collection
# ============================================================
def collect_suspilne(sess):
    print("\n" + "=" * 50)
    print("SUSPILNE NOVYNY")
    print("=" * 50)

    # Fetch sitemap index
    resp = sess.get('https://suspilne.media/suspilne/sitemap/sitemap.xml', timeout=15)
    root = ET.fromstring(resp.text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    smap_urls = [s.findtext('sm:loc', '', ns).strip() for s in root.findall('sm:sitemap', ns) if 'post-sitemap' in s.findtext('sm:loc', '', ns)]
    print(f"Found {len(smap_urls)} post-sitemaps")

    # Parse all sitemaps
    urls_by_period = defaultdict(list)
    for i, smap in enumerate(smap_urls):
        print(f"  {i+1}/{len(smap_urls)}: {smap.split('/')[-1]}", end="")
        try:
            r = sess.get(smap, timeout=20)
            items = ET.fromstring(r.text).findall('sm:url', {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'})
            count = 0
            for item in items:
                loc = item.findtext('{http://www.sitemaps.org/schemas/sitemap/0.9}loc', '').strip()
                lastmod = item.findtext('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod', '').strip()
                if not loc or not lastmod: continue
                try:
                    d = date.fromisoformat(lastmod[:10])
                except: continue
                p = in_period(d)
                if p:
                    urls_by_period[p].append({'url': loc, 'date': d.isoformat()})
                    count += 1
            print(f" → {count} in scope")
        except Exception as e:
            print(f" → ERROR: {e}")
        time.sleep(0.3)

    total = sum(len(v) for v in urls_by_period.values())
    print(f"\nTotal Suspilne in scope: {total} (P1: {len(urls_by_period.get('p1',[]))}, P2: {len(urls_by_period.get('p2',[]))})")
    return urls_by_period


def parse_suspilne(sess, url):
    try:
        r = sess.get(url, timeout=12)
        if r.status_code != 200: return None
        soup = BeautifulSoup(r.text, 'html.parser')
        title_tag = soup.find('meta', attrs={'property': 'og:title'})
        title = title_tag['content'].strip() if title_tag and title_tag.get('content') else ''
        body = soup.select_one('div.c-article-content') or soup.select_one('article') or soup.find('main')
        if not body: return None
        text = ' '.join(p.get_text(' ', strip=True) for p in body.find_all('p') if p.get_text(' ', strip=True))
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 50: return None
        sc, oc, noc = extract_sources(text)
        off = is_official_url(url)
        return {'title': title, 'sc': sc, 'oc': oc, 'noc': noc,
                'parket': off and sc <= 1 and noc == 0,
                'balance': off and noc == 0 and sc <= 1}
    except: return None


# ============================================================
# UKRAINSKA PRAVDA: date-based page scraping
# ============================================================
def collect_up(sess):
    print("\n" + "=" * 50)
    print("UKRAINSKA PRAVDA")
    print("=" * 50)

    urls_by_period = defaultdict(list)

    for p_name, start, end in [('p1', P1_START, P1_END), ('p2', P2_START, P2_END)]:
        d = start
        day_count = 0
        while d <= end:
            url = f"https://www.pravda.com.ua/news/date_{d.strftime('%d%m%Y')}/"
            try:
                r = sess.get(url, timeout=15)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    links = soup.select('div.article_header a[href*="/news/"]')
                    if not links:
                        links = soup.select('a[href*="/news/20"]')
                    for a in links:
                        href = a.get('href', '')
                        if href and '/news/20' in href:
                            full = href if href.startswith('http') else f"https://www.pravda.com.ua{href}"
                            urls_by_period[p_name].append({'url': full, 'date': d.isoformat()})
                    day_count += 1
                    if day_count % 14 == 0:
                        print(f"  {p_name}: {d} → {len(urls_by_period[p_name])} URLs so far")
            except: pass
            d += timedelta(days=7)  # Sample every 7th day for speed
            time.sleep(0.5)

    total = sum(len(v) for v in urls_by_period.values())
    print(f"\nTotal UP sampled: {total} (P1: {len(urls_by_period.get('p1',[]))}, P2: {len(urls_by_period.get('p2',[]))})")
    return urls_by_period


def parse_up(sess, url):
    try:
        r = sess.get(url, timeout=12)
        if r.status_code != 200: return None
        soup = BeautifulSoup(r.text, 'html.parser')
        title_tag = soup.find('meta', attrs={'property': 'og:title'})
        title = title_tag['content'].strip() if title_tag and title_tag.get('content') else ''
        body = soup.select_one('div.post_text') or soup.select_one('div.post__text') or soup.select_one('article')
        if not body: return None
        text = ' '.join(p.get_text(' ', strip=True) for p in body.find_all('p') if p.get_text(' ', strip=True))
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 50: return None
        sc, oc, noc = extract_sources(text)
        off = is_official_url(url)
        return {'title': title, 'sc': sc, 'oc': oc, 'noc': noc,
                'parket': off and sc <= 1 and noc == 0,
                'balance': off and noc == 0 and sc <= 1}
    except: return None


# ============================================================
# AUDIT: parse articles in parallel
# ============================================================
def audit_batch(sess, records, parser_fn, label, max_articles=3000):
    sample = records[:max_articles]
    print(f"\n  Auditing {len(sample)} {label} articles...")
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(parser_fn, sess, r['url']): r for r in sample}
        done = 0
        for f in as_completed(futures):
            done += 1
            if done % 200 == 0: print(f"    {done}/{len(sample)}")
            rec = futures[f]
            parsed = f.result()
            if parsed:
                rec.update(parsed)
                rec['audited'] = True
            else:
                rec['audited'] = False
            results.append(rec)
    return results


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("CONTROL GROUP COLLECTION: Suspilne + UP")
    print("=" * 60)

    sess = session()

    # Collect URLs
    susp_urls = collect_suspilne(sess)
    up_urls = collect_up(sess)

    # Audit
    all_results = {'suspilne': {}, 'up': {}}

    for p in ['p1', 'p2']:
        susp = susp_urls.get(p, [])
        if susp:
            results = audit_batch(sess, susp, parse_suspilne, f"Suspilne {p}")
            all_results['suspilne'][p] = results

        up = up_urls.get(p, [])
        if up:
            results = audit_batch(sess, up, parse_up, f"UP {p}")
            all_results['up'][p] = results

    # Save
    for media in ['suspilne', 'up']:
        flat = []
        for p, records in all_results[media].items():
            for r in records:
                r['period'] = p
                r['media'] = media
                flat.append(r)
        path = DATA_DIR / f'{media}_study.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(flat, f, ensure_ascii=False, indent=2)

    # Report
    print(f"\n{'=' * 60}")
    print("CONTROL GROUP RESULTS")
    print(f"{'=' * 60}")

    for media in ['suspilne', 'up']:
        print(f"\n  {media.upper()}:")
        for p in ['p1', 'p2']:
            records = all_results[media].get(p, [])
            audited = [r for r in records if r.get('audited')]
            pk = sum(1 for r in audited if r.get('parket'))
            br = sum(1 for r in audited if r.get('balance'))
            avg_sc = sum(r.get('sc', 0) for r in audited) / len(audited) if audited else 0
            pct = f"{pk/len(audited)*100:.2f}%" if audited else "N/A"
            print(f"    {p}: collected={len(records)}, audited={len(audited)}, parket={pk} ({pct}), avg_src={avg_sc:.2f}")


if __name__ == '__main__':
    main()
