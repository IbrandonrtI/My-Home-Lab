"use strict";

const framed = window.parent !== window;
(function () {
  if (framed) return;
  const BANDS = [[1850, 2000, 0.9], [2450, 2650, 1.1]], root = document.documentElement;
  let timer = 0;
  const fit = () => {
    const phys = Math.round(window.innerWidth * window.devicePixelRatio), band = BANDS.find(b => phys >= b[0] && phys <= b[1]), z = band ? band[2] : 1;
    if (z === 1) { root.style.removeProperty("zoom"); root.style.removeProperty("--vh"); return; }
    root.style.zoom = String(z);
    root.style.setProperty("--vh", (1 / z).toFixed(4) + "vh");
  };
  fit();
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(fit, 150); });
})();
let S = null;
let view = "look";
let stripEl = null;
let lookW = null, bgW = null, layW = null, linkW = null, linkBase = "", schedW = null;
const root = document.getElementById("app");
const LOOKVIEWS = ["look"];
const BLURS = ["none", "sm", "md", "lg", "xl", "2xl", "3xl"];
const BLUR_NAMES = { none: "None", sm: "Small", md: "Medium", lg: "Large", xl: "Extra Large", "2xl": "Huge", "3xl": "Very Huge" };
const ONLY = new URLSearchParams(location.search).get("only");
const VIEWS = ONLY === "links" ? [["links", "Links"]]
  : [["look", "Look"], ["layout", "Layout"], ["cards", "Cards"], ["drives", "Drives"], ["upload", "Upload"], ["backups", "Backups"], ["updates", "Updates"]];
// Screens whose buttons act at once. They have no Save and no Undo in the header.
const NOSAVE = ["drives", "upload", "backups"];
if (ONLY === "links") view = "links";

try { const v = sessionStorage.getItem("hlp-view"); if (v && VIEWS.some(x => x[0] === v)) view = v; } catch (e) {  }
if (ONLY !== "links" && VIEWS.some(x => x[0] === location.hash.slice(1))) view = location.hash.slice(1);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value" || k === "checked" || k === "disabled" || k === "selected") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
function add(el, ...kids) {
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}
const put = (el, ...kids) => { el.replaceChildren(); return add(el, ...kids); };
const clone = o => JSON.parse(JSON.stringify(o));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
function send(msg) { if (framed) { try { window.parent.postMessage(Object.assign({ hlp: 1 }, msg), "*"); } catch (e) {  } } }

async function api(method, path, body, raw, undoGroup) {
  noChange = false;
  const opt = { method, credentials: "same-origin", headers: { "X-Panel": "1" } };
  if (undoGroup) opt.headers["X-Undo-Merge"] = undoGroup;
  if (raw) { opt.body = raw; opt.headers["Content-Type"] = "application/octet-stream"; }
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  let r;
  try { r = await fetch(path, opt); } catch (e) { throw new Error("The panel is not responding. Check that the server is running."); }
  let js = {};
  try { js = await r.json(); } catch (e) {  }
  if (r.status === 401 && path !== "/api/login") { S = null; showLogin(); throw new Error(js.error || "Please log in again."); }
  if (!r.ok) { const err = new Error(js.error || ("Something went wrong (" + r.status + ").")); err.status = r.status; throw err; }
  noChange = method === "POST" && js.changed === false;
  return js;
}

let toastTimer = null, noChange = false;
function toast(msg, bad, action) {
  if (noChange && !bad && !action && !/^Undone/.test(msg)) msg = "Nothing changed. It was already set that way.";
  noChange = false;
  const t = document.getElementById("toast");
  t.className = "show" + (bad ? " bad" : "");
  put(t, h("span", {}, msg), action ? h("button", { class: "small", onclick: action[1] }, action[0]) : null);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, bad ? 7000 : 3800);
}
const fail = e => toast(e.message || String(e), true);

