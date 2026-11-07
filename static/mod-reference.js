/* Game Field Guide family navigation, read from Maurice's completed 2026-10-25
 * 04:01:49 recording (155.83s). This is display evidence only, never ownership.
 * Later frames show the fourth Bounce and Shrapnel family labels.
 */
const modReferenceSlotOrder=['weapon_mod','helmet_mod','chest_mod','pants_mod','boots_mod','gloves_mod','mask_mod'];
const modReferenceWeaponOrder={
 burn:['Flame Resonance','Embers','Blaze Blessing','Burning Wrath'],
 electric:['Shock Rampage','Shock Diffusion','Static Shock','Surge Amplifier'],
 frost:['Shattering Ice','Cryo Blast','Cryo Catalyst','Frosty Blessing'],
 bullseye:['Recover Mark',"Hunter's Perk",'Spreading Marks','Vulnerability Amplifier'],
 fortress_warfare:['United We Stand','Durable Territory','Portable Territory','Final Territory'],
 unstable_bomber:['Super Charged','Reckless Bomber','Bombardier Souvenir','Heavy Explosives'],
 fast_gunner:['Shoot Out','Precision Rush','Shooting Blitz','Cowboy'],
 bounce:['Super Bullet','Multi-Bounce','Boomerang Bullet','Bounce Rampage'],
 shrapnel:['Shatter Them All','Shrapnel Souvenir','Shrapnel Smash','Shield Breaker']
};
const modReferenceArmorOrder={
 helmet_mod:['Precise Strike','Deviation Expert','First-Move Advantage','Mag Expansion','Work of Proficiency',"Fortune's Favor",'Momentum Up','Elemental Havoc','Weapon Symphony','Quick Toss'],
 chest_mod:['Healing Fortification','Quick Comeback','Rejuvenating','Critical Rescue','Head-on Conflict','Head Guard','Resist Advantage','Enduring Shield','Status Immune','Ardent Shield'],
 pants_mod:['Critical Surge','Precision Load','Reload Rampage','Three Strikes','Bullet Siphon','Deadshot','Abnormal Increase','Melee Momentum','Distant Strike','Precision Charge','Elemental Resonance'],
 boots_mod:['Slow and Steady','Against All Odds','Covered Advance','Ruthless Reaper','Rush Hour','Ferocious Charge','Secluded Strike','Power of Striving'],
 gloves_mod:['Weapon Amplifier','Melee Amplifier','Crit Boost','Crit Amplifier','Weakspot DMG Boost','Lifeforce Boost','Flame Resonance','Elemental Overload','Turret Enhancement'],
 mask_mod:['Blaze Amplifier','Frost Construct','Explosive Shrapnel','Precision Bounce','Explosive Barrage','Pinpoint Strike','Targeted Strike','Thunderclap','Light Cannon','Unbreakable','Retrusion Explosion','Shrapnel Carnage','First Electrocution','Frostwave Wither','Most Wanted','Break Bounce','Blitzkrieg','Delayed Blast']
};
const modReferenceUnresolved={};
// Visible family-emblem pixels from Maurice's game recordings and Burn image.
// Family emblems are distinct from mechanic category icons and variant glyphs.
// Complete historical PNGs are used only where their full shapes match the
// visible current-game watermark; remaining recording crops stay partial.
const modReferenceFamilyArt={
 'weapon_mod|Shock Rampage':{
  path:'/artwork/family__weapon_mod__shock-rampage.png',
  source:'OhDex complete PNG; shape checked against Maurice game recording at 175s',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_drshcfglzj_d.png',partial:false
 },
 'weapon_mod|Shock Diffusion':{
  path:'/artwork/family__weapon_mod__shock-diffusion.png',
  source:'MetaForge July 2024 PNG; shape checked against Maurice game recording at 193s',source_url:'https://i0.wp.com/mmo-wiki.com/wp-content/uploads/2024/07/icon_mods_cbt2_jsdydwrd_d-1.png',partial:false
 },
 'weapon_mod|Static Shock':{
  path:'/artwork/family__weapon_mod__static-shock.png',
  source:'MetaForge July 2024 PNG; shape checked against Maurice game recording at 193s',source_url:'https://i0.wp.com/mmo-wiki.com/wp-content/uploads/2024/07/icon_mods_cbt2_dyzsdj_d.png',partial:false
 },
 'weapon_mod|Surge Amplifier':{
  path:'/artwork/family__weapon_mod__surge-amplifier.png',
  source:'OhDex complete PNG; lightning/star checked against Maurice game recording at 193s',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_dyycsjjsshts_d.png',partial:false
 },
 'weapon_mod|Embers':{path:'/artwork/family__weapon_mod__embers.png',source:'MetaForge July 2024 PNG; shape checked against Maurice game recording at 3s',source_url:'https://i0.wp.com/mmo-wiki.com/wp-content/uploads/2024/07/icon_mods_cbt2_zsbyc_d.png',partial:false},
 'weapon_mod|Blaze Blessing':{path:'/artwork/family__weapon_mod__blaze-blessing.png',source:'MetaForge July 2024 PNG; shape checked against Maurice game recording at 10s',source_url:'https://i0.wp.com/mmo-wiki.com/wp-content/uploads/2024/07/icon_mods_cbt2_jszshfsmz_d.png',partial:false},
 'weapon_mod|Burning Wrath':{path:'/artwork/family__weapon_mod__burning-wrath.png',source:'OhDex complete PNG; flame/chevrons checked against Maurice game recording',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_cfzsgldj_d.png',partial:false},
 'weapon_mod|Cryo Catalyst':{path:'/artwork/family__weapon_mod__cryo-catalyst.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:16,partial:true},
 'weapon_mod|Shattering Ice':{path:'/artwork/family__weapon_mod__shattering-ice.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:17,partial:true},
 'weapon_mod|Cryo Blast':{path:'/artwork/family__weapon_mod__cryo-blast.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:17,partial:true},
 'weapon_mod|Frosty Blessing':{path:'/artwork/family__weapon_mod__frosty-blessing.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:19,partial:true},
 'weapon_mod|Spreading Marks':{path:'/artwork/family__weapon_mod__spreading-marks.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:21,partial:true},
 'weapon_mod|Recover Mark':{path:'/artwork/family__weapon_mod__recover-mark.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:22,partial:true},
 'weapon_mod|Hunter\'s Perk':{path:'/artwork/family__weapon_mod__hunter-s-perk.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:22,partial:true},
 'weapon_mod|Durable Territory':{path:'/artwork/family__weapon_mod__durable-territory.png',source:'Wikily 2026-09-07 complete icon; people/clock mark matched Maurice Fortress Warfare screenshot',source_url:'https://media.wikily.gg/38635074-e152-4473-98a4-078ff7685096/2026-09-07/5f9c9408-6c4d-4fb4-9f3d-ffde98b2e368-once-human-item-6a9789bea8e6a825b3a0.webp',partial:false,current_match:true},
 'weapon_mod|Portable Territory':{path:'/artwork/family__weapon_mod__portable-territory.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:24,partial:true},
 'weapon_mod|Final Territory':{path:'/artwork/family__weapon_mod__final-territory.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:24,partial:true},
 'weapon_mod|United We Stand':{path:'/artwork/family__weapon_mod__united-we-stand.png',source:'Wikily 2026-09-07 complete icon; people/star mark matched Maurice Fortress Warfare screenshot',source_url:'https://media.wikily.gg/38635074-e152-4473-98a4-078ff7685096/2026-09-07/5f377eb0-fb44-420f-b680-2c3f209cf0d2-once-human-item-6cc0f2c47795b9a6a1c1.webp',partial:false,current_match:true},
 'weapon_mod|Super Charged':{path:'/artwork/family__weapon_mod__super-charged.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:27,partial:true},
 'weapon_mod|Reckless Bomber':{path:'/artwork/family__weapon_mod__reckless-bomber.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:27,partial:true},
 'weapon_mod|Heavy Explosives':{path:'/artwork/family__weapon_mod__heavy-explosives.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:28,partial:true},
 'weapon_mod|Shooting Blitz':{path:'/artwork/family__weapon_mod__shooting-blitz.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:31,partial:true},
 'weapon_mod|Cowboy':{path:'/artwork/family__weapon_mod__cowboy.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:32,partial:true},
 'weapon_mod|Shoot Out':{path:'/artwork/family__weapon_mod__shoot-out.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:34,partial:true},
 'weapon_mod|Precision Rush':{path:'/artwork/family__weapon_mod__precision-rush.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:34,partial:true},
 'weapon_mod|Super Bullet':{path:'/artwork/family__weapon_mod__super-bullet.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:35,partial:true},
 'weapon_mod|Multi-Bounce':{path:'/artwork/family__weapon_mod__multi-bounce.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:37,partial:true},
 'weapon_mod|Boomerang Bullet':{path:'/artwork/family__weapon_mod__boomerang-bullet.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:37,partial:true},
 'weapon_mod|Shrapnel Souvenir':{path:'/artwork/family__weapon_mod__shrapnel-souvenir.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:40,partial:true},
 'weapon_mod|Shrapnel Smash':{path:'/artwork/family__weapon_mod__shrapnel-smash.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:41,partial:true},
 'weapon_mod|Shatter Them All':{path:'/artwork/family__weapon_mod__shatter-them-all.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:42,partial:true},
 'helmet_mod|Fortune\'s Favor':{path:'/artwork/family__helmet_mod__fortune-s-favor.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:54,partial:true},
 'helmet_mod|Momentum Up':{path:'/artwork/family__helmet_mod__momentum-up.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:57,partial:true},
 'helmet_mod|Precise Strike':{path:'/artwork/family__helmet_mod__precise-strike.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:59,partial:true},
 'helmet_mod|Deviation Expert':{path:'/artwork/family__helmet_mod__deviation-expert.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:62,partial:true},
 'helmet_mod|Mag Expansion':{path:'/artwork/family__helmet_mod__mag-expansion.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:65,partial:true},
 'helmet_mod|Work of Proficiency':{path:'/artwork/family__helmet_mod__work-of-proficiency.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:66,partial:true},
 'helmet_mod|Elemental Havoc':{path:'/artwork/family__helmet_mod__elemental-havoc.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:69,partial:true},
 'helmet_mod|Weapon Symphony':{path:'/artwork/family__helmet_mod__weapon-symphony.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:71,partial:true},
 'helmet_mod|Quick Toss':{path:'/artwork/family__helmet_mod__quick-toss.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:72,partial:true},
 'chest_mod|Healing Fortification':{path:'/artwork/family__chest_mod__healing-fortification.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:76,partial:true},
 'chest_mod|Quick Comeback':{path:'/artwork/family__chest_mod__quick-comeback.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:79,partial:true},
 'chest_mod|Critical Rescue':{path:'/artwork/family__chest_mod__critical-rescue.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:83,partial:true},
 'chest_mod|Head-on Conflict':{path:'/artwork/family__chest_mod__head-on-conflict.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:85,partial:true},
 'chest_mod|Head Guard':{path:'/artwork/family__chest_mod__head-guard.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:87,partial:true},
 'chest_mod|Resist Advantage':{path:'/artwork/family__chest_mod__resist-advantage.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:88,partial:true},
 'chest_mod|Enduring Shield':{path:'/artwork/family__chest_mod__enduring-shield.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:90,partial:true},
 'chest_mod|Status Immune':{path:'/artwork/family__chest_mod__status-immune.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:91,partial:true},
 'chest_mod|Ardent Shield':{path:'/artwork/family__chest_mod__ardent-shield.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:93,partial:true},
 'pants_mod|Precision Load':{path:'/artwork/family__pants_mod__precision-load-native.png',source:'Once Human build 26267212 native icon icon_mods_cbt2_jzzt_d.png · mod family 9321',current_match:true,native_icon:true},
 'pants_mod|Reload Rampage':{path:'/artwork/family__pants_mod__reload-rampage.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:97,partial:true},
 'pants_mod|Three Strikes':{path:'/artwork/family__pants_mod__three-strikes.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:100,partial:true},
 'pants_mod|Bullet Siphon':{path:'/artwork/family__pants_mod__bullet-siphon.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:101,partial:true},
 'pants_mod|Deadshot':{path:'/artwork/family__pants_mod__deadshot.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:103,partial:true},
 'pants_mod|Abnormal Increase':{path:'/artwork/family__pants_mod__abnormal-increase.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:104,partial:true},
 'pants_mod|Melee Momentum':{path:'/artwork/family__pants_mod__melee-momentum.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:105,partial:true},
 'pants_mod|Distant Strike':{path:'/artwork/family__pants_mod__distant-strike.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:107,partial:true},
 'pants_mod|Precision Charge':{path:'/artwork/family__pants_mod__precision-charge.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:108,partial:true},
 'pants_mod|Critical Surge':{path:'/artwork/family__pants_mod__critical-surge.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:110,partial:true},
 'boots_mod|Against All Odds':{path:'/artwork/family__boots_mod__against-all-odds.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:113,partial:true},
 'boots_mod|Covered Advance':{path:'/artwork/family__boots_mod__covered-advance.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:116,partial:true},
 'boots_mod|Ruthless Reaper':{path:'/artwork/family__boots_mod__ruthless-reaper.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:117,partial:true},
 'boots_mod|Rush Hour':{path:'/artwork/family__boots_mod__rush-hour.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:119,partial:true},
 'boots_mod|Ferocious Charge':{path:'/artwork/family__boots_mod__ferocious-charge.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:121,partial:true},
 'boots_mod|Secluded Strike':{path:'/artwork/family__boots_mod__secluded-strike.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:122,partial:true},
 'boots_mod|Slow and Steady':{path:'/artwork/family__boots_mod__slow-and-steady.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:123,partial:true},
 'boots_mod|Power of Striving':{path:'/artwork/family__boots_mod__power-of-striving.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:125,partial:true},
 'gloves_mod|Weapon Amplifier':{path:'/artwork/family__gloves_mod__weapon-amplifier.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:128,partial:true},
 'gloves_mod|Crit Boost':{path:'/artwork/family__gloves_mod__crit-boost.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:129,partial:true},
 'gloves_mod|Crit Amplifier':{path:'/artwork/family__gloves_mod__crit-amplifier.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:130,partial:true},
 'gloves_mod|Lifeforce Boost':{path:'/artwork/family__gloves_mod__lifeforce-boost.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:133,partial:true},
 'gloves_mod|Flame Resonance':{path:'/artwork/family__gloves_mod__flame-resonance.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:134,partial:true},
 'gloves_mod|Melee Amplifier':{path:'/artwork/family__gloves_mod__melee-amplifier.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:136,partial:true},
 'gloves_mod|Elemental Overload':{path:'/artwork/family__gloves_mod__elemental-overload.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:137,partial:true},
 'mask_mod|Frostwave Wither':{path:'/artwork/family__mask_mod__frostwave-wither.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:139,partial:true},
 'mask_mod|Most Wanted':{path:'/artwork/family__mask_mod__most-wanted.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:139,partial:true},
 'mask_mod|Blaze Amplifier':{path:'/artwork/family__mask_mod__blaze-amplifier.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:141,partial:true},
 'mask_mod|Frost Construct':{path:'/artwork/family__mask_mod__frost-construct.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:141,partial:true},
 'mask_mod|Explosive Shrapnel':{path:'/artwork/family__mask_mod__explosive-shrapnel.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:143,partial:true},
 'mask_mod|Precision Bounce':{path:'/artwork/family__mask_mod__precision-bounce.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:144,partial:true},
 'mask_mod|Explosive Barrage':{path:'/artwork/family__mask_mod__explosive-barrage.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:145,partial:true},
 'mask_mod|Pinpoint Strike':{path:'/artwork/family__mask_mod__pinpoint-strike.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:145,partial:true},
 'mask_mod|Targeted Strike':{path:'/artwork/family__mask_mod__targeted-strike.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:145,partial:true},
 'mask_mod|Thunderclap':{path:'/artwork/family__mask_mod__thunderclap.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:146,partial:true},
 'mask_mod|Light Cannon':{path:'/artwork/family__mask_mod__light-cannon.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:146,partial:true},
 'mask_mod|Unbreakable':{path:'/artwork/family__mask_mod__unbreakable.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:147,partial:true},
 'mask_mod|Retrusion Explosion':{path:'/artwork/family__mask_mod__retrusion-explosion.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:147,partial:true},
 'mask_mod|Shrapnel Carnage':{path:'/artwork/family__mask_mod__shrapnel-carnage.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:147,partial:true},
 'mask_mod|First Electrocution':{path:'/artwork/family__mask_mod__first-electrocution.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:148,partial:true},
 'mask_mod|Break Bounce':{path:'/artwork/family__mask_mod__break-bounce.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:149,partial:true},
 'mask_mod|Blitzkrieg':{path:'/artwork/family__mask_mod__blitzkrieg.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:150,partial:true},
 'mask_mod|Delayed Blast':{path:'/artwork/family__mask_mod__delayed-blast.png',source:'screenrecording-2026-10-25_04-01-49.mp4',seconds:150,partial:true},
 "weapon_mod|Vulnerability Amplifier":{path:"/artwork/family__weapon_mod__vulnerability-amplifier.png",source:"screenrecording-2026-10-25_04-01-49.mp4",seconds:23.5,partial:true},
 "weapon_mod|Bombardier Souvenir":{path:"/artwork/family__weapon_mod__bombardier-souvenir.png",source:"screenrecording-2026-10-25_04-01-49.mp4",seconds:28.25,partial:true},
 "helmet_mod|First-Move Advantage":{path:"/artwork/family__helmet_mod__first-move-advantage.png",source:"screenrecording-2026-10-25_04-01-49.mp4",seconds:63.5,partial:true},
 "chest_mod|Rejuvenating":{path:"/artwork/family__chest_mod__rejuvenating.png",source:"screenrecording-2026-10-25_04-01-49.mp4",seconds:81.75,partial:true},
 "pants_mod|Elemental Resonance":{path:"/artwork/family__pants_mod__elemental-resonance.png",source:"screenrecording-2026-10-25_04-01-49.mp4",seconds:109.25,partial:true},
 "gloves_mod|Weakspot DMG Boost":{path:"/artwork/family__gloves_mod__weakspot-dmg-boost.png",source:"screenrecording-2026-10-25_04-01-49.mp4",seconds:132.75,partial:true},
 "gloves_mod|Turret Enhancement":{path:"/artwork/family__gloves_mod__turret-enhancement-native.png",source:"Once Human build 26267212 native icon icon_mods_cbt2_ptqh_d.png · mod family 9524",current_match:true,native_icon:true},
 "weapon_mod|Flame Resonance":{path:"/artwork/family__weapon_mod__flame-resonance.png",source:"MetaForge July 2024 PNG; shape checked against Maurice Weapon/Burn screenshot",source_url:"https://i0.wp.com/mmo-wiki.com/wp-content/uploads/2024/07/icon_mods_cbt2_zscxsj_d.png",partial:false}
};
const modReferenceAliases={
 'helmet_mod|First Move Advantage':'First-Move Advantage',
 'helmet_mod|Fortunes Favor':"Fortune's Favor",
 'helmet_mod|Work Of Proficiency':'Work of Proficiency',
 'chest_mod|Head On Conflict':'Head-on Conflict',
 'boots_mod|Slow And Steady':'Slow and Steady',
 'boots_mod|Power Of Striving':'Power of Striving',
 'gloves_mod|Weakspot Dmg Boost':'Weakspot DMG Boost',
 'weapon_mod|Multi Bounce':'Multi-Bounce'
};
// These two families only have historical spelling in the catalog. The video
// confirms the display name; retain the catalog IDs and show them in place.
const modReferenceOnlyAliasFamilies=new Set([
 'weapon_mod|Multi Bounce','boots_mod|Power Of Striving','boots_mod|Slow And Steady',
 'helmet_mod|First Move Advantage','helmet_mod|Work Of Proficiency',
 'chest_mod|Head On Conflict','gloves_mod|Weakspot Dmg Boost'
]);
function modReferenceFamily(entry){
 // The current Field Guide and current catalog both call this exact slug
 // Flame Resonance. The older catalog record's "Flame" family is preserved.
 if(entry.id==='mod:weapon_mod:flame-resonance-deviant-energy')return 'Flame Resonance';
 const name=entry.base_name||entry.tree||entry.name||'';
 return modReferenceAliases[`${entry.slot}|${name}`]||name;
}
function modReferenceVariant(entry){
 return entry.id==='mod:weapon_mod:flame-resonance-deviant-energy'?'Deviant Energy':entry.variant||'Base';
}
// The recording shows these glyph positions, but never opens their tooltip to
// confirm the older catalog's suffix spelling. Keep their catalog identities.
function modReferenceSuffixNeedsTooltip(entry){
 return (entry.id==='mod:boots_mod:slow-and-steady-resistance')||entry.slot==='weapon_mod'&&(
  (modReferenceFamily(entry)==='Spreading Marks'&&modReferenceVariant(entry)==='Common')||
  (modReferenceFamily(entry)==='Bombardier Souvenir'&&modReferenceVariant(entry)==='Violence')
 );
}
// Left-to-right order visible in the supplied Weapon/Burn screenshot and
// 2026-10-25 04:01:49 game recording (Power Surge around 12–15 seconds).
// This is presentation order only; levels and locks are not saved ownership.
const modReferenceWeaponVariantOrder={
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
// The Helmet grid in Maurice's 04:01:49 recording: ten families, 89 positions.
// The first N cards below had a level in that recording; the remaining cards
// carried the game's lock symbol at recording time. Neither is live ownership.
const modReferenceHelmetVariantOrder={
 'Precise Strike':['Violent','Precision','Deviant Energy','Survival','General','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Deviation Expert':['Violent','Survival','General','Precision','Deviant Energy','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'First-Move Advantage':['Violent','Deviant Energy','Survival','General','Precision','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Mag Expansion':['Deviant Energy','Precision','Violent','Survival','General','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Work of Proficiency':['Deviant Energy','Precision','Violent','Survival','General','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 "Fortune's Favor":['General','Violent','Deviant Energy','Survival','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Momentum Up':['Deviant Energy','Survival','General','Violent','Precision','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Elemental Havoc':['Precision','Deviant Energy','Violent','Survival','General','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Weapon Symphony':['Survival','General','Deviant Energy','Precision','Violent','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy'],
 'Quick Toss':['General','Violent','Precision','Survival','Deviant Energy','Lunar','Crescent','Lunar Deviant Energy','Crescent Deviant Energy']
};
const modReferenceHelmetRecordedLevels={
 'Precise Strike':4,'Deviation Expert':4,'First-Move Advantage':4,'Mag Expansion':5,
 'Work of Proficiency':4,"Fortune's Favor":4,'Momentum Up':3,'Elemental Havoc':4,
 'Weapon Symphony':5,'Quick Toss':4
};
// Top rows at 74–94s in the 04:01:49 recording: ten families, fourteen
// positions each. These are display positions, not owned instances or rolls.
const modReferenceTopVariantOrder={
 'Healing Fortification':['Battle','General','Deviant Energy','Violent','Precision','Lunar','Lunar Deviant Energy','Survival','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Quick Comeback':['Deviant Energy','Precision','Battle','Survival','General','Violent','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Rejuvenating':['Violent','Precision','General','Survival','Deviant Energy','Battle','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Critical Rescue':['Battle','Violent','General','Deviant Energy','Survival','Precision','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Head-on Conflict':['Precision','Violent','General','Battle','Deviant Energy','Lunar','Lunar Deviant Energy','Survival','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Head Guard':['Survival','Precision','Violent','Battle','Deviant Energy','General','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Resist Advantage':['Battle','Survival','General','Violent','Precision','Deviant Energy','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Enduring Shield':['Precision','General','Violent','Battle','Deviant Energy','Lunar','Lunar Deviant Energy','Survival','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Status Immune':['Precision','Survival','General','Violent','Deviant Energy','Battle','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Ardent Shield':['Precision','Survival','Deviant Energy','General','Violent','Battle','Lunar','Lunar Deviant Energy','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy']
};
const modReferenceTopRecordedLevels={
 'Healing Fortification':3,'Quick Comeback':5,'Rejuvenating':4,
 'Critical Rescue':5,'Head-on Conflict':4,'Head Guard':5,
 'Resist Advantage':5,'Enduring Shield':5,'Status Immune':6,'Ardent Shield':6
};
// Bottoms at 94–109s in the same recording: 118 positions, 60 level badges.
// Glyph order and source-time lock cues are presentation evidence only.
const modReferenceBottomsVariantOrder={
 'Critical Surge':['Precision','Resonance Deviant Energy','General','Downstar','Survival','Resonance','Aero','Violent','Deviant Energy','Downstar Deviant Energy','Aero Deviant Energy'],
 'Precision Load':['General','Violent','Precision','Deviant Energy','Resonance','Downstar','Resonance Deviant Energy','Downstar Deviant Energy','Survival','Aero','Aero Deviant Energy'],
 'Reload Rampage':['Survival','Aero Deviant Energy','Deviant Energy','Downstar','Downstar Deviant Energy','Precision','General','Violent','Resonance','Resonance Deviant Energy','Aero'],
 'Three Strikes':['Downstar Deviant Energy','Precision','Deviant Energy','General','Resonance Deviant Energy','Violent','Resonance','Downstar','Survival','Aero','Aero Deviant Energy'],
 'Bullet Siphon':['Violent','Deviant Energy','Aero Deviant Energy','Precision','Resonance Deviant Energy','Resonance','General','Downstar','Downstar Deviant Energy','Survival','Aero'],
 'Deadshot':['Violent','Resonance Deviant Energy','Downstar Deviant Energy','Precision','Resonance','Aero Deviant Energy','Deviant Energy','Survival','General','Downstar','Aero'],
 'Abnormal Increase':['Violent','Resonance','Precision','Resonance Deviant Energy','Deviant Energy','General','Downstar','Downstar Deviant Energy','Survival','Aero','Aero Deviant Energy'],
 'Melee Momentum':['Downstar','Resonance','Survival','Melee Default','Resonance Deviant Energy','Downstar Deviant Energy','Aero','Aero Deviant Energy'],
 'Distant Strike':['Resonance','Downstar','Survival','Deviant Energy','Resonance Deviant Energy','Aero','General','Violent','Precision','Downstar Deviant Energy','Aero Deviant Energy'],
 'Precision Charge':['Downstar Deviant Energy','General','Resonance','Violent','Precision','Aero','Deviant Energy','Downstar','Resonance Deviant Energy','Survival','Aero Deviant Energy'],
 'Elemental Resonance':['Violent','Deviant Energy','Resonance Deviant Energy','General','Precision','Resonance','Downstar','Downstar Deviant Energy','Survival','Aero','Aero Deviant Energy']
};
const modReferenceBottomsRecordedLevels={
 'Critical Surge':7,'Precision Load':0,'Reload Rampage':7,'Three Strikes':5,
 'Bullet Siphon':6,'Deadshot':9,'Abnormal Increase':5,'Melee Momentum':4,
 'Distant Strike':6,'Precision Charge':7,'Elemental Resonance':4
};
// Shoes at 109–128 s in the same recording: eight families, fourteen cards
// each. The game's 46/112 panel agrees with the level-badged prefixes below.
// "Resistance" is the older catalog label for the matching triangle glyph;
// its current tooltip spelling remains unverified.
const modReferenceShoesVariantOrder={
 'Slow and Steady':['Precision','Resistance','Violent','Deviant Energy','General','Downstar','Downstar Deviant Energy','Survival','Mirror','Wild','Phantasmal','Mirror Deviant Energy','Wild Deviant Energy','Phantasmal Deviant Energy'],
 'Against All Odds':['Downstar','Violent','Battle','Survival','Deviant Energy','Precision','General','Downstar Deviant Energy','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy'],
 'Covered Advance':['General','Downstar Deviant Energy','Violent','Deviant Energy','Survival','Downstar','Battle','Precision','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy'],
 'Ruthless Reaper':['Downstar','Precision','Violent','Deviant Energy','Survival','General','Battle','Downstar Deviant Energy','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy'],
 'Rush Hour':['Survival','Precision','Deviant Energy','Battle','Downstar','Downstar Deviant Energy','General','Violent','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy'],
 'Ferocious Charge':['Violent','Precision','Downstar','Battle','General','Deviant Energy','Downstar Deviant Energy','Survival','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy'],
 'Secluded Strike':['Downstar','Violent','Battle','Survival','Precision','Deviant Energy','General','Downstar Deviant Energy','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy'],
 'Power of Striving':['General','Violent','Deviant Energy','Downstar Deviant Energy','Precision','Battle','Downstar','Survival','Mirror','Wild','Phantasmal','Phantasmal Deviant Energy','Wild Deviant Energy','Mirror Deviant Energy']
};
const modReferenceShoesRecordedLevels={
 'Slow and Steady':5,'Against All Odds':6,'Covered Advance':7,'Ruthless Reaper':5,
 'Rush Hour':6,'Ferocious Charge':4,'Secluded Strike':7,'Power of Striving':6
};
// Gloves at 128–139 s: 96 positions in nine families. The game's 44/96
// progress agrees with the level-badged prefixes. These are source-time
// presentation observations, never live ownership or numeric evidence.
const modReferenceGlovesVariantOrder={
 'Weapon Amplifier':['Violent','Precision','Deviant Energy','Survival','Resonance','General','Crescent','Resonance Deviant Energy','Crescent Deviant Energy','Aero','Aero Deviant Energy'],
 'Melee Amplifier':['Melee Default','Resonance','Crescent','Resonance Deviant Energy','Crescent Deviant Energy','Survival','Aero','Aero Deviant Energy'],
 'Crit Boost':['Survival','Violent','Deviant Energy','General','Precision','Resonance Deviant Energy','Resonance','Crescent','Crescent Deviant Energy','Aero','Aero Deviant Energy'],
 'Crit Amplifier':['Deviant Energy','Survival','Violent','Precision','Resonance','Resonance Deviant Energy','General','Crescent','Crescent Deviant Energy','Aero Deviant Energy','Aero'],
 'Weakspot DMG Boost':['Precision','Survival','Deviant Energy','Violent','General','Resonance Deviant Energy','Resonance','Crescent','Crescent Deviant Energy','Aero','Aero Deviant Energy'],
 'Lifeforce Boost':['Violent','Deviant Energy','General','Survival','Precision','Resonance','Crescent','Resonance Deviant Energy','Crescent Deviant Energy','Aero','Aero Deviant Energy'],
 'Flame Resonance':['Violent','Precision','Resonance','General','Survival','Deviant Energy','Crescent','Resonance Deviant Energy','Crescent Deviant Energy','Aero','Aero Deviant Energy'],
 'Elemental Overload':['Precision','Survival','Violent','Resonance','Resonance Deviant Energy','General','Deviant Energy','Crescent','Crescent Deviant Energy','Aero','Aero Deviant Energy'],
 'Turret Enhancement':['General','Violent','Precision','Deviant Energy','Resonance','Crescent','Resonance Deviant Energy','Crescent Deviant Energy','Survival','Aero','Aero Deviant Energy']
};
const modReferenceGlovesRecordedLevels={
 'Weapon Amplifier':6,'Melee Amplifier':1,'Crit Boost':7,'Crit Amplifier':7,
 'Weakspot DMG Boost':6,'Lifeforce Boost':5,'Flame Resonance':5,
 'Elemental Overload':7,'Turret Enhancement':0
};
// Mask at 139–152s in the same recording: 18 families, 92 cards, 54
// level badges and 38 source-time locks. Pinpoint Strike and Delayed Blast
// have a sixth card that wraps beneath the first five.
const modReferenceMaskVariantOrder={
 'Blaze Amplifier':['General','Deviant Energy','Burn','Violent','Survival'],
 'Frost Construct':['Frost Vortex','General','Violent','Deviant Energy','Survival'],
 'Explosive Shrapnel':['Violent','General','Survival','Precision','Shrapnel'],
 'Precision Bounce':['Precision','General','Violent','Bounce','Survival'],
 'Explosive Barrage':['Precision','General','Fast Gunner','Violent','Survival'],
 'Pinpoint Strike':['General','Violent','Precision','Deviant Energy','Unstable Bomber','Survival'],
 'Targeted Strike':['Violent',"The Bull's Eye",'Precision','General','Survival'],
 Thunderclap:['Deviant Energy','General','Power Surge','Survival','Violent'],
 'Light Cannon':['Fortress Warfare','Violent','General','Precision','Survival'],
 Unbreakable:['Fortress Warfare','Violent','Survival','General','Precision'],
 'Retrusion Explosion':['Burn','Violent','Deviant Energy','Survival','General'],
 'Shrapnel Carnage':['Violent','General','Shrapnel','Precision','Survival'],
 'First Electrocution':['Power Surge','General','Survival','Violent','Deviant Energy'],
 'Frostwave Wither':['Violent','Deviant Energy','General','Frost Vortex','Survival'],
 'Most Wanted':["The Bull's Eye",'Survival','General','Precision','Violent'],
 'Break Bounce':['General','Violent','Precision','Bounce','Survival'],
 Blitzkrieg:['Violent','Fast Gunner','General','Precision','Survival'],
 'Delayed Blast':['Deviant Energy','Violent','General','Precision','Unstable Bomber','Survival']
};
const modReferenceMaskRecordedLevels={
 'Blaze Amplifier':3,'Frost Construct':2,'Explosive Shrapnel':4,
 'Precision Bounce':2,'Explosive Barrage':5,'Pinpoint Strike':1,
 'Targeted Strike':3,Thunderclap:5,'Light Cannon':3,Unbreakable:3,
 'Retrusion Explosion':4,'Shrapnel Carnage':3,'First Electrocution':5,
 'Frostwave Wither':2,'Most Wanted':4,'Break Bounce':1,Blitzkrieg:2,
 'Delayed Blast':2
};
// Source-time lock symbols in the nine Weapon groups of the 04:01:49 game
// recording. These are dated display observations, never current ownership.
const modReferenceWeaponRecordedLocks={
 'Flame Resonance':['Burn','Survival'],Embers:['Violent'],
 'Blaze Blessing':['Survival'],'Burning Wrath':['General','Survival'],
 'Shattering Ice':['Survival'],'Cryo Blast':['Frost Vortex','Survival'],
 'Recover Mark':['General',"The Bull's Eye",'Survival'],
 "Hunter's Perk":["The Bull's Eye",'Precision','Survival'],
 'Spreading Marks':['Survival'],
 'Vulnerability Amplifier':["The Bull's Eye",'Survival'],
 'United We Stand':['General'],'Durable Territory':['Precision','Survival'],
 'Portable Territory':['Survival'],'Final Territory':['Survival'],
 'Reckless Bomber':['General'],'Heavy Explosives':['Survival'],
 'Shoot Out':['General','Fast Gunner'],'Precision Rush':['Violent'],
 'Shooting Blitz':['Survival'],Cowboy:['Fast Gunner'],
 'Super Bullet':['Bounce'],'Multi-Bounce':['General'],
 'Boomerang Bullet':['Bounce'],'Bounce Rampage':['Violent']
};
function modReferenceSourceLocked(entry){
 const family=modReferenceFamily(entry);
 if(entry.slot==='weapon_mod')return (modReferenceWeaponRecordedLocks[family]||[]).includes(modReferenceVariant(entry));
 const order=entry.slot==='helmet_mod'?modReferenceHelmetVariantOrder[family]:
  entry.slot==='chest_mod'?modReferenceTopVariantOrder[family]:
  entry.slot==='pants_mod'?modReferenceBottomsVariantOrder[family]:
  entry.slot==='boots_mod'?modReferenceShoesVariantOrder[family]:
  entry.slot==='gloves_mod'?modReferenceGlovesVariantOrder[family]:
  entry.slot==='mask_mod'?modReferenceMaskVariantOrder[family]:null;
 if(!order)return false;
 const index=order.indexOf(modReferenceVariant(entry));
 const recorded=entry.slot==='helmet_mod'?modReferenceHelmetRecordedLevels[family]:
  entry.slot==='chest_mod'?modReferenceTopRecordedLevels[family]:
  entry.slot==='pants_mod'?modReferenceBottomsRecordedLevels[family]:
  entry.slot==='boots_mod'?modReferenceShoesRecordedLevels[family]:
  entry.slot==='gloves_mod'?modReferenceGlovesRecordedLevels[family]:
  modReferenceMaskRecordedLevels[family];
 return index>=recorded;
}
function modReferenceOrder(slot,goal='all'){
 if(slot==='weapon_mod')return goal==='all'?Object.values(modReferenceWeaponOrder).flat():modReferenceWeaponOrder[goal]||[];
 return modReferenceArmorOrder[slot]||[];
}
function modReferenceIsCurrent(entry){
 const name=entry.base_name||entry.tree||entry.name||'';
 const canonical=modReferenceFamily(entry);
 // A screenshot confirms the Violent glyph for Elemental Havoc. Keep the
 // older Violence spelling/ID in Other rather than duplicating one position.
 if(entry.id==='mod:helmet_mod:elemental-havoc-violence')return false;
 // Retain the older typo record in Other without duplicating Mirror's card.
 if(entry.id==='mod:boots_mod:secluded-strike-mrror')return false;
 // These older records describe a family effect, not a variant card in the
 // current Top grid. Retain them under Other for historical references.
 if((entry.slot==='chest_mod'||entry.slot==='pants_mod'||entry.slot==='gloves_mod'||entry.slot==='mask_mod')&&!entry.variant)return false;
 // An older Resonant variant has a different effect identity. The current
 // Crit Boost glyph is a separate unknown-effect catalog sighting.
 if(entry.id==='mod:gloves_mod:crit-boost-resonant-deviant-energy')return false;
 return modReferenceOrder(entry.slot,'all').includes(canonical)&&
  (name===canonical||entry.id==='mod:weapon_mod:flame-resonance-deviant-energy'||modReferenceOnlyAliasFamilies.has(`${entry.slot}|${name}`));
}
function modReferenceMatchesGoal(entry,goal){
 if(goal==='all')return true;
 return entry.slot==='weapon_mod'&&modReferenceOrder('weapon_mod',goal).includes(modReferenceFamily(entry));
}
function modReferenceSortRows(rows,goal='all'){
 return rows.sort((a,b)=>{
  const left=a.entry||a,right=b.entry||b;
  const slotA=modReferenceSlotOrder.indexOf(left.slot),slotB=modReferenceSlotOrder.indexOf(right.slot);
  if(slotA!==slotB)return (slotA<0?100:slotA)-(slotB<0?100:slotB);
  const order=modReferenceOrder(left.slot,goal),fa=modReferenceFamily(left),fb=modReferenceFamily(right);
  const ia=order.indexOf(fa),ib=order.indexOf(fb);
  if(ia!==ib)return (ia<0?1000:ia)-(ib<0?1000:ib);
  const variantOrder=fa===fb?(left.slot==='weapon_mod'?modReferenceWeaponVariantOrder[fa]:left.slot==='helmet_mod'?modReferenceHelmetVariantOrder[fa]:left.slot==='chest_mod'?modReferenceTopVariantOrder[fa]:left.slot==='pants_mod'?modReferenceBottomsVariantOrder[fa]:left.slot==='boots_mod'?modReferenceShoesVariantOrder[fa]:left.slot==='gloves_mod'?modReferenceGlovesVariantOrder[fa]:left.slot==='mask_mod'?modReferenceMaskVariantOrder[fa]:null):null;
  if(variantOrder){
   const va=variantOrder.indexOf(modReferenceVariant(left)),vb=variantOrder.indexOf(modReferenceVariant(right));
   if(va!==vb)return (va<0?100:va)-(vb<0?100:vb);
  }
  return fa.localeCompare(fb)||modReferenceVariant(left).localeCompare(modReferenceVariant(right))||(left.id||'').localeCompare(right.id||'');
 });
}

// Complete named-slot source candidates replace label-obscured screen fragments.
// Their current-game identity remains unverified until hidden details can be
// compared with a clear capture; the browser displays that state.
Object.assign(modReferenceFamilyArt,{
 "weapon_mod|Shattering Ice":{path:"/artwork/family__weapon_mod__shattering-ice.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bsxwshtg_d.png",partial:false,current_match:false},
 "weapon_mod|Cryo Blast":{path:"/artwork/family__weapon_mod__cryo-blast.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bsxwshcxtg_d.png",partial:false,current_match:false},
 "weapon_mod|Frosty Blessing":{path:"/artwork/family__weapon_mod__frosty-blessing.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bsxwxshfsmz_d.png",partial:false,current_match:false},
 "weapon_mod|Spreading Marks":{path:"/artwork/family__weapon_mod__spreading-marks.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_lrbjks_d.png",partial:false,current_match:false},
 "weapon_mod|Recover Mark":{path:"/artwork/family__weapon_mod__recover-mark.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_lrbjhf_d.png",partial:false,current_match:false},
 "weapon_mod|Hunter's Perk":{path:"/artwork/family__weapon_mod__hunter-s-perk.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_jsbbjmbjssh_d.png",partial:false,current_match:false},
 "weapon_mod|Durable Territory":{path:"/artwork/family__weapon_mod__durable-territory.png",source:"Wikily 2026-09-07 complete icon; people/clock mark matched Maurice Fortress Warfare screenshot",source_url:"https://media.wikily.gg/38635074-e152-4473-98a4-078ff7685096/2026-09-07/5f9c9408-6c4d-4fb4-9f3d-ffde98b2e368-once-human-item-6a9789bea8e6a825b3a0.webp",partial:false,current_match:true},
 "weapon_mod|Portable Territory":{path:"/artwork/family__weapon_mod__portable-territory.png",source:"OhDex named-slot catalog; current-game Fortress Warfare recording at 24-26s shows a target-and-clock silhouette that does not match this launcher-and-arc candidate",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zzzdzybl_d.png",partial:false,current_match:"mismatch"},
 "weapon_mod|Final Territory":{path:"/artwork/family__weapon_mod__final-territory.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zzzdwshd_d.png",partial:false,current_match:false},
 "weapon_mod|United We Stand":{path:"/artwork/family__weapon_mod__united-we-stand.png",source:"Wikily 2026-09-07 complete icon; people/star mark matched Maurice Fortress Warfare screenshot",source_url:"https://media.wikily.gg/38635074-e152-4473-98a4-078ff7685096/2026-09-07/5f377eb0-fb44-420f-b680-2c3f209cf0d2-once-human-item-6cc0f2c47795b9a6a1c1.webp",partial:false,current_match:true},
 "weapon_mod|Super Charged":{path:"/artwork/family__weapon_mod__super-charged.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_cfbdshdj_d.png",partial:false,current_match:false},
 "weapon_mod|Reckless Bomber":{path:"/artwork/family__weapon_mod__reckless-bomber.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bdmzts_d.png",partial:false,current_match:false},
 "weapon_mod|Heavy Explosives":{path:"/artwork/family__weapon_mod__heavy-explosives.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bdzsj_d.png",partial:false,current_match:false},
 "weapon_mod|Shooting Blitz":{path:"/artwork/family__weapon_mod__shooting-blitz.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_kqscxsj_d.png",partial:false,current_match:false},
 "weapon_mod|Cowboy":{path:"/artwork/family__weapon_mod__cowboy.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_kchdcf_d.png",partial:false,current_match:false},
 "weapon_mod|Shoot Out":{path:"/artwork/family__weapon_mod__shoot-out.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_kqsht_d.png",partial:false,current_match:false},
 "weapon_mod|Precision Rush":{path:"/artwork/family__weapon_mod__precision-rush.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_kqscxsjjztsrdts_d.png",partial:false,current_match:false},
 "weapon_mod|Super Bullet":{path:"/artwork/family__weapon_mod__super-bullet.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_tsbj_d.png",partial:false,current_match:false},
 "weapon_mod|Multi-Bounce":{path:"/artwork/family__weapon_mod__multi-bounce.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_tsyxmz_d.png",partial:false,current_match:false},
 "weapon_mod|Boomerang Bullet":{path:"/artwork/family__weapon_mod__boomerang-bullet.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_tsjshfzd_d.png",partial:false,current_match:false},
 "weapon_mod|Shrapnel Souvenir":{path:"/artwork/family__weapon_mod__shrapnel-souvenir.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_sdmztsshjd_d.png",partial:false,current_match:false},
 "weapon_mod|Shrapnel Smash":{path:"/artwork/family__weapon_mod__shrapnel-smash.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_sdbjtsrdjd_d.png",partial:false,current_match:false},
 "weapon_mod|Shatter Them All":{path:"/artwork/family__weapon_mod__shatter-them-all.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/meme_cbt2_icon_skill_sdshts_big.png",partial:false,current_match:false},
 "helmet_mod|Momentum Up":{path:"/artwork/family__helmet_mod__momentum-up.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_hlzj_d.png",partial:false,current_match:false},
 "helmet_mod|Precise Strike":{path:"/artwork/family__helmet_mod__precise-strike.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_jzdj_d.png",partial:false,current_match:false},
 "helmet_mod|Deviation Expert":{path:"/artwork/family__helmet_mod__deviation-expert.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_ysyczsdj_d.png",partial:false,current_match:false},
 "helmet_mod|Mag Expansion":{path:"/artwork/family__helmet_mod__mag-expansion.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_my_d.png",partial:false,current_match:false},
 "helmet_mod|Work of Proficiency":{path:"/artwork/family__helmet_mod__work-of-proficiency.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_wzsyl_d.png",partial:false,current_match:false},
 "helmet_mod|Elemental Havoc":{path:"/artwork/family__helmet_mod__elemental-havoc.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_yscz_d.png",partial:false,current_match:false},
 "helmet_mod|Weapon Symphony":{path:"/artwork/family__helmet_mod__weapon-symphony.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_wqjx_d.png",partial:false,current_match:false},
 "helmet_mod|Quick Toss":{path:"/artwork/family__helmet_mod__quick-toss.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_szjx_d.png",partial:false,current_match:false},
 "chest_mod|Healing Fortification":{path:"/artwork/family__chest_mod__healing-fortification.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zlsh_d.png",partial:false,current_match:false},
 "chest_mod|Quick Comeback":{path:"/artwork/family__chest_mod__quick-comeback.png",source:"OhDex full emblem; syringe and three-round shape matched supplied Top tooltip at 12s (source SHA-256 0db2c1c0333fe68c898dca311deb66868343a2c7d5283518c92c067140751c41)",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_ysbc_d.png",reference_frame:"video-review/3eca1e237ab643989c03a1b9c767555d/tooltip-12-mod-chest-mod-quick-comeback-battle.png",partial:false,current_match:true},
 "chest_mod|Critical Rescue":{path:"/artwork/family__chest_mod__critical-rescue.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_jcfs_d.png",partial:false,current_match:false},
 "chest_mod|Head-on Conflict":{path:"/artwork/family__chest_mod__head-on-conflict.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_shjmjjl_d.png",partial:false,current_match:false},
 "chest_mod|Head Guard":{path:"/artwork/family__chest_mod__head-guard.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_tbshjm_d.png",partial:false,current_match:false},
 "chest_mod|Resist Advantage":{path:"/artwork/family__chest_mod__resist-advantage.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_hsxgts_d.png",partial:false,current_match:false},
 "chest_mod|Enduring Shield":{path:"/artwork/family__chest_mod__enduring-shield.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_qgshjm_d.png",partial:false,current_match:false},
 "chest_mod|Status Immune":{path:"/artwork/family__chest_mod__status-immune.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_ycbl_d.png",partial:false,current_match:false},
 "chest_mod|Ardent Shield":{path:"/artwork/family__chest_mod__ardent-shield.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_jdbh_d.png",partial:false,current_match:false},
 "pants_mod|Reload Rampage":{path:"/artwork/family__pants_mod__reload-rampage.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_cxbj_d.png",partial:false,current_match:false},
 "pants_mod|Three Strikes":{path:"/artwork/family__pants_mod__three-strikes.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_sbgs_d.png",partial:false,current_match:false},
 "pants_mod|Bullet Siphon":{path:"/artwork/family__pants_mod__bullet-siphon.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_dyhd_d.png",partial:false,current_match:false},
 "pants_mod|Deadshot":{path:"/artwork/family__pants_mod__deadshot.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bjkr_d.png",partial:false,current_match:false},
 "pants_mod|Abnormal Increase":{path:"/artwork/family__pants_mod__abnormal-increase.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_yszf_d.png",partial:false,current_match:false},
 "pants_mod|Melee Momentum":{path:"/artwork/family__pants_mod__melee-momentum.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_rbz_d.png",partial:false,current_match:false},
 "pants_mod|Precision Charge":{path:"/artwork/family__pants_mod__precision-charge.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_yjlzzwq_d.png",partial:false,current_match:false},
 "pants_mod|Critical Surge":{path:"/artwork/family__pants_mod__critical-surge.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bjyd_d.png",partial:false,current_match:false},
 "boots_mod|Against All Odds":{path:"/artwork/family__boots_mod__against-all-odds.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_njzy_d.png",partial:false,current_match:false},
 "boots_mod|Covered Advance":{path:"/artwork/family__boots_mod__covered-advance.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_yhbz_d.png",partial:false,current_match:false},
 "boots_mod|Ruthless Reaper":{path:"/artwork/family__boots_mod__ruthless-reaper.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zcsg_d.png",partial:false,current_match:false},
 "boots_mod|Rush Hour":{path:"/artwork/family__boots_mod__rush-hour.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_xxkr_d.png",partial:false,current_match:false},
 "boots_mod|Ferocious Charge":{path:"/artwork/family__boots_mod__ferocious-charge.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_shjcjjl_d.png",partial:false,current_match:false},
 "boots_mod|Secluded Strike":{path:"/artwork/family__boots_mod__secluded-strike.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_gagh_d.png",partial:false,current_match:false},
 "boots_mod|Slow and Steady":{path:"/artwork/family__boots_mod__slow-and-steady.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_wzwd_d.png",partial:false,current_match:false},
 "boots_mod|Power of Striving":{path:"/artwork/family__boots_mod__power-of-striving.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_jlzw_d.png",partial:false,current_match:false},
 "gloves_mod|Crit Boost":{path:"/artwork/family__gloves_mod__crit-boost.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bjlts_d.png",partial:false,current_match:false},
 "gloves_mod|Crit Amplifier":{path:"/artwork/family__gloves_mod__crit-amplifier.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bjsh_d.png",partial:false,current_match:false},
 "gloves_mod|Lifeforce Boost":{path:"/artwork/family__gloves_mod__lifeforce-boost.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_smbfbjc_d.png",partial:false,current_match:false},
 "gloves_mod|Melee Amplifier":{path:"/artwork/family__gloves_mod__melee-amplifier.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_jzshjc_d.png",partial:false,current_match:false},
 "gloves_mod|Elemental Overload":{path:"/artwork/family__gloves_mod__elemental-overload.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_gzshts_d.png",partial:false,current_match:false},
 "mask_mod|Most Wanted":{path:"/artwork/family__mask_mod__most-wanted.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_mcbjzjsh_d.png",partial:false,current_match:false},
 "mask_mod|Blaze Amplifier":{path:"/artwork/family__mask_mod__blaze-amplifier.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/meme_cbt2_icon_skill_zs_xgts_big.png",partial:false,current_match:false},
 "mask_mod|Frost Construct":{path:"/artwork/family__mask_mod__frost-construct.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bsxwshtg_d.png",partial:false,current_match:false},
 "mask_mod|Explosive Shrapnel":{path:"/artwork/family__mask_mod__explosive-shrapnel.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/meme_cbt2_icon_skill_sdsjjd_big.png",partial:false,current_match:false},
 "mask_mod|Precision Bounce":{path:"/artwork/family__mask_mod__precision-bounce.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_tsyxmz_d.png",partial:false,current_match:false},
 "mask_mod|Explosive Barrage":{path:"/artwork/family__mask_mod__explosive-barrage.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_kqsewxhzdshts_d.png",partial:false,current_match:false},
 "mask_mod|Pinpoint Strike":{path:"/artwork/family__mask_mod__pinpoint-strike.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bdmzts_d.png",partial:false,current_match:false},
 "mask_mod|Targeted Strike":{path:"/artwork/family__mask_mod__targeted-strike.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_lrbjbj_d.png",partial:false,current_match:false},
 "mask_mod|Thunderclap":{path:"/artwork/family__mask_mod__thunderclap.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zhtl_d.png",partial:false,current_match:false},
 "mask_mod|Light Cannon":{path:"/artwork/family__mask_mod__light-cannon.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zzzdtlsc_d.png",partial:false,current_match:false},
 "mask_mod|Unbreakable":{path:"/artwork/family__mask_mod__unbreakable.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zzzdwshd_d.png",partial:false,current_match:false},
 "mask_mod|Retrusion Explosion":{path:"/artwork/family__mask_mod__retrusion-explosion.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_zscxsj_d.png",partial:false,current_match:false},
 "mask_mod|Shrapnel Carnage":{path:"/artwork/family__mask_mod__shrapnel-carnage.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_sdmzrd_d.png",partial:false,current_match:false},
 "mask_mod|First Electrocution":{path:"/artwork/family__mask_mod__first-electrocution.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_dyzsdj_d.png",partial:false,current_match:false},
 "mask_mod|Break Bounce":{path:"/artwork/family__mask_mod__break-bounce.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_tsmbsl_d.png",partial:false,current_match:false},
 "mask_mod|Blitzkrieg":{path:"/artwork/family__mask_mod__blitzkrieg.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_kqsewxhzdshts_d.png",partial:false,current_match:false},
 "mask_mod|Delayed Blast":{path:"/artwork/family__mask_mod__delayed-blast.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bdshts_d.png",partial:false,current_match:false},
 "weapon_mod|Vulnerability Amplifier":{path:"/artwork/family__weapon_mod__vulnerability-amplifier.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_lrbjysxgzj_d.png",partial:false,current_match:false},
 "weapon_mod|Bombardier Souvenir":{path:"/artwork/family__weapon_mod__bombardier-souvenir.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_cfbdztdj_d.png",partial:false,current_match:false},
 "helmet_mod|First-Move Advantage":{path:"/artwork/family__helmet_mod__first-move-advantage.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_bjshjctxwq_d.png",partial:false,current_match:false},
 "chest_mod|Rejuvenating":{path:"/artwork/family__chest_mod__rejuvenating.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_ksfc_d.png",partial:false,current_match:false},
 "pants_mod|Elemental Resonance":{path:"/artwork/family__pants_mod__elemental-resonance.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_ysgm_d.png",partial:false,current_match:false},
 "gloves_mod|Weakspot DMG Boost":{path:"/artwork/family__gloves_mod__weakspot-dmg-boost.png",source:"OhDex named-slot catalog; current game detail obscured in supplied recording",source_url:"https://ohdex.gg/mods/icon_mods_cbt2_rdsh_d.png",partial:false,current_match:false}
});

// Six 2026 game-video names have complete public candidate symbols under
// earlier catalog names. Match by item ID and equipment slot, never by the
// visible name alone. The readable motif is a lead, not proof that every
// hidden line of the current-game emblem is identical.
Object.assign(modReferenceFamilyArt,{
 'weapon_mod|Cryo Catalyst':{path:'/artwork/family__weapon_mod__cryo-catalyst.png',source:'OhDex Vortex Multiplier · item 19404035 · All Weapons; ID/slot crosswalk, current-game detail unverified',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_bsxwzdsh_d.png',reference_url:'https://wikily.gg/once-human/mods/19404035/',candidate_item_id:19404035,partial:false,current_match:false},
 "helmet_mod|Fortune's Favor":{path:'/artwork/family__helmet_mod__fortune-s-favor.png',source:'OhDex Fateful Strike · item 19201165 · Helmet; ID/slot crosswalk, current-game detail unverified',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_bjlts_d.png',reference_url:'https://wikily.gg/once-human/mods/19201165/',candidate_item_id:19201165,partial:false,current_match:false},
 'pants_mod|Distant Strike':{path:'/artwork/family__pants_mod__distant-strike.png',source:'OhDex Unstoppable · item 19203175 · Bottoms; ID/slot crosswalk, current-game detail unverified',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_jjqmzd_d.png',reference_url:'https://wikily.gg/once-human/mods/19203175/',candidate_item_id:19203175,partial:false,current_match:false},
 'gloves_mod|Weapon Amplifier':{path:'/artwork/family__gloves_mod__weapon-amplifier.png',source:'OhDex Munitions Amplifier · item 19205165 · Gloves; ID/slot crosswalk, current-game detail unverified',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_sqshjc_d.png',reference_url:'https://wikily.gg/once-human/mods/19205165/',candidate_item_id:19205165,partial:false,current_match:false},
 'gloves_mod|Flame Resonance':{path:'/artwork/family__gloves_mod__flame-resonance.png',source:'OhDex Status Enhancement · item 19205155 · Gloves; ID/slot crosswalk, current-game detail unverified',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_ysyczsdj_d.png',reference_url:'https://wikily.gg/once-human/mods/19205155/',candidate_item_id:19205155,partial:false,current_match:false},
 'mask_mod|Frostwave Wither':{path:'/artwork/family__mask_mod__frostwave-wither.png',source:'OhDex Obliteration · item 19206245 · Mask; ID/slot crosswalk, current-game detail unverified',source_url:'https://ohdex.gg/mods/icon_mods_cbt2_bsxwyxsh_d.png',reference_url:'https://wikily.gg/once-human/mods/19206245/',candidate_item_id:19206245,partial:false,current_match:false}
});

// Named Shield Breaker base item 19401045 supplies this family emblem.
// Its current Field Guide emblem was not exposed clearly in the recording.
modReferenceFamilyArt['weapon_mod|Shield Breaker']={
  path:'/artwork/family__weapon_mod__shield-breaker.webp',
  source:'Wikily Shield Breaker base item 19401045; current-game detail unverified',
  source_url:'https://r2.wikily.gg/images/once-human/icons/icon_mods_cbt2_sdhdshts_d.webp',
  reference_url:'https://wikily.gg/once-human/mods/19401045/',
  candidate_item_id:19401045,partial:false,current_match:false
};
