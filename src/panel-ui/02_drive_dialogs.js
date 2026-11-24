let footEl = null, footSave = null;
function saveButton(off, fn) {
  if (!footSave) footSave = h("button", { class: "primary" }, "Save");
  footSave.disabled = off; footSave.onclick = fn;
  return footSave;
}
function drawFoot(dirty, onSave, onRevert, extra) {
  if (!footEl) return;
  put(footEl,
    onSave ? h("div", { class: "state" + (dirty ? " dirty" : ""), title: dirty ? "There are unsaved changes." : "Everything shown is saved." }, dirty ? "Unsaved Changes" : "Saved") : null,
    onRevert ? h("button", { disabled: !dirty, onclick: onRevert }, "Discard Changes") : null,
    extra || null,
    view === "drives" ? null : h("button", { disabled: !S.undo, onclick: doUndo, title: S.undo ? "Undo: " + S.undo : "Nothing to undo" }, "Undo"),
    view === "drives" ? null : saveButton(!onSave || !dirty, onSave || (() => {})),
    framed ? h("a", { class: "btn", href: location.href, target: "_blank", rel: "noopener" }, "Open in New Tab") : null,
    h("button", { class: "ghost", onclick: async () => { try { await api("POST", "/api/logout", {}); } catch (e) {  } S = null; showLogin(); } }, "Log Out"));
}
function saveBar(dirty, onSave, onRevert, saveLabel, extra) {
  drawFoot(dirty, onSave, onRevert, extra);
  return null;
}


let DRapps = null;
let DR = null, DRerr = "", DRbusy = "", DRhealth = null, DRcheck = null, DRwait = "", DRjob = null, DRpoll = 0;
let drivesBox = null;
const ROLE_TEXT = { main: "Main", backup: "Backup", parity: "Parity", array: "Array", spare: "Spare", system: "System", "plain-data": "Plain Data" };
const STATE_TEXT = { connected: "Connected", "connected (used last)": "Connected", MISSING: "Missing", "NOT MOUNTED": "Not Mounted",
  "not connected to a pool": "Not in a Pool", "boot/system drive (not changed)": "Boot Drive" };
const STATE_HINT = { "connected (used last)": "A backup copy on the boot drive. It is used only when the other backup drives are full.", "boot/system drive (not changed)": "The boot drive. The panel never changes it." };
const JOB_TEXT = { add: "Adding the drive...", wipe: "Erasing the drive...", disconnect: "Taking the drive out of its pool...", move: "Moving the drive...", remount: "Repairing the drives. This can take a minute...", moveboot: "Moving the files from the boot drive to the drive. This can take a while...", movefolders: "Moving the folders to the other drive. This can take a while...", appsfix: "Repairing Immich and Nextcloud. Copying files back from the backup can take a long time...",
  setup: "Building the new setup. This can take a few minutes...", bootadd: "Reserving part of the boot drive...", rename: "Saving the name...", sleep: "Telling the drive to sleep...", wake: "Waking the drive up..." };
