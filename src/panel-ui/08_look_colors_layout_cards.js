function labelIconSample(style) {
  return h("span", { class: "lis lis-" + style }, h("img", { src: iconInfo("mdi-movie-open").url, class: "mdi", alt: "" }));
}

// The color choices of the Look screen: the accent colors of cards, tiles, bookmarks and group labels.
function colorOptions() {
  const L = lookW, P = S.paint;

  function colorInput(value, label, onset) {
    const inp = h("input", { type: "color", value: value || "#8ab4ff", "aria-label": label });
    inp.addEventListener("input", () => onset(inp.value));
    return inp;
  }
  const followers = [];
  function itemRow(map, key, name, sub, def) {
    const badge = h("span", { class: "badge" }), reset = h("button", { class: "small" }, "Reset");
    const base = () => L.paintAll || def || "#8ab4ff";
    const inp = colorInput(map[key] || base(), "Color of " + name, v => { map[key] = v; lookChanged(); refresh(); });
    function refresh() {
      const set = !!map[key];
      badge.textContent = set ? "Custom" : (L.paintAll ? "All Color" : "Default");
      badge.className = "badge" + (set ? "" : " dim");
      reset.disabled = !set;
      if (!set && inp.value !== base()) inp.value = base();
    }
    reset.addEventListener("click", () => { delete map[key]; lookChanged(); refresh(); });
    refresh();
    return h("div", { class: "prow" }, h("div", { class: "txt" }, h("b", {}, name), sub ? h("span", {}, sub) : null), badge, inp, reset);
  }
  function section(title, hint, items, map, keyOf, subOf, open) {
    if (!items.length) return null;
    let bulk = "#8ab4ff";
    const rows = h("div", {});
    const draw = () => put(rows, items.map(it => itemRow(map, keyOf(it), it.name, subOf(it), it.color)));
    draw();
    const bulkInp = colorInput(bulk, "One color for all in " + title, v => { bulk = v; });
    followers.push(draw, () => { if (L.paintAll) { bulk = L.paintAll; bulkInp.value = bulk; } });
    return h("details", { class: "card", open: open }, h("summary", {}, h("b", {}, title), h("span", { class: "badge" }, String(items.length)), saveTag("save")),
      h("p", { class: "muted small" }, hint),
      h("div", { class: "row bulk" }, h("span", { class: "lab" }, "One Color for All Below:"), bulkInp,
        h("button", { class: "small", onclick: () => { for (const it of items) map[keyOf(it)] = bulk; lookChanged(); draw(); } }, "Apply"),
        h("button", { class: "small", onclick: () => { for (const it of items) delete map[keyOf(it)]; lookChanged(); draw(); } }, "Set All to Default")),
      rows);
  }

  const labelRows = h("div", {});
  function drawLabels() {
    put(labelRows, P.labels.map(name => {
      const part = (key, text, def) => {
        const reset = h("button", { class: "small", "aria-label": "Reset " + text.toLowerCase() + " of " + name }, "Reset");
        const inp = colorInput((L.labels[name] || {})[key] || def, text + " of " + name, v => { (L.labels[name] = L.labels[name] || {})[key] = v; lookChanged(); refresh(); });
        const refresh = () => { reset.disabled = !(L.labels[name] || {})[key]; };
        reset.addEventListener("click", () => {
          if (L.labels[name]) { delete L.labels[name][key]; if (!Object.keys(L.labels[name]).length) delete L.labels[name]; }
          inp.value = def; lookChanged(); refresh();
        });
        refresh();
        return h("span", { class: "lpart" }, h("span", { class: "small muted" }, text), inp, reset);
      };
      return h("div", { class: "prow" }, h("div", { class: "txt" }, h("b", {}, name)), part("text", "Text", "#eef2f9"), part("icon", "Icon", "#c9d6f2"));
    }));
  }
  drawLabels();
  let bulkText = "#eef2f9", bulkIcon = "#c9d6f2";
  const styles = h("div", { class: "chips" });
  function drawStyles() {
    put(styles, [["plain", "Plain Icon"], ["circle", "Circle Badge"], ["square", "Rounded Square Badge"], ["ring", "Glowing Ring"]].map(([id, text]) =>
      h("button", { class: "chip styl", "aria-pressed": String(L.labelIcon === id), onclick: () => { L.labelIcon = id; lookChanged(); drawStyles(); } }, labelIconSample(id), text)));
  }
  drawStyles();

  const allBadge = h("span", { class: "badge" }), allOff = h("button", { class: "small" }, "Turn Off");
  const allInp = colorInput(L.paintAll || "#8ab4ff", "One color for everything", v => { L.paintAll = v; lookChanged(); refreshAll(); });
  function refreshAll() {
    allBadge.textContent = L.paintAll ? "On" : "Off";
    allBadge.className = "badge" + (L.paintAll ? "" : " dim");
    allOff.disabled = !L.paintAll;
    for (const f of followers) f();
  }
  allOff.addEventListener("click", () => { L.paintAll = ""; lookChanged(); refreshAll(); });
  refreshAll();
  const paintAll = h("div", {},
    h("div", { class: "row" }, allInp, allBadge, allOff),
    h("div", { class: "hint" }, "Choose a color to give every card, tile and bookmark the same color. A color chosen for a single item below takes precedence."));

  const styleChips = h("div", { class: "chips" });
  function drawPaintStyle() {
    put(styleChips, [["gradient", "Gradient"], ["solid", "Solid"]].map(([id, text]) =>
      h("button", { class: "chip", "aria-pressed": String(L.paintStyle === id), onclick: () => { L.paintStyle = id; lookChanged(); drawPaintStyle(); } }, text)));
  }
  drawPaintStyle();

  return h("div", {},
    h("details", { class: "card" }, h("summary", {}, h("b", {}, "Colors of Cards, Tiles and Bookmarks"), saveTag("save"), h("span", { class: "muted small" }, "Advanced: a theme already sets these")),
      h("p", { class: "muted" }, "Set a color for single service cards, the calendar, the tiles of the Stats tab and the bookmarks of the Links tab: a tint, a colored edge and a soft glow. It works best with Transparent glass (set under Colors and Glass)."),
      h("p", { class: "muted small" }, "To see a color on the dashboard, open the tab that has it (Home, Stats or Links). The preview stays there. Return here and press Save to keep it."),
      h("div", { class: "field" }, h("div", { class: "lab" }, "Color Style"), styleChips,
        h("div", { class: "hint" }, "Gradient: the color is strong on one side and fades out across the card. Solid: the same color across the whole card.")),
      h("div", { class: "field" }, h("div", { class: "lab" }, "One Color for Everything"), paintAll)),
    section("Service Cards", "The cards of the Home tab, such as Portainer or Downtify.", P.cards, L.cards, it => it.id, it => it.group, false),
    section("Stats Tiles", "The tiles of the Stats tab.", P.stats, L.cards, it => it.id, it => it.group, false),
    section("Calendar", "The calendar and the list of coming events.", P.calendar, L.cards, it => it.id, it => it.group, false),
    section("Bookmarks", "The bookmarks of the Links tab.", P.links, L.links, it => it.name, it => it.group, false),
    h("details", { class: "card" }, h("summary", {}, h("b", {}, "Labels"), h("span", { class: "badge" }, String(P.labels.length)), saveTag("save")),
      h("p", { class: "muted small" }, "The names above each row of cards, such as Media & Entertainment. Choose a color for the text and for the small icon next to it."),
      h("div", { class: "row bulk" }, h("span", { class: "lab" }, "One Color for All Labels:"),
        h("span", { class: "lpart" }, h("span", { class: "small muted" }, "Text"), colorInput(bulkText, "Text color for all labels", v => { bulkText = v; })),
        h("span", { class: "lpart" }, h("span", { class: "small muted" }, "Icon"), colorInput(bulkIcon, "Icon color for all labels", v => { bulkIcon = v; })),
        h("button", { class: "small", onclick: () => { for (const n of P.labels) L.labels[n] = { text: bulkText, icon: bulkIcon }; lookChanged(); drawLabels(); } }, "Apply"),
        h("button", { class: "small", onclick: () => { L.labels = {}; lookChanged(); drawLabels(); } }, "Set All to Default")),
      labelRows,
      h("div", { class: "field", style: { marginTop: "14px" } }, h("div", { class: "lab" }, "Icon Style"), h("div", { class: "hint", style: { marginBottom: "8px" } }, "How the small icon next to every label looks."), styles)));
}

