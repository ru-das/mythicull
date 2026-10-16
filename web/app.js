const app = document.getElementById("app");

async function api(path, opts) {
  const res = await fetch("/api" + path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

const jsonBody = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

function el(tag, props = {}, ...kids) {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...kids);
  return e;
}

async function showList() {
  const projects = await api("/projects");
  const msg = el("p", { className: "error" });
  const name = el("input", { placeholder: "Project name", required: true });
  const folder = el("input", { placeholder: "Photo folder path, e.g. /home/me/shoots/wedding", required: true });
  const form = el("form", {}, name, folder, el("button", { textContent: "Create and import" }), msg);
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      const out = await api("/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.value, folder: folder.value }),
      });
      location.hash = `#/p/${out.project.id}/${out.job_id}`;
    } catch (e) {
      msg.textContent = e.message;
    }
  };
  const list = el("ul");
  for (const p of projects) {
    list.append(el("li", {},
      el("a", { href: `#/p/${p.id}`, textContent: p.name }),
      el("span", { className: "muted", textContent: ` ${p.photo_count} photos, ${p.folder}` })));
  }
  if (!projects.length) list.append(el("li", { className: "muted", textContent: "No projects yet." }));
  app.replaceChildren(el("h2", { textContent: "New project" }), form, el("h2", { textContent: "Projects" }), list);
}

function summaryView(p) {
  const s = p.last_import;
  const box = el("div", {}, el("p", { textContent: `${p.photo_count} photos in ${p.folder}` }));
  if (!s) {
    box.append(el("p", { className: "muted", textContent: "No import summary yet (import still running or interrupted)." }));
    return box;
  }
  box.append(el("p", { textContent: `Found ${s.found}, imported ${s.imported}, already present ${s.already_present}, skipped ${s.skipped.length}.` }));
  if (!p.photo_count) {
    box.append(el("p", { className: "error", textContent: `No supported photos found in this folder. MythiCull reads JPEG and RAW (CR2, CR3, NEF, ARW, RAF, DNG). Check the folder path and create the project again.` }));
  }
  if (s.skipped.length) {
    const ul = el("ul");
    for (const k of s.skipped) ul.append(el("li", { textContent: `${k.path}: ${k.reason}` }));
    box.append(el("h3", { textContent: "Skipped files" }), ul);
  }
  return box;
}

let pollTimer = null;
let indexTimer = null;

