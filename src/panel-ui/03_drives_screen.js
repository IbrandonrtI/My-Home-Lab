async function renameDrive(a) {
  const name = await askText("Rename Drive", "New name for " + a.name + " (letters, numbers, spaces and . ( ) + , -)", a.custom ? a.name : "");
  if (name === null) return;
  if (!/^[A-Za-z0-9 .()+,-]{1,40}$/.test(name) || /^[ .-]|[ .-]$/.test(name)) { toast("A name may have up to 40 letters, numbers, spaces and these marks: . ( ) + , -  It cannot start or end with a space, a dot or a dash.", true); return; }
  driveDo("rename", { id: a.id, name }, true);
}
async function autoName(a) {
  if (await confirmBox("Use the Automatic Name?", "The drive goes back to its automatic name (size, make and type) instead of \"" + a.name + "\".", "Use Automatic Name")) driveDo("rename", { id: a.id, name: "auto" }, true);
}
async function remountDrives() {
  const ok = await confirmBox("Fix Drives?",
    "Use this after a drive was disconnected, a power loss or a missing drive. Containers that use the pool stop, every drive and pool is mounted again from the saved setup, and the containers restart. Immich and Nextcloud are then checked for their files. If missing, they stay stopped and you choose the next step. Takes about a minute. Nothing is erased or moved. Refused while a backup or upload is running.",
    "Fix Drives");
  if (ok) driveDo("remount", {}, true);
}

const poolOf = role => ((DR && DR.status && DR.status.pools) || []).find(p => p.role === role) || {};
const devOf = t => "/dev/" + diskOf(t.d.device);
const nDrives = n => n === 0 ? "No Drives" : n + (n === 1 ? " Drive" : " Drives");
const KEEP_OPT = R => ({ value: "keep", label: "Keep the files", hint: "Added as it is. Its files appear in the " + R + " pool." });
const ERASE_OPT = { value: "erase", label: "Erase the drive and format it", hint: "Everything on it is deleted. It is added as a new, empty drive." };
const CANT_KEEP_OPT = { value: "erase", label: "Erase the drive and format it", hint: "HomeLab can keep a drive's files only if it has one Linux (ext4) partition. This one does not (for example exFAT, NTFS or several partitions), so it must be erased and formatted." };

