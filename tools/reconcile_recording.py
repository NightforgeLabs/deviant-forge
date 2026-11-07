#!/usr/bin/env python3
"""Reclassify already extracted source crops without reencoding the recording."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recognition
import server


def main():
    server.init()
    tally=collections.Counter()
    for obs in server.observations():
        identity=recognition.identify(obs['ocr'], server.DATA / obs['image'])
        fields=server.parse_ocr(obs['ocr'])
        fields['identification']=identity
        if identity.get('catalog_id'):
            fields['name']={'value':identity['name'],'confidence':'high' if identity['match']['confidence']>=.95 else 'medium','reason':'Catalog title match; source crop retained'}
            fields['slot']={'value':identity['slot'],'confidence':'high','reason':'Catalog slot'}
            if identity.get('variant'):fields['variant']={'value':identity['variant'],'confidence':'high','reason':'Catalog variant'}
            if identity.get('level') is not None:fields['level']={'value':identity['level'],'confidence':'medium','reason':'Visible Field Guide level'}
        # OCR from an overview or a fading tooltip is retained as evidence, but not a review task.
        relevant=bool(identity['match']['status']=='ambiguous' or (identity.get('catalog_id') and identity.get('ownership')=='unknown'))
        state=obs['state'] if relevant else 'ignored'
        with server.connect() as c:
            c.execute('UPDATE observations SET fields=?,state=? WHERE id=?',(json.dumps(fields),state,obs['id']))
        if identity.get('ownership')=='unlocked' and identity.get('level'):
            if server.auto_confirm_catalog_mod(obs['id']):state='confirmed'
        tally[(identity['match']['status'],identity['ownership'],state)]+=1
    print(json.dumps({'observations':sum(tally.values()),'classes':{' / '.join(k):v for k,v in sorted(tally.items())},'inventory_items':len(server.inventory())},indent=2))


if __name__=='__main__':main()
