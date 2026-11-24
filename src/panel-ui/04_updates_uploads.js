let UPD = null, UPDerr = "", UPDtimer = 0, UPDjob = null, UPDwas = "", UPDheld = "";
const updBox = h("div", { class: "upd" });
const UPD_WORKING = { check: "Looking for new versions...", containers: "Updating the containers...", "containers-now": "Updating the containers...", system: "Updating the system...", restart: "Restarting the machine..." };

function updAgo(then, now) {
  if (!then) return "never";
  const m = Math.max(0, Math.round((now - then) / 60));
  return m < 2 ? "just now" : m < 120 ? m + " minutes ago" : m < 2880 ? Math.round(m / 60) + " hours ago" : Math.round(m / 1440) + " days ago";
}
async function loadUpdates(fresh) {
  try { UPD = await api("GET", "/api/updates" + (fresh === true ? "?fresh=1" : "")); UPDerr = ""; if (UPD.job && UPD.job.running) { UPDjob = UPD.job; UPDwas = UPD.job.action; followUpdates(); } } catch (e) { UPD = null; UPDerr = e.message; }
  drawUpdates();
}
function followUpdates() {
  clearTimeout(UPDtimer);
  const tick = async () => {
    if (!updBox.isConnected) return;
    let j;
    try { j = await api("GET", "/api/updates/job"); } catch (e) { UPDtimer = setTimeout(tick, 3000); return; }
    if (j.running) { UPDjob = j; drawUpdates(); UPDtimer = setTimeout(tick, 1500); return; }
    UPDjob = null;
    const said = UPDwas;
    UPDwas = "";
    if (said === "containers" || said === "containers-now") UPDheld = j.held ? j.held : "";
    await loadUpdates();
    if (said) toast(j.message || "Done.", !!j.rc);
  };
  tick();
}
async function updStart(what, extra) {
  if (UPDjob && UPDjob.running) return;
  try {
    await api("POST", "/api/updates/start", Object.assign({ what }, extra || {}));
    UPDjob = { running: true, action: what, lines: [], pct: null, stage: "" };
    UPDwas = what;
    drawUpdates();
    followUpdates();
  } catch (e) { fail(e); }
}
async function updAnyway() {
  if (!(await confirmBox("Update anyway?", "The update is held back because " + UPDheld + ". Updating now can slow that down or interrupt it, and each service restarts briefly. Update now?", "Update Anyway", true))) return;
  UPDheld = "";
  updStart("containers-now");
}
async function updRestart() {
  if (!(await confirmBox("Restart the machine?", "Every service stops for a minute or two and restarts on its own. Do not restart during a backup or upload.", "Restart Now", true))) return;
  updStart("restart", { confirm: true });
}
function updRow(title, sub, pill, buttons, prog) {
  return h("div", { class: "bkt" }, h("div", { class: "ph" }, h("div", { class: "pt" }, h("h3", {}, title), h("span", { class: "sub" }, sub)), pill, buttons), prog || null);
}
function updBar(job) {
  const pct = typeof job.pct === "number" ? Math.max(2, Math.min(100, job.pct)) : null;
  const words = job.stage || UPD_WORKING[job.action] || "Working...";
  return h("div", { class: "bkprog updprog" },
    h("div", { class: "bar" + (pct === null ? " wait" : ""), role: "progressbar", "aria-label": words, "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": pct === null ? null : String(pct) },
      h("i", { style: { width: (pct === null ? 100 : pct) + "%" } })),
    h("span", { class: "muted small" }, words + (pct === null ? "" : "  (" + pct + "%)")));
}
// Draw the Updates tab: what is waiting, the progress of a running update and its output.
function drawUpdates() {
  const busy = !!(UPDjob && UPDjob.running);
  const body = [h("div", { class: "ph" },
    h("div", { class: "pt" }, h("h2", {}, "Updates"), h("span", { class: "sub" }, "What is waiting to be updated. The bell on the dashboard shows the same things.")),
    h("button", { class: "small", disabled: busy, onclick: () => loadUpdates(true) }, "Refresh"))];
  if (UPDerr) body.push(h("p", { class: "badtext", role: "alert" }, UPDerr), h("button", { class: "small", onclick: loadUpdates }, "Try Again"));
  else if (!UPD) body.push(h("p", { class: "muted" }, "Looking at the updates..."));
  else {
    const n = UPD.containers.length;
    const names = UPD.containers.map(c => c.name).join(", ");
    body.push(h("div", { class: "bkl" },
      updRow("Containers", n ? n + " waiting: " + names + ". A quick database dump is made first, then each service is updated one at a time." : "Everything is up to date. Last looked " + updAgo(UPD.checked, UPD.now) + ".",
        h("span", { class: "pill " + (n ? "warn" : "ok") }, n ? n + " waiting" : "Up to date"),
        h("div", { class: "pills" }, h("button", { class: "small", disabled: busy, onclick: () => updStart("check") }, "Check Now"),
          h("button", { class: "small primary", disabled: busy || !n, onclick: () => updStart("containers") }, "Update Containers")),
        busy && ["containers", "containers-now", "check"].includes(UPDjob.action) ? updBar(UPDjob)
          : UPDheld ? h("div", { class: "updheld", role: "status" },
            h("span", { class: "badtext" }, "Nothing was updated: " + UPDheld + "."),
            h("span", { class: "muted small" }, "Wait for it to finish and press Update Containers again, or update now."),
            h("button", { class: "small", onclick: updAnyway }, "Update Anyway")) : null),
      updRow("System", UPD.system === null ? "Not checked yet. Press Update System to check and install." : UPD.system ? UPD.system + " package" + (UPD.system === 1 ? "" : "s") + " waiting (Ubuntu or Mint). Installing can take several minutes." : "Everything that can be installed is installed." + (UPD.kept_back ? " " + UPD.kept_back + " more " + (UPD.kept_back === 1 ? "package is" : "packages are") + " held back by Ubuntu: " + (UPD.kept_back === 1 ? "it needs" : "they need") + " other changes first, or " + (UPD.kept_back === 1 ? "is" : "are") + " being rolled out slowly. " + (UPD.kept_back === 1 ? "It installs" : "They install") + " automatically later. To see the list: apt list --upgradable" : ""),
        h("span", { class: "pill " + (UPD.system ? "warn" : UPD.system === null ? "dim" : "ok") }, UPD.system === null ? "Unknown" : UPD.system ? UPD.system + " waiting" : "Up to date"),
        h("div", { class: "pills" }, h("button", { class: "small primary", disabled: busy || UPD.system === 0, onclick: () => updStart("system") }, "Update System")),
        busy && UPDjob.action === "system" ? updBar(UPDjob) : null),
      updRow("Restart", UPD.restart ? "A system update requires a restart. Restart when nothing important is running." : "No restart is needed.",
        h("span", { class: "pill " + (UPD.restart ? "warn" : "ok") }, UPD.restart ? "Needed" : "Not needed"),
        h("div", { class: "pills" }, h("button", { class: "small" + (UPD.restart ? " primary" : ""), disabled: busy, onclick: updRestart }, "Restart Machine")),
        busy && UPDjob.action === "restart" ? updBar(UPDjob) : null)));
  }
  if (UPDjob && UPDjob.running) {
    if (!UPD || UPDerr) body.push(updBar(UPDjob));
    body.push(h("p", { class: "muted" }, "Keep this page open if possible. The process continues if the page is closed."),
      h("pre", { class: "updlog", "aria-live": "polite" }, (UPDjob.lines || []).join("\n")));
  }
  put(updBox, h("div", { class: "card" }, body));
}
function viewUpdates() {
  drawUpdates();
  loadUpdates();
  return updBox;
}

