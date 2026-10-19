const app = document.getElementById("app");
const barSlot = document.getElementById("bar-slot");
const toasts = document.getElementById("toasts");
const topbar = document.querySelector(".topbar");
new ResizeObserver(() => document.documentElement.style.setProperty("--bar-h", topbar.offsetHeight + "px")).observe(topbar);

async function api(path, opts) {
  const res = await fetch("/api" + path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

const jsonBody = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

function el(tag, props = {}, ...kids) {
  const { attrs, ...rest } = props;
  const e = Object.assign(document.createElement(tag), rest);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  e.append(...kids);
  return e;
}

/* ---------- icons, theme, toasts ---------- */

const ICONS = {
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  chevron: '<path d="M6 9l6 6 6-6"/>',
  star: '<path stroke="none" fill="currentColor" d="M12 3.2l2.7 5.6 6.1.8-4.5 4.3 1.1 6.1-5.4-3-5.4 3 1.1-6.1-4.5-4.3 6.1-.8z"/>',
};

const icon = (name, className = "") => el("span", {
  className: ("ic " + className).trim(),
  innerHTML: `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`,
});

const themeBtn = document.getElementById("theme");
function applyTheme(theme, save) {
  const root = document.documentElement;
  if (save) {
    root.classList.add("theming");
    setTimeout(() => root.classList.remove("theming"), 450);
  }
  root.dataset.theme = theme;
  const next = theme === "dark" ? "light" : "dark";
  themeBtn.replaceChildren(icon(theme === "dark" ? "sun" : "moon"));
  themeBtn.title = themeBtn.ariaLabel = `Switch to ${next} mode`;
  if (save) try { localStorage.setItem("mythicull-theme", theme); } catch (e) { /* private mode: theme just won't persist */ }
}
themeBtn.onclick = () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true);
applyTheme(document.documentElement.dataset.theme, false);

function toast(message, kind = "info") {
  const t = el("div", { className: "toast " + kind, attrs: kind === "error" ? { role: "alert" } : {} }, el("span", { textContent: message }));
  toasts.append(t);
  const close = () => {
    t.classList.add("out");
    t.addEventListener("animationend", () => t.remove(), { once: true });
    setTimeout(() => t.remove(), 600);
  };
  setTimeout(close, kind === "error" ? 7000 : 4000);
}

/* ---------- custom controls ---------- */

function seg(label, options, value, onChange, inBar = false) {
  let cur = value;
  const ind = el("span", { className: "seg-ind" });
  const root = el("div", { className: "seg" + (inBar ? " in-bar" : ""), attrs: { role: "radiogroup", "aria-label": label } }, ind);
  const btns = options.map(([v, text, tip]) => el("button", { type: "button", className: "seg-b", textContent: text, title: tip || "", attrs: { role: "radio" }, onclick: () => pick(v) }));
  const place = () => {
    const i = options.findIndex((o) => o[0] === cur);
    const b = btns[i];
    if (!b || !b.offsetWidth) return;
    ind.style.width = b.offsetWidth + "px";
    ind.style.transform = `translateX(${b.offsetLeft}px)`;
  };
  const paint = () => {
    btns.forEach((b, i) => {
      const on = options[i][0] === cur;
      b.classList.toggle("on", on);
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    place();
  };
  const pick = (v) => {
    if (v === cur) return;
    cur = v;
    paint();
    onChange(v);
  };
  root.onkeydown = (e) => {
    const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (d === undefined) return;
    const n = (options.findIndex((o) => o[0] === cur) + d + options.length) % options.length;
    pick(options[n][0]);
    btns[n].focus();
    e.preventDefault();
    e.stopPropagation();
  };
  root.append(...btns);
  new ResizeObserver(place).observe(root);
  paint();
  return root;
}

function toggle(text, checked, onChange, title = "") {
  const b = el("button", { type: "button", className: "switch", title, attrs: { role: "switch", "aria-checked": String(checked) } },
    el("span", { className: "switch-track" }), el("span", { textContent: text }));
  b.onclick = () => {
    const on = b.getAttribute("aria-checked") !== "true";
    b.setAttribute("aria-checked", String(on));
    onChange(on);
  };
  return b;
}

function stepper({ value, min = -Infinity, max = Infinity, step = 1, title = "", onCommit }) {
  let last = value;
  const input = el("input", { value: String(value), title, attrs: { inputmode: "numeric", "aria-label": title } });
  const commit = (raw) => {
    const n = Math.min(max, Math.max(min, Math.round(Number(raw))));
    if (!Number.isFinite(n)) { input.value = String(last); return; }
    input.value = String(n);
    if (n !== last) { last = n; onCommit(n); }
  };
  const bump = (d) => commit((Number(input.value) || 0) + d * step);
  input.onchange = () => commit(input.value);
  input.onkeydown = (e) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") { bump(e.key === "ArrowUp" ? 1 : -1); e.preventDefault(); }
  };
  return el("div", { className: "stepper" },
    el("button", { type: "button", title: "Decrease", attrs: { "aria-label": "Decrease" }, onclick: () => bump(-1) }, icon("minus")),
    input,
    el("button", { type: "button", title: "Increase", attrs: { "aria-label": "Increase" }, onclick: () => bump(1) }, icon("plus")));
}

function slider({ value, min = 0, max = 1, step = 0.05, title = "", onCommit }) {
  let cur = value, last = value, timer = null;
  const fill = el("i", { className: "slider-fill" });
  const thumb = el("i", { className: "slider-thumb" });
  const root = el("div", { className: "slider", title, attrs: { role: "slider", tabindex: "0", "aria-label": title, "aria-valuemin": min, "aria-valuemax": max, "aria-valuestep": step } },
    el("div", { className: "slider-track" }, fill), thumb);
  const paint = () => {
    const pct = ((cur - min) / (max - min)) * 100;
    fill.style.width = pct + "%";
    thumb.style.left = pct + "%";
    root.setAttribute("aria-valuenow", cur);
    root.setAttribute("aria-valuetext", Math.round(pct) + "%");
  };
  const set = (v) => { cur = Number(Math.min(max, Math.max(min, Math.round(v / step) * step)).toFixed(4)); paint(); };
  const commit = () => { clearTimeout(timer); if (cur !== last) { last = cur; onCommit(cur); } };
  const fromPointer = (e) => {
    const r = root.getBoundingClientRect();
    set(min + ((e.clientX - r.left) / r.width) * (max - min));
  };
  root.onpointerdown = (e) => { root.setPointerCapture(e.pointerId); root.classList.add("drag"); root.focus(); fromPointer(e); };
  root.onpointermove = (e) => { if (root.classList.contains("drag")) fromPointer(e); };
  root.onpointerup = () => { root.classList.remove("drag"); commit(); };
  root.onkeydown = (e) => {
    const d = { ArrowRight: step, ArrowUp: step, ArrowLeft: -step, ArrowDown: -step, PageUp: step * 4, PageDown: -step * 4 }[e.key];
    if (e.key === "Home") set(min);
    else if (e.key === "End") set(max);
    else if (d !== undefined) set(cur + d);
    else return;
    clearTimeout(timer);
    timer = setTimeout(commit, 400);
    e.preventDefault();
  };
  root.onblur = commit;
  paint();
  return root;
}

function progressBar() {
  const fill = el("i");
  const root = el("div", { className: "bar", attrs: { role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "1", "aria-valuenow": "0" } }, fill);
  return {
    root,
    set(done, total, running = true) {
      const frac = total ? Math.min(1, done / total) : 0;
      fill.style.transform = `scaleX(${frac})`;
      root.setAttribute("aria-valuenow", frac.toFixed(3));
      root.classList.toggle("run", running);
    },
  };
}

function panel(label, ...content) {
  const body = el("div", { className: "panel-body" }, ...content);
  const wrap = el("div", { className: "panel" }, el("div", { className: "panel-inner" }, body));
  const head = el("button", { type: "button", className: "panel-head", attrs: { "aria-expanded": "false" } }, label, icon("chevron"));
  head.onclick = () => {
    const open = !wrap.classList.contains("open");
    wrap.classList.toggle("open", open);
    head.setAttribute("aria-expanded", String(open));
  };
  return { head, wrap };
}

function field(label, input) {
  input.classList.add("input");
  input.setAttribute("aria-label", label);
  return el("label", { className: "field" }, el("span", { textContent: label }), input);
}

function folderField(label, purpose, input) {
  input.readOnly = true;
  input.placeholder = "No folder selected";
  const error = el("p", { className: "error", attrs: { role: "alert" } });
  const manual = el("button", { type: "button", className: "btn text", textContent: "Enter path manually", hidden: true, onclick: () => {
    input.readOnly = false;
    input.focus();
  } });
  const choose = el("button", { type: "button", className: "btn", textContent: "Choose folder…", attrs: { "aria-label": `Choose ${label.toLowerCase()}` }, onclick: async () => {
    choose.disabled = true;
    choose.textContent = "Choosing…";
    error.textContent = "";
    try {
      const out = await api("/folders/choose", jsonBody("POST", { purpose }));
      if (out.folder) {
        input.value = out.folder;
        input.readOnly = true;
        manual.hidden = true;
      }
    } catch (e) {
      error.textContent = e.message;
      manual.hidden = false;
    } finally {
      choose.disabled = false;
      choose.textContent = "Choose folder…";
    }
  } });
  return el("div", { className: "field folder-field" }, field(label, input), choose, error, manual);
}

function roll(node, value) {
  const next = String(value);
  const prev = node.dataset.v;
  if (prev === next) return;
  node.dataset.v = next;
  const old = prev === undefined ? [] : [...prev];
  node.replaceChildren(...[...next].map((d, i) => {
    const changed = prev !== undefined && old[old.length - next.length + i] !== d;
    return el("i", { className: changed ? "d flip" : "d", textContent: d, style: `--k:${next.length - 1 - i}`, attrs: { "aria-hidden": "true" } });
  }));
}

/* ---------- project list ---------- */

async function showList() {
  const projects = await api("/projects");
  const msg = el("p", { className: "error", attrs: { role: "alert" } });
  const name = el("input", { placeholder: "Project name" });
  const folder = el("input");
  const form = el("form", { className: "newform", noValidate: true }, field("Project name", name), folderField("Photo folder", "import", folder), el("button", { className: "btn primary", textContent: "Create and import" }), msg);
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    if (!name.value.trim() || !folder.value.trim()) {
      msg.textContent = "Enter a project name and choose a photo folder.";
      form.classList.remove("shake");
      void form.offsetWidth;
      form.classList.add("shake");
      return;
    }
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
  const list = el("ul", { className: "rolls" });
  projects.forEach((p, i) => {
    list.append(el("li", { style: `--d:${Math.min(i, 12)}` },
      el("a", { className: "roll", href: `#/p/${p.id}` },
        el("span", { className: "roll-no", textContent: String(i + 1).padStart(2, "0") }),
        el("span", {}, el("strong", { className: "roll-name", textContent: p.name }), el("span", { className: "roll-folder", textContent: p.folder })),
        el("span", { className: "roll-count" }, el("b", { textContent: String(p.photo_count) }), "photos"))));
  });
  if (!projects.length) list.append(el("li", { className: "empty", textContent: "No projects yet." }));
  app.replaceChildren(el("div", { className: "view home" },
    el("section", {}, el("h2", { textContent: "New project" }), form),
    el("section", {}, el("h2", { textContent: "Projects" }), list)));
}

function summaryView(p) {
  const s = p.last_import;
  const box = el("div", { className: "summary" }, el("p", { textContent: `${p.photo_count} photos in ${p.folder}` }));
  if (!s) {
    box.append(el("p", { className: "muted", textContent: "No import summary yet (import still running or interrupted)." }));
    return box;
  }
  box.append(el("p", { className: "muted", textContent: `Found ${s.found}, imported ${s.imported}, already present ${s.already_present}, skipped ${s.skipped.length}.` }));
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

/* ---------- project workspace ---------- */

let pollTimer = null;
let indexTimer = null;

async function showProject(id, jobId) {
  const head = el("h2", { textContent: "Loading…" });
  const status = el("div");
  const page = el("div", { className: "view" }, el("div", { className: "proj-head" }, head, status));
  app.replaceChildren(page);
  const grid = el("div", { className: "grid", attrs: { role: "listbox", "aria-label": "Photos" } });
  const side = el("nav", { className: "sidebar", attrs: { "aria-label": "Chapters and settings" } });
  let chapterId = null;
  const searchMsg = el("span", { className: "hit muted" });
  const searchBox = el("input", { type: "text", id: "search", placeholder: "Search photos (/)", title: "Plain-English search, e.g. people dancing", attrs: { "aria-label": "Search photos" } });
  const clearBtn = el("button", { type: "button", className: "clear", title: "Clear search", attrs: { "aria-label": "Clear search" } }, icon("close"));
  const searchWrap = el("div", { className: "search" }, icon("search"), searchBox, clearBtn);
  const syncClear = () => searchWrap.classList.toggle("has", !!searchBox.value);
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
      syncClear();
      await loadGrid();
      searchMsg.textContent = e.message;
    }
  };
  const clearSearch = () => { searchBox.value = ""; syncClear(); if (searchQ) { searchQ = ""; loadGrid().catch(showError); } };
  searchBox.oninput = syncClear;
  searchBox.onkeydown = (ev) => {
    if (ev.key === "Enter") { searchQ = searchBox.value; loadGrid().catch(showError); }
    else if (ev.key === "Escape") { clearSearch(); searchBox.blur(); }
  };
  clearBtn.onclick = () => { clearSearch(); searchBox.focus(); };
  const stat = (label) => ({ n: el("b"), node: el("span", { className: "stat" }, "", label) });
  const sAll = stat(" photos"), sKept = stat(" kept"), sRej = stat(" rejected"), sNew = stat(" unreviewed");
  const counters = el("div", { className: "counters", attrs: { role: "group" } });
  [sAll, sKept, sRej, sNew].forEach((s) => { s.node.prepend(s.n); counters.append(s.node); });
  let chapterProject = null;
  let rcTimer = null;
  refreshCounts = () => { clearTimeout(rcTimer); rcTimer = setTimeout(() => chapterProject && loadChapters(chapterProject), 250); };
  const loadChapters = async (p) => {
    chapterProject = p;
    const chapters = await api(`/projects/${id}/chapters`);
    const cameras = await api(`/projects/${id}/cameras`);
    const total = (k) => chapters.reduce((n, c) => n + c[k], 0);
    const all = total("photo_count"), kept = total("kept_count"), rejected = total("rejected_count");
    roll(sAll.n, all); roll(sKept.n, kept); roll(sRej.n, rejected); roll(sNew.n, all - kept - rejected);
    counters.setAttribute("aria-label", `${all} photos, ${kept} kept, ${rejected} rejected, ${all - kept - rejected} unreviewed`);
    if (chapterId && !chapters.some((c) => c.id === chapterId)) chapterId = null;
    const gap = stepper({ value: p.chapter_gap_minutes, min: 1, title: "Minutes of quiet that start a new chapter", onCommit: async (n) => {
      try {
        const np = await api(`/projects/${id}`, jsonBody("PATCH", { chapter_gap_minutes: n }));
        await loadChapters(np);
        await loadGrid();
      } catch (e) {
        toast(e.message, "error");
        await loadChapters(await api(`/projects/${id}`));
      }
    } });
    const patchVibe = async (body) => {
      try {
        await loadChapters(await api(`/projects/${id}`, jsonBody("PATCH", body)));
        await loadGrid();
      } catch (e) {
        toast(e.message, "error");
        await loadChapters(await api(`/projects/${id}`)); // put the controls back to the saved values
      }
    };
    const vibe = el("input", { type: "text", value: p.vibe_prompt || "", placeholder: "e.g. candid laughter", title: "Group picks lean toward photos matching this text" });
    vibe.onchange = () => patchVibe({ vibe_prompt: vibe.value });
    const weight = slider({ value: p.vibe_weight, title: "Left: sharpest photo. Right: best match for the vibe text", onCommit: (v) => patchVibe({ vibe_weight: v }) });
    const cameraRows = cameras.length < 2 ? [] : [el("div", { className: "label", textContent: "Camera clocks (seconds to add)" }),
      ...cameras.map((c) => el("div", { className: "setting" },
        el("span", { textContent: `${c.camera_model || "Unknown camera"} (${c.photo_count})` }),
        stepper({ value: c.offset_seconds, step: 1, title: "Seconds to add to this camera's clock", onCommit: async (n) => {
          try {
            await api(`/projects/${id}/cameras`, jsonBody("PUT", { camera_model: c.camera_model, offset_seconds: n }));
            await loadChapters(p);
            await loadGrid();
          } catch (e) {
            toast(e.message, "error");
            await loadChapters(p); // put the box back to the saved value
          }
        } })))];
    const entry = (c, i) => {
      const name = c ? c.title : "All photos";
      const li = el("li", { className: (c ? c.id : null) === chapterId ? "active" : "" });
      const titleEl = el("span", { className: "ch-title", textContent: name });
      li.append(el("button", { type: "button", className: "ch-main", attrs: { "aria-current": li.className ? "true" : "false" }, onclick: async () => {
        chapterId = c ? c.id : null;
        await loadChapters(p);
        await loadGrid();
      } }, el("span", { className: "ch-no", textContent: c ? String(i + 1).padStart(2, "0") + "A" : "ALL" }), titleEl,
      el("span", { className: "ch-n", textContent: c ? String(c.photo_count) : String(all) })));
      if (c) {
        const meta = el("div", { className: "ch-meta" }, el("span", { textContent: `${c.photo_count} photos, ${c.kept_count} kept` }));
        if (c.suggested_title && !c.user_title) {
          meta.append(el("button", { type: "button", className: "btn text", textContent: `Use "${c.suggested_title}"`, title: "Suggested from the photos; ignore it to keep the current name", onclick: async () => {
            await api(`/chapters/${c.id}`, jsonBody("PATCH", { user_title: c.suggested_title }));
            await loadChapters(p);
          } }));
        }
        const renameBtn = el("button", { type: "button", className: "btn text", textContent: "rename" });
        renameBtn.onclick = () => {
          const input = el("input", { className: "input rename", value: c.user_title || c.title, attrs: { "aria-label": "Chapter title (blank resets)" } });
          let done = false;
          const finish = async (save) => {
            if (done) return;
            done = true;
            if (!save) { input.replaceWith(meta); return; }
            try {
              await api(`/chapters/${c.id}`, jsonBody("PATCH", { user_title: input.value }));
            } catch (e) {
              toast(e.message, "error");
            }
            await loadChapters(p);
          };
          input.onkeydown = (ev) => {
            if (ev.key === "Enter") finish(true);
            else if (ev.key === "Escape") finish(false);
          };
          input.onblur = () => finish(false);
          meta.replaceWith(input);
          input.focus();
          input.select();
        };
        meta.append(renameBtn);
        li.append(meta);
      }
      return li;
    };
    side.replaceChildren(
      el("div", { className: "setting" }, el("span", { className: "label", textContent: "Gap (min)" }), gap),
      el("label", { className: "setting" }, el("span", { className: "label", textContent: "Vibe" }), Object.assign(vibe, { className: "input" })),
      el("div", { className: "setting" }, el("span", { className: "label", textContent: "Pick weighting" }), weight,
        el("div", { className: "slider-ends" }, el("span", { textContent: "Sharp" }), el("span", { textContent: "Vibe" }))),
      ...cameraRows,
      el("ul", { className: "chapters" }, entry(null, 0), ...chapters.map((c, i) => entry(c, i))));
  };
  const render = async () => {
    const p = await api(`/projects/${id}`);
    head.textContent = p.name;
    status.replaceChildren(summaryView(p));
    await loadChapters(p);
    await loadGrid();
  };
  const indexBox = el("div", { className: "indexbox" });
  const indexMsg = el("p", { className: "error", attrs: { role: "alert" } });
  const indexBtn = el("button", { type: "button", className: "btn primary", textContent: "Index photos", title: "Embed previews for search and duplicate groups" });
  const mb = (n) => `${Math.round(n / 1048576)} MB`;
  const trackIndex = async (indexJob, downloading = false) => {
    const bar = progressBar();
    const label = el("span", { className: "muted mono" });
    const stop = el("button", { type: "button", className: "btn text", textContent: "cancel", onclick: () => api(`/jobs/${indexJob}/cancel`, { method: "POST" }) });
    indexBox.replaceChildren(bar.root, label, stop, indexMsg);
    const poll = async () => {
      const j = await api(`/jobs/${indexJob}`);
      const running = ["queued", "running"].includes(j.status);
      bar.set(j.done, j.total || 1, running);
      label.textContent = downloading
        ? `Downloading search model (one time) ${j.status}: ${mb(j.done)}/${mb(j.total)}`
        : `Indexing ${j.status}: ${j.done}/${j.total}` + (j.failures.length ? `, ${j.failures.length} failed` : "");
      if (running) {
        indexTimer = setTimeout(() => poll().catch(showError), 500);
        return;
      }
      stop.remove();
      if (j.status === "done" && !downloading) await loadGrid();
      indexBtn.disabled = false;
      indexBox.append(indexBtn);
      if (j.status !== "done") indexMsg.textContent = j.failures.length ? j.failures[j.failures.length - 1].error : `${downloading ? "Download" : "Indexing"} ${j.status}.`;
      else if (downloading) await indexBtn.onclick(); // model is local now, carry on with indexing
    };
    await poll();
  };
  indexBtn.onclick = async () => {
    indexBtn.disabled = true;
    indexMsg.textContent = "";
    try {
      if (!(await api("/model")).ready) return await trackIndex((await api("/model/download", { method: "POST" })).job_id, true);
      await trackIndex((await api(`/projects/${id}/index`, { method: "POST" })).job_id);
    } catch (e) {
      indexMsg.textContent = e.message;
      indexBtn.disabled = false;
    }
  };
  indexBox.append(indexBtn, indexMsg);
  const filterSeg = seg("Show photos by review state", [["all", "All"], ["unreviewed", "Unreviewed"], ["keep", "Kept"], ["reject", "Rejected"]], filter, (v) => { filter = v; renderGrid(); }, true);
  const viewSeg = seg("Grouping", [["best", "Best", "Best: one tile per duplicate group"], ["all", "All", "All: every photo"]], view, (v) => { view = v; renderGrid(); }, true);
  const advance = toggle("Auto-advance", autoAdvance, (on) => { autoAdvance = on; }, "Move to the next photo after P or X");
  barSlot.replaceChildren(searchWrap, filterSeg, viewSeg, advance);
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
  const dest = el("input");
  let perChapter = false;
  const exp = panel("Export",
    el("div", { className: "row" }, el("button", { type: "button", className: "btn", textContent: "Write XMP sidecars", title: "Keep/reject/stars for Lightroom or darktable (RAW only)", onclick: () => runExport(`/projects/${id}/export/xmp`, null, "XMP export") })),
    el("div", { className: "row" }, folderField("Destination folder for copy", "export", dest),
      toggle("One folder per chapter", false, (on) => { perChapter = on; }),
      el("button", { type: "button", className: "btn", textContent: "Copy kept photos", onclick: () => {
        if (!dest.value.trim()) { toast("Choose a destination folder first.", "error"); return; }
        runExport(`/projects/${id}/export/copy`, { destination: dest.value, per_chapter: perChapter }, "Copy export");
      } })),
    exportMsg);
  const sideToggle = el("button", { type: "button", className: "btn side-toggle", textContent: "Chapters and settings", attrs: { "aria-expanded": "false" } });
  sideToggle.onclick = () => { const open = side.classList.toggle("open"); sideToggle.setAttribute("aria-expanded", String(open)); };
  page.append(el("div", { className: "workbar" }, indexBox, counters, searchMsg, el("span", { className: "push" }, exp.head)), exp.wrap, sideToggle, el("div", { className: "layout" }, side, grid));
  if (!jobId) return render();
  const bar = progressBar();
  const label = el("p", { className: "muted mono" });
  status.replaceChildren(bar.root, label);
  const tick = async () => {
    const j = await api(`/jobs/${jobId}`);
    const running = ["queued", "running"].includes(j.status);
    bar.set(j.done, j.total || 1, running);
    label.textContent = `${j.status}: ${j.done}/${j.total}`;
    if (running) {
      pollTimer = setTimeout(() => tick().catch(showError), 500);
    } else {
      await render();
      if (j.status !== "done") status.prepend(el("p", { className: "error", textContent: `Import ${j.status}.` + (j.status === "failed" && j.failures.length ? ` ${j.failures[j.failures.length - 1].error}` : "") }));
    }
  };
  head.textContent = "Importing…";
  await tick();
}

/* ---------- photo grid and preview ---------- */

let photos = [];
let current = -1; // overlay index, -1 = closed
let selected = 0; // grid selection
let autoAdvance = true;
let filter = "all";
let searchQ = ""; // active search: grid shows ranked hits, ungrouped
let refreshCounts = () => {};
const undoStack = [];
let cells = [];
let enterAnim = false; // stagger tiles in only on a fresh load, not on every re-render
const overlay = el("div", { className: "overlay", attrs: { role: "dialog", "aria-modal": "true", "aria-label": "Photo preview", "aria-hidden": "true" } });
let lastFocus = null;
const bigImg = el("img", { className: "lb-img", alt: "" });
const caption = el("div", { className: "caption" });
const closeBtn = el("button", { type: "button", className: "lb-close", title: "Close preview (Esc)", attrs: { "aria-label": "Close preview" } }, icon("close"));
overlay.append(bigImg, caption, closeBtn);
overlay.onclick = () => openPreview(-1);
document.body.append(overlay);

const starsEl = (n) => el("span", { className: "stars", title: n ? `${n} star${n > 1 ? "s" : ""}` : "" }, ...Array.from({ length: n }, () => icon("star")));

function paintCaption(p, i) {
  caption.replaceChildren(
    el("span", { className: "lb-no", textContent: `${i + 1} / ${photos.length}` }),
    el("strong", { textContent: p.filename }),
    el("span", { className: "lb-time", textContent: p.capture_time || "" }),
    ...(p.time_source === "mtime" ? [el("span", { className: "lb-warn", textContent: "file time, not EXIF" })] : []),
    ...(p.status ? [el("span", { className: "chip " + p.status, textContent: p.status === "keep" ? "Keep" : "Reject" })] : []),
    starsEl(p.stars),
    el("span", { className: "lb-hint", textContent: "← → move · P keep · X reject · 0–5 stars · Esc close" }));
}

function select(i) {
  selected = Math.min(Math.max(i, 0), photos.length - 1);
  cells.forEach((c, k) => { c.classList.toggle("sel", k === selected); c.setAttribute("aria-selected", String(k === selected)); });
  cells[selected]?.scrollIntoView({ block: "nearest" });
}

function openPreview(i) {
  if (i < 0 || i >= photos.length) {
    current = -1;
    const wasOpen = overlay.classList.contains("open");
    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
    if (wasOpen && lastFocus && lastFocus !== document.body && document.contains(lastFocus)) lastFocus.focus();
    lastFocus = null;
    return;
  }
  const wasOpen = current >= 0;
  if (!wasOpen) lastFocus = document.activeElement;
  current = i;
  select(i);
  const p = photos[i];
  bigImg.src = `/api/photos/${p.id}/preview`;
  bigImg.alt = p.filename;
  if (wasOpen) {
    bigImg.classList.remove("swap");
    void bigImg.offsetWidth;
    bigImg.classList.add("swap");
  }
  paintCaption(p, i);
  overlay.classList.add("open");
  overlay.setAttribute("aria-hidden", "false");
  closeBtn.focus({ preventScroll: true });
}

function paintCell(i) {
  const p = photos[i];
  const cell = cells[i];
  const st = p.status || "";
  const was = cell.dataset.st;
  cell.classList.toggle("keep", st === "keep");
  cell.classList.toggle("reject", st === "reject");
  const mark = cell.querySelector(".mark");
  mark.className = "mark" + (st ? " " + st : "");
  mark.replaceChildren(...(st ? [icon(st === "keep" ? "check" : "close")] : []));
  mark.title = st === "keep" ? "Kept" : st === "reject" ? "Rejected" : "";
  if (was !== undefined && was !== st && st) {
    void mark.offsetWidth;
    mark.classList.add("stamp");
  }
  cell.dataset.st = st;
  const old = Number(cell.dataset.stars || 0);
  const stars = starsEl(p.stars);
  cell.querySelector(".stars").replaceWith(stars);
  if (cell.dataset.stars !== undefined && p.stars > old) stars.classList.add("pop");
  cell.dataset.stars = p.stars;
  cell.setAttribute("aria-label", `${p.filename}, ${st ? (st === "keep" ? "kept" : "rejected") : "unreviewed"}${p.stars ? `, ${p.stars} stars` : ""}`);
  if (current === i) paintCaption(p, i);
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
    toast(`Could not save decision: ${e.message}`, "error");
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
  openPreview(-1);
  const sizes = new Map();
  for (const p of allPhotos) sizes.set(p.group_id, (sizes.get(p.group_id) || 0) + 1);
  const animate = enterAnim;
  enterAnim = false;
  gridEl.replaceChildren(...photos.map((p, i) => {
    const frame = el("div", { className: "frame" }, el("img", { loading: "lazy", alt: p.filename, src: `/api/photos/${p.id}/thumb` }));
    const cell = el("div", { className: "cell" + (animate && i < 40 ? " enter" : "") + (view === "best" && !searchQ && expanded.has(p.group_id) && p.is_group_pick ? " pick" : ""), style: `--d:${i}`, attrs: { role: "option" } },
      frame,
      el("div", { className: "edge" }, el("i", { className: "dx" }), el("span", { className: "fno", textContent: `${i + 1}A` }), el("span", { className: "fname", textContent: p.filename }), el("span", { className: "mark" }), el("span", { className: "stars" })));
    if (p.time_source === "mtime") frame.append(el("span", { className: "badge", title: "No EXIF time: using file modified time", textContent: "!" }));
    const n = sizes.get(p.group_id);
    if (view === "best" && !searchQ && n > 1 && (p.is_group_pick || expanded.has(p.group_id))) {
      const open = expanded.has(p.group_id);
      frame.append(el("button", {
        type: "button",
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
  enterAnim = true;
  renderGrid();
}

document.addEventListener("keydown", (e) => {
  const t = e.target;
  const box = document.getElementById("search");
  if (e.key === "/" && box && !t.matches("input, textarea")) {
    box.focus();
    e.preventDefault();
    return;
  }
  if (t.closest("input, textarea, [role=slider]")) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    undo();
    e.preventDefault();
    return;
  }
  if (!photos.length || e.ctrlKey || e.metaKey || e.altKey) return;
  if ((e.key === "Enter" || e.key === " ") && t.closest("button, [role=radio], [role=switch]")) return; // let the focused control act
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
  app.replaceChildren(el("div", { className: "view" }, el("p", { className: "error", textContent: e.message })));
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
  barSlot.replaceChildren();
  current = -1;
  overlay.classList.remove("open");
  const m = location.hash.match(/^#\/p\/([^/]+)(?:\/([^/]+))?$/);
  (m ? showProject(m[1], m[2]) : showList()).catch(showError);
}

window.addEventListener("hashchange", route);
route();
