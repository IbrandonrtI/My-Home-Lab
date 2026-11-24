function themeColors(t) {
  const P = S.paint, out = { cards: {}, links: {}, paintAll: t.paintAll || "" };
  if (t.paintLinks) for (const it of P.links) out.links[it.name] = t.paintLinks;
  if (!t.palette || !t.palette.length) return out;
  const groups = [];
  const pick = g => { let i = groups.indexOf(g); if (i < 0) { groups.push(g); i = groups.length - 1; } return t.palette[i % t.palette.length]; };
  for (const list of [P.cards, P.stats, P.calendar]) for (const it of list) out.cards[it.id] = pick(it.group);
  for (const it of P.links) out.links[it.name] = pick(it.group);
  return out;
}
let themePic = true;
function themeBg(t) {
  const g = t && t.background;
  if (!g || !themePic) return null;
  return { url: g.url, blur: g.blur, saturate: g.saturate, brightness: g.brightness, opacity: g.opacity, theme: t.id };
}
function savedBg() { const b = S.background; return { url: "", blur: b.blur || "none", saturate: b.saturate, brightness: b.brightness, opacity: b.opacity }; }
function previewBg() { const B = bgW || savedBg(), b = S.background; send({ type: "bg", image: B.url || b.image, blur: B.blur, saturate: B.saturate, brightness: B.brightness, opacity: B.opacity }); }
// What belongs to the person and not to a theme: a theme never changes these.
const PERSONAL = ["labels", "labelIcon", "names", "logo", "motion", "iconStyle", "hello", "helloName", "dockMode", "dock"];
function themeLook(t) {
  const def = S.look.defaults;
  const base = clone(def); base.tabs = Object.assign({}, def.tabs);
  const pl = clone(t.look); const tabs = Object.assign({}, base.tabs, pl.tabs || {}); delete pl.tabs;
  const col = themeColors(t);
  return Object.assign(base, pl, { tabs, theme: t.id, cards: col.cards, links: col.links, paintAll: col.paintAll });
}
function chooseTheme(t) {
  const next = themeLook(t);
  for (const k of PERSONAL) next[k] = clone(lookW[k]);
  lookW = next;
  bgW = (t.id !== S.look.values.theme && themeBg(t)) || null;
  render(); lookChanged(); previewBg();
  toast(lookDirty() || bgDirty() ? t.name + " is a draft. Press Save to keep it, or Discard Changes to revert." : t.name + " is already in use.");
}
async function chooseMyTheme(t) {
  const server = t.parts.filter(p => p === "layout" || p === "cards");
  if (server.length) {
    const what = server.map(p => p === "layout" ? "layout (tabs and groups)" : "cards (their names, icons, groups and order)").join(" and ");
    const draft = t.parts.includes("look") || t.parts.includes("background");
    if (!await confirmBox("Use “" + t.name + "”?", "This also restores the theme's " + what + ". It applies right away, and Undo reverts it. " +
      (draft ? "The colors and the picture are a draft until you press Save." : ""), "Use This Theme")) return;
    try { await api("POST", "/api/mytheme", { op: "apply", id: t.id }); await afterChange(true); } catch (e) { return fail(e); }
    if (framed && autoReload()) await new Promise(r => setTimeout(r, 1400));
  }
  const def = S.look.defaults;
  if (t.parts.includes("look")) {
    const base = clone(def); base.tabs = Object.assign({}, def.tabs);
    const pl = clone(t.look || {}); const tabs = Object.assign({}, base.tabs, pl.tabs || {}); delete pl.tabs;
    lookW = Object.assign(base, pl, { tabs, theme: t.id });
  } else if (!lookW) lookW = startLook();
  if (t.parts.includes("background") && t.background) {
    const g = t.background;
    bgW = { url: g.image || "", blur: g.blur || "none", saturate: g.saturate, brightness: g.brightness, opacity: g.opacity };
  }
  render(); lookChanged(); previewBg();
  toast(t.name + (lookDirty() || bgDirty() ? " is a draft. Press Save to keep it, or Discard Changes to revert." : " is in place."));
}
async function refreshMyThemes() { const s = await api("GET", "/api/state"); S.mythemes = s.mythemes; S.undo = s.undo; render(); }
// The dialog that saves the current look as a new theme.
function createThemeDialog() {
  const name = h("input", { type: "text", maxlength: 30, placeholder: "For example: Movie Night", "aria-label": "Theme name" });
  const blurb = h("input", { type: "text", maxlength: 90, placeholder: "Optional: a few words about it", "aria-label": "Theme description" });
  const err = h("div", { class: "err", role: "alert", style: { color: "var(--bad)", minHeight: "20px" } });
  const parts = [
    ["look", "Look", "Colors, glass, shapes, the colors of tabs and cards, names and logo, as they are on this screen now (also what is not saved yet).", true],
    ["background", "Background Picture", "The picture and its sliders (blur, brightness and so on).", true],
    ["layout", "Layout", "The tabs, which groups are on each tab, their order, icons and columns (the Layout screen).", false],
    ["cards", "Cards", "The list of cards with their names, icons, texts, groups and order (the Cards screen). Applying the theme later restores them. Undo restores the previous cards.", false]];
  const boxes = parts.map(([id, label, hint, on]) => ({ id, box: h("input", { type: "checkbox", checked: on, "aria-label": label }), label, hint }));
  const d = h("dialog", {}, h("h2", {}, "Make a Theme"),
    h("p", { class: "muted" }, "The settings on the Look screen are included. Select what else the theme should contain, so that applying it later changes those too."),
    h("div", { class: "field" }, h("label", {}, "Name"), name), h("div", { class: "field" }, h("label", {}, "Description"), blurb),
    boxes.map(b => h("label", { class: "partrow" }, b.box, h("span", {}, h("b", {}, b.label), h("span", { class: "muted small" }, b.hint)))),
    err,
    h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Cancel"), h("button", { class: "primary", onclick: async () => {
      err.textContent = "";
      const chosen = boxes.filter(b => b.box.checked).map(b => b.id);
      if (!name.value.trim()) { err.textContent = "Give the theme a name."; name.focus(); return; }
      if (!chosen.length) { err.textContent = "Select at least one item for the theme to contain."; return; }
      const cur = allThemes().find(x => x.id === lookW.theme);
      const B = bgW || savedBg(), sb = S.background;
      const body = { op: "create", name: name.value.trim(), blurb: blurb.value.trim(), parts: chosen, look: lookOut(), ui: cur && cur.ui,
        background: { image: B.url || sb.image || "", blur: B.blur || "none", saturate: B.saturate, brightness: B.brightness, opacity: B.opacity } };
      try {
        const r = await api("POST", "/api/mytheme", body);
        d.close(); await refreshMyThemes();
        if (chosen.includes("look")) { lookW.theme = r.id; lookChanged(); render(); }
        toast("The theme “" + body.name + "” is saved. It is listed under Your Themes.");
      } catch (e) { err.textContent = e.message; }
    } }, "Save the Theme")));
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  name.focus();
}
function myThemeTile(t) {
  const partName = { look: "Look", background: "Picture", layout: "Layout", cards: "Cards" };
  const tile = themeTile(t, lookW.theme, () => chooseMyTheme(t));
  const chips = h("div", { class: "chips2" }, t.parts.map(p => h("span", { class: "badge" }, partName[p])));
  return h("div", { class: "mytheme" }, tile, chips,
    h("div", { class: "row tight" },
      h("button", { class: "small", onclick: async () => {
        const n = await askText("Rename the Theme", "New name for “" + t.name + "”", t.name);
        if (!n || n === t.name) return;
        try { await api("POST", "/api/mytheme", { op: "rename", id: t.id, name: n, blurb: t.blurb }); await refreshMyThemes(); } catch (e) { fail(e); }
      } }, "Rename"),
      h("button", { class: "small danger", onclick: async () => {
        if (!await confirmBox("Delete “" + t.name + "”?", "The theme is removed from the list. The current dashboard is unchanged.", "Delete the Theme", true)) return;
        try { await api("POST", "/api/mytheme", { op: "delete", id: t.id }); await refreshMyThemes(); toast("Deleted."); } catch (e) { fail(e); }
      } }, "Delete")));
}
function themeTile(t, now, onpick) {
  const lk = Object.assign({}, S.look.defaults, t.look);
  const alpha = glassAlpha(lk);
  const cols = (t.palette && t.palette.length) ? t.palette : t.paintAll ? [t.paintAll].concat(t.paintLinks ? [t.paintLinks] : []) : S.paint.cards.slice(0, 3).map(c => c.color);
  const shot = h("div", { class: "shot" },
    h("div", { class: "tabs" }, h("span", { class: "on" }), h("span", {}), h("span", {})),
    h("div", { class: "cards" }, [0, 1, 2].map(i => { const c = h("i", {}); c.style.setProperty("--c", rgb(cols[i % cols.length] || lk.accent).join(", ")); return c; })));
  shot.style.setProperty("--pc", rgb(lk.accent).join(", "));
  shot.style.setProperty("--pg", rgb(lk.glass).join(", "));
  shot.style.setProperty("--pa", alpha);
  shot.style.setProperty("--pr", Math.round(Math.min(lk.radius, 30) * 0.5) + "px");
  shot.style.setProperty("--pe", lk.edge / 100);
  shot.style.setProperty("--bl", Math.round(lk.glassBlur * 0.5) + "px");
  shot.style.setProperty("--prm", rimShadow(lk.glassRim, lk.glassBevel, lk.tone));
  return h("button", { class: "theme", "aria-pressed": String(now === t.id), onclick: onpick || (() => chooseTheme(t)) }, shot, h("b", {}, t.name), h("span", { class: "small muted" }, t.blurb));
}
function themesCard() {
  return h("div", { class: "card" }, h("h2", {}, "Themes"),
    h("p", { class: "muted" }, "A theme changes the colors, glass and shapes of the dashboard and of this panel together, and gives every card, tile and bookmark a matching color. Choose one to preview it. Nothing is saved until “Save” is pressed."),
    h("div", { class: "themes" }, S.look.themes.map(t => themeTile(t, lookW.theme))),
    (S.mythemes || []).length ? [h("h3", {}, "Your Themes"), h("div", { class: "themes" }, S.mythemes.map(myThemeTile))] : null,
    h("div", { class: "row", style: { marginBottom: "10px" } }, h("button", { onclick: createThemeDialog }, "+ Make a Theme from These Settings…")),
    h("label", { class: "row check" }, h("input", { type: "checkbox", checked: themePic, "aria-label": "Also change the background picture", onchange: ev => {
      themePic = ev.target.checked;
      const t = S.look.themes.find(x => x.id === lookW.theme);
      bgW = (themePic && t) ? themeBg(t) : null;
      render(); previewBg(); refreshLookBar();
    } }), h("span", {}, "Also Change the Background Picture")),
    h("p", { class: "muted small" }, "Each theme has a matching background picture. When the box is selected, the picture and its sliders change when a theme is chosen. Clear the box to keep the current picture. Names and the logo are never changed. Colors set for single cards are replaced by the theme’s colors. Any setting below can still be changed after choosing a theme."));
}

