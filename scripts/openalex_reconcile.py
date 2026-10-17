#!/usr/bin/env python3
"""Read-only OpenAlex/website bibliography audit, including verified Zenodo DOI pairs.

Run in repository root: python scripts/openalex_reconcile.py
Offline recheck: python scripts/openalex_reconcile.py --input-csv openalex_reconciliation.csv
"""
import argparse
import csv
import io
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

AUTHOR = 'A5137924014'
OPENALEX_API = f'https://api.openalex.org/works?filter=author.id:{AUTHOR}&per-page=100'
ZENODO_RE = re.compile(r'^10\.5281/zenodo\.(\d+)$', re.I)
FIELDS = ['status', 'verification', 'local_id', 'local_title', 'local_year',
          'local_status', 'local_dois', 'openalex_id', 'openalex_title',
          'openalex_year', 'openalex_doi', 'local_wikidata', 'notes']

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'AcademicBibliographyAudit/2.0 (read-only)', 'Accept': 'application/json, text/csv'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8-sig')

def normalize_doi(value):
    s = (value or '').strip().lower()
    s = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', s)
    return s.rstrip('.,; ')

def local_dois(row):
    values = set()
    for field in ('doi_work_or_edition', 'doi_landing_page', 'doi_repository'):
        for match in re.findall(r'10\.\d{4,9}/[^\s;,]+', row.get(field, '') or '', re.I):
            values.add(normalize_doi(match))
    return values

def norm(text):
    s = unicodedata.normalize('NFKD', text or '').casefold()
    return re.sub(r'[^\w]+', ' ', ''.join(c for c in s if not unicodedata.combining(c))).strip()

def zenodo_record(doi, cache):
    match = ZENODO_RE.fullmatch(doi)
    if not match:
        return None
    recid = match.group(1)
    if recid not in cache:
        try:
            data = json.loads(fetch(f'https://zenodo.org/api/records/{recid}'))
            metadata = data.get('metadata', {})
            cache[recid] = {
                'conceptrecid': str(data.get('conceptrecid') or ''),
                'doi': normalize_doi(data.get('doi')),
                'conceptdoi': normalize_doi(data.get('conceptdoi') or metadata.get('conceptdoi')),
                'id': str(data.get('id') or ''),
            }
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            cache[recid] = {'error': str(exc)}
    return cache[recid]

def verified_zenodo_pair(a, b, cache):
    """Only Zenodo metadata can establish concept/version relationship; never use numeric proximity."""
    ra, rb = zenodo_record(a, cache), zenodo_record(b, cache)
    if not ra or not rb or 'error' in ra or 'error' in rb:
        return False
    if ra['conceptrecid'] and ra['conceptrecid'] == rb['conceptrecid']:
        return True
    return (a in (rb['doi'], rb['conceptdoi']) and b in (ra['doi'], ra['conceptdoi']))

def get_works():
    first = json.loads(fetch(OPENALEX_API))
    works = first.get('results', [])
    count = first.get('meta', {}).get('count', len(works))
    if count > len(works):
        raise RuntimeError(f'OpenAlex returned {len(works)} of {count}; pagination required. Aborting.')
    return works

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-csv', help='Existing reconciliation CSV for offline Zenodo verification (still requires Zenodo API)')
    parser.add_argument('--local', default='data/publications.csv')
    parser.add_argument('--output', default='openalex_reconciliation.csv')
    args = parser.parse_args()
    local_path = Path(args.local)
    if not local_path.exists():
        raise RuntimeError(f'Run from repository root; missing {local_path}')
    local = list(csv.DictReader(io.StringIO(local_path.read_text(encoding='utf-8-sig'))))
    by_id = {r['id']: r for r in local}
    if len(by_id) != len(local):
        raise RuntimeError('Duplicate local IDs: aborting')
    if args.input_csv:
        previous = list(csv.DictReader(open(args.input_csv, encoding='utf-8-sig', newline='')))
        works = [{'id': r['openalex_id'], 'title': r['openalex_title'],
                  'publication_year': r['openalex_year'], 'doi': r['openalex_doi']}
                 for r in previous]
    else:
        works = get_works()
    cache = {}
    output = []
    for work in works:
        doi = normalize_doi(work.get('doi'))
        exact = [r for r in local if doi and doi in local_dois(r)]
        if len(exact) == 1:
            match, status, verification, note = exact[0], 'MATCH_DOI', 'DOI_EXACT', ''
        elif len(exact) > 1:
            match, status, verification, note = None, 'REVIEW_MULTIPLE_DOI', 'AMBIGUOUS', 'Multiple local records share DOI'
        else:
            # Use title/year only to identify a candidate, never to confirm identity.
            ranked = sorted(((max(SequenceMatcher(None, norm(work.get('title')), norm(r.get(k))).ratio()
                                  for k in ('title_sr', 'title_en')), r) for r in local),
                            key=lambda pair: pair[0], reverse=True)
            top_score, candidate = ranked[0] if ranked else (0, None)
            try:
                year_ok = abs(int(candidate['year']) - int(work.get('publication_year'))) <= 1 if candidate else False
            except (ValueError, TypeError):
                year_ok = False
            if candidate and top_score >= 0.87 and year_ok:
                match = candidate
                related = [d for d in local_dois(match) if verified_zenodo_pair(doi, d, cache)]
                if related:
                    status, verification, note = 'MATCH_ZENODO', 'ZENODO_API_CONCEPT_VERSION', f'Zenodo relationship verified: {related[0]}'
                else:
                    status, verification, note = 'REVIEW_TITLE', 'TITLE_YEAR_ONLY', f'Title similarity {top_score:.3f}; DOI not verified as same Zenodo concept/version'
            else:
                match, status, verification, note = None, 'UNMATCHED', 'NONE', ''
        output.append(dict(status=status, verification=verification,
                           local_id=match['id'] if match else '', local_title=match['title_sr'] if match else '',
                           local_year=match['year'] if match else '', local_status=match['status'] if match else '',
                           local_dois='; '.join(sorted(local_dois(match))) if match else '',
                           openalex_id=work.get('id', ''), openalex_title=work.get('title', ''),
                           openalex_year=work.get('publication_year', ''), openalex_doi=doi,
                           local_wikidata=match.get('wikidata', '') if match else '', notes=note))
    with open(args.output, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    print(f'Local: {len(local)}; OpenAlex: {len(works)}; output: {args.output}')
    print('Statuses:', dict(Counter(r['status'] for r in output)))
    print('No bibliography, JSON-LD or manifest files were changed.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
