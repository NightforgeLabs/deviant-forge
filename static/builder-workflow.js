/* Catalog-backed readout and saved-version comparison for the visual editor. */
let builderAnalysis = null, builderAnalysisKey = "", builderAnalysisRequest = 0;
let builderDirty = false, builderComparison = null, builderCompareTarget = null, builderCompareRequest = 0;
let builderHoverTimer = null, builderDetailPinned = false, builderEstimateValues = {};
let builderContext = {scenario:"",hp:"",stance:"",elevation:"",crit:"",weak:"",incoming:""};
const baseBuilderPage = builderPage;
const baseEnsureBuilder = ensureBuilder;
const basePickerHtml = pickerHtml;
const baseOpenPicker = openPicker;
const basePickerTab = pickerTab;
const baseSelectCatalogItem = selectCatalogItem;
const basePreviewCatalogItem = previewCatalogItem;
const baseChangeBuilderOption = changeBuilderOption;
const baseChangeSlotSetting = changeSlotSetting;
const baseRemovePlannedMod = removePlannedMod;
const baseSetBuilderFilter = setBuilderFilter;

ensureBuilder = async function() {
  await baseEnsureBuilder();
  if (!picker && !planned.id && !Object.keys(planned.slots).length)
    picker = {slot:"primary",mode:"gear",tab:"primary"};
};
pickerHtml = function() {
  const html = basePickerHtml();
  const coverage = esc(JSON.stringify(builderData.artwork_coverage));
  return html.replace(" · " + coverage + "</p>",
    " · exact matched artwork where available</p><details class='catalog-coverage'><summary>Artwork coverage</summary><pre>" +
    esc(JSON.stringify(builderData.artwork_coverage,null,2)) + "</pre></details>");
};

