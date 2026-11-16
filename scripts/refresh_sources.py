#!/usr/bin/env python3
"""Check source identities and fingerprints; never infer application directions."""
from __future__ import annotations
import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
import re
import time
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA_PATH=ROOT/'data/reviewed.json'
STATUS_PATH=ROOT/'data/source-status.json'
HTTP_TIMEOUT=max(5,min(30,int(os.environ.get('CANOLA_SOURCE_TIMEOUT','20'))))

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(data): return json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def read_baseline(): return json.loads(DATA_PATH.read_text())
def baseline_hash(data): return digest(canonical(data))

def fetch(url,binary=False):
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password: raise ValueError('HTTPS source required')
    # The reviewed Regalia 16 EPA master label is about 40 MB.
    cap=50_000_000 if binary else 10_000_000
    for attempt in range(2):
        try:
            req=Request(url,headers={'User-Agent':'Canola-Guide-Source-Check/1.0','Cache-Control':'no-cache'})
            with urlopen(req,timeout=HTTP_TIMEOUT) as response:
                body=response.read(cap+1)
            if len(body)>cap: raise ValueError('Source exceeds size limit')
            if binary:
                if b'%PDF-' not in body[:1024]: raise ValueError('Response is not a PDF')
                return body
            return json.loads(body)
        except HTTPError as exc:
            if exc.code in {429,502,503,504} and attempt==0:
                time.sleep(1)
                continue
            raise
    raise ValueError('Source unavailable')

def normalize_pdf(body):
    text=body.decode('latin1')
    text=re.sub(r'/ModDate\(D:[^)]*\)','/ModDate(download-time)',text)
    text=re.sub(r'xmp:ModifyDate="[^"]*"','xmp:ModifyDate="download-time"',text)
    text=re.sub(r'(/ID\s*\[\s*<[0-9a-fA-F]+>\s*)<[0-9a-fA-F]+>(\s*\])',r'\1<download-instance>\2',text)
    return text.encode('utf-8')

def document_matches(profile,body):
    return digest(body)==profile['sha256'] or (
        profile.get('fingerprintMode')=='syngenta-download-metadata-v1' and
        bool(profile.get('normalizedSha256')) and digest(normalize_pdf(body))==profile['normalizedSha256'])

def latest_epa(files):
    if not isinstance(files,list): raise ValueError('Missing document history')
    valid=[f for f in files if re.fullmatch(r'[0-9-]+-[0-9]{8}\.pdf',str(f.get('pdffile','')),re.I)]
    return max(valid,key=lambda f:f['pdffile'][-12:-4]) if valid else None

def compare_epa(record,payload):
    if not isinstance(payload.get('items'),list): raise ValueError('Unexpected EPA response')
    live=next((r for r in payload['items'] if r.get('eparegno')==record['reg']),None)
    if not live: raise ValueError('Exact registration not returned; possible transfer requires review')
    ingredients=live.get('active_ingredients')
    if not live.get('product_status') or not isinstance(ingredients,list): raise ValueError('Incomplete EPA record')
    for i in ingredients:
        if not i.get('pc_code'): raise ValueError('Incomplete ingredient')
        n=float(i['active_ing_percent'])
        if not 0<=n<=100: raise ValueError('Invalid ingredient percentage')
    latest=latest_epa(live.get('pdffiles'))
    url='https://www3.epa.gov/pesticides/chem_search/ppls/'+latest['pdffile'] if latest else None
    changes=[]
    for field,old,label in [('product_status','status','Federal status'),('rup_yn','restrictedUse','Restricted-use classification'),('signal_word','signalWord','Signal word')]:
        if live.get(field)!=record.get(old): changes.append(label+' changed')
    if not latest: changes.append('No label document returned')
    elif url!=record['latestDocument']: changes.append('Latest EPA document changed')
    normalized=lambda items:sorted((str(i['pc_code']),float(i['active_ing_percent']))for i in items)
    if normalized(ingredients)!=normalized(record['ingredients']): changes.append('Active ingredient record changed')
    current=dict(reg=record['reg'],name=live['productname'],status=live['product_status'],statusDate=live.get('product_status_date'),signalWord=live.get('signal_word'),restrictedUse=live.get('rup_yn'),ingredients=ingredients,aliases=[a['altbrandname']for a in live.get('altbrandnames',[])],transfers=live.get('transfer_history',[]),latestDocument=url,latestAccepted=latest.get('pdffile_accepted_date')if latest else None,documentHistory=live.get('pdffiles',[]),checked=now())
    return changes,current

FEEDS={
 'uk':'https://public-api.wordpress.com/rest/v1.1/sites/kentuckypestnews.wordpress.com/posts/?search=canola&number=100&fields=ID,date,modified,title,URL',
 'ut':'https://news.utcrops.com/wp-json/wp/v2/posts?search=canola&per_page=100&_fields=id,date,modified,title,link'
}
def check_feed(key,baseline,reader=fetch):
    payload=reader(FEEDS[key]);posts=payload.get('posts')if key=='uk'else payload
    if not isinstance(posts,list): raise ValueError('Unexpected feed response')
    if (key=='uk' and int(payload.get('found',0))>len(posts)) or (key=='ut' and len(posts)>=100): raise ValueError('Incomplete feed; review pagination')
    def title(post):return post.get('title','')if key=='uk'else post.get('title',{}).get('rendered','')
    relevant=[p for p in posts if re.search('canola',title(p),re.I) and re.search(r'white\s*mold|sclerotinia',title(p),re.I)]
    if not relevant: raise ValueError('No matching Extension article')
    latest=max(relevant,key=lambda p:p['date']);url=latest['URL'if key=='uk'else'link'];modified=latest.get('modified')or latest['date']
    expected='kentuckypestnews.wordpress.com'if key=='uk'else'news.utcrops.com'
    if urlsplit(url).hostname!=expected:raise ValueError('Unexpected article host')
    changed=url!=baseline['url'] or bool(baseline.get('modified')and modified!=baseline['modified'])
    return dict(status='changed'if changed else'matched',date=now(),url=url,modified=modified,title=title(latest),result='Article changed; manual review required'if changed else'Latest matching article matches reviewed reference')

