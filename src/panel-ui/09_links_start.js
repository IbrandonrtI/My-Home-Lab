// The draft of the Links screen. It is the saved list plus the changes made since, and only Save sends it (all at once).
const NAME_OK = /^[^"'\\{};<>/*:#\[\]|`]+$/;
function startLinks() {
  linkW = S.links.map(g => ({ group: g.group, was: g.group, links: g.links.map(l => Object.assign({}, l, { was: l.name })) }));
  linkBase = JSON.stringify(linkPayload());
}
function linkPayload() {
  return (linkW || []).filter(g => g.links.length).map(g => ({ name: g.group, was: g.was || "", tab: g.tab || "",
    links: g.links.map(l => ({ name: l.name, was: l.was || "", href: l.href || "", icon: l.icon || "", description: l.description || "", abbr: l.abbr || "" })) }));
}
function linkDirty() { return linkW !== null && JSON.stringify(linkPayload()) !== linkBase; }
// Puts the values of the Add or Change window into the draft. Returns a sentence when something is wrong, and changes nothing then.
function draftLink(g, it, v, target, tab) {
  if (!v.name) return "The name cannot be empty.";
  if (!NAME_OK.test(v.name)) return "The name has characters that are not allowed.";
  if (linkW.some(x => x.links.some(l => l !== it && l.name === v.name))) return "There is already a link called “" + v.name + "”. Choose another name.";
  if (!/^https?:\/\/[^\s"'<>]+$/.test(v.href)) return v.href ? "The address must start with http:// or https:// and have no spaces." : "The address cannot be empty.";
  if (!target) return "Choose a group, or give the new group a name.";
  if (!NAME_OK.test(target)) return "The group name has characters that are not allowed.";
  let to = linkW.find(x => x.group === target);
  if (!to) { to = { group: target, was: "", tab: tab || "Links", links: [] }; linkW.push(to); }
  if (it) { Object.assign(it, v); if (to !== g) { g.links.splice(g.links.indexOf(it), 1); to.links.push(it); } }
  else to.links.push(Object.assign({ was: "" }, v));
  return "";
}
async function saveLinks() {
  try { await api("POST", "/api/link", { op: "save", version: S.linksVersion, groups: linkPayload() }); toast("Saved."); await afterChange(true); } catch (e) { fail(e); }
}
// The Save bar of the Edit Links box on the dashboard. It stays in view while the list scrolls.
function drawLinkBar(own) {
  if (!own) return;
  const dirty = linkDirty();
  const back = () => { linkW = null; render(); };
  put(own.firstChild,
    h("div", { class: "state" + (dirty ? " dirty" : ""), title: dirty ? "There are unsaved changes." : "Everything shown is saved." }, dirty ? "Unsaved Changes" : "Saved"),
    h("button", { disabled: !dirty, onclick: back }, "Discard Changes"),
    h("button", { class: "primary", disabled: !dirty, onclick: saveLinks }, "Save"));
}
window.addEventListener("beforeunload", ev => { if (linkDirty()) { ev.preventDefault(); ev.returnValue = ""; } });

async function start() {
  let s;
  try { s = await api("GET", "/api/session"); } catch (e) { root.replaceChildren(h("p", { class: "loading" }, e.message)); return; }
  if (!s.loggedIn) return showLogin(s.passwordSet);
  try { S = await api("GET", "/api/state"); } catch (e) { return; }
  render();
}
start();
