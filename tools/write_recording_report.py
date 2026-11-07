#!/usr/bin/env python3
"""Write a traceable report from the saved observations and inventory."""
import collections
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

root=Path(__file__).resolve().parents[1]
obs=server.observations();items=server.inventory()
line=['# Recording review — 2026-10-22','',
      'Source: `screenrecording-2026-10-22_15-15-01.mp4` (424.033 seconds, 7678×2160). The original file in `~/Videos/` was not changed. Frames below are native-resolution crops, extracted before OCR.','',
      '## Field Guide unlocks with corroborating cues','',
      'The exact catalog title, visible level badge, and **Equip** action appeared together. These are saved as `mod_unlock`, not crafted equipment or an equipped item. Roll text remains an OCR candidate tied to the frame; level alone does not establish its values.','',
      '| Mod and variant | Level | Time | Source crop |','| --- | ---: | ---: | --- |']
for item in sorted(items,key=lambda x:x['evidence'][0]['timestamp'] if x['evidence'] else 999):
    if item['kind']!='mod_unlock':continue
    ev=item['evidence'][0]
    line.append(f"| {item['name']} <{item['variant']}> | {item['level']} | {ev['timestamp']:.0f}s | [frame](data/{ev['image']}) |")
line+=['','## Explicitly locked sightings','',
       'These do not enter owned inventory. A `Locked` label or `Unlock Cost` takes precedence over other OCR text such as `View Details Unlocked`.','',
       '| Entry | Time | Source crop |','| --- | ---: | --- |']
for o in obs:
    ident=o['fields'].get('identification') or {}
    if ident.get('catalog_id') and ident.get('ownership')=='locked':
        line.append(f"| {ident['name']}{' <'+ident['variant']+'>' if ident.get('variant') else ''} | {o['timestamp']:.0f}s | [frame](data/{o['image']}) |")
pending=[o for o in obs if o['state']=='pending']
line+=['','## Review queue and limitations','',
       f"The scan saved {len(obs)} source observations. It classified {sum(o['state']=='confirmed' for o in obs)} unlock observations, left {len(pending)} uncertain observations pending, and hid {sum(o['state']=='ignored' for o in obs)} overview, repeated, or explicit-lock crops from the default review queue. Pending means identity ambiguity, missing ownership cue, or incomplete frame; it does not imply ownership.", '',
       'Examples: AUG - Electron Cloud blueprint at 20s, Treacherous Tides Mask blueprint at 101s, and several armor and mod cards have identifiable titles but no corroborated ownership state in their extracted crop. The gear overview at 5–18s shows occupied slots but does not expose reliable item names. No crafted or equipped weapon was confirmed.','',
       'At 180s, the catalog match for Shock Diffusion <Power Surge> Lv. 11 populates the known primary effect, visually checked four attribute identities, and the official ordered subattribute tier profile `[3,3,3,2]` without submitting tooltip text. The card itself separately shows four rolled lines; these remain observation-specific and are not copied to every Lv. 11 card. At 225s, Overflow <General> Lv. 8 provides another visually checked identity set but has OCR ambiguity (`DMG ++ 2.4%`) in its numeric roll. At 281s and 307s, the newer current catalog identifies Precision Charge <Aero> Lv. 8 and Bullet Siphon <Aero Deviant Energy> Lv. 12; their aerial conditions are retained. At 315s, Reload Rampage <Downstar Deviant Energy> Lv. 11 has height-dependent rolls. Conditional values are not flattened to constant bonuses.','',
       '## Recommendation check','',
       f"Owned-only combination search currently returns zero legal scored builds: {sum(i['kind']=='mod_unlock' for i in items)} Field Guide mod unlocks are confirmed, but no primary crafted weapon with a measured or unbuffed tooltip base is confirmed. The recording also has no controlled combat hit, target, buffs, or firing cycle. Therefore the app does not establish a numerical winner from this recording. Catalog effects can still explain possible synergies and acquisition paths, with unknown stacking, activation, and roll values shown explicitly.",'',
       'To enable a trustworthy personal ranking, the minimum additional views are: (1) hover each **equipped** primary/secondary and armor piece with its name, tier, stats, and active mods visible; (2) show whether the currently viewed blueprint is unlocked or crafted; and (3) for a measured comparison, record the same target and conditions with a normal hit, firing cycle, and each exact compared loadout. The existing recording already supports mod unlock recognition; no transcription of known primary mod effects is needed.','']
(root/'RECORDING_REVIEW.md').write_text('\n'.join(line))
print('wrote RECORDING_REVIEW.md',len(items),'inventory entries',len(pending),'pending observations')