// A small label on a card: does a change there wait for the Save button, or is it kept as soon as its own button is pressed?
const SAVE_TAGS = {
  save: ["Needs Save", "Shown on the dashboard as a preview. It is kept only after Save (top right) is pressed."],
  now: ["Saves Now", "Kept as soon as the button on this card is pressed. Save (top right) is not needed."],
  run: ["Runs Now", "The buttons on this card act as soon as they are pressed. Save (top right) is not needed."]
};
function saveTag(kind) { const t = SAVE_TAGS[kind]; return h("span", { class: "stag " + kind, title: t[1] }, t[0]); }
// A card heading with its label.
function cardHead(text, kind) { return h("h2", {}, text, saveTag(kind)); }

function confirmBox(title, text, yes, danger) {
  return new Promise(resolve => {
    const d = h("dialog", {}, h("h2", {}, title), h("p", {}, text),
      h("div", { class: "actions" },
        h("button", { onclick: () => { d.close(); resolve(false); } }, "Cancel"),
        h("button", { class: danger ? "danger" : "primary", onclick: () => { d.close(); resolve(true); } }, yes)));
    d.addEventListener("close", () => { d.remove(); resolve(false); });
    document.body.append(d);
    d.showModal();
  });
}

function askText(title, label, value) {
  return new Promise(resolve => {
    const inp = h("input", { type: "text", value: value || "", maxlength: 40, "aria-label": label });
    let done = false;
    const finish = v => { if (!done) { done = true; resolve(v); } d.close(); };
    inp.addEventListener("keydown", e => { if (e.key === "Enter") finish(inp.value.trim()); });
    const d = h("dialog", {}, h("h2", {}, title), h("div", { class: "field" }, h("label", {}, label), inp),
      h("div", { class: "actions" }, h("button", { onclick: () => finish(null) }, "Cancel"), h("button", { class: "primary", onclick: () => finish(inp.value.trim()) }, "OK")));
    d.addEventListener("close", () => { d.remove(); finish(null); });
    document.body.append(d);
    d.showModal();
    inp.focus();
    inp.select();
  });
}

function afterChange(reload) {
  return api("GET", "/api/state").then(s => {
    const y = window.scrollY;
    S = s;
    lookW = bgW = layW = linkW = schedW = null;
    clearDraft();
    render();
    window.scrollTo(0, y);
    if (reload && autoReload()) setTimeout(() => send({ type: "reload" }), 900);
  });
}
function autoReload() { try { return localStorage.getItem("hlp-auto") !== "0"; } catch (e) { return true; } }

const MDI = ("home server router lan wifi network web earth cloud database harddisk folder file-document image camera music headphones movie youtube play television " +
  "gamepad-variant steam controller book school briefcase email calendar clock chart-line monitor-dashboard desktop-classic laptop cellphone tablet printer " +
  "shield-lock lock key account-circle cog tune wrench hammer palette brush cart shopping credit-card bank wallet cash heart star bookmark link-variant " +
  "github git code-tags console terminal docker memory chip lightning-bolt fire water weather-sunny moon-waning-crescent food coffee car airplane map-marker " +
  "newspaper rss message chat phone video podcast radio headset download upload sync backup-restore archive trash-can magnify information help alert " +
  "check-circle popcorn robot bug flask lightbulb leaf paw dumbbell run bike stethoscope hospital-box scale-balance gavel briefcase-search account-search " +
  "file-search domain office-building school-outline notebook pencil format-list-bulleted view-dashboard view-grid cube-outline puzzle application").split(" ");

