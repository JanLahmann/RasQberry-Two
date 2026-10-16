"""
Rig mission 2026-10-16: the IBM Quantum Courses and Tutorials showed the
website's source in Jupyter - front matter as text ("title: Circuits ..."),
every picture broken (/learning/images/... is a path on IBM's website), raw
<Admonition>/<Image .../> tags, and pictures of outputs as '<Image src=... />'
text. setup_ibm_tutorials.py converts the notebooks once after the download;
the pictures come with it (public/..., RQ_IBM_LEARNING_PATHS).

The snippets below are taken from the pinned Qiskit/documentation notebooks.
"""

import importlib.util
import json
import os
import stat

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SCRIPT = os.path.join(_ROOT, "RQB2-bin", "setup_ibm_tutorials.py")


def _module():
    spec = importlib.util.spec_from_file_location("setup_ibm_tutorials", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sit = _module()

LESSON = "learning/courses/basics-of-quantum-information/quantum-circuits/circuits.ipynb"
PICTURE = "public/learning/images/courses/basics-of-quantum-information/quantum-circuits/Boolean-circuit-XOR.svg"
OUTPUT = "public/docs/images/tutorials/chsh-inequality/extracted-outputs/1b2c-0.avif"


def _md(text, **extra):
    return dict({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}, **extra)


def _code(source, outputs=(), tags=None, **extra):
    meta = {"tags": tags} if tags else {}
    return dict({"cell_type": "code", "execution_count": None, "metadata": meta,
                 "outputs": list(outputs), "source": source}, **extra)


def _nb(*cells, minor=5):
    return {"cells": list(cells), "metadata": {}, "nbformat": 4, "nbformat_minor": minor}


@pytest.fixture
def base(tmp_path):
    """An ibm-quantum-learning folder with a lesson, a tutorial and two pictures."""
    for rel in (LESSON, "docs/tutorials/chsh-inequality.ipynb", "docs/guides/hello-world.ipynb",
                "learning/courses/basics-of-quantum-information/entanglement-in-action/chsh-game.ipynb"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_nb(_md("# x\n"))))
    for rel in (PICTURE, OUTPUT):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"<svg/>")
    return tmp_path


def _convert(base, nb, rel=LESSON):
    changed = sit.convert_notebook(nb, base / rel, base)
    return changed, ["".join(c["source"]) for c in nb["cells"]]


def test_front_matter_goes_and_the_pictures_show(base):
    nb = _nb(_md("---\ntitle: Circuits\ndescription: A free IBM course on quantum information\n---\n\n\n"
                 "# Circuits\n\nHere is an example:\n\n"
                 "![Example of a Boolean circuit](/learning/images/courses/basics-of-quantum-information/"
                 "quantum-circuits/Boolean-circuit-XOR.svg)\n"))
    changed, (text,) = _convert(base, nb)
    assert changed
    assert text.startswith("# Circuits\n")
    assert "title:" not in text and "---" not in text
    assert "![Example of a Boolean circuit](../../../../" + PICTURE + ")" in text
    # the relative path really leads to the picture, from the notebook's folder
    rel = text.split("](", 1)[1].split(")", 1)[0]
    assert (base / LESSON).parent.joinpath(rel).resolve() == (base / PICTURE).resolve()


def test_a_notebook_without_a_heading_gets_its_title(base):
    nb = _nb(_md("---\ntitle: \"Error mitigation\"\ndescription: x\n---\n\nSome text.\n"),
             _md("```python\n# a comment is no heading\n```\n"))
    _, texts = _convert(base, nb)
    assert texts[0] == "# Error mitigation\n\nSome text.\n"


def test_a_picture_that_is_not_here_comes_from_the_website(base):
    nb = _nb(_md("![x](/learning/images/courses/other/missing.svg)\n"))
    _, (text,) = _convert(base, nb)
    assert text == "![x](https://quantum.cloud.ibm.com/learning/images/courses/other/missing.svg)\n"


def test_links_open_the_notebook_here_or_the_page_online(base):
    nb = _nb(_md("- [CHSH](/docs/tutorials/chsh-inequality)\n"
                 "- [Lesson](/learning/courses/basics-of-quantum-information/entanglement-in-action/chsh-game#the-game)\n"
                 "- [Primitives](/docs/guides/primitives)\n"
                 "- [API](/docs/api/qiskit/qiskit.quantum_info.SparsePauliOp)\n"
                 "- [fake backend](../api/qiskit-ibm-runtime/fake-provider)\n"
                 "- [IBM](https://quantum.cloud.ibm.com/) and [top](#top)\n"
                 '- <a href="/docs/guides/hello-world">Hello</a>\n'),
             )
    _, (text,) = _convert(base, nb, "docs/guides/hello-world.ipynb")
    assert "[CHSH](../tutorials/chsh-inequality.ipynb)" in text
    assert ("[Lesson](../../learning/courses/basics-of-quantum-information/entanglement-in-action/"
            "chsh-game.ipynb#the-game)") in text
    assert "[Primitives](https://quantum.cloud.ibm.com/docs/guides/primitives)" in text
    assert "[API](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.quantum_info.SparsePauliOp)" in text
    # relative on the website (docs/guides/ + ../api/...)
    assert "[fake backend](https://quantum.cloud.ibm.com/docs/api/qiskit-ibm-runtime/fake-provider)" in text
    assert "[IBM](https://quantum.cloud.ibm.com/) and [top](#top)" in text
    assert '<a href="hello-world.ipynb">Hello</a>' in text


