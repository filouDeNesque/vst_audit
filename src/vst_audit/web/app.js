"use strict";

// Statuts, dans l'ordre de gravité (identique à models.Verdict)
// Icônes géométriques monochromes (16×16), dans l'esprit de Live
const ICONS = {
  logo: '<path opacity=".35" d="M3 1h2v14H3zM7 1h2v14H7zM11 1h2v14h-2z"/><path d="M2 9h4v3H2zM6 4h4v3H6zM10 7h4v3h-4z"/>',
  refresh: '<path d="M8 2a6 6 0 1 0 5.66 8h-2.17A4 4 0 1 1 8 4c1.1 0 2.1.45 2.83 1.17L9 7h5V2l-1.76 1.76A5.98 5.98 0 0 0 8 2z"/>',
  save: '<path fill-rule="evenodd" d="M2 2h9.5L14 4.5V14H2zm2 1.5V6h6.5V3.5zM5 9v3.5h6V9z"/>',
  play: '<path d="M4 2.5v11L13 8z"/>',
  folder: '<path d="M1.5 3h5L8 5h6.5v8.5h-13z"/>',
  copy: '<path d="M5 1h9v9h-2V3H5zM2 5h8v9H2z"/>',
  seal: '<path fill-rule="evenodd" d="M8 1l6 2.5V8c0 3.5-2.6 6-6 7-3.4-1-6-3.5-6-7V3.5zm-1 9.5L11.5 6l-1-1L7 8.5 5.5 7l-1 1z"/>',
  pulse: '<path d="M1 7.2h3.1L6 2.6l3 9.2 1.9-4.6H15v1.6h-3.1L9 16 6 6.8 5.1 8.8H1z"/>',
  close: '<path d="M3.4 2.3 8 6.9l4.6-4.6 1.1 1.1L9.1 8l4.6 4.6-1.1 1.1L8 9.1l-4.6 4.6-1.1-1.1L6.9 8 2.3 3.4z"/>',
  key: '<path fill-rule="evenodd" d="M10.5 1.5a4 4 0 0 0-3.8 5.3L1.5 12v2.5H4V13h1.5v-1.5H7l1.2-1.2A4 4 0 1 0 10.5 1.5zm1 2a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z"/>',
  noentry: '<path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zm0 2a4.5 4.5 0 0 1 3.6 7.2L5.3 4.4A4.5 4.5 0 0 1 8 3.5zM4.4 5.3l6.3 6.3A4.5 4.5 0 0 1 4.4 5.3z"/>',
  half: '<path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zm0 2v9a4.5 4.5 0 0 1 0-9z"/>',
  pause: '<path d="M4 3h3v10H4zM9 3h3v10H9z"/>',
  question: '<path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM7.1 10.6h1.8v1.8H7.1zM8 3.8c1.5 0 2.7 1 2.7 2.4 0 1-.6 1.6-1.3 2-.4.3-.5.5-.5.9v.3H7.2V9c0-.9.4-1.4 1-1.8.5-.3.8-.6.8-1 0-.5-.4-.9-1-.9s-1 .4-1.1 1H5.3C5.4 4.9 6.5 3.8 8 3.8z"/>',
  check: '<path d="M6.2 12.3 2.3 8.4l1.4-1.4 2.5 2.5 6.1-6.1 1.4 1.4z"/>',
  info: '<path fill-rule="evenodd" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM7.1 4h1.8v1.8H7.1zm0 3h1.8v5H7.1z"/>',
  scissors: '<path fill-rule="evenodd" d="M4 1.5a2.5 2.5 0 1 0 1.6 4.4L7.2 8l-1.6 2.1A2.5 2.5 0 1 0 6.9 11.3L8.3 9.5 13 15h2L9.4 8.1 15 1h-2L8.3 6.6 6.9 4.7A2.5 2.5 0 0 0 4 1.5zm0 1.5a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm0 8a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>',
  external: '<path d="M9 2h5v5h-1.5V4.6L7.6 9.5 6.5 8.4l4.9-4.9H9zM2 4h5v1.5H3.5v7h7V9H12v5H2z"/>',
};
const ic = (name, cls = "") => `<svg class="ic ${cls}" viewBox="0 0 16 16" aria-hidden="true">${ICONS[name] || ""}</svg>`;

const VERDICTS = [
  { v: "invalide", icon: "close", c: "--v-invalide", desc: "Aucun format ne fonctionne (binaire manquant, rejeté par Ableton, échec Logic…)" },
  { v: "clé requise", icon: "key", c: "--v-cle", desc: "À réactiver : clé perdue, changement d'ordinateur" },
  { v: "non acquis", icon: "noentry", c: "--v-nonacquis", desc: "Installé mais jamais acheté (typiquement le catalogue UAD)" },
  { v: "démo", icon: "half", c: "--v-demo", desc: "Version d'essai en cours" },
  { v: "désactivé", icon: "pause", c: "--v-desactive", desc: "Désactivé dans une DAW" },
  { v: "à vérifier", icon: "question", c: "--v-verifier", desc: "Techniquement OK, licence non déterminée" },
  { v: "fonctionnel", icon: "check", c: "--v-ok", desc: "OK et licence confirmée (ou gratuit)" },
];
const V = Object.fromEntries(VERDICTS.map((x, i) => [x.v, { ...x, rank: i }]));
const LICENSES = ["licencié", "gratuit", "démo", "non acquis", "clé requise"];
const PROBE_VERDICT = { "licencié": "fonctionnel", "clé requise": "clé requise", "démo": "démo", "non acquis": "non acquis" };
const TIP_ICON = { "clé": "key", uad: "info", non_acquis: "noentry", invalide: "close", nettoyage: "scissors" };
const TIP_COLOR = { "clé": "--v-cle", uad: "--v-verifier", non_acquis: "--v-nonacquis", invalide: "--v-invalide", nettoyage: "--v-invalide" };

