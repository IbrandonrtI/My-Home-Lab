function rgb(hex) { const m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); const n = m ? parseInt(m[1], 16) : 0; return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
let lookBarEl = null, pvTimer = null, pvSeq = 0;

function cleanOut(look) {
  const out = clone(look);
  out.tabs = {};
  for (const [n, c] of Object.entries(look.tabs)) if (c !== S.look.defaults.tabs[n]) out.tabs[n] = c;
  return out;
}
function lookOut() { return cleanOut(lookW); }
function rimShadow(level, bevel, tone) {
  const r = Math.max(0, Math.min(100, Number(level) || 0)) / 100, bv = Math.max(0, Math.min(100, Number(bevel) || 0)) / 100;
  const n = x => String(Math.round(x * 1000) / 1000), parts = [];
  if (r > 0) parts.push("inset 1px 1px 0 rgba(255,255,255," + n(0.7 * r) + ")", "inset -1px -1px 0 rgba(255,255,255," + n(0.32 * r) + ")", "inset 0 0 " + Math.round(10 + 14 * r) + "px rgba(255,255,255," + n(0.12 * r) + ")", "inset 0 12px 18px -14px rgba(255,255,255," + n(0.3 * r) + ")");
  if (bv > 0) {
    const light = tone === "light", shade = light ? "70,92,126" : "0,0,0";
    parts.push("inset 2px 2px 2px rgba(255,255,255," + n((light ? 0.95 : 0.4) * bv) + ")", "inset -2px -3px 4px rgba(" + shade + "," + n((light ? 0.2 : 0.45) * bv) + ")",
      "inset 0 0 14px rgba(255,255,255," + n((light ? 0.18 : 0.08) * bv) + ")", "0 8px 18px -8px rgba(" + shade + "," + n(0.38 * bv) + ")");
  }
  return parts.length ? parts.join(", ") : "0 0 0 0 transparent";
}
function glassAlpha(v) { if (v.glassTint === false) return 0; return v.glassClear ? 0.4 * (1 - v.glassLevel / 100) : v.glassOpacity / 100; }
function lookPreview(quiet) {
  const p = document.getElementById("mock");
  if (p) {
    p.style.setProperty("--pc", rgb(lookW.accent).join(", "));
    p.style.setProperty("--pg", rgb(lookW.glass).join(", "));
    p.style.setProperty("--pa", glassAlpha(lookW));
    p.style.setProperty("--pr", Math.min(lookW.radius, 30) + "px");
    p.style.setProperty("--pe", lookW.edge / 100);
    p.style.setProperty("--pbl", Math.round(lookW.glassBlur * 0.6) + "px");
    p.style.setProperty("--prm", rimShadow(lookW.glassRim, lookW.glassBevel, lookW.tone));
  }
  applyAccent();
  if (quiet) return;
  send({ type: "names", names: lookW.names || {}, logo: (lookW.logo && !lookW.logo.off) ? lookW.logo : {} });
  clearTimeout(pvTimer);
  pvTimer = setTimeout(async () => {
    const n = ++pvSeq;
    try { const r = await api("POST", "/api/look/css", { look: lookOut() }); if (n === pvSeq) send({ type: "css", css: r.css }); } catch (e) {  }
  }, 120);
}
function lookDirty() { return !same(lookNorm(lookW), lookNorm(S.look.values)); }
function lookNorm(v) { const o = clone(v); o.tabs = o.tabs || {}; o.names = o.names || {}; o.logo = o.logo || {}; return o; }
function bgDirty() {
  const b = S.background, B = bgW;
  return !!B && (B.url !== "" || B.blur !== (b.blur || "none") || B.saturate !== b.saturate || B.brightness !== b.brightness || B.opacity !== b.opacity);
}
function refreshLookBar() {
  if (!lookBarEl) return;
  put(lookBarEl, saveBar(lookDirty() || bgDirty(), saveLook, () => { discardPreview(); render(); }, "Save",
    h("button", { onclick: resetLook }, "Reset All Settings")));
}
function lookChanged() { lookPreview(); refreshLookBar(); try { sessionStorage.setItem("hlp-draft", JSON.stringify(lookW)); } catch (e) {  } }
function clearDraft() { try { sessionStorage.removeItem("hlp-draft"); } catch (e) {  } }
function startLook() {
  try {
    const d = JSON.parse(sessionStorage.getItem("hlp-draft") || "null");
    if (d && typeof d === "object") { const l = Object.assign(clone(S.look.values), d); if (!same(lookNorm(l), lookNorm(S.look.values))) return l; }
  } catch (e) {  }
  return clone(S.look.values);
}
async function saveLook() {
  try {
    const both = lookDirty() && bgDirty();
    let restarting = false;
    const bgSaved = bgDirty();
    if (bgSaved) {
      const B = bgW;
      const nums = { blur: B.blur, saturate: B.saturate, brightness: B.brightness, opacity: B.opacity };
      if (B.theme && B.url) { toast("Getting the picture of the theme…"); const r = await api("POST", "/api/background/theme", Object.assign({ theme: B.theme }, nums)); restarting = !!r.restarting; }
      else await api("POST", "/api/background", Object.assign({ url: B.url || undefined }, nums));
    }
    if (lookDirty()) {
      clearTimeout(pvTimer); pvSeq++;
      await api("POST", "/api/look", { look: lookOut(), version: S.look.version }, undefined, bgSaved ? "Look and background changed" : "");
    }
    if (lookDirty() || bgSaved) { clearTimeout(pvTimer); pvSeq++; send({ type: "saved", bg: !!bgSaved }); }
    const what = both ? "Look and background saved." : (bgDirty() ? "Background saved." : "Look saved.");
    toast(restarting ? what + " The dashboard restarts for about 10 seconds…" : what);
    await afterChange(false);
    if (restarting) setTimeout(() => send({ type: "reload", wait: true }), 4000);
  } catch (e) { fail(e); }
}
async function resetLook() {
  if (!await confirmBox("Reset All Settings?", "Colors, glass, shapes, names, logo and card and label colors return to the defaults. The picture, cards and layout are unchanged. Undo restores the previous settings.", "Reset All Settings")) return;
  try { await api("POST", "/api/look/reset", {}); send({ type: "saved" }); toast("All settings are back to the defaults."); await afterChange(false); } catch (e) { fail(e); }
}
function lookSlider(label, key, lo, hi, step, unit, hint) {
  const L = lookW;
  const val = h("span", { class: "val" }, L[key] + unit);
  const inp = h("input", { type: "range", min: lo, max: hi, step, value: L[key], "aria-label": label, oninput: ev => { L[key] = Number(ev.target.value); val.textContent = L[key] + unit; lookChanged(); } });
  return h("div", { class: "field" }, h("div", { class: "slider" }, h("span", { class: "lab" }, label), val, inp), hint ? h("div", { class: "hint" }, hint) : null);
}
function colorField(label, key, hint, swatches) {
  const L = lookW;
  const hex = h("input", { type: "text", value: L[key], maxlength: 7, "aria-label": label + " (hex code)", style: { maxWidth: "120px" } });
  const pick = h("input", { type: "color", value: L[key], "aria-label": label });
  const set = v => { L[key] = v; hex.value = v; pick.value = v; lookChanged(); };
  pick.addEventListener("input", () => set(pick.value));
  hex.addEventListener("input", () => { const v = hex.value.trim().toLowerCase(); if (/^#[0-9a-f]{6}$/.test(v) && v !== L[key]) { L[key] = v; pick.value = v; lookChanged(); } });
  hex.addEventListener("change", () => { const v = hex.value.trim().toLowerCase(); if (/^#[0-9a-f]{6}$/.test(v)) { if (v !== L[key]) set(v); hex.value = v; } else hex.value = L[key]; });
  return h("div", { class: "field" }, h("div", { class: "lab" }, label),
    h("div", { class: "row" }, pick, hex, h("div", { class: "swatches" }, (swatches || []).map(c => h("button", { class: "swatch", style: { background: c }, title: c, "aria-label": "Use " + c, onclick: () => set(c) })))),
    hint ? h("div", { class: "hint" }, hint) : null);
}

const SHIPPED_NAMES = [["homelab", "HomeLab", "Server Name", "The name under the big tile at the top left (and anywhere else it is shown)."],
  ["main", "Main Pool", "Main Pool Name", "The first drive: shown on its tile at the top and in the Stats tab."],
  ["backup", "Backup Pool", "Backup Pool Name", "The second drive. When it is not connected, its tile shows “Connect”, then this name, then “Drive”."]];
// Shrink a picture chosen as the logo before it is sent to the panel.
function shrinkLogo(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onerror = () => reject(new Error("That file could not be read."));
    fr.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("That file could not be read as a picture. Choose a PNG, JPG, WebP, GIF or SVG file."));
      img.onload = () => {
        const w = img.naturalWidth || 256, ht = img.naturalHeight || 256, big = Math.max(w, ht);
        let scale = file.type === "image/svg+xml" ? 256 / big : Math.min(1, 256 / big);
        for (let i = 0; i < 8; i++) {
          const c = document.createElement("canvas");
          c.width = Math.max(1, Math.round(w * scale)); c.height = Math.max(1, Math.round(ht * scale));
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
          const out = c.toDataURL("image/png");
          if (out.length <= 140000) return resolve(out);
          scale *= 0.7;
        }
        reject(new Error("That picture is too detailed to use as a logo. Use a simpler or smaller one."));
      };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  });
}
const LOGO_ART = [
  ["Server", '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M12 6.5h5M12 17.5h5"/><circle cx="7" cy="6.5" r="1" fill="#C"/><circle cx="7" cy="17.5" r="1" fill="#C"/>'],
  ["House", '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M10 20v-5.5h4V20"/>'],
  ["Cloud", '<path d="M7 18.5h10.5a4 4 0 0 0 .5-7.97A6 6 0 0 0 6.4 9.1 4.7 4.7 0 0 0 7 18.5z"/>'],
  ["Shield", '<path d="M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>'],
  ["Bolt", '<path d="M13 2.5 5 13.5h6l-1 8 8-11h-6z"/>'],
  ["Database", '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13"/><path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>'],
  ["Cube", '<path d="M12 2.8 20 7.4v9.2l-8 4.6-8-4.6V7.4z"/><path d="M4 7.4l8 4.6 8-4.6M12 12v9.2"/>'],
  ["Music", '<path d="M9 18V5.5l11-2V16"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>'],
  ["Movie", '<rect x="3" y="4.5" width="18" height="15" rx="3"/><path d="m10 9 5 3-5 3z"/>'],
  ["Terminal", '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 9 3 3-3 3M12.5 15H17"/>'],
];
function logoArt(i, color, px) {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="' + px + '" height="' + px + '" fill="none" stroke="' + color + '" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + LOGO_ART[i][1].replace(/#C/g, color) + "</svg>";
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}
function logoPicture(i, color) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onerror = () => reject(new Error("The logo could not be drawn."));
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = c.height = 256;
      c.getContext("2d").drawImage(img, 0, 0, 256, 256);
      resolve(c.toDataURL("image/png"));
    };
    img.src = logoArt(i, color, 256);
  });
}
let logoPick = { i: -1, color: "", src: "" };
// The card on the Look screen where the dashboard's title and other names are set.
function namesCard() {
  const L = lookW;
  L.names = L.names || {}; L.logo = L.logo || {};
  const inputs = SHIPPED_NAMES.map(([key, shipped, label, hint]) => {
    const inp = h("input", { type: "text", maxlength: 24, value: L.names[key] || "", placeholder: shipped, "aria-label": label,
      oninput: ev => { const v = ev.target.value.replace(/\s+/g, " ").trim(); if (v && v !== shipped) L.names[key] = v; else delete L.names[key]; lookChanged(); } });
    return [key, inp, h("div", { class: "field" }, h("div", { class: "lab" }, label), inp, h("div", { class: "hint" }, hint))];
  });
  const now = h("span", { class: "logo-now" }), nowName = h("span", { class: "small muted" });
  const status = h("div", {});
  const tiles = [];
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp,image/gif,image/svg+xml", hidden: true, onchange: async () => {
    const f = file.files[0]; file.value = "";
    if (!f) return;
    if (f.size > 15 * 1024 * 1024) return toast("That picture is larger than 15 MB. Choose a smaller one.", true);
    try { L.logo.src = await shrinkLogo(f); delete L.logo.off; logoPick.i = -1; lookChanged(); refresh(); toast("The logo is ready. Press Save to keep it."); } catch (e) { fail(e); }
  } });
  const color = logoPick.color || L.accent;
  LOGO_ART.forEach(([name], i) => tiles.push(h("button", { class: "logo-tile", title: name, "aria-label": "Use the " + name + " logo",
    onclick: async () => {
      try {
        L.logo.src = await logoPicture(i, logoPick.color || L.accent); delete L.logo.off;
        logoPick = { i, color: logoPick.color, src: L.logo.src };
        lookChanged(); refresh(); toast("The logo is ready. Press Save to keep it.");
      } catch (e) { fail(e); }
    } }, h("img", { src: logoArt(i, color, 40), alt: "", width: 40, height: 40 }))));
  const pick = h("input", { type: "color", value: color, "aria-label": "Color of the built-in logos" });
  pick.addEventListener("input", async () => {
    logoPick.color = pick.value;
    tiles.forEach((t, i) => { t.firstChild.src = logoArt(i, pick.value, 40); });
    if (logoPick.i >= 0 && logoPick.src === L.logo.src) {
      try { L.logo.src = await logoPicture(logoPick.i, pick.value); logoPick.src = L.logo.src; lookChanged(); refresh(); } catch (e) {  }
    }
  });
  const url = h("input", { type: "url", placeholder: "https://…", "aria-label": "Address of a logo picture on the web" });
  const menu = h("details", { class: "logo-menu" },
    h("summary", {}, now, h("b", {}, "Choose a Logo"), nowName),
    h("div", { class: "field" }, h("div", { class: "lab" }, "Built-In Logos"),
      h("div", { class: "logo-tiles" }, tiles),
      h("div", { class: "row", style: { marginTop: "8px", alignItems: "center" } }, pick, h("span", { class: "small muted" }, "Color of the built-in logos"))),
    h("div", { class: "field" }, h("div", { class: "lab" }, "Your Own Picture"),
      h("div", { class: "row" }, h("button", { class: "primary", onclick: () => file.click() }, "Choose a Picture from This Computer…"), file),
      h("div", { class: "row", style: { marginTop: "8px" } }, h("div", { class: "grow" }, url), h("button", { onclick: () => {
        const v = url.value.trim();
        if (!/^https?:\/\/\S+$/.test(v)) return toast("Type a web address that starts with http:// or https:// first.", true);
        L.logo.src = v; delete L.logo.off; logoPick.i = -1; lookChanged(); refresh(); toast("Press Save to keep it.");
      } }, "Use This Address")),
      h("div", { class: "hint" }, "A picture from the web needs an address that starts with http:// or https://.")));
  function refresh() {
    const has = !!L.logo.src, on = has && !L.logo.off;
    const shown = has && logoPick.i >= 0 && logoPick.src === L.logo.src;
    put(now, has ? h("img", { src: L.logo.src, alt: "", style: { opacity: on ? 1 : 0.4 } }) : h("span", { class: "small muted" }, "None"));
    nowName.textContent = !has ? "No logo chosen" : (shown ? LOGO_ART[logoPick.i][0] + (on ? "" : " (off)") : (on ? "Your picture" : "Your picture (off)"));
    tiles.forEach((t, i) => t.setAttribute("aria-pressed", String(on && logoPick.i === i && logoPick.src === L.logo.src)));
    const link = h("input", { type: "url", placeholder: "https://… (optional)", value: L.logo.link || "", "aria-label": "Web address the logo opens",
      oninput: ev => { const v = ev.target.value.trim(); if (v) L.logo.link = v; else delete L.logo.link; lookChanged(); } });
    const val = h("span", { class: "val" }, (L.logo.size || 48) + " px");
    put(status,
      h("div", { class: "lab" }, "Logo"),
      has ? [
        h("div", { class: "row logo-state" },
          h("button", { class: "chip logo-switch", "aria-pressed": String(on), onclick: () => { if (L.logo.off) delete L.logo.off; else L.logo.off = true; lookChanged(); refresh(); } }, on ? "Logo: On" : "Logo: Off"),
          h("span", { class: "small muted" }, on ? "Shown at the top left of the dashboard." : "Hidden. It is kept and can be turned on again.")),
        h("div", { class: "field" }, h("div", { class: "lab" }, "Web Address the Logo Opens"), link,
          h("div", { class: "hint" }, "Optional. Leave it empty for a logo that only shows.")),
        h("div", { class: "field" }, h("div", { class: "slider" }, h("span", { class: "lab" }, "Logo Size"), val,
          h("input", { type: "range", min: 24, max: 96, step: 2, value: L.logo.size || 48, "aria-label": "Logo size",
            oninput: ev => { const n = Number(ev.target.value); if (n === 48) delete L.logo.size; else L.logo.size = n; val.textContent = n + " px"; lookChanged(); } })))
      ] : h("p", { class: "muted small" }, "There is no logo yet. Open “Choose a Logo” below to pick one."));
  }
  refresh();
  return h("details", { class: "card" }, h("summary", {}, h("b", {}, "Names and Logo"), h("span", { class: "muted small" }, "Name the server and drives, add a logo")),
    h("p", { class: "muted" }, "Set custom names for the server and the two drives, and show a logo at the top left of the dashboard. Nothing is saved until “Save” is pressed."),
    h("div", { class: "grid cols2" },
      h("div", {}, inputs.map(x => x[2]),
        h("div", { class: "row" }, h("button", { class: "small", onclick: () => { L.names = {}; inputs.forEach(x => { x[1].value = ""; }); lookChanged(); } }, "Restore Original Names"))),
      status),
    menu);
}

