"use strict";

// Statuts, dans l'ordre de gravité (identique à models.Verdict)
const VERDICTS = [
  { v: "invalide", icon: "✖", c: "--v-invalide", desc: "Aucun format ne fonctionne (binaire manquant, rejeté par Ableton, échec Logic…)" },
  { v: "clé requise", icon: "⚿", c: "--v-cle", desc: "À réactiver : clé perdue, changement d'ordinateur" },
  { v: "non acquis", icon: "∅", c: "--v-nonacquis", desc: "Installé mais jamais acheté (typiquement le catalogue UAD)" },
  { v: "démo", icon: "◐", c: "--v-demo", desc: "Version d'essai en cours" },
  { v: "désactivé", icon: "⏸", c: "--v-desactive", desc: "Désactivé dans une DAW" },
  { v: "à vérifier", icon: "?", c: "--v-verifier", desc: "Techniquement OK, licence non déterminée" },
  { v: "fonctionnel", icon: "✔", c: "--v-ok", desc: "OK et licence confirmée (ou gratuit)" },
];
const V = Object.fromEntries(VERDICTS.map((x, i) => [x.v, { ...x, rank: i }]));
const LICENSES = ["licencié", "gratuit", "démo", "non acquis", "clé requise"];
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
const badge = (verdict) => `<span class="badge" style="--c:${color(verdict)}">${V[verdict]?.icon ?? "?"} ${esc(verdict)}</span>`;
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
        <div class="n">${x.count}</div><div class="l">${V[x.verdict].icon} ${esc(x.verdict)}</div></button>`).join("");
  $("#distribution").innerHTML = summary.verdicts.filter((x) => x.count)
    .map((x) => `<div style="--c:${color(x.verdict)};width:${(100 * x.count) / total}%" title="${esc(x.verdict)} : ${x.count}"></div>`).join("");

  $("#todo").innerHTML = summary.todo.length
    ? summary.todo.map((t) => `<li class="${t.filter ? "link" : ""}" data-filter="${esc(t.filter)}" data-kind="${esc(t.kind)}">
        <span class="ic" style="--c:var(${TIP_COLOR[t.kind]})">${esc(t.icon)}</span>
        <span><b>${esc(t.title)}</b> ${esc(t.text)}</span></li>`).join("")
    : `<li class="muted">Rien à signaler.</li>`;

  $("#formats").innerHTML = Object.entries(summary.formats).sort()
    .map(([f, n]) => `<span><b>${esc(f)}</b> ${n}</span>`).join("");
  $("#hosts").textContent = scan.hosts.length ? scan.hosts.join(", ") : "aucune";

  $("#vendors-table").innerHTML =
    `<thead><tr><th>Éditeur</th>${VERDICTS.map((x) => `<th class="num" title="${esc(x.v)}" style="color:${color(x.v)}">${x.icon}</th>`).join("")}<th class="num">Total</th></tr></thead>
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
    `<span class="badge chip ${state.filters.verdicts.has(x.v) ? "on" : ""}" data-verdict="${esc(x.v)}" style="--c:${color(x.v)}">${x.icon} ${esc(x.v)} · ${counts[x.v] || 0}</span>`).join("");

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
    <div class="muted">${esc(d.vendor)}${d.uad_family ? ` · ${esc(d.uad_family)}` : ""}</div>
    <p>${badge(d.verdict)} ${fmtChips(d.formats)}</p>
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

    ${d.ua_plugin_id ? `
      <h3>Universal Audio</h3>
      <dl class="kv">
        <dt>Identifiant</dt><dd><code>${esc(d.ua_plugin_id)}</code></dd>
        ${d.ua_suivi ? `<dt>Suivi</dt><dd>${esc(d.ua_suivi.label)} · ${esc(d.ua_suivi.date.slice(0, 10))}${d.ua_suivi.note ? ` · ${esc(d.ua_suivi.note)}` : ""}</dd>` : ""}
      </dl>
      <div class="actions"><button class="btn" data-ua-check="${esc(d.ua_plugin_id)}">Lire le journal UA</button></div>
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
          <button class="btn small" data-act="reveal" data-n="${n}">📂 Finder</button>
          <button class="btn small" data-act="copy" data-n="${n}">⧉ Copier le chemin</button>
          <button class="btn small" data-act="signature" data-n="${n}">🔏 Signature</button>
          ${item.extra.au_id ? `<button class="btn small" data-act="auval" data-n="${n}">🧪 auval</button>` : ""}
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
      show(r.ok, `<b>${r.ok ? "✔ Signature valide" : "✖ Signature invalide"}</b>${r.ok ? "" : ` : ${esc(r.message)}`}
        <dl class="kv" style="margin-top:6px">${Object.entries(r.details).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`);
    } else if (act === "auval") {
      show(true, "auval en cours… (quelques secondes)");
      const r = await api("POST", "/api/plugin/auval", { path: item.path });
      show(r.ok, `<b>${r.ok ? "✔" : "✖"} ${esc(r.summary)}</b><details><summary>Sortie complète</summary><pre>${esc(r.output)}</pre></details>`);
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
          ${i.entry ? `<button class="btn small ghost" data-forget title="Effacer la note">✕</button>` : ""}
        </div></td>
      </tr>`).join("")}</tbody>`
    : `<tbody><tr><td class="empty">Tous les UADx ont un état connu par leur journal. 🎉</td></tr></tbody>`;

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
    : `<tbody><tr><td class="empty">Aucune analyse enregistrée. Cliquez sur « 💾 Enregistrer ».</td></tr></tbody>`;

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

bind();
loadAnalysis().then(routeFromHash).catch((e) => toast(e.message, true));