// Motion, icons, greeting and quick launch.
function polishCard() {
  const L = lookW;
  const box = h("div", {});
  const chip = (on, text, set) => h("button", { class: "chip", "aria-pressed": String(on), onclick: () => { set(); lookChanged(); draw(); } }, text);
  function draw() {
    const cards = (S.paint.cards || []).filter(c => c.id !== "navidrome-card");
    const mode = L.dockMode || "auto";
    const picked = Array.isArray(L.dock) ? L.dock : [];
    put(box,
      h("div", { class: "field" }, h("div", { class: "lab" }, "Motion"),
        h("div", { class: "chips" }, [["off", "Off"], ["subtle", "Subtle"], ["lively", "Lively"]].map(([k, t]) => chip((L.motion || "subtle") === k, t, () => { L.motion = k; }))),
        h("div", { class: "hint" }, "Cards lift when pointed at, a soft light follows the pointer, a slow glow drifts behind the cards, status dots pulse and numbers count up. Lively makes all of it larger and slower. Off turns all of it off. A device that is set to reduce motion always gets Off.")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Icons"),
        h("div", { class: "chips" }, chip((L.iconStyle || "plate") === "plate", "Glass Plates", () => { L.iconStyle = "plate"; }), chip(L.iconStyle === "none", "Plain", () => { L.iconStyle = "none"; })),
        h("div", { class: "hint" }, "Glass Plates puts every icon on the same rounded glass tile, so icons of different shapes and colors look like a set. Plain shows the icons as they are.")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Greeting"),
        h("label", { class: "row check" }, h("input", { type: "checkbox", checked: L.hello !== false, "aria-label": "Show a greeting at the top of the page", onchange: ev => { L.hello = ev.target.checked; lookChanged(); } }),
          h("span", {}, "Show a Greeting at the Top of the Page")),
        h("input", { type: "text", maxlength: 24, value: L.helloName || "", placeholder: S.look.helloDefault || "Your name", "aria-label": "Name in the greeting",
          oninput: ev => { L.helloName = ev.target.value.replace(/\s+/g, " ").trim(); lookChanged(); } }),
        h("div", { class: "hint" }, "The page shows just this name at the top, with no “Good morning” in front. Leave it empty to use the admin name you typed in the installer (or, if there is none, the name of the account the panel runs as). The name and the quick launch icons appear after Save.")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Quick Launch"),
        h("div", { class: "chips" }, [["auto", "Most Visited"], ["custom", "Choose Cards"], ["off", "Off"]].map(([k, t]) => chip(mode === k, t, () => { L.dockMode = k; }))),
        h("div", { class: "hint" }, "A row of icons in the bar next to the search icon that opens a service with one click. Most Visited starts with Jellyfin, Immich, Nextcloud, FileBrowser and Portainer, then moves the services you open most often to the front (counted in this browser only). Choose Cards lets you pick up to 12 (the order is the order you tick them). Off hides the row and its three-dot menu. The three-dot menu at the end of the row lets you add your own links and reorder the icons in this browser. It is not shown on a phone.")),
      mode === "custom" ? h("div", { class: "grid cols2" }, cards.map(c => {
        const on = picked.includes(c.id);
        return h("label", { class: "row check" }, h("input", { type: "checkbox", checked: on, "aria-label": c.name, onchange: ev => {
          const cur = Array.isArray(L.dock) ? L.dock.slice() : [];
          if (ev.target.checked) { if (cur.length >= 12) { ev.target.checked = false; return toast("Up to 12 cards can be in quick launch.", true); } cur.push(c.id); }
          else cur.splice(cur.indexOf(c.id), 1);
          L.dock = cur; lookChanged();
        } }), h("span", {}, c.name, h("span", { class: "muted small" }, "  " + c.group)));
      })) : null);
  }
  draw();
  return h("div", { class: "card" }, h("h2", {}, "Motion, Icons and Greeting"), box);
}

