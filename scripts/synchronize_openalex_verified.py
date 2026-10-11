#!/usr/bin/env python3
"""Synchronize OpenAlex A5072525869 -> A5137924014 in a local GitHub Pages checkout.
Dry-run by default. --apply writes changes with backup and verifies both manifests.
Python 3.9+. No dependencies and no network access required.
"""
from pathlib import Path
import argparse, csv, datetime, hashlib, json, re, shutil, sys, zipfile
OLD='A5072525869'; NEW='A5137924014'
PATTERN=re.compile(r'(?i)A5072525869')
EXT={'.html','.htm','.json','.jsonld','.csv','.xml','.md','.txt','.yml','.yaml','.ttl','.nt','.rdf','.js','.ts'}
SKIP={'.git','node_modules','venv','.venv','dist','build'}
MANIFESTS=('data/manifest.json','data/entities/entity-manifest.json')

def sha(b): return hashlib.sha256(b).hexdigest()
def report_manifest(root, rel):
    path=root/rel
    if not path.is_file(): return {'manifest':rel,'status':'missing','files':[]}
    data=json.loads(path.read_text(encoding='utf-8'))
    prefix='data/entities/' if 'entity-manifest' in rel else ''
    results=[]
    for item in data.get('files',[]):
        relative=(prefix+item['path']) if prefix else item['path']
        p=root/relative
        if not p.is_file():results.append({'path':relative,'status':'missing'});continue
        b=p.read_bytes(); old_size=item.get('bytes',item.get('byteSize'))
        details={}
        if len(b)!=old_size:details['size']={'recorded':old_size,'actual':len(b)}
        if sha(b)!=item.get('sha256'):details['sha256']={'recorded':item.get('sha256'),'actual':sha(b)}
        if p.suffix.lower()=='.jsonld':
            try:
                doc=json.loads(b)
                num=len(doc.get('@graph',[]))
                if item.get('recordCount')!=num:details['recordCount']={'recorded':item.get('recordCount'),'actual':num}
            except Exception as e: details['jsonld_error']=str(e)
        results.append({'path':relative,'status':'mismatch' if details else 'ok','details':details})
    return {'manifest':rel,'status':'ok' if all(x['status']=='ok' for x in results) else 'mismatch','files':results}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('repo',type=Path,help='Root directory of local GitHub Pages checkout')
    ap.add_argument('--apply',action='store_true',help='Back up and apply changes')
    args=ap.parse_args(); root=args.repo.resolve()
    if not (root/'.git').exists() and not (root/'data/knowledge-graph.jsonld').exists():
        ap.error('Expected repository root (missing .git and data/knowledge-graph.jsonld)')
    before=[report_manifest(root,m) for m in MANIFESTS]
    changes=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in EXT or set(p.relative_to(root).parts)&SKIP:continue
        try: raw=p.read_bytes();s=raw.decode('utf-8')
        except (OSError,UnicodeError):continue
        n=len(PATTERN.findall(s))
        if not n:continue
        updated=PATTERN.sub(NEW,s).encode('utf-8')
        if p.suffix.lower() in {'.json','.jsonld'}:json.loads(updated)
        changes.append((p.relative_to(root).as_posix(),n,updated))
    modified={p:b for p,_,b in changes}
    # Recompute the entire main manifest: it was stale even before the identifier change.
    if (root/'data/manifest.json').is_file():
        mf=json.loads((root/'data/manifest.json').read_text(encoding='utf-8'))
        for ent in mf.get('files',[]):
            rel=ent['path'];b=modified.get(rel)
            if b is None:
                p=root/rel
                if not p.is_file():raise FileNotFoundError(rel)
                b=p.read_bytes()
            ent['byteSize']=len(b);ent['sha256']=sha(b)
            if rel.endswith('.jsonld'):ent['recordCount']=len(json.loads(b)['@graph'])
        mf['dateModified']=datetime.date.today().isoformat()
        modified['data/manifest.json']=(json.dumps(mf,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    # Update entity manifest only if its referenced files actually changed.
    entity='data/entities/entity-manifest.json'
    if (root/entity).is_file():
        em=json.loads((root/entity).read_text(encoding='utf-8'))
        needs=False
        for ent in em.get('files',[]):
            rel='data/entities/'+ent['path']
            if rel not in modified:continue
            needs=True;b=modified[rel]
            ent['bytes']=len(b);ent['sha256']=sha(b)
            if rel.endswith('.jsonld'):ent['recordCount']=len(json.loads(b)['@graph'])
        if needs:
            em['dateModified']=datetime.date.today().isoformat()
            modified[entity]=(json.dumps(em,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    summary={'mode':'apply' if args.apply else 'dry-run','old_openalex':OLD,'primary_openalex':NEW,
             'affected_source_files':len(changes),'occurrences':sum(n for _,n,_ in changes),
             'files':[{'path':p,'occurrences':n} for p,n,_ in changes],
             'manifest_audit_before':before,'will_write':list(modified)}
    if args.apply:
        stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup=root.parent/f'openalex-backup-{stamp}.zip'
        with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
            for rel in modified:
                p=root/rel
                if p.exists():z.write(p,rel)
        for rel,b in modified.items():
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        remaining=[]
        for p in root.rglob('*'):
            if p.is_file() and p.suffix.lower() in EXT and not set(p.relative_to(root).parts)&SKIP:
                try:
                    if PATTERN.search(p.read_text('utf-8')):remaining.append(str(p.relative_to(root)))
                except UnicodeError:pass
        after=[report_manifest(root,m) for m in MANIFESTS]
        summary.update({'backup':str(backup),'remaining_old_id_files':remaining,'manifest_audit_after':after})
        if remaining or any(x['status']!='ok' for x in after):
            summary['result']='FAILED_VERIFICATION';print(json.dumps(summary,ensure_ascii=False,indent=2));sys.exit(2)
        summary['result']='VERIFIED'
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
