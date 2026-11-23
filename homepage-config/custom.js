/* >>> homelab groups >>> */
(function () {
  var queued = false;
  function slug(t) { return String(t || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); }
  function label() {
    queued = false;
    var groups = document.querySelectorAll(".bookmark-group, .services-group");
    for (var i = 0; i < groups.length; i++) {
      var h = groups[i].querySelector(".bookmark-group-name, .service-group-name");
      var s = h ? slug(h.textContent.replace(/\s*\u00b7\s*\d+$/, "")) : "";
      if (s && groups[i].getAttribute("data-group") !== s) groups[i].setAttribute("data-group", s);
    }
    var marks = document.querySelectorAll(".bookmark > a");
    for (var j = 0; j < marks.length; j++) {
      var n = marks[j].querySelector(".bookmark-name");
      var t = n ? slug(n.textContent) : "";
      if (t && marks[j].getAttribute("data-bm") !== t) marks[j].setAttribute("data-bm", t);
    }
  }
  function soon() { if (!queued) { queued = true; window.requestAnimationFrame(label); } }
  soon();
  new MutationObserver(soon).observe(document.documentElement, { childList: true, subtree: true });
})();
/* <<< homelab groups <<< */

/* >>> homelab player >>> */
(function () {
  var box = null, frame = null, src = "", queued = false;
  var style = document.createElement("style");
  style.textContent = "#hl-player-box{position:absolute;z-index:5;overflow:hidden;border-radius:10px;}" +
    "#hl-player-box.hl-away{left:-10000px !important;pointer-events:none;}" +
    "#hl-player{display:block;width:calc(100% + 32px);height:100%;border:0;}";
  document.head.appendChild(style);

  function cardFrame() { return document.querySelector("#navidrome-card iframe"); }
  function real(u) { return !!u && u.indexOf("about:") !== 0; }

  function address(cf) {
    var u = cf.getAttribute("src") || "";
    if (!real(u)) return src;
    if (location.protocol === "https:" && u.indexOf("http:") === 0) {
      var a = document.querySelector('#navidrome-card a[href^="https:"]');
      if (a) { try { return new URL(a.href).origin; } catch (e) {  } }
    }
    return u;
  }

  function make(u) {
    box = document.createElement("div");
    box.id = "hl-player-box";
    box.className = "hl-away";
    frame = document.createElement("iframe");
    frame.id = "hl-player";
    frame.setAttribute("allow", "autoplay; fullscreen");
    frame.src = u;
    box.appendChild(frame);
    document.body.appendChild(box);
  }

  function scroller(el) {
    for (var e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      var o = window.getComputedStyle(e).overflowY;
      if (o === "auto" || o === "scroll" || e.hasAttribute("data-hl-locked")) return e;
    }
    return null;
  }

  function place() {
    queued = false;
    var cf = cardFrame(), host = null, sc = null;
    if (cf) {
      var u = address(cf);
      if (u) {
        if (!box) make(u); else if (u !== src) frame.src = u;
        src = u;
      }
      if (real(cf.getAttribute("src"))) cf.setAttribute("src", "about:blank");
      if (cf.parentElement && !cf.closest(".hl-folded") && !document.documentElement.classList.contains("hl-sliding")) { host = cf.parentElement.getBoundingClientRect(); sc = scroller(cf.parentElement); }
    }
    if (!box) return;
    if (host && host.width > 0 && host.height > 0) {
      var home = sc || document.body;
      if (box.parentNode !== home) {
        if (sc && window.getComputedStyle(sc).position === "static") sc.style.position = "relative";
        home.appendChild(box);
      }
      box.className = "";
      box.style.left = "0px";
      box.style.top = "0px";
      var o = box.getBoundingClientRect();
      var z = parseFloat(window.getComputedStyle(document.documentElement).zoom) || 1;
      box.style.cssText = "left:" + ((host.left - o.left) / z) + "px;top:" + ((host.top - o.top) / z) + "px;width:" + (host.width / z) + "px;height:" + (host.height / z) + "px;";
    } else if (box.className !== "hl-away") {
      box.className = "hl-away";
    }
  }

  function soon() { if (!queued) { queued = true; window.requestAnimationFrame(place); } }
  soon();
  new MutationObserver(soon).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("resize", soon);
  window.setInterval(soon, 500);
})();
/* <<< homelab player <<< */

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
    root.classList.toggle("hl-player-min", store("hl-player-shrunk") === "1");
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
    var d = new Date(), h = d.getHours();
    var part = h >= 5 && h < 12 ? "Good morning" : h >= 12 && h < 17 ? "Good afternoon" : "Good evening";
    var line = part + (raw ? ", " + raw : ""), date = d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }), key = line + "|" + (inside ? "" : date);
    if (box.getAttribute("data-key") !== key) {
      box.setAttribute("data-key", key);
      box.textContent = line;
      if (!inside) box.appendChild(el("small", "", date));
    }
    if (box.hidden) box.hidden = false;
  }

  /* Quick launch: icons of favorite services in the bar under the header. By default it starts with the list below and moves the services opened most often to the front (counted in this browser). */
  var PREFER = ["jellyfin-card", "immich-card", "nextcloud-card", "filebrowser-card", "portainer-card", "adguard-card", "beszel-card", "tailscale-card"];
  var DOCK_MAX = 5, SKIP = /^(customize|linkedit|terminal|navidrome)-card$/, VKEY = "hl-visits", CKEY = "hl-dock-cache", BKEY = "hl-link-cache", TKEY = "hl-tray", TRAY_MAX = 12;
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
      var li = el("li", "hl-trow"), ic = el("span", "hl-di");
      trayIcon(ic, c);
      li.appendChild(ic);
      li.appendChild(el("span", "hl-tname", c.r.name));
      li.appendChild(trayBtn("↑", "Move " + c.r.name + " earlier", function () { trayEdit(function (l) { l.splice(i - 1, 0, l.splice(i, 1)[0]); }); }, i === 0));
      li.appendChild(trayBtn("↓", "Move " + c.r.name + " later", function () { trayEdit(function (l) { l.splice(i + 1, 0, l.splice(i, 1)[0]); }); }, i === list.length - 1));
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
      lsSet("hl-jf-open", jfOpen() ? 0 : 1);
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
    if (!side || !sc) return;
    var a = card.querySelector("a[href]"), base = "";
    try { base = a ? new URL(a.href).origin : ""; } catch (e) { base = ""; }
    if (!base) return;
    if (!fr) {
      fr = el("div"); fr.id = "hl-jf-frame";
      var view = el("div", "hl-jf-view");
      var f = el("iframe"); f.title = "Jellyfin library"; f.setAttribute("loading", "lazy"); f.setAttribute("allow", "fullscreen; autoplay"); f.src = base + "/web/index.html";
      var o = el("a", "hl-jf-open", "Open Jellyfin"); o.href = base + "/"; o.target = "_blank"; o.rel = "noopener";
      view.appendChild(f); fr.appendChild(view); fr.appendChild(o);
      if (window.ResizeObserver) new ResizeObserver(jfFit).observe(view);
    }
    if (fr.parentNode !== sc) sc.appendChild(fr);
    jfFit();
  }
  /* The card is narrower than a desktop window, which makes Jellyfin switch to its small-screen layout (and its slideshow does not show there). So Jellyfin is drawn at desktop width and scaled down to fit the card. */
  var JF_WIDE = 1100;
  function jfFit() {
    var v = document.querySelector("#hl-jf-frame .hl-jf-view"), f = v ? v.firstElementChild : null;
    if (!v || !f || !v.clientWidth || !v.clientHeight) return;
    var k = v.clientWidth / JF_WIDE;
    if (k < 0.6 || k > 1) k = 1;
    var w = Math.round(v.clientWidth / k), h = Math.round(v.clientHeight / k), sig = w + "x" + h;
    if (f.getAttribute("data-fit") === sig) return;
    f.setAttribute("data-fit", sig);
    f.style.width = w + "px";
    f.style.height = h + "px";
    f.style.transform = k < 1 ? "scale(" + k.toFixed(4) + ")" : "";
  }

  /* Search palette (Ctrl+K). */
  var PAL = { box: null, input: null, list: null, items: [], shown: [], at: 0, from: null };
  var ICON_PAL = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>';
  function palItems() {
    var out = [];
    all(".service").forEach(function (li) {
      if (/^(stat|cal)-/.test(li.id) || /^(customize|linkedit|terminal)-card$/.test(li.id)) return;
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
  function palDraw() {
    var q = PAL.input.value.trim().toLowerCase();
    var list = PAL.items.map(function (it) { return { it: it, s: palScore(q, it) }; }).filter(function (x) { return x.s > 0; });
    list.sort(function (a, b) { return b.s - a.s; });
    PAL.shown = list.slice(0, 40).map(function (x) { return x.it; });
    if (PAL.at >= PAL.shown.length) PAL.at = Math.max(0, PAL.shown.length - 1);
    var ul = PAL.list;
    while (ul.firstChild) ul.removeChild(ul.firstChild);
    if (!PAL.shown.length) { var none = el("li", "hl-pnone", "Nothing matches."); none.setAttribute("role", "presentation"); ul.appendChild(none); return; }
    PAL.shown.forEach(function (it, i) {
      var li = el("li"), ic = el("span", "hl-pi");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", i === PAL.at ? "true" : "false");
      if (it.icon) ic.appendChild(it.icon.cloneNode(true)); else ic.innerHTML = ICON_PAL;
      li.appendChild(ic);
      li.appendChild(el("span", "hl-pn", it.name));
      li.appendChild(el("span", "hl-pg", it.group));
      li.onmousemove = function () { if (PAL.at !== i) { PAL.at = i; palMark(); } };
      li.onclick = function () { palGo(i); };
      ul.appendChild(li);
    });
  }
  function palMark() {
    all("li", PAL.list).forEach(function (li, i) { li.setAttribute("aria-selected", i === PAL.at ? "true" : "false"); });
    var cur = PAL.list.children[PAL.at];
    if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
  }
  function palClose() {
    if (!PAL.box || PAL.box.hidden) return;
    PAL.box.hidden = true;
    var f = PAL.from; PAL.from = null;
    if (f && f.focus) try { f.focus(); } catch (e) {  }
  }
  function palGo(i) {
    var it = PAL.shown[i];
    palClose();
    if (it) window.setTimeout(it.go, 0);
  }
  function palOpen() {
    if (!PAL.box) {
      var box = el("div"), card = el("div", "hl-pbox"), input = el("input"), ul = el("ul"), foot = el("div", "hl-pfoot");
      box.id = "hl-palette"; box.hidden = true;
      input.type = "text"; input.placeholder = "Search services, links and tabs"; input.setAttribute("aria-label", "Search"); input.setAttribute("role", "combobox"); input.setAttribute("autocomplete", "off"); input.spellcheck = false;
      ul.setAttribute("role", "listbox");
      foot.appendChild(el("span", "", "↑ ↓ to choose")); foot.appendChild(el("span", "", "Enter to open")); foot.appendChild(el("span", "", "Esc to close"));
      card.appendChild(input); card.appendChild(ul); card.appendChild(foot); box.appendChild(card);
      box.addEventListener("mousedown", function (e) { if (e.target === box) palClose(); });
      input.addEventListener("input", function () { PAL.at = 0; palDraw(); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") { e.preventDefault(); if (PAL.shown.length) { PAL.at = (PAL.at + 1) % PAL.shown.length; palMark(); } }
        else if (e.key === "ArrowUp") { e.preventDefault(); if (PAL.shown.length) { PAL.at = (PAL.at + PAL.shown.length - 1) % PAL.shown.length; palMark(); } }
        else if (e.key === "Enter") { e.preventDefault(); palGo(PAL.at); }
        else if (e.key === "Escape") { e.preventDefault(); palClose(); }
      });
      document.body.appendChild(box);
      PAL.box = box; PAL.input = input; PAL.list = ul;
    }
    var w = inner();
    ["--lk-accent", "--lk-ink", "--lk-shadow", "--lk-popbase", "--lk-hi", "--lk-popmuted", "--lk-font"].forEach(function (n) {
      var v = w ? tok(n, w) : "";
      if (v) PAL.box.style.setProperty(n, v); else PAL.box.style.removeProperty(n);
    });
    PAL.from = document.activeElement;
    PAL.items = palItems(); PAL.at = 0; PAL.input.value = "";
    palDraw();
    PAL.box.hidden = false;
    PAL.input.focus();
  }
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && String(e.key).toLowerCase() === "k") {
      e.preventDefault();
      if (PAL.box && !PAL.box.hidden) palClose(); else palOpen();
    }
  }, true);
  function find() {
    var tabs = document.getElementById("tabs"), box = document.getElementById("hl-find");
    if (!tabs || !document.getElementById("myTab")) return;
    if (!box) {
      box = el("div"); box.id = "hl-find";
      var b = el("button"); b.type = "button"; b.title = "Search (Ctrl+K)"; b.setAttribute("aria-label", "Search services, links and tabs"); b.innerHTML = ICON_PAL;
      b.onclick = function () { palOpen(); };
      box.appendChild(b);
    }
    after(box, document.getElementById("hl-bell") || document.getElementById("myTab"));
  }

  /* History for the small network graph (the control panel keeps the last hour in trends.json). */
  var TR = { data: null, at: 0, busy: false, stamp: 0 };
  function trendsLoad() {
    TR.busy = true;
    fetch("/images/trends.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); })
      .then(function (d) { TR.data = d; TR.stamp = d && d.updated ? d.updated : Date.now(); TR.busy = false; TR.at = Date.now(); soon(); })
      .catch(function () { TR.busy = false; TR.at = Date.now(); });
  }
  var SVGNS = "http://www.w3.org/2000/svg";
  function sparkPaths(vals, lo, hi) {
    var pts = [], n = vals.length, i;
    for (i = 0; i < n; i++) {
      if (typeof vals[i] !== "number") continue;
      pts.push([n > 1 ? i / (n - 1) * 100 : 0, 38 - (Math.max(lo, Math.min(hi, vals[i])) - lo) / (hi - lo) * 34]);
    }
    if (pts.length < 2) return null;
    var line = pts.map(function (p, k) { return (k ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    return { line: line, area: line + " L" + pts[pts.length - 1][0].toFixed(1) + " 40 L" + pts[0][0].toFixed(1) + " 40 Z" };
  }
  /* The system numbers in the header, drawn as gauges. The original widgets stay in the page (hidden) and are the source of the values. */
  var RING = 113.1, GT = {};
  function clean(s) { return s.replace(/\s+/g, " ").trim(); }
  function num(s) { var m = /(-?\d+(?:[.,]\d+)?)/.exec(s); return m ? parseFloat(m[1].replace(",", ".")) : NaN; }
  function barPct(item) { var b = item.querySelector('div[style*="width"]'), v = b ? parseFloat(b.style.width) : NaN; return isNaN(v) ? NaN : Math.max(0, Math.min(100, v)); }
  function size(s, word) { var m = new RegExp("([\\d.,]+\\s*[KMGTP]i?B)\\s*" + word, "i").exec(s); return m ? m[1].replace(/\s+/, " ") : ""; }
  function rate(s, arrow) { var m = new RegExp("([\\d.,]+)\\s*([KMGT]?i?B/s)\\s*" + arrow, "i").exec(s); return m ? m[1] + " " + m[2] : ""; }
  function tempColor(c) {
    var stops = [[45, 74, 222, 128], [70, 250, 204, 21], [90, 248, 90, 90]], i, a, b, k;
    if (isNaN(c) || c <= stops[0][0]) return stops[0].slice(1).join(",");
    for (i = 1; i < stops.length; i++) {
      if (c <= stops[i][0]) {
        a = stops[i - 1]; b = stops[i]; k = (c - a[0]) / (b[0] - a[0]);
        return [1, 2, 3].map(function (n) { return Math.round(a[n] + (b[n] - a[n]) * k); }).join(",");
      }
    }
    return stops[stops.length - 1].slice(1).join(",");
  }
  function readStats() {
    var wrap = document.getElementById("widgets-wrap"), out = [];
    if (!wrap) return out;
    var kids = Array.prototype.filter.call(wrap.children, function (c) { return c.classList.contains("widget-container"); });
    kids.forEach(function (c) {
      var items = all(".information-widget-resource", c);
      if (!items.length) return;
      var last = c.lastElementChild, label = last && !last.querySelector(".information-widget-resource") && !last.classList.contains("information-widget-resource") ? clean(last.textContent) : "";
      var whole = clean(c.textContent);
      if (/network/i.test(label) || /B\/s/i.test(whole)) {
        var dn = rate(whole, "↓"), up = rate(whole, "↑");
        if (dn || up) out.push({ key: "net", kind: "net", name: "Network", down: dn, up: up });
        return;
      }
      if (/CPU|°|uptime/i.test(whole)) {
        items.forEach(function (it) {
          var tx = clean(it.textContent), p = barPct(it), v;
          if (/CPU/i.test(tx)) { v = num(tx); out.push({ key: "cpu", kind: "ring", name: "CPU", value: isNaN(v) ? "" : Math.round(v) + "%", pct: isNaN(p) ? v : p }); }
          else if (/°|temp/i.test(tx)) {
            v = num(tx); var f = /°\s*F/i.test(tx), lv = f ? (v - 32) * 5 / 9 : v;
            out.push({ key: "temp", kind: "ring", name: "Temperature", value: isNaN(v) ? "" : Math.round(v) + (f ? "°F" : "°C"), pct: lv, col: tempColor(lv) });
          } else if (/uptime/i.test(tx)) out.push({ key: "up", kind: "text", name: "Uptime", value: clean(tx.replace(/uptime/i, "")).replace(/(\d+[dhm])(?=\d)/g, "$1 ") });
          else { var fr = size(tx, "free") || size(tx, ""); out.push({ key: "mem", kind: "ring", name: "Memory", value: fr ? fr + " free" : clean(tx), pct: p }); }
        });
        return;
      }
      if (/no drive|not mounted|not connected/i.test(whole)) return;
      var free = size(whole, "free"), total = size(whole, "total"), pp = barPct(items[0]), bak = /backup/i.test(label);
      if (free) out.push({ key: bak ? "bak" : "pool", kind: "ring", name: bak ? "Backup" : (label || "Storage"), value: free + " free", sub: total ? "of " + total : "", pct: pp, warn: pp >= 85, bad: pp >= 95 });
    });
    var order = { cpu: 1, mem: 2, temp: 3, pool: 4, bak: 5, net: 6, up: 7 };
    out.sort(function (x, y) { return (order[x.key] || 9) - (order[y.key] || 9); });
    return out;
  }
  function ringSvg() {
    var s = document.createElementNS(SVGNS, "svg"), t = document.createElementNS(SVGNS, "circle"), a = document.createElementNS(SVGNS, "circle");
    s.setAttribute("class", "hl-ring"); s.setAttribute("viewBox", "0 0 44 44"); s.setAttribute("aria-hidden", "true");
    [t, a].forEach(function (c, i) { c.setAttribute("cx", "22"); c.setAttribute("cy", "22"); c.setAttribute("r", "18"); c.setAttribute("class", i ? "a" : "t"); s.appendChild(c); });
    a.setAttribute("transform", "rotate(-90 22 22)"); a.setAttribute("stroke-dasharray", String(RING)); a.setAttribute("stroke-dashoffset", String(RING));
    return s;
  }
  function netSpark() {
    var D = TR.data;
    if (!D || !D.rx || D.rx.length < 3) return null;
    var svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("class", "hl-gs"); svg.setAttribute("viewBox", "0 0 100 40"); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true");
    var made = 0;
    [[D.rx, "34,211,238"], [D.tx, "167,139,250"]].forEach(function (s) {
      var v = (s[0] || []).filter(function (x) { return typeof x === "number"; });
      if (v.length < 3) return;
      var p = sparkPaths(s[0], 0, Math.max(Math.max.apply(null, v) * 1.2, 1024));
      if (!p) return;
      var l = document.createElementNS(SVGNS, "path");
      l.setAttribute("d", p.line); l.setAttribute("class", "hl-sl"); l.style.stroke = "rgb(" + s[1] + ")";
      svg.appendChild(l); made++;
    });
    return made ? svg : null;
  }
  function stats() {
    var wrap = document.getElementById("widgets-wrap");
    if (!wrap) return;
    var model = readStats(), box = document.getElementById("hl-stats");
    if (!model.length) { wrap.classList.remove("hl-stats-on"); if (box) box.hidden = true; return; }
    if (!box) { box = el("div"); box.id = "hl-stats"; }
    if (box.parentNode !== wrap) wrap.appendChild(box);
    box.hidden = false;
    wrap.classList.add("hl-stats-on");
    var seen = {};
    model.forEach(function (m, i) {
      seen[m.key] = true;
      var t = GT[m.key];
      if (!t || !t.node.parentNode) {
        var n = el("div", "hl-g hl-g-" + m.key), tx = el("div", "hl-gt"), nm = el("span", "hl-gn"), vl = el("span", "hl-gv"), sb = el("span", "hl-gs2");
        t = GT[m.key] = { node: n, nm: nm, vl: vl, sb: sb, ring: null, sig: "" };
        if (m.kind === "ring") { t.ring = ringSvg(); n.appendChild(t.ring); }
        tx.appendChild(nm); tx.appendChild(vl); tx.appendChild(sb); n.appendChild(tx);
        if (m.kind === "net") { t.spark = null; t.tx = tx; }
      }
      var sig = JSON.stringify(m) + "|" + (m.kind === "net" ? TR.stamp : "");
      if (t.sig !== sig) {
        t.sig = sig;
        t.nm.textContent = m.name;
        if (m.kind === "net") {
          t.vl.textContent = "";
          t.vl.appendChild(el("i", "", "↓")); t.vl.appendChild(document.createTextNode(" " + (m.down || "0") + "  "));
          var up = el("i", "u", "↑"); t.vl.appendChild(up); t.vl.appendChild(document.createTextNode(" " + (m.up || "0")));
          if (t.spark && t.spark.parentNode) t.spark.parentNode.removeChild(t.spark);
          t.spark = netSpark();
          if (t.spark) t.node.appendChild(t.spark);
        } else { t.vl.textContent = m.value || ""; }
        t.sb.textContent = m.sub || ""; t.sb.hidden = !m.sub;
        t.node.classList.toggle("hl-warn", !!m.warn && !m.bad); t.node.classList.toggle("hl-bad", !!m.bad);
        if (m.col) t.node.style.setProperty("--g", m.col); else t.node.style.removeProperty("--g");
        if (t.ring) {
          var p = typeof m.pct === "number" && !isNaN(m.pct) ? Math.max(0, Math.min(100, m.pct)) : 0;
          t.ring.querySelector(".a").setAttribute("stroke-dashoffset", String((RING * (1 - p / 100)).toFixed(1)));
        }
      }
      if (box.children[i] !== t.node) box.insertBefore(t.node, box.children[i] || null);
    });
    Object.keys(GT).forEach(function (k) { if (!seen[k]) { if (GT[k].node.parentNode) GT[k].node.parentNode.removeChild(GT[k].node); delete GT[k]; } });
  }

  /* Numbers count up to their value when they first show, and glide to a new value when it changes. */
  var NUM = /^(\D*?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\D*)$/;
  function parseNum(t) {
    var m = NUM.exec(t);
    if (!m || t.length > 24) return null;
    return { pre: m[1], val: parseFloat(m[2].replace(/,/g, "") + (m[3] || "")), dec: m[3] ? m[3].length - 1 : 0, comma: m[2].indexOf(",") >= 0, post: m[4] };
  }
  function fmtNum(p, v) {
    var s = v.toFixed(p.dec);
    if (p.comma) { var a = s.split("."); a[0] = a[0].replace(/\B(?=(\d{3})+(?!\d))/g, ","); s = a.join("."); }
    return p.pre + s + p.post;
  }
  function tween(node, from, p, final, st) {
    var t0 = Date.now(), dur = 700;
    st.run = true;
    (function frame() {
      var k = Math.min(1, (Date.now() - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      if (!node.parentNode) { st.run = false; return; }
      if (k >= 1) { node.nodeValue = final; st.last = final; st.run = false; return; }
      node.nodeValue = fmtNum(p, from + (p.val - from) * e);
      window.requestAnimationFrame(frame);
    })();
  }
  function counting() {
    var mv = moving();
    all('.service .service-block, #information-widgets .information-widget-resource').forEach(function (b) {
      if (b.closest("#navidrome-card")) return;
      var w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT, null), n;
      while ((n = w.nextNode())) {
        var t = n.nodeValue, st = n.__hl;
        var shown = !!n.parentNode && !!n.parentNode.offsetParent;
        if (!st) st = n.__hl = { last: t, run: false, pending: true, hid: !shown };
        if (st.run) continue;
        var p = parseNum(t);
        if (!p || !mv) { st.last = t; st.pending = false; continue; }
        if (t !== st.last) {
          var old = parseNum(st.last);
          st.last = t; st.pending = false;
          if (old && old.pre === p.pre && old.post === p.post && shown) tween(n, old.val, p, t, st);
        } else if (st.pending && shown) {
          st.pending = false;
          if (p.val !== 0 && (st.hid || Date.now() - T0 < 8000)) tween(n, 0, p, t, st);
        }
      }
    });
  }

  function run() {
    queued = false;
    dots(); waiting(); hello(); dock(); find(); jellyfin(); stats(); counting();
    if (!TR.busy && Date.now() - TR.at > 30000) trendsLoad();
  }
  function soon() { if (!queued) { queued = true; window.requestAnimationFrame(run); } }
  soon();
  new MutationObserver(soon).observe(document.documentElement, { childList: true, subtree: true });
  window.setInterval(soon, 3000);
})();
/* <<< homelab extras <<< */

/* >>> homelab panel >>> */
(function () {
  var STYLE_ID = "hl-live-look";
  var BLUR_PX = { none: 0, sm: 4, md: 12, lg: 16, xl: 24, "2xl": 40, "3xl": 64 };

  function fromPanel(e) {
    var frames = document.querySelectorAll("iframe");
    for (var i = 0; i < frames.length; i++) {
      if (frames[i].contentWindow === e.source) return !!frames[i].closest("#customize-card, #linkedit-card");
    }
    return false;
  }
  function inRange(n) { return typeof n === "number" && n >= 0 && n <= 100; }

  var kept = null;
  function keep() {
    if (kept) return;
    var w = document.getElementById("inner_wrapper"), b = document.getElementById("background");
    kept = {
      filter: w ? w.style.getPropertyValue("backdrop-filter") : "",
      webkit: w ? w.style.getPropertyValue("-webkit-backdrop-filter") : "",
      image: b ? b.style.getPropertyValue("background-image") : ""
    };
  }
  function put(el, prop, val) { if (!el) return; if (val) el.style.setProperty(prop, val); else el.style.removeProperty(prop); }
  var SAVED_ID = "hl-saved-sheet", headWatch = null;
  function placePreview(s) {
    var sv = document.getElementById(SAVED_ID);
    if (sv && sv.parentNode && (s.parentNode !== sv.parentNode || !(sv.compareDocumentPosition(s) & 4))) sv.parentNode.appendChild(s);
    else if (!s.parentNode) document.head.appendChild(s);
    return s;
  }
  var pendingCss = null, savedSeq = 0;
  function clearAll() {
    var s = document.getElementById(STYLE_ID);
    if (pendingCss !== null) {
      if (!s) { s = document.createElement("style"); s.id = STYLE_ID; }
      s.textContent = pendingCss;
      placePreview(s);
    } else if (s) s.remove();
    if (kept) {
      var w = document.getElementById("inner_wrapper"), b = document.getElementById("background");
      put(w, "backdrop-filter", kept.filter);
      put(w, "-webkit-backdrop-filter", kept.webkit);
      put(b, "background-image", kept.image);
      kept = null;
    }
    window.dispatchEvent(new CustomEvent("hl-names", { detail: null }));
    window.dispatchEvent(new Event("hl-look-changed"));
  }
  function look(css) {
    if (typeof css !== "string" || css.length > 60000 || /[<\\]|url\s*\(|@import|expression|javascript:/i.test(css) || !/^[A-Za-z0-9 \n#,.:;(){}\[\]="%@&_>*~+!-]*$/.test(css)) return;
    var s = document.getElementById(STYLE_ID);
    if (!s) { s = document.createElement("style"); s.id = STYLE_ID; }
    s.textContent = css;
    placePreview(s);
  }
  function background(d) {
    if (!inRange(d.saturate) || !inRange(d.brightness) || !inRange(d.opacity) || !Object.prototype.hasOwnProperty.call(BLUR_PX, d.blur)) return;
    keep();
    var w = document.getElementById("inner_wrapper");
    if (w) {
      var f = "blur(" + BLUR_PX[d.blur] + "px) saturate(" + d.saturate / 100 + ") brightness(" + d.brightness / 100 + ")";
      w.style.setProperty("backdrop-filter", f);
      w.style.setProperty("-webkit-backdrop-filter", f);
    }
    var b = document.getElementById("background");
    if (b && typeof d.image === "string" && /^(https?:\/\/|\/)[^'"()\\\s]+$/.test(d.image)) {
      var o = 1 - d.opacity / 100;
      b.style.setProperty("background-image", "linear-gradient(rgb(var(--bg-color) / " + o + "), rgb(var(--bg-color) / " + o + ")), url('" + d.image + "')");
    }
    window.dispatchEvent(new Event("hl-look-changed"));
  }
  function names(d) {
    function t(v, n) { return typeof v === "string" && v.length <= n && !/[\u0000-\u001f"\\<>{}`]/.test(v) ? v : ""; }
    var n = d.names || {}, lg = d.logo || {}, size = typeof lg.size === "number" && lg.size >= 24 && lg.size <= 96 ? lg.size : 48;
    window.dispatchEvent(new CustomEvent("hl-names", { detail: { homelab: t(n.homelab, 24), main: t(n.main, 24), backup: t(n.backup, 24), src: t(lg.src, 150000), link: t(lg.link, 600), size: size } }));
  }
  function saved(d) {
    if (d && d.bg === true && kept) {
      var w0 = document.getElementById("inner_wrapper"), b0 = document.getElementById("background");
      kept.image = b0 ? b0.style.getPropertyValue("background-image") : kept.image;
      kept.filter = w0 ? w0.style.getPropertyValue("backdrop-filter") : kept.filter;
      kept.webkit = w0 ? w0.style.getPropertyValue("-webkit-backdrop-filter") : kept.webkit;
    }
    try {
      fetch("/api/hash", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) { if (j && j.hash) window.localStorage.setItem("hash", j.hash); }).catch(function () {  });
    } catch (e) {  }
    var prevSheet = document.querySelector('link[rel="stylesheet"][href*="custom.css"]');
    if (!prevSheet) { clearAll(); return; }
    var cur = document.getElementById(STYLE_ID);
    if (cur) pendingCss = cur.textContent;
    var base = prevSheet.getAttribute("href").replace(/[?&]hl=\d+/, "");
    var tries = 0, mine = ++savedSeq;
    (function load() {
      if (mine !== savedSeq) return;
      var fresh = prevSheet.cloneNode();
      fresh.setAttribute("href", base + (base.indexOf("?") < 0 ? "?" : "&") + "hl=" + Date.now());
      fresh.onload = function () {
        if (mine !== savedSeq) { fresh.remove(); return; }
        var all = document.querySelectorAll('link[rel="stylesheet"][href*="custom.css"]');
        for (var i = 0; i < all.length; i++) if (all[i] !== fresh) all[i].remove();
        pendingCss = null; clearAll();
        keepSaved(fresh.getAttribute("href"));
      };
      fresh.onerror = function () {
        fresh.remove();
        if (++tries < 40) setTimeout(load, 1500);
      };
      (prevSheet.parentNode || document.head).insertBefore(fresh, prevSheet.nextSibling);
    })();
  }
  function keepSaved(href) {
    try {
      fetch(href, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no"); return r.text(); }).then(function (txt) {
        if (!txt || txt.length > 400000) return;
        var s = document.getElementById(SAVED_ID);
        if (!s) { s = document.createElement("style"); s.id = SAVED_ID; (document.body || document.head).appendChild(s); }
        s.textContent = txt;
        var pv = document.getElementById(STYLE_ID); if (pv) placePreview(pv);
        if (!headWatch && window.MutationObserver) {
          headWatch = new MutationObserver(function (list) {
            for (var i = 0; i < list.length; i++) for (var j = 0; j < list[i].addedNodes.length; j++) {
              var n = list[i].addedNodes[j];
              if (n.nodeType === 1 && n.tagName === "LINK" && /custom\.css/.test(n.getAttribute("href") || "") && !/[?&]hl=\d+/.test(n.getAttribute("href"))) n.setAttribute("media", "not all");
            }
          });
          headWatch.observe(document.head, { childList: true });
        }
        var all = document.querySelectorAll('link[rel="stylesheet"][href*="custom.css"]');
        for (var k = 0; k < all.length; k++) if (!/[?&]hl=\d+/.test(all[k].getAttribute("href"))) all[k].setAttribute("media", "not all");
      }).catch(function () {  });
    } catch (e) {  }
  }
  var waiting = false;
  function reloadWhenUp() {
    if (waiting) return;
    waiting = true;
    var t0 = Date.now(), sawDown = false;
    (function poll() {
      fetch("/api/hash", { cache: "no-store" }).then(function (r) {
        if (!r.ok) throw new Error("not yet");
        if (sawDown || Date.now() - t0 >= 10000) window.location.reload(); else setTimeout(poll, 1500);
      }).catch(function () {
        sawDown = true;
        if (Date.now() - t0 > 90000) window.location.reload(); else setTimeout(poll, 1500);
      });
    })();
  }
  window.addEventListener("message", function (e) {
    var d = e.data;
    if (!d || d.hlp !== 1 || typeof d.type !== "string" || !fromPanel(e)) return;
    if (d.type === "css") look(d.css);
    else if (d.type === "bg") background(d);
    else if (d.type === "names") names(d);
    else if (d.type === "saved") saved(d);
    else if (d.type === "clear") clearAll();
    else if (d.type === "reload") { if (d.wait === true) reloadWhenUp(); else window.location.reload(); }
  });
})();
/* <<< homelab panel <<< */
