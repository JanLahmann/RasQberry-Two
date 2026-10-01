# Which branch owns which workflow

GitHub runs a workflow from the branch that triggered it: a push uses the
pushed branch's copy, a manual dispatch the selected branch's copy, and a
schedule **only main's**. So each workflow lives where its trigger fires, and
nowhere else (#212).

| Workflow | Lives on | Trigger | Notes |
|---|---|---|---|
| `link-check.yml` | main | weekly schedule, dispatch | checks gh-pages (built), development, beta, 3D-model |
| `consolidate-json.yaml` | main | schedule, dispatch | script in `.github/scripts/consolidate_json.py`; writes to gh-pages |
| `family-dispatch-relay.yml` | main | repository_dispatch | relays Fun-with-Quantum updates to the site build |
| `stl-analysis.yml` | main **and** 3D-model, identical | STL push/PR (3D-model copy), weekly schedule (main copy, audits 3D-model) | edit both together |
| `paradox-notebooks.yml` | main **and** development, identical | push of the patch rules/test (development copy); weekly PyPI check (main copy) runs it when a new Qiskit x.y.0 came out | Quantum Paradoxes regression test (#181); edit both together |
| `RQB-image-v2.yaml` | development, beta, dev-* | push dev*, dispatch | flows development → beta by merge |
| `code-quality.yml` | development, beta, dev-* | push, PR | flows development → beta by merge |
| `nextjs.yml` | gh-pages | push gh-pages, dispatch | website build and deploy |
| `generate-demo-gif.yml` | gh-pages | push of `public/demo-screenshots/source/*.png` | |

A stable image is not built from main today (main holds no RQB2-bin/config code).
