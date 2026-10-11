#!/usr/bin/env python3
"""Audit and optionally synchronize OpenAlex IDs in a local GitHub Pages checkout.
Dry-run is the default. Never touches .git. Validates JSON and existing manifest
checksums; refreshes tracked hashes only for changed files when --apply is used.
Run: python audit_sync_openalex_v2.py /path/to/repository
     python audit_sync_openalex_v2.py /path/to/repository --apply
"""
from pathlib import Path
import argparse, datetime, hashlib, json, re, shutil, sys, zipfile
OLD = 'A5072525869'
NEW = 'A5137924014'
RE = re.compile(re.escape(OLD), re.I)
TEXT_SUFFIXES={'.html','.htm','.json','.jsonld','.csv','.xml','.md','.txt','.yml','.yaml','.ttl','.nt','.rdf','.js','.ts'}
SKIP={'.git','node_modules','.venv','venv','dist','build'}
def sha(b): return hashlib.sha256(b).hexdigest()
def scan(root):
    changes=[]; invalid=[]; total=0
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES or SKIP.intersection(p.relative_to(root).parts): continue
        try: raw=p.read_bytes(); text=raw.decode('utf-8')
        except (OSError,UnicodeError): continue
        total+=1
        hits=len(RE.findall(text))
        if not hits:continue
        updated=RE.sub(NEW,text).encode('utf-8')
        if p.suffix.lower() in ('.json','.jsonld'):
            try: json.loads(updated)
            except ValueError as e:invalid.append({'path':str(p.relative_to(root)),'error':str(e)})
        changes.append({'path':p.relative_to(root).as_posix(),'count':hits,'before':raw,'after':updated})
    return total,changes,invalid

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('--apply',action='store_true')
    a=parser.parse_args();root=a.root.resolve()
    if not root.is_dir():parser.error('Repository directory does not exist')
    count,changes,invalid=scan(root)
    manifest=root/'data/manifest.json'
    original_manifest=None;manifest_data=None;checks=[];changed={c['path']:c for c in changes}
    if manifest.exists():
        original_manifest=manifest.read_bytes()
        try:
            manifest_data=json.loads(original_manifest)
            for item in manifest_data.get('files',[]):
                path=item.get('path');p=root/path if path else None
                if p is None or not p.is_file():checks.append({'path':path,'status':'missing'});continue
                b=p.read_bytes();actual={'sha256':sha(b),'byteSize':len(b)}
                mismatch={k:{'recorded':item.get(k),'actual':v} for k,v in actual.items() if item.get(k)!=v}
                checks.append({'path':path,'status':'mismatch' if mismatch else 'ok','details':mismatch})
        except ValueError as e: invalid.append({'path':'data/manifest.json','error':str(e)})
    report={'scanned_text_files':count,'affected_files':len(changes),'old_id_occurrences':sum(c['count'] for c in changes),'old_id':OLD,'new_id':NEW,'changes':[{'path':c['path'],'count':c['count']} for c in changes], 'invalid_after_replacement':invalid,'manifest_checks_before':checks,'applied':False}
    if a.apply:
        if invalid: sys.exit('REFUSED: invalid JSON. No files written.')
        modified=[c['path'] for c in changes]
        if manifest_data is not None:
            for item in manifest_data.get('files',[]):
                if item.get('path') in changed:
                    b=changed[item['path']]['after'];item['sha256']=sha(b);item['byteSize']=len(b)
            if any(i.get('path') in changed for i in manifest_data.get('files',[])):
                manifest_data['dateModified']=datetime.date.today().isoformat()
                modified.append('data/manifest.json')
        backup=root.parent/('openalex-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip')
        with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
            for p in modified:z.write(root/p,p)
        for c in changes:(root/c['path']).write_bytes(c['after'])
        if 'data/manifest.json' in modified:
            manifest.write_text(json.dumps(manifest_data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        report['applied']=True;report['backup']=str(backup)
    out=root.parent/'openalex-audit-v2.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
