  function linkRows() {
    var lg = document.getElementById("layout-groups");
    if (!lg) return;
    var items = Array.prototype.filter.call(lg.children, function (g) { return g.classList.contains("bookmark-group"); });
    var on = items.length > 0 && window.matchMedia("(min-width: 1500px)").matches && !lg.querySelector("#navidrome-card, #customize-card, li[id^='stat-']");
    var half = Math.ceil(items.length / 2);
    items.forEach(function (g, k) {
      var want = on ? String(k < half ? 2 * k : 2 * (k - half) + 1) : "";
      if (g.style.order !== want) g.style.order = want;
    });
  }

  function wording() {
    all("#information-widgets .pr-1").forEach(function (e) { if (e.children.length === 0 && e.textContent === "UP") e.textContent = "Uptime"; });
    all("li.service details > summary div").forEach(function (e) {
      var said = e.textContent.replace(/\s+/g, " ").trim();
      if (said !== "API Error Information" && said !== "API Error") return;
      var kids = Array.prototype.slice.call(e.childNodes).filter(function (n) { return n.nodeType === 3; });
      kids.forEach(function (n, i) { n.nodeValue = i === 0 ? "Service Unavailable" : ""; });
    });
    all("#information-widgets span.primary-text").forEach(function (e) {
      if (e.childNodes.length !== 1 || e.firstChild.nodeType !== 3 || e.firstChild.nodeValue.trim() !== "API Error") return;
      var up = e.parentElement, hops = 0;
      while (up && hops < 5 && !/connect .+ drive/i.test(up.textContent)) { up = up.parentElement; hops++; }
      if (up && hops < 5 && /connect .+ drive/i.test(up.textContent) && up.querySelectorAll("span.primary-text").length === 1) e.firstChild.nodeValue = "No Drive";
    });
  }

  var BELL = { data: null, at: 0, busy: false, failed: false, checking: false, note: "" };
  var BELL_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>';
  function panelUrl(hash) { return "https://" + window.location.hostname + ":1100/" + (hash ? "#" + hash : ""); }
  function ago(sec) {
    var m = Math.max(0, Math.round(sec / 60));
    return m < 2 ? "just now" : m < 120 ? m + " minutes ago" : Math.round(m / 60) + " hours ago";
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function bellLoad() {
    BELL.busy = true;
    fetch("/images/alerts.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); })
      .then(function (j) { BELL.data = j && Array.isArray(j.items) ? j : null; BELL.failed = !BELL.data; })
      .catch(function () { BELL.failed = true; })
      .then(function () { BELL.busy = false; BELL.at = Date.now(); bellDraw(); });
  }
  function bellRefresh() {
    if (BELL.checking) return;
    BELL.checking = true;
    BELL.note = "";
    bellDraw();
    var stop = new AbortController(), timer = setTimeout(function () { stop.abort(); }, 70000);
    fetch(panelUrl("") + "api/alerts/refresh", { method: "POST", signal: stop.signal })
      .then(function (r) { if (!r.ok) throw new Error("refused"); })
      .catch(function () { BELL.note = "The control panel did not answer, so this is the last saved list."; })
      .then(function () { clearTimeout(timer); return fetch("/images/alerts.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); }); })
      .then(function (j) { BELL.data = j && Array.isArray(j.items) ? j : null; BELL.failed = !BELL.data; })
      .catch(function () { BELL.failed = true; })
      .then(function () { BELL.checking = false; BELL.at = Date.now(); bellDraw(); });
  }
  function bellDraw() {
    var box = document.getElementById("hl-bell");
    if (!box) return;
    var d = BELL.data, items = d ? d.items : [], worst = items.length ? items[0].level : "";
    var badge = box.querySelector(".hl-bell-n"), btn = box.querySelector("button");
    badge.textContent = items.length > 9 ? "9+" : String(items.length);
    badge.hidden = !items.length;
    badge.className = "hl-bell-n hl-lv-" + (worst || "info");
    btn.setAttribute("aria-label", items.length ? "Notifications: " + items.length + " need attention" : "Notifications: nothing needs attention");
    var pop = box.querySelector(".hl-bellpop");
    while (pop.firstChild) pop.removeChild(pop.firstChild);
    var head = el("div", "hl-bellhead");
    head.appendChild(el("strong", "", "Notifications"));
    var stale = d && d.updated && (Date.now() / 1000 - d.updated) > 1200;
    var side = el("span", "hl-bellside");
    side.appendChild(el("span", "hl-bellsub", BELL.checking ? "Checking..." : !d ? "" : (stale ? "Not updated for a while" : "Checked " + ago(Date.now() / 1000 - (d.updated || 0)))));
    var rb = el("button", "hl-bellrefresh", "Refresh");
    rb.type = "button";
    rb.disabled = BELL.checking;
    rb.setAttribute("aria-label", "Check for new notifications now");
    rb.onclick = function (e) { e.stopPropagation(); bellRefresh(); };
    side.appendChild(rb);
    head.appendChild(side);
    pop.appendChild(head);
    if (BELL.note) pop.appendChild(el("p", "hl-bellempty", BELL.note));
    if (!d) pop.appendChild(el("p", "hl-bellempty", BELL.failed ? "The list is not there yet. It is generated every 5 minutes (run sudo homelab-alerts to generate it now)." : "Looking..."));
    else if (!items.length) pop.appendChild(el("p", "hl-bellempty hl-allgood", "All good. Nothing needs attention."));
    items.forEach(function (it) {
      var row = el("div", "hl-bellrow");
      row.appendChild(el("span", "hl-dot hl-lv-" + (it.level === "bad" || it.level === "warn" ? it.level : "info")));
      var txt = el("div", "hl-belltxt");
      txt.appendChild(el("div", "hl-belltitle", String(it.title || "")));
      if (it.detail) txt.appendChild(el("div", "hl-belldetail", String(it.detail)));
      row.appendChild(txt);
      if (it.action === "update" || it.action === "drives") {
        var a = el("a", "hl-bellbtn", it.action === "update" ? "Update" : "Open Drives");
        a.href = panelUrl(it.action === "update" ? "updates" : "drives");
        a.target = "_blank";
        a.rel = "noopener";
        row.appendChild(a);
      }
      pop.appendChild(row);
    });
  }
  function bell() {
    var tabs = document.getElementById("tabs"), ul = document.getElementById("myTab");
    if (!tabs || !ul) return;
    var box = document.getElementById("hl-bell");
    if (!box) {
      box = el("div", "hl-bellwrap");
      box.id = "hl-bell";
      var btn = el("button", "hl-bellbtn-main");
      btn.type = "button";
      btn.setAttribute("aria-haspopup", "true");
      btn.setAttribute("aria-expanded", "false");
      btn.innerHTML = BELL_ICON;
      btn.appendChild(el("span", "hl-bell-n hl-lv-info", "0"));
      btn.onclick = function () {
        var open = !box.classList.contains("hl-open");
        box.classList.toggle("hl-open", open);
        btn.setAttribute("aria-expanded", String(open));
        if (open && !BELL.busy) bellLoad();
      };
      box.appendChild(btn);
      var pop = el("div", "hl-bellpop");
      pop.setAttribute("role", "region");
      pop.setAttribute("aria-label", "Notifications");
      box.appendChild(pop);
      document.addEventListener("click", function (e) { var b = document.getElementById("hl-bell"); if (b && !b.contains(e.target)) { b.classList.remove("hl-open"); b.querySelector("button").setAttribute("aria-expanded", "false"); } });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") { var b = document.getElementById("hl-bell"); if (b) b.classList.remove("hl-open"); } });
      bellDraw();
    }
    if (box.parentNode !== tabs || ul.nextSibling !== box) tabs.insertBefore(box, ul.nextSibling);
    if (!BELL.busy && Date.now() - BELL.at > 60000) bellLoad();
  }

  var INSTALL = { data: null, at: 0, busy: false };
  var JOBS = { list: [], at: 0, busy: false, seen: 0, seenAt: 0 };
  var INSTALL_STALE = 1200;
  var JOBS_QUIET = 90000;
  function installLoad() {
    INSTALL.busy = true;
    fetch("/images/install-status.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); })
      .then(function (j) { INSTALL.data = j && typeof j.total === "number" && typeof j.done === "number" ? j : null; })
      .catch(function () { INSTALL.data = null; })
      .then(function () { INSTALL.busy = false; INSTALL.at = Date.now(); installDraw(); });
  }
  function jobsLoad() {
    JOBS.busy = true;
    fetch("/images/job-status.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); })
      .then(function (j) {
        var list = j && Array.isArray(j.jobs) ? j.jobs : [], up = j && j.updated || 0, now = Date.now();
        if (up !== JOBS.seen) { JOBS.seen = up; JOBS.seenAt = now; }
        JOBS.list = list.length && now / 1000 - up < INSTALL_STALE && now - JOBS.seenAt < JOBS_QUIET ? list : [];
      })
      .catch(function () { JOBS.list = []; })
      .then(function () { JOBS.busy = false; JOBS.at = Date.now(); installDraw(); });
  }
  function installMode(d) {
    if (!d || d.state === "done" || !(d.total > 0)) return "hidden";
    if (d.state === "failed") return "failed";
    if (d.state === "waiting") return "waiting";
    if (Date.now() / 1000 - (d.updated || 0) > INSTALL_STALE) return "stale";
    return "running";
  }
  function timeLeft(sec) {
    if (typeof sec !== "number" || !(sec > 0)) return "";
    if (sec < 120) return "about a minute left";
    if (sec < 5400) return "about " + Math.round(sec / 60) + " minutes left";
    if (sec < 129600) return "about " + Math.round(sec / 3600) + " hours left";
    return "more than a day left";
  }
  var STEP_MARK = { done: "✓", failed: "✗", now: "●", wait: "○" };
  function jobBlock(pop, jb) {
    var has = typeof jb.pct === "number", box = el("div", "hl-job");
    box.appendChild(el("div", "hl-jobtitle", String(jb.title || "")));
    var line = has ? jb.pct + "%" : "Working";
    var left = timeLeft(jb.eta);
    if (left) line += " \u00b7 " + left;
    box.appendChild(el("div", "hl-jobline", line));
    var bar = el("div", "hl-jobbar" + (has ? "" : " hl-jobwait"));
    var fill = el("i", "");
    fill.style.width = (has ? Math.min(100, Math.max(2, jb.pct)) : 100) + "%";
    bar.appendChild(fill);
    box.appendChild(bar);
    if (jb.step) box.appendChild(el("div", "hl-jobstep", String(jb.step)));
    pop.appendChild(box);
  }
  function installBlock(pop, d, mode) {
    var head = el("div", "hl-bellhead");
    head.appendChild(el("strong", "", mode === "running" ? "Finishing the install" : mode === "failed" ? "A step needs attention" : mode === "waiting" ? "Some steps are waiting" : "No recent progress"));
    head.appendChild(el("span", "hl-bellsub", d.done + " of " + d.total + " steps done"));
    pop.appendChild(head);
    var note = mode === "running" ? ""
      : mode === "stale" ? "The status has not changed for a while. Check it with: sudo homelab-setup status"
      : "Check what is left with: sudo homelab-setup status";
    if (note) pop.appendChild(el("p", "hl-bellempty", note));
    var list = el("div", "hl-steplist");
    (Array.isArray(d.steps) ? d.steps : []).forEach(function (st) {
      var k = st && STEP_MARK[st.s] ? st.s : "wait";
      var row = el("div", "hl-steprow hl-st-" + k);
      row.appendChild(el("span", "hl-stepmark", STEP_MARK[k]));
      row.appendChild(el("span", "hl-steptxt", String(st && st.t || "")));
      list.appendChild(row);
    });
    pop.appendChild(list);
  }
  function installDraw() {
    var box = document.getElementById("hl-install");
    if (!box) return;
    var d = INSTALL.data, mode = installMode(d), jobs = JOBS.list;
    var showInstall = mode !== "hidden";
    box.hidden = !showInstall && !jobs.length;
    if (box.hidden) { box.classList.remove("hl-open"); return; }
    var top = jobs.length ? jobs[0] : null;
    var known = top && typeof top.pct === "number";
    box.classList.toggle("hl-warn", !top && mode !== "running");
    box.classList.toggle("hl-spin", !!top && !known);
    var frac = top ? (known ? Math.min(1, Math.max(0, top.pct / 100)) : 0.25) : Math.min(1, Math.max(0, d.done / d.total));
    box.querySelector(".hl-ring-arc").setAttribute("stroke-dasharray", (frac * 94.25).toFixed(2) + " 94.25");
    box.querySelector(".hl-ring-n").textContent = top ? (known ? top.pct + "%" : "") : Math.ceil(d.done / d.total * 100) + "%";
    box.querySelector("button").setAttribute("aria-label", top ? String(top.title) + (known ? ": " + top.pct + " percent" : "") : "Install progress: " + Math.ceil(d.done / d.total * 100) + " percent, " + d.done + " of " + d.total + " steps done");
    var pop = box.querySelector(".hl-bellpop");
    while (pop.firstChild) pop.removeChild(pop.firstChild);
    if (jobs.length) {
      var head = el("div", "hl-bellhead");
      head.appendChild(el("strong", "", "In progress"));
      head.appendChild(el("span", "hl-bellsub", jobs.length === 1 ? "1 job" : jobs.length + " jobs"));
      pop.appendChild(head);
      jobs.forEach(function (jb) { jobBlock(pop, jb); });
    }
    if (showInstall) installBlock(pop, d, mode);
  }
  function installRing() {
    var tabs = document.getElementById("tabs"), bellBox = document.getElementById("hl-bell");
    if (!tabs || !bellBox) return;
    var box = document.getElementById("hl-install");
    if (!box) {
      box = el("div", "hl-bellwrap");
      box.id = "hl-install";
      box.hidden = true;
      var btn = el("button", "hl-bellbtn-main");
      btn.type = "button";
      btn.setAttribute("aria-haspopup", "true");
      btn.setAttribute("aria-expanded", "false");
      btn.innerHTML = '<svg viewBox="0 0 36 36" width="40" height="40" aria-hidden="true"><circle class="hl-ring-track" cx="18" cy="18" r="15" fill="none" stroke-width="3"/><circle class="hl-ring-arc" cx="18" cy="18" r="15" fill="none" stroke-width="3" stroke-linecap="round" stroke-dasharray="0 94.25" transform="rotate(-90 18 18)"/></svg>';
      btn.appendChild(el("span", "hl-ring-n", ""));
      btn.onclick = function () {
        var open = !box.classList.contains("hl-open");
        box.classList.toggle("hl-open", open);
        btn.setAttribute("aria-expanded", String(open));
        if (open && !INSTALL.busy) installLoad();
        if (open && !JOBS.busy) jobsLoad();
      };
      box.appendChild(btn);
      var pop = el("div", "hl-bellpop");
      pop.setAttribute("role", "region");
      pop.setAttribute("aria-label", "Progress");
      box.appendChild(pop);
      document.addEventListener("click", function (e) { var b = document.getElementById("hl-install"); if (b && !b.contains(e.target)) { b.classList.remove("hl-open"); b.querySelector("button").setAttribute("aria-expanded", "false"); } });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") { var b = document.getElementById("hl-install"); if (b) b.classList.remove("hl-open"); } });
    }
    var place = document.getElementById("hl-find");
    if (!place || place.parentNode !== tabs) place = bellBox;
    if (box.parentNode !== tabs || place.nextSibling !== box) tabs.insertBefore(box, place.nextSibling);
    var every = box.hidden ? 15000 : 10000;
    if (!INSTALL.busy && Date.now() - INSTALL.at > every) installLoad();
    var jevery = JOBS.list.length ? 5000 : 20000;
    if (!JOBS.busy && Date.now() - JOBS.at > jevery) jobsLoad();
  }

  function run() {
    queued = false;
    wording(); health(); shrinkButton(); playerHeight(); frameHeights(); rename(); logo(); groups(); calendar(); linkRows(); searchButton(); tabName(); bars(); sharp(); bell(); installRing();
  }
  function soon() { if (!queued) { queued = true; window.requestAnimationFrame(run); } }
  night(); soon();
  new MutationObserver(soon).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("resize", soon);
  window.setInterval(soon, 3000);
  window.setInterval(night, 600000);
})();
(function () {
  if (window.parent !== window) return;
  var BANDS = [[1850, 2000, "1080", 0.9], [2450, 2650, "1440", 1.1]];
  var root = document.documentElement, timer = 0;
  function fit() {
    var phys = Math.round(window.innerWidth * window.devicePixelRatio), z = 1, name = "";
    for (var i = 0; i < BANDS.length; i++) if (phys >= BANDS[i][0] && phys <= BANDS[i][1]) { name = BANDS[i][2]; z = BANDS[i][3]; }
    if (z === 1) { root.style.removeProperty("zoom"); root.style.removeProperty("--hl-vh"); root.removeAttribute("data-hl-fit"); return; }
    root.style.zoom = String(z);
    root.style.setProperty("--hl-vh", (1 / z).toFixed(4) + "vh");
    root.setAttribute("data-hl-fit", name);
  }
  fit();
  window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(fit, 150); });
})();
(function () {
  if (window.parent !== window) return;
  var root = document.documentElement, queued = false, T0 = Date.now(), GRACE = 25000;
  var reduce = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  function all(sel, from) { return Array.prototype.slice.call((from || document).querySelectorAll(sel)); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function inner() { return document.getElementById("inner_wrapper"); }
  function tok(name, node) { var n = node || document.body; return n ? (window.getComputedStyle(n).getPropertyValue(name) || "").trim() : ""; }
  function quoted(name) { var w = inner(), v = w ? tok(name, w) : ""; return v.length >= 2 && v.charAt(0) === '"' && v.charAt(v.length - 1) === '"' ? v.slice(1, -1) : ""; }
  function moving() { var m = parseFloat(tok("--lk-mo")); return !reduce && !(m === 0); }

  /* Soft light that follows the pointer over a card (the card's own CSS draws it from --mx and --my). */
  var SPOT = 'li[id$="-card"]:not(#navidrome-card), li[id^="stat-"], li[id^="cal-"], .bookmark > a', spotLast = null, spotEvent = null, spotRaf = 0;
  function spotClear() { if (spotLast) { spotLast.style.removeProperty("--mx"); spotLast.style.removeProperty("--my"); spotLast = null; } }
  function spotMove() {
    spotRaf = 0;
    var e = spotEvent;
    if (!e || !e.target || !e.target.closest) return;
    var t = e.target.closest(SPOT);
    if (spotLast && spotLast !== t) spotClear();
    if (!t || !moving()) return;
    var r = t.getBoundingClientRect(), z = parseFloat(root.style.zoom) || 1;
    spotLast = t;
    t.style.setProperty("--mx", ((e.clientX - r.left) / z).toFixed(1) + "px");
    t.style.setProperty("--my", ((e.clientY - r.top) / z).toFixed(1) + "px");
  }
  document.addEventListener("mousemove", function (e) { spotEvent = e; if (!spotRaf) spotRaf = window.requestAnimationFrame(spotMove); }, { passive: true });
  document.addEventListener("mouseleave", spotClear);

  /* Status dots pulse: green when the service is up, red when it is down. */
  function dots() {
    all('.service [class*="-status"] > div').forEach(function (d) {
      var c = typeof d.className === "string" ? d.className : "";
      if (d.offsetWidth > 20) return;
      var down = /rose|red/.test(c), up = !down && /emerald|green|lime/.test(c);
      if (d.classList.contains("hl-dot-up") !== up) d.classList.toggle("hl-dot-up", up);
      if (d.classList.contains("hl-dot-down") !== down) d.classList.toggle("hl-dot-down", down);
    });
  }

  /* While the page is new (or Homepage has just restarted) a tile that cannot reach its service yet shows a moving placeholder, not a red error. */
  function waiting() {
    var on = Date.now() - T0 < GRACE;
    all(".service details").forEach(function (d) {
      var s = d.querySelector("summary"), err = !!s && /api error/i.test(s.textContent);
      if (d.classList.contains("hl-wait") !== (on && err)) d.classList.toggle("hl-wait", on && err);
    });
  }

  /* A small pill at the end of the tab bar that says whether every service answers ("13/13"). It counts the status dots of the cards on the page. A tab with no dots
     (Stats, Links, Customize) keeps showing the count from the last time the Home tab was open, and the details say how long ago that was. Pressing the pill lists what
     is not answering, and each name scrolls to its card (it goes back to the Home tab first when needed). Just after the page opens, a red dot is shown as "checking",
     because services that are still starting look the same. */
  var SKEY = "hl-status-last", STALE_MAX = 12 * 3600000, statusLast = null;
  function statusSave(up, down) {
    var names = down.map(function (x) { return { id: x.id, name: x.name }; });
    if (statusLast && statusLast.up === up && JSON.stringify(statusLast.down) === JSON.stringify(names) && Date.now() - statusLast.at < 30000) return;
    statusLast = { up: up, at: Date.now(), down: names };
    try { window.sessionStorage.setItem(SKEY, JSON.stringify(statusLast)); } catch (e) { /* private window: the count is kept in memory only */ }
  }
  function statusHeld() {
    var m = statusLast;
    if (!m) { try { m = JSON.parse(window.sessionStorage.getItem(SKEY) || "null"); } catch (e) { m = null; } }
    var ok = m && typeof m.up === "number" && typeof m.at === "number" && Array.isArray(m.down) && Date.now() - m.at < STALE_MAX &&
      m.down.every(function (x) { return x && typeof x.name === "string" && typeof x.id === "string"; });
    return ok ? m : null;
  }
  function statusAgo(ms) { var m = Math.floor(ms / 60000); return m < 1 ? "just now" : m < 60 ? m + " min ago" : Math.floor(m / 60) + " h ago"; }
  function statusReveal(id) {
    function show(e) {
      e.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
      e.classList.add("hl-flash");
      window.setTimeout(function () { e.classList.remove("hl-flash"); }, 1800);
    }
    var here = id && document.getElementById(id);
    if (here && here.offsetParent) { show(here); return; }
    var home = document.getElementById("home-tab") || document.querySelector("#myTab button");
    if (home) home.click();
    var tries = 0, t = window.setInterval(function () {
      var e = id && document.getElementById(id);
      if (e && e.offsetParent) { window.clearInterval(t); show(e); } else if (++tries > 25) window.clearInterval(t);
    }, 150);
  }
  /* The notification, install and status popups hang from their button. When the button is not at the edge of the screen (the bell sits in the middle of the bar on a phone)
     a popup that is wider than the room beside it would run off the screen, so it is slid back inside with a small margin. */
  function fitPops() {
    var vw = document.documentElement.clientWidth, gap = 8;
    all("#hl-bell.hl-open, #hl-install.hl-open, #hl-status.hl-open").forEach(function (b) {
      var pop = b.querySelector(".hl-bellpop");
      if (!pop || pop.offsetWidth === 0) return;
      var was = Number(pop.getAttribute("data-dx")) || 0, r = pop.getBoundingClientRect(), left = r.left - was, right = r.right - was, dx = 0;
      if (left < gap) dx = gap - left; else if (right > vw - gap) dx = vw - gap - right;
      if (right - left > vw - 2 * gap) dx = gap - left;
      dx = Math.round(dx);
      if (dx !== was) { pop.style.transform = dx ? "translateX(" + dx + "px)" : ""; pop.setAttribute("data-dx", String(dx)); }
    });
  }
  document.addEventListener("click", function () { window.setTimeout(fitPops, 0); window.setTimeout(fitPops, 150); });
  function status() {
    var tabs = document.getElementById("tabs"), box = document.getElementById("hl-status"), up = 0, down = [];
    all(".service").forEach(function (li) {
      var seen = "";
      all('[class*="-status"] > div', li).forEach(function (d) {
        if (d.offsetWidth > 20) return;
        var c = typeof d.className === "string" ? d.className : "";
        if (/rose|red/.test(c)) seen = "down"; else if (seen !== "down" && /emerald|green|lime/.test(c)) seen = "up";
      });
      if (seen === "up") up++;
      else if (seen === "down") { var a = li.querySelector(".service-title-text, .service-title a, .service-name"); down.push({ id: li.id, name: ((a && a.textContent) || li.id.replace(/-card$/, "")).trim() }); }
    });
    var total = up + down.length, held = null;
    if (total === 0) {
      held = statusHeld();
      if (held) { up = held.up; down = held.down.slice(); total = up + down.length; }
    }
    if (!tabs || total === 0) { if (box && !box.hidden) box.hidden = true; return; }
    var waiting = !held && down.length && Date.now() - T0 < GRACE;
    if (!held && !waiting) statusSave(up, down);
    var state = !down.length ? "ok" : (waiting ? "wait" : "bad");
    var ago = held ? statusAgo(Date.now() - held.at) : "";
    var key = state + "|" + up + "|" + down.map(function (x) { return x.name; }).join(",") + "|" + ago;
    if (!box) {
      box = el("div", "hl-stwrap");
      box.id = "hl-status";
      var btn = el("button");
      btn.type = "button";
      btn.setAttribute("aria-haspopup", "true");
      btn.setAttribute("aria-expanded", "false");
      btn.appendChild(el("span", "hl-st-dot"));
      btn.appendChild(el("span", "hl-st-n"));
      btn.onclick = function () {
        var open = !box.classList.contains("hl-open");
        box.classList.toggle("hl-open", open);
        btn.setAttribute("aria-expanded", String(open));
      };
      box.appendChild(btn);
      var pop = el("div", "hl-bellpop");
      pop.setAttribute("role", "region");
      pop.setAttribute("aria-label", "Service status");
      box.appendChild(pop);
      document.addEventListener("click", function (e) { var b = document.getElementById("hl-status"); if (b && !b.contains(e.target)) { b.classList.remove("hl-open"); b.querySelector("button").setAttribute("aria-expanded", "false"); } });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape") { var b = document.getElementById("hl-status"); if (b) b.classList.remove("hl-open"); } });
    }
    if (box.getAttribute("data-key") !== key) {
      box.setAttribute("data-key", key);
      ["ok", "wait", "bad"].forEach(function (k) { box.classList.toggle("hl-st-" + k, k === state); });
      var head = state === "ok" ? "All services are healthy" : state === "wait" ? "Checking the services…" : down.length + (down.length === 1 ? " service is" : " services are") + " not answering";
      var sub = state === "ok" ? up + " of " + total + " answering" : state === "wait" ? "Some services are still starting." : "";
      if (held) sub += (sub ? ". " : "") + "Last checked " + ago + ", on the Home tab.";
      box.querySelector(".hl-st-n").textContent = state === "ok" ? up + "/" + total : state === "wait" ? "…" : down.length + " down";
      box.querySelector("button").setAttribute("aria-label", head + (sub ? ". " + sub : ""));
      box.querySelector("button").title = head;
      var pop2 = box.querySelector(".hl-bellpop"), top = el("div", "hl-sthead");
      pop2.textContent = "";
      top.appendChild(el("b", "", head));
      if (sub) top.appendChild(el("small", "", sub));
      pop2.appendChild(top);
      if (state === "bad") {
        var list = el("div", "hl-stlist");
        down.forEach(function (x) {
          var b = el("button", "hl-st-chip", x.name);
          b.type = "button";
          b.addEventListener("click", function () { box.classList.remove("hl-open"); statusReveal(x.id); });
          list.appendChild(b);
        });
        pop2.appendChild(list);
      }
    }
    if (tabs.lastElementChild !== box) tabs.appendChild(box);
    if (box.hidden) box.hidden = false;
  }

  /* Greeting above the tabs. */
  function hello() {
    var tabs = document.getElementById("tabs"), wrap = document.getElementById("widgets-wrap"), box = document.getElementById("hl-hello"), raw = quoted("--hl-hello");
    if (!tabs || !tabs.parentNode) return;
    if (raw === "off") { if (box && !box.hidden) box.hidden = true; return; }
    if (!box) { box = el("div"); box.id = "hl-hello"; }
    var inside = !!wrap;
    if (inside) { if (box.parentNode !== wrap) wrap.appendChild(box); }
    else if (box.parentNode !== tabs.parentNode || box.nextSibling !== tabs) tabs.parentNode.insertBefore(box, tabs);
    box.classList.toggle("hl-in-panel", inside);
    var d = new Date();
    var line = raw, date = d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }), key = line + "|" + (inside ? "" : date);
    if (!line) { if (!box.hidden) box.hidden = true; return; }
    if (box.getAttribute("data-key") !== key) {
      box.setAttribute("data-key", key);
      box.textContent = line;
      if (!inside) box.appendChild(el("small", "", date));
    }
    if (box.hidden) box.hidden = false;
  }

  /* Quick launch: icons of favorite services in the bar under the header. By default it starts with the list below and moves the services opened most often to the front (counted in this browser). */
  var PREFER = ["jellyfin-card", "immich-card", "nextcloud-card", "filebrowser-card", "portainer-card", "adguard-card", "beszel-card", "tailscale-card"];
  var DOCK_MAX = 5, SKIP = /^(customize|linkedit|terminal|navidrome|watching|downloaders)-card$/, VKEY = "hl-visits", CKEY = "hl-dock-cache", BKEY = "hl-link-cache", TKEY = "hl-tray", TRAY_MAX = 12;
