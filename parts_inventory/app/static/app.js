/* Parts Inventory — single-page app (no build step). */
"use strict";

// ------------------------------------------------------------------ basics
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => (n == null || n === "" ? "" : (Math.round(Number(n) * 1000) / 1000).toLocaleString());
const money = (n) => (n == null ? "" : Number(n).toLocaleString(undefined, { style: "currency", currency: "USD" }));
const haptic = (ms = 8) => { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} };
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const thumb = (f) => (f ? `thumbs/${f}` : "");
const full = (f) => (f ? `photos/${f}` : "");
const timeAgo = (ts) => {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  if (s < 86400 * 7) return Math.floor(s / 86400) + "d ago";
  return new Date(ts * 1000).toLocaleDateString();
};
const store = {
  get(k, d) { try { const v = localStorage.getItem("inv." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("inv." + k, JSON.stringify(v)); } catch (e) {} },
};

const I = {
  back: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  chev: '<svg class="chev" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  box: '<svg viewBox="0 0 24 24"><path d="M21 8 12 3 3 8v8l9 5 9-5zM12 12 3.5 7.5M12 12l8.5-4.5M12 12v9"/></svg>',
  camera: '<svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.8"/></svg>',
  image: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/></svg>',
  pin: '<svg viewBox="0 0 24 24"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
  search: '<svg class="mag" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4"/></svg>',
  link: '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
  qr: '<svg viewBox="0 0 24 24"><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 14h2M14 18h2v2M18 18h2v2h-2z"/></svg>',
  scan: '<svg viewBox="0 0 24 24"><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M7 12h10"/></svg>',
  more: '<svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>',
  star: '<svg viewBox="0 0 24 24"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
  starOn: '<svg viewBox="0 0 24 24" style="fill:#ffcc00;stroke:#ffcc00"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
  grid: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/></svg>',
  list: '<svg viewBox="0 0 24 24"><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/></svg>',
  sort: '<svg viewBox="0 0 24 24"><path d="M7 4v16M3 16l4 4 4-4M17 20V4M13 8l4-4 4 4"/></svg>',
  sparkle: '<svg viewBox="0 0 24 24"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/></svg>',
  tag: '<svg viewBox="0 0 24 24"><path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.5"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  down: '<svg viewBox="0 0 24 24"><path d="M12 4v12M6 10l6 6 6-6M4 20h16"/></svg>',
  up: '<svg viewBox="0 0 24 24"><path d="M12 20V8M6 14l6-6 6 6M4 4h16"/></svg>',
  alert: '<svg viewBox="0 0 24 24"><path d="M12 3 2 20h20zM12 10v4M12 17h.01"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3"/></svg>',
  copy: '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
  folder: '<svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
};

// ------------------------------------------------------------------ api
async function api(method, url, data) {
  const opt = { method, headers: {} };
  if (data instanceof FormData) opt.body = data;
  else if (data !== undefined) { opt.body = JSON.stringify(data); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, opt);
  let j = null;
  try { j = await r.json(); } catch (e) {}
  if (r.status === 401) { location.reload(); throw new Error("Unauthorized"); }
  if (!r.ok) { const e = new Error((j && j.error) || `Request failed (${r.status})`); e.status = r.status; e.data = j; throw e; }
  return j;
}
const GET = (u) => api("GET", u);
const POST = (u, d) => api("POST", u, d ?? {});
const PUT = (u, d) => api("PUT", u, d);
const DEL = (u) => api("DELETE", u);

const cache = { config: null, locations: null, categories: null };
async function config() { return cache.config || (cache.config = await GET("api/config")); }
async function locations(force) { if (force || !cache.locations) cache.locations = await GET("api/locations"); return cache.locations; }
async function categories(force) { if (force || !cache.categories) cache.categories = await GET("api/categories"); return cache.categories; }
const invalidate = () => { cache.locations = null; cache.categories = null; };

// ------------------------------------------------------------------ toast
let toastT;
function toast(msg, action) {
  const t = $("#toast");
  t.innerHTML = `<span>${esc(msg)}</span>` + (action ? `<button>${esc(action.label)}</button>` : "");
  if (action) $("button", t).onclick = () => { t.classList.remove("show"); action.fn(); };
  t.classList.add("show");
  clearTimeout(toastT);
  toastT = setTimeout(() => t.classList.remove("show"), action ? 4500 : 2200);
}
const fail = (e) => { console.error(e); toast(e.message || String(e)); };

// ------------------------------------------------------------------ sheets
const sheets = [];
function openSheet({ title = "", left, right, full = false, body = "", onClose } = {}) {
  const root = $("#sheet-root");
  const bd = document.createElement("div");
  bd.className = "backdrop";
  const sh = document.createElement("div");
  sh.className = "sheet" + (full ? " full" : "");
  sh.innerHTML = `<div class="grab"></div><header><div class="side l"></div><div class="title">${esc(title)}</div><div class="side r"></div></header><div class="content"></div>`;
  const content = $(".content", sh);
  if (typeof body === "string") content.innerHTML = body; else content.append(body);
  root.append(bd, sh);
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => { bd.classList.add("show"); sh.classList.add("show"); });
  let closed = false;
  const api_ = {
    el: sh, content,
    close(result) {
      if (closed) return; closed = true;
      bd.classList.remove("show"); sh.classList.remove("show");
      setTimeout(() => { bd.remove(); sh.remove(); }, 320);
      sheets.splice(sheets.indexOf(api_), 1);
      if (!sheets.length) document.body.style.overflow = "";
      onClose && onClose(result);
    },
    setButtons(l, r) {
      const mk = (b) => {
        if (!b) return "";
        const el = document.createElement("button");
        el.className = "navbtn";
        if (b.bold) el.style.fontWeight = "600";
        el.innerHTML = b.label;
        el.onclick = b.fn;
        return el;
      };
      const L = $(".side.l", sh), R = $(".side.r", sh);
      L.innerHTML = ""; R.innerHTML = "";
      const a = mk(l), b = mk(r);
      if (a) L.append(a);
      if (b) R.append(b);
      return { left: a, right: b };
    },
  };
  api_.buttons = api_.setButtons(left, right);
  bd.onclick = () => api_.close();
  // swipe down to dismiss
  let y0 = null, dy = 0;
  const startDrag = (e) => { if (content.scrollTop > 0 && !e.target.closest("header,.grab")) return; y0 = e.touches[0].clientY; dy = 0; sh.style.transition = "none"; };
  sh.addEventListener("touchstart", startDrag, { passive: true });
  sh.addEventListener("touchmove", (e) => {
    if (y0 == null) return;
    dy = e.touches[0].clientY - y0;
    if (dy > 0 && window.innerWidth < 700) sh.style.transform = `translateY(${dy}px)`;
    else if (dy < 0) y0 = null;
  }, { passive: true });
  sh.addEventListener("touchend", () => {
    if (y0 == null) return;
    sh.style.transition = ""; sh.style.transform = "";
    if (dy > 110) api_.close();
    y0 = null;
  });
  sheets.push(api_);
  return api_;
}

function actionSheet(options, message) {
  return new Promise((resolve) => {
    const root = $("#sheet-root");
    const bd = document.createElement("div");
    bd.className = "backdrop";
    const sh = document.createElement("div");
    sh.className = "sheet asheet";
    sh.style.background = "transparent";
    sh.style.boxShadow = "none";
    sh.innerHTML = `<div class="group">${message ? `<div class="msg">${esc(message)}</div>` : ""}${options.map((o, i) =>
      `<button class="row ${o.red ? "red" : ""}" data-i="${i}">${o.icon || ""}${esc(o.label)}</button>`).join("")}</div>
      <div class="group"><button class="row cancel">Cancel</button></div>`;
    root.append(bd, sh);
    requestAnimationFrame(() => { bd.classList.add("show"); sh.classList.add("show"); });
    const done = (v) => {
      bd.classList.remove("show"); sh.classList.remove("show");
      setTimeout(() => { bd.remove(); sh.remove(); }, 300);
      resolve(v);
    };
    bd.onclick = () => done(null);
    $(".cancel", sh).onclick = () => done(null);
    $$("[data-i]", sh).forEach((b) => (b.onclick = () => { haptic(); done(options[+b.dataset.i].value ?? +b.dataset.i); }));
  });
}
const confirmDanger = async (label, message) => (await actionSheet([{ label, red: true, value: true }], message)) === true;

function promptSheet({ title, value = "", placeholder = "", type = "text", inputmode, label = "Done" }) {
  return new Promise((resolve) => {
    let result = null;
    const s = openSheet({
      title,
      body: `<div class="form" style="padding-top:8px"><div class="group"><div class="field"><input id="pv" type="${type}" ${inputmode ? `inputmode="${inputmode}"` : ""} step="any" placeholder="${esc(placeholder)}" value="${esc(value)}"></div></div></div>`,
      left: { label: "Cancel", fn: () => s.close() },
      right: { label, bold: true, fn: () => { result = $("#pv", s.el).value; s.close(); } },
      onClose: () => resolve(result),
    });
    const inp = $("#pv", s.el);
    setTimeout(() => { inp.focus(); inp.select(); }, 350);
    inp.onkeydown = (e) => { if (e.key === "Enter") { result = inp.value; s.close(); } };
  });
}

// ------------------------------------------------------------------ photos
function pickFiles(source = "camera") {
  return new Promise((resolve) => {
    const inp = $(source === "camera" ? "#camera-input" : "#library-input");
    inp.value = "";
    const onChange = () => { inp.removeEventListener("change", onChange); resolve(Array.from(inp.files || [])); };
    inp.addEventListener("change", onChange);
    inp.click();
  });
}
async function choosePhotos() {
  const v = await actionSheet([
    { label: "Take Photo", value: "camera", icon: I.camera },
    { label: "Photo Library", value: "library", icon: I.image },
  ]);
  if (!v) return [];
  return pickFiles(v);
}

function loadImage(file) {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => res({ img, url });
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error("Could not read image")); };
    img.src = url;
  });
}
// Downscale on-device before upload: much faster on phones, server re-encodes anyway.
async function shrink(file, max = 2000) {
  try {
    const { img, url } = await loadImage(file);
    const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement("canvas");
    c.width = Math.round(img.naturalWidth * scale);
    c.height = Math.round(img.naturalHeight * scale);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    URL.revokeObjectURL(url);
    const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.88));
    return { blob: blob || file, canvas: c };
  } catch (e) {
    return { blob: file, canvas: null };
  }
}
function formWithPhotos(blobs, extra = {}) {
  const fd = new FormData();
  blobs.forEach((b, i) => fd.append("photo", b, `photo${i}.jpg`));
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  return fd;
}

// Decode QR / barcodes from a still image (BarcodeDetector where available, jsQR fallback).
async function decodeCode(canvas) {
  if (!canvas) return null;
  try {
    if ("BarcodeDetector" in window) {
      const det = new window.BarcodeDetector();
      const r = await det.detect(canvas);
      if (r && r.length) return r[0].rawValue;
    }
  } catch (e) {}
  try {
    if (window.jsQR) {
      // try at a couple of sizes; jsQR likes ~1000px
      for (const max of [1000, 600]) {
        const s = Math.min(1, max / Math.max(canvas.width, canvas.height));
        const c = document.createElement("canvas");
        c.width = Math.round(canvas.width * s); c.height = Math.round(canvas.height * s);
        const ctx = c.getContext("2d");
        ctx.drawImage(canvas, 0, 0, c.width, c.height);
        const d = ctx.getImageData(0, 0, c.width, c.height);
        const r = window.jsQR(d.data, c.width, c.height, { inversionAttempts: "attemptBoth" });
        if (r && r.data) return r.data;
      }
    }
  } catch (e) {}
  return null;
}

