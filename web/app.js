const app = document.getElementById("app");

async function api(path, opts) {
  const res = await fetch("/api" + path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

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
  if (s.skipped.length) {
    const ul = el("ul");
    for (const k of s.skipped) ul.append(el("li", { textContent: `${k.path}: ${k.reason}` }));
    box.append(el("h3", { textContent: "Skipped files" }), ul);
  }
  return box;
}

let pollTimer = null;

async function showProject(id, jobId) {
  const head = el("h2", { textContent: "Loading…" });
  const status = el("div");
  app.replaceChildren(head, status);
  const grid = el("div", { className: "grid" });
  const render = async () => {
    const p = await api(`/projects/${id}`);
    head.textContent = p.name;
    status.replaceChildren(summaryView(p));
    showGrid(grid, await api(`/projects/${id}/photos`));
  };
  app.append(grid);
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
      if (j.status !== "done") status.prepend(el("p", { className: "error", textContent: `Import ${j.status}.` }));
    }
  };
  head.textContent = "Importing…";
  await tick();
}

let photos = [];
let current = -1;
const overlay = el("div", { className: "overlay", hidden: true });
const bigImg = el("img");
const caption = el("div", { className: "caption" });
overlay.append(bigImg, caption);
overlay.onclick = () => openPreview(-1);
document.body.append(overlay);

function openPreview(i) {
  if (i < 0 || i >= photos.length) {
    current = -1;
    overlay.hidden = true;
    return;
  }
  current = i;
  const p = photos[i];
  bigImg.src = `/api/photos/${p.id}/preview`;
  caption.textContent = `${p.filename}  ${p.capture_time || ""}${p.time_source === "mtime" ? "  (file time, not EXIF)" : ""}`;
  overlay.hidden = false;
}

function showGrid(grid, list) {
  photos = list;
  current = -1;
  overlay.hidden = true;
  grid.replaceChildren(...list.map((p, i) => {
    const img = el("img", { loading: "lazy", alt: p.filename, src: `/api/photos/${p.id}/thumb` });
    const cell = el("div", { className: "cell" }, img);
    if (p.time_source === "mtime") cell.append(el("span", { className: "badge", title: "No EXIF time: using file modified time", textContent: "!" }));
    cell.onclick = () => openPreview(i);
    return cell;
  }));
}

document.addEventListener("keydown", (e) => {
  if (!photos.length || e.target.matches("input, textarea")) return;
  if (current < 0) {
    if (e.key === "Enter") openPreview(0);
    return;
  }
  const next = { ArrowRight: current + 1, ArrowDown: current + 1, ArrowLeft: current - 1, ArrowUp: current - 1 }[e.key];
  if (next !== undefined) openPreview(Math.min(Math.max(next, 0), photos.length - 1));
  else if (e.key === "Escape" || e.key === "Enter" || e.key === " ") openPreview(-1);
  else return;
  e.preventDefault();
});

function showError(e) {
  app.replaceChildren(el("p", { className: "error", textContent: e.message }));
}

function route() {
  clearTimeout(pollTimer);
  photos = [];
  openPreview(-1);
  const m = location.hash.match(/^#\/p\/([^/]+)(?:\/([^/]+))?$/);
  (m ? showProject(m[1], m[2]) : showList()).catch(showError);
}

window.addEventListener("hashchange", route);
route();