// The dialog that adds spare drives to a pool.
async function addDrives(tiles, role) {
  const R = cap(role), sps = tiles.map(t => t.sp), one = sps.length === 1;
  const modeOf = (s, sp) => one ? s.mode : s["m-" + sp.id];
  const erasing = s => sps.filter(sp => modeOf(s, sp) === "erase");
  const questions = one
    ? [{ id: "mode", label: sps[0].keep_ok ? "What should happen to the files on this drive?" : "This drive has to be erased first", value: sps[0].keep_ok ? "keep" : "erase", options: sps[0].keep_ok ? [KEEP_OPT(R), ERASE_OPT] : [CANT_KEEP_OPT] }]
    : sps.map(sp => ({ id: "m-" + sp.id, label: sp.name + "  ·  " + sp.device, value: sp.keep_ok ? "keep" : "erase", options: sp.keep_ok ? [KEEP_OPT(R), ERASE_OPT] : [CANT_KEEP_OPT] }));
  const running = poolOf(role).mounted;
  const r = await driveDialog({
    title: one ? "Add Drive to " + R + " Pool" : "Add " + sps.length + " Drives to " + R + " Pool",
    lead: sps.map(sp => sp.name + "  ·  " + sp.device + "  ·  " + humanBytes(sp.size_bytes)),
    questions,
    warn: s => {
      const e = erasing(s);
      if (e.length) return "Everything on " + e.map(sp => sp.device).join(", ") + " will be permanently deleted.";
      return "The files on the drive" + (one ? "" : "s") + " stay unchanged and appear in the " + R + " pool. " + (running ? "The pool keeps running." : "Containers that use it stop briefly.");
    },
    typed: s => { const e = erasing(s); return e.length ? e.map(sp => ({ word: sp.device })).concat([{ word: "ERASE" }]) : []; },
    sure: () => "I understand that everything on " + (one ? "this drive" : "the erased drives") + " will be permanently deleted.",
    ok: s => erasing(s).length ? "Erase and Add " + (one ? "Drive" : "Drives") : "Add " + (one ? "Drive" : "Drives"), danger: s => erasing(s).length > 0 });
  if (!r) return;
  const body = one ? { ids: [sps[0].id], role, mode: r.answers.mode, typed: r.typed }
    : { ids: sps.map(sp => sp.id + ":" + r.answers["m-" + sp.id]), role, typed: r.typed };
  startJob("add", body, one ? sps[0].name + " was added to the " + R + " pool." : nDrives(sps.length) + " were added to the " + R + " pool.");
}
async function eraseSpare(sp) {
  const dev = sp.device;
  const r = await driveDialog({
    title: "Erase Spare Drive",
    lead: [sp.name + "  ·  " + dev + "  ·  " + humanBytes(sp.size_bytes), "Only spare drives can be erased here, never a pool drive or the boot drive."],
    questions: [{ id: "mode", label: "What should the drive be afterwards?", value: "format", options: [
      { value: "format", label: "A new, empty drive (formatted)", hint: "Ready to be added to a pool." },
      { value: "empty", label: "Empty, without a file system", hint: "It must be formatted before it can be used." }] }],
    warn: () => "Everything on " + dev + " will be permanently deleted.",
    typed: () => [{ word: dev }, { word: "ERASE" }],
    sure: () => "I understand that everything on this drive will be permanently deleted.",
    ok: () => "Erase Drive", danger: () => true });
  if (r) startJob("wipe", { id: sp.id, mode: r.answers.mode, typed: r.typed }, sp.name + " was erased" + (r.answers.mode === "format" ? " and formatted." : "."));
}
const DRAIN_SPARE = 2147483648;
async function bootAdd(role) {
  const bl = bootLimits(), R = cap(role);
  if (!bl) { toast("The boot drive cannot provide any space right now.", true); return; }
  if (bootIn(role)) { toast("The " + R + " pool already has a Boot Drive Space. Remove it first to create one of a different size.", true); return; }
  const free = (DR.status || {}).boot_free_bytes;
  const r = await driveDialog({
    title: "Use Part of the Boot Drive for the " + R + " Pool",
    lead: ["Free now: " + humanBytes(free) + ". At least " + humanBytes(typeof free === "number" ? free - bl.max_bytes : 0) + " always stays free for the system.",
      "The space is reserved right away, even while empty. The " + role + " pool uses it last, only when its other drives are full."],
    fields: [{ id: "size", label: "Size in " + bl.unit, value: Math.max(bl.lo, Math.min(bl.hi, 100)), min: bl.lo, max: bl.hi, hint: bl.lo + " to " + bl.hi + " " + bl.unit + ". About 2% less is usable (file system overhead)." }],
    questions: [],
    invalid: st => { const n = Number(st.size); return !Number.isInteger(n) || n < bl.lo || n > bl.hi ? "Choose a whole number from " + bl.lo + " to " + bl.hi + " " + bl.unit + "." : null; },
    warn: () => "If the boot drive fails, everything in this space is lost with the system." + (role === "backup" ? " A backup here helps if a Main drive fails, but not if the boot drive fails." : ""),
    typed: () => [{ word: "CONTINUE" }],
    sure: () => "I understand this space is lost if the boot drive fails.",
    ok: () => "Add to " + R + " Pool", danger: () => false });
  if (r) startJob("bootadd", { role, units: Number(r.answers.size), typed: r.typed }, "The Boot Drive Space was added to the " + R + " pool.");
}
function poolFacts(tiles) {
  const rens = tiles.map(t => t.ren), total = rens[0].others + 1, remaining = total - rens.length, role = rens[0].role;
  const copyable = rens.some(a => a.has_data) && remaining > 0;
  const leaving = new Set(tiles.map(t => t.id));
  const stay = tilesNow().filter(t => (t.kind === "pool" || t.kind === "boot") && t.d.role === role && t.ren && t.ren.connected && !leaving.has(t.id));
  const free = stay.reduce((n, t) => n + (t.d.free_bytes || 0), 0), maxFree = stay.reduce((n, t) => Math.max(n, t.d.free_bytes || 0), 0);
  const need = rens.reduce((n, a) => n + (a.used_bytes || 0), 0), maxNeed = rens.reduce((n, a) => Math.max(n, a.used_bytes || 0), 0);
  const noRoom = copyable && (need + DRAIN_SPARE > free || maxNeed + DRAIN_SPARE > maxFree);
  const roomText = "There is not enough free space on the " + role + " drives that stay (" + humanBytes(need) + " to copy, " + humanBytes(free) + " free, and " + humanBytes(DRAIN_SPARE) + " is kept free). A drive whose files do not fit is not removed. Choose fewer drives, or choose not to copy.";
  return { remaining, only: remaining <= 0, copyable, noRoom, roomText };
}
function friendlyService(n) { const w = String(n).split(/[_-]/)[0] || String(n); return w.charAt(0).toUpperCase() + w.slice(1); }
function serviceText(list) {
  const names = [...new Set((list || []).map(friendlyService))];
  if (!names.length) return "No services use the Main pool right now.";
  return "These services use the Main pool and are stopped while the files are copied, then started again: " + names.join(", ") + ". Until the copy is done, they cannot reach their files.";
}
function emptyDriveText(t) { return t.ren.used_bytes > 0 ? "  ·  no files on it (the " + humanBytes(t.ren.used_bytes) + " used is the drive's own format)" : "  ·  holds no files"; }
async function takeOutDrives(tiles) {
  const f = poolFacts(tiles), role = tiles[0].ren.role, R = cap(role), one = tiles.length === 1;
  const names = tiles.map(t => t.d.name).join(", ");
  const held = tiles.reduce((n, t) => n + (t.ren.used_bytes || 0), 0);
  const bootData = tiles.some(t => t.kind === "boot" && t.ren.has_data);
  const r = await driveDialog({
    title: one ? "Take Drive Out of the " + R + " Pool" : "Take " + tiles.length + " Drives Out of the " + R + " Pool",
    lead: [one ? tiles[0].d.name + (tiles[0].ren.has_data ? "  ·  holds " + humanBytes(held) : emptyDriveText(tiles[0])) : names],
    questions: f.copyable && !bootData ? [{ id: "copy", label: (one ? "Its files are" : "Their files are") + " in the " + role + " pool. What should happen to them?", value: "yes", options: [
      { value: "yes", label: "Copy them to another " + role + " drive first (recommended)", hint: "Every file is copied and checked first. Nothing is lost." },
      { value: "no", label: "Do not copy them", hint: "The files stay on the drive only and leave the " + role + " pool." }] }] : [],
    note: () => bootData && !f.only ? "The Boot Drive Space files are copied to the other " + role + " drives first. Removing it returns its space to the boot drive." : null,
    warn: s => bootData && f.only ? "There is no other " + role + " drive to copy the files of the Boot Drive Space to, and removing it deletes it. Every file in it is permanently lost. To keep them, add another " + role + " drive first (or cancel)." : f.only ? "No " + role + " drive stays, so nothing can be copied. The files stay on the " + (one ? "drive" : "drives") + " only (nothing is deleted). " + (role === "main" ? "The Main pool will be empty. The services that use it (such as Immich, Nextcloud and FileBrowser) will keep running and save their files on the boot drive until a Main drive is added again." : "Backups stop until another backup drive is added.") : f.copyable && s.copy === "no" ? "Without copying, the files on " + (one ? "this drive" : "these drives") + " will not show in the " + role + " pool any more. They stay on the drive." : f.noRoom && s.copy === "yes" ? f.roomText : "The drive" + (one ? " is" : "s are") + " taken out of the " + role + " pool. Its data is not changed. Containers that use the pool stop briefly.",
    typed: s => bootData && f.only ? [{ word: "ERASE" }, { word: "REMOVE" }] : f.only ? [{ word: "REMOVE" }] : f.copyable && s.copy === "no" ? [{ word: "CONTINUE" }] : [],
    sure: () => bootData && f.only ? "I understand that the files in the Boot Drive Space will be permanently deleted." : f.only ? (role === "main" ? "I understand that the Main pool will be empty and the services that use it will save their files on the boot drive until a Main drive is added." : "I understand that backups stop until another backup drive is added.") : "I understand that the files on " + (one ? "this drive" : "these drives") + " will no longer show in the " + role + " pool.",
    ok: () => one ? "Take Drive Out" : "Take Drives Out", danger: s => f.only || (f.copyable && s.copy === "no") });
  if (r) startJob("disconnect", { ids: tiles.map(t => t.ren.id), copy: bootData ? "yes" : (r.answers.copy || "no"), typed: r.typed }, one ? tiles[0].d.name + " was taken out of the " + R + " Pool." : nDrives(tiles.length) + " were taken out of the " + R + " Pool.");
}
// The dialog that moves drives from one pool to the other.
async function moveDrives(tiles) {
  const f = poolFacts(tiles), role = tiles[0].ren.role, to = other(role), T = cap(to), R = cap(role), one = tiles.length === 1;
  const keepQ = (id, label, t) => ({ id, label, value: "keep", options: t.kind === "boot" ? [
    { value: "keep", label: "Keep the files in the space", hint: "The space moves as it is, so its files appear in the " + T + " pool." },
    { value: "erase", label: "Start with a new, empty space", hint: "The files in the space are deleted. A new, empty space of the same size joins the " + T + " pool." }] : [
    { value: "keep", label: "Keep the files on the drive", hint: "The drive is added to the " + T + " pool as it is, so its files appear in the " + T + " pool." },
    { value: "erase", label: "Erase the drive and format it", hint: "Everything on the drive is deleted. It joins the " + T + " pool as a new, empty drive." }] });
  const clash = tiles.some(t => t.kind === "boot") && bootIn(to);
  const questions = (one ? [keepQ("keep", "What should happen to the files on this drive?", tiles[0])] : tiles.map(t => keepQ("k-" + t.ren.id, t.d.name, t)))
    .concat([{ id: "copy", label: (one ? "Copy its files" : "Copy their files") + " to the other " + role + " drives first?", value: "yes", show: () => f.copyable, options: [
      { value: "yes", label: "Yes, copy them first (recommended)", hint: "Every file is copied and checked, so the " + role + " pool keeps them." },
      { value: "no", label: "No, do not copy them", hint: "The " + role + " pool loses the files of " + (one ? "this drive" : "these drives") + "." }] }]);
  const keepOf = (s, t) => one ? s.keep : s["k-" + t.ren.id];
  const erasing = s => tiles.filter(t => keepOf(s, t) === "erase");
  const r = await driveDialog({
    title: one ? "Move Drive to the " + T + " Pool" : "Move " + tiles.length + " Drives to the " + T + " Pool",
    lead: [one ? tiles[0].d.name + " moves from the " + R + " pool to the " + T + " pool." + (tiles[0].ren.has_data ? "  It holds " + humanBytes(tiles[0].ren.used_bytes) + "." : tiles[0].ren.used_bytes > 0 ? "  It has no files on it (the " + humanBytes(tiles[0].ren.used_bytes) + " used is the drive's own format)." : "  It holds no files.")
      : tiles.map(t => t.d.name).join(", ") + " move from the " + R + " pool to the " + T + " pool."],
    questions,
    refuse: () => clash ? "The " + T + " pool already has a Boot Drive Space. A pool can have only one." : f.only && role === "main" ? (one ? "This is the only Main drive. Moving it would remove the pool the services use. Add another Main drive first." : "These are all the Main drives. Moving them would remove the pool the services use. Leave at least one Main drive.") : null,
    warn: s => {
      const noCopy = f.copyable && s.copy === "no", e = erasing(s);
      const devs = x => x.map(t => t.kind === "boot" ? "the Boot Drive Space" : devOf(t)).join(", ");
      if (e.length && noCopy) return "The files on " + (one ? "this drive" : "the erased drives") + " will be permanently lost: " + (one ? "the drive is" : "they are") + " erased and the files are not copied anywhere.";
      if (e.length) return "Everything on " + devs(e) + " will be permanently deleted" + (f.copyable ? ", after its files are copied to the other " + role + " drives." : ".");
      if (f.only) return "No " + role + " drive stays, so nothing can be copied. The files stay on the " + (one ? "drive" : "drives") + " and show in the " + T + " pool. The " + R + " pool is empty until another drive is added.";
      if (f.noRoom && s.copy === "yes") return f.roomText;
      if (noCopy) return "The files go with the drive" + (one ? "" : "s") + " to the " + T + " pool. The " + R + " pool loses them.";
      return "The files stay on the drive" + (one ? "" : "s") + " and also show up in the " + T + " pool, while the " + R + " pool keeps its own copy. The two pools then hold some of the same files." + (f.only ? " This is the only Backup drive: backups stop until another backup drive is added." : "");
    },
    typed: s => {
      const t = [];
      erasing(s).forEach(x => { if (x.kind !== "boot") t.push({ word: devOf(x) }); });
      if (erasing(s).length) t.push({ word: "ERASE" });
      if (erasing(s).length < tiles.length) t.push({ word: "KEEP", auto: true });
      if (f.copyable && s.copy === "no") t.push({ word: "CONTINUE" });
      if (f.only) t.push({ word: "REMOVE" });
      return t;
    },
    sure: s => {
      const noCopy = f.copyable && s.copy === "no";
      if (erasing(s).length) return noCopy ? "I understand that everything on the erased drives will be permanently deleted and its files are not copied anywhere." : "I understand that everything on " + (one ? "this drive" : "the erased drives") + " will be permanently deleted.";
      return noCopy ? "I understand that the " + role + " pool will lose the files of " + (one ? "this drive" : "these drives") + "." : "I understand that backups stop until another backup drive is added.";
    },
    ok: s => erasing(s).length ? (one ? "Erase and Move Drive" : "Erase and Move Drives") : (one ? "Move Drive" : "Move Drives"), danger: s => erasing(s).length > 0 || (f.copyable && s.copy === "no") });
  if (!r) return;
  const copy = f.copyable ? r.answers.copy : "no";
  const body = one ? { ids: [tiles[0].ren.id], keep: r.answers.keep, copy, typed: r.typed }
    : { ids: tiles.map(t => t.ren.id + ":" + r.answers["k-" + t.ren.id]), copy, typed: r.typed };
  startJob("move", body, one ? tiles[0].d.name + " was moved to the " + T + " Pool." : nDrives(tiles.length) + " were moved to the " + T + " Pool.");
}