// ------------------------------------------------------------------ fragments
const picHTML = (photo, cls = "pic") => photo ? `<img class="${cls}" loading="lazy" src="${thumb(photo)}" alt="">` : `<div class="${cls}">${I.box}</div>`;
function itemRow(it, opts = {}) {
  const sub = [it.part_number, it.location_path || "", it.category_name].filter(Boolean).join(" · ");
  return `<a class="row thumb" href="#/item/${it.id}" data-id="${it.id}">
    ${picHTML(it.photo)}
    <div class="main"><div class="t">${it.favorite ? "★ " : ""}${esc(it.name)}</div><div class="s">${esc(sub) || "&nbsp;"}</div></div>
    <div class="qty ${it.low ? "low" : ""}">${fmt(it.quantity)}<span class="s" style="font-weight:400"> ${esc(it.unit || "")}</span></div>
    ${opts.noChev ? "" : I.chev}
  </a>`;
}
function itemCard(it) {
  return `<a class="card" href="#/item/${it.id}">
    <div class="img">${it.photo ? `<img loading="lazy" src="${thumb(it.photo)}" alt="">` : I.box}</div>
    <span class="q ${it.low ? "low" : ""}">${fmt(it.quantity)}</span>
    <div class="body"><div class="t">${esc(it.name)}</div><div class="s">${esc(it.location_path || it.category_name || " ")}</div></div>
  </a>`;
}
function topbar({ title = "", back = false, right = "", always = false, left = "" }) {
  return `<div class="topbar ${always ? "always" : ""}">
    <div class="side l">${back ? `<button class="navbtn back" onclick="history.length>1?history.back():location.hash='#/'">${I.back}<span>${esc(back === true ? "Back" : back)}</span></button>` : left}</div>
    <div class="title">${esc(title)}</div>
    <div class="side r">${right}</div>
  </div>`;
}
function locationOptions(locs, selected) {
  const sorted = [...locs].sort((a, b) => a.path.localeCompare(b.path));
  return `<option value="">None</option>` + sorted.map((l) => `<option value="${l.id}" ${+selected === l.id ? "selected" : ""}>${esc(l.path)}</option>`).join("") + `<option value="__new">New location…</option>`;
}
function categoryOptions(cats, selected) {
  const opt = (c, label) => `<option value="${c.id}" ${+selected === c.id ? "selected" : ""}>${esc(label)}</option>`;
  const tops = cats.filter((c) => !c.parent_id);
  return `<option value="">None</option>` + tops.map((t) => {
    const kids = cats.filter((c) => c.parent_id === t.id);
    if (!kids.length) return opt(t, t.name);
    return `<optgroup label="${esc(t.name)}">${opt(t, `${t.name} (general)`)}${kids.map((k) => opt(k, k.name)).join("")}</optgroup>`;
  }).join("") + `<option value="__new">New category…</option>`;
}
// match an AI / CSV category ("Group › Sub" or just a name) against existing categories
function findCat(cats, name) {
  if (!name) return null;
  const n = name.toLowerCase().replace(/\s*[>/]\s*/g, " › ").trim();
  return cats.find((c) => (c.path || c.name).toLowerCase() === n)
    || cats.find((c) => c.parent_id && c.name.toLowerCase() === n)
    || cats.find((c) => c.name.toLowerCase() === n) || null;
}

// ------------------------------------------------------------------ router
const routes = [];
const route = (re, fn, tab) => routes.push({ re, fn, tab });
let currentCleanup = null;
async function render() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const [path, qs] = hash.split("?");
  const params = new URLSearchParams(qs || "");
  for (const r of routes) {
    const m = path.match(r.re);
    if (m) {
      $$("#tabbar a").forEach((a) => a.classList.toggle("on", a.dataset.tab === r.tab));
      if (currentCleanup) { currentCleanup(); currentCleanup = null; }
      const view = $("#view");
      try {
        const res = await r.fn(view, m.slice(1), params);
        if (typeof res === "function") currentCleanup = res;
      } catch (e) {
        view.innerHTML = topbar({ back: true, always: true }) + `<div class="empty">${I.alert}<div>${esc(e.message)}</div></div>`;
      }
      return;
    }
  }
  location.hash = "#/";
}
window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
window.addEventListener("scroll", () => {
  const tb = $(".topbar");
  if (tb) tb.classList.toggle("scrolled", window.scrollY > 36);
}, { passive: true });
const refresh = () => render();

// ------------------------------------------------------------------ home
route(/^\/$/, async (view) => {
  const [s, cfg] = await Promise.all([GET("api/stats"), config()]);
  view.innerHTML = `<div class="page">
    ${topbar({ title: "Inventory", right: `<button class="navbtn" id="addbtn">${I.plus}</button>` })}
    <div class="largetitle">Inventory</div>
    <div class="searchbar"><a href="#/items?focus=1" style="display:block"><input readonly placeholder="Search parts, numbers, places…"></a>${I.search}</div>
    <div class="stats">
      <a class="stat" href="#/items"><div class="n">${fmt(s.items)}</div><div class="l">Items</div></a>
      <a class="stat" href="#/items"><div class="n">${fmt(s.units)}</div><div class="l">Units in stock</div></a>
      <a class="stat ${s.low ? "warn" : ""}" href="#/items?low=1"><div class="n">${fmt(s.low || 0)}</div><div class="l">Low stock</div></a>
      <a class="stat" href="#/locations"><div class="n">${fmt(s.locations)}</div><div class="l">Locations</div></a>
    </div>
    ${s.items === 0 ? `<div class="empty">${I.camera}<div><b>Start by snapping a photo</b></div><div>Tap the camera button to add your first part${cfg.ai_enabled ? " — AI will fill in the details" : ""}.</div>
      <button class="btn" id="firstsnap">${I.camera} Snap a part</button></div>` : ""}
    ${s.duplicates ? `<div class="group" style="margin-top:14px"><a class="row" href="#/duplicates"><span class="ico" style="background:#ff9500">${I.copy}</span><div class="main"><div class="t">${s.duplicates} duplicate${s.duplicates === 1 ? "" : "s"} hidden</div><div class="s">Review and merge them</div></div>${I.chev}</a></div>` : ""}
    ${s.low_items.length ? `<div class="section-h"><span>Low stock</span><a href="#/items?low=1">See all</a></div><div class="hscroll">${s.low_items.map(itemCard).join("")}</div>` : ""}
    ${s.recent.length ? `<div class="section-h"><span>Recently updated</span><a href="#/items">See all</a></div><div class="hscroll">${s.recent.map(itemCard).join("")}</div>` : ""}
    ${s.items ? `<div class="section-h"><span>Quick actions</span></div>
    <div class="group">
      <button class="row" id="qa-snap"><span class="ico">${I.camera}</span><div class="main">Snap &amp; identify</div>${I.chev}</button>
      ${cfg.ai_enabled ? `<button class="row" id="qa-box"><span class="ico" style="background:#00c7be">${I.grid}</span><div class="main">Scan a whole picking box</div>${I.chev}</button>` : ""}
      <button class="row" id="qa-scan"><span class="ico" style="background:#5856d6">${I.qr}</span><div class="main">Scan a label or barcode</div>${I.chev}</button>
      <button class="row" id="qa-new"><span class="ico" style="background:#34c759">${I.plus}</span><div class="main">New item</div>${I.chev}</button>
      <a class="row" href="#/activity"><span class="ico" style="background:#ff9500">${I.clock}</span><div class="main">Activity</div>${I.chev}</a>
    </div>
    <div class="help" style="margin-top:10px">${cfg.ai_enabled ? `AI identification on (${esc(cfg.ai_model)})` : "Tip: add an OpenAI API key in the add-on configuration to auto-identify parts from photos."}</div>` : ""}
  </div>`;
  $("#addbtn").onclick = () => itemForm();
  const fs = $("#firstsnap"); if (fs) fs.onclick = () => snap("camera");
  const q = (id, fn) => { const e = $(id); if (e) e.onclick = fn; };
  q("#qa-snap", () => snap("camera"));
  q("#qa-scan", () => scanFlow());
  q("#qa-box", () => boxScan());
  q("#qa-new", () => itemForm());
}, "home");

// ------------------------------------------------------------------ items list
const listState = { q: "", category: "", location: "", low: false, favorite: false, sort: store.get("sort", "updated"), view: store.get("view", "list") };
route(/^\/items$/, async (view, _, params) => {
  if (params.has("low")) { listState.low = params.get("low") === "1"; }
  if (params.has("q")) listState.q = params.get("q");
  if (params.has("category")) listState.category = params.get("category");
  const cats = await categories();
  view.innerHTML = `<div class="page">
    ${topbar({ title: "Items", right: `<button class="navbtn" id="sortbtn">${I.sort}</button><button class="navbtn" id="viewbtn">${listState.view === "grid" ? I.list : I.grid}</button><button class="navbtn" id="addbtn">${I.plus}</button>` })}
    <div class="largetitle">Items</div>
    <div class="searchbar ${listState.q ? "has" : ""}">
      ${I.search}<input id="q" type="search" enterkeyhint="search" autocomplete="off" placeholder="Search parts, numbers, places…" value="${esc(listState.q)}">
      <button class="clear" id="qclear">✕</button>
      <button class="scan" id="qscan" title="Scan">${I.qr}</button>
    </div>
    <div class="chips" id="chips">
      <button class="chip ${!listState.low && !listState.favorite && !listState.category ? "on" : ""}" data-f="all">All</button>
      <button class="chip ${listState.low ? "on" : ""}" data-f="low">Low stock</button>
      <button class="chip ${listState.favorite ? "on" : ""}" data-f="fav">★ Favorites</button>
      <a class="chip dupchip" id="dupchip" href="#/duplicates" hidden></a>
      ${cats.filter((c) => !c.parent_id && c.total_count).map((c) => `<button class="chip ${+listState.category === c.id ? "on" : ""}" data-c="${c.id}">${c.color ? `<span class="dot" style="background:${esc(c.color)}"></span>` : ""}${esc(c.name)}</button>`).join("")}
    </div>
    <div id="count" class="subtitle" style="margin-top:0"></div>
    <div id="results"></div>
    <div class="loadmore" id="more"></div>
  </div>`;
  const qi = $("#q");
  let offset = 0, total = 0, loading = false, token = 0;
  const load = async (reset) => {
    if (loading && !reset) return;
    if (reset) { offset = 0; }
    loading = true;
    const my = ++token;
    const p = new URLSearchParams({ q: listState.q, sort: listState.sort, limit: 60, offset });
    if (listState.low) p.set("low", "1");
    if (listState.favorite) p.set("favorite", "1");
    if (listState.category) p.set("category", listState.category);
    if (listState.location) p.set("location", listState.location);
    const res = await GET("api/items?" + p).catch(fail);
    if (my !== token || !res) { loading = false; return; }
    total = res.total;
    const html = listState.view === "grid" ? res.items.map(itemCard).join("") : res.items.map((i) => itemRow(i)).join("");
    const box = $("#results");
    if (reset) {
      box.innerHTML = res.items.length ? (listState.view === "grid" ? `<div class="grid">${html}</div>` : `<div class="group">${html}</div>`)
        : `<div class="empty">${I.search}<div>${listState.q ? `No items match “${esc(listState.q)}”` : "No items yet"}</div><button class="btn" id="emptyadd">${I.plus} ${listState.q ? `Add “${esc(listState.q)}”` : "Add item"}</button></div>`;
      const ea = $("#emptyadd"); if (ea) ea.onclick = () => itemForm({ name: listState.q });
    } else {
      (box.firstElementChild).insertAdjacentHTML("beforeend", html);
    }
    offset += res.items.length;
    $("#count").textContent = total ? `${total.toLocaleString()} item${total === 1 ? "" : "s"}` : "";
    const dc = $("#dupchip");
    if (dc) { dc.hidden = !res.duplicates; dc.textContent = `⧉ Duplicates (${res.duplicates})`; }
    $("#more").textContent = offset < total ? "Loading…" : "";
    loading = false;
  };
  const search = debounce(() => load(true), 180);
  qi.oninput = () => { listState.q = qi.value; qi.parentElement.classList.toggle("has", !!qi.value); search(); };
  qi.onkeydown = (e) => { if (e.key === "Enter") qi.blur(); };
  $("#qclear").onclick = () => { qi.value = ""; listState.q = ""; qi.parentElement.classList.remove("has"); load(true); qi.focus(); };
  $("#qscan").onclick = () => scanFlow();
  $("#addbtn").onclick = () => itemForm({ name: listState.q, category_id: listState.category || "" });
  $("#viewbtn").onclick = () => { listState.view = listState.view === "grid" ? "list" : "grid"; store.set("view", listState.view); render(); };
  $("#sortbtn").onclick = async () => {
    const v = await actionSheet([
      { label: (listState.sort === "updated" ? "✓ " : "") + "Recently updated", value: "updated" },
      { label: (listState.sort === "name" ? "✓ " : "") + "Name", value: "name" },
      { label: (listState.sort === "quantity" ? "✓ " : "") + "Quantity (lowest first)", value: "quantity" },
      { label: (listState.sort === "created" ? "✓ " : "") + "Newest", value: "created" },
    ], "Sort by");
    if (v) { listState.sort = v; store.set("sort", v); load(true); }
  };
  $("#chips").onclick = (e) => {
    const b = e.target.closest(".chip"); if (!b) return;
    haptic();
    if (b.dataset.f === "all") { listState.low = false; listState.favorite = false; listState.category = ""; }
    else if (b.dataset.f === "low") listState.low = !listState.low;
    else if (b.dataset.f === "fav") listState.favorite = !listState.favorite;
    else listState.category = +listState.category === +b.dataset.c ? "" : b.dataset.c;
    $$(".chip", $("#chips")).forEach((c) => c.classList.toggle("on",
      (c.dataset.f === "all" && !listState.low && !listState.favorite && !listState.category) ||
      (c.dataset.f === "low" && listState.low) || (c.dataset.f === "fav" && listState.favorite) ||
      (c.dataset.c && +c.dataset.c === +listState.category)));
    load(true);
  };
  const io = new IntersectionObserver((ents) => { if (ents[0].isIntersecting && offset < total) load(false); });
  io.observe($("#more"));
  await load(true);
  if (params.get("focus")) setTimeout(() => qi.focus(), 50);
  return () => io.disconnect();
}, "items");