let locDraft = null;
// The card on the Look screen where the city and time zone are chosen.
function locationCard() {
  const Lc = S.location || { timeZone: "", city: "", zones: [] };
  if (!locDraft) locDraft = { timeZone: Lc.timeZone, place: null };
  const D = locDraft;
  const zoneList = h("datalist", { id: "zone-list" }, (Lc.zones || []).map(z => h("option", { value: z })));
  const zone = h("input", { type: "text", list: "zone-list", value: D.timeZone, placeholder: "America/New_York", maxlength: 60, "aria-label": "Time zone",
    oninput: ev => { D.timeZone = ev.target.value.trim(); refreshBtn(); } });
  const q = h("input", { type: "text", placeholder: "Type a city, like Chicago", maxlength: 60, "aria-label": "City for the weather card",
    onkeydown: ev => { if (ev.key === "Enter") search(); } });
  const results = h("div", { class: "row", style: { flexWrap: "wrap", gap: "6px", marginTop: "8px" } });
  const now = h("div", { class: "hint" });
  const btn = h("button", { class: "primary", onclick: async () => {
    try {
      await api("POST", "/api/location", { timeZone: D.timeZone && D.timeZone !== Lc.timeZone ? D.timeZone : undefined, place: D.place || undefined });
      locDraft = null; toast("Saved. Reload the dashboard to see the new time and weather."); await afterChange(true);
    } catch (e) { fail(e); }
  } }, "Save Time Zone and City");
  function refreshBtn() {
    const changed = (D.timeZone && D.timeZone !== Lc.timeZone) || !!D.place;
    btn.disabled = !changed;
    put(now, h("span", {}, "Now: " + (Lc.city || "no city set") + (Lc.timeZone ? ", time zone " + Lc.timeZone : ", the clock uses the time zone of the browser"),
      D.place ? "  →  " + D.place.name + (D.place.region ? ", " + D.place.region : "") : ""));
  }
  async function search() {
    const text = q.value.trim();
    if (!text) return toast("Type the name of a city first.", true);
    try {
      const r = await api("POST", "/api/location/search", { q: text });
      put(results, r.places.length ? r.places.map(p => h("button", { class: "chip", onclick: () => { D.place = p; refreshBtn(); put(results, h("span", { class: "small muted" }, "Chosen: " + p.name + (p.region ? ", " + p.region : "") + (p.country ? ", " + p.country : "") + ". Press Save to keep it.")); } },
        p.name + (p.region ? ", " + p.region : "") + (p.country ? ", " + p.country : ""))) : h("span", { class: "small muted" }, "No city with that name was found. Try the name alone, without a state or country."));
    } catch (e) { fail(e); }
  }
  refreshBtn();
  return h("details", { class: "card" }, h("summary", {}, h("b", {}, "Time Zone and City"), h("span", { class: "muted small" }, "The dashboard clock and the weather card")),
    h("p", { class: "muted" }, "The installer detected these from the internet connection. Change them here if they are wrong. This changes only the dashboard's clock and its weather card."),
    h("div", { class: "grid cols2" },
      h("div", { class: "field" }, h("div", { class: "lab" }, "Time Zone"), zone, zoneList, h("div", { class: "hint" }, "Start typing a region or city, for example America/Chicago or Europe/London, and choose one from the list.")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "City for the Weather Card"),
        h("div", { class: "row" }, h("div", { class: "grow" }, q), h("button", { onclick: search }, "Search")), results)),
    now, h("div", { class: "row" }, btn));
}