def test_notes_become_blockquotes_that_keep_markdown_and_math(base):
    nb = _nb(_md("Intro.\n<Admonition type=\"tip\" title=\"Recommendations\">\n"
                 "If you found this interesting:\n- [CHSH](/docs/tutorials/chsh-inequality)\n</Admonition>\n\n"
                 "<Admonition type=\"caution\">\n  Indented text.\n</Admonition>\n\n"
                 "<Figure title=\"Theorem\">\nNo-cloning theorem: such that\n$$\nU = V\n$$\nfor every state.\n"
                 "</Figure>\n"))
    _, (text,) = _convert(base, nb)
    assert "<Admonition" not in text and "<Figure" not in text
    assert ("Intro.\n\n<blockquote>\n\n**Recommendations**\n\nIf you found this interesting:\n"
            "- [CHSH](../../../../docs/tutorials/chsh-inequality.ipynb)\n\n</blockquote>") in text
    assert "<blockquote>\n\n**Caution**\n\nIndented text.\n\n</blockquote>" in text
    # an HTML blockquote, not "> " lines: Jupyter would show the ">" in the formula
    assert "**Theorem**\n\nNo-cloning theorem: such that\n$$\nU = V\n$$\nfor every state." in text
    assert "\n>" not in text


def test_a_note_inside_a_list_stays_in_the_list(base):
    nb = _nb(_md("2. Set up:\n\n    - Go to the platform.\n"
                 "         <Admonition type=\"note\" title=\"Important\">\n"
                 "         Use Qiskit Runtime v0.44.0 or later.\n         </Admonition>\n"
                 "    - Generate your API key.\n"))
    _, (text,) = _convert(base, nb, "docs/guides/hello-world.ipynb")
    assert ("    - Go to the platform.\n\n         <blockquote>\n\n         **Important**\n\n"
            "         Use Qiskit Runtime v0.44.0 or later.\n\n         </blockquote>\n\n"
            "    - Generate your API key.\n") in text


def test_code_is_never_changed(base):
    fenced = ("1. Save it:\n\n    ```python\n    QiskitRuntimeService.save_account(\n"
              '        token="<your-api-key>",\n        instance="<CRN>", # Optional\n    )\n    ```\n')
    nb = _nb(_md(fenced + "\nUse `<Admonition>` and `[x](/docs/guides/y)` like this.\n"
                 "<Admonition type=\"note\">\n```python\nprint('<Image src=\"/docs/a.png\" />')\n\n\n"
                 "x = 1\n```\n</Admonition>\n"))
    _, (text,) = _convert(base, nb, "docs/guides/hello-world.ipynb")
    assert fenced in text
    assert "Use `<Admonition>` and `[x](/docs/guides/y)` like this." in text
    assert "```python\nprint('<Image src=\"/docs/a.png\" />')\n\n\nx = 1\n```" in text


def test_tooltips_videos_comments_and_accordions(base):
    nb = _nb(_md("{/* cspell:ignore Watrous */}\n\nA <DefinitionTooltip definition=\"A *string* is a "
                 "finite sequence of symbols, like $a_1 a_2$ & <b>\">string</DefinitionTooltip> here.\n\n"
                 "<IBMVideo id=\"134056223\" title=\"In this video, John Watrous introduces entanglement.\"/>\n\n"
                 "<Accordion>\n  <AccordionItem title=\"Click to view `source_files\\engine.py`\">\n"
                 "    <CodeCellPlaceholder tag=\"id-engine\" />\n  </AccordionItem>\n</Accordion>\n"),
             _code("print(1)", tags=["id-engine"]))
    _, texts = _convert(base, nb)
    text = texts[0]
    assert "cspell" not in text and "{/*" not in text
    assert ('A <abbr title="A string is a finite sequence of symbols, like a_1 a_2 &amp; &lt;b&gt;">'
            "string</abbr> here.") in text
    assert ("**Video** (online): [In this video, John Watrous introduces entanglement.]"
            "(https://video.ibm.com/recorded/134056223)") in text
    assert ("<details>\n<summary>Click to view <code>source_files\\engine.py</code></summary>\n\n"
            "*The code is in a code cell further down in this notebook.*\n\n</details>") in text
    assert "<Accordion" not in text and "<CodeCellPlaceholder" not in text


