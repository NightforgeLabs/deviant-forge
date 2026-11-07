import json
import sqlite3
import tempfile
import unittest
import subprocess
from pathlib import Path

import catalog
import field_guide_profiles as guide


ID='mod:weapon_mod:shock-diffusion-power-surge'
OTHER='mod:weapon_mod:shock-diffusion-deviant-energy'


class FieldGuideProfilesTests(unittest.TestCase):
    def test_ui_has_explicit_profile_level_editor_and_no_automatic_inventory_add(self):
        script=(Path(__file__).resolve().parents[1]/'static'/'builder-character.js').read_text()
        css=(Path(__file__).resolve().parents[1]/'static'/'style.css').read_text()
        self.assertIn("New player · empty",script)
        self.assertIn("fieldGuideCardClick(this.dataset.modId)",script)
        self.assertIn('Field Guide level (0 = not unlocked)',script)
        self.assertIn('previewFieldGuideDraft()',script)
        self.assertIn("api('field-guide/level'",script)
        self.assertIn('mod-profile-controls',css)
        self.assertIn('grid-row:6',css)
        importer=(Path(__file__).resolve().parents[1]/'static'/'app.js').read_text()
        self.assertIn('owned&&legacyCopy&&p.status',importer)
        self.assertIn('Preview Field Guide progression',importer)
        self.assertIn('Source system ',importer)

    def test_late_personal_save_cannot_replace_new_player_preview(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/builder-character.js','utf8');
const body=source.slice(source.indexOf('let fieldGuideProfile='),source.indexOf('let modSelectedDetail='));
let resolveSave,fetches=0;
const ctx={state:{field_guide_profiles:{personal:{levels:{}},new_player:{levels:{}}}},
 document:{querySelector:key=>({value:key==='#fieldGuideLevel'?'11':'unknown'})},
 api:()=>new Promise(resolve=>{resolveSave=resolve}),fetch:()=>{fetches++;throw Error('stale response fetched state')},
 modRender:()=>{},resetModCollectionDetail:()=>{},notice:()=>{},fail:error=>{throw error}};
vm.createContext(ctx);
vm.runInContext(body+';this.select=id=>{fieldGuideSelection=id};this.save=saveFieldGuideLevel;this.switchProfile=setFieldGuideProfile;this.preview=()=>fieldGuidePreview;',ctx);
(async()=>{ctx.select('same-mod');const pending=ctx.save();ctx.switchProfile('new_player');ctx.select('same-mod');
 resolveSave({catalog_id:'same-mod',proposed_level:11});await pending;
 assert.equal(ctx.preview(),null);assert.equal(fetches,0);
 assert.deepEqual(ctx.state.field_guide_profiles.new_player.levels,{});
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result=subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parents[1],
                              text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.c=sqlite3.connect(Path(self.temp.name)/'fixture.sqlite3')
        self.c.row_factory=sqlite3.Row
        guide.ensure_schema(self.c)
        self.c.execute('CREATE TABLE inventory(id TEXT PRIMARY KEY, stats TEXT)')
        self.c.execute('INSERT INTO inventory VALUES(?,?)',('legacy-copy',json.dumps({'legacy_enhancement':12})))
        self.c.commit()

    def tearDown(self):
        self.c.close()
        self.temp.cleanup()

    def video(self,level,*,identity=ID,system='current_field_guide',ownership='unlocked',shiny='unknown'):
        return {'catalog_id':identity,'level':level,'ownership':ownership,'shiny_status':shiny,
                'source':{'mod_system':system,'frame':'frame.png','timestamp':11.0}}

    def test_empty_new_player_is_separate_from_personal_and_legacy(self):
        self.assertEqual(guide.profile(self.c,'new_player')['levels'],{})
        guide.set_manual(self.c,'personal',ID,11)
        self.assertEqual(guide.profile(self.c,'new_player')['levels'],{})
        self.assertEqual(guide.profile(self.c,'personal')['levels'][ID]['level'],11)
        self.assertEqual(json.loads(self.c.execute('SELECT stats FROM inventory').fetchone()[0]),
                         {'legacy_enhancement':12})

    def test_zero_means_not_unlocked_and_has_no_numeric_rows(self):
        saved=guide.set_manual(self.c,'new_player',ID,0)
        self.assertEqual(saved['decision'],'record_locked')
        self.assertEqual(saved['known_attributes'],[])
        self.assertEqual(guide.get(self.c,'new_player',ID)['level'],0)

    def test_official_level_tiers_do_not_fill_unknown_magnitudes(self):
        self.assertEqual([guide.rarity_for_level(level) for level in (0,1,3,5,7,9,17)],
                         ['not_unlocked','common','uncommon','rare','epic','legendary','legendary'])
        for level,expected in ((15,[5,4,4,2]),(16,[5,5,4,2]),(17,[5,5,5,2])):
            result=guide.preview(self.c,'new_player',ID,level)
            self.assertEqual(result['level_profile'],expected)
            self.assertGreater(result['unresolved_attribute_count'],0)
            self.assertEqual(result['tech_activation'],'unknown')
        self.assertEqual(guide.preview(self.c,'new_player',ID,11)['numeric_coverage'],'complete')

    def test_repeated_higher_and_stale_video_hovers_do_not_mutate_profile(self):
        guide.set_manual(self.c,'personal',ID,11)
        before=self.c.total_changes
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(11))['decision'],
                         'same_level_observation')
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(12))['decision'],
                         'higher_level_progression')
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(9))['decision'],
                         'stale_lower_level_observation')
        self.assertEqual(self.c.total_changes,before)
        self.assertEqual(guide.get(self.c,'personal',ID)['level'],11)

    def test_unknown_and_legacy_video_system_cannot_merge(self):
        for system in (None,'legacy_random_roll'):
            self.assertEqual(guide.preview_video(self.c,'personal',self.video(11,system=system))['decision'],
                             'source_system_needs_review')
        conflicting=self.video(11)
        conflicting['source_audit']={'mod_system':'legacy_backpack'}
        self.assertEqual(guide.preview_video(self.c,'personal',conflicting)['source_system'],'conflicting')
        self.assertEqual(guide.profile(self.c,'personal')['levels'],{})

    def test_suffixes_are_independent_progression_keys(self):
        guide.set_manual(self.c,'personal',ID,11)
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(13,identity=OTHER))['decision'],
                         'new_unlock')
        self.assertEqual(len(guide.profile(self.c,'personal')['levels']),1)

    def test_shiny_status_never_inferred_from_level(self):
        guide.set_manual(self.c,'personal',ID,17,'regular')
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(17,shiny='shiny'))['decision'],
                         'shiny_identity_needs_review')
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(17,shiny='regular'))['decision'],
                         'same_level_observation')
        self.assertEqual(guide.get(self.c,'personal',ID)['shiny_status'],'regular')

    def test_locked_video_card_never_becomes_owned(self):
        self.assertEqual(guide.preview_video(self.c,'personal',self.video(None,ownership='locked'))['decision'],
                         'locked_preview_not_owned')
        self.assertEqual(guide.profile(self.c,'personal')['levels'],{})

    def test_manual_correction_keeps_history_without_touching_legacy_copy(self):
        guide.set_manual(self.c,'personal',ID,13)
        result=guide.set_manual(self.c,'personal',ID,12)
        self.assertEqual(result['decision'],'lower_level_correction')
        self.assertEqual(self.c.execute('SELECT count(*) FROM field_guide_level_events').fetchone()[0],2)
        self.assertEqual(self.c.execute('SELECT count(*) FROM inventory').fetchone()[0],1)

    def test_reject_family_unknown_level_and_invalid_shiny(self):
        with self.assertRaises(ValueError):guide.preview(self.c,'personal','mod:weapon_mod:shock-rampage',9)
        with self.assertRaisesRegex(ValueError,'not verified as a current Field Guide'):
            guide.preview(self.c,'personal','mod:helmet_mod:fortunes-favor-crescent',9)
        for level in (-1,18,True,2.5):
            with self.assertRaises(ValueError):guide.preview(self.c,'personal',ID,level)
        with self.assertRaises(ValueError):guide.preview(self.c,'personal',ID,16,'shiny')
        with self.assertRaises(ValueError):guide.preview(self.c,'personal',ID,0,'regular')


if __name__=='__main__':unittest.main()