let UP = null, UPerr = "";
const UPq = { photo: [], song: [] }, UPrun = { photo: false, song: false };
const upBox = h("div", { class: "up" });
const UP_NAMES = { photo: "Photos and Videos", song: "Songs" };
const upBusy = () => UPrun.photo || UPrun.song;
window.addEventListener("beforeunload", e => { if (upBusy()) { e.preventDefault(); e.returnValue = ""; } });

async function loadUploads() {
  try { UP = await api("GET", "/api/upload"); UPerr = ""; } catch (e) { UP = null; UPerr = e.message; }
  drawUploads();
}
const upExt = n => (n.includes(".") ? n.split(".").pop().toLowerCase() : "");
function upAdd(kind, files) {
  const ok = new Set(kind === "photo" ? UP.photo_ext : UP.song_ext), max = UP.limits[kind];
  for (const f of files) {
    const it = { file: f, state: "wait", pct: 0, msg: "" };
    if (!ok.has(upExt(f.name))) { it.state = "fail"; it.msg = upExt(f.name) ? "Not accepted here (." + upExt(f.name) + ")" : "No ending like .mp3 or .jpg"; }
    else if (f.size === 0) { it.state = "fail"; it.msg = "The file is empty"; }
    else if (f.size > max) { it.state = "fail"; it.msg = "Too big (the most is " + humanBytes(max) + ")"; }
    UPq[kind].push(it);
  }
  drawUploads();
  upPump(kind);
}
function upSendOne(kind, it) {
  return new Promise(resolve => {
    const x = new XMLHttpRequest();
    x.open("POST", "/api/upload/" + kind + "?name=" + encodeURIComponent(it.file.name) + (kind === "photo" ? "&mtime=" + (it.file.lastModified || Date.now()) : ""));
    x.setRequestHeader("X-Panel", "1");
    it.xhr = x;
    x.upload.onprogress = e => {
      if (!e.lengthComputable) return;
      it.pct = Math.round(e.loaded * 100 / e.total);
      if (it.barEl) it.barEl.style.width = it.pct + "%";
      if (it.pctEl) put(it.pctEl, it.pct + "%");
    };
    x.onload = () => {
      let js = {};
      try { js = JSON.parse(x.responseText); } catch (e) {  }
      if (x.status === 401) { S = null; showLogin(); it.state = "fail"; it.msg = "Please log in again"; }
      else if (x.status >= 200 && x.status < 300) { it.state = kind === "photo" && js.status === "duplicate" ? "dup" : "done"; it.msg = js.saved && js.saved !== it.file.name ? "Saved as " + js.saved : ""; it.pct = 100; }
      else { it.state = "fail"; it.msg = js.error || ("Something went wrong (" + x.status + ")"); if (x.status === 409 && kind === "photo") loadUploads(); }
      resolve();
    };
    x.onerror = () => { it.state = "fail"; it.msg = "The connection was lost"; resolve(); };
    x.onabort = () => { it.state = "fail"; it.msg = "Stopped"; resolve(); };
    x.send(it.file);
  });
}
async function upPump(kind) {
  if (UPrun[kind]) return;
  UPrun[kind] = true;
  let sent = 0, bad = 0;
  try {
    for (;;) {
      const it = UPq[kind].find(x => x.state === "wait");
      if (!it) break;
      it.state = "send";
      drawUploads();
      await upSendOne(kind, it);
      delete it.xhr;
      if (it.state === "fail") bad++; else sent++;
      drawUploads();
    }
  } finally { UPrun[kind] = false; drawUploads(); }
  if (sent || bad) toast((UP_NAMES[kind]) + ": " + sent + " sent" + (bad ? ", " + bad + " failed (see the list)" : "") + ".", !!bad && !sent);
}
function upStop(kind) {
  for (const it of UPq[kind]) { if (it.state === "wait") { it.state = "fail"; it.msg = "Stopped"; } else if (it.xhr) it.xhr.abort(); }
  drawUploads();
}
function upClear(kind) { UPq[kind] = UPq[kind].filter(x => x.state === "wait" || x.state === "send"); drawUploads(); }

