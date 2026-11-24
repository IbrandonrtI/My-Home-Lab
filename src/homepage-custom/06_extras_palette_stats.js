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
  /* Docker charts on the Stats tab: processor and memory of every container, stacked, for the last hour. The control panel samples docker once a minute into docker-trends.json. */
  var DK = { data: null, at: 0, busy: false }, DK_COLORS = ["#5b8def", "#4fd1b0", "#f2b84b", "#e27d8b", "#9b7bea", "#6ec1e4", "#b5d96b", "#f08a4b", "#d98bd9", "#7fb0a8"], DK_OTHER = "#8892a8";
  function dockerLoad() {
    DK.busy = true;
    fetch("/images/docker-trends.json?t=" + Date.now(), { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error("no file"); return r.json(); })
      .then(function (d) { if (d && Array.isArray(d.t) && d.charts && d.charts.cpu && d.charts.mem) DK.data = d; })
      .catch(function () { /* keep what is shown */ })
      .then(function () { DK.busy = false; DK.at = Date.now(); soon(); });
  }
  function dkNice(v) { var p = Math.pow(10, Math.floor(Math.log(v) / Math.LN10)), m = v / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p; }
  function dkPct(v) { return v === 0 ? "0%" : (v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v.toFixed(2)) + "%"; }
  function dkBytes(b) { return b >= 1073741824 ? (b / 1073741824).toFixed(b >= 10737418240 ? 0 : 1) + " GiB" : Math.round(b / 1048576) + " MiB"; }
  /* A container keeps the same color in both charts: the colors go out in alphabetical order of every name shown. */
  function dkColor(d, name) {
    if (name === "other") return DK_OTHER;
    if (!d.pal) { var all = {}; ["cpu", "mem"].forEach(function (k) { d.charts[k].names.forEach(function (n) { if (n !== "other") all[n] = 1; }); }); d.pal = Object.keys(all).sort(); }
    return DK_COLORS[Math.max(0, d.pal.indexOf(name)) % DK_COLORS.length];
  }
  /* The containers added together as "other" at one reading, biggest first. */
  function dkInside(c, j) {
    var rows = Object.keys(c.rest || {}).map(function (n) { return [n, (c.rest[n] || [])[j] || 0]; }).filter(function (r) { return r[1] > 0; });
    rows.sort(function (a, b) { return b[1] - a[1]; });
    return rows;
  }
  function dkSvg(tag, attrs) { var n = document.createElementNS(SVGNS, tag), k; for (k in attrs) n.setAttribute(k, attrs[k]); return n; }
  function dkCard(d, title, key, fmt, floor, cap, note) {
    var card = el("div", "hl-dk-card"), n = d.t.length, c = d.charts[key], names = c.names, i, k;
    var totals = [];
    for (i = 0; i < n; i++) totals.push(names.reduce(function (a, nm) { return a + ((c.series[nm] || [])[i] || 0); }, 0));
    var top = Math.max(floor, Math.max.apply(null, totals) * 1.12), ymax = Math.min(cap || Infinity, dkNice(top));
    var head = el("div", "hl-dk-head"), now = totals[n - 1] || 0;
    head.appendChild(el("b", "", title));
    head.appendChild(el("span", "hl-dk-now", fmt(now)));
    if (note) head.appendChild(el("small", "", note));
    card.appendChild(head);
    var plot = el("div", "hl-dk-plot"), svg = dkSvg("svg", { viewBox: "0 0 1000 100", preserveAspectRatio: "none", "aria-hidden": "true" }), below = [];
    for (i = 0; i < n; i++) below.push(0);
    names.forEach(function (nm) {
      var vals = c.series[nm] || [], up = [], top2 = [], bot = [];
      for (i = 0; i < n; i++) { up.push(below[i] + (vals[i] || 0)); }
      for (i = 0; i < n; i++) { var x = (n > 1 ? i / (n - 1) * 1000 : 0).toFixed(1); top2.push(x + " " + (100 - Math.min(up[i], ymax) / ymax * 100).toFixed(2)); bot.push(x + " " + (100 - Math.min(below[i], ymax) / ymax * 100).toFixed(2)); }
      var path = dkSvg("path", { d: "M" + top2.join(" L") + " L" + bot.reverse().join(" L") + " Z", fill: dkColor(d, nm), "fill-opacity": "0.8", stroke: dkColor(d, nm), "stroke-width": "1.2", "vector-effect": "non-scaling-stroke" });
      svg.appendChild(path);
      below = up;
    });
    [0, 50, 100].forEach(function (y) { svg.appendChild(dkSvg("line", { x1: 0, x2: 1000, y1: y, y2: y, class: "hl-dk-grid", "vector-effect": "non-scaling-stroke" })); });
    plot.appendChild(svg);
    [[0, 0], [50, ymax / 2], [100, ymax]].forEach(function (p) { var l = el("span", "hl-dk-y", fmt(p[1])); l.style.bottom = p[0] + "%"; plot.appendChild(l); });
    var line = el("div", "hl-dk-line"), tip = el("div", "hl-dk-tip");
    line.hidden = tip.hidden = true;
    plot.appendChild(line); plot.appendChild(tip);
    plot.addEventListener("mousemove", function (e) {
      var r = plot.getBoundingClientRect(), f = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), j = Math.round(f * (n - 1)), when = new Date(d.t[j] * 1000);
      line.style.left = (n > 1 ? j / (n - 1) * 100 : 0) + "%"; line.hidden = tip.hidden = false;
      tip.textContent = "";
      tip.appendChild(el("b", "", when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) + "  ·  " + fmt(totals[j])));
      /* Biggest first, so the list reads from the container using the most down to the least. */
      names.slice().sort(function (x, y) { return ((c.series[y] || [])[j] || 0) - ((c.series[x] || [])[j] || 0); }).forEach(function (nm) {
        var v = (c.series[nm] || [])[j] || 0, row = el("div", "hl-dk-row"), dot = el("i");
        dot.style.background = dkColor(d, nm);
        row.appendChild(dot); row.appendChild(el("span", "", nm)); row.appendChild(el("em", "", fmt(v)));
        tip.appendChild(row);
        if (nm === "other") {
          var ins = dkInside(c, j);
          ins.slice(0, 6).forEach(function (r) { var sub = el("div", "hl-dk-sub"); sub.appendChild(el("span", "", r[0])); sub.appendChild(el("em", "", fmt(r[1]))); tip.appendChild(sub); });
          if (ins.length > 6) tip.appendChild(el("div", "hl-dk-sub", "+ " + (ins.length - 6) + " more"));
        }
      });
      tip.style.left = (f > 0.6 ? "auto" : "calc(" + f * 100 + "% + 14px)"); tip.style.right = (f > 0.6 ? "calc(" + (100 - f * 100) + "% + 14px)" : "auto");
    });
    plot.addEventListener("mouseleave", function () { line.hidden = tip.hidden = true; });
    card.appendChild(plot);
    var ax = el("div", "hl-dk-x"), span = Math.round((d.t[n - 1] - d.t[0]) / 60);
    ax.appendChild(el("span", "", span > 0 ? span + " min ago" : "")); ax.appendChild(el("span", "", "now"));
    card.appendChild(ax);
    return card;
  }
  function dkDraw(box, d) {
    box.textContent = "";
    if (!d || d.t.length < 2) {
      box.appendChild(el("p", "hl-dk-empty", d ? "Collecting data. The Docker charts fill in over the next hour." : DK.at ? "No Docker data yet. The control panel writes it once a minute, a minute after it starts." : "Loading Docker usage…"));
      return;
    }
    var cores = d.cores || 1, ageMin = Math.round((Date.now() / 1000 - d.updated) / 60);
    box.appendChild(dkCard(d, "Docker CPU", "cpu", dkPct, 5, 100, "of all " + cores + " cores" + (ageMin > 5 ? " · last sample " + ageMin + " min ago" : "")));
    box.appendChild(dkCard(d, "Docker memory", "mem", dkBytes, 268435456, 0, ""));
  }
  function dockerCharts() {
    var lg = document.getElementById("layout-groups"), box = document.getElementById("hl-docker");
    var on = lg && lg.parentNode && lg.querySelector("li[id^='stat-']");
    if (!on) { if (box && !box.hidden) box.hidden = true; return; }
    if (!box) { box = el("section"); box.id = "hl-docker"; box.setAttribute("aria-label", "Docker usage"); }
    if (box.parentNode !== lg.parentNode || box.nextSibling !== lg) lg.parentNode.insertBefore(box, lg);
    if (box.hidden) box.hidden = false;
    if (!DK.busy && Date.now() - DK.at > 60000) dockerLoad();
    var key = DK.data ? DK.data.updated + ":" + DK.data.t.length : DK.at ? "none" : "wait";
    if (box.getAttribute("data-key") !== key) { box.setAttribute("data-key", key); dkDraw(box, DK.data); }
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
    /* The plain header is hidden by the style sheet until the gauges hold real numbers (it shows anyway after 4 seconds). */
    if (!document.documentElement.classList.contains("hl-ready") && /\d/.test(box.textContent)) document.documentElement.classList.add("hl-ready");
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
    dots(); waiting(); hello(); dock(); find(); jellyfin(); stats(); dockerCharts(); counting();
    if (!TR.busy && Date.now() - TR.at > 30000) trendsLoad();
  }
  function soon() { if (!queued) { queued = true; window.requestAnimationFrame(run); } }
  soon();
  new MutationObserver(soon).observe(document.documentElement, { childList: true, subtree: true });
  window.setInterval(soon, 3000);
})();
/* <<< homelab extras <<< */

