# Sparkling Pumpkin Soup: configured Power Surge rate input

Static source packet for installed build `26267212`. The reproducible, hash-checked record is [sparkling_pumpkin_effect_rate.json](sparkling_pumpkin_effect_rate.json); run `python build_sparkling_pumpkin_rate_packet.py` to verify copied code bodies and the typed item/graph ledger. The script parses bytes and does not import or execute game code.

## Exact configured path

| Link | Source-backed result |
| --- | --- |
| Item | `30110374`, installed English name **Sparkling Pumpkin Soup**, `related_func=food`. `item_use_para_data.buff_effect_list` points to `403136600` at typed token byte `88378`. |
| Buff configuration | `403136600` has nominal `life_time=1980` seconds (33 minutes). Actual duration may differ if time modifiers are supplied. |
| Graph | Typed `buff_403136600_1` data pins connect `NodeGetBuffRate.effect_rate` → add `1.0` → multiply `0.1` → `NodeChangeAttrInputValue.value` for native `E121 keyword_proc_dam_add_rate_surge`, `value_type=1`. Thus the **configured node input** is `(1 + buff.effect_rate) × 0.1`. The readable graph does not establish application to a live character or AUG damage. |

The graph pyc SHA-256 is `a52de0efdcfb8b95cbce4186bac12932f08316d829759e6b69b9366c896a88f5`; its literal SHA-256 is `36fbcab35a29e9e6c10f983dec5171525507c3ccea7927af21350aa22bb5dc92`, node-map literal offset `976`. These typed links are in [food_whim_bonus_coverage.json](food_whim_bonus_coverage.json).

## Rate producer and storage

`MemeMasteryHelper.pyc` assigns `MEME_MASTERY_BUFF_ENHANCE=4010`: module code bytes `[106,110)` are `ca175a18` (load constant index 23, value 4010; store name index 24). Its pyc SHA-256 is `de6795e0055075c200890eecfe32a5b2c5a6f1d203fa19be1e48ac5a6a53dce8`.

`cuisine_buff_utility.calc_item_meme_effect` (pyc SHA-256 `14df41f9138cb87130a72de6995707a39c3fa89dbd3afa03f673371ec242c643`, code bytes start `9494`, body SHA-256 `77a74ac57b2ba271b8cdab177c34334b53b9445851b40473a8de8dfb5945ed13`) initializes `enhance_rate=0.0` at absolute code offsets `10710–10712`. It adds `float(effect_info[4010][0])` when present (`10714–10840`), then for each `pal_effect_dict` value adds `float(pal_effect[str(4010)][0])` when present (`10844–11034`). It adds `{'effect_rate': enhance_rate}` to `buff_extra_dict` only when the result is nonzero (`11228–11274`). This is the **conditional item enhancement construction**; no value for Maurice's actual item is known.

`filter_item_food_hunter_buff` reads the item's `pal_effect_dct` at `8143–8183` and the native base `buff_effect_list` at `8185–8335`. It calls `calc_item_meme_effect` at `8681–8719` and returns the resulting buff list and extra dictionary at `8765–8775`. A private custom item branch can replace the base list. The filter's body SHA-256 is `2c8c7a19f4f85565c359dd2bc7bd0f0c346d8b3c06c73791b2cc097bf7e54ddd`.

The separate `get_item_mem_effect` reads instance `meme_effect_list`, and its DIY-material branch reads `diy_forge_choice_material_data[group_id].survival_effects` and `survival_effects_params` (`6199–7145`). That branch appends to `MEME_MASTERY_USE_PARAM_VALUE`, **not** directly to `MEME_MASTERY_BUFF_ENHANCE`. We therefore have no basis to map a recipe ingredient or food quality to a Soup `effect_rate` number. The first-value semantics above apply only if a 4010 effect is actually present. `time_rate` is a distinct duration modifier and is not part of this E121 expression.

The shared `CompBuffMgrBase.cast_buff` accesses `buff_args.get('effect_rate', 0.0)` (code offsets `20360–20402`; body SHA-256 `484a71ac1dd4ee45e121ad8bb8a8b025915fc80ea7a7d33bd4cc748a33c66354`). `CompBuffBase.init_buff` stores `buff_args.get('effect_rate', 0.0)` into `holder.buff_dict[buff_index]` (`4850–4892`, dictionary stored at `5542–5566`; body SHA-256 `f577e5e8b1a57d8050f62a15c6672b9537b5f91269153727d85986474944ce53`). `NodeGetBuffRate.NodeMainClient._do` reads the stored `buff_data['effect_rate']` (`1270–1304`; body SHA-256 `5287e6a8ef6f40ccfa46594eaac6e745ef7461f0fb5a4dbc5d4fb02626a409f4`). These prove the generic buff-rate storage/read path; the readable item-use code does **not** prove that the Soup's returned extra dictionary is passed to this constructor.

## Controlled vectors and boundary

For a **synthetic** `effect_info[4010]` first value `0.20` and two synthetic `pal_effect[str(4010)]` first values `0.05` and `0.10`, the helper builds `effect_rate=0.35`; if that rate reaches the active buff, the E121 graph input is `(1+0.35)×0.1 = 0.135`. With no 4010 values, the helper omits `effect_rate`; the shared constructor defaults an absent value to `0.0`, yielding configured input `0.1` **if** this item actually follows that route. Neither vector is an observed player bonus or certified applied combat delta.

The exact item-use transfer is the remaining gap: `CompUseItem` delegates to `ClientAvatar.run_sel_item_type_func`, whose body is absent from the readable copied module. The supplied `effect_info` and actual instance `pal_effect_dct`, recipe/quality state, buff executor, and AUG keyword damage gate are not established for this item. Nominal 33-minute configuration does not prove the applied or effective duration.

No game code was executed; no installed game or Forge files were changed.
