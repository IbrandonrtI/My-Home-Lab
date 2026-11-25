function bkStatus(t) {
  const mine = BKjob && BKjob.running && BKjob.task === t.id;
  if (mine) return h("span", { class: "pill warn" }, BK_WORKING[BKjob.action] || "Working...");
  if (t.running) return h("span", { class: "pill warn" }, "Running now");
  if (!t.enabled) return h("span", { class: "pill dim" }, "Off");
  if (t.waiting) return h("span", { class: "pill warn" }, "Waiting for a backup drive");
  if (!t.last) return h("span", { class: "pill dim" }, "Never run");
  return t.last.result === "OK" ? h("span", { class: "pill ok" }, "Last run OK, " + bkWhen(t.last.when, t.last.zone)) : h("span", { class: "pill bad" }, "Last run failed, " + bkWhen(t.last.when, t.last.zone));
}
function bkTask(t) {
  const mine = BKjob && BKjob.running && BKjob.task === t.id ? BKjob : null;
  const off = bkBusy();
  const nightly = t.kind === "nightly";
  const last = t.last;
  const rows = [
    h("div", { class: "bkline" }, h("span", { class: "k" }, "From"), h("span", { class: "v" }, t.source)),
    h("div", { class: "bkline" }, h("span", { class: "k" }, "To"), h("span", { class: "v" }, bkDestText(t.dest))),
    h("div", { class: "bkline" }, h("span", { class: "k" }, "When"), h("span", { class: "v" }, t.schedule_text + (t.schedule_zone && t.schedule.kind !== "hourly" ? " (server time, " + t.schedule_zone + ")" : "") + (t.enabled && t.next_run && !t.waiting ? ". Next: " + bkWhen(t.next_run, t.next_zone) : ""))),
    t.waiting ? h("div", { class: "bkline" }, h("span", { class: "k" }, "Status"), h("span", { class: "v" }, "There is no drive in the Backup pool, so nothing is copied. The backup runs on its schedule once a backup drive is added.")) : null,
    bkKeepText(t) ? h("div", { class: "bkline" }, h("span", { class: "k" }, "Keeps"), h("span", { class: "v" }, bkKeepText(t))) : null,
    last && typeof last.size_bytes === "number" ? h("div", { class: "bkline" }, h("span", { class: "k" }, "Space used"), h("span", { class: "v" }, humanBytes(last.size_bytes) + " in all versions together")) : null,
    last && last.message ? h("div", { class: "bkline" }, h("span", { class: "k" }, "Last run"), h("span", { class: "v " + (last.result === "OK" ? "" : "badtext") }, last.message)) : null];
  const prog = mine ? h("div", { class: "bkprog" },
    h("div", { class: "bar" + (typeof mine.pct === "number" ? "" : " wait") }, h("i", { style: { width: (typeof mine.pct === "number" ? mine.pct : 100) + "%" } })),
    h("span", { class: "muted small" }, (mine.lines || []).slice(-1)[0] || BK_WORKING[mine.action])) : null;
  return h("div", { class: "bkt" + (t.enabled ? "" : " isoff") },
    h("div", { class: "ph" },
      h("div", { class: "pt" }, h("h3", {}, t.name), h("span", { class: "sub" }, nightly ? "The nightly backup of your files" : BK_KIND[t.dest.type])),
      bkStatus(t)),
    h("div", { class: "bklines" }, rows),
    prog,
    h("div", { class: "row tight" },
      h("button", { class: "small primary", disabled: off, onclick: () => bkStart("run", { id: t.id }) }, "Run Now"),
      nightly ? null : h("button", { class: "small", disabled: off, onclick: () => bkStart("dry", { id: t.id }), title: "Shows how much would be copied. Nothing is changed" }, "Preview"),
      h("button", { class: "small", disabled: off, onclick: () => bkRestore(t) }, "Restore"),
      t.dest.type === "local" ? h("button", { class: "small", onclick: () => bkDownload(t), title: "Download files or folders of this backup to this device (for when there is no other way to get the files)" }, "Download") : null,
      h("button", { class: "small", onclick: () => bkEdit(t) }, "Edit"),
      h("button", { class: "small", onclick: () => bkToggle(t) }, t.enabled ? "Turn Off" : "Turn On"),
      nightly ? null : h("button", { class: "small danger", disabled: off, onclick: () => bkDelete(t) }, "Delete")));
}
function drawBackups() {
  const off = bkBusy();
  const body = [h("div", { class: "ph" },
    h("div", { class: "pt" }, cardHead("Backups", "now"), h("span", { class: "sub" }, "Copy a folder to a drive, another computer or the cloud on a schedule. Every run keeps a version that can be restored.")),
    h("button", { class: "small", onclick: loadBackups }, "Refresh"),
    h("button", { class: "small primary", disabled: !BK || off, onclick: () => bkEdit(null) }, "New Backup Task"))];
  if (BKerr) body.push(h("p", { class: "badtext", role: "alert" }, BKerr), h("button", { class: "small", onclick: loadBackups }, "Try Again"));
  else if (!BK) body.push(h("p", { class: "muted" }, "Looking at the backups..."));
  else body.push(h("div", { class: "bkl" }, BK.tasks.map(bkTask)));
  put(bkBox, h("div", { class: "card" }, body));
}
async function bkToggle(t) {
  try { await api("POST", "/api/backup/toggle", { id: t.id, enabled: !t.enabled }); await loadBackups(); } catch (e) { fail(e); }
}
function bkDelete(t) {
  const d = h("dialog", {}, h("h2", {}, "Delete " + t.name + "?"),
    h("p", {}, "The task stops running. Choose what happens to the copies it already made."),
    h("p", { class: "muted small" }, "Your original files are never changed."),
    h("div", { class: "actions" },
      h("button", { onclick: () => d.close() }, "Cancel"),
      h("button", { onclick: () => go("keep") }, "Delete Task, Keep Copies"),
      h("button", { class: "danger", onclick: () => go("erase") }, "Delete Task and Erase Copies")));
  const go = async data => {
    d.close();
    try { await api("POST", "/api/backup/delete", { id: t.id, data }); toast("The task was deleted."); await loadBackups(); } catch (e) { fail(e); }
  };
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
}

