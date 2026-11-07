# Deviant Forge — continuity handoff

This file is how the owner and Computer pick up without starting from scratch.
In the app: Updates → **Copy status for Computer**, paste into a Computer chat in the
"Deviant Forge" project. That text plus this file is the whole context.

## House rules (never break)
- Never modify Once Human game files, never touch the game process or its memory. Read only.
- Workspace 10 belongs to the game: never launch, move, focus or send input to windows there.
- Every DPS / best-build answer is a labeled **estimate** with a "not counted" list.
- `data/` (profile, mods, typed items, live game data) is never shipped in an update package.
- the owner installs updates himself from workspaces 1–9: `bash /tmp/install-forge-update.sh`
  (backs up, extracts, runs tests, restarts `deviant-forge.service`, prints an undo command).

## Where things live
- App: `~/Projects/once-human-advisor`, served at http://127.0.0.1:8765/forge (systemd user service `deviant-forge.service`).
- `gamedata/thgl_snapshot.json` — game data shipped with the app (weapons, armor, sets, mods from oncehuman.th.gl).
- `data/live/` — written by the Update button, survives app updates:
  - `thgl_snapshot.json` (+ `history/` up to 10 backups) — used instead of the shipped copy when newer.
  - `overrides.json` — foods / deviations typed in by hand, custom fights.
  - `seen.json` — first-seen date per item, `sources` (when each list was first read = baseline), verdicts (cool / wrong / not new), `repairs`.
  - `mentions.json` — which official post names which item (normalized names), with the post's scenario. Evidence for NEW! and scenario labels.
  - `names.json`, `news.json`, `updates.jsonl` (log), `last_report.json`, `icons/`.

## Code map
| File | Job |
|---|---|
| `forge.py` | Profile, inventory, optimizer (best build, top 10, upgrades), UI catalog, `reload_data()` |
| `forge_effects.py` | Effect text parser, stat buckets, `SCENARIOS` (fight types), uptime rules |
| `forge_extras.py` | Hand-written tables: foods/drinks, deviations, calibrations, mask hides, cradle, fight buffs |
| `forge_theory.py` | "Theoretical best" builds and next-magnitude-of-power ladder |
| `forge_crates.py` | Mod crate / Starchrom spending advisor |
| `forge_live.py` | Live data layer: active snapshot, overrides, NEW! tracking, verdicts |
| `forge_path.py` | Path to max: greedy step plan (gain per effort), ceilings, group-share targets (25/33/50%), background job, data/live/path_plan.json |
| `forge_devguide.py` | Plain-words guide for all 77 deviations (job, tag, tier, which rating matters) + keep_verdict(name, skill, activity); JS twin is devVerdict in forge.js |
| `forge_starter.py` | New-player plan when the profile owns no weapon: first legendary gun (day-one vs ceiling), free steps, Starchrom, mods to farm |
| `forge_update.py` | Update button: patch notes reader, th.gl refresh, plain-word diff, validation, swap/undo, impact, handoff text |
| `server.py` | HTTP API (`/api/forge/...`) |
| `static/forge.{html,js,css}` | UI (pages: build, weapons, armor, mods, crates, deviation & food, class, updates, later) |
| `tests/test_forge_optimizer.py` | Unit tests (run: `python3 -W ignore -m unittest tests.test_forge_optimizer`) |

## How the Update button works
1. Quick check (~20 s): reads official posts (oncehuman.game news/update and news/devBlog), tags lines
   (new weapon/armor/mod, balance, scenario, cradle), collects names, re-reads th.gl food/deviation name lists.
2. Full check (~5 min): also re-reads every weapon, armor and mod page on th.gl, builds a new snapshot.
3. Validation: rejected if any category count drops below 80 % or errors exceed max(8, 5 %); failed pages keep old data.
4. Swap: old snapshot backed up, new one active, caches cleared, builds re-run. **Undo** restores the previous one.
5. Report: plain words ("Magazine 35 → 25 (10 fewer bullets, -28.6%)"), new items, removed, "needs numbers",
   news highlights, impact on your best build / theory top 5 / top upgrade.
