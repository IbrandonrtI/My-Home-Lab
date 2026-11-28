/* >>> homelab edit >>> */
(function () {
  if (window.parent !== window) return;
  var FRAME_ID = "hl-edit-bridge", NARROW = "(max-width: 700px)";
  var HINT = "Drag a card or a group to move it, or focus its handle and use the arrow keys. Nothing changes until you press Save.";
  var frame = null, origin = "", ready = false, needLogin = false, waiters = [], pending = {}, seq = 0, connectTimer = 0;
  var mode = false, busy = false, leaving = false, info = null, locked = {}, start = "", dirty = false;
  var sayTimer = 0, bar = null, wrap = null, parts = {}, back = null, watch = null, queued = false, drag = null, discard = 0;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }
  function groups() {
    return Array.prototype.slice.call(document.querySelectorAll("#layout-groups > .services-group, #services > .services-group"));
  }
  function gname(g) {
    var h = g.querySelector(".service-group-name");
    return h ? h.textContent.replace(/\s*·\s*\d+$/, "").trim() : "";
  }
  function listOf(g) { return g.querySelector(".services-list"); }
  function cardsOf(g) {
    var ul = listOf(g), out = [];
    if (!ul) return out;
    for (var i = 0; i < ul.children.length; i++) {
      if (ul.children[i].matches("li.service") && ul.children[i].getAttribute("data-name")) out.push(ul.children[i]);
    }
    return out;
  }
  function activeTab() {
    var b = document.querySelector('#myTab button[aria-selected="true"]');
    return b && b.textContent.trim() ? b.textContent.trim() : "Home";
  }
  function read() {
    var out = [];
    groups().forEach(function (g) {
      var n = gname(g);
      if (n) out.push({ name: n, cards: cardsOf(g).map(function (c) { return c.getAttribute("data-name"); }) });
    });
    return out;
  }
  function groupInfo(n) {
    if (!info) return null;
    for (var i = 0; i < info.services.length; i++) if (info.services[i].group === n) return info.services[i];
    return null;
  }

  // The address of the control panel is the one the Customize tab uses. Homepage only draws the groups of the open tab, so it is read from Homepage's own list of cards.
  function originOf(src) {
    try { return new URL(src, window.location.href).origin; } catch (e) { return ""; }
  }
  function findOrigin() {
    var f = document.querySelector("#customize-card iframe");
    if (f && f.getAttribute("src")) return Promise.resolve(originOf(f.getAttribute("src")));
    return fetch("/api/services", { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("no list");
      return r.json();
    }).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        var items = list[i].services || [];
        for (var j = 0; j < items.length; j++) {
          var w = items[j].id === "customize-card" ? (items[j].widgets || [])[0] : null;
          if (w && w.src) return originOf(w.src);
        }
      }
      return "";
    }).catch(function () { return ""; }).then(function (o) {
      return o || (/\.ts\.net$/.test(window.location.hostname) ? "https://" + window.location.hostname + ":1100" : "");
    });
  }
  function openBridge(o) {
    if (!o) return false;
    origin = o;
    frame = document.createElement("iframe");
    frame.id = FRAME_ID;
    frame.title = "Control panel sign-in";
    frame.src = origin + "/?only=edit";
    document.body.appendChild(frame);
    return true;
  }
  function flush(err) {
    var w = waiters;
    waiters = [];
    clearTimeout(connectTimer);
    w.forEach(function (x) { if (err) x.no(err); else x.ok(); });
  }
  function loginBox(on) {
    document.documentElement.classList.toggle("hl-edit-login", !!on);
    if (on && !back) {
      back = el("div", "hl-edit-back");
      var no = el("button", "hl-edit-cancel", "Cancel");
      no.type = "button";
      no.addEventListener("click", function () { loginBox(false); flush(new Error("Sign-in was cancelled.")); });
      back.appendChild(no);
      document.body.appendChild(back);
    }
    if (back) back.hidden = !on;
  }
  function armTimer() {
    clearTimeout(connectTimer);
    connectTimer = setTimeout(function () {
      if (!ready && !document.documentElement.classList.contains("hl-edit-login")) flush(new Error("The control panel did not answer. Check that it is running."));
    }, 25000);
  }
  function connect() {
    if (ready) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      waiters.push({ ok: resolve, no: reject });
      // The sign-in frame is kept after a cancel. The panel only announces its login once, so it is shown again from here.
      if (frame) {
        if (needLogin) loginBox(true);
        armTimer();
        return;
      }
      if (waiters.length > 1) return;
      findOrigin().then(function (o) {
        if (!openBridge(o)) { flush(new Error("The address of the control panel was not found.")); return; }
        armTimer();
      });
    });
  }
  function ask(op, data) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      var t = setTimeout(function () { delete pending[id]; reject(new Error("The control panel did not answer.")); }, 20000);
      pending[id] = { t: t, fn: function (d) {
        if (d.ok) { resolve(d); return; }
        var err = new Error(d.error || "Something went wrong.");
        err.login = !!d.login;
        reject(err);
      } };
      frame.contentWindow.postMessage(Object.assign({ hle: 1, id: id, op: op }, data || {}), origin);
    });
  }
  // A request that fails because the login ran out asks for the password again, once, and then repeats.
  function call(op, data) {
    return connect().then(function () { return ask(op, data); }).catch(function (err) {
      if (!err.login) throw err;
      ready = false;
      return connect().then(function () { return ask(op, data); });
    });
  }
  window.addEventListener("message", function (e) {
    if (!frame || e.source !== frame.contentWindow || e.origin !== origin) return;
    var d = e.data;
    if (!d || d.hlp !== 1) return;
    if (d.type === "edit-ready") { ready = true; needLogin = false; loginBox(false); flush(); }
    else if (d.type === "edit-login") { ready = false; needLogin = true; loginBox(true); }
    else if (d.type === "edit-reply" && pending[d.id]) {
      var p = pending[d.id];
      delete pending[d.id];
      clearTimeout(p.t);
      p.fn(d);
    }
  });

  function say(text, bad) {
    if (!parts.msg) return;
    parts.msg.textContent = text;
    parts.msg.classList.toggle("bad", !!bad);
    window.clearTimeout(sayTimer);
    if (!mode && text) sayTimer = window.setTimeout(function () { if (!mode && !busy) { parts.msg.textContent = ""; draw(); } }, 8000);
  }
  function visible() {
    return mode || (!window.matchMedia(NARROW).matches && groups().some(function (g) { return !!gname(g); }));
  }
  function draw() {
    if (!bar) return;
    place();
    var shown = visible(), tabs = !!document.getElementById("tabs");
    wrap.hidden = !shown || !tabs;
    wrap.classList.toggle("hl-open", mode);
    parts.edit.textContent = mode ? "Editing" : "Edit";
    parts.edit.setAttribute("aria-pressed", String(mode));
    bar.hidden = !mode && !busy && !parts.msg.textContent;
    parts.save.hidden = !mode;
    parts.cancel.hidden = !mode;
    parts.edit.disabled = busy || mode;
    parts.save.disabled = !dirty || busy;
    parts.cancel.disabled = busy;
    parts.cancel.textContent = discard ? "Discard changes?" : "Cancel";
  }
  function refresh() {
    dirty = mode && JSON.stringify(read()) !== start;
    draw();
  }
  function place() {
    var tabs = document.getElementById("tabs");
    if (tabs && wrap.parentNode !== tabs) tabs.appendChild(wrap);
    if (bar.parentNode !== document.body) document.body.appendChild(bar);
  }
  function buildBar() {
    wrap = el("div", "hl-editbtn");
    wrap.id = "hl-editbtn";
    parts.edit = el("button", "", "Edit");
    parts.edit.type = "button";
    parts.edit.title = "Move the cards and groups on this page";
    parts.edit.addEventListener("click", begin);
    wrap.appendChild(parts.edit);
    bar = el("div", "hl-editbar");
    bar.id = "hl-editbar";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Edit this page");
    parts.msg = el("span", "hl-edit-msg");
    parts.msg.setAttribute("aria-live", "polite");
    parts.save = el("button", "hl-eb hl-eb-main", "Save");
    parts.cancel = el("button", "hl-eb", "Cancel");
    parts.save.type = parts.cancel.type = "button";
    parts.save.addEventListener("click", save);
    parts.cancel.addEventListener("click", cancel);
    [parts.msg, parts.save, parts.cancel].forEach(function (n) { bar.appendChild(n); });
    place();
    var inner = document.getElementById("inner_wrapper");
    if (inner) {
      var cs = window.getComputedStyle(inner);
      ["--lk-accent", "--lk-glass", "--lk-glass-a", "--lk-text", "--lk-muted", "--lk-ink", "--lk-hi", "--lk-radius", "--lk-font"].forEach(function (k) {
        var v = cs.getPropertyValue(k);
        if (v && v.trim()) bar.style.setProperty(k, v.trim());
      });
    }
  }

  function begin() {
    if (mode || busy) return;
    busy = true;
    say("Connecting to the control panel...");
    draw();
    call("state").then(function (st) {
      info = st;
      locked = {};
      st.services.forEach(function (g) { g.cards.forEach(function (c) { if (c.locked) locked[c.name] = true; }); });
      busy = false;
      mode = true;
      document.documentElement.classList.add("hl-editing");
      start = JSON.stringify(read());
      dirty = false;
      decorate();
      say(HINT);
      draw();
    }).catch(function (err) {
      busy = false;
      say(err.message, true);
      draw();
    });
  }

  function decorate() {
    queued = false;
    if (!mode) return;
    groups().forEach(function (g) {
      var n = gname(g), gi = groupInfo(n), open = !!gi && !gi.locked;
      var moves = open && window.getComputedStyle(g).order === "0";
      g.setAttribute("data-hl-drop", open ? "1" : "0");
      g.setAttribute("data-hl-move", moves ? "1" : "0");
      var gg = g.querySelector(":scope > .hl-ggrip");
      if (moves && !gg) {
        gg = el("span", "hl-grip hl-ggrip");
        gg.setAttribute("role", "button");
        gg.tabIndex = 0;
        gg.title = "Drag to move the group";
        g.appendChild(gg);
      }
      if (!moves && gg) gg.remove();
      if (gg) gg.setAttribute("aria-label", "Move the group " + n + ". Drag it, or press an arrow key.");
      cardsOf(g).forEach(function (c) {
        var name = c.getAttribute("data-name"), can = open && !locked[name];
        c.setAttribute("data-hl-move", can ? "1" : "0");
        var cg = c.querySelector(":scope > .hl-cgrip");
        if (can && !cg) {
          cg = el("span", "hl-grip hl-cgrip");
          cg.setAttribute("role", "button");
          cg.tabIndex = 0;
          cg.title = "Drag to move";
          c.appendChild(cg);
        }
        if (!can && cg) cg.remove();
        if (cg) cg.setAttribute("aria-label", "Move " + name + ". Drag it, or press an arrow key.");
      });
    });
  }
  function soon() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(function () { queued = false; decorate(); if (bar) draw(); });
  }

  // `tie` is for a pointer exactly on the middle of a card: the card being dragged takes the place of the card it is dropped on.
  function isBefore(r, x, y, grid, tie) {
    if (!grid) return y < r.top + r.height / 2 || (tie && y === r.top + r.height / 2);
    return y < r.top || (y <= r.bottom && (x < r.left + r.width / 2 || (tie && x === r.left + r.width / 2)));
  }
  function placeCard(d, x, y) {
    var under = document.elementsFromPoint(x, y), g = null;
    for (var i = 0; i < under.length && !g; i++) {
      var c = under[i].closest && under[i].closest(".services-group");
      if (c && c.getAttribute("data-hl-drop") === "1" && listOf(c)) g = c;
    }
    if (!g) return;
    var ul = listOf(g), all = cardsOf(g), others = all.filter(function (c) { return c !== d.el; });
    var cs = window.getComputedStyle(ul), grid = cs.display === "grid" && cs.gridTemplateColumns.split(" ").length > 1, ref = null;
    for (var j = 0; j < others.length; j++) {
      if (isBefore(others[j].getBoundingClientRect(), x, y, grid, !!(others[j].compareDocumentPosition(d.el) & Node.DOCUMENT_POSITION_FOLLOWING))) { ref = others[j]; break; }
    }
    var at = all.indexOf(d.el);
    if (at >= 0 && (all[at + 1] || null) === ref) return;
    ul.insertBefore(d.el, ref);
  }
  function placeGroup(d, x, y) {
    var box = d.el.parentNode;
    var mv = groups().filter(function (g) { return g.parentNode === box && g.getAttribute("data-hl-move") === "1"; });
    var others = mv.filter(function (g) { return g !== d.el; }), ref = null;
    for (var i = 0; i < others.length; i++) {
      if (isBefore(others[i].getBoundingClientRect(), x, y, true)) { ref = others[i]; break; }
    }
    var at = mv.indexOf(d.el);
    if (at >= 0 && (mv[at + 1] || null) === ref) return;
    // Past the last group that can move means right after it, so a group that stays at the top by itself keeps its place in the list.
    box.insertBefore(d.el, ref || (others.length ? others[others.length - 1].nextSibling : null));
  }
  function onDown(e) {
    if (!mode || busy || drag || (e.pointerType === "mouse" && e.button !== 0) || !e.target.closest) return;
    var item = null, kind = "", gg = e.target.closest(".hl-ggrip");
    if (gg) { item = gg.parentNode; kind = "group"; }
    else {
      var c = e.target.closest("li.service");
      if (c && c.getAttribute("data-hl-move") === "1" && (e.pointerType !== "touch" || e.target.closest(".hl-cgrip"))) { item = c; kind = "card"; }
    }
    if (!item) return;
    drag = { el: item, kind: kind, id: e.pointerId, x: e.clientX, y: e.clientY, cx: e.clientX, cy: e.clientY, on: false, ghost: null, raf: 0 };
    e.preventDefault();
  }
  function onMove(e) {
    if (!drag || e.pointerId !== drag.id) return;
    if (!drag.on) {
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) < 6) return;
      drag.on = true;
      drag.el.classList.add("hl-dragging");
      drag.ghost = el("div", "hl-ghost", drag.kind === "group" ? gname(drag.el) : drag.el.getAttribute("data-name"));
      document.body.appendChild(drag.ghost);
      document.documentElement.classList.add("hl-dragmode");
    }
    drag.ghost.style.transform = "translate(" + (e.clientX + 14) + "px," + (e.clientY + 14) + "px)";
    drag.cx = e.clientX;
    drag.cy = e.clientY;
    put(drag);
    if (!drag.raf) drag.raf = window.requestAnimationFrame(edgeScroll);
  }
  function put(d) {
    if (d.kind === "group") placeGroup(d, d.cx, d.cy); else placeCard(d, d.cx, d.cy);
  }
  // Holding the pointer near the top or bottom edge keeps scrolling, even when the mouse is not moving.
  function edgeScroll() {
    if (!drag || !drag.on) return;
    drag.raf = 0;
    var step = drag.cy < 60 ? -12 : drag.cy > window.innerHeight - 60 ? 12 : 0, page = document.getElementById("inner_wrapper");
    if (step) {
      if (page && page.scrollHeight > page.clientHeight) page.scrollTop += step; else window.scrollBy(0, step);
      put(drag);
    }
    drag.raf = window.requestAnimationFrame(edgeScroll);
  }
  function onUp(e) {
    if (!drag || e.pointerId !== drag.id) return;
    var d = drag;
    drag = null;
    if (!d.on) return;
    d.el.classList.remove("hl-dragging");
    d.ghost.remove();
    document.documentElement.classList.remove("hl-dragmode");
    discard = 0;
    refresh();
  }
  function onKey(e) {
    if (!mode || !e.target.closest) return;
    var gp = e.target.closest(".hl-grip");
    if (!gp) return;
    var up = e.key === "ArrowUp" || e.key === "ArrowLeft", down = e.key === "ArrowDown" || e.key === "ArrowRight";
    if (!up && !down) return;
    e.preventDefault();
    var item = gp.parentNode, isGroup = gp.classList.contains("hl-ggrip");
    var sibs = isGroup
      ? groups().filter(function (g) { return g.parentNode === item.parentNode && g.getAttribute("data-hl-move") === "1"; })
      : cardsOf(item.closest(".services-group")).filter(function (c) { return c.getAttribute("data-hl-move") === "1"; });
    var to = sibs[sibs.indexOf(item) + (up ? -1 : 1)];
    if (!to) return;
    item.parentNode.insertBefore(item, up ? to : to.nextSibling);
    gp.focus();
    discard = 0;
    refresh();
  }

  // Homepage keeps its own copy of the card list for a moment after the files change. The page reloads only once that list shows what was saved, or after about six seconds.
  function listShows(saved) {
    return fetch("/api/services", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (list) {
      if (!Array.isArray(list)) return true;
      return saved.every(function (g) {
        var hit = list.filter(function (x) { return x.name === g.name; })[0];
        return !hit || (hit.services || []).map(function (s) { return s.name; }).join("\n") === g.cards.join("\n");
      });
    }).catch(function () { return true; });
  }
  function reloadWhenListIsFresh(saved, tries) {
    listShows(saved).then(function (ok) {
      if (ok || tries >= 12) { window.location.reload(); return; }
      setTimeout(function () { reloadWhenListIsFresh(saved, tries + 1); }, 500);
    });
  }
  function save() {
    if (!mode || !dirty || busy) return;
    busy = true;
    say("Saving...");
    draw();
    var sent = read();
    call("arrange", { tab: activeTab(), groups: sent }).then(function () {
      say("Saved. The page reloads in a moment.");
      leaving = true;
      setTimeout(function () { reloadWhenListIsFresh(sent, 0); }, 900);
    }).catch(function (err) {
      busy = false;
      say(err.message, true);
      draw();
    });
  }
  function cancel() {
    if (!mode || busy) return;
    if (dirty && !discard) {
      discard = setTimeout(function () { discard = 0; draw(); }, 4000);
      draw();
      return;
    }
    leaving = true;
    window.location.reload();
  }

  function init() {
    buildBar();
    draw();
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", function (e) {
      if (mode && e.target.closest && e.target.closest("li.service")) { e.preventDefault(); e.stopPropagation(); }
    }, true);
    document.addEventListener("dragstart", function (e) { if (mode) e.preventDefault(); }, true);
    window.addEventListener("beforeunload", function (e) { if (mode && dirty && !leaving) { e.preventDefault(); e.returnValue = ""; } });
    window.addEventListener("resize", draw);
    watch = new MutationObserver(soon);
    watch.observe(document.body, { childList: true, subtree: true });
  }
  if (document.body) init(); else document.addEventListener("DOMContentLoaded", init);
})();
/* <<< homelab edit <<< */
