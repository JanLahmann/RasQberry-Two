# RasQberry Two Style Guide

Rules for everything a user reads: the website, docs, menus, dialogs, desktop
icons, demo manifests and release notes.

## Names

- **RasQberry Two** in prose. **RasQberry-Two** only for the repository, paths
  (`~/RasQberry-Two`) and identifiers. **RasQberry** alone only for the menu entry
  **0 RasQberry** and the command names.
- **LED panel** for the hardware (not LED array, matrix or strip). Without a
  panel: the **on-screen view** (`LED_VIRTUAL`) and the **browser view** (`LED_WEB`).
- **A/B image** and **standard image**. Say **system** for what a slot holds:
  "two systems on one card", "Slot A", "Slot B". A slot has no role name (not
  "stable", not "testing": those are release streams). Say what it holds and
  whether it runs: "Slot A: beta-2026-10-03-095636 (beta) - running, start slot".
- An update goes into **the other system** (the slot not running). When an
  update fails, say what happened and what runs now: "The update of Slot B to
  <version> didn't work, so Slot A (<version>) is running again." Never "didn't
  start".
- **IBM Quantum account** in user text; "token" or "API key" only where the user
  pastes one.
- A demo has one name, its manifest `name`, used on the desktop icon, in the menu
  and on the website. Demo directories keep the upstream repository name.
  doQumentation is only named as the project the **Workshop & Qiskit Server** is
  built on.
- A new or less-tested demo has `"maturity": "beta"` in its manifest: "(beta)" in
  the menus and tooltips, a beta tag on the website, and a link to the demo
  feedback form.
- **Raspberry Pi Imager** (then **Imager**), **Pi 4**, **Pi 5**.

## Language

- British English: colour, customise, organise, licence (noun), centre, catalogue.
- Short sentences, second person, present tense. Say what the user sees and what
  to do next. One topic in one place: link instead of repeating.
- Card sizes as printed on the card, decimal, with a space: "64 GB card", "about 1.7 GB". GiB only
  in developer docs.
- Ranges with an en dash: "20–30 minutes".

## Menu paths

- Write them as `sudo raspi-config` → **0 RasQberry** → **Quantum Demos** →
  **LED panel**, with the label the user sees. Never an internal tag such as
  `AB_BOOT`, `SLOTS` or `EXPAND`.
- In whiptail text, which is plain ASCII, use `->`.

## Dialogs

- Titles and menu items in Title Case, like raspi-config; body text in sentence
  case. Menu titles start with `RasQberry:`.
- Buttons name the action ("Install", "Stop demo", "Keep running") instead of
  Yes/No where whiptail allows it.
- Errors say what failed, why, and what to do next. Never only "Failed to run
  demo: <id>".
- Fit 80x24. Long output goes to a scrollable text box, not a message box. Use
  the sizing helpers in `rq_common.sh`.
- Never capture the output of a command that asks a question: the prompt is
  then invisible.
- Stopping a demo is worded the same everywhere (`rq_stop_hint`): "To stop
  <demo>: press Enter or Ctrl+C, or close this window." A demo that uses the
  keyboard leaves out Enter.
- Colour is never the only cue: add a word, a position or a shape.

## Website

- Internal links are absolute with a trailing slash: `/02-software/03-ab-boot/`.
  The CI link check is strict.
- Pages are MDX: no `<!-- -->` comments, use `{/* */}`.
- Statements that depend on a release decision carry a marker comment, for
  example `{/* CONDITIONAL: A/B default */}`, so they can be found and switched.

## Glossary

| Term | Meaning |
|---|---|
| A/B image | Image with two systems (Slot A, Slot B) on cards of 64 GB or more; one system on smaller cards |
| Standard image | Image with one system |
| Other system | The slot that is not running; every update goes there |
| Start slot | The slot a normal start boots (`[all]` in `autoboot.txt`); a confirmed update becomes it |
| Switch to Slot X | Restart into the other slot on trial; a good start makes it the start slot |
| CONFIG drive | The first partition, readable on any computer; holds `autoboot.txt` |
| Data partition | `/data` on the A/B image; keeps `~/Shared`, `~/My-Quantum-Programs`, the IBM Quantum account and settings across updates |
| Setup checklist | The steps offered at the first login (`rq_firstlogin.sh`) |
| Demo catalogue | Reviewed third-party demos added with **Add demo from catalogue** |