// ------------------------------------------------------------------ item detail
route(/^\/item\/(\d+)$/, async (view, [id]) => {
  const it = await GET(`api/items/${id}`);
  const cfg = await config();
  const photos = it.photos || [];
  const kv = [
    ["Part number", it.part_number], ["Manufacturer", it.manufacturer], ["Barcode", it.barcode],
    ["Unit value", it.value != null ? money(it.value) : ""],
    ["Total value", it.value != null ? money(it.value * it.quantity) : ""],
    ["Reorder at", it.min_quantity != null ? `${fmt(it.min_quantity)} ${it.unit || ""}` : ""],
    ["Link", it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.url.replace(/^https?:\/\//, "").slice(0, 40))}</a>` : ""],
  ].filter((x) => x[1]);
  const byRel = {};
  (it.links || []).forEach((l) => (byRel[l.label] = byRel[l.label] || []).push(l));
  view.innerHTML = `<div class="page">
    ${topbar({ title: it.name, back: "Items", right: `<button class="navbtn" id="fav">${it.favorite ? I.starOn : I.star}</button><button class="navbtn" id="editbtn">Edit</button>` })}
    <div class="hero">
      ${photos.length ? `<div class="slides" id="slides">${photos.map((p) => `<img src="${full(p.filename)}" data-pid="${p.id}" alt="">`).join("")}</div>
        ${photos.length > 1 ? `<div class="dots">${photos.map((_, i) => `<i class="${i ? "" : "on"}"></i>`).join("")}</div>` : ""}`
      : `<div class="noimg">${I.image}</div>`}
      <button class="addphoto" id="addphoto">${I.camera}</button>
    </div>
    <div class="ititle">${esc(it.name)}</div>
    <div class="imeta">${it.category_name ? `<span class="dot" style="background:${esc(it.category_color || "var(--accent)")}"></span>${esc(it.category_name)}` : ""}
      ${it.location_path ? `${it.category_name ? " · " : ""}<a href="#/location/${it.location_id}">${I.pin.replace("<svg", '<svg style="width:15px;height:15px;vertical-align:-2px"')} ${esc(it.location_path)}</a>` : ""}</div>
    ${it.description ? `<div style="margin:0 16px 8px">${esc(it.description)}</div>` : ""}
    <div class="stepper ${it.low ? "low" : ""}">
      <button id="minus" aria-label="Remove one">−</button>
      <button class="val" id="qtyval"><b id="qty">${fmt(it.quantity)}</b><span>${esc(it.unit || "")}${it.low ? " · low stock" : ""}</span></button>
      <button id="plus" aria-label="Add one">+</button>
    </div>
    <div class="actions">
      <button id="a-photo">${I.camera}Photo</button>
      <button id="a-link">${I.link}Link</button>
      <button id="a-label">${I.qr}Label</button>
      <button id="a-more">${I.more}More</button>
    </div>
    ${it.tags.length ? `<div class="tags">${it.tags.map((t) => `<a class="chip" href="#/items?q=${encodeURIComponent(t)}">${esc(t)}</a>`).join("")}</div>` : ""}
    ${it.compatible.length ? `<div class="section-h">Works with</div><div class="tags">${it.compatible.map((t) => `<a class="chip compat" href="#/items?q=${encodeURIComponent(t)}">${esc(t)}</a>`).join("")}</div>
      <div id="compat-suggest"></div>` : ""}
    ${kv.length ? `<div class="section-h">Details</div><div class="group kv">${kv.map(([k, v]) => `<div class="row"><span class="k">${k}</span><span class="v2">${k === "Link" ? v : esc(v)}</span></div>`).join("")}</div>` : ""}
    ${it.notes ? `<div class="section-h">Notes</div><div class="group notes">${esc(it.notes)}</div>` : ""}
    <div class="section-h"><span>Linked items</span><a href="#" id="addlink">Add</a></div>
    ${it.links.length ? Object.entries(byRel).map(([label, ls]) => `
      <div class="help" style="margin:8px 32px 6px">${esc(label)}</div>
      <div class="group">${ls.map((l) => `<a class="row thumb" href="#/item/${l.id}" data-link="${l.link_id}">${picHTML(l.photo)}<div class="main"><div class="t">${esc(l.name)}</div><div class="s">${fmt(l.quantity)} ${esc(l.unit || "")}${l.note ? " · " + esc(l.note) : ""}</div></div>${I.chev}</a>`).join("")}</div>`).join("")
      : `<div class="group"><button class="row center" id="addlink2">${I.link} Link a related part</button></div>`}
    <div class="section-h">History</div>
    <div class="group">${it.history.length ? it.history.slice(0, 12).map((h) => `<div class="row"><div class="main"><div class="t">${h.delta > 0 ? "+" : ""}${fmt(h.delta)} → ${fmt(h.quantity_after)}</div><div class="s">${esc(h.reason || "Adjusted")}</div></div><span class="v">${timeAgo(h.created_at)}</span></div>`).join("") : `<div class="row"><span class="s">No changes yet</span></div>`}</div>
    <div class="help" style="margin-top:14px">Added ${new Date(it.created_at * 1000).toLocaleDateString()} · Updated ${timeAgo(it.updated_at)} · #${it.id}</div>
  </div>`;

  // photo dots
  const slides = $("#slides");
  if (slides && photos.length > 1) {
    slides.addEventListener("scroll", debounce(() => {
      const i = Math.round(slides.scrollLeft / slides.clientWidth);
      $$(".dots i", view).forEach((d, j) => d.classList.toggle("on", i === j));
    }, 40), { passive: true });
  }
  if (slides) slides.onclick = (e) => { const img = e.target.closest("img"); if (img) photoActions(it, +img.dataset.pid); };

  let qty = it.quantity, pending = 0;
  const flush = debounce(async () => {
    const d = pending; pending = 0;
    if (!d) return;
    try { const r = await POST(`api/items/${it.id}/adjust`, { delta: d, reason: d > 0 ? "Added" : "Used" }); qty = r.quantity; $("#qty").textContent = fmt(qty); }
    catch (e) { fail(e); }
  }, 600);
  const bump = (d) => {
    if (qty + d < 0) return;
    haptic(); qty += d; pending += d;
    $("#qty").textContent = fmt(qty);
    $(".stepper").classList.toggle("low", it.min_quantity != null && qty <= it.min_quantity);
    flush();
  };
  $("#plus").onclick = () => bump(1);
  $("#minus").onclick = () => bump(-1);
  $("#qtyval").onclick = async () => {
    const v = await promptSheet({ title: "Set quantity", value: fmt(qty).replace(/,/g, ""), type: "number", inputmode: "decimal", label: "Save" });
    if (v == null || v === "" || isNaN(+v)) return;
    const r = await POST(`api/items/${it.id}/adjust`, { set: +v, reason: "Counted" }).catch(fail);
    if (r) refresh();
  };
  $("#fav").onclick = async () => { haptic(); await PUT(`api/items/${it.id}`, { favorite: !it.favorite }).catch(fail); refresh(); };
  $("#editbtn").onclick = () => itemForm(it);
  const addPhoto = async () => {
    const files = await choosePhotos();
    if (!files.length) return;
    toast("Uploading…");
    const blobs = await Promise.all(files.map((f) => shrink(f).then((r) => r.blob)));
    await POST(`api/items/${it.id}/photos`, formWithPhotos(blobs)).catch(fail);
    refresh();
  };
  $("#addphoto").onclick = addPhoto;
  $("#a-photo").onclick = addPhoto;
  const link = (e) => { e && e.preventDefault(); linkFlow(it); };
  $("#a-link").onclick = link; $("#addlink").onclick = link;
  const al2 = $("#addlink2"); if (al2) al2.onclick = link;
  $("#a-label").onclick = () => printLabels([{ code: `INV:${it.id}`, title: it.name, sub: [it.part_number, it.location_path].filter(Boolean).join(" · ") }]);
  // suggest owned parts that match "works with" entries
  if (it.compatible.length) {
    const linked = new Set(it.links.map((l) => l.id));
    const seen = new Set([it.id]);
    const found = [];
    for (const term of it.compatible.slice(0, 6)) {
      const r = await GET("api/items?" + new URLSearchParams({ q: term, limit: 4 })).catch(() => null);
      (r ? r.items : []).forEach((x) => { if (!seen.has(x.id) && !linked.has(x.id)) { seen.add(x.id); found.push({ ...x, why: term }); } });
    }
    const box = $("#compat-suggest");
    if (found.length && box) {
      box.innerHTML = `<div class="help" style="margin:10px 32px 6px">In your inventory</div><div class="group">${found.slice(0, 6).map((x) => `
        <div class="row thumb">${picHTML(x.photo)}<a class="main" href="#/item/${x.id}" style="color:var(--text)"><div class="t">${esc(x.name)}</div><div class="s">matches “${esc(x.why)}” · ${fmt(x.quantity)} ${esc(x.unit || "")}</div></a>
        <button class="btn small gray" data-clink="${x.id}">${I.link.replace("<svg", '<svg style="width:16px;height:16px"')} Link</button></div>`).join("")}</div>`;
      $$("[data-clink]", box).forEach((b) => (b.onclick = async () => {
        await POST(`api/items/${it.id}/links`, { target_id: +b.dataset.clink, relation: "compatible" }).catch(fail);
        haptic(15); toast("Linked as compatible"); refresh();
      }));
    }
  }
  // long-press linked item to unlink
  $$("[data-link]", view).forEach((el) => longPress(el, async () => {
    if (await confirmDanger("Remove link", "Unlink this item?")) { await DEL(`api/links/${el.dataset.link}`).catch(fail); refresh(); }
  }));
  $("#a-more").onclick = async () => {
    const v = await actionSheet([
      { label: "Use some…", value: "use", icon: I.down },
      { label: "Restock…", value: "restock", icon: I.up },
      { label: "Move to location…", value: "move", icon: I.pin },
      { label: "Duplicate", value: "dup", icon: I.copy },
      ...(cfg.ai_enabled && photos.length ? [{ label: "Re-identify with AI", value: "ai", icon: I.sparkle }] : []),
      { label: "Delete item", value: "del", red: true, icon: I.trash },
    ]);
    if (v === "use" || v === "restock") {
      const n = await promptSheet({ title: v === "use" ? "How many used?" : "How many added?", type: "number", inputmode: "decimal", value: "1" });
      if (n && !isNaN(+n)) { await POST(`api/items/${it.id}/adjust`, { delta: v === "use" ? -n : +n, reason: v === "use" ? "Used" : "Restocked" }).catch(fail); refresh(); }
    } else if (v === "move") {
      const locs = await locations();
      const loc = await pickLocation(locs, it.location_id);
      if (loc !== undefined) { await PUT(`api/items/${it.id}`, { location_id: loc }).catch(fail); toast("Moved"); refresh(); }
    } else if (v === "dup") {
      const n = await POST(`api/items/${it.id}/duplicate`).catch(fail);
      if (n) { location.hash = `#/item/${n.id}`; itemForm(n); }
    } else if (v === "ai") {
      aiFillExisting(it);
    } else if (v === "del") {
      if (await confirmDanger("Delete item", `Delete “${it.name}” and its photos? This can't be undone.`)) {
        await DEL(`api/items/${it.id}`).catch(fail); toast("Deleted"); history.back();
      }
    }
  };
}, "items");

function longPress(el, fn) {
  let t;
  el.addEventListener("touchstart", () => { t = setTimeout(() => { haptic(20); fn(); t = "fired"; }, 550); }, { passive: true });
  el.addEventListener("touchend", (e) => { if (t === "fired") e.preventDefault(); clearTimeout(t); }, { passive: false });
  el.addEventListener("touchmove", () => clearTimeout(t), { passive: true });
  el.addEventListener("contextmenu", (e) => { e.preventDefault(); fn(); });
}

async function photoActions(it, pid) {
  const v = await actionSheet([
    { label: "View full size", value: "view" },
    { label: "Make cover photo", value: "primary" },
    { label: "Delete photo", value: "del", red: true },
  ]);
  const p = it.photos.find((x) => x.id === pid);
  if (v === "view" && p) window.open(full(p.filename), "_blank");
  if (v === "primary") { await POST(`api/photos/${pid}/primary`).catch(fail); refresh(); }
  if (v === "del" && (await confirmDanger("Delete photo"))) { await DEL(`api/photos/${pid}`).catch(fail); refresh(); }
}

function pickLocation(locs, current) {
  return new Promise((resolve) => {
    let result;
    const sorted = [...locs].sort((a, b) => a.path.localeCompare(b.path));
    const s = openSheet({
      title: "Location", full: true,
      left: { label: "Cancel", fn: () => s.close() },
      right: { label: "New", fn: async () => { const id = await newLocationPrompt(); if (id) { result = id; s.close(); } } },
      body: `<div class="searchbar" style="margin-top:6px">${I.search}<input id="lf" placeholder="Filter"></div>
        <div class="group" id="ll"><button class="row" data-id="">No location${!current ? " ✓" : ""}</button>${sorted.map((l) => `<button class="row" data-id="${l.id}" data-p="${esc(l.path.toLowerCase())}"><span class="main">${esc(l.path)}</span>${l.id === current ? "✓" : ""}</button>`).join("")}</div>`,
      onClose: () => resolve(result),
    });
    $("#lf", s.el).oninput = (e) => { const v = e.target.value.toLowerCase(); $$("[data-p]", s.el).forEach((r) => (r.style.display = r.dataset.p.includes(v) ? "" : "none")); };
    $("#ll", s.el).onclick = (e) => { const b = e.target.closest("[data-id]"); if (b) { result = b.dataset.id ? +b.dataset.id : null; s.close(); } };
  });
}
async function newLocationPrompt(parent_id) {
  const name = await promptSheet({ title: "New location", placeholder: "e.g. Garage, Shelf A, Bin 3", label: "Create" });
  if (!name) return null;
  const l = await POST("api/locations", { name, parent_id: parent_id || null }).catch(fail);
  invalidate();
  return l && l.id;
}

// ------------------------------------------------------------------ item form
async function itemForm(item = {}, opts = {}) {
  const [locs, cats, cfg] = await Promise.all([locations(), categories(), config()]);
  const isNew = !item.id;
  let photos = (opts.photos || item.photos || []).map((p) => ({ id: p.id, filename: p.filename }));
  const v = (k) => esc(item[k] ?? "");
  const tagStr = Array.isArray(item.tags) ? item.tags.join(", ") : (item.tags || "");
  const compatSrc = item.compatible || item.compatible_with || [];
  const compatStr = Array.isArray(compatSrc) ? compatSrc.join(", ") : compatSrc;
  const s = openSheet({
    title: isNew ? "New Item" : "Edit Item", full: true,
    left: { label: "Cancel", fn: () => s.close() },
    right: { label: isNew ? "Add" : "Save", bold: true, fn: () => save() },
    body: `<form class="form" onsubmit="return false">
      <div class="photostrip" id="strip"></div>
      ${cfg.ai_enabled ? `<div style="padding:4px 16px 0"><button type="button" class="btn small gray" id="aifill">${I.sparkle} Fill from photo with AI</button></div>` : ""}
      <div class="section-h"></div>
      <div class="group">
        <div class="field"><input name="name" placeholder="Name" value="${v("name")}" style="font-weight:600" autocomplete="off"></div>
        <div class="field"><textarea name="description" placeholder="Description" rows="2">${v("description")}</textarea></div>
      </div>
      <div class="section-h">Stock</div>
      <div class="group">
        <div class="field"><label>Quantity</label><input name="quantity" type="number" inputmode="decimal" step="any" value="${item.quantity ?? 1}"><input name="unit" placeholder="pcs" value="${esc(item.unit || "pcs")}" style="max-width:70px;text-align:right;color:var(--text2)"></div>
        <div class="field"><label>Reorder at</label><input name="min_quantity" type="number" inputmode="decimal" step="any" placeholder="Optional low-stock alert" value="${v("min_quantity")}"></div>
        <div class="field"><label>Unit value</label><input name="value" type="number" inputmode="decimal" step="any" placeholder="$0.00" value="${v("value")}"></div>
      </div>
      <div class="section-h">Organize</div>
      <div class="group">
        <div class="field"><label>Location</label><select name="location_id">${locationOptions(locs, item.location_id)}</select></div>
        <div class="field"><label>Category</label><select name="category_id">${categoryOptions(cats, item.category_id)}</select></div>
        <div class="field"><label>Tags</label><input name="tags" placeholder="comma, separated" value="${esc(tagStr)}" autocomplete="off"></div>
        <div class="field"><label>Works with</label><input name="compatible_with" placeholder="e.g. ESP32, 3.3V, XT60" value="${esc(compatStr)}" autocomplete="off"></div>
      </div>
      <div class="section-h">Identification</div>
      <div class="group">
        <div class="field"><label>Part number</label><input name="part_number" value="${v("part_number")}" autocomplete="off" autocapitalize="characters"></div>
        <div class="field"><label>Manufacturer</label><input name="manufacturer" value="${v("manufacturer")}" autocomplete="off"></div>
        <div class="field"><label>Barcode</label><input name="barcode" value="${v("barcode")}" autocomplete="off"><button type="button" class="navbtn" id="scanbc">${I.scan}</button></div>
        <div class="field"><label>Link</label><input name="url" type="url" inputmode="url" placeholder="https://" value="${v("url")}"></div>
      </div>
      <div class="section-h">Notes</div>
      <div class="group"><div class="field"><textarea name="notes" placeholder="Notes" rows="3">${v("notes")}</textarea></div></div>
      ${opts.aiNote ? `<div class="help">${esc(opts.aiNote)}</div>` : ""}
    </form>`,
  });
  const f = $("form", s.el);
  const F = (n) => f.elements[n];
  if (opts.categoryName && !item.category_id) {
    const match = findCat(cats, opts.categoryName);
    if (match) F("category_id").value = match.id;
    else {
      const o = document.createElement("option");
      o.value = "__name:" + opts.categoryName; o.textContent = opts.categoryName + " (new)";
      F("category_id").insertBefore(o, F("category_id").lastElementChild); F("category_id").value = o.value;
    }
  }
  const drawStrip = () => {
    $("#strip", s.el).innerHTML = photos.map((p, i) => `<div class="ph"><img src="${thumb(p.filename)}"><button type="button" class="x" data-i="${i}">✕</button></div>`).join("") +
      `<button type="button" class="add" id="addph">${I.camera}</button>`;
    $("#addph", s.el).onclick = async () => {
      const files = await choosePhotos();
      if (!files.length) return;
      const blobs = await Promise.all(files.map((x) => shrink(x).then((r) => r.blob)));
      const r = await POST("api/uploads", formWithPhotos(blobs)).catch(fail);
      if (r) { photos.push(...r.photos); drawStrip(); }
    };
    $$(".x", s.el).forEach((b) => (b.onclick = async () => {
      const p = photos[+b.dataset.i];
      if (!isNew && item.photos && item.photos.some((x) => x.id === p.id)) {
        if (!(await confirmDanger("Delete photo"))) return;
        await DEL(`api/photos/${p.id}`).catch(fail);
      }
      photos.splice(+b.dataset.i, 1); drawStrip();
    }));
  };
  drawStrip();
  const sel = async (name, makeNew) => {
    F(name).onchange = async () => {
      if (F(name).value !== "__new") return;
      const id = await makeNew();
      if (!id) { F(name).value = ""; return; }
      if (name === "location_id") F(name).innerHTML = locationOptions(await locations(true), id);
      else F(name).innerHTML = categoryOptions(await categories(true), id);
    };
  };
  sel("location_id", () => newLocationPrompt());
  sel("category_id", async () => {
    const n = await promptSheet({ title: "New category", placeholder: "e.g. Sensors › Temperature", label: "Create" });
    if (!n) return null;
    const c = await POST("api/categories", { name: n }).catch(fail);
    return c && c.id;
  });
  $("#scanbc", s.el).onclick = async () => {
    const files = await pickFiles("camera");
    if (!files.length) return;
    const { canvas } = await shrink(files[0], 1600);
    const code = await decodeCode(canvas);
    if (code) { F("barcode").value = code; haptic(); } else toast("No barcode found — try closer & sharper");
  };
  const aifill = $("#aifill", s.el);
  if (aifill) aifill.onclick = async () => {
    if (!photos.length) { toast("Add a photo first"); return; }
    aifill.disabled = true; aifill.innerHTML = `<span class="spinner"></span> Identifying…`;
    const fd = new FormData(); fd.append("photo_ids", photos.map((p) => p.id).join(",")); fd.append("hint", F("name").value);
    const r = await POST("api/ai/identify", fd).catch(fail);
    aifill.disabled = false; aifill.innerHTML = `${I.sparkle} Fill from photo with AI`;
    if (!r) return;
    if (r.error) { toast(r.error); return; }
    applySuggestion(f, r.suggestion, cats, true);
    haptic(15);
  };
  if (isNew && !opts.photos?.length && !item.name) setTimeout(() => F("name").focus(), 380);
  else if (isNew && opts.focusName) setTimeout(() => F("name").focus(), 380);

  async function save() {
    const data = {};
    ["name", "description", "quantity", "unit", "min_quantity", "value", "tags", "compatible_with", "part_number", "manufacturer", "barcode", "url", "notes"].forEach((k) => (data[k] = F(k).value));
    data.location_id = F("location_id").value.startsWith("__") ? null : F("location_id").value || null;
    const cv = F("category_id").value;
    if (cv.startsWith("__name:")) data.category_name = cv.slice(7);
    else data.category_id = cv.startsWith("__") ? null : cv || null;
    data.photo_ids = photos.map((p) => p.id);
    if (!data.name.trim()) { toast("Give it a name"); F("name").focus(); return; }
    s.buttons.right.disabled = true;
    try {
      let res;
      try {
        res = isNew ? await POST("api/items", data) : await PUT(`api/items/${item.id}`, data);
      } catch (e) {
        if (e.status !== 409 || !e.data || !e.data.duplicate) throw e;
        const ex = e.data.duplicate;
        const q = +data.quantity || 0;
        const v = await actionSheet([
          ...(q ? [{ label: `Add ${fmt(q)} to “${ex.name.slice(0, 28)}”`, value: "add" }] : []),
          { label: "Open existing item", value: "open" },
          { label: "Create anyway (it's different)", value: "force" },
        ], `You already have “${ex.name}” (${fmt(ex.quantity)} ${ex.unit || ""}).`);
        if (!v) { s.buttons.right.disabled = false; return; }
        if (v === "add") {
          await POST(`api/items/${ex.id}/adjust`, { delta: q, reason: "Added (duplicate avoided)" });
          if (data.photo_ids.length) await PUT(`api/items/${ex.id}`, { photo_ids: data.photo_ids });
          res = ex;
        } else if (v === "open") {
          s.close(); location.hash = `#/item/${ex.id}`; return;
        } else {
          res = await POST("api/items", { ...data, allow_duplicate: true });
        }
      }
      invalidate();
      haptic(15);
      s.close();
      toast(isNew ? "Item added" : "Saved");
      if (opts.onSaved) opts.onSaved(res);
      else if (location.hash !== `#/item/${res.id}`) location.hash = `#/item/${res.id}`;
      else refresh();
    } catch (e) { fail(e); s.buttons.right.disabled = false; }
  }
  return s;
}

function applySuggestion(f, sug, cats, overwrite) {
  if (!sug) return;
  const set = (k, v) => { if (v == null || v === "") return; if (overwrite || !f.elements[k].value) f.elements[k].value = v; };
  set("name", sug.name); set("description", sug.description); set("part_number", sug.part_number);
  set("manufacturer", sug.manufacturer); set("barcode", sug.barcode); set("unit", sug.unit);
  if (sug.tags && sug.tags.length) set("tags", sug.tags.join(", "));
  if (sug.compatible_with && sug.compatible_with.length) set("compatible_with", sug.compatible_with.join(", "));
  if (sug.quantity && f.elements.quantity.value === "1") f.elements.quantity.value = sug.quantity;
  if (sug.category) {
    const sel = f.elements.category_id;
    if (overwrite || !sel.value) {
      const m = findCat(cats, sug.category);
      if (m) sel.value = m.id;
      else {
        let o = $$("option", sel).find((x) => x.value === "__name:" + sug.category);
        if (!o) { o = document.createElement("option"); o.value = "__name:" + sug.category; o.textContent = sug.category + " (new)"; sel.insertBefore(o, sel.lastElementChild); }
        sel.value = o.value;
      }
    }
  }
}

async function aiFillExisting(it) {
  toast("Identifying…");
  const fd = new FormData(); fd.append("photo_ids", it.photos.map((p) => p.id).join(","));
  const r = await POST("api/ai/identify", fd).catch(fail);
  if (!r) return;
  if (r.error) return toast(r.error);
  const s = await itemForm(it);
  applySuggestion($("form", s.el), r.suggestion, await categories(), false);
  toast("Filled empty fields from AI");
}

// ------------------------------------------------------------------ item picker / links
function pickItem({ title = "Choose Item", exclude, initial = "" } = {}) {
  return new Promise((resolve) => {
    let result = null;
    const s = openSheet({
      title, full: true,
      left: { label: "Cancel", fn: () => s.close() },
      body: `<div class="searchbar" style="margin-top:6px">${I.search}<input id="pq" type="search" placeholder="Search items" value="${esc(initial)}" autocomplete="off"></div><div id="pr"></div>`,
      onClose: () => resolve(result),
    });
    const inp = $("#pq", s.el);
    const load = debounce(async () => {
      const r = await GET("api/items?" + new URLSearchParams({ q: inp.value, limit: 40 })).catch(fail);
      if (!r) return;
      const items = r.items.filter((i) => i.id !== exclude);
      $("#pr", s.el).innerHTML = items.length ? `<div class="group">${items.map((i) => itemRow(i, { noChev: true }).replace("<a ", "<a data-pick ")).join("")}</div>` : `<div class="empty">No items</div>`;
    }, 150);
    inp.oninput = load; load();
    $("#pr", s.el).onclick = (e) => {
      const a = e.target.closest("[data-id]"); if (!a) return;
      e.preventDefault(); result = r_items_find(a.dataset.id); s.close();
    };
    const r_items_find = (id) => ({ id: +id, name: $(`[data-id="${id}"] .t`, s.el).textContent });
    setTimeout(() => inp.focus(), 380);
  });
}

async function linkFlow(it) {
  const cfg = await config();
  const target = await pickItem({ title: "Link to…", exclude: it.id });
  if (!target) return;
  const opts = [];
  cfg.relations.forEach((r) => {
    opts.push({ label: `${it.name.slice(0, 22)} — ${r.label.toLowerCase()} — ${target.name.slice(0, 22)}`, value: { relation: r.key, inverse: false } });
    if (r.label !== r.inverse) opts.push({ label: `${it.name.slice(0, 22)} — ${r.inverse.toLowerCase()} — ${target.name.slice(0, 22)}`, value: { relation: r.key, inverse: true } });
  });
  const v = await actionSheet(opts, "How are they related?");
  if (!v) return;
  await POST(`api/items/${it.id}/links`, { target_id: target.id, ...v }).then(() => { toast("Linked"); refresh(); }).catch(fail);
}

// ------------------------------------------------------------------ snap (photo-first)
document.getElementById("snapbtn").addEventListener("click", () => snap("camera"));
longPress(document.getElementById("snapbtn"), async () => {
  const v = await actionSheet([
    { label: "Take Photo", value: "camera", icon: I.camera },
    { label: "Photo Library", value: "library", icon: I.image },
    { label: "Scan Whole Box (many labels)", value: "box", icon: I.grid },
    { label: "Scan Label / Barcode", value: "scan", icon: I.qr },
    { label: "New Item (no photo)", value: "new", icon: I.plus },
  ]);
  if (v === "box") boxScan();
  else if (v === "scan") scanFlow();
  else if (v === "new") itemForm();
  else if (v) snap(v);
});

async function snap(source) {
  const files = await pickFiles(source);
  if (!files.length) return;
  const cfg = await config();
  const shrunk = await Promise.all(files.map((f) => shrink(f)));
  const previewURL = URL.createObjectURL(shrunk[0].blob);
  const s = openSheet({
    title: cfg.ai_enabled ? "Identify" : "New from Photo", full: true,
    left: { label: "Cancel", fn: () => s.close() },
    body: `<div class="snap-preview ${cfg.ai_enabled ? "scanning" : ""}" id="sp"><img src="${previewURL}"></div><div id="out"><div class="status"><span class="spinner"></span> ${cfg.ai_enabled ? "Identifying…" : "Uploading…"}</div></div>`,
    onClose: () => setTimeout(() => URL.revokeObjectURL(previewURL), 120000),
  });
  const out = $("#out", s.el);

  // 1. Any QR / barcode in the shot? Jump straight to that item.
  const code = await decodeCode(shrunk[0].canvas);
  if (code) {
    const r = await GET("api/lookup?code=" + encodeURIComponent(code)).catch(() => null);
    if (r && r.type === "item") { $("#sp", s.el).classList.remove("scanning"); return showFound(s, out, r.id, shrunk.map((x) => x.blob)); }
    if (r && r.type === "location") { s.close(); location.hash = `#/location/${r.id}`; return; }
  }

  // 2. Upload (+ AI identify when configured)
  const fd = formWithPhotos(shrunk.map((x) => x.blob));
  let res;
  try { res = await POST(cfg.ai_enabled ? "api/ai/identify" : "api/uploads", fd); }
  catch (e) { out.innerHTML = `<div class="empty">${I.alert}<div>${esc(e.message)}</div></div>`; return; }
  $("#sp", s.el).classList.remove("scanning");
  const photos = res.photos;
  if (code) res.barcode = code;
  const sug = res.suggestion;
  const matches = res.matches || [];
  const newFromPhoto = () => {
    s.close();
    const base = sug ? { name: sug.name, description: sug.description, part_number: sug.part_number, manufacturer: sug.manufacturer, barcode: sug.barcode || code || "", quantity: sug.quantity || 1, unit: sug.unit || "pcs", tags: sug.tags || [], compatible: sug.compatible_with || [] } : { barcode: code || "" };
    itemForm(base, { photos, categoryName: sug && sug.category, focusName: !sug, aiNote: sug ? `Suggested by AI (${sug.confidence} confidence). Review before saving.` : "" });
  };
  out.innerHTML = `
    ${res.error ? `<div class="help" style="margin:12px 32px;color:var(--orange)">${esc(res.error)}</div>` : ""}
    ${sug ? `<div class="suggest"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><div class="n">${esc(sug.name)}</div><span class="conf ${esc(sug.confidence)}">${esc(sug.confidence)}</span></div>
      <div class="d">${esc(sug.description)}</div>
      <div class="d">${[sug.category, sug.manufacturer, sug.part_number].filter(Boolean).map(esc).join(" · ")}${sug.quantity > 1 ? ` · ${fmt(sug.quantity)} counted` : ""}</div>
      ${sug.compatible_with && sug.compatible_with.length ? `<div class="d">Works with: ${sug.compatible_with.map(esc).join(", ")}</div>` : ""}</div>` : ""}
    <div class="btnrow" style="margin-top:12px"><button class="btn" id="mknew">${I.plus} New item</button></div>
    ${matches.length ? `<div class="section-h">Already have it? Add to stock</div><div class="group" id="matches">${matches.map((m) => `
      <div class="row thumb" data-id="${m.id}">${picHTML(m.photo)}<div class="main"><div class="t">${esc(m.name)}</div><div class="s">${fmt(m.quantity)} ${esc(m.unit || "")} · ${esc(m.location_path || "No location")}</div></div>
      <button class="btn small" data-add="${m.id}">+${fmt(sug && sug.quantity > 1 ? sug.quantity : 1)}</button></div>`).join("")}</div>` : ""}
    <div class="section-h">Other options</div>
    <div class="group">
      <button class="row" id="addexisting"><span class="ico" style="background:#5856d6">${I.search}</span><div class="main">Add to an existing item…</div>${I.chev}</button>
      ${cfg.ai_enabled ? `<button class="row" id="isbox"><span class="ico" style="background:#00c7be">${I.grid}</span><div class="main">It's a box of many labelled parts</div>${I.chev}</button>` : ""}
      <button class="row" id="morephotos"><span class="ico" style="background:#8e8e93">${I.camera}</span><div class="main">Add another angle${cfg.ai_enabled ? " & re-identify" : ""}</div>${I.chev}</button>
    </div>`;
  $("#mknew", s.el).onclick = newFromPhoto;
  const addTo = async (id, qty) => {
    const what = await actionSheet([
      { label: `Add ${fmt(qty)} to stock + keep photo`, value: "both" },
      { label: `Add ${fmt(qty)} to stock only`, value: "stock" },
      { label: "Just attach the photo", value: "photo" },
      { label: "Open item", value: "open" },
    ]);
    if (!what) return;
    if (what === "both" || what === "photo") await PUT(`api/items/${id}`, { photo_ids: photos.map((p) => p.id) }).catch(fail);
    if (what === "both" || what === "stock") await POST(`api/items/${id}/adjust`, { delta: qty, reason: "Stocked from photo" }).catch(fail);
    haptic(15); s.close();
    if (what !== "open") toast(what === "photo" ? "Photo added" : `Added ${fmt(qty)}`, { label: "View", fn: () => (location.hash = `#/item/${id}`) });
    else location.hash = `#/item/${id}`;
    if (location.hash.startsWith("#/item/" + id) || location.hash === "#/" || location.hash === "") refresh();
  };
  $$("[data-add]", s.el).forEach((b) => (b.onclick = (e) => { e.stopPropagation(); addTo(+b.dataset.add, sug && sug.quantity > 1 ? sug.quantity : 1); }));
  $$("#matches .row", s.el).forEach((r) => (r.onclick = () => addTo(+r.dataset.id, sug && sug.quantity > 1 ? sug.quantity : 1)));
  $("#addexisting", s.el).onclick = async () => {
    const t = await pickItem({ title: "Add to…", initial: sug ? sug.name.split(" ").slice(0, 2).join(" ") : "" });
    if (t) addTo(t.id, 1);
  };
  const ib = $("#isbox", s.el);
  if (ib) ib.onclick = () => { s.close(); boxScan(null, photos, previewURL); };
  $("#morephotos", s.el).onclick = async () => {
    const more = await choosePhotos();
    if (!more.length) return;
    out.innerHTML = `<div class="status"><span class="spinner"></span> ${cfg.ai_enabled ? "Re-identifying…" : "Uploading…"}</div>`;
    const blobs = await Promise.all(more.map((f) => shrink(f).then((r) => r.blob)));
    const up = await POST("api/uploads", formWithPhotos(blobs)).catch(fail);
    if (!up) return;
    const all = photos.concat(up.photos);
    if (cfg.ai_enabled) {
      const f2 = new FormData(); f2.append("photo_ids", all.map((p) => p.id).join(","));
      const r2 = await POST("api/ai/identify", f2).catch(fail);
      s.close();
      if (r2) itemForm(r2.suggestion ? { ...r2.suggestion, compatible: r2.suggestion.compatible_with || [], quantity: r2.suggestion.quantity || 1 } : {}, { photos: all, categoryName: r2.suggestion && r2.suggestion.category });
    } else { s.close(); itemForm({}, { photos: all, focusName: true }); }
  };
}

async function showFound(s, out, id, blobs) {
  const it = await GET(`api/items/${id}`);
  haptic(20);
  out.innerHTML = `<div class="section-h">Scanned item</div><div class="group">${itemRow(it)}</div>
    <div class="stepper" style="margin-top:14px"><button id="fm">−</button><div class="val"><b id="fq">${fmt(it.quantity)}</b><span>${esc(it.unit || "")}</span></div><button id="fp">+</button></div>
    <div class="btnrow" style="margin-top:10px"><a class="btn gray" href="#/item/${id}" id="fo">Open item</a></div>`;
  let q = it.quantity;
  const adj = async (d) => { if (q + d < 0) return; haptic(); q += d; $("#fq", out).textContent = fmt(q); await POST(`api/items/${id}/adjust`, { delta: d, reason: d > 0 ? "Added (scan)" : "Used (scan)" }).catch(fail); };
  $("#fm", out).onclick = () => adj(-1);
  $("#fp", out).onclick = () => adj(1);
  $("#fo", out).onclick = () => s.close();
}

async function scanFlow() {
  const files = await pickFiles("camera");
  if (!files.length) return;
  const { canvas } = await shrink(files[0], 1600);
  const code = await decodeCode(canvas);
  if (!code) { toast("No code found — try again closer"); return; }
  const r = await GET("api/lookup?code=" + encodeURIComponent(code)).catch(fail);
  if (!r) return;
  haptic(20);
  if (r.type === "item") location.hash = `#/item/${r.id}`;
  else if (r.type === "location") location.hash = `#/location/${r.id}`;
  else {
    const v = await actionSheet([{ label: "Create new item with this code", value: "new" }, { label: "Search for it", value: "search" }], `Code “${code}” isn't in your inventory`);
    if (v === "new") itemForm({ barcode: code });
    if (v === "search") { listState.q = code; location.hash = "#/items?q=" + encodeURIComponent(code); }
  }
}


// ------------------------------------------------------------------ box scan (many labels)
async function boxScan(presetLocation, existingPhotos, existingPreview) {
  const cfg = await config();
  if (!cfg.ai_enabled) { toast("Box scan needs AI — add an OpenAI key in the add-on configuration"); return; }
  let shrunk = [], previewURL = existingPreview || "";
  if (!existingPhotos) {
    const files = await pickFiles("camera");
    if (!files.length) return;
    shrunk = await Promise.all(files.map((f) => shrink(f, 2600)));
    previewURL = URL.createObjectURL(shrunk[0].blob);
  }
  const s = openSheet({
    title: "Scan Box", full: true,
    left: { label: "Cancel", fn: () => s.close() },
    body: `<div class="snap-preview scanning" id="sp"><img src="${previewURL}" style="max-height:28vh"></div>
      <div id="out"><div class="status"><span class="spinner"></span> Reading every label…</div>
      <div class="help" style="text-align:center">Big boxes can take up to a minute.</div></div>`,
    onClose: () => { if (!existingPreview) URL.revokeObjectURL(previewURL); },
  });
  const out = $("#out", s.el);
  const fd = existingPhotos ? new FormData() : formWithPhotos(shrunk.map((x) => x.blob));
  if (existingPhotos) fd.append("photo_ids", existingPhotos.map((p) => p.id).join(","));
  let res;
  try { res = await POST("api/ai/identify-box", fd); }
  catch (e) { out.innerHTML = `<div class="empty">${I.alert}<div>${esc(e.message)}</div></div>`; return; }
  $("#sp", s.el).classList.remove("scanning");
  if (res.error) { out.innerHTML = `<div class="empty">${I.alert}<div>${esc(res.error)}</div></div>`; return; }
  const photos = res.photos;
  // mode: "new" | "add" (+1 to existing) | "skip"
  const rows = res.items.map((it) => ({ ...it, quantity: 1, mode: it.match ? "skip" : "new" }));
  if (!rows.length) { out.innerHTML = `<div class="empty">${I.search}<div>No labels found. Try a straighter, closer, well-lit photo.</div></div>`; return; }
  const locs = await locations();
  const modeLabel = { new: "New", add: "+1 existing", skip: "Skip" };
  const draw = () => {
    const n = rows.filter((r) => r.mode !== "skip").length;
    out.innerHTML = `
      <div class="subtitle" style="margin:12px 16px 4px">Found ${rows.length} label${rows.length === 1 ? "" : "s"}. Each is added with stock 1. Tap a name to fix it.</div>
      <div class="form"><div class="group" style="margin-top:8px"><div class="field"><label>Put in</label><select id="bloc">${locationOptions(locs, presetLocation)}</select></div></div></div>
      <div class="help">The box photo is attached to every item${presetLocation ? "" : " and saved on the location"}.</div>
      <div class="section-h"><span>Items</span><a href="#" id="toggleall">${n === rows.length ? "Skip all" : "Select all"}</a></div>
      <div class="group">${rows.map((r, i) => `
        <div class="row brow ${r.mode === "skip" ? "off" : ""}" data-i="${i}">
          <button class="check ${r.mode === "skip" ? "" : "on"}" data-check="${i}" aria-label="Include">✓</button>
          <div class="main">
            <input class="bname" data-name="${i}" value="${esc(r.name)}">
            <div class="s">${esc([r.label_text && r.label_text !== r.name ? `“${r.label_text}”` : "", r.position, r.category].filter(Boolean).join(" · "))}</div>
            ${r.match ? `<div class="s" style="color:var(--orange)">Already have: ${esc(r.match.name)} (${fmt(r.match.quantity)})</div>` : ""}
          </div>
          <button class="pill ${r.mode}" data-mode="${i}">${modeLabel[r.mode]}</button>
        </div>`).join("")}</div>
      <div style="height:90px"></div>
      <div class="sticky-cta"><button class="btn block" id="addall" ${n ? "" : "disabled"}>${I.plus} Add ${n} item${n === 1 ? "" : "s"}</button></div>`;
    $("#bloc", out).onchange = async (e) => {
      if (e.target.value === "__new") {
        const id = await newLocationPrompt();
        presetLocation = id || "";
        locs.splice(0, locs.length, ...(await locations(true)));
        draw();
      } else presetLocation = e.target.value;
    };
    $$("[data-name]", out).forEach((inp) => (inp.oninput = () => (rows[+inp.dataset.name].name = inp.value)));
    $$("[data-check]", out).forEach((b) => (b.onclick = () => {
      haptic(); const r = rows[+b.dataset.check];
      r.mode = r.mode === "skip" ? (r.match ? "add" : "new") : "skip"; draw();
    }));
    $$("[data-mode]", out).forEach((b) => (b.onclick = async () => {
      const r = rows[+b.dataset.mode];
      const opts = [{ label: "Add as new item", value: "new" }];
      if (r.match) opts.push({ label: `+1 to “${r.match.name.slice(0, 30)}”`, value: "add" });
      opts.push({ label: "Skip", value: "skip" });
      const v = await actionSheet(opts, r.name);
      if (v) { r.mode = v; draw(); }
    }));
    $("#toggleall", out).onclick = (e) => {
      e.preventDefault();
      const allOn = rows.every((r) => r.mode !== "skip");
      rows.forEach((r) => (r.mode = allOn ? "skip" : (r.mode === "skip" ? (r.match ? "add" : "new") : r.mode)));
      draw();
    };
    $("#addall", out).onclick = async () => {
      const chosen = rows.filter((r) => r.mode !== "skip" && r.name.trim());
      if (!chosen.length) return;
      const btn = $("#addall", out); btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Adding…`;
      try {
        const r = await POST("api/items/batch", {
          location_id: presetLocation || null,
          photo_ids: photos.map((p) => p.id),
          items: chosen.map((c) => c.mode === "add" ? { add_to_id: c.match.id, quantity: 1 }
            : { name: c.name.trim(), description: c.description, category: c.category, part_number: c.part_number,
                manufacturer: c.manufacturer, tags: c.tags, compatible_with: c.compatible_with, label_text: c.label_text, position: c.position, quantity: 1 }),
        });
        invalidate(); haptic(20); s.close();
        const msg = [r.created.length ? `Added ${r.created.length} item${r.created.length === 1 ? "" : "s"}` : "", r.stocked.length ? `stocked ${r.stocked.length}` : ""].filter(Boolean).join(", ");
        toast(msg || "Done");
        location.hash = presetLocation ? `#/location/${presetLocation}` : "#/items?sort=created";
        refresh();
      } catch (e) { fail(e); btn.disabled = false; btn.innerHTML = `${I.plus} Retry`; }
    };
  };
  draw();
}

