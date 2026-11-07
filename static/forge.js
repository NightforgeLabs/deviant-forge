(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n) => (n == null || isNaN(n) ? "—" : Math.round(n).toLocaleString());
  const SLOT_ORDER = ["helmet", "mask", "top", "gloves", "bottoms", "shoes", "weapon"];
  const ARMOR_SLOTS = ["Helmet", "Mask", "Top", "Gloves", "Bottoms", "Shoes"];
  const KIND_LABEL = { all: "All", mod: "Mods", weapon: "Weapons", armor: "Armor sets", stars: "Stars", combo: "Weapon + set",
    food: "Food & drink", deviation: "Deviation", keyarmor: "Key armor", calibration: "Calibration", hide: "Mask hide", secondary: "Secondary" };
  const CAL_SUBS = { crit_rate: "Crit Rate", crit_dmg: "Crit DMG", weakspot_dmg: "Weakspot DMG", elemental_dmg: "Elemental DMG" };
  const STAT_LABEL = {
    weapon_dmg: "Weapon DMG", status_dmg: "Status DMG", elemental_dmg: "Elemental DMG", crit_rate: "Crit Rate",
    crit_dmg: "Crit DMG", weakspot_dmg: "Weakspot DMG", attack: "Attack", fire_rate: "Fire Rate", magazine: "Magazine",
    reload_speed: "Reload Speed", vs_enemies: "DMG vs Enemies", vulnerability: "Vulnerability", dmg_boost: "DMG Boost",
  };
  let state = null;
  let tab = "all";

  async function load() {
    try {
      const r = await fetch("/api/forge/state", { cache: "no-store" });
      if (!r.ok) throw new Error(`Server answered ${r.status}`);
      state = await r.json();
      render();
    } catch (e) {
      $("#bestTitle").textContent = "Could not load your builds";
      $("#bestBody").innerHTML = `<p class="empty-msg">${esc(e.message)}. Is the Deviant Forge server running?</p>`;
    }
  }

  function statLabel(k) {
    if (STAT_LABEL[k]) return STAT_LABEL[k];
    if (k === "weapon_taken") return "Target takes Weapon DMG";
    if (k === "marked_dmg") return "DMG vs marked target";
    const m = k.match(/^(kw_dmg|kw_chance|kw_base|kw_final|el|kw_crit_rate|kw_crit_dmg|kw_ws_dmg|el_taken):(.+)$/);
    if (m) return { kw_dmg: `${m[2]} DMG`, kw_chance: `${m[2]} chance`, kw_base: `${m[2]} base chance`, kw_final: `${m[2]} final DMG`, el: `${m[2]} DMG`,
      kw_crit_rate: `${m[2]} Crit Rate`, kw_crit_dmg: `${m[2]} Crit DMG`, kw_ws_dmg: `${m[2]} Weakspot DMG`, el_taken: `Target takes ${m[2]} DMG` }[m[1]];
    return k.replace(/_/g, " ");
  }

  function render() {
    const { result, profile } = state;
    renderTop(result, profile);
    renderNotes(result);
    renderBest(result.best);
    renderTabs(result.upgrades);
    renderUpgrades();
    renderAlts(result.alternatives || []);
    renderSecondary(result.secondary);
    loadEffort();
    renderLadder(result.ladder);
    renderReadout(result, profile);
    renderProfBtn();
    $("#foot").innerHTML =
      `Numbers are estimates of sustained single-target DPS from game data (${esc(result.data?.source || "game files")}, ` +
      `retrieved ${esc((result.data?.retrieved_at || "").slice(0, 10))}). Use them to compare options, not as exact in-game damage. ` +
      `Effects the model can't count are listed under each build. Starchrom costs assume 1★ purchases at Tier 5.`;
  }

  function renderLadder(L) {
    const list = $("#ladList"), note = $("#ladNote");
    if (!L || L.error || !L.top?.length) { list.innerHTML = `<li class="empty-msg">Ranking not available${L?.error ? `: ${esc(L.error)}` : ""}.</li>`; return; }
    const max = L.top[0].dps;
    const bar = (d) => `<span class="lbar"><i style="width:${Math.max(1.5, Math.min(100, d / max * 100)).toFixed(1)}%"></i></span>`;
    // the mods each top build runs; ✓ = you own that mod (any level), with your level
    const own = new Map((state.inventory?.mods || []).map((m) => [modKey(m), m]));
    const SLOT_N = { weapon: "Weapon", helmet: "Helmet", mask: "Mask", top: "Top", gloves: "Gloves", bottoms: "Pants", shoes: "Boots" };
    const modsLine = (mods) => !mods?.length ? "" : `<span class="lmods">${mods.map((m) => { const o = own.get(modKey(m));
      return `<span class="lmod ${o ? "have" : ""}" title="${esc(`${SLOT_N[m.slot] || m.slot}: ${m.name} (${m.variant})${o ? ` · you have it at Lv ${o.level}${o.shiny ? " Shiny" : ""}` : " · not owned"}`)}"><em>${esc(SLOT_N[m.slot] || m.slot)}</em> ${esc(m.name)}${o ? ` <i>✓ ${o.level}</i>` : ""}</span>`; }).join("")}</span>`;
    const row = (cls, rank, name, sub, d, mods) => `<li class="lrow ${cls}"><span class="lrank">${rank}</span>
      <span class="lname"><b>${esc(name)}</b><small>${esc(sub)}</small>${modsLine(mods)}</span>${bar(d)}<span class="ldps">${num(d)}</span></li>`;
    const marks = [];
    if (L.you) marks.push({ ...L.you, cls: "you", name: `You · ${L.you.weapon}`, sub: `${L.you.pct_of_top}% of #1 · your best build right now` });
    if (L.next && (!L.you || L.next.dps > L.you.dps)) marks.push({ ...L.next, cls: "next", name: `After your next upgrade`, sub: `${L.next.title} · ${L.next.pct_of_top}% of #1` });
    const out = [];
    L.top.forEach((b, i) => {
      marks.filter((m) => m.in_top10 && m.rank === i + 1).forEach((m) => out.push(row(m.cls, `#${m.rank}`, m.name, m.sub, m.dps)));
      out.push(row("", `#${i + 1}`, b.weapon, [b.keyword, Object.entries(b.sets || {}).map(([k, v]) => `${k} ${v}pc`).join(" + "), b.key_armor ? `key: ${b.key_armor}` : "", b.foods?.length ? b.foods.join(", ") : ""].filter(Boolean).join(" · "), b.dps, b.mods));
    });
    const below = marks.filter((m) => !m.in_top10).sort((a, b) => b.dps - a.dps);
    if (below.length) {
      out.push(`<li class="lgap" aria-hidden="true">⋯</li>`);
      below.forEach((m) => out.push(row(m.cls, m.beyond ? `${m.of}+` : `#${m.rank}`, m.name, m.sub, m.dps)));
    }
    list.innerHTML = out.join("");
    const y = L.you;
    note.textContent = (y ? (y.in_top10 ? `You'd be #${y.rank}. ` : y.beyond ? `You're below the top ${y.of} max-gear builds (${y.pct_of_top}% of #1). ` : `You'd be about #${y.rank} of ${y.of}. `) : "")
      + L.basis + " It updates every time you change your gear.";
  }

  let lastDps = null;
  function renderReadout(result, profile) {
    const b = result.best, el = $("#readout");
    el.innerHTML = `<span class="r-l">Best now</span><b>${num(b?.dps)}</b><small>${esc(b?.weapon?.name || "no weapon yet")} · est. DPS</small>`;
    if (lastDps != null && b && lastDps !== b.dps) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
    lastDps = b?.dps ?? null;
    const sc = profile.starchrom, L = result.ladder;
    $("#hud").innerHTML = `<div class="h-t">Status</div>
      <div class="row"><span>Class</span><b>${esc(b?.config?.class?.label || "Freelancer")}</b></div>
      <div class="row"><span>Starchrom</span><b class="${sc == null ? "warn" : ""}">${sc == null ? "not set" : num(sc)}</b></div>
      <div class="row"><span>Armor worn</span><b class="${result.owned_counts?.armor ? "" : "warn"}">${num(result.owned_counts?.armor)} / 6</b></div>
      <div class="row"><span>Armor owned</span><b>${num(result.owned_counts?.armor_owned ?? result.owned_counts?.armor)}</b></div>
      <div class="row"><span>Mods owned</span><b>${num(result.owned_counts?.mods)}</b></div>
      ${L?.you ? `<div class="row"><span>vs #1 build</span><b>${esc(L.you.pct_of_top)}%</b></div>` : ""}`;
    renderHudData();
  }

  function renderTop(result, profile) {
    const sc = profile.starchrom;
    $("#topMeta").innerHTML = [
      `Starchrom <b>${sc == null ? "not set" : num(sc)}</b>`,
      `Psi Intensity <b>${num(result.psi?.value)}</b> <span class="chip ${/assumed/.test(result.psi?.basis) ? "warn" : "good"}">${esc(result.psi?.basis)}</span>`,
      `Owned mods <b>${num(result.owned_counts?.mods)}</b>`,
      `Fight <b>${esc(result.scenario?.label || result.scenario?.key)}</b>`,
      `Class <b>${esc(result.best?.config?.class?.label || "not set")}</b>`,
    ].map((s) => `<span>${s}</span>`).join("");
  }

  function renderNotes(result) {
    const notes = [...(result.notes || [])];
    const freshBar = result.fresh ? `<div class="note fresh-note"><span><b>Fresh-start test.</b> Your real profile is put aside, and recorded game data is ignored. Only what you add now counts.</span><button class="btn small primary" type="button" data-profiles>Switch profile</button></div>` : "";
    if (state.profile.starchrom == null) notes.push("Add your Starchrom balance to see which upgrades you can afford right now.");
    const go = (n) => /armor/i.test(n) ? ["armor", "Add armor"] : /weapon/i.test(n) ? ["weapons", "Add weapons"] : /starchrom|psi/i.test(n) ? ["profile", "Open settings"] : ["build", "OK"];
    $("#notes").innerHTML = freshBar + notes.map((n) => { const [pg, l] = go(n); return `<div class="note"><span>${esc(n.replace(/in 'My gear'/g, "on the Armor page").replace(/'My gear'/g, "the Weapons page"))}</span><a class="btn small" href="#/${pg}">${l}</a></div>`; }).join("");
  }

  function modCard(slot, m, baseline) {
    if (!m) return `<div class="mod empty"><div class="slot">${esc(slot)}</div><div class="mname">Empty</div><div class="mvar">no owned mod helps here</div></div>`;
    const b = baseline && baseline[slot];
    const changed = baseline && (!b || b.name !== m.name || b.variant !== m.variant);
    return `<div class="mod ${changed ? "new" : ""}" title="${esc(m.core)}">
      <div class="slot">${esc(slot)}${changed ? " · change" : ""}</div>
      <div class="mname">${esc(m.name)}</div>
      <div class="mvar">${esc(m.variant)} · Lv ${esc(m.level)}${m.shiny ? ` <span class="shiny-text" title="Shiny">✦ Shiny</span>` : ""}${m.owned === false ? " · not owned" : ""}</div></div>`;
  }

  function buildBody(b, baselineMods) {
    const res = b.result;
    const total = Object.values(res.breakdown).reduce((a, v) => a + v, 0) || 1;
    const bars = Object.entries(res.breakdown).sort((a, c) => c[1] - a[1]).map(([k, v]) =>
      `<div class="bar"><span>${esc(k)}</span><div class="track"><div class="fill" style="width:${(100 * v / total).toFixed(1)}%"></div></div><span class="v">${num(v)}</span></div>`).join("");
    const d = res.derived || {};
    const stats = [
      ["Psi Intensity", num(d.psi)], ["Attack", num(d.attack)], ["Fire rate", `${num(d.fire_rate_rpm)} rpm`], ["Magazine", num(d.magazine)],
      ["Crit rate", `${d.crit_rate ?? 0}%`], ["Crit DMG", `${d.crit_dmg ?? 0}%`], ["Weakspot DMG", `${d.weakspot_dmg ?? 0}%`],
      ["Firing uptime", `${Math.round((d.uptime || 0) * 100)}%`], ["Keyword procs/s", (d.keyword_procs_per_s ?? 0).toFixed(2)],
    ].map(([k, v]) => `<div class="stat"><span>${k}</span><b>${esc(v)}</b></div>`).join("");
    const bonus = Object.entries(res.stats || {}).filter(([k, v]) => !k.startsWith("_") && !k.startsWith("per:") && v)
      .sort((a, c) => c[1] - a[1]).map(([k, v]) => `<li>${esc(statLabel(k))}: +${(+v).toFixed(1)}%</li>`).join("");
    const unm = (res.unmodeled || []).map((u) => `<li>${esc(u)}</li>`).join("");
    const sets = Object.entries(b.sets || {}).map(([k, v]) => `<span class="chip">${esc(k)} ${v}pc</span>`).join(" ");
    const c = b.config || {};
    const cfgRows = [["Key armor", c.key_armor], ["Deviation", c.deviation], ...(c.consumables || []).map((f) => [c.food_auto ? `${f.slot} · best pick` : f.slot, f]),
      ...(c.food ? [["Food", c.food]] : []), ...(c.drink ? [["Drink", c.drink]] : []),
      ...(c.class && c.class.key !== "freelancer" ? [["Class", { name: c.class.label, text: c.class.text, source: c.class.source }]] : []),
      ["Calibration", c.calibration]]
      .filter(([, v]) => v).map(([k, v]) => `<div class="cfg"><span>${k}</span><b>${esc(v.name || v.label)}</b>${v.text ? `<small>${esc(v.text)}${v.approx ? ` · estimate: ${esc(v.approx)}` : ""}</small>` : ""}${v.source ? `<a href="${esc(v.source)}" target="_blank" rel="noopener">source</a>` : ""}</div>`).join("");
    return `
      <div class="weapon-box">
        <div class="wname">${esc(b.weapon.name)} <span class="chip">${esc(b.weapon.stars)}★</span> <span class="chip kw">${esc(b.weapon.keyword || "no keyword")}</span> ${sets}</div>
        <p>${esc(b.weapon.effect_text || "")}</p>
      </div>
      <div class="mods">${SLOT_ORDER.map((s) => modCard(s, b.mods[s], baselineMods)).join("")}</div>
      ${cfgRows ? `<div class="section-t">Gear outside mods</div><div class="cfgs">${cfgRows}</div>` : ""}
      <div class="section-t">Where the damage comes from</div><div class="bars">${bars}</div>
      <div class="section-t">Stats</div><div class="stats">${stats}</div>
      ${magPanel(b.magazine)}
      <details><summary>All bonuses counted</summary><ul>${bonus || "<li>None</li>"}</ul></details>
      <details><summary>Not counted (${(res.unmodeled || []).length})</summary><ul>${unm || "<li>Nothing — every effect was counted.</li>"}</ul></details>`;
  }

  function renderBest(b) {
    if (!b && state.result?.starter && !state.result.starter.error) {
      const S = state.result.starter;
      $("#bestTitle").textContent = "New player start";
      $("#bestDps").innerHTML = `<small>You own no weapons yet · ${num(S.budget)} Starchrom · ${esc(S.scenario)}</small>`;
      const HOW = { sc: ["how-sc", "Starchrom"], free: ["how-free", "Free"], farm: ["how-farm", "Farm"] };
      $("#bestBody").innerHTML = `<p class="path-verdict">First legendary gun to aim for: <b>${esc(S.pick.weapon)}</b> (${esc(S.pick.keyword || "")}, ${esc(S.pick.type || "")}).
          About ${num(S.pick.day1)} DPS on day one, and it grows to about ${num(S.pick.ceiling)} fully built.</p>
        <ol class="path-steps">${S.steps.map((st, i) => `<li class="path-step"><span class="ps-n">${i + 1}</span><div class="ps-body">
          <div class="ps-title">${esc(st.title)}</div>
          <div class="ps-meta"><span class="chip ${HOW[st.how][0]}">${HOW[st.how][1]}</span>${st.cost ? `<span class="chip">${num(st.cost)} Starchrom</span>` : ""}</div>
          <p class="hint">${esc(st.why)}</p>
          ${st.mods ? `<div class="starter-mods">${st.mods.map((m) => `<span class="starter-mod">${pic(m.name, "sm")}<span><b>${esc(m.name)}</b><small>${esc(m.variant)} · ${esc(SLOT_NAME[m.slot] || m.slot)}</small></span></span>`).join("")}</div>` : ""}
          </div><span></span></li>`).join("")}</ol>
        <details class="starter-alt"><summary>Other good first guns</summary><ul class="plain">${S.options.slice(1).map((o) =>
          `<li>${pic(o.weapon, "sm")} <b>${esc(o.weapon)}</b> · ${esc(o.keyword || "")} · day one ${num(o.day1)} · fully built ${num(o.ceiling)}</li>`).join("")}</ul></details>
        <p class="hint">${esc(S.note)}</p>`;
      return;
    }
    if (!b) {
      $("#bestTitle").textContent = "No weapon recorded yet";
      $("#bestDps").innerHTML = "";
      $("#bestBody").innerHTML = `<p class="empty-msg">Add a weapon you own on the Weapons page and the best mod setup will appear here.</p>`;
      return;
    }
    $("#bestTitle").textContent = b.weapon.name;
    $("#bestDps").innerHTML = `<span class="dps">${num(b.dps)}</span><small>estimated DPS · ${esc(b.weapon.type || "")}</small>`;
    $("#bestBody").innerHTML = wearingHtml() + armorCompareHtml(b) + buildBody(b, null);
  }
  // Your armor (with its best mods) next to the best armor you could wear from pieces you own
  function armorCompareHtml(b) {
    const A = state.result.best_armor, armor = prof().armor || {};
    if (!A || A.error) return "";
    const row = (slot, piece, mod, changed) => `<li class="${changed ? "chg" : ""}"><span class="ac-slot">${slot}</span>
        <span class="ac-piece">${piece ? `${pic(piece.name, "sm")}<span><b>${esc(piece.name)}</b><small>${"★".repeat(+piece.stars || 1)}${changed ? " · swap" : ""}</small></span>` : `<span class="faint">empty</span>`}</span>
        <span class="ac-mod">${mod ? `<b>${esc(mod.name)}</b><small>${esc(mod.variant)} · Lv ${esc(mod.level)}</small>` : `<small class="faint">no mod you own helps</small>`}</span></li>`;
    const sets = (o) => Object.entries(o || {}).map(([k, v]) => `<span class="chip">${esc(k)} ${v}pc</span>`).join(" ");
    const left = ARMOR_SLOTS.map((s) => row(s, armor[s], b.mods?.[s.toLowerCase()], false)).join("");
    const keep = `<div class="ac-col"><div class="ac-h"><small>Keep the armor you're wearing</small><b class="mono">${num(b.dps)} DPS</b><div>${sets(b.sets)}</div></div><ul class="ac-list">${left}</ul>
        <p class="hint">Best mod from your collection on each piece you have on.</p></div>`;
    if (A.same) return `<div class="ac"><div class="section-t">Your armor vs everything you own</div>
        <div class="ac-okbar"><span class="chip good">Your armor is already the best you own</span><span class="hint">Checked ${num(A.layouts_checked)} armor combos from your ${num(state.result.owned_counts?.armor_owned)} pieces. No mix beats what you have on.</span></div>
        <div class="ac-grid">${keep}</div></div>`;
    const right = ARMOR_SLOTS.map((s) => { const p = A.armor[s]; return row(s, p, A.build.mods?.[s.toLowerCase()], (p?.name || null) !== (armor[s]?.name || null)); }).join("");
    return `<div class="ac"><div class="section-t">Your armor vs everything you own</div><div class="ac-grid">${keep}
      <div class="ac-col best"><div class="ac-h"><small>Best armor you own</small><b class="mono">${num(A.dps)} DPS</b><span class="chip good">+${A.gain_pct}%</span><div>${sets(A.build.sets)}</div></div>
        <ul class="ac-list">${right}</ul>
        ${A.build.weapon.name !== b.weapon.name ? `<p class="hint">With ${esc(A.build.weapon.name)}.</p>` : ""}
        <button class="btn primary" type="button" data-wear-best>Wear this armor</button>
        <p class="hint">Swaps ${A.changes.length} piece${A.changes.length === 1 ? "" : "s"}. Mods you marked as "on it now" for swapped pieces are cleared, since they stay in the old piece.</p></div></div></div>`;
  }
  function wearingHtml() {
    const W = state.result.wearing;
    const how = `Tell the app what's on your gear: on <a href="#/armor">Armor</a> tap "+ Mod on it now" under each piece, and on <a href="#/weapons">Weapons</a> tap "Using this gun now", then "+ Mod on it now".`;
    if (!W) return `<div class="wear-now empty"><b>Your gear right now: not set.</b> <span class="hint">${how} Then this shows your damage as you are, and exactly which mods to swap.</span></div>`;
    if (W.dps == null) return `<div class="wear-now"><b>Your gear right now</b><p class="hint">${esc(W.note || "")} ${how}</p></div>`;
    const sw = (W.swaps || []).map((x) => `<li><span class="chip">${esc(x.slot === "gun" ? "Gun" : SLOT_NAME[x.slot] || x.slot)}</span><span>${x.now ? esc(x.now) : "<i class=\"faint\">empty</i>"} → <b>${esc(x.to)}</b></span></li>`).join("");
    return `<div class="wear-now">
      <div class="wear-head"><div><small>Your gear right now</small><b class="mono">${num(W.dps)} DPS</b><span class="hint">${esc(W.weapon)}${W.empty.length ? ` · no mod set on: ${W.empty.map((s) => SLOT_NAME[s]).join(", ")}` : ""}</span></div>
        ${W.gain_pct > 0.5 ? `<div class="wear-gain"><small>Best with what you own</small><b class="mono">${num(W.best_dps)} DPS</b><span class="chip good">+${W.gain_pct}% by swapping</span></div>` : `<div class="wear-gain"><span class="chip good">You're already wearing the best setup</span></div>`}</div>
      ${sw ? `<p class="hint">Swap these to get there:</p><ul class="wear-swaps">${sw}</ul>` : ""}
      <p class="hint">${how}</p></div>`;
  }

  function renderTabs(ups) {
    const kinds = ["all", ...["mod", "weapon", "armor", "stars", "combo", "food", "deviation", "keyarmor", "calibration"].filter((k) => ups.some((u) => u.kind === k))];
    if (!kinds.includes(tab)) tab = "all";
    $("#upTabs").innerHTML = kinds.map((k) =>
      `<button class="tab" role="tab" type="button" data-tab="${k}" aria-selected="${k === tab}">${KIND_LABEL[k]}</button>`).join("");
  }

  function renderUpgrades() {
    let ups = state.result.upgrades.filter((u) => (tab === "all" || u.kind === tab) && (tab !== "all" || u.multiplier > 1.01));
    if (tab === "all") {
      // keep the list varied: one weapon + set combo per weapon, max 4 armor sets
      const seenW = new Set(); let armorN = 0;
      ups = ups.filter((u) => {
        if (u.kind === "combo") { const w = u.build?.weapon?.name; if (seenW.has(w)) return false; seenW.add(w); }
        if (u.kind === "armor" && ++armorN > 4) return false;
        return true;
      }).slice(0, 20);
    } else ups = ups.slice(0, 40);
    const sc = state.profile.starchrom;
    if (!ups.length) { $("#upList").innerHTML = `<li class="empty-msg">No upgrades found for this category.</li>`; return; }
    const baseline = state.result.best?.mods;
    $("#upList").innerHTML = ups.map((u, i) => {
      const cost = u.cost_starchrom;
      let afford = "";
      if (cost === 0) afford = `<small>no Starchrom · ${u.kind === "mod" ? "find or drop" : "free"}</small>`;
      else if (sc != null) afford = `<small class="${cost <= sc ? "ok" : "no"}">${cost <= sc ? "you can afford this" : `need ${num(cost - sc)} more`}</small>`;
      else if (u.gain_per_10k) afford = `<small>+${(+u.gain_per_10k).toFixed(1)}% per 10k ✦</small>`;
      const more = u.build && u.build.result ? buildBody(u.build, baseline) : "";
      return `<li class="up" data-i="${i}">
        <button type="button" aria-expanded="false">
          <div class="mult">×${(+u.multiplier).toFixed(2)}<small>${u.gain_pct >= 0 ? "+" : ""}${(+u.gain_pct).toFixed(1)}%</small></div>
          <div><div class="t">${esc(u.title)}</div><div class="sub">${esc(KIND_LABEL[u.kind] || u.kind)} · ${num(u.dps)} DPS</div></div>
          <div class="cost">${cost ? `${num(cost)} <span aria-hidden="true">✦</span>` : "—"}${afford}</div>
        </button>
        <div class="more"><p>${esc(u.detail || "")}</p>${more}</div>
      </li>`;
    }).join("");
  }

  let effSeq = 0;
  async function loadEffort() {
    const my = ++effSeq;
    $("#effCard").hidden = false;
    try {
      const r = await fetch("/api/forge/effort", { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      if (my === effSeq) renderEffort(d);
    } catch (e) { if (my === effSeq) $("#eff").innerHTML = `<p class="hint warn">Couldn't compare effort levels (${esc(e.message)}).</p>`; }
  }
  function renderEffort(d) {
    const B = d.builds || {};
    if (!B.easy) { $("#eff").innerHTML = `<p class="hint">${esc((d.notes || [])[0] || "")}</p>`; return; }
    const mine = prof().extras?.effort || "normal";
    const col = (k, cls) => {
      const b = B[k], e = d.efforts[k];
      return `<div class="eff-col ${cls} ${mine === k ? "mine" : ""}">
        <div class="eff-top"><span class="eff-name">${esc(e.label)}</span>${mine === k ? '<span class="chip good">your style</span>' : ""}</div>
        <div class="eff-dps">${num(b.dps)}</div><div class="eff-pct">${b.pct_of_max}% of max</div>
        <div class="eff-bar"><i style="width:${Math.min(100, b.pct_of_max)}%"></i></div>
        <p class="eff-desc">${esc(e.desc)}</p>
        <p class="eff-gear"><b>${esc(b.weapon)}</b></p>
        <p class="hint">Same gear played easy: ${num(b.played_at.easy)} · normal: ${num(b.played_at.normal)} · hard: ${num(b.played_at.max)}</p>
        ${mine === k ? "" : `<button class="btn" type="button" data-effort="${k}">Use ${esc(e.label)} as my style</button>`}
      </div>`;
    };
    const SN = { weapon: "Weapon", helmet: "Helmet", mask: "Mask", top: "Top", gloves: "Gloves", bottoms: "Bottoms", shoes: "Shoes" };
    const m = (x) => x ? `${esc(x.name)} <span class="muted">${esc(x.variant)} · Lv ${x.level}</span>` : "—";
    const diff = (d.diff || []).length ? `<div class="section-t">What changes between Koala and Try-hard gear</div>
      <div class="eff-diff">${d.diff.map((r) => `<div class="eff-drow"><span class="lbl">${esc(SN[r.slot] || r.slot)}</span><span>${m(r.easy)}</span><span class="arrow">→</span><span>${m(r.max)}</span></div>`).join("")}</div>`
      : `<p class="hint">The gear is the same at every effort level.</p>`;
    $("#eff").innerHTML = `<p class="eff-verdict">${esc(d.verdict)}</p>
      <div class="eff-cols">${col("easy", "koala")}${col("normal", "")}${col("max", "hard")}</div>${diff}
      <p class="hint">${(d.notes || []).map(esc).join(" ")} Assumed weakspot hits: Koala ${Math.round(d.assumptions.easy.weakspot_rate * 100)}%,
        Normal 35%, Try-hard ${Math.round(d.assumptions.max.weakspot_rate * 100)}%. Time in the air: Koala 0%, Try-hard ${Math.round(d.assumptions.max.airborne * 100)}%.</p>`;
  }

  function renderSecondary(sc) {
    $("#secCard").hidden = !sc;
    if (!sc) return;
    const gain = sc.has_amp ? sc.gain_amp_pct : sc.gain_pct;
    const head = sc.primary_marks
      ? `<p>Your main gun <b>${esc(sc.primary)}</b> already applies The Bull's Eye by itself, so the secondary is free for anything you like
         (a ranged gun for travel, or a Fortress Warfare / Fast Gunner gun for the weapon-swap buffs).</p>`
      : sc.pick
        ? `<p class="sec-pick"><b>Use ${esc(sc.pick)}</b> — you own it. Shoot the boss once, swap back to ${esc(sc.primary)}.</p>`
        : `<p class="sec-pick"><b>You don't own a marking gun yet.</b> Get one of the guns below — it's the cheapest big damage boost for ${esc(sc.primary)}.</p>`;
    const nums = sc.primary_marks ? "" : `<div class="sec-nums">
        <div><span class="lbl">No mark</span><b>${num(sc.dps_no_mark)}</b></div>
        <div><span class="lbl">Marked (+8%)</span><b>${num(sc.dps_mark)}</b><span class="up">+${sc.gain_pct}%</span></div>
        <div><span class="lbl">+ Vulnerability Amplifier</span><b>${num(sc.dps_amp)}</b><span class="up">+${sc.gain_amp_pct}%</span></div></div>
      <p class="hint">${sc.has_amp ? "You own Vulnerability Amplifier — put it on the secondary, not the main gun." : "Vulnerability Amplifier (weapon mod) on the secondary doubles the mark to +16%."}
        ${sc.marked_on ? "Your numbers already count the mark." : `Your numbers don't count the mark yet. Once you're doing it, switch on “Bull's Eye kept on target” in <a href="#/profile">Class &amp; settings</a> (+${gain}%).`}</p>`;
    const list = sc.primary_marks ? "" : `<div class="sec-list">${sc.markers.map((m) => `<div class="sec-row ${m.name === sc.pick ? "on" : ""}">
        ${pic(m.name, "")}<div><b>${esc(m.name)}</b>${m.owned ? ' <span class="chip good">owned</span>' : ""}<p>${esc(m.why)}</p></div></div>`).join("")}</div>`;
    $("#sec").innerHTML = head + nums + list + `<p class="hint">How to choose: the secondary isn't for damage. Its job is to mark the boss with The Bull's Eye, which makes it take more damage from you and your team.
      Melee isn't counted. <a href="${esc(sc.source)}" target="_blank" rel="noopener">Community guide</a> · estimate</p>`;
  }

  function renderAlts(alts) {
    $("#altsCard").hidden = !alts.length;
    $("#alts").innerHTML = alts.map((a) =>
      `<div class="alt-row"><div><b>${esc(a.weapon.name)}</b> <span class="chip">${esc(a.weapon.stars)}★</span> <span class="chip kw">${esc(a.weapon.keyword || "")}</span></div><div class="cost">${num(a.dps)} DPS</div></div>`).join("");
  }

  // ---------------------------------------------------------- Best in game
  async function runTheory() {
    const btn = $("#thRun");
    btn.disabled = true; btn.textContent = "Searching…";
    $("#thBody").innerHTML = `<div class="skeleton"></div><p class="empty-msg">Testing every weapon with every setup…</p>`;
    try {
      const q = new URLSearchParams({ scenario: state.profile.scenario || "boss", marked: $("#thMarked").checked ? "1" : "0" });
      const r = await fetch(`/api/forge/theory?${q}`, { cache: "no-store" });
      if (!r.ok) throw new Error(`Server answered ${r.status}`);
      renderTheory(await r.json());
    } catch (e) {
      $("#thBody").innerHTML = `<p class="empty-msg">Could not run the search: ${esc(e.message)}</p>`;
    } finally { btn.disabled = false; btn.textContent = "Find the best builds"; }
  }

  function renderTheory(t) {
    const top = t.builds[0];
    if (!top) { $("#thBody").innerHTML = `<p class="empty-msg">No builds found.</p>`; return; }
    const mine = state.result.best?.dps;
    const gap = mine ? `<p class="gap">Your best build is at <b>${Math.round(100 * mine / top.dps)}%</b> of the strongest build found (${num(mine)} vs ${num(top.dps)} estimated DPS, ${esc(t.scenario.label)}). See "Your next jump in power" for the cheapest steps toward it.</p>` : "";
    const rows = t.builds.map((b, i) => `<li class="up th-row" data-th="${i}">
        <button type="button" aria-expanded="false">
          <div class="mult">#${i + 1}<small>${Math.round(100 * b.dps / top.dps)}%</small></div>
          <div><div class="t">${esc(b.weapon.name)} <span class="chip kw">${esc(b.weapon.keyword || "no keyword")}</span></div>
            <div class="sub">${Object.entries(b.sets).map(([k, v]) => `${esc(k)} ${v}`).join(" + ") || "no set"}${b.config.key_armor ? ` + ${esc(b.config.key_armor.name)}` : ""}${b.config.deviation ? ` · ${esc(b.config.deviation.name)}` : ""}</div></div>
          <div class="cost">${num(b.dps)}<small>est. DPS</small></div>
        </button>
        <div class="more">${buildBody(b, null)}</div></li>`).join("");
    $("#thBody").innerHTML = `${gap}<ol class="up-list">${rows}</ol>
      <details><summary>Assumptions (Psi Intensity ${num(t.psi.value)}, ${esc(t.psi.basis)})</summary><ul>${t.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details>`;
  }

  // ---------------------------------------------------------- My gear (picture screen)
  const PAGES = {
    weapons: ["Arsenal", "Weapons", "Every weapon in the game. Mark the ones you own, set stars and calibration. Each card shows its estimated DPS with the mods and armor you have now."],
    armor: ["Loadout", "Armor", "Tap a piece to wear it. Sets are ranked by how much damage a 4-piece would add to your best build."],
    mods: ["Mod vault", "Mods", "Your mods. Set the level, remove ones you scrapped, add new drops. The best build picks from these."],
    crates: ["Supply", "Mod crates", "Tell the app which crate you have. It tells you which pick gives you the best chance at the mod your build needs."],
    support: ["Buffs", "Deviation & food", "Pick your deviation and what you eat and drink. By default the app picks the best food for each build."],
    profile: ["Settings", "Class & settings", "Your class, Starchrom, Psi Intensity and fight type. Everything stays on this computer."],
    survive: ["Stay alive", "Survivability", "The toughest builds you can make from what you own: give up 5% damage, 10%, or go all in on staying alive. Toughness is how much boss damage you can take before you die. Every number is an estimate."],
    path: ["Roadmap", "Path to max", "The quickest order of upgrades from your build now to the strongest build you can reach: what it costs, what you get at each step, and where it stops being worth it. Every number is an estimate."],
    updates: ["Continuity", "Updates", "Check the official patch notes and refresh the game data. The app says what changed in plain words, marks new things NEW!, and re-runs your builds so you know what to farm and where to spend Starchrom."],
    later: ["Roadmap", "Coming later", "Tools from the older version that aren't useful enough yet. They're parked here until they're rebuilt properly."],
  };
  let page = "build", modFilter = "", modSlot = "all", saveTimer = null, saving = false, pending = false;
  let wq = "", wType = "all", wOwned = "all", wSort = "dps", wLegendary = true, aq = "", aSlot = "all";

  const icon = (name) => state.catalog.icons[name] || state.catalog.icons[String(name || "").toLowerCase()];
  function pic(name, cls = "") {
    const u = icon(name);
    return u ? `<img class="pic ${cls}" src="${esc(u)}" alt="" loading="lazy" decoding="async">`
      : `<span class="pic ph ${cls}" aria-hidden="true">${esc(String(name || "?").replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase())}</span>`;
  }
  function starPicker(cur, attr, max = 6) {
    return `<div class="stars" role="group" aria-label="Stars">${Array.from({ length: max }, (_, i) =>
      `<button type="button" class="st ${i < cur ? "on" : ""}" ${attr}="${i + 1}" aria-label="${i + 1} star${i ? "s" : ""}" aria-pressed="${i < cur}">★</button>`).join("")}</div>`;
  }
  function stepper(val, min, max, attr, label) {
    return `<div class="stepper" role="group" aria-label="${label}">
      <button type="button" ${attr}="-1" aria-label="Lower ${label}" ${val <= min ? "disabled" : ""}>−</button>
      <b>${val}</b>
      <button type="button" ${attr}="1" aria-label="Raise ${label}" ${val >= max ? "disabled" : ""}>+</button></div>`;
  }

  function prof() { return state.profile; }
  let editCount = 0;
  function queueSave() {
    editCount++;
    $("#saveMsg").textContent = "Saving…"; $("#saveMsg").className = "save-state";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(doSave, 500);
  }
  // "Best build updated" whenever a save changes the best build's damage
  let toastTimer = null;
  function bestToast(before, beforeW, B) {
    if (!B || before == null || Math.abs(B.dps - before) < 1) return;
    let el = $("#bestToast");
    if (!el) { el = document.createElement("div"); el.id = "bestToast"; el.className = "best-toast"; el.setAttribute("role", "status"); el.setAttribute("aria-live", "polite"); document.body.appendChild(el); }
    const d = B.dps - before, pct = before ? (d / before * 100).toFixed(1) : null;
    el.innerHTML = `<b>Best build updated</b><span class="mono ${d > 0 ? "up" : "down"}">${d > 0 ? "+" : "−"}${num(Math.abs(d))} DPS${pct ? ` (${d > 0 ? "+" : "−"}${Math.abs(pct)}%)` : ""}</span>
      <small>${num(before)} → ${num(B.dps)}${beforeW && beforeW !== B.weapon.name ? ` · now ${esc(B.weapon.name)}` : ""}</small><a href="#/build">See it</a>`;
    el.hidden = false; el.classList.remove("show"); void el.offsetWidth; el.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.classList.remove("show"); }, 4500);
  }
  async function saveNow() {   // flush a pending save and wait for it
    clearTimeout(saveTimer);
    for (let i = 0; saving && i < 600; i++) await new Promise((r) => setTimeout(r, 100));
    if ($("#saveMsg")?.textContent.startsWith("Saving")) await doSave();
  }
  async function doSave() {
    if (saving) { pending = true; return; }
    saving = true;
    const p = prof(), sentAt = editCount;
    const body = { starchrom: p.starchrom, psi_intensity: p.psi_intensity, scenario: p.scenario, armor: p.armor || {}, armor_owned: p.armor_owned || {},
      weapons: p.weapons || [], mods: p.mods || [], extras: p.extras || {}, mod_edits: p.mod_edits || {}, weapon_edits: p.weapon_edits || {},
      accessories_owned: p.accessories_owned || [], accessory_values: p.accessory_values || {} };
    try {
      const r = await fetch("/api/forge/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error(`Server answered ${r.status}`);
      const next = await r.json();
      if (editCount !== sentAt) return;  // you changed something while this was saving; keep it, the next save sends it
      const before = state.result?.best?.dps, beforeW = state.result?.best?.weapon?.name;
      state.result = next.result; state.inventory = next.inventory; state.profile = next.profile;
      render(); renderPage();
      bestToast(before, beforeW, state.result.best);
      $("#saveMsg").textContent = state.result.best ? `Saved · best ${num(state.result.best.dps)} DPS` : "Saved"; $("#saveMsg").className = "save-state ok";
    } catch (e) {
      $("#saveMsg").textContent = `Could not save: ${e.message}`; $("#saveMsg").className = "save-state bad";
    } finally {
      saving = false;
      if (pending) { pending = false; doSave(); }
    }
  }

  function route() {
    const h = (location.hash.match(/^#\/(\w+)/) || [])[1];
    page = h && (h === "build" || PAGES[h]) ? h : "build";
    document.querySelectorAll("[data-nav]").forEach((a) => { if (a.dataset.nav === page) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    $('[data-page="build"]').hidden = page !== "build";
    $('[data-page="gear"]').hidden = page === "build";
    $("#notes").hidden = !["build", "weapons", "armor"].includes(page);
    if (page === "updates") loadUpd();
    if (page === "path") loadPath();
    renderPage();
  }
  function renderPage() {
    if (!state || page === "build") return;
    const [eb, title, hint] = PAGES[page];
    $("#pageHead").innerHTML = `<div><p class="eyebrow">${esc(eb)}</p><h1 class="ph1">${esc(title)}</h1><p class="hint">${esc(hint)}</p></div>`;
    const pane = { weapons: paneWeapons, armor: paneArmor, mods: paneMods, crates: paneCrates, support: paneSupport, profile: paneBasics, later: paneLater, updates: paneUpdates, path: panePath, survive: paneSurvive }[page];
    const f = document.activeElement, fid = f && f.id;
    $("#gearPane").innerHTML = pane();
    if (page === "mods") { gmTipHide(); gmFillInline(); }
    if (fid && /Search$/.test(fid) && $("#" + fid)) { const i = $("#" + fid); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
  }
  const renderGear = renderPage;
  function paneSupport() {
    return `<div class="section-t">Deviation</div>${paneDeviation()}<div class="section-t" style="margin-top:28px">Food &amp; drink</div>${paneFood()}`;
  }

  // weapons
  function weaponFamilyLabel(t) { return String(t || "Other"); }
  function paneWeapons() {
    const c = state.catalog, owned = new Map(state.inventory.weapons.map((w) => [w.name, w]));
    const wd = state.result.weapon_dps || {}, best = state.result.best?.dps || 0;
    const types = [...new Set(c.weapons.map((n) => c.weapon_info[n]?.type).filter(Boolean))].sort();
    const kws = [...new Set(c.weapons.map((n) => c.weapon_info[n]?.keyword).filter(Boolean))].sort();
    const q = wq.toLowerCase();
    let list = c.weapons.filter((n) => {
      const i = c.weapon_info[n] || {};
      if (wLegendary && !i.legendary && !owned.has(n)) return false;
      if (wOwned === "owned" && !owned.has(n)) return false;
      if (wOwned === "missing" && owned.has(n)) return false;
      if (wType !== "all" && i.type !== wType && i.keyword !== wType) return false;
      return !q || `${n} ${i.type} ${i.keyword}`.toLowerCase().includes(q);
    });
    const score = (n) => wd[n]?.dps ?? -1;
    list.sort((x, y) => wSort === "name" ? x.localeCompare(y) : (owned.has(y) - owned.has(x)) * (wSort === "owned" ? 1e9 : 0) + (score(y) - score(x)) || x.localeCompare(y));
    const tiles = list.map((n) => {
      const i = c.weapon_info[n] || {}, w = owned.get(n), e = wd[n];
      let est = "";
      if (e) {
        const d = best ? Math.round(100 * (e.dps / best - 1)) : 0;
        est = `<div class="est"><span>${w ? "best with your gear" : "if you got it (1★)"}</span><b class="${w ? "" : d > 0 ? "up" : "down"}">${num(e.dps)}${!w && best ? ` <small>${d > 0 ? "+" : ""}${d}%</small>` : ""}</b></div>`;
      } else if (!w) est = `<div class="est"><span>${i.legendary ? "not estimated" : "not legendary · not estimated"}</span><b class="down">—</b></div>`;
      if (!w) return `<div class="tile hov dim" data-wname="${esc(n)}">${pic(n, "wide")}
        <div class="tname">${esc(n)}${newTag("weapon", n)}</div><div class="tsub">${esc(i.type || "")}${i.keyword ? ` · <span class="kwc">${esc(i.keyword)}</span>` : ""}</div>${est}
        <button class="btn small own-btn" type="button" data-w-own>+ I own this</button></div>`;
      const fam = c.weapon_family[n];
      const styleMap = c.extras.calibration.styles[fam] || {};
      const styles = Object.keys(styleMap);
      const cal = w.calibration || {};
      const calKey = cal.style ? (styles.find((k) => k.toLowerCase() === String(cal.style).replace(/\s*style\s*$/i, "").trim().toLowerCase()
        || (k === "Rapid Shot" && /^rapid/i.test(cal.style)) || (k === "Lightweight" && /^light\b/i.test(cal.style))) || null) : null;
      const ent = calKey ? styleMap[calKey] : null;
      return `<div class="tile owned" data-wname="${esc(n)}">
        <button class="tile-x" type="button" data-w-remove aria-label="I don't own ${esc(n)}">✕</button>
        ${state.result.best?.weapon?.name === n ? `<span class="in-use">best build</span>` : ""}
        ${pic(n, "wide")}
        <div class="tname">${esc(n)}${newTag("weapon", n)}</div>
        <div class="tsub">${esc(i.type || "")}${i.keyword ? ` · <span class="kwc">${esc(i.keyword)}</span>` : ""}</div>
        ${starPicker(w.stars, "data-w-star")}${est}
        ${(prof().extras?.equipped_weapon === n || (state.inventory.weapons.length === 1))
          ? `<span class="chip good in-hands">In your hands</span>${modOnIt("weapon", "Gun")}`
          : `<button class="btn small" type="button" data-w-hands>Using this gun now</button>`}
        <details class="cal" ${calOpen.has(n) ? "open" : ""}><summary>Calibration ${cal.style ? `· ${esc(cal.style)}` : "· not set"}</summary>
          <div class="cal-grid">
            <label>Style<select data-w-cal="style"><option value="">— none —</option>
              <optgroup label="Standard">${styles.filter((st) => !styleMap[st].seasonal).map((st) => `<option value="${esc(st)}" ${calKey === st ? "selected" : ""}>${esc(st)}</option>`).join("")}</optgroup>
              <optgroup label="Seasonal (Super Anomaly)">${styles.filter((st) => styleMap[st].seasonal).map((st) => `<option value="${esc(st)}" ${calKey === st ? "selected" : ""}>${esc(st)}</option>`).join("")}</optgroup></select></label>
            <label>Attack %<input type="number" min="0" max="50" step="0.1" data-w-cal="attack" value="${esc(cal.attack ?? "")}" placeholder="33–50"></label>
            <label>Bonus line<select data-w-cal="sub"><option value="">— none —</option>${Object.entries(CAL_SUBS).map(([k, v]) => `<option value="${k}" ${cal.sub === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
            <label>Bonus %<input type="number" min="0" max="40" step="0.1" data-w-cal="sub_value" value="${esc(cal.sub_value ?? "")}"></label>
            ${ent?.var ? `<label class="span2">${esc(ent.var.label)}<input type="number" min="0" max="${ent.var.max}" step="0.1" data-w-cal="style_value" value="${esc(cal.style_value ?? "")}" placeholder="${ent.var.default}"></label>` : ""}
          </div>
          ${ent ? `<p class="hint cal-note"><b>${esc(calKey)} style:</b> ${esc(ent.text)}${ent.note ? ` <span class="warn">${esc(ent.note)}</span>` : ""}</p>` : ""}
          ${cal.style && !calKey ? `<p class="hint warn">Saved style “${esc(cal.style)}” isn't available for this gun type.</p>` : ""}
        </details>
        ${magBlock(n, w, i)}
      </div>`;
    }).join("");
    const chip = (attr, v, cur, l) => `<button type="button" class="chip-btn" ${attr}="${esc(v)}" aria-pressed="${cur === v}">${esc(l)}</button>`;
    return `<div class="toolbar">
        <input type="search" id="wSearch" placeholder="Find a weapon…" value="${esc(wq)}" autocomplete="off">
        <div class="chips">${chip("data-wown", "all", wOwned, "All")}${chip("data-wown", "owned", wOwned, `Owned (${owned.size})`)}${chip("data-wown", "missing", wOwned, "Not owned")}</div>
        <select id="wType" aria-label="Type or keyword"><option value="all">Any type / keyword</option>
          <optgroup label="Type">${types.map((t) => `<option ${wType === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</optgroup>
          <optgroup label="Keyword">${kws.map((t) => `<option ${wType === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</optgroup></select>
        <select id="wSort" aria-label="Sort"><option value="dps" ${wSort === "dps" ? "selected" : ""}>Sort: estimated DPS</option><option value="owned" ${wSort === "owned" ? "selected" : ""}>Sort: owned first</option><option value="name" ${wSort === "name" ? "selected" : ""}>Sort: name</option></select>
        <label class="check"><input type="checkbox" id="wLeg" ${wLegendary ? "checked" : ""}> Legendary only</label>
        <span class="grow"></span><span class="count">${list.length} shown</span>
      </div>
      <div class="tile-grid wide">${tiles || `<p class="empty-msg">No weapons match.</p>`}</div>
      <p class="hint" style="margin-top:12px">DPS numbers are estimates for the fight type in Class &amp; settings, using the mods, armor, deviation and food you have now. Unowned weapons are counted at 1★ with no calibration.</p>`;
  }
  function magBlock(n, w, i) {
    const M = state.catalog?.magazines; if (!M) return "";
    const fitsT = (m) => m.fits.includes("*") || m.fits.includes(i.type);
    const mags = M.items.filter(fitsT); if (!mags.length) return "";
    const p = prof(), own = new Set(p.accessories_owned || []), vals = p.accessory_values || {};
    const cur = w.magazine ?? w.magazine_acc ?? "";
    const curName = (mags.find((m) => m.id === cur) || {}).name;
    const base = M.reload_s[i.type] ?? 2.4;
    return `<details class="cal mag" ${calOpen.has(n + "#mag") ? "open" : ""} data-magkey="${esc(n)}#mag"><summary>Magazine · ${esc(curName || "none")}</summary>
      <div class="cal-grid">
        <label class="span2">On the gun now<select data-w-mag><option value="">— no magazine —</option>${mags.map((m) => `<option value="${esc(m.id)}" ${cur === m.id ? "selected" : ""}>${esc(m.name)} (${esc(m.rarity)})</option>`).join("")}</select></label>
        <label class="span2">Reload time you timed (s)<input type="number" min="0.3" max="10" step="0.01" data-w-reload value="${esc(w.reload_s ?? "")}" placeholder="${base} (estimate, no mag)"></label>
      </div>
      <div class="mag-own"><span class="hint">Unlocked magazines (the Best build picks the best one you have):</span>
        ${mags.map((m) => `<label class="check mag-row"><input type="checkbox" data-mag-own="${esc(m.id)}" ${own.has(m.id) ? "checked" : ""}>
          <span><b>${esc(m.name)}</b> <small>${esc(m.text)}${m.confirmed ? "" : " · estimate"}</small>
          ${m.confirmed ? "" : `<span class="mag-val-row">Your tooltip reload %<input type="number" step="0.1" min="-50" max="50" class="mag-val" data-mag-val="${esc(m.id)}" value="${esc(vals[m.id]?.reload_speed ?? "")}" placeholder="${esc(m.stats.reload_speed)}"></span>`}</span></label>`).join("")}
      </div></details>`;
  }
  function magPanel(mc) {
    if (!mc || mc.error || !mc.rows) return "";
    const pc = (v) => v == null ? "—" : `${Math.round(v * 100)}%`;
    const zone = mc.rows.some((r) => r.zone_uptime != null);
    const rows = mc.rows.map((r) => `<tr class="${r.id === mc.best_owned ? "win" : ""}">
      <td><b>${esc(r.name)}</b>${r.equipped ? ` <span class="chip good">on gun</span>` : ""}${!r.owned ? ` <span class="chip">not unlocked</span>` : ""}${r.confirmed ? "" : ` <span class="chip warn">estimate</span>`}<br><small>${esc(r.text)}</small></td>
      <td>${num(r.dps)}<br><small class="${r.vs_equipped_pct > 0 ? "up" : r.vs_equipped_pct < 0 ? "down" : ""}">${r.vs_equipped_pct > 0 ? "+" : ""}${r.vs_equipped_pct}%</small></td>
      <td>${r.magazine}</td><td>${r.reload_s}s</td><td>${r.cycle_s}s</td><td>${pc(r.uptime)}</td>${zone ? `<td>${pc(r.zone_uptime)}</td>` : ""}</tr>`).join("");
    const pick = mc.best_owned && mc.best_owned !== mc.equipped
      ? `Best magazine you have: <b>${esc(mc.best_owned_name)}</b>.` : mc.best_owned ? `<b>${esc(mc.best_owned_name)}</b> is already the best one you have.` : "";
    const better = mc.best !== mc.best_owned ? ` If you unlock <b>${esc(mc.best_name)}</b> it would be the top pick.` : "";
    return `<div class="section-t">Magazine choice · estimate</div>
      <div class="mag-panel"><p>${pick}${better}</p>
      <div class="tbl-wrap"><table class="mag-tbl"><thead><tr><th>Magazine</th><th>DPS</th><th>Ammo</th><th>Reload</th><th>Cycle</th><th>Firing</th>${zone ? "<th>Zone</th>" : ""}</tr></thead><tbody>${rows}</tbody></table></div>
      <ul class="plain">${mc.why.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
      <details><summary>Not counted (${mc.not_counted.length})</summary><ul>${mc.not_counted.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></details></div>`;
  }
  function weaponEdit(name, patch) {
    const p = prof();
    const manual = (p.weapons || []).find((w) => w.name === name);
    if (manual) Object.assign(manual, patch);
    else { p.weapon_edits = p.weapon_edits || {}; p.weapon_edits[name] = Object.assign({}, p.weapon_edits[name], patch); }
    const inv = state.inventory.weapons.find((w) => w.name === name);
    if (inv) Object.assign(inv, patch);
  }
  function removeWeapon(name) {
    const p = prof();
    const had = (p.weapons || []).length;
    p.weapons = (p.weapons || []).filter((w) => w.name !== name);
    const src = state.inventory.weapons.find((w) => w.name === name)?.source;
    if (src === "recorded" || p.weapons.length === had) { p.weapon_edits = p.weapon_edits || {}; p.weapon_edits[name] = { removed: true }; }
    state.inventory.weapons = state.inventory.weapons.filter((w) => w.name !== name);
  }
  function addWeapon(name) {
    const p = prof();
    if (p.weapon_edits && p.weapon_edits[name]) delete p.weapon_edits[name];
    if (!state.inventory.weapons.some((w) => w.name === name)) {
      p.weapons = [...(p.weapons || []), { name, stars: 1, tier: 5 }];
      state.inventory.weapons.push({ name, stars: 1, source: "profile" });
    }
  }

  // armor
  // armor you OWN (several per slot) vs. armor you WEAR (one per slot). Wearing a piece also marks it owned.
  function ownedArmor() {
    const p = prof(), o = { ...(p.armor_owned || {}) };
    Object.values(p.armor || {}).forEach((x) => { if (x?.name && !o[x.name]) o[x.name] = { stars: +x.stars || 1 }; });
    return o;
  }
  function own(name, on) {
    const p = prof(); p.armor_owned = { ...(p.armor_owned || {}) };
    if (on) p.armor_owned[name] = p.armor_owned[name] || { stars: 1 };
    else {
      delete p.armor_owned[name];
      Object.entries(p.armor || {}).forEach(([sl, x]) => { if (x?.name === name) delete p.armor[sl]; });   // can't wear what you don't own
    }
  }
  // anything you've worn stays in "Armor you own" when you take it off or swap it
  function keepWornOwned(p) {
    p.armor_owned = { ...(p.armor_owned || {}) };
    Object.values(p.armor || {}).forEach((x) => { if (x?.name && !p.armor_owned[x.name]) p.armor_owned[x.name] = { stars: +x.stars || 1 }; });
  }
  function wear(slot, name) {
    const p = prof(); p.armor = p.armor || {};
    keepWornOwned(p);
    if (!name) { delete p.armor[slot]; return; }
    const st = +(ownedArmor()[name]?.stars) || 1;
    p.armor[slot] = { name, stars: st, tier: 5 };
    p.armor_owned = { ...(p.armor_owned || {}), [name]: { stars: st } };
  }
  function armorStars(name, n) {
    const p = prof(); p.armor_owned = { ...(p.armor_owned || {}), [name]: { stars: n } };
    Object.values(p.armor || {}).forEach((x) => { if (x?.name === name) x.stars = n; });
  }
  function slotOf(name) { return state.catalog.armor_info[name]?.slot; }
  // "mod on it right now" for one armor slot or the gun in your hands
  function eqOf(slotKey) { return (prof().extras?.equipped || {})[slotKey] || null; }
  // the best mod from your collection for this piece, with a one-tap "I put it on"
  function bestFor(slotKey) {
    const B = state.result?.best;
    if (!B) return null;
    if (slotKey === "weapon") {
      const inHands = prof().extras?.equipped_weapon || (state.inventory.weapons.length === 1 ? state.inventory.weapons[0].name : null);
      if (inHands !== B.weapon.name) return null;
    }
    return B.mods?.[slotKey] || null;
  }
  function gmMini(slotKey, name, variant, level) {
    const A = modArt(), art = A.tiles[`${slotKey}|${name}|${variant}`.toLowerCase()];
    return `<span class="gm-mini ${RARITY(level)}" title="${esc(variant)} · Lv ${esc(level)}"><span class="gm-mini-d"></span>${art ? `<img src="${esc(art)}" alt="">` : ""}<span class="gm-mini-lv">${esc(level)}</span></span>`;
  }
  function modBest(slotKey) {
    const b = bestFor(slotKey), m = eqOf(slotKey);
    if (!b) return "";
    const same = m && m.name === b.name && (m.variant || "General") === b.variant;
    if (same) return `<div class="mod-best ok"><span class="chip good">Best mod you own</span></div>`;
    return `<div class="mod-best"><small>Best from your collection</small><span class="mb-row">${gmMini(slotKey, b.name, b.variant, b.level)}<span><b>${esc(b.name)}</b><span class="mb-v">${esc(b.variant)} · Lv ${esc(b.level)}</span></span></span>
      <button class="btn small primary" type="button" data-eq-best="${slotKey}">I put it on</button></div>`;
  }
  function modOnIt(slotKey, label) {
    return modOnItNow(slotKey, label) + modBest(slotKey);
  }
  function modOnItNow(slotKey, label) {
    const m = eqOf(slotKey);
    if (!m) return `<button class="btn small mod-on-add" type="button" data-eq-pick="${slotKey}">+ Mod on it now</button>`;
    return `<div class="mod-on" data-eq="${slotKey}">${gmMini(slotKey, m.name, m.variant, m.level)}<span class="mod-on-t"><small>${esc(label)} mod now</small><b>${esc(m.name)}</b><small>${esc(m.variant)}</small></span>
      <span class="mod-on-ctl"><label class="mc-lv">Lv<input type="number" min="1" max="17" inputmode="numeric" data-eq-lv="${slotKey}" value="${m.level || 10}" aria-label="${esc(m.name)} level"></label>
      <button type="button" class="mc-x" data-eq-swap="${slotKey}" aria-label="Change mod" title="Change mod">⇄</button><button type="button" class="mc-x" data-eq-clear="${slotKey}" aria-label="Remove mod" title="Remove mod">✕</button></span></div>`;
  }
  function setEq(slotKey, mod) {
    const p = prof(); const ex = { ...(p.extras || {}) }; const eq = { ...(ex.equipped || {}) };
    if (mod) eq[slotKey] = mod; else delete eq[slotKey];
    ex.equipped = eq; p.extras = ex;
  }
  function paneArmor() {
    const c = state.catalog, armor = prof().armor || {};
    const worn = new Set(Object.values(armor).map((x) => x.name));
    const wearing = ARMOR_SLOTS.map((slot) => {
      const cur = armor[slot], key = cur && c.extras.key_armor[cur.name], info = cur ? c.armor_info[cur.name] || {} : {};
      return `<div class="tile ${cur ? "owned" : ""}" data-aslot="${slot}">
        ${cur ? `<button class="tile-x" type="button" data-a-clear aria-label="Take off ${esc(cur.name)}">✕</button>` : ""}
        <button class="tile-pick" type="button" data-a-slotfilter aria-label="Show ${slot} pieces">
          ${cur ? pic(cur.name) : `<span class="pic ph" aria-hidden="true">+</span>`}
          <div class="tslot">${slot}</div>
          <div class="tname">${cur ? esc(cur.name) : "Empty"}</div>
          <div class="tsub">${cur ? (key ? `<span class="kwc">Key armor</span>` : esc(info.set ? `${info.set} set` : "")) : "tap to choose"}</div>
        </button>
        ${cur ? starPicker(+cur.stars || 1, "data-a-star") : ""}
        ${cur ? modOnIt(slot.toLowerCase(), slot) : ""}
      </div>`;
    }).join("");
    const owned = ownedArmor();
    const ownedNames = Object.keys(owned);
    const perSlot = ARMOR_SLOTS.map((sl) => [sl, ownedNames.filter((n) => slotOf(n) === sl)]);
    const ownedHtml = `<div class="section-t">Armor you own · ${ownedNames.length} piece${ownedNames.length === 1 ? "" : "s"}</div>
      <p class="hint">Every piece or blueprint you have, even if it's in a box. Tap a piece in any set below to mark it owned; tap "Wear" to put it on. Upgrades only charge Starchrom for pieces you don't own.</p>
      <div class="chips owned-count">${perSlot.map(([sl, l]) => `<span class="chip ${l.length ? "good" : ""}">${sl} · ${l.length}</span>`).join("")}</div>
      ${ownedNames.length ? `<div class="owned-armor">${perSlot.filter(([, l]) => l.length).map(([sl, l]) => `<div class="oa-slot"><div class="tslot">${sl}</div>${l.map((n) => {
        const on = (armor[sl] || {}).name === n, info = c.armor_info[n] || {}, isKey = !!c.extras.key_armor[n];
        return `<div class="oa-item ${on ? "on" : ""}" data-aname="${esc(n)}">${pic(n, "sm")}<span class="oa-t"><b>${esc(n)}</b><small>${isKey ? "Key armor" : esc(info.set ? `${info.set} set` : "")}</small></span>
          ${starPicker(+owned[n].stars || 1, "data-ao-star")}
          ${on ? `<span class="chip good">Wearing</span>` : `<button class="btn small" type="button" data-ao-wear>Wear</button>`}
          <button class="mc-x" type="button" data-ao-del aria-label="I don't own ${esc(n)}" title="I don't own this">✕</button></div>`;
      }).join("")}</div>`).join("")}</div>` : `<p class="empty-msg">No armor marked yet. Find your pieces in the sets below and tap them.</p>`}`;
    const counts = state.result.best?.sets || {};
    const sd = state.result.set_dps || {}, best = state.result.best?.dps || 0;
    const q = aq.toLowerCase();
    const sets = Object.entries(c.sets).map(([k, v]) => ({ k, v, pieces: Object.entries(v.pieces || {}) }))
      .filter((x) => x.pieces.length && (!q || `${x.k} ${Object.values(x.v.effects).join(" ")} ${x.pieces.map((p) => p[1]).join(" ")}`.toLowerCase().includes(q)))
      .filter((x) => aSlot === "all" || x.pieces.some(([s]) => s.toLowerCase() === aSlot.toLowerCase()));
    sets.sort((x, y) => (counts[y.k] || 0) - (counts[x.k] || 0) || (sd[y.k]?.dps || 0) - (sd[x.k]?.dps || 0) || x.k.localeCompare(y.k));
    const setCards = sets.map(({ k, v, pieces }) => {
      const n = counts[k] || 0, e = sd[k];
      const fx = Object.entries(v.effects).map(([pc, t]) => `<span class="${n >= +pc ? "hit" : ""}"><b>${pc}pc</b>${esc(t)}</span>`).join("");
      const ps = pieces.filter(([s]) => aSlot === "all" || s.toLowerCase() === aSlot.toLowerCase()).map(([s, nm]) => {
        const has = !!owned[nm], on = worn.has(nm);
        return `<span class="piece-wrap"><button type="button" class="piece ${on ? "on" : has ? "own" : "no"}" data-own="${esc(nm)}" aria-pressed="${has}" title="${has ? "You own this. Tap to unmark" : "Tap if you own this"}">
          ${pic(nm, "sm")}<span><small>${esc(s)}${on ? " · wearing" : has ? " · owned" : ""}</small>${esc(nm)}</span></button>${has && !on ? `<button type="button" class="piece-wear" data-wear="${esc(nm)}" aria-label="Wear ${esc(nm)}">Wear</button>` : ""}</span>`;
      }).join("");
      const ownN = pieces.filter(([, nm]) => owned[nm]).length;
      return `<div class="set ${n ? "on" : ""}"><h3>${esc(k)}${newTag("set", k)} ${n ? `<span class="chip good">wearing ${n}pc</span>` : ""}${ownN ? ` <span class="chip">own ${ownN} of ${pieces.length}</span>` : ""}</h3>
        <div class="sest">${e ? `${e.gain_pct >= 0 ? "+" : ""}${(+e.gain_pct).toFixed(1)}%<small>4pc on your best build</small>` : n ? "" : `<small>no damage gain counted</small>`}</div>
        <div class="fx">${fx}</div><div class="pieces">${ps}</div></div>`;
    }).join("");
    const keys = Object.entries(c.extras.key_armor).filter(([nm]) => (aSlot === "all" || (slotOf(nm) || "").toLowerCase() === aSlot.toLowerCase()) && (!q || `${nm} ${c.extras.key_armor[nm].text}`.toLowerCase().includes(q)));
    const keyTiles = keys.map(([nm, k]) => {
      const has = !!owned[nm], on = worn.has(nm);
      return `<div class="tile key-tile ${on ? "on" : has ? "owned" : "dim"}"><button type="button" class="tile-pick" data-own="${esc(nm)}" aria-pressed="${has}" title="${has ? "You own this. Tap to unmark" : "Tap if you own this"}">
      ${pic(nm)}<div class="tslot">${esc(slotOf(nm) || "")}${on ? " · wearing" : has ? " · owned" : ""}</div><div class="tname">${esc(nm)}${newTag("armor", nm)}</div><div class="tsub">${esc(k.text)}</div></button>
      ${has && !on ? `<button type="button" class="btn small" data-wear="${esc(nm)}">Wear</button>` : ""}</div>`;
    }).join("");
    const slotChips = ["all", ...ARMOR_SLOTS].map((s) => `<button type="button" class="chip-btn" data-aslotf="${s}" aria-pressed="${aSlot === s}">${s === "all" ? "All slots" : s}</button>`).join("");
    const counted = Object.entries(counts).map(([k, v]) => `${esc(k)} ${v}pc`).join(" + ");
    return `<div class="section-t">Wearing now</div><div class="wearing">${wearing}</div>
      <p class="hint">Sets counted: ${counted || "none"}. Key armor doesn't count toward a set. Stars on armor raise Psi Intensity.</p>
      ${ownedHtml}
      ${hidePanel()}
      <div class="toolbar" style="margin-top:16px"><input type="search" id="aSearch" placeholder="Find a set, piece or effect…" value="${esc(aq)}" autocomplete="off"><div class="chips">${slotChips}</div></div>
      <div class="split"><div><div class="section-t">Armor sets</div><div class="sets">${setCards || `<p class="empty-msg">No sets match.</p>`}</div></div>
        <div class="panel-side"><div class="section-t">Key armor</div><div class="tile-grid">${keyTiles || `<p class="empty-msg">No key armor for this slot.</p>`}</div></div></div>`;
  }

  // mods
  function modKey(m) { return `${m.name}|${m.variant}`.toLowerCase(); }
  let modView = "all", modFam = "all";
  const FAMS = ["Burn", "Frost Vortex", "Power Surge", "Shrapnel", "Unstable Bomber", "Bounce", "Fast Gunner", "The Bull's Eye", "Fortress Warfare"];
  function modFamily(m) {
    const t = `${m.name} ${m.summary || ""}`.toLowerCase();
    const k = FAMS.find((f) => t.includes(f.toLowerCase()) || (f === "The Bull's Eye" && t.includes("bull's eye")));
    if (k) return k;
    if (/dmg reduction|healing|shield|purge|movement speed|deviated states|max hp/.test(t) && !/weapon dmg|crit dmg|status dmg/.test(t)) return "Survival";
    if (/elemental|status dmg/.test(t)) return "Elemental & status";
    if (/crit|weakspot/.test(t)) return "Crit & weakspot";
    if (/reload|magazine|bullet|refill/.test(t)) return "Reload & ammo";
    return "Damage boosts";
  }
  // Mods page laid out like the game's Mods screen: slot tabs, one row per mod, a tile per variant.
  // Owned tiles are colored by level (the game's rarity colors), locked tiles are dark with a lock.
  let gmSel = null;   // "slot|name" row whose level editor is open, plus the tile key
  const RARITY = (lv) => !lv ? "locked" : lv <= 2 ? "common" : lv <= 4 ? "uncommon" : lv <= 6 ? "rare" : lv <= 8 ? "epic" : "legendary";
  const RARITY_NAME = { common: "White", uncommon: "Green", rare: "Blue", epic: "Purple", legendary: "Gold" };
  const LOCK = `<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M4.5 7V5.2a3.5 3.5 0 0 1 7 0V7h.7c.7 0 1.3.6 1.3 1.3v5.4c0 .7-.6 1.3-1.3 1.3H3.8c-.7 0-1.3-.6-1.3-1.3V8.3C2.5 7.6 3.1 7 3.8 7h.7zm1.6 0h3.8V5.2a1.9 1.9 0 0 0-3.8 0V7z"/></svg>`;
  function modArt() { return state.catalog.mod_art || { tiles: {}, emblems: {}, order: {}, weapon_group: {}, groups: {}, slots: ["weapon", "helmet", "top", "bottoms", "shoes", "gloves", "mask"], variant_order: [] }; }
  function variantRank(v) {
    const VO = modArt().variant_order || [], de = v !== "Deviant Energy" && v.endsWith("Deviant Energy");
    const base = de ? v.replace(/ Deviant Energy$/, "") : v, i = VO.indexOf(base);
    return (de ? 100 : 0) + (i < 0 ? 6 : i);
  }
  // Shiny level 17: color-shifting rim, a light sweep, and twinkling stars (still when the OS asks for reduced motion)
  const SHINY_FX = `<span class="gm-holo" aria-hidden="true"></span><span class="gm-sweep" aria-hidden="true"></span>
        <span class="gm-twinkle" aria-hidden="true">${"<i></i>".repeat(9)}</span>`;
  function gmTile(m, v, own, used, sel) {
    const A = modArt(), key = modKey({ name: m.name, variant: v }), o = own.get(key), r = RARITY(o?.level);
    const art = A.tiles[`${m.slot}|${m.name}|${v}`.toLowerCase()];
    const label = `${m.name} · ${v}${o ? ` · Lv ${o.level}${o.shiny ? " Shiny" : ""} (${RARITY_NAME[r]})` : " · not owned"}`;
    return `<button type="button" class="gm-tile ${r} ${o?.shiny ? "shiny" : ""} ${sel === key ? "sel" : ""}" data-gm="${esc(m.name)}|${esc(v)}" data-gslot="${esc(m.slot)}" title="${esc(label)}" aria-label="${esc(label)}" aria-pressed="${sel === key}">
        ${o ? `<span class="gm-lv">${o.level}${o.shiny ? `<span class="gm-shiny-star" aria-hidden="true">✦</span>` : ""}</span>` : `<span class="gm-lock">${LOCK}</span>`}
        ${used.has(key) ? `<span class="gm-inb" title="Used in your best build">IN BUILD</span>` : ""}
        ${r === "legendary" ? `<span class="gm-spark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></span>` : ""}
        ${o?.shiny ? SHINY_FX : ""}
        <span class="gm-dia">${art ? `<img src="${esc(art)}" alt="" loading="lazy" decoding="async">` : `<b>${esc(v.slice(0, 2))}</b>`}</span>
        <span class="gm-var">${esc(v)}</span></button>`;
  }
  function gmEditor(m, v, own) {
    const key = modKey({ name: m.name, variant: v }), o = own.get(key), A = modArt();
    const art = A.tiles[`${m.slot}|${m.name}|${v}`.toLowerCase()];
    const lvBtns = Array.from({ length: 17 }, (_, i) => i + 1).map((n) =>
      `<button type="button" class="gm-lvb ${RARITY(n)} ${o?.level === n ? "on" : ""}" data-gm-lv="${n}" aria-pressed="${o?.level === n}" aria-label="Level ${n}">${n}</button>`).join("");
    return `<div class="gm-edit" data-gm-edit="${esc(m.name)}|${esc(v)}">
        <div class="gm-edit-h"><span class="gm-dia sm ${RARITY(o?.level)} ${o?.shiny ? "shiny-dia" : ""}">${art ? `<img src="${esc(art)}" alt="">` : ""}</span>
          <div><b>${esc(m.name)}</b>${o?.shiny ? ` <span class="shiny-text">✦ Shiny</span>` : ""} <span class="muted">· ${esc(v)}</span><small>${o ? `You have it at Lv ${o.level} (${RARITY_NAME[RARITY(o.level)]}). Tap another level to change it.` : "Not in your collection yet. Tap the level it shows in the game to add it."}</small></div>
          <button type="button" class="mc-x gm-close" data-gm-close aria-label="Close">✕</button></div>
        <div class="gm-lvs" role="group" aria-label="Level">${lvBtns}</div>
        ${o?.level === 17 ? `<div class="gm-shiny ${o.shiny ? "on" : ""}">
          <label class="check"><input type="checkbox" data-gm-shiny ${o.shiny ? "checked" : ""}> Shiny (the glowing level 17 version)</label>
          ${o.shiny ? `<p class="hint">Shiny mods have a slightly higher main effect and an extra Shiny effect. The numbers are different for each mod and no data source lists them yet, so type them from your in-game tooltip. Leave a box empty and the app counts it as a normal level 17.</p>
            <label>Main effect, as your Shiny tooltip shows it<textarea rows="2" data-gm-shiny-main placeholder="e.g. copy the top effect line from the tooltip">${esc(o.shiny_main || "")}</textarea></label>
            <label>Extra Shiny effect line<textarea rows="2" data-gm-shiny-extra placeholder="e.g. Frost Vortex DMG +5%">${esc(o.shiny_extra || "")}</textarea></label>` : ""}
        </div>` : ""}
        <div class="gm-info-inline" data-gm-info="${esc(m.slot)}|${esc(m.name)}|${esc(v)}|${o?.level || 0}"></div>
        ${o ? `<button type="button" class="btn small ghost gm-del" data-gm-del>I don't have this one</button>` : ""}
      </div>`;
  }
  // Hover card: the game's mod tooltip, plus whether each line is in the damage math.
  const gmInfoCache = new Map();
  async function gmInfo(name, variant, level) {
    const k = `${name}|${variant}|${level}`;
    if (!gmInfoCache.has(k)) gmInfoCache.set(k, fetch(`/api/forge/mod_info?${new URLSearchParams({ name, variant, level })}`).then((r) => r.json()).catch(() => null));
    return gmInfoCache.get(k);
  }
  const SLOT_KIND = { weapon: "Weapon Mods", helmet: "Armor Mods-Helmet", mask: "Armor Mods-Mask", top: "Armor Mods-Top", gloves: "Armor Mods-Gloves", bottoms: "Armor Mods-Bottoms", shoes: "Armor Mods-Shoes" };
  function gmCardHtml(I, slot, owned) {
    if (!I || I.error) return `<p class="hint">No details for this mod.</p>`;
    const r = owned ? RARITY(I.level) : "locked", art = modArt().tiles[`${slot}|${I.name}|${I.variant}`.toLowerCase()];
    const coreTag = I.core_keywords.length ? `<span class="gm-tag kw">Only with ${esc(I.core_keywords.join(", "))} weapons</span>`
      : I.core_counted ? `<span class="gm-tag in">In DPS</span>` : I.core_partial ? `<span class="gm-tag part">Partly in DPS</span>` : `<span class="gm-tag out">Not in DPS</span>`;
    const lines = I.lines.map((l) => {
      const label = l.line.replace(/\s*\+?-?X%?\.?$/, "").replace(/^(Lunar|Crescent|Mirror|Wild|Phantasmal|Downstar|Aero|Resonance|Battlefield):\s*/, "$1: ");
      return `<li class="${l.counted ? "" : "off"}"><div class="gm-ln"><span>${esc(label)} ${l.counted ? `<span class="gm-tag in">In DPS</span>` : `<span class="gm-tag out">Not in DPS</span>`}</span><b class="mono">${esc(l.text || "—")}</b></div>
        ${l.note ? `<div class="gm-ln-sub"><small>${esc(l.note)}</small></div>` : ""}</li>`;
    }).join("");
    return `<div class="gm-card-h ${r}"><b>${esc(I.name)} &lt;${esc(I.variant)}&gt;</b><small>${esc(SLOT_KIND[slot] || I.slot || "")}</small></div>
      <div class="gm-card-core"><div class="gm-ln"><b>${esc(I.name)}</b>${coreTag}</div><p>${esc(I.core)}</p></div>
      <div class="gm-card-var"><span class="gm-dia sm ${r}">${art ? `<img src="${esc(art)}" alt="">` : ""}</span>
        <span class="gm-card-lv"><span>${owned ? I.level : LOCK}</span></span><b>${esc(I.variant)}</b>${owned ? "" : `<small>not owned · numbers at Lv 17</small>`}</div>
      <ul class="gm-card-lines">${lines}</ul>
      <p class="gm-card-foot">${esc(I.level_note)}</p>`;
  }
  let gmTipEl = null, gmTipFor = null, gmTipTimer = null;
  function gmTipHide() { clearTimeout(gmTipTimer); gmTipFor = null; if (gmTipEl) gmTipEl.hidden = true; }
  async function gmTipShow(tile) {
    const [name, variant] = tile.dataset.gm.split("|"), slot = tile.dataset.gslot;
    const o = state.inventory.mods.find((x) => modKey(x) === modKey({ name, variant }));
    gmTipFor = tile;
    const I = await gmInfo(name, variant, o ? o.level : 17);
    if (gmTipFor !== tile || !document.body.contains(tile)) return;
    if (!gmTipEl) { gmTipEl = document.createElement("div"); gmTipEl.className = "gm-card gm-tip"; gmTipEl.setAttribute("role", "tooltip"); document.body.appendChild(gmTipEl); }
    gmTipEl.innerHTML = gmCardHtml(I, slot, !!o); gmTipEl.hidden = false;
    const b = tile.getBoundingClientRect(), w = gmTipEl.offsetWidth, h = gmTipEl.offsetHeight;
    let x = b.right + 10; if (x + w > innerWidth - 8) x = b.left - w - 10; if (x < 8) x = Math.max(8, Math.min(innerWidth - w - 8, b.left));
    let y = Math.min(Math.max(8, b.top - 10), innerHeight - h - 8);
    gmTipEl.style.left = `${x}px`; gmTipEl.style.top = `${Math.max(8, y)}px`;
  }
  let lastPointer = "mouse";
  document.addEventListener("pointerdown", (e) => { lastPointer = e.pointerType; if (e.pointerType !== "mouse") gmTipHide(); }, true);
  document.addEventListener("pointerover", (e) => {
    if (e.pointerType !== "mouse") return;
    lastPointer = "mouse";
    const t = e.target.closest?.(".gm-tile");
    if (!t || t === gmTipFor) return;
    clearTimeout(gmTipTimer); gmTipTimer = setTimeout(() => gmTipShow(t), 90);
  });
  document.addEventListener("pointerout", (e) => {
    const t = e.target.closest?.(".gm-tile");
    if (t && !t.contains(e.relatedTarget)) gmTipHide();
  });
  document.addEventListener("focusin", (e) => { const t = e.target.closest?.(".gm-tile"); if (t && t.matches(":focus-visible")) gmTipShow(t); });
  document.addEventListener("focusout", (e) => { if (e.target.closest?.(".gm-tile")) gmTipHide(); });
  addEventListener("scroll", gmTipHide, { passive: true });
  async function gmFillInline() {
    const el = document.querySelector("[data-gm-info]");
    if (!el) return;
    const [slot, name, variant, lv] = el.dataset.gmInfo.split("|");
    const I = await gmInfo(name, variant, +lv || 17);
    if (document.body.contains(el)) el.innerHTML = `<div class="gm-card">${gmCardHtml(I, slot, +lv > 0)}</div>`;
  }
  function paneMods() {
    const A = modArt(), C = state.catalog.mods, inv = state.inventory.mods;
    const own = new Map(inv.map((m) => [modKey(m), m]));
    const used = new Set(Object.values(state.result.best?.mods || {}).filter(Boolean).map(modKey));
    if (!A.slots.includes(modSlot)) modSlot = "weapon";
    const q = modFilter.toLowerCase().trim(), mine = modView === "mine";
    const rows = C.map((m) => ({ ...m, fam: modFamily(m), vars: m.variants.length ? m.variants : ["General"] }));
    const count = (sl) => { const r = rows.filter((m) => m.slot === sl); return [r.reduce((n, m) => n + m.vars.filter((v) => own.has(modKey({ name: m.name, variant: v }))).length, 0), r.reduce((n, m) => n + m.vars.length, 0)]; };
    const tabs = A.slots.map((sl) => { const [h, t] = count(sl);
      return `<button type="button" class="gm-tab" role="tab" data-mslot="${sl}" aria-selected="${!q && modSlot === sl}"><span>${esc(SLOT_NAME[sl] || sl)}</span><small>${h}/${t}</small></button>`; }).join("");
    const isW = modSlot === "weapon" && !q;
    // Only the weapon tab has real game families; armor tabs are one list in game order, like the game.
    const famList = isW ? Object.keys(A.groups) : [];
    if (modFam !== "all" && !famList.includes(modFam)) modFam = "all";
    const famOf = (m) => m.slot === "weapon" ? (A.weapon_group[m.name.toLowerCase()] || "other") : m.fam;
    let shown = rows.filter((m) => q ? `${m.name} ${m.summary} ${m.fam} ${SLOT_NAME[m.slot] || ""} ${A.groups[famOf(m)]?.label || ""} ${m.vars.join(" ")}`.toLowerCase().includes(q)
      : m.slot === modSlot && (modFam === "all" || famOf(m) === modFam));
    if (mine) shown = shown.filter((m) => m.vars.some((v) => own.has(modKey({ name: m.name, variant: v }))));
    const ord = (m) => A.order[`${m.slot}|${m.name.toLowerCase()}`] ?? 999;
    shown.sort((x, y) => (q ? A.slots.indexOf(x.slot) - A.slots.indexOf(y.slot) : 0) || ord(x) - ord(y) || x.name.localeCompare(y.name));
    const famChips = famList.length > 1 ? `<div class="chips gm-fams"><button type="button" class="chip-btn" data-mfam="all" aria-pressed="${modFam === "all"}">All</button>${famList.map((f) =>
      `<button type="button" class="chip-btn" data-mfam="${esc(f)}" aria-pressed="${modFam === f}">${isW && A.groups[f] ? `<img class="gm-ficon" src="${esc(A.groups[f].icon)}" alt="">` : ""}${esc(A.groups[f]?.label || f)}</button>`).join("")}</div>` : "";
    const [selName, selVar] = (gmSel || "").split("|");
    const rowHtml = (m) => {
      const vars = [...m.vars].filter((v) => !mine || own.has(modKey({ name: m.name, variant: v })))
        .sort((x, y) => (own.get(modKey({ name: m.name, variant: y }))?.level || 0) - (own.get(modKey({ name: m.name, variant: x }))?.level || 0) || variantRank(x) - variantRank(y));
      const h = m.vars.filter((v) => own.has(modKey({ name: m.name, variant: v }))).length;
      const emb = A.emblems[`${m.slot}|${m.name}`.toLowerCase()];
      const selKey = selName === m.name ? modKey({ name: selName, variant: selVar }) : null;
      return `<section class="gm-row ${h ? "has" : ""}">
          <div class="gm-head">${emb ? `<img class="gm-emb" src="${esc(emb)}" alt="" loading="lazy">` : pic(m.name, "gm-emb")}
            <div class="gm-name"><b>${esc(m.name)}${newTag("mod", m.name)}</b>${q ? `<span class="chip">${esc(SLOT_NAME[m.slot] || m.slot)}</span>` : ""}
              <small class="gm-own ${h ? "on" : ""}">${h} of ${m.vars.length} owned</small>
              <p>${esc(m.summary)}</p></div></div>
          <div class="gm-body"><div class="gm-tiles">${vars.map((v) => gmTile(m, v, own, used, selKey)).join("")}</div>
            ${selKey && m.vars.includes(selVar) ? gmEditor(m, selVar, own) : ""}</div></section>`;
    };
    let body = "";
    if (isW && modFam === "all") {
      for (const g of [...Object.keys(A.groups), "other"]) {
        const list = shown.filter((m) => famOf(m) === g);
        if (!list.length) continue;
        const G = A.groups[g];
        body += `<div class="gm-group"><div class="gm-group-h">${G ? `<img src="${esc(G.icon)}" alt="">` : ""}<span>${esc(G?.label || "Other")}</span></div>${list.map(rowHtml).join("")}</div>`;
      }
    } else body = shown.map(rowHtml).join("");
    const views = `<div class="view-tabs" role="tablist"><button type="button" role="tab" class="vt ${!mine ? "on" : ""}" aria-selected="${!mine}" data-mview="all">All mods</button>
      <button type="button" role="tab" class="vt ${mine ? "on" : ""}" aria-selected="${mine}" data-mview="mine">Only mine · ${inv.length}</button></div>`;
    const legend = `<div class="gm-legend"><span><i class="sw legendary"></i>Gold · Lv 9–17</span><span><i class="sw epic"></i>Purple · Lv 7–8</span><span><i class="sw rare"></i>Blue · Lv 5–6</span><span><i class="sw uncommon"></i>Green · Lv 3–4</span><span><i class="sw common"></i>White · Lv 1–2</span><span><i class="sw locked">${LOCK}</i>Locked · you don't have it</span></div>`;
    return `<div class="gm-top">${views}<input type="search" id="modSearch" placeholder="Search every mod: name, effect, Burn, Violent…" value="${esc(modFilter)}" autocomplete="off"></div>
      <div class="gm-tabs" role="tablist" aria-label="Mod slot">${tabs}</div>
      <p class="hint gm-help">Same layout as the game's Mods screen. Tap a tile, then tap the level the game shows. Locked tiles are ones you don't have. ${q ? `<b>${shown.length} mods match “${esc(modFilter)}” across all slots.</b>` : ""}</p>
      ${legend}${q ? "" : famChips}
      <div class="gm-list">${body || `<p class="empty-msg">${mine ? "You haven't added any mods for this slot yet. Switch to All mods and tap a tile." : "No mods match."}</p>`}</div>`;
  }
  function modLevel(m, level) {
    const p = prof();
    const manual = (p.mods || []).find((x) => x.name.toLowerCase() === m.name.toLowerCase() && (x.variant || "General").toLowerCase() === m.variant.toLowerCase());
    if (manual) manual.level = level;
    p.mod_edits = p.mod_edits || {};
    const prev = p.mod_edits[modKey(m)] || {};
    // Shiny only exists at level 17, so it survives a level change only if the mod stays at 17.
    p.mod_edits[modKey(m)] = level === 17 && prev.shiny ? { level, shiny: true, shiny_main: prev.shiny_main || null, shiny_extra: prev.shiny_extra || null } : { level };
    if (level !== 17) m.shiny = false;
    m.level = level;
  }
  function modShiny(m, patch) {
    const p = prof(); p.mod_edits = p.mod_edits || {};
    const e = { level: m.level, ...(p.mod_edits[modKey(m)] || {}), ...patch };
    if (!e.shiny) { delete e.shiny; delete e.shiny_main; delete e.shiny_extra; }
    p.mod_edits[modKey(m)] = e; Object.assign(m, { shiny: !!e.shiny, shiny_main: e.shiny_main || null, shiny_extra: e.shiny_extra || null });
  }
  function removeMod(m) {
    const p = prof();
    p.mods = (p.mods || []).filter((x) => !(x.name.toLowerCase() === m.name.toLowerCase() && (x.variant || "General").toLowerCase() === m.variant.toLowerCase()));
    p.mod_edits = p.mod_edits || {}; p.mod_edits[modKey(m)] = { removed: true };
    state.inventory.mods = state.inventory.mods.filter((x) => modKey(x) !== modKey(m));
  }
  function addMod(name, variant) {
    const p = prof();
    const cat = state.catalog.mods.find((x) => x.name === name);
    const m = { name, variant, level: 10 };
    if (p.mod_edits) delete p.mod_edits[modKey(m)];
    if (!state.inventory.mods.some((x) => modKey(x) === modKey(m))) {
      p.mods = [...(p.mods || []), m];
      state.inventory.mods.push({ ...m, slot: cat?.slot || "" });
    }
  }

  // deviation
  let devFilter = "all";
  function devVerdict(name, sk, ac) {
    const g = state.catalog.dev_guide?.guide?.[name] || { tier: "situational", rating: "both" };
    const s = Math.max(1, Math.min(5, +sk || 1)), a = Math.max(1, Math.min(5, +ac || 1)), r = g.rating;
    if (g.tier === "pvp") return { keep: "toss", text: "PvP only. Toss it on PvE servers." };
    if (r === "none") return { keep: "keep", text: "Ratings barely matter for this one. Keep one, toss duplicates." };
    if (r === "skill" || r === "activity") {
      const key = r === "skill" ? s : a, other = r === "skill" ? a : s, which = r === "skill" ? "Skill" : "Activity", an = which === "Activity" ? "an" : "a";
      if (key === 5) return { keep: "keep", text: `Keep. ${which} 5 is the top roll${other === 5 ? " — a perfect one." : `; the other number (${other}) matters less.`}` };
      if (key === 4) return { keep: "keep", text: `Keep until you find ${an} ${which} 5.` };
      if (key === 3 && (g.tier === "low" || g.tier === "situational")) return { keep: "maybe", text: `Fine for now; swap when you catch a better ${which.toLowerCase()} roll.` };
      return { keep: "toss", text: `Toss or use as fusion fodder once you have ${an} ${which} 4+. ${which} is the number that matters here.` };
    }
    if (s + a >= 9) return { keep: "keep", text: "Keep. Both numbers are high." };
    if (s + a >= 7 && Math.min(s, a) >= 3) return { keep: "keep", text: "Keep until you find a 5/4 or better." };
    if (Math.min(s, a) <= 2) return { keep: "toss", text: `Toss once you have a better one: ${s < a ? "Skill" : "Activity"} ${Math.min(s, a)} drags it down. Both numbers matter for this one.` };
    return { keep: "maybe", text: "Usable. Replace it when you catch a higher pair." };
  }
  const RATING_TXT = { skill: "Skill (1st number) matters most", activity: "Activity (2nd number) matters most", both: "Both numbers matter", none: "Ratings barely matter" };
  const KEEP_LBL = { keep: "Keep", toss: "Toss", maybe: "Your call" };
  function devOwnedHtml(ex) {
    const owned = Array.isArray(ex.dev_owned) ? ex.dev_owned : [];
    const D = state.catalog.dev_guide || { guide: {} };
    const names = [...new Set([...Object.keys(D.guide), ...state.catalog.all_deviations])].sort();
    // duplicates: only the best copy of each deviation is worth a slot
    const best = {};
    owned.forEach((o, i) => {
      const g = D.guide[o.n] || { rating: "both" };
      const sc = g.rating === "skill" ? o.s * 10 + o.a : g.rating === "activity" ? o.a * 10 + o.s : (o.s + o.a) * 10 + Math.min(o.s, o.a);
      if (!best[o.n] || sc > best[o.n].sc) best[o.n] = { i, sc };
    });
    const rows = owned.map((o, i) => {
      let v = devVerdict(o.n, o.s, o.a);
      const dup = owned.filter((x) => x.n === o.n).length > 1;
      if (dup && best[o.n].i !== i) v = { keep: "toss", text: `You have a better ${o.n} (${owned[best[o.n].i].s}/${owned[best[o.n].i].a}). Toss or fuse this one.` };
      const g = D.guide[o.n];
      return `<li class="dev-own"><span class="dev-own-n">${pic(o.n)}<b>${esc(o.n)}</b> <span class="mono">${o.s}/${o.a}</span></span>
        <span class="chip keep-${v.keep}">${KEEP_LBL[v.keep]}</span><span class="hint">${esc(v.text)}${g ? ` <i class="faint">${esc(RATING_TXT[g.rating])}.</i>` : ""}</span>
        <button class="btn small" type="button" data-devown-del="${i}" aria-label="Remove ${esc(o.n)}">Remove</button></li>`;
    }).join("");
    const opts = names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
    const num = (id, lbl) => `<label>${lbl}<select id="${id}">${[5, 4, 3, 2, 1].map((x) => `<option>${x}</option>`).join("")}</select></label>`;
    return `<section class="card dev-keep"><div class="card-head"><p class="eyebrow">Keep or toss?</p><h2>Your deviations</h2></div>
      <p class="hint">Every deviation shows two numbers, written like <b>4/4</b>: <b>Skill</b> first (how well it does its job: damage, buff size, ore quality) and <b>Activity</b> second (how long it works before it rests and how fast it recovers). Combat deviations live on Skill. Farm and crop workers live on Activity: a 2/5 Growshroom out-farms a 5/2 because it stays awake. Miners like the Digby Boy want both. <a href="${esc(D.sources?.rating || "")}" target="_blank" rel="noopener">Wiki</a></p>
      <div class="path-goal-row"><label>Deviation<select id="devOwnName">${opts}</select></label>${num("devOwnS", "Skill")}${num("devOwnA", "Activity")}
        <button class="btn small primary" type="button" data-devown-add>Add</button></div>
      ${rows ? `<ul class="dev-own-list">${rows}</ul>` : `<p class="hint">Add the deviations you have (with their two numbers) and the app says which to keep, which to toss, and which duplicate wins.</p>`}
    </section>`;
  }
  function paneDeviation() {
    const ex = prof().extras || {};
    const counted = state.catalog.extras.deviations;
    const D = state.catalog.dev_guide || { guide: {}, tiers: {}, tags: {} };
    const all = [...new Set([...Object.keys(counted), ...state.catalog.all_deviations])];
    const tierOrder = { must: 0, strong: 1, situational: 2, low: 3, pvp: 4 };
    const tagOf = (n) => D.guide[n]?.tag || (counted[n] ? "combat" : "other");
    all.sort((a, b) => (tierOrder[D.guide[a]?.tier] ?? 5) - (tierOrder[D.guide[b]?.tier] ?? 5) || (!!counted[b] - !!counted[a]) || a.localeCompare(b));
    const filters = ["all", "combat", "resources", "base", "comfort", "defense", "crafting"];
    const fbar = `<div class="chip-row dev-filter" role="group" aria-label="Filter deviations">${filters.map((f) => {
      const n = f === "all" ? all.length : all.filter((x) => tagOf(x) === f).length;
      return `<button type="button" class="chip ${devFilter === f ? "on" : ""}" data-devfilter="${f}" aria-pressed="${devFilter === f}">${esc(f === "all" ? "All" : D.tags[f] || f)} · ${n}</button>`;
    }).join("")}</div>`;
    const shown = all.filter((n) => devFilter === "all" || tagOf(n) === devFilter);
    const tiles = shown.map((n) => {
      const c = counted[n], g = D.guide[n];
      const on = ex.deviation === n;
      const combat = tagOf(n) === "combat";
      const tier = g ? `<span class="badge tier-${g.tier}">${esc(D.tiers[g.tier])}</span>` : "";
      const body = `${pic(n)}<div class="tname">${esc(n)}${newTag("deviation", n)}</div>
        <div class="dev-tags"><span class="chip">${esc(D.tags[g?.tag] || (combat ? "Combat" : "Other"))}</span>${tier}</div>
        <div class="tsub">${esc(g?.job || (c ? c.text : ""))}</div>
        ${g?.why ? `<div class="tsub dev-why">${esc(g.why)}</div>` : ""}
        ${combat ? `<div class="tsub dev-dmg">${c ? (c.unmodeled ? "Damage effect not counted yet" : `Counted: ${esc(c.text)}`) : "No damage bonus counted"}</div>` : ""}
        ${g ? `<div class="tsub faint">${esc(RATING_TXT[g.rating])}</div>` : ""}`;
      return combat
        ? `<button type="button" class="tile sel dev-tile ${on ? "on" : ""}" data-dev="${esc(n)}" aria-pressed="${on}">${body}</button>`
        : `<div class="tile dev-tile info">${body}</div>`;
    }).join("");
    return `${devOwnedHtml(ex)}
      <div class="dev-level"><span>Skill rating of your combat deviation (first number)</span>${starPicker(+ex.deviation_level || 5, "data-dev-lv", 5)}
      <span class="hint">${ex.deviation ? `Using ${esc(ex.deviation)}` : "No deviation picked"} · tap a combat deviation to use it in your build</span></div>
      ${fbar}
      <div class="tile-grid">${tiles}</div>
      <p class="hint">Jobs come from the <a href="${esc(D.sources?.list || "")}" target="_blank" rel="noopener">Fandom deviation list</a> and oncehuman.th.gl. "Must have / Strong / Situational / Can toss" are the app's calls, not official.</p>`;
  }

  // food & drink (class-aware: Chef holds 2 food + 2 drink effects)
  const CLASS_ORDER = ["freelancer", "chef", "beastmaster", "gardener"];
  function consList(ex) {
    const all = state.catalog.extras.consumables;
    const raw = Array.isArray(ex.consumables) ? ex.consumables : [ex.food, ex.drink];
    return raw.filter((n, i, a) => n && all[n] && a.indexOf(n) === i);
  }
  function caps(cls) { const c = state.catalog.extras.classes[cls || "freelancer"] || state.catalog.extras.classes.freelancer; return { food: c.food, drink: c.drink }; }
  function fitCons(names, cls) {
    const left = caps(cls), kept = [];
    for (const n of names) {
      const sl = state.catalog.extras.consumables[n].slots;
      if (sl.every((x) => left[x] > 0)) { sl.forEach((x) => left[x]--); kept.push(n); }
    }
    return kept;
  }
  // eating something new pushes out the oldest effect in a full slot, like the game does
  function addCons(list, n, cls) {
    let cur = [...list, n];
    while (fitCons(cur, cls).length < cur.length) {
      const sl = state.catalog.extras.consumables[n].slots;
      const i = cur.findIndex((x) => x !== n && state.catalog.extras.consumables[x].slots.some((y) => sl.includes(y)));
      if (i < 0) break;
      cur.splice(i, 1);
    }
    return fitCons(cur, cls);
  }
  function classPicker() {
    const C = state.catalog.extras, cls = (prof().extras || {}).class || "freelancer";
    return CLASS_ORDER.map((k) => {
      const c = C.classes[k], on = k === cls;
      return `<button type="button" class="tile sel cls ${on ? "on" : ""}" data-cls="${k}" aria-pressed="${on}">
        <div class="tname">${esc(c.label)}</div><div class="tsub">${esc(c.text)}</div></button>`;
    }).join("");
  }
  function paneFood() {
    const ex = prof().extras || {};
    const cls = ex.class || "freelancer";
    const C = state.catalog.extras;
    const auto = ex.auto_food !== false;
    const bc = state.result?.best?.config || {};
    const list = auto ? (bc.consumables || []).map((f) => f.name) : fitCons(consList(ex), cls);
    const cp = caps(cls);
    const used = { food: 0, drink: 0 };
    list.forEach((n) => C.consumables[n].slots.forEach((x) => used[x]++));
    const classTiles = classPicker();
    const tiles = Object.entries(C.consumables).map(([n, f]) => {
      const on = list.includes(n);
      return `<button type="button" class="tile sel ${on ? "on" : ""}" data-cons="${esc(n)}" aria-pressed="${on}">
        ${pic(n)}<div class="tname">${esc(n)}${newTag("food", n)}</div><div class="tsub">${esc(f.text)}</div>
        <span class="badge slot-${f.slots.join("-")}">${esc(f.slot_label)}</span>${f.typed ? ` <span class="badge typed">typed in by you</span>` : ""}</button>`;
    }).join("");
    return `<div class="section-t">Your class</div><div class="tile-grid cls-grid">${classTiles}</div>
      <div class="slot-meter"><span>Food slots <b>${used.food} / ${cp.food}</b></span><span>Drink slots <b>${used.drink} / ${cp.drink}</b></span></div>
      <label class="check"><input type="checkbox" data-auto-food ${auto ? "checked" : ""}> Pick the best food and drink for me (recommended)</label>
      <p class="hint">${auto ? `Highlighted: the best set for ${esc(state.result?.best?.weapon?.name || "your best weapon")} with your class's slots. Each build gets its own best food. Tap a dish to choose yourself instead.` : "Counting only what you picked below."}</p>
      <div class="section-t">Food & drink</div><div class="tile-grid">${tiles}</div>
      <p class="hint">Tap to eat or drink, tap again to remove. A "Food + Drink" dish uses one food and one drink slot.
      When slots are full, the oldest effect in that slot is replaced, like in the game. Only items that raise damage are listed.</p>`;
  }

  // mask hide: the only hide slot that adds damage
  function hidePanel() {
    const C = state.catalog.extras, ex = prof().extras || {};
    if (!C.mask_hides) return "";
    const cur = ex.mask_hide || "", conds = new Set(ex.hide_cond || []);
    const h = C.mask_hides[cur];
    const tip = (state.result?.upgrades || []).find((u) => u.kind === "hide");
    const groups = { dmg: [], cond: [], none: [] };
    Object.entries(C.mask_hides).forEach(([n, v]) => groups[v.unmodeled ? "none" : v.cond ? "cond" : "dmg"].push(n));
    const opt = (n) => `<option value="${esc(n)}" ${n === cur ? "selected" : ""}>${esc(n)} — ${esc(C.mask_hides[n].text)}</option>`;
    return `<div class="card hide-card"><p class="eyebrow">Hides</p>
      <div class="split"><div>
        <label>Hide used on your mask<select data-mask-hide><option value="">— not set (counts nothing) —</option>
          <optgroup label="Always on in a fight">${groups.dmg.map(opt).join("")}</optgroup>
          <optgroup label="Needs a condition">${groups.cond.map(opt).join("")}</optgroup>
          <optgroup label="No boss-damage effect">${groups.none.map(opt).join("")}</optgroup></select></label>
        ${h ? `<p class="hint hide-cur">${pic(cur, "sm")}<span>${esc(h.text)}${h.unmodeled ? ' <span class="warn">(not counted for sustained boss damage)</span>' : ""}</span></p>` : ""}
        ${tip ? `<p class="hint good">Best for this build: <b>${esc(tip.title.replace("Craft your mask with ", ""))}</b> · ${tip.gain_pct >= 0 ? "+" : ""}${tip.gain_pct}% est. DPS</p>` : (cur ? `<p class="hint good">Your mask hide is already the best one for this build and these conditions.</p>` : "")}
        ${(() => { const tn = tip ? tip.title.replace("Craft your mask with ", "") : cur; const o = tn && C.mask_hides[tn]?.origin;
          return o ? `<p class="hint breed">${pic(tn, "sm")}<span><b>Where to get ${esc(tn)}:</b> ${esc(o.animal)}${o.trait ? ` with the <b>${esc(o.trait)}</b> trait` : ""}. ${esc(o.note)}
            <a href="${esc(C.hide_traits_source || "")}" target="_blank" rel="noopener">Trait list</a></span></p>` : ""; })()}
        <p class="hint">Only the mask hide adds damage. Hides on other pieces give resistances, stamina or gathering bonuses.
          Hide rarity (+15/30/40% Psi and HP) is already inside your Psi number, so keep typing Psi from the character sheet. Every gold hide gives the same Psi boost, so choose your mask hide by its effect, not its colour.
          <a href="${esc(C.hide_source)}" target="_blank" rel="noopener">Hide list</a></p>
      </div><div>
        <p class="hint" style="margin-top:0">Turn on what's true in your usual fights:</p>
        ${Object.entries(C.hide_conds).map(([k, v]) => `<label class="check"><input type="checkbox" data-hide-cond="${esc(k)}" ${conds.has(k) ? "checked" : ""}> ${esc(v)}</label>`).join("")}
      </div></div></div>`;
  }

  // map + Cradle overrides
  function mapPicker() {
    const C = state.catalog.cradle; if (!C) return "";
    const ex = prof().extras || {}, cur = ex.map || "", m = C.maps[cur];
    const sel = `<label>Your map (scenario)<select data-map><option value="">— not set (Cradle not counted) —</option>
      ${Object.entries(C.maps).map(([k, v]) => `<option value="${esc(k)}" ${k === cur ? "selected" : ""}>${esc(v.label)}${v.cradle ? " · has a Cradle" : " · no Cradle"}</option>`).join("")}</select></label>`;
    let body = "";
    if (m && !m.cradle) {
      body = `<p class="hint">${esc(m.note)}${m.source ? ` <a href="${esc(m.source)}" target="_blank" rel="noopener">Official notes</a>` : ""}</p>`;
    } else if (m) {
      const cat = C.catalogs[m.catalog], best = state.result?.best?.config || {};
      const manual = Array.isArray(ex.cradle), skip = best.cradle_skipped || {};
      const picks = manual ? ex.cradle : (best.cradle || []).map((n) => ({ name: n }));
      const byRow = {}; picks.forEach((p) => { const o = cat.overrides.find((x) => x.name === (p.name || p)); if (o) byRow[o.row] = { ...o, value: p.value }; });
      const rows = [...new Set(cat.overrides.map((o) => o.row))];
      body = `<p class="hint">${esc(m.note)} <a href="${esc(cat.source)}" target="_blank" rel="noopener">Override list</a></p>
        <p class="hint">${manual ? "Counting the overrides you picked." : !picks.length ? "Add a weapon in My gear and the app will suggest the best override in each row for it. Or pick yours below." : `Suggested for ${esc(state.result?.best?.weapon?.name || "your best weapon")}: the app picks the best override in each row for each weapon. Change a row to count what you really run.`}
          ${manual ? ` <button class="btn small" type="button" data-cradle-auto>Use suggestions again</button>` : ""}</p>
        <div class="cradle-rows">${rows.map((r) => { const on = byRow[r];
          return `<div class="row3"><label>Row ${r}<select data-cradle-row="${r}"><option value="">— empty —</option>
            ${cat.overrides.filter((o) => o.row === r).map((o) => `<option value="${esc(o.name)}" ${on && on.name === o.name ? "selected" : ""}>${esc(o.name)}${o.counted ? "" : " (not counted: " + esc(o.why_not) + ")"}</option>`).join("")}</select></label>
            <label>Main % from your tooltip<input type="number" step="0.5" min="0" max="200" data-cradle-val="${r}" ${manual && on ? "" : "disabled"} value="${esc(on?.value ?? "")}" placeholder="${on && on.main_value != null ? "list value " + on.main_value + (on.per_stack ? " per stack" : "") : "pick an override"}"></label>
            <p class="hint" style="margin:0">${on ? (skip[on.name] ? `<span class="warn">Not counted: ${esc(skip[on.name])}.</span> ` : "") + esc(on.text) + (on.approx ? ` <span class="warn">(estimate: ${esc(on.approx)})</span>` : "") : ""}</p></div>`; }).join("")}</div>
        <p class="hint">${C.assumptions.map(esc).join(" ")}</p>`;
    }
    return `<div class="section-t" style="margin-top:20px">Your map and Cradle</div><div class="card cradle-card">${sel}${body}</div>`;
  }
  function cradleEdit(row, name, value) {
    const p = prof(), ex = p.extras || {}, C = state.catalog.cradle, m = C.maps[ex.map]; if (!m || !m.cradle) return;
    const cat = C.catalogs[m.catalog];
    let list = Array.isArray(ex.cradle) ? ex.cradle.map((x) => (typeof x === "string" ? { name: x } : { ...x }))
      : (state.result?.best?.config?.cradle || []).map((n) => ({ name: n }));
    const rowOf = (n) => cat.overrides.find((o) => o.name === n)?.row;
    const keep = list.filter((x) => rowOf(x.name) !== +row);
    const old = list.find((x) => rowOf(x.name) === +row);
    if (name === undefined) name = old?.name;
    if (name) keep.push({ name, value: value === undefined ? (old && old.name === name ? old.value ?? null : null) : value });
    p.extras = { ...ex, cradle: keep.sort((a, b) => rowOf(a.name) - rowOf(b.name)) };
  }

  // basics
  function paneBasics() {
    const p = prof(), ex = p.extras || {};
    return `<div class="section-t">Your class</div><div class="tile-grid cls-grid">${classPicker()}</div>
    <div class="row3">
      <label>Starchrom balance<input type="number" min="0" step="100" data-basic="starchrom" value="${esc(p.starchrom ?? "")}" placeholder="e.g. 24000"></label>
      <label>Psi Intensity (character sheet — already includes hide rarity, stars and tier)<input type="number" min="0" step="1" data-basic="psi_intensity" value="${esc(p.psi_intensity ?? "")}" placeholder="leave blank to estimate"></label>
      <label>Fight type<select data-basic="scenario">${Object.entries(state.catalog.scenarios).map(([k, v]) => `<option value="${esc(k)}" ${p.scenario === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
    </div>
    ${mapPicker()}
    <label class="check"><input type="checkbox" data-basic="marked" ${ex.marked ? "checked" : ""}> Bull's Eye kept on target (secondary weapon or teammate)</label>
    <div class="row3" style="margin-top:12px"><label>Sniper shots that hit a weakspot (%)<input type="number" min="0" max="100" step="5" data-basic="sniper_ws" value="${esc(ex.sniper_ws ?? "")}" placeholder="blank = 2× the fight's rate (boss: 70%)"></label></div>
    <p class="hint">Sniper rifles aim each shot, so they get their own weakspot rate. Other guns use the fight's rate (boss: 35%). This matters most for SN700 - Finale, where weakspot hits always trigger Shrapnel and build Reverb.</p>
    <div class="section-t" style="margin-top:24px">Your play style</div>
    <div class="tile-grid eff-pick">${Object.entries(state.catalog.efforts || {}).map(([k, v]) => `<button type="button" class="tile sel ${(ex.effort || "normal") === k ? "on" : ""}" data-effort="${k}" aria-pressed="${(ex.effort || "normal") === k}">
      <div class="tname">${esc(v.label)}</div><div class="tsub">${esc(v.desc)}</div></button>`).join("")}</div>
    <p class="hint">The best build and upgrade list are worked out for this play style. The Best build page compares all three.</p>
    <div class="section-t" style="margin-top:28px">Your data</div>
    <p class="hint">Everything you enter is saved on this computer only. Download a backup file before big changes.</p>
    <p style="margin-top:10px"><button class="btn" type="button" data-backup>Download backup</button></p>
    <div class="section-t" style="margin-top:28px">Start fresh (new player test)</div>
    <div class="card fresh-card">
      <p class="hint">Clears what you own so you can see what the app tells a brand new player, and test adding gear by hand. Nothing is deleted:
        your real profile is put aside and recorded game data is only ignored. One click puts everything back.</p>
      ${state.result?.fresh ? `<p class="hint good">You are in a fresh-start test now.</p>` : ""}
      <div class="path-goal-row"><label>Starchrom to start with<input type="number" min="0" step="100" id="freshSc" value="5000"></label>
        <button class="btn small" type="button" data-fresh>${state.result?.fresh ? "Clear again" : "Clear and start fresh"}</button>
        <button class="btn small primary" type="button" data-profiles>Profiles (3 slots)</button></div>
      <p class="hint">The profile you're using stays in its slot. The fresh start isn't in a slot until you save it in one.</p>
    </div>`;
  }

  const calOpen = new Set();
  document.addEventListener("toggle", (e) => {
    const d = e.target; if (!(d instanceof HTMLDetailsElement) || !d.classList.contains("cal")) return;
    const n = d.closest("[data-wname]")?.dataset.wname; if (!n) return;
    const key = d.dataset.magkey || n;
    d.open ? calOpen.add(key) : calOpen.delete(key);
  }, true);

  // ---------------------------------------------------------- Mod crates
  const SLOT_NAME = { weapon: "Weapon", mask: "Mask", helmet: "Helmet", top: "Top", gloves: "Gloves", bottoms: "Bottoms", shoes: "Shoes" };
  const SLOT_WORDS = { weapon: /\bweapon|gun\b/, mask: /\bmask\b/, helmet: /\bhelmet|\bhat\b|\bhead\b/, top: /\btop\b|\bchest|\bjacket|upper body/,
    gloves: /\bgloves?\b|\bhands?\b/, bottoms: /\bbottoms?|\bpants\b|\blegs?\b|lower body/, shoes: /\bshoes?\b|\bboots?\b|\bfeet\b/ };
  let crq = "", crId = null, crSlot = "", crLevel = 13, crAim = "", crRes = null, crBusy = false, crDust = "", crBought = 0, dustRes = null, pityRes = null;
  function matchCrates(text) {
    const t = text.toLowerCase(); if (!t.trim()) return [];
    const toks = t.split(/[^a-z0-9-]+/).filter((w) => w.length > 1 && !["i", "my", "a", "the", "it", "is", "have", "got", "with", "from", "and", "of", "by", "or", "that", "mod", "mods", "crate", "crates"].includes(w));
    const rng = t.match(/(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})/), fixed = t.match(/(?:lv\.?|level)\s*(\d{1,2})/);
    return state.catalog.crates.crates.map((c) => {
      const hay = `${c.name} ${c.words} ${c.text}`.toLowerCase();
      let sc = toks.reduce((a, w) => a + (hay.includes(w) ? (w.length > 4 ? 2 : 1) : 0), 0);
      if (rng && +rng[1] === c.lo && +rng[2] === c.hi) sc += 5;
      if (fixed && !rng && +fixed[1] === c.lo && c.lo === c.hi) sc += 4;
      if (/non[- ]?keyword|no suffix|non suffix/.test(t)) sc += c.id === "nonkw_sel" || c.id.startsWith("group") ? 3 : 0;
      if (/select|choose|pick/.test(t)) sc += c.mode === "select" ? 2 : 0;
      if (/random/.test(t)) sc += c.mode === "random" ? 2 : 0;
      return { c, sc };
    }).filter((x) => x.sc > 1).sort((a, b) => b.sc - a.sc).slice(0, 3).map((x) => x.c);
  }
  function crateFromText() {
    const t = crq.toLowerCase();
    const slot = Object.keys(SLOT_WORDS).find((k) => SLOT_WORDS[k].test(t)); if (slot) crSlot = slot;
    const fixed = t.match(/(?:lv\.?|level)\s*(\d{1,2})/); if (fixed) crLevel = Math.min(17, +fixed[1]);
    const dust = t.match(/(\d[\d,.]*)\s*k?\s*(?:mod\s*)?dust/); if (dust) { let n = +dust[1].replace(/[,.]/g, ""); if (/\d\s*k/.test(dust[0])) n *= 1000; crDust = String(n); }
  }
  async function runCrate() {
    if (!crId) return;
    crBusy = true; crRes = null; renderPage();
    try {
      const q = new URLSearchParams({ id: crId, slot: crSlot || "", level: String(crLevel), aim: crAim || "" });
      const r = await fetch(`/api/forge/crate?${q}`, { cache: "no-store" });
      crRes = await r.json();
    } catch (e) { crRes = { error: e.message }; }
    crBusy = false; renderPage();
    $("#crResult")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  async function runDust() {
    dustRes = { busy: true }; renderPage();
    try { dustRes = await (await fetch(`/api/forge/dust?dust=${+crDust || 0}&bought=${crBought}`, { cache: "no-store" })).json(); } catch (e) { dustRes = { error: e.message }; }
    renderPage();
  }
  async function runPity() {
    pityRes = { busy: true }; renderPage();
    try { pityRes = await (await fetch(`/api/forge/crate?id=sel_17`, { cache: "no-store" })).json(); } catch (e) { pityRes = { error: e.message }; }
    renderPage();
  }
  const pct = (v) => `${v > 0 ? "+" : ""}${(+v).toFixed(1)}%`;
  function menuSteps(r, big) {
    if (!r.menu) return "";
    return `<span class="cr-menu ${big ? "big" : ""}"><span class="cr-menu-t">In game:</span>${r.menu.steps.map((x, i) => `<span class="cr-step"><i>${i + 1}</i>${esc(x)}</span>`).join(`<span class="cr-arr">›</span>`)}${r.menu.sure ? "" : `<small class="faint">(second list's wording not confirmed yet)</small>`}</span>`;
  }
  function pickRow(r, i, lv) {
    const have = r.have ? `you have Lv ${r.have}` : "you don't own it";
    return `<li class="cr-row ${i === 0 ? "top" : ""}"><span class="lrank">#${i + 1}</span>${pic(r.name, "sm")}
      <span class="lname"><b>${esc(r.name)} · ${esc(r.variant)}${r.in_target ? ` <span class="cr-tgt">in build #${esc(crRes?.aim?.rank)}</span>` : ""}</b><small>${esc(SLOT_NAME[r.slot] || r.slot)} · ${esc(have)}${lv[0] !== lv[1] ? ` · improves your build in ${Math.round(r.hit_pct)}% of rolls` : ""}</small>${menuSteps(r)}</span>
      <span class="ldps">${pct(r.exp_pct)}<small>${lv[0] !== lv[1] ? `up to ${pct(r.top_pct)}` : "at Lv " + lv[0]}</small></span></li>`;
  }
  // which build the crate advice is measured on: yours now, or one of the Top 10 in the game
  function aimSelect() {
    const top = state.result?.ladder?.top || [];
    return `<label>Open it for<select id="crAim"><option value="">your best build now</option>
      ${top.map((b, i) => `<option value="rank:${i + 1}" ${crAim === `rank:${i + 1}` ? "selected" : ""}>#${i + 1} in the game · ${esc(b.weapon)}</option>`).join("")}</select></label>`;
  }
  function aimPanel(A) {
    if (!A) return "";
    return `<div class="cr-aim"><b>Working toward #${A.rank} · ${esc(A.weapon)}</b> <span class="muted">(${num(A.dps)} DPS at max)</span>
      <span class="lmods">${A.lineup.map((m) => `<span class="lmod ${m.have ? "have" : ""}" title="${esc(`${SLOT_NAME[m.slot] || m.slot}: ${m.name} (${m.variant})`)}"><em>${esc(SLOT_NAME[m.slot] || m.slot)}</em> ${esc(m.name)}${m.have ? ` <i>✓ ${m.have}</i>` : ` <i class="miss">missing</i>`}</span>`).join("")}</span></div>`;
  }
  function crateResult() {
    if (crBusy) return `<div class="card" id="crResult"><div class="skeleton"></div><p class="empty-msg">Testing every possible mod from this crate on your build…</p></div>`;
    if (!crRes) return "";
    if (crRes.error) return `<div class="card" id="crResult"><p class="empty-msg">${esc(crRes.error)}</p></div>`;
    const R = crRes, lv = R.levels, c = R.crate;
    let head = "", body = "";
    if (c.mode === "select") {
      const p = R.picks || [];
      head = p.length ? `Pick <b>${esc(p[0].name)} (${esc(p[0].variant)})</b> for ${esc(SLOT_NAME[p[0].slot])}. `
        + (p[0].exp_pct > 0.001 ? `Expected ${pct(p[0].exp_pct)} DPS on ${esc(R.lenses[0])}.` : `It's a piece of ${esc(R.lenses[0])} you don't have yet.`)
        : R.aim ? `Nothing in this crate moves you toward build #${R.aim.rank}.` : "No pick in this crate raises your build.";
      if (p[0]?.menu) head += menuSteps(p[0], true);
      body = p.length ? `<ol class="lad cr-list">${p.map((r, i) => pickRow(r, i, lv)).join("")}</ol>` : "";
      if (R.future?.length) body += `<div class="section-t">If you switch to ${esc(R.lenses[1])}</div><ol class="lad cr-list">${R.future.map((r, i) => pickRow(r, i, lv)).join("")}</ol>
        <p class="hint">Only worth choosing over #1 if you're about to make that switch.</p>`;
    } else {
      const o = R.options || [];
      const word = c.choose === "slot" ? "slot" : c.choose === "group" ? "category" : c.choose === "family" ? "suffix" : "";
      head = o.length && o[0].exp_pct > 0.05 ? (word ? `Choose <b>${esc(o[0].label)}</b>. ` : "") + `Expected ${pct(o[0].exp_pct)} per crate; ${Math.round(o[0].hit_pct)}% of rolls improve your build.` : "This crate is unlikely to improve your build.";
      body = `<ol class="lad cr-list">${o.map((x, i) => `<li class="cr-row ${i === 0 ? "top" : ""}"><span class="lrank">#${i + 1}</span>
        <span class="lname"><b>${esc(x.label)}</b><small>${x.pool} possible mods · ${Math.round(x.hit_pct)}% chance to help${x.best[0] ? ` · jackpot: ${esc(x.best[0].name)} (${esc(x.best[0].variant)}) ${pct(x.best[0].top_pct)}` : ""}</small></span>
        <span class="ldps">${pct(x.exp_pct)}<small>expected</small></span></li>`).join("")}</ol>`;
    }
    if (R.suggest_aim) body += `<div class="gap cr-aim-tip"><b>Want to aim higher?</b> Your current build has nothing to gain here, but a top build might.
      <span class="chips" style="margin-top:6px">${(state.result?.ladder?.top || []).slice(0, 5).map((b, i) => `<button type="button" class="chip-btn" data-cr-aim="rank:${i + 1}">Open it for #${i + 1} ${esc(b.weapon)}</button>`).join("")}</span></div>`;
    if (R.fallback) body += `<div class="gap"><b>Least-likely but still useful:</b> ${esc(R.fallback.text)}${R.fallback.mods?.length ? `<br><small>For example: ${R.fallback.mods.map((m) => `${esc(m.name)} (${esc(m.variant)}, ${esc(SLOT_NAME[m.slot])})`).join(", ")}</small>` : ""}</div>`;
    return `<div class="card cr-res" id="crResult"><p class="eyebrow">Recommendation · ${esc(c.name)} · Lv ${lv[0]}${lv[1] !== lv[0] ? `–${lv[1]}` : ""}</p>
      <h2 class="cr-head">${head}</h2>${aimPanel(R.aim)}${body}
      <details><summary>How this is worked out</summary><ul>${R.notes.map((n) => `<li>${esc(n)}</li>`).join("")}${R.notes_aim ? `<li>${esc(R.notes_aim)}</li>` : ""}<li>Base: ${num(R.base_dps)} estimated DPS.</li></ul></details>
      <p class="hint" style="margin-top:8px">Crate details: <a href="${esc(c.src)}" target="_blank" rel="noopener">source</a></p></div>`;
  }
  function pityPanel() {
    const ex = prof().extras || {}, hits = +ex.pity_hits || 0;
    const st = hits >= 140 ? "Guaranteed on your next eligible clear." : hits >= 80 ? `About 1% or more per eligible clear now, guaranteed in ${140 - hits} more.` : `Under 1% per clear until about hit 80. Guaranteed in ${140 - hits} more.`;
    let tgt = "";
    if (pityRes?.busy) tgt = `<p class="hint">Finding your best Lv 17 target…</p>`;
    else if (pityRes?.picks?.length) {
      const t = pityRes.picks[0];
      tgt = `<p>Best Lv 17 target: <b>${esc(t.name)} (${esc(t.variant)})</b>, ${esc(SLOT_NAME[t.slot])}, ${pct(t.exp_pct)}.</p>
        <p class="hint">${hits >= 80 ? `You're close. Do your next Pro/Nightmare runs on the <b>${esc(SLOT_NAME[t.slot])}</b> Silo so the crate lands on that slot.` : `Build up hits anywhere (Forsaken Giant is a common choice), then switch to the ${esc(SLOT_NAME[t.slot])} Silo past ~80.`}
        ${t.have === 17 ? ` You already have it at Lv 17: each new Lv 17 copy has a 30% Shiny chance, and the 6th is guaranteed.` : ""}</p>`;
    } else if (pityRes) tgt = `<p class="hint">No Lv 17 target found.</p>`;
    return `<div class="card"><p class="eyebrow">Lv 17 pity</p><h2>Aim your weekly Lv 17 crate</h2>
      <div class="row3" style="margin-top:12px"><label>Hits since your last Lv 17 crate<input type="number" min="0" max="200" id="pityHits" value="${hits || ""}" placeholder="0–140"></label></div>
      <p>${esc(st)}</p>${tgt}${pityRes ? "" : `<button class="btn small" type="button" data-pity>Find my best Lv 17 target</button>`}
      <p class="hint" style="margin-top:8px">Bought crates don't count. One per account per week, banks up to 5. A separate hidden counter gives one after roughly 1,000 eligible rolls.</p></div>`;
  }
  function dustPanel() {
    let out = "";
    if (dustRes?.busy) out = `<div class="skeleton"></div>`;
    else if (dustRes?.error) out = `<p class="empty-msg">${esc(dustRes.error)}</p>`;
    else if (dustRes) {
      const p = dustRes.selection_advice?.picks || [];
      out = `<ol class="steps">${dustRes.selection ? `<li>Buy <b>${dustRes.selection}× Mod Selection Crate</b> (6,000 each). Pick ${p.slice(0, Math.min(3, dustRes.selection)).map((x) => `<b>${esc(x.name)} (${esc(x.variant)})</b>`).join(", then ") || "the top mod on the list"}. Picks repeat until you roll a high level.</li>` : `<li>Not enough for a Mod Selection Crate (6,000), or this week's 10 are used.</li>`}
        ${dustRes.leftover ? `<li>With the leftover ${num(dustRes.left)} dust: up to ${dustRes.leftover.n}× ${esc(dustRes.leftover.crate)} on <b>${esc(SLOT_NAME[dustRes.leftover.slot] || dustRes.leftover.slot)}</b> (${pct(dustRes.leftover.exp_pct)} expected each). Or save it for next week's selection crates, which is usually better.</li>` : dustRes.left ? `<li>Keep the remaining ${num(dustRes.left)} dust for next week's selection crates.</li>` : ""}</ol>`;
    }
    return `<div class="card"><p class="eyebrow">Mod Dust</p><h2>Spend my Mod Dust</h2>
      <div class="row3" style="margin-top:12px"><label>Mod Dust balance<input type="number" min="0" step="1000" id="dustIn" value="${esc(crDust)}" placeholder="e.g. 42000"></label>
      <label>Selection crates bought this week<input type="number" min="0" max="10" id="dustBought" value="${crBought || ""}" placeholder="0"></label></div>
      <button class="btn small" type="button" data-dust>Make a plan</button>${out}</div>`;
  }
  function paneCrates() {
    const C = state.catalog.crates, sug = matchCrates(crq);
    const tiles = C.crates.map((c) => `<button type="button" class="tile sel crate ${c.id === crId ? "on" : ""}" data-crate="${c.id}" aria-pressed="${c.id === crId}">
      <span class="badge ${c.mode === "select" ? "" : "slot-drink"}">${c.mode === "select" ? "you pick" : "random"} · Lv ${c.lo}${c.hi !== c.lo ? `–${c.hi}` : ""}</span>
      <div class="tname">${esc(c.name)}</div><div class="tsub">${esc(c.text)}</div><div class="tsub src">${esc(c.source)}</div></button>`).join("");
    const cur = C.crates.find((c) => c.id === crId);
    const needSlot = cur && (cur.choose_slot_filter);
    const opts = cur ? `<div class="toolbar cr-opts"><b class="tname">${esc(cur.name)}</b>
      ${needSlot ? `<label>Slot<select id="crSlot"><option value="">${cur.id === "slot_pick" ? "choose…" : "any slot"}</option>${cur.slots.map((s) => `<option value="${s}" ${crSlot === s ? "selected" : ""}>${SLOT_NAME[s]}</option>`).join("")}</select></label>` : ""}
      ${cur.level_input ? `<label>Level<input type="number" id="crLevel" min="1" max="17" value="${crLevel}" style="width:80px"></label>` : ""}
      ${aimSelect()}
      ${crSlot && !cur.slots.includes(crSlot) ? `<span class="hint warn">This crate only has ${esc(cur.slots.map((s) => SLOT_NAME[s]).join(" / "))} mods, not ${esc(SLOT_NAME[crSlot])}. Check the crate name in game.</span>` : ""}
      <span class="grow"></span><button class="btn primary" type="button" data-crate-run ${crBusy ? "disabled" : ""}>${crBusy ? "Working…" : "How should I open it?"}</button></div>` : "";
    return `<div class="card cr-ask"><p class="eyebrow">Tell me what you got</p>
      <input type="search" id="crSearch" class="cr-input" value="${esc(crq)}" placeholder="e.g. “boss dropped a 9-17 non-keyword selection crate for gloves” or “I have 40k mod dust”" autocomplete="off">
      ${sug.length ? `<div class="chips" style="margin-top:10px"><span class="hint">Sounds like:</span>${sug.map((c) => `<button type="button" class="chip-btn" data-crate="${c.id}" aria-pressed="${c.id === crId}">${esc(c.name)}</button>`).join("")}</div>` : `<p class="hint" style="margin-top:8px">Or tap the crate below. Mentioning a slot (gloves, shoes…), a level range (9-17) or a Mod Dust amount fills those in too.</p>`}
      </div>
      ${opts}${crateResult()}
      <div class="section-t">All crate types</div><div class="tile-grid wide">${tiles}</div>
      <div class="grid" style="margin-top:18px">${dustPanel()}${pityPanel()}</div>
      <div class="section-t">How mod crates work now (Mod 2.0)</div>
      <div class="later-grid">${C.facts.map((f) => `<div class="later fact"><h3>${esc(f.t)}</h3><p>${esc(f.d)}</p><a href="${esc(f.src)}" target="_blank" rel="noopener">Source</a></div>`).join("")}</div>`;
  }

  // parked tools
  const LATER = [
    ["Video & screenshot import", "Read your gear from game recordings instead of typing it in.", "Works only for some screens and needs a lot of manual checking. Typing your gear here is faster for now.", "import"],
    ["Abyss guide", "Where to farm what in the Abyss.", "Mostly a list of hedged source notes, with no routes or drop rates. It will come back when the drop data is good enough.", "map"],
    ["Compare builds", "Put two builds side by side.", "The Best build page and the ranking already compare every build. A cleaner side-by-side view is planned.", "compare"],
    ["Farming & upgrade routes", "Which activity drops which upgrade.", "Drop sources are incomplete. The upgrade list on the Best build page covers what to get next.", "upgrades"],
    ["Item catalog & mechanics", "Raw game data and how each effect is sourced.", "Useful for checking the math, not for playing. The Weapons, Armor and Mods pages show the same items with pictures.", "catalog"],
    ["Saved inventory builds", "Save named loadouts.", "Saved under the old data format. Saving loadouts on the new pages is planned.", "builds"],
  ];
  function paneLater() {
    return `<div class="later-grid">${LATER.map(([t, d, why, pg]) => `<div class="later"><h3>${esc(t)}</h3><p>${esc(d)}</p><p class="why">Why it's parked: ${esc(why)}</p><a href="/classic?page=${pg}">Open the old version →</a></div>`).join("")}</div>
      <p class="hint" style="margin-top:14px">The old version still reads and saves the same data, so nothing is lost. <a href="/classic">Open the full classic tools</a>.</p>`;
  }

  // picker
  let pickCtx = null;
  function openPicker(kind, slot) {
    pickCtx = { kind, slot };
    pickLock = null; pickMine = true;
    $("#picker").classList.toggle("wide", kind === "equip");
    $("#pickTitle").textContent = kind === "weapon" ? "Add a weapon" : kind === "mod" ? "Add a mod" : kind === "equip" ? `Which mod is on your ${SLOT_NAME[slot] || slot} right now?` : `Choose ${slot}`;
    $("#pickSearch").value = "";
    renderPicker();
    $("#picker").showModal();
    $("#pickSearch").focus();
  }
  function pickItems() {
    const c = state.catalog;
    if (pickCtx.kind === "weapon") return c.weapons.map((n) => ({ id: n, name: n, sub: `${c.weapon_info[n]?.type || ""} · ${c.weapon_info[n]?.keyword || ""}` }));
    if (pickCtx.kind === "equip") {
      const have = new Map(state.inventory.mods.map((m) => [modKey(m), m]));
      return c.mods.filter((m) => m.slot === pickCtx.slot).flatMap((m) => (m.variants.length ? m.variants : ["General"]).map((v) => {
        const o = have.get(modKey({ name: m.name, variant: v }));
        return { id: `${m.name}|${v}`, name: m.name, sub: `${v}${o ? ` · you have it · Lv ${o.level}` : ""}`, own: !!o };
      })).sort((a, b) => b.own - a.own || a.name.localeCompare(b.name));
    }
    if (pickCtx.kind === "mod") return c.mods.flatMap((m) => m.variants.length ? m.variants.map((v) => ({ id: `${m.name}|${v}`, name: m.name, sub: `${v} · ${m.slot || ""}` })) : [{ id: `${m.name}|General`, name: m.name, sub: `General · ${m.slot || ""}` }]);
    const names = c.armor[pickCtx.slot] || [];
    return [{ id: "", name: "None", sub: "Nothing / not legendary" }, ...names.map((n) => ({ id: n, name: n,
      sub: c.extras.key_armor[n] ? `Key armor · ${c.extras.key_armor[n].text}` : `${c.armor_info[n]?.set || ""} set` }))];
  }
  // "Which mod is on your X right now?" — same rows, colors and order as the Mods screen
  let pickMine = true, pickLock = null;
  function renderEquipPicker(q) {
    const A = modArt(), slot = pickCtx.slot, own = new Map(state.inventory.mods.map((m) => [modKey(m), m]));
    const used = new Set([bestFor(slot)].filter(Boolean).map(modKey));
    const cur = eqOf(slot), curKey = cur ? modKey(cur) : null;
    const rows = state.catalog.mods.filter((m) => m.slot === slot).map((m) => ({ ...m, vars: m.variants.length ? m.variants : ["General"] }));
    const hasAny = rows.some((m) => m.vars.some((v) => own.has(modKey({ name: m.name, variant: v }))));
    const mine = pickMine && hasAny && !q;
    const ord = (m) => A.order[`${m.slot}|${m.name.toLowerCase()}`] ?? 999;
    const famOf = (m) => slot === "weapon" ? (A.weapon_group[m.name.toLowerCase()] || "other") : "";
    let shown = rows.filter((m) => !q || `${m.name} ${m.summary} ${m.vars.join(" ")} ${A.groups[famOf(m)]?.label || ""}`.toLowerCase().includes(q));
    if (mine) shown = shown.filter((m) => m.vars.some((v) => own.has(modKey({ name: m.name, variant: v }))));
    shown.sort((x, y) => ord(x) - ord(y) || x.name.localeCompare(y.name));
    const [lkN, lkV] = (pickLock || "").split("|");
    const rowHtml = (m) => {
      const vars = m.vars.filter((v) => !mine || own.has(modKey({ name: m.name, variant: v })))
        .sort((x, y) => (own.get(modKey({ name: m.name, variant: y }))?.level || 0) - (own.get(modKey({ name: m.name, variant: x }))?.level || 0) || variantRank(x) - variantRank(y));
      const h = m.vars.filter((v) => own.has(modKey({ name: m.name, variant: v }))).length;
      const emb = A.emblems[`${m.slot}|${m.name}`.toLowerCase()];
      const tiles = vars.map((v) => {
        const k = modKey({ name: m.name, variant: v }), id = `${m.name}|${v}`;
        let t = gmTile(m, v, own, used, curKey).replace("data-gm=", `${own.has(k) ? `data-pick="${esc(id)}"` : `data-pick-lock="${esc(id)}"`} data-gm=`);
        if (k === curKey) t = t.replace('<span class="gm-var">', '<span class="gm-inb on-it">ON IT NOW</span><span class="gm-var">');
        return t;
      }).join("");
      const lockEd = lkN === m.name && m.vars.includes(lkV) ? `<div class="gm-edit pk-lv"><div class="gm-edit-h"><b>${esc(m.name)} · ${esc(lkV)}</b><small>You haven't added this one yet. Tap the level the game shows to add it and put it on.</small></div>
          <div class="gm-lvs">${Array.from({ length: 17 }, (_, i) => i + 1).map((n) => `<button type="button" class="gm-lvb ${RARITY(n)}" data-pick-lv="${n}" aria-label="Level ${n}">${n}</button>`).join("")}</div></div>` : "";
      return `<section class="gm-row pk-row ${h ? "has" : ""}"><div class="gm-head">${emb ? `<img class="gm-emb" src="${esc(emb)}" alt="" loading="lazy">` : pic(m.name, "gm-emb")}
          <div class="gm-name"><b>${esc(m.name)}</b><small class="gm-own ${h ? "on" : ""}">${h} of ${m.vars.length} owned</small><p>${esc(m.summary)}</p></div></div>
        <div class="gm-body"><div class="gm-tiles">${tiles}</div>${lockEd}</div></section>`;
    };
    let body = "";
    if (slot === "weapon") {
      for (const g of [...Object.keys(A.groups), "other"]) {
        const list = shown.filter((m) => famOf(m) === g); if (!list.length) continue;
        const G = A.groups[g];
        body += `<div class="gm-group"><div class="gm-group-h">${G ? `<img src="${esc(G.icon)}" alt="">` : ""}<span>${esc(G?.label || "Other")}</span></div>${list.map(rowHtml).join("")}</div>`;
      }
    } else body = shown.map(rowHtml).join("");
    const tog = hasAny && !q ? `<div class="view-tabs pk-views" role="tablist"><button type="button" role="tab" class="vt ${mine ? "on" : ""}" aria-selected="${mine}" data-pick-mine="1">Mods I have</button>
      <button type="button" role="tab" class="vt ${!mine ? "on" : ""}" aria-selected="${!mine}" data-pick-mine="0">All ${esc(SLOT_NAME[slot] || slot)} mods</button></div>` : "";
    const legend = `<div class="gm-legend"><span><i class="sw legendary"></i>Gold · Lv 9–17</span><span><i class="sw epic"></i>Purple · Lv 7–8</span><span><i class="sw rare"></i>Blue · Lv 5–6</span><span><i class="sw uncommon"></i>Green · Lv 3–4</span><span><i class="sw common"></i>White · Lv 1–2</span><span><i class="sw locked">${LOCK}</i>Not added yet</span></div>`;
    $("#pickGrid").className = "pick-grid pk-gm";
    $("#pickGrid").innerHTML = `${tog}${legend}<p class="hint">Tap the tile that's on your ${esc(SLOT_NAME[slot] || slot)} in the game.${used.size ? " IN BUILD marks the best one from your collection." : ""}</p>
      <div class="gm-list">${body || `<p class="empty-msg">Nothing matches.</p>`}</div>`;
  }
  function chooseEquip(id, level) {
    const [n, v] = id.split("|");
    let o = state.inventory.mods.find((m) => modKey(m) === modKey({ name: n, variant: v }));
    if (!o) { addMod(n, v); o = state.inventory.mods.find((m) => modKey(m) === modKey({ name: n, variant: v })); if (level) modLevel(o, level); }
    setEq(pickCtx.slot, { name: n, variant: v, level: level || o?.level || 10 });
    if (pickCtx.slot === "weapon" && !prof().extras.equipped_weapon && state.inventory.weapons.length === 1) prof().extras.equipped_weapon = state.inventory.weapons[0].name;
    $("#picker").close(); renderGear(); queueSave();
  }
  function renderPicker() {
    const q = $("#pickSearch").value.toLowerCase().trim();
    if (pickCtx.kind === "equip") return renderEquipPicker(q);
    $("#pickGrid").className = "tile-grid pick-grid";
    const items = pickItems().filter((i) => !q || `${i.name} ${i.sub}`.toLowerCase().includes(q)).slice(0, 240);
    $("#pickGrid").innerHTML = items.map((i) => `<button type="button" class="tile ${i.own ? "owned" : ""}" data-pick="${esc(i.id)}">
      ${i.id || pickCtx.kind !== "armor" ? pic(i.name) : `<span class="pic ph">—</span>`}<div class="tname">${esc(i.name)}${newTag(pickCtx.kind === "mod" || pickCtx.kind === "equip" ? "mod" : pickCtx.kind === "weapon" ? "weapon" : "armor", i.name)}</div><div class="tsub">${esc(i.sub)}</div></button>`).join("")
      || `<p class="empty-msg">Nothing matches.</p>`;
  }
  function choose(id) {
    const p = prof();
    if (pickCtx.kind === "weapon") addWeapon(id);
    else if (pickCtx.kind === "mod") { const [n, v] = id.split("|"); addMod(n, v); }
    else if (pickCtx.kind === "equip") {
      const [n, v] = id.split("|");
      const o = state.inventory.mods.find((m) => modKey(m) === modKey({ name: n, variant: v }));
      if (!o) addMod(n, v);
      setEq(pickCtx.slot, { name: n, variant: v, level: o?.level || 10 });
      if (pickCtx.slot === "weapon" && !prof().extras.equipped_weapon && state.inventory.weapons.length === 1) prof().extras.equipped_weapon = state.inventory.weapons[0].name;
    }
    else {
      p.armor = p.armor || {};
      if (!id) delete p.armor[pickCtx.slot];
      else p.armor[pickCtx.slot] = { name: id, stars: p.armor[pickCtx.slot]?.stars || 1, tier: 5 };
    }
    $("#picker").close(); renderGear(); queueSave();
  }

  async function exportBackup(btn) {
    btn.disabled = true;
    try {
      const d = await (await fetch("/api/backup")).json();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify(d)], { type: "application/json" }));
      a.download = `deviant-forge-backup-${new Date().toISOString().slice(0, 10)}.json`; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    } catch (e) { alert(`Backup failed: ${e.message}`); } finally { btn.disabled = false; }
  }

  // gear events
  document.addEventListener("input", (e) => {
    const t = e.target;
    if (t.id === "modSearch") { modFilter = t.value; renderGear(); }
    else if (t.id === "wSearch") { wq = t.value; renderPage(); }
    else if (t.id === "aSearch") { aq = t.value; renderPage(); }
    else if (t.id === "crSearch") { crq = t.value; crateFromText(); const m = matchCrates(crq); if (m[0] && m[0].id !== crId) { crId = m[0].id; crRes = null; } renderPage(); }
    else if (t.id === "pickSearch") renderPicker();
  });
  document.addEventListener("change", (e) => {
    const t = e.target, p = state && prof();
    if (!p) return;
    if (t.dataset.eqLv) {
      const m = eqOf(t.dataset.eqLv);
      if (m) { setEq(t.dataset.eqLv, { ...m, level: Math.max(1, Math.min(17, Math.round(+t.value) || m.level || 10)) }); renderGear(); queueSave(); }
      return;
    }
    const gse = t.closest && t.closest("[data-gm-edit]");
    if (gse && (t.hasAttribute("data-gm-shiny") || t.hasAttribute("data-gm-shiny-main") || t.hasAttribute("data-gm-shiny-extra"))) {
      const [n, v] = gse.dataset.gmEdit.split("|");
      const m = state.inventory.mods.find((x) => modKey(x) === modKey({ name: n, variant: v }));
      if (!m) return;
      if (t.hasAttribute("data-gm-shiny")) { modShiny(m, { shiny: t.checked }); renderGear(); }
      else modShiny(m, t.hasAttribute("data-gm-shiny-main") ? { shiny_main: t.value.trim() || null } : { shiny_extra: t.value.trim() || null });
      queueSave(); return;
    }
    if (t.dataset.mcLv) {
      const m = state.inventory.mods.find((x) => modKey(x) === t.dataset.mcLv);
      if (m) { modLevel(m, Math.max(1, Math.min(17, Math.round(+t.value) || m.level))); renderGear(); queueSave(); }
      return;
    }
    if (t.id === "wType") { wType = t.value; renderPage(); return; }
    if (t.id === "crSlot") { crSlot = t.value; crRes = null; renderPage(); return; }
    if (t.id === "crAim") { crAim = t.value; crRes = null; renderPage(); return; }
    if (t.id === "crLevel") { crLevel = Math.max(1, Math.min(17, +t.value || 13)); crRes = null; renderPage(); return; }
    if (t.id === "dustIn") { crDust = t.value; return; }
    if (t.id === "dustBought") { crBought = Math.max(0, Math.min(10, +t.value || 0)); return; }
    if (t.id === "pityHits") { p.extras = { ...(p.extras || {}), pity_hits: Math.max(0, Math.round(+t.value || 0)) }; renderPage(); queueSave(); return; }
    if (t.id === "wSort") { wSort = t.value; renderPage(); return; }
    if (t.id === "wLeg") { wLegendary = t.checked; renderPage(); return; }
    if (t.hasAttribute("data-map")) { p.extras = { ...(p.extras || {}), map: t.value || null }; delete p.extras.cradle; renderPage(); queueSave(); return; }
    if (t.dataset.cradleRow) { cradleEdit(t.dataset.cradleRow, t.value || null); renderPage(); queueSave(); return; }
    if (t.dataset.cradleVal) { cradleEdit(t.dataset.cradleVal, undefined, t.value === "" ? null : Math.max(0, Math.min(200, +t.value))); queueSave(); return; }
    if (t.hasAttribute("data-mask-hide")) { p.extras = { ...(p.extras || {}), mask_hide: t.value || null }; renderPage(); queueSave(); return; }
    if (t.dataset.hideCond) {
      const set = new Set(p.extras?.hide_cond || []); t.checked ? set.add(t.dataset.hideCond) : set.delete(t.dataset.hideCond);
      p.extras = { ...(p.extras || {}), hide_cond: [...set] }; renderPage(); queueSave(); return;
    }
    if (t.hasAttribute("data-auto-food")) {
      p.extras = { ...(p.extras || {}), auto_food: t.checked };
      if (!t.checked) p.extras.consumables = (state.result?.best?.config?.consumables || []).map((f) => f.name);
      renderGear(); queueSave(); return;
    }
    if (t.dataset.basic) {
      const k = t.dataset.basic;
      if (k === "marked") { p.extras = { ...(p.extras || {}), marked: t.checked }; }
      else if (k === "sniper_ws") { p.extras = { ...(p.extras || {}), sniper_ws: t.value === "" ? null : Math.max(0, Math.min(100, Math.round(+t.value))) }; }
      else if (k === "scenario") p.scenario = t.value;
      else p[k] = t.value === "" ? null : Math.max(0, Math.round(+t.value));
      queueSave();
    } else if (t.hasAttribute("data-w-mag")) {
      weaponEdit(t.closest("[data-wname]").dataset.wname, { magazine: t.value }); queueSave();
    } else if (t.hasAttribute("data-w-reload")) {
      weaponEdit(t.closest("[data-wname]").dataset.wname, { reload_s: t.value === "" ? null : Math.min(10, Math.max(0.3, +t.value)) }); queueSave();
    } else if (t.dataset.magOwn) {
      const set = new Set(p.accessories_owned || []); t.checked ? set.add(t.dataset.magOwn) : set.delete(t.dataset.magOwn);
      p.accessories_owned = [...set]; queueSave();
    } else if (t.dataset.magVal) {
      p.accessory_values = { ...(p.accessory_values || {}) };
      if (t.value === "") delete p.accessory_values[t.dataset.magVal];
      else p.accessory_values[t.dataset.magVal] = { reload_speed: Math.min(50, Math.max(-50, +t.value)) };
      queueSave();
    } else if (t.dataset.wCal) {
      const tile = t.closest("[data-wname]"); const name = tile.dataset.wname;
      const get = (f) => tile.querySelector(`[data-w-cal="${f}"]`).value;
      const style = get("style");
      const cal = style ? { style, attack: Math.min(50, Math.max(0, +get("attack") || 0)), sub: get("sub") || null,
        sub_value: Math.min(40, Math.max(0, +get("sub_value") || 0)),
        style_value: tile.querySelector('[data-w-cal="style_value"]')?.value === "" || !tile.querySelector('[data-w-cal="style_value"]') ? null : +tile.querySelector('[data-w-cal="style_value"]').value } : null;
      weaponEdit(name, { calibration: cal });
      queueSave();
    }
  });
  function gearClick(t) {
    const p = prof();
    if (t.dataset.wown) { wOwned = t.dataset.wown; renderPage(); return true; }
    if (t.dataset.aslotf) { aSlot = t.dataset.aslotf; renderPage(); return true; }
    if (t.dataset.wear) {
      const nm = t.dataset.wear, slot = slotOf(nm), cur = (p.armor || {})[slot];
      wear(slot, cur && cur.name === nm ? null : nm); renderPage(); queueSave(); return true;
    }
    if (t.hasAttribute("data-backup")) { exportBackup(t); return true; }
    if (t.hasAttribute("data-cradle-auto")) { const p = prof(); p.extras = { ...(p.extras || {}) }; delete p.extras.cradle; renderPage(); queueSave(); return true; }
    if (t.dataset.crate) { if (crId !== t.dataset.crate) { crId = t.dataset.crate; crRes = null; } renderPage(); $(".cr-opts")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); return true; }
    if (t.hasAttribute("data-crate-run")) { runCrate(); return true; }
    if (t.dataset.crAim) { crAim = t.dataset.crAim; runCrate(); return true; }
    if (t.hasAttribute("data-dust")) { crDust = $("#dustIn").value; crBought = Math.max(0, Math.min(10, +$("#dustBought").value || 0)); runDust(); return true; }
    if (t.hasAttribute("data-pity")) { runPity(); return true; }
    if (t.dataset.add) { openPicker(t.dataset.add); return true; }
    if (t.closest("#pickGrid") && pickCtx?.kind === "equip") {
      if (t.dataset.pickMine) { pickMine = t.dataset.pickMine === "1"; pickLock = null; renderPicker(); return true; }
      if (t.dataset.pick) { chooseEquip(t.dataset.pick); return true; }
      if (t.dataset.pickLock) { pickLock = pickLock === t.dataset.pickLock ? null : t.dataset.pickLock; renderPicker(); return true; }
      if (t.dataset.pickLv) { chooseEquip(pickLock, +t.dataset.pickLv); return true; }
    }
    if (t.dataset.pick !== undefined && t.closest("#pickGrid")) { choose(t.dataset.pick); return true; }
    if (t.id === "closePicker") { $("#picker").close(); return true; }
    const wt = t.closest("[data-wname]");
    if (wt && t.dataset.wStar) { weaponEdit(wt.dataset.wname, { stars: +t.dataset.wStar }); renderGear(); queueSave(); return true; }
    if (wt && t.hasAttribute("data-w-own")) { addWeapon(wt.dataset.wname); renderGear(); queueSave(); return true; }
    if (wt && t.hasAttribute("data-w-remove")) { removeWeapon(wt.dataset.wname); renderGear(); queueSave(); return true; }
    if (t.dataset.own) { own(t.dataset.own, !ownedArmor()[t.dataset.own]); renderGear(); queueSave(); return true; }
    const oa = t.closest("[data-aname]");
    if (oa) {
      const n = oa.dataset.aname;
      if (t.dataset.aoStar) { armorStars(n, +t.dataset.aoStar); renderGear(); queueSave(); return true; }
      if (t.hasAttribute("data-ao-wear")) { wear(slotOf(n), n); renderGear(); queueSave(); return true; }
      if (t.hasAttribute("data-ao-del")) { own(n, false); renderGear(); queueSave(); return true; }
    }
    const at = t.closest("[data-aslot]");
    if (at) {
      const slot = at.dataset.aslot;
      if (t.dataset.aStar) { armorStars(p.armor[slot].name, +t.dataset.aStar); renderGear(); queueSave(); return true; }
      if (t.hasAttribute("data-a-clear")) { delete p.armor[slot]; renderGear(); queueSave(); return true; }
      if (t.closest("[data-a-slotfilter]")) { aSlot = slot; renderPage(); $("#aSearch")?.scrollIntoView({ behavior: "smooth", block: "start" }); return true; }
    }
    if (t.dataset.mslot) { modSlot = t.dataset.mslot; modFam = "all"; gmSel = null; if (modFilter) { modFilter = ""; } renderGear(); return true; }
    if (t.dataset.eqPick || t.dataset.eqSwap) { openPicker("equip", t.dataset.eqPick || t.dataset.eqSwap); return true; }
    if (t.dataset.eqBest) { const b = bestFor(t.dataset.eqBest); if (b) setEq(t.dataset.eqBest, { name: b.name, variant: b.variant, level: b.level }); renderGear(); queueSave(); return true; }
    if (t.dataset.eqClear) { setEq(t.dataset.eqClear, null); renderGear(); queueSave(); return true; }
    if (t.hasAttribute("data-w-hands")) { const n = t.closest("[data-wname]").dataset.wname; prof().extras = { ...(prof().extras || {}), equipped_weapon: n }; renderGear(); queueSave(); return true; }
    if (t.dataset.mview) { modView = t.dataset.mview; renderGear(); return true; }
    if (t.dataset.mfam) { modFam = t.dataset.mfam; renderGear(); return true; }
    if (t.dataset.gm) {
      const k = t.dataset.gm; gmSel = gmSel === k ? null : k; renderGear();
      document.querySelector(`[data-gm-edit="${CSS.escape(k)}"] .gm-lvb.on, [data-gm-edit="${CSS.escape(k)}"] .gm-lvb`)?.focus({ preventScroll: true });
      return true;
    }
    const ge = t.closest("[data-gm-edit]");
    if (ge) {
      const [n, v] = ge.dataset.gmEdit.split("|");
      if (t.hasAttribute("data-gm-close")) { gmSel = null; renderGear(); return true; }
      if (t.dataset.gmLv) {
        const lv = +t.dataset.gmLv;
        if (!state.inventory.mods.some((x) => modKey(x) === modKey({ name: n, variant: v }))) addMod(n, v);
        const m = state.inventory.mods.find((x) => modKey(x) === modKey({ name: n, variant: v }));
        modLevel(m, lv); if (lv !== 17) gmSel = null; renderGear(); queueSave(); return true;  // stay open at 17 so Shiny can be ticked
      }
      if (t.hasAttribute("data-gm-del")) {
        const m = state.inventory.mods.find((x) => modKey(x) === modKey({ name: n, variant: v }));
        if (m) removeMod(m); gmSel = null; renderGear(); queueSave(); return true;
      }
    }
    if (t.dataset.mcAdd) {
      const [n, v] = t.dataset.mcAdd.split("|"); addMod(n, v); renderGear(); queueSave();
      const inp = document.querySelector(`[data-mc-lv="${CSS.escape(modKey({ name: n, variant: v }))}"]`); if (inp) { inp.focus(); inp.select(); }
      return true;
    }
    const mt = t.closest("[data-mkey]");
    if (mt) {
      const m = state.inventory.mods.find((x) => modKey(x) === mt.dataset.mkey);
      if (m && t.dataset.mLv) { modLevel(m, Math.max(1, Math.min(17, m.level + +t.dataset.mLv))); renderGear(); queueSave(); return true; }
      if (m && t.hasAttribute("data-m-remove")) { removeMod(m); renderGear(); queueSave(); return true; }
    }
    if (t.dataset.dev !== undefined) {
      p.extras = { ...(p.extras || {}) };
      p.extras.deviation = p.extras.deviation === t.dataset.dev ? null : t.dataset.dev;
      renderGear(); queueSave(); return true;
    }
    if (t.dataset.cls) {
      p.extras = { ...(p.extras || {}), class: t.dataset.cls };
      p.extras.consumables = fitCons(consList(p.extras), t.dataset.cls);
      delete p.extras.food; delete p.extras.drink;
      renderGear(); queueSave(); return true;
    }
    if (t.dataset.cons !== undefined) {
      const ex = { ...(p.extras || {}) }, n = t.dataset.cons, cls = ex.class || "freelancer";
      const cur = ex.auto_food !== false ? (state.result?.best?.config?.consumables || []).map((f) => f.name) : fitCons(consList(ex), cls);
      ex.auto_food = false;
      ex.consumables = cur.includes(n) ? cur.filter((x) => x !== n) : addCons(cur, n, cls);
      delete ex.food; delete ex.drink;
      p.extras = ex; renderGear(); queueSave(); return true;
    }
    if (t.dataset.devLv) { p.extras = { ...(p.extras || {}), deviation_level: +t.dataset.devLv }; renderGear(); queueSave(); return true; }
    return false;
  }

  document.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.effort) {
      const p = prof(); p.extras = { ...(p.extras || {}), effort: t.dataset.effort === "normal" ? null : t.dataset.effort };
      if (!$("#gearPane")?.closest("[hidden]")) renderPage();
      $("#eff") && ($("#eff").innerHTML = '<div class="skeleton"></div>');
      queueSave(); return;
    }
    if (t.closest("#gearPane, #picker") && gearClick(t)) return;
    else if (t.hasAttribute("data-wear-best")) {
      const A = state.result.best_armor; if (!A || A.same) return;
      const p = prof(); p.armor = { ...(p.armor || {}) }; keepWornOwned(p);
      A.changes.forEach((c) => {
        if (c.to) p.armor[c.slot] = { name: c.to, stars: +c.stars || 1, tier: 5 }; else delete p.armor[c.slot];
        setEq(c.slot.toLowerCase(), null);
      });
      t.disabled = true; t.textContent = "Wearing it · recalculating…"; queueSave();
    }
    else if (t.dataset.wearSurv) {
      const B = (survSt?.builds || []).find((x) => x.key === t.dataset.wearSurv); if (!B) return;
      const p = prof(); p.armor = { ...(p.armor || {}) }; keepWornOwned(p);
      B.armor_changes.forEach((c) => {
        const piece = B.armor[c.slot];
        if (piece) p.armor[c.slot] = { name: piece.name, stars: +piece.stars || 1, tier: 5 }; else delete p.armor[c.slot];
        setEq(c.slot.toLowerCase(), null);
      });
      t.disabled = true; t.textContent = "Wearing it · recalculating…"; queueSave();
    }
    else if (t.id === "thRun") runTheory();
    else if (t.hasAttribute("data-remove")) t.parentElement.remove();
    else if (t.dataset.tab) { tab = t.dataset.tab; renderTabs(state.result.upgrades); renderUpgrades(); }
    else if (t.parentElement?.classList.contains("up")) {
      const li = t.parentElement; li.classList.toggle("open"); t.setAttribute("aria-expanded", li.classList.contains("open"));
    }
  });


  // ---------------------------------------------------------- Updates (continuity)
  const KIND_NAME = { weapon: "Weapon", armor: "Armor", set: "Armor set", mod: "Mod", food: "Food / drink", deviation: "Deviation", fight: "Fight type" };
  function newMark(kind, name) { return state?.catalog?.new_marks?.[`${kind}:${name}`]; }
  function newTag(kind, name) {
    const m = newMark(kind, name);
    return m ? ` <span class="new-tag" title="First seen ${esc(m.first)}${m.post ? ` · named in ${esc(m.post.title || "an official post")}` : m.via ? ` (${esc(m.via)})` : ""}">NEW!</span>` : "";
  }
  let upd = null, updTimer = null, updFight = {}, handoff = "";
  async function loadUpd() {
    try {
      const r = await fetch("/api/forge/update/status", { cache: "no-store" });
      const was = upd?.job?.running;
      upd = await r.json();
      if (was && !upd.job.running) await load();   // a run just finished: pick up new items and numbers
      if (page === "updates") renderPage();
      renderHudData();
      clearTimeout(updTimer);
      if (upd.job.running) updTimer = setTimeout(loadUpd, 1500);
    } catch (e) { upd = { error: e.message }; if (page === "updates") renderPage(); }
  }
  function renderHudData() {
    const i = upd?.info || state?.catalog?.data_info;
    const hud = $("#hud"); if (!hud || !i) return;
    hud.querySelectorAll(".row.data").forEach((n) => n.remove());
    const nNew = Object.keys(state?.catalog?.new_marks || {}).length;
    hud.insertAdjacentHTML("beforeend", `<div class="row data"><span>App version</span><b class="ver">${esc(i.app_version || "—")}</b></div>
      <div class="row data"><span>Game data</span><b>${esc(String(i.retrieved_at || "").slice(0, 10))}</b></div>
      <div class="row data"><span>Last check</span><b class="${i.last_check ? "" : "warn"}">${i.last_check ? esc(String(i.last_check).slice(0, 10)) : "never"}</b></div>
      ${nNew ? `<div class="row data"><span>New items</span><b class="new-c">${nNew}</b></div>` : ""}`);
    const nav = $("#navNew"); if (nav) nav.textContent = nNew ? String(nNew) : "";
  }
  const when = (s) => s ? String(s).replace("T", " ").slice(0, 16) : "never";
  function paneUpdates() {
    if (!upd) { loadUpd(); return `<div class="skeleton"></div>`; }
    if (upd.error) return `<p class="empty-msg">Could not reach the update service: ${esc(upd.error)}</p>`;
    const j = upd.job || {}, i = upd.info || {}, rep = j.report;
    const run = j.running ? `<div class="upd-prog" role="status"><div class="upd-bar"><span style="width:${Math.max(3, j.pct || 0)}%"></span></div>
        <p>${esc(j.mode === "quick" ? "Quick check" : "Full check")} · ${esc(j.msg || "")} · ${j.pct || 0}%</p></div>` : "";
    const hero = `<section class="card upd-hero">
      <div class="upd-facts">
        <div><span>Game data (th.gl)</span><b>${esc(when(i.retrieved_at))}</b><small>${i.refreshed ? "refreshed by this button" : "the copy that came with the app"}</small></div>
        <div><span>Last check</span><b>${esc(when(i.last_check))}</b><small>${i.last_check ? "" : "press Check for updates"}</small></div>
        <div><span>Newest official post</span><b>${esc(i.latest_post?.date || "—")}</b><small>${i.latest_post ? `<a href="${esc(i.latest_post.url)}" target="_blank" rel="noopener">${esc(i.latest_post.title)}</a>` : "not read yet"}</small></div>
        <div><span>App version</span><b>${esc(i.app_version || "—")}</b>${appUpdCell()}</div>
      </div>
      <div class="upd-actions">
        <button class="btn primary" type="button" data-upd="full" ${j.running ? "disabled" : ""}>Check for updates</button>
        <button class="btn" type="button" data-upd="quick" ${j.running ? "disabled" : ""}>Quick check</button>
        ${i.can_undo ? `<button class="btn" type="button" data-upd="undo" ${j.running ? "disabled" : ""}>Undo last data refresh</button>` : ""}
        <button class="btn" type="button" data-upd="handoff">Copy status for Computer</button>
      </div>
      <p class="hint">Full check: reads the official patch notes and dev blogs, then re-reads every weapon, armor piece and mod from oncehuman.th.gl (about 5 minutes). Quick check: patch notes and new names only (about 20 seconds). Your game files are never touched.</p>
      ${run}${j.error ? `<p class="upd-err">The run stopped: ${esc(j.error)}</p>` : ""}
      ${handoff ? `<label class="upd-hand">Status for Computer (copied; paste it into a Computer chat)<textarea readonly rows="8" id="handoffBox">${esc(handoff)}</textarea></label>` : ""}
    </section>`;
    return hero + (rep ? reportHtml(rep) : `<p class="hint">No report yet. Press <b>Check for updates</b>.</p>`) + newItemsHtml() + fightsHtml(rep) + typedHtml() + historyHtml() + honestHtml();
  }
  function reportHtml(r) {
    const imp = r.impact?.lines || [];
    const ch = (r.changes || []).map((c) => `<li><b>${esc(c.kind)} · ${esc(c.name)}</b>${newTag(c.kind === "Mod" ? "mod" : c.kind === "Weapon" ? "weapon" : "armor", c.name)}
        <ul>${c.lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">th.gl page</a>` : ""}</li>`).join("");
    const gone = (r.removed || []).map((x) => `<li>${esc(x.kind)} · ${esc(x.name)}</li>`).join("");
    const need = (r.needs_numbers || []).filter((x) => !(state.catalog.typed?.[x.kind === "food" ? "consumables" : "deviations"] || {})[x.name]);
    const needRows = need.map((x, k) => `<div class="upd-need upd-form" data-kind="${x.kind === "food" ? "consumables" : "deviations"}">
        <div class="upd-need-h">${pic(x.name, "sm")}<div><b>${esc(x.name)}</b>${newTag(x.kind, x.name)} <span class="chip">${esc(x.kind)}</span>
          <div class="tsub">${x.text ? `th.gl says: “${esc(x.text)}”` : "th.gl lists the name only."}${x.post ? ` Announced in <a href="${esc(x.post_url)}" target="_blank" rel="noopener">${esc(x.post)}</a>.` : ""}</div></div></div>
        <div class="upd-row"><input type="hidden" data-f="name" value="${esc(x.name)}">
          ${x.kind === "food" ? `<select data-f="slots" aria-label="Slot"><option value="food">Food</option><option value="drink">Drink</option><option value="food,drink">Food + drink</option></select>` : ""}
          <input type="text" data-f="text" placeholder="Type the buff from the in-game tooltip, e.g. Weapon DMG +15%" aria-label="Buff for ${esc(x.name)}">
          <button class="btn small" type="button" data-upd="savetyped">Count it</button></div></div>`).join("");
    const posts = (r.news?.posts || []).map((p) => {
      const ann = (p.announced || []).map((a) => `<span class="chip ${a.in_data ? "good" : "warn"}">${esc(a.kind)}: ${esc(a.name)} · ${a.in_data ? "in the app's data" : "not in the data yet"}</span>`).join(" ");
      const scn = (p.scenarios || []).map((s) => `<button class="chip-btn" type="button" data-upd="prefill" data-name="${esc(s)}">Plan for “${esc(s)}”</button>`).join(" ");
      const hl = (p.highlights || []).filter((h) => !(h.tags.length === 1 && h.tags[0] === "mentions") || h.names.length).slice(0, 30)
        .map((h) => `<li>${h.tags.map((t) => `<span class="tag t-${esc(t.split(" ")[0])}">${esc(t)}</span>`).join("")} ${esc(h.text)}${h.hand_written?.length ? ` <span class="chip warn">check: ${esc(h.hand_written.join(", "))}</span>` : ""}</li>`).join("");
      return `<details class="upd-post"><summary><span class="d">${esc(p.date)}</span> ${esc(p.title)} <span class="count">${(p.highlights || []).length} lines of interest</span></summary>
        <p><a href="${esc(p.url)}" target="_blank" rel="noopener">Open the official post</a>${p.cradle ? ` · <span class="chip warn">mentions the Cradle</span>` : ""}</p>
        ${ann ? `<p>${ann}</p>` : ""}${scn ? `<p>${scn}</p>` : ""}<ul class="upd-hl">${hl || "<li>Nothing about combat, gear or scenarios.</li>"}</ul></details>`;
    }).join("");
    return `<section class="card upd-rep"><div class="card-head"><p class="eyebrow">Last report · ${esc(when(r.finished))} · ${esc(r.mode === "quick" ? "quick check" : r.kind === "undo" ? "undo" : "full check")}</p><h2>What changed</h2></div>
      <ul class="upd-sum">${(r.summary || []).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
      ${(r.errors || []).length ? `<div class="upd-err"><b>Problems</b><ul>${r.errors.map((e) => `<li>${esc(e)}</li>`).join("")}</ul></div>` : ""}
      ${imp.length ? `<div class="section-t">What it means for your builds</div><ul class="upd-imp">${imp.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : ""}
      ${need.length ? `<div class="section-t">New items with no numbers yet</div><p class="hint">th.gl has no buff numbers for foods and deviations. Type what the in-game tooltip says and the app counts it right away. Leave it blank if it doesn't do damage.</p>${needRows}` : ""}
      ${ch ? `<div class="section-t">Stat changes (${r.changes.length})</div><ul class="upd-ch">${ch}</ul>` : ""}
      ${gone ? `<div class="section-t">No longer in the game data</div><ul class="upd-ch">${gone}</ul>` : ""}
      ${posts ? `<div class="section-t">Official posts read (${r.news.posts.length})</div>${posts}` : ""}
    </section>`;
  }
  const DPS_CHIP = { gear: ["good", "affects DPS"], counted: ["good", "affects DPS (counted)"], "no numbers": ["warn", "no numbers yet"], other: ["", ""] };
  function dpsChip(d) { const c = DPS_CHIP[d]; return c && c[1] ? ` <span class="chip ${c[0]}">${esc(c[1])}</span>` : ""; }
  const DPS_ORDER = { gear: 0, counted: 1, "no numbers": 2, other: 3 };
  const KIND_ORDER = { weapon: 0, armor: 1, set: 2, mod: 3, food: 4, deviation: 5, fight: 6 };
  function sortMarks(m) {
    return Object.keys(m).sort((a, b) => (DPS_ORDER[m[a].dps] ?? 9) - (DPS_ORDER[m[b].dps] ?? 9)
      || (KIND_ORDER[a.split(":")[0]] ?? 9) - (KIND_ORDER[b.split(":")[0]] ?? 9) || a.localeCompare(b));
  }
  function splitKey(k) { const [kind, ...rest] = k.split(":"); return [kind, rest.join(":")]; }
  function newItemsHtml() {
    const m = state.catalog.new_marks || {}, dm = state.catalog.data_marks || {}, sm = state.catalog.scenario_marks || {};
    const keys = sortMarks(m);
    const tiles = keys.map((k) => {
      const [kind, name] = splitKey(k), v = m[k];
      const label = kind === "fight" ? (state.catalog.scenarios[name] || name) : name;
      const why = v.post ? `${v.post.how === "announced" ? "Announced" : "Named"} in <a href="${esc(v.post.url)}" target="_blank" rel="noopener">${esc(v.post.title || "an official post")}</a> (${esc(v.post.date || "")})` : (v.via === "typed in" ? "You added it" : "");
      return `<div class="tile upd-tile ${v.verdict ? "v-" + v.verdict : ""}">${pic(label)}<div class="tname">${esc(label)} <span class="new-tag">NEW!</span></div>
        <div class="tsub">${esc(KIND_NAME[kind] || kind)} · ${v.via === "announced" ? "announced" : "first seen"} ${esc(v.first)}${dpsChip(v.dps)}${v.scenario ? ` <span class="chip scn">${esc(v.scenario)}</span>` : ""}</div>
        ${why ? `<div class="tsub">${why}</div>` : ""}
        <div class="upd-vote" role="group" aria-label="Is ${esc(label)} really new?">
          <button type="button" class="chip-btn" data-upd="verdict" data-key="${esc(k)}" data-v="cool" aria-pressed="${v.verdict === "cool"}">Nice find</button>
          <button type="button" class="chip-btn" data-upd="verdict" data-key="${esc(k)}" data-v="wrong" aria-pressed="${v.verdict === "wrong"}">Looks wrong</button>
          <button type="button" class="chip-btn" data-upd="verdict" data-key="${esc(k)}" data-v="not_new">Not new</button></div></div>`;
    }).join("");
    const main = `<section class="card upd-new"><div class="card-head"><p class="eyebrow">Quality check</p><h2>New in the game${keys.length ? ` (${keys.length})` : ""}</h2></div>
      ${keys.length ? `<p class="hint">Only things that showed up after the app's first read <b>and</b> are named in an official patch note or dev blog get <span class="new-tag">NEW!</span>. Things that change damage are listed first. If one isn't really new, tap <b>Not new</b>; <b>Looks wrong</b> flags it for Computer's next check-in.</p>
        <div class="tile-grid">${tiles}</div>`
        : `<p class="hint">Nothing new right now. A gun, armor piece, mod, food or deviation gets <span class="new-tag">NEW!</span> (for 21 days) only when it shows up in the data after the app's first read and an official post names it.</p>`}</section>`;
    // scenario items: named in a scenario post (e.g. Isles of Abyss); new or not
    const byScn = {};
    for (const k of sortMarks(sm)) (byScn[sm[k].scenario] ||= []).push(k);
    const scn = Object.entries(byScn).map(([s, ks]) => {
      const p = sm[ks[0]];
      const rows = ks.map((k) => { const [kind, name] = splitKey(k), v = sm[k];
        return `<li><b>${esc(name)}</b>${v.new ? ` <span class="new-tag">NEW!</span>` : ""} <span class="chip">${esc(KIND_NAME[kind] || kind)}</span>${dpsChip(v.dps)}${v.line ? `<div class="tsub">“${esc(v.line)}”</div>` : ""}</li>`; }).join("");
      return `<details class="upd-post" ${ks.length <= 8 ? "open" : ""}><summary><span class="d">${esc(p.date || "")}</span> ${esc(s)} <span class="count">${ks.length} item${ks.length === 1 ? "" : "s"}</span></summary>
        <p class="hint">Named in <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title || "the official post")}</a>. These came with or are used in ${esc(s)}. Most were already in the game data before the app's first read, so they don't get NEW!.</p>
        <ul class="upd-ch">${rows}</ul></details>`;
    }).join("");
    const scnCard = scn ? `<section class="card upd-scn"><div class="card-head"><p class="eyebrow">By scenario</p><h2>Scenario items</h2></div>${scn}</section>` : "";
    // new to the data only
    const dk = sortMarks(dm);
    const dataCard = dk.length ? `<section class="card upd-data"><details><summary><b>New to the data, not in patch notes (${dk.length})</b></summary>
      <p class="hint">These showed up on th.gl but no official post names them, so they're probably older items th.gl only now lists. No NEW! badge. If one really is new, tap <b>It's new</b>.</p>
      <ul class="upd-ch">${dk.map((k) => { const [kind, name] = splitKey(k), v = dm[k];
        return `<li><b>${esc(name)}</b> <span class="chip">${esc(KIND_NAME[kind] || kind)}</span>${dpsChip(v.dps)} <span class="tsub">first seen ${esc(v.first)}</span>
          <button type="button" class="chip-btn" data-upd="verdict" data-key="${esc(k)}" data-v="cool">It's new</button></li>`; }).join("")}</ul></details></section>` : "";
    return main + scnCard + dataCard;
  }  function fightsHtml(rep) {
    const cs = state.catalog.custom_scenarios || {}, cur = (prof().scenario || "boss").split("@")[0];
    const named = [...new Set((rep?.news?.posts || []).flatMap((p) => p.scenarios || []))];
    const rows = Object.entries(cs).map(([k, s]) => `<div class="upd-fight ${cur === k ? "on" : ""}"><div><b>${esc(s.label)}</b>${newTag("fight", k)} <span class="chip">${esc(s.base)}</span>
        <div class="tsub">Buffs: ${s.buff_text ? `“${esc(s.buff_text)}”` : "none"}${Object.keys(s.buffs || {}).length ? ` → counted as ${Object.entries(s.buffs).map(([a, b]) => `${esc(statLabel(a))} +${b}%`).join(", ")}` : ""}
        ${(s.unparsed || []).length ? ` · <span class="warn">not understood: ${esc(s.unparsed.join("; "))}</span>` : ""}${s.note ? ` · ${esc(s.note)}` : ""}</div></div>
        <div class="upd-row">${cur === k ? `<span class="chip good">your fight type</span>` : `<button class="btn small" type="button" data-upd="usefight" data-key="${esc(k)}">Plan for this fight</button>`}
        <button class="btn small" type="button" data-upd="editfight" data-key="${esc(k)}">Edit</button>
        <button class="btn small" type="button" data-upd="delfight" data-key="${esc(k)}">Delete</button></div></div>`).join("");
    const f = updFight;
    return `<section class="card upd-fights" id="fightForm"><div class="card-head"><p class="eyebrow">New scenario? Plan for it before anyone else</p><h2>Custom fights</h2></div>
      <p class="hint">When a new scenario or season brings fight-wide buffs (like a Cradle, a scenario bonus or a boss weakness), set it up here. Type the buffs the way the patch notes or the in-game text says them. Pick it as your fight type, and the best build, the next-upgrade list, the Starchrom plan and the crate advice all follow it.</p>
      ${rows || ""}
      ${named.length ? `<p class="hint">Named in recent posts: ${named.map((s) => `<button class="chip-btn" type="button" data-upd="prefill" data-name="${esc(s)}">${esc(s)}</button>`).join(" ")}</p>` : ""}
      <div class="upd-form upd-grid" data-kind="scenarios">
        <label>Name<input type="text" data-f="name" value="${esc(f.name || "")}" placeholder="e.g. Isles of Abyss boss"></label>
        <label>Built on<select data-f="base">${["boss", "abyss", "mobs"].map((b) => `<option value="${b}" ${f.base === b ? "selected" : ""}>${esc(state.catalog.scenarios[b] || b)}</option>`).join("")}</select></label>
        <label class="wide">Fight buffs (optional)<input type="text" data-f="buff_text" value="${esc(f.buff_text || "")}" placeholder="e.g. Elemental DMG +20%, Burn DMG +50%, Weakspot DMG +15%"></label>
        <label>Weak-spot hit rate % (optional)<input type="number" min="0" max="100" data-f="weakspot_rate" value="${f.weakspot_rate != null ? esc(f.weakspot_rate) : ""}" placeholder="35"></label>
        <label>Enemies hit at once (optional)<input type="number" min="1" max="20" data-f="enemies_hit" value="${esc(f.enemies_hit || "")}" placeholder="1"></label>
        <label class="wide">Note (optional)<input type="text" data-f="note" value="${esc(f.note || "")}" placeholder="where the buff comes from"></label>
        <div class="wide upd-row"><button class="btn primary small" type="button" data-upd="savefight">${f.key ? "Save changes" : "Add fight"}</button>${f.key ? `<button class="btn small" type="button" data-upd="clearfight">Cancel</button>` : ""}</div>
      </div></section>`;
  }
  function typedHtml() {
    const t = state.catalog.typed || {};
    const rows = [...Object.entries(t.consumables || {}).map(([n, v]) => ["consumables", n, v]), ...Object.entries(t.deviations || {}).map(([n, v]) => ["deviations", n, v])];
    const C = state.catalog.extras;
    const list = rows.map(([k, n, v]) => `<li><b>${esc(n)}</b> <span class="chip">${k === "consumables" ? esc((v.slots || ["food"]).join(" + ")) : "deviation"}</span> “${esc(v.text)}”
        ${(k === "consumables" ? C.consumables[n] : C.deviations[n]) ? `<span class="chip good">counted</span>` : `<span class="chip warn">not counted</span>`}
        <button class="btn small" type="button" data-upd="deltyped" data-kind="${k}" data-name="${esc(n)}">Remove</button></li>`).join("");
    return `<section class="card upd-typed"><div class="card-head"><p class="eyebrow">Your additions</p><h2>Foods and deviations you typed in</h2></div>
      ${list ? `<ul class="upd-ch">${list}</ul>` : `<p class="hint">None yet.</p>`}
      <details><summary>Add one by hand</summary><div class="upd-form upd-row" data-kind="consumables">
        <input type="text" data-f="name" placeholder="Name" aria-label="Name">
        <select data-f="kindsel" aria-label="Kind"><option value="food">Food</option><option value="drink">Drink</option><option value="food,drink">Food + drink</option><option value="deviation">Deviation</option></select>
        <input type="text" data-f="text" placeholder="Buff, e.g. Status DMG +20%" aria-label="Buff">
        <button class="btn small" type="button" data-upd="savetyped">Save</button></div></details>
      <p class="hint">These live in your data folder and survive app updates. Computer checks them at the next check-in and moves confirmed ones into the app.</p></section>`;
  }
  function historyHtml() {
    const h = upd.history || [];
    if (!h.length) return "";
    return `<section class="card"><div class="card-head"><p class="eyebrow">Log</p><h2>Past checks</h2></div><ul class="upd-ch">${h.map((e) => `<li><b>${esc(when(e.finished))}</b> · ${esc(e.kind === "undo" ? "undo" : e.mode === "quick" ? "quick check" : "full check")}${e.ok === false ? ` <span class="chip warn">had problems</span>` : ""}<div class="tsub">${esc((e.summary || []).slice(0, 3).join(" "))}</div></li>`).join("")}</ul></section>`;
  }
  function honestHtml() {
    return `<details class="card upd-honest"><summary>What this button can and can't do</summary><ul>
      <li>It reads the official patch notes and dev blogs, plus oncehuman.th.gl, which publishes numbers from the current game files. th.gl usually updates within a day or two of a patch. Until then a check can show the patch notes but not the new numbers. Check again later.</li>
      <li>New or changed weapons, armor and mods are counted automatically, because their effects are written out on th.gl and the app reads them like everything else.</li>
      <li>Foods and deviations have no numbers on th.gl. New ones are marked NEW! and listed until you type their buff or Computer adds it.</li>
      <li>Patch-note numbers for hand-written items (deviations, foods, key armor, calibrations, hides) are flagged, not applied. Wording in patch notes is too loose to trust blindly.</li>
      <li>A brand-new mechanic, for example a new keyword that works differently from the existing ones, needs a code update from Computer. The report shows it under “not counted”.</li>
      <li>Every refresh is backed up, and <b>Undo last data refresh</b> puts the old numbers back.</li></ul></details>`;
  }
  async function updPost(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || `Server answered ${r.status}`);
    return j;
  }

  // ---------------------------------------------------------------- path to max
  let pathSt = null, pathTimer = null;
  async function loadPath() {
    try {
      const r = await fetch("/api/forge/path/status", { cache: "no-store" });
      pathSt = await r.json();
      if (page === "path") renderPage();
      clearTimeout(pathTimer);
      if (pathSt.running) pathTimer = setTimeout(loadPath, 1500);
    } catch (e) { pathSt = { error: e.message }; if (page === "path") renderPage(); }
  }
  const fmt = (n) => n == null ? "—" : Math.round(n).toLocaleString("en-US");
  const HOWCLS = { "Starchrom": "sc", "cook": "free", "catch": "farm", "breed / hunt": "farm", "farm drops / crates": "farm", "calibrate (luck)": "luck", "duplicates + Starchrom": "luck" };
  function pathChart(P) {
    const pts = [{ n: 0, dps: P.start.dps, t: "Now" }, ...P.steps.map((x) => ({ n: x.n, dps: x.dps, t: x.title }))];
    if (P.grind) pts.push({ n: "max", dps: P.grind.dps, t: "Maxed out", grind: true });
    const W = 860, H = 260, L = 64, R = 16, T = 14, B = 34;
    const lines = [];
    const tg = P.group?.targets || {};
    Object.entries(tg).forEach(([pct, v]) => lines.push({ v: v.dps, label: `${pct}% of group`, cls: pct === "50" ? "goal" : "tgt" }));
    if (P.top?.dps) lines.push({ v: P.top.dps, label: "Best build in the game", cls: "top" });
    const maxV = Math.max(...pts.map((p) => p.dps), ...lines.map((l) => l.v)) * 1.06;
    const bw = (W - L - R) / pts.length;
    const y = (v) => T + (H - T - B) * (1 - v / maxV);
    const bars = pts.map((p, i) => {
      const x = L + i * bw + bw * 0.14, w = bw * 0.72, yy = y(p.dps);
      return `<g><title>${esc(p.t)}: ${fmt(p.dps)} est. DPS</title><rect class="pbar ${p.grind ? "grind" : i === 0 ? "now" : ""}" x="${x.toFixed(1)}" y="${yy.toFixed(1)}" width="${w.toFixed(1)}" height="${(H - B - yy).toFixed(1)}" rx="3"/>
        <text class="plab" x="${(x + w / 2).toFixed(1)}" y="${H - B + 16}" text-anchor="middle">${p.n === 0 ? "Now" : p.n === "max" ? "Max" : p.n}</text></g>`;
    }).join("");
    const hl = lines.map((l) => `<g class="pline ${l.cls}"><line x1="${L}" x2="${W - R}" y1="${y(l.v).toFixed(1)}" y2="${y(l.v).toFixed(1)}"/>
      <text x="${L + 6}" y="${(y(l.v) - 5).toFixed(1)}" text-anchor="start">${esc(l.label)} · ${fmt(l.v)}</text></g>`).join("");
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => `<text class="ptick" x="${L - 8}" y="${(y(maxV / 1.06 * f) + 4).toFixed(1)}" text-anchor="end">${fmt(maxV / 1.06 * f / 1000)}k</text>`).join("");
    return `<svg class="path-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Estimated DPS after each step">${ticks}${bars}${hl}</svg>`;
  }

  // Survivability page
  let survSt = null, survKey = "", survBusy = false;
  async function loadSurvive() {
    const k = JSON.stringify(state?.profile || {});
    if (survBusy || (survSt && survKey === k)) return;
    survBusy = true; survKey = k;
    try { const r = await fetch("/api/forge/survive", { cache: "no-store" }); survSt = await r.json(); }
    catch (e) { survSt = { error: e.message }; }
    survBusy = false;
    if (page === "survive") renderPage();
    if (JSON.stringify(state?.profile || {}) !== survKey) loadSurvive();
  }
  function survCard(b, ref, A) {
    const armor = prof().armor || {};
    const refMods = ref?.build?.mods || {};
    const rows = ARMOR_SLOTS.map((s) => {
      const p = b.armor[s], m = b.build.mods?.[s.toLowerCase()], changed = (p?.name || null) !== (armor[s]?.name || null);
      const rm = refMods[s.toLowerCase()], mchg = b.key !== "best" && (m?.name || "") + (m?.variant || "") !== (rm?.name || "") + (rm?.variant || "");
      return `<li class="${changed || mchg ? "chg" : ""}"><span class="ac-slot">${s}</span>
        <span class="ac-piece">${p ? `${pic(p.name, "sm")}<span><b>${esc(p.name)}</b><small>${"★".repeat(+p.stars || 1)}${changed ? " · swap" : ""}</small></span>` : `<span class="faint">empty</span>`}</span>
        <span class="ac-mod">${m ? `<b>${esc(m.name)}</b><small>${esc(m.variant)} · Lv ${esc(m.level)}${mchg ? " · change" : ""}</small>` : `<small class="faint">no mod</small>`}</span></li>`;
    }).join("");
    const wm = b.build.mods?.weapon, rwm = refMods.weapon;
    const gunRow = `<li class="${b.key !== "best" && (wm?.name || "") + (wm?.variant || "") !== (rwm?.name || "") + (rwm?.variant || "") ? "chg" : ""}"><span class="ac-slot">Gun</span>
      <span class="ac-piece">${pic(b.build.weapon.name, "sm")}<span><b>${esc(b.build.weapon.name)}</b></span></span>
      <span class="ac-mod">${wm ? `<b>${esc(wm.name)}</b><small>${esc(wm.variant)} · Lv ${esc(wm.level)}</small>` : `<small class="faint">no mod</small>`}</span></li>`;
    const pctBar = (v, max, cls) => `<span class="sv-bar ${cls}"><i style="width:${Math.max(2, Math.min(100, v / max * 100)).toFixed(1)}%"></i></span>`;
    const maxX = Math.max(...(A.builds || []).map((x) => x.x), 1);
    const kinds = { hp_pct: (e) => `HP +${e.value}%`, hp_flat: (e) => `HP +${num(e.value)}`, shield_pct: (e) => `Shield ${e.value}% of Max HP`, dr: (e) => `${e.value}% less damage taken`, dr_shielded: (e) => `${e.value}% less damage taken` };
    const counted = b.counted.map((e) => `<li><b>${esc(e.src)}</b> · ${esc((kinds[e.kind] || (() => e.text))(e))}<small>${esc(e.why)}</small></li>`).join("");
    const missed = b.not_counted.map((e) => `<li><b>${esc(e.src)}</b> · ${esc(e.text)}</li>`).join("");
    const head = b.key === "best" ? "Your best-DPS build" : b.label;
    const sub = { best: "The Best build page's pick, for comparison", free: "Same damage, harder to kill", t5: "Keeps at least 95% of your damage", t10: "Keeps at least 90% of your damage", immortal: "As tough as your gear allows, whatever the damage" }[b.key] || "";
    return `<section class="card sv-card sv-${b.key}">
      <div class="card-head"><p class="eyebrow">${esc(sub)}</p><h2>${esc(head)}</h2></div>
      <div class="sv-nums">
        <div><small>Toughness</small><b class="mono">${num(b.toughness)}</b><span class="chip ${b.x > 1.005 ? "good" : ""}">${b.x.toFixed(2)}× ${b.key === "best" ? "baseline" : "vs best DPS"}</span>${pctBar(b.x, maxX, "t")}</div>
        <div><small>Damage</small><b class="mono">${num(b.dps)} DPS</b><span class="chip ${b.dps_pct < 99.5 ? "warn" : "good"}">${b.dps_pct}% of max</span>${pctBar(b.dps_pct, 100, "d")}</div>
      </div>
      <p class="sv-stats mono">HP ${num(b.hp)}${b.hp_pct ? ` (+${b.hp_pct}%)` : ""} · damage taken −${b.dr_pct}%${b.shield ? ` · shield ${num(b.shield)}` : ""}</p>
      ${b.beats_wearing ? `<p class="chip good">More damage and tougher than what you're wearing</p>` : ""}
      <ul class="ac-list">${rows}${gunRow}</ul>
      ${b.key !== "best" && b.armor_changes.length ? `<button class="btn small" type="button" data-wear-surv="${esc(b.key)}">Wear this armor (${b.armor_changes.length} swap${b.armor_changes.length === 1 ? "" : "s"})</button>` : ""}
      <details class="sv-why"><summary>What's counted (${b.counted.length})</summary><ul class="plain">${counted || `<li class="faint">Nothing on this build adds survival.</li>`}</ul></details>
      ${missed ? `<details class="sv-why"><summary>Not counted (${b.not_counted.length})</summary><ul class="plain">${missed}</ul></details>` : ""}
    </section>`;
  }
  function paneSurvive() {
    if (!state.result.best) return `<section class="card"><div class="card-head"><p class="eyebrow">Survivability</p><h2>Get your first gun first</h2></div><p class="hint">Survivability starts from a build you own. Add a weapon on the <a href="#/weapons">Weapons</a> page.</p></section>`;
    if (JSON.stringify(state.profile || {}) !== survKey || !survSt) loadSurvive();
    if (!survSt || survBusy) return `<section class="card"><p class="hint">Searching every armor piece and mod you own for the toughest builds… (about 10 seconds)</p><div class="skeleton"></div><div class="skeleton"></div></section>`;
    const A = survSt;
    if (A.error) return `<section class="card"><p class="bad">${esc(A.error)}</p></section>`;
    const W = A.wearing;
    const top = `<section class="card sv-top"><div class="sv-top-row">
      <div><small>Your best-DPS build</small><b class="mono">${num(A.reference.toughness)}</b><span class="hint">toughness · ${num(A.reference.dps)} DPS</span></div>
      ${W ? `<div><small>What you're wearing now</small><b class="mono">${num(W.toughness)}</b><span class="hint">toughness · ${num(W.dps)} DPS · ${W.x.toFixed(2)}×</span></div>` : ""}
      <div class="sv-free">${A.free_none ? `<span class="chip">No free toughness</span><span class="hint">Every tougher build you own costs some damage.</span>` : `<span class="chip good">Free toughness found</span><span class="hint">A build with the same damage that's harder to kill is shown first.</span>`}</div>
      </div><p class="hint">${esc(A.note)} 1.25× means you survive 25% more boss damage.</p></section>`;
    const cards = A.builds.map((b) => survCard(b, A.reference, A)).join("");
    const how = `<details class="card sv-how"><summary>How the estimate works</summary>
      <p class="hint">Toughness = (HP + shield) ÷ share of damage that gets through. Conditional damage reduction is weighted by how often it's on in a long boss fight:</p>
      <ul class="plain">${A.uptimes.map((u) => `<li>${esc(u.how)}</li>`).join("")}</ul>
      <p class="hint">Not counted anywhere: your character's base HP, healing (syringes, lifesteal, kill heals), Deviations, food, dodging and teammates. Healing and kill effects don't add toughness here.</p></details>`;
    return top + `<div class="sv-grid">${survCard(A.reference, A.reference, A)}${cards}</div>` + how;
  }
  function panePath() {
    if (!state.result.best) return `<section class="card"><div class="card-head"><p class="eyebrow">Path to max</p><h2>Get your first gun first</h2></div>
      <p class="hint">The path starts from a build you own. You don't own a weapon yet, so the <a href="#/build">Best build</a> page shows a new-player start instead: what to save for, what's free, and which mods to farm.</p></section>`;
    if (!pathSt) { loadPath(); return `<div class="skeleton"></div>`; }
    const ex = prof().extras || {}, g = ex.group_share || {};
    const mine = state.result.best?.dps;
    const P = pathSt.plan;
    const run = pathSt.running;
    const goal = `<section class="card path-goal"><div class="card-head"><p class="eyebrow">Your goal</p><h2>Carry the group</h2></div>
      <p class="hint">After your next group run (dungeon, Nightmare, Abyss), check the damage meter and type your share of the team's damage. The app works out how strong your teammates were and shows the step where you'd reach 25%, a third, and half of the group's damage.</p>
      <div class="path-goal-row">
        <label>My share last run (%)<input type="number" min="1" max="99" step="1" id="grpPct" value="${g.pct ?? ""}" placeholder="e.g. 9"></label>
        <label>My build then (est. DPS)<input type="number" min="1" step="1" id="grpDps" value="${g.dps ?? (mine ? Math.round(mine) : "")}"></label>
        <button class="btn small" type="button" data-path="savegrp">Save</button>
        ${g.pct ? `<button class="btn small" type="button" data-path="clrgrp">Clear</button>` : ""}
      </div>
      <p class="hint">"My build then" defaults to your current estimate (${fmt(mine)}). Change it if your gear was different on that run.</p>
      <div class="upd-row"><button class="btn primary" type="button" data-path="run" ${run ? "disabled" : ""}>${P ? "Re-plan my path" : "Plan my path"}</button>
      <span class="hint">Takes about a minute: it re-runs the optimizer after each step.</span></div>
      ${run ? `<div class="upd-prog"><div class="upd-bar"><i style="width:${pathSt.pct || 2}%"></i></div><p class="mono">${esc(pathSt.msg || "")} · ${pathSt.pct || 0}%</p></div>` : ""}
      ${pathSt.error ? `<p class="bad">Planning failed: ${esc(pathSt.error)}</p>` : ""}
      ${P && pathSt.stale && !run ? `<p class="warn-line">Your gear or settings changed since this plan was made. Press <b>Re-plan my path</b>.</p>` : ""}
    </section>`;
    if (!P) return goal + `<p class="hint">No plan yet. Press <b>Plan my path</b>.</p>`;
    if (P.error) return goal + `<p class="bad">${esc(P.error)}</p>`;
    const tg = P.group?.targets || {};
    const tgChips = Object.keys(tg).length ? Object.entries(tg).map(([pct, v]) => {
      const where = v.start ? "already there" : v.step ? `at step ${v.step}` : v.grind ? "only after maxing out" : "not reachable with this plan";
      return `<span class="chip ${v.start || v.step ? "good" : v.grind ? "" : "bad"}">${pct}% of group: ${fmt(v.dps)} DPS · ${where}</span>`;
    }).join(" ") : `<span class="hint">Type your group share above to see when you'd carry the team.</span>`;
    const half = tg["50"];
    let verdict = "";
    if (half) {
      if (half.start || half.step) verdict = `You can reach half of the group's damage ${half.start ? "already" : `at step ${half.step}`}.`;
      else {
        const endShare = P.grind?.share ?? P.end.share;
        verdict = `Against the teammates from that run, half the damage needs about ${fmt(half.dps)} DPS. This plan gets you to ${P.end.share}%${P.grind ? `, and ${P.grind.share}% fully maxed` : ""}. ${endShare >= 40 ? "Close: better weakspot aim and uptime closes the rest." : "Those teammates were very strong, or the run favoured area damage. Re-check with a normal group."}`;
      }
    }
    const sum = `<section class="card"><div class="card-head"><p class="eyebrow">Plan · ${esc((P.made_at || "").slice(0, 16).replace("T", " "))} · ${esc(state.catalog.scenarios[P.scenario] || P.scenario || "")}</p><h2>${fmt(P.start.dps)} → ${fmt(P.end.dps)} est. DPS (×${P.end.x_start})</h2></div>
      <div class="upd-facts">
        <div><span>Starchrom needed</span><b>${fmt(P.end.spent)}</b><small>${P.budget != null ? `you have ${fmt(P.budget)}` : ""}</small></div>
        <div><span>Of the best build in the game</span><b>${P.start.pct_of_top}% → ${P.end.pct_of_top}%</b><small>${esc(P.top.weapon || "")}${P.top.marked ? " (with Bull's Eye)" : ""}</small></div>
        <div><span>Your share of group damage</span><b>${P.start.share != null ? `${P.start.share}% → ${P.end.share}%` : "—"}</b><small>${P.start.share != null ? "vs the teammates from your typed run" : "type your share above"}</small></div>
        <div><span>Worth it up to</span><b>${P.knee ? `step ${P.knee}` : "—"}</b><small>later steps add under 5% each</small></div>
      </div>
      <div class="path-targets">${tgChips}</div>
      ${verdict ? `<p class="path-verdict">${esc(verdict)}</p>` : ""}
      <div class="path-chart-wrap">${pathChart(P)}</div>
    </section>`;
    const rows = P.steps.map((x) => `<li class="path-step ${P.knee && x.n > P.knee ? "dim" : ""}">
      <div class="ps-n">${x.n}</div>
      <div class="ps-body"><div class="ps-title">${esc(x.title)}</div>
        <div class="ps-meta"><span class="chip how-${HOWCLS[x.how] || "farm"}">${esc(x.how)}</span>
          ${x.cost ? `<span class="chip">${fmt(x.cost)} Starchrom · total ${fmt(x.spent)}</span>` : `<span class="chip">no Starchrom</span>`}
          ${x.over_budget ? `<span class="chip bad">past your current Starchrom</span>` : ""}
          ${P.knee && x.n === P.knee ? `<span class="chip good">worth it up to here</span>` : ""}</div>
        ${x.detail ? `<p class="hint">${esc(x.detail.slice(0, 260))}</p>` : ""}</div>
      <div class="ps-num"><b>${fmt(x.dps)}</b><span>+${x.gain_pct}% · ${x.pct_of_top}% of top${x.share != null ? ` · ${x.share}% of group` : ""}</span></div></li>`).join("");
    const grind = P.grind ? `<li class="path-step grind"><div class="ps-n">∞</div><div class="ps-body"><div class="ps-title">Then grind: max out ${esc(P.grind.weapon)}</div>
      <p class="hint">${esc(P.grind.text)}</p></div><div class="ps-num"><b>${fmt(P.grind.dps)}</b><span>+${P.grind.gain_pct}% · ${P.grind.pct_of_top}% of top${P.grind.share != null ? ` · ${P.grind.share}% of group` : ""}</span></div></li>` : "";
    const steps = `<section class="card"><div class="card-head"><p class="eyebrow">In this order</p><h2>Your steps</h2></div>
      <p class="hint">Do them top to bottom. Each step is counted on top of the ones before it. The planner settles your main weapon before it spends luck on stars or calibration, so nothing gets wasted on a gun you'll replace.</p>
      <ol class="path-steps">${rows}${grind}</ol></section>`;
    const okRoutes = (P.routes || []).filter((r) => !r.error);
    const routes = okRoutes.length ? `<section class="card"><div class="card-head"><p class="eyebrow">Longer road</p><h2>Routes to the top of the ranking</h2></div>
      <p class="hint">The steps above take the best gain for the effort with what you own today, and they end on ${esc(P.grind?.weapon || P.steps.at(-1)?.weapon || P.start.weapon)}${P.grind ? ` (maxed: ${fmt(P.grind.dps)}, ${P.grind.pct_of_top}% of #1)` : ""}. These routes commit to a gun near the top instead. They start slower and need more farming, but they end higher.</p>
      <div class="route-grid">${okRoutes.map((r) => `<div class="route">
        <div class="route-h"><b>${esc(r.weapon)}</b><span class="chip ${r.owned ? "good" : ""}">${r.owned ? "you own it" : r.weapon_cost ? `${fmt(r.weapon_cost)} Starchrom` : "not in your shop list"}</span></div>
        <p class="hint">${esc(r.why_not_main)}</p>
        <ol class="route-steps"><li><span>Switch to it with your current mods</span><b>${fmt(r.first)}</b></li>
          ${r.steps.map((x) => `<li><span>${esc(x.title)} <small>${esc(x.how)}${x.cost ? ` · ${fmt(x.cost)} Starchrom` : ""}</small></span><b>${fmt(x.dps)}</b></li>`).join("")}
          ${r.maxed ? `<li class="grind"><span>Then grind: max it out (6★, level-17 mods, best rolls)</span><b>${fmt(r.maxed)}</b></li>` : ""}</ol>
        <p class="route-foot">After the steps: <b>${fmt(r.end)}</b> (${r.end_pct_of_top}% of #1) · maxed: <b>${fmt(r.maxed)}</b> (${r.maxed_pct_of_top}% of #1) · Starchrom ${fmt(r.spent)}</p>
      </div>`).join("")}</div></section>` : "";
    const honest = `<details class="card upd-honest"><summary>How this is worked out</summary><ul>${(P.notes || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
      <p class="hint">Why not just copy the #1 build? It assumes 6★, level-17 mods and perfect rolls on a gun and damage type you may not have. Rebuilding around it usually throws away the mods you already own. This path is the fastest way up from what you have.</p></details>`;
    return goal + sum + steps + routes + honest;
  }
  // ---------------------------------------------------------- named profiles (3 slots)
  function activeSlot() { const S = state?.slots; return S && S.active ? S.slots.find((s) => s.slot === S.active) : null; }
  function renderProfBtn() {
    const b = $("#profBtn"); if (!b) return;
    const a = activeSlot();
    b.innerHTML = `<span class="r-l">Profile</span><b>${esc(a ? a.name : "Not saved in a slot")}</b><span class="caret" aria-hidden="true">▾</span>`;
    b.classList.toggle("warn", !a);
    const dlg = $("#profDlg"); if (dlg?.open) renderProfDlg();
  }
  function renderProfDlg() {
    const S = state.slots || { slots: [] }, body = $("#profBody");
    const cards = S.slots.map((s) => {
      const on = S.active === s.slot;
      return `<div class="prof-slot ${on ? "on" : ""} ${s.empty ? "empty" : ""}">
        <label class="prof-name"><span class="eyebrow">Slot ${s.slot}${on ? " · in use" : ""}</span>
          <input type="text" maxlength="40" value="${esc(s.name)}" data-slot-name="${s.slot}" aria-label="Name for slot ${s.slot}"></label>
        <p class="tsub">${s.empty ? "Empty" : esc(s.summary)}${s.saved ? ` · saved ${esc(new Date(s.saved).toLocaleString())}` : ""}</p>
        ${s.empty ? "" : s.fresh ? `<p><span class="chip warn">New-player test · ignores your recorded game data</span></p>` : `<p><span class="chip good">Uses your recorded game data</span></p>`}
        <div class="upd-row">
          ${on ? `<span class="chip good">in use</span>` : s.empty ? "" : `<button class="btn small primary" type="button" data-slot="load" data-n="${s.slot}">Load</button>`}
          <button class="btn small" type="button" data-slot="save" data-n="${s.slot}">Save</button>
          <button class="btn small" type="button" data-slot="rename" data-n="${s.slot}">Rename</button>
          ${s.empty ? "" : `<button class="btn small" type="button" data-slot="clear" data-n="${s.slot}" ${on ? `disabled title="Load another profile first"` : ""}>Delete</button>`}
        </div></div>`;
    }).join("");
    body.innerHTML = `${S.active ? "" : `<p class="note warn-note">The profile you're using isn't in a slot yet. Press <b>Save</b> on a slot to keep it.</p>`}
      <div class="prof-grid">${cards}</div>
      <p class="hint">Changes save into the profile in use on their own. Loading another profile first saves the one you're leaving (plus a backup copy), so nothing is lost. Each profile remembers whether it uses your recorded game data (inventory, mod levels); a new-player test ignores it.</p>`;
  }
  async function slotPost(body, btn, msg) {
    await profAction("/api/forge/profile/slot", body, btn, msg);
    if ($("#profDlg")?.open) renderProfDlg();
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("#profBtn") || e.target.closest("[data-profiles]")) { renderProfDlg(); $("#profDlg").showModal(); return; }
    if (e.target.closest("[data-prof-close]")) { $("#profDlg").close(); return; }
    const b = e.target.closest("[data-slot]"); if (!b) return;
    const n = Number(b.dataset.n), s = (state.slots?.slots || []).find((x) => x.slot === n), act = b.dataset.slot;
    const name = $(`[data-slot-name="${n}"]`)?.value;
    if (act === "load") return slotPost({ action: "load", slot: n }, b, `Switched to ${s?.name || "slot " + n}`);
    if (act === "rename") {
      const nn = prompt(`New name for slot ${n}:`, s?.name || "");
      if (nn === null || nn.trim() === (s?.name || "")) return;
      return slotPost({ action: "rename", slot: n, name: nn }, b, "Name saved");
    }
    if (act === "save") {
      if (s && !s.empty && state.slots?.active !== n && !confirm(`Replace “${s.name}” with the profile you're using now? The old copy goes to the backup list.`)) return;
      return slotPost({ action: "save", slot: n, name }, b, `Saved in ${name || "slot " + n}`);
    }
    if (act === "clear") {
      if (!confirm(`Are you sure you want to delete “${s?.name}”? A backup copy is kept in the backup list.`)) return;
      return slotPost({ action: "clear", slot: n }, b, "Profile deleted");
    }
  });
  document.addEventListener("change", (e) => {
    const i = e.target.closest("[data-slot-name]"); if (!i) return;
    const n = Number(i.dataset.slotName), s = (state.slots?.slots || []).find((x) => x.slot === n);
    if (s && i.value.trim() === s.name) return;
    slotPost({ action: "rename", slot: n, name: i.value }, null, "Name saved");
  });
  async function profAction(url, body, btn, msg) {
    if (btn) btn.disabled = true;
    $("#saveMsg").textContent = "Working…"; $("#saveMsg").className = "save-state";
    try {
      // drop any queued save and ignore one still in flight, so it can't overwrite this
      clearTimeout(saveTimer); pending = false; editCount++;
      for (let i = 0; saving && i < 600; i++) await new Promise((r) => setTimeout(r, 100));
      pending = false;
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      const next = await r.json();
      if (!r.ok) throw new Error(next.error || `Server answered ${r.status}`);
      Object.assign(state, next); if (page === "path") loadPath();
      render(); renderPage();
      $("#saveMsg").textContent = msg || (next.profile.fresh ? "Fresh start ready" : "Your profile is back"); $("#saveMsg").className = "save-state ok";
    } catch (e) {
      $("#saveMsg").textContent = `Could not do that: ${e.message}`; $("#saveMsg").className = "save-state bad";
    } finally { if (btn) btn.disabled = false; }
  }
  document.addEventListener("click", async (e) => {
    const sv = e.target.closest("[data-save-now]");
    if (sv) { sv.disabled = true; clearTimeout(saveTimer); $("#saveMsg").textContent = "Saving…"; await doSave(); sv.disabled = false; return; }
    const fr = e.target.closest("[data-fresh]");
    if (fr) {
      const sc = $("#freshSc")?.value ?? 5000;
      if (!confirm(`Start fresh with ${sc || 0} Starchrom? The profile you're using stays in its slot; switch back to it any time.`)) return;
      return profAction("/api/forge/profile/fresh", { starchrom: sc }, fr);
    }
    const rs = e.target.closest("[data-restore]");
    if (rs) return profAction("/api/forge/profile/restore", {}, rs);
  });
  document.addEventListener("click", (e) => {
    const f = e.target.closest("[data-devfilter]");
    if (f) { devFilter = f.dataset.devfilter; renderPage(); return; }
    const add = e.target.closest("[data-devown-add]");
    const del = e.target.closest("[data-devown-del]");
    if (!add && !del) return;
    const ex = { ...(prof().extras || {}) };
    const list = Array.isArray(ex.dev_owned) ? [...ex.dev_owned] : [];
    if (add) list.push({ n: $("#devOwnName").value, s: +$("#devOwnS").value, a: +$("#devOwnA").value });
    if (del) list.splice(+del.dataset.devownDel, 1);
    ex.dev_owned = list; prof().extras = ex; queueSave(); renderPage();
  });
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-path]");
    if (!t) return;
    const a = t.dataset.path;
    if (a === "savegrp" || a === "clrgrp") {
      const pct = +($("#grpPct")?.value || 0), dps = +($("#grpDps")?.value || 0);
      const ex = { ...(prof().extras || {}) };
      if (a === "clrgrp" || !pct) delete ex.group_share;
      else ex.group_share = { pct: Math.max(1, Math.min(99, pct)), dps: dps || Math.round(state.result.best?.dps || 0) };
      prof().extras = ex; queueSave(); renderPage(); return;
    }
    if (a === "run") {
      t.disabled = true;
      await saveNow();
      await fetch("/api/forge/path/start", { method: "POST" });
      loadPath();
    }
  });
  function takeState(j) { if (j.result) { state.result = j.result; state.inventory = j.inventory; state.profile = j.profile; state.catalog = j.catalog; render(); } }
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-upd]");
    if (!t) return;
    const a = t.dataset.upd, form = t.closest(".upd-form");
    const val = (f) => form?.querySelector(`[data-f="${f}"]`)?.value?.trim() ?? "";
    try {
      if (a === "full" || a === "quick") { const j = await updPost("/api/forge/update/check", { mode: a }); upd.job = j; renderPage(); loadUpd(); return; }
      if (a === "undo") { if (!confirm("Put the previous game data back?")) return; await updPost("/api/forge/update/undo"); await load(); await loadUpd(); return; }
      if (a === "handoff") {
        const r = await fetch("/api/forge/handoff", { cache: "no-store" }); handoff = (await r.json()).text || "";
        try { await navigator.clipboard.writeText(handoff); } catch (_) { /* the box below lets you copy by hand */ }
        renderPage(); const b = $("#handoffBox"); if (b) { b.focus(); b.select(); }
        $("#saveMsg").textContent = "Status copied. Paste it into Computer."; $("#saveMsg").className = "save-state ok"; return;
      }
      if (a === "verdict") {
        const v = t.dataset.v, k = t.dataset.key, m = state.catalog.new_marks[k], next = m?.verdict === v ? null : v;
        await updPost("/api/forge/verdict", { key: k, verdict: next });
        if (!m && state.catalog.data_marks?.[k]) { await load(); renderPage(); renderHudData(); return; }   // "It's new": moves it up to NEW!
        if (next === "not_new") delete state.catalog.new_marks[k]; else if (m) m.verdict = next;
        renderPage(); renderHudData(); return;
      }
      if (a === "prefill") { updFight = { name: t.dataset.name, base: /abyss/i.test(t.dataset.name) ? "abyss" : "boss", note: "named in the official patch notes" }; renderPage(); $("#fightForm")?.scrollIntoView({ behavior: "smooth" }); return; }
      if (a === "editfight") { const s = state.catalog.custom_scenarios[t.dataset.key], o = state.catalog.typed.scenarios[t.dataset.key] || {};
        updFight = { key: t.dataset.key, name: o.name || s.label, base: s.base, buff_text: o.buff_text || "", weakspot_rate: o.weakspot_rate != null ? Math.round(o.weakspot_rate * 100) : null, enemies_hit: o.enemies_hit, note: o.note };
        renderPage(); $("#fightForm")?.scrollIntoView({ behavior: "smooth" }); return; }
      if (a === "clearfight") { updFight = {}; renderPage(); return; }
      if (a === "savefight") {
        const name = val("name"); if (!name) { alert("Give the fight a name."); return; }
        const ws = val("weakspot_rate"), en = val("enemies_hit");
        const entry = { name, base: val("base"), buff_text: val("buff_text"), note: val("note"),
          weakspot_rate: ws !== "" ? Math.max(0, Math.min(100, +ws)) / 100 : null, enemies_hit: en !== "" ? Math.max(1, +en) : null };
        if (updFight.key) await updPost("/api/forge/typed", { kind: "scenarios", name: updFight.key, entry: null });
        const j = await updPost("/api/forge/typed", { kind: "scenarios", name, entry }); updFight = {}; takeState(j); renderPage(); return;
      }
      if (a === "usefight") { prof().scenario = t.dataset.key; queueSave(); return; }
      if (a === "delfight") {
        if (!confirm("Delete this custom fight?")) return;
        if ((prof().scenario || "").split("@")[0] === t.dataset.key) { prof().scenario = "boss"; }
        const j = await updPost("/api/forge/typed", { kind: "scenarios", name: t.dataset.key, entry: null }); takeState(j); queueSave(); renderPage(); return;
      }
      if (a === "savetyped") {
        const name = val("name"), text = val("text"); if (!name) { alert("Give it a name."); return; }
        const ks = val("kindsel"), isDev = ks === "deviation" || form.dataset.kind === "deviations";
        const slots = (ks && ks !== "deviation" ? ks : val("slots") || "food").split(",");
        const j = await updPost("/api/forge/typed", { kind: isDev ? "deviations" : "consumables", name, entry: isDev ? { text } : { text, slots } });
        takeState(j); renderPage(); return;
      }
      if (a === "deltyped") { const j = await updPost("/api/forge/typed", { kind: t.dataset.kind, name: t.dataset.name, entry: null }); takeState(j); renderPage(); return; }
    } catch (err) { alert(`That didn't work: ${err.message}`); }
  });


  // ---------- app updates (GitHub Releases; nothing installs until "Update now") ----------
  let appUpd = null, appUpdTimer = null;
  async function loadAppUpd(refresh) {
    try {
      const r = await fetch(`/api/app-update${refresh ? "?refresh=1" : ""}`, { cache: "no-store" });
      if (r.ok) appUpd = await r.json();
    } catch (e) { /* offline: just no banner */ }
    renderAppUpd();
    if (page === "updates") renderPage();
    const st = appUpd?.job?.stage;
    clearTimeout(appUpdTimer);
    if (["downloading", "checking", "unpacking"].includes(st)) appUpdTimer = setTimeout(() => loadAppUpd(false), 800);
    else if (st === "restarting") waitForNewVersion(appUpd.job.target);
    else if (!refresh) appUpdTimer = setTimeout(() => loadAppUpd(false), 6 * 3600 * 1000);
  }
  async function waitForNewVersion(target) {
    for (let i = 0; i < 180; i++) {
      await new Promise((ok) => setTimeout(ok, 1000));
      try {
        const r = await fetch("/api/health", { cache: "no-store" });
        const h = await r.json();
        if (h.version && h.version === target) { location.reload(); return; }
      } catch (e) { /* server is restarting */ }
    }
    if (appUpd) { appUpd.job = { stage: "error", error: "The new version didn't answer after 3 minutes. Open Deviant Forge from the Desktop shortcut." }; renderAppUpd(); }
  }
  function appUpdNotes(u) {
    return u.notes ? `<details class="au-notes"><summary>What's new</summary><pre>${esc(u.notes)}</pre></details>` : `<a href="${esc(u.release_url)}" target="_blank" rel="noopener">What's new</a>`;
  }
  function appUpdJob(j) {
    if (!j || j.stage === "idle") return "";
    if (j.stage === "error") return `<p class="au-err">Update didn't finish: ${esc(j.error || "unknown problem")}</p>`;
    if (j.stage === "ready_manual") return `<p class="au-msg">${esc(j.msg)}</p><code class="au-cmd">${esc(j.command)}</code>`;
    return `<div class="au-prog" role="status"><div class="upd-bar"><span style="width:${Math.max(3, j.pct || 0)}%"></span></div><p>${esc(j.msg || "")}</p></div>`;
  }
  function renderAppUpd() {
    let el = $("#appUpd");
    if (!el) { const m = $(".main .wrap"); if (!m) return; m.insertAdjacentHTML("afterbegin", `<section id="appUpd" class="app-upd" aria-live="polite" hidden></section>`); el = $("#appUpd"); }
    const u = appUpd, j = u?.job || {};
    const busy = ["downloading", "checking", "unpacking", "restarting"].includes(j.stage);
    const later = u && sessionStorage.getItem("df-upd-later") === u.latest;
    const show = u && ((u.available && !later) || busy || j.stage === "error" || j.stage === "ready_manual");
    el.hidden = !show;
    if (!show) return;
    el.innerHTML = `<div class="au-row"><div class="au-t"><b>Deviant Forge ${esc(u.latest || "")} is ready</b><span>You have ${esc(u.current)}. Your saved gear stays as it is.</span></div>
      <div class="au-act">${appUpdNotes(u)}
        <button class="btn primary small" type="button" data-appupd="install" ${busy ? "disabled" : ""}>${u.platform === "linux" ? "Download update" : "Update now"}</button>
        ${busy ? "" : `<button class="btn small" type="button" data-appupd="later">Later</button>`}</div></div>${appUpdJob(j)}`;
  }
  function appUpdCell() {
    const u = appUpd;
    if (!u) return `<small>checking…</small>`;
    if (!u.enabled) return `<small>update check is off</small>`;
    const line = u.available ? `<b class="new-c">${esc(u.latest)} is ready</b>` : u.latest ? `newest` : (u.error ? `couldn't reach GitHub` : `no release yet`);
    return `<small>${line} · <button class="linkish" type="button" data-appupd="check">check now</button>${u.checked_at ? ` · checked ${esc(when(u.checked_at))}` : ""}</small>`;
  }
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-appupd]"); if (!t) return;
    const a = t.dataset.appupd;
    if (a === "later") { sessionStorage.setItem("df-upd-later", appUpd?.latest || ""); renderAppUpd(); return; }
    if (a === "check") { t.disabled = true; await loadAppUpd(true); return; }
    if (a === "install") {
      t.disabled = true;
      try {
        const r = await fetch("/api/app-update/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        appUpd = await r.json();
      } catch (err) { appUpd = { ...(appUpd || {}), job: { stage: "error", error: err.message } }; }
      renderAppUpd(); loadAppUpd(false);
    }
  });

  window.addEventListener("hashchange", () => { route(); window.scrollTo(0, 0); });
  route();
  load().then(route);
  loadAppUpd(false);
})();