async function showProject(id, jobId) {
  const head = el("h2", { textContent: "Loading…" });
  const status = el("div");
  app.replaceChildren(head, status);
  const grid = el("div", { className: "grid" });
  const side = el("nav", { className: "sidebar" });
  let chapterId = null;
  const searchMsg = el("span", { className: "muted" });
  const loadGrid = async () => {
    const ch = chapterId ? `chapter=${chapterId}` : "";
    searchQ = searchQ.trim();
    searchMsg.textContent = "";
    if (!searchQ) return showGrid(grid, await api(`/projects/${id}/photos` + (ch ? `?${ch}` : "")));
    try {
      const hits = await api(`/projects/${id}/search?q=${encodeURIComponent(searchQ)}&${ch}`);
      showGrid(grid, hits);
      searchMsg.textContent = hits.length ? `${hits.length} best matches` : "No matches. Index the photos first?";
    } catch (e) {
      searchQ = "";
      searchBox.value = "";
      await loadGrid();
      searchMsg.textContent = e.message;
    }
  };
  const searchBox = el("input", { type: "search", id: "search", placeholder: "Search photos (/)", title: "Plain-English search, e.g. people dancing" });
  searchBox.onkeydown = (ev) => {
    if (ev.key === "Enter") { searchQ = searchBox.value; loadGrid().catch(showError); }
    else if (ev.key === "Escape") { searchBox.value = ""; searchBox.blur(); if (searchQ) { searchQ = ""; loadGrid().catch(showError); } }
  };
  searchBox.onsearch = () => { if (!searchBox.value && searchQ) { searchQ = ""; loadGrid().catch(showError); } }; // the x button
  const counters = el("span", { className: "muted counters" });
  let chapterProject = null;
  refreshCounts = () => chapterProject && loadChapters(chapterProject);
  const loadChapters = async (p) => {
    chapterProject = p;
    const chapters = await api(`/projects/${id}/chapters`);
    const total = (k) => chapters.reduce((n, c) => n + c[k], 0);
    const all = total("photo_count"), kept = total("kept_count"), rejected = total("rejected_count");
    counters.textContent = `${all} photos · ${kept} kept · ${rejected} rejected · ${all - kept - rejected} unreviewed`;
    if (chapterId && !chapters.some((c) => c.id === chapterId)) chapterId = null;
    const gap = el("input", { type: "number", min: 1, value: p.chapter_gap_minutes, title: "Minutes of quiet that start a new chapter" });
    gap.onchange = async () => {
      if (!(gap.value >= 1)) return;
      const np = await api(`/projects/${id}`, jsonBody("PATCH", { chapter_gap_minutes: Number(gap.value) }));
      await loadChapters(np);
      await loadGrid();
    };
    const entry = (c) => {
      const name = c ? c.title : "All photos";
      const li = el("li", { className: (c ? c.id : null) === chapterId ? "active" : "" },
        el("a", { href: "#", textContent: name, onclick: async (ev) => {
          ev.preventDefault();
          chapterId = c ? c.id : null;
          await loadChapters(p);
          await loadGrid();
        } }));
      if (c) {
        li.append(el("div", { className: "muted", textContent: `${c.photo_count} photos, ${c.kept_count} kept` }),
          el("button", { className: "link", textContent: "rename", onclick: async () => {
            const t = prompt("Chapter title (blank resets)", c.user_title || c.title);
            if (t === null) return;
            await api(`/chapters/${c.id}`, jsonBody("PATCH", { user_title: t }));
            await loadChapters(p);
          } }));
      }
      return li;
    };
    side.replaceChildren(el("label", {}, "Gap (min) ", gap), el("ul", {}, entry(null), ...chapters.map(entry)));
  };
  const render = async () => {
    const p = await api(`/projects/${id}`);
    head.textContent = p.name;
    status.replaceChildren(summaryView(p));
    await loadChapters(p);
    await loadGrid();
  };
  const indexBox = el("div", { className: "indexbox" });
  const indexMsg = el("p", { className: "error" });
  const indexBtn = el("button", { textContent: "Index photos", title: "Embed previews for search and duplicate groups" });
  const trackIndex = async (indexJob) => {
    const bar = el("progress", { max: 1, value: 0 });
    const label = el("span", { className: "muted" });
    const stop = el("button", { className: "link", textContent: "cancel", onclick: () => api(`/jobs/${indexJob}/cancel`, { method: "POST" }) });
    indexBox.replaceChildren(bar, label, " ", stop, indexMsg);
    const poll = async () => {
      const j = await api(`/jobs/${indexJob}`);
      bar.max = j.total || 1;
      bar.value = j.done;
      label.textContent = ` Indexing ${j.status}: ${j.done}/${j.total}` + (j.failures.length ? `, ${j.failures.length} failed` : "");
      if (["queued", "running"].includes(j.status)) {
        indexTimer = setTimeout(() => poll().catch(showError), 500);
        return;
      }
      stop.remove();
      if (j.status === "done") await loadGrid();
      indexBtn.disabled = false;
      indexBox.append(" ", indexBtn);
      if (j.status !== "done") indexMsg.textContent = j.failures.length ? j.failures[j.failures.length - 1].error : `Indexing ${j.status}.`;
    };
    await poll();
  };
  indexBtn.onclick = async () => {
    indexBtn.disabled = true;
    indexMsg.textContent = "";
    try {
      await trackIndex((await api(`/projects/${id}/index`, { method: "POST" })).job_id);
    } catch (e) {
      indexMsg.textContent = e.message;
      indexBtn.disabled = false;
    }
  };
  indexBox.append(indexBtn, indexMsg);
  const viewBtn = el("button", { title: "Best: one tile per duplicate group. All: every photo." });
  const syncView = () => { viewBtn.textContent = view === "best" ? "View: Best" : "View: All"; };
  viewBtn.onclick = () => { view = view === "best" ? "all" : "best"; syncView(); renderGrid(); };
  syncView();
  const adv = el("input", { type: "checkbox", checked: autoAdvance, onchange: () => { autoAdvance = adv.checked; } });
  const filterSel = el("select", { title: "Show photos by review state", onchange: () => { filter = filterSel.value; renderGrid(); } },
    ...[["all", "All"], ["unreviewed", "Unreviewed"], ["keep", "Kept"], ["reject", "Rejected"]]
      .map(([v, t]) => el("option", { value: v, textContent: t, selected: v === filter })));
  indexBox.append(" ", searchBox, " ", searchMsg, " ", filterSel, " ", counters, " ", viewBtn, " ", el("label", { title: "Move to the next photo after P or X" }, adv, " Auto-advance"));
  const exportMsg = el("div");
  const runExport = async (path, body, label) => {
    exportMsg.replaceChildren(el("span", { className: "muted", textContent: `${label}…` }));
    try {
      const { job_id } = await api(path, body ? jsonBody("POST", body) : { method: "POST" });
      const poll = async () => {
        const j = await api(`/jobs/${job_id}`);
        if (["queued", "running"].includes(j.status)) {
          exportMsg.firstChild.textContent = `${label}: ${j.done}/${j.total}…`;
          indexTimer = setTimeout(() => poll().catch(showError), 500);
          return;
        }
        const fails = j.failures;
        exportMsg.replaceChildren(
          el("p", { className: j.status === "done" ? "" : "error", textContent: `${label} ${j.status}: ${j.total - fails.length} written, ${fails.length} skipped.` }),
          el("ul", {}, ...fails.map((f) => el("li", { className: "muted", textContent: f.item ? `${f.item}: ${f.error}` : f.error }))));
      };
      await poll();
    } catch (e) {
      exportMsg.replaceChildren(el("p", { className: "error", textContent: e.message }));
    }
  };
  const dest = el("input", { placeholder: "Destination folder for copy", size: 30 });
  const perChapter = el("input", { type: "checkbox" });
  const exportBox = el("details", { className: "exportbox" },
    el("summary", { textContent: "Export" }),
    el("p", {}, el("button", { textContent: "Write XMP sidecars", title: "Keep/reject/stars for Lightroom or darktable (RAW only)", onclick: () => runExport(`/projects/${id}/export/xmp`, null, "XMP export") })),
    el("p", {}, dest, " ", el("label", {}, perChapter, " One folder per chapter"), " ",
      el("button", { textContent: "Copy kept photos", onclick: () => runExport(`/projects/${id}/export/copy`, { destination: dest.value, per_chapter: perChapter.checked }, "Copy export") })),
    exportMsg);
  app.append(indexBox, exportBox, el("div", { className: "layout" }, side, grid));
  if (!jobId) return render();
  const bar = el("progress", { max: 1, value: 0 });
  const label = el("p", { className: "muted" });
  status.replaceChildren(bar, label);
  const tick = async () => {
    const j = await api(`/jobs/${jobId}`);
    bar.max = j.total || 1;
    bar.value = j.done;
    label.textContent = `${j.status}: ${j.done}/${j.total}`;
    if (["queued", "running"].includes(j.status)) {
      pollTimer = setTimeout(() => tick().catch(showError), 500);
    } else {
      await render();
      if (j.status !== "done") status.prepend(el("p", { className: "error", textContent: `Import ${j.status}.` + (j.status === "failed" && j.failures.length ? ` ${j.failures[j.failures.length - 1].error}` : "") }));
    }
  };
  head.textContent = "Importing…";
  await tick();
}