// ------------------------------------------------------------------ locations
route(/^\/locations$/, async (view) => {
  const locs = await locations(true);
  const kids = (pid) => locs.filter((l) => (l.parent_id || null) === pid);
  const total = (l) => l.item_count + kids(l.id).reduce((a, k) => a + total(k), 0);
  const tops = kids(null);
  view.innerHTML = `<div class="page">
    ${topbar({ title: "Places", right: `<button class="navbtn" id="scanloc">${I.qr}</button><button class="navbtn" id="addloc">${I.plus}</button>` })}
    <div class="largetitle">Places</div>
    <div class="subtitle">Rooms, shelves, bins and drawers. Nest them as deep as you like.</div>
    ${tops.length ? `<div class="group">${tops.map((l) => locRow(l, total(l), kids(l.id).length)).join("")}</div>`
      : `<div class="empty">${I.pin}<div>No locations yet</div><button class="btn" id="firstloc">${I.plus} Add a location</button></div>`}
  </div>`;
  const add = async () => { const id = await newLocationPrompt(); if (id) location.hash = `#/location/${id}`; };
  $("#addloc").onclick = add;
  $("#scanloc").onclick = () => scanFlow();
  const fl = $("#firstloc"); if (fl) fl.onclick = add;
}, "locations");

function locRow(l, count, children) {
  return `<a class="row thumb" href="#/location/${l.id}">
    ${l.photo ? `<img class="pic" src="${thumb(l.photo)}" loading="lazy">` : `<div class="pic">${I.folder}</div>`}
    <div class="main"><div class="t">${esc(l.name)}</div><div class="s">${count} item${count === 1 ? "" : "s"}${children ? ` · ${children} inside` : ""}</div></div>${I.chev}</a>`;
}

