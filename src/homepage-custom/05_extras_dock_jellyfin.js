  function lsGet(k) { try { return JSON.parse(window.localStorage.getItem(k) || "null"); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage may be blocked */ } }
  var VIS = lsGet(VKEY) || {}, CACHE = lsGet(CKEY) || {}, BM = lsGet(BKEY) || {};
  function countVisit(e) {
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null, id = "";
    if (!a || (e.type === "auxclick" && e.button !== 1)) return;
    var d = a.closest("#hl-dock"), li = a.closest("li[id$='-card']");
    if (d) id = a.getAttribute("data-id") || ""; else if (li && a.closest(".service")) id = li.id;
    if (!id || SKIP.test(id)) return;
    VIS[id] = Math.min(9999, (VIS[id] || 0) + 1);
    lsSet(VKEY, VIS);
  }
  document.addEventListener("click", countVisit, true);
  document.addEventListener("auxclick", countVisit, true);
  function iconRec(node) {
    if (!node) return null;
    if (node.tagName === "IMG" && node.getAttribute("src")) return { t: "img", v: node.getAttribute("src") };
    var h = node.outerHTML || "";
    return h && h.length < 4000 ? { t: "html", v: h } : null;
  }
  function iconNode(rec) {
    if (!rec) return null;
    if (rec.t === "img") { var im = el("img"); im.src = rec.v; im.alt = ""; return im; }
    var doc = new DOMParser().parseFromString(String(rec.v), "text/html"), n = doc.body.firstElementChild;
    if (!n) return null;
    all("script, iframe, object, embed", n).forEach(function (x) { x.remove(); });
    [n].concat(all("*", n)).forEach(function (x) { Array.prototype.slice.call(x.attributes).forEach(function (at) { if (/^on/i.test(at.name)) x.removeAttribute(at.name); }); });
    return document.importNode(n, true);
  }
  function remember() {
    var dirty = false;
    all('.services-list > li[id$="-card"]').forEach(function (li) {
      if (SKIP.test(li.id)) return;
      var a = li.querySelector("a[href]"), nm = li.querySelector(".service-name"), ic = li.querySelector(".service-icon");
      if (!a) return;
      var rec = { href: a.href, name: (nm ? nm.textContent : a.textContent).trim(), target: a.target || "", ic: iconRec(ic && ic.firstElementChild) };
      if (JSON.stringify(CACHE[li.id]) !== JSON.stringify(rec)) { CACHE[li.id] = rec; dirty = true; }
    });
    if (dirty) lsSet(CKEY, CACHE);
    var bd = false;
    all(".bookmark > a[href]").forEach(function (a) {
      var nm = a.querySelector(".bookmark-name"), ic = a.querySelector(".bookmark-icon"), name = (nm ? nm.textContent : a.textContent).trim();
      if (!name || (!BM[a.href] && Object.keys(BM).length >= 100)) return;
      var rec = { name: name, ic: iconRec(ic && ic.firstElementChild) };
      if (JSON.stringify(BM[a.href]) !== JSON.stringify(rec)) { BM[a.href] = rec; bd = true; }
    });
    if (bd) lsSet(BKEY, BM);
  }
  function dockIds() {
    var raw = quoted("--hl-dock");
    if (raw === "off") return null;
    if (raw === "none") return [];
    if (raw) return raw.split(",");
    var ids = Object.keys(CACHE).filter(function (id) { return !SKIP.test(id) && CACHE[id] && CACHE[id].href; });
    ids.sort(function (x, y) {
      var vx = (VIS[x] || 0) >= 3 ? VIS[x] : 0, vy = (VIS[y] || 0) >= 3 ? VIS[y] : 0;
      if (vx !== vy) return vy - vx;
      var px = PREFER.indexOf(x), py = PREFER.indexOf(y);
      return (px < 0 ? 100 : px) - (py < 0 ? 100 : py);
    });
    return ids.slice(0, DOCK_MAX);
  }
  function cardInfo(li) {
    var a = li.querySelector("a[href]"), nm = li.querySelector(".service-name"), ic = li.querySelector(".service-icon");
    if (!a) return null;
    return { a: a, name: (nm ? nm.textContent : a.textContent).trim(), icon: ic && ic.firstElementChild ? ic.firstElementChild : null };
  }
  /* The icon row: services and links in this browser's own order. Until the person edits it, it follows the Look setting (Most Visited, chosen cards or off). */
  function trayList() {
    if (quoted("--hl-dock") === "off") return null;
    var mine = lsGet(TKEY), out = [];
    if (mine && Array.isArray(mine.items)) {
      mine.items.forEach(function (it) {
        if (it && it.id) { var r = CACHE[it.id]; if (r && r.href) out.push({ id: it.id, r: r }); }
        else if (it && it.h) out.push({ link: true, r: { href: it.h, name: it.n || it.h, target: "_blank", ic: it.i || null } });
      });
      return out.slice(0, TRAY_MAX);
    }
    (dockIds() || []).forEach(function (id) { var r = CACHE[id]; if (r && r.href) out.push({ id: id, r: r }); });
    return out;
  }
  function traySave(list) {
    var items = list.slice(0, TRAY_MAX).map(function (x) { return x.link ? { n: x.r.name, h: x.r.href, i: x.r.ic || null } : { id: x.id }; });
    lsSet(TKEY, { items: items });
  }
  function trayReset() { try { window.localStorage.removeItem(TKEY); } catch (e) { /* storage may be blocked */ } }
  function linkAddress(text) {
    var t = String(text || "").trim();
    if (!t) return "";
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(t)) {
      if (/^(javascript|data|vbscript|file|blob):/i.test(t)) return "";
      var host = t.split(/[\/?#]/)[0].replace(/:\d+$/, "").replace(/^.*@/, "");
      t = (/^\d{1,3}(\.\d{1,3}){3}$/.test(host) || /\.(local|lan|home|internal)$/i.test(host) || host.indexOf(".") < 0 ? "http://" : "https://") + t;
    }
    try { var u = new URL(t); return (u.protocol === "http:" || u.protocol === "https:") && u.hostname ? u.href : ""; } catch (e) { return ""; }
  }
  function letterTile(span, name) { span.textContent = (name || "?").trim().charAt(0).toUpperCase() || "?"; }
  function trayIcon(span, c) {
    var ico = iconNode(c.r.ic);
    if (ico) { span.appendChild(ico); return; }
    if (c.link) {
      var o = ""; try { o = new URL(c.r.href).origin; } catch (e) { o = ""; }
      if (o) {
        var im = el("img"); im.alt = ""; im.referrerPolicy = "no-referrer";
        im.onerror = function () { if (im.parentNode) im.parentNode.removeChild(im); letterTile(span, c.r.name); };
        im.src = o + "/favicon.ico";
        span.appendChild(im);
        return;
      }
    }
    letterTile(span, c.r.name);
  }
  function after(box, anchor) {
    if (!anchor || !anchor.parentNode) return;
    if (box.parentNode !== anchor.parentNode || anchor.nextSibling !== box) anchor.parentNode.insertBefore(box, anchor.nextSibling);
  }
  var DOTS_ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>';
  var TRAY = { wrap: null, btn: null, pop: null, note: "" };
  function trayOpen() { return !!TRAY.wrap && TRAY.wrap.classList.contains("hl-open"); }
  function trayClose(focus) {
    if (!TRAY.wrap) return;
    TRAY.wrap.classList.remove("hl-open");
    TRAY.pop.hidden = true;
    TRAY.btn.setAttribute("aria-expanded", "false");
    if (focus) TRAY.btn.focus();
  }
  function trayEdit(fn) {
    var list = trayList() || [];
    fn(list);
    traySave(list);
    dock();
    trayDraw();
  }
  function trayBtn(txt, label, fn, off) {
    var b = el("button", "hl-tbtn", txt); b.type = "button"; b.setAttribute("aria-label", label); b.title = label;
    if (off) b.disabled = true; else b.onclick = fn;
    return b;
  }
  /* Drag a row to move an icon. The row follows the pointer, the rows it passes slide out of the way, and the list is saved when it is let go. The grip also takes the up and down arrow keys. */
  function trayDrag(ev, li, ul) {
    if (ev.button > 0 || !li.isConnected) return;
    var grip = ev.target.closest && ev.target.closest(".hl-tgrip");
    if (!grip && (ev.pointerType === "touch" || (ev.target.closest && ev.target.closest("button")))) return;
    var rows = Array.prototype.slice.call(ul.children).filter(function (r) { return r.classList.contains("hl-trow"); });
    var from = rows.indexOf(li), step = li.offsetHeight, y0 = ev.clientY, to = from, moved = false;
    if (from < 0 || rows.length < 2) return;
    ev.preventDefault();
    try { li.setPointerCapture(ev.pointerId); } catch (e) { /* the row still follows through the events below */ }
    function place(dy) {
      to = Math.max(0, Math.min(rows.length - 1, from + Math.round(dy / step)));
      rows.forEach(function (r, i) {
        if (r === li) { r.style.transform = "translateY(" + dy + "px)"; return; }
        var shift = (from < to && i > from && i <= to) ? -step : (to < from && i >= to && i < from) ? step : 0;
        r.style.transform = shift ? "translateY(" + shift + "px)" : "";
      });
    }
    function finish(save) {
      li.removeEventListener("pointermove", onMove); li.removeEventListener("pointerup", onUp); li.removeEventListener("pointercancel", onCancel);
      try { li.releasePointerCapture(ev.pointerId); } catch (e) { /* already released */ }
      ul.classList.remove("hl-dragging"); li.classList.remove("hl-drag");
      rows.forEach(function (r) { r.style.transform = ""; });
      if (save && moved && to !== from) trayEdit(function (l) { l.splice(to, 0, l.splice(from, 1)[0]); });
    }
    function onMove(e) {
      var dy = e.clientY - y0;
      if (!moved && Math.abs(dy) < 4) return;
      if (!moved) { moved = true; ul.classList.add("hl-dragging"); li.classList.add("hl-drag"); }
      place(dy);
    }
    function onUp() { finish(true); }
    function onCancel() { finish(false); }
    li.addEventListener("pointermove", onMove); li.addEventListener("pointerup", onUp); li.addEventListener("pointercancel", onCancel);
  }
  function trayDraw() {
    var pop = TRAY.pop;
    if (!pop || !trayOpen()) return;
    var list = trayList() || [], mine = !!lsGet(TKEY);
    while (pop.firstChild) pop.removeChild(pop.firstChild);
    var head = el("div", "hl-thead");
    head.appendChild(el("strong", "", "Quick launch icons"));
    head.appendChild(el("span", "hl-tsub", list.length + " of " + TRAY_MAX));
    pop.appendChild(head);
    var ul = el("ul", "hl-tlist");
    if (!list.length) ul.appendChild(el("li", "hl-tnone", "No icons yet. Add one below."));
    list.forEach(function (c, i) {
      var li = el("li", "hl-trow"), ic = el("span", "hl-di"), grip = el("span", "hl-tgrip", "⋮⋮");
      grip.setAttribute("role", "button"); grip.tabIndex = 0; grip.title = "Drag to move";
      grip.setAttribute("aria-label", "Move " + c.r.name + ". Drag it, or press the up or down arrow key.");
      grip.addEventListener("keydown", function (ev) {
        var d = ev.key === "ArrowUp" ? -1 : ev.key === "ArrowDown" ? 1 : 0, j = i + d;
        if (!d || j < 0 || j >= list.length) return;
        ev.preventDefault();
        trayEdit(function (l) { l.splice(j, 0, l.splice(i, 1)[0]); });
        var g = TRAY.pop && TRAY.pop.querySelectorAll(".hl-tgrip")[j];
        if (g) g.focus();
      });
      li.addEventListener("pointerdown", function (ev) { trayDrag(ev, li, ul); });
      trayIcon(ic, c);
      li.appendChild(grip);
      li.appendChild(ic);
      li.appendChild(el("span", "hl-tname", c.r.name));
      li.appendChild(trayBtn("✕", "Remove " + c.r.name, function () { trayEdit(function (l) { l.splice(i, 1); }); }));
      ul.appendChild(li);
    });
    pop.appendChild(ul);
    var full = list.length >= TRAY_MAX, used = {};
    list.forEach(function (c) { used[c.r.href] = true; });
    var sel = el("select"); sel.setAttribute("aria-label", "Add a service or link from this dashboard");
    var o0 = el("option", "", "Add from this dashboard…"); o0.value = ""; sel.appendChild(o0);
    var gs = el("optgroup"); gs.label = "Services";
    Object.keys(CACHE).filter(function (id) { return !SKIP.test(id) && CACHE[id] && CACHE[id].href && !used[CACHE[id].href]; }).sort(function (x, y) { return CACHE[x].name.localeCompare(CACHE[y].name); }).forEach(function (id) { var o = el("option", "", CACHE[id].name); o.value = "s:" + id; gs.appendChild(o); });
    var gl = el("optgroup"); gl.label = "Links";
    Object.keys(BM).filter(function (h) { return !used[h]; }).sort(function (x, y) { return BM[x].name.localeCompare(BM[y].name); }).forEach(function (h) { var o = el("option", "", BM[h].name); o.value = "b:" + h; gl.appendChild(o); });
    if (gs.children.length) sel.appendChild(gs);
    if (gl.children.length) sel.appendChild(gl);
    sel.disabled = full || sel.children.length < 2;
    sel.onchange = function () {
      var v = sel.value; if (!v) return;
      trayEdit(function (l) {
        if (v.slice(0, 2) === "s:") l.push({ id: v.slice(2), r: CACHE[v.slice(2)] });
        else { var h = v.slice(2), b = BM[h]; if (b) l.push({ link: true, r: { href: h, name: b.name, target: "_blank", ic: b.ic || null } }); }
      });
    };
    var row = el("div", "hl-tadd"); row.appendChild(sel); pop.appendChild(row);
    var form = el("form", "hl-tform");
    var nm = el("input"); nm.type = "text"; nm.maxLength = 24; nm.placeholder = "Name"; nm.setAttribute("aria-label", "Name of the link");
    var ad = el("input"); ad.type = "text"; ad.placeholder = "https://example.com"; ad.setAttribute("aria-label", "Address of the link"); ad.setAttribute("autocapitalize", "off"); ad.spellcheck = false;
    var go = el("button", "hl-tgo", "Add Link"); go.type = "submit"; go.disabled = full;
    var msg = el("div", "hl-tmsg", TRAY.note); msg.setAttribute("role", "status");
    form.appendChild(nm); form.appendChild(ad); form.appendChild(go);
    form.onsubmit = function (ev) {
      ev.preventDefault();
      var name = nm.value.replace(/\s+/g, " ").trim(), href = linkAddress(ad.value);
      if (!name) { msg.textContent = "Enter a name for the link."; nm.focus(); return; }
      if (!href) { msg.textContent = "That address does not work. Use something like https://example.com or http://192.168.1.5:8080."; ad.focus(); return; }
      if (used[href]) { msg.textContent = "That link is already in the row."; return; }
      TRAY.note = "";
      trayEdit(function (l) { l.push({ link: true, r: { href: href, name: name, target: "_blank", ic: null } }); });
    };
    pop.appendChild(form);
    pop.appendChild(msg);
    if (full) pop.appendChild(el("div", "hl-tmsg", "The row can hold up to " + TRAY_MAX + " icons. Remove one to add another."));
    var foot = el("div", "hl-tfoot");
    var rs = el("button", "hl-treset", "Use Most Visited"); rs.type = "button"; rs.disabled = !mine;
    rs.title = "Go back to the icons chosen on the Look screen";
    rs.onclick = function () { trayReset(); TRAY.note = ""; dock(); trayDraw(); };
    foot.appendChild(rs);
    pop.appendChild(foot);
  }
  function trayMenu(tabs) {
    var w = TRAY.wrap;
    if (!w) {
      w = el("div"); w.id = "hl-tray-menu";
      var b = el("button"); b.type = "button"; b.innerHTML = DOTS_ICON;
      b.title = "Edit the quick launch icons"; b.setAttribute("aria-label", "Edit the quick launch icons"); b.setAttribute("aria-haspopup", "dialog"); b.setAttribute("aria-expanded", "false");
      var pop = el("div", "hl-traypop"); pop.hidden = true; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Quick launch icons");
      b.onclick = function () {
        if (trayOpen()) { trayClose(false); return; }
        w.classList.add("hl-open"); pop.hidden = false; b.setAttribute("aria-expanded", "true"); TRAY.note = "";
        trayDraw();
      };
      w.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape" && trayOpen()) { ev.stopPropagation(); trayClose(true); return; }
        if (pop.contains(ev.target)) ev.stopPropagation();
      });
      document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && trayOpen()) trayClose(false); });
      document.addEventListener("click", function (ev) { var path = ev.composedPath ? ev.composedPath() : []; if (trayOpen() && path.indexOf(w) < 0 && !w.contains(ev.target)) trayClose(false); });
      w.appendChild(b); w.appendChild(pop);
      TRAY.wrap = w; TRAY.btn = b; TRAY.pop = pop;
    }
    return w;
  }
  function dock() {
    var tabs = document.getElementById("tabs"), ul = document.getElementById("myTab");
    if (!tabs || !ul) return;
    remember();
    var list = trayList(), box = document.getElementById("hl-dock"), menu = trayMenu(tabs);
    if (!box) { box = el("nav"); box.id = "hl-dock"; box.setAttribute("aria-label", "Quick launch"); }
    if (!list) {
      box.hidden = true; menu.hidden = true;
      if (trayOpen()) trayClose(false);
      return;
    }
    var sig = list.map(function (c) { return (c.id || "l") + "|" + c.r.href + "|" + c.r.name; }).join("\n");
    if (box.getAttribute("data-sig") !== sig) {
      box.setAttribute("data-sig", sig);
      while (box.firstChild) box.removeChild(box.firstChild);
      list.forEach(function (c) {
        var a = el("a"), span = el("span", "hl-di");
        a.href = c.r.href; a.title = c.r.name; a.setAttribute("aria-label", c.r.name);
        if (c.id) a.setAttribute("data-id", c.id);
        if (c.r.target) a.target = c.r.target;
        a.rel = "noopener";
        trayIcon(span, c);
        a.appendChild(span);
        box.appendChild(a);
      });
    }
    var anchor = document.getElementById("hl-install"), fb = document.getElementById("hl-find"), bell = document.getElementById("hl-bell");
    if (!anchor || anchor.parentNode !== tabs) anchor = fb && fb.parentNode === tabs ? fb : bell && bell.parentNode === tabs ? bell : ul;
    after(box, anchor);
    after(menu, box);
    box.hidden = list.length === 0;
    menu.hidden = false;
  }

  /* Jellyfin card: leave out the Songs count. A small arrow on the card opens Jellyfin's own library inside it, beside Navidrome (and hides the card's numbers while it is open). */
  function jfOpen() { return lsGet("hl-jf-open") !== 0; }
  function jfLabel(b) {
    var on = jfOpen();
    b.setAttribute("aria-label", on ? "Close the Jellyfin library" : "Open the Jellyfin library");
    b.setAttribute("title", on ? "Close the Jellyfin library" : "Open the Jellyfin library");
    b.setAttribute("aria-expanded", on ? "true" : "false");
  }
  function jfButton(card) {
    var title = card.querySelector(".service-title");
    if (!title || title.querySelector(".hl-jf-toggle")) return;
    var b = el("button", "hl-shrink hl-jf-toggle");
    b.type = "button";
    b.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var closing = jfOpen();
      lsSet("hl-jf-open", closing ? 0 : 1);
      if (closing) { var old = document.getElementById("hl-jf-frame"); if (old) old.remove(); }
      jellyfin();
      jfLabel(b);
      window.dispatchEvent(new Event("resize"));
    });
    jfLabel(b);
    title.appendChild(b);
  }
  function jellyfin() {
    var card = document.getElementById("jellyfin-card"), side = !!card && jfOpen(), root = document.documentElement;
    if (root.classList.contains("hl-jf-side") !== side) root.classList.toggle("hl-jf-side", side);
    if (!card) return;
    all(".service-block", card).forEach(function (b) {
      var l = b.querySelector(".service-block-label"), tx = (l ? l.textContent : b.textContent).replace(/[\d.,]+/g, "").trim(), gone = /^songs?$/i.test(tx);
      if (b.classList.contains("hl-gone") !== gone) b.classList.toggle("hl-gone", gone);
    });
    jfButton(card);
    var sc = card.querySelector(".service-card"), fr = document.getElementById("hl-jf-frame");
    if (!side || !sc) { jfPlace(); return; }
    var a = card.querySelector("a[href]"), base = "";
    try { base = a ? new URL(a.href).origin : ""; } catch (e) { base = ""; }
    if (!base) return;
    /* The card is rebuilt each time the dashboard switches tabs, and a frame inside it would load Jellyfin again. So the card only holds an empty slot, and the
       frame itself lives outside the card and is laid over the slot (and moved out of sight while the slot is not there), the way the Navidrome player is kept. */
    var slot = document.getElementById("hl-jf-slot");
    if (!slot || slot.parentNode !== sc) { slot = slot || el("div"); slot.id = "hl-jf-slot"; sc.appendChild(slot); }
    if (!fr) {
      fr = el("div", "hl-away"); fr.id = "hl-jf-frame";
      var view = el("div", "hl-jf-view");
      var f = el("iframe"); f.title = "Jellyfin library"; f.setAttribute("allow", "fullscreen; autoplay"); f.src = base + "/web/index.html";
      var o = el("a", "hl-jf-open", "Open Jellyfin"); o.href = base + "/"; o.target = "_blank"; o.rel = "noopener";
      view.appendChild(f); fr.appendChild(view); fr.appendChild(o);
      document.body.appendChild(fr);
      if (window.ResizeObserver) new ResizeObserver(jfFit).observe(view);
    }
    jfPlace();
    jfFit();
  }
  function jfScroller(node) {
    for (var e = node; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      var o = window.getComputedStyle(e).overflowY;
      if (o === "auto" || o === "scroll" || e.hasAttribute("data-hl-locked")) return e;
    }
    return null;
  }
  /* Lay the frame over the slot, or move it out of sight when there is no slot on the page. Moving an iframe in the page loads it again, so it only changes
     parent when the scrolling box around the card changes. */
  function jfPlace() {
    var fr = document.getElementById("hl-jf-frame"), slot = document.getElementById("hl-jf-slot"), root = document.documentElement;
    if (!fr) return;
    var host = null, sc = null;
    if (slot && jfOpen() && !slot.closest(".hl-folded") && !root.classList.contains("hl-sliding")) {
      var r = slot.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) { host = r; sc = jfScroller(slot.parentElement); }
    }
    if (!host) { if (fr.className !== "hl-away") fr.className = "hl-away"; return; }
    var home = sc || document.body;
    if (fr.parentNode !== home) {
      if (sc && window.getComputedStyle(sc).position === "static") sc.style.position = "relative";
      home.appendChild(fr);
    }
    fr.className = "";
    fr.style.left = "0px";
    fr.style.top = "0px";
    var o = fr.getBoundingClientRect(), z = parseFloat(window.getComputedStyle(root).zoom) || 1;
    fr.style.cssText = "left:" + ((host.left - o.left) / z) + "px;top:" + ((host.top - o.top) / z) + "px;width:" + (host.width / z) + "px;height:" + (host.height / z) + "px;";
  }
  window.addEventListener("resize", jfPlace);
  window.setInterval(jfPlace, 500);
  /* The card is narrower than a desktop window, which makes Jellyfin switch to its small-screen layout. So Jellyfin is drawn at exactly JF_WIDE pixels and scaled to fit the card. The Jellyfin look step uses that width to hide the home slideshow in this box only (see JELLYFIN_BOX_CSS in the installer). */
  var JF_WIDE = 1137;
  function jfFit() {
    var v = document.querySelector("#hl-jf-frame .hl-jf-view"), f = v ? v.firstElementChild : null;
    if (!v || !f || !v.clientWidth || !v.clientHeight) return;
    var k = v.clientWidth / JF_WIDE;
    if (k < 0.6) k = 1;
    var w = Math.round(v.clientWidth / k), h = Math.round(v.clientHeight / k), sig = w + "x" + h;
    if (f.getAttribute("data-fit") === sig) return;
    f.setAttribute("data-fit", sig);
    f.style.width = w + "px";
    f.style.height = h + "px";
    f.style.transform = k !== 1 ? "scale(" + k.toFixed(4) + ")" : "";
  }

  /* Search palette (Ctrl+K). */
  var PAL = { box: null, input: null, list: null, items: [], shown: [], at: 0, from: null };
  var ICON_PAL = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>';
  function palItems() {
    var out = [];
    all(".service").forEach(function (li) {
      if (/^(stat|cal)-/.test(li.id) || /^(customize|linkedit|terminal|watching)-card$/.test(li.id)) return;
      var c = cardInfo(li), g = li.closest(".services-group"), gn = g ? g.querySelector(".service-group-name") : null;
      if (c && c.name) out.push({ name: c.name, group: gn ? gn.textContent.trim() : "Services", icon: c.icon, go: function () { c.a.click(); } });
    });
    all(".bookmark > a[href]").forEach(function (a) {
      var nm = a.querySelector(".bookmark-name"), ic = a.querySelector(".bookmark-icon"), g = a.closest(".bookmark-group"), gn = g ? g.querySelector(".bookmark-group-name") : null;
      var name = (nm ? nm.textContent : a.textContent).trim();
      if (name) out.push({ name: name, group: gn ? gn.textContent.trim() : "Links", icon: ic && ic.firstElementChild ? ic.firstElementChild : null, go: function () { a.click(); } });
    });
    all("#myTab button").forEach(function (b) {
      var name = b.textContent.trim();
      if (name) out.push({ name: "Go to " + name, group: "Tab", icon: null, go: function () { b.click(); } });
    });
    var p = el("a"); p.href = "https://" + window.location.hostname + ":1100/"; p.target = "_blank"; p.rel = "noopener";
    out.push({ name: "Open the control panel", group: "Customize", icon: null, go: function () { p.click(); } });
    return out;
  }
  function palScore(q, it) {
    if (!q) return 1;
    var n = it.name.toLowerCase(), i = n.indexOf(q);
    if (i === 0) return 100;
    if (i > 0) return 80 - Math.min(i, 30);
    if (it.group.toLowerCase().indexOf(q) >= 0) return 40;
    var j = 0, k;
    for (k = 0; k < n.length && j < q.length; k++) if (n.charAt(k) === q.charAt(j)) j++;
    return j === q.length ? 20 : 0;
  }
