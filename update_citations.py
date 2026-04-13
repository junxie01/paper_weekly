#!/usr/bin/env python3
"""
Fetch papers that cited the user's publications in the past week
using the scholarly library (Google Scholar scraper).
"""

import json
import os
from datetime import datetime, timedelta

try:
    from scholarly import scholarly
    HAS_SCHOLARLY = True
except ImportError:
    HAS_SCHOLARLY = False
    print("scholarly not installed, skipping citations fetch.")

SCHOLAR_ID = 'HlONCtkAAAAJ'
OUTPUT_FILE = 'data_citations.json'


def fetch_citing_papers():
    now = datetime.now()
    results = []
    current_year = str(now.year)

    print(f"Fetching author profile: {SCHOLAR_ID}")
    try:
        author = scholarly.search_author_id(SCHOLAR_ID)
        scholarly.fill(author, sections=['publications'])
    except Exception as e:
        print(f"Error fetching author profile: {e}")
        save_results(results, now)
        return

    pubs = author.get('publications', [])
    print(f"Found {len(pubs)} publications. Checking citations...")

    for pub in pubs:
        try:
            scholarly.fill(pub)
            pub_title = pub['bib'].get('title', 'Unknown')
            print(f"  Checking citations for: {pub_title[:60]}")

            citedby_url = pub.get('citedby_url', '')
            if not citedby_url:
                continue

            # Iterate citing articles
            for citer in scholarly.citedby(pub):
                try:
                    year = str(citer['bib'].get('pub_year', ''))
                    if year != current_year:
                        continue

                    authors_raw = citer['bib'].get('author', 'N/A')
                    first_author = authors_raw.split(' and ')[0].strip() if authors_raw != 'N/A' else 'N/A'

                    results.append({
                        'id': citer.get('author_pub_id', '') or citer['bib'].get('title', '')[:40],
                        'title': citer['bib'].get('title', 'No Title'),
                        'url': citer.get('pub_url', ''),
                        'first_author': first_author,
                        'corr_author': 'N/A',
                        'affiliation': 'N/A',
                        'abs_zh': f"This paper cited: {pub_title}",
                        'source': citer['bib'].get('venue', 'Unknown'),
                        'published': year,
                        'cited_paper': pub_title
                    })
                except Exception as e:
                    print(f"    Error processing citing paper: {e}")
                    continue

        except Exception as e:
            print(f"  Error processing publication: {e}")
            continue

    # Deduplicate by id
    seen = set()
    unique = []
    for r in results:
        key = r['id'] or r['title'][:40]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Sort by title
    unique.sort(key=lambda x: x.get('title', ''))

    print(f"Done: {len(unique)} unique citing papers found.")
    save_results(unique, now)


def save_results(papers, now):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'last_update': now.strftime('%Y-%m-%d %H:%M'),
            'topic_name': '文章引用',
            'papers': papers
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    if HAS_SCHOLARLY:
        fetch_citing_papers()
    else:
        save_results([], datetime.now())
