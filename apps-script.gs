/** FORMA — client intake backend.
 *
 *  REPLACE the contents of the ONE file already in your Apps Script project
 *  (normally Code.gs). Do not add this as a second file: Apps Script merges
 *  every .gs file into one scope, so a second copy declares SHEET_ID twice and
 *  nothing runs at all — every request answers with a syntax error instead.
 */

const SHEET_ID = 'PASTE_YOUR_SHEET_ID_HERE';
const ACCESS_CODE = 'FORMA-2026';   // invent your own, keep it private
const MAX_ROWS = 500;               // how many recent clients the console loads
const PHOTO_DIR = 'FORMA client photos';   // created in your Drive on the first upload
const PHOTO_MAX = 4000000;          // base64 characters, about 3MB of image

// Bump nothing here — it is a stamp, so you can prove which version is really
// live. Editing the code changes nothing until you Deploy again, and that is
// the single most common reason photos stop arriving.
const BUILD = '2026-08-18-photos';

function sheet_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  return ss.getSheetByName('Clients') || ss.insertSheet('Clients');
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o))
    .setMimeType(ContentService.MimeType.JSON);
}

// header row, extended on the right if this key has never been seen
function head_(sh) {
  if (sh.getLastRow() === 0) sh.appendRow(['submittedAt', 'fullName', 'phone']);
  return sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
}

function colOf_(sh, head, key) {
  var i = head.indexOf(key);
  if (i === -1) { head.push(key); i = head.length - 1; sh.getRange(1, i + 1).setValue(key); }
  return i + 1;
}

// which row holds this submission, or 0
function rowOf_(sh, head, id) {
  const idCol = head.indexOf('submissionId') + 1;
  const rows = sh.getLastRow();
  if (idCol < 1 || !id || rows < 2) return 0;
  const seen = sh.getRange(2, idCol, rows - 1, 1).getValues();
  for (var i = 0; i < seen.length; i++) {
    if (String(seen[i][0]) === String(id)) return i + 2;
  }
  return 0;
}

// one folder for everyone, one subfolder per client
function folder_(name) {
  const it = DriveApp.getFoldersByName(PHOTO_DIR);
  const root = it.hasNext() ? it.next() : DriveApp.createFolder(PHOTO_DIR);
  const sub = root.getFoldersByName(name);
  return sub.hasNext() ? sub.next() : root.createFolder(name);
}

// A photo from the form. doPost is deliberately unauthenticated — the form is
// public — so a file is only accepted when its submissionId is already a row in
// the sheet. Without that check anyone holding the URL could fill your Drive.
//
// The row is waited for rather than demanded. The form cannot tell when this
// script finished appending it — Google answers the submission with a redirect
// the browser usually refuses to let the page read — so the photos leave at the
// same moment as the answers. Refusing them outright threw all four away.
function photo_(obj) {
  const slots = { front: 1, back: 1, side: 1, inbody: 1 };
  const slot = String(obj.slot || '');
  if (!slots[slot]) return json_({ ok: false, error: 'Unknown slot.' });
  const data = String(obj.data || '');
  if (!data || data.length > PHOTO_MAX) return json_({ ok: false, error: 'Bad photo size.' });

  // no lock while waiting: the row we are waiting for needs it to be written
  const sh = sheet_();
  var head = null, row = 0;
  for (var t = 0; t < 8 && !row; t++) {
    if (t) Utilities.sleep(1500);
    head = head_(sh);
    row = rowOf_(sh, head, obj.submissionId);
  }
  if (!row) return json_({ ok: false, error: 'No such submission.', retry: true });

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const who = String(obj.fullName || 'client').replace(/[\\/:*?"<>|]/g, ' ').trim() || 'client';
    const dir = folder_(who + ' - ' + String(obj.submissionId).slice(0, 8));
    const name = slot + '.jpg';
    const old = dir.getFilesByName(name);
    while (old.hasNext()) old.next().setTrashed(true);   // a re-send replaces
    const blob = Utilities.newBlob(Utilities.base64Decode(data), obj.mime || 'image/jpeg', name);
    const file = dir.createFile(blob);

    head = head_(sh);
    const key = 'photo' + slot.charAt(0).toUpperCase() + slot.slice(1);
    sh.getRange(row, colOf_(sh, head, key)).setValue(file.getId());
    sh.getRange(row, colOf_(sh, head, 'photosFolder')).setValue(dir.getUrl());
    return json_({ ok: true, id: file.getId() });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function doPost(e) {
  // photos do their own locking, and must not hold it while they wait
  try {
    const probe = JSON.parse(e.postData.contents);
    if (probe.action === 'photo') return photo_(probe);
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const obj = JSON.parse(e.postData.contents);
    const sh = sheet_();
    const head = head_(sh);
    Object.keys(obj).forEach(function (k) {
      if (head.indexOf(k) === -1) { head.push(k); sh.getRange(1, head.length).setValue(k); }
    });

    // the form gives every file a submissionId, so a retry or a double tap
    // can never write the same client twice
    if (obj.submissionId && rowOf_(sh, head, obj.submissionId)) {
      return json_({ ok: true, duplicate: true });
    }

    sh.appendRow(head.map(function (h) { return obj[h] == null ? '' : obj[h]; }));
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  const p = e.parameter || {};
  function out(o) {
    if (p.callback) {
      return ContentService.createTextOutput(p.callback + '(' + JSON.stringify(o) + ')')
        .setMimeType(ContentService.MimeType.JAVASCRIPT);
    }
    return json_(o);
  }
  // deliberately before the access-code check: a build stamp is not a secret,
  // and being able to ask a deployment what it is saves an hour of guessing
  if (p.action === 'version') return out({ ok: true, build: BUILD });

  if (String(p.code) !== ACCESS_CODE) return out({ ok: false, error: 'Wrong access code.' });

  // A client photo, for the console. The files stay private in your Drive —
  // nothing is shared by link — so your access code is the only way to see them.
  if (p.action === 'photo') {
    try {
      const file = DriveApp.getFileById(String(p.id));
      var blob = null;
      if (p.size === 'thumb') { try { blob = file.getThumbnail(); } catch (er) { blob = null; } }
      if (!blob) blob = file.getBlob();
      return out({ ok: true, mime: blob.getContentType(),
        data: Utilities.base64Encode(blob.getBytes()) });
    } catch (err) {
      return out({ ok: false, error: 'Photo not found.' });
    }
  }

  const sh = sheet_();
  const n = sh.getLastRow();
  if (n < 2) return out({ ok: true, clients: [], total: 0 });
  const cols = sh.getLastColumn();
  const head = sh.getRange(1, 1, 1, cols).getValues()[0];
  const start = Math.max(2, n - MAX_ROWS + 1);
  const values = sh.getRange(start, 1, n - start + 1, cols).getValues();
  const clients = values.map(function (r) {
    const o = {};
    head.forEach(function (h, i) {
      const v = r[i];
      o[h] = (v instanceof Date) ? v.toISOString() : String(v == null ? '' : v);
    });
    return o;
  });
  return out({ ok: true, clients: clients, total: n - 1 });
}