function upList(kind) {
  const q = UPq[kind];
  if (!q.length) return null;
  const done = q.filter(x => x.state === "done" || x.state === "dup").length, bad = q.filter(x => x.state === "fail").length, running = UPrun[kind];
  const sumEl = h("span", {}, done + " of " + q.length + " done" + (bad ? ", " + bad + " failed" : ""));
  return h("div", { class: "uplist" },
    h("div", { class: "row tight" }, sumEl, h("span", { class: "grow" }),
      running ? h("button", { class: "small danger", onclick: () => upStop(kind) }, "Stop") : h("button", { class: "small", onclick: () => upClear(kind) }, "Clear the List")),
    h("div", { class: "upitems" }, q.map(it => {
      it.barEl = null; it.pctEl = null;
      const label = { wait: "Waiting", send: "Sending", done: "Sent", dup: "Already in Immich", fail: it.msg }[it.state];
      it.pctEl = it.state === "send" ? h("span", { class: "muted small" }, it.pct + "%") : null;
      it.barEl = it.state === "send" ? h("i", { style: { width: it.pct + "%" } }) : null;
      return h("div", { class: "upit " + it.state },
        h("span", { class: "n" }, it.file.name),
        h("span", { class: "s" + (it.state === "fail" ? " badtext" : " muted") }, it.state === "send" ? it.pctEl : label + (it.state !== "fail" && it.msg ? " (" + it.msg + ")" : "")),
        it.state === "send" ? h("div", { class: "bar" }, it.barEl) : null);
    })));
}
function upZone(kind, accept, title, hint) {
  const input = h("input", { type: "file", multiple: true, accept, hidden: true, "aria-label": title, onchange: e => { const fs = [...e.target.files]; e.target.value = ""; if (fs.length) upAdd(kind, fs); } });
  const zone = h("div", { class: "upzone", role: "button", tabindex: "0", onclick: () => input.click(),
    onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } },
    ondragover: e => { e.preventDefault(); zone.classList.add("over"); }, ondragleave: () => zone.classList.remove("over"),
    ondrop: e => { e.preventDefault(); zone.classList.remove("over"); const fs = [...(e.dataTransfer ? e.dataTransfer.files : [])]; if (fs.length) upAdd(kind, fs); } },
  h("b", {}, title), h("span", { class: "muted small" }, hint), input);
  return zone;
}
function upPhotoBox() {
  const im = UP.immich;
  const key = h("input", { type: "password", autocomplete: "new-password", maxlength: 200, "aria-label": "Immich API key", placeholder: "Paste the Immich API key" });
  const msg = h("p", { class: "badtext small", role: "alert" });
  const save = async () => {
    put(msg, "");
    try { const r = await api("POST", "/api/upload/immich-key", { key: key.value }); toast(r.message); await loadUploads(); } catch (e) { put(msg, e.message); }
  };
  const link = "https://" + location.hostname + ":1002/user-settings?isOpen=api-keys";
  return h("div", { class: "upbox" },
    h("div", { class: "ph" }, h("div", { class: "pt" }, h("h3", {}, "Photos and Videos"), h("span", { class: "sub" }, "Go to Immich")),
      h("span", { class: "pill " + (!im.up ? "bad" : im.configured ? "ok" : "warn") }, !im.up ? "Immich is not answering" : im.configured ? "Ready" : "Needs a key")),
    im.configured ? upZone("photo", "image/*,video/*,.heic,.heif,.dng,.arw,.cr2,.cr3,.nef,.orf,.raf,.rw2,.mkv,.mts,.m2ts", "Drop photos and videos here, or press to choose",
      "Any size. Sent one at a time. Photos that Immich already has are skipped.") :
      h("div", { class: "upkey" },
        h("p", { class: "small" }, "Immich needs an API key before the panel can add photos. In Immich, open Account Settings, then API Keys, create a new key with upload permission and paste it here once. It is kept in a private file on the server and never shown again."),
        h("p", { class: "small" }, h("a", { href: link, target: "_blank", rel: "noopener" }, "Open Immich's API Keys page")),
        h("div", { class: "row tight" }, key, h("button", { class: "small primary", onclick: save }, "Save the Key")), msg),
    upList("photo"),
    im.configured ? h("button", { class: "small link", onclick: async () => { if (await confirmBox("Forget the Immich key?", "Uploads to Immich stop until a key is pasted again. The key itself stays in Immich.", "Forget It", true)) { try { await api("POST", "/api/upload/immich-key", { key: "" }); await loadUploads(); } catch (e) { fail(e); } } } }, "Forget the Immich key") : null);
}
function upSongBox() {
  const m = UP.music, usable = m.exists && m.writable;
  return h("div", { class: "upbox" },
    h("div", { class: "ph" }, h("div", { class: "pt" }, h("h3", {}, "Songs"), h("span", { class: "sub" }, "Saved in " + m.dir + " (Navidrome plays them, Downtify saves there too)")),
      h("span", { class: "pill " + (usable ? "ok" : "bad") }, usable ? "Ready" : m.exists ? "Cannot write there" : "Folder not found")),
    usable ? upZone("song", "audio/*,.flac,.m4a,.opus,.ogg,.wma,.alac,.aiff,.ape,.wv", "Drop songs here, or press to choose",
      "Saved as they are. A song with the same name is never replaced. Navidrome adds new songs at its next scan (within the hour).") :
      h("p", { class: "warntext small" }, m.exists ? "The panel is not allowed to write in that folder." : "That folder is not there. Is the music drive connected?"),
    !usable && m.exists ? h("p", { class: "muted small" }, "To allow it, run this once on the server. It only gives this user access to that folder; nothing else changes:") : null,
    !usable && m.exists ? h("code", { class: "upcmd" }, "sudo setfacl -m u:" + (m.user || "USER") + ":rwx " + upQuote(m.dir)) : null,
    typeof m.free === "number" ? h("span", { class: "muted small" }, humanBytes(m.free) + " free there") : null,
    upList("song"));
}
function upQuote(t) { return /^[A-Za-z0-9_\/.@%+=:,-]+$/.test(t) ? t : "'" + t.replace(/'/g, "'\\''") + "'"; }

function drawUploads() {
  const body = [h("div", { class: "ph" }, h("div", { class: "pt" }, h("h2", {}, "Upload"), h("span", { class: "sub" }, "Send photos and videos to Immich, and songs to the music folder, from this device. Keep this page open while files are being sent.")),
    h("button", { class: "small", disabled: upBusy(), onclick: loadUploads }, "Refresh"))];
  if (UPerr) body.push(h("p", { class: "badtext", role: "alert" }, UPerr), h("button", { class: "small", onclick: loadUploads }, "Try Again"));
  else if (!UP) body.push(h("p", { class: "muted" }, "Looking at Immich and the music folder..."));
  else body.push(h("div", { class: "upgrid" }, upPhotoBox(), upSongBox()));
  put(upBox, h("div", { class: "card" }, body));
}

let BK = null, BKerr = "", BKjob = null, BKtimer = 0, BKwas = "";
const bkBox = h("div", { class: "bk" });
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const BK_KIND = { local: "Drive", ssh: "Another computer", cloud: "Cloud" };
const BK_WORKING = { run: "Backing up...", dry: "Checking what would be copied...", restore: "Restoring..." };
const KEEP_LABELS = [["hourly", "Hourly"], ["daily", "Daily"], ["weekly", "Weekly"], ["monthly", "Monthly"], ["yearly", "Yearly"]];

function bkWhen(s, zone) {
  const m = /^(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)$/.exec(s || "");
  return m ? MONTHS[+m[2] - 1] + " " + (+m[3]) + ", " + m[4] + (zone ? " " + zone : "") : (s || "");
}
function bkDestText(d) {
  if (d.type === "ssh") return d.host + ":" + d.path;
  if (d.type === "cloud") return d.remote + ":" + (d.path || "");
  return d.path;
}
function bkKeepText(t) {
  if (t.dest.type === "cloud" || t.kind === "nightly") return "Files you delete or replace are kept for " + (t.keep.days || 30) + " days";
  const parts = KEEP_LABELS.filter(([k]) => t.keep[k] > 0).map(([k, l]) => t.keep[k] + " " + l.toLowerCase());
  return parts.length ? parts.join(", ") + " (newest version of each)" : "";
}
async function loadBackups() {
  try { BK = await api("GET", "/api/backup"); BKerr = ""; } catch (e) { BK = null; BKerr = e.message; }
  drawBackups();
}
function followBackup() {
  clearTimeout(BKtimer);
  const tick = async () => {
    if (!bkBox.isConnected) return;
    let j;
    try { j = await api("GET", "/api/backup/job"); } catch (e) { BKtimer = setTimeout(tick, 3000); return; }
    if (j.running) { BKjob = j; drawBackups(); BKtimer = setTimeout(tick, 1500); return; }
    BKjob = null;
    const said = BKwas;
    BKwas = "";
    await loadBackups();
    if (said || j.rc) toast(j.message || "Done.", !!j.rc);
  };
  tick();
}
async function bkStart(action, body) {
  if ((BKjob && BKjob.running) || DRbusy) return;
  try {
    await api("POST", "/api/backup/" + action, body);
    BKjob = { running: true, action, task: body.id, lines: [], pct: null };
    BKwas = action;
    drawBackups();
    followBackup();
  } catch (e) { fail(e); }
}
function bkBusy() { return !!(BKjob && BKjob.running) || !!(BK && BK.running) || !!DRbusy; }