// Day and night: the server changes the theme at sunrise and sunset.
function scheduleCard() {
  const sc = S.schedule || {};
  if (!schedW) schedW = { mode: sc.mode || "sun", dayAt: sc.dayAt || "07:00", nightAt: sc.nightAt || "19:00", day: sc.dayTheme || "liquid", night: sc.nightTheme || "crystalnight" };
  const W = schedW, themes = S.look.themes;
  const box = h("div", {});
  const pick = (label, key) => {
    const sel = h("select", { "aria-label": label, onchange: ev => { W[key] = ev.target.value; } }, themes.map(t => h("option", { value: t.id }, t.name)));
    sel.value = W[key];
    return h("div", { class: "field" }, h("div", { class: "lab" }, label), sel);
  };
  const timeBox = (label, key) => {
    const inp = h("input", { type: "time", value: W[key], "aria-label": label, onchange: ev => { if (ev.target.value) W[key] = ev.target.value; } });
    return h("div", { class: "field" }, h("div", { class: "lab" }, label), inp);
  };
  function draw() {
    const sun = W.mode === "sun";
    const now = sc.now ? (sc.now === "day" ? "daytime" : "night") : "";
    put(box,
      h("div", { class: "grid cols2" }, pick("Theme by Day", "day"), pick("Theme at Night", "night")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "When to Switch"),
        h("div", { class: "chips" }, h("button", { class: "chip", "aria-pressed": String(sun), onclick: () => { W.mode = "sun"; draw(); } }, "Sunrise and Sunset"),
          h("button", { class: "chip", "aria-pressed": String(!sun), onclick: () => { W.mode = "fixed"; draw(); } }, "Fixed Times")),
        sun
          ? h("div", { class: "hint" }, sc.hasPlace
            ? "Uses the city of the weather card" + (sc.city ? " (" + sc.city + ")" : "") + (sc.sunrise ? ". Today: sunrise " + sc.sunrise + ", sunset " + sc.sunset + "." : ".")
            : "No city is set for the weather card yet. Choose one under Location first, or use fixed times.")
          : h("div", { class: "grid cols2" }, timeBox("Day Starts At", "dayAt"), timeBox("Night Starts At", "nightAt"))),
      h("div", { class: "row" },
        h("button", { class: "primary", onclick: save }, sc.enabled ? "Save and Switch Now" : "Turn On and Switch Now"),
        sc.enabled ? h("button", { onclick: off }, "Turn Off") : null),
      h("p", { class: "muted small" }, sc.enabled
        ? "On. It is " + now + " now" + (sc.phase ? ", and the " + (sc.phase === "day" ? "day" : "night") + " theme is in place." : ".") + " A theme you choose yourself stays until the next switch."
        : "Off. Nothing changes by itself."));
  }
  async function save() {
    const pk = id => {
      const t = themes.find(x => x.id === id), g = t.background || {};
      return { theme: t.id, look: cleanOut(themeLook(t)), bg: g.url ? { blur: g.blur, saturate: g.saturate, brightness: g.brightness, opacity: g.opacity } : {} };
    };
    try {
      await api("POST", "/api/schedule", { op: "save", mode: W.mode, dayAt: W.dayAt, nightAt: W.nightAt, day: pk(W.day), night: pk(W.night) });
      toast("Saved. The dashboard changes theme at " + (W.mode === "sun" ? "sunrise and sunset." : W.dayAt + " and " + W.nightAt + "."));
      await afterChange(true);
    } catch (e) { fail(e); }
  }
  async function off() {
    try { await api("POST", "/api/schedule", { op: "off" }); toast("Day and night switching is off. The current theme stays."); await afterChange(false); } catch (e) { fail(e); }
  }
  draw();
  return h("div", { class: "card" }, h("h2", {}, "Day and Night"),
    h("p", { class: "muted" }, "Switch the whole dashboard to one theme by day and another at night. It changes for everyone who has the dashboard open. Names, the logo, motion and quick launch stay as they are. It has its own button and does not wait for Save."),
    box);
}

