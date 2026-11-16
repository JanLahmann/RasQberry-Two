// Checks the Ket loader on both sides of KET_OPEN_UNTIL: before it every
// visitor gets the widget (public), after it only ?assistant=1 / a Pi.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
assert.equal(run(end), undefined, "not loaded for visitors from the cutoff on");
assert.equal(run(end + 1000, "?from=pi")?.["data-public"], undefined, "Pi after the date: loaded, not public");
assert.ok(run(end + 1000, "?from=pi"), "Pi after the date: still loaded");
assert.ok(run(end + 1000, "?assistant=1"), "?assistant=1 after the date: still loaded");
// The privacy page names the last open day
const lastDay = new Date(end - 1).toLocaleDateString("en-US", { timeZone: "Europe/Berlin", month: "long", day: "numeric", year: "numeric" });
assert.ok(readFileSync(new URL("../content/privacy.md", import.meta.url), "utf8").includes(lastDay), `content/privacy.md should say ${lastDay}`);

console.log(`Ket loader OK (open until ${KET_OPEN_UNTIL})`);
