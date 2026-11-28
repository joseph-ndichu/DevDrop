"use strict";

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};

// Same lists and order as app/classify.py
const LEVELS = ["Internship", "Junior", "Mid", "Senior", "Lead / Staff", "Manager", "Unspecified"];
const JOB_FIELDS = ["Full-stack", "Frontend", "Backend", "Mobile", "Data & AI", "DevOps & Cloud",
  "IT & Support", "Security", "QA & Testing", "Design & Product", "Software Engineering", "Other tech"];
const EVENT_TYPES = ["Conference", "Hackathon", "Workshop", "Meetup", "Webinar", "Other"];
const JOB_TYPES = ["Full-time", "Part-time", "Contract", "Unspecified"];
const WORK_MODES = { job: ["Remote", "Hybrid", "On-site"], event: ["Online", "In person"], kenya: ["Remote", "Hybrid", "On-site"] };
// Kenya tab chips -> the listing's `kenya` value.
const KENYA_SCOPES = { "In Kenya": "in", "Remote, open to Kenya": "remote" };

const state = {
  items: [],
  kind: ["job", "event", "kenya"].includes(store.get("kind", "job")) ? store.get("kind", "job") : "job",
  hours: store.get("window", 24),   // 24 = posted 0–24 h ago, 48 = 24–48 h ago, 72 = 48–72 h ago (Kenya only)
  source: "",
  level: store.get("level", ""),        // jobs tab only
  jobType: store.get("jobType", ""),    // jobs tab only
  category: "",                         // job field or event type; cleared when switching tabs
  workMode: "",                         // cleared when switching tabs
  kenyaScope: store.get("kenyaScope", ""),  // Kenya tab: a KENYA_SCOPES label, or "" for both
  query: "",
  shown: 100,
};

const $ = (s) => document.querySelector(s);
const els = {
  results: $("#results"), status: $("#statusLine"), refresh: $("#refreshBtn"),
  source: $("#sourceFilter"), search: $("#search"), levels: $("#levelChips"),
  kenyaRow: $("#kenyaRow"), kenyaScopes: $("#kenyaChips"),
  workModes: $("#workModeChips"), category: $("#categoryFilter"), jobType: $("#typeFilter"),
};

// ---------- helpers ----------
const H = 3600 * 1000;

function ago(iso) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (mins < 60) return `${mins} min ago`;
  return `${Math.floor(mins / 60)} h ago`;
}