def refresh(data,previous=None,reader=fetch,workers=4):
    fingerprint=baseline_hash(data)
    previous=previous if isinstance(previous,dict)and previous.get('reviewedHash')==fingerprint else{}
    valid_regs={r['reg']for r in data['registry']};valid_ids={p['id']for p in data['products']}
    critical={k:v for k,v in previous.get('criticalChanges',{}).items()if k in valid_regs}
    alerts={k:v for k,v in previous.get('pdfAlerts',{}).items()if k in valid_ids}
    snapshot=dict(schema=1,reviewedHash=fingerprint,startedAt=now(),generatedAt=None,requestTimeoutSeconds=HTTP_TIMEOUT,epaChecks={},checks={},feedChecks={},liveRegistry={},criticalChanges=critical,pdfAlerts=alerts,candidates=[],scope='Tracked EPA records, reviewed primary PDFs and two Extension feeds. No automatic approval of changed use directions.')
    lock=threading.Lock();counts={'epa_failed':0,'epa_reached':0,'pdf_failed':0,'pdf_reached':0};host_failures={}
    def epa(record):
        try:
            with lock:
                if counts['epa_failed']>=6 and not counts['epa_reached']:raise ValueError('Not requested: repeated EPA endpoint failures in this run')
            changes,current=compare_epa(record,reader(record['source']))
            with lock:counts['epa_reached']+=1
            return record['reg'],dict(status='changed'if changes else'matched',date=now(),result='; '.join(changes)if changes else'Federal record matches reviewed baseline'),current,changes
        except Exception as exc:
            with lock:counts['epa_failed']+=1
            reason=str(exc)
            return record['reg'],dict(status='unavailable',date=now(),result='Not verified: '+reason[:300]),None,['Exact registration unavailable; possible transfer requires review']if 'Exact registration' in reason else None
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
        for reg,result,current,changes in pool.map(epa,data['registry']):
            snapshot['epaChecks'][reg]=result
            if current:snapshot['liveRegistry'][reg]=current
            elif reg in previous.get('liveRegistry',{}):snapshot['liveRegistry'][reg]=previous['liveRegistry'][reg]
            if changes:snapshot['criticalChanges'][reg]=changes
            elif changes==[]:snapshot['criticalChanges'].pop(reg,None)
    def pdf(profile):
        host=urlsplit(profile['labelUrl']).hostname
        try:
            with lock:
                if host_failures.get(host,0)>=3 or (counts['pdf_failed']>=8 and not counts['pdf_reached']):raise ValueError('Not requested: repeated document access failures in this run')
            body=reader(profile['labelUrl'],binary=True)
            if b'%PDF-'not in body[:1024]: raise ValueError('Response is not a PDF')
            matched=document_matches(profile,body)
            with lock:counts['pdf_reached']+=1
            return profile['id'],dict(status='matched'if matched else'changed',date=now(),result='Linked PDF matches reviewed fingerprint'if matched else'PDF changed; directions withheld pending review',sha256=digest(body))
        except Exception as exc:
            with lock:
                counts['pdf_failed']+=1;host_failures[host]=host_failures.get(host,0)+1
            return profile['id'],dict(status='unavailable',date=now(),result='Not verified: '+str(exc)[:300])
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
        for id,result in pool.map(pdf,data['products']):
            snapshot['checks'][id]=result
            if result['status']=='changed':snapshot['pdfAlerts'][id]='Linked PDF changed from the reviewed document'
            elif result['status']=='matched':snapshot['pdfAlerts'].pop(id,None)
    for key in FEEDS:
        try:snapshot['feedChecks'][key]=check_feed(key,next(s for s in data['sources']if s['id']==key),reader)
        except Exception as exc:snapshot['feedChecks'][key]=dict(status='unavailable',date=now(),result='Not verified: '+str(exc)[:300])
    for reg,reasons in snapshot['criticalChanges'].items():
        snapshot['candidates'].append(dict(name='EPA review: '+reg,url=next(r['source']for r in data['registry']if r['reg']==reg),reason='; '.join(reasons)))
    for id,reason in snapshot['pdfAlerts'].items():
        p=next(p for p in data['products']if p['id']==id)
        snapshot['candidates'].append(dict(name='Changed label: '+p['name'],url=p['labelUrl'],reason=reason))
    for key,c in snapshot['feedChecks'].items():
        if c['status']=='changed':snapshot['candidates'].append(dict(name='Extension article review: '+key,url=c['url'],reason=c['result']))
    snapshot['summary']={key:dict(Counter(v['status']for v in snapshot[key].values()))for key in ['epaChecks','checks','feedChecks']}
    snapshot['generatedAt']=now()
    return snapshot

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    previous=json.loads(STATUS_PATH.read_text())if STATUS_PATH.exists()else None
    data=read_baseline();snapshot=refresh(data,previous,workers=max(1,min(4,args.workers)))
    STATUS_PATH.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(snapshot['summary']))

if __name__=='__main__':main()
