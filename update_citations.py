#!/usr/bin/env python3
"""
Fetch papers that cited the user's publications.

Strategy (in order, results merged and deduplicated):
  1. OpenCitations COCI API  — confirmed citation index (may lag ~weeks)
  2. Crossref journal scan   — scan ALL recent papers from key seismo journals,
                               check each reference list for our fingerprints
                               (catches papers immediately after deposit)
  3. scholarly (fallback)    — Google Scholar "Cited by" list
"""

import json
import os
import time
import urllib.parse
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── proxy bypass ────────────────────────────────────────────────────────────
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

session = requests.Session()
session.trust_env = False
_retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=_retry))
session.mount('http://', HTTPAdapter(max_retries=_retry))

OUTPUT_FILE = 'data_citations.json'

# ── your publications ────────────────────────────────────────────────────────
# Add all your papers here.  fingerprints = distinctive text snippets that
# appear literally in citation records (journal article ID, short title, etc.)
MY_PAPERS = [
    {
        'title': (
            'Generation mechanism of the 26 s and 28 s tremors in the Gulf of Guinea '
            'from statistical analysis of magnitudes and event intervals'
        ),
        'doi': '10.1016/j.epsl.2021.117334',
        'fingerprints': [
            '10.1016/j.epsl.2021.117334',   # DOI string
            'j.epsl.2021.117334',            # shorter DOI form
            '26 s and 28 s tremors in the gulf',
            '26 s and 28 s tremors of the gulf',
            'epsl.2021.117334',
        ],
    },
    # ── add more papers here ──────────────────────────────────────────────
    # {
    #     'title': 'Your next paper title',
    #     'doi': '10.xxxx/xxxxxxx',
    #     'fingerprints': ['10.xxxx/xxxxxxx', 'short distinctive phrase'],
    # },
]

# ── manually known citing papers ─────────────────────────────────────────────
# If you know a specific paper's DOI that cites your work, add it here.
# These are always fetched directly and will appear immediately.
# Format: {'doi': '10.xxx/xxx', 'cited_paper_doi': '10.yyy/yyy'}
KNOWN_CITING_DOIS = [
    {
        'doi': '10.1038/s41467-026-71541-6',  # Poli et al. 2026, Nat Comms
        'cited_paper_doi': '10.1016/j.epsl.2021.117334',
    },
]

# Seismology / geophysics journals to scan in Crossref
SEISMO_JOURNALS = [
    'Nature',
    'Science',
    'Nature Geoscience',
    'Nature Communications',
    'Science Advances',
    'Geophysical Research Letters',
    'Journal of Geophysical Research: Solid Earth',
    'Earth and Planetary Science Letters',
    'Geophysical Journal International',
    'Seismological Research Letters',
    'Bulletin of the Seismological Society of America',
    'Journal of Seismology',
    'Tectonophysics',
    'Solid Earth',
    'Communications Earth & Environment',
]

# How far back to scan (days) — use 30 to catch papers with indexing lag
SCAN_DAYS = 30


# ── helpers ──────────────────────────────────────────────────────────────────

def _ref_text(ref: dict) -> str:
    return (
        ref.get('DOI', '') + ' ' +
        ref.get('unstructured', '') + ' ' +
        ref.get('article-title', '')
    ).lower()


def _ref_matches(ref: dict, paper: dict) -> bool:
    text = _ref_text(ref)
    for fp in paper['fingerprints']:
        if fp.lower() in text:
            return True
    return False


def _make_entry(item: dict, paper: dict, source_tag: str) -> dict:
    authors = item.get('author', [])
    first_author = (
        f"{authors[0].get('given', '')} {authors[0].get('family', '')}".strip()
        if authors else 'N/A'
    )
    corr_author = (
        f"{authors[-1].get('given', '')} {authors[-1].get('family', '')}".strip()
        if len(authors) > 1 else first_author
    )
    doi = item.get('DOI', '')
    date_parts = (
        item.get('issued', item.get('created', {}))
        .get('date-parts', [[datetime.now().year]])
    )
    published = '-'.join(str(p) for p in date_parts[0]) if date_parts and date_parts[0] else str(datetime.now().year)
    return {
        'id': doi,
        'title': (item.get('title') or ['No Title'])[0],
        'url': f'https://doi.org/{doi}' if doi else '',
        'first_author': first_author,
        'corr_author': corr_author,
        'affiliation': (
            authors[0].get('affiliation', [{}])[0].get('name', 'N/A')
            if authors and authors[0].get('affiliation') else 'N/A'
        ),
        'abs_zh': f'This paper cited: {paper["title"]}',
        'source': (item.get('container-title') or ['Unknown'])[0],
        'published': published,
        'cited_paper': paper['title'],
        '_source_tag': source_tag,
    }