6. NEW! badges for 21 days, with Nice find / Looks wrong / Not new buttons for quality checking.

## What counts as NEW! (since 2026.11.05.2)
- Baseline per source: the first read of any list (th.gl snapshot, th.gl foods, th.gl deviations, app tables) is baseline, never NEW!.
- NEW! needs patch-note evidence: first seen after the baseline AND named in an official post (≤60 days older), or announced
  as new ("New Armor: X") in a patch note within 21 days / a dev blog within 35 days, or typed in / marked "It's new" by the owner.
- Items that show up on th.gl without any post are listed apart ("New to the data, not in patch notes"), no badge.
- Items named in a scenario post (title names the scenario, or the line does) get a scenario label (e.g. Isles of Abyss), new or not.
  Lone gun suffixes ("Corrosion") and deviation skins ("Director Fox - Vacation") are not counted as mentions.
- `fl.classify()` returns {new, data, scenario}; the UI gets new_marks / data_marks / scenario_marks.

## Known limits (be honest)
- th.gl can lag a patch by days; the patch-note reader flags announced items that aren't in the data yet.
- th.gl food pages have no buff numbers and deviation pages show "?%": new foods/deviations land on the
  "needs numbers" list for the owner to type in (Updates → Foods and deviations you typed in).
- Hand-written tables (foods, deviations, calibrations, cradle, scenarios) are flagged when patch notes mention them, never auto-changed.
- Brand-new mechanics (a new keyword, a new scaling rule) need code from Computer.
- New scenarios: add them under Updates → Custom fights (base fight type + buffs text); every planner follows.

## Check-in routine for Computer
1. Read the pasted status + this file. 2. Read `data/live/last_report.json` and `updates.jsonl` tail on the device (read only).
3. Confirm "wrong" / "not new" verdicts and typed numbers; move confirmed ones into `forge_extras.py`.
4. Add code for unmodeled mechanics, add tests, bump `APP_VERSION` in `forge_live.py`, package without `data/`, hand over the installer.

## Profile keys added in 2026-11
- `fresh` (bool): fresh-start test. Recorded game data (inventory table, field_guide_levels) is ignored. `start_fresh()` puts the real profile in table `forge_profile_saves`; `restore_profile()` brings back the latest. API: POST /api/forge/profile/fresh {starchrom}, /api/forge/profile/restore {id?}.
- `extras.equipped` {helmet|mask|top|gloves|bottoms|shoes|weapon: {name, variant, level}} = mods on the gear right now; they count as owned. `extras.equipped_weapon` = gun in hands (defaults to the only gun). `optimize()` returns `wearing` (dps now, best_dps, gain_pct, swaps).
- `extras.dev_owned` [{n, s, a}] = your deviations with Skill/Activity ratings (keep/toss list).
- `extras.group_share` {pct, dps} = your share of group damage from a real run (Path to max).
- Client: a save in flight is ignored when fresh/restore runs (profAction bumps editCount) so it can't overwrite them.

## Mods page = the game's Mods screen (since 2026.11.05.5)
- forge_modart.py builds `catalog["mod_art"]`: variant glyph per (slot|name|variant) from the classic app's static/artwork + artwork_manifest.json (821/821 covered; same-variant glyph fallback), family emblems, game tab order, game row order (from static/mod-reference.js recording), weapon family groups (Burn, Power Surge…).
- UI: tabs Weapon/Helmet/Top/Bottoms/Shoes/Gloves/Mask with owned/total; one row per mod; tiles colored by level like the game (classic fieldGuideRarity: ≤2 white, ≤4 green, ≤6 blue, ≤8 purple, else gold), locked = dark + lock. Tiles sorted like the game: owned by level desc, then locked by variant rank. Tap tile -> level picker 1–17 (adds or changes), "I don't have this one" removes. Search covers all slots. "Only mine" hides locked.

