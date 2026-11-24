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
