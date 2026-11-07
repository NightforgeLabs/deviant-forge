# Outgoing comparison: evidence and scope

The Compare page runs `outgoing.run_example()` through `/api/outgoing-example`. It compares two real boots mods in the current catalog. It never writes either choice to the confirmed inventory.

## Sourced game data

| Choice | Same-level native Field Guide tooltip | Resolved effects and attributes |
| --- | --- | --- |
| Against All Odds `<Precision>` Lv. 7 | [native crop 0091](data/media/b0aad7d457fd4e699605ae1f78d4ec51/frames/1b99d4a1dce94a8294f2459acf6303a7/0091.png) | Main: +10% Weapon and Status DMG, extra after HP consumption. Weakspot DMG +3.6%, Weapon DMG +2.4%, Magazine Capacity +4.8%, All DMG Boost +1.5%. |
| Power of Striving `<Downstar Deviant Energy>` Lv. 9 | [native crop 0094](data/media/b0aad7d457fd4e699605ae1f78d4ec51/frames/1b99d4a1dce94a8294f2459acf6303a7/0094.png) | Main: +10% Weapon and Status DMG, extra after stamina loss. Elemental DMG +4.8% with up to +2.4% elevation bonus, Status DMG +2.4% with up to +1.2% elevation bonus, All DMG Boost +3%, Max HP +2.4%. |

The [official September 2025 note](https://www.oncehuman.game/news/devBlog/20250922/40781_1260687.html) describes Against All Odds as Weapon/Status DMG with more after HP loss. The [official January 2025 preview](https://www.oncehuman.game/news/update/20250110/40780_1205980.html) describes Power of Striving's stamina trigger. The [official May 2026 note](https://www.oncehuman.game/news/devBlog/20260522/40781_1301328.html) defines Downstar's elevation relationship. The [official Field Guide explanation](https://www.oncehuman.game/news/devBlog/20251212/40781_1276354.html) supplies the level-tier structure. The current [Against](https://www.oncehumandb.com/mods/against-all-odds-precision) and [Power](https://www.oncehumandb.com/mods/power-of-striving-downstar-deviant-energy) community detail pages corroborate the identities, but list multiple effect strengths without a demonstrated Field Guide-level map. The exact +10% values above come from the native same-level crops.

## Encounter inputs and explicit assumptions

The example weapon is an **illustrative direct-only primary** with unbuffed normal/critical/weak-spot/combined hit inputs of 100/150/200/300, 600 RPM, 20-round base magazine, and a 2-second reload. It is not a claimed current-stat profile for a named game weapon. The encounter is one stationary PvE target at the player's elevation for 40 seconds; critical and weak-spot shares are each 20%. It assumes no HP or stamina loss and no other gear buff, proc, or status source. Proc and status damage are therefore zero **only for this defined example**.

The independent 20% branch shares yield 64% ordinary body, 16% critical body, 16% noncritical weak spot, and 4% critical weak spot. The additive/floor model uses `hit × (1 + main Weapon DMG + All DMG + subattribute Weapon DMG + applicable Weakspot DMG)`. This is an explicit model assumption, not a sourced game formula. The tool also evaluates multiplicative and conservative branch application and floor/ceil magazine rounding. A shot at time zero is counted; the last magazine shot consumes a full firing interval before reload, and a shot exactly at the duration endpoint is excluded.

For the additive/floor model, Against's branch-weighted expected hit is `0.64×113.9 + 0.16×170.85 + 0.16×235 + 0.04×352.5 = 151.932`. Power's is `0.64×113 + 0.16×169.5 + 0.16×226 + 0.04×339 = 149.16`. Each fires 20 shots in 2 seconds, then reloads in 2 seconds. Ten cycles give 200 shots in 40 seconds. Thus first-magazine burst is **3038.64 vs 2983.2**, and sustained total is **30386.4 vs 29832.0**. This arithmetic is independently asserted in `tests/test_outgoing.py`.

The two main +10% Weapon bonuses are equal, while their conditional bonuses are inactive under these encounter inputs. Against's Weakspot, Weapon, and Magazine subattributes compete with Power's larger All DMG subattribute. Power's Elemental and Status values are inactive only because this example has no elemental/status damage source. Max HP has no direct outgoing contribution in this scenario.

## Ranking boundary

The displayed six sensitivity rows all favor Against for both first-magazine burst and 40-second sustained damage. The narrowest sustained lead is **0.0885%** relative to Power. That is a **conditional winner within the six shown models**. It is not a defensible bound on every game stacking rule: an unmodeled Power benefit of roughly this size could reverse that row.

If stamina is spent, HP is lost, elevation differs, or a proc/status source exists, the API returns `winner_established: false` and an explicit blocker. The sensitivity rows then show only the modeled direct component. The real values and uptime of triggered buffs, exact damage-bucket stacking, exact magazine rounding, application to critical and weak-spot branches, and current named-weapon behavior still need primary rule evidence or controlled measurements. A personal recommendation also needs an identified equipped primary and matched encounter context. Unknown effects are never set to zero to establish a winner.