## Armor you own (since 2026.11.05.4)
- Profile key `armor_owned`: piece name -> {"stars": n}. Several pieces per slot allowed (e.g. two helmets from different sets). `armor` stays "what you WEAR" (one per slot).
- `forge.owned_armor(profile)` = armor_owned ∪ worn pieces (worn always counts as owned). `owned_set_slots`, `pieces_to_get(profile, combo)` -> (missing, owned_used).
- Set/combo upgrades cost only the missing pieces ("Wear 4-piece X (you own the pieces)" = 0 Starchrom). Owned key armor costs 0. forge_path `_assign_set` prefers owned pieces and their stars.
- UI (Armor page): set-card pieces toggle owned (gray dashed = not owned), side "Wear" button; "Armor you own · N pieces" list per slot with stars, Wear, ✕. Swapping/taking off a worn piece keeps it in owned (keepWornOwned). Removing ownership also takes it off.

## Profiles (3 named slots, since 2026.11.05.3)
- Tables in data/advisor.sqlite3: `forge_profile_slots(slot 1-3, name, saved, value)` and `forge_profile_meta(key, value)` with keys `active` (slot in use or null), `seeded`, `names`.
- forge.py: `profile_slots()`, `slot_action(action, slot, name)`. `save_profile` also writes into the slot in use, so it never goes stale.
- API: POST /api/forge/profile/slot {action: save|load|rename|clear, slot: 1-3, name}. State, fresh and restore responses carry `slots` {active, slots[]}.
- Load first stores the current profile in the slot being left and in forge_profile_saves ("before switching to X"). Delete (clear) refuses the slot in use and keeps a backup ("cleared slot N").
- Each slot is a full profile, including `fresh` (a new-player test ignores recorded game data). start_fresh sets active = null until the user saves it to a slot.
- First open seeds: slot 1 "My profile" = real profile (from the last backup if in fresh mode), slot 2 "Fresh start test" if in fresh mode, slot 3 empty.
- UI: "Profile: <name>" button in the top bar opens dialog #profDlg (Load / Save / Rename / Delete per slot, Delete asks "are you sure"). The fresh banner button is "Switch profile".
- Tests (ProfileSlotTests) run on a temp copy of the DB, never the real one.

## Changelog
- 2026.11.05.5 — Mods page rebuilt to match the game's Mods screen: same tabs and order, variant symbols, rarity colors by level, lock on missing ones, tap-to-set level.
- 2026.11.05.4 — Armor ownership: mark every piece you own (several per slot), stars per piece, Wear button, counts per slot, sidebar "Armor owned"; upgrades and Path to max charge only for pieces you don't own yet.
- 2026.11.05.3 — Three named profile slots with Load / Save / Rename / Delete, profile name in the top bar, lossless switching (tests switch back and forth and compare). Ships together with the 2026.11.05.2 NEW! fix.
- 2026.11.05.2 — NEW! fix: the first th.gl food/deviation list read had no baseline, so 291 old foods/deviations showed NEW!. Per-source baselines, a one-time repair of seen.json, patch-note evidence (mentions.json, backfilled on the next check), scenario labels (Isles of Abyss), DPS-first sorting with "affects DPS" / "no numbers yet" chips.
- 2026.11.05 — Update button (quick/full), plain-word change report, impact on builds, undo, NEW! badges with
  quality-check verdicts, custom fights for new scenarios, typed foods/deviations, Copy status for Computer, this handoff.
  Armor page hide panel now says which animal + breeding trait gives the recommended mask hide (`HIDE_ORIGIN` in forge_extras.py).
- Earlier (Nov 2026) — optimizer rewrite on th.gl data, community meta, Abyss with/without cradle, top-10 ranking,
  best foods, futuristic UI, weapon/gear pages, mod crate advisor, calibrations, mask hides, secondary weapon advice.
