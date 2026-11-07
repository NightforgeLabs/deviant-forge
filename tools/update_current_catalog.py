#!/usr/bin/env python3
"""Capture factual mod identities and icon links from a dated community page."""
import json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path

URL='https://www.oncehumandb.com/mods'
root=Path(__file__).resolve().parents[1]
request=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 OnceHumanAdvisor/1'})
html=urllib.request.urlopen(request,timeout=30).read().decode('utf-8')
raw=re.findall(r'\{\\"slug\\":\\".*?\\"\}',html)
records=[];rejected=[]
for candidate in raw:
    try:
        value=json.loads(candidate.replace('\\"','"'))
        if not all(value.get(k) for k in ('slug','name','variant','modType')):raise ValueError('missing identity')
        records.append({k:value.get(k) for k in ('slug','name','variant','modType','category','rarity','coreEffect','imageUrl')})
    except Exception:rejected.append(candidate[:120])
if len(records)<1000:raise RuntimeError('Current catalog page layout changed; snapshot not replaced')
snapshot={'source':URL,'retrieved_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'page_records':len(raw),'parsed_records':len(records),'rejected_records':len(rejected),'status':'community page snapshot; names, effect text and icon links require current game corroboration','records':records}
(root/'catalog_current.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
print('saved',len(records),'records; rejected',len(rejected))
