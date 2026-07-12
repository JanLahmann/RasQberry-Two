# External Demo Template Specification

Status: **DRAFT** (design approved 2026-07-12, implementation pending)

## Goal

Third-party demo repositories can be added to a RasQberry system through the
menu without RasQberry shipping any per-demo code. A demo repo declares how it
runs by carrying a manifest file; RasQberry maintains only a short registry of
known demos. This replaces the current model where every demo needs a manifest
*and* often a launcher script inside this repository.

## How it fits the existing manifest system

The manifest system (#228) already separates demo *data* (JSON manifests in
`/usr/config/demo-manifests/`) from demo *execution* (`rq_demo_run.sh`, the
universal launcher that all menu dispatch goes through). External demos reuse
both mechanisms unchanged — the only new parts are where the manifest comes
from and the trust constraints applied to it.

## 1. What a demo repository provides: `rqb-demo.json`

A single file at the repository root, following the same schema as internal
manifests (`rq_demo_schema.json`), with these constraints:

**Required fields**
- `id` — globally unique, kebab-case, must match the registry entry
- `name`, `category`, `description`
- `entrypoint.type` — one of `python`, `jupyter`, `browser`, `docker`
- `entrypoint.working_dir` — must equal the repository name
- `install.marker_file` — a file that proves checkout integrity

**Forbidden fields for external demos** (accepted for internal manifests only)
- `entrypoint.launcher` — external demos cannot ship or reference launcher
  scripts; only declarative types are dispatched
- `install.patch_file` — no patching of external content at install time;
  the demo repo must work as published
- `entrypoint.command` — no arbitrary command strings

**Recommended**
- `needs_hw` declarations (leds/display/network) so requirement checks work
- `install.pip_requirements: true` with a `requirements.txt` carrying
  **pinned versions** (`package==x.y.z`)
- `variants[]` for multiple modes (args-only variants preferred)

## 2. What RasQberry maintains: `known-demos.json`

A thin registry in `RQB2-config/known-demos.json`:

```json
{
  "demos": [
    {
      "id": "example-demo",
      "repo_url": "https://github.com/someuser/example-demo.git",
      "ref": "a1b2c3d4e5f6...",
      "manifest_path": "rqb-demo.json",
      "added": "2026-07-12",
      "note": "optional curator note"
    }
  ]
}
```

- `ref` is a **full commit SHA** (not a branch or tag). Updating a demo means
  updating the SHA in the registry — a reviewable, revertable change. This is
  the fix for the drift class of failures where unpinned HEAD clones break
  when upstream restructures (seen live 2026-07-12: quantum-raspberry-tie
  v7_1 → v8_0 rename broke install; patches died on upstream edits).
- `repo_url` must be `https://` (no ssh/git protocols, no redirects followed).

## 3. Add flow (menu: "Add demo from catalog")

1. Menu lists registry entries not yet installed.
2. On selection: shallow-fetch the pinned ref
   (`git init && git fetch <url> <sha> && git checkout FETCH_HEAD`
   — a plain `git clone --depth 1` cannot fetch an arbitrary SHA).
3. Read `rqb-demo.json` from the checkout, validate against
   `rq_demo_schema.json` **plus** the external constraints in §1
   (extend `rq_demo_validate.sh` with an `--external` mode).
4. On pass: copy the manifest to the **user manifest directory**
   `~/.local/config/demo-manifests/` (never into `/usr/config`).
5. Refresh the menu cache. The demo now dispatches like any other via
   `rq_demo_run.sh <id>`.

Updates are explicit: a "Update demo" action re-fetches the (possibly new)
pinned SHA from a refreshed registry; never an implicit `git pull`.

## 4. Structural change: manifest search path

`MANIFEST_DIR` (single directory today) becomes a search path:

```
/usr/config/demo-manifests          # shipped, trusted
~/.local/config/demo-manifests      # user-added external demos
```

User-dir manifests must not shadow shipped ids (shipped wins; warn on
collision). Three scripts read `MANIFEST_DIR` and need the change:
`rq_demo_run.sh`, `rq_demo_generate_menu.sh`, `rq_demo_validate.sh`.

## 5. Security model

External manifests execute on a system where menu dispatch may run as root
(raspi-config context). Constraints, in addition to §1 field restrictions:

1. **Declarative dispatch only** — external demos run exclusively through
   `rq_demo_run.sh`'s type handlers. The menu cache generator already emits
   only `rq_demo_run.sh "<id>"` (no manifest values compiled into shell).
2. **Schema hardening** — patterns reject path traversal: `id`, `working_dir`,
   `script`, `marker_file` must match `^[A-Za-z0-9._-]+$`-class patterns with
   no `..`, no leading `/`, no whitespace.
3. **Privilege rules** — same as internal: python+`needs_hw.leds` runs as
   root (that is the point of LED demos — flag in the add-flow confirmation
   dialog: "this demo drives LEDs and will run with root privileges");
   everything else runs as the user.
4. **Pinned dependencies** — pip installs go into the user venv as the user.
   Registry curation should prefer demos with pinned requirements. (Future
   option: per-demo venvs to isolate dependency conflicts.)
5. **No network at run time beyond what the demo does itself** — install-time
   fetch is exactly the pinned SHA.

The registry itself is the trust anchor: adding an entry to
`known-demos.json` is a RasQberry PR, reviewed like code.

## 6. Implementation checklist

- [ ] `known-demos.json` + JSON schema for it
- [ ] `rq_demo_validate.sh --external` (§1 constraints)
- [ ] SHA fetch helper in `rq_common.sh` (`fetch_pinned_repo <url> <sha> <dest>`)
- [ ] Manifest search path in the three readers (§4)
- [ ] Menu flow: list / add / update / remove external demos
- [ ] Add-flow confirmation dialog incl. root warning for LED demos
- [ ] Docs for demo authors (template repo with example `rqb-demo.json`)

## 7. Migration perspective

Internal demos can migrate to the same model over time: today their manifests
live in this repo and clone unpinned HEAD. Adding `ref` pins to internal
manifests (same mechanism, no registry needed) would close the drift failure
mode for them too — recommended as part of implementing this spec.