- 2026-11-05: Path to max page (forge_path.py) with group-share targets; deviations page rebuilt (job, role tag, tier, which number matters, filter chips, keep-or-toss list with duplicate check); fresh-start test + restore; new-player plan (forge_starter.py); mod collection view (families, search, gray until owned, type level); "Mod on it now" for every armor piece and the gun in hands, with "Your gear right now" + swap list on Best build; Save to profile button in the top bar; missing pictures fixed (mask hides from th.gl materials, key armor from Fandom wiki fallback, aliases in tools/import_thgl_icons.py).


## Mod hover card (2026.11.05.6)
- `GET /api/forge/mod_info?name&variant&level` → `forge.mod_info()`: main effect, variant, level, and the 4 lines with value, `counted` (In DPS / Not in DPS) and a note. Locked mods show Lv 17 numbers.
- Line math lives in `forge.mod_lines_eval(gm, names, tiers, vision)`, which `_mod_substats_impl` also uses, so the card and the optimizer always agree.
- Estimate constants: `MIRROR_BEHIND=0.1` (share of hits from behind), `WILD_NEAR=0.7` (share of time within 15m), `WILD_CLOSE_SHARE=0.4`. Survival lines (`SURVIVAL_WORDS`) are not counted.
- UI: desktop shows the card on mouse hover/focus (`gmTipShow/gmTipHide`, cached in `gmInfo`); touch shows it inside the level picker (`gmFillInline`).
- Changelog: 2026.11.05.6 — Mod hover card like the game tooltip with In DPS / Not in DPS per line; Mirror/Wild Firearm & Crit lines and Explosive now counted.
- 2026.11.05.7 — 4th-line rule confirmed from in-game tooltips (Rejuvenating Violent Lv15 = 15/4.8/9.6/3.0; Shock Rampage Power Surge Lv17 = 6/6/6/3.0): the all-DMG-Boost line caps at tier 2. No math change; the note now says confirmed.

