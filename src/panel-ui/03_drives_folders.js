// Move folders between the drives of a pool. The pool shows the folders of all its drives as one, so a folder can live on any of them.
// A folder moved to its own drive stays there for new files too, when "keep new files on their drive" is on.
async function moveFoldersDialog(role) {
  const T = (ROLE_TEXT[role] || role) + " Pool";
  const body = h("div", {});
  const d = h("dialog", { class: "wide fmove" }, h("h2", {}, "Move Folders: " + T), body);
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  const closeBtn = () => h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Close"));
  put(body, [h("p", { class: "muted" }, "Measuring the folders on each drive. This can take a minute on big drives."), closeBtn()]);
  d.showModal();
  let info;
  try { info = await api("GET", "/api/drives/folders?role=" + encodeURIComponent(role)); } catch (e) {
    put(body, [h("p", { class: "dwarn", role: "alert" }, e.message || "The folders could not be read."), closeBtn()]);
    return;
  }
  if (!info.eligible) { put(body, [h("p", {}, info.why || "Folders cannot be moved in this pool."), closeBtn()]); return; }
  const drives = info.drives || [], folders = info.folders || [];
  if (!folders.length) { put(body, [h("p", {}, "There are no folders on these drives yet."), closeBtn()]); return; }
  let target = drives.length ? drives[drives.length - 1].id : "";
  let keep = true;
  const picked = new Set();
  const sizeOn = (f, id) => (f.bytes && typeof f.bytes[id] === "number") ? f.bytes[id] : null;
  const onlyOn = (f, id) => drives.every(x => x.id === id ? sizeOn(f, x.id) !== null : sizeOn(f, x.id) === null);
  const moveBytes = f => drives.reduce((s, x) => s + (x.id !== target && sizeOn(f, x.id) !== null ? sizeOn(f, x.id) : 0), 0);
  const draw = () => {
    const tg = drives.find(x => x.id === target) || drives[0];
    folders.forEach(f => { if (onlyOn(f, target)) picked.delete(f.name); });
    const list = folders.filter(f => picked.has(f.name));
    const need = list.reduce((s, f) => s + moveBytes(f), 0);
    const room = Math.max(0, tg.free_bytes - tg.limit_bytes);
    const tooBig = need > room;
    put(body, [
      info.pinned ? h("div", { class: "dnote", role: "status" }, "New files of moved folders currently stay on the drive that holds their folder. ",
        h("button", { class: "small", onclick: async () => {
          if (!await confirmBox("Turn Off Keeping Files on Their Drive?", "New files then go by the pool's usual fill setting again. Files already on a drive stay where they are.", "Turn Off")) return;
          d.close();
          driveDo("folderpin", { role, on: false });
        } }, "Turn Off")) : null,
      h("p", { class: "muted" }, "Pick the folders to move and the drive they should go to. The pool looks the same afterwards. Every file is copied and checked before the old copy is removed."),
      h("fieldset", { class: "dq" }, h("legend", {}, "Move to"),
        drives.map(x => h("label", { class: "dopt" },
          h("input", Object.assign({ type: "radio", name: "fm-target", value: x.id, onchange: () => { target = x.id; draw(); } }, x.id === target ? { checked: true } : {})),
          h("span", {}, h("b", {}, x.name), h("small", {}, humanBytes(x.used_bytes) + " used, " + humanBytes(x.free_bytes) + " free"))))),
      h("div", { class: "fm-scroll" }, h("table", { class: "fm-table" },
        h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", {}, "Folder"), drives.map(x => h("th", { class: "num" }, x.name)))),
        h("tbody", {}, folders.map(f => {
          const here = onlyOn(f, target);
          return h("tr", { class: here ? "here" : "" },
            h("td", {}, h("input", Object.assign({ type: "checkbox", "aria-label": "Move " + f.name, disabled: here, onchange: ev => { if (ev.target.checked) picked.add(f.name); else picked.delete(f.name); draw(); } }, picked.has(f.name) ? { checked: true } : {}))),
            h("td", {}, f.name, here ? h("small", { class: "muted" }, "  already only on " + tg.name) : null),
            drives.map(x => h("td", { class: "num" }, sizeOn(f, x.id) === null ? "-" : humanBytes(sizeOn(f, x.id)))));
        })))),
      h("label", { class: "dopt" },
        h("input", Object.assign({ type: "checkbox", onchange: ev => { keep = ev.target.checked; draw(); } }, keep ? { checked: true } : {})),
        h("span", {}, h("b", {}, "Keep new files of these folders on their drive"),
          h("small", {}, "On: a new movie put into a folder you moved goes to that folder's drive. Off: new files follow the pool's usual fill setting, so the drives can mix again over time. This setting applies to the whole " + T.toLowerCase() + "."))),
      list.length ? h("p", { class: tooBig ? "dwarn" : "dnote", role: tooBig ? "alert" : "status" },
        tooBig ? humanBytes(need) + " does not fit on " + tg.name + ": it has " + humanBytes(room) + " free above its limit. Choose fewer folders or another drive."
               : "Moving " + list.length + (list.length === 1 ? " folder" : " folders") + " (" + humanBytes(need) + ") to " + tg.name + ". It has " + humanBytes(room) + " free above its limit.") : null,
      h("div", { class: "actions" },
        h("button", { onclick: () => d.close() }, "Cancel"),
        h("button", { class: "primary", disabled: !list.length || tooBig, onclick: async () => {
          if (!await confirmBox("Move " + list.length + (list.length === 1 ? " Folder?" : " Folders?"),
            humanBytes(need) + " is copied to " + tg.name + " and checked, then the old copies are removed. This can take hours for big folders; the page can be closed while it works. Services that use the pool stop for a short time at the end.",
            "Move the Folders")) return;
          d.close();
          startJob("movefolders", { role, id: target, folders: list.map(f => f.hex), keep }, list.length === 1 ? "The folder is on " + tg.name + " now." : "The folders are on " + tg.name + " now.");
        } }, "Move the Folders"))]);
  };
  draw();
}