const state = {
  view: "dashboard",
  source: { type: "live", id: null },
  data: null,
  filters: { q: "", verdicts: new Set(), vendor: "", format: "", stale: false },
  sort: { key: "verdict", asc: true },
  selectedScans: [],
};

// --- utilitaires ------------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const color = (verdict) => `var(${(V[verdict] || V["à vérifier"]).c})`;
const badge = (verdict) => `<span class="badge" data-v="${esc(verdict)}" style="--c:${color(verdict)}">${ic(V[verdict]?.icon ?? "question")} ${esc(verdict)}</span>`;
const fmtChips = (formats) => formats.map((f) =>
  `<span class="fmt ${f.verdict === "invalide" ? "broken" : ""}" style="--c:${color(f.verdict)}" title="${esc(f.format)} : ${esc(f.verdict)}">${esc(f.format)}</span>`).join("");
const dateFr = (iso) => iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "";

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Erreur ${res.status}`);
  return data;
}

let toastTimer;
function toast(message, error = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast${error ? " error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), error ? 6000 : 2500);
}

async function busy(button, fn) {
  button?.classList.add("busy");
  try { return await fn(); }
  catch (e) { toast(e.message, true); }
  finally { button?.classList.remove("busy"); }
}

// --- chargement -----------------------------------------------------------------------

async function loadAnalysis(refresh = false) {
  const { type, id } = state.source;
  state.data = type === "live"
    ? await api("GET", `/api/analysis${refresh ? "?refresh=true" : ""}`)
    : await api("GET", `/api/scans/${id}`);
  const s = state.data.scan;
  $("#source-label").innerHTML = type === "live"
    ? `Analyse en direct · ${dateFr(s.started_at)} · ${s.total} bundles en ${s.duration_s.toFixed(1)} s`
    : `<b>Analyse #${s.id}</b> du ${dateFr(s.started_at)} (lecture seule)`;
  $("#btn-live").classList.toggle("hidden", type === "live");
  renderDashboard();
  renderPlugins();
}

function showView(view, { updateHash = true } = {}) {
  state.view = view;
  if (updateHash) history.replaceState(null, "", `#${view}`);
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (view === "uad") renderUad().catch((e) => toast(e.message, true));
  if (view === "history") renderHistory().catch((e) => toast(e.message, true));
  if (view === "docs") renderDocs();
}

// --- tableau de bord ------------------------------------------------------------------

function renderDashboard() {
  const { summary, scan } = state.data;
  const total = summary.unique || 1;
  $("#stat-cards").innerHTML =
    `<button class="card static" style="--c:var(--accent)"><div class="n">${summary.unique}</div><div class="l">plugins uniques · ${summary.bundles} bundles</div></button>` +
    summary.verdicts.map((x) =>
      `<button class="card" data-verdict="${esc(x.verdict)}" style="--c:${color(x.verdict)}" title="${esc(V[x.verdict].desc)}">
        <div class="n">${x.count}</div><div class="l">${ic(V[x.verdict].icon)} ${esc(x.verdict)}</div></button>`).join("");
  $("#distribution").innerHTML = summary.verdicts.filter((x) => x.count)
    .map((x) => `<div style="--c:${color(x.verdict)};width:${(100 * x.count) / total}%" title="${esc(x.verdict)} : ${x.count}"></div>`).join("");

  $("#todo").innerHTML = summary.todo.length
    ? summary.todo.map((t) => `<li class="${t.filter ? "link" : ""}" data-filter="${esc(t.filter)}" data-kind="${esc(t.kind)}">
        <span style="--c:var(${TIP_COLOR[t.kind]})">${ic(TIP_ICON[t.kind])}</span>
        <span><b>${esc(t.title)}</b> ${esc(t.text)}</span></li>`).join("")
    : `<li class="muted">Rien à signaler.</li>`;

  $("#formats").innerHTML = Object.entries(summary.formats).sort()
    .map(([f, n]) => `<span><b>${esc(f)}</b> ${n}</span>`).join("");
  $("#hosts").textContent = scan.hosts.length ? scan.hosts.join(", ") : "aucune";

  $("#vendors-table").innerHTML =
    `<thead><tr><th>Éditeur</th>${VERDICTS.map((x) => `<th class="num" title="${esc(x.v)}" style="color:${color(x.v)}">${ic(x.icon)}</th>`).join("")}<th class="num">Total</th></tr></thead>
     <tbody>${summary.vendors.map((r) => `<tr data-vendor="${esc(r.vendor)}" style="cursor:pointer">
       <td class="name">${esc(r.vendor)}</td>
       ${VERDICTS.map((x) => `<td class="num" style="color:${r.counts[x.v] ? color(x.v) : "var(--muted)"}">${r.counts[x.v] || "·"}</td>`).join("")}
       <td class="num"><b>${r.total}</b></td></tr>`).join("")}</tbody>`;
}

