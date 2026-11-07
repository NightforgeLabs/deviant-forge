# Wind Intepreter Cap: conditional ammo scenarios

The [July 9, 2026 official release](https://www.oncehuman.game/news/update/20260709/40780_1307147.html) says that an Unstable Bomber explosion automatically loads one bullet and gives Unstable Bomber DMG Rate +25%, outside RaidZone. It does **not** state whether the bullet comes from reserve, whether it is retained through a reload transaction, or the exact order of a reload blast and a bullet load. No game action or personal observation was used here.

The existing source-linked Hazardous Object reload blast is the sole integrated ammo trigger for this version. A named `source_timeline.wind_ammo_scenario` is required when that cap and blast occur:

| Scenario | Explicit assumption | Modeled magazine effect |
| --- | --- | --- |
| `created_after_reload` | The explosion creates a bullet, retained after the reload transaction. | Adds one, capped by magazine capacity; later shots are rescheduled. |
| `reserve_transfer_after_reload` | The bullet comes from finite reserve after the reload transaction. | Transfers at most one if reserve and capacity remain. |
| `not_retained_during_reload` | The load is overwritten by the same reload. | Retains zero; lower-bound hypothesis. |

These are conditional hypotheses, not three confirmed game mechanics. No option is selected by default. Without a choice, the app shows the known damage subtotal and withholds the full timed total. The result exposes `unique_armor.ammo_scenario`, `source_timeline.wind_ammo_trace`, shot times, final magazine/reserve, and assumptions. The guided Compare control is under **Generate sourced hits, counters, ticks and reloads**. An optional `source_timeline.wind_ammo_scenario` key is also accepted by the existing structured comparison API.

One bullet-load event is linked to one reload blast, independent of target count. Event IDs make replay idempotent; a second load with another ID for the same blast is rejected. The event must follow a reload that consumed at least one magazine round, at that reload's timestamp. It cannot exceed capacity, create a reserve transfer with empty reserve, or be used without the selected cap, non-RaidZone mode and supported blast binding. The generic timed scheduler still enforces reload completion before the next shot.

Remaining evidence: a current tooltip or one controlled shot/reload contrast can distinguish creation from reserve transfer and retention versus overwrite. Other weapons' Unstable Bomber explosions need a source event timestamp and outcome binding before this ammo rule can be applied to them. The bonus damage uses a named additive Unstable Bomber pool hypothesis; target mitigation and other unknown packets remain outside a game-verified winner.