// The Look screen: colors, background, logo and names.
function viewLook() {
  if (!lookW) lookW = startLook();
  const L = lookW;
  lookBarEl = h("div", {});
  const glass = h("div", {});
  function drawGlass() {
    const chip = (on, text, set) => h("button", { class: "chip", "aria-pressed": String(on), onclick: () => { set(); lookChanged(); drawGlass(); } }, text);
    const tint = L.glassTint !== false;
    put(glass,
      h("div", { class: "field" }, h("div", { class: "lab" }, "Card Tint"),
        h("div", { class: "chips" }, chip(tint, "Tint On", () => { L.glassTint = true; }), chip(!tint, "No Tint", () => { L.glassTint = false; })),
        h("div", { class: "hint" }, "No Tint removes the colored glass layer from the cards, so only the blur remains. Colors set for individual cards are kept (see Color Strength below). The text gets a thin shadow so that it stays readable over a bright picture.")),
      tint ? [h("div", { class: "field" }, h("div", { class: "lab" }, "Glass Style"),
        h("div", { class: "chips" }, chip(!L.glassClear, "Tinted", () => { L.glassClear = false; }), chip(L.glassClear, "Transparent", () => { L.glassClear = true; })),
        h("div", { class: "hint" }, "Transparent glass lets the picture and the colors of the cards show through, which makes them look more vivid.")),
      L.glassClear
        ? [lookSlider("How Transparent", "glassLevel", 0, 100, 1, "%", "A higher value is clearer. 100% is plain frosted glass with no tint."),
           h("div", { class: "chips", style: { marginBottom: "12px" } }, [["A Little", 30], ["Medium", 55], ["Very", 80], ["Clear", 100]].map(([t, n]) =>
             h("button", { class: "chip", onclick: () => { L.glassLevel = n; lookChanged(); render(); } }, t)))]
        : lookSlider("How Solid the Glass Is", "glassOpacity", 0, 100, 1, "%", "A low value shows the picture through the cards. A high value makes them solid.")] : null,
      lookSlider("Shine on the Glass Edge", "glassRim", 0, 100, 1, "%", "A thin bright line around the glass and a soft glow just inside it. 0% turns it off."),
      lookSlider("Raised Glass Edge", "glassBevel", 0, 100, 1, "%", "A rounded, raised edge with a soft shadow, like thick glass. It looks best on light glass. 0% turns it off."),
      lookSlider("Glow Around Cards", "glow", 0, 100, 1, "%", "A soft glow in the color of each card. 0% turns it off."),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Light or Dark Look"),
        h("div", { class: "chips" }, chip(L.tone !== "light", "Dark", () => { L.tone = "dark"; }), chip(L.tone === "light", "Light", () => { L.tone = "light"; })),
        h("div", { class: "hint" }, "Light changes the shadows, the lines and the layer over the picture to suit light glass. Also set the text colors below to dark colors.")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Text Style"),
        h("div", { class: "chips" }, [["default", "Dashboard Default"], ["apple", "Apple"], ["windows", "Windows"], ["mono", "Monospace"], ["rounded", "Rounded"]].map(([k, t]) => chip((L.font || "default") === k, t, () => { L.font = k; }))),
        h("div", { class: "hint" }, "Uses a font that is already on the device that shows the dashboard, so it can look different on another device.")));
  }
  drawGlass();
  const tabRows = S.look.tabNames.map(name => {
    const cur = () => L.tabs[name] || L.accent;
    const pick = h("input", { type: "color", value: cur(), "aria-label": "Color of the tab " + name });
    pick.addEventListener("input", () => { L.tabs[name] = pick.value; lookChanged(); });
    return h("div", { class: "row", style: { marginBottom: "6px" } }, pick, h("span", { class: "grow" }, name),
      h("button", { class: "small", onclick: () => { L.tabs[name] = L.accent; pick.value = L.accent; lookChanged(); } }, "Use Main Color"));
  });
  const mock = h("div", { class: "preview", id: "mock" },
    h("div", { class: "mini-tabs" }, h("span", { class: "on" }, "Home"), h("span", {}, "Stats"), h("span", {}, "Links")),
    h("div", { class: "mini-cards" }, ["Navidrome", "Immich", "Beszel"].map(n => h("div", { class: "mini-card" }, h("b", {}, n), h("span", { class: "small muted" }, "Sample Card"), h("i", {})))));
  setTimeout(() => { lookPreview(!lookDirty()); refreshLookBar(); }, 0);
  const previewCard =