function builderSource(source) {
  if (!source) return "Source not cataloged";
  if (/^https:\/\//.test(source)) return "<a href='" + esc(source) + "' target='_blank' rel='noopener'>Source ↗</a>";
  return "<code>" + esc(source) + "</code>";
}
function builderAssumptions() {
  const conditions = [builderContext.stance,builderContext.elevation].filter(Boolean).join("; ");
  return {scenario:builderContext.scenario || null,conditions, hp_fraction:builderContext.hp === "" ? null : Number(builderContext.hp),
    crit_rate:builderContext.crit === "" ? null : Number(builderContext.crit),
    weakspot_rate:builderContext.weak === "" ? null : Number(builderContext.weak),
    incoming_monster_hit:builderContext.incoming === "" ? null : Number(builderContext.incoming)};
}
function builderContextHtml() {
  return "<div class='builder-context'><b>Encounter context <small>optional · unknown stays unknown</small></b>" +
    "<label>Scenario <select id='ctxScenario' onchange='updateBuilderContext()'>" +
    [["","Unknown"],["PvE","PvE non-RaidZone"],["PvP","PvP"],["RaidZone","RaidZone"]].map(pair =>
      "<option value='" + pair[0] + "'" + (builderContext.scenario === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>").join("") + "</select></label>" +
    "<label>Stance <select id='ctxStance' onchange='updateBuilderContext()'>" +
    [["","Unknown"],["grounded","Grounded"],["aerial","Aerial"]].map(pair =>
      "<option value='" + pair[0] + "'" + (builderContext.stance === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>").join("") + "</select></label>" +
    "<label>Elevation <select id='ctxElevation' onchange='updateBuilderContext()'>" +
    [["","Unknown"],["same elevation","Same elevation"],["enemy below player 5m","Enemy 5m below"]].map(pair =>
      "<option value='" + pair[0] + "'" + (builderContext.elevation === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>").join("") + "</select></label>" +
    "<label>HP fraction <input id='ctxHp' type='number' min='0' max='1' step='any' placeholder='unknown' value='" + esc(builderContext.hp) + "' onchange='updateBuilderContext()'></label>" +
    "<label>Crit share <input id='ctxCrit' type='number' min='0' max='1' step='any' placeholder='unknown' value='" + esc(builderContext.crit) + "' onchange='updateBuilderContext()'></label>" +
    "<label>Weak-spot share <input id='ctxWeak' type='number' min='0' max='1' step='any' placeholder='unknown' value='" + esc(builderContext.weak) + "' onchange='updateBuilderContext()'></label>" +
    "<label>First monster hit <input id='ctxIncoming' type='number' min='0' step='any' placeholder='unknown' title='Raw PvE monster hit before this mod and without other mitigation' value='" + esc(builderContext.incoming) + "' onchange='updateBuilderContext()'></label></div>";
}
function updateBuilderContext() {
  const next = {scenario:document.querySelector("#ctxScenario")?.value || "",
    hp:document.querySelector("#ctxHp")?.value || "",
    stance:document.querySelector("#ctxStance")?.value || "",
    elevation:document.querySelector("#ctxElevation")?.value || "",
    crit:document.querySelector("#ctxCrit")?.value || "",
    weak:document.querySelector("#ctxWeak")?.value || "",
    incoming:document.querySelector("#ctxIncoming")?.value || ""};
  for (const key of ["hp","crit","weak"]) {
    if (next[key] !== "" && (!Number.isFinite(Number(next[key])) || Number(next[key]) < 0 || Number(next[key]) > 1)) {
      fail(Error("Enter a " + key + " value from 0 to 1, or leave it blank."));
      return;
    }
  }
  if (next.incoming !== "" && (!Number.isFinite(Number(next.incoming)) || Number(next.incoming) < 0)) {
    fail(Error("First monster hit must be zero or greater, or left blank.")); return;
  }
  builderContext = next; builderAnalysis = null; builderAnalysisKey = "";
  const area = document.querySelector("#builderCompare");
  const comparisonWasPending = area?.innerHTML.includes("Comparing saved builds…");
  ++builderCompareRequest;
  if (builderComparison || comparisonWasPending) {
    builderComparison = null; builderCompareTarget = null;
    if (area) area.innerHTML = "<p class='note'>Encounter changed. Compare the saved versions again to use this context.</p>";
  }
  const summaryArea = document.querySelector("#builderSummary");
  if (summaryArea) summaryArea.innerHTML = builderAnalysisHtml();
  queueBuilderAnalysis();
}
function listedAttribute(attribute) {
  const amount = attribute.value_percent == null ? "value unknown" :
    (attribute.direction === "reduction" ? "−" : "+") + esc(attribute.value_percent) + "%";
  const extra = attribute.conditional_bonus_percent == null ? "" :
    " · extra +" + esc(attribute.conditional_bonus_percent) + "% when " + esc(attribute.condition || "condition unknown");
  return "<b>" + esc(attribute.name) + " " + amount + "</b>" + extra +
    "<small>" + esc(attribute.component || "component unknown") + " · " +
    esc(attribute.activation_state || "activation unknown") + "</small>";
}
function builderAnalysisHtml() {
  if (!builderAnalysis) return "<div class='card build-summary'><h3>Your build at a glance</h3><p class='muted'>Resolving selected catalog entries…</p></div>";
  const analysis = builderAnalysis;
  const attributes = analysis.slots.flatMap(part => part.mod ?
    part.mod.attributes.map(attribute => ({slot:part.label, item:part.mod.name, attribute})) : []);
  const shown = attributes.filter(row => /outgoing|direct|critical|weak|firing cycle|proc|status/i.test(row.attribute.component || "")).slice(0, 5);
  const sets = analysis.sets.map(group => "<div class='set-line'><b>" + esc(group.name) + " " + group.count +
    " piece" + (group.count === 1 ? "" : "s") + "</b>" +
    group.thresholds.map(t => "<small>" + t.pieces + " pieces · " + esc(t.state) + " · " +
      esc(t.description) + "</small>").join("") + "</div>").join("");
  const allAttributes = attributes.map(row => "<li><span>" + esc(row.slot) + " · " + esc(row.item) +
    "</span>" + listedAttribute(row.attribute) + "<details><summary>Evidence</summary>" +
    builderSource(row.attribute.source) + "</details></li>").join("");
  const effects = analysis.slots.flatMap(part => [part.gear,part.mod].filter(Boolean).filter(item => item.effect).map(item =>
    "<li><b>" + esc(item.name) + "</b>: " + esc(item.effect) +
    "<small>" + esc(item.effect_state.base) + "; " + esc(item.effect_state.conditional) + "</small>" +
    (item.effect_activation.length ? "<small>Requires " + esc(item.effect_activation.join("; ")) + "</small>" : "") +
    "<small>Full damage calculation unresolved.</small><details><summary>Evidence</summary>" +
    builderSource(item.effect_source) + "</details></li>")).join("");
  return "<div class='card build-summary'><div class='summary-heading'><div><div class='kicker'>SELECTED SETUP</div>" +
    "<h3>Build readout</h3></div><span class='badge partial'>Catalog plan · ownership separate</span></div>" +
    "<p class='muted small'>" + esc(analysis.compatibility) + "</p>" +
    "<p class='next-step'><b>Next useful move:</b> " + esc(analysis.next_step.text) + "</p>" +
    (analysis.next_step.source ? "<details><summary>Suggestion source</summary>" + builderSource(analysis.next_step.source) + "</details>" : "") +
    (sets ? "<div class='summary-block'><b>Armor sets</b>" + sets + "</div>" :
      "<p class='muted small'>No armor set pieces selected yet.</p>") +
    (analysis.synergies.length ? "<div class='summary-block'><b>Possible synergies</b><ul>" +
      analysis.synergies.map(s => "<li>" + esc(s.text) + "</li>").join("") + "</ul></div>" :
      "<p class='muted small'>No shared effect family is established between the selected primary weapon and gear.</p>") +
    (shown.length ? "<div class='summary-block'><b>Known listed attributes</b><ul>" +
      shown.map(row => "<li>" + esc(row.slot) + " · " + listedAttribute(row.attribute) + "</li>").join("") +
      "</ul></div>" : attributes.length ?
      "<p class='muted small'>Known attributes affect other components; open all attributes below.</p>" :
      "<p class='muted small'>No complete numeric mod profile selected yet.</p>") +
    "<details><summary>All selected effects and attributes (" + attributes.length + " numeric attributes)</summary>" +
    (effects ? "<h4>Main effects</h4><ul>" + effects + "</ul>" : "") +
    (allAttributes ? "<h4>Known mod attributes</h4><ul>" + allAttributes + "</ul>" : "") +
    "<p class='muted small'>Unknown catalog values stay unresolved. Tier, blueprint stars, calibration rolls, and legacy enhancement are saved but their resulting stats are not calculated.</p></details>" +
    "<details><summary>Calculation limits (" + analysis.unresolved.length + ")</summary><ul>" +
    analysis.unresolved.map(line => "<li>" + esc(line) + "</li>").join("") +
    "</ul><p>" + esc(analysis.scope) + "</p></details></div>";
}
function queueBuilderAnalysis() {
  if (!builderData || page !== "builder") return;
  const key = JSON.stringify([planned.slots,builderAssumptions()]);
  if (builderAnalysisKey === key && builderAnalysis) return;
  builderAnalysisKey = key;
  const request = ++builderAnalysisRequest;
  api("planned-analysis", {slots:planned.slots,assumptions:builderAssumptions()}).then(result => {
    if (request !== builderAnalysisRequest || key !== JSON.stringify([planned.slots,builderAssumptions()])) return;
    builderAnalysis = result;
    const area = document.querySelector("#builderSummary");
    if (area) area.innerHTML = builderAnalysisHtml();
    const stats = document.querySelector("#characterCombatStats");
    if (stats && typeof characterCombatStatsHtml === "function") stats.outerHTML = characterCombatStatsHtml();
  }).catch(error => {
    if (request === builderAnalysisRequest) {
      const area = document.querySelector("#builderSummary");
      if (area) area.innerHTML = "<div class='note warn'>" + esc(error.message) + "</div>";
    }
  });
}
builderPage = function() {
  const oldScroll = document.querySelector(".builder-layout > section:first-child")?.scrollTop || 0;
  const original = baseBuilderPage();
  setTimeout(() => {
    const rail = document.querySelector(".builder-layout > section:first-child");
    if (rail) rail.scrollTop = oldScroll;
    queueBuilderAnalysis();
  }, 0);
  return original.replace('oninput="planned.name=this.value"', 'oninput="planned.name=this.value;builderDirty=true"')
    .replace('<div class="builder-layout">',
      (builderDirty ? "<p class='unsaved-note'>Unsaved changes · save before comparing versions.</p>" : "") +
      '<div class="builder-layout">')
    .replace('<div id="builderCompare"></div>',
      "<details class='builder-secondary' id='builderSecondary' " + (builderComparison ? "open" : "") + "><summary>Build advice, encounter, and comparison</summary>" +
      "<div id='builderSummary'>" + builderAnalysisHtml() + "</div><details class='encounter-panel'><summary>Encounter settings</summary>" + builderContextHtml() + "</details>" +
      "<div id='builderCompare'>" + (builderComparison ? builderComparisonHtml(builderComparison) : "") + "</div></details>");
};

entryCard = function(e) {
  const current = planned.slots[picker?.slot] || {};
  const selected = (picker?.mode === "mod" ? current.mod_id : current.catalog_id) === e.id;
  const elsewhere = Object.entries(planned.slots).some(([slot,s]) =>
    slot !== picker?.slot && (s.catalog_id === e.id || s.mod_id === e.id));
  const level = selected ? current.mod_level : e.available_level;
  const badge = e.kind === "mod" ? (level ? "Lv " + esc(level) : "Lv ?") :
    (selected && current.tier ? "Tier " + ["","I","II","III","IV","V"][current.tier] : "Tier ?");
  const art = e.artwork ? "<img src='" + esc(e.artwork) + "' alt='" + esc(e.name) + " artwork' loading='lazy'>" :
    "<span class='no-art'>Artwork unavailable</span>";
  return "<button class='item-icon " + esc(e.rarity || "unknown") +
    (e.ownership === "locked" ? " locked" : "") + (selected ? " selected" : "") +
    "' data-id='" + esc(e.id) + "' onclick='selectCatalogItem(this.dataset.id)' " +
    "title='" + esc(e.name) + " · " +
    esc(e.effect || "Effect not cataloged") + "'>" + art +
    "<span class='level-chip'>" + badge + "</span>" +
    "<span class='ownership-chip'>" + (e.ownership === "locked" ? "🔒" : e.ownership === "unlocked" ? "✓" : "?") + "</span>" +
    "<span class='icon-name'>" + esc(e.base_name) + "</span><span class='icon-variant'>" +
    esc(e.variant || e.set_name || "Base") + " · " + esc(e.rarity || "rarity unknown") + "</span>" +
    (selected ? "<span class='in-build-chip'>Selected here</span>" : elsewhere ? "<span class='in-build-chip elsewhere'>Elsewhere in build</span>" : "") +
    "</button>";
};
pickerResults = function(shown,groups) {
  if (!shown.length) return empty("No matching items","Try All items, another family, or a different search.");
  const screenshotOrder = picker?.mode === "mod" && picker?.slot === "helmet" ?
    ["Precise Strike","Deviation Expert"] : [];
  return Object.entries(groups).sort(([left],[right]) => {
    const a = screenshotOrder.indexOf(left), b = screenshotOrder.indexOf(right);
    return (a >= 0 || b >= 0) ? (a < 0 ? 999 : a) - (b < 0 ? 999 : b) : left.localeCompare(right);
  }).map(([family,entries]) => "<section class='mod-family'><h3>" + esc(family) +
    "</h3><div class='icon-grid'>" + entries.sort((a,b) =>
      (a.base_name || a.name).localeCompare(b.base_name || b.name) ||
      (a.variant || "").localeCompare(b.variant || "")).map(entryCard).join("") +
    "</div></section>").join("");
};

detailHtml = function(detail) {
  const e=catalogEntry(detail.id),r=detail.result;
  if (!e)return "";
  const levelNote=e.kind==="mod" ? "<p class='small muted'>Verified numbers for this variant: " +
    (e.observed_numeric_levels?.length ? "Lv. " + e.observed_numeric_levels.join(", ") : "none yet") +
    ". Other level values or availability may be unresolved.</p>" : "";
  return "<div class='card item-detail'><button class='detail-close' aria-label='Close item details' onclick='closeBuilderDetail()'>×</button>" +
    "<div class='detail-title'>" + entryArt(e) + "<div><h3>" + esc(e.base_name) + "</h3><p>" +
    esc(e.variant||e.set_name||e.family||"") + " · " + esc(e.rarity||"rarity unknown") + "</p><small>" + esc(ownedLabel(e)) + "</small></div></div>" +
    "<p>" + esc(r?.primary_effect||e.effect||"Effect details unavailable") + "</p>" +
    "<p class='small muted'>Edit tier, stars, calibration, and attached mod level on the equipped setup card.</p>" +
    "<div class='detail-ownership'><label>Ownership<select id='builderOwnership' onchange=\"markBuilderOwnership('" + esc(e.id) + "',this.value)\">" +
    [["unknown","Unknown"],["unlocked","I own / unlocked this"],["locked","Confirmed locked"]].map(pair =>
      "<option value='"+pair[0]+"' "+(e.ownership===pair[0]?"selected":"")+">"+pair[1]+"</option>").join("") + "</select></label>" +
    (e.kind==="mod"&&e.ownership==="unlocked" ? "<label>Available mod level<input id='availableLevel' type='number' min='1' max='17' value='" + esc(e.available_level||"") + "' onchange=\"markBuilderOwnership('" + esc(e.id) + "','unlocked')\"></label>" : "") + "</div>" +
    (r?.known_attributes?.length ? "<details><summary>Known attributes at this level ("+r.known_attributes.length+")</summary><ul>" + r.known_attributes.map(a=>
      "<li>"+esc(a.name)+" "+(a.value_percent==null?"unknown":(a.direction==="reduction"?"−":"+")+esc(a.value_percent)+"%")+
      (a.conditional_bonus_percent!=null?" · extra +"+esc(a.conditional_bonus_percent)+"% when "+esc(a.condition):"")+"</li>").join("")+"</ul></details>" :
      "<p class='muted small'>Exact attributes at this level are not cataloged yet.</p>") + levelNote +
    "<details><summary>Sources and coverage</summary><p class='small'>" +
    (e.artwork_source?"<a href='"+esc(e.artwork_source)+"' target='_blank' rel='noopener'>Artwork source ↗</a>":"Artwork source unavailable") +
    ". Numeric coverage: "+esc(r?.attribute_coverage||"unknown")+". "+esc((r?.unknowns||[]).join("; "))+"</p></details></div>";
};
function closeBuilderDetail() {
  builderDetail = null;
  builderDetailPinned = false;
  const area = document.querySelector("#builderDetail");
  if (area) area.innerHTML = "";
}
previewCatalogItem = function(id) {
  // The grid remains stable while the pointer moves; selecting a card opens details below it.
};
openPicker = function(slot, mode) {
  clearTimeout(builderHoverTimer);
  builderDetailPinned = false;
  baseOpenPicker(slot, mode);
};
pickerTab = function(tab) {
  const oldMode = picker?.mode;
  basePickerTab(tab);
  if (oldMode === "mod" && picker?.mode === "gear")
    builderSwap = "Choose " + picker.slot + " equipment before attaching its compatible mod.";
};
function builderCompatible(entry, slot, mode) {
  if (mode === "mod") return entry.kind === "mod" && entry.slot === builderMods[slot];
  if (slot in builderArmor) return entry.kind === "armor" && entry.slot === builderArmor[slot];
  return entry.kind === "weapon" && (slot === "melee" ? entry.family === "melee" : entry.family !== "melee");
}
selectCatalogItem = async function(id, proposedLevel) {
  const entry = catalogEntry(id), slot = picker?.slot, mode = picker?.mode;
  if (!entry || !slot || !builderCompatible(entry,slot,mode)) {
    fail(Error("That item is not compatible with this slot."));
    return;
  }
  const before = structuredClone(planned.slots[slot] || {});
  const attached = before.mod_id && catalogEntry(before.mod_id);
  if (mode === "gear" && attached && attached.slot !== builderMods[slot]) {
    fail(Error("The attached mod conflicts with this gear slot. Remove it explicitly before replacing gear."));
    return;
  }
  builderDirty = true;
  builderComparison = null;
  builderAnalysis = null;
  builderDetailPinned = true;
  clearTimeout(builderHoverTimer);
  await baseSelectCatalogItem(id, proposedLevel);
  if (mode === "gear" && before.catalog_id && before.catalog_id !== id && attached) {
    builderSwap = "Replaced " + (catalogEntry(before.catalog_id)?.name || "gear") + " with " + entry.name +
      ". Attached " + attached.name + " was kept because its mod slot is still compatible. Damage effect needs comparison context.";
    const area = document.querySelector(".picker-head .note");
    if (area) area.textContent = builderSwap;
  }
  queueBuilderAnalysis();
};
changeSlotSetting = function(slot,key,value) {
  const before=JSON.stringify(planned.slots[slot]||{});
  const wasDirty=builderDirty;
  const selected=planned.slots[slot];
  if (!selected?.catalog_id)return;
  if (key==='mod_level'&&!selected.mod_id)return;
  if (key==='calibration_blueprint'||key==='calibration_bonus') {
    if (String(selected[key]||'')===String(value).trim())return;
  } else if (['legacy_enhancement','tier','stars'].includes(key)&&value==='') {
    if (selected[key]==null)return;
  } else if (selected[key]!=null && Number(selected[key])===Number(value))return;
  builderDirty=true;builderComparison=null;builderAnalysis=null;
  baseChangeSlotSetting(slot,key,value);
  if (JSON.stringify(planned.slots[slot]||{})===before)builderDirty=wasDirty;
  else queueBuilderAnalysis();
};
changeBuilderOption=function(key,value){if(picker?.slot)changeSlotSetting(picker.slot,key,value)};
removePlanned = function(slot) {
  const attached = catalogEntry(planned.slots[slot]?.mod_id);
  delete planned.slots[slot];
  builderSwap = attached ? attached.name + " was detached when its gear was removed." : "";
  builderDirty = true; builderComparison = null; builderAnalysis = null;
  render();
  if (attached) notice(attached.name + " detached with its gear. Choose new gear to attach a compatible mod.");
};
removePlannedMod = function(slot) {
  baseRemovePlannedMod(slot);
  builderDirty = true; builderComparison = null; builderAnalysis = null;
  queueBuilderAnalysis();
};
newPlannedBuild = function() {
  planned = {id:null,name:"New planned build",notes:"",slots:{}};
  picker = {slot:"primary",mode:"gear",tab:"primary"};
  builderSwap = ""; builderAnalysis = null; builderDirty = false; builderComparison = null;
  render();
};
openPlannedBuild = function(id) {
  const saved = builderData.planned_builds.find(build => build.id === id);
  if (!saved) return;
  planned = {id:saved.id,name:saved.name,notes:saved.notes || "",slots:structuredClone(saved.slots)};
  picker = {slot:"primary",mode:"gear",tab:"primary"};
  builderSwap = ""; builderAnalysis = null; builderDirty = false; builderComparison = null;
  render(); notice("Planned build reopened");
};
duplicatePlannedBuild = function() {
  planned = {...structuredClone(planned),id:null,name:(document.querySelector("#plannedName")?.value || planned.name) + " copy"};
  builderDirty = true; builderComparison = null;
  render(); notice("Copy ready to save. Ownership did not change.");
};
savePlannedBuild = async function() {
  try {
    const name = (document.querySelector("#plannedName")?.value || planned.name).trim();
    const result = await api("planned-build", {id:planned.id,name,notes:planned.notes,slots:planned.slots});
    planned.id = result.id; planned.name = name; builderDirty = false;
    builderData = await (await fetch("/api/builder-catalog")).json();
    render(); notice("Planned build saved; ownership unchanged");
  } catch (error) { fail(error); }
};
setBuilderFilter = function(value) {
  baseSetBuilderFilter(value);
  queueBuilderAnalysis();
};

function buildPartLabel(part) {
  if (!part) return "Empty";
  const gear = part.gear ? part.gear.name : "Empty gear";
  const mod = part.mod ? " + " + part.mod.name + " Lv " + (part.mod.level ?? "?") : "";
  const details=[];
  if (part.settings?.tier!=null)details.push("Tier "+part.settings.tier);
  if (part.settings?.stars)details.push("★ "+part.settings.stars);
  if (part.settings?.calibration_blueprint)details.push("calibration blueprint "+part.settings.calibration_blueprint);
  if (part.settings?.calibration_bonus)details.push(part.settings.calibration_bonus);
  if (part.settings?.legacy_enhancement!=null)details.push("legacy +"+part.settings.legacy_enhancement);
  const settings=details.length?" · "+details.join(" · "):"";
  return gear + mod + settings;
}
function modChangesHtml(record) {
  const result = record.result;
  const rows = (result.attribute_changes || []).map(change => {
    const before = change.from?.effective_value_percent;
    const after = change.to?.effective_value_percent;
    const delta = change.numeric_delta_percent == null ? "exact delta unresolved" :
      (change.numeric_delta_percent >= 0 ? "+" : "") + change.numeric_delta_percent + " percentage points of the listed modifier";
    return "<li><b>" + esc(change.name) + "</b>: " +
      esc(before == null ? "unknown/absent" : before + "%") + " → " +
      esc(after == null ? "unknown/absent" : after + "%") + " · " + esc(delta) +
      "<small>" + esc(change.meaning || "") + " · " + esc(change.activation || "activation unresolved") + "</small></li>";
  }).join("");
  return "<div class='mod-diff'><h4>" + esc(record.slot) + " mod effects</h4><p><b>Before:</b> " +
    esc(result.left.main_effect || "not cataloged") + "</p><p><b>After:</b> " +
    esc(result.right.main_effect || "not cataloged") + "</p>" +
    (result.left.main_effect_activation.length || result.right.main_effect_activation.length ?
      "<p class='small'>Activation: " + esc(result.left.main_effect_activation.join("; ") || "not resolved") +
      " → " + esc(result.right.main_effect_activation.join("; ") || "not resolved") + "</p>" : "") +
    (rows ? "<ul>" + rows + "</ul>" : "<p class='muted small'>No verified numeric attribute difference.</p>") +
    (result.selected_metric ? "<p class='note'>Supported " + esc(result.selected_metric.name) + ": " +
      esc(result.selected_metric.left.damage_taken) + " vs " + esc(result.selected_metric.right.damage_taken) +
      " damage taken; " + esc(result.selected_metric.winner) + " for this metric only.</p>" : "") +
    "<details><summary>Why this is not a full DPS ranking</summary><ul>" +
    result.blockers.map(line => "<li>" + esc(line) + "</li>").join("") +
    "</ul></details></div>";
}
function canEstimatePair(result) {
  return result.changes.length > 0 && !!result.left.weapon.name &&
    result.left.weapon.name === result.right.weapon.name;
}
function estimateInput(id, label, extra) {
  return "<label>" + label + "<input id='estimate_" + id + "' " + (extra || "") +
    " value='" + esc(builderEstimateValues[id] ?? "") + "'></label>";
}
function estimateChoice(id,label) {
  return "<label>" + label + " <select id='estimate_" + id + "'>" +
    [["","Choose"],["yes","Yes"],["no","No"]].map(pair =>
      "<option value='" + pair[0] + "'" + (builderEstimateValues[id] === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>").join("") +
    "</select></label>";
}
function estimateControls(result) {
  const profile = result.left.weapon.reference_profile;
  if (!profile) return "<p class='note'>A sourced weapon reference profile is not yet available for " +
    esc(result.left.weapon.name) + ". The known effect changes remain visible; no outgoing estimate is claimed.</p>";
  return "<details class='estimate-controls'><summary>Estimate this saved-build change</summary>" +
    "<p class='small muted'>" + esc(profile.name) + " client-reference profile: " +
    esc(profile.damage_per_projectile) + " damage, " + esc(profile.rpm) + " RPM, " +
    esc(profile.magazine) + " rounds, " + esc(profile.reload_seconds) +
    "s reload. Its in-game tier and calibration are unlabeled. The inputs below describe the target and encounter, not your owned weapon.</p>" +
    "<button class='secondary' onclick='fillReferenceScenario()'>Fill illustrative 25 m scenario</button>" +
    "<div class='estimate-grid'><label>Scenario <select id='estimate_scenario'>" +
    [["","Choose"],["PvE","PvE non-RaidZone"],["PvP","PvP"],["RaidZone","RaidZone"]].map(pair =>
      "<option value='" + pair[0] + "'" + (builderEstimateValues.scenario === pair[0] ? " selected" : "") +
      ">" + pair[1] + "</option>").join("") + "</select></label>" +
    estimateInput("distance","Target distance (m)","type='number' min='0' step='any'") +
    estimateInput("critShare","Critical hit share (0–1); source base " + esc(profile.crit_rate_percent) + "%","type='number' min='0' max='1' step='any'") +
    estimateInput("weakShare","Weak-spot hit share (0–1)","type='number' min='0' max='1' step='any'") +
    estimateInput("duration","Duration seconds","type='number' min='0' step='any'") +
    estimateInput("nearbyKills","Kills within 10 m","type='number' min='0' step='1'") +
    estimateInput("elementalEvents","Elemental events in previous magazine","type='number' min='0' step='1'") +
    "</div><div class='estimate-checks'>" +
    estimateChoice("aerial","Aerial hits") + estimateChoice("sameElevation","Same elevation") +
    estimateChoice("below","Target lower within 5 m") +
    estimateChoice("hp","HP consumed") + estimateChoice("stamina","Stamina spent") +
    "</div><button class='primary' onclick='runPlannedEstimate()'>Calculate conditional primary-fire estimate</button>" +
    "<p class='small muted'>Source and calculation details appear with the result. Unknown mechanics block the scoped winner.</p></details>";
}
function fillReferenceScenario() {
  builderEstimateValues = {scenario:"PvE",distance:25,critShare:.02,weakShare:.8,duration:40,
    nearbyKills:0,elementalEvents:0,aerial:"no",sameElevation:"yes",below:"no",hp:"no",stamina:"no"};
  const area = document.querySelector("#builderCompare");
  if (area && builderComparison) area.innerHTML = builderComparisonHtml(builderComparison);
}
function scopedOutgoingHtml(result, builds) {
  if (!result) return "";
  const modifiers = values => Object.entries(values || {}).filter(pair => pair[1] !== 0)
    .map(pair => ({all:"All DMG",weapon:"Weapon DMG",weakspot:"Weak-spot DMG",
      crit:"Crit DMG",magazine:"Magazine capacity"}[pair[0]] || pair[0]) + " +" + pair[1] + "%").join(", ") || "none";
  const active = side => (result.trace?.[side] || []).filter(rule =>
    rule.rule_id !== "field-guide-attribute" && rule.rule_id !== "main-effect-structured-corroboration" &&
    (rule.value_percent > 0 || /inactive/.test(rule.activation || ""))).map(rule =>
    rule.item + ": " + rule.component.replaceAll("_"," ") + " — " + rule.activation).join("; ");
  const row = result.rows?.find(item => item.base_crit_weak_model === "additive" &&
    item.stacking_model === "additive" && item.magazine_rounding === "floor" &&
    item.distant_extra_bound === "lower");
  const label = result.winner_established ?
    "Conditional primary-fire recommendation: " + (result.winner === "left" ? builds.left.name :
      result.winner === "right" ? builds.right.name : "tie") : "Primary-fire winner unresolved";
  return "<div class='card scoped-outgoing'><h4>" + esc(label) + "</h4>" +
    (row ? "<p>Additive / floor-magazine sensitivity row: burst " + esc(row.left.burst_damage) +
      " vs " + esc(row.right.burst_damage) + "; " + esc(result.duration_seconds) +
      "s sustained " + esc(row.left.sustained_damage) + " vs " + esc(row.right.sustained_damage) +
      ". Both sides include " + esc(row.left.shots) + " and " + esc(row.right.shots) +
      " shots including reload timing.</p><p class='small'><b>" + esc(builds.left.name) + ":</b> " +
      esc(modifiers(row.left.modifiers_percent)) + ". <b>" + esc(builds.right.name) + ":</b> " +
      esc(modifiers(row.right.modifiers_percent)) + ".</p>" : "") +
    (active("left") || active("right") ? "<p class='small'><b>Effect conditions:</b> " +
      esc(active("left") || "none") + " ↔ " + esc(active("right") || "none") + "</p>" : "") +
    "<p class='small'>This uses the " + esc(result.selected_primary || "selected") +
    " source reference profile and all modeled selected mods. The profile's in-game tier is unlabeled; this is not a personalized or full-build DPS winner.</p>" +
    (result.winner_established ? "<p class='note'>This conclusion depends on the selected weapon having no undocumented proc or status damage, common armor retaining only its sourced effect, and no external buff or calibration changing between plans.</p>" : "") +
    (result.blockers.length ? "<p class='note warn'>" + esc(result.blockers.join("; ")) + "</p>" : "") +
    "<details><summary>Rules, sources, assumptions, and all sensitivity rows</summary><p>" +
    builderSource(result.weapon_profile?.source) + "</p><ul>" +
    (result.model_assumptions || []).map(line => "<li>" + esc(line) + "</li>").join("") +
    "</ul><pre>" + esc(JSON.stringify({trace:result.trace,rows:result.rows,capabilities:result.capabilities},null,2)) +
    "</pre></details></div>";
}
function builderComparisonHtml(result) {
  const leftAttack=result.left?.weapon_reference_timing?.native_attack_component;
  const rightAttack=result.right?.weapon_reference_timing?.native_attack_component;
  const leftRate=result.left?.weapon_reference_timing?.native_interval_inputs?.zero_modifier_scenario;
  const rightRate=result.right?.weapon_reference_timing?.native_interval_inputs?.zero_modifier_scenario;
  const nativeValue=item=>item?.value==null?'unknown':new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(item.value);
  const nativeAttackHtml=leftAttack?.value!=null||rightAttack?.value!=null?
    "<div class='combat-known'><b>Source-native base weapon Attack · tier × stars</b><span>"+
    esc(result.builds.left.name)+": "+esc(nativeValue(leftAttack))+" → "+
    esc(result.builds.right.name)+": "+esc(nativeValue(rightAttack))+"</span>"+
    "<small>Copied native method output before calibration, mods, target, projectiles or final damage. This component alone does not rank the builds.</small></div>":"";
  const nativeRateHtml=leftRate?.native_return_expected!=null||rightRate?.native_return_expected!=null?
    "<div class='combat-known'><b>Native base fire rate · 0 RPM bonus</b><span>"+
    esc(result.builds.left.name)+": "+esc(nativeValue({value:leftRate?.native_return_expected}))+" RPM → "+
    esc(result.builds.right.name)+": "+esc(nativeValue({value:rightRate?.native_return_expected}))+" RPM</span>"+
    "<small>Built-in-round expectation from source-native interval fields. Current equipped RPM remains unknown; this base rate alone does not rank damage.</small></div>":"";
  const listed = change => change.listed_attribute_changes.map(row =>
    "<li><b>" + esc(row.name) + "</b>: " +
    esc(!row.before ? "not listed in this slot" : row.before.value_percent == null ? "value unresolved" : row.before.value_percent + "%") + " → " +
    esc(!row.after ? "not listed in this slot" : row.after.value_percent == null ? "value unresolved" : row.after.value_percent + "%") +
    "<small>" + esc(row.component || "component unresolved") + "; " + esc(row.meaning) + "</small></li>").join("");
  const changes = result.changes.map(change => "<div class='comparison-change'><h4>" + esc(change.label) +
    "</h4><div class='comparison-sides'><p><b>" + esc(result.builds.left.name) + "</b><br>" +
    esc(buildPartLabel(change.before)) + "</p><p><b>" + esc(result.builds.right.name) + "</b><br>" +
    esc(buildPartLabel(change.after)) + "</p></div><small>Changed: " +
    esc(change.fields.join(", ")) + "</small>" +
    (change.before.mod || change.after.mod ?
      "<p class='small'>Mod activation: " +
      esc(change.before.mod ? change.before.mod.effect_state.base + "; " + change.before.mod.effect_state.conditional : "none") +
      " → " + esc(change.after.mod ? change.after.mod.effect_state.base + "; " + change.after.mod.effect_state.conditional : "none") +
      "</p>" : "") +
    (change.before.gear?.effect !== change.after.gear?.effect ?
      "<p class='small'>Gear effect: " + esc(change.before.gear?.effect || "not recorded") + " → " +
      esc(change.after.gear?.effect || "not recorded") + "</p>" : "") +
    (!result.mod_comparisons.some(mod => mod.slot === change.slot) && change.listed_attribute_changes.length ?
      "<p class='small'>Listed mod attributes entering or leaving this slot:</p><ul>" + listed(change) + "</ul>" : "") +
    "</div>").join("");
  const sets = result.set_changes.map(group => "<li>" + esc(group.name) + ": " +
    esc(group.before?.count || 0) + " → " + esc(group.after?.count || 0) +
    " pieces.<small>Before: " + esc((group.before?.thresholds || []).map(t => t.pieces + " pieces " + t.state).join("; ") || "none") +
    "</small><small>After: " + esc((group.after?.thresholds || []).map(t => t.pieces + " pieces " + t.state).join("; ") || "none") +
    "</small></li>").join("");
  return "<div class='card planned-comparison'><div class='summary-heading'><div><div class='kicker'>SAVED BUILD COMPARISON</div>" +
    "<h3>" + esc(result.builds.left.name) + " ↔ " + esc(result.builds.right.name) + "</h3></div>" +
    "<button class='secondary' onclick='dismissBuilderComparison()'>Return to editing</button></div>" +
    nativeAttackHtml +
    nativeRateHtml +
    (changes || "<p>These saved versions have the same selections and settings.</p>") +
    result.mod_comparisons.map(modChangesHtml).join("") +
    (sets ? "<div><h4>Armor set changes</h4><ul>" + sets + "</ul></div>" : "") +
    (result.component_analysis && typeof componentComparisonHtml === 'function' ?
      "<details><summary>Component sensitivity across both builds</summary>" +
      componentComparisonHtml(result.component_analysis) + "</details>" : "") +
    "<p class='note warn'>Overall DPS winner unresolved. Known listed changes are shown above; no unknown effect is counted as zero.</p>" +
    (canEstimatePair(result) ? estimateControls(result) : "") +
    scopedOutgoingHtml(result.scoped_outgoing,result.builds) +
    "<details><summary>Precise ranking blockers (" + result.overall_blockers.length + ")</summary><ul>" +
    result.overall_blockers.map(line => "<li>" + esc(line) + "</li>").join("") +
    "</ul><p>" + esc(result.scope) + "</p></details></div>";
}
function dismissBuilderComparison() {
  ++builderCompareRequest;
  builderComparison = null; builderCompareTarget = null;
  const area = document.querySelector("#builderCompare");
  if (area) area.innerHTML = "";
}
async function requestPlannedCompare(target, outgoingInputs) {
  const request = ++builderCompareRequest;
  const snapshot = JSON.stringify([planned.id,planned.name,planned.slots,builderAssumptions(),builderDirty,
    builderData?.planned_builds?.find(build => build.id === target)?.slots]);
  try {
    if (builderCompareTarget && builderCompareTarget !== target && !outgoingInputs) builderEstimateValues = {};
    builderComparison = null;
    const pendingArea = document.querySelector("#builderCompare");
    if (pendingArea) pendingArea.innerHTML = "<p class='note'>Comparing saved builds…</p>";
    const result = await api("planned-compare", {
      left_id:planned.id,right_id:target,assumptions:builderAssumptions(),outgoing_inputs:outgoingInputs || null
    });
    if (request !== builderCompareRequest || page !== "builder") return;
    if (snapshot !== JSON.stringify([planned.id,planned.name,planned.slots,builderAssumptions(),builderDirty,
          builderData?.planned_builds?.find(build => build.id === target)?.slots])) {
      builderCompareTarget = null;
      const staleArea = document.querySelector("#builderCompare");
      if (staleArea) staleArea.innerHTML = "<p class='note'>Build or encounter changed. Compare the saved versions again.</p>";
      return;
    }
    builderComparison = result; builderCompareTarget = target;
    const area = document.querySelector("#builderCompare");
    if (area) area.innerHTML = builderComparisonHtml(result);
  } catch(error) {
    if (request !== builderCompareRequest) return;
    builderCompareTarget = null;
    const area = document.querySelector("#builderCompare");
    if (area && page === "builder") area.innerHTML = "<p class='note warn'>Comparison unavailable. Review the error and try again.</p>";
    fail(error);
  }
}
comparePlannedBuilds = function(targetId) {
  const area = document.querySelector("#builderCompare");
  if (!area) return;
  const panel = document.querySelector("#builderSecondary");
  if (panel) panel.open = true;
  if (!planned.id || builderDirty) {
    area.innerHTML = "<p class='note warn'>Save this version before comparing two saved builds.</p>";
    return;
  }
  const choices = builderData.planned_builds.filter(build => build.id !== planned.id);
  if (!choices.length) {
    area.innerHTML = "<p class='note'>Duplicate and save this build, then change a piece to compare versions.</p>";
    return;
  }
  if (!targetId && choices.length > 1) {
    area.innerHTML = "<div class='card'><h3>Compare with which saved build?</h3>" +
      choices.map(build => "<button class='secondary compare-choice' data-id='" + esc(build.id) +
        "' onclick='comparePlannedBuilds(this.dataset.id)'>" + esc(build.name) + "</button>").join("") + "</div>";
    return;
  }
  return requestPlannedCompare(targetId || choices[0].id);
};
async function runPlannedEstimate() {
  if (!builderCompareTarget) return;
  const ids = ["distance","critShare","weakShare","duration","nearbyKills","elementalEvents"];
  const values = {};
  for (const id of ids) {
    const raw = document.querySelector("#estimate_" + id)?.value.trim();
    if (raw === "" || raw == null || !Number.isFinite(Number(raw))) {
      fail(Error("Enter every target, event, share, and duration input for this estimate."));
      return;
    }
    values[id] = Number(raw);
  }
  const choices = ["aerial","sameElevation","below","hp","stamina"].map(id => document.querySelector("#estimate_" + id)?.value);
  if (choices.some(value => !["yes","no"].includes(value))) {
    fail(Error("Choose aerial, elevation, lower-target, HP-consumption, and stamina conditions."));
    return;
  }
  const scenario = document.querySelector("#estimate_scenario")?.value;
  if (!["PvE","PvP","RaidZone"].includes(scenario)) {
    fail(Error("Choose the encounter scenario.")); return;
  }
  if (values.nearbyKills < 0 || !Number.isInteger(values.nearbyKills) ||
      values.elementalEvents < 0 || !Number.isInteger(values.elementalEvents) ||
      values.distance < 0 || values.duration <= 0 ||
      values.critShare < 0 || values.critShare > 1 || values.weakShare < 0 || values.weakShare > 1) {
    fail(Error("Use nonnegative whole event counts, positive duration, and hit shares from 0 to 1.")); return;
  }
  builderEstimateValues = {...values,scenario,aerial:choices[0],sameElevation:choices[1],below:choices[2],hp:choices[3],stamina:choices[4]};
  await requestPlannedCompare(builderCompareTarget, {
    distance_meters:values.distance,crit_share:values.critShare,weakspot_share:values.weakShare,
    duration_seconds:values.duration,nearby_kills:values.nearbyKills,
    prior_magazine_elemental_events:values.elementalEvents,
    aerial_hit:choices[0] === "yes",same_elevation:choices[1] === "yes",
    target_below_within_5m:choices[2] === "yes",
    hp_consumed:choices[3] === "yes",stamina_spent:choices[4] === "yes",
    scenario
  });
}