function when(iso) {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function safeUrl(u) {
  try { const x = new URL(u); return x.protocol === "http:" || x.protocol === "https:" ? x.href : "#"; } catch { return "#"; }
}

function countBy(list, key) {
  const c = {};
  for (const it of list) c[it[key]] = (c[it[key]] || 0) + 1;
  return c;
}

// ---------- filtering ----------
// The windows don't overlap: "Last 24 h" is 0–24 h old, "2 days" is 24–48 h old and,
// on the Kenya tab only, "3 days" is 48–72 h old. Other tabs stop at 2 days.
function windowBounds(kind = state.kind) {
  const now = Date.now();
  const hours = state.hours === 72 && kind !== "kenya" ? 48 : state.hours;
  return hours === 24 ? [now - 24 * H, Infinity] : [now - hours * H, now - (hours - 24) * H];
}

// Which listings belong on a tab. The Kenya tab holds jobs located in Kenya or
// remote and open to Kenya; its events are listed separately (kenyaEvents).
function onTab(it, kind) {
  return kind === "kenya" ? it.kind === "job" && !!it.kenya : it.kind === kind;
}

// `kind` defaults to the open tab; `ignore` skips one filter (used to count that filter's options).
function filtered(kind = state.kind, ignore = "") {
  const [from, to] = windowBounds(kind);
  const q = state.query.trim().toLowerCase();
  const isOpenTab = kind === state.kind;  // tab-specific filters only apply to the open tab's counts
  const jobs = kind !== "event";
  const level = jobs && ignore !== "level" ? state.level : "";
  const jobType = jobs && ignore !== "jobType" ? state.jobType : "";
  const category = isOpenTab && ignore !== "category" ? state.category : "";
  const workMode = isOpenTab && ignore !== "workMode" ? state.workMode : "";
  const kenyaScope = kind === "kenya" && ignore !== "kenyaScope" ? KENYA_SCOPES[state.kenyaScope] : "";
  const seen = new Set();
  const out = [];
  for (const it of state.items) {
    const posted = new Date(it.posted_at).getTime();
    if (posted < from || posted >= to) continue;   // strict: outside the selected window -> gone
    if (!onTab(it, kind)) continue;
    if (kenyaScope && it.kenya !== kenyaScope) continue;
    if (level && it.level !== level) continue;
    if (jobType && it.job_type !== jobType) continue;
    if (category && it.category !== category) continue;
    if (workMode && it.work_mode !== workMode) continue;
    if (state.source && it.source !== state.source) continue;
    if (q && !`${it.title} ${it.org} ${it.location} ${it.source} ${(it.tags || []).join(" ")}`.toLowerCase().includes(q)) continue;
    // The same role is often cross-posted; show it once.
    const key = `${it.title}|${it.org}`.toLowerCase().replace(/\s+/g, " ");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(it);
  }
  return out; // the API already sorts newest first
}

// Events in Kenya for the Kenya tab, in the selected window.
function kenyaEvents() {
  const [from, to] = windowBounds("kenya");
  return state.items.filter((it) => {
    const posted = new Date(it.posted_at).getTime();
    return it.kind === "event" && it.kenya === "in" && posted >= from && posted < to;
  });
}

// ---------- rendering ----------
function card(it) {
  const age = Date.now() - new Date(it.posted_at);
  // Where the work happens, by work mode.
  const loc = esc(it.location || "");
  const place = {
    Remote: it.remote_from === "Worldwide" ? "🌍 Remote · worldwide" : `🌍 Remote · from ${esc(it.remote_from || "anywhere")}`,
    Hybrid: `🏢 Hybrid${loc ? " · " + loc : ""}`,
    "On-site": `📍 On-site · ${loc}`,
    Online: "💻 Online",
    "In person": `📍 ${loc || "In person"}`,
  }[it.work_mode] || (loc ? `📍 ${loc}` : "");
  const tags = (it.tags || []).filter(Boolean).slice(0, 3).map((t) => `<span class="tag">${esc(t)}</span>`).join("");
  const pills = [
    it.level && it.level !== "Unspecified" ? `<span class="pill level">${esc(it.level)}</span>` : "",
    it.category ? `<span class="pill cat">${esc(it.category)}</span>` : "",
    it.job_type && it.job_type !== "Unspecified" ? `<span class="pill cat">${esc(it.job_type)}</span>` : "",
  ].join("");
  return `
    <li class="card ${it.kind}">
      <div class="card-top">
        <h3><a href="${esc(safeUrl(it.url))}" target="_blank" rel="noopener">${esc(it.title)}</a></h3>
        <span class="age ${age < 6 * H ? "fresh" : ""}" title="Posted ${esc(new Date(it.posted_at).toLocaleString())}">${ago(it.posted_at)}</span>
      </div>
      ${it.org ? `<div class="org">${esc(it.org)}</div>` : ""}
      <div class="meta">
        ${pills}
        ${it.starts_at ? `<span class="when">🗓 ${esc(when(it.starts_at))}</span>` : ""}
        ${place ? `<span>${place}</span>` : ""}
        ${it.salary ? `<span>💰 ${esc(it.salary)}</span>` : ""}
        <span>via ${esc(it.source)}</span>
        ${tags}
      </div>
    </li>`;
}

// A row of toggle chips: click one to filter by it, click it again to clear.
function chips(values, counts, selected, attr) {
  return values.map((v) => {
    const n = counts[v] || 0;
    const on = selected === v;
    return `<button class="chip" data-${attr}="${esc(v)}" aria-pressed="${on}" ${!n && !on ? "disabled" : ""}>${esc(v)} <span class="n">${n}</span></button>`;
  }).join("");
}

function options(values, counts, selected) {
  return values.filter((v) => counts[v] || v === selected)
    .map((v) => `<option value="${esc(v)}" ${v === selected ? "selected" : ""}>${esc(v)} (${counts[v] || 0})</option>`).join("");
}

function renderControls() {
  const jobs = state.kind !== "event";
  els.workModes.innerHTML = chips(WORK_MODES[state.kind], countBy(filtered(state.kind, "workMode"), "work_mode"), state.workMode, "mode");

  // Kenya tab: in Kenya vs remote and open to Kenya.
  els.kenyaRow.hidden = state.kind !== "kenya";
  if (state.kind === "kenya") {
    const byScope = countBy(filtered("kenya", "kenyaScope"), "kenya");
    const counts = Object.fromEntries(Object.entries(KENYA_SCOPES).map(([label, v]) => [label, byScope[v] || 0]));
    els.kenyaScopes.innerHTML = chips(Object.keys(KENYA_SCOPES), counts, state.kenyaScope, "scope");
  }

  els.levels.hidden = !jobs;
  els.jobType.hidden = !jobs;
  if (jobs) {
    els.levels.innerHTML = chips(LEVELS, countBy(filtered(state.kind, "level"), "level"), state.level, "level");
    els.jobType.innerHTML = `<option value="">All job types</option>` +
      options(JOB_TYPES, countBy(filtered(state.kind, "jobType"), "job_type"), state.jobType);
  }

  els.category.innerHTML = `<option value="">${jobs ? "All fields" : "All event types"}</option>` +
    options(jobs ? JOB_FIELDS : EVENT_TYPES, countBy(filtered(state.kind, "category"), "category"), state.category);
}

function render() {
  $("#nJob").textContent = filtered("job").length;
  $("#nEvent").textContent = filtered("event").length;
  $("#nKenya").textContent = filtered("kenya").length;
  renderControls();

  const items = filtered();
  const label = { 24: "Posted in the last 24 hours", 48: "Posted 2 days ago", 72: "Posted 3 days ago" }[state.hours];
  const where = state.kind !== "kenya" ? ""
    : state.kenyaScope ? ` · ${esc(state.kenyaScope[0].toLowerCase() + state.kenyaScope.slice(1))}` : " · in Kenya or remote, open to Kenya";
  const n = state.shown;
  let html = items.length
    ? `<h2 class="group-title">${label}${where} <span class="n">${items.length}</span></h2>
       <ol class="results">${items.slice(0, n).map(card).join("")}</ol>
       ${items.length > n ? `<button class="btn more" data-more>Show ${Math.min(100, items.length - n)} more</button>` : ""}`
    : `<p class="empty">${state.items.length
      ? `Nothing ${label.toLowerCase()}${where} matches your filters.`
      : "Collecting listings… the first scrape takes about a minute."}</p>`;

  if (state.kind === "kenya") {
    const events = kenyaEvents();
    html += `<h2 class="group-title">Events in Kenya <span class="n">${events.length}</span></h2>` + (events.length
      ? `<ol class="results">${events.map(card).join("")}</ol>`
      : `<p class="section-note">No tech events in Kenya ${label.toLowerCase()}.</p>`);
  }
  els.results.innerHTML = html;
}

els.results.addEventListener("click", (e) => {
  if (!e.target.closest("[data-more]")) return;
  state.shown += 100;
  render();
});

function fillSources() {
  const current = els.source.value;
  const names = [...new Set(state.items.filter((i) => onTab(i, state.kind)).map((i) => i.source))].sort();
  els.source.innerHTML = `<option value="">All sources</option>` +
    names.map((n) => `<option ${n === current ? "selected" : ""}>${esc(n)}</option>`).join("");
  state.source = els.source.value;
}

// ---------- data ----------
async function loadItems() {
  try {
    const data = await (await fetch("/api/items?hours=72")).json();
    state.items = data.items;
    fillSources();
    showStatus(data.status);
    render();
  } catch {
    els.status.textContent = "Can't reach the server. Is it running?";
  }
}

function showStatus(s) {
  if (!s) return;
  const entries = Object.entries(s.sources || {});
  const errs = entries.filter(([, v]) => v.error);
  const text = s.running ? "Scraping sources…" : s.finished ? `Updated ${ago(s.finished)}` : "";
  const detail = entries.map(([k, v]) =>
    `<li>${esc(k)}: ${v.error ? `<span class="err">failed: ${esc(v.error)}</span>`
      : v.skipped ? esc(v.skipped) : `${v.ok} kept, ${v.dropped} dropped (old, undated or non-tech)`}</li>`).join("");
  els.status.innerHTML = esc(text) +
    (entries.length ? ` · <details><summary>${errs.length ? `<span class="err">${errs.length} source${errs.length > 1 ? "s" : ""} failed</span>` : "sources"}</summary><ul>${detail}</ul></details>` : "");
  els.refresh.disabled = !!s.running;
  els.refresh.textContent = s.running ? "Refreshing…" : "Refresh";
}

let polling = null;
function pollUntilDone() {
  clearInterval(polling);
  let ticks = 0;
  polling = setInterval(async () => {
    ticks++;
    let s;
    try { s = await (await fetch("/api/status")).json(); } catch { return; }
    showStatus(s);
    if (s.running && ticks % 3 === 0) loadItems();
    if ((!s.running && ticks > 1) || ticks > 150) { clearInterval(polling); loadItems(); }
  }, 2000);
}

els.refresh.addEventListener("click", async () => {
  await fetch("/api/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: true }) });
  pollUntilDone();
});

// ---------- filters ----------
function bindSegmented(container, attr, apply) {
  container.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    container.querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    apply(b.dataset[attr]);
  });
}
function selectTab(container, attr, value) {
  container.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset[attr] === String(value))));
}
const resetPaging = () => { state.shown = 100; };