let photos = [];
let current = -1; // overlay index, -1 = closed
let selected = 0; // grid selection
let autoAdvance = true;
let filter = "all";
let searchQ = ""; // active search: grid shows ranked hits, ungrouped
let refreshCounts = () => {};
const undoStack = [];
let cells = [];
const overlay = el("div", { className: "overlay", hidden: true });
const bigImg = el("img");
const caption = el("div", { className: "caption" });
overlay.append(bigImg, caption);
overlay.onclick = () => openPreview(-1);
document.body.append(overlay);

const stars = (n) => "★".repeat(n);

function captionText(p) {
  return `${p.filename}  ${p.capture_time || ""}${p.time_source === "mtime" ? "  (file time, not EXIF)" : ""}  ${p.status || ""} ${stars(p.stars)}`;
}

function select(i) {
  selected = Math.min(Math.max(i, 0), photos.length - 1);
  cells.forEach((c, k) => c.classList.toggle("sel", k === selected));
  cells[selected]?.scrollIntoView({ block: "nearest" });
}

function openPreview(i) {
  if (i < 0 || i >= photos.length) {
    current = -1;
    overlay.hidden = true;
    return;
  }
  current = i;
  select(i);
  const p = photos[i];
  bigImg.src = `/api/photos/${p.id}/preview`;
  caption.textContent = captionText(p);
  overlay.hidden = false;
}

function paintCell(i) {
  const p = photos[i];
  const cell = cells[i];
  cell.classList.toggle("keep", p.status === "keep");
  cell.classList.toggle("reject", p.status === "reject");
  cell.querySelector(".stars")?.remove();
  if (p.stars) cell.append(el("span", { className: "stars", textContent: stars(p.stars) }));
  if (current === i) caption.textContent = captionText(p);
}

async function save(p, next) {
  const old = { status: p.status, stars: p.stars };
  const paint = () => { const i = photos.indexOf(p); if (i >= 0) paintCell(i); };
  Object.assign(p, next); // optimistic; same object lives in allPhotos
  paint();
  try {
    await api(`/photos/${p.id}/decision`, jsonBody("PUT", next));
    refreshCounts();
    return old;
  } catch (e) {
    Object.assign(p, old);
    paint();
    alert(`Could not save decision: ${e.message}`);
    return null;
  }
}

