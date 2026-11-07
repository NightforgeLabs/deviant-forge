"""Snapshot compact OnceHumanDB mod detail descriptions; never infer level values."""
import concurrent.futures
import datetime
import json
import time
import urllib.request
from bs4 import BeautifulSoup
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=json.loads((ROOT/'catalog_current.json').read_text())
DEST=ROOT/'catalog_details.json'
old=json.loads(DEST.read_text()) if DEST.exists() else {'records':{}}

def fetch(slug):
    url='https://www.oncehumandb.com/mods/'+slug
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'OnceHumanAdvisorCatalogResearch/1.0'})
            with urllib.request.urlopen(req,timeout=25) as response: html=response.read()
            soup=BeautifulSoup(html,'html.parser')
            heading=soup.find('h2',string=lambda x: bool(x and x.strip()=='Effect variants'))
            variants=[li.get_text(' ',strip=True) for li in heading.parent.select('ul li')] if heading else []
            return slug,{'source_url':url,'effect_variants':list(dict.fromkeys(variants)),'detail_title':soup.h1.get_text(' ',strip=True) if soup.h1 else None}
        except Exception as exc:
            if attempt==2:return slug,{'source_url':url,'error':str(exc)}
            time.sleep(attempt+1)

slugs=list(dict.fromkeys(row['slug'] for row in INDEX['records']))
pending=[slug for slug in slugs if slug not in old['records'] or 'error' in old['records'][slug]]
print('pending',len(pending),'total',len(slugs),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for n,(slug,result) in enumerate(pool.map(fetch,pending),1):
        old['records'][slug]=result
        if n%50==0 or n==len(pending):
            old.update({'source':'https://www.oncehumandb.com/mods','retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'detail_count':len(old['records'])})
            DEST.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
            print(n,'/',len(pending),'errors',sum('error' in r for r in old['records'].values()),flush=True)