function powerFor(drive, power) {
  const dev = (drive.device || "").replace(/^\/dev\//, "");
  return (power || []).find(p => dev.startsWith(p.id) && /^p?\d*$/.test(dev.slice(p.id.length))) || null;
}
function rowFor(d, rows) {
  rows = rows || [];
  const disk = diskOf(d.device);
  return rows.find(r => r.name === d.name && diskOf(r.device) === disk) || rows.find(r => disk && diskOf(r.device) === disk) || rows.find(r => r.name === d.name) || null;
}
function runLook(kind) {
  return async () => {
    DRwait = kind === "health" ? "Reading the health of the drives..." : "Checking the drives...";
    drawDrives();
    try { const r = await api("GET", "/api/drives/" + kind); if (kind === "health") DRhealth = r; else DRcheck = r; } catch (e) { fail(e); }
    DRwait = "";
    drawDrives();
  };
}
function healthBlock(d) {
  const r = rowFor(d, DRhealth && DRhealth.drives);
  if (!DRhealth) return null;
  if (!r) return h("p", { class: "muted small" }, "Health: this drive did not report anything (a Boot Drive Space has no health reading of its own).");
  const bits = [typeof r.temperature_c === "number" ? r.temperature_c + " °C" : "", typeof r.power_on_hours === "number" ? r.power_on_hours.toLocaleString() + " hours on" : "",
    typeof r.reallocated_sectors === "number" ? r.reallocated_sectors + " moved sectors" : "", typeof r.pending_sectors === "number" ? r.pending_sectors + " waiting sectors" : ""].filter(Boolean);
  const bad = r.health === "FAILED" || r.pending_sectors > 0;
  return h("div", { class: "result" },
    h("div", { class: "row tight" }, h("b", {}, "Health"), h("span", { class: "pill " + (r.health === "PASSED" ? "ok" : bad ? "bad" : "dim") }, r.health === "PASSED" ? "Passed" : r.health === "FAILED" ? "Failing" : r.health === "asleep" ? "Asleep" : r.health === "unsupported" ? "Not Reported" : stateText(r.health))),
    bits.length ? h("p", { class: "muted small" }, bits.join("  ·  ")) : null,
    r.note ? h("p", { class: bad ? "badtext" : "muted small" }, cap(r.note)) : null,
    bad ? h("p", { class: "badtext" }, "Copy its files to another drive soon.") : null);
}
function checkBlock(d, spare) {
  const r = rowFor(d, DRcheck && DRcheck.drives);
  if (!DRcheck) return null;
  if (!r) return h("p", { class: "muted small" }, spare ? "Quick Check: nothing to check yet. It checks the drives in the Main and Backup pools, and this drive is not in a pool. Add it to a pool and check again." : "Quick Check: this drive has no result.");
  return h("div", { class: "result" },
    h("div", { class: "row tight" }, h("b", {}, "Quick Check"), h("span", { class: "pill " + (r.result === "ok" ? "ok" : r.result === "warn" ? "warn" : "bad") }, r.result === "ok" ? "OK" : r.result === "warn" ? "Warning" : "Problem")),
    (r.findings || []).length ? r.findings.map(f => h("p", { class: f.level === "problem" ? "badtext" : "muted small" }, cap(f.text))) : h("p", { class: "muted small" }, "The file system is clean, no errors are recorded and the drive reports no problem."));
}
function hddIcon() {
  const ns = "http://www.w3.org/2000/svg";
  const mk = (tag, at) => { const e = document.createElementNS(ns, tag); for (const k in at) e.setAttribute(k, at[k]); return e; };
  const svg = mk("svg", { viewBox: "0 0 64 48", width: 64, height: 48, class: "hdd", "aria-hidden": "true" });
  svg.append(mk("rect", { x: 3, y: 4, width: 58, height: 40, rx: 7, class: "hdd-body" }), mk("circle", { cx: 26, cy: 24, r: 12, class: "hdd-disc" }), mk("circle", { cx: 26, cy: 24, r: 3.5, class: "hdd-hub" }),
    mk("path", { d: "M26 24 L45 11", class: "hdd-arm" }), mk("circle", { cx: 54, cy: 37, r: 2.2, class: "hdd-led" }));
  return svg;
}
function ring(used, size) {
  const pct = typeof used === "number" && typeof size === "number" && size > 0 ? Math.max(0, Math.min(100, Math.round(used * 100 / size))) : null;
  const R = 26, C = 2 * Math.PI * R, ns = "http://www.w3.org/2000/svg";
  const mk = (tag, at) => { const e = document.createElementNS(ns, tag); for (const k in at) e.setAttribute(k, at[k]); return e; };
  const svg = mk("svg", { viewBox: "0 0 64 64", width: 56, height: 56, class: "ring" + (pct !== null && pct >= 95 ? " full" : pct !== null && pct >= 85 ? " high" : ""), role: "img", "aria-label": pct === null ? "Usage not known" : pct + " percent used" });
  svg.append(mk("circle", { cx: 32, cy: 32, r: R, class: "ring-bg" }));
  if (pct !== null) svg.append(mk("circle", { cx: 32, cy: 32, r: R, class: "ring-fg", "stroke-dasharray": (C * pct / 100).toFixed(1) + " " + C.toFixed(1), transform: "rotate(-90 32 32)" }));
  const t = mk("text", { x: 32, y: 36, "text-anchor": "middle", class: "ring-t" });
  t.textContent = pct === null ? "-" : pct + "%";
  svg.append(t);
  return svg;
}
function tempCell(r, pw) {
  if (!DRhealth) return h("span", { class: "muted" }, "...");
  if (pw && pw.state === "asleep") return h("span", { class: "muted", title: "The drive is asleep, so its temperature is not read." }, "Asleep");
  if (!r || typeof r.temperature_c !== "number") return h("span", { class: "muted", title: r && r.health === "unsupported" ? "This drive does not report a temperature." : null }, "-");
  return h("span", { class: r.temperature_c >= 60 ? "badtext" : r.temperature_c >= 50 ? "warntext" : "" }, r.temperature_c + " °C");
}
function healthCell(r) {
  if (!DRhealth) return h("span", { class: "muted" }, "...");
  if (!r) return h("span", { class: "muted", title: "This drive did not report anything." }, "-");
  const bad = r.health === "FAILED" || r.pending_sectors > 0;
  return h("span", { class: "pill " + (r.health === "PASSED" && !bad ? "ok" : bad ? "bad" : "dim"), title: r.health === "unsupported" ? (cap(r.note) || "This drive does not report its health.") : null },
    bad && r.health !== "FAILED" ? "Warning" : r.health === "PASSED" ? "Passed" : r.health === "FAILED" ? "Failing" : r.health === "asleep" ? "Asleep" : r.health === "unsupported" ? "Not Reported" : stateText(r.health));
}

let DRsel = new Set(), DRselMode = false, DRdrag = null, DRdrawLater = false, DRcard = null, DRlast = null;
function tilesNow() {
  if (!DR) return [];
  const st = DR.status || {}, act = DR.actions || {};
  const lend = bootTile();
  const list = (st.drives || []).filter(d => !(lend.length && /^boot\/system drive/.test(d.state || ""))).map(d0 => {
    const ren = (act.rename || []).find(a => d0.mount && d0.mount.split("/").pop() === a.id) || null;
    const d = ren && ren.boot_section ? Object.assign({}, d0, { name: bootSectionName(d0) }) : d0;
    const sp = ren ? null : (act.spare || []).find(a => diskOf(d.device) === a.id) || null;
    const kind = ren ? (ren.boot_section ? "boot" : "pool") : sp ? "spare" : "other";
    const group = kind === "spare" ? "spare" : (kind === "pool" || kind === "boot") && ren.connected ? ren.role : "";
    return { d, ren, sp, kind, group, id: ren ? ren.id : sp ? sp.id : (d.device && d.device !== "-" ? d.device : d.name) };
  });
  const arr = arrayTile(st, list);
  return list.concat(arr ? [arr] : [], lend);
}
const isMember = t => t.kind === "other" && t.d.role === "array";
function arrayTile(st, list) {
  if (!st.array) return null;
  const p = (st.pools || []).find(x => x.role === "main") || {}, members = list.filter(isMember);
  const ok = /^(online|clean|active|optimal)/i.test(st.array.health || "");
  return { d: { name: st.array.title, device: "-", role: "main", state: ok ? "connected" : (st.array.health || "unknown"), size_bytes: p.size_bytes, used_bytes: p.used_bytes, free_bytes: p.free_bytes, mount: p.path },
    ren: null, sp: null, kind: "array", group: "", id: "ARRAY", members, array: st.array };
}
function bootLimits() {
  const bl = ((DR && DR.status) || {}).boot_limits;
  if (!bl || bl.small || typeof bl.max_bytes !== "number" || bl.max_bytes < bl.min_bytes || (bl.main && bl.backup)) return null;
  return Object.assign({ lo: Math.ceil(bl.min_bytes / bl.unit_bytes), hi: Math.floor(bl.max_bytes / bl.unit_bytes) }, bl);
}
const bootIn = role => ((DR && DR.actions && DR.actions.rename) || []).some(a => a.boot_section && a.role === role);
function bootTile() {
  const bl = bootLimits();
  if (!bl || bl.hi < bl.lo) return [];
  return [{ d: { name: "Boot Drive", device: "-", role: "bootfree", state: "connected", size_bytes: bl.max_bytes, used_bytes: null, free_bytes: null, mount: "" }, ren: null, sp: null, kind: "bootfree", group: "bootfree", id: "BOOTFREE" }];
}
const tileById = id => tilesNow().find(t => t.id === id) || null;
function selTiles() { return tilesNow().filter(t => DRsel.has(t.id)); }
function toggleSel(t) {
  if (!t.group || DRbusy || t.kind === "bootfree") return;
  if (DRsel.has(t.id)) DRsel.delete(t.id);
  else {
    const have = selTiles()[0];
    if (have && have.group !== t.group) { toast("Select drives from one place: the Drives box, or one pool.", true); return; }
    DRsel.add(t.id);
  }
  drawDrives();
}
function dotBad(t) { return stateClass(t.d.state) === "bad"; }
function tile(t) {
  const d = t.d, pw = powerFor(d, (DR.actions || {}).power), hr = rowFor(d, DRhealth && DRhealth.drives);
  const bad = hr && (hr.health === "FAILED" || hr.pending_sectors > 0);
  const prog = DRjob && DRjob.running && (DRjob.items || []).includes(t.id) ? ((DRjob.progress || {})[t.id] || { pct: 0, text: "Waiting" }) : null;
  const dim = DRbusy && !prog;
  const sel = DRsel.has(t.id);
  const used = t.kind === "array" ? (typeof d.used_bytes === "number" ? humanBytes(d.used_bytes) + " of " + humanBytes(d.size_bytes) + " used  ·  " : "") + nDrives(t.members.length).toLowerCase() : t.kind === "bootfree" ? "up to " + humanBytes(d.size_bytes) + " to lend" : typeof d.used_bytes === "number" ? humanBytes(d.used_bytes) + " of " + humanBytes(d.size_bytes) + " used" : typeof d.size_bytes === "number" ? humanBytes(d.size_bytes) + " drive" : "";
  const draggable = !!t.group && !DRbusy;
  const el = h("div", {
    class: "tile" + (sel ? " sel" : "") + (t.group ? "" : " locked") + (dim ? " dim" : "") + (prog ? " working" : "") + (pw && pw.state === "asleep" ? " asleep" : ""),
    role: "button", tabindex: 0, draggable: draggable ? "true" : "false", "data-id": t.id, "data-group": t.group,
    "aria-label": d.name + ", " + stateText(d.state) + (used ? ", " + used : "") + (sel ? ", selected" : ""),
    title: d.name + (d.device && d.device !== "-" ? "  ·  " + d.device : ""),
    onclick: ev => { if (ev.ctrlKey || ev.metaKey || ev.shiftKey || DRselMode) { ev.preventDefault(); toggleSel(t); } else openCard(t.id); },
    onkeydown: ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); if (ev.ctrlKey || ev.metaKey || ev.shiftKey || DRselMode) toggleSel(t); else openCard(t.id); } },
    ondragstart: ev => dragStart(ev, t),
    ondragend: dragEnd },
    h("div", { class: "tname" }, d.name),
    h("div", { class: "ticon" }, hddIcon(),
      h("span", { class: "dot " + (dotBad(t) ? "bad" : "ok"), title: dotBad(t) ? stateText(d.state) : "Connected", role: "img", "aria-label": dotBad(t) ? stateText(d.state) : "Connected" }),
      bad ? h("span", { class: "warnmark", title: "The drive reports a problem. Press it for the health details." }, "!") : null,
      (t.kind === "other" || (t.kind === "boot" && !t.group)) ? h("span", { class: "lock", title: t.kind === "boot" ? "This Boot Drive Space is not connected." : "This drive is managed outside the pools.", "aria-hidden": "true" }, "🔒") : null),
    prog ? h("div", { class: "tprog", role: "progressbar", "aria-valuenow": prog.pct, "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": d.name + ": " + prog.text },
        h("div", { class: "bar" }, h("i", { style: { width: Math.max(4, prog.pct) + "%" } })), h("small", {}, prog.text + (/%$/.test(prog.text) ? "" : "  " + prog.pct + "%")))
      : [usageBar(d.used_bytes, d.size_bytes) || h("div", { class: "usebar ghost" }), h("div", { class: "tused" }, used || "Size unknown")]);
  return el;
}
function dragStart(ev, t) {
  if (DRbusy || !t.group) { ev.preventDefault(); return; }
  const sel = selTiles(), ids = DRsel.has(t.id) ? sel.map(x => x.id) : [t.id];
  if (DRsel.has(t.id) && sel.some(x => x.group !== t.group)) { ev.preventDefault(); toast("Select drives from one place: the Drives box, or one pool.", true); return; }
  DRdrag = { ids, group: t.group };
  try { ev.dataTransfer.setData("text/plain", ids.join(",")); ev.dataTransfer.effectAllowed = "move"; } catch (e) {  }
  if (drivesBox) drivesBox.dataset.drag = t.group;
  document.querySelectorAll(".tile").forEach(x => { if (ids.includes(x.dataset.id)) x.classList.add("dragging"); });
}
function dragEnd() {
  DRdrag = null;
  if (drivesBox) delete drivesBox.dataset.drag;
  document.querySelectorAll(".dzone.over").forEach(z => z.classList.remove("over"));
  document.querySelectorAll(".tile.dragging").forEach(z => z.classList.remove("dragging"));
  if (DRdrawLater) { DRdrawLater = false; drawDrives(); }
}
function zone(kind, accepts, kids, extra) {
  const ok = () => DRdrag && accepts.includes(DRdrag.group) && !(DRdrag.group === kind);
  return h("div", Object.assign({
    class: "dzone zone-" + kind, "data-zone": kind, "data-accepts": accepts.join(" "),
    ondragover: ev => { if (ok()) { ev.preventDefault(); ev.currentTarget.classList.add("over"); } },
    ondragleave: ev => { if (!ev.currentTarget.contains(ev.relatedTarget)) ev.currentTarget.classList.remove("over"); },
    ondrop: ev => { ev.preventDefault(); ev.currentTarget.classList.remove("over"); dropOn(kind); } }, extra || {}), kids);
}
function dropOn(kind) {
  const drag = DRdrag;
  dragEnd();
  if (!drag || DRbusy) return;
  const tiles = drag.ids.map(tileById).filter(Boolean);
  if (!tiles.length) return;
  if (drag.group === "bootfree" && (kind === "main" || kind === "backup")) bootAdd(kind);
  else if (drag.group === "spare" && (kind === "main" || kind === "backup")) addDrives(tiles, kind);
  else if ((drag.group === "main" || drag.group === "backup") && kind === other(drag.group)) moveDrives(tiles);
  else if ((drag.group === "main" || drag.group === "backup") && kind === "drives") takeOutDrives(tiles);
}
function selBar() {
  const sel = selTiles();
  if (!sel.length) return null;
  const g = sel[0].group, n = sel.length;
  const go = f => () => f(selTiles());
  return h("div", { class: "selbar", role: "region", "aria-label": "Selected drives" },
    h("b", {}, nDrives(n) + " selected"),
    g === "spare" ? [h("button", { class: "small", disabled: !!DRbusy, onclick: go(t => addDrives(t, "main")) }, "Add to Main"), h("button", { class: "small", disabled: !!DRbusy, onclick: go(t => addDrives(t, "backup")) }, "Add to Backup")] :
      [h("button", { class: "small", disabled: !!DRbusy, onclick: go(t => moveDrives(t)) }, "Move to " + cap(other(g))), h("button", { class: "small danger", disabled: !!DRbusy, onclick: go(t => takeOutDrives(t)) }, "Take Out")],
    h("button", { class: "small", onclick: () => { DRsel = new Set(); drawDrives(); } }, "Clear"));
}
function poolBox(p, tiles) {
  const T = (ROLE_TEXT[p.role] || p.role) + " Pool";
  return zone(p.role, ["spare", other(p.role)].concat(bootIn(p.role) ? [] : ["bootfree"]), [
    h("div", { class: "ph" },
      h("div", { class: "pt" }, h("h2", {}, T), h("span", { class: "sub" }, p.path + (p.mounted ? "  ·  " + (p.filesystem || "") : ""))),
      p.mounted ? [ring(p.used_bytes, p.size_bytes), h("div", { class: "pu" }, h("b", {}, humanBytes(p.used_bytes) + " used"), h("span", { class: "sub" }, humanBytes(p.free_bytes) + " free of " + humanBytes(p.size_bytes)))] : h("div", { class: "pu" }, h("span", { class: "sub" }, "Not mounted")),
      h("span", { class: "pill " + (p.mounted ? "ok" : "bad") }, p.mounted ? "Online" : "Offline")),
    h("div", { class: "tiles" }, tiles.length ? tiles.map(tile) : h("p", { class: "dropnote" }, "Drag a drive here to add it to the " + (ROLE_TEXT[p.role] || p.role) + " pool."))], { class: "dzone card pool zone-" + p.role });
}
function cardStat(label, ...kids) { return h("div", { class: "st" }, h("small", {}, label), h("div", {}, kids)); }
function bootCardBody(t) {
  const bl = bootLimits(), dis = !!DRbusy || !!DRwait, go = f => () => { closeCard(); f(); };
  const btn = (role, label) => h("button", { class: "small", disabled: dis || bootIn(role), title: bootIn(role) ? "The " + cap(role) + " pool already has a Boot Drive Space" : "", onclick: go(() => bootAdd(role)) }, label);
  return [
    h("p", { class: "muted" }, "The drive the system runs from. Part of its free space can be used as a drive of Main or Backup (a Boot Drive Space)."),
    h("div", { class: "stats" },
      cardStat("Free Space", typeof ((DR.status || {}).boot_free_bytes) === "number" ? humanBytes(DR.status.boot_free_bytes) : "-"),
      cardStat("Can Lend", bl ? bl.lo + " to " + bl.hi + " " + bl.unit : "-"),
      cardStat("Always Kept Free", bl ? humanBytes(bl.max_bytes > 0 ? DR.status.boot_free_bytes - bl.max_bytes : 0) : "-")),
    h("div", { class: "row tight cardactions" }, btn("main", "Add to Main"), btn("backup", "Add to Backup")),
    h("p", { class: "muted small" }, "This tile can also be dragged into Main or Backup. A Boot Drive Space is the last drive its pool uses. It can be moved to the other pool or removed at any time.")];
}
function arrayCardBody(t) {
  const d = t.d, a = t.array || {};
  return [
    h("p", { class: "muted" }, "A RAID or ZFS setup: its drives work together as one pool, so the drives cannot be moved or erased individually here."),
    h("div", { class: "stats" },
      cardStat("Health", h("span", { class: "pill " + (t.d.state === "connected" ? "ok" : "bad") }, cap(String(a.health || "unknown").toLowerCase()))),
      cardStat("Size", typeof d.size_bytes === "number" ? humanBytes(d.size_bytes) : "-"),
      cardStat("Used", typeof d.used_bytes === "number" ? humanBytes(d.used_bytes) + " (" + humanBytes(d.free_bytes) + " free)" : "-"),
      cardStat("Pool", "Main Pool")),
    typeof d.used_bytes === "number" ? usageBar(d.used_bytes, d.size_bytes) : null,
    h("div", { class: "stats" }, t.members.map(m => cardStat(m.d.name, humanBytes(m.d.size_bytes), h("span", { class: "devpath" }, m.d.device || "")))),
    h("p", { class: "muted small" }, "To remove this setup, run \"sudo drives release\" on the server. It asks for confirmation because it erases the drives of the setup.")];
}
function cardBody(t) {
  if (t.kind === "array") return arrayCardBody(t);
  if (t.kind === "bootfree") return bootCardBody(t);
  const d = t.d, act = DR.actions || {}, pw = powerFor(d, act.power), hr = rowFor(d, DRhealth && DRhealth.drives);
  const dis = !!DRbusy, ren = t.ren, sp = t.sp, wait = !!DRwait;
  const dev = devOf(t);
  const ident = hr ? [hr.model, hr.serial ? "Serial " + hr.serial : "", hr.filesystem ? hr.filesystem + (hr.label ? ' "' + hr.label + '"' : "") : ""].filter(Boolean).join("  ·  ") : "";
  const used = typeof d.used_bytes === "number" ? d : hr && typeof hr.used_bytes === "number" ? { used_bytes: hr.used_bytes, free_bytes: hr.free_bytes, size_bytes: d.size_bytes } : null;
  const poolName = t.kind === "spare" ? "Not in a pool" : t.kind === "other" ? "Outside the pools" : cap(ren.role) + " Pool";
  const go = f => () => { closeCard(); f(); };
  const btn = (label, f, opt) => h("button", { class: (opt && opt.danger ? "danger " : "") + "small", disabled: dis || wait || (opt && opt.off), onclick: f }, label);
  const connected = (d.state || "").startsWith("connected") || t.kind === "spare";
  const actions = [
    ren && btn("Rename", go(() => renameDrive(ren))),
    ren && ren.custom && btn("Automatic Name", go(() => autoName(ren))),
    pw && pw.state !== "asleep" && btn("Put to Sleep", go(() => driveDo("sleep", { id: pw.id }))),
    pw && pw.state === "asleep" && btn("Wake Up", go(() => driveDo("wake", { id: pw.id }))),
    (t.kind === "pool" || t.kind === "boot") && ren.connected && btn("Move to " + cap(other(ren.role)), go(() => moveDrives([t]))),
    (t.kind === "pool" || t.kind === "boot") && ren.connected && btn("Take Out", go(() => takeOutDrives([t])), { danger: true }),
    sp && btn("Add to Main", go(() => addDrives([t], "main"))),
    sp && btn("Add to Backup", go(() => addDrives([t], "backup"))),
    sp && btn("Erase", go(() => eraseSpare(sp)), { danger: true })].filter(Boolean);
  return [
    h("p", { class: "muted" }, [d.device && d.device !== "-" ? d.device : "", ident].filter(Boolean).join("  ·  ")),
    h("div", { class: "stats" },
      cardStat("Status", h("span", { class: "pill " + stateClass(d.state), title: STATE_HINT[d.state] || null }, stateText(d.state))),
      cardStat("Power", pw ? h("span", { class: "pill " + (pw.state === "asleep" ? "dim" : "") }, pw.state === "asleep" ? "Asleep" : pw.state === "awake" ? "Awake" : "Unknown")
        : hr && hr.removable ? h("span", { class: "pill", title: "A USB stick or memory card has no motor, so it never sleeps." }, "Always On") : h("span", { class: "muted" }, "-")),
      cardStat("Temp", tempCell(hr, pw)),
      cardStat("Health", healthCell(hr)),
      cardStat("Hours On", hr && typeof hr.power_on_hours === "number" ? hr.power_on_hours.toLocaleString() : h("span", { class: "muted" }, DRhealth ? "-" : "...")),
      cardStat("Size", typeof d.size_bytes === "number" ? humanBytes(d.size_bytes) : "-"),
      cardStat("Used", used ? humanBytes(used.used_bytes) + " (" + humanBytes(used.free_bytes) + " free)" : t.kind === "spare" && !DRhealth ? "..." : "-"),
      cardStat("Pool", poolName)),
    used ? usageBar(used.used_bytes, used.size_bytes || (used.used_bytes + used.free_bytes)) : null,
    connected ? h("div", { class: "row tight" },
      btn(DRhealth ? "Check Health Again" : "Check Health", runLook("health")),
      btn(DRcheck ? "Run Quick Check Again" : "Run Quick Check", runLook("check"))) : h("p", { class: "muted small" }, "This drive is not connected. Connect it and press Fix Drives."),
    wait ? h("p", { class: "muted small", role: "status" }, DRwait) : null,
    healthBlock(d), checkBlock(d, !!sp),
    actions.length ? h("div", { class: "row tight cardactions" }, actions) : null,
    h("p", { class: "muted small" }, "Health shows what the drive reports about itself (SMART). A sleeping drive is not woken up. The quick check looks for file system errors and changes nothing." + (dev !== "/dev/" ? "" : ""))];
}
function openCard(id) {
  closeCard();
  const t = tileById(id);
  if (!t) return;
  const body = h("div", {});
  const d = h("dialog", { class: "wide dcard" }, h("h2", {}, t.d.name), body, h("div", { class: "actions" }, h("button", { class: "primary", onclick: () => closeCard() }, "Close")));
  d.addEventListener("close", () => { d.remove(); if (DRcard && DRcard.dlg === d) DRcard = null; });
  DRcard = { id, dlg: d, body, title: d.querySelector("h2") };
  document.body.append(d);
  refreshCard();
  d.showModal();
}
function refreshCard() {
  if (!DRcard) return;
  const t = tileById(DRcard.id);
  if (!t) { closeCard(); return; }
  DRcard.title.textContent = t.d.name;
  put(DRcard.body, cardBody(t));
}
function closeCard() { if (DRcard) { const d = DRcard.dlg; DRcard = null; try { d.close(); } catch (e) {  } d.remove(); } }
async function abortJob() {
  const act = DRbusy;
  if (!/^(add|disconnect|move|setup|appsfix)$/.test(act) || (DRjob && DRjob.stopping)) return;
  if (act === "appsfix") {
    if (!await confirmBox("Cancel the Copy?", "The copy stops now and the files already copied from the backup are removed. Files that were in Main before are not changed. Immich and Nextcloud stay stopped, and the restore can be started again later.", "Cancel the Copy", true)) return;
    try { const r = await api("POST", "/api/drives/abort", {}); if (DRjob) DRjob.stopping = true; toast(r.message || "Stopping."); } catch (e) { fail(e); }
    drawDrives();
    return;
  }
  const text = act === "add"
    ? "Drives that are not yet added are not added. A drive that is already added stays added. A drive that is being erased finishes that step first."
    : act === "setup"
    ? "The copy stops immediately. The Main pool stays exactly as it is, with all of its files. The new setup is removed again and its drives are left empty."
    : "A drive that is still copying stops immediately and stays where it is, with its files. A drive that is already done is returned to the pool it came from. A drive that is being erased finishes that step first. Files already copied to other drives stay there as extra copies.";
  if (!await confirmBox("Abort This Change?", text, "Abort", true)) return;
  try {
    const r = await api("POST", "/api/drives/abort", {});
    if (DRjob) DRjob.stopping = true;
    toast(r.message || "Stopping.");
  } catch (e) { fail(e); }
  drawDrives();
}
let DRlogOpen = false;
function stepsBox(lines) {
  const pre = h("pre", { class: "joblog" }, lines.join("\n"));
  const box = h("details", { class: "joblogbox", open: DRlogOpen }, h("summary", {}, "Show the steps"), pre);
  box.addEventListener("toggle", () => { DRlogOpen = box.open; });
  const keep = DRlogOpen && drivesBox && drivesBox.querySelector("details.joblogbox pre.joblog");
  if (keep) { const atEnd = keep.scrollTop + keep.clientHeight >= keep.scrollHeight - 4; setTimeout(() => { pre.scrollTop = atEnd ? pre.scrollHeight : keep.scrollTop; }, 0); }
  return box;
}
// Build the parts of the Drives tab from the state the server sent.
function drivesParts() {
  const out = [];
  if (DRwait || DRbusy) {
    const lines = DRjob && DRjob.lines ? DRjob.lines.filter(l => !/\(typed in the panel\)|^Type /.test(l)).slice(-60) : [];
    const copying = !!DRjob && Object.values(DRjob.progress || {}).some(p => /^Copying files/.test(p.text || ""));
    const stopping = !!(DRjob && DRjob.stopping), canStop = !!DRbusy && (/^(add|disconnect|move)$/.test(DRbusy) || ((DRbusy === "setup" || DRbusy === "appsfix") && copying));
    const rp = (DRbusy === "appsfix" || DRbusy === "moveboot") && DRjob && DRjob.progress ? DRjob.progress[DRbusy] : null;
    out.push(h("div", { class: "card working", role: "status" }, DRbusy ? (stopping ? "Stopping at the next safe moment..." : (JOB_TEXT[DRbusy] || "Working...")) : DRwait,
      canStop ? h("div", { class: "row tight" }, h("button", { class: "danger small", disabled: stopping, onclick: abortJob, title: "Stops what is not finished and returns the drives that are done to their previous pool" }, stopping ? "Stopping..." : (DRbusy === "appsfix" ? "Cancel" : "Abort")),
        stopping ? h("span", { class: "muted small" }, DRbusy === "appsfix" ? "The copy has been told to stop. The files copied so far are being removed. This can take a minute or two." : DRbusy === "setup" ? "The copy has been told to stop. The drives must finish writing what they already received, and then the new setup is removed and the services start again. This can take a few minutes, longer if more was already copied. The Main pool is not changed." : "A copy stops immediately; a step that has started finishes first. Drives that are already done are returned to their previous pool. This can take a few minutes.") : null) : null,
      rp ? h("div", { class: "tprog big", role: "progressbar", "aria-valuenow": rp.pct, "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": rp.text },
        h("div", { class: "bar" }, h("i", { style: { width: Math.max(2, rp.pct) + "%" } })), h("small", {}, rp.text + "  (" + rp.pct + "%)")) : null,
      DRbusy === "appsfix" && !stopping ? h("p", { class: "muted small" }, copying ? "Cancel stops the copy and removes the files copied so far, so Main has none of this restore's data. The page can be left; the work continues." : "The page can be left; the work continues. The Cancel button appears while the files are being copied.") : null,
      DRbusy && /^(add|wipe|disconnect|move)$/.test(DRbusy) ? h("p", { class: "muted small" }, "Copying files can take a long time. The page can be left open or closed; the work continues.") : null,
      DRbusy === "setup" && !stopping ? h("p", { class: "muted small" }, copying ? "The process can be stopped while the files are copied, and the Main pool then stays as it is. The page can be left; the work continues." : "A new setup can be stopped only while its files are copied (the Abort button appears then). The page can be left; the work continues.") : null,
      lines.length ? stepsBox(lines) : null));
  }
  if (DRfail && !DRbusy) out.push(h("div", { class: "card failcard", role: "alert" }, h("h2", {}, "What Happened"),
    h("p", {}, h("b", {}, DRfail.what + " did not work. "), DRfail.message),
    h("p", { class: "muted small" }, "Nothing else was changed unless the message above says so. " + DRfail.time.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })),
    DRfail.lines.length ? stepsBox(DRfail.lines) : null,
    h("div", { class: "row tight" }, h("button", { class: "small", onclick: () => { DRfail = null; drawDrives(); } }, "Dismiss"))));
  if (DRerr) out.push(h("div", { class: "card", role: "alert" }, h("h2", {}, "The Drives Could Not Be Read"), h("p", { class: "muted" }, DRerr), h("button", { onclick: loadDrives }, "Try Again")));
  if (!DR) return out;
  const st = DR.status || {}, drives = st.drives || [];
  const off = !!DRbusy || !!DRwait;
  const tiles = tilesNow();
  out.push(h("div", { class: "dbar" },
    h("div", { class: "info" },
      st.last_backup ? h("span", {}, "Last backup: " + st.last_backup) : null,
      typeof st.boot_free_bytes === "number" ? h("span", {}, "Free space on the boot drive: " + humanBytes(st.boot_free_bytes)) : null),
    h("button", { class: "small" + (DRselMode ? " on" : ""), "aria-pressed": DRselMode ? "true" : "false", disabled: !!DRbusy, onclick: () => { DRselMode = !DRselMode; if (!DRselMode) DRsel = new Set(); drawDrives(); }, title: "Press drives to select several, then use the buttons that appear" }, DRselMode ? "Done Selecting" : "Select"),
    h("button", { class: "small", disabled: off, onclick: () => { DRhealth = null; loadDrives(); } }, "Refresh"),
    h("button", { class: "small", disabled: !!DRbusy, onclick: remountDrives, title: "Mounts every drive and pool again from the saved setup and checks that Immich and Nextcloud find their files (after a disconnection, a power loss or a missing drive)" }, "Fix Drives")));
  if ((st.main_empty || st.main_on_boot) && !DRbusy) {
    out.push(h("div", { class: "card warncard", role: "alert" }, h("h2", {}, st.main_on_boot ? "A Main Drive Is Missing" : "Main Has No Drive"),
      h("p", {}, st.main_on_boot
        ? "The Main drive was not found, so the services (for example Immich and Nextcloud) are running from the boot drive. Files on the missing drive are not available until it is back."
        : "Nothing is connected to the Main pool, so the services (for example Immich and Nextcloud) are using the boot drive as storage."),
      h("p", { class: "muted small" }, st.main_on_boot
        ? "Connect the drive and press Fix Drives. Files saved on the boot drive in the meantime can then be copied to the drive."
        : "To use a drive instead, drag it into Main, or press Configure Drives and build a setup. Files already saved on the boot drive are copied to the drive first.")));
  }
  if (st.boot_files_waiting && !DRbusy) {
    out.push(h("div", { class: "card warncard", role: "status" }, h("h2", {}, "Files Are Waiting On The Boot Drive"),
      h("p", {}, "Some files were saved on the boot drive while Main had no drive. They are hidden while the Main pool is mounted."),
      h("p", { class: "muted small" }, "This copies them to the Main pool, checks every file, and only then removes the old copies from the boot drive. Photos, videos and documents are not involved: only the small files that kept the services running. The services stop briefly and start again."),
      h("div", { class: "row tight" }, h("button", { class: "primary", onclick: moveBootFiles }, "Move the Files to the Drive"))));
  }
  const ac = appsCard();
  if (ac && !DRbusy) out.push(ac);
  out.push(selBar());
  const inPool = t => t.kind === "pool" || t.kind === "boot" || t.kind === "array" || (t.kind === "other" && (t.d.role === "main" || t.d.role === "backup"));
  const top = tiles.filter(t => !inPool(t) && !isMember(t));
  out.push(zone("drives", ["main", "backup"], [
    h("div", { class: "ph" }, h("div", { class: "pt" }, h("h2", {}, "Drives"), h("span", { class: "sub" }, "Connected but not in a pool. Drag a drive into Main or Backup, or select it for its details and buttons (a phone uses the buttons). Hold Ctrl or Shift while selecting, or use Select, to choose several.")),
      h("span", { class: "pill dim" }, nDrives(top.filter(t => t.kind !== "bootfree").length)),
      h("button", { class: "small" + (DRcfg ? " on" : ""), "aria-expanded": DRcfg ? "true" : "false", disabled: off, onclick: openConfig, title: "Scans the spare drives and suggests a setup for them (ZFS, RAID, SnapRAID, a pool)" }, "Configure Drives")),
    cfgBox(),
    h("div", { class: "tiles" }, top.length ? top.map(tile) : h("p", { class: "dropnote" }, "No spare drives. Connect a drive and press Refresh. Drag a drive from a pool here to remove it from the pool."))], { class: "dzone card pool zone-drives" }));
  out.push(h("div", { class: "pools" }, (st.pools || []).map(p => poolBox(p, tiles.filter(t => inPool(t) && t.d.role === p.role)))));
  if (!drives.length && !(st.pools || []).length) out.push(h("p", { class: "muted" }, "No drives were found."));
  if ((DR.actions || {}).can_sleep === false) out.push(h("p", { class: "muted small" }, "Sleep and wake need the hdparm tool, which is not installed on this machine."));
  return out;
}
function drivesBody() { return [drivesParts(), upBox, bkBox]; }
function viewDrives() {
  drivesBox = h("div", {});
  put(drivesBox, drivesBody());
  loadUploads();
  loadBackups();
  api("GET", "/api/backup/job").then(j => { if (j.running) { BKjob = j; BKwas = j.action; drawBackups(); followBackup(); } }).catch(() => {  });
  api("GET", "/api/drives/job").then(j => {
    if (j.running) {
      DRbusy = j.action; DRjob = j; followJob(); drawDrives();
      api("GET", "/api/drives").then(d => { if (!DR) { DR = d; drawDrives(); } }).catch(() => {  });
    } else loadDrives();
  }).catch(() => loadDrives());
  return drivesBox;
}