// --- plugins ------------------------------------------------------------------------------

function filteredPlugins() {
  const f = state.filters;
  const q = f.q.trim().toLowerCase();
  let rows = state.data.plugins.filter((p) =>
    (!q || `${p.name} ${p.vendor} ${p.license_detail} ${p.issues.join(" ")}`.toLowerCase().includes(q)) &&
    (!f.verdicts.size || f.verdicts.has(p.verdict)) &&
    (!f.vendor || p.vendor === f.vendor) &&
    (!f.format || p.formats.some((x) => x.format === f.format)) &&
    (!f.stale || p.broken_formats.length > 0));
  const { key, asc } = state.sort;
  const val = (p) => key === "verdict" ? V[p.verdict].rank : key === "version" ? (p.versions[0] || "") : String(p[key] ?? "").toLowerCase();
  rows.sort((a, b) => {
    const x = val(a), y = val(b);
    const c = x < y ? -1 : x > y ? 1 : a.name.localeCompare(b.name);
    return asc ? c : -c;
  });
  return rows;
}

function renderPlugins() {
  const vendors = [...new Set(state.data.plugins.map((p) => p.vendor))].sort((a, b) => a.localeCompare(b));
  const sel = $("#filter-vendor");
  sel.innerHTML = `<option value="">Tous les éditeurs</option>` + vendors.map((v) => `<option ${v === state.filters.vendor ? "selected" : ""}>${esc(v)}</option>`).join("");

  const counts = Object.fromEntries(state.data.summary.verdicts.map((x) => [x.verdict, x.count]));
  $("#verdict-chips").innerHTML = VERDICTS.map((x) =>
    `<span class="badge chip ${state.filters.verdicts.has(x.v) ? "on" : ""}" data-verdict="${esc(x.v)}" data-v="${esc(x.v)}" style="--c:${color(x.v)}">${ic(x.icon)} ${esc(x.v)} · ${counts[x.v] || 0}</span>`).join("");

  $$("#plugins-table th[data-sort]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === state.sort.key);
    th.classList.toggle("asc", th.dataset.sort === state.sort.key && !state.sort.asc);
  });

  const rows = filteredPlugins();
  $("#plugins-count").textContent = `${rows.length} plugin(s) affiché(s) sur ${state.data.plugins.length}`;
  $("#plugins-table tbody").innerHTML = rows.length ? rows.map((p) => `
    <tr data-key="${esc(p.key)}">
      <td>${badge(p.verdict)}</td>
      <td class="name">${esc(p.name)}</td>
      <td>${esc(p.vendor)}</td>
      <td style="white-space:nowrap">${fmtChips(p.formats)}</td>
      <td class="muted">${esc(p.versions.slice(0, 2).join(", "))}${p.versions.length > 2 ? "…" : ""}</td>
      <td>${esc(p.license)}${p.license_source ? `<div class="lic-src">${esc(p.license_source)}</div>` : ""}</td>
      <td class="notes"><span title="${esc([...p.issues, p.license_detail].filter(Boolean).join("\n"))}">${esc([...p.issues, p.license_detail].filter(Boolean).join(" · "))}</span></td>
    </tr>`).join("") : `<tr><td colspan="7" class="empty">Aucun plugin ne correspond aux filtres.</td></tr>`;
}

function filterPlugins(patch) {
  Object.assign(state.filters, { q: "", verdicts: new Set(), vendor: "", format: "", stale: false }, patch);
  $("#search").value = state.filters.q;
  $("#filter-format").value = state.filters.format;
  $("#filter-stale").checked = state.filters.stale;
  showView("plugins");
  renderPlugins();
}

// --- panneau de détail ------------------------------------------------------------------

async function openPlugin(key) {
  history.replaceState(null, "", `#${state.view}&plugin=${encodeURIComponent(key)}`);
  $("#drawer-body").innerHTML = `<div class="empty">Chargement…</div>`;
  $("#drawer").classList.add("open");
  $("#overlay").classList.remove("hidden");
  try {
    renderDrawer(await api("GET", `/api/plugin?key=${encodeURIComponent(key)}`));
  } catch (e) {
    // plugin d'une analyse passée qui n'est plus installé : on montre ce que l'on sait
    const p = state.data.plugins.find((x) => x.key === key);
    $("#drawer-body").innerHTML = p
      ? `<h1>${esc(p.name)}</h1><div class="muted">${esc(p.vendor)}</div><p>${badge(p.verdict)}</p>
         <p class="muted">Ce plugin n'est plus présent dans l'analyse en direct : actions indisponibles.</p>`
      : `<div class="empty">${esc(e.message)}</div>`;
  }
}

