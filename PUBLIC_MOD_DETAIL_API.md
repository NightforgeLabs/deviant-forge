# Public mod detail API contract

`GET /api/public-mod-detail/{catalog_id}?level=8&shiny=0` is read-only and does
not consult inventory, saved builds or a personal Field Guide profile. Omit
`level` to preview level 17. Shiny requires level 17. The path requires one
exact selectable mod identity; family-only and set entries are rejected.

Response fields:

- `catalog_id`, `display_name`, `slot`, `variant`, `system_scope`,
  `preview_level`, `shiny`
- `core_effect`: `text`, `source_ref`, `status`, `conflict`
- `bonus_lines`: four ordered rows, each with `position`, `name`, `stat_type`,
  `tier`, `locked`, `value_percent`, `unit`, `direction`, `condition`,
  `conditional_bonus_percent`, `status`, `source_ref`, `source_status`,
  `source_sha256`, `source_conflict`
- `progression`: all 17 levels, with the same four rows and `known_numeric_lines`
- `source_version`, `coverage`, `missing`

`locked_at_this_level` means the official ordered tier chart gives tier zero;
it is not a numerical zero bonus. `value_unavailable` means a source mapping
is still missing; the UI should show the row and its condition but not invent
a number. `source_conflict` withholds a conflicting value. A legacy-only
instance returns `system_scope=legacy_instance_specific`, no Field Guide
progression and an explicit missing-data reason.

The official chart establishes row tiers 1–17. The installed published
slot/suffix tables supply default line names and numeric components where
available. Each derived row carries a formula URL, layout URL, generation
status and condition. `published_formula_candidate_current_generation` means
the catalog recognizes the current fixed-subattribute system, while
`published_formula_candidate_generation_unverified` also has a matching
published layout but its current/legacy generation is unresolved. Neither
status asserts a current client measurement. Complex event-conversion rows
retain named `components` with no invented single percentage.

Existing exact observations take priority when they corroborate a published
formula. A numerical or semantic conflict is shown as `source_conflict` and
the disputed value is withheld. No ownership or obtainability is inferred.

At `shiny=1&level=17`, the backend uses a separate conditional suffix-only
packet for 629 current-generation identities and blocks three missing
layouts. It returns `shiny_suffix_scope`,
`shiny_availability_for_identity`, and `shiny_core_effect_status` separately.
No Shiny ownership, availability, main-effect increase or core-effect strength
is inferred from the ordinary suffix table. A sourced conditional maximum is
shown as `display_value` (for example, `up to +30%`) while `value_percent`
remains null until the low-HP curve or explicit activity is modeled.