async function decide(change) {
  const p = photos[selected];
  if (!p) return;
  const old = await save(p, { status: p.status, stars: p.stars, ...change });
  if (old) undoStack.push({ p, old });
}

async function undo() {
  const last = undoStack.pop();
  if (last) await save(allPhotos.find((q) => q.id === last.p.id) || last.p, last.old); // grid may have reloaded
}

let allPhotos = [];
let gridEl = null;
let view = "best";
const expanded = new Set();

const matchesFilter = (p) =>
  filter === "all" || (filter === "unreviewed" ? !p.status : p.status === filter);

function visiblePhotos() {
  return groupedPhotos().filter(matchesFilter);
}

function groupedPhotos() {
  if (view === "all" || searchQ) return allPhotos;
  const groups = new Map();
  for (const p of allPhotos) {
    if (!groups.has(p.group_id)) groups.set(p.group_id, []);
    groups.get(p.group_id).push(p);
  }
  const out = [];
  for (const g of groups.values()) {
    if (g.length > 1 && expanded.has(g[0].group_id)) out.push(...g);
    else out.push(g.find((p) => p.is_group_pick) || g[0]);
  }
  return out;
}

function renderGrid() {
  photos = visiblePhotos();
  current = -1;
  overlay.hidden = true;
  const sizes = new Map();
  for (const p of allPhotos) sizes.set(p.group_id, (sizes.get(p.group_id) || 0) + 1);
  gridEl.replaceChildren(...photos.map((p, i) => {
    const img = el("img", { loading: "lazy", alt: p.filename, src: `/api/photos/${p.id}/thumb` });
    const cell = el("div", { className: "cell" + (view === "best" && !searchQ && expanded.has(p.group_id) && p.is_group_pick ? " pick" : "") }, img);
    if (p.time_source === "mtime") cell.append(el("span", { className: "badge", title: "No EXIF time: using file modified time", textContent: "!" }));
    const n = sizes.get(p.group_id);
    if (view === "best" && !searchQ && n > 1 && (p.is_group_pick || expanded.has(p.group_id))) {
      const open = expanded.has(p.group_id);
      cell.append(el("button", {
        className: "count",
        title: open ? "Collapse group" : `Expand group of ${n}`,
        textContent: String(n),
        onclick: (ev) => {
          ev.stopPropagation();
          if (open) expanded.delete(p.group_id);
          else expanded.add(p.group_id);
          renderGrid();
        },
      }));
    }
    cell.onclick = () => openPreview(i);
    return cell;
  }));
  cells = [...gridEl.children];
  photos.forEach((_, i) => paintCell(i));
  select(selected);
}

function showGrid(grid, list) {
  gridEl = grid;
  allPhotos = list;
  renderGrid();
}

document.addEventListener("keydown", (e) => {
  const box = document.getElementById("search");
  if (e.key === "/" && box && !e.target.matches("input, textarea")) {
    box.focus();
    e.preventDefault();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.target.matches("input, textarea")) {
    undo();
    e.preventDefault();
    return;
  }
  if (!photos.length || e.target.matches("input, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
  const open = current >= 0;
  const move = (i) => (open ? openPreview(Math.min(Math.max(i, 0), photos.length - 1)) : select(i));
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
  const key = e.key.toLowerCase();
  if (step !== undefined) move(selected + step);
  else if (e.key === "Enter" || e.key === " ") openPreview(open ? -1 : selected);
  else if (e.key === "Escape") openPreview(-1);
  else if (key === "p" || key === "x") {
    decide({ status: key === "p" ? "keep" : "reject" });
    if (autoAdvance) move(selected + 1);
  } else if (key === "u") decide({ status: null });
  else if (/^[0-5]$/.test(e.key)) decide({ stars: Number(e.key) });
  else return;
  e.preventDefault();
});

function showError(e) {
  app.replaceChildren(el("p", { className: "error", textContent: e.message }));
}

function route() {
  clearTimeout(pollTimer);
  clearTimeout(indexTimer);
  photos = [];
  allPhotos = [];
  selected = 0;
  expanded.clear();
  undoStack.length = 0;
  filter = "all";
  searchQ = "";
  refreshCounts = () => {};
  openPreview(-1);
  const m = location.hash.match(/^#\/p\/([^/]+)(?:\/([^/]+))?$/);
  (m ? showProject(m[1], m[2]) : showList()).catch(showError);
}

window.addEventListener("hashchange", route);
route();