function bgUrl(img) { return !img ? "" : (img.startsWith("/") && S.background.homepageUrl ? S.background.homepageUrl + img : (img.startsWith("/") ? "" : img)); }
// The cards of the Look screen that set the background picture.
function backgroundCards() {
  const b = S.background;
  if (!bgW) bgW = savedBg();
  const B = bgW;
  const pic = h("div", { class: "pic" });
  const drawPic = () => { const u = B.url || bgUrl(b.image); pic.style.backgroundImage = u ? 'url("' + u.replace(/"/g, "%22") + '")' : "none"; };
  drawPic();
  const preview = () => { send({ type: "bg", image: B.url || b.image, blur: B.blur, saturate: B.saturate, brightness: B.brightness, opacity: B.opacity }); refreshLookBar(); };
  function reset() {
    const d = b.defaults || { blur: "md", saturate: 60, brightness: 42, opacity: 80 };
    B.blur = d.blur; B.saturate = d.saturate; B.brightness = d.brightness; B.opacity = d.opacity;
    preview();
    render();
    toast("The sliders are reset to their default values. Press Save to keep the change.");
  }
  function slider(label, key, hint) {
    const val = h("span", { class: "val" }, B[key] + "%");
    return h("div", { class: "field" }, h("div", { class: "slider" }, h("span", { class: "lab" }, label), val,
      h("input", { type: "range", min: 0, max: 100, step: 1, value: B[key], "aria-label": label, oninput: ev => { B[key] = Number(ev.target.value); val.textContent = B[key] + "%"; preview(); } })),
      h("div", { class: "hint" }, hint));
  }
  const blurVal = h("span", { class: "val" }, BLUR_NAMES[B.blur] || B.blur);
  const url = h("input", { type: "url", placeholder: "https://…", "aria-label": "Picture address" });
  const file = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp,image/gif,image/avif", hidden: true, onchange: upload });
  async function upload() {
    const f = file.files[0];
    if (!f) return;
    if (f.size > 14 * 1024 * 1024) return toast("That picture is larger than 14 MB. Choose a smaller one.", true);
    toast("Sending the picture…");
    try {
      const r = await api("POST", "/api/background/upload", undefined, f);
      toast(r.restarting ? "Picture saved. The dashboard restarts for about 10 seconds…" : "Picture saved.");
      await afterChange(false);
      if (r.restarting) setTimeout(() => send({ type: "reload" }), 12000);
    } catch (e) { fail(e); }
  }
  return h("div", { class: "grid cols2" },
    h("div", { class: "card" }, cardHead("Background Picture", "save"), pic,
      h("div", { class: "row", style: { marginTop: "12px" } }, file, h("button", { class: "primary", onclick: () => file.click() }, "Upload a Picture…")),
      h("p", { class: "hint muted small" }, "JPG, PNG, WebP, GIF or AVIF, up to 14 MB. After a new picture the dashboard restarts for about 10 seconds."),
      b.mounted === false ? h("p", { class: "small", style: { color: "var(--bad)" } }, "The dashboard cannot see its pictures folder yet, so an uploaded picture will not show. Run: sudo homelab-setup upgrade") : null,
      h("div", { class: "field", style: { marginTop: "12px" } }, h("label", {}, "Or Use a Picture from the Web"), h("div", { class: "row" }, h("div", { class: "grow" }, url),
        h("button", { onclick: () => { const v = url.value.trim(); if (!/^https?:\/\/\S+$/.test(v)) return toast("Type a web address that starts with http:// or https:// first.", true); B.url = v; B.theme = ""; drawPic(); preview(); toast("Press Save to keep it."); } }, "Use This Address")))),
    h("div", { class: "card" }, cardHead("How the Background Looks Behind the Cards", "save"),
      h("div", { class: "field" }, h("div", { class: "slider" }, h("span", { class: "lab" }, "Picture Blur"), blurVal,
        h("input", { type: "range", min: 0, max: 6, step: 1, value: BLURS.indexOf(B.blur) < 0 ? 2 : BLURS.indexOf(B.blur), "aria-label": "Picture Blur",
          oninput: ev => { B.blur = BLURS[Number(ev.target.value)]; blurVal.textContent = BLUR_NAMES[B.blur] || B.blur; preview(); } })), h("div", { class: "hint" }, "None keeps the picture sharp. Very Huge makes it very soft.")),
      slider("Picture Brightness", "brightness", "A low value makes the picture darker, so the text is easier to read."),
      slider("Picture Color", "saturate", "Low turns the picture toward gray."),
      slider("How Much Picture Shows", "opacity", "A higher value shows more of the picture. A lower value covers it with the dark layer."),
      h("div", { class: "row" }, h("button", { class: "small", onclick: reset }, "Restore Default Sliders"))));
}

// The Layout screen: tabs, the order of groups and their icons, styles and columns.
function viewLayout() {
  if (!layW) layW = clone(S.layout.tabs);
  const T = layW;
  const dirty = () => !same(T, S.layout.tabs);
  const bar = h("div", {});
  const refreshBar = () => put(bar, saveBar(dirty(), save, () => { layW = null; render(); }, "Save"));
  async function save() {
    try { await api("POST", "/api/layout", { tabs: T.filter(t => t.groups.length) }); toast("Layout saved."); await afterChange(true); } catch (e) { fail(e); }
  }
  const tabNames = () => T.map(t => t.name);
  // Only a tab of links (with the Edit Links box) puts groups side by side, so only there is "Groups in a row" offered.
  const takesRows = t => t.groups.some(g => /bookmarks/.test(g.kind)) && t.groups.every(g => /bookmarks/.test(g.kind) || ["Customize", "Edit Links", "Terminal"].includes(g.name));
  function moveTo(gi, ti, name) {
    const g = T[ti].groups.splice(gi, 1)[0];
    let dest = T.find(t => t.name === name);
    if (!dest) { dest = { name, groups: [] }; T.push(dest); }
    dest.groups.push(g);
    redraw();
  }
  function redraw() { const y = window.scrollY; put(board, T.map(tabCol)); window.scrollTo(0, y); refreshBar(); }
  let dragging = null;
  function drop(ti, at) {
    if (!dragging) return;
    const [fti, fgi] = dragging;
    const g = T[fti].groups.splice(fgi, 1)[0];
    let idx = at;
    if (fti === ti && fgi < at) idx -= 1;
    T[ti].groups.splice(Math.max(0, idx), 0, g);
    dragging = null;
    redraw();
  }
  let draggingTab = null;
  function dropTab(to) {
    const from = draggingTab;
    draggingTab = null;
    if (from === null || from === to) return;
    T.splice(to, 0, T.splice(from, 1)[0]);
    redraw();
  }
  function groupRow(g, ti, gi) {
    const row = h("div", { class: "grp", draggable: "true",
      ondragstart: ev => { dragging = [ti, gi]; ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", g.name); row.classList.add("drag"); },
      ondragend: () => row.classList.remove("drag"),
      ondragover: ev => { if (!dragging) return; ev.preventDefault(); const b = ev.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2; row.classList.toggle("over-b", b); row.classList.toggle("over-t", !b); },
      ondragleave: () => row.classList.remove("over-t", "over-b"),
      ondrop: ev => { if (!dragging) return; ev.preventDefault(); const b = ev.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2; row.classList.remove("over-t", "over-b"); drop(ti, gi + (b ? 1 : 0)); } });
    const move = (d) => { const arr = T[ti].groups; const j = gi + d; if (j < 0 || j >= arr.length) return; [arr[gi], arr[j]] = [arr[j], arr[gi]]; redraw(); };
    const handle = h("span", { class: "handle", tabindex: "0", role: "button", title: "Drag to move", "aria-label": "Move " + g.name + ". Drag it, or press the up or down arrow key.",
      onkeydown: ev => { if (ev.key === "ArrowUp" || ev.key === "ArrowDown") { ev.preventDefault(); move(ev.key === "ArrowUp" ? -1 : 1); } } }, "⠿");
    const sel = h("select", { "aria-label": "Move " + g.name + " to a tab", onchange: async ev => {
      let v = ev.target.value;
      if (v === "__new") { v = (await askText("New tab", "Name of the new tab", "")) || ""; if (!v) return redraw(); if (tabNames().includes(v)) return moveTo(gi, ti, v); }
      if (v && v !== T[ti].name) moveTo(gi, ti, v);
    } }, tabNames().map(n => h("option", { value: n, selected: n === T[ti].name }, "Tab: " + n)), h("option", { value: "__new" }, "New tab…"));
    const icon = h("button", { class: "small", "aria-label": "Choose the icon of " + g.name, onclick: async () => { const pick = await pickIcon(g.icon || ""); if (typeof pick === "string" && pick !== (g.icon || "")) { g.icon = pick; redraw(); } } }, "Icon…");
    const style = h("select", { "aria-label": "Shape of " + g.name, onchange: ev => { g.style = ev.target.value; redraw(); } },
      h("option", { value: "", selected: !g.style }, "Cards in a list"), h("option", { value: "row", selected: g.style === "row" }, "Cards in a row"));
    const cols = h("input", { class: "cols-in", type: "number", min: 1, max: 8, value: g.columns || "", placeholder: "Columns", title: "How many columns (empty = automatic)", "aria-label": "Columns of " + g.name, onchange: ev => { g.columns = ev.target.value; redraw(); } });
    add(row, handle, iconEl(g.icon), h("span", { class: "name" }, g.name),
      g.automatic ? h("span", { class: "badge", title: "HomeLab fills this group automatically" }, "automatic") : null,
      sel, icon, style, cols);
    return row;
  }
  function tabCol(t, ti) {
    const col = h("div", { class: "tabcol",
      ondragover: ev => { ev.preventDefault(); if (draggingTab !== null) col.classList.add("over"); },
      ondragleave: ev => { if (!col.contains(ev.relatedTarget)) col.classList.remove("over"); },
      ondrop: ev => {
        col.classList.remove("over");
        if (draggingTab !== null) { ev.preventDefault(); dropTab(ti); return; }
        if (ev.target === col || !ev.target.closest(".grp")) { ev.preventDefault(); drop(ti, t.groups.length); }
      } });
    const mvT = d => { const j = ti + d; if (j < 0 || j >= T.length) return; [T[ti], T[j]] = [T[j], T[ti]]; redraw(); };
    const head = h("header", { draggable: "true",
      ondragstart: ev => { draggingTab = ti; ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", t.name); setTimeout(() => col.classList.add("drag"), 0); },
      ondragend: () => { draggingTab = null; col.classList.remove("drag", "over"); } },
      h("span", { class: "handle", tabindex: "0", role: "button", title: "Drag to move the tab", "aria-label": "Move the tab " + t.name + ". Drag it, or press the left or right arrow key.",
        onkeydown: ev => { if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") { ev.preventDefault(); mvT(ev.key === "ArrowLeft" ? -1 : 1); } } }, "⠿"),
      h("h3", {}, t.name),
      h("button", { class: "small", onclick: async () => {
        const n = (await askText("Rename the tab", "New name for the tab “" + t.name + "”", t.name)) || "";
        if (!n || n === t.name) return;
        if (T.some(x => x.name === n)) return toast("There is already a tab with that name.", true);
        t.name = n; redraw();
      } }, "Rename"));
    add(col, head,
    takesRows(t) ? h("div", { class: "row", style: { margin: "4px 0 10px" } }, h("label", { for: "per-row-" + ti, class: "muted small" }, "Groups in a row"),
      h("select", { id: "per-row-" + ti, title: "How many groups sit side by side on this tab. More groups start a new row. A narrow window shows fewer.", onchange: ev => { t.perRow = ev.target.value; redraw(); } },
        h("option", { value: "", selected: !t.perRow }, "Standard (2)"), [1, 2, 3, 4].map(n => h("option", { value: String(n), selected: String(t.perRow) === String(n) }, String(n))))) : null,
    t.groups.map((g, gi) => groupRow(g, ti, gi)),
    t.groups.length ? null : h("p", { class: "muted small" }, "Empty. A tab with no group is not kept."));
    return col;
  }
  const board = h("div", { class: "grid" }, T.map(tabCol));
  setTimeout(refreshBar, 0);
  return h("div", {},
    h("div", { class: "card" }, cardHead("Tabs and Groups", "save"),
      h("p", { class: "muted" }, "Each box is a tab of the dashboard. Drag a group by its handle to change the order, or drag a tab by the handle in its title. Choose another tab to move a group there, and choose how its cards are laid out. “Cards in a row” places the cards side by side."),
      h("div", { class: "row", style: { marginBottom: "12px" } }, h("button", { onclick: async () => {
        const n = (await askText("Add a tab", "Name of the new tab", "")) || "";
        if (!n) return;
        if (T.some(x => x.name === n)) return toast("There is already a tab with that name.", true);
        T.push({ name: n, groups: [] }); redraw();
      } }, "+ Add a Tab"), h("span", { class: "muted small" }, "Then move a group into it.")),
      board),
    bar);
}

function viewCards() { return viewItems("cards"); }
function viewLinks() { return viewItems("links"); }

// The Cards and Links screens share this editor: add, edit, move and remove cards, bookmarks and groups.
function viewItems(kind) {
  const isCards = kind === "cards";
  if (!isCards && !linkW) startLinks();
  // The Links screen works on a draft. Nothing is sent until Save, and then the whole list goes at once, so the dashboard reloads once.
  const groups = (isCards ? S.services.filter(g => !g.locked) : linkW);
  const path = isCards ? "/api/card" : "/api/link";
  const items = g => isCards ? g.cards : g.links;
  const tabsList = S.layout.tabs.map(t => t.name);
  const word = isCards ? "card" : "link";

  async function op(body, okMsg) { try { await api("POST", path, body); toast(okMsg); await afterChange(true); } catch (e) { fail(e); } }
  async function reorder(g, i, d) {
    if (!isCards) { const a = g.links, j = i + d; if (j >= 0 && j < a.length) { [a[i], a[j]] = [a[j], a[i]]; redraw(); } return; }
    const arr = items(g);
    const it = arr[i];
    const before = d < 0 ? arr[i - 1] : arr[i + 2];
    await op({ op: "move", group: g.group, name: it.name, to: g.group, before: before ? before.name : undefined }, "Order saved.");
  }
  async function dropCard(f, to, at) {
    const it = items(f.g)[f.i];
    if (!it || (f.g === to && (at === f.i || at === f.i + 1))) return;
    const next = items(to)[at];
    await op({ op: "move", group: f.g.group, name: it.name, to: to.group, before: next ? next.name : undefined }, f.g === to ? "Order saved." : "Moved to " + to.group + ".");
  }
  async function quickIcon(g, it) {
    const pick = await pickIcon(it.icon);
    if (pick === it.icon) return;
    await op({ op: "edit", group: g.group, old: it.name, name: it.name, href: it.href, icon: pick, description: it.description, dot: !!it.siteMonitor }, "Icon saved.");
  }
  async function remove(g, it) {
    if (!isCards) { g.links.splice(g.links.indexOf(it), 1); redraw(); return; }
    if (it.hl) {
      if (!await confirmBox("Hide “" + it.name + "”?", "It is removed from the dashboard. Restore it any time with Add From HomeLab's List, or with Undo.", "Hide It", true)) return;
      return op({ op: "remove", group: g.group, name: it.name }, "Hidden.");
    }
    if (!await confirmBox("Remove “" + it.name + "”?", "It is removed from the dashboard. Undo restores it.", "Remove It", true)) return;
    await op({ op: "remove", group: g.group, name: it.name }, "Removed.");
  }
  function hlList() {
    const list = S.hlcards || [];
    if (!list.length) { toast("The list of HomeLab's cards is not on this machine yet. On the server run: sudo homelab-setup upgrade", true); return; }
    const picks = new Set();
    const err = h("div", { class: "err", role: "alert", style: { color: "var(--bad)", minHeight: "20px" } });
    const gsel = h("select", { "aria-label": "Put them in" }, h("option", { value: "" }, "Each in its usual group"), groups.map(x => h("option", { value: x.group }, x.group)));
    const names = [...new Set(list.map(c => c.group))];
    const rows = names.map(n => h("div", { class: "card", style: { margin: "8px 0" } }, h("h3", {}, n),
      list.filter(c => c.group === n).map(c => {
        const on = !!c.in;
        const box = h("input", { type: "checkbox", disabled: on, "aria-label": c.name + (on ? " (already on the dashboard)" : ""), onchange: ev => { ev.target.checked ? picks.add(c.id) : picks.delete(c.id); } });
        return h("label", { class: "item", style: { cursor: on ? "default" : "pointer" } }, box, iconEl(c.icon),
          h("div", { class: "txt" }, h("b", {}, c.name), h("span", {}, c.description || "")),
          on ? h("span", { class: "badge" }, "On the dashboard" + (c.in !== n ? " (in " + c.in + ")" : "")) : (c.extra ? h("span", { class: "badge" }, "Extra") : null));
      })));
    const d = h("dialog", {}, h("h2", {}, "Add From HomeLab's List"),
      h("p", { class: "muted" }, "Cards that HomeLab fills in with numbers. Select the ones to add. Cards already on the dashboard are greyed out. “Extra” cards show a single number."),
      h("div", { style: { maxHeight: "50vh", overflow: "auto" } }, rows),
      h("div", { class: "field" }, h("label", {}, "Put them in"), gsel), err,
      h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Cancel"), h("button", { class: "primary", onclick: async () => {
        err.textContent = "";
        if (!picks.size) { err.textContent = "Tick at least one card."; return; }
        try {
          await api("POST", "/api/card", { op: "add-list", ids: [...picks], group: gsel.value || undefined });
          d.close(); toast("Added."); await afterChange(true);
        } catch (e) { err.textContent = e.message; }
      } }, "Add the Ticked Cards")));
    d.addEventListener("close", () => d.remove());
    document.body.append(d);
    d.showModal();
  }
  async function hlRestore() {
    if (!await confirmBox("Put HomeLab's Cards Back?", "HomeLab's own cards return to their name, icon and group, and hidden cards show again. Cards you added are kept. Undo reverts this.", "Put Them Back", true)) return;
    try { await api("POST", "/api/hlcards/restore", {}); toast("Put back."); await afterChange(true); } catch (e) { fail(e); }
  }

  function editor(g, it) {
    const adding = !it;
    const v = it || { name: "", href: "", icon: "", description: "", abbr: "", siteMonitor: "" };
    const managed = isCards && it && it.managed;
    const name = h("input", { type: "text", value: v.name, maxlength: 60, "aria-label": "Name" });
    const href = h("input", { type: "url", value: v.href, placeholder: "https://…", disabled: managed, "aria-label": "Address" });
    const desc = h("input", { type: "text", value: v.description || "", maxlength: isCards ? 160 : 120, "aria-label": "Description" });
    const abbr = h("input", { type: "text", value: v.abbr || "", maxlength: 6, placeholder: "automatic", "aria-label": "Short label" });
    const dot = h("input", { type: "checkbox", id: "dot", checked: !!v.siteMonitor });
    const ic = iconField(v.icon, v.hl ? null : () => href.value);
    const names = groups.map(x => x.group);
    const gsel = h("select", { "aria-label": "Group" }, names.map(n => h("option", { value: n, selected: g && n === g.group }, n)), h("option", { value: "__new" }, "A new group…"));
    const gnew = h("input", { type: "text", placeholder: "Name of the new group", maxlength: 40, hidden: true, "aria-label": "New group name" });
    const tsel = h("select", { "aria-label": "Tab for the new group", hidden: true }, tabsList.map(n => h("option", { value: n, selected: n === (isCards ? "Home" : "Links") }, "On the tab: " + n)));
    gsel.addEventListener("change", () => { const nw = gsel.value === "__new"; gnew.hidden = !nw; tsel.hidden = !nw; if (nw) gnew.focus(); });
    if (!names.length) { gsel.value = "__new"; gnew.hidden = false; tsel.hidden = false; }
    // The key or password a card's widget uses. The panel only says whether one is saved, never what it is, so the box starts empty and an empty box keeps the saved one.
    const keyBoxes = {};
    const keysEl = isCards && it && !v.hl && Array.isArray(it.keys) && it.keys.length ? h("div", {}, it.keys.map(k => {
      const box = h("input", { type: "password", autocomplete: "new-password", spellcheck: "false", maxlength: 400, "aria-label": k.label,
        placeholder: k.set ? "Saved. Type a new one to replace it." : "Not set yet. Paste it here." });
      keyBoxes[k.field] = box;
      const showId = "show-" + k.field;
      const show = h("input", { type: "checkbox", id: showId, onchange: ev => { box.type = ev.target.checked ? "text" : "password"; } });
      return h("div", { class: "field" }, h("label", {}, k.label), box,
        h("label", { for: showId, class: "row" }, show, "Show what I type"),
        h("div", { class: "hint" }, (k.set ? (k.field === "password" ? "A password is saved. " : "An API key is saved. ") : (k.field === "password" ? "No password is saved yet. " : "No API key is saved yet. "))
          + "The card uses it to read its live numbers. It is never shown again after you save. Leave the box empty to keep the one that is saved."));
    })) : null;
    const err = h("div", { class: "err", role: "alert", style: { color: "var(--bad)", minHeight: "20px" } });
    const d = h("dialog", {}, h("h2", {}, adding ? "Add a " + word : "Change “" + v.name + "”"),
      h("div", { class: "field" }, h("label", {}, "Name"), name),
      v.hl ? h("p", { class: "muted small" }, "HomeLab fills in the numbers of this card automatically, so only its name, icon, color, text and group can be changed here.") :
        h("div", { class: "field" }, h("label", {}, "Web address"), href, managed ? h("div", { class: "hint" }, "HomeLab keeps this address up to date (the Tailscale name and ports), so it cannot be changed here.") : null),
      keysEl,
      ic.el,
      h("div", { class: "field" }, h("label", {}, "Short text"), desc, h("div", { class: "hint" }, isCards ? "Shown under the name." : "Optional.")),
      isCards ? (managed ? null : h("div", { class: "field" }, h("label", { for: "dot", class: "row" }, dot, "Show a green or red dot to indicate whether it is running"))) : h("div", { class: "field" }, h("label", {}, "Short label"), abbr, h("div", { class: "hint" }, "Up to 6 letters, shown when there is no icon.")),
      h("div", { class: "field" }, h("label", {}, adding ? "Put it in" : "Group"), gsel, gnew, tsel),
      isCards ? null : h("p", { class: "muted small" }, "Nothing is saved until you press Save at the top."),
      err,
      h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Cancel"), h("button", { class: "primary", onclick: async () => {
        err.textContent = "";
        const target = gsel.value === "__new" ? gnew.value.trim() : gsel.value;
        if (!isCards) {
          const bad = draftLink(g, it, { name: name.value.trim(), href: href.value.trim(), icon: ic.input.value.trim(), description: desc.value.trim(), abbr: abbr.value.trim() }, target, tsel.value);
          if (bad) { err.textContent = bad; return; }
          d.close(); redraw(); return;
        }
        const body = { name: name.value.trim(), href: href.value.trim(), icon: ic.input.value.trim(), description: desc.value.trim(), dot: dot.checked, abbr: abbr.value.trim() };
        const secrets = {};
        for (const f of Object.keys(keyBoxes)) if (keyBoxes[f].value.trim()) secrets[f] = keyBoxes[f].value.trim();
        const newKey = Object.keys(secrets).length > 0;
        if (newKey) body.secrets = secrets;
        try {
          if (adding) { await api("POST", path, Object.assign(body, { op: "add", group: target, tab: tsel.value })); }
          else {
            await api("POST", path, Object.assign(body, { op: "edit", group: g.group, old: v.name }));
            if (target !== g.group) await api("POST", path, { op: "move", group: g.group, name: body.name, to: target, tab: tsel.value });
          }
          d.close(); toast(adding ? "Added." : (newKey ? "Saved. The card picks up the change the next time it refreshes." : "Saved.")); await afterChange(true);
        } catch (e) { err.textContent = e.message; }
      } }, adding ? "Add" : "Save")));
    d.addEventListener("close", () => d.remove());
    document.body.append(d);
    d.showModal();
    name.focus();
  }

  async function groupMenu(g) {
    const n = (await askText("Rename the Group", "New name for the group “" + g.group + "”", g.group)) || "";
    if (!n || n === g.group) return;
    if (!isCards) {
      if (!NAME_OK.test(n)) return toast("The group name has characters that are not allowed.", true);
      if (groups.some(x => x.group === n)) return toast("There is already a group called “" + n + "”.", true);
      g.group = n; redraw(); return;
    }
    try {
      await api("POST", isCards ? "/api/group" : "/api/link", isCards ? { op: "rename", group: g.group, to: n } : { op: "group-rename", group: g.group, to: n });
      toast("Renamed."); await afterChange(true);
    } catch (e) { fail(e); }
  }
  async function groupRemove(g) {
    if (!isCards) {
      if (!await confirmBox("Remove the Whole Group “" + g.group + "”?", "This removes the group and its " + g.links.length + " link" + (g.links.length === 1 ? "" : "s") + " from the list. The dashboard changes when you press Save.", "Remove the Group", true)) return;
      groups.splice(groups.indexOf(g), 1); redraw(); return;
    }
    if (!await confirmBox("Remove the Whole Group “" + g.group + "”?", "This removes the group and its " + items(g).length + " " + word + (items(g).length === 1 ? "" : "s") + ". Undo can bring them back.", "Remove the Group", true)) return;
    try {
      await api("POST", isCards ? "/api/group" : "/api/link", isCards ? { op: "remove", group: g.group } : { op: "group-remove", group: g.group });
      toast("Removed."); await afterChange(true);
    } catch (e) { fail(e); }
  }

  // Dragging a link: where it comes from, and the group and position it is dropped on.
  let dragFrom = null, listEl = null, barEl = null;
  function dropAt(to, at) {
    const f = dragFrom;
    dragFrom = null;
    if (!f) return;
    if (isCards) { dropCard(f, to, at); return; }
    const it = f.g.links.splice(f.i, 1)[0];
    if (f.g === to && f.i < at) at -= 1;
    to.links.splice(Math.max(0, Math.min(at, to.links.length)), 0, it);
    redraw();
  }
  function itemRow(g, it, i) {
    const row = h("div", { class: "item" });
    const movable = !(isCards && it.locked);
    if (movable) {
      const after = ev => { const r = row.getBoundingClientRect(); return ev.clientY > r.top + r.height / 2; };
      const clear = () => row.classList.remove("over-t", "over-b");
      row.draggable = true;
      row.addEventListener("dragstart", ev => { dragFrom = { g, i }; ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", it.name); setTimeout(() => row.classList.add("drag"), 0); });
      row.addEventListener("dragend", () => { dragFrom = null; row.classList.remove("drag"); clear(); });
      row.addEventListener("dragover", ev => { if (!dragFrom) return; ev.preventDefault(); ev.stopPropagation(); const b = after(ev); row.classList.toggle("over-b", b); row.classList.toggle("over-t", !b); });
      row.addEventListener("dragleave", clear);
      row.addEventListener("drop", ev => { if (!dragFrom) return; ev.preventDefault(); ev.stopPropagation(); const b = after(ev); clear(); dropAt(g, i + (b ? 1 : 0)); });
    }
    const grip = movable ? h("span", { class: "handle", tabindex: "0", role: "button", title: "Drag to move", "aria-label": "Move " + it.name + ". Drag it, or press the up or down arrow key.",
      onkeydown: ev => { if (ev.key === "ArrowUp" && i > 0) { ev.preventDefault(); reorder(g, i, -1); } else if (ev.key === "ArrowDown" && i < items(g).length - 1) { ev.preventDefault(); reorder(g, i, 1); } } }, "⠿")
      : h("span", { class: "handle off", "aria-hidden": "true" }, "⠿");
    add(row, grip, iconEl(it.icon),
      h("div", { class: "txt" }, h("b", {}, it.name), h("span", {}, [it.description, it.href].filter(Boolean).join("  ·  ") || "No address")),
      isCards && it.managed ? h("span", { class: "badge", title: "Created by HomeLab; it keeps the address up to date" }, "Built-In") : null,
      isCards && !it.locked ? h("button", { class: "small", onclick: () => quickIcon(g, it) }, "Icon…") : null,
      h("button", { class: "small", onclick: () => editor(g, it) }, "Change"),
      h("button", { class: "small danger", onclick: () => remove(g, it) }, it.hl ? "Hide" : "Remove"));
    return row;
  }
  function groupCards() {
    if (!groups.length) return [h("p", { class: "muted" }, "There is nothing here yet.")];
    return groups.map(g => {
      const box = h("div", { class: "card group-card" },
        h("header", {}, h("h2", {}, g.group), h("span", { class: "badge" }, items(g).length + (items(g).length === 1 ? " " + word : " " + word + "s")),
          isCards && g.automatic ? h("span", { class: "badge", title: "HomeLab fills in the numbers of these cards" }, "Filled in by HomeLab") : null,
          isCards && g.automatic ? null : [h("button", { class: "small", onclick: () => groupMenu(g) }, "Rename"), h("button", { class: "small danger", onclick: () => groupRemove(g) }, "Remove Group")]),
        items(g).map((it, i) => itemRow(g, it, i)),
        !isCards && !items(g).length ? h("p", { class: "muted small" }, "Empty. Drag a link here or add one. A group with no links is not kept when you save.") : null,
        h("div", { style: { marginTop: "10px" } }, h("button", { class: "small", onclick: () => editor(g, null) }, "+ Add a " + (word === "card" ? "Card" : "Link") + " here")));
      box.addEventListener("dragover", ev => { if (!dragFrom) return; ev.preventDefault(); box.classList.add("over"); });
      box.addEventListener("dragleave", ev => { if (!box.contains(ev.relatedTarget)) box.classList.remove("over"); });
      box.addEventListener("drop", ev => { if (!dragFrom) return; ev.preventDefault(); box.classList.remove("over"); dropAt(g, items(g).length); });
      return box;
    });
  }
  function redraw() { const y = window.scrollY; put(listEl, groupCards()); window.scrollTo(0, y); drawLinkBar(barEl); }
  listEl = h("div", {}, groupCards());
  barEl = isCards ? null : h("div", { class: "stickytop linkbar" }, h("div", { class: "hactions" }));
  drawLinkBar(barEl);

  return h("div", {},
    barEl,
    h("div", { class: "card" }, cardHead(isCards ? "Cards on the Dashboard" : "Links (Bookmarks)", isCards ? "now" : "save"),
      h("p", { class: "muted" }, isCards ? "The cards of the Home tab. Add cards for any web page, change a name or text, or remove cards. Drag a card by its handle to change the order, or drop it on another group to move it."
        : "The bookmarks of the Links tab, in groups. Add your own sites with icons. Drag a link by its handle to change the order, or drop it on another group to move it. Nothing changes on the dashboard until you press Save."),
      h("div", { class: "row" }, h("button", { class: "primary", onclick: () => editor(groups[0] || null, null) }, "+ Add a " + (word === "card" ? "Card" : "Link")),
        isCards ? [h("button", { onclick: hlList }, "Add From HomeLab's List…"), h("button", { onclick: hlRestore, title: "Restore the cards that HomeLab fills in to their defaults" }, "Put HomeLab's Cards Back…")] : null),
      isCards ? h("p", { class: "muted small" }, "The groups marked “Filled in by HomeLab” hold the numbers and the calendar. Their cards can be renamed, given another icon or color, moved, reordered, hidden and restored like any other card.") : null),
    listEl);
}