route(/^\/location\/(\d+)$/, async (view, [id]) => {
  const [loc, all, items] = await Promise.all([GET(`api/locations/${id}`), locations(true), GET(`api/items?location=${id}&sort=name&limit=500`)]);
  const kids = (pid) => all.filter((l) => (l.parent_id || null) === pid);
  const total = (l) => l.item_count + kids(l.id).reduce((a, k) => a + total(k), 0);
  const parentPath = loc.path.split(" › ").slice(0, -1).join(" › ");
  view.innerHTML = `<div class="page">
    ${topbar({ title: loc.name, back: "Places", right: `<button class="navbtn" id="lmore">${I.more}</button>` })}
    ${loc.photos.length ? `<div class="hero"><div class="slides">${loc.photos.map((p) => `<img src="${full(p.filename)}">`).join("")}</div></div>` : ""}
    <div class="largetitle">${esc(loc.name)}</div>
    ${parentPath ? `<div class="subtitle"><a href="#/location/${loc.parent_id}">${esc(parentPath)}</a></div>` : ""}
    ${loc.description ? `<div style="margin:0 16px 10px">${esc(loc.description)}</div>` : ""}
    <div class="btnrow"><button class="btn gray small" id="additem">${I.plus} Item here</button><button class="btn gray small" id="addsub">${I.folder} Sub-location</button></div>
    ${(await config()).ai_enabled ? `<div class="btnrow" style="margin-top:8px"><button class="btn gray small" id="scanbox">${I.grid} Scan box contents into here</button></div>` : ""}
    ${loc.children.length ? `<div class="section-h">Inside</div><div class="group">${kids(+id).map((l) => locRow(l, total(l), kids(l.id).length)).join("")}</div>` : ""}
    <div class="section-h"><span>Items${items.total ? ` (${items.total})` : ""}</span></div>
    ${items.items.length ? `<div class="group">${items.items.map((i) => itemRow(i)).join("")}</div>` : `<div class="group"><div class="row"><span class="s">Nothing here yet</span></div></div>`}
  </div>`;
  $("#additem").onclick = () => itemForm({ location_id: +id });
  const sb = $("#scanbox"); if (sb) sb.onclick = () => boxScan(+id);
  $("#addsub").onclick = async () => { const nid = await newLocationPrompt(+id); if (nid) refresh(); };
  $("#lmore").onclick = async () => {
    const v = await actionSheet([
      { label: "Rename / edit", value: "edit", icon: I.edit },
      { label: "Move inside…", value: "move", icon: I.pin },
      { label: "Add photo", value: "photo", icon: I.camera },
      { label: "Print label", value: "label", icon: I.qr },
      { label: "Print labels for all items here", value: "labels", icon: I.tag },
      { label: "Delete location", value: "del", red: true, icon: I.trash },
    ]);
    if (v === "edit") {
      const name = await promptSheet({ title: "Name", value: loc.name, label: "Save" });
      if (name == null) return;
      const desc = await promptSheet({ title: "Description (optional)", value: loc.description || "", label: "Save" });
      await PUT(`api/locations/${id}`, { name: name || loc.name, parent_id: loc.parent_id, description: desc ?? loc.description }).catch(fail);
      invalidate(); refresh();
    } else if (v === "move") {
      const p = await pickLocation(all.filter((l) => l.id !== +id), loc.parent_id);
      if (p === undefined) return;
      await PUT(`api/locations/${id}`, { name: loc.name, parent_id: p, description: loc.description }).catch(fail);
      invalidate(); refresh();
    } else if (v === "photo") {
      const files = await choosePhotos(); if (!files.length) return;
      const blobs = await Promise.all(files.map((f) => shrink(f).then((r) => r.blob)));
      await POST(`api/locations/${id}/photos`, formWithPhotos(blobs)).catch(fail); refresh();
    } else if (v === "label") {
      printLabels([{ code: `LOC:${id}`, title: loc.name, sub: parentPath }]);
    } else if (v === "labels") {
      printLabels(items.items.map((i) => ({ code: `INV:${i.id}`, title: i.name, sub: [i.part_number, i.location_path].filter(Boolean).join(" · ") })));
    } else if (v === "del") {
      if (await confirmDanger("Delete location", "Items and sub-locations inside will move up one level.")) {
        await DEL(`api/locations/${id}`).catch(fail); invalidate(); history.back();
      }
    }
  };
}, "locations");