def fetch_known_citing_dois() -> list:
    """Directly fetch metadata for manually-known citing papers."""
    results = []
    paper_map = {p['doi'].lower(): p for p in MY_PAPERS}

    for entry in KNOWN_CITING_DOIS:
        doi = entry.get('doi', '')
        cited_doi = entry.get('cited_paper_doi', '').lower()
        paper = paper_map.get(cited_doi)
        if not doi or not paper:
            continue
        try:
            url = f'https://api.crossref.org/works/{doi}'
            meta = session.get(url, timeout=15).json().get('message', {})
            entry_data = _make_entry(meta, paper, 'known')
            results.append(entry_data)
            print(f'  [Known] Fetched: {entry_data["title"][:70]}')
        except Exception as e:
            print(f'  [Known] Error fetching {doi}: {e}')
    return results


# ── Strategy 1: OpenCitations ────────────────────────────────────────────────

def fetch_opencitations(paper: dict) -> list:
    """Query OpenCitations COCI for confirmed citations of a DOI."""
    results = []
    doi = paper.get('doi', '')
    if not doi:
        return results
    url = f'https://opencitations.net/index/coci/api/v1/citations/{doi}'
    try:
        r = session.get(url, timeout=20, headers={'Accept': 'application/json'})
        if r.status_code != 200:
            return results
        citations = r.json()
        print(f'  [OpenCitations] {len(citations)} citation(s) found for {doi}')
        for cit in citations:
            citing_doi = cit.get('citing', '')
            if not citing_doi:
                continue
            # Fetch metadata for the citing paper
            meta_url = f'https://api.crossref.org/works/{citing_doi}?select=DOI,title,author,container-title,issued,created'
            try:
                meta = session.get(meta_url, timeout=15).json().get('message', {})
                entry = _make_entry(meta, paper, 'OpenCitations')
                results.append(entry)
                print(f'    -> {entry["title"][:70]}')
            except Exception as e:
                print(f'    Metadata fetch error for {citing_doi}: {e}')
                # Still add a minimal entry
                results.append({
                    'id': citing_doi,
                    'title': citing_doi,
                    'url': f'https://doi.org/{citing_doi}',
                    'first_author': 'N/A', 'corr_author': 'N/A', 'affiliation': 'N/A',
                    'abs_zh': f'This paper cited: {paper["title"]}',
                    'source': 'Unknown', 'published': cit.get('creation', '')[:4],
                    'cited_paper': paper['title'], '_source_tag': 'OpenCitations',
                })
    except Exception as e:
        print(f'  [OpenCitations] Error: {e}')
    return results


# ── Strategy 2: Crossref journal scan ───────────────────────────────────────

def fetch_crossref_scan(paper: dict, since: str) -> list:
    """
    Scan recently deposited papers from key seismology journals and check
    each paper's reference list for fingerprints of our paper.
    Uses cursor-based pagination to get up to 500 papers per journal.
    """
    results = []
    doi = paper.get('doi', '')

    for journal in SEISMO_JOURNALS:
        j_encoded = urllib.parse.quote(journal)
        base_url = (
            f'https://api.crossref.org/works'
            f'?filter=container-title:{j_encoded},type:journal-article,from-index-date:{since}'
            f'&select=DOI,title,author,container-title,issued,created,reference'
            f'&rows=100&cursor=*'
        )
        cursor = '*'
        page = 0
        max_pages = 5  # up to 500 papers per journal

        while page < max_pages:
            url = (
                f'https://api.crossref.org/works'
                f'?filter=container-title:{j_encoded},type:journal-article,from-index-date:{since}'
                f'&select=DOI,title,author,container-title,issued,created,reference'
                f'&rows=100&cursor={urllib.parse.quote(cursor)}'
            )
            try:
                resp = session.get(url, timeout=30)
                data = resp.json().get('message', {})
                items = data.get('items', [])
                next_cursor = data.get('next-cursor', '')

                for item in items:
                    item_doi = item.get('DOI', '')
                    if doi and item_doi.lower() == doi.lower():
                        continue
                    references = item.get('reference', [])
                    if references and any(_ref_matches(ref, paper) for ref in references):
                        entry = _make_entry(item, paper, 'Crossref')
                        results.append(entry)
                        print(f'    [Crossref/{journal}] {entry["title"][:70]}')

                if not items or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f'  [Crossref] Error scanning {journal}: {e}')
                break

    return results


