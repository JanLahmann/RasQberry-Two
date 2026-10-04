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
 * It also writes 02-learning-paths.md from learning-paths.json, which sits next
 * to the manifests: the Pi's Learning paths chooser reads the same file, so the
 * website and the Pi show the same paths, their Keep going links and the
 * Where to go next ladder (issue #309).
 *
 *   node scripts/generate-demo-list.js            # write both files
 *   node scripts/generate-demo-list.js --check    # fail if one is out of date (CI)
 *   node scripts/generate-demo-list.js --ref beta # read from another branch
 *   node scripts/generate-demo-list.js --local ../RasQberry-Two-development
 *                                                 # read a local checkout instead
 *                                                 # (before a push; links still name --ref)
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
const PATHS_FILE = 'learning-paths.json';
const PATHS_OUT = path.join(path.dirname(OUT), '02-learning-paths.md');
const DEMO_LIST_URL = '/03-quantum-computing-demos/01-demo-list/';
// The demo feedback form, as the Pi's beta demos link it (rq_common.sh RQ_FEEDBACK_URL)
const FEEDBACK = `https://github.com/${REPO}/issues/new?template=demo-feedback.yml`;

const args = process.argv.slice(2);
const check = args.includes('--check');
const refIdx = args.indexOf('--ref');
const ref = refIdx !== -1 ? args[refIdx + 1] : DEFAULT_REF;
const localIdx = args.indexOf('--local');
const local = localIdx !== -1 ? args[localIdx + 1] : null;

// A demo has a full page when a file of that name exists next to the list.
function pageFor(id) {
  const dir = path.dirname(OUT);
  const candidates = { 'quantum-fractals': 'fractals', 'grok-bloch': 'bloch-sphere', 'quantum-raspberry-tie': 'raspberry-tie', 'led-demos': 'led-display' };
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
  if (m.needs_ibm_token === 'required') n.push('IBM Quantum account');
  else if (m.needs_ibm_token === 'prefer') n.push('IBM Quantum account optional');
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

const isManifest = (name) => name.startsWith('rq_demo_') && name.endsWith('.json') && !name.includes('schema');

// The manifests and the learning paths, from GitHub at `ref` or from a local
// checkout (--local). A missing learning-paths.json is an error, not an empty
// page: the Pi would still show the paths.
async function fetchSources() {
  if (local) {
    const dir = path.join(local, MANIFEST_DIR);
    const manifests = fs.readdirSync(dir).filter(isManifest).sort()
      .map((n) => JSON.parse(fs.readFileSync(path.join(dir, n), 'utf8')));
    const file = path.join(dir, PATHS_FILE);
    if (!fs.existsSync(file)) throw new Error(`${PATHS_FILE} not found in ${dir}`);
    return { manifests, learning: JSON.parse(fs.readFileSync(file, 'utf8')) };
  }
  const api = `https://api.github.com/repos/${REPO}/contents/${MANIFEST_DIR}?ref=${ref}`;
  const res = await fetch(api, { headers: ghHeaders() });
  if (!res.ok) {
    const hint = res.status === 403 ? ' (rate limited? set GITHUB_TOKEN)' : '';
    throw new Error(`GitHub API ${res.status} for ${api}${hint}`);
  }
  const files = await res.json();
  const get = async (f) => {
    const r = await fetch(f.download_url, { headers: ghHeaders() });
    if (!r.ok) throw new Error(`fetch ${f.name}: ${r.status}`);
    return r.json();
  };
  const manifests = [];
  for (const f of files) if (isManifest(f.name)) manifests.push(await get(f));
  const pathsFile = files.find((f) => f.name === PATHS_FILE);
  if (!pathsFile) throw new Error(`${PATHS_FILE} not found on ${ref}: merge the learning paths there first`);
  return { manifests, learning: await get(pathsFile) };
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

// A manifest hidden from both the menu and the desktop is not a demo of its
// own (grok-bloch-web: the online version is now a variant of grok-bloch).
const isShown = (m) => !(m.menu?.show === false && m.desktop?.show === false);

function render(manifests) {
  const byCategory = {};
  for (const m of manifests.filter(isShown)) (byCategory[m.category || 'other'] ||= []).push(m);
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
"network on first start" download the first time you run them. An IBM Quantum
account is only needed to run on real IBM hardware. Demos tagged beta are new:
[tell us how they work](${FEEDBACK}).

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
      const beta = m.maturity === 'beta' ? ' <span className="beta-tag">beta</span>' : '';
      const needs = needsOf(m);
      md += `| **${name}**${beta} | ${m.description || ''} | ${needs.length ? needs.join(', ') : '—'} | \`${m.id}\` |\n`;
    }
    md += `\n`;
  }

  md += `---\n\n*Generated from the demo manifests in [\`${MANIFEST_DIR}\`](https://github.com/${REPO}/tree/${ref}/${MANIFEST_DIR}) — the same files the image installs from.*\n`;
  return md;
}

// Text from the JSON inside Markdown/MDX: characters that would start markup,
// JSX or an expression are escaped.
const esc = (t) => String(t).replace(/[\\`*_{}[\]<>]/g, (c) => `\\${c}`);

// One step: where to start it, then what to try and what to notice. A demo
// links to its page (or the demo list); a notebook inside a demo (a Fun with
// Quantum game) names the demo it is in.
function renderStep(step, i, byId) {
  let what;
  if (step.demo) {
    const m = byId[step.demo];
    if (!m) throw new Error(`learning path step "${step.name || step.demo}": no demo "${step.demo}" in the manifests`);
    const link = pageFor(m.id) || DEMO_LIST_URL;
    const name = step.name || m.name;
    what = name === m.name ? `**[${esc(name)}](${link})**` : `**${esc(name)}** in [${esc(m.name)}](${link})`;
  } else if (step.command) {
    what = `**${esc(step.name)}** (desktop icon on the Pi)`;
  } else {
    what = `**[${esc(step.name)}](${step.url})** (online)`;
  }
  return `${i + 1}. ${what}\n   - Try: ${esc(step.try)}\n   - Notice: ${esc(step.notice)}\n`;
}

// The anchor the site gives an H2 (src/utils/toKebabCase.ts, "2-" + title)
const h2Anchor = (title) => `#${`2 ${title}`.replace(/[^a-zA-Z0-9]/g, ' ').replace(/\s+/g, '-').toLowerCase().replace(/^-|-$/g, '')}`;
// rasqberry.org pages as site links, so the build's link check covers them
const siteUrl = (url) => url.replace(/^https:\/\/rasqberry\.org(?=\/)/, '');

// Keep going: the path's next entries on one line, the reason on hover
function renderNext(p, paths) {
  const links = (p.next || []).map((e) => {
    const target = e.path ? paths.find((q) => q.id === e.path) : null;
    if (e.path && !target) throw new Error(`learning path ${p.id}: next path "${e.path}" does not exist`);
    const name = target ? target.title : e.name;
    const url = target ? h2Anchor(target.title) : siteUrl(e.url);
    return `[${esc(name)}](${url} "${e.why.replace(/"/g, "'")}")`;
  });
  return links.length ? `**Keep going:** ${links.join(' · ')}\n` : '';
}

// Where to go next: one line per rung, its links, and the notes (sentences
// that name their link, e.g. CertiQ's: a community project, not IBM's)
function renderLadder(ladder) {
  if (!ladder || !ladder.length) return '';
  let md = `\n## Where to go next\n\nFrom playing to building your own:\n\n`;
  ladder.forEach((r, i) => {
    const links = r.links.map((l) => `[${esc(l.name)}](${siteUrl(l.url)})`).join(', ');
    const notes = r.links.filter((l) => l.note).map((l) => ` ${esc(l.note)}`).join('');
    md += `${i + 1}. **${esc(r.rung)}.** ${esc(r.text)}: ${links}.${notes}\n`;
  });
  return md;
}

function renderPaths(learning, manifests) {
  const paths = learning.paths;
  const byId = Object.fromEntries(manifests.map((m) => [m.id, m]));
  // MDX comment: invisible on the page, unlike the demo list's blockquote
  let md = `{/* Generated by scripts/generate-demo-list.js from ${MANIFEST_DIR}/${PATHS_FILE} (${ref}). Edit that file, not this page. */}

# Learning paths

Short tours through the demos, each for one audience. Every step says what to
try and what to notice. On the Pi, open the **Learning paths** icon or
\`sudo raspi-config\` → **0 RasQberry** → **Quantum Demos** → **Learning paths
(beta)**: it starts each demo for you. All demos are on the
[Demo List](${DEMO_LIST_URL}).
`;
  for (const p of paths) {
    const beta = p.maturity === 'beta' ? ' · <span className="beta-tag">beta</span>' : '';
    md += `
<div className="path-card">

## ${esc(p.title)}

${esc(p.audience)} · about ${p.minutes} minutes${beta}

${esc(p.goal)}

${p.steps.map((st, i) => renderStep(st, i, byId)).join('')}
${renderNext(p, paths)}
${p.maturity === 'beta' ? 'This path is new: ' : ''}[tell us how it went](${FEEDBACK}&demo=learning-paths/${p.id}).

</div>
`;
  }
  return md + renderLadder(learning.ladder);
}

(async () => {
  const { manifests, learning } = await fetchSources();
  const paths = learning.paths;
  if (!manifests.length) throw new Error('no manifests found — refusing to write an empty list');
  if (!paths || !paths.length) throw new Error(`no paths in ${PATHS_FILE} — refusing to write an empty page`);
  const outputs = [
    [OUT, render(manifests), `demo list matches the manifests (${manifests.filter(isShown).length} demos)`],
    [PATHS_OUT, renderPaths(learning, manifests), `learning paths match ${PATHS_FILE} (${paths.length} paths)`],
  ];

  if (check) {
    let stale = false;
    for (const [file, md, ok] of outputs) {
      const current = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
      if (current !== md) {
        console.error(`✗ ${path.basename(file)} is out of date with ${MANIFEST_DIR}.`);
        stale = true;
      } else {
        console.log(`✓ ${ok}`);
      }
    }
    if (stale) {
      console.error('  Run: node scripts/generate-demo-list.js');
      process.exit(1);
    }
    return;
  }

  for (const [file, md] of outputs) {
    fs.writeFileSync(file, md);
    console.log(`✓ wrote ${path.relative(process.cwd(), file)} (from ${local || ref})`);
  }
})().catch((e) => {
  console.error(`✗ ${e.message}`);
  process.exit(1);
});