function iconInfo(name) {
  name = (name || "").trim();
  if (!name) return null;
  if (/^https?:\/\//i.test(name)) return { url: name, cls: "" };
  let m = name.match(/^mdi-([a-z0-9-]+?)(?:-?#[0-9a-fA-F]{3,8})?$/);
  if (m) return { url: "https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/" + m[1] + ".svg", cls: "mdi" };
  m = name.match(/^si-([a-z0-9-]+?)(?:-?#[0-9a-fA-F]{3,8})?$/);
  if (m) return { url: "https://cdn.jsdelivr.net/npm/simple-icons@11.14.0/icons/" + m[1] + ".svg", cls: "mdi" };
  m = name.match(/^([A-Za-z0-9._-]+)\.(svg|png)$/);
  if (m) return { url: "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/" + m[2] + "/" + m[1] + "." + m[2], cls: "" };
  return null;
}
function iconEl(name) {
  const i = iconInfo(name);
  const box = h("span", { class: "ico" });
  if (i) box.append(h("img", { src: i.url, class: i.cls, alt: "", loading: "lazy", referrerpolicy: "no-referrer", onerror: ev => ev.target.remove() }));
  return box;
}
function siteIcon(href) {
  try { return "https://www.google.com/s2/favicons?domain=" + new URL(href).hostname + "&sz=128"; } catch (e) { return ""; }
}
let iconLib = null;
function loadIcons() {
  if (!iconLib) iconLib = api("GET", "/api/icons").catch(() => ({ apps: [], mdi: [] }));
  return iconLib;
}
const APP_ICON_URL = n => "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/" + n.slice(n.lastIndexOf(".") + 1) + "/" + n;
function pickIcon(current) {
  return new Promise(resolve => {
    let kind = "apps", lib = { apps: [], mdi: [] };
    const grid = h("div", { class: "picker" });
    const note = h("p", { class: "muted small" });
    const q = h("input", { type: "text", placeholder: "Search, for example: portainer, plex, music, server", "aria-label": "Search icons" });
    const tabs = h("div", { class: "chips", style: { margin: "10px 0" } });
    const MAX = 120;
    const choose = v => { d.close(); resolve(v); };
    const draw = () => {
      const t = q.value.trim().toLowerCase();
      const names = kind === "apps" ? (lib.apps.length ? lib.apps : []) : (lib.mdi.length ? lib.mdi : MDI);
      const hits = names.filter(n => !t || n.toLowerCase().includes(t));
      put(grid, hits.slice(0, MAX).map(n => kind === "apps"
        ? h("button", { title: n, onclick: () => choose(n) }, h("img", { src: APP_ICON_URL(n), alt: "", loading: "lazy" }), n.replace(/\.(svg|png)$/, ""))
        : h("button", { title: "mdi-" + n, onclick: () => choose("mdi-" + n) }, h("img", { src: iconInfo("mdi-" + n).url, class: "mdi", alt: "", loading: "lazy" }), n)));
      if (!hits.length) grid.append(h("p", { class: "muted" }, kind === "apps" && !lib.apps.length
        ? "The list of app icons could not be loaded (check that the server is online). An icon name such as plex.svg can still be typed in the icon box."
        : "No icons match. Try a shorter search term."));
      put(note, hits.length > MAX ? "Showing the first " + MAX + " of " + hits.length + ". Type more letters to narrow it down." : hits.length + " icon" + (hits.length === 1 ? "" : "s"));
    };
    const drawTabs = () => put(tabs, [["apps", "Apps and Logos"], ["mdi", "Symbols"]].map(([id, text]) =>
      h("button", { class: "chip", "aria-pressed": String(kind === id), onclick: () => { kind = id; drawTabs(); draw(); } }, text)));
    q.addEventListener("input", draw);
    const d = h("dialog", { class: "wide" }, h("h2", {}, "Choose an Icon"), q, tabs, grid, note,
      h("p", { class: "muted small" }, "Apps and Logos contains icons for thousands of programs (Portainer, Plex, Nextcloud…). Symbols are simple pictures such as a house or a folder. A name can also be typed in the icon box, or the web address of a picture."),
      h("div", { class: "actions" }, h("button", { onclick: () => { d.close(); resolve(current); } }, "Cancel")));
    d.addEventListener("close", () => { d.remove(); resolve(current); });
    document.body.append(d);
    drawTabs();
    put(grid, h("p", { class: "muted" }, "Loading the icon library…"));
    d.showModal();
    q.focus();
    loadIcons().then(l => { lib = l; if (!lib.apps.length && lib.mdi.length) kind = "mdi"; drawTabs(); draw(); });
  });
}
function iconField(initial, getHref) {
  const inp = h("input", { type: "text", value: initial || "", placeholder: "mdi-home, plex.svg or a picture address", "aria-label": "Icon" });
  const prev = h("span", {});
  const redraw = () => put(prev, iconEl(inp.value));
  inp.addEventListener("input", redraw);
  redraw();
  const row = h("div", { class: "row tight" }, prev, h("div", { class: "grow" }, inp),
    h("button", { class: "small", type: "button", onclick: async () => { inp.value = await pickIcon(inp.value); redraw(); } }, "Choose…"),
    getHref ? h("button", { class: "small", type: "button", title: "Use the picture the website itself uses", onclick: () => {
      const u = siteIcon(getHref());
      if (!u) return toast("Type the address first.", true);
      inp.value = u; redraw();
    } }, "Use the Site's Icon") : null);
  const swatch = h("input", { type: "color", value: ((inp.value.match(/#[0-9a-fA-F]{6}$/) || ["#ffffff"])[0]), "aria-label": "Icon color", title: "Color of the icon" });
  const colorRow = h("div", { class: "row tight", style: { marginTop: "6px" } }, h("span", { class: "muted small" }, "Icon color"), swatch,
    h("button", { class: "small", type: "button", onclick: () => { inp.value = inp.value.replace(/-?#[0-9a-fA-F]{3,8}$/, ""); redraw(); } }, "No Color"),
    h("span", { class: "muted small" }, "(for the round icon library: names that start with mdi- or si-)"));
  swatch.addEventListener("input", () => {
    const base = inp.value.trim().replace(/-?#[0-9a-fA-F]{3,8}$/, "");
    if (!/^(mdi|si)-/.test(base)) { toast("Colors work with icons that start with mdi- or si-. Choose one of those first.", true); return; }
    inp.value = base + "-" + swatch.value;
    redraw();
  });
  return { input: inp, el: h("div", { class: "field" }, h("label", {}, "Icon"), row, colorRow, h("div", { class: "hint" }, "Optional. Leave it empty for no icon.")) };
}

function showLogin(passwordSet = true, msg = "") {
  DR = DRhealth = DRcheck = null;
  const err = h("div", { class: "err", role: "alert" }, msg);
  const pw = h("input", { type: "password", autocomplete: "current-password", "aria-label": "Password", placeholder: "Panel password" });
  const go = async () => {
    err.textContent = "";
    try { await api("POST", "/api/login", { password: pw.value }); await start(); }
    catch (e) { err.textContent = e.message; pw.select(); }
  };
  pw.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  put(root, h("div", { class: "login card" },
    h("h1", {}, "Customize Your Dashboard"),
    h("p", { class: "muted" }, "Enter the control panel password. Initially this is the admin password chosen at the start of the installation."),
    passwordSet ? [pw, err, h("button", { class: "primary", onclick: go }, "Log In")] :
      h("p", {}, "No password is set. On the server, open a terminal and run: ", h("b", {}, "homelab panel password")),
    framed ? h("p", { class: "muted small" }, "If the login is not kept, the browser may be blocking it inside the dashboard. ", h("a", { href: location.href, target: "_blank", rel: "noopener" }, "Open the panel in its own tab"), ".") : null));
  if (passwordSet) pw.focus();
  if (ONLY === "edit") send({ type: "edit-login" });
}

window.addEventListener("hashchange", () => {
  const id = location.hash.slice(1);
  if (ONLY === "links" || !S || id === view || !VIEWS.some(x => x[0] === id)) return;
  if (!(LOOKVIEWS.includes(view) && LOOKVIEWS.includes(id))) discardPreview();
  view = id;
  render();
  window.scrollTo(0, 0);
});

function render() {
  if (!S) return;
  try { sessionStorage.setItem("hlp-view", view); } catch (e) {  }
  if (ONLY !== "links" && location.hash.slice(1) !== view) { try { history.replaceState(null, "", "#" + view); } catch (e) {  } }
  const fns = { look: viewLook, layout: viewLayout, cards: viewCards, drives: viewDrives, upload: viewUpload, backups: viewBackups, updates: viewUpdates, links: viewLinks };
  if (ONLY === "links") { put(root, viewLinks()); applyAccent(); return; }
  footEl = h("div", { class: "hactions" });
  drawFoot(false, null, null);
  const auto = h("input", { type: "checkbox", checked: autoReload(), id: "auto", onchange: ev => { try { localStorage.setItem("hlp-auto", ev.target.checked ? "1" : "0"); } catch (e) {  } } });
  stripEl = h("div", { class: "substrip" });
  // On a phone the header already takes much of the screen, so the section menu scrolls with the page there.
  const narrow = window.matchMedia("(max-width: 760px)").matches;
  put(root,
    h("div", { class: "stickytop" },
      h("header", { class: "top" },
        h("h1", {}, "Customize Your Dashboard"),
        h("nav", { class: "tabs", role: "tablist" }, VIEWS.map(([id, label]) =>
          h("button", { role: "tab", "aria-selected": String(view === id), onclick: () => { if (view !== id) { if (!(LOOKVIEWS.includes(view) && LOOKVIEWS.includes(id))) discardPreview(); view = id; render(); window.scrollTo(0, 0); } } }, label))),
        footEl),
      narrow ? null : stripEl),
    narrow ? stripEl : null,
    fns[view](),
    framed ? h("p", { class: "muted small" }, h("label", { for: "auto" }, auto, " Refresh the dashboard automatically after layout, cards or links change")) : null);
  applyAccent();
}
function colorParts(str) {
  str = String(str || "");
  let m = str.match(/#([0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3})\b/i);
  if (m) {
    let x = m[1];
    if (x.length === 3) x = x.split("").map(c => c + c).join("");
    return [parseInt(x.slice(0, 2), 16), parseInt(x.slice(2, 4), 16), parseInt(x.slice(4, 6), 16), x.length === 8 ? parseInt(x.slice(6, 8), 16) / 255 : 1];
  }
  m = str.match(/rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)/i);
  if (m) {
    let a = m[4] === undefined ? 1 : m[4].endsWith("%") ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
    return [+m[1], +m[2], +m[3], isNaN(a) ? 1 : a];
  }
  return null;
}
function optionColors(ui) {
  const base = colorParts(ui.bg) || colorParts("#0a0f19");
  let c = colorParts(ui.panel2) || colorParts(ui.panel) || colorParts(ui.field) || [23, 32, 51, 1];
  const a = Math.max(0, Math.min(1, c[3]));
  const mix = [0, 1, 2].map(i => Math.round(c[i] * a + base[i] * (1 - a)));
  const lum = (0.2126 * mix[0] + 0.7152 * mix[1] + 0.0722 * mix[2]) / 255;
  return { bg: "rgb(" + mix.join(", ") + ")", fg: lum > 0.55 ? "#101418" : "#f2f5fa", dark: lum <= 0.55 };
}
function allThemes() { return ((S.look && S.look.themes) || []).concat(S.mythemes || []); }
function applyAccent() {
  const v = lookW || S.look.values;
  const [r, g, b] = rgb(v.accent);
  const st = document.documentElement.style;
  st.setProperty("--accent", r + ", " + g + ", " + b);
  const t = allThemes().find(x => x.id === v.theme), ui = (t && t.ui) || {};
  for (const [k, name] of [["bg", "--bg"], ["panel", "--panel"], ["panel2", "--panel2"], ["line", "--line"], ["field", "--field"], ["dialog", "--dialog"], ["blur", "--pblur"]]) {
    if (ui[k]) st.setProperty(name, ui[k]); else st.removeProperty(name);
  }
  const opt = optionColors(ui);
  st.setProperty("--opt-bg", opt.bg); st.setProperty("--opt-fg", opt.fg);
  document.documentElement.classList.toggle("glassy", !!ui.blur);
  if (ui.rim) st.setProperty("--prim", rimShadow(ui.rim)); else st.removeProperty("--prim");
}
async function doUndo() {
  try { const r = await api("POST", "/api/undo", {}); send({ type: "clear" }); toast("Undone: " + r.undone); await afterChange(true); } catch (e) { fail(e); }
}
function discardPreview() { send({ type: "clear" }); lookW = bgW = layW = null; clearDraft(); }

