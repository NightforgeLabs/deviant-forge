#!/usr/bin/env python3
"""Reconcile downloaded mod detail strengths without guessing their levels.

This is an evidence index, not an equipable profile. A candidate becomes an
applied main-effect rule only when an exact-level card supplies that mapping.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import catalog

PERCENT=re.compile(r'(?<!\w)([+-]?\d+(?:\.\d+)?)\s*%')
SECONDS=re.compile(r'(?<!\w)(\d+(?:\.\d+)?)\s*s\b',re.I)
STACKS=re.compile(r'(?:up to|stacking up to)\s+(\d+)\s+stack',re.I)


def audit(details=None):
    details=details or catalog.DETAILS
    by_slug={}
    for entry in catalog.DATA['mods']:
        for record in entry.get('current_records') or []:
            by_slug.setdefault(record['slug'],set()).add(entry['id'])
    rows={};ambiguous=[]
    for slug,detail in details['records'].items():
        variants=detail.get('effect_variants') or []
        ids=by_slug.get(slug,set())
        if len(ids)!=1:
            if variants:ambiguous.append({'slug':slug,'catalog_ids':sorted(ids)})
            continue
        identity=next(iter(ids))
        for index,description in enumerate(variants):
            row={'detail_variant_index':index,
                 'percent_values':[float(x) for x in PERCENT.findall(description)],
                 'duration_seconds_candidates':[float(x) for x in SECONDS.findall(description)],
                 'stack_limits':[int(x) for x in STACKS.findall(description)],
                 'source_url':detail['source_url'],
                 'field_guide_level':'unmapped',
                 'source_status':'2026-10-22 current community client detail; exact Field Guide level not identified'}
            if any(row[key] for key in ('percent_values','duration_seconds_candidates','stack_limits')):
                rows.setdefault(identity,[]).append(row)
    return {'schema_version':1,'source_snapshot':details.get('retrieved_utc'),
            'source':'https://www.oncehumandb.com/mods','identities_with_numeric_candidates':len(rows),
            'candidate_rows':sum(map(len,rows.values())),'ambiguous_slugs':ambiguous,
            'entries':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    report=audit()
    target=ROOT/'catalog_effect_magnitudes.json'
    if args.check:
        if not target.exists() or json.loads(target.read_text())!=report:
            raise SystemExit('Detail magnitude index differs; run importer and inspect changes')
    else:target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('identities_with_numeric_candidates','candidate_rows')}))
