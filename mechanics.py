"""Explicit weapon capabilities, never inferred from a family name or prose keyword."""
import json
from pathlib import Path

DATA = json.loads(Path(__file__).with_name('weapon_capabilities.json').read_text())
COMPONENTS = ('direct_hit','triggered_damage','status_damage','debuff','conditional_buff','firing_reload')


def weapon_capabilities(catalog_id):
    row = DATA['entries'].get(catalog_id)
    if row is None:
        return {'catalog_id':catalog_id, 'capabilities':{name:'unknown' for name in COMPONENTS},
                'source':[], 'evidence':'No exact-identity capability record; catalog family text is not a mechanic rule.'}
    capabilities = {name:row.get(name,'unknown') for name in COMPONENTS}
    if any(value not in ('present','absent_in_record','unknown') for value in capabilities.values()):
        raise ValueError('Invalid weapon capability record: ' + catalog_id)
    return {'catalog_id':catalog_id,'capabilities':capabilities,
            'source':row['source'],'evidence':row['evidence']}