h("div", { class: "card" }, h("h2", {}, "Preview and Shape"),
  h("div", { class: "grid cols2" },
        h("div", {}, h("p", { class: "muted" }, framed ? "The dashboard around this panel changes while the sliders are moved, so the actual result is visible." : "A small sample of how cards and tabs look."), mock),
        h("div", {},
          lookSlider("How Round the Corners Are", "radius", 0, 40, 1, " px"),
          lookSlider("Brightness of the Card Edge", "edge", 0, 60, 0.5, "%"),
          lookSlider("Space at the Left and Right", "side", 0, 120, 2, " px"),
          lookSlider("Darkness Over the Picture", "veil", 0, 100, 1, "%", "A dark layer between the picture and the cards that keeps the text readable. 0% shows the picture as it is."),
          h("p", { class: "muted small" }, "The height of the music player is changed on the dashboard itself, with the small arrows button next to the shrink button on the player."))));
  const colorsCard =
h("div", { class: "card" }, h("h2", {}, "Colors and Glass"),
      h("div", { class: "grid cols2" },
        h("div", {},
          colorField("Main Color", "accent", "The color of the active tab, bars, icons and the edge of a card you point at.", ["#8ab4ff", "#5ec8ff", "#7ee0a0", "#ffa66b", "#ff8fb5", "#c9a0ff", "#ffd36b", "#c3cad6"]),
          colorField("Glass Color", "glass", "The tint of every card and tile (only when Card Tint is on).", ["#0d121e", "#06141f", "#07150d", "#1c0f12", "#1a0c16", "#111214"]),
          colorField("Text Color", "text", "The names and numbers on cards, tiles and bookmarks. Choose a light color on a dark picture and a dark color on a bright one.", ["#eef2f9", "#ffffff", "#fff6ee", "#f2fcff", "#fff2f7", "#1a2233"]),
          colorField("Smaller Text Color", "muted", "The descriptions and labels under the names.", ["#a9b4c7", "#dde8f8", "#ecd0bf", "#bcdbe8", "#efcadb", "#4a5568"])),
        glass),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Color of Each Tab"), h("div", { class: "hint", style: { marginBottom: "8px" } }, "Each tab can have its own accent color."),
        h("div", { class: "grid cols2 tabcolors" }, tabRows)),
      h("p", { class: "muted small" }, "Further down, single cards, tiles, bookmarks and labels can be given their own colors."));
  const strengthCard =
h("div", { class: "card" }, h("h2", {}, "Color Strength"),
  lookSlider("How Strong the Colors Are", "paintStrength", 0, 100, 1, "%", "How strong the colors of the cards, tiles and bookmarks are. A higher value makes the color, the edge and the glow stronger."),
  lookSlider("Card Depth", "cardDepth", 0, 100, 1, "%", "A darker shade of each card's own color under the bright color. A higher value makes the text stand out more and the colors look fuller. 0% turns it off."));
  return h("div", {},
    themesCard(),
    scheduleCard(),
    polishCard(),
    previewCard,
    colorsCard,
    strengthCard,
    backgroundCards(),
    namesCard(),
    locationCard(),
    colorOptions(),
    lookBarEl);
}

