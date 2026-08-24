/*
 * The browser half, tested where it can be: the pure helpers.
 *
 * Run with:  node --test tests/huckepack_js.test.js
 *
 * The parts that need a document (banner, IndexedDB, folder picker) are not
 * covered here — a test that stubs a whole browser proves the stub, not the
 * page. What is covered is what would silently go wrong: an unmasked number in
 * a receipt, a file name that a file system rejects, a "database" that is not
 * one, a PDF that no reader opens.
 */

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const huckepack = require(path.join(__dirname, "..", "ringedingeding", "web", "static", "huckepack.js"));

test("phone numbers do not survive into a receipt", () => {
  const masked = huckepack.maskPhones("Rufen Sie 020 79460000 an oder +44 7700 900000.");
  assert.ok(!masked.includes("3920000"));
  assert.ok(masked.includes("•••"));
});

test("a short number stays readable, because it is not a phone number", () => {
  assert.strictEqual(huckepack.maskPhones("Tisch 12"), "Tisch 12");
});

test("a key is shown by its last four characters and never in full", () => {
  assert.strictEqual(huckepack.maskKey("sk-abcdefgh"), "••••efgh");
  assert.strictEqual(huckepack.maskKey("ab"), "••••");
  assert.strictEqual(huckepack.maskKey(""), "");
});

test("the receipt file name sorts itself and survives a file system", () => {
  const when = new Date(2026, 7, 2, 19, 30);
  const name = huckepack.receiptFilename({ business: "Surf/Grill Express *" }, "txt", when);
  assert.strictEqual(name, "2026-08-02_1930_Surf-Grill-Express_beleg.txt");
  assert.ok(!/[\\/:*?"<>|]/.test(name));
});

test("a business without a name still yields a file name", () => {
  const name = huckepack.receiptFilename({}, "pdf", new Date(2026, 0, 1, 8, 5));
  assert.strictEqual(name, "2026-01-01_0805_call_beleg.pdf");
});

test("the receipt says who was called, what came of it, and whose words these are", () => {
  const text = huckepack.receiptText(
    {
      business: "Surf Grill Express",
      business_phone_masked: "•••567",
      created_at: "2026-08-02 19:30:00",
      total_price_eur: 18.5,
      eta_minutes: 35,
      order_id: "ord_1",
      summary: "Bestellt, Lieferung in 35 Minuten.",
      transcript: "Wirt: Ihre Nummer war 020 79460000?"
    },
    "de"
  );
  assert.ok(text.includes("Surf Grill Express"));
  assert.ok(text.includes("18.50 EUR"));
  assert.ok(text.includes("Äußerungen der angerufenen Person"));
  assert.ok(!text.includes("23125000"));
});

test("the receipt speaks the language of the page", () => {
  const english = huckepack.receiptText({ business: "Grill" }, "en");
  assert.ok(english.includes("person who was called"));
  assert.ok(!english.includes("Äußerungen"));
});

test("only a real SQLite file is accepted as a database", () => {
  const good = new TextEncoder().encode("SQLite format 3\u0000 rest of the file").buffer;
  const bad = new TextEncoder().encode("not a database at all----------").buffer;
  assert.strictEqual(huckepack.looksLikeSqlite(good), true);
  assert.strictEqual(huckepack.looksLikeSqlite(bad), false);
});

test("the hand-written PDF is one a reader will open", () => {
  const bytes = huckepack.receiptPdf("Beleg\n\nBetrieb: Surf Grill Express\n");
  const text = Buffer.from(bytes).toString("latin1");
  assert.ok(text.startsWith("%PDF-1.4"));
  assert.ok(text.includes("/Type /Catalog"));
  assert.ok(text.includes("startxref"));
  assert.ok(text.trimEnd().endsWith("%%EOF"));
});

test("a long receipt becomes several pages instead of one clipped one", () => {
  const long = new Array(200).fill("Zeile mit Inhalt").join("\n");
  const text = Buffer.from(huckepack.receiptPdf(long)).toString("latin1");
  assert.ok(text.includes("/Count 4"), "expected four pages for 200 lines");
});

test("a session token is long enough that it cannot be guessed", () => {
  const random = { getRandomValues: (array) => { for (let i = 0; i < array.length; i += 1) array[i] = i * 7; return array; } };
  const token = huckepack.newSessionToken(random);
  assert.strictEqual(token.length, 24);
  assert.ok(/^[A-Za-z0-9_-]+$/.test(token));
});
