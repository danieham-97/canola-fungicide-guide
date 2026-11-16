#!/usr/bin/env python3
"""Persist only generated source status, retaining holds across network failures."""
import base64,json,os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,urlopen
from refresh_sources import ROOT,STATUS_PATH

def main():
    repo=os.environ['GITHUB_REPOSITORY'];branch=os.environ['TARGET_BRANCH'];token=os.environ['GH_TOKEN']
    if not all(part and part.replace('-','').replace('_','').replace('.','').isalnum()for part in repo.split('/'))or repo.count('/')!=1:raise ValueError('Invalid repository')
    api='https://api.github.com/repos/'+repo+'/contents/data/source-status.json'
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'canola-guide-actions'}
    current=None
    try:
        with urlopen(Request(api+'?ref='+quote(branch,safe=''),headers=headers),timeout=30)as r:current=json.load(r)
    except HTTPError as exc:
        if exc.code!=404:raise
    body={'message':'Refresh tracked source checks','content':base64.b64encode(STATUS_PATH.read_bytes()).decode(),'branch':branch}
    if current:body['sha']=current['sha']
    with urlopen(Request(api,data=json.dumps(body).encode(),headers={**headers,'Content-Type':'application/json'},method='PUT'),timeout=30)as r:result=json.load(r)
    print('Saved source-check history at commit '+result['commit']['sha'][:12])
if __name__=='__main__':main()
