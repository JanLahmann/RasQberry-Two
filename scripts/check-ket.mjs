// Checks the Ket loader on both sides of KET_OPEN_UNTIL: before it every
// visitor gets the widget (public), after it only ?assistant=1 / a Pi.
import assert from "node:assert/strict";
import { KET_OPEN_UNTIL, ketLoader } from "../src/lib/ket.mjs";

function run(now, search = "") {
  const added = [];
  const el = () => { const a = {}; return { attrs: a, setAttribute: (k, v) => { a[k] = v; } }; };
  const ctx = {
    location: { search },
    sessionStorage: { getItem: () => null },
    document: { querySelector: () => null, createElement: el, body: { appendChild: (e) => added.push(e) } },
    Date: { now: () => now },
    URLSearchParams,
  };
  new Function(...Object.keys(ctx), ketLoader())(...Object.values(ctx));
  return added[0]?.attrs;
}

const end = Date.parse(KET_OPEN_UNTIL);
assert.ok(!Number.isNaN(end), "KET_OPEN_UNTIL must be a date");
assert.equal(run(end - 1000)?.["data-public"], "1", "open before the date");
assert.equal(run(end)?.["data-public"], "1", "open on the last second");
assert.equal(run(end + 1000), undefined, "not loaded for visitors after the date");
assert.equal(run(end + 1000, "?from=pi")?.["data-public"], undefined, "Pi after the date: loaded, not public");
assert.ok(run(end + 1000, "?from=pi"), "Pi after the date: still loaded");
assert.ok(run(end + 1000, "?assistant=1"), "?assistant=1 after the date: still loaded");
console.log(`Ket loader OK (open until ${KET_OPEN_UNTIL})`);