function bkNew() {
  return { name: "", enabled: true, kind: "versions", source: "", exclude: [], dest: { type: "local", path: "" }, schedule: { kind: "daily", time: "02:00" }, keep: { hourly: 0, daily: 7, weekly: 4, monthly: 6, yearly: 1 } };
}
function bkField(label, input, hint) { return h("div", { class: "field" }, h("label", {}, label), input, hint ? h("span", { class: "hint" }, hint) : null); }
function bkNum(f, k, label) {
  return h("div", { class: "field bknum" }, h("label", {}, label), h("input", { type: "number", min: 0, max: 90, value: f.keep[k] || 0, "aria-label": label + " versions to keep", oninput: e => { f.keep[k] = Math.max(0, parseInt(e.target.value, 10) || 0); } }));
}
// The dialog to create or change a backup task.
function bkEdit(t) {
  const f = t ? clone(t) : bkNew();
  const nightly = f.kind === "nightly";
  const err = h("p", { class: "badtext", role: "alert" });
  const where = h("div", {});
  const when = h("div", {});
  const keep = h("div", {});
  let keyInfo = null;
  const setErr = m => { put(err, m || ""); };
  const drawWhere = () => {
    const d = f.dest;
    const pick = BK.drives.length ? h("div", { class: "field" }, h("select", { "aria-label": "Choose a connected drive", onchange: e => { if (e.target.value) { d.path = e.target.value.replace(/\/$/, "") + "/backups"; drawWhere(); } } },
      h("option", { value: "" }, "Choose a connected drive to fill in the folder..."),
      BK.drives.map(x => h("option", { value: x.path }, x.path + "  (" + humanBytes(x.free) + " free of " + humanBytes(x.size) + ")")))) : null;
    const types = h("select", { "aria-label": "Where the copies go", onchange: e => {
      const ty = e.target.value;
      f.dest = ty === "local" ? { type: "local", path: "" } : ty === "ssh" ? { type: "ssh", host: "", path: "" } : { type: "cloud", remote: (BK.cloud.remotes || [])[0] || "", path: "homelab-backups" };
      f.keep = ty === "cloud" ? { days: 30 } : { hourly: 0, daily: 7, weekly: 4, monthly: 6, yearly: 1 };
      drawWhere(); drawKeep();
    } }, Object.entries(BK_KIND).map(([k, v]) => h("option", { value: k, selected: d.type === k }, k === "local" ? "A drive connected to this machine" : k === "ssh" ? "Another computer (over Tailscale or the network)" : "The cloud (Google Drive, Backblaze, ...)")));
    const kids = [bkField("Where should the copies go?", types)];
    if (d.type === "local") {
      kids.push(pick, bkField("Folder for the copies", h("input", { type: "text", value: d.path, placeholder: "/mnt/backup/homelab-backups", maxlength: 300, oninput: e => { d.path = e.target.value.trim(); } }),
        "Each task gets its own folder here, with one dated folder per version. It must be on a connected drive."));
    } else if (d.type === "ssh") {
      kids.push(bkField("The other computer", h("input", { type: "text", value: d.host, placeholder: "user@computer.your-tailnet.ts.net", maxlength: 300, oninput: e => { d.host = e.target.value.trim(); } }), "The login account. Add :2222 for another port."),
        bkField("Folder on that computer", h("input", { type: "text", value: d.path, placeholder: "/home/user/homelab-backups", maxlength: 300, oninput: e => { d.path = e.target.value.trim(); } })),
        h("div", { class: "row tight" },
          h("button", { class: "small", onclick: showKey }, "Show the Key"),
          h("button", { class: "small", onclick: testSsh }, "Test the Connection")),
        keyInfo || (BK.ssh.key ? null : h("p", { class: "muted small" }, "First press Show the Key, add it on the other computer, then test the connection.")),
        h("p", { class: "muted small" }, "It needs rsync installed and must accept this machine's key."));
    } else {
      const remotes = BK.cloud.remotes || [];
      if (!BK.cloud.installed) kids.push(h("p", { class: "warntext" }, "The cloud tool (rclone) is not installed on this machine. Install it first: sudo apt install rclone"));
      kids.push(remotes.length ? bkField("Cloud account", h("select", { "aria-label": "Cloud account", onchange: e => { d.remote = e.target.value; } }, remotes.map(r => h("option", { value: r, selected: d.remote === r }, r)))) :
        h("p", { class: "muted" }, "No cloud account is set up yet. Add a Backblaze B2 or S3 account below, or set up Google Drive, OneDrive, Dropbox and others once in the Terminal card with: sudo rclone config (it asks you to log in through your browser). Then press Refresh."),
        bkField("Folder in the cloud", h("input", { type: "text", value: d.path, maxlength: 200, oninput: e => { d.path = e.target.value.trim().replace(/^\/+/, ""); } })),
        cloudAdd(),
        h("p", { class: "muted small" }, "The cloud keeps the latest copy plus the older versions of files that changed or were deleted, for the chosen number of days. It does not keep a full copy for every run."));
    }
    put(where, kids);
  };
  const cloudAdd = () => {
    const v = { type: "b2", name: "", key_id: "", key: "", endpoint: "" };
    const note = h("p", { class: "muted small" });
    return h("details", { class: "bkmore" }, h("summary", {}, "Add a Backblaze B2 or S3 account"),
      bkField("Kind", h("select", { "aria-label": "Kind of account", onchange: e => { v.type = e.target.value; } }, h("option", { value: "b2" }, "Backblaze B2"), h("option", { value: "s3" }, "S3 (Amazon or compatible)"))),
      bkField("Name for this account", h("input", { type: "text", maxlength: 32, placeholder: "b2", oninput: e => { v.name = e.target.value.trim(); } })),
      bkField("Key ID", h("input", { type: "text", autocomplete: "off", maxlength: 200, oninput: e => { v.key_id = e.target.value.trim(); } })),
      bkField("Application Key", h("input", { type: "password", autocomplete: "new-password", maxlength: 200, oninput: e => { v.key = e.target.value.trim(); } }), "It is saved in a file only the administrator of this machine can read."),
      bkField("Address of the service (S3 only, optional)", h("input", { type: "text", maxlength: 200, placeholder: "https://s3.example.com", oninput: e => { v.endpoint = e.target.value.trim(); } })),
      note,
      h("button", { class: "small", onclick: async () => {
        try {
          await api("POST", "/api/backup/cloud-add", v);
          await loadBackups();
          f.dest.remote = v.name;
          drawWhere();
        } catch (e) { put(note, e.message); note.className = "badtext small"; }
      } }, "Add the Account"));
  };
  const showKey = async () => {
    try {
      const r = await api("POST", "/api/backup/sshkey", {});
      const line = r.key;
      const box = h("textarea", { readonly: true, rows: 3, "aria-label": "The public key", onfocus: e => e.target.select() }, line);
      keyInfo = h("div", { class: "bkkey" }, h("p", { class: "small" }, "Add this line to the file ~/.ssh/authorized_keys of the account you log in with on the other computer:"), box,
        h("button", { class: "small", onclick: async () => { try { await navigator.clipboard.writeText(line); toast("Copied."); } catch (e) { box.focus(); box.select(); } } }, "Copy"));
      drawWhere();
    } catch (e) { setErr(e.message); }
  };
  const testSsh = async () => {
    setErr("");
    try { const r = await api("POST", "/api/backup/sshtest", { host: f.dest.host }); toast("It works: " + r.message); } catch (e) { setErr(e.message); }
  };
  const drawWhen = () => {
    const s = f.schedule;
    const kind = h("select", { "aria-label": "How often", onchange: e => {
      const k = e.target.value;
      f.schedule = k === "hourly" ? { kind: k, minute: 0 } : k === "weekly" ? { kind: k, dow: 6, time: s.time || "02:00" } : k === "monthly" ? { kind: k, dom: 1, time: s.time || "02:00" } : k === "days" ? { kind: k, every: 3, time: s.time || "02:00" } : { kind: k, time: s.time || "02:00" };
      drawWhen();
    } }, [["hourly", "Every hour"], ["daily", "Every day"], ["days", "Every few days"], ["weekly", "Every week"], ["monthly", "Every month"]].map(([k, l]) => h("option", { value: k, selected: s.kind === k }, l)));
    const kids = [kind];
    if (s.kind === "days") kids.push(h("label", { class: "inl" }, "every ", h("input", { type: "number", min: 2, max: 30, value: s.every || 3, "aria-label": "Number of days between backups",
      oninput: e => { s.every = Math.max(2, Math.min(30, parseInt(e.target.value, 10) || 3)); delete s.from; } }), " days"));
    if (s.kind === "weekly") kids.push(h("select", { "aria-label": "Day of the week", onchange: e => { s.dow = +e.target.value; } }, WEEKDAYS.map((n, i) => h("option", { value: i, selected: s.dow === i }, n))));
    if (s.kind === "monthly") kids.push(h("select", { "aria-label": "Day of the month", onchange: e => { s.dom = +e.target.value; } }, Array.from({ length: 28 }, (_, i) => h("option", { value: i + 1, selected: s.dom === i + 1 }, "Day " + (i + 1)))));
    if (s.kind === "hourly") kids.push(h("label", { class: "inl" }, "at minute ", h("input", { type: "number", min: 0, max: 59, value: s.minute || 0, "aria-label": "Minute of the hour", oninput: e => { s.minute = Math.max(0, Math.min(59, parseInt(e.target.value, 10) || 0)); } })));
    else kids.push(h("label", { class: "inl" }, "at ", h("input", { type: "time", value: s.time || "02:00", "aria-label": "Time of day", oninput: e => { s.time = e.target.value || "02:00"; } }), BK && BK.server_zone ? h("span", { class: "muted" }, " (server time, " + BK.server_zone + ")") : ""));
    put(when, h("div", { class: "field" }, h("label", {}, "When should it run?"), h("div", { class: "row tight" }, kids)));
  };
  const drawKeep = () => {
    if (f.dest.type === "cloud") {
      put(keep, bkField("How long to keep older versions of changed files", h("input", { type: "number", min: 1, max: 3650, value: (f.keep.days || 30), "aria-label": "Days", oninput: e => { f.keep = { days: Math.max(1, parseInt(e.target.value, 10) || 30) }; } }), "In days. The latest copy always stays."));
      return;
    }
    put(keep, h("div", { class: "field" }, h("label", {}, "Versions to keep"), h("div", { class: "row tight bkkeep" }, KEEP_LABELS.map(([k, l]) => bkNum(f, k, l))),
      h("span", { class: "hint" }, "For example, Daily 7 keeps the newest version of each of the last 7 days. Older versions are removed automatically. Versions share the files that did not change, so they take little extra space.")));
  };
  const form = [h("h2", {}, t ? "Edit " + t.name : "New Backup Task"),
    bkField("Name", h("input", { type: "text", value: f.name, maxlength: 40, placeholder: "My documents", oninput: e => { f.name = e.target.value; } }))];
  const FOLDER_NAMES = { immich: ["Photos and videos", "Immich"], nextcloud: ["Files and documents", "Nextcloud"], music: ["Music", "Navidrome and Downtify"], videos: ["Videos", "MeTube"], movies: ["Movies", "Jellyfin"], shows: ["TV shows", "Jellyfin"] };
  const folderName = n => (FOLDER_NAMES[n] || [n, ""])[0];
  const folders = h("div", { class: "field bkfolders" });
  const drawFolders = () => {
    const skip = new Set(f.skip || []), names = f.folders || [];
    const left = names.filter(n => skip.has(n));
    const tiles = names.map(n => h("label", { class: "bktile" },
      h("input", { type: "checkbox", checked: !skip.has(n), "aria-label": "Back up " + folderName(n),
        onchange: e => { if (e.target.checked) skip.delete(n); else skip.add(n); f.skip = names.filter(x => skip.has(x)); drawFolders(); } }),
      h("span", { class: "bkfname" }, h("b", {}, folderName(n)), h("small", {}, (FOLDER_NAMES[n] || [])[1] || "Folder"))));
    put(folders, h("label", {}, "What to back up"),
      names.length ? h("div", { class: "bktiles" }, tiles) : h("p", { class: "muted" }, "No folders found. The whole pool is backed up."),
      left.length === names.length && names.length ? h("p", { class: "warntext bknote" }, "Keep at least one folder ticked.") : null,
      left.length ? h("p", { class: "warntext bknote" }, "Not backed up: " + left.map(folderName).join(", ") + ". They cannot be restored if a drive fails.") : null,
      h("span", { class: "hint" }, "Settings and the Nextcloud database are always included."));
  };
  if (nightly) {
    drawFolders();
    form.push(h("p", { class: "muted bkintro" }, "Copies " + f.source + " to " + f.dest.path + "."), folders, when,
      bkField("Keep older versions (days)",
        h("input", { type: "number", min: 1, max: 3650, value: (f.keep && f.keep.days) || 30, "aria-label": "Days to keep deleted or replaced files", oninput: e => { f.keep = { days: Math.max(1, Math.min(3650, parseInt(e.target.value, 10) || 30)) }; } }),
        "Deleted or replaced files are kept this long. More days use more space."));
  } else {
    form.push(bkField("Folder to back up", h("input", { type: "text", value: f.source, placeholder: "/mnt/storage/photos", maxlength: 300, list: "bk-src", oninput: e => { f.source = e.target.value.trim(); } }), "Full path of the folder on this machine."),
      h("datalist", { id: "bk-src" }, BK.drives.map(x => h("option", { value: x.path }))),
      where, when, keep,
      h("details", { class: "bkmore" }, h("summary", {}, "Skip some files (optional)"),
        h("div", { class: "field" }, h("textarea", { rows: 3, "aria-label": "Files and folders to skip, one per line", placeholder: "*.tmp\ncache/", value: (f.exclude || []).join("\n"), oninput: e => { f.exclude = e.target.value.split("\n").map(x => x.trim()).filter(Boolean); } }),
          h("span", { class: "hint" }, "One pattern per line, for example *.tmp or cache/. Skipped files are not copied."))));
  }
  const d = h("dialog", { class: "wide dcard bkdlg" }, form, err,
    h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Cancel"),
      h("button", { class: "primary", onclick: async () => {
        setErr("");
        const out = { id: f.id, name: f.name, enabled: f.enabled, schedule: f.schedule };
        if (!nightly) Object.assign(out, { source: f.source, exclude: f.exclude, dest: f.dest, keep: f.keep });
        else { out.keep = { days: (f.keep && f.keep.days) || 30 }; out.skip = f.skip || []; }
        if (!t) delete out.id;
        try { await api("POST", "/api/backup/save", out); d.close(); toast("Saved."); await loadBackups(); } catch (e) { setErr(e.message); }
      } }, "Save")));
  if (!nightly) { drawWhere(); drawKeep(); }
  drawWhen();
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
}

