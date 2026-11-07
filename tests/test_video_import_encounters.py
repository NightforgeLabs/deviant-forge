import tempfile
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import video_import


class EncounterTests(unittest.TestCase):
    def test_field_guide_all_weapons_tooltip_keeps_four_distinct_rows(self):
        texts=[(10,95,'Shock Rampage <Power Surge>'),
               (79,95,'Weapon Mods-All Weapons'),
               (136,97,'Shock Rampage'),
               (177,98,'Inflicting Power Surge grants + 5.0% Power'),
               (207,98,"Surge Trigger Chance (based on weapon's"),
               (238,97,'Trigger Chance) for 5.0s, up to 4.0'),
               (269,46,'N'),(269,97,'stack(s).'),(345,111,'4'),
               (359,194,'17 Power Surge'),
               (455,97,'Power Surge DMG + 6.0%'),
               (528,97,'Power Surge Trigger Chance + 6.0%'),
               (601,98,'Shock DMG + 6.0%'),
               (674,98,'Increases damage dealt to all DMG Boost by +'),
               (704,97,'3.0%'),(784,98,'Level 5 and above, higher levels yield better')]
        lines=[{'y':y,'x':x,'text':text,'confidence':90} for y,x,text in texts]
        result=video_import.parse_tooltip(lines,'mod:weapon_mod:shock-rampage-power-surge')
        self.assertEqual(result['slot'],'weapon_mod')
        self.assertEqual(result['level'],17)
        self.assertEqual(result['ownership'],'unknown')
        self.assertEqual(result['main_effect'],
                         "Inflicting Power Surge grants + 5.0% Power Surge Trigger Chance (based on weapon's Trigger Chance) for 5.0s, up to 4.0 stack(s).")
        self.assertEqual(result['attribute_rows'],[
            'Power Surge DMG + 6.0%',
            'Power Surge Trigger Chance + 6.0%',
            'Shock DMG + 6.0%',
            'Increases damage dealt to all DMG Boost by + 3.0%'])

    def test_actual_reviewed_top_frame_extracts_exact_identity_level_and_rows(self):
        db=Path(__file__).resolve().parents[1]/'data'/'advisor.sqlite3'
        if not db.is_file():self.skipTest('Preserved Top source unavailable')
        with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as c:
            records=[json.loads(row[0]) for row in c.execute(
                'SELECT data FROM video_import_proposals WHERE run_id=?',
                ('3eca1e237ab643989c03a1b9c767555d',))]
        expected=next((row for row in records if row.get('catalog_id')==
                       'mod:chest_mod:ardent-shield-battle' and row.get('ownership')=='unlocked'),None)
        if not expected:self.skipTest('Expected reviewed tooltip unavailable')
        frame=db.parent/expected['source']['frame']
        if not frame.is_file():self.skipTest('Preserved game frame unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            result=video_import.analyze_image(frame,Path(tmp))
        matched=[item for item in result['proposals'] if item['catalog_id']==expected['catalog_id']]
        self.assertEqual(len(matched),1)
        self.assertEqual(matched[0]['level'],expected['level'])
        self.assertEqual(matched[0]['ownership'],'unlocked')
        self.assertEqual(matched[0]['attribute_rows'],expected['attribute_rows'])

    def test_uploaded_screenshot_produces_review_only_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'uploaded.png';Image.new('RGB',(900,900)).save(source)
            title=[{'catalog_id':'mod:chest_mod:healing-fortification-battle',
                    'title':'Healing Fortification <Battle>',
                    'header':{'x':10,'y':10,'w':200,'h':30}}]
            detail={'slot':'chest_mod','level':9,'ownership':'unlocked',
                    'ownership_cues':['Equip action','visible level and suffix'],
                    'main_effect':'Healing effect','attribute_rows':['Max HP + 2.4%'],
                    'raw_ocr':'Max HP + 2.4%','ocr_confidence':90}
            with (patch.object(video_import,'ocr_lines',return_value=[]),
                  patch.object(video_import,'titles',return_value=title),
                  patch.object(video_import,'parse_tooltip',return_value=detail),
                  patch.object(video_import,'header_rarity',return_value=('legendary',[]))):
                result=video_import.analyze_image(source,Path(tmp)/'review')
            self.assertEqual(result['frames_scanned'],1)
            self.assertEqual(len(result['proposals']),1)
            proposal=result['proposals'][0]
            self.assertEqual(proposal['attribute_rows'],['Max HP + 2.4%'])
            self.assertIn('require review',proposal['unknowns'][0])
            self.assertTrue(Path(proposal['source']['context']).is_file())
            self.assertEqual(proposal['source']['encounter'],0)

    def test_separate_same_level_hovers_remain_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = {'time': 0}
            def frame_at(path, seconds, target, scale=None):
                current['time'] = int(seconds)
                Image.new('RGB', (900, 900)).save(target)
                return target
            def titles(lines):
                if current['time'] not in (0, 1, 6):
                    return []
                return [{'catalog_id': 'mod:chest_mod:healing-fortification-battle',
                         'title': 'Healing Fortification <Battle>',
                         'header': {'x': 10, 'y': 10, 'w': 200, 'h': 30}}]
            def parse(lines, catalog_id):
                value = 'Max HP +2.4%' if current['time'] < 6 else 'Max HP +3.2%'
                return {'slot': 'chest_mod', 'level': 9, 'ownership': 'unlocked',
                        'ownership_cues': ['Equip action', 'visible level and suffix'],
                        'main_effect': 'Healing effect', 'attribute_rows': [value] * 4,
                        'raw_ocr': value, 'ocr_confidence': 90}
            with (patch.object(video_import, 'video_info', return_value={'duration': 7}),
                  patch.object(video_import, 'frame_at', side_effect=frame_at),
                  patch.object(video_import, 'ocr_lines', return_value=[]),
                  patch.object(video_import, 'titles', side_effect=titles),
                  patch.object(video_import, 'parse_tooltip', side_effect=parse),
                  patch.object(video_import, 'header_rarity', return_value=('legendary', []))):
                result = video_import.analyze(Path(tmp) / 'source.mp4', Path(tmp) / 'frames')
            self.assertEqual(len(result['proposals']), 2)
            self.assertEqual([p['source']['encounter'] for p in result['proposals']], [0, 1])
            self.assertEqual([p['attribute_rows'][0] for p in result['proposals']],
                             ['Max HP +2.4%', 'Max HP +3.2%'])

    def test_partial_conflict_then_complete_reading_preserves_both_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            current={'time':0}
            def frame_at(path, seconds, target, scale=None):
                current['time']=int(seconds)
                Image.new('RGB',(900,900)).save(target)
                return target
            def titles(lines):
                return [{'catalog_id':'mod:chest_mod:healing-fortification-battle',
                         'title':'Healing Fortification <Battle>',
                         'header':{'x':10,'y':10,'w':200,'h':30}}]
            def parse(lines,catalog_id):
                rows=(['Max HP +2.4%','Magazine Capacity +4.8%','Status DMG +2.4%']
                      if current['time']==0 else
                      ['Max HP +3.2%','Magazine Capacity +4.8%',
                       'Status DMG +2.4%','All DMG Boost +3.0%'])
                return {'slot':'chest_mod','level':9,'ownership':'unlocked',
                        'ownership_cues':['Equip action','visible level and suffix'],
                        'main_effect':'Healing effect','attribute_rows':rows,
                        'raw_ocr':'\n'.join(rows),'ocr_confidence':90}
            with (patch.object(video_import,'video_info',return_value={'duration':2}),
                  patch.object(video_import,'frame_at',side_effect=frame_at),
                  patch.object(video_import,'ocr_lines',return_value=[]),
                  patch.object(video_import,'titles',side_effect=titles),
                  patch.object(video_import,'parse_tooltip',side_effect=parse),
                  patch.object(video_import,'header_rarity',return_value=('legendary',[]))):
                result=video_import.analyze(Path(tmp)/'source.mp4',Path(tmp)/'frames')
            self.assertEqual(len(result['proposals']),2)
            self.assertEqual([len(p['attribute_rows']) for p in result['proposals']],[3,4])
            self.assertEqual([p['source']['timestamp'] for p in result['proposals']],[0,1])
            self.assertTrue(all(any('Conflicting tooltip readings' in warning for warning in p['unknowns'])
                                for p in result['proposals']))


if __name__ == '__main__':
    unittest.main()