// "3 days" is on the Kenya tab only; leaving it falls back to "2 days".
function syncWindowTabs() {
  $("#threeDays").hidden = state.kind !== "kenya";
  if (state.kind !== "kenya" && state.hours === 72) state.hours = 48;
  selectTab($("#hoursTabs"), "hours", state.hours);
}

bindSegmented($("#kindTabs"), "kind", (v) => {
  state.kind = v;
  store.set("kind", v);
  syncWindowTabs();
  // Fields, event types, work modes and sources differ between the tabs.
  state.category = "";
  state.workMode = "";
  els.source.value = "";
  fillSources();
  resetPaging(); render();
});
selectTab($("#kindTabs"), "kind", state.kind);

bindSegmented($("#hoursTabs"), "hours", (v) => { state.hours = +v; store.set("window", state.hours); resetPaging(); render(); window.scrollTo(0, 0); });
syncWindowTabs();

function bindChips(container, attr, key, persist) {
  container.addEventListener("click", (e) => {
    const b = e.target.closest(`[data-${attr}]`); if (!b || b.disabled) return;
    const v = b.dataset[attr];
    state[key] = state[key] === v ? "" : v;   // click again to clear
    if (persist) store.set(key, state[key]);
    resetPaging(); render();
  });
}
bindChips(els.levels, "level", "level", true);
bindChips(els.workModes, "mode", "workMode", false);
bindChips(els.kenyaScopes, "scope", "kenyaScope", true);

els.source.addEventListener("change", () => { state.source = els.source.value; resetPaging(); render(); });
els.category.addEventListener("change", () => { state.category = els.category.value; resetPaging(); render(); });
els.jobType.addEventListener("change", () => { state.jobType = els.jobType.value; store.set("jobType", state.jobType); resetPaging(); render(); });
let t;
els.search.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { state.query = els.search.value; resetPaging(); render(); }, 150); });

// Listings age out of the window on their own; re-check every minute.
setInterval(render, 60 * 1000);
setInterval(loadItems, 5 * 60 * 1000);

loadItems().then(pollUntilDone);