function closeDrawer() {
  if ($("#drawer").classList.contains("open")) history.replaceState(null, "", `#${state.view}`);
  $("#drawer").classList.remove("open");
  $("#overlay").classList.add("hidden");
}

function renderDrawer(d) {
  const past = state.source.type !== "live";
  const override = d.override;
  const hostRows = (item) => Object.entries(item.hosts).map(([h, s]) => {
    const code = item.extra[`${h.toLowerCase()}_scanstate`];
    return `<dt>${esc(h)}</dt><dd>${esc(s)}${code ? ` <span class="muted">(code ${esc(code)})</span>` : ""}</dd>`;
  }).join("");

  $("#drawer-body").innerHTML = `
    <h1>${esc(d.name)}</h1>
    <div class="sub">${esc(d.vendor)}${d.uad_family ? ` · ${esc(d.uad_family)}` : ""}
      <div style="margin-top:6px">${badge(d.verdict)} ${fmtChips(d.formats)}</div></div>
    ${past ? `<p class="muted small">Détail issu de l'analyse en direct (vous consultez une analyse passée).</p>` : ""}

    <h3>Licence</h3>
    <dl class="kv">
      <dt>Statut</dt><dd>${esc(d.license)}</dd>
      <dt>Source</dt><dd>${esc(d.license_source || "aucune")}</dd>
      ${d.license_detail ? `<dt>Détail</dt><dd>${esc(d.license_detail)}</dd>` : ""}
      ${d.portal ? `<dt>Récupérer</dt><dd>${esc(d.portal)}</dd>` : ""}
    </dl>
    <div class="form-row">
      <select id="ov-status">${LICENSES.map((l) => `<option ${override?.status === l ? "selected" : ""}>${l}</option>`).join("")}</select>
      <input id="ov-note" type="text" placeholder="Note (facultatif)" value="${esc(override?.note || "")}">
      <button class="btn primary" id="ov-save">Définir le statut</button>
      ${override ? `<button class="btn ghost" id="ov-reset" title="Supprimer le statut défini">Revenir à l'auto</button>` : ""}
    </div>

    <h3>Vérification active</h3>
    ${d.probe ? `
      <dl class="kv">
        <dt>Résultat</dt><dd>${d.probe.status ? badge(PROBE_VERDICT[d.probe.status] || "à vérifier") : `<span class="muted">non concluant</span>`} ${esc(d.probe.label)}</dd>
        <dt>Sondé le</dt><dd>${dateFr(d.probe.date)} · ${esc(d.probe.format || "")}</dd>
        ${d.probe.evidence.length ? `<dt>Indices</dt><dd>${d.probe.evidence.map((e) => esc(e)).join("<br>")}</dd>` : ""}
      </dl>
      ${d.probe.capture ? `<a href="/api/plugin/probe-capture?key=${encodeURIComponent(d.key)}&t=${encodeURIComponent(d.probe.date)}" target="_blank">
        <img class="probe-capture" alt="Interface du plugin lors de la sonde" src="/api/plugin/probe-capture?key=${encodeURIComponent(d.key)}&t=${encodeURIComponent(d.probe.date)}"></a>` : ""}`
      : `<p class="muted small">Charge le plugin, écoute ce qu'il produit et lit son interface (écran d'activation, mode démo…).</p>`}
    ${d.probe_possible ? `
      <div class="form-row">
        <label class="check"><input type="checkbox" id="probe-gui" checked> lire son interface</label>
        <button class="btn primary" id="probe-run">${ic("pulse")} ${d.probe ? "Resonder" : "Sonder ce plugin"}</button>
      </div>
      <div class="probe-status muted small"></div>`
      : `<p class="muted small">Non sondable : ${esc(d.probe_blocked || "")}.</p>`}

    ${d.ua_plugin_id ? `
      <h3>Universal Audio</h3>
      <dl class="kv">
        <dt>Identifiant</dt><dd><code>${esc(d.ua_plugin_id)}</code></dd>
        ${d.ua_suivi ? `<dt>Suivi</dt><dd>${esc(d.ua_suivi.label)} · ${esc(d.ua_suivi.date.slice(0, 10))}${d.ua_suivi.note ? ` · ${esc(d.ua_suivi.note)}` : ""}</dd>` : ""}
      </dl>
      <div class="actions"><button class="btn" data-ua-check="${esc(d.ua_plugin_id)}">${ic("refresh")} Lire le journal UA</button></div>
      <div class="ua-result"></div>` : ""}

    ${d.issues.length ? `<h3>Remarques</h3>${d.issues.map((i) => `<div class="issue">${esc(i)}</div>`).join("")}` : ""}

    <h3>Formats installés (${d.items.length})</h3>
    ${d.items.map((item, n) => `
      <div class="fmt-card">
        <header>${badge(item.verdict)} <b>${esc(item.format)}</b> <span class="muted">${esc(item.version)}</span></header>
        <div class="path">${esc(item.path)}</div>
        <dl class="kv" style="margin-top:8px">
          <dt>Nom</dt><dd>${esc(item.name)}</dd>
          <dt>Bundle ID</dt><dd><code>${esc(item.bundle_id || "—")}</code></dd>
          <dt>Architectures</dt><dd>${esc(item.archs.join(", ") || "—")}</dd>
          <dt>État technique</dt><dd>${esc(item.health)}</dd>
          ${item.issues.length ? `<dt>Problèmes</dt><dd>${esc(item.issues.join(" · "))}</dd>` : ""}
          ${hostRows(item)}
          ${item.extra.au_id ? `<dt>Composant AU</dt><dd><code>${esc(item.extra.au_id)}</code></dd>` : ""}
        </dl>
        <div class="actions">
          <button class="btn small" data-act="reveal" data-n="${n}">${ic("folder")} Finder</button>
          <button class="btn small" data-act="copy" data-n="${n}">${ic("copy")} Copier le chemin</button>
          <button class="btn small" data-act="signature" data-n="${n}">${ic("seal")} Signature</button>
          ${item.extra.au_id ? `<button class="btn small" data-act="auval" data-n="${n}">${ic("pulse")} auval</button>` : ""}
        </div>
        <div class="result hidden" data-result="${n}"></div>
      </div>`).join("")}
  `;

  const body = $("#drawer-body");
  $("#ov-save", body).onclick = (e) => busy(e.target, async () => {
    const updated = await api("PUT", "/api/plugin/override", { key: d.key, status: $("#ov-status").value, note: $("#ov-note").value });
    toast("Statut enregistré");
    renderDrawer(updated);
    await reloadLiveSilently();
  });
  const reset = $("#ov-reset", body);
  if (reset) reset.onclick = (e) => busy(e.target, async () => {
    renderDrawer(await api("DELETE", `/api/plugin/override?key=${encodeURIComponent(d.key)}`));
    toast("Retour à la détection automatique");
    await reloadLiveSilently();
  });

  const probe = $("#probe-run", body);
  if (probe) probe.onclick = () => busy(probe, async () => {
    const gui = $("#probe-gui", body).checked;
    $(".probe-status", body).textContent = gui
      ? "Sonde en cours (≈ 25 s) : la fenêtre du plugin va s'ouvrir puis se refermer…"
      : "Sonde en cours (≈ 15 s)…";
    const updated = await api("POST", "/api/plugin/probe", { key: d.key, gui });
    renderDrawer(updated);
    toast(updated.probe ? `Sonde : ${updated.probe.label}` : "Sonde terminée");
    await reloadLiveSilently();
  });

  $$("[data-act]", body).forEach((btn) => btn.onclick = () => runAction(btn, d.items[+btn.dataset.n]));
  const ua = $("[data-ua-check]", body);
  if (ua) ua.onclick = () => busy(ua, async () => {
    const { state: st } = await api("POST", `/api/uad/check/${encodeURIComponent(d.ua_plugin_id)}`);
    const out = $(".ua-result", body);
    out.innerHTML = st
      ? `<div class="result ok">Journal : <b>${esc(st.label)}</b> (${dateFr(st.seen)})
           <button class="btn small" id="ua-accept">Valider dans le suivi</button></div>`
      : `<div class="result ko">Aucun état de licence dans le journal. Ouvrez le plugin en mode natif dans une DAW, puis réessayez.</div>`;
    const accept = $("#ua-accept", out);
    if (accept) accept.onclick = () => busy(accept, async () => {
      await api("POST", `/api/uad/suivi/${encodeURIComponent(d.ua_plugin_id)}/journal`);
      toast("Validé dans le suivi");
      await reloadLiveSilently();
      openPlugin(d.key);
    });
  });
}

async function runAction(btn, item) {
  const out = $(`[data-result="${btn.dataset.n}"]`, $("#drawer-body"));
  const show = (ok, html) => { out.className = `result ${ok ? "ok" : "ko"}`; out.innerHTML = html; };
  const act = btn.dataset.act;
  if (act === "copy") {
    await navigator.clipboard.writeText(item.path);
    return toast("Chemin copié");
  }
  await busy(btn, async () => {
    if (act === "reveal") {
      await api("POST", "/api/plugin/reveal", { path: item.path });
      toast("Ouvert dans le Finder");
    } else if (act === "signature") {
      const r = await api("POST", "/api/plugin/signature", { path: item.path });
      show(r.ok, `<b>${r.ok ? `${ic("check")} Signature valide` : `${ic("close")} Signature invalide`}</b>${r.ok ? "" : ` : ${esc(r.message)}`}
        <dl class="kv" style="margin-top:6px">${Object.entries(r.details).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`);
    } else if (act === "auval") {
      show(true, "auval en cours… (quelques secondes)");
      const r = await api("POST", "/api/plugin/auval", { path: item.path });
      show(r.ok, `<b>${ic(r.ok ? "check" : "close")} ${esc(r.summary)}</b><details><summary>Sortie complète</summary><pre>${esc(r.output)}</pre></details>`);
    }
  });
}

async function reloadLiveSilently() {
  if (state.source.type === "live") await loadAnalysis(false);
  if (state.view === "uad") await renderUad();
}

// --- UAD ---------------------------------------------------------------------------------------

async function renderUad() {
  const u = await api("GET", "/api/uad");
  const prof = u.sources.profile;
  $("#uad-sources").innerHTML = `
    <div class="card static" style="--c:var(--v-ok)"><div class="n">${u.sources.uadx_logs}</div><div class="l">UADx avec un état dans leur journal</div></div>
    <div class="card static" style="--c:${prof ? "var(--v-ok)" : "var(--v-demo)"}">
      <div class="n">${prof ? prof.products : "—"}</div>
      <div class="l">${prof ? `produits UAD-2 · profil du ${esc(prof.date)}` : "profil UAD-2 inexploitable : Apollo branché, UAD Meter → System Info"}</div></div>
    <div class="card static" style="--c:var(--v-verifier)"><div class="n">${u.suivi.length}</div><div class="l">UADx à suivre</div></div>`;

  const done = u.suivi.filter((i) => i.entry).length;
  const pct = u.suivi.length ? (100 * done) / u.suivi.length : 100;
  $("#uad-progress div").style.width = `${pct}%`;
  $("#uad-progress span").textContent = `${done}/${u.suivi.length} traités`;

  const choices = [["acheté", "Acheté"], ["spark", "Spark"], ["démo", "Démo"], ["non acquis", "Non acquis"]];
  $("#uad-suivi").innerHTML = u.suivi.length ? `
    <thead><tr><th>#</th><th>Plugin</th><th>Formats</th><th>État</th><th>Actions</th></tr></thead>
    <tbody>${u.suivi.map((i, n) => `
      <tr data-pid="${esc(i.plugin_id)}">
        <td class="num muted">${n + 1}</td>
        <td class="name">${esc(i.name)}<div class="lic-src"><code>${esc(i.plugin_id)}</code></div></td>
        <td class="muted">${esc(i.formats)}</td>
        <td>${i.entry ? `<b>${esc(i.entry.label)}</b><div class="lic-src">${esc(i.entry.source)} · ${esc(i.entry.date.slice(0, 10))}${i.entry.note ? ` · ${esc(i.entry.note)}` : ""}</div>` : `<span class="muted">○ à faire</span>`}
          <div class="ua-inline"></div></td>
        <td><div class="actions" style="margin:0">
          <button class="btn small" data-check>Lire le journal</button>
          ${choices.map(([v, l]) => `<button class="btn small ghost" data-note="${v}">${l}</button>`).join("")}
          ${i.entry ? `<button class="btn small ghost" data-forget title="Effacer la note">${ic("close")}</button>` : ""}
        </div></td>
      </tr>`).join("")}</tbody>`
    : `<tbody><tr><td class="empty">Tous les UADx ont un état connu par leur journal.</td></tr></tbody>`;

  $$("#uad-suivi tr[data-pid]").forEach((tr) => {
    const pid = tr.dataset.pid;
    $("[data-check]", tr).onclick = (e) => busy(e.target, async () => {
      const { state: st } = await api("POST", `/api/uad/check/${encodeURIComponent(pid)}`);
      const box = $(".ua-inline", tr);
      box.innerHTML = st
        ? `<div class="result ok">Journal : <b>${esc(st.label)}</b> <button class="btn small" data-accept>Valider</button></div>`
        : `<div class="result ko">Aucun état dans le journal : ouvrez le plugin en natif.</div>`;
      const acc = $("[data-accept]", box);
      if (acc) acc.onclick = () => busy(acc, async () => {
        await api("POST", `/api/uad/suivi/${encodeURIComponent(pid)}/journal`);
        toast("Validé");
        await reloadLiveSilently();
      });
    });
    $$("[data-note]", tr).forEach((b) => b.onclick = () => busy(b, async () => {
      const note = prompt(`Note pour ${pid} (facultatif)`, "") ?? "";
      await api("PUT", `/api/uad/suivi/${encodeURIComponent(pid)}`, { status: b.dataset.note, note });
      toast("Noté");
      await reloadLiveSilently();
    }));
    const forget = $("[data-forget]", tr);
    if (forget) forget.onclick = () => busy(forget, async () => {
      await api("DELETE", `/api/uad/suivi/${encodeURIComponent(pid)}`);
      await reloadLiveSilently();
    });
  });

  // Vue d'ensemble par famille et par état
  const families = {};
  for (const p of u.plugins) {
    const fam = p.uad_family || "Autre";
    const label = p.license_source.startsWith("UA ") ? p.license_detail.split(" · ")[0].replace(/ (le|jusqu'au) .*$/, "") : "aucune information";
    ((families[fam] ??= {})[label] ??= []).push(p);
  }
  $("#uad-families").innerHTML = Object.entries(families).map(([fam, labels]) => `
    <div class="family"><h4>${esc(fam)} · ${Object.values(labels).flat().length} plugins</h4>
    ${Object.entries(labels).sort((a, b) => V[a[1][0].verdict].rank - V[b[1][0].verdict].rank).map(([label, ps]) => `
      <div class="label-row">${badge(label === "aucune information" ? "à vérifier" : ps[0].verdict)}
        <b>${esc(label)}</b> <span class="muted">${ps.length}</span>
        <span class="names">${ps.sort((a, b) => a.name.localeCompare(b.name))
          .map((p) => `<a data-key="${esc(p.key)}">${esc(p.name.replace(/^UADx? /, ""))}</a>`).join(", ")}</span>
      </div>`).join("")}</div>`).join("");
  $$("#uad-families a[data-key]").forEach((a) => a.onclick = () => openPlugin(a.dataset.key));
}

// --- historique ---------------------------------------------------------------------------------

async function renderHistory() {
  const scans = await api("GET", "/api/scans");
  state.selectedScans = state.selectedScans.filter((id) => scans.some((s) => s.id === id));
  $("#btn-compare").disabled = state.selectedScans.length !== 2;
  $("#scans-table").innerHTML = scans.length ? `
    <thead><tr><th></th><th>#</th><th>Date</th><th>Machine</th><th>Bundles</th><th>Durée</th><th>DAW</th><th></th></tr></thead>
    <tbody>${scans.map((s) => `<tr>
      <td><input type="checkbox" data-scan="${s.id}" ${state.selectedScans.includes(s.id) ? "checked" : ""}></td>
      <td class="num"><b>${s.id}</b></td><td>${dateFr(s.started_at)}</td><td class="muted">${esc(s.machine)}</td>
      <td class="num">${s.total}</td><td class="num">${s.duration_s.toFixed(1)} s</td><td>${esc(s.hosts.join(", "))}</td>
      <td><button class="btn small" data-open="${s.id}">Ouvrir</button></td></tr>`).join("")}</tbody>`
    : `<tbody><tr><td class="empty">Aucune analyse enregistrée. Cliquez sur « Enregistrer ».</td></tr></tbody>`;

  $$("[data-scan]").forEach((cb) => cb.onchange = () => {
    const id = +cb.dataset.scan;
    state.selectedScans = cb.checked ? [...state.selectedScans, id].slice(-2) : state.selectedScans.filter((x) => x !== id);
    renderHistory();
  });
  $$("[data-open]").forEach((b) => b.onclick = () => busy(b, async () => {
    state.source = { type: "scan", id: +b.dataset.open };
    await loadAnalysis();
    showView("dashboard");
  }));
}

function renderDiff(d) {
  const el = $("#diff");
  el.classList.remove("hidden");
  const row = (tag, p, change) => `<tr data-key="${esc(p.key)}"><td>${tag}</td><td class="name">${esc(p.name)}</td><td>${esc(p.vendor)}</td><td>${change}</td></tr>`;
  const rows = [
    ...d.added.map((p) => row(`<span style="color:var(--v-ok)">+ ajouté</span>`, p, badge(p.verdict))),
    ...d.removed.map((p) => row(`<span style="color:var(--v-invalide)">− retiré</span>`, p, "")),
    ...d.changed.map((c) => row(`<span style="color:var(--v-demo)">~ modifié</span>`, c,
      c.what === "statut" ? `${badge(c.before)} → ${badge(c.after)}` : `<span class="muted">${esc(c.what)}</span> : ${esc(c.before || "∅")} → ${esc(c.after || "∅")}`)),
  ];
  el.innerHTML = `
    <div class="panel-head"><h2>Évolution #${d.old} → #${d.new}</h2>
      <span class="muted"><b style="color:var(--v-ok)">+${d.added.length}</b> <b style="color:var(--v-invalide)">−${d.removed.length}</b> <b style="color:var(--v-demo)">~${d.changed.length}</b></span></div>
    ${d.transitions.length ? `<div class="diff-moves">${d.transitions.map((t) => `<div>${badge(t.before)} → ${badge(t.after)} <b>${t.count}</b> plugin(s)</div>`).join("")}</div>` : ""}
    ${rows.length ? `<div class="table-wrap"><table class="table clickable"><thead><tr><th></th><th>Plugin</th><th>Éditeur</th><th>Changement</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`
      : `<div class="empty">Aucun changement.</div>`}`;
  $$("tr[data-key]", el).forEach((tr) => tr.onclick = () => openPlugin(tr.dataset.key));
}

// --- documentation ---------------------------------------------------------------------------

let docsLoaded = false;
async function renderDocs() {
  $("#docs-statuses").innerHTML = VERDICTS.map((x) => `<tr><td>${badge(x.v)}</td><td>${esc(x.desc)}</td></tr>`).join("");
  if (docsLoaded) return;
  try {
    const spec = await api("GET", "/api/openapi.json");
    const rows = [];
    for (const [path, ops] of Object.entries(spec.paths)) {
      for (const [method, op] of Object.entries(ops)) {
        rows.push(`<tr><td><span class="method ${method}">${method.toUpperCase()}</span></td><td><code>${esc(path)}</code></td>
          <td>${esc(op.summary || "")}</td><td class="muted">${esc((op.tags || []).join(", "))}</td></tr>`);
      }
    }
    $("#docs-api").innerHTML = `<thead><tr><th>Méthode</th><th>Route</th><th>Rôle</th><th>Groupe</th></tr></thead><tbody>${rows.join("")}</tbody>`;
    docsLoaded = true;
  } catch (e) { toast(e.message, true); }
}

// --- événements -------------------------------------------------------------------------------

function bind() {
  $$(".tab").forEach((t) => t.onclick = () => showView(t.dataset.view));

  $("#btn-refresh").onclick = (e) => busy(e.target, async () => {
    state.source = { type: "live", id: null };
    await loadAnalysis(true);
    if (state.view === "uad") await renderUad();
    toast("Analyse actualisée");
  });
  $("#btn-live").onclick = (e) => busy(e.target, async () => {
    state.source = { type: "live", id: null };
    await loadAnalysis();
  });
  $("#btn-save").onclick = (e) => busy(e.target, async () => {
    const r = await api("POST", "/api/scans");
    state.source = { type: "live", id: null };
    await loadAnalysis();
    toast(`Analyse #${r.scan.id} enregistrée`);
    if (r.diff) { showView("history"); renderDiff(r.diff); }
  });
  $("#btn-compare").onclick = (e) => busy(e.target, async () => {
    const [a, b] = [...state.selectedScans].sort((x, y) => x - y);
    renderDiff(await api("GET", `/api/diff?old=${a}&new=${b}`));
  });

  $("#stat-cards").onclick = (e) => {
    const card = e.target.closest("[data-verdict]");
    if (card) filterPlugins({ verdicts: new Set([card.dataset.verdict]) });
  };
  $("#todo").onclick = (e) => {
    const li = e.target.closest("li");
    if (!li) return;
    if (li.dataset.kind === "uad") return showView("uad");
    if (li.dataset.kind === "nettoyage") return filterPlugins({ stale: true });
    if (li.dataset.filter) filterPlugins({ verdicts: new Set([li.dataset.filter]) });
  };
  $("#vendors-table").onclick = (e) => {
    const tr = e.target.closest("tr[data-vendor]");
    if (tr) filterPlugins({ vendor: tr.dataset.vendor });
  };

  $("#search").oninput = (e) => { state.filters.q = e.target.value; renderPlugins(); };
  $("#filter-vendor").onchange = (e) => { state.filters.vendor = e.target.value; renderPlugins(); };
  $("#filter-format").onchange = (e) => { state.filters.format = e.target.value; renderPlugins(); };
  $("#filter-stale").onchange = (e) => { state.filters.stale = e.target.checked; renderPlugins(); };
  $("#btn-clear").onclick = () => filterPlugins({});
  $("#verdict-chips").onclick = (e) => {
    const chip = e.target.closest("[data-verdict]");
    if (!chip) return;
    const v = chip.dataset.verdict;
    state.filters.verdicts.has(v) ? state.filters.verdicts.delete(v) : state.filters.verdicts.add(v);
    renderPlugins();
  };
  $("#plugins-table thead").onclick = (e) => {
    const th = e.target.closest("th[data-sort]");
    if (!th) return;
    state.sort = { key: th.dataset.sort, asc: state.sort.key === th.dataset.sort ? !state.sort.asc : true };
    renderPlugins();
  };
  $("#plugins-table tbody").onclick = (e) => {
    const tr = e.target.closest("tr[data-key]");
    if (tr) openPlugin(tr.dataset.key);
  };

  $("#overlay").onclick = closeDrawer;
  $("#drawer-close").onclick = closeDrawer;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
      e.preventDefault();
      showView("plugins");
      $("#search").focus();
    }
  });
}

