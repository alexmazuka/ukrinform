"""
Full audit of Suspilne articles — parse ALL collected URLs.
Slower but reliable: 5 workers, retry on failure.
"""
from __future__ import annotations
import json, re, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup

DATA = Path(__file__).resolve().parent.parent / 'data' / 'control_group'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'

REPORTING_VERBS = (
    'заявив','заявила','повідомив','повідомила','сказав','сказала',
    'наголосив','наголосила','зауважив','зауважила','додав','додала',
    'підкреслив','підкреслила','відзначив','відзначила','розповів',
    'розповіла','написав','написала','зазначив','зазначила'
)
PERSON_RE = re.compile(r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b')
LEADING_RE = re.compile(r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|Як зазначив|Як зазначила|Повідомляє)\s+([^,.;:\n]{1,90})')
OFFICIAL = ['zelensk','prezident','ofis-prezidenta','opu','kabmin','uryad','smygal','verhovn','rada','ministr','mzs','minoboroni','genshtab','zsu','sbu','gur','ova','kmda']

def normalize(t):
    c = re.sub(r'\s+', ' ', t.replace('\xa0', ' ')).strip(' ,;:.!?"""«»()[]')
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

def is_official(url):
    slug = url.rstrip('/').split('/')[-1].lower()
    return any(m in slug for m in OFFICIAL)

def parse_one(url):
    sess = requests.Session()
    sess.headers['User-Agent'] = UA
    for attempt in range(2):
        try:
            r = sess.get(url, timeout=15)
            if r.status_code != 200: return None
            soup = BeautifulSoup(r.text, 'html.parser')
            title_tag = soup.find('meta', attrs={'property': 'og:title'})
            title = title_tag['content'].strip() if title_tag and title_tag.get('content') else ''
            body = soup.select_one('div.c-article-content') or soup.select_one('article')
            if not body: return None
            text = ' '.join(p.get_text(' ', strip=True) for p in body.find_all('p') if p.get_text(' ', strip=True))
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) < 30: return None
            sc, oc, noc = extract_sources(text)
            off = is_official(url)
            return {'title': title, 'sc': sc, 'oc': oc, 'noc': noc,
                    'parket': off and sc <= 1 and noc == 0,
                    'balance': off and noc == 0 and sc <= 1}
        except:
            if attempt == 0: time.sleep(1)
    return None

def main():
    data = json.load(open(DATA / 'suspilne_study.json'))
    not_audited = [d for d in data if not d.get('audited')]
    already_ok = [d for d in data if d.get('audited')]

    print(f"Suspilne: {len(data)} total, {len(already_ok)} already audited, {len(not_audited)} to process")

    results = list(already_ok)  # Keep already parsed

    BATCH = 200
    for batch_start in range(0, len(not_audited), BATCH):
        batch = not_audited[batch_start:batch_start + BATCH]
        batch_num = batch_start // BATCH + 1
        total_batches = (len(not_audited) + BATCH - 1) // BATCH
        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} articles)")

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(parse_one, r['url']): r for r in batch}
            done = 0
            for f in as_completed(futures):
                done += 1
                rec = futures[f]
                parsed = f.result()
                if parsed:
                    rec.update(parsed)
                    rec['audited'] = True
                else:
                    rec['audited'] = False
                results.append(rec)
                if done % 100 == 0:
                    print(f"  {done}/{len(batch)}")

        # Save after each batch
        with open(DATA / 'suspilne_study.json', 'w', encoding='utf-8') as fp:
            json.dump(results, fp, ensure_ascii=False, indent=2)

        audited_now = sum(1 for r in results if r.get('audited'))
        print(f"  Saved. Total audited: {audited_now}")
        time.sleep(1)

    # Final report
    audited = [r for r in results if r.get('audited')]
    pk = sum(1 for r in audited if r.get('parket'))
    br = sum(1 for r in audited if r.get('balance'))
    avg_sc = sum(r.get('sc', 0) for r in audited) / len(audited) if audited else 0

    print(f"\n{'='*50}")
    print(f"SUSPILNE FULL AUDIT COMPLETE")
    print(f"Total: {len(results)}, Audited: {len(audited)}")
    print(f"Parket: {pk} ({pk/len(audited)*100:.2f}%)" if audited else "N/A")
    print(f"Balance risk: {br} ({br/len(audited)*100:.2f}%)" if audited else "N/A")
    print(f"Avg sources: {avg_sc:.2f}")

if __name__ == '__main__':
    main()