// ------------------------------------------------------------------ labels
function printLabels(labels) {
  if (!labels.length) return toast("Nothing to print");
  let root = $("#print-root");
  if (!root) { root = document.createElement("div"); root.id = "print-root"; document.body.append(root); }
  root.innerHTML = labels.map((l) => `<div class="label"><img src="api/qr?data=${encodeURIComponent(l.code)}"><div><b>${esc(l.title)}</b><small>${esc(l.sub || "")}</small><br><small>${esc(l.code)}</small></div></div>`).join("");
  const imgs = $$("img", root);
  let n = 0;
  const go = () => setTimeout(() => window.print(), 100);
  imgs.forEach((i) => { i.onload = i.onerror = () => { if (++n === imgs.length) go(); }; });
  toast("Preparing labels…");
}

// ------------------------------------------------------------------ activity
route(/^\/activity$/, async (view) => {
  const rows = await GET("api/activity?limit=150");
  view.innerHTML = `<div class="page">${topbar({ title: "Activity", back: true })}
    <div class="largetitle">Activity</div>
    ${rows.length ? `<div class="group">${rows.map((r) => `<a class="row thumb" href="#/item/${r.item_id}">${picHTML(r.photo)}<div class="main"><div class="t">${esc(r.name)}</div><div class="s">${esc(r.reason || "Adjusted")} · ${timeAgo(r.created_at)}</div></div><div class="qty" style="color:${r.delta > 0 ? "var(--green)" : "var(--red)"}">${r.delta > 0 ? "+" : ""}${fmt(r.delta)}</div></a>`).join("")}</div>` : `<div class="empty">${I.clock}<div>No activity yet</div></div>`}
  </div>`;
}, "more");

