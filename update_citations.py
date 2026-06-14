#!/usr/bin/env python3
"""
Fetch papers that cited the user's publications and generate citation statistics with map data.

Strategy (in order, results merged and deduplicated):
  1. Fetch user's publication list from about page
  2. OpenCitations COCI API  — confirmed citation index (may lag ~weeks)
  3. Crossref journal scan   — scan ALL recent papers from key seismo journals,
                               check each reference list for our fingerprints
                               (catches papers immediately after deposit)
  4. Semantic Scholar (fallback) — Get full citation graph

Features:
  - Geocode author affiliations to lat/lon coordinates
  - Track weekly vs total citations
  - Generate map-ready JSON data
"""

import json
import os
import time
import re
import urllib.parse
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

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
MY_PAPERS_FILE = 'my_papers.json'
SCAN_DAYS = 7
SEISMO_JOURNALS = [
    'Nature', 'Science', 'Nature Geoscience', 'Nature Communications',
    'Science Advances', 'Geophysical Research Letters',
    'Journal of Geophysical Research: Solid Earth',
    'Earth and Planetary Science Letters', 'Geophysical Journal International',
    'Seismological Research Letters',
    'Bulletin of the Seismological Society of America',
    'Journal of Seismology', 'Tectonophysics', 'Solid Earth',
    'Communications Earth & Environment', 'The Cryosphere',
    'Earth and Space Science', 'Earthquake Research Advances',
]

def citation_key(paper):
    """Return a stable key for deduplicating citation records."""
    raw = paper.get('id') or paper.get('url') or paper.get('title', '')[:120]
    return raw.lower().strip() if raw else ''

def load_existing_citations():
    """Load historical citations so weekly updates do not erase old records."""
    if not os.path.exists(OUTPUT_FILE):
        return []
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('papers', [])
    except Exception as e:
        print(f'Could not load existing citations from {OUTPUT_FILE}: {e}')
        return []

def merge_citation_record(old, new):
    """Merge a fresh citation into an existing record while keeping cached geocoding."""
    merged = dict(old)
    for key, value in new.items():
        if key == 'coordinates' and value is None:
            continue
        if value not in (None, '', 'N/A'):
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged

