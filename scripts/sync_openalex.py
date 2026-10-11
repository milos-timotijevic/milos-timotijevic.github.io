#!/usr/bin/env python3
"""Audit / safely synchronize OpenAlex author IDs in a local website checkout.
Usage: python sync_openalex.py /path/to/site [--apply]
Defaults to dry-run. Backs up edited files in a ZIP before applying changes.
"""
from pathlib import Path
import argparse, json, re, sys, zipfile
from datetime import datetime

OLD='A5072525869'
NEW='A5137924014'
EXTS={'.html','.htm','.json','.jsonld','.csv','.xml','.md','.txt','.yml','.yaml','.ttl','.nt','.rdf','.js','.ts'}
SKIP={'.git','node_modules','.venv','venv','dist','build'}
PATTERN=re.compile(re.escape(OLD),re.IGNORECASE)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path,help='Root directory of local GitHub Pages repository')
    p.add_argument('--apply',action='store_true',help='Apply reviewed, narrowly scoped ID replacements')
    args=p.parse_args()
    root=args.root.resolve()
    if not root.is_dir(): p.error('Directory does not exist')
    matches=[]; invalid=[]; checked=0
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f.suffix.lower() not in EXTS or any(x in SKIP for x in f.relative_to(root).parts):continue
        try:s=f.read_text(encoding='utf-8')
        except (UnicodeError,OSError):continue
        checked+=1
        n=len(PATTERN.findall(s))
        if not n: continue
        revised=PATTERN.sub(NEW,s)
        if f.suffix.lower() in {'.json','.jsonld'}:
            try:json.loads(revised)
            except json.JSONDecodeError as ex:invalid.append(f'{f.relative_to(root)}: {ex}')
        matches.append((f,n,s,revised))
    report={'source_root':str(root),'scanned_text_files':checked,'old_author_id':OLD,'new_author_id':NEW,
            'affected_file_count':len(matches),'old_id_occurrences':sum(x[1] for x in matches),
            'affected_files':[{'path':str(f.relative_to(root)).replace('\\','/'),'occurrences':n} for f,n,_,_ in matches],
            'invalid_json_after_replacement':invalid,'applied':False}
    if args.apply and invalid:
        print('REFUSING TO APPLY: JSON validation errors.');print('\n'.join(invalid));sys.exit(2)
    if args.apply and matches:
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
        archive=root.parent / f'openalex-backup-{stamp}.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for f,_,_,_ in matches:z.write(f,f.relative_to(root))
        for f,_,_,revised in matches:f.write_text(revised,encoding='utf-8',newline='')
        report['applied']=True
        report['backup_zip']=str(archive)
    out=root.parent/'openalex-audit-report.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('\n' + ('Changes applied. Review git diff and run site validators before commit.' if args.apply else 'DRY RUN ONLY. Re-run with --apply to modify files.'))
if __name__=='__main__':main()