// ------------------------------------------------------------------ more
route(/^\/more$/, async (view) => {
  const [s, cfg] = await Promise.all([GET("api/stats"), config()]);
  view.innerHTML = `<div class="page">${topbar({ title: "More" })}
    <div class="largetitle">More</div>
    <div class="group">
      <a class="row" href="#/categories"><span class="ico" style="background:#af52de">${I.tag}</span><div class="main">Categories</div><span class="v">${s.categories}</span>${I.chev}</a>
      ${cfg.ai_enabled ? `<button class="row" id="autocat"><span class="ico" style="background:#bf5af2">${I.sparkle}</span><div class="main">Auto-categorize items</div>${I.chev}</button>` : ""}
      <a class="row" href="#/activity"><span class="ico" style="background:#ff9500">${I.clock}</span><div class="main">Activity</div>${I.chev}</a>
      <a class="row" href="#/items?low=1"><span class="ico" style="background:#ff3b30">${I.alert}</span><div class="main">Low stock</div><span class="v">${s.low || 0}</span>${I.chev}</a>
      <a class="row" href="#/duplicates"><span class="ico" style="background:#ff9500">${I.copy}</span><div class="main">Duplicates</div><span class="v">${s.duplicates || ""}</span>${I.chev}</a>
      <button class="row" id="scan"><span class="ico" style="background:#5856d6">${I.qr}</span><div class="main">Scan label / barcode</div>${I.chev}</button>
    </div>
    <div class="section-h">Inventory value</div>
    <div class="group"><div class="row"><div class="main">Total value</div><span class="v">${money(s.total_value)}</span></div>
      <div class="row"><div class="main">Units in stock</div><span class="v">${fmt(s.units)}</span></div>
      <div class="row"><div class="main">Photos</div><span class="v">${fmt(s.photos)}</span></div></div>
    <div class="section-h">Data</div>
    <div class="group">
      <a class="row" href="api/export.csv" download><span class="ico" style="background:#34c759">${I.down}</span><div class="main">Export CSV</div>${I.chev}</a>
      <a class="row" href="api/export.json" download><span class="ico" style="background:#34c759">${I.down}</span><div class="main">Export full JSON</div>${I.chev}</a>
      <button class="row" id="import"><span class="ico" style="background:#0a84ff">${I.up}</span><div class="main">Import CSV</div>${I.chev}</button>
    </div>
    <div class="help">Your database and photos live in the add-on's /data folder and are included in Home Assistant backups. CSV columns: name, description, category, location (use “Garage &gt; Shelf A”), quantity, unit, min_quantity, part_number, manufacturer, barcode, value, tags, notes, url.</div>
    <div class="section-h">AI photo identification</div>
    <div class="group"><div class="row"><div class="main">Status</div><span class="v">${cfg.ai_enabled ? "On · " + esc(cfg.ai_model) : "Off"}</span></div></div>
    <div class="help">${cfg.ai_enabled ? `Snapped photos are sent to ${cfg.ai_provider === "anthropic" ? "Anthropic" : "OpenAI"} for identification.` : "Add an OpenAI API key in Settings → Add-ons → Parts Inventory → Configuration to enable."}</div>
    <div class="help" style="margin-top:24px;text-align:center">Parts Inventory · search ${cfg.fts ? "full-text" : "basic"}</div>
    <input type="file" id="csvfile" accept=".csv,text/csv" hidden>
  </div>`;
  $("#scan").onclick = () => scanFlow();
  const ac = $("#autocat"); if (ac) ac.onclick = () => autoCategorize();
  $("#import").onclick = () => $("#csvfile").click();
  $("#csvfile").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    toast("Importing…");
    const r = await POST("api/import.csv", fd).catch(fail);
    if (r) { invalidate(); toast(`Imported ${r.created} new, ${r.updated} updated${r.merged ? `, ${r.merged} merged into existing` : ""}${r.errors.length ? `, ${r.errors.length} errors` : ""}`); if (r.errors.length) console.warn(r.errors); }
  };
}, "more");

