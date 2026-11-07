"""Cache only artwork attached to an exact catalog identity or unique listing name.

The source pages remain in the manifest. Ambiguous names are intentionally unmapped.
"""
import concurrent.futures
import io
import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'static'/'artwork'
DEST.mkdir(exist_ok=True)
SESSION=requests.Session()
BASE='https://www.oncehumandb.com'

def listing(kind, page_count):
    found={}
    for page in range(1,page_count+1):
        response=SESSION.get(f'{BASE}/{kind}',params={'page':page},timeout=25)
        response.raise_for_status()
        soup=BeautifulSoup(response.text,'html.parser')
        for anchor in soup.select(f'a[href^="/{kind}/"]'):
            name=anchor.find('h3');image=anchor.find('img')
            if name and image and image.get('src'):
                spans=anchor.find_all('span')
                category=spans[1].get_text(' ',strip=True) if kind=='weapons' and len(spans)>1 else None
                found.setdefault(name.get_text(' ',strip=True).casefold(),{})[anchor['href']]={'image_url':image['src'],'category':category}
    return found

def main():
    indexes={'weapon':listing('weapons',7),'armor':listing('armor',8)}
    records={};ambiguous=[]
    for identity,entry in catalog.ENTRIES.items():
        if entry['kind'] not in ('mod','weapon','armor'):continue
        url=entry.get('image_url');page=entry.get('source_url');category=None
        if not url and entry['kind'] in indexes:
            candidates=indexes[entry['kind']].get(entry['name'].casefold(),{})
            if len(candidates)==1:
                path,detail=next(iter(candidates.items()));url=detail['image_url'];category=detail['category'];page=urljoin(BASE,path)
            elif len(candidates)>1:ambiguous.append({'catalog_id':identity,'name':entry['name'],'source_pages':list(candidates)})
        if url:
            records[identity]={'image_url':url,'source_page':page,'matching':'catalog detail image' if entry.get('image_url') else 'unique exact listing name','weapon_category':category,'local_path':None}
    def fetch(pair):
        identity,record=pair
        try:
            existing=list(DEST.glob(identity.replace(':','__').replace('/','_')+'.*'))
            if existing:return identity,'/artwork/'+existing[0].name,None
            response=requests.get(record['image_url'],timeout=25)
            response.raise_for_status()
            image=Image.open(io.BytesIO(response.content));image.verify()
            ext='.png' if Image.open(io.BytesIO(response.content)).format=='PNG' else '.webp' if Image.open(io.BytesIO(response.content)).format=='WEBP' else None
            if ext is None:return identity,None,'unsupported image format'
            filename=identity.replace(':','__').replace('/','_')+ext
            (DEST/filename).write_bytes(response.content)
            return identity,'/artwork/'+filename,None
        except Exception as exc:return identity,None,str(exc)
    failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for identity,path,error in pool.map(fetch,records.items()):
            records[identity]['local_path']=path
            if error:failures.append({'catalog_id':identity,'error':error})
    counts={kind:{'total':0,'mapped':0,'cached':0} for kind in ('mod','weapon','armor')}
    for identity,entry in catalog.ENTRIES.items():
        kind=entry['kind']
        if kind not in counts:continue
        counts[kind]['total']+=1
        if identity in records:counts[kind]['mapped']+=1
        if records.get(identity,{}).get('local_path'):counts[kind]['cached']+=1
    missing=[{'catalog_id':identity,'name':entry['name'],'kind':entry['kind'],'reason':'no unique exact image match in current source'} for identity,entry in catalog.ENTRIES.items() if entry['kind'] in counts and not records.get(identity,{}).get('local_path')]
    output={'captured_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'source_index':BASE,'records':records,'ambiguous':ambiguous,'missing':missing,'failures':failures,'coverage':counts}
    (ROOT/'artwork_manifest.json').write_text(json.dumps(output,indent=2))
    print(json.dumps({'coverage':counts,'ambiguous':len(ambiguous),'download_failures':len(failures)},indent=2))

if __name__=='__main__':main()