def fetch_user_publications():
    """Fetch user's publication list from local about.md by parsing paper titles and querying Crossref."""
    local_file = 'about.md'
    try:
        print(f'Fetching publications from local {local_file}')
        with open(local_file, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f'File size: {len(content)} characters')
        print(f'Looking for Publications section...')

        publications = []
        paper_blocks = []

        lines = content.split('\n')
        in_publications = False
        current_block = ""

        for i, line in enumerate(lines):
            if 'Publications' in line and ('##' in line or '# ' in line):
                in_publications = True
                print(f'Found Publications at line {i}: {line[:50]}')
                continue
            if in_publications:
                if line.strip().startswith('## ') and 'Publications' not in line:
                    print(f'Exiting Publications section at line {i}')
                    break
                if re.match(r'^\d+\.', line.strip()):
                    if current_block:
                        paper_blocks.append(current_block)
                    current_block = line
                elif current_block:
                    current_block += " " + line

        if current_block:
            paper_blocks.append(current_block)

        print(f'Found {len(paper_blocks)} paper blocks')

        for i, block in enumerate(paper_blocks[:3]):
            print(f'\nFirst block preview:')
            print(f'  {block[:200]}...')

        for i, block in enumerate(paper_blocks):
            title_match = re.search(r'\[([^\]]+)\]\(https?://[^\)]+\)', block)
            if not title_match:
                print(f'Block {i+1}: No title match found')
                continue

            title = title_match.group(1).strip()

            year_match = re.search(r'\((\d{4})\)', block)
            year = year_match.group(1) if year_match else ""

            print(f'\nPaper {i+1}: {title[:60]}...')

            try:
                query = urllib.parse.quote(f'{title}')
                search_url = f'https://api.crossref.org/works?query={query}&rows=3'
                resp = session.get(search_url, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get('message', {}).get('items', [])
                    doi_found = False
                    for item in items:
                        item_title = (item.get('title') or [''])[0].lower()
                        if title.lower() in item_title or item_title in title.lower():
                            doi = item.get('DOI', '')
                            authors = item.get('author', [])
                            first = 'N/A'
                            if authors:
                                author = authors[0]
                                first = ' '.join([author.get('given', ''), author.get('family', '')]).strip()
                            publications.append({
                                'doi': doi,
                                'title': item.get('title', [title])[0],
                                'first_author': first,
                                'year': year
                            })
                            print(f'    -> DOI: {doi}')
                            doi_found = True
                            break
                    if not doi_found and items:
                        item = items[0]
                        doi = item.get('DOI', '')
                        authors = item.get('author', [])
                        first = 'N/A'
                        if authors:
                            author = authors[0]
                            first = ' '.join([author.get('given', ''), author.get('family', '')]).strip()
                        publications.append({
                            'doi': doi,
                            'title': item.get('title', [title])[0],
                            'first_author': first,
                            'year': year
                        })
                        print(f'    -> Using first result DOI: {doi}')
                time.sleep(0.5)
            except Exception as e:
                print(f'    -> Error: {e}')

        with open(MY_PAPERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'papers': publications, 'last_update': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        print(f'\n=== Total publications found: {len(publications)} ===')
        return publications
    except Exception as e:
        print(f'Error fetching user publications: {e}')
        import traceback
        traceback.print_exc()
        return []

def load_user_papers():
    """Load user papers from cached file or fetch fresh."""
    if os.path.exists(MY_PAPERS_FILE):
        try:
            with open(MY_PAPERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [p for p in data.get('papers', []) if p.get('doi')]
        except:
            pass
    papers = fetch_user_publications()
    return [p for p in papers if p.get('doi')]

def geocode_affiliation(affiliation_name):
    """Geocode an affiliation name to lat/lon coordinates using Nominatim."""
    if not affiliation_name or affiliation_name == 'N/A':
        return None
    cache_file = 'geocode_cache.json'
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except:
            pass
    if affiliation_name in cache:
        return cache[affiliation_name]

    queries = [
        affiliation_name,
    ]

    parts = [p.strip() for p in affiliation_name.split(',')]
    if len(parts) >= 2:
        queries.append(f"{parts[-2]}, {parts[-1]}".strip())
        if len(parts) >= 3:
            queries.append(f"{parts[-3]}, {parts[-1]}".strip())
    else:
        words = affiliation_name.split()
        for i, w in enumerate(words):
            if any(kw in w for kw in ['University', 'Institute', 'College']):
                queries.append(' '.join(words[i:]))
                if i > 0:
                    queries.append(' '.join(words[i-1:]))
                break

    import re

    city_match = re.search(r'\b(Beijing|Shanghai|Wuhan|Guangzhou|Chengdu|Xian|Nanjing|Tianjin|Chongqing|Qingdao|Hefei|Xian|Taipei|Seoul|Tokyo|Osaka|Kyoto|Potsdam|Munich|Berlin|Paris|London|Berkeley|Stanford|Cambridge|MIT|Harvard|New York|Los Angeles|Singapore)\b', affiliation_name)
    country_match = re.search(r'\b(USA|US|United States|China|Germany|UK|Japan|Australia|Canada|France|Russia|Singapore|Switzerland|Netherlands|Brazil|India|Taiwan|Korea)\b', affiliation_name)

    cas_match = re.search(r'Chinese Academy of Sciences', affiliation_name)
    if cas_match and city_match:
        queries.append(f"Chinese Academy of Sciences, {city_match.group(1)}")
        if country_match:
            queries.append(f"Chinese Academy of Sciences, {city_match.group(1)}, {country_match.group(1)}")

    if city_match and country_match:
        queries.append(f"{city_match.group(1)}, {country_match.group(1)}")
    elif city_match:
        queries.append(city_match.group(1))

    kw_pattern = r'(?:Chinese Academy|Academy|Institute|University|College|Laboratory|Observatory)'
    kw_matches = list(re.finditer(kw_pattern, affiliation_name))
    if kw_matches:
        last_kw = kw_matches[-1]
        words_before = affiliation_name[:last_kw.start()].split()
        if len(words_before) <= 5:
            univ = affiliation_name[:last_kw.end()].strip()
        else:
            univ = ' '.join(words_before[-5:]) + ' ' + last_kw.group()
        queries.append(univ)
        if city_match:
            queries.append(f"{univ}, {city_match.group(1)}")
        if country_match:
            queries.append(f"{univ}, {country_match.group(1)}")

    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen and q != affiliation_name:
            seen.add(q)
            unique_queries.append(q)

    for query in unique_queries:
        try:
            encoded = urllib.parse.quote(query)
            url = f'https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1'
            response = session.get(url, timeout=10, headers={'User-Agent': 'paper-weekly-bot/1.0'})
            if response.status_code == 200:
                data = response.json()
                if data:
                    lat = float(data[0].get('lat', 0))
                    lon = float(data[0].get('lon', 0))
                    if lat and lon:
                        result = {'lat': lat, 'lon': lon, 'display_name': data[0].get('display_name', '')}
                        cache[affiliation_name] = result
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache, f, ensure_ascii=False)
                        print(f'  [Geo] {affiliation_name[:50]} -> ({lat:.2f}, {lon:.2f}) [{query[:30]}]')
                        return result
            time.sleep(1)
        except Exception as e:
            print(f'  [Geo] Error geocoding {query[:30]}: {e}')
            continue

    cache[affiliation_name] = None
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    return None

def _in_window(pub_date_str, since_dt, until_dt=None):
    if not pub_date_str:
        return False
    if until_dt is None:
        until_dt = datetime.now()
    try:
        for fmt in ('%Y-%m-%d', '%Y-%m', '%Y'):
            try:
                dt = datetime.strptime(pub_date_str[:len('%Y-%m-%d' if len(pub_date_str) >= 10 else '%Y-%m')], fmt)
                return since_dt <= dt <= until_dt
            except:
                continue
        year = int(pub_date_str[:4])
        return since_dt.year <= year <= until_dt.year
    except:
        return False

def _ref_matches(ref, paper):
    ref_doi = (ref.get('DOI') or '').lower().strip()
    if ref_doi and ref_doi == paper.get('doi', '').lower():
        return True
    for fp in paper.get('fingerprints', []):
        if not fp:
            continue
        if fp.lower() in (ref.get('unstructured', '') or '').lower():
            return True
        if fp.lower() in (ref.get('articleTitle', '') or '').lower():
            return True
    return False

def _s2_entry(cp, paper):
    authors = cp.get('authors', [])
    first = authors[0].get('name', 'N/A') if authors else 'N/A'
    corr = authors[-1].get('name', 'N/A') if len(authors) > 1 else first
    ext = cp.get('externalIds') or {}
    doi = ext.get('DOI', '') or ''
    url = f'https://doi.org/{doi}' if doi else ''
    pub = cp.get('publicationDate', '') or str(cp.get('year', ''))
    journal = cp.get('journal') or {}
    source = cp.get('venue') or (journal.get('name', 'Unknown') if isinstance(journal, dict) else 'Unknown')
    authors_data = cp.get('authors', [])
    aff = ''
    if authors_data:
        first_author = authors_data[0] if authors_data else {}
        aff = first_author.get('affiliation', '')
        if isinstance(aff, dict):
            aff = aff.get('name', 'N/A')
    return {
        'id': doi or cp.get('paperId', ''),
        'title': cp.get('title', 'No Title'),
        'url': url,
        'first_author': first,
        'corr_author': corr,
        'affiliation': aff or 'N/A',
        'abs_zh': f'This paper cited: {paper["title"]}',
        'source': source,
        'published': pub,
        'cited_paper': paper['title'],
    }

def fetch_paper_affiliation(paper_doi):
    """Fetch author affiliation for a specific paper by DOI using Semantic Scholar."""
    if not paper_doi:
        return 'N/A'
    fields = 'authors'
    try:
        url = f'https://api.semanticscholar.org/graph/v1/paper/DOI:{paper_doi}?fields={fields}'
        r = session.get(url, timeout=15, headers={'User-Agent': 'paper-weekly-bot/1.0'})
        if r.status_code == 200:
            data = r.json()
            authors = data.get('authors', [])
            if authors and authors[0].get('affiliation'):
                return authors[0].get('affiliation')
    except Exception:
        pass
    return 'N/A'

def fetch_semantic_scholar(paper_doi, since_dt, paper=None):
    if paper is None:
        paper = {'doi': paper_doi, 'title': paper_doi}
    results = []
    if not paper_doi:
        return results
    fields = 'title,authors,year,publicationDate,externalIds,venue,journal,authors.affiliation'
    base = f'https://api.semanticscholar.org/graph/v1/paper/DOI:{paper_doi}/citations'
    offset = 0
    limit = 500
    while True:
        url = f'{base}?fields={fields}&limit={limit}&offset={offset}'
        try:
            r = session.get(url, timeout=30, headers={'User-Agent': 'paper-weekly-bot/1.0'})
            if r.status_code == 404:
                break
            if r.status_code == 429:
                time.sleep(15)
                continue
            data = r.json()
        except Exception as e:
            print(f'  [S2] Error for {paper_doi}: {e}')
            break
        items = data.get('data', [])
        found_in_page = 0
        for item in items:
            cp = item.get('citingPaper', {})
            if not cp:
                continue
            pub = cp.get('publicationDate', '') or str(cp.get('year', ''))
            if since_dt is None or _in_window(pub, since_dt):
                results.append(_s2_entry(cp, paper))
                found_in_page += 1
        oldest_in_page = ''
        for item in reversed(items):
            cp = item.get('citingPaper', {})
            oldest_in_page = cp.get('publicationDate', '') or str(cp.get('year', ''))
            if oldest_in_page:
                break
        if since_dt is not None and oldest_in_page and not _in_window(oldest_in_page, since_dt):
            break
        next_offset = data.get('next')
        if next_offset is None or len(items) < limit:
            break
        offset = next_offset
        time.sleep(1)
    if results:
        print(f'  [S2] {len(results)} new citation(s) in window for {paper_doi}')
    return results

def fetch_opencitations(paper_doi, since_dt, paper=None):
    if paper is None:
        paper = {'doi': paper_doi, 'title': paper_doi}
    results = []
    if not paper_doi:
        return results
    paper_title = paper.get('title', paper_doi)
    try:
        r = session.get(
            f'https://opencitations.net/index/coci/api/v1/citations/{paper_doi}',
            timeout=20, headers={'Accept': 'application/json'}
        )
        if r.status_code != 200:
            return results
        for cit in r.json():
            creation = cit.get('creation', '')
            if since_dt is not None and not _in_window(creation, since_dt):
                continue
            citing_doi = cit.get('citing', '')
            if not citing_doi:
                continue
            try:
                meta = session.get(
                    f'https://api.crossref.org/works/{citing_doi}',
                    timeout=15
                ).json().get('message', {})
                if not isinstance(meta, dict):
                    continue
                authors = meta.get('author', [])
                first = (f"{authors[0].get('given','')} {authors[0].get('family','')}".strip()
                         if authors else 'N/A')
                corr = (f"{authors[-1].get('given','')} {authors[-1].get('family','')}".strip()
                         if len(authors) > 1 else first)
                aff = (authors[0].get('affiliation', [{}])[0].get('name', 'N/A')
                       if authors and authors[0].get('affiliation') else 'N/A')
                date_parts = (meta.get('issued') or meta.get('created') or {}).get('date-parts', [['']])
                pub = '-'.join(str(x) for x in (date_parts[0] if date_parts else [])) or creation[:4]
                results.append({
                    'id': citing_doi,
                    'title': (meta.get('title') or ['No Title'])[0],
                    'url': f'https://doi.org/{citing_doi}',
                    'first_author': first,
                    'corr_author': corr,
                    'affiliation': aff,
                    'abs_zh': f'This paper cited: {paper_title}',
                    'source': (meta.get('container-title') or ['Unknown'])[0],
                    'published': pub,
                    'cited_paper': paper_title,
                })
                print(f'  [OC] {(meta.get("title") or [""])[0][:65]}')
            except Exception:
                pass
    except Exception as e:
        print(f'  [OC] Error for {paper_doi}: {e}')
    return results

def _crossref_entry(item, paper_title):
    authors = item.get('author', [])
    first = (f"{authors[0].get('given','')} {authors[0].get('family','')}".strip()
             if authors else 'N/A')
    corr = (f"{authors[-1].get('given','')} {authors[-1].get('family','')}".strip()
             if len(authors) > 1 else first)
    doi = item.get('DOI', '')
    dp = (item.get('issued') or item.get('created') or {}).get('date-parts', [['']])
    pub = '-'.join(str(x) for x in (dp[0] if dp else [])) or ''
    aff = (authors[0].get('affiliation', [{}])[0].get('name', 'N/A')
           if authors and authors[0].get('affiliation') else 'N/A')
    return {
        'id': doi,
        'title': (item.get('title') or ['No Title'])[0],
        'url': f'https://doi.org/{doi}' if doi else '',
        'first_author': first,
        'corr_author': corr,
        'affiliation': aff,
        'abs_zh': f'This paper cited: {paper_title}',
        'source': (item.get('container-title') or ['Unknown'])[0],
        'published': pub,
        'cited_paper': paper_title,
    }

def fetch_crossref_scan(paper_doi, since_dt, paper=None):
    if paper is None:
        paper = {'doi': paper_doi, 'title': paper_doi}
    paper_title = paper.get('title', paper_doi)
    results = []
    own_doi = paper_doi.lower()
    if since_dt is not None:
        since_str = since_dt.strftime('%Y-%m-%d')
    else:
        since_str = '1900-01-01'
    for journal in SEISMO_JOURNALS:
        j_enc = urllib.parse.quote(journal)
        cursor = '*'
        pages = 0
        max_pages = 5 if since_dt is None else 2
        while pages < max_pages:
            url = (f'https://api.crossref.org/works'
                   f'?filter=container-title:{j_enc},type:journal-article,from-index-date:{since_str}'
                   f'&select=DOI,title,author,container-title,issued,created,reference'
                   f'&rows=100&cursor={urllib.parse.quote(cursor)}')
            try:
                resp = session.get(url, timeout=30)
                msg = resp.json().get('message', {})
                items = msg.get('items', [])
                for item in items:
                    if item.get('DOI', '').lower() == own_doi:
                        continue
                    dp = (item.get('issued') or item.get('created') or {}).get('date-parts', [[]])
                    pub_str = '-'.join(str(x) for x in (dp[0] if dp and dp[0] else []))
                    if since_dt is not None and not _in_window(pub_str, since_dt):
                        continue
                    refs = item.get('reference', [])
                    if refs:
                        for ref in refs:
                            ref_doi = (ref.get('DOI') or '').lower().strip()
                            if ref_doi and ref_doi == own_doi:
                                e = _crossref_entry(item, paper_title)
                                results.append(e)
                                print(f'  [Crossref] {e["title"][:65]}')
                                break
                next_cursor = msg.get('next-cursor', '')
                if not items or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                pages += 1
                time.sleep(0.5)
            except Exception as e:
                print(f'  [Crossref] Error scanning {journal}: {e}')
                break
    return results

def fetch_all_citations(paper_doi, since_dt, paper=None):
    if paper is None:
        paper = {'doi': paper_doi, 'title': paper_doi}
    all_results = []
    r1 = fetch_semantic_scholar(paper_doi, since_dt, paper)
    all_results.extend(r1)
    time.sleep(1)
    r2 = fetch_opencitations(paper_doi, since_dt, paper)
    s2_ids = {x['id'].lower() for x in r1}
    for x in r2:
        if x['id'].lower() not in s2_ids:
            all_results.append(x)
    time.sleep(0.5)
    if not r1 and not r2:
        r3 = fetch_crossref_scan(paper_doi, since_dt, paper)
        all_results.extend(r3)
        time.sleep(0.5)
    return all_results

def fetch_full_citations(paper_doi):
    """Fetch all historical citations for a paper (not just recent)."""
    results = []
    if not paper_doi:
        return results
    fields = 'title,authors,year,publicationDate,externalIds,venue,journal,authors.affiliation'
    base = f'https://api.semanticscholar.org/graph/v1/paper/DOI:{paper_doi}/citations'
    offset = 0
    limit = 500
    while True:
        url = f'{base}?fields={fields}&limit={limit}&offset={offset}'
        try:
            r = session.get(url, timeout=30, headers={'User-Agent': 'paper-weekly-bot/1.0'})
            if r.status_code == 404:
                break
            if r.status_code == 429:
                time.sleep(15)
                continue
            data = r.json()
        except Exception as e:
            print(f'  [S2 Full] Error for {paper_doi}: {e}')
            break
        items = data.get('data', [])
        for item in items:
            cp = item.get('citingPaper', {})
            if not cp:
                continue
            pub = cp.get('publicationDate', '') or str(cp.get('year', ''))
            entry = _s2_entry(cp, {'title': paper_doi})
            entry['published'] = pub
            results.append(entry)
        next_offset = data.get('next')
        if next_offset is None or len(items) < limit:
            break
        offset = next_offset
        time.sleep(1)
    if not results:
        r2 = fetch_opencitations(paper_doi, datetime(1900, 1, 1))
        for x in r2:
            x['abs_zh'] = f'This paper cited: {paper_doi}'
            results.append(x)
    print(f'  [S2 Full] Total {len(results)} citations for {paper_doi}')
    return results

def save_results(papers, now):
    since_dt = now - timedelta(days=SCAN_DAYS)

    existing_papers = load_existing_citations()
    if existing_papers:
        print(f'Loaded {len(existing_papers)} existing citation record(s).')

    unique_by_id = {}
    for r in existing_papers + papers:
        key = citation_key(r)
        if not key:
            continue
        if key in unique_by_id:
            unique_by_id[key] = merge_citation_record(unique_by_id[key], r)
        else:
            unique_by_id[key] = dict(r)

    all_papers = list(unique_by_id.values())
    weekly_papers = []
    for r in all_papers:
        r['is_new_this_week'] = _in_window(r.get('published', ''), since_dt)
        if r['is_new_this_week']:
            weekly_papers.append(r)

    all_papers.sort(key=lambda x: x.get('published', ''), reverse=True)
    weekly_papers.sort(key=lambda x: x.get('published', ''), reverse=True)
    for paper in all_papers:
        if 'coordinates' not in paper or paper['coordinates'] is None:
            aff = paper.get('affiliation', 'N/A')
            if aff == 'N/A' or not aff:
                print(f'  [Aff] Fetching affiliation for {paper.get("id", paper.get("title", "")[:30])}...')
                aff = fetch_paper_affiliation(paper.get('id', ''))
                paper['affiliation'] = aff
                time.sleep(1)
            coords = geocode_affiliation(aff)
            paper['coordinates'] = coords
            if coords:
                print(f'  [Geo] {aff[:50]} -> ({coords["lat"]:.2f}, {coords["lon"]:.2f})')
            time.sleep(1)
    map_data = []
    for paper in all_papers:
        if paper.get('coordinates'):
            map_data.append({
                'lat': paper['coordinates']['lat'],
                'lon': paper['coordinates']['lon'],
                'title': paper['title'],
                'author': paper['first_author'],
                'affiliation': paper['affiliation'],
                'published': paper['published'],
                'url': paper['url'],
                'is_new_this_week': paper.get('is_new_this_week', False)
            })
    result = {
        'last_update': now.strftime('%Y-%m-%d %H:%M'),
        'topic_name': '文章引用',
        'total_citations': len(all_papers),
        'weekly_citations': len(weekly_papers),
        'papers': all_papers,
        'weekly_papers': weekly_papers,
        'map_data': map_data
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\nSaved to {OUTPUT_FILE}')
    print(f'Total citations: {len(all_papers)}')
    print(f'This week: {len(weekly_papers)}')

def fetch_citing_papers():
    now = datetime.now()
    
    full_scan = os.environ.get('FULL_SCAN', 'false').lower() == 'true'
    
    if full_scan:
        since_dt = None
        print('MODE: FULL HISTORICAL SCAN - Fetching all citations\n')
    else:
        since_dt = now - timedelta(days=SCAN_DAYS)
        since_str = since_dt.strftime('%Y-%m-%d')
        print(f'MODE: WEEKLY UPDATE - Scanning for citations since {since_str}\n')
    
    my_papers = load_user_papers()
    if not my_papers:
        print('No DOIs found. Please check your about page.')
        return

    test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
    if test_mode:
        my_papers = my_papers[:3]
        print(f'TEST MODE: Only processing first {len(my_papers)} papers\n')

    all_results = []
    for i, paper in enumerate(my_papers, 1):
        doi = paper['doi']
        print(f'[{i}/{len(my_papers)}] Processing {doi} ({paper.get("title", "")[:40]}...)')
        results = fetch_all_citations(doi, since_dt, paper)
        all_results.extend(results)
        time.sleep(1)
    
    seen = set()
    unique_results = []
    for r in all_results:
        key = citation_key(r)
        if key and key not in seen:
            seen.add(key)
            unique_results.append(r)
    
    if since_dt is not None:
        filtered = []
        for r in unique_results:
            pub = r.get('published', '')
            if _in_window(pub, since_dt):
                filtered.append(r)
        filtered.sort(key=lambda x: x.get('published', ''), reverse=True)
        print(f'\nDone. {len(filtered)} unique citing paper(s) in the past {SCAN_DAYS} days.')
        save_results(filtered, now)
    else:
        unique_results.sort(key=lambda x: x.get('published', ''), reverse=True)
        print(f'\nDone. {len(unique_results)} total unique citing paper(s) found.')
        save_results(unique_results, now)

if __name__ == '__main__':
    fetch_citing_papers()