# ── Strategy 3: scholarly (Google Scholar) ───────────────────────────────────

def fetch_scholarly(paper: dict) -> list:
    """Fallback: Google Scholar 'Cited by' via scholarly library."""
    results = []
    try:
        from scholarly import scholarly as sch
        pubs = sch.search_pubs(paper['title'])
        pub = next(pubs, None)
        if not pub:
            print(f'  [scholarly] Not found on Google Scholar: {paper["title"][:50]}')
            return results
        sch.fill(pub)
        print(f'  [scholarly] Scanning citedby...')
        for citer in sch.citedby(pub):
            try:
                bib = citer.get('bib', {})
                authors_raw = bib.get('author', 'N/A')
                first_author = authors_raw.split(' and ')[0].strip() if authors_raw != 'N/A' else 'N/A'
                results.append({
                    'id': citer.get('author_pub_id', '') or bib.get('title', '')[:40],
                    'title': bib.get('title', 'No Title'),
                    'url': citer.get('pub_url', ''),
                    'first_author': first_author,
                    'corr_author': 'N/A',
                    'affiliation': 'N/A',
                    'abs_zh': f'This paper cited: {paper["title"]}',
                    'source': bib.get('venue', 'Unknown'),
                    'published': str(bib.get('pub_year', '')),
                    'cited_paper': paper['title'],
                    '_source_tag': 'scholarly',
                })
                print(f'    [scholarly] {bib.get("title", "")[:70]}')
            except Exception:
                continue
    except ImportError:
        print('  [scholarly] Library not installed, skipping.')
    except Exception as e:
        print(f'  [scholarly] Error: {e}')
    return results


# ── main ─────────────────────────────────────────────────────────────────────

def fetch_citing_papers():
    now = datetime.now()
    since = (now - timedelta(days=SCAN_DAYS)).strftime('%Y-%m-%d')
    all_results = []

    # 0. Manually known citing papers (always fetched, no lag)
    print('=== Fetching manually known citing papers...')
    r0 = fetch_known_citing_dois()
    all_results.extend(r0)

    for paper in MY_PAPERS:
        print(f'\n=== Searching citations for: {paper["title"][:60]}...')

        # 1. OpenCitations
        r1 = fetch_opencitations(paper)
        all_results.extend(r1)
        time.sleep(1)

        # 2. Crossref journal scan (recent papers)
        print(f'  [Crossref] Scanning journals for papers deposited since {since}...')
        r2 = fetch_crossref_scan(paper, since)
        all_results.extend(r2)
        time.sleep(1)

        # 3. scholarly
        r3 = fetch_scholarly(paper)
        all_results.extend(r3)

    # Deduplicate by id (lowercased)
    seen = set()
    unique = []
    for r in all_results:
        key = (r.get('id') or r.get('title', '')[:60]).lower()
        if key and key not in seen:
            seen.add(key)
            # Remove internal tag before saving
            r.pop('_source_tag', None)
            unique.append(r)

    # Sort newest first
    unique.sort(key=lambda x: x.get('published', ''), reverse=True)

    print(f'\nTotal unique citing papers found: {len(unique)}')
    save_results(unique, now)


def save_results(papers, now):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'last_update': now.strftime('%Y-%m-%d %H:%M'),
            'topic_name': '文章引用',
            'papers': papers,
        }, f, ensure_ascii=False, indent=2)
    print(f'Saved {len(papers)} entries to {OUTPUT_FILE}')


if __name__ == '__main__':
    fetch_citing_papers()
