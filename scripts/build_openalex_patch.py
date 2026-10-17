#!/usr/bin/env python3
"""Add audited OpenAlex work links to publication JSON-LD; no network required.
Run at repository root. Fails before writing if any local ID is absent or duplicated.
"""
import csv, hashlib, json, pathlib, re, sys
ROOT=pathlib.Path('.')
LINKS=ROOT/'data/openalex-links.csv'
JSONLD=ROOT/'data/publications.jsonld'
MANIFEST=ROOT/'data/manifest.json'

def main():
    rows=list(csv.DictReader(LINKS.open(encoding='utf-8-sig',newline='')))
    if len(rows)!=67 or len({r['local_id'] for r in rows})!=67 or len({r['openalex_work_id'] for r in rows})!=67:
        raise ValueError('Expected 67 unique verified local IDs and OpenAlex work IDs')
    if any(r['link_status']!='VERIFIED_REPORT' or not re.fullmatch(r'W\d+',r['openalex_work_id']) for r in rows):
        raise ValueError('Only audited VERIFIED_REPORT work IDs allowed')
    data=json.loads(JSONLD.read_text(encoding='utf-8-sig'))
    nodes=data['@graph']; idx={}
    for node in nodes:
        ident=node.get('@id','')
        if ident.startswith('https://milos-timotijevic.github.io/data/publications.jsonld#'):
            key=ident.rsplit('#',1)[1]
            if key in idx: raise ValueError('Duplicate JSON-LD ID '+key)
            idx[key]=node
    missing=[r['local_id'] for r in rows if r['local_id'] not in idx]
    if missing: raise ValueError('Missing JSON-LD IDs: '+', '.join(missing))
    changed=0
    for r in rows:
        node=idx[r['local_id']]
        url='https://openalex.org/'+r['openalex_work_id']
        same=node.get('sameAs',[])
        if isinstance(same,str): same=[same]
        if not isinstance(same,list): raise ValueError('Unexpected sameAs for '+r['local_id'])
        old=[x for x in same if isinstance(x,str) and re.search(r'openalex\.org/(?:works/)?W\d+',x,re.I)]
        if old and url not in old: raise ValueError('Conflicting OpenAlex link '+r['local_id']+': '+str(old))
        if url not in same:
            node['sameAs']=same+[url]
            changed+=1
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8-sig'))
    entries=[e for e in manifest['files'] if e['path']=='data/publications.jsonld']
    if len(entries)!=1: raise ValueError('Missing/duplicate manifest entry')
    rendered=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    e=entries[0];e['sha256']=hashlib.sha256(rendered).hexdigest();e['byteSize']=len(rendered)
    e['recordCount']=len(nodes)
    if '--apply' not in sys.argv:
        print('DRY RUN: validated',len(rows),'links;',changed,'JSON-LD nodes need updating. Pass --apply to write.')
        return
    JSONLD.write_bytes(rendered)
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Updated',changed,'nodes; refreshed JSON-LD SHA-256 manifest entry. Other files untouched.')
if __name__=='__main__':main()