// Liens directs : #plugins, #uad, #plugins&plugin=<clé>
function routeFromHash() {
  const [view, ...params] = location.hash.slice(1).split("&");
  const plugin = params.find((x) => x.startsWith("plugin="));
  if (["dashboard", "plugins", "uad", "history", "docs"].includes(view)) showView(view, { updateHash: false });
  if (plugin) openPlugin(decodeURIComponent(plugin.slice(7)));
}

// Thème Ableton Live : celui de Live par défaut, ou celui choisi ici (mémorisé dans ce navigateur)
async function setupTheme() {
  let saved = "";
  try { saved = localStorage.getItem("vst-audit-theme") || ""; } catch {}
  const info = await api("GET", "/api/theme").catch(() => null);
  if (!info?.available.length) return;
  const sel = $("#theme-select");
  sel.innerHTML = `<option value="">Thème Live : ${esc(info.active || "par défaut")}</option>` +
    info.available.map((t) => `<option ${t === saved ? "selected" : ""}>${esc(t)}</option>`).join("");
  sel.classList.remove("hidden");
  const apply = (name) => { $("#theme-css").href = name ? `/theme.css?name=${encodeURIComponent(name)}` : "/theme.css"; };
  if (saved && info.available.includes(saved)) apply(saved);
  sel.onchange = () => {
    apply(sel.value);
    try { sel.value ? localStorage.setItem("vst-audit-theme", sel.value) : localStorage.removeItem("vst-audit-theme"); } catch {}
  };
}

$$("[data-icon]").forEach((el) => { el.outerHTML = ic(el.dataset.icon, el.dataset.size || ""); });
bind();
setupTheme();
loadAnalysis().then(routeFromHash).catch((e) => toast(e.message, true));