route(/^\/categories$/, async (view) => {
  const cats = await categories(true);
  const colors = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be", "#0a84ff", "#5856d6", "#af52de", "#ff2d55", "#a2845e", "#8e8e93"];
  view.innerHTML = `<div class="page">${topbar({ title: "Categories", back: "More", right: `<button class="navbtn" id="addcat">${I.plus}</button>` })}
    <div class="largetitle">Categories</div>
    <div class="btnrow" style="margin-bottom:12px">
      ${(await config()).ai_enabled ? `<button class="btn gray small" id="autocat">${I.sparkle} Auto-categorize</button>` : ""}
      <button class="btn gray small" id="defcats">${I.tag} Restore standard set</button>
    </div>
    <div class="searchbar">${I.search}<input id="catq" type="search" placeholder="Filter categories" autocomplete="off"></div>
    ${cats.length ? `<div class="group" id="cattree">${cats.filter((c) => !c.parent_id).map((t) => {
      const kids = cats.filter((c) => c.parent_id === t.id);
      return `<div class="catgroup" data-name="${esc(t.name.toLowerCase())}">
        <div class="row" data-id="${t.id}"><button class="navbtn expander" data-exp="${t.id}" ${kids.length ? "" : 'style="visibility:hidden"'}>${I.chev}</button><span class="dot" style="width:14px;height:14px;background:${esc(t.color || "var(--fill2)")}"></span><a class="main" href="#/items?category=${t.id}" style="color:var(--text);font-weight:600">${esc(t.name)}</a><span class="v">${t.total_count || ""}</span><button class="navbtn" data-edit="${t.id}">${I.more}</button></div>
        <div class="catkids" hidden>${kids.map((k) => `<div class="row sub" data-name="${esc(k.name.toLowerCase())}"><a class="main" href="#/items?category=${k.id}" style="color:var(--text)">${esc(k.name)}</a><span class="v">${k.item_count || ""}</span><button class="navbtn" data-edit="${k.id}">${I.more}</button></div>`).join("")}
          <button class="row sub center" data-addsub="${t.id}">${I.plus} Add sub-category</button></div>
      </div>`;
    }).join("")}</div>`
      : `<div class="empty">${I.tag}<div>No categories yet</div></div>`}
  </div>`;
  const ac = $("#autocat"); if (ac) ac.onclick = () => autoCategorize();
  $$("[data-exp]", view).forEach((b) => (b.onclick = () => {
    const kids = b.closest(".catgroup").querySelector(".catkids");
    kids.hidden = !kids.hidden; b.classList.toggle("open", !kids.hidden);
  }));
  $$("[data-addsub]", view).forEach((b) => (b.onclick = async () => {
    const n = await promptSheet({ title: "New sub-category", placeholder: "Name", label: "Create" });
    if (n) { await POST("api/categories", { name: n, parent_id: +b.dataset.addsub }).catch(fail); invalidate(); refresh(); }
  }));
  const cq = $("#catq");
  if (cq) cq.oninput = () => {
    const v = cq.value.toLowerCase().trim();
    $$(".catgroup", view).forEach((g) => {
      const subs = $$(".row.sub[data-name]", g);
      let any = !v || g.dataset.name.includes(v);
      subs.forEach((r) => { const hit = !v || r.dataset.name.includes(v) || g.dataset.name.includes(v); r.style.display = hit ? "" : "none"; any = any || hit; });
      g.style.display = any ? "" : "none";
      const kids = $(".catkids", g); kids.hidden = !v; $(".expander", g).classList.toggle("open", !!v);
    });
  };
  $("#defcats").onclick = async () => {
    const r = await POST("api/categories/defaults").catch(fail);
    if (r) { invalidate(); toast(r.added ? `Added ${r.added} missing categories` : "You already have them all"); refresh(); }
  };
  $("#addcat").onclick = async () => {
    const n = await promptSheet({ title: "New category", placeholder: "e.g. Electronics", label: "Create" });
    if (n) { await POST("api/categories", { name: n, color: colors[cats.length % colors.length] }).catch(fail); invalidate(); refresh(); }
  };
  $$("[data-edit]", view).forEach((b) => (b.onclick = async () => {
    const c = cats.find((x) => x.id === +b.dataset.edit);
    const v = await actionSheet([{ label: "Rename", value: "rename" }, { label: "Change color", value: "color" }, { label: "Delete", value: "del", red: true }], c.name);
    if (v === "rename") {
      const n = await promptSheet({ title: "Rename", value: c.name, label: "Save" });
      if (n) { await PUT(`api/categories/${c.id}`, { name: n, color: c.color }).catch(fail); invalidate(); refresh(); }
    } else if (v === "color") {
      const names = ["Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Indigo", "Purple", "Pink", "Brown", "Gray"];
      const i = await actionSheet(colors.map((col, k) => ({ label: names[k], value: col, icon: `<span class="dot" style="width:14px;height:14px;margin-right:10px;background:${col}"></span>` })), "Pick a color");
      if (i) { await PUT(`api/categories/${c.id}`, { name: c.name, color: i }).catch(fail); invalidate(); refresh(); }
    } else if (v === "del") {
      if (await confirmDanger("Delete category", c.parent_id ? "Items keep existing, just uncategorized." : "Deletes this group and its sub-categories. Items keep existing, just uncategorized.")) { await DEL(`api/categories/${c.id}`).catch(fail); invalidate(); refresh(); }
    }
  }));
}, "more");

// ------------------------------------------------------------------ duplicates
route(/^\/duplicates$/, async (view) => {
  const res = await GET("api/duplicates");
  const groups = res.groups;
  view.innerHTML = `<div class="page">${topbar({ title: "Duplicates", back: true })}
    <div class="largetitle">Duplicates</div>
    <div class="subtitle">Items that look like the same part. Extras are hidden from your item list until you merge them or mark them as different.</div>
    ${groups.length ? `<div class="btnrow" style="margin-bottom:6px"><button class="btn" id="mergeall">${I.copy} Merge all ${res.count}</button></div>
      <div class="help">Merging keeps the highlighted item, adds up stock, and moves photos, links and history onto it.</div>
      ${groups.map((g, gi) => `<div class="section-h"><span>${esc(g.reasons.join(" · "))}</span></div>
        <div class="group" data-g="${gi}">${g.items.map((it) => `
          <div class="row thumb brow dupitem" data-id="${it.id}">
            <button class="check ${it.id === g.keep_id ? "on" : ""}" data-keep="${gi}:${it.id}" aria-label="Keep this one">✓</button>
            ${picHTML(it.photo)}
            <a class="main" href="#/item/${it.id}" style="color:var(--text)"><div class="t">${esc(it.name)}</div>
              <div class="s">${fmt(it.quantity)} ${esc(it.unit || "")} · #${it.id}${it.part_number ? " · " + esc(it.part_number) : ""}${it.category_name ? " · " + esc(it.category_name) : ""}</div></a>
          </div>`).join("")}
          <div class="row" style="gap:8px"><button class="btn small" data-merge="${gi}" style="flex:1">Merge into ✓</button><button class="btn small gray" data-ignore="${gi}" style="flex:1">Not duplicates</button></div>
        </div>`).join("")}`
      : `<div class="empty">${I.copy}<div>No duplicates. Nice and tidy.</div></div>`}
  </div>`;
  const keep = groups.map((g) => g.keep_id);
  $$("[data-keep]", view).forEach((b) => (b.onclick = () => {
    const [gi, id] = b.dataset.keep.split(":").map(Number);
    keep[gi] = id; haptic();
    $$(`[data-g="${gi}"] .check`, view).forEach((c) => c.classList.toggle("on", c.dataset.keep === `${gi}:${id}`));
  }));
  $$("[data-merge]", view).forEach((b) => (b.onclick = async () => {
    const gi = +b.dataset.merge, g = groups[gi];
    const others = g.items.map((i) => i.id).filter((i) => i !== keep[gi]);
    await POST("api/duplicates/merge", { keep_id: keep[gi], merge_ids: others }).catch(fail);
    haptic(15); toast(`Merged ${others.length + 1} into one`); refresh();
  }));
  $$("[data-ignore]", view).forEach((b) => (b.onclick = async () => {
    const g = groups[+b.dataset.ignore];
    await POST("api/duplicates/ignore", { ids: g.items.map((i) => i.id) }).catch(fail);
    toast("Kept as separate items"); refresh();
  }));
  const ma = $("#mergeall");
  if (ma) ma.onclick = async () => {
    if (!(await confirmDanger(`Merge all ${res.count}`, "Each group becomes one item (keeping the one with the most info). Stock is added together."))) return;
    const r = await POST("api/duplicates/merge-all").catch(fail);
    if (r) { haptic(20); toast(`Merged ${r.merged} duplicate${r.merged === 1 ? "" : "s"}`); refresh(); }
  };
}, "more");

// ------------------------------------------------------------------ auto-categorize
async function autoCategorize() {
  const scope = await actionSheet([
    { label: "Only uncategorized items", value: "uncategorized" },
    { label: "Re-check every item", value: "all" },
  ], "AI sorts items into categories. You review before anything changes.");
  if (!scope) return;
  const s = openSheet({
    title: "Auto-categorize", full: true,
    left: { label: "Cancel", fn: () => s.close() },
    body: `<div class="status" style="padding-top:40px"><span class="spinner"></span> Sorting your parts…</div>`,
  });
  let res;
  try { res = await POST("api/ai/categorize", { scope }); }
  catch (e) { s.content.innerHTML = `<div class="empty">${I.alert}<div>${esc(e.message)}</div></div>`; return; }
  const props = res.proposals.map((p) => ({ ...p, on: true }));
  if (!props.length) { s.content.innerHTML = `<div class="empty">${I.tag}<div>Everything is already categorized nicely.</div></div>`; return; }
  const draw = () => {
    const groups = {};
    props.forEach((p, i) => (groups[p.category] = groups[p.category] || []).push(i));
    const n = props.filter((p) => p.on).length;
    s.content.innerHTML = `<div class="subtitle" style="margin:8px 16px">${props.length} suggestion${props.length === 1 ? "" : "s"}. Untick anything you disagree with.</div>
      ${Object.keys(groups).sort().map((g) => `<div class="section-h">${esc(g)}</div><div class="group">${groups[g].map((i) => {
        const p = props[i];
        return `<div class="row thumb brow ${p.on ? "" : "off"}"><button class="check ${p.on ? "on" : ""}" data-i="${i}">✓</button>${picHTML(p.photo)}
          <div class="main"><div class="t">${esc(p.name)}</div><div class="s">${p.current ? `was ${esc(p.current)}` : "uncategorized"}</div></div></div>`;
      }).join("")}</div>`).join("")}
      <div style="height:90px"></div>
      <div class="sticky-cta"><button class="btn block" id="apply" ${n ? "" : "disabled"}>${I.sparkle} Apply ${n}</button></div>`;
    $$("[data-i]", s.content).forEach((b) => (b.onclick = () => { haptic(); props[+b.dataset.i].on = !props[+b.dataset.i].on; draw(); }));
    $("#apply", s.content).onclick = async () => {
      const r = await POST("api/ai/categorize/apply", { assignments: props.filter((p) => p.on).map((p) => ({ id: p.id, category: p.category })) }).catch(fail);
      if (r) { invalidate(); s.close(); toast(`Categorized ${r.updated} item${r.updated === 1 ? "" : "s"}`); refresh(); }
    };
  };
  draw();
}

// ------------------------------------------------------------------ boot
render();
if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
