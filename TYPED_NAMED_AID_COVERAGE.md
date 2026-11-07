# Typed named Food and Whim Aid coverage

Source: `evidence_packets/native-typed-named-food-whim-v1.json`, a pinned
static decode of installed game build 26267212. The original game files are
read only and remain outside Forge.

| Native record group | Indexed typed title, description, category | Forge Aid treatment |
| --- | ---: | --- |
| Cuisine ID group | 501 of 509 | Named source records; 483 have a `food` use function, 5 `gift_open`, 13 no bound use function. The latter 18 are not asserted to grant food buffs. |
| Adjacent Whim candidates | 12 of 12 in this bounded packet | Named source records; same-ID lifetime token is nominal evidence, not proof of active Whim application or a complete Whim taxonomy. |
| Cuisine IDs without indexed item row | 8 | Withheld from the named Aid list. |

`evidence_packets/native-english-food-whim-v1.json` binds exact English
localization strings to all 513 indexed records. The nine corrected translations
do not overlap the earlier named Aid entries. Previous English glosses remain
search aliases; source English is now the display title, with native title,
description, and item ID retained in Sources. The 8 cuisine IDs without indexed
item rows remain withheld.

`evidence_packets/native-mod-choice-containers-v1.json` supplies 579 native
all-mod choice containers and 5,760 configured option positions. All 579 lists
are browsable by container ID. A second pinned packet binds exact installed
English titles and descriptions to all 579 containers and English names to all
1,640 unique native mod options. Dual item-ID/mod-code matching links 5,738 of
5,760 option positions to `catalog_systems`; 446 positions also have canonical
Build mod links. The 22 options without a dual-key match remain native-only.
Only the 446 canonical Build links open a read-only mod preview. Opening one
does not equip it, record ownership, or save the planned build; Back returns
to the same Aid category and search. Container-granted level is unknown, so
the Build preview level is a selectable model setting, not a claimed reward.
Container 37167141 has 10 ordinary chest options, 37167208 has 16 Shiny Bounce
options, and 37181192 has 10 helmet options. These are configured
selection lists, not random reward pools or proof of availability, cost,
ownership, grants, current level, or odds.

Three corrected armor packets supply 4,828 HP/Psi base-preview gear-and-star
pairs across 1,018 exact native gear IDs. The display uses the source origin
value multiplied by the indexed blueprint/star ratio and the client `.0f`
format. It never maps a similar Forge catalog name to a native ID. These are
blueprint-style previews, not equipped HP/Psi after materials, calibration,
set effects or other player state. Superseded optional-ratio packets are not
imported; R3600/Y0100 values remain withheld.
The pinned installed-English native index gives exact gear and blueprint
titles for all 1,018 preview gear IDs across 305 blueprint IDs, with raw
names, offsets and source hashes retained. Aid groups equal-name rows only
within the same exact blueprint, yielding 323 browse cards; numeric gear-ID
search still reaches every individual row. Of 1,018 gear rows, 801 have a
source-backed Forge catalog link through numeric artwork ID plus installed
gear title or the same exact blueprint/name as that direct anchor. The other
217 remain searchable by installed name without a Build link. The 218 rows
whose gear and blueprint titles differ display both titles; those labels are
not silently equated. Build links open a read-only catalog preview and do not
copy an Aid tier/star into the selected build or change ownership.
When a source-linked armor catalog identity is actually selected in a plan
with a supported tier and star, Build shows that piece's native HP/Psi base
preview as a separate known component. It remains a per-piece source preview,
not an equipped total, final damage input, or ownership claim. Missing exact
links, missing configuration and absent star rows stay explicitly unavailable.

`evidence_packets/named-food-bonus-reference-v1.json` adds two informational
graph records: Heavy Strike Azure Cake has four raw 0.1 target-attribute
values, and Star Sprinter Drink has one raw 0.08 movement attribute value.
The application operator, recipient, external eligibility and stacking are
unproven, so the raw values are not applied to Build calculations.

The Aid API provides exact native item IDs, source title, description, category,
use function and bound buff IDs. Its default screen displays 24 records at a
time, with search across source wording and collapsed source details. Nominal
duration appears only for typed source lifetimes; zero and absent lifetime
remain unknown. Flavor and spoilage descriptions are never converted into
combat effects. No record implies current availability, ownership, active
effect, stacking, enemy health, damage or crate odds.