## Best armor you own + live feedback (2026.11.05.8)
- `forge.best_owned_armor()` (called from `optimize`, result key `best_armor`): searches owned armor — every owned key armor (or none) × set combos (1 set; 2 sets 4+2/3+3/2+2/4+1/3+2; 3 sets 2+2+2) over the 8 most useful sets plus worn sets, highest-star pieces first. Each layout is scored with the current best mods (fast `evaluate`), the top 6 get a single-slot polish, then a full mod re-pick on the top 3 guns. About 0.7 s extra per save. Returns dps, gain_pct, same, armor{slot}, changes[], build.
- Set-effect parsing fixes in `forge_effects.parse_effect`: "Element DMG (Blaze, Frost, Shock, Blast) +8%" now counts per element (Shelterer 2pc); "... DMG dealt increases by +10%" now parses (Savior 2pc). `SAVIOR_SHIELD_UPTIME = 0.9` (estimate) is used for "while shielded" effects when Savior 3pc is worn.
- Best build page: "Your armor vs everything you own" — your worn armor with the best mod per piece, next to the best owned armor combo with a "Wear this armor" button (it clears "on it now" mods on swapped pieces).
- Armor page: each worn piece shows "Best from your collection" with an "I put it on" button (sets extras.equipped).
- Toast "Best build updated +X DPS" after any save that changes the best build's DPS.
- Changelog: 2026.11.05.8 — Best armor you own, best-mod-per-piece with I put it on, Best build updated toast; Shelterer 2pc and Savior 2pc now counted.
- 2026.11.05.9 — Armor mod tabs sort by the game's mod ID (`forge_modart.game_ids()` from gamedata/thgl_snapshot.json), which is how the game lists them; fixes Bottoms (Reload Rampage first, Critical Surge/Precision Load last), Shoes (Covered Advance first) and Gloves (Crit Boost first). Removed the made-up keyword filter chips on armor tabs; only the Weapon tab keeps its real game families.
- 2026.11.05.10 — "Which mod is on your X right now?" picker now uses the Mods screen layout (`renderEquipPicker`): game-order rows, rarity-colored variant tiles, weapon families, "Mods I have / All X mods" toggle, ON IT NOW + IN BUILD tags; tapping an owned tile puts it on at its level, tapping a locked tile asks the level (adds it to the collection and puts it on). Armor cards show a small rarity tile (`gmMini`) for the current and best mod. Gold tiles get rising ember dots (`.gm-spark`, off with prefers-reduced-motion).
- 2026.11.05.11 — th.gl's /db/mods index only lists 100 mods; `tools/import_thgl_gamedata.probe_missing_mods()` now checks ID gaps and a few IDs past each run. Added Shooting Blitz (mod_10903) and Cowboy (mod_10904) to gamedata/thgl_snapshot.json (102 mods). Full probe of every run found no others missing.
- 2026.11.05.12 — New Survivability page (`forge_survive.py`, GET /api/forge/survive, #/survive). Toughness = (HP + shield) ÷ damage that gets through; conditional DR weighted by fight uptime (UPTIME table). Hill-climb over owned armor + pruned mods per slot for "give up 5%", "give up 10%", "Immortal" and "free toughness"; ~9s for 292 mods / 63 armor, cached per profile. Added the Island Mod Selection Crate – Legendary (island_17: Precision Load / Turret Enhancement at Lv 17; crate "mods" filter).
- 2026.11.05.13 — 6,000-dust Mod Selection Crate matches the in-game menu (user screenshots): box per armor slot (Helmet / Upper Body / Gloves / Lower Body Module / Shoes) then "<Slot> – Violent/Precise/Survival/Deviant Energy" (no General, no Battle); weapon/mask via Non-Keyword / Keyword / Resonance suffix boxes. `menu_path()` adds the in-game click path to every pick.
- 2026.11.05.14 — Magazines. New forge_accessories.py (rifle/pistol/SR/LMG mags; confirmed vs estimate flags; dev blog Reload Efficiency numbers; tooltip overrides in profile.accessory_values). `evaluate` takes wstate.magazine_acc + reload_s, counts magazine_flat, and computes the reload cycle from calibration + magazine up front so "after reloading" effects (AUG zone) react. `magazine_choice()` scores every fitting mag on the exact build (DPS, ammo, reload, cycle, firing %, zone %) with a plain-language why; Best build picks the best owned mag (`pick_magazine`). Weapons tile: Magazine block (on gun, timed reload, unlocked mags). Rapid Shot AR reload fixed to +10% (gold blueprint tooltip). Recorded calibrations now count their rolled lines (Weapon DMG roll → attack, Elemental/Crit roll → bonus line).
- 2026.11.05.15 — Path to max vs ranking. Theory now adds Psi from outside armor (character sheet − armor Psi; `psi_bonus`/`theory_psi`), counts the Vulnerability Amplifier when marked, and picks a mask hide; before this the path could end above "#1 in the game". Path plan gains `routes`: up to 2 commit-to-a-top-gun plans (`route_to`, locked to that weapon) when the greedy path ends on a gun whose maxed number is >5% below a ranked gun; UI "Routes to the top of the ranking".
- 2026.11.05.16 — SN700 - Finale's [Reverb] modeled (`reverb_model`): trigger = weakspot + 40% of other hits, per-magazine stack DP (cap 4, cleared on reload), +1 Shrapnel part per stack, last bullet +5%/stack and re-triggers once per stack at 3+; Gas-tight Helmet single-part respected. Snipers get their own weakspot rate (`sniper_weakspot_rate`: profile extras.sniper_ws 0-100, default 2x fight rate capped 90%); Class & settings input; theory cache key includes it. Finale goes 37.8k -> ~137k theory (boss, marked, 70%).
- 2026.11.05.17 — Removed Quick Magazine and Expanded Magazine (old all-gun mags, not in the current shop). Assault rifles offer only Extended / Light / Amended Rifle Mag (user report from the in-game shop). Light Rifle Mag numbers are still an estimate (+13% Reload Efficiency) until a tooltip is recorded.
- 2026.11.06.01 — Gear coverage pass. New gamedata/supplement.json (items the game has but th.gl doesn't list; it never overrides th.gl): sets Blackstone Heat, Blackstone Cold and Snowland Rustic (17 pieces); weapon mods Munitions Amplifier, Crit Rate Enhancement, Crit DMG Enhancement and Status Enhancement (sourced from oncehub.de); mod name aliases (Unstoppable = Distant Strike, Fateful Strike = Fortune's Favor, Overflow = Mag Expansion, ...). Fixed a set-name collision that merged the Blackstone variants. Key armor now has 42 entries: 4 wrong names fixed (old names still map), and added Snowdrift Top (SKS - Pathfinder only), Wind Intepreter Cap, Ankh Mask, Bloodstained Tracker Boots, Gilded Gloves, plus utility pieces (not counted). Gas-tight Helmet changed from +150% to +120% (sources disagree). Blackstone Heat/Cold 4pc assumes a 20°C zone (+30% elemental). RaidZone sets not added. GearCoverageTests added.
- 2026.11.06.02 — Speed + Windows sharing. optimize() remembers its last answers (keyed by the profile plus the database, data/live and game-data file stamps), so reopening/refreshing the Best build page is instant until something changes; the server computes it in the background right after start; fe.mentioned_keywords is cached (~25% faster recalculation). Player data folder: forge.py and forge_live.py now honor OH_ADVISOR_DATA like server.py (default still data/). aug_blueprint_preview no longer crashes the app when the original recording frame is missing (shared copies). New forge_windows.py (Windows starter: data in %LOCALAPPDATA%\DeviantForge\data, one-time move of an in-folder data/, installs Pillow, opens the browser) and forge_updater.py (installs .zip/.tgz updates, refuses data/ and paths outside the app, backs up code + data first, keeps 5). Minimum Python 3.10 (checked by compiling and running on 3.10). SharingAndSpeedTests added.
- 2026.11.06.03 — Map + Cradle. New forge_cradle.py: maps (Isles of Abyss = no Cradle, official 3.1.1 notes; Manibus = official Jan 2025 override table, 5 rows x 5; Way of Winter = Game8 Oct 2024 list, unverified; other-with/without-Cradle). Overrides count only for the right weapon class / keyword / mark / deviation; utility and survival overrides and Super Anomaly bonuses are listed as not counted. profile.extras.map + extras.cradle ([{name, value}] or unset = suggested: best override per row for each weapon by real DPS). Tooltip values replace list values (per stack for stacking overrides). Abyss fight type never counts a Cradle. Theory ladder follows your profile map. No map set = old behavior (no Cradle). Settings UI: 'Your map and Cradle' card. Assumption: one override per row (sources don't say). CradleMapTests added.
- 2026.11.06.04 — Shiny mods. mod_edits[key].shiny (+ shiny_main, shiny_extra) only at level 17. Official dev blog: Shiny = same sub-stats as Lv 17, slightly higher main effect, plus an extra Shiny effect; per-mod values aren't in th.gl or any list, so the app counts the tooltip lines you type (main replaces the core text; extra is parsed as its own source). Shiny with no text = plain Lv 17 plus a 'Shiny bonus not counted' note. UI: Shiny box in the mod editor (editor stays open after picking 17), ✦ on tiles and best-build mod cards. Shiny tiles animate: rotating rainbow rim (@property --shiny-a), holo tint, light sweep, twinkling stars, pulsing icon glow; all still under prefers-reduced-motion. Theory ladder doesn't assume Shiny. ShinyModTests added.
- 2026.11.06.05 — Ranking shows mods. top_ladder rows carry mods [{slot,name,variant}] (weapon first, then armor slots) and key_armor. The Top 10 list shows a chip per mod; green ✓ + your level when you own that exact mod and variant.
- 2026.11.06.06 — Crates can aim at a top build. advise(aim='rank:N') (/api/forge/crate?aim=rank:N) measures gains on build #N of the Top 10 (its weapon at 6 stars and its sets, filled with the best mods you own for it via best_mods_for). Picks sorted by gain; the ranking's own mods get an 'in build #N' badge; a build mod you don't own at all is listed even at +0%. When nothing helps your current build, the result offers 'Open it for #1..#5'. UI: 'Open it for' select next to Slot/Level, plus a lineup panel (✓ level / missing). CrateAimTests added.
- 2026.11.06.07 — One real copy on Windows. Cause of 'update has none of the new things': forge_windows.py opened whatever Deviant Forge already answered on port 8765, so an old copy kept being shown. Now: VERSION file (forge_live.APP_VERSION reads it; sidebar shows 'App version'); /api/health returns version + app_dir; POST /api/shutdown (localhost only). Starter stops a running copy whose version/folder differ (shutdown, then netstat+taskkill for old builds without the endpoint, only after health says deviant-forge). New forge_install.py + 'INSTALL or UPDATE - double-click me.bat': installs to %LOCALAPPDATA%\DeviantForge\app (previous app kept in backups, 3 kept), never copies data/, migrates data once from the newest old unzipped copy (Desktop/Downloads/Documents/OneDrive, 3 deep), makes Desktop + Start menu shortcuts, writes an 'OLD COPY' note into old folders, starts the new one. Zip layout: top folder has only the installer .bat, the readme and app/. VersionTests added.
- 2026.11.06.08 — Updates from GitHub (public repo NightforgeLabs/deviant-forge). The app asks GitHub for the newest release a few seconds after starting (cached 6 h; Updates page has "check now"); if it's newer, a green bar says "Deviant Forge <ver> is ready" with What's new / Update now / Later. Nothing installs without the button. Update now downloads GitHub's code zip for the release tag (https://github.com/<repo>/archive/refs/tags/v<ver>.zip — no uploaded files needed; asset uploads are refused from Computer's sandbox) and checks it (CRC of every file, VERSION inside = release version, and a `sha256: <hex>` line in the release text if present); Windows: unpacks it (refusing data/ and unsafe paths), starts its installer with --auto, which stops this copy, backs up, installs and restarts; the open page reloads when the new version answers. Linux: repacks it as /tmp/forge-update.tgz (paths relative to the app, no windows/) and shows the install command. Off switch: DF_NO_UPDATE_CHECK=1. New: forge_appupdate.py, /api/app-update, POST /api/app-update/install (local only), tools/build_release.py (zip + tgz + SHA256SUMS + notes into dist/), tools/export_public.py (public copy without data/, research/, desktop/, home paths), windows/ (installer .bat, readme, Start .bat), player README.md (old one is TECHNICAL_README.md). tools/install-forge-update.sh finds its own app folder and refuses to run outside one. AppUpdateTests added.
  Release steps: bump VERSION; add a changelog line here; tests; `python3 tools/export_public.py <clone> --name <owner first name>`; commit + push; `gh release create v<VERSION> --title "Deviant Forge <VERSION>" --notes-file <player-facing notes>` (no assets). Optional: `python3 tools/build_release.py` makes the friendlier hand-shared Windows zip in dist/. Root "INSTALL or UPDATE - double-click me.bat" works from GitHub's zip (forge_install.py next to it) and from the hand-shared zip (app\\forge_install.py).
- 2026.11.06.09 — First working GitHub release. The updater downloads GitHub's code zip for the tag instead of uploaded release files (uploads are refused from Computer's sandbox), checks every file's CRC and that VERSION inside equals the release version; Linux repacks it into /tmp/forge-update.tgz. INSTALL .bat moved to the repo root and works from GitHub's zip or the hand-shared zip; the installer copies windows/Start Deviant Forge.bat into the app. Release v2026.11.06.08 on GitHub is superseded (its updater looked for uploaded files).
