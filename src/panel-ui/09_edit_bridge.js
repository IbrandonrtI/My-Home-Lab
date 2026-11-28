// Edit mode on the dashboard talks to the panel through a hidden copy of this page (?only=edit). Only the page that framed it can ask, and every call still needs the panel login.
function dashboardOrigin() {
  try { if (location.ancestorOrigins && location.ancestorOrigins.length) return location.ancestorOrigins[0]; } catch (e) {  }
  try { return new URL(document.referrer).origin; } catch (e) { return ""; }
}
const EDIT_OPS = {
  state: async () => {
    S = await api("GET", "/api/state");
    return { services: S.services.map(g => ({ group: g.group, locked: !!g.locked, automatic: !!g.automatic, cards: g.cards.map(c => ({ name: c.name, locked: !!c.locked, fixed: !!c.fixed })) })), undo: S.undo || "" };
  },
  arrange: async d => {
    await api("POST", "/api/arrange", { tab: d.tab, groups: d.groups });
    S = await api("GET", "/api/state");
    return { undo: S.undo || "" };
  }
};
window.addEventListener("message", async e => {
  const home = dashboardOrigin(), d = e.data;
  if (ONLY !== "edit" || !framed || !home || e.source !== window.parent || e.origin !== home) return;
  if (!d || d.hle !== 1 || typeof d.id !== "number" || !Object.prototype.hasOwnProperty.call(EDIT_OPS, d.op)) return;
  let out;
  try { out = Object.assign({ ok: true }, await EDIT_OPS[d.op](d)); }
  catch (err) { out = { ok: false, login: /log in/i.test(err.message || ""), error: err.message || "Something went wrong." }; }
  window.parent.postMessage(Object.assign({ hlp: 1, type: "edit-reply", id: d.id }, out), home);
});
