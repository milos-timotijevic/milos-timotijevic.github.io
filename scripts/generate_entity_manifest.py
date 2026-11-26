#!/usr/bin/env python3
"""Regenerate schema 1.2 entity manifest from actual data, preserving metadata."""
import argparse,csv,json,hashlib,io
from pathlib import Path
FILES={'people.csv':'people','institutions.csv':'institutions','places.csv':'places','sources.csv':'historicalSources','aircraft.csv':'aircraft','relations.csv':'relations','relation-types.csv':'relationTypes','entity-graph.jsonld':'jsonLdNodes'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--version',required=True);p.add_argument('--date',required=True);a=p.parse_args();d=a.root/'data/entities';m=json.loads((d/'entity-manifest.json').read_text());assert m['schemaVersion']=='1.2';m.update(version=a.version,dateModified=a.date);entries=[]
 for name,key in FILES.items():
  b=(d/name).read_bytes();n=len(json.loads(b)['@graph']) if name.endswith('.jsonld') else sum(1 for _ in csv.DictReader(io.StringIO(b.decode('utf-8-sig'))));m['scope'][key]=n;entries.append(dict(path=name,recordCount=n,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
 ids={r['source_id'] for r in csv.DictReader((d/'relations.csv').open(encoding='utf-8-sig'))};pub={r['id'] for r in csv.DictReader((a.root/'data/publications.csv').open(encoding='utf-8-sig'))};assert ids<=pub;m['scope']['publications']=len(ids);m['files']=entries;(d/'entity-manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
