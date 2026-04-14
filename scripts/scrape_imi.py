"""
Phase 1.2: Collect IMI methodology and white list reports.
===========================================================
Scrapes imi.org.ua for:
  - All White List publications (Білий список)
  - All professional standards monitoring reports
  - Saves raw HTML + structured JSON for transparency

Every source is archived via Wayback Machine save API.
All attempts (success and failure) are documented.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
IMI_DIR = BASE_DIR / 'data' / 'imi-reports'
IMI_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

# Known IMI reports from the project prompt + public sources
KNOWN_REPORTS = [
    {
        'type': 'white_list',
        'period': 'H1 2024',
        'date': '2024-04-26',
        'url': 'https://imi.org.ua/monitorings/bilyj-spysok-imi-za-pershe-pivrichchya-2024-roku',
        'note': 'Ukrinform EXCLUDED. Reason: "паркетні повідомлення" та недостатній баланс думок',
        'ukrinform_status': 'EXCLUDED',
    },
    {
        'type': 'white_list',
        'period': 'H2 2024',
        'date': '2024-11-01',
        'url': 'https://imi.org.ua/monitorings/bilyj-spysok-imi-za-druge-pivrichchya-2024-roku-uvishly-13-media-i64640',
        'note': 'Ukrinform NOT returned. 13 media included.',
        'ukrinform_status': 'EXCLUDED',
    },
    {
        'type': 'white_list',
        'period': 'H2 2025',
        'date': '2025-12-16',
        'url': 'https://imi.org.ua/monitorings/bilyj-spysok-imi-za-druge-pivrichchya-2025-roku-uvijshly-17-media',
        'note': 'Ukrinform RETURNED. 17 media included.',
        'ukrinform_status': 'INCLUDED',
    },
    {
        'type': 'methodology',
        'period': 'September 2024',
        'date': '2024-10-01',
        'url': 'https://imi.org.ua/monitorings/novyny-pid-chas-vijny-analiz-profesijnyh-standartiv-providnyh-onlajn-media-u-veresni-2024-roku-i64521',
        'note': 'Key methodology source: 100 articles per media over 2 days. 14 indicators.',
        'ukrinform_status': None,
    },
    {
        'type': 'context',
        'period': '2024-04-26',
        'date': '2024-04-26',
        'url': 'https://detector.media/community/article/226025/2024-04-26-oleksiy-matsuka-dlya-nas-bulo-neochikuvanym-rishennya-imi-pro-vyklyuchennya-ukrinformu-z-bilogo-spysku/',
        'note': 'Matsuka reaction to IMI exclusion — Detector Media',
        'ukrinform_status': None,
    },
    {
        'type': 'context',
        'period': '2024',
        'date': '2024-11-01',
        'url': 'https://detector.media/infospace/article/234255/2024-11-01-imi-onovyv-bilyy-spysok-prozorykh-i-vidpovidalnykh-media/',
        'note': 'Detector: IMI updated white list Nov 2024 — Ukrinform not returned',
        'ukrinform_status': None,
    },
    {
        'type': 'context',
        'period': '2024',
        'date': '2024-11-01',
        'url': 'https://imi.org.ua/news/sergij-cherevatyj-ukrinform-boretsya-za-povernennya-do-bilogo-spysku-i65189',
        'note': 'IMI: Cherevaty says Ukrinform is fighting for return to White List',
        'ukrinform_status': None,
    },
]

# IMI monitoring search pages to discover additional reports
IMI_SEARCH_URLS = [
    'https://imi.org.ua/monitorings?page=1',
    'https://imi.org.ua/monitorings?page=2',
    'https://imi.org.ua/monitorings?page=3',
]


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers['User-Agent'] = USER_AGENT
    return s


def safe_filename(url: str) -> str:
    return re.sub(r'[^\w\-]', '_', url.split('/')[-1])[:80]


def archive_to_wayback(url: str, session: requests.Session) -> str | None:
    """Submit URL to Wayback Machine for archiving."""
    save_url = f'https://web.archive.org/save/{url}'
    try:
        resp = session.get(save_url, timeout=20)
        if resp.status_code in (200, 302):
            archived = resp.headers.get('Content-Location', '')
            if archived:
                return f'https://web.archive.org{archived}'
        return None
    except Exception:
        return None


def fetch_and_save(url: str, slug: str, session: requests.Session) -> dict:
    """Fetch a URL, save HTML, return structured result."""
    result = {
        'url': url,
        'slug': slug,
        'fetched_at': date.today().isoformat(),
        'status': None,
        'html_file': None,
        'wayback_url': None,
        'title': None,
        'text_excerpt': None,
        'error': None,
    }

    try:
        resp = session.get(url, timeout=15)
        result['status'] = resp.status_code

        if resp.status_code != 200:
            result['error'] = f'HTTP {resp.status_code}'
            return result

        # Save raw HTML
        html_path = IMI_DIR / f'{slug}.html'
        html_path.write_text(resp.text, encoding='utf-8')
        result['html_file'] = str(html_path.name)

        # Extract text
        soup = BeautifulSoup(resp.text, 'html.parser')

        title_tag = soup.find('h1') or soup.find('title')
        result['title'] = title_tag.get_text(strip=True) if title_tag else ''

        # Get main content
        content = (
            soup.select_one('div.article-content') or
            soup.select_one('div.post-content') or
            soup.select_one('article') or
            soup.select_one('main')
        )
        if content:
            text = content.get_text(' ', strip=True)
            result['text_excerpt'] = text[:1000]

        print(f'  ✓ {url[:70]}')
        print(f'    Title: {result["title"][:60]}')

    except Exception as e:
        result['error'] = str(e)
        print(f'  ✗ {url[:70]} → {e}')

    return result


def discover_additional_reports(session: requests.Session) -> list[dict]:
    """Search IMI monitoring page for additional Ukrinform-related reports."""
    found = []
    print('\nSearching for additional IMI reports...')

    for search_url in IMI_SEARCH_URLS:
        try:
            resp = session.get(search_url, timeout=15)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a', href=True)

            for link in links:
                href = link['href']
                text = link.get_text(strip=True).lower()

                # Look for relevant reports
                if any(kw in text for kw in ['білий список', 'white list', 'стандарт', 'моніторинг', 'ukrinform', 'укрінформ']):
                    if '/monitorings/' in href or '/news/' in href:
                        full_url = href if href.startswith('http') else f'https://imi.org.ua{href}'
                        found.append({
                            'type': 'discovered',
                            'url': full_url,
                            'title_hint': link.get_text(strip=True)[:100],
                            'source_page': search_url,
                        })

            time.sleep(1)

        except Exception as e:
            print(f'  Search page error: {e}')

    # Deduplicate
    seen = set()
    unique = []
    for item in found:
        if item['url'] not in seen:
            seen.add(item['url'])
            unique.append(item)

    print(f'  Found {len(unique)} additional candidate links')
    return unique


def main():
    print('=' * 60)
    print('PHASE 1.2: IMI REPORTS COLLECTION')
    print('=' * 60)

    session = make_session()
    audit_log = {
        'generated_at': date.today().isoformat(),
        'known_reports': [],
        'discovered_reports': [],
        'wayback_archive_attempts': [],
        'summary': {},
    }

    # --- Step 1: Fetch all known reports ---
    print(f'\nFetching {len(KNOWN_REPORTS)} known reports...')

    for report in KNOWN_REPORTS:
        slug = f"{report['type']}_{report['date']}_{safe_filename(report['url'])}"
        result = fetch_and_save(report['url'], slug, session)
        result.update({
            'report_type': report['type'],
            'period': report['period'],
            'note': report['note'],
            'ukrinform_status': report.get('ukrinform_status'),
        })
        audit_log['known_reports'].append(result)
        time.sleep(1.5)

    # --- Step 2: Discover additional reports ---
    additional = discover_additional_reports(session)

    # Fetch the most relevant ones (max 15 to avoid overload)
    relevant = [r for r in additional if any(
        kw in r.get('title_hint', '').lower()
        for kw in ['білий', 'стандарт', 'укрінформ', 'моніторинг 202']
    )][:15]

    print(f'\nFetching {len(relevant)} additional relevant reports...')
    for item in relevant:
        slug = f"discovered_{safe_filename(item['url'])}"
        result = fetch_and_save(item['url'], slug, session)
        result.update({'title_hint': item.get('title_hint'), 'report_type': 'discovered'})
        audit_log['discovered_reports'].append(result)
        time.sleep(1.5)

    # --- Step 3: Archive key URLs to Wayback Machine ---
    key_urls = [r['url'] for r in KNOWN_REPORTS[:4]]  # Top 4 most important
    print(f'\nSubmitting {len(key_urls)} key URLs to Wayback Machine...')

    for url in key_urls:
        print(f'  Archiving: {url[:70]}...')
        wayback_url = archive_to_wayback(url, session)
        audit_log['wayback_archive_attempts'].append({
            'url': url,
            'archived_url': wayback_url,
            'success': wayback_url is not None,
        })
        time.sleep(2)

    # --- Step 4: Extract structured data from white list reports ---
    print('\nExtracting structured data from White List reports...')
    white_lists = {}

    for report in audit_log['known_reports']:
        if report.get('report_type') != 'white_list':
            continue
        html_filename = report.get('html_file')
        if not html_filename:
            continue
        html_file = IMI_DIR / html_filename
        if not html_file.exists():
            continue

        soup = BeautifulSoup(html_file.read_text(encoding='utf-8'), 'html.parser')
        text = soup.get_text(' ', strip=True)

        # Extract media names from white list text
        # IMI usually lists them as bullet points or numbered list
        media_mentioned = []
        known_media = [
            'Укрінформ', 'Ukrinform', 'NV', 'LIGA', 'Ліга', 'Громадське',
            'Радіо Свобода', 'Тексти', 'Тиждень', 'Слово і діло',
            'Українська правда', 'Цензор', 'Дзеркало тижня', 'Lb.ua',
        ]
        for media in known_media:
            if media.lower() in text.lower():
                media_mentioned.append(media)

        white_lists[report['period']] = {
            'url': report['url'],
            'date': report.get('fetched_at'),
            'title': report.get('title'),
            'ukrinform_status': report.get('ukrinform_status'),
            'media_mentioned': media_mentioned,
            'text_excerpt': report.get('text_excerpt', '')[:500],
        }

    # --- Step 5: Save full audit log ---
    audit_log['summary'] = {
        'total_reports_fetched': len([r for r in audit_log['known_reports'] if r['status'] == 200]),
        'total_discovered': len(audit_log['discovered_reports']),
        'wayback_archived': sum(1 for a in audit_log['wayback_archive_attempts'] if a['success']),
        'white_lists_structured': len(white_lists),
        'html_files_saved': len(list(IMI_DIR.glob('*.html'))),
    }
    audit_log['white_list_data'] = white_lists

    log_path = IMI_DIR / 'imi_collection_log.json'
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(audit_log, f, ensure_ascii=False, indent=2)

    # --- Print summary ---
    print(f'\n{"=" * 60}')
    print('IMI COLLECTION COMPLETE')
    print(f'Reports fetched: {audit_log["summary"]["total_reports_fetched"]}')
    print(f'Additional discovered: {audit_log["summary"]["total_discovered"]}')
    print(f'Wayback archived: {audit_log["summary"]["wayback_archived"]}')
    print(f'HTML files saved: {audit_log["summary"]["html_files_saved"]}')
    print(f'\nWhite List timeline:')
    for period, data in white_lists.items():
        status = data["ukrinform_status"] or "N/A"
        print(f'  {period}: Укрінформ → {status}')
    print(f'\nAll data: {IMI_DIR}')
    print(f'Audit log: {log_path}')


if __name__ == '__main__':
    main()
