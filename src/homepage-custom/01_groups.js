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

