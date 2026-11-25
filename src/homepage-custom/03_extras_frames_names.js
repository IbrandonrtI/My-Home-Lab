/* >>> homelab extras >>> */
(function () {
  var root = document.documentElement, queued = false;
  function store(key, value) { try { if (value === undefined) return window.localStorage.getItem(key); window.localStorage.setItem(key, value); } catch (e) {  } return null; }
  function all(sel, from) { return Array.prototype.slice.call((from || document).querySelectorAll(sel)); }

  function health() {
    all(".service.hl-down").forEach(function (li) { li.classList.remove("hl-down"); });
    all(".service .site-monitor-status > div").forEach(function (d) {
      var li = d.closest(".service");
      if (li && /rose|red/.test(d.className)) li.classList.add("hl-down");
    });
  }

  function moving() {
    var until = Date.now() + 450;
    root.classList.add("hl-sliding");
    (function follow() {
      window.dispatchEvent(new Event("resize"));
      if (Date.now() < until) window.requestAnimationFrame(follow);
      else { root.classList.remove("hl-sliding"); window.dispatchEvent(new Event("resize")); }
    })();
  }

  function shrinkButton() {
    /* The player starts as a slim bar. It is opened with the arrow or by pressing the bar, and the choice is remembered in this browser. The music keeps playing while it is closed. */
    root.classList.toggle("hl-player-min", store("hl-player-shrunk") !== "0");
    var title = document.querySelector("#navidrome-card .service-title");
    if (!title || title.querySelector(".hl-shrink")) return;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "hl-shrink";
    b.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      var on = !root.classList.contains("hl-player-min");
      store("hl-player-shrunk", on ? "1" : "0");
      moving();
      root.classList.toggle("hl-player-min", on);
      label(b);
    });
    label(b);
    title.appendChild(b);
    title.addEventListener("click", function (ev) { if (root.classList.contains("hl-player-min") && !ev.target.closest("a, button")) b.click(); });
  }
  function label(b) {
    var min = root.classList.contains("hl-player-min");
    b.setAttribute("aria-label", min ? "Show the player" : "Shrink the player");
    b.setAttribute("title", min ? "Show the player" : "Shrink the player");
    b.setAttribute("aria-expanded", min ? "false" : "true");
  }

  function folded() { try { return JSON.parse(store("hl-folded") || "[]"); } catch (e) { return []; } }
  function opened() { try { return JSON.parse(store("hl-opened") || "[]"); } catch (e) { return []; } }
  var PANEL_GROUPS = ["Customize", "Edit Links", "Terminal"];
  var FOLDED_AT_FIRST = ["Edit Links", "Terminal"];
  function isFolded(name) { return folded().indexOf(name) >= 0 || (FOLDED_AT_FIRST.indexOf(name) >= 0 && opened().indexOf(name) < 0); }
  function slide(g, fold) {
    var panel = g.querySelector(":scope > div"), still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!panel || still) { g.classList.toggle("hl-folded", fold); window.dispatchEvent(new Event("resize")); return; }
    if (g.querySelector("#navidrome-card")) moving();
    else { var until = Date.now() + 450; (function follow() { window.dispatchEvent(new Event("resize")); if (Date.now() < until) window.requestAnimationFrame(follow); })(); }
    function done() { panel.style.maxHeight = ""; panel.removeEventListener("transitionend", ended); }
    function ended(ev) { if (ev.target === panel && ev.propertyName === "max-height") done(); }
    panel.addEventListener("transitionend", ended);
    window.setTimeout(done, 600);
    if (fold) {
      panel.style.maxHeight = panel.scrollHeight + "px";
      void panel.offsetHeight;
      g.classList.add("hl-folded");
    } else {
      panel.style.maxHeight = "0px";
      g.classList.remove("hl-folded");
      void panel.offsetHeight;
      panel.style.maxHeight = panel.scrollHeight + "px";
    }
  }
  var FRAMES = {
    "Customize": { key: "hl-h-customize", css: "--hl-h-customize", min: 400, max: 1600, vh: 0.88, top: 1200, label: "Customize Height", sel: "#customize-card iframe" },
    "Terminal": { key: "hl-h-terminal", css: "--hl-h-terminal", min: 240, max: 1400, vh: 0.7, top: 720, label: "Terminal Height", sel: "#terminal-card iframe" },
    "Player": { key: "hl-player-h", css: "--lk-player-h", min: 240, max: 1000, vh: 0.54, top: 680, label: "Player Height", sel: "#navidrome-card iframe" }
  };
  function frameHeights() {
    var w = document.getElementById("inner_wrapper");
    if (!w) return;
    Object.keys(FRAMES).forEach(function (n) {
      var f = FRAMES[n], v = parseInt(store(f.key) || "", 10);
      if (v >= f.min && v <= f.max) { if (w.style.getPropertyValue(f.css) !== v + "px") w.style.setProperty(f.css, v + "px"); }
      else if (w.style.getPropertyValue(f.css)) w.style.removeProperty(f.css);
    });
  }
  function groupHeight(g, name) {
    var f = FRAMES[name];
    if (!f || g.querySelector(":scope > .hl-gheight")) return;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "hl-height hl-gheight";
    b.setAttribute("aria-label", "Change the height of " + (name === "Player" ? "the player" : name));
    b.setAttribute("title", "Change the height");
    b.setAttribute("aria-expanded", "false");
    var pop = document.createElement("aside");
    pop.className = "hl-height-pop";
    pop.hidden = true;
    var lab = document.createElement("label");
    lab.textContent = f.label;
    var val = document.createElement("span");
    var rng = document.createElement("input");
    rng.type = "range"; rng.min = String(f.min); rng.max = String(f.max); rng.step = "20";
    rng.setAttribute("aria-label", f.label);
    var back = document.createElement("button");
    back.type = "button";
    back.textContent = "Default";
    function current() {
      var v = parseInt(store(f.key) || "", 10);
      if (v >= f.min && v <= f.max) return v;
      var fr = document.querySelector(f.sel);
      if (fr && fr.offsetHeight > 100) return Math.min(f.max, Math.max(f.min, Math.round(fr.offsetHeight)));
      return Math.min(f.max, Math.max(f.min, Math.round(Math.min(window.innerHeight / (parseFloat(getComputedStyle(document.documentElement).zoom) || 1) * f.vh, f.top))));
    }
    function show() { var v = current(); rng.value = String(v); val.textContent = v + " px"; }
    function changed() { frameHeights(); show(); window.dispatchEvent(new Event("resize")); }
    rng.addEventListener("input", function () { store(f.key, rng.value); changed(); });
    back.addEventListener("click", function () { store(f.key, ""); changed(); });
    ["click", "mousedown", "pointerdown", "touchstart"].forEach(function (t) { pop.addEventListener(t, function (ev) { ev.stopPropagation(); }); });
    function close() { pop.hidden = true; b.setAttribute("aria-expanded", "false"); }
    b.addEventListener("click", function (ev) {
      ev.preventDefault(); ev.stopPropagation();
      pop.hidden = !pop.hidden;
      b.setAttribute("aria-expanded", pop.hidden ? "false" : "true");
      if (!pop.hidden) show();
    });
    document.addEventListener("click", function (ev) { if (!pop.hidden && !pop.contains(ev.target) && ev.target !== b) close(); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !pop.hidden) { close(); b.focus(); } });
    pop.appendChild(lab); pop.appendChild(rng); pop.appendChild(val); pop.appendChild(back);
    g.appendChild(b);
    g.appendChild(pop);
  }

  var LOCKED = "#hl-player-box, #hl-jf-frame iframe, #customize-card iframe, #linkedit-card iframe, #terminal-card iframe", held = null;
  function scrolling(el) {
    for (var e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      if (e.hasAttribute("data-hl-locked")) return e;
      var o = window.getComputedStyle(e).overflowY;
      if (o === "auto" || o === "scroll") return e;
    }
    return null;
  }
  function lock(el) {
    if (held) return;
    var box = scrolling(el), t = box || root;
    var bar = box ? box.offsetWidth - box.clientWidth - (parseFloat(window.getComputedStyle(box).borderLeftWidth) || 0) - (parseFloat(window.getComputedStyle(box).borderRightWidth) || 0)
                  : window.innerWidth - root.clientWidth;
    held = { el: t, overflow: t.style.overflowY, gutter: t.style.scrollbarGutter };
    t.setAttribute("data-hl-locked", "");
    if (bar > 0) t.style.scrollbarGutter = "stable";
    t.style.overflowY = "hidden";
    root.classList.add("hl-lock");
  }
  function unlock() {
    if (!held) return;
    held.el.style.overflowY = held.overflow;
    held.el.style.scrollbarGutter = held.gutter;
    held.el.removeAttribute("data-hl-locked");
    held = null;
    root.classList.remove("hl-lock");
  }
  var hovered = null;
  /* While the pointer is over one of these frames the page itself stays still, so reaching the top or bottom of the frame never moves the dashboard. */
  function sync() {
    if (hovered && hovered.getClientRects().length) lock(hovered); else unlock();
  }
  if (window.matchMedia && window.matchMedia("(hover: hover)").matches) {
    function leave(was) {
      if (was && document.activeElement === was) { try { was.blur(); } catch (e) {  } }
    }
    document.addEventListener("mouseover", function (ev) {
      var over = ev.target && ev.target.closest ? ev.target.closest(LOCKED) : null, now = over ? (over.tagName === "IFRAME" ? over : over.querySelector("iframe")) : null, was = hovered;
      hovered = now;
      if (was && was !== now) leave(was);
      sync();
    });
    root.addEventListener("mouseleave", function () { var was = hovered; hovered = null; leave(was); sync(); });
    window.addEventListener("blur", function () { window.setTimeout(sync, 0); });
    window.addEventListener("focus", function () { window.setTimeout(sync, 0); });
    document.addEventListener("mousedown", function () { window.setTimeout(sync, 0); }, true);
    window.setInterval(sync, 1000);
  }

  function groups() {
    all(".services-group, .bookmark-group").forEach(function (g) {
      var h = g.querySelector(".service-group-name, .bookmark-group-name");
      if (!h) return;
      var name = h.textContent.replace(/\s*·\s*\d+$/, "").trim(), n = g.querySelectorAll("li.service, li.bookmark").length;
      if (PANEL_GROUPS.indexOf(name) >= 0) h.removeAttribute("data-count");
      else if (n && h.getAttribute("data-count") !== String(n)) h.setAttribute("data-count", String(n));
      g.classList.toggle("hl-folded", isFolded(name));
      groupHeight(g, g.querySelector("#navidrome-card") ? "Player" : name);
      if (g.querySelector(":scope > .hl-gfold")) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "hl-gfold";
      b.setAttribute("aria-label", "Fold or open " + name);
      b.addEventListener("click", function () {
        var fold = !isFolded(name), cur = folded().filter(function (x) { return x !== name; }), op = opened().filter(function (x) { return x !== name; });
        if (fold) { if (FOLDED_AT_FIRST.indexOf(name) < 0) cur.push(name); } else if (FOLDED_AT_FIRST.indexOf(name) >= 0) op.push(name);
        store("hl-folded", JSON.stringify(cur));
        store("hl-opened", JSON.stringify(op));
        b.setAttribute("aria-expanded", fold ? "false" : "true");
        slide(g, fold);
      });
      b.setAttribute("aria-expanded", isFolded(name) ? "false" : "true");
      g.appendChild(b);
    });
  }

  function sharp() {
    var w = document.getElementById("inner_wrapper");
    if (!w) return;
    var f = window.getComputedStyle(w).getPropertyValue("backdrop-filter") || "";
    var m = /blur\(\s*([0-9.]+)/.exec(f);
    root.classList.toggle("hl-sharp", !m || parseFloat(m[1]) === 0);
  }
  window.addEventListener("hl-look-changed", sharp);

  function playerHeight() {
    var w = document.getElementById("inner_wrapper"), v = parseInt(store("hl-player-h") || "", 10);
    if (!w) return;
    if (v >= 240 && v <= 1000) { if (w.style.getPropertyValue("--lk-player-h") !== v + "px") w.style.setProperty("--lk-player-h", v + "px"); }
    else if (w.style.getPropertyValue("--lk-player-h")) w.style.removeProperty("--lk-player-h");
  }
  var namesPreview = null, textWas = new WeakMap(), textSet = new WeakMap(), renamed = false;
  function cssText(name) {
    var w = document.getElementById("inner_wrapper");
    var v = w ? (window.getComputedStyle(w).getPropertyValue(name) || "").trim() : "";
    return v.length >= 2 && v.charAt(0) === '"' && v.charAt(v.length - 1) === '"' ? v.slice(1, -1) : "";
  }
  function theNames() {
    if (namesPreview) return namesPreview;
    var w = document.getElementById("inner_wrapper");
    return { homelab: cssText("--hl-name-homelab"), main: cssText("--hl-name-main"), backup: cssText("--hl-name-backup"), src: cssText("--hl-logo-src"), link: cssText("--hl-logo-link"),
             size: w ? parseFloat(window.getComputedStyle(w).getPropertyValue("--hl-logo-size")) || 48 : 48 };
  }
  function nameOf(text, N) {
    var t = text;
    t = t.replace(/^(\s*)connect (main|backup) drive(\s*)$/i, function (all, a, k, z) { var n = N[k.toLowerCase()]; return n ? a + "Connect " + n + " Drive" + z : all; });
    t = t.replace(/^(\s*)homelab(\s*)$/i, function (all, a, z) { return N.homelab ? a + N.homelab + z : all; });
    t = t.replace(/\bmain pool\b/gi, function (all) { return N.main || all; });
    t = t.replace(/\bbackup pool\b/gi, function (all) { return N.backup || all; });
    return t;
  }
  var NAMED = /homelab|main pool|backup pool|connect (main|backup) drive/i;
  function rename() {
    var N = theNames(), w = document.getElementById("inner_wrapper");
    if (!w || !(N.homelab || N.main || N.backup || renamed)) return;
    var walk = document.createTreeWalker(w, NodeFilter.SHOW_TEXT, null), n;
    while ((n = walk.nextNode())) {
      var cur = n.nodeValue, mine = textWas.has(n);
      if (!mine && !NAMED.test(cur)) continue;
      var orig = mine && textSet.get(n) === cur ? textWas.get(n) : cur;
      var next = nameOf(orig, N);
      if (next !== orig) {
        textWas.set(n, orig); textSet.set(n, next); renamed = true;
        if (cur !== next) n.nodeValue = next;
      } else if (mine) {
        if (cur !== orig && textSet.get(n) === cur) n.nodeValue = orig;
        textWas.delete(n); textSet.delete(n);
      }
    }
  }
  var logoShown = "";
  function logo() {
    var N = theNames(), wrap = document.getElementById("widgets-wrap"), el = document.getElementById("hl-logo");
    var tile = wrap ? wrap.querySelector(":scope > .widget-container:has(.information-widget-resource)") || wrap.querySelector(":scope > .widget-container") : null;
    var ok = N.src && /^(https?:\/\/[^\s"'()\\<>]+|data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+\/]+={0,2})$/.test(N.src);
    var link = N.link && /^https?:\/\/[^\s"'()\\<>]+$/.test(N.link) ? N.link : "";
    if (!tile || !ok) {
      if (el) el.remove();
      logoShown = "";
      all(".hl-has-logo").forEach(function (t) { t.classList.remove("hl-has-logo"); });
      return;
    }
    var key = N.src + "|" + link;
    if (el && (el.tagName === "A") !== !!link) { el.remove(); el = null; }
    if (!el) {
      el = document.createElement(link ? "a" : "span");
      el.id = "hl-logo";
      var img = document.createElement("img");
      img.alt = "";
      img.setAttribute("decoding", "async");
      el.appendChild(img);
      logoShown = "";
    }
    if (link) { el.setAttribute("href", link); el.setAttribute("target", "_blank"); el.setAttribute("rel", "noopener noreferrer"); el.setAttribute("aria-label", "Logo (opens a link)"); }
    if (logoShown !== key) { el.firstChild.src = N.src; logoShown = key; }
    var h = Math.max(24, Math.min(96, N.size || 48)) + "px";
    if (el.firstChild.style.height !== h) el.firstChild.style.height = h;
    if (tile.firstElementChild !== el) tile.insertBefore(el, tile.firstChild);
    if (!tile.classList.contains("hl-has-logo")) tile.classList.add("hl-has-logo");
  }
  window.addEventListener("hl-names", function (e) { namesPreview = e.detail || null; rename(); logo(); });

  function searchButton() {
    var host = document.getElementById("information-widgets-right");
    if (!host || document.getElementById("hl-search-btn")) return;
    var b = document.createElement("button");
    b.type = "button";
    b.id = "hl-search-btn";
    b.setAttribute("aria-label", "Search");
    b.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15.5 15.5 21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span>Search</span>';
    b.addEventListener("click", function () {
      var open = root.classList.toggle("hl-search-open");
      var input = document.querySelector("#information-widgets .information-widget-search input");
      if (open && input) input.focus();
    });
    host.appendChild(b);
  }

  function tabName() {
    var t = document.querySelector('#myTab button[aria-selected="true"]');
    var name = t ? t.textContent.trim() : "";
    if (name && root.getAttribute("data-tab") !== name) root.setAttribute("data-tab", name);
  }

  function bars() {
    all('li[id^="stat-"] .service-block').forEach(function (blk) {
      var v = blk.querySelector(".service-block-value, .font-thin");
      var m = v && /^\s*(\d+(?:\.\d+)?)\s*%\s*$/.exec(v.textContent);
      if (!m) { if (blk.classList.contains("hl-bar")) blk.classList.remove("hl-bar", "hl-amber", "hl-red"); return; }
      var pct = Math.max(0, Math.min(100, parseFloat(m[1])));
      blk.classList.add("hl-bar");
      blk.classList.toggle("hl-amber", pct >= 85 && pct < 95);
      blk.classList.toggle("hl-red", pct >= 95);
      if (blk.style.getPropertyValue("--hl-pct") !== pct + "%") blk.style.setProperty("--hl-pct", pct + "%");
    });
  }

  function night() {
    var d = new Date(), h = d.getHours() + d.getMinutes() / 60;
    var n = Math.max(0, Math.min(1, (Math.abs(h - 13) - 5) / 6));
    root.style.setProperty("--hl-night", n.toFixed(2));
  }

  var calWatch = null, calChrome = 70;
  function calendar() {
    var lg = document.getElementById("layout-groups");
    if (!lg) return;
    var cal = lg.querySelector(":scope > .services-group:has(li[id^='cal-'])"), media = lg.querySelector(":scope > .services-group:has(#navidrome-card)");
    var off = !cal || !media || !window.matchMedia("(min-width: 1500px)").matches || document.documentElement.classList.contains("hl-jf-side");
    if (off) {
      if (lg.classList.contains("hl-cal-a") || lg.classList.contains("hl-cal-b")) { lg.classList.remove("hl-cal-a", "hl-cal-b"); lg.style.removeProperty("--hl-cal-h"); lg.style.removeProperty("--hl-cal-cell"); }
      return;
    }
    var others = Array.prototype.filter.call(lg.children, function (g) { return g !== cal && g !== media && g.classList.contains("services-group") && g.offsetHeight > 0; });
    if (calWatch !== lg && window.ResizeObserver) {
      if (calWatch && calWatch.ro) calWatch.ro.disconnect();
      var ro = new ResizeObserver(function () { soon(); });
      ro.observe(media); others.forEach(function (g) { ro.observe(g); });
      lg.ro = ro; calWatch = lg;
    }
    var cols = Math.max(1, getComputedStyle(lg).gridTemplateColumns.split(" ").length - 1), gap = parseFloat(getComputedStyle(lg).rowGap) || 8;
    var rows = [];
    others.forEach(function (g, i) { var r = Math.floor(i / cols); rows[r] = Math.max(rows[r] || 0, g.offsetHeight); });
    var right = rows.reduce(function (a, b) { return a + b; }, 0) + gap * Math.max(0, rows.length - 1);
    var avail = right - media.offsetHeight - gap;
    var state = lg.classList.contains("hl-cal-a") ? "a" : lg.classList.contains("hl-cal-b") ? "b" : "c";
    var toA = state === "a" ? 380 : 392, toB = state === "c" ? 282 : 270;
    var next = avail >= toA ? "a" : avail >= toB ? "b" : "c";
    var ul = cal.querySelector(".services-list"), month = document.getElementById("cal-month");
    if (state !== "b" && ul && cal.offsetHeight > 0) calChrome = cal.offsetHeight - ul.offsetHeight;
    lg.classList.toggle("hl-cal-a", next === "a"); lg.classList.toggle("hl-cal-b", next === "b");
    if (next === "c" || !month) { lg.style.removeProperty("--hl-cal-h"); lg.style.removeProperty("--hl-cal-cell"); return; }
    var h = Math.floor(next === "a" ? avail - calChrome : avail);
    lg.style.setProperty("--hl-cal-h", h + "px");
    var days = month.querySelectorAll("button[style*='14%']"), box = month.querySelector(".service-container");
    if (days.length >= 28 && box) {
      var rowsN = Math.round(days.length / 7), cell = days[0].offsetHeight, title = month.querySelector(".service-title");
      var fixed = (title ? title.offsetHeight : 0) + box.offsetHeight + 8 - rowsN * cell;
      lg.style.setProperty("--hl-cal-cell", Math.max(18, Math.min(44, Math.floor((h - fixed) / rowsN))) + "px");
    }
  }

