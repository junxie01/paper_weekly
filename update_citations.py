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
    # ── 2010 ──────────────────────────────────────────────────────────────
    {
        'title': 'The M5.0 Suining-Tongnan (China) earthquake of 31 January 2010: A destructive earthquake occurring in sedimentary cover',
        'doi': '10.1007/s11434-010-4276-2',
        'fingerprints': ['10.1007/s11434-010-4276-2', 's11434-010-4276', 'Suining-Tongnan'],
    },
    {
        'title': 'Comparison of ground truth location of earthquake from InSAR and from ambient seismic noise: A case study of the 1998 Zhangbei earthquake',
        'doi': '10.1007/s11589-010-0788-5',
        'fingerprints': ['10.1007/s11589-010-0788-5', 's11589-010-0788', 'Zhangbei earthquake'],
    },
    {
        'title': 'Effects of sedimentary layer on earthquake source modelling from geodetic inversion',
        'doi': '10.1007/s11589-010-0786-7',
        'fingerprints': ['10.1007/s11589-010-0786-7', 's11589-010-0786'],
    },
    # ── 2014 ──────────────────────────────────────────────────────────────
    {
        'title': 'Validating Accuracy of Rayleigh Wave Dispersion Extracted from Ambient Seismic Noise via Comparison with Data from a Ground-Truth Earthquake',
        'doi': '10.1785/0120130279',
        'fingerprints': ['10.1785/0120130279', '0120130279'],
    },
    {
        'title': 'Ground Truth Location of Earthquakes by Use of Ambient Seismic Noise From a Sparse Seismic Network: A Case Study in Western Australia',
        'doi': '10.1007/s00024-014-0993-6',
        'fingerprints': ['10.1007/s00024-014-0993-6', 's00024-014-0993', 'Western Australia'],
    },
    # ── 2015 ──────────────────────────────────────────────────────────────
    {
        'title': 'Synchronizing Intercontinental Seismic Networks Using the 26 s Persistent Localized Microseismic Source',
        'doi': '10.1785/0120140252',
        'fingerprints': ['10.1785/0120140252', '0120140252', '26 s persistent localized microseismic'],
    },
    {
        'title': 'Measurement of Rayleigh wave ellipticity and its application to the joint inversion of high-resolution S-wave velocity structure beneath northeast China',
        'doi': '10.1002/2015jb012459',
        'fingerprints': ['10.1002/2015jb012459', '2015jb012459'],
    },
    # ── 2016 ──────────────────────────────────────────────────────────────
    {
        'title': 'On the accuracy of long-period Rayleigh waves extracted from ambient noise',
        'doi': '10.1093/gji/ggw137',
        'fingerprints': ['10.1093/gji/ggw137', 'gji/ggw137'],
    },
    {
        'title': 'An investigation of time-frequency domain phase-weighted stacking and its application to phase-velocity extraction from ambient noise empirical Green\'s functions',
        'doi': '10.1093/gji/ggx448',
        'fingerprints': ['10.1093/gji/ggx448', 'gji/ggx448', 'phase-weighted stacking'],
    },
    # ── 2017 ──────────────────────────────────────────────────────────────
    {
        'title': 'Broad-band Rayleigh wave phase velocity maps (10-150 s) across the United States from ambient noise data',
        'doi': '10.1093/gji/ggw460',
        'fingerprints': ['10.1093/gji/ggw460', 'gji/ggw460'],
    },
    # ── 2018 ──────────────────────────────────────────────────────────────
    {
        'title': 'Assessing the short-term clock drift of early broadband stations with burst events of the 26 s persistent and localized microseism',
        'doi': '10.1093/gji/ggx401',
        'fingerprints': ['10.1093/gji/ggx401', 'gji/ggx401', 'clock drift', '26 s persistent'],
    },
    {
        'title': 'Nonlinear inversion of resistivity sounding data for 1-D earth models using the Neighbourhood Algorithm',
        'doi': '10.1016/j.jafrearsci.2017.09.003',
        'fingerprints': ['10.1016/j.jafrearsci.2017.09.003', 'jafrearsci.2017.09.003'],
    },
    {
        'title': 'Crust-mantle coupling mechanism in Cameroon, West Africa, revealed by 3D S-wave velocity and azimuthal anisotropy',
        'doi': '10.1016/j.pepi.2017.12.006',
        'fingerprints': ['10.1016/j.pepi.2017.12.006', 'pepi.2017.12.006', 'Cameroon'],
    },
    {
        'title': '3D upper-mantle shear velocity model beneath the contiguous United States based on broadband surface wave from ambient seismic noise',
        'doi': '10.1007/s00024-018-1881-2',
        'fingerprints': ['10.1007/s00024-018-1881-2', 's00024-018-1881'],
    },
    # ── 2019 ──────────────────────────────────────────────────────────────
    {
        'title': 'Imaging 3D upper-mantle structure with autocorrelation of seismic noise recorded on a transportable single station',
        'doi': '10.1785/0220180260',
        'fingerprints': ['10.1785/0220180260', '0220180260'],
    },
    {
        'title': 'Further constraints on the shear wave velocity structure of Cameroon from joint inversion of receiver function, Rayleigh wave dispersion and ellipticity measurements',
        'doi': '10.1093/gji/ggz008',
        'fingerprints': ['10.1093/gji/ggz008', 'gji/ggz008'],
    },
    {
        'title': 'Millimeter-level ultra-long period multiple Earth-circling surface waves retrieved from dense high-rate GPS network',
        'doi': '10.1016/j.epsl.2019.07.007',
        'fingerprints': ['10.1016/j.epsl.2019.07.007', 'epsl.2019.07.007', 'earth-circling surface waves'],
    },
    # ── 2020 ──────────────────────────────────────────────────────────────
    {
        'title': 'Enhancing Signal-to-Noise Ratios of High-Frequency Rayleigh Waves Extracted from Ambient Seismic Noises in Topographic Region',
        'doi': '10.1785/0120190177',
        'fingerprints': ['10.1785/0120190177', '0120190177'],
    },
    {
        'title': 'Relocation of the June 17th, 2017 Nuugaatsiaq (Greenland) landslide based on Green\'s functions from ambient seismic noise',
        'doi': '10.1029/2019jb018947',
        'fingerprints': ['10.1029/2019jb018947', '2019jb018947', 'Nuugaatsiaq'],
    },
    {
        'title': 'Validity of Resolving the 785 km Discontinuity in the Lower Mantle with P\'P\' Precursors',
        'doi': '10.1785/0220200210',
        'fingerprints': ['10.1785/0220200210', '0220200210', '785 km discontinuity'],
    },
    {
        'title': 'Coseismic Slip Distribution of the 24 January 2020 Mw 6.7 Doganyol Earthquake and in Relation to the Foreshock and Aftershock Activities',
        'doi': '10.1785/0220200152',
        'fingerprints': ['10.1785/0220200152', '0220200152', 'Doganyol'],
    },
    {
        'title': 'Crust and upper mantle structure of the South China Sea and adjacent areas from the joint inversion of ambient noise and earthquake surface wave dispersions',
        'doi': '10.1029/2020gc009356',
        'fingerprints': ['10.1029/2020gc009356', '2020gc009356'],
    },
    # ── 2021 ──────────────────────────────────────────────────────────────
    {
        'title': 'Evaluating global tomography models with antipodal ambient noise cross correlation functions',
        'doi': '10.1029/2020jb020444',
        'fingerprints': ['10.1029/2020jb020444', '2020jb020444', 'antipodal ambient noise'],
    },
    {
        'title': 'Sedimentary structure of the Sichuan Basin derived from seismic ambient noise tomography',
        'doi': '10.1093/gji/ggaa578',
        'fingerprints': ['10.1093/gji/ggaa578', 'gji/ggaa578', 'Sichuan Basin'],
    },
    {
        'title': 'Sensing shallow structure and traffic noise with fiber-optic internet cables in an urban area',
        'doi': '10.1007/s10712-021-09678-w',
        'fingerprints': ['10.1007/s10712-021-09678-w', 's10712-021-09678', 'fiber-optic internet cables'],
    },
    # ── 2022 ──────────────────────────────────────────────────────────────
    {
        'title': 'Generation mechanism of the 26 s and 28 s tremors in the Gulf of Guinea from statistical analysis of magnitudes and event intervals',
        'doi': '10.1016/j.epsl.2021.117334',
        'fingerprints': [
            '10.1016/j.epsl.2021.117334',
            'j.epsl.2021.117334',
            '26 s and 28 s tremors in the gulf',
            '26 s and 28 s tremors of the gulf',
            'epsl.2021.117334',
        ],
    },
    {
        'title': 'ADE-Net: A deep neural network for DAS earthquake detection trained with a limited number of positive samples',
        'doi': '10.1109/tgrs.2022.3143120',
        'fingerprints': ['10.1109/tgrs.2022.3143120', 'tgrs.2022.3143120', 'ADE-Net'],
    },
    {
        'title': 'Crustal structure in the Weiyuan shale gas field, China, and its tectonic implications',
        'doi': '10.1016/j.tecto.2022.229449',
        'fingerprints': ['10.1016/j.tecto.2022.229449', 'tecto.2022.229449', 'Weiyuan'],
    },
    # ── 2023 ──────────────────────────────────────────────────────────────
    {
        'title': 'Seismometer orientation correction via teleseismic receiver function measurements in West Africa and adjacent Islands',
        'doi': '10.1785/0220220316',
        'fingerprints': ['10.1785/0220220316', '0220220316'],
    },
    {
        'title': 'Topography effect on ambient noise tomography: a case study for the Longmen Shan area, eastern Tibetan Plateau',
        'doi': '10.1093/gji/ggac435',
        'fingerprints': ['10.1093/gji/ggac435', 'gji/ggac435', 'Longmen Shan'],
    },
    # ── 2024 ──────────────────────────────────────────────────────────────
    {
        'title': 'Ice plate deformation and cracking revealed by an in situ-distributed acoustic sensing array',
        'doi': '10.5194/tc-18-837-2024',
        'fingerprints': ['10.5194/tc-18-837-2024', 'tc-18-837', 'ice plate deformation'],
    },
    {
        'title': 'Near real-time in situ monitoring of nearshore ocean currents using distributed acoustic sensing on submarine fiber-optic cable',
        'doi': '10.1029/2024ea003572',
        'fingerprints': ['10.1029/2024ea003572', '2024ea003572', 'nearshore ocean currents'],
    },
    # ── 2025 ──────────────────────────────────────────────────────────────
    {
        'title': 'Seismotectonics of Ghana and adjacent regions in western Africa: a review',
        'doi': '10.1016/j.eqrea.2025.100442',
        'fingerprints': ['10.1016/j.eqrea.2025.100442', 'eqrea.2025.100442', 'Ghana'],
    },
    {
        'title': 'Complex seismogenic fault system for the 2022 Ms6.0 Maerkang (China) earthquake sequence resolved with reliable seismic source parameters',
        'doi': '10.1016/j.tecto.2025.230718',
        'fingerprints': ['10.1016/j.tecto.2025.230718', 'tecto.2025.230718', 'Maerkang'],
    },
    {
        'title': 'High resolution shallow structure of Ebao basin revealed with DAS ambient noise tomography and its relation to earthquake ground motion',
        'doi': '10.1029/2024jb029874',
        'fingerprints': ['10.1029/2024jb029874', '2024jb029874', 'Ebao basin'],
    },
    # ── 2026 ──────────────────────────────────────────────────────────────
    {
        'title': 'Fault Intersections Control the Extremely Shallow 2020 Mw 5.1 Sparta, North Carolina, Earthquake Sequence',
        'doi': '10.1785/0220250313',
        'fingerprints': ['10.1785/0220250313', '0220250313', 'Sparta', 'North Carolina'],
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
    return []  # removed — replaced by Semantic Scholar


# ── Strategy 1: Semantic Scholar (primary, fastest index) ────────────────────

def _s2_entry(citing_paper: dict, paper: dict) -> dict:
    """Build a result dict from a Semantic Scholar citingPaper object."""
    authors = citing_paper.get('authors', [])
    first_author = authors[0].get('name', 'N/A') if authors else 'N/A'
    corr_author = authors[-1].get('name', 'N/A') if len(authors) > 1 else first_author
    ext_ids = citing_paper.get('externalIds', {}) or {}
    doi = ext_ids.get('DOI', '') or ''
    url = f'https://doi.org/{doi}' if doi else citing_paper.get('url', '')
    published = citing_paper.get('publicationDate', '') or str(citing_paper.get('year', ''))
    return {
        'id': doi or citing_paper.get('paperId', ''),
        'title': citing_paper.get('title', 'No Title'),
        'url': url,
        'first_author': first_author,
        'corr_author': corr_author,
        'affiliation': 'N/A',
        'abs_zh': f'This paper cited: {paper["title"]}',
        'source': (citing_paper.get('venue') or citing_paper.get('journal', {}).get('name', 'Unknown') if isinstance(citing_paper.get('journal'), dict) else 'Unknown'),
        'published': published,
        'cited_paper': paper['title'],
        '_source_tag': 'S2',
    }


def fetch_semantic_scholar(paper: dict) -> list:
    """
    Use Semantic Scholar Graph API to get all papers citing this paper.
    Paginates through all results (500 per page).
    No API key required (free tier: 1 req/s).
    """
    results = []
    doi = paper.get('doi', '')
    if not doi:
        return results

    fields = 'title,authors,year,publicationDate,externalIds,venue,journal'
    base = f'https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}/citations'
    offset = 0
    limit = 500
    total_fetched = 0

    while True:
        url = f'{base}?fields={fields}&limit={limit}&offset={offset}'
        try:
            r = session.get(url, timeout=30, headers={'User-Agent': 'paper-weekly-bot/1.0'})
            if r.status_code == 404:
                print(f'  [S2] Paper not found: {doi}')
                break
            if r.status_code == 429:
                print(f'  [S2] Rate limited, waiting 10s...')
                time.sleep(10)
                continue
            data = r.json()
        except Exception as e:
            print(f'  [S2] Request error for {doi}: {e}')
            break

        items = data.get('data', [])
        for item in items:
            cp = item.get('citingPaper', {})
            if cp:
                results.append(_s2_entry(cp, paper))
        total_fetched += len(items)

        # Check if more pages exist
        next_offset = data.get('next', None)
        if next_offset is None or len(items) < limit:
            break
        offset = next_offset
        time.sleep(1)  # respect rate limit

    if total_fetched:
        print(f'  [S2] {total_fetched} citation(s) for {doi}')
    return results


# ── Strategy 2: OpenCitations

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


# ── Strategy 3: Crossref journal scan ───────────────────────────────────────

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


# ── Strategy 4: scholarly (Google Scholar) ───────────────────────────────────

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

    for paper in MY_PAPERS:
        print(f'\n=== Citations for: {paper["title"][:65]}...')

        # 1. Semantic Scholar — fastest, most up-to-date citation index
        r1 = fetch_semantic_scholar(paper)
        all_results.extend(r1)
        time.sleep(1)

        # 2. OpenCitations — confirmed citation graph (may lag weeks)
        r2 = fetch_opencitations(paper)
        all_results.extend(r2)
        time.sleep(0.5)

        # 3. Crossref journal scan — catches papers not yet in S2/OC
        #    Only run this for papers where S2 returned 0 results
        if not r1:
            print(f'  [Crossref] S2 had no results, scanning journals since {since}...')
            r3 = fetch_crossref_scan(paper, since)
            all_results.extend(r3)
            time.sleep(0.5)

        # 4. scholarly — slowest, skip unless specifically needed
        # (disabled by default to avoid rate limiting in CI)

    # Deduplicate by id (lowercased)
    seen = set()
    unique = []
    for r in all_results:
        key = (r.get('id') or r.get('title', '')[:60]).lower()
        if key and key not in seen:
            seen.add(key)
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
