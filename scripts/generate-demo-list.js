#!/usr/bin/env node
/**
 * Generate the demo list from the demo manifests.
 *
 * The manifests in RQB2-config/demo-manifests/ are what the image actually
 * installs from - id, name, description, what hardware it needs. So they are
 * the only honest source for "which demos exist". A hand-maintained list drifts:
 * when this was written 17 demos shipped, 8 were listed, and the page still said
 * they "will be made available".
 *
 * This writes content/03-quantum-computing-demos/01-demo-list.md from those
 * manifests. Prose stays hand-written in the per-demo pages - only the catalogue
 * is generated.
 *
 *   node scripts/generate-demo-list.js            # write the file
 *   node scripts/generate-demo-list.js --check    # fail if it is out of date (CI)
 *   node scripts/generate-demo-list.js --ref beta # read manifests from another branch
 */

const fs = require('fs');
const path = require('path');

const REPO = 'JanLahmann/RasQberry-Two';
const MANIFEST_DIR = 'RQB2-config/demo-manifests';

// Which branch the website describes. `development` while the demo work is
// landing there; switch to `beta` once this round is merged to beta, so the
// site documents what people can actually download rather than what is in
// flight. Override per-run with --ref.
const DEFAULT_REF = 'development';
const OUT = path.join(__dirname, '..', 'content', '03-quantum-computing-demos', '01-demo-list.md');

const args = process.argv.slice(2);
const check = args.includes('--check');
const refIdx = args.indexOf('--ref');
const ref = refIdx !== -1 ? args[refIdx + 1] : DEFAULT_REF;

// A demo has a full page when a file of that name exists next to the list.
function pageFor(id) {
  const dir = path.dirname(OUT);
  const candidates = { 'quantum-fractals': 'fractals', 'grok-bloch': 'bloch-sphere', 'quantum-raspberry-tie': 'raspberry-tie' };
  const slug = candidates[id] || id;
  // Absolute, because pages are served with a trailing slash: a bare slug
  // would resolve below the list page itself and 404.
  return fs.existsSync(path.join(dir, `${slug}.md`)) ? `/03-quantum-computing-demos/${slug}/` : null;
}

// What a demo needs, in the words a teacher plans with. LED demos fall back to
// an on-screen view without a panel; an IBM account that is only "preferred"
// is optional (the simulator is the default); a demo that is not on the card
// needs the network once, for its first start.
function needsOf(m) {
  const n = [];
  if (m.needs_hw?.leds) n.push('LED panel or on-screen view');
  if (m.needs_hw?.display === 'required') n.push('display');
  if (m.needs_hw?.network) n.push('network');
  else if (m.install && m.install.preinstalled === false) n.push('network on first start');
  if (m.needs_ibm_token === 'required') n.push('IBM account');
  else if (m.needs_ibm_token === 'prefer') n.push('IBM account optional');
  return n;
}

// Authenticate when a token is around (CI sets GITHUB_TOKEN). Unauthenticated
// GitHub API calls are limited to 60/hour per IP, and Actions runners share IPs
// - which is the difference between this check being reliable in the deploy
// build and failing at random.
function ghHeaders() {
  const h = { Accept: 'application/vnd.github+json' };
  const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function fetchManifests() {
  const api = `https://api.github.com/repos/${REPO}/contents/${MANIFEST_DIR}?ref=${ref}`;
  const res = await fetch(api, { headers: ghHeaders() });
  if (!res.ok) {
    const hint = res.status === 403 ? ' (rate limited? set GITHUB_TOKEN)' : '';
    throw new Error(`GitHub API ${res.status} for ${api}${hint}`);
  }
  const files = await res.json();
  const out = [];
  for (const f of files) {
    if (!f.name.startsWith('rq_demo_') || !f.name.endsWith('.json')) continue;
    if (f.name.includes('schema')) continue;
    const r = await fetch(f.download_url, { headers: ghHeaders() });
    if (!r.ok) throw new Error(`fetch ${f.name}: ${r.status}`);
    out.push(await r.json());
  }
  return out;
}

// Headings and running order for the manifest `category` values. Anything not
// listed still renders (title-cased, at the end), so a new category is a
// cosmetic follow-up rather than a broken page.
const CATEGORIES = [
  ['visualization', 'See quantum states'],
  ['game', 'Play'],
  ['jupyter', 'Notebooks to work through'],
  ['education', 'Learn and teach'],
  ['led-demo', 'LED panel'],
  ['tool', 'Tools'],
];

function render(manifests) {
  const byCategory = {};
  for (const m of manifests) (byCategory[m.category || 'other'] ||= []).push(m);
  for (const list of Object.values(byCategory)) list.sort((a, b) => (a.menu?.order ?? 99) - (b.menu?.order ?? 99));

  const known = CATEGORIES.map(([c]) => c);
  const order = [...known.filter((c) => byCategory[c]), ...Object.keys(byCategory).filter((c) => !known.includes(c)).sort()];
  const title = (c) =>
    CATEGORIES.find(([k]) => k === c)?.[1] ||
    c.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');

  // No HTML comment header here: pages are compiled as MDX, which rejects
  // <!-- --> ("Unexpected character `!`"). The generated-file warning is the
  // blockquote below - visible to readers, which is where it belongs anyway.
  let md = `# Quantum Computing Demos in RasQberry Two

Start a demo from its desktop icon, from \`sudo raspi-config\` → **0 RasQberry** →
**Quantum Demos**, or from a terminal with \`rq_demo_run.sh <id>\`. Demos marked
"network on first start" download the first time you run them. An optional IBM
account is only needed to run on real IBM hardware.

> This page is generated from the [demo manifests](https://github.com/${REPO}/tree/${ref}/${MANIFEST_DIR})
> — the same files the image installs from, so it cannot fall out of step with
> what ships. To change an entry, edit its manifest; edits made here are
> overwritten.

`;

  for (const category of order) {
    md += `## ${title(category)}\n\n`;
    md += `| Demo | What it is | Needs | Start it with |\n|---|---|---|---|\n`;
    for (const m of byCategory[category]) {
      const page = pageFor(m.id);
      const name = page ? `[${m.name}](${page})` : m.name;
      const needs = needsOf(m);
      md += `| **${name}** | ${m.description || ''} | ${needs.length ? needs.join(', ') : '—'} | \`${m.id}\` |\n`;
    }
    md += `\n`;
  }

  md += `---\n\n*Generated from the demo manifests in [\`${MANIFEST_DIR}\`](https://github.com/${REPO}/tree/${ref}/${MANIFEST_DIR}) — the same files the image installs from.*\n`;
  return md;
}

(async () => {
  const manifests = await fetchManifests();
  if (!manifests.length) throw new Error('no manifests found — refusing to write an empty list');
  const md = render(manifests);

  if (check) {
    const current = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8') : '';
    if (current !== md) {
      console.error('✗ 01-demo-list.md is out of date with the demo manifests.');
      console.error('  Run: node scripts/generate-demo-list.js');
      process.exit(1);
    }
    console.log(`✓ demo list matches the manifests (${manifests.length} demos)`);
    return;
  }

  fs.writeFileSync(OUT, md);
  console.log(`✓ wrote ${path.relative(process.cwd(), OUT)} (${manifests.length} demos from ${ref})`);
})().catch((e) => {
  console.error(`✗ ${e.message}`);
  process.exit(1);
});
