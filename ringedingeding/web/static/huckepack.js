/*
 * huckepack — the browser half of the hosting pattern.
 *
 * In the huckepack modes the durable copy of the database lives here, in the
 * visitor's browser, and the host holds it only in memory while a request runs.
 * This file is what makes that true:
 *
 *   - it keeps the SQLite file in IndexedDB and hands it to the server on load
 *     ("PUT /huckepack/session"), fetching it back after every change;
 *   - it holds the visitor's CALL-E key in localStorage, shows it masked, and
 *     sends it as a request header — never as a query parameter, never logged;
 *   - it exports and imports that database as a real .sqlite file, because a
 *     cleared browser would otherwise be an unannounced total loss;
 *   - it writes the receipt of a finished call as a file, into a folder the
 *     visitor picked once, or into the ordinary download folder.
 *
 * In "local" mode almost nothing here runs: no banner, no snapshot traffic.
 * Only the receipt download stays available, because it is useful there too.
 *
 * The file is a plain script, not a module, so it also loads from a page with a
 * strict script setup. The pure helpers are exported at the bottom for tests.
 */
(function (global) {
  "use strict";

  var SQLITE_MAGIC = "SQLite format 3\u0000";
  var IDB_NAME = "huckepack";
  var IDB_VERSION = 1;
  var STORE_META = "meta";
  var KEY_STORAGE = "huckepack.calle-key";
  var SESSION_STORAGE = "huckepack.session";
  var SNAPSHOT_RECORD = "snapshot";
  var FOLDER_RECORD = "receipt-folder";

  var WORDS = {
    de: {
      giftNotice: "Anrufe werden vom Betreiber gestellt. Ihre Daten bleiben in diesem Browser.",
      onlyHostNotice: "Ihr Schlüssel bleibt in Ihrem Browser. Ihre Daten auch.",
      stubNotice: "Dieser Betriebsmodus ist ein Platzhalter und nicht verfügbar.",
      keyLabel: "CALL-E-Schlüssel",
      keyPlaceholder: "Schlüssel einfügen",
      keySave: "Übernehmen",
      keyStored: "Hinterlegt:",
      keyMissing: "Kein Schlüssel hinterlegt — Live-Anrufe sind nicht möglich.",
      keyForget: "Vergessen",
      exportLabel: "Daten sichern",
      importLabel: "Daten einlesen",
      folderLabel: "Belegordner wählen",
      folderChosen: "Belegordner:",
      wipeLabel: "Daten löschen",
      wipeConfirm: "Alle in diesem Browser gespeicherten Daten löschen?",
      receiptSave: "Beleg speichern",
      receiptPdf: "Als PDF",
      receiptWritten: "Beleg gespeichert:",
      importDone: "Daten eingelesen. Die Seite wird neu geladen.",
      importBad: "Diese Datei ist keine Datenbank dieser Anwendung.",
      lossHint: "Gelöschte Browserdaten sind endgültig weg. Sichern Sie regelmäßig.",
      receiptTitle: "Beleg",
      receiptBusiness: "Betrieb",
      receiptWhen: "Zeitpunkt",
      receiptPrice: "Preis",
      receiptEta: "Dauer",
      receiptSummary: "Ergebnis",
      receiptTranscript: "Gesprächsverlauf",
      receiptThirdParty:
        "Hinweis: Der Gesprächsverlauf enthält Äußerungen der angerufenen Person.",
      receiptMasked: "Rufnummern sind maskiert."
    },
    en: {
      giftNotice: "Calls are paid for by the operator. Your data stays in this browser.",
      onlyHostNotice: "Your key stays in your browser. So does your data.",
      stubNotice: "This server mode is a placeholder and not available.",
      keyLabel: "CALL-E key",
      keyPlaceholder: "paste key",
      keySave: "Use it",
      keyStored: "Stored:",
      keyMissing: "No key stored — live calls are not possible.",
      keyForget: "Forget",
      exportLabel: "Back up data",
      importLabel: "Restore data",
      folderLabel: "Choose receipt folder",
      folderChosen: "Receipt folder:",
      wipeLabel: "Delete data",
      wipeConfirm: "Delete everything stored in this browser?",
      receiptSave: "Save receipt",
      receiptPdf: "As PDF",
      receiptWritten: "Receipt saved:",
      importDone: "Data restored. Reloading the page.",
      importBad: "That file is not a database of this application.",
      lossHint: "Cleared browser data is gone for good. Back up regularly.",
      receiptTitle: "Receipt",
      receiptBusiness: "Business",
      receiptWhen: "Time",
      receiptPrice: "Price",
      receiptEta: "Duration",
      receiptSummary: "Outcome",
      receiptTranscript: "Conversation",
      receiptThirdParty:
        "Note: the conversation contains statements by the person who was called.",
      receiptMasked: "Phone numbers are masked."
    }
  };

  // ---------------------------------------------------------------- pure part

  function words(lang) {
    return String(lang || "").toLowerCase().indexOf("de") === 0 ? WORDS.de : WORDS.en;
  }

  /* Second line of defence. The server masks before it sends; a receipt that
     is assembled from anything else still must not carry a dialable number. */
  function maskPhones(text) {
    return String(text == null ? "" : text).replace(
      /(\+?\d[\d\s/()-]{5,}\d)/g,
      function (match) {
        var digits = match.replace(/\D/g, "");
        if (digits.length < 6) return match;
        return "•••" + digits.slice(-3);
      }
    );
  }

  function twoDigits(value) {
    return (value < 10 ? "0" : "") + value;
  }

  function stamp(date) {
    var d = date || new Date();
    return (
      d.getFullYear() +
      "-" +
      twoDigits(d.getMonth() + 1) +
      "-" +
      twoDigits(d.getDate()) +
      "_" +
      twoDigits(d.getHours()) +
      twoDigits(d.getMinutes())
    );
  }

  /* A file name that sorts itself: date, time, business. Everything that could
     confuse a file system becomes a hyphen. */
  function receiptFilename(payload, extension, date) {
    var business = String((payload && payload.business) || "call")
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "call";
    return stamp(date) + "_" + business + "_beleg." + (extension || "txt");
  }

  function line(label, value) {
    return value === undefined || value === null || value === "" ? "" : label + ": " + value + "\n";
  }

  function receiptText(payload, lang) {
    var w = words(lang);
    var p = payload || {};
    var body = w.receiptTitle + "\n" + new Array(w.receiptTitle.length + 1).join("=") + "\n\n";
    body += line(w.receiptBusiness, p.business);
    body += line("", p.business_phone_masked ? p.business_phone_masked : "");
    body += line(w.receiptWhen, p.created_at);
    if (p.total_price_eur !== undefined && p.total_price_eur !== null) {
      body += line(w.receiptPrice, Number(p.total_price_eur).toFixed(2) + " EUR");
    }
    if (p.eta_minutes) body += line(w.receiptEta, p.eta_minutes + " min");
    body += line("ID", p.order_id);
    body += "\n" + w.receiptSummary + "\n" + maskPhones(p.summary || "") + "\n";
    if (p.transcript) {
      body += "\n" + w.receiptTranscript + "\n" + maskPhones(p.transcript) + "\n";
    }
    body += "\n" + w.receiptThirdParty + "\n" + w.receiptMasked + "\n";
    return body;
  }

  function maskKey(value) {
    if (!value) return "";
    return value.length <= 4 ? "••••" : "••••" + value.slice(-4);
  }

  function looksLikeSqlite(buffer) {
    var head = new Uint8Array(buffer.slice ? buffer.slice(0, 16) : buffer, 0, 16);
    for (var i = 0; i < SQLITE_MAGIC.length; i += 1) {
      if (head[i] !== SQLITE_MAGIC.charCodeAt(i)) return false;
    }
    return true;
  }

  /* A minimal single-font PDF, written by hand. A library would be a megabyte
     for six lines of layout, and the point of the receipt is that no one else
     is involved — least of all a CDN. */
  function receiptPdf(text) {
    var lines = String(text).split("\n");
    var wrapped = [];
    lines.forEach(function (raw) {
      var rest = raw;
      if (rest === "") wrapped.push("");
      while (rest.length > 92) {
        var cut = rest.lastIndexOf(" ", 92);
        if (cut < 40) cut = 92;
        wrapped.push(rest.slice(0, cut));
        rest = rest.slice(cut).replace(/^\s+/, "");
      }
      if (rest !== "") wrapped.push(rest);
    });

    var pages = [];
    for (var i = 0; i < wrapped.length; i += 58) pages.push(wrapped.slice(i, i + 58));
    if (pages.length === 0) pages = [[""]];

    function escape(value) {
      return value
        .replace(/\\/g, "\\\\")
        .replace(/\(/g, "\\(")
        .replace(/\)/g, "\\)")
        .replace(/[^\x00-\xff]/g, "?");
    }

    var objects = [];
    var kids = [];
    pages.forEach(function (pageLines, index) {
      kids.push(3 + index * 2 + " 0 R");
    });

    objects.push("<< /Type /Catalog /Pages 2 0 R >>");
    objects.push(
      "<< /Type /Pages /Kids [" + kids.join(" ") + "] /Count " + pages.length + " >>"
    );
    pages.forEach(function (pageLines, index) {
      var contentId = 4 + index * 2;
      objects.push(
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 " +
          (2 + pages.length * 2 + 1) +
          " 0 R >> >> /Contents " +
          contentId +
          " 0 R >>"
      );
      var stream = "BT /F1 10 Tf 12 TL 48 794 Td\n";
      pageLines.forEach(function (pageLine) {
        stream += "(" + escape(pageLine) + ") Tj T*\n";
      });
      stream += "ET";
      objects.push("<< /Length " + stream.length + " >>\nstream\n" + stream + "\nendstream");
    });
    objects.push("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");

    var pdf = "%PDF-1.4\n";
    var offsets = [0];
    objects.forEach(function (body, index) {
      offsets.push(pdf.length);
      pdf += index + 1 + " 0 obj\n" + body + "\nendobj\n";
    });
    var xref = pdf.length;
    pdf += "xref\n0 " + (objects.length + 1) + "\n0000000000 65535 f \n";
    for (var o = 1; o <= objects.length; o += 1) {
      pdf += ("0000000000" + offsets[o]).slice(-10) + " 00000 n \n";
    }
    pdf +=
      "trailer\n<< /Size " +
      (objects.length + 1) +
      " /Root 1 0 R >>\nstartxref\n" +
      xref +
      "\n%%EOF";

    var bytes = new Uint8Array(pdf.length);
    for (var b = 0; b < pdf.length; b += 1) bytes[b] = pdf.charCodeAt(b) & 0xff;
    return bytes;
  }

  function newSessionToken(randomSource) {
    var raw = new Uint8Array(24);
    (randomSource || global.crypto).getRandomValues(raw);
    var out = "";
    var alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    for (var i = 0; i < raw.length; i += 1) out += alphabet[raw[i] % 64];
    return out;
  }

  var pure = {
    words: words,
    maskPhones: maskPhones,
    maskKey: maskKey,
    receiptText: receiptText,
    receiptFilename: receiptFilename,
    receiptPdf: receiptPdf,
    looksLikeSqlite: looksLikeSqlite,
    newSessionToken: newSessionToken,
    stamp: stamp
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = pure;
  }
  if (typeof document === "undefined") {
    return; // running under a test runner, not in a page
  }

  // --------------------------------------------------------------- live part

  var state = {
    mode: null,
    session: null,
    words: words(document.documentElement.lang || "en"),
    folder: null,
    lastReceipt: null
  };

  function openIdb() {
    return new Promise(function (resolve, reject) {
      var request = global.indexedDB.open(IDB_NAME, IDB_VERSION);
      request.onupgradeneeded = function () {
        var db = request.result;
        if (!db.objectStoreNames.contains(STORE_META)) db.createObjectStore(STORE_META);
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
  }

  function idbGet(key) {
    return openIdb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE_META, "readonly");
        var request = tx.objectStore(STORE_META).get(key);
        request.onsuccess = function () { resolve(request.result); };
        request.onerror = function () { reject(request.error); };
      });
    });
  }

  function idbPut(key, value) {
    return openIdb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE_META, "readwrite");
        tx.objectStore(STORE_META).put(value, key);
        tx.oncomplete = function () { resolve(true); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function idbDelete(key) {
    return openIdb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE_META, "readwrite");
        tx.objectStore(STORE_META).delete(key);
        tx.oncomplete = function () { resolve(true); };
        tx.onerror = function () { reject(tx.error); };
      });
    });
  }

  function sessionToken() {
    if (state.session) return state.session;
    var stored = global.localStorage.getItem(SESSION_STORAGE);
    if (!stored) {
      stored = newSessionToken();
      global.localStorage.setItem(SESSION_STORAGE, stored);
    }
    state.session = stored;
    return stored;
  }

  function storedKey() {
    return global.localStorage.getItem(KEY_STORAGE) || "";
  }

  function headers() {
    var out = {};
    if (!state.mode) return out;
    out[state.mode.session_header] = sessionToken();
    if (state.mode.key_field) {
      var key = storedKey();
      if (key) out[state.mode.key_header] = key;
    }
    return out;
  }

  function browserStorage() {
    return state.mode && state.mode.storage === "browser";
  }

  function pushSnapshot() {
    return idbGet(SNAPSHOT_RECORD).then(function (buffer) {
      if (!buffer) return null;
      return fetch(state.mode.snapshot_url, {
        method: "PUT",
        headers: headers(),
        body: buffer
      });
    });
  }

  function pullSnapshot() {
    return fetch(state.mode.snapshot_url, { headers: headers() })
      .then(function (response) {
        if (!response.ok) return null;
        return response.arrayBuffer();
      })
      .then(function (buffer) {
        if (buffer && buffer.byteLength) return idbPut(SNAPSHOT_RECORD, buffer);
        return null;
      });
  }

  function download(bytes, filename, type) {
    var blob = new Blob([bytes], { type: type || "application/octet-stream" });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }

  /* Into the chosen folder if there is one, otherwise the ordinary download.
     Never a hard requirement: a browser without the folder picker loses the
     convenience, not the function. */
  function writeFile(bytes, filename, type) {
    if (!state.folder) {
      download(bytes, filename, type);
      return Promise.resolve(filename);
    }
    return state.folder
      .getFileHandle(filename, { create: true })
      .then(function (handle) { return handle.createWritable(); })
      .then(function (writable) {
        return writable.write(new Blob([bytes], { type: type })).then(function () {
          return writable.close();
        });
      })
      .then(function () { return filename; })
      .catch(function () {
        download(bytes, filename, type);
        return filename;
      });
  }

  function chooseFolder() {
    if (!global.showDirectoryPicker) {
      note(state.words.folderLabel + " — " + "not supported by this browser");
      return;
    }
    global
      .showDirectoryPicker({ id: "huckepack-receipts", mode: "readwrite" })
      .then(function (handle) {
        state.folder = handle;
        return idbPut(FOLDER_RECORD, handle);
      })
      .then(function () { render(); })
      .catch(function () { /* the visitor cancelled; nothing to repair */ });
  }

  function saveReceipt(asPdf) {
    var payload = state.lastReceipt;
    if (!payload) return;
    var text = receiptText(payload, document.documentElement.lang);
    if (asPdf) {
      var name = receiptFilename(payload, "pdf");
      writeFile(receiptPdf(text), name, "application/pdf").then(function () {
        note(state.words.receiptWritten + " " + name);
      });
      return;
    }
    var textName = receiptFilename(payload, "txt");
    writeFile(text, textName, "text/plain;charset=utf-8").then(function () {
      note(state.words.receiptWritten + " " + textName);
    });
  }

  function exportData() {
    idbGet(SNAPSHOT_RECORD).then(function (buffer) {
      var chain = buffer ? Promise.resolve(buffer) : pullSnapshot().then(function () {
        return idbGet(SNAPSHOT_RECORD);
      });
      chain.then(function (data) {
        if (!data) return;
        download(data, "ringedingeding_" + stamp() + ".sqlite", "application/vnd.sqlite3");
      });
    });
  }

  function importData(file) {
    file.arrayBuffer().then(function (buffer) {
      if (!looksLikeSqlite(buffer)) {
        note(state.words.importBad);
        return;
      }
      idbPut(SNAPSHOT_RECORD, buffer)
        .then(pushSnapshot)
        .then(function () {
          note(state.words.importDone);
          setTimeout(function () { global.location.reload(); }, 900);
        });
    });
  }

  function wipe() {
    if (!global.confirm(state.words.wipeConfirm)) return;
    fetch(state.mode.snapshot_url, { method: "DELETE", headers: headers() })
      .catch(function () { /* the session may already be gone */ })
      .then(function () { return idbDelete(SNAPSHOT_RECORD); })
      .then(function () {
        global.localStorage.removeItem(SESSION_STORAGE);
        state.session = null;
        global.location.reload();
      });
  }

  function note(message) {
    var box = document.getElementById("huckepack-note");
    if (!box) return;
    box.textContent = message;
    box.hidden = false;
  }

  function element(tag, attributes, text) {
    var node = document.createElement(tag);
    Object.keys(attributes || {}).forEach(function (name) {
      node.setAttribute(name, attributes[name]);
    });
    if (text) node.textContent = text;
    return node;
  }

  /* The bar brings its own few rules instead of editing the application's
     stylesheet — one file to add, one file to remove. */
  function ensureStyles() {
    if (document.getElementById("huckepack-style")) return;
    var style = element("style", { id: "huckepack-style" });
    style.textContent =
      ".huckepack-bar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;" +
      "padding:.5rem .9rem;font-size:.85rem;background:#f4f1ea;color:#2b2b2b;" +
      "border-bottom:1px solid rgba(0,0,0,.15)}" +
      ".huckepack-bar[hidden]{display:none}" +
      ".huckepack-btn{font:inherit;padding:.25rem .6rem;border:1px solid rgba(0,0,0,.3);" +
      "border-radius:.3rem;background:#fff;cursor:pointer}" +
      ".huckepack-hint,.huckepack-note{opacity:.75}" +
      ".huckepack-key{font-variant-numeric:tabular-nums}" +
      "#huckepack-key-input{font:inherit;padding:.25rem .4rem;border:1px solid rgba(0,0,0,.3);border-radius:.3rem}" +
      "@media (prefers-color-scheme: dark){.huckepack-bar{background:#232323;color:#eee}" +
      ".huckepack-btn,#huckepack-key-input{background:#2f2f2f;color:#eee;border-color:rgba(255,255,255,.3)}}";
    document.head.appendChild(style);
  }

  function render() {
    ensureStyles();
    var bar = document.getElementById("huckepack-bar");
    if (!bar) {
      bar = element("div", { id: "huckepack-bar", class: "huckepack-bar" });
      document.body.insertBefore(bar, document.body.firstChild);
    }
    bar.textContent = "";

    if (!state.mode || (state.mode.mode === "local" && !state.lastReceipt)) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;

    var w = state.words;
    if (state.mode.host_pays_calls) bar.appendChild(element("span", { class: "huckepack-notice" }, w.giftNotice));
    if (state.mode.key_field) bar.appendChild(element("span", { class: "huckepack-notice" }, w.onlyHostNotice));
    if (!state.mode.implemented) bar.appendChild(element("span", { class: "huckepack-notice" }, w.stubNotice));

    if (state.mode.key_field) {
      var key = storedKey();
      if (key) {
        bar.appendChild(element("span", { class: "huckepack-key" }, w.keyStored + " " + maskKey(key)));
        var forget = element("button", { type: "button", class: "huckepack-btn" }, w.keyForget);
        forget.addEventListener("click", function () {
          global.localStorage.removeItem(KEY_STORAGE);
          render();
        });
        bar.appendChild(forget);
      } else {
        var field = element("input", {
          type: "password",
          id: "huckepack-key-input",
          autocomplete: "off",
          spellcheck: "false",
          placeholder: w.keyPlaceholder,
          "aria-label": w.keyLabel
        });
        var save = element("button", { type: "button", class: "huckepack-btn" }, w.keySave);
        save.addEventListener("click", function () {
          var value = field.value.trim();
          if (!value) return;
          global.localStorage.setItem(KEY_STORAGE, value);
          field.value = "";
          render();
        });
        bar.appendChild(element("span", { class: "huckepack-notice" }, w.keyMissing));
        bar.appendChild(field);
        bar.appendChild(save);
      }
    }

    if (state.mode.export_import) {
      var exportButton = element("button", { type: "button", class: "huckepack-btn" }, w.exportLabel);
      exportButton.addEventListener("click", exportData);
      bar.appendChild(exportButton);

      var importInput = element("input", { type: "file", id: "huckepack-import", accept: ".sqlite,.db", hidden: "hidden" });
      importInput.addEventListener("change", function () {
        if (importInput.files && importInput.files[0]) importData(importInput.files[0]);
      });
      var importButton = element("button", { type: "button", class: "huckepack-btn" }, w.importLabel);
      importButton.addEventListener("click", function () { importInput.click(); });
      bar.appendChild(importButton);
      bar.appendChild(importInput);

      var wipeButton = element("button", { type: "button", class: "huckepack-btn" }, w.wipeLabel);
      wipeButton.addEventListener("click", wipe);
      bar.appendChild(wipeButton);
      bar.appendChild(element("span", { class: "huckepack-hint" }, w.lossHint));
    }

    var folderButton = element("button", { type: "button", class: "huckepack-btn" },
      state.folder ? w.folderChosen + " " + state.folder.name : w.folderLabel);
    folderButton.addEventListener("click", chooseFolder);
    bar.appendChild(folderButton);

    if (state.lastReceipt) {
      var receiptButton = element("button", { type: "button", class: "huckepack-btn" }, w.receiptSave);
      receiptButton.addEventListener("click", function () { saveReceipt(false); });
      bar.appendChild(receiptButton);
      var pdfButton = element("button", { type: "button", class: "huckepack-btn" }, w.receiptPdf);
      pdfButton.addEventListener("click", function () { saveReceipt(true); });
      bar.appendChild(pdfButton);
    }

    bar.appendChild(element("span", { id: "huckepack-note", class: "huckepack-note", hidden: "hidden" }));
  }

  function collectReceipt(root) {
    var node = (root || document).querySelector("#huckepack-receipt");
    if (!node) return;
    try {
      state.lastReceipt = JSON.parse(node.textContent);
    } catch (error) {
      return;
    }
    render();
    if (state.folder) saveReceipt(false);
  }

  function patchFetch() {
    var original = global.fetch;
    global.fetch = function (input, init) {
      var options = init || {};
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (url.indexOf("http") === 0 && url.indexOf(global.location.origin) !== 0) {
        return original.call(global, input, options);
      }
      var merged = new Headers(options.headers || (typeof input === "object" && input.headers) || {});
      var extra = headers();
      Object.keys(extra).forEach(function (name) {
        if (!merged.has(name)) merged.set(name, extra[name]);
      });
      var next = {};
      Object.keys(options).forEach(function (name) { next[name] = options[name]; });
      next.headers = merged;
      return original.call(global, input, next);
    };
  }

  function boot() {
    fetch("/huckepack/mode")
      .then(function (response) { return response.json(); })
      .then(function (mode) {
        state.mode = mode;
        patchFetch();

        document.body.addEventListener("htmx:configRequest", function (event) {
          var extra = headers();
          Object.keys(extra).forEach(function (name) {
            event.detail.headers[name] = extra[name];
          });
        });

        document.body.addEventListener("htmx:afterSwap", function (event) {
          collectReceipt(event.detail.elt || document);
          if (browserStorage()) pullSnapshot();
        });

        return idbGet(FOLDER_RECORD)
          .then(function (handle) { if (handle) state.folder = handle; })
          .catch(function () { /* no folder remembered */ })
          .then(function () {
            if (!browserStorage()) return null;
            return pushSnapshot();
          });
      })
      .then(function () {
        collectReceipt(document);
        render();
      })
      .catch(function () { /* an installation without the endpoint behaves as before */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  global.huckepack = pure;
})(typeof globalThis !== "undefined" ? globalThis : this);