// The automatic name of a Boot Drive Space starts with the size of its file. Show the space that can be filled instead, so the name and the pool agree.
function bootSectionName(d) {
  const n = String(d.name || "");
  const auto = /^[\d.]+ (MB|GB|TB) boot drive section$/i.test(n);
  return auto && typeof d.size_bytes === "number" ? humanBytes(d.size_bytes) + " Boot Drive Space" : n.replace(/ boot drive section$/i, " Boot Drive Space");
}
function humanBytes(n) {
  if (typeof n !== "number" || !(n >= 0)) return "-";
  const u = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  while (n >= 1000 && i < u.length - 1) { n /= 1000; i++; }
  return (n >= 100 || i === 0 ? Math.round(n) : n.toFixed(1)) + " " + u[i];
}
function stateText(t) { t = t || ""; return STATE_TEXT[t] || (t ? t[0].toUpperCase() + t.slice(1) : ""); }
function stateClass(t) { t = t || ""; return t.startsWith("connected") ? "ok" : (t.startsWith("MISSING") || t === "NOT MOUNTED") ? "bad" : ""; }
function usageBar(used, size) {
  if (typeof used !== "number" || typeof size !== "number" || !(size > 0)) return null;
  const pct = Math.max(0, Math.min(100, Math.round(used * 100 / size)));
  return h("div", { class: "usebar", role: "img", "aria-label": pct + " percent used" }, h("i", { style: { width: pct + "%" }, class: pct >= 95 ? "full" : pct >= 85 ? "high" : "" }));
}
function diskOf(dev) {
  dev = (dev || "").replace(/^\/dev\//, "");
  return /^(nvme|mmcblk|loop)/.test(dev) ? dev.replace(/p\d+$/, "") : dev.replace(/\d+$/, "");
}
let DRretry = 0, DRhealthRetry = 0;
function loadDrives(tries) {
  if (DRjob && DRjob.running) return Promise.resolve();
  tries = tries || 0;
  clearTimeout(DRretry);
  DRwait = "Looking at the drives...";
  drawDrives();
  const gaveUp = e => { DRerr = e.message; DRwait = ""; drawDrives(); };
  const follow = () => api("GET", "/api/drives/job").then(j => { if (j.running) { DRbusy = j.action; DRjob = j; DRwait = ""; followJob(); drawDrives(); return true; } return false; }).catch(() => false);
  return api("GET", "/api/drives").then(d => {
    DR = d; DRerr = ""; DRwait = "";
    if (d.stale) {
      return follow().then(running => { if (!running && tries < 20) DRretry = setTimeout(() => { if (drivesBox && drivesBox.isConnected) loadDrives(tries + 1); }, 2500); drawDrives(); });
    }
    drawDrives(); if (!DRhealth) quietHealth(); rescanConfig(); quietApps();
  }).catch(e => {
    if (e.status !== 409) return gaveUp(e);
    return api("GET", "/api/drives/job").then(j => {
      if (j.running) { DRbusy = j.action; DRjob = j; DRwait = ""; followJob(); drawDrives(); }
      else if (tries < 20) DRretry = setTimeout(() => { if (drivesBox && drivesBox.isConnected) loadDrives(tries + 1); }, 2500);
      else gaveUp(e);
    }).catch(() => gaveUp(e));
  });
}
function quietHealth(tries) {
  tries = tries || 0;
  clearTimeout(DRhealthRetry);
  api("GET", "/api/drives/health").then(r => { DRhealth = r; drawDrives(); }).catch(e => {
    if (e.status === 409 && tries < 20) { DRhealthRetry = setTimeout(() => { if (drivesBox && drivesBox.isConnected && !DRhealth) quietHealth(tries + 1); }, 3000); return; }
    DRhealth = { drives: [], ok: true }; drawDrives();
  });
}
function quietApps() {
  api("GET", "/api/drives/apps").then(a => { DRapps = a; drawDrives(); }).catch(() => { DRapps = null; });
}
async function appsRestore() {
  const b = (DRapps || {}).backup || {};
  const ok = await confirmBox("Restore From the Backup?",
    "Missing files are copied back from the last backup" + (b.stamp ? " (" + b.stamp + ", result " + (b.result || "unknown") + ")" : "") + ". Existing files are never overwritten, and files added or changed after that backup cannot be restored. Immich and Nextcloud stop while the files copy and restart on their own. Accounts and settings are unchanged. This can take a long time.",
    "Restore From Backup");
  if (ok) startJob("appsfix", { mode: "restore", typed: ["RESTORE"] }, "The files are restored and Immich and Nextcloud are running again.");
}
async function appsFresh() {
  const names = ((DRapps || {}).problems || []).map(a => a === "nextcloud" ? "Nextcloud" : a === "immich" ? "Immich" : a).join(" and ");
  const r = await driveDialog({
    title: "Start on Empty Folders",
    lead: [names + " will start on empty folders. Accounts and settings are unchanged."],
    questions: [],
    warn: () => "Photos and files from the missing drive will not be available. Immich keeps a list of photos it cannot open, and apps that sync with Nextcloud may delete their own copies. Do this only if the old files are gone for good, or after restoring what you can.",
    typed: () => [{ word: "START" }],
    sure: () => "I understand the old files will not be available.",
    ok: () => "Start on Empty Folders", danger: () => true });
  if (!r) return;
  startJob("appsfix", { mode: "fresh", typed: r.typed }, names + " started on empty folders.");
}
async function moveBootFiles() {
  const ok = await confirmBox("Move the Files to the Drive?",
    "Files on the boot drive are copied to the Main pool and checked. The old copies are removed only after every file is verified. A file that exists in both places with different content is never replaced. Services stop briefly.",
    "Move the Files");
  if (ok) startJob("moveboot", {}, "The files are on the Main pool now.");
}
function appsCard() {
  const p = (DRapps && DRapps.problems) || [];
  if (!p.length) return null;
  const names = p.map(a => a === "nextcloud" ? "Nextcloud" : a === "immich" ? "Immich" : a).join(" and ");
  const bk = (DRapps.backup || {}).found;
  return h("div", { class: "card warncard", role: "alert" }, h("h2", {}, names + " Cannot Find Their Files"),
    h("p", {}, "Their files were on a drive that is not in the Main pool now, so " + (p.length > 1 ? "they refuse" : "it refuses") + " to start. This is intentional: if started on an empty folder, they would appear to have lost everything. Their accounts and settings are not lost."),
    h("p", { class: "muted small" }, bk ? "A backup copy of the files was found. Restoring copies back only what is missing." : "No backup copy of the files was found. If the old drive still works, connect it again and press Fix Drives. Otherwise, the apps can be started on empty folders."),
    h("div", { class: "row" },
      bk ? h("button", { class: "primary small", disabled: !!DRbusy, onclick: appsRestore }, "Restore From Backup") : null,
      h("button", { class: "small", disabled: !!DRbusy, onclick: appsFresh }, "Start on Empty Folders")));
}
function drawDrives() {
  if (!(drivesBox && drivesBox.isConnected)) return;
  if (DRdrag) { DRdrawLater = true; return; }
  put(drivesBox, drivesBody());
  drawBackups();
  refreshCard();
}

function followJob() {
  clearTimeout(DRpoll);
  const tick = () => api("GET", "/api/drives/job").then(j => {
    DRjob = j;
    if (j.running) { drawDrives(); DRpoll = setTimeout(tick, 2000); return; }
    jobFinished(j);
  }).catch(() => { DRpoll = setTimeout(tick, 4000); });
  tick();
}
async function jobFinished(j) {
  const was = DRbusy, okText = DRokText, last = DRlast;
  DRbusy = "";
  DRjob = null;
  DRokText = "";
  DRlast = null;
  DRhealth = DRcheck = null;
  const busy = j.rc !== 0 && /Not safe to continue now/.test(j.message || "") && last && !(last.body.typed || []).includes("NOW");
  if (busy) {
    await loadDrives();
    const why = (j.message || "").replace(/^.*?Not safe to continue now: ?/, "").replace(/\. (Nothing was changed|Stopping the containers).*$/, "").replace(/\.$/, "") || "something is being written to a pool";
    const go = await confirmBox("Not Safe to Continue", why[0].toUpperCase() + why.slice(1) + ". Nothing was changed. Continuing now stops the containers briefly and can interrupt it. Wait for it to finish, or continue anyway?", "Go Ahead Anyway", true);
    if (go) startJob(last.action, Object.assign({}, last.body, { typed: (last.body.typed || []).concat(["NOW"]) }), last.okText);
    return was;
  }
  if (j.rc !== 0 && j.rc !== 4) DRfail = { what: JOB_TEXT[j.action] ? JOB_TEXT[j.action].replace(/\.\.\..*$/, "") : "That change", message: j.message || "That did not work.", lines: (j.lines || []).filter(l => !/\(typed in the panel\)|^Type /.test(l)), time: new Date() };
  else DRfail = null;
  toast(j.rc === 0 ? (okText || "Done.") : (j.message || (j.rc === 4 ? "Stopped." : "That did not work.")), j.rc !== 0 && j.rc !== 4);
  await loadDrives();
  return was;
}
let DRokText = "";
let DRfail = null;
async function startJob(action, body, okText) {
  if (DRbusy) return;
  DRbusy = action;
  DRfail = null;
  DRokText = okText || "";
  DRlast = { action, body, okText };
  const items = (body.ids || [body.id]).filter(Boolean).map(x => String(x).split(":")[0]);
  DRjob = { running: true, action, items, progress: {}, lines: [] };
  DRsel = new Set();
  drawDrives();
  try { await api("POST", "/api/drives/" + action, body); followJob(); } catch (e) { DRbusy = ""; DRjob = null; DRokText = ""; DRlast = null; fail(e); drawDrives(); }
}
async function driveDo(action, body, okReload) {
  if (DRbusy) return;
  DRbusy = action;
  drawDrives();
  try {
    const r = await api("POST", "/api/drives/" + action, body);
    toast(r.message || "Done.");
  } catch (e) { fail(e); }
  DRbusy = "";
  await loadDrives();
}

// A dialog with questions and typed confirmations. cfg: { title, lead: [text], questions: [{ id, label, options: [{ value, label, hint }], value, show(state) }], ... }.
function driveDialog(cfg) {
  return new Promise(resolve => {
    const state = {};
    (cfg.questions || []).forEach(q => { state[q.id] = q.value; });
    const dynamic = h("div", {});
    (cfg.fields || []).forEach(f => { state[f.id] = f.value; });
    const fieldBox = (cfg.fields || []).map(f => h("label", { class: "dfield" }, h("span", {}, h("b", {}, f.label), f.hint ? h("small", {}, f.hint) : null),
      h("input", { type: "number", min: f.min, max: f.max, step: 1, value: f.value, inputmode: "numeric", oninput: ev => { state[f.id] = ev.target.value; refresh(); } })));
    const okBtn = h("button", { class: "primary" }, "OK");
    let sure = false;
    const finish = v => { if (!done) { done = true; resolve(v); } d.close(); };
    let done = false;
    const refresh = () => {
      const qs = (cfg.questions || []).filter(q => !q.show || q.show(state));
      const refuse = cfg.refuse ? cfg.refuse(state) : null;
      const typed = refuse ? [] : (cfg.typed ? cfg.typed(state) : []);
      const needSure = typed.some(t => !t.auto);
      const bad = refuse ? null : (cfg.invalid ? cfg.invalid(state) : null);
      const check = () => { const b = cfg.invalid && !refuse ? cfg.invalid(state) : null; okBtn.disabled = !!b || (!refuse && needSure && !sure); if (invalidBox) { invalidBox.textContent = b || ""; invalidBox.hidden = !b; } };
      const invalidBox = h("p", { class: "dwarn", role: "alert", hidden: !bad }, bad || "");
      put(dynamic, [
        qs.map(q => h("fieldset", { class: "dq" }, h("legend", {}, q.label),
          q.options.map(o => h("label", { class: "dopt" },
            h("input", Object.assign({ type: "radio", name: "dq-" + q.id, value: o.value, onchange: () => { state[q.id] = o.value; sure = false; refresh(); } }, state[q.id] === o.value ? { checked: true } : {})),
            h("span", {}, h("b", {}, o.label), o.hint ? h("small", {}, o.hint) : null))))),
        cfg.note && cfg.note(state) ? h("p", { class: "muted" }, cfg.note(state)) : null,
        cfg.fields && !refuse ? invalidBox : null,
        refuse ? h("p", { class: "dwarn", role: "alert" }, refuse) : (cfg.warn && cfg.warn(state) ? h("p", cfg.danger && cfg.danger(state) ? { class: "dwarn", role: "alert" } : { class: "dnote", role: "status" }, cfg.warn(state)) : null),
        needSure ? h("label", { class: "dopt sure" },
          h("input", { type: "checkbox", checked: sure, onchange: ev => { sure = ev.target.checked; check(); } }),
          h("span", {}, h("b", {}, cfg.sure ? cfg.sure(state) : "I understand this cannot be undone."))) : null]);
      okBtn.textContent = refuse ? "Close" : cfg.ok(state);
      okBtn.className = !refuse && cfg.danger && cfg.danger(state) ? "danger" : "primary";
      okBtn.onclick = () => refuse ? finish(null) : finish({ answers: Object.assign({}, state), typed: typed.map(t => t.word) });
      check();
    };
    const d = h("dialog", { class: "wide" }, h("h2", {}, cfg.title), (cfg.lead || []).map(t => h("p", {}, t)), fieldBox, dynamic,
      h("div", { class: "actions" }, h("button", { onclick: () => finish(null) }, "Cancel"), okBtn));
    d.addEventListener("close", () => { d.remove(); finish(null); });
    refresh();
    document.body.append(d);
    d.showModal();
  });
}
let DRcfg = null;
let DRskip = new Set();
let DRcfgBusy = false;
const setupsUrl = () => "/api/drives/setups" + (DRskip.size ? "?skip=" + encodeURIComponent([...DRskip].join(",")) : "");
async function skipDrive(id, leave) {
  if (leave) DRskip.add(id); else DRskip.delete(id);
  DRcfgBusy = true;
  drawDrives();
  await rescanConfig();
  DRcfgBusy = false;
  drawDrives();
}
async function openConfig() {
  if (DRcfg && !DRcfg.loading) { DRcfg = null; drawDrives(); return; }
  DRcfg = { loading: true };
  DRskip = new Set();
  drawDrives();
  try {
    DRcfg = await api("GET", setupsUrl());
    (DRcfg.options || []).forEach(o => { if (o.id === "pool" && o.fits) { o.can_build = true; o.why = ""; } });
  } catch (e) { DRcfg = { err: String((e && e.message) || e || "The drives could not be scanned.") }; }
  drawDrives();
}
async function rescanConfig() {
  if (!DRcfg || DRcfg.loading || DRcfg.err) return;
  try {
    const c = await api("GET", setupsUrl());
    DRskip = new Set([...DRskip].filter(id => (c.spare || []).some(sp => sp.id === id)));
    (c.options || []).forEach(o => { if (o.id === "pool" && o.fits) { o.can_build = true; o.why = ""; } });
    if (DRcfg && !DRcfg.loading) { DRcfg = c; drawDrives(); }
  } catch (e) {  }
}
const protectText = o => o.tolerates > 0 ? (o.tolerates === 1 ? "1 drive can fail" : o.tolerates + " drives can fail") + (o.nightly ? " (copied every night)" : "") : "no protection";
const setupLine = o => o.title + (o.fits ? "  -  " + humanBytes(o.usable_bytes) + " usable, " + protectText(o) : "  -  needs " + o.min + " drives");
async function buildPlainPool(o) {
  const c = DRcfg || { spare: [] };
  const drives = o.drives.map(id => c.spare.find(sp => sp.id === id)).filter(Boolean);
  const left = c.spare.filter(sp => !o.drives.includes(sp.id));
  const withFiles = drives.filter(sp => !sp.blank);
  const mode = (s, sp) => sp.blank ? "erase" : s["m-" + sp.id];
  const erasing = s => drives.filter(sp => mode(s, sp) === "erase");
  const running = poolOf("main").mounted;
  const r = await driveDialog({
    title: "Build: " + o.title,
    lead: [o.blurb, "Drives used (" + drives.length + " of " + c.spare.length + "): " + drives.map(sp => sp.name + " (" + humanBytes(sp.size_bytes) + ")").join(", "),
      withFiles.length ? "Formatted drives can keep their files, which then appear in the Main pool." : "These drives are empty. They will be formatted for HomeLab.",
      left.length ? "Not used: " + left.map(sp => sp.name + " (" + humanBytes(sp.size_bytes) + ")").join(", ") + ". They stay as spare drives." : "Every spare drive is used."],
    questions: withFiles.map(sp => ({ id: "m-" + sp.id, label: sp.name + "  ·  " + sp.device + "  ·  already formatted", value: sp.keep_ok ? "keep" : "erase", options: sp.keep_ok ? [KEEP_OPT("Main"), ERASE_OPT] : [CANT_KEEP_OPT] })),
    warn: s => {
      const e = erasing(s).filter(sp => !sp.blank);
      if (e.length) return "Everything on " + e.map(sp => sp.device).join(", ") + " will be permanently deleted.";
      if (erasing(s).length) return "Empty drives are formatted for HomeLab. Nothing is lost. " + (withFiles.length ? "The files on the other drives are unchanged. " : "") + (running ? "The Main pool keeps running." : "Containers that use the Main pool stop briefly.");
      return "The files on the drives are unchanged. " + (running ? "The Main pool keeps running." : "Containers that use the Main pool stop briefly.");
    },
    typed: s => erasing(s).length ? erasing(s).map(sp => ({ word: sp.device })).concat([{ word: "ERASE" }]) : [],
    sure: () => "I understand that everything on the drives marked for erasing will be permanently deleted.",
    ok: s => erasing(s).some(sp => !sp.blank) ? "Erase Where Needed and Build" : erasing(s).length ? "Format and Build Pool" : "Build Pool", danger: s => erasing(s).some(sp => !sp.blank) });
  if (!r) return;
  const ids = drives.map(sp => sp.id + ":" + mode(r.answers, sp));
  const body = drives.length === 1 ? { ids: [drives[0].id], role: "main", mode: mode(r.answers, drives[0]), typed: r.typed } : { ids, role: "main", typed: r.typed };
  startJob("add", body, o.title + " is ready: " + nDrives(drives.length).toLowerCase() + " in the Main pool.");
}
// The dialog that builds a ready-made drive setup on the spare drives the person chooses.
async function buildSetup(o) {
  if (o.id === "pool") return buildPlainPool(o);
  const c = DRcfg || { spare: [] };
  const drives = o.drives.map(id => c.spare.find(sp => sp.id === id)).filter(Boolean);
  const left = c.spare.filter(sp => !o.drives.includes(sp.id));
  const withFiles = drives.filter(sp => !sp.blank);
  const par = o.id === "snapraid1" ? 1 : o.id === "snapraid2" ? 2 : 0;
  const keepable = o.can_keep ? withFiles.filter(sp => sp.keep_ok) : [];
  const defKeep = new Set();
  if (o.id === "mirror") { const k = keepable.slice().sort((a, b) => b.size_bytes - a.size_bytes)[0]; if (k) defKeep.add(k.id); }
  else if (par) drives.slice().sort((a, b) => b.size_bytes - a.size_bytes).slice(par).forEach(sp => { if (keepable.includes(sp)) defKeep.add(sp.id); });
  const modeOf = (st, sp) => (keepable.includes(sp) ? st["m-" + sp.id] : "erase");
  const kept = st => drives.filter(sp => modeOf(st, sp) === "keep");
  const erased = st => drives.filter(sp => modeOf(st, sp) !== "keep");
  const withFilesErased = st => erased(st).filter(sp => !sp.blank);
  const r = await driveDialog({
    title: "Build: " + o.title,
    lead: [o.blurb, "Drives used (" + drives.length + " of " + c.spare.length + "): " + drives.map(sp => sp.name + " (" + humanBytes(sp.size_bytes) + ")").join(", "),
      (humanBytes(o.usable_bytes) === humanBytes(o.used_bytes) ? "You get all of the " + humanBytes(o.used_bytes) + " on these drives. " : "You get about " + humanBytes(o.usable_bytes) + " of the " + humanBytes(o.used_bytes) + " on these drives. ") + (o.tolerates > 0 ? cap(protectText(o)) + " without losing files." : "There is no redundancy: if one drive fails, the files are lost."),
      keepable.length ? (o.id === "mirror" ? "One drive can keep its files and becomes Main. The other holds the copy and is erased." : "Drives that hold files can keep them as data drives. The largest drive" + (par > 1 ? "s" : "") + " that " + (par > 1 ? "are" : "is") + " not kept hold" + (par > 1 ? "" : "s") + " the protection data and " + (par > 1 ? "are" : "is") + " erased.") : null,
      o.migrate ? "Your Main pool has " + humanBytes(c.main_used_bytes || 0) + " of files and this setup holds " + humanBytes(o.usable_bytes) + ", so it all fits. The files are copied into the new setup and checked first, then it becomes the Main pool. The old Main drives are released afterwards with their files intact, as spare drives. " + serviceText(c.main_services) + " Large copies can take hours. If you press Abort while it copies, the services restart and nothing changes." : null,
      left.length ? "Not used: " + left.map(sp => sp.name + " (" + humanBytes(sp.size_bytes) + ")").join(", ") + ". They stay as spare drives." : "Every spare drive is used."].filter(Boolean),
    questions: keepable.map(sp => ({ id: "m-" + sp.id, label: sp.name + "  ·  " + sp.device + "  ·  already formatted", value: defKeep.has(sp.id) ? "keep" : "erase", options: [KEEP_OPT("Main"), ERASE_OPT] })),
    invalid: st => o.id === "mirror" && kept(st).length > 1 ? "A mirror can keep the files of only one drive. The other drive becomes the copy." : par && drives.length - kept(st).length < par ? "SnapRAID needs " + par + " drive" + (par > 1 ? "s" : "") + " for the protection data, and " + (par > 1 ? "they are" : "it is") + " erased. Let at least " + par + " of the drives be erased." : null,
    refuse: () => o.can_build ? null : o.why,
    warn: st => (erased(st).length ? "Everything on " + erased(st).map(sp => sp.device).join(", ") + " will be permanently deleted" + (withFilesErased(st).length ? " (" + withFilesErased(st).map(sp => sp.name).join(", ") + " already hold files)" : "") + "." : "") + (kept(st).length ? " The files on " + kept(st).map(sp => sp.device).join(", ") + " stay as they are." : "") + (o.kind !== "pool" && o.id !== "mirror" && !/^snapraid/.test(o.id) ? " The new pool becomes the Main pool." : "") + (o.migrate ? " The files of the current Main pool are copied into it, and the old Main drives are released. Nothing on them is erased." : ""),
    typed: () => [{ word: o.id }, { word: "ERASE" }],
    sure: () => "I understand that everything on the drives marked for erasing will be permanently deleted.",
    ok: st => erased(st).length === drives.length ? "Erase and Build Setup" : "Build Setup", danger: () => true });
  if (!r) return;
  const ids = keepable.length ? o.drives.map(id => id + ":" + (modeOf(r.answers, drives.find(sp => sp.id === id) || {}) || "erase")) : o.drives;
  startJob("setup", { setup: o.id, ids, typed: r.typed }, o.title + " is ready.");
}
function cfgBox() {
  if (!DRcfg) return null;
  const off = !!DRbusy || !!DRwait;
  if (DRcfg.loading) return h("div", { class: "cfg", role: "status" }, h("p", { class: "muted" }, "Scanning the drives..."));
  if (DRcfg.err) return h("div", { class: "cfg", role: "alert" }, h("p", { class: "dwarn" }, DRcfg.err), h("button", { class: "small", onclick: () => { DRcfg = null; openConfig(); } }, "Try Again"));
  const c = DRcfg, rec = (c.options || []).find(o => o.id === c.recommended);
  const spare = c.spare || [], usable = spare.filter(sp => !sp.skipped);
  const sizes = usable.map(sp => humanBytes(sp.size_bytes)).join(", ");
  if (!spare.length) return h("div", { class: "cfg" }, h("p", { class: "muted" }, "There are no spare drives to build a setup on. Connect drives (or remove them from Main and Backup), then press Configure Drives again."));
  const pick = spare.length >= 2 ? h("fieldset", { class: "cfgpick", disabled: off || DRcfgBusy }, h("legend", {}, "Drives to Use"),
    spare.map(sp => h("label", {}, h("input", Object.assign({ type: "checkbox", onchange: ev => skipDrive(sp.id, !ev.target.checked) }, sp.skipped ? {} : { checked: true })),
      h("span", {}, sp.name + "  ·  " + sp.device + "  ·  " + humanBytes(sp.size_bytes)))),
    h("small", { class: "muted" }, "Clear the checkbox of a drive to leave it out. It stays a spare drive and is not changed.")) : null;
  if (!rec) return h("div", { class: "cfg" }, pick, h("p", { class: "muted" }, usable.length ? "No setup can be built on the chosen drives." : "Every spare drive is left out. Select at least one drive to see the setups."));
  const others = c.options.filter(o => o.id !== rec.id);
  return h("div", { class: "cfg" }, pick,
    h("p", { class: "muted small" }, "Scanned " + nDrives(spare.length).toLowerCase() + (spare.length === 1 ? " that is" : " that are") + " not in a pool" + (usable.length < spare.length ? " (using " + usable.length + ": " + sizes + ")" : ": " + sizes) + ". Setups are ranked by redundancy and usable space. Every setup erases the drives it uses, except a plain pool, a mirror and SnapRAID, which can keep a drive's files. A RAID or ZFS setup can also replace a Main pool that has drives: the files are copied first, and the old drives are released without being erased."),
    h("div", { class: "cfgrec" }, h("b", {}, "Recommended: " + rec.title), h("span", { class: "muted small" }, humanBytes(rec.usable_bytes) + " usable, " + protectText(rec) + ", uses " + nDrives(rec.drives.length).toLowerCase()),
      !rec.can_build ? h("span", { class: "dwarn small" }, rec.why) : null),
    h("div", { class: "row tight" },
      h("button", { class: "primary", disabled: off, onclick: () => buildSetup(rec) }, "Build Recommended Setup"),
      h("select", { class: "cfgsel", disabled: off, "aria-label": "Other setups, best to worst", onchange: ev => { const o = others.find(x => x.id === ev.target.value); ev.target.value = ""; if (o && o.fits) buildSetup(o); else if (o) toast(o.title + " needs " + o.min + " drives, and only " + usable.length + " can be used now.", true); } },
        h("option", { value: "" }, "Other setups, best to worst..."),
        others.map(o => h("option", Object.assign({ value: o.id }, o.fits ? {} : { disabled: true }), setupLine(o) + (o.fits && !o.can_build ? "  (not possible yet)" : ""))))));
}
const other = r => (r === "main" ? "backup" : "main");
const cap = t => t[0].toUpperCase() + t.slice(1);