// The download dialog: look inside a backup and save a file, or a folder as a .zip, to this device.
async function bkDownload(t) {
  let versions;
  try { versions = (await api("GET", "/api/backup/versions?id=" + encodeURIComponent(t.id))).versions; } catch (e) { fail(e); return; }
  if (!versions.length) { toast("There is nothing to download yet. Run the backup first.", true); return; }
  let ver = versions[0], path = [];
  const list = h("div", { class: "bklist" });
  const crumbs = h("div", { class: "bkcrumbs" });
  const note = h("p", { class: "muted small" });
  const err = h("p", { class: "badtext", role: "alert" });
  const rel = () => path.join("/") || ".";
  const go = async p => {
    path = p;
    put(err, "");
    let entries = [];
    try { entries = (await api("GET", "/api/backup/browse?id=" + encodeURIComponent(t.id) + "&v=" + encodeURIComponent(ver.name) + "&rel=" + encodeURIComponent(rel()))).entries; } catch (e) { put(err, e.message); }
    put(crumbs, h("button", { class: "small link", onclick: () => go([]) }, "Top"), path.map((n, i) => [" / ", h("button", { class: "small link", onclick: () => go(path.slice(0, i + 1)) }, n)]));
    put(note, ver.kind === "changes" ? "This version holds only the files that were replaced or deleted at that time." : "");
    put(list, entries.length ? entries.map(e => h("div", { class: "item" },
      h("div", { class: "txt" }, e.type === "dir" ? h("button", { class: "small link", onclick: () => go(path.concat(e.name)) }, "\uD83D\uDCC1 " + e.name) : h("b", {}, e.name), e.type === "file" ? h("span", {}, humanBytes(e.size)) : null),
      h("button", { class: "small", onclick: () => fetchOut(path.concat(e.name).join("/"), e.type === "dir" ? "zip" : "file") }, e.type === "dir" ? "Download .zip" : "Download"))) : h("p", { class: "muted" }, "Nothing in this folder."));
  };
  const fetchOut = async (r, mode) => {
    put(err, "");
    try {
      const j = await api("POST", "/api/backup/dltoken", { id: t.id, v: ver.name, rel: r, mode });
      const a = h("a", { href: j.url, target: "_blank", rel: "noopener" });
      document.body.append(a); a.click(); a.remove();
      toast(mode === "zip" ? "The .zip is being prepared. A large folder takes a while: the download starts immediately and runs until it is done." : "The download has started.");
    } catch (e) { put(err, e.message); }
  };
  const d = h("dialog", { class: "wide dcard bkdlg" }, h("h2", {}, "Download from " + t.name),
    h("p", { class: "muted small" }, "Save a file, or a folder as one .zip, to this device. A large .zip shows no size while it downloads. Keep this page open until the browser says it is done."),
    h("div", { class: "field" }, h("label", {}, "Which version?"),
      h("select", { "aria-label": "Version", onchange: e => { ver = versions.find(v => v.name === e.target.value); go([]); } }, versions.map(v => h("option", { value: v.name }, v.label)))),
    note, crumbs, list, err,
    h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Close"), h("button", { class: "primary", onclick: () => fetchOut(rel(), "zip") }, "Download This Folder as .zip")));
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  go([]);
}

// The restore dialog: pick a version, look inside, and bring back a file or a folder.
async function bkRestore(t) {
  let versions;
  try { versions = (await api("GET", "/api/backup/versions?id=" + encodeURIComponent(t.id))).versions; } catch (e) { fail(e); return; }
  if (!versions.length) { toast("There is nothing to restore yet. Run the backup first.", true); return; }
  let ver = versions[0], path = [], target = "folder";
  const list = h("div", { class: "bklist" });
  const crumbs = h("div", { class: "bkcrumbs" });
  const note = h("p", { class: "muted small" });
  const err = h("p", { class: "badtext", role: "alert" });
  const rel = () => path.join("/") || ".";
  const go = async p => {
    path = p;
    put(err, "");
    let entries = [];
    try { entries = (await api("GET", "/api/backup/browse?id=" + encodeURIComponent(t.id) + "&v=" + encodeURIComponent(ver.name) + "&rel=" + encodeURIComponent(rel()))).entries; } catch (e) { put(err, e.message); }
    put(crumbs, h("button", { class: "small link", onclick: () => go([]) }, "Top"), path.map((n, i) => [" / ", h("button", { class: "small link", onclick: () => go(path.slice(0, i + 1)) }, n)]));
    put(note, ver.kind === "changes" ? "This version holds only the files that were replaced or deleted at that time." : "");
    put(list, entries.length ? entries.map(e => h("div", { class: "item" },
      h("div", { class: "txt" }, e.type === "dir" ? h("button", { class: "small link", onclick: () => go(path.concat(e.name)) }, "\uD83D\uDCC1 " + e.name) : h("b", {}, e.name), e.type === "file" ? h("span", {}, humanBytes(e.size)) : null),
      h("button", { class: "small", onclick: () => doRestore(path.concat(e.name).join("/")) }, "Restore"))) : h("p", { class: "muted" }, "Nothing in this folder."));
  };
  const doRestore = async r => {
    if (target === "original" && !(await confirmBox("Replace the originals with the restored files?", "Files with the same name in " + t.source + " are replaced by this version. The replaced files are kept in the _restored folder next to them.", "Replace the Files", true))) return;
    d.close();
    bkStart("restore", { id: t.id, version: ver.name, rel: r, target });
  };
  const d = h("dialog", { class: "wide dcard bkdlg" }, h("h2", {}, "Restore from " + t.name),
    h("div", { class: "field" }, h("label", {}, "Which version?"),
      h("select", { "aria-label": "Version", onchange: e => { ver = versions.find(v => v.name === e.target.value); go([]); } }, versions.map(v => h("option", { value: v.name }, v.label)))),
    note, crumbs, list,
    h("div", { class: "field" }, h("label", {}, "Where should the files go?"),
      h("label", { class: "inl" }, h("input", { type: "radio", name: "bk-target", checked: true, onchange: () => { target = "folder"; } }), " Into a new folder next to the originals (nothing is replaced)"),
      h("label", { class: "inl" }, h("input", { type: "radio", name: "bk-target", onchange: () => { target = "original"; } }), " Over the original files (replaced files are kept)")),
    err,
    h("div", { class: "actions" }, h("button", { onclick: () => d.close() }, "Close"), h("button", { class: "primary", onclick: () => doRestore(rel()) }, "Restore Everything Shown Here")));
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  go([]);
}