def test_unknown_components_keep_their_content(base):
    nb = _nb(_md("<Tabs>\n<TabItem value=\"mac\" label=\"macOS\">\nOpen a terminal.\n</TabItem>\n</Tabs>\n\n"
                 "<LeftColoredBar color=\"blue\">\nKept.\n</LeftColoredBar>\n\n<SomethingNew x=\"1\" />\nEnd.\n"))
    _, (text,) = _convert(base, nb)
    assert text == "**macOS**\n\nOpen a terminal.\n\nKept.\n\nEnd.\n"


def test_pictures_of_outputs_show(base):
    out = {"output_type": "execute_result", "execution_count": 3, "metadata": {},
           "data": {"text/plain": ['<Image src="/docs/images/tutorials/chsh-inequality/extracted-outputs/'
                                   '1b2c-0.avif" alt="Output of the previous code cell" />']}}
    text_out = {"output_type": "stream", "name": "stdout", "text": ["<Image is just text here\n"]}
    nb = _nb(_md("# T\n"), _code("qc.draw()", [out, text_out]))
    changed, _ = _convert(base, nb, "docs/tutorials/chsh-inequality.ipynb")
    assert changed
    assert out["data"] == {
        "text/markdown": ["![Output of the previous code cell](../../" + OUTPUT + ")"],
        "text/plain": ["Output of the previous code cell"]}
    assert text_out == {"output_type": "stream", "name": "stdout", "text": ["<Image is just text here\n"]}


def test_a_cell_without_website_markup_stays_as_it_is(base):
    source = "# Title\n\n\n\nText with  trailing spaces   \n<details>\n<summary>S</summary>\n\nx\n</details>\n"
    nb = _nb(_md(source))
    changed, (text,) = _convert(base, nb)
    assert not changed and text == source


def test_converting_twice_changes_nothing(base):
    nb = _nb(_md("---\ntitle: T\n---\n\n# T\n<Admonition type=\"note\">\nA [link](/docs/guides/hello-world) "
                 "and ![p](/learning/images/courses/basics-of-quantum-information/quantum-circuits/"
                 "Boolean-circuit-XOR.svg)\n</Admonition>\n"), minor=4)
    nb["cells"][0]["id"] = "intro"
    assert sit.convert_notebook(nb, base / LESSON, base)
    once = json.dumps(nb, sort_keys=True)
    assert not sit.convert_notebook(nb, base / LESSON, base)
    assert json.dumps(nb, sort_keys=True) == once


def test_cell_ids_in_an_old_notebook_make_it_valid(base):
    # 41 of the upstream notebooks: nbformat 4.2/4.4 with cell ids, which
    # Jupyter reports as "Notebook validation failed"
    nb = _nb(_md("# A\n", id="a"), _code("x", id="a"), _code("y", id="bad id!"), _code("z"), minor=4)
    assert sit.convert_notebook(nb, base / LESSON, base)
    assert nb["nbformat_minor"] == 5
    ids = [c["id"] for c in nb["cells"]]
    assert ids[0] == "a" and len(set(ids)) == 4
    assert all(len(i) <= 64 and i.replace("-", "").replace("_", "").isalnum() for i in ids)
    plain = _nb(_md("# A\n"), minor=4)
    assert not sit.convert_notebook(plain, base / LESSON, base) and plain["nbformat_minor"] == 4


def test_converted_notebooks_are_valid(base):
    nbformat = pytest.importorskip("nbformat")
    nb = _nb(_md("---\ntitle: T\n---\n\n# T\n<Admonition>x</Admonition>\n", id="m"),
             _code("x", [{"output_type": "display_data", "metadata": {},
                          "data": {"text/plain": ['<Image src="/docs/images/x.svg" alt="o" />']}}], id="c"),
             minor=2)
    sit.convert_notebook(nb, base / LESSON, base)
    nbformat.validate(nbformat.from_dict(nb))


def test_the_whole_download_is_converted_once(base):
    lesson = base / LESSON
    lesson.write_text(json.dumps(_nb(_md("---\ntitle: C\n---\n\n# C\n"))))
    os.chmod(lesson, 0o640)
    broken = base / "docs" / "tutorials" / "notes.ipynb"
    broken.write_text("my notes")
    assert sit.convert_learning_content(base) == 1
    assert json.loads(lesson.read_text())["cells"][0]["source"] == ["# C\n"]
    assert stat.S_IMODE(lesson.stat().st_mode) == 0o640
    assert broken.read_text() == "my notes"
    assert (base / sit.CONVERTED_MARKER).read_text().strip() == sit.CONVERTER_VERSION
    assert not list(base.rglob("*.rq-tmp"))
    # once: a later start does not open the notebooks again
    lesson.write_text(json.dumps(_nb(_md("---\ntitle: C\n---\n"))))
    assert sit.convert_learning_content(base) == 0
    assert "title: C" in lesson.read_text()
    assert sit.convert_learning_content(base, force=True) == 1


def test_an_empty_folder_gets_no_marker(tmp_path):
    assert sit.convert_learning_content(tmp_path) == 0
    assert not (tmp_path / sit.CONVERTED_MARKER).exists()
