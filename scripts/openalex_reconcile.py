#!/usr/bin/env python3
"""Read-only reconciliation of site bibliography and OpenAlex author works."""
import csv, io, json, re, sys, unicodedata, urllib.request
from difflib import SequenceMatcher
from pathlib import Path

AUTHOR = 'A5137924014'
BASE = 'https://raw.githubusercontent.com/milos-timotijevic/milos-timotijevic.github.io/main/data/publications.csv'
API = f'https://api.openalex.org/works?filter=author.id:{AUTHOR}&per-page=100'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'BibliographyReconciliation/1.0 (research audit)'})
    with urllib.request.urlopen(req, timeout=35) as response:
        return response.read().decode('utf-8-sig')

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').casefold()
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', s).strip()

def dois(row):
    result = set()
    for key in ('doi_work_or_edition', 'doi_landing_page', 'doi_repository'):
        for v in re.findall(r'10\.\d{4,9}/[^\s;,]+', row.get(key, '') or '', re.I):
            result.add(v.rstrip('.').lower())
    return result

def main():
    local = list(csv.DictReader(io.StringIO(get(BASE))))
    remote = json.loads(get(API))
    works = remote.get('results', [])
    if remote.get('meta', {}).get('count', 0) > len(works):
        raise RuntimeError('OpenAlex pagination incomplete; do not treat results as exhaustive')
    records=[]
    for w in works:
        wd = (w.get('doi') or '').replace('https://doi.org/', '').lower()
        matches = [p for p in local if wd and wd in dois(p)]
        method='DOI' if matches else ''
        if not matches:
            ranked = sorted(((max(SequenceMatcher(None,norm(w.get('title')),norm(p.get(k))).ratio() for k in ('title_sr','title_en')),p) for p in local),key=lambda x:x[0],reverse=True)
            if ranked and ranked[0][0] >= .87 and abs(int(ranked[0][1].get('year') or 0)-int(w.get('publication_year') or 0))<=1:
                matches=[ranked[0][1]]; method='TITLE_REVIEW'
        p=matches[0] if len(matches)==1 else {}
        status = 'MATCH_DOI' if method=='DOI' and len(matches)==1 else ('REVIEW_TITLE' if method else 'UNMATCHED')
        if len(matches)>1: status='REVIEW_MULTIPLE_DOI'
        records.append({'status':status,'match_method':method,'local_id':p.get('id',''),'local_title':p.get('title_sr',''),'local_year':p.get('year',''),'local_status':p.get('status',''),'openalex_id':w.get('id',''),'openalex_title':w.get('title',''),'openalex_year':w.get('publication_year',''),'openalex_doi':wd,'local_wikidata':p.get('wikidata','')})
    out=Path('openalex_reconciliation.csv')
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]) if records else ['status']);writer.writeheader();writer.writerows(records)
    print(f'Local records: {len(local)}; OpenAlex records: {len(works)}; output: {out}')
    from collections import Counter
    print(dict(Counter(r['status'] for r in records)))
    print('No repository files were modified. Review all TITLE_REVIEW matches manually.')

if __name__=='__main__':
    try: main()
    except Exception as exc: print(f'ERROR: {exc}',file=sys.stderr);sys.exit(1)
