"""Verify the video-backed presentation without changing saved inventory."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import catalog
import mod_rolls
import server


ROOT = Path(__file__).resolve().parents[1]


class GameVideoNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = (server.DATA, server.MEDIA, server.DB)
        server.DATA = Path(self.temp.name)
        server.MEDIA = server.DATA / 'media'
        server.DB = server.DATA / 'advisor.sqlite3'
        server.init()

    def tearDown(self):
        server.DATA, server.MEDIA, server.DB = self.old
        self.temp.cleanup()

    def test_family_only_gloves_record_has_no_invented_variant(self):
        entry = catalog.ENTRIES['mod:gloves_mod:flame-resonance']
        self.assertEqual(entry['slot'], 'gloves_mod')
        self.assertTrue(entry['family_only'])
        self.assertIsNone(entry['variant'])
        self.assertIsNone(entry['rarity'])
        self.assertIsNone(entry['primary_effect'])
        self.assertFalse(entry['structured_effects'])
        self.assertEqual(entry['source_video_timestamp_seconds'], 133)
        self.assertFalse(any(item.get('effects', {}).get('catalog_id') == entry['id']
                             for item in server.inventory()))
        gloves = next(item['id'] for item in catalog.ENTRIES.values()
                      if item['kind'] == 'armor' and item['slot'] == 'gloves')
        with self.assertRaisesRegex(ValueError, 'no verified selectable variant'):
            server.validate_planned_slots({'gloves': {'catalog_id': gloves,
                                                      'mod_id': entry['id'], 'mod_level': 1}})

    def test_gloves_variant_sightings_do_not_add_ownership_or_effects(self):
        ids = [f'mod:gloves_mod:flame-resonance-{suffix}' for suffix in
               ('violent', 'precision', 'resonance', 'general', 'survival',
                'deviant-energy', 'crescent', 'resonance-deviant-energy',
                'crescent-deviant-energy', 'aero', 'aero-deviant-energy')]
        ids.append('mod:gloves_mod:crit-boost-resonance-deviant-energy')
        listed = {e['id']: e for e in server.builder_catalog()['entries']}
        for identity in ids:
            entry = catalog.ENTRIES[identity]
            self.assertEqual(entry['slot'], 'gloves_mod')
            self.assertIsNone(entry['primary_effect'])
            self.assertFalse(entry['structured_effects'])
            self.assertEqual(entry['attribute_values_by_level'], {})
            self.assertEqual(listed[identity]['ownership'], 'unknown')
            self.assertIsNone(listed[identity]['available_level'])
            self.assertTrue(listed[identity]['artwork'].startswith('/artwork/mod__gloves_mod__'))
            self.assertIsNone(catalog.resolve(identity, 1)['verified_main_effect'])
            self.assertEqual(mod_rolls.equipped_build_modifiers(
                {'gloves': {'mod_id': identity, 'mod_level': 1}}, [])['modifiers'], [])
        self.assertEqual(server.personal_mods(), [])
        self.assertEqual(server.inventory(), [])

    def test_shrapnel_general_is_a_sighting_not_owned_or_calculable(self):
        identity = 'mod:weapon_mod:shrapnel-souvenir-general'
        entry = catalog.ENTRIES[identity]
        self.assertEqual((entry['name'], entry['variant'], entry['slot']),
                         ('Shrapnel Souvenir', 'General', 'weapon_mod'))
        self.assertEqual(entry['source_observed_level'], 12)
        self.assertEqual(entry['source_video_timestamp_seconds'], 41)
        self.assertIsNone(entry['primary_effect'])
        self.assertEqual(entry['structured_effects'], [])
        self.assertIsNone(entry['attribute_names'])
        self.assertEqual(entry['attribute_values_by_level'], {})
        resolved = catalog.resolve(identity, 12)
        self.assertIsNone(resolved['verified_main_effect'])
        self.assertIsNone(resolved['known_attributes'])
        self.assertTrue(any('core effect was not inspected' in note for note in resolved['unknowns']))
        listed = next(item for item in server.builder_catalog()['entries'] if item['id'] == identity)
        self.assertEqual(listed['ownership'], 'unknown')
        self.assertIsNone(listed['available_level'])
        self.assertEqual(listed['source_observed_level'], 12)
        self.assertEqual(server.personal_mods(), [])
        self.assertEqual(server.inventory(), [])
        selected = mod_rolls.equipped_build_modifiers(
            {'primary': {'mod_id': identity, 'mod_level': 12}}, [])
        self.assertEqual(selected['modifiers'], [])
        self.assertEqual(selected['unresolved'][0]['code'], 'owned_instance_missing')

    def test_mask_precision_bounce_general_is_sighting_not_legacy_effect_or_owned(self):
        identity = 'mod:mask_mod:precision-bounce-general'
        entry = catalog.ENTRIES[identity]
        self.assertEqual((entry['name'], entry['variant'], entry['slot']),
                         ('Precision Bounce', 'General', 'mask_mod'))
        self.assertEqual(entry['source_observed_level'], 7)
        self.assertEqual(entry['rarity'], 'epic')
        self.assertIsNone(entry['primary_effect'])
        self.assertFalse(entry['structured_effects'])
        self.assertEqual(entry['attribute_values_by_level'], {})
        self.assertIsNone(catalog.resolve(identity, 7)['verified_main_effect'])
        listed = next(e for e in server.builder_catalog()['entries'] if e['id'] == identity)
        self.assertEqual(listed['ownership'], 'unknown')
        self.assertIsNone(listed['available_level'])
        self.assertEqual(listed['source_observed_level'], 7)
        self.assertEqual(listed['artwork'], '/artwork/mod__mask_mod__precise-bounce-general.png')
        self.assertEqual(server.personal_mods(), [])
        self.assertEqual(server.inventory(), [])
        selected = mod_rolls.equipped_build_modifiers(
            {'mask': {'mod_id': identity, 'mod_level': 7}}, [])
        self.assertEqual(selected['modifiers'], [])
        self.assertEqual(selected['unresolved'][0]['code'], 'owned_instance_missing')
        self.assertEqual(catalog.ENTRIES['mod:mask_mod:precise-bounce-general']['name'],
                         'Precise Bounce')

    def test_precision_rush_general_is_video_sighting_not_legacy_effect_or_owned(self):
        identity = 'mod:weapon_mod:precision-rush-general'
        entry = catalog.ENTRIES[identity]
        self.assertEqual((entry['name'], entry['variant'], entry['slot']),
                         ('Precision Rush', 'General', 'weapon_mod'))
        self.assertEqual(entry['source_observed_level'], 11)
        self.assertEqual(entry['source_video_timestamp_seconds'], 30)
        self.assertIsNone(entry['primary_effect'])
        self.assertEqual(entry['structured_effects'], [])
        self.assertIsNone(entry['attribute_names'])
        self.assertEqual(entry['attribute_values_by_level'], {})
        self.assertIsNone(catalog.resolve(identity, 11)['verified_main_effect'])
        listed = next(item for item in server.builder_catalog()['entries'] if item['id'] == identity)
        self.assertEqual(listed['ownership'], 'unknown')
        self.assertIsNone(listed['available_level'])
        self.assertEqual(listed['source_observed_level'], 11)
        self.assertEqual(listed['artwork'], '/artwork/mod__weapon_mod__precise-rush-general.png')
        self.assertEqual(server.personal_mods(), [])
        self.assertEqual(server.inventory(), [])
        selected = mod_rolls.equipped_build_modifiers(
            {'primary': {'mod_id': identity, 'mod_level': 11}}, [])
        self.assertEqual(selected['modifiers'], [])
        self.assertEqual(selected['unresolved'][0]['code'], 'owned_instance_missing')

    def test_bottoms_sightings_are_separate_from_legacy_and_do_not_calculate(self):
        for identity, variant, level in (
            ('mod:pants_mod:precision-charge-general', 'General', 11),
            ('mod:pants_mod:elemental-resonance-deviant-energy-current', 'Deviant Energy', 10),
        ):
            entry = catalog.ENTRIES[identity]
            self.assertEqual((entry['slot'], entry['variant']), ('pants_mod', variant))
            self.assertEqual(entry['source_observed_level'], level)
            self.assertIsNone(entry['primary_effect'])
            self.assertFalse(entry['structured_effects'])
            resolved = catalog.resolve(identity, level)
            self.assertIsNone(resolved['verified_main_effect'])
            self.assertIsNone(resolved['known_attributes'])
            listed = next(row for row in server.builder_catalog()['entries']
                          if row['id'] == identity)
            self.assertEqual(listed['ownership'], 'unknown')
            self.assertIsNone(listed['available_level'])
            selected = mod_rolls.equipped_build_modifiers(
                {'bottoms': {'mod_id': identity, 'mod_level': level}}, [])
            self.assertEqual(selected['modifiers'], [])
            self.assertEqual(selected['unresolved'][0]['code'], 'owned_instance_missing')
        old = catalog.ENTRIES['mod:pants_mod:elemental-resonance-deviant-energy']
        self.assertEqual((old['name'], old['variant']),
                         ('Elemental', 'Resonance Deviant Energy'))
        self.assertEqual(server.personal_mods(), [])
        self.assertEqual(server.inventory(), [])

    def test_missing_mag_expansion_video_cards_are_catalog_only(self):
        for variant in ('lunar', 'crescent', 'lunar-deviant-energy',
                        'crescent-deviant-energy'):
            identity = f'mod:helmet_mod:mag-expansion-{variant}'
            entry = catalog.ENTRIES[identity]
            self.assertEqual(entry['slot'], 'helmet_mod')
            self.assertIn('lock cue visible', entry['source_observed_unlock_status'])
            self.assertIsNone(entry['rarity'])
            self.assertIsNone(entry['primary_effect'])
            self.assertFalse(entry['structured_effects'])
            self.assertIsNone(catalog.resolve(identity, 1)['verified_main_effect'])
            listed = next(item for item in server.builder_catalog()['entries']
                          if item['id'] == identity)
            self.assertEqual(listed['ownership'], 'unknown')
            self.assertIsNone(listed['available_level'])
            self.assertTrue(listed['artwork'].endswith('.png'))
            selected = mod_rolls.equipped_build_modifiers(
                {'helmet': {'mod_id': identity, 'mod_level': 1}}, [])
            self.assertEqual(selected['modifiers'], [])
            self.assertEqual(selected['unresolved'][0]['code'], 'owned_instance_missing')
        self.assertEqual(server.personal_mods(), [])
        self.assertEqual(server.inventory(), [])

    def test_bounce_and_shrapnel_have_every_visible_variant_identity(self):
        families = ('Super Bullet', 'Multi Bounce', 'Boomerang Bullet', 'Bounce Rampage',
                    'Shatter Them All', 'Shrapnel Souvenir', 'Shrapnel Smash', 'Shield Breaker')
        variants = {'Super Bullet', 'Multi Bounce', 'Boomerang Bullet', 'Bounce Rampage'}
        for family in families:
            found = {entry['variant'] for entry in catalog.ENTRIES.values()
                     if entry['kind'] == 'mod' and entry['slot'] == 'weapon_mod'
                     and entry['name'] == family and entry.get('variant')}
            expected = {'Bounce', 'General', 'Precision', 'Survival', 'Violent'} if family in variants else \
                {'General', 'Precision', 'Shrapnel', 'Survival', 'Violent'}
            self.assertEqual(found, expected, family)

    def test_live_catalog_follows_video_family_and_slot_order(self):
        fixture = json.dumps(server.builder_catalog()['entries'])
        picker_source = (ROOT / 'static/builder-character.js').read_text()
        group_source = picker_source[picker_source.index('function modFamilyGroups(rows){'):
                                     picker_source.index('function modFocusedHtml(){')]
        picker_source = picker_source[picker_source.index('function modPickerRows(){'):
                                      picker_source.index('function modRender(')]
        script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const context={};vm.createContext(context);
vm.runInContext(fs.readFileSync('static/mod-reference.js','utf8')+`
 this.ref={slots:modReferenceSlotOrder,weapon:modReferenceWeaponOrder,
 armor:modReferenceArmorOrder,family:modReferenceFamily,
 variant:modReferenceVariant,current:modReferenceIsCurrent,sort:modReferenceSortRows,
 helmetVariants:modReferenceHelmetVariantOrder,topVariants:modReferenceTopVariantOrder,
 bottomsVariants:modReferenceBottomsVariantOrder,shoesVariants:modReferenceShoesVariantOrder,
 glovesVariants:modReferenceGlovesVariantOrder,maskVariants:modReferenceMaskVariantOrder,
 sourceLocked:modReferenceSourceLocked};`,context);
const ref=context.ref,entries=JSON.parse(fs.readFileSync(0,'utf8')).filter(e=>e.kind==='mod');
assert.deepStrictEqual(Array.from(ref.slots),
 ['weapon_mod','helmet_mod','chest_mod','pants_mod','boots_mod','gloves_mod','mask_mod']);
for(const slot of ref.slots){
 const rows=entries.filter(e=>e.slot===slot&&ref.current(e));ref.sort(rows);
 const names=[...new Set(rows.map(ref.family))];
 const expected=slot==='weapon_mod'?Object.values(ref.weapon).flat():ref.armor[slot];
 assert.deepStrictEqual(names,Array.from(expected),slot+' family order');
 assert.strictEqual(names.length,new Set(names).size,slot+' duplicate heading');
}
for(const [goal,expected] of Object.entries(ref.weapon)){
 const rows=entries.filter(e=>e.slot==='weapon_mod'&&ref.current(e)&&expected.includes(ref.family(e)));
 ref.sort(rows,goal);
 assert.deepStrictEqual([...new Set(rows.map(ref.family))],Array.from(expected),goal+' order');
}
const recordedVariantOrder={
 'Flame Resonance':['Deviant Energy','General','Violent','Burn','Survival'],
 Embers:['General','Survival','Deviant Energy','Burn','Violent'],
 'Blaze Blessing':['Violent','Deviant Energy','General','Burn','Survival'],
 'Burning Wrath':['Deviant Energy','Violent','Burn','General','Survival'],
 'Shock Rampage':['Power Surge','Deviant Energy','Violent','Survival','General'],
 'Shock Diffusion':['General','Violent','Deviant Energy','Power Surge','Survival'],
 'Static Shock':['Power Surge','Violent','Deviant Energy','General','Survival'],
 'Surge Amplifier':['Power Surge','General','Violent','Deviant Energy','Survival']
 ,'Shattering Ice':['Deviant Energy','General','Violent','Frost Vortex','Survival']
 ,'Cryo Blast':['Deviant Energy','Violent','General','Frost Vortex','Survival']
 ,'Cryo Catalyst':['Frost Vortex','General','Violent','Deviant Energy','Survival']
 ,'Frosty Blessing':['Deviant Energy','General','Violent','Frost Vortex','Survival']
 ,'Recover Mark':['Violent',"The Bull's Eye",'General','Precision','Survival']
 ,"Hunter's Perk":['General','Violent',"The Bull's Eye",'Precision','Survival']
 ,'Spreading Marks':['Violent','Common',"The Bull's Eye",'Precision','Survival']
 ,'Vulnerability Amplifier':['General','Violent',"The Bull's Eye",'Precision','Survival']
 ,'United We Stand':['Fortress Warfare','Violent','Precision','Survival','General']
 ,'Durable Territory':['General','Fortress Warfare','Violent','Precision','Survival']
 ,'Portable Territory':['Violent','Precision','Fortress Warfare','General','Survival']
 ,'Final Territory':['General','Fortress Warfare','Violent','Precision','Survival']
 ,'Super Charged':['Violent','General','Precision','Deviant Energy','Unstable Bomber','Survival']
 ,'Reckless Bomber':['Violent','Precision','Deviant Energy','Unstable Bomber','Survival','General']
 ,'Bombardier Souvenir':['Precision','Violence','Survival','General','Unstable Bomber','Deviant Energy']
 ,'Heavy Explosives':['General','Deviant Energy','Violent','Precision','Unstable Bomber','Survival']
 ,'Shoot Out':['Violent','Precision','Survival','General','Fast Gunner']
 ,'Precision Rush':['General','Precision','Fast Gunner','Survival','Violent']
 ,'Shooting Blitz':['Violent','Fast Gunner','General','Precision','Survival']
 ,'Cowboy':['Violent','Precision','General','Survival','Fast Gunner']
};
for(const [family,expected] of Object.entries(recordedVariantOrder)){
 const variants=entries.filter(e=>e.slot==='weapon_mod'&&e.variant&&ref.current(e)&&ref.family(e)===family);
 ref.sort(variants);
 assert.deepStrictEqual(variants.map(ref.variant),expected,family+' recorded card order and coverage');
}
const multi=entries.find(e=>e.id==='mod:weapon_mod:multi-bounce-bounce');
const striving=entries.find(e=>e.id==='mod:boots_mod:power-of-striving-battle');
assert.strictEqual(ref.family(multi),'Multi-Bounce');assert(ref.current(multi));
assert.strictEqual(ref.family(striving),'Power of Striving');assert(ref.current(striving));
const legacy=entries.find(e=>e.slot==='helmet_mod'&&e.base_name==='Fateful Strike');
assert(legacy);assert(!ref.current(legacy));
const oldViolence=entries.find(e=>e.id==='mod:helmet_mod:elemental-havoc-violence');
assert(oldViolence&&!ref.current(oldViolence),'older Violence spelling retained outside current view');
const helmetRows=entries.filter(e=>e.slot==='helmet_mod'&&e.variant&&ref.current(e));
ref.sort(helmetRows);
assert.strictEqual(helmetRows.length,89,'all 89 source Helmet positions visible');
assert.strictEqual(helmetRows.filter(ref.sourceLocked).length,48,'video-time lock cues kept distinct');
for(const [family,expected] of Object.entries(ref.helmetVariants)){
 const actual=helmetRows.filter(e=>ref.family(e)===family).map(ref.variant);
 assert.deepStrictEqual(actual,Array.from(expected),family+' exact video card order');
}
assert(helmetRows.some(e=>e.id==='mod:helmet_mod:mag-expansion-crescent-deviant-energy'));
assert(helmetRows.some(e=>e.id==='mod:helmet_mod:work-of-proficiency-violent'));
assert(helmetRows.some(e=>e.id==='mod:helmet_mod:first-move-advantage-violent'));
const topRows=entries.filter(e=>e.slot==='chest_mod'&&ref.current(e));
ref.sort(topRows);
assert.strictEqual(topRows.length,140,'all 140 current Top positions visible');
assert.strictEqual(topRows.filter(ref.sourceLocked).length,92,'Top video lock cues are source-time only');
const topFirstSix={
 'Healing Fortification':['Battle','General','Deviant Energy','Violent','Precision','Lunar'],
 'Quick Comeback':['Deviant Energy','Precision','Battle','Survival','General','Violent'],
 'Rejuvenating':['Violent','Precision','General','Survival','Deviant Energy','Battle'],
 'Critical Rescue':['Battle','Violent','General','Deviant Energy','Survival','Precision'],
 'Head-on Conflict':['Precision','Violent','General','Battle','Deviant Energy','Lunar'],
 'Head Guard':['Survival','Precision','Violent','Battle','Deviant Energy','General'],
 'Resist Advantage':['Battle','Survival','General','Violent','Precision','Deviant Energy'],
 'Enduring Shield':['Precision','General','Violent','Battle','Deviant Energy','Lunar'],
 'Status Immune':['Precision','Survival','General','Violent','Deviant Energy','Battle'],
 'Ardent Shield':['Precision','Survival','Deviant Energy','General','Violent','Battle']
};
for(const [family,prefix] of Object.entries(topFirstSix)){
 const variants=topRows.filter(e=>ref.family(e)===family).map(ref.variant);
 assert.strictEqual(variants.length,14,family+' fourteen video positions');
 assert.deepStrictEqual(variants.slice(0,6),prefix,family+' source-backed first row');
 assert.deepStrictEqual(variants,Array.from(ref.topVariants[family]),family+' full wrap order');
}
const topLegacy=entries.find(e=>e.id==='mod:chest_mod:head-on-conflict');
assert(topLegacy&&!ref.current(topLegacy),'family-only historic Top record stays outside current grid');
assert(topRows.some(e=>e.id==='mod:chest_mod:head-on-conflict-precision'));
const bottomRows=entries.filter(e=>e.slot==='pants_mod'&&ref.current(e));
ref.sort(bottomRows);
assert.strictEqual(bottomRows.length,118,'all 118 current Bottoms positions visible');
assert.strictEqual(bottomRows.filter(ref.sourceLocked).length,58,'58 recording-time Bottoms lock cues');
assert.deepStrictEqual([...new Set(bottomRows.map(ref.family))],Array.from(ref.armor.pants_mod));
for(const [family,expected] of Object.entries(ref.bottomsVariants)){
 const actual=bottomRows.filter(e=>ref.family(e)===family).map(ref.variant);
 assert.deepStrictEqual(actual,Array.from(expected),family+' exact Bottoms card order');
}
const bottomSighting=bottomRows.find(e=>e.id==='mod:pants_mod:precision-charge-general');
assert(bottomSighting&&bottomSighting.ownership==='unknown'&&bottomSighting.available_level==null);
assert.strictEqual(bottomSighting.source_observed_level,11);
assert(!bottomSighting.effect&&bottomSighting.observed_numeric_levels.length===0);
const elementalDe=bottomRows.find(e=>e.id==='mod:pants_mod:elemental-resonance-deviant-energy-current');
assert(elementalDe&&ref.family(elementalDe)==='Elemental Resonance'&&elementalDe.source_observed_level===10);
assert(elementalDe.ownership==='unknown'&&elementalDe.available_level==null);
assert(!elementalDe.effect&&elementalDe.observed_numeric_levels.includes(15));
const shoesRows=entries.filter(e=>e.slot==='boots_mod'&&ref.current(e));
ref.sort(shoesRows);
assert.strictEqual(shoesRows.length,112,'all 112 current Shoes positions visible');
assert.strictEqual(shoesRows.filter(ref.sourceLocked).length,66,'66 recording-time Shoes lock cues');
assert.deepStrictEqual([...new Set(shoesRows.map(ref.family))],Array.from(ref.armor.boots_mod));
for(const [family,expected] of Object.entries(ref.shoesVariants)){
 const actual=shoesRows.filter(e=>ref.family(e)===family).map(ref.variant);
 assert.deepStrictEqual(actual,Array.from(expected),family+' exact Shoes card order');
}
const olderShoe=entries.find(e=>e.id==='mod:boots_mod:secluded-strike-mrror');
assert(olderShoe&&!ref.current(olderShoe),'historical typo remains outside current Shoes grid');
const resistance=shoesRows.find(e=>e.id==='mod:boots_mod:slow-and-steady-resistance');
assert(resistance&&resistance.ownership==='unknown','source glyph is not ownership evidence');
const glovesRows=entries.filter(e=>e.slot==='gloves_mod'&&ref.current(e));
ref.sort(glovesRows);
assert.strictEqual(glovesRows.length,96,'all 96 current Gloves positions visible');
assert.strictEqual(glovesRows.filter(ref.sourceLocked).length,52,'52 recording-time Gloves lock cues');
assert.deepStrictEqual([...new Set(glovesRows.map(ref.family))],Array.from(ref.armor.gloves_mod));
for(const [family,expected] of Object.entries(ref.glovesVariants)){
 const actual=glovesRows.filter(e=>ref.family(e)===family).map(ref.variant);
 assert.deepStrictEqual(actual,Array.from(expected),family+' exact Gloves card order');
}
assert(!glovesRows.some(e=>!e.variant),'family-only records are not variant cards');
assert(!glovesRows.some(e=>e.id==='mod:gloves_mod:crit-boost-resonant-deviant-energy'));
const glovesFlame=glovesRows.find(e=>e.id==='mod:gloves_mod:flame-resonance-violent');
const weaponFlame=entries.find(e=>e.id==='mod:weapon_mod:flame-resonance-violent');
assert(glovesFlame&&weaponFlame&&glovesFlame.slot!==weaponFlame.slot);
assert(glovesFlame.ownership==='unknown'&&glovesFlame.available_level==null&&glovesFlame.source_observed_level===13);
const maskRows=entries.filter(e=>e.slot==='mask_mod'&&ref.current(e));
ref.sort(maskRows);
assert.strictEqual(maskRows.length,92,'all 92 current Mask positions visible');
assert.strictEqual(maskRows.filter(ref.sourceLocked).length,38,'38 source-time Mask lock cues');
assert.deepStrictEqual([...new Set(maskRows.map(ref.family))],Array.from(ref.armor.mask_mod));
for(const [family,expected] of Object.entries(ref.maskVariants)){
 const actual=maskRows.filter(e=>ref.family(e)===family).map(ref.variant);
 assert.deepStrictEqual(actual,Array.from(expected),family+' exact Mask card order');
}
assert.strictEqual(maskRows.filter(e=>ref.family(e)==='Pinpoint Strike').length,6);
assert.strictEqual(maskRows.filter(e=>ref.family(e)==='Delayed Blast').length,6);
assert(!maskRows.some(e=>!e.variant),'historic family-only Mask records stay outside cards');
const maskSighting=maskRows.find(e=>e.id==='mod:mask_mod:precision-bounce-general');
assert(maskSighting&&maskSighting.source_observed_level===7&&!ref.sourceLocked(maskSighting));
assert(maskSighting.ownership==='unknown'&&maskSighting.available_level==null&&!maskSighting.effect);
assert(!maskRows.some(e=>e.id==='mod:mask_mod:precise-bounce-general'));
const oldElemental=entries.find(e=>e.id==='mod:pants_mod:elemental-resonance-deviant-energy');
assert(oldElemental&&!ref.current(oldElemental)&&ref.variant(oldElemental)==='Resonance Deviant Energy');
assert(!bottomRows.some(e=>e.id==='mod:pants_mod:precision-charge'));
assert(entries.find(e=>e.id==='mod:gloves_mod:flame-resonance').family_only);
context.builderData={entries};context.modCollectionMode=true;context.characterModView='all';
context.modReferenceScope='game';context.modSlotFilter='all';context.modSearch='';
context.characterModGoal='all';context.modTargetSlots={};
vm.runInContext(`function modOwnedInstances(){return []}
function modFamilyName(e){return modReferenceFamily(e)}
function modCategoryEntryMatches(){return true}
`+process.env.PICKER_SOURCE+`\nthis.rows=modPickerRows;`,context);
let shown=context.rows();let headings=[...new Set(shown.map(r=>r.entry.slot+'|'+ref.family(r.entry)))];
assert.strictEqual(headings.length,102,'all 102 readable headings appear once');
assert.deepStrictEqual(Array.from(ref.weapon.bounce),['Super Bullet','Multi-Bounce','Boomerang Bullet','Bounce Rampage']);
assert.deepStrictEqual(Array.from(ref.weapon.shrapnel),['Shatter Them All','Shrapnel Souvenir','Shrapnel Smash','Shield Breaker']);
assert(shown.some(r=>r.entry.id==='mod:gloves_mod:flame-resonance-violent'));
assert(!shown.some(r=>r.entry.base_name==='Fateful Strike'));
assert(!shown.some(r=>r.entry.id==='mod:helmet_mod:elemental-havoc-violence'));
context.modReferenceScope='other';let other=context.rows();
assert(other.some(r=>r.entry.base_name==='Fateful Strike'),'legacy entry retained');
assert(other.some(r=>r.entry.id==='mod:helmet_mod:elemental-havoc-violence'),'older spelling retained');
assert(other.some(r=>r.entry.id==='mod:chest_mod:head-on-conflict'),'Top family-only record retained');
assert(other.some(r=>r.entry.id==='mod:gloves_mod:flame-resonance'),'family-only reference retained outside the variant grid');
assert(other.some(r=>r.entry.id==='mod:mask_mod:precise-bounce-general'),'historical Mask spelling remains in Other');
context.modReferenceScope='game';context.modSlotFilter='weapon_mod';
const weaponRows=context.rows();assert.strictEqual(weaponRows.length,184);
assert.strictEqual(weaponRows.filter(r=>ref.sourceLocked(r.entry)).length,34,'all 34 Weapon source-time lock cues');
assert(ref.sourceLocked(weaponRows.find(r=>r.entry.id==='mod:weapon_mod:flame-resonance-burn').entry));
assert(ref.sourceLocked(weaponRows.find(r=>r.entry.id==='mod:weapon_mod:bounce-rampage-violent').entry));
assert(!ref.sourceLocked(weaponRows.find(r=>r.entry.id==='mod:weapon_mod:shock-rampage-power-surge').entry));
context.modSlotTabs=[['weapon_mod','Weapon']];context.characterModView='all';
vm.runInContext(`function esc(s){return String(s)}
function modVariantCard(row){return '<i data-mod-id="'+row.entry.id+'"></i>'}
`+process.env.GROUP_SOURCE+`\nthis.groups=modFamilyGroups;`,context);
const html=context.groups(weaponRows);
assert.strictEqual((html.match(/data-mod-id=/g)||[]).length,weaponRows.length,'every variant rendered');
assert(html.includes('data-mod-id="'+weaponRows.at(-1).entry.id+'"'),'last variant reachable');
assert(!html.includes('Show more'));
context.modSearch='Shock Diffusion';
const searched=context.rows();assert(searched.length>0&&searched.length<weaponRows.length);
assert(searched.every(row=>row.entry.name.toLowerCase().includes('shock diffusion')));
console.log('7 slots; 102 video families, 89 Helmet positions and 48 recording lock cues; picker and legacy archive verified');
'''
        import os
        result = subprocess.run(['node', '-e', script], cwd=ROOT, input=fixture,
                                text=True, capture_output=True,
                                env={**os.environ, 'PICKER_SOURCE': picker_source,
                                     'GROUP_SOURCE': group_source})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_horizontal_navigation_and_reference_sized_cards(self):
        script = (ROOT / 'static/builder-character.js').read_text()
        css = (ROOT / 'static/style.css').read_text()
        self.assertNotIn('showMoreMods', script)
        self.assertNotIn('modLimit', script)
        self.assertIn('modSlotTabs.filter(([key])=>key!==\'all\')', script)
        self.assertIn('weaponBrowse?`<nav class="mod-damage-rail"', script)
        self.assertIn('repeat(auto-fill,minmax(128px,136px))', css)
        self.assertIn('grid-template-rows:auto auto auto auto minmax(0,1fr)', css)
        self.assertIn('Locked in video · 10/25/26<br>', script)
        self.assertIn('const videoLocked=historicalLock&&!instance&&!locked&&!recordedUnlock', script)
        self.assertIn('.mod-variant-card.source-locked', css)

    def test_historical_lock_does_not_override_current_unlock_or_owned_instance(self):
        script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('static/builder-character.js','utf8');
const card=source.slice(source.indexOf('function modVariantCard(row){'),
                        source.indexOf('function modFamilyGroups(rows){'));
const context={modCollectionMode:true,modRecordsMode:true,modSharedSuffixGlyph:{},characterModView:'all',fieldGuideProfile:'personal',fieldGuideSelection:null,fieldGuideRecorded:()=>null,
  fieldGuideRarity:()=> 'legendary',
  characterPreviewId:null,characterSlot:'helmet',characterPreviewLevel:1,
  modRowLevel:()=>1,modLevelEditorId:null,
  esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;')};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/mod-reference.js','utf8')+card+';this.card=modVariantCard;',context);
const entry={id:'mod:helmet_mod:mag-expansion-lunar',name:'Mag Expansion Lunar',
  base_name:'Mag Expansion',slot:'helmet_mod',variant:'Lunar',rarity:'legendary',
  ownership:'unknown'};
const row={entry,target_slot:'helmet',instances:[]};
let html=context.card(row);
assert(html.includes('mod-video-lock-mark'));
assert(html.includes('Ownership unverified in this profile'));
assert(!html.includes('Locked in video · 10/25/26<br>'));
entry.ownership='unlocked';html=context.card(row);
assert(html.includes('mod-video-lock-mark'));
assert(html.includes('Ownership unverified in this profile'),'a source-time catalog unlock is not this profile ownership');
assert(!html.includes('mod-owned-mark'));
row.instances=[{id:'owned-a',level:11}];html=context.card(row);
assert(html.includes('mod-backpack-mark')&&!html.includes('mod-owned-mark'));
assert(html.includes('Existing mod record Lv 11; system unverified'));
assert(html.includes('>11</span>'),'the saved personal level stays visible');
assert(!html.includes('class="mod-variant-card legendary locked'));
assert(!html.includes('Owned now recorded'));
context.fieldGuideProfile='new_player';html=context.card(row);
assert(html.includes('Ownership unverified in new-player profile'));
assert(html.includes('>?</span>'),'a separate new-player profile remains unverified');
assert(!html.includes('mod-backpack-mark')&&!html.includes('mod-owned-mark'));
assert(!html.includes('Seen in video')&&!html.includes('Owned now recorded'));
context.fieldGuideProfile='personal';
row.instances=[];entry.ownership='locked';html=context.card(row);
assert(html.includes('mod-video-lock-mark')&&!html.includes('mod-owned-mark'));
context.fieldGuideRecorded=id=>id===entry.id?{level:9}:null;
html=context.card(row);
assert(html.includes('mod-owned-mark')&&!html.includes('mod-video-lock-mark'));
context.fieldGuideRecorded=()=>null;
const weapon={id:'mod:weapon_mod:flame-resonance-burn',name:'Flame Resonance Burn',
  base_name:'Flame Resonance',slot:'weapon_mod',variant:'Burn',rarity:'legendary',
  ownership:'unknown'};
html=context.card({entry:weapon,target_slot:'primary',instances:[]});
assert(html.includes('mod-video-lock-mark'));
weapon.ownership='unlocked';html=context.card({entry:weapon,target_slot:'primary',instances:[]});
assert(html.includes('mod-video-lock-mark')&&html.includes('Ownership unverified in this profile'));
const unknown={...entry,id:'mod:helmet_mod:mag-expansion-general',variant:'General',ownership:'unknown'};
html=context.card({entry:unknown,target_slot:'helmet',instances:[]});
assert(!html.includes('mod-video-lock-mark'));
'''
        result = subprocess.run(['node', '-e', script], cwd=ROOT, text=True,
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
