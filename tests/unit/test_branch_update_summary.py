"""
Update from GitHub branch says what it changed (H-42, rig check 2026-10-23):
it said "Scripts updated" and "Config files updated" also when the branch
was the one installed. count_changes counts the scripts and config files
that are new or different; the merged env file and the rebuilt menu cache
do not count. The menu's box shows the updater's own summary line.
"""

import os
import re
import shutil
import subprocess

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_UPDATER = os.path.join(_ROOT, "RQB2-bin", "rq_update_from_branch.sh")
_MENU = os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")


def _count(tmp_path):
    text = open(_UPDATER).read()
    fn = re.search(r"^count_changes\(\) \{.*?^\}\n", text, re.S | re.M).group(0)
    script = (f'TARGET_BIN="{tmp_path}/usr-bin"; TARGET_CONFIG="{tmp_path}/usr-config"\n{fn}'
              f'count_changes "{tmp_path}/src"; echo "$CHANGED_BIN $CHANGED_CFG"')
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return tuple(int(v) for v in proc.stdout.split())


def _tree(tmp_path):
    files = {"RQB2-bin/rq_a.sh": "a", "RQB2-bin/rq_b.py": "b",
             "RQB2-config/demo-groups.json": "{}", "RQB2-config/LED-Logos/x.png": "png",
             "RQB2-config/rasqberry_environment.env": "LED_LAYOUT=x\n",
             "RQB2-config/demo-menu-cache.sh": "cache"}
    for rel, body in files.items():
        for base, name in (("src", rel), ("usr-bin" if rel.startswith("RQB2-bin") else "usr-config",
                                          rel.split("/", 1)[1])):
            p = tmp_path / base / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)


def test_the_installed_branch_changes_nothing(tmp_path):
    _tree(tmp_path)
    # the device's own settings and menu cache differ: still nothing changed
    (tmp_path / "usr-config/rasqberry_environment.env").write_text("LED_LAYOUT=quad-4x12\n")
    (tmp_path / "usr-config/demo-menu-cache.sh").write_text("device cache")
    assert _count(tmp_path) == (0, 0)


def test_new_and_different_files_are_counted(tmp_path):
    _tree(tmp_path)
    (tmp_path / "src/RQB2-bin/rq_a.sh").write_text("a2")
    (tmp_path / "src/RQB2-bin/rq_new.sh").write_text("new")
    (tmp_path / "src/RQB2-config/LED-Logos/x.png").write_text("png2")
    assert _count(tmp_path) == (2, 1)


def test_the_summary_and_the_menu_box_say_it():
    text = open(_UPDATER).read()
    assert 'count_changes "$WORK_DIR"' in text
    assert "Already up to date: no script or config file differs from this branch." in text
    assert 'info "Changed: $CHANGED_BIN script(s)' in text
    menu = open(_MENU).read()
    assert "grep -oE '(Changed|Already up to date): .*'" in menu
    assert "Scripts updated in /usr/bin/" not in menu


@pytest.mark.parametrize("env, want", [
    ({}, "JanLahmann/RasQberry-Two"),
    ({"RQB_GIT_USER": "someone", "REPO": "RasQberry-Two"}, "someone/RasQberry-Two"),
])
def test_the_repository_is_only_the_name_not_its_log_line(tmp_path, env, want):
    # rig check 2026-10-24: the log line went into the clone URL
    # ("https://github.com/[2026-10-24 08:20:13] Using default repository: ...")
    text = open(_UPDATER).read()
    fns = "".join(re.search(rf"^{n}\(\) \{{.*?^\}}\n", text, re.S | re.M).group(0)
                  for n in ("log_message", "detect_current_repo"))
    script = (f'LOG_FILE=/dev/null; DEFAULT_REPO=JanLahmann/RasQberry-Two; USER_HOME="{tmp_path}"\n'
              f'{fns}r=$(detect_current_repo 2>/dev/null); echo "$r"')
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env=dict({"PATH": os.environ["PATH"]}, **env))
    assert proc.stdout == want + "\n"
