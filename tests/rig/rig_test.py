#!/usr/bin/env python3
"""
RasQberry rig test (issue #234): test a real image on the test Pis.

Runs from a machine on the rig's network (not in CI: the Pis and the camera
are on a local LAN). For every Pi in rig.json it

  1. optionally installs a release into the other A/B slot and boots it
     (--update TAG: OTA the release into the slot that is not running),
  2. runs the system checks (tests/rig/pi/checks.sh),
  3. smoke-tests each demo the way a person does - desktop terminal, runs,
     Ctrl+C, nothing left behind (tests/rig/pi/demo_smoke.sh),
  4. for LED demos, first checks the Pi's LED layout against rig.json and that
     its panel_crop still frames the panel (a corner pattern on the camera),
     then checks that each demo actually lights the panel,
  5. for web/Jupyter/docker demos, checks the page in the demo's own Chromium
     tab (tests/rig/pi/webcheck.py): it renders, a control responds, a
     notebook's first safe code cell runs - never one that touches the IBM
     Quantum account; ~/.qiskit is backed up and restored around the check,
  6. with --icons, starts demos by double-clicking their desktop icons with a
     real (uinput) mouse (tests/rig/pi/mouse.py),

and writes results/<timestamp>/report.md with screenshots and camera frames.
Exit status 1 if anything failed.

Usage:
    python3 tests/rig/rig_test.py                       # all Pis, all demos
    python3 tests/rig/rig_test.py --pi pi5 --demos quantum-lights-out,rasq-led
    python3 tests/rig/rig_test.py --update beta-2026-09-30-142314
    python3 tests/rig/rig_test.py --checks-only
    python3 tests/rig/rig_test.py --demos none --icons --docker

Needs on this machine: ssh (key login to the Pis), ffmpeg, Python 3 + Pillow.
Needs on the Pis: nothing beyond the image (key login for the rig user).
"""

import argparse
import atexit
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
REMOTE_DIR = "/tmp/rigtest"
# the rig user's (the ssh login, rig.json "host"/"user"): with a renamed user
# a /home/* glob could also match the old home and run the wrong python
VENV_PY = "$HOME/RasQberry-Two/venv/RQB2/bin/python3"
CLEAR_LEDS = f"sudo {VENV_PY} /usr/bin/turn_off_LEDs.py >/dev/null 2>&1"
HOLDER_PID = f"{REMOTE_DIR}/led_fill.pid"
GITHUB_REPO = "JanLahmann/RasQberry-Two"
# --update: release images are downloaded once into this cache (RIG_IMAGE_CACHE)
# and every such download is logged in OWN_DOWNLOADS (CSV: date_utc, tag,
# asset, bytes, purpose), so the project's download numbers can leave ours out
IMAGE_CACHE = Path(os.environ.get("RIG_IMAGE_CACHE") or "~/.cache/rasqberry-rig/images").expanduser()
CACHE_KEEP = 3                             # releases kept in the cache
OWN_DOWNLOADS = Path.home() / ".local" / "share" / "rasqberry-rig" / "own-image-downloads.csv"
PI_IMAGE_DIR = "/var/tmp/rigtest-image"    # the copy on the Pi (rq_update_slot.sh --image-file)
UPDATE_LOG = "/var/log/rasqberry-update-slot.log"
REAL_PATH = "real-path-test"               # OWN_DOWNLOADS purpose of a real user's update
CDP_PORT = 9222   # the desktop Chromium's debugging port during web checks (127.0.0.1)
# Rig runs stay out of the project's usage counts (rq_umami_event.py): RQ_UMAMI=0
# in the Pi's environment file reaches demos started from the desktop icons too,
# the health check and the timers, and an update carries it into the new slot
ENV_FILE = "/usr/config/rasqberry_environment.env"
NO_USAGE_COUNTS = (f"grep -qx RQ_UMAMI=0 {ENV_FILE} || {{ sudo sed -i '/^RQ_UMAMI=/d' {ENV_FILE} "
                   f"&& echo RQ_UMAMI=0 | sudo tee -a {ENV_FILE} >/dev/null; }}")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def rig_pi(pi):
    """
    One Pi of rig.json with its login user: "user", or the user in "host"
    (user@address), else rasqberry (the image's default). Every command runs
    over ssh as this user, the desktop user ($HOME, its uid's Wayland session),
    so a renamed user (Imager, #319) only needs its name here.

    Returns:
        dict: the entry with "user" set and "host" as user@address.
    """
    pi = dict(pi)
    user, addr = pi.get("user"), pi["host"]
    if "@" in addr:
        host_user, addr = addr.split("@", 1)
        if user and user != host_user:
            raise SystemExit(f"rig.json: {pi['name']}: user {user!r} but host {pi['host']!r}")
        user = host_user
    pi["user"] = user or "rasqberry"
    pi["host"] = f"{pi['user']}@{addr}"
    return pi


def ssh(host, command, timeout=600, check=False):
    """Run a command on a Pi; returns (rc, stdout)."""
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, command],
        capture_output=True, text=True, timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"{host}: {command!r} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout


def scp(host, sources, dest, timeout=120):
    """Copy local files to the Pi."""
    subprocess.run(["scp", "-q", *map(str, sources), f"{host}:{dest}"], check=True, timeout=timeout)


def fetch(host, remote, local):
    """Copy a file from the Pi; ignore missing files."""
    subprocess.run(["scp", "-q", f"{host}:{remote}", str(local)], timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# A demo that needs an IBM Quantum account fails like this when the Pi's saved
# key is missing or invalid: that is the rig's set-up, not the image - WARN
ACCOUNT_ERRORS = re.compile(r"InvalidAccountError|IBMNotAuthorizedError|AccountNotFoundError|"
                            r"Unable to retrieve instances|API key could not be found")


def parse_lines(text):
    """Parse 'VERDICT name | detail' lines into dicts."""
    out = []
    for line in text.splitlines():
        head, _, detail = line.partition(" | ")
        parts = head.split(None, 1)
        if len(parts) == 2 and parts[0] in ("PASS", "FAIL", "WARN", "INFO", "SKIP"):
            verdict, detail = parts[0], detail.strip()
            if verdict == "FAIL" and ACCOUNT_ERRORS.search(detail):
                verdict, detail = "WARN", detail + " (needs a valid IBM Quantum account on this Pi)"
            # the demo's own tab loaded, only the test click timed out (IBM's
            # Composer is heavy for the 2 GB Pi 4): the demo worked
            elif verdict == "FAIL" and "tab=demo" in detail and "check error: TimeoutError" in detail:
                verdict, detail = "WARN", detail + " (page loaded; the test click timed out)"
            out.append({"verdict": verdict, "name": parts[1], "detail": detail})
    return out


def wait_for(host, predicate_cmd, timeout, interval=10, fail_cmd=None):
    """
    Poll until the command succeeds on the Pi (e.g. after a reboot). With
    fail_cmd: raise RuntimeError with its output as soon as it succeeds.
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            if ssh(host, predicate_cmd, timeout=30)[0] == 0:
                return True
            if fail_cmd:
                rc, out = ssh(host, fail_cmd, timeout=30)
                if rc == 0:
                    raise RuntimeError(f"stopped on the Pi: {out.strip()[-300:]}")
        except subprocess.TimeoutExpired:
            pass
        time.sleep(interval)
    return False


# ----------------------------------------------------------------------------
# camera
# ----------------------------------------------------------------------------
class Camera:
    """A persistent RTSP reader that keeps one fresh frame on disk (~1 fps)."""

    def __init__(self, url, workdir):
        self.url = url
        self.latest = Path(workdir) / "camera_latest.png"
        self.proc = None

    def start(self):
        """Start ffmpeg and wait for the first frame (keyframe wait ~10 s)."""
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "quiet", "-rtsp_transport", "tcp", "-i", self.url,
             "-vf", "fps=1", "-update", "1", "-y", str(self.latest)],
            stdin=subprocess.DEVNULL,
        )
        # an aborted or killed run must not leave the stream behind: stale
        # readers hold RTSP sessions and garble later runs' frames
        atexit.register(self.stop)
        for _ in range(40):
            if self.latest.exists() and self.latest.stat().st_size > 0:
                return True
            time.sleep(1)
        return False

    def grab(self, dest):
        """Copy the current frame to dest (after ~2 s so it is fresh)."""
        from PIL import Image
        time.sleep(2)
        for _ in range(10):  # ffmpeg rewrites the file in place: retry partial reads
            dest.write_bytes(self.latest.read_bytes())
            try:
                with Image.open(dest) as im:
                    im.load()
                return dest
            except OSError:
                time.sleep(0.3)
        raise RuntimeError("camera: could not read a complete frame")

    def stop(self):
        """Stop ffmpeg (also at exit, and on SIGTERM/SIGHUP via main)."""
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class PanelLock:
    """
    One camera judgement at a time.

    The Pis' panels share the camera view: while one Pi's LED demo is judged,
    no other Pi may light its panel or change it. Held across threads and
    across harness processes run side by side (--pi pi5 & --pi pi4).
    """

    def __init__(self):
        self.path = Path(tempfile.gettempdir()) / "rasqberry-rigtest-panels.lock"
        self.local = threading.Lock()
        self.fh = None

    def __enter__(self):
        self.local.acquire()
        self.fh = open(self.path, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()
        self.local.release()


PANEL_LOCK = PanelLock()


def clear_all_panels(pis):
    """
    Switch every Pi's LEDs off (in parallel).

    Returns:
        list: names of the Pis whose panel could not be cleared.
    """
    failed = []

    def one(p):
        try:
            if ssh(p["host"], CLEAR_LEDS, timeout=60)[0] != 0:
                failed.append(p["name"])
        except subprocess.TimeoutExpired:
            failed.append(p["name"])

    threads = [threading.Thread(target=one, args=(p,)) for p in pis]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return failed


def fresh_baseline(pis, camera, dest):
    """
    A frame with every panel off, taken now.

    A baseline from the start of the run goes stale: daylight and the camera's
    auto exposure drift, and a stale one made a dark panel score 0.01-0.04
    ("partly lit"). Take it right before each judgement, under PANEL_LOCK.

    Returns:
        tuple: (frame path, list of Pis that could not be cleared)
    """
    failed = clear_all_panels(pis)
    time.sleep(3)   # last frame out, camera exposure settled
    return camera.grab(dest), failed


LIT_DELTA = 40   # grey levels brighter than the baseline: "clearly lit"
# The corner pattern, judged inside panel_crop (fractions of the crop): each
# corner block must light its own quarter's outer part, the origin's block
# (3x3, the others 2x2) top left; the band between them must stay mostly dark.
MIDDLE_X, MIDDLE_Y = (0.3, 0.7), (0.4, 0.6)
CORNER_MIN_SHARE = 0.05    # of the lit samples, in each corner
ORIGIN_MIN_REDNESS = 10    # the red origin block: top left this much redder than the next corner
MIDDLE_MAX_SHARE = 0.2     # of the lit samples, between the corners
SAMPLES = (96, 32)         # about 4 per LED of a 24x8 panel
SAMPLE_LIT = 0.05          # share of a sample's camera pixels that must be lit
MIN_LIT_SAMPLES = 20       # fewer: the pattern is not out (or the panel is dark)
FIND_GRID = (160, 90)      # samples over the whole frame when looking for the panel
FRAME_ASPECT = 16 / 9      # the camera's frame
FIND_LEVEL = 0.08          # top (bottom) blocks level, left (right) blocks aligned: share of the frame
FIND_MAX_BLOB = 0.03       # a blob bigger than this share of the frame is no LED block (light, a screen)
CROP_MARGIN = 0.02         # around the corner blocks, as a share of the frame
PANEL_ASPECT = (2.0, 4.5)  # width/height of the corner rectangle on camera (24x8 panels: about 3);
                           # a wrong layout drawing its corners inside the panel gives another shape
MOVED_INSIDE = 0.8         # less of the found panel inside rig.json's crop: the camera moved


def inside(a, b):
    """Share of box a that lies inside box b ([x1, y1, x2, y2])."""
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return iw * ih / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))


def lit_samples(frame, baseline, crop, size):
    """
    Which samples of the crop are lit: per camera pixel as lit_score judges,
    then a sample counts when SAMPLE_LIT of its pixels are.

    Returns:
        PIL.Image: size, 255 = lit sample, 0 = dark
    """
    from PIL import Image
    lit_px = lit_diff(frame, baseline, crop).point(lambda v: 255 if v >= LIT_DELTA else 0)
    return lit_px.resize(size, Image.BOX).point(lambda v: 255 if v >= 255 * SAMPLE_LIT else 0)




def crop_diff(frame, baseline, crop, mode="L"):
    """The crop of the frame minus the baseline (mode "L": greyscale, "RGB": colour)."""
    from PIL import Image, ImageChops
    a, b = Image.open(frame).convert(mode), Image.open(baseline).convert(mode)
    w, h = a.size
    box = tuple(int(v * (w if i % 2 == 0 else h)) for i, v in enumerate(crop))
    return ImageChops.subtract(a.crop(box), b.crop(box))


def lit_diff(frame, baseline, crop):
    """The crop of the frame minus the baseline, as a greyscale image."""
    return crop_diff(frame, baseline, crop)


def redness(frame, baseline, crop, size):
    """
    Per sample of the crop: how much redder than the baseline it got
    (red minus the mean of green and blue), for the red origin block.

    Returns:
        list: one value per sample, row by row
    """
    from PIL import Image
    r, g, bl = crop_diff(frame, baseline, crop, "RGB").resize(size, Image.BOX).split()
    return [rv - (gv + bv) / 2 for rv, gv, bv in zip(r.getdata(), g.getdata(), bl.getdata())]


def lit_score(frame, baseline, crop):
    """
    How much of the panel region is lit, compared with the LEDs off: the share
    of LED-sized samples (SAMPLES) that brightened. Per camera pixel, a dim
    pattern of a few LEDs (Lights Out's grid) scored "dark" in daylight: a lit
    dot covers only a few pixels, and in daylight only some of them clear
    LIT_DELTA.

    Args:
        frame, baseline (Path): camera frames with the demo running / LEDs off.
        crop (list): [x1, y1, x2, y2] as fractions of the frame size.

    Returns:
        float: share of the samples in the crop that lit up (0..1).
    """
    data = lit_samples(frame, baseline, crop, SAMPLES).getdata()
    return sum(1 for v in data if v) / len(data)


# ----------------------------------------------------------------------------
# steps
# ----------------------------------------------------------------------------
def no_usage_counts(pi):
    """
    Switch the usage counts off on this Pi (NO_USAGE_COUNTS), and mark the card
    as ours (rasqberry-internal on CONFIG on A/B cards, else bootfs) if that was
    forgotten after writing it: then its first start was counted once.
    """
    if ssh(pi["host"], NO_USAGE_COUNTS, timeout=60)[0] != 0:
        raise RuntimeError("could not set RQ_UMAMI=0 (usage counts off)")
    # where rq_umami_event.internal_card looks: CONFIG on A/B cards, else bootfs
    _, out = ssh(pi["host"], "d=/boot/firmware; [ -e /boot/config/autoboot.txt ] && d=/boot/config; "
                             "ls $d/rasqberry-internal* >/dev/null 2>&1 || "
                             "{ sudo touch $d/rasqberry-internal && echo $d; }", timeout=60)
    if out.strip():
        print(f"   {pi['name']}: card marked as ours now ({out.strip()}/rasqberry-internal): "
              "its first start was counted; mark rig cards right after writing them")


def file_sha256(path):
    """SHA256 of a file, as hex."""
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def log_own_download(tag, name, size, purpose="rig-update"):
    """One row in OWN_DOWNLOADS: a GitHub download of ours, for the stats to subtract."""
    new = not OWN_DOWNLOADS.exists()
    OWN_DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
    with OWN_DOWNLOADS.open("a") as log:
        if new:
            log.write("date_utc,tag,asset,bytes,purpose\n")
        when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log.write(f"{when},{tag},{name},{size},{purpose}\n")


def cached_image(tag):
    """
    The release's A/B image from this machine's cache, downloaded from GitHub
    once per release (logged, checked against GitHub's SHA256).

    Returns:
        tuple: (Path of the .img.xz, its SHA256, its GitHub URL)
    """
    assets = json.loads(subprocess.run(
        ["gh", "api", f"repos/{GITHUB_REPO}/releases/tags/{tag}", "--jq",
         '[.assets[]|select(.name|endswith("-ab.img.xz"))|{name, size, digest, url: .browser_download_url}]'],
        capture_output=True, text=True, check=True).stdout)
    if len(assets) != 1 or not (assets[0].get("digest") or "").startswith("sha256:"):
        raise RuntimeError(f"release {tag}: no single A/B image with a SHA256 on GitHub")
    a = assets[0]
    sha = a["digest"].split(":", 1)[1]
    path = IMAGE_CACHE / tag / a["name"]
    checked = path.with_name(path.name + ".sha256")    # written once the file matched
    path.parent.mkdir(parents=True, exist_ok=True)
    # one harness at a time per release: two side by side make one download
    with open(path.parent / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (path.exists() and path.stat().st_size == a["size"]
                and checked.exists() and checked.read_text().strip() == sha):
            print(f"  downloading {a['name']} once into {path.parent}")
            log_own_download(tag, a["name"], a["size"])    # first: GitHub counts a broken-off one too
            subprocess.run(["gh", "release", "download", tag, "--repo", GITHUB_REPO, "--pattern", a["name"],
                            "--dir", str(path.parent), "--clobber"], check=True)
            if file_sha256(path) != sha:
                path.unlink()
                raise RuntimeError(f"{a['name']}: downloaded, but its SHA256 is not GitHub's")
            checked.write_text(sha + "\n")
    old = sorted((d for d in IMAGE_CACHE.iterdir() if d.is_dir() and d != path.parent), key=lambda d: d.stat().st_mtime)
    for d in old[:max(0, len(old) - (CACHE_KEEP - 1))]:
        shutil.rmtree(d, ignore_errors=True)
    return path, sha, a["url"]


def real_path_tested(tag):
    """True once a real-path update of `tag` ran on some Pi (logged in OWN_DOWNLOADS)."""
    return OWN_DOWNLOADS.exists() and any(
        line.split(",")[1:2] == [tag] and line.strip().endswith(f",{REAL_PATH}")
        for line in OWN_DOWNLOADS.read_text().splitlines())


def latest_on_pi(pi):
    """
    What the Pi's own release lookup offers, as the menu and the taskbar's
    update notice get it (rq_ab_releases.sh latest: rasqberry.org's manifest).

    Returns:
        dict: tag, url, size, sha256 (empty if the lookup fails)
    """
    rc, out = ssh(pi["host"], "rq_ab_releases.sh latest", timeout=120)
    fields = out.strip().split("\t")
    if rc != 0 or len(fields) < 5:
        return {}
    return dict(zip(("tag", "url", "date", "size", "sha256"), fields))


def check_imager_entry(tag):
    """
    The Imager lists on rasqberry.org (RQB-images.json, rpi-imager.json)
    against GitHub for this release's images: URL, size and SHA256 a card
    written from them gets. Short of writing a card.

    Returns:
        dict: a report row
    """
    assets = {a["name"]: a for a in json.loads(subprocess.run(
        ["gh", "api", f"repos/{GITHUB_REPO}/releases/tags/{tag}", "--jq", "[.assets[]|{name, size, digest}]"],
        capture_output=True, text=True, check=True).stdout)}
    errors, seen = [], 0
    for listing in ("RQB-images.json", "rpi-imager.json"):
        with urllib.request.urlopen(f"https://rasqberry.org/{listing}", timeout=30) as r:
            doc = json.load(r)
        entries, todo = [], list(doc.get("os_list", []))
        while todo:                                   # dev images sit in a sub-list
            e = todo.pop()
            todo += e.get("subitems", [])
            entries.append(e)
        for entry in entries:
            url = entry.get("url", "")
            if f"/{tag}/" not in url:
                continue
            seen += 1
            asset = assets.get(url.rsplit("/", 1)[-1])
            sha = entry.get("image_download_sha256") or entry.get("image_sha256")
            if not asset:
                errors.append(f"{listing}: {url} is no asset of {tag}")
            elif entry.get("image_download_size") != asset["size"] or (sha and f"sha256:{sha}" != asset["digest"]):
                errors.append(f"{listing}: {url.rsplit('/', 1)[-1]} size/SHA256 differ from GitHub")
    if errors:
        return {"verdict": "FAIL", "name": "imager-lists", "detail": "; ".join(errors)}
    if not seen:
        return {"verdict": "INFO", "name": "imager-lists", "detail": f"{tag} is in neither Imager list (not the newest of its stream)"}
    return {"verdict": "PASS", "name": "imager-lists", "detail": f"{seen} entries for {tag}: URL, size and SHA256 as on GitHub"}


def update_slot(pi, tag):
    """
    OTA `tag` into the slot that is not running (ping-pong); the running slot
    stays as the way back. The first update to a new release that the Pi
    itself offers as its latest goes the real user's way (REAL_PATH: the Pi's
    own lookup, its own updater, its own GitHub download); after that, the
    image comes from this machine's cache (--image-file) and the updater from
    this checkout.

    Returns:
        list: report rows about the path taken
    """
    host = pi["host"]
    # a slot still on trial refuses updates (exit 28): wait for its health check
    if not wait_for(host, "sudo rq_slot_manager.sh status 2>&1 | grep -q 'Slot Status: CONFIRMED'", 600):
        raise RuntimeError("the running slot is not confirmed")
    # the root partition before the update: the new slot is the other one
    # (the same tag may already run here, so the version alone proves nothing)
    _, before = ssh(host, "findmnt -no SOURCE /")
    before = before.strip()
    offer = latest_on_pi(pi)
    real = offer.get("tag") == tag and not real_path_tested(tag)
    # The operator chose the release: the guard's questions (downgrade, last
    # beta/stable slot) are answered yes, as nobody is at the Pi to type them.
    guard = "--allow-downgrade --force-replace-safe-slot"
    if real:
        name = offer["url"].rsplit("/", 1)[-1]
        log_own_download(tag, name, offer["size"], REAL_PATH)   # first: GitHub counts a broken-off one too
        rows = [{"verdict": "INFO", "name": "update-path",
                 "detail": f"real: the Pi's own lookup offered {tag}; its updater downloaded {name} from GitHub"},
                check_imager_entry(tag)]
        cmd = (f"/usr/bin/rq_update_slot.sh {shlex.quote(offer['url'])} {shlex.quote(tag)} "
               f"--sha256 {offer['sha256']} {guard}")
        print(f"  {pi['name']}: installing {tag} the real user's way (download on the Pi, 15-30 min)")
        _run_update(pi, tag, before, cmd)
    else:
        image, digest, url = cached_image(tag)
        rows = [{"verdict": "INFO", "name": "update-path",
                 "detail": f"cached (real path {'done before' if real_path_tested(tag) else 'needs ' + tag + ' to be the latest the Pi offers'})"}]
        ssh(host, f"mkdir -p {REMOTE_DIR}/ota {PI_IMAGE_DIR}", check=True)
        scp(host, [REPO / "RQB2-bin" / f for f in ("rq_update_slot.sh", "rq_stream_image.py", "rq_slot_manager.sh",
                                                   "rq_carry_ssh_identity.sh", "rq_common.sh")],
            f"{REMOTE_DIR}/ota/")
        print(f"  {pi['name']}: installing {tag} into the other slot (15-25 min)")
        remote_image = f"{PI_IMAGE_DIR}/{image.name}"
        try:
            scp(host, [image], remote_image, timeout=1800)
            ssh(host, f"chmod +x {REMOTE_DIR}/ota/*.sh", timeout=60)
            _run_update(pi, tag, before, f"{REMOTE_DIR}/ota/rq_update_slot.sh {shlex.quote(url)} {shlex.quote(tag)} "
                                         f"--sha256 {digest} --image-file {remote_image} {guard}")
        finally:
            ssh(host, f"sudo rm -rf {PI_IMAGE_DIR}", timeout=60)   # left over only if the update failed
    # the health check confirms the new slot a minute or two after boot; the
    # service may not have started yet when the release first answers
    wait_for(host, "sudo rq_slot_manager.sh status 2>&1 | grep -q 'Slot Status: CONFIRMED'", 600)
    return rows


def _run_update(pi, tag, before, cmd):
    """Start `cmd` (an rq_update_slot.sh call) on the Pi and wait for the new slot to run `tag`."""
    host = pi["host"]
    # "seen": the update log's lines so far, so only this run's failure counts
    _, seen = ssh(host, f"sudo wc -l < {UPDATE_LOG} 2>/dev/null || echo 0; "
                        f"sudo setsid nohup {cmd} </dev/null >{REMOTE_DIR}/ota.log 2>&1 &", timeout=60)
    if not wait_for(host, f"grep -qx {shlex.quote(tag)} /etc/rasqberry-version && "
                          f"[ \"$(findmnt -no SOURCE /)\" != {shlex.quote(before)} ]", 3600, interval=30,
                    fail_cmd=f"sudo tail -n +{int(seen.split()[0]) + 1} {UPDATE_LOG} | grep -q 'Update stopped' "
                             f"&& tail -5 {REMOTE_DIR}/ota.log"):
        raise RuntimeError("new slot did not come up with the release")


def run_checks(pi):
    """Copy the Pi-side scripts and run the system checks."""
    host = pi["host"]
    ssh(host, f"mkdir -p {REMOTE_DIR}", check=True)
    scp(host, [HERE / "pi" / f for f in ("checks.sh", "demo_smoke.sh", "led_fill.py", "mouse.py", "keyboard.py",
                                         "webcheck.py")], f"{REMOTE_DIR}/")
    _, out = ssh(host, f"bash {REMOTE_DIR}/checks.sh", timeout=300)
    return parse_lines(out)


def list_demos(pi):
    """
    Demo ids with their type, LED need and launcher, from the Pi's manifests
    (a variant's own type and launcher win: Fun with Quantum's website variant
    is a script that opens a page, its notebooks are Jupyter).
    """
    # built-in demos, plus demos added from the catalogue (user manifests).
    # A demo that runs another's Docker image (install.docker_image_of: Qiskit
    # Tutorials on this Pi) is a docker demo too: --docker only
    _, out = ssh(pi["host"], "for f in /usr/config/demo-manifests/rq_demo_*.json "
                             "$HOME/.local/config/demo-manifests/*.json; do [ -f \"$f\" ] || continue; "
                             "jq -r 'select(.id) | . as $m | [(if ($m.install.docker_image_of // \"\") != \"\" "
                             "then \"docker\" else $m.entrypoint.type end), ($m.needs_hw.leds // false|tostring)] as $c "
                             "| if ([.variants[]?] | length) == 0 then [$m.id] + $c + [$m.entrypoint.launcher // \"\"] "
                             "else ($m.variants[] | [\"\\($m.id):\\(.id)\", (.entrypoint.type // $c[0]), $c[1]] "
                             "+ [.entrypoint.launcher // $m.entrypoint.launcher // \"\"]) end | @tsv' \"$f\"; done")
    demos = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        # a manifest with variants is a menu; each variant is its own demo
        demos.append({"id": parts[0], "type": parts[1], "leds": parts[2] == "true", "launcher": parts[3]})
    return demos


# desktop icons --icons double-clicks by default: an LED demo, a Jupyter
# demo and a docker demo (the docker one runs only with --docker)
DEFAULT_ICONS = "rasq-led.desktop,quantum-paradoxes.desktop,qoffee-maker.desktop"
# the demo group folders the desktop's group icons open (rq_desktop_session.py)
GROUP_DIR = ".local/share/rasqberry/desktop-groups"


def icon_demos(pi, icons, demos):
    """
    The demo each desktop icon starts, read from the icon's Exec line.

    Args:
        icons (list): desktop file names, e.g. "rasq-led.desktop".
        demos (list): list_demos() of this Pi.

    Returns:
        list: demo dicts with an "icon" key (unknown icons: id "?").
    """
    out = []
    for icon in icons:
        # on the desktop, or in its demo group's folder (demo-groups.json)
        q = shlex.quote(icon)
        _, line = ssh(pi["host"], f"f=~/Desktop/{q}; [ -f \"$f\" ] || f=$(ls ~/{GROUP_DIR}/*/{q} 2>/dev/null | head -1); "
                                  f"sed -n 's/^Exec=//p' \"$f\" | head -1")
        words = shlex.split(line.strip()) if line.strip() else []
        spec = None
        runner = [i for i, w in enumerate(words) if w.endswith("rq_demo_run.sh")]
        if runner:
            spec = ":".join(words[runner[0] + 1:runner[0] + 3])
        else:   # a demo's own launcher script
            scripts = {os.path.basename(w) for w in words if w.endswith(".sh")}
            spec = next((d["id"] for d in demos if d["launcher"] and d["launcher"] in scripts), None)
        demo = next((d for d in demos if d["id"] == spec), None)
        if demo is None and spec:   # a menu of variants: the icon asks which
            demo = next(({**d, "id": spec} for d in demos if d["id"].startswith(spec + ":")), None)
        out.append(dict(demo or {"id": "?", "type": "?", "leds": False, "launcher": ""}, icon=icon))
    return out


# Per-demo test hints, for demos a plain "start and watch" cannot judge:
#   keys:    typed into the demo's terminal ("<delay>:<keys>" ...) - accepts the
#            defaults of the text/logo dialogs so the demo reaches its LED output
#   seconds: minimum run time - Lights Out computes its solution before it
#            lights up, which takes ~20 s on a Pi 4
#   dark:    the demo's job is to switch the panel off - lit is the failure.
#            A helper (led_fill.py --hold) lights the panel and keeps holding
#            it, like a program a person forgot; the demo must stop that
#            holder and leave the panel dark (last frame vs. a fresh baseline)
#   service: the panel stays dark by design (Painter starts with an empty
#            canvas), so check instead that the unit driving the LEDs runs at
#            some point (a first start installs the demo first: 90 s)
DEMO_HINTS = {
    "led-demos:text-display": {"keys": r"5:\r 2:\r 2:\r 2:\r"},
    "led-demos:logo-display": {"keys": r"5:\r 2:\r 2:\r 2:\r"},
    "quantum-lights-out:gui": {"seconds": 60},
    "quantum-lights-out:console": {"seconds": 60},
    # a holder owns the panel: Clear LEDs asks "Stop it ...? [Y/n]" - Enter
    "led-demos:clear-leds": {"dark": True, "keys": r"4:\r"},
    "led-painter": {"service": "rasqberry-led-renderer", "seconds": 90},
    # without an IBM account the real backend waits at its account prompt
    "quantum-raspberry-tie:real": {"led_optional": True},
    # web:     what webcheck.py checks on the demo's page - wait: a selector
    #          that must appear; click: the key control; click_at: [x, y] in a
    #          canvas app (negative = from the right/bottom), judged by the
    #          picture changing. Grok Bloch is a Babylon.js canvas: its "X"
    #          gate button sits 140 px from the right edge.
    "grok-bloch:local": {"web": {"wait": "canvas#renderCanvas", "click_at": [-140, 226]}},
    "grok-bloch:web": {"web": {"wait": "canvas#renderCanvas", "click_at": [-140, 226]}},
    "grok-bloch-web": {"web": {"wait": "canvas#renderCanvas", "click_at": [-140, 226]}},
    # load: seconds to wait for the page to load (default 45; webcheck.py
    # polls for the load event). IBM's Composer was still busy after 40 s on
    # the 2 GB Pi 4 (dev-000029, N5): give it 120 s, and the check 180 s.
    "composer": {"web": {"load": 120, "timeout": 180}},
    # title: text the page title must have. The Fun with Quantum website is a
    # web page (a script variant of a Jupyter demo), not a Jupyter UI
    "fun-with-quantum:website": {"web": {"title": "Fun with Quantum"}},
    # answers: "<dialog text>|<keys>;..." - pressed when the text shows. The
    # Workshop & Qiskit Server asks how many participants, then shows their
    # addresses and opens its page after Ok. The address dialog comes only
    # once the server answers (25-30 s on a Pi), so give it 75 s
    # It keeps running when its window closes (by design): "cleanup" stops
    # it before the check (a server left from an earlier run shows its
    # keep/restart/stop menu instead) and after it.
    "doqumentation": {"answers": r"How many participants|\r;Participants open (same|\r",
                      "seconds": 75,
                      "cleanup": "for c in $(docker ps --format '{{.Names}}' | grep -x doqumentation); "
                                 "do docker stop -t 15 \"$c\" >/dev/null; done; true"},
}

# a first start installs the demo after the consent dialog: allow for it
INSTALL_ALLOWANCE = 600


def demo_tag(demo):
    """File-name tag of a demo run (as demo_smoke.sh names its files)."""
    return ("icon-" if demo.get("icon") else "") + demo["id"].replace(":", "-")


def browser_debug(pi, on):
    """
    Turn the remote debugging of the Pi's desktop Chromium on (restart it with
    a 127.0.0.1 debugging port, same profile and page) or off again (restore).

    Returns:
        bool: True if debugging is on (web checks possible).
    """
    sub = "browser-debug" if on else "browser-restore"
    rc, out = ssh(pi["host"], f"RIG_OUT={REMOTE_DIR} RIG_CDP_PORT={CDP_PORT} timeout 90 "
                              f"$HOME/RasQberry-Two/venv/RQB2/bin/python {REMOTE_DIR}/webcheck.py {sub}", timeout=120)
    print(f"   {out.strip()}")
    return on and rc == 0


def smoke_demo(pi, demo, seconds, camera, outdir, all_pis, docker):
    """
    Run one demo smoke test; for LED demos judge the panel with the camera.

    With a camera, an LED demo holds PANEL_LOCK for its whole run, so no other
    Pi (thread or harness process) lights its panel in the shared view while
    one is judged. It is judged unless the Pi's LED setup check failed.
    """
    # with a camera every LED demo holds the lock (it lights the shared view),
    # judged or not
    lit = bool(camera and demo["leds"])
    judged = lit and bool(pi.get("panel_crop")) and pi.get("led_setup_ok", True)
    with PANEL_LOCK if lit else contextlib.nullcontext():
        return _smoke_demo(pi, demo, seconds, camera if judged else None, outdir, all_pis, docker)


def _smoke_demo(pi, demo, seconds, camera, outdir, all_pis, docker):
    """smoke_demo's body (camera is None unless this demo is camera-judged)."""
    hint = DEMO_HINTS.get(demo["id"], {})
    seconds = max(seconds, hint.get("seconds", 0))
    env = "RIG_ALLOW_DOCKER=1 " if docker else ""
    if hint.get("keys"):
        env += f"RIG_KEYS={shlex.quote(hint['keys'])} "
    if hint.get("answers"):
        env += f"RIG_ANSWERS={shlex.quote(hint['answers'])} "
    if pi.get("web_check"):
        env += f"RIG_CDP_PORT={CDP_PORT} "
        if hint.get("web"):
            env += f"RIG_WEB={shlex.quote(json.dumps(hint['web']))} "
    if demo.get("icon"):
        env += f"RIG_ICON={shlex.quote(demo['icon'])} "
        if pi.get("icon_offset"):
            env += f"RIG_ICON_OFFSET={pi['icon_offset'][0]},{pi['icon_offset'][1]} "
    tag = demo_tag(demo)
    crop = pi.get("panel_crop")
    notes = ""
    if demo.get("leds"):
        # A Pi 5 LED stall offers "Lower to 0.2?" in the demo's terminal, and
        # scripted Enter keys answer it with the default: restore the shipped
        # brightness so later LED checks are judged at the same level
        _, level = ssh(pi["host"], "rq_led_brightness.sh --show 2>/dev/null | sed -n 's/.*level=//p'")
        if level.strip() and level.strip() != "normal":
            ssh(pi["host"], "sudo rq_led_brightness.sh --set normal >/dev/null 2>&1")
            notes += f" (brightness was {level.strip()}: reset to normal - a stall dialog answered?)"

    baseline = before = None
    holding = False
    if hint.get("cleanup"):
        ssh(pi["host"], hint["cleanup"], timeout=60)
    try:
        # a fresh baseline right before the demo: every panel off, now
        if camera and not hint.get("service"):
            baseline, unclear = fresh_baseline(all_pis, camera, outdir / f"{pi['name']}-{tag}-baseline.png")
            if unclear:
                notes += f" (baseline: could not clear {','.join(unclear)})"
            if hint.get("dark"):
                # a program holds the panel lit, as when a person picks Clear
                # LEDs: the demo must stop it and leave the panel dark (and
                # the camera is shown to see this Pi's panel at all)
                holding = True
                before = start_holder(pi, camera, baseline, outdir / f"{pi['name']}-{tag}-before.png",
                                      seconds + INSTALL_ALLOWANCE)
        return _run_and_judge(pi, demo, hint, seconds, camera, outdir, env, baseline, before, notes)
    finally:
        if holding:
            stop_holder(pi)   # always: it must never outlive the check
        if hint.get("cleanup"):
            ssh(pi["host"], hint["cleanup"], timeout=60)


def start_holder(pi, camera, baseline, dest, hold):
    """
    Light the Pi's panel with a helper that keeps holding it (led_fill.py
    --hold), and wait until the camera sees it lit.

    Returns:
        float: the lit score of the last frame (below the threshold: the
            panel never lit).
    """
    launch_holder(pi, hold, "0 60 0")
    score, end = 0.0, time.time() + 20
    while time.time() < end:
        score = lit_score(camera.grab(dest), baseline, pi["panel_crop"])
        if score >= pi.get("lit_threshold", 0.006):
            break
    return score


def launch_holder(pi, hold, pattern):
    """Start led_fill.py --hold on the Pi with `pattern` (its other arguments)."""
    ssh(pi["host"], f"sudo rm -f {HOLDER_PID}; sudo setsid nohup {VENV_PY} {REMOTE_DIR}/led_fill.py "
                    f"--hold {int(hold)} --pidfile {HOLDER_PID} {pattern} >{REMOTE_DIR}/led_fill.log 2>&1 </dev/null &",
        timeout=60)


def corners_in_crop(frame, baseline, crop):
    """
    Judge the corner pattern against panel_crop.

    A stale crop misses a corner; a layout that doesn't match the wiring puts
    the blocks elsewhere, or the origin's red block in another corner (mirrored
    or upside down). Reflections on the table are outside the crop.

    Returns:
        tuple: (True/False, or None while nothing is lit; str: what the camera saw)
    """
    w, h = SAMPLES
    red = redness(frame, baseline, crop, SAMPLES)
    lit = [(i % w / w, i // w / h, red[i]) for i, v in enumerate(lit_samples(frame, baseline, crop, SAMPLES).getdata()) if v]
    if len(lit) < MIN_LIT_SAMPLES:
        return None, f"panel dark inside the crop ({len(lit)} lit samples)"
    corners = [[[], []], [[], []]]   # [bottom][right]: the redness of each lit sample
    middle = 0
    for fx, fy, rv in lit:
        if MIDDLE_X[0] < fx < MIDDLE_X[1] or MIDDLE_Y[0] < fy < MIDDLE_Y[1]:
            middle += 1
        else:
            corners[fy >= 0.5][fx >= 0.5].append(rv)
    dark = [f"{('top', 'bottom')[r]}-{('left', 'right')[c]}"
            for r in (0, 1) for c in (0, 1) if len(corners[r][c]) < CORNER_MIN_SHARE * len(lit)]
    if dark:
        return False, f"no corner block in the crop's {', '.join(dark)}"
    if middle > MIDDLE_MAX_SHARE * len(lit):
        return False, f"{middle / len(lit):.0%} of the light between the corners"
    mean = [sum(c) / len(c) for row in corners for c in row]   # TL, TR, BL, BR
    if mean[0] < max(mean[1:]) + ORIGIN_MIN_REDNESS:
        return False, "the red origin block is not top left: the layout is mirrored or upside down"
    return True, "a block in each corner of the crop, the origin's top left"


def lit_blobs(on):
    """
    Groups of lit samples, joined across the gaps between one LED block's dots
    (a sample next to a lit one bridges them).

    Returns:
        list: each blob a list of (x, y) lit samples
    """
    from PIL import ImageFilter
    w, h = on.size
    near, on = on.filter(ImageFilter.MaxFilter(3)).load(), on.load()
    seen, blobs = set(), []
    for start in ((x, y) for y in range(h) for x in range(w)):
        if not near[start] or start in seen:
            continue
        blob, todo = [], [start]
        seen.add(start)
        while todo:
            cx, cy = todo.pop()
            if on[cx, cy]:
                blob.append((cx, cy))
            for n in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= n[0] < w and 0 <= n[1] < h and n not in seen and near[n]:
                    seen.add(n)
                    todo.append(n)
        if blob:
            blobs.append(blob)
    return blobs


def find_panel(frame, baseline):
    """
    The panel from the corner pattern, anywhere in the frame: the four
    brightest blobs, two level above two level. The camera may have moved
    since rig.json's panel_crop was set.

    Returns:
        list or None: a panel_crop [x1, y1, x2, y2], None if four corner
            blocks can't be told apart
    """
    from PIL import Image, ImageChops
    w, h = FIND_GRID
    # peak brightness per sample, at 3x3 finer steps: a lit LED saturates, a
    # reflection or a light change doesn't (an average favours their solid areas)
    r, g, b = crop_diff(frame, baseline, [0, 0, 1, 1], "RGB").resize((w * 3, h * 3), Image.BOX).split()
    fine = ImageChops.lighter(r, ImageChops.lighter(g, b)).load()   # brightest channel: the red block too
    peak = lambda b: max(fine[x * 3 + i, y * 3 + j] for x, y in b for i in range(3) for j in range(3))
    # brightest first; big changed areas are no LED block
    blobs = sorted((b for b in lit_blobs(lit_samples(frame, baseline, [0, 0, 1, 1], FIND_GRID))
                    if len(b) <= FIND_MAX_BLOB * w * h), key=peak, reverse=True)[:4]
    if len(blobs) < 4:
        return None
    centres = sorted((sum(c[0] for c in b) / len(b) / w, sum(c[1] for c in b) / len(b) / h) for b in blobs)
    left, right = sorted(centres[:2], key=lambda c: c[1]), sorted(centres[2:], key=lambda c: c[1])
    # a rectangle: left over left and right over right, top pair and bottom pair level
    if (abs(left[0][0] - left[1][0]) > FIND_LEVEL or abs(right[0][0] - right[1][0]) > FIND_LEVEL
            or abs(left[0][1] - right[0][1]) > FIND_LEVEL or abs(left[1][1] - right[1][1]) > FIND_LEVEL):
        return None
    cells = [c for b in blobs for c in b]
    ratio = ((max(c[0] for c in cells) - min(c[0] for c in cells) + 1) / w * FRAME_ASPECT
             / ((max(c[1] for c in cells) - min(c[1] for c in cells) + 1) / h))
    if not PANEL_ASPECT[0] <= ratio <= PANEL_ASPECT[1]:
        return None
    box = (min(c[0] for c in cells) / w - CROP_MARGIN, min(c[1] for c in cells) / h - CROP_MARGIN,
           (max(c[0] for c in cells) + 1) / w + CROP_MARGIN, (max(c[1] for c in cells) + 1) / h + CROP_MARGIN)
    return [round(min(1.0, max(0.0, v)), 3) for v in box]


def corner_pattern(pi, camera, baseline, crop, want, frame):
    """
    Light the corner pattern (led_fill.py --corners), find the panel in the
    camera frame and judge the pattern there.

    Returns:
        tuple: (match of led_fill's layout line or None, led_fill's log,
                the crop it was judged in, corners_in_crop's result)
    """
    expect = f"--expect {shlex.quote(want)} " if want else ""
    seen = (None, "no camera or panel_crop")
    try:
        launch_holder(pi, 60, f"--corners {expect}200 200 200")
        end = time.time() + 20
        while baseline and time.time() < end:
            camera.grab(frame)
            found = find_panel(frame, baseline)
            if found or crop:
                seen = corners_in_crop(frame, baseline, found or crop)
            # done once the panel was found and judged; rig.json's crop is the last resort
            if found:
                crop = found
                break
        # without the camera: wait until led_fill.py has reported the layout
        wait_for(pi["host"], f"grep -q '^led_fill: corners, ' {REMOTE_DIR}/led_fill.log", 20, interval=1)
    finally:
        stop_holder(pi)
    _, log = ssh(pi["host"], f"cat {REMOTE_DIR}/led_fill.log; {CLEAR_LEDS}", timeout=60)
    m = re.search(r"^led_fill: corners, layout (\S+?)(?:, matches \S+: (yes|no))?$", log, re.M)
    return m, log, crop, seen


def led_layout_setting(pi):
    """The Pi's LED_LAYOUT line as written (None: not set), to put back exactly."""
    rc, out = ssh(pi["host"], f"grep -m1 '^LED_LAYOUT=' {ENV_FILE}", timeout=60)
    return out.strip() if rc == 0 and out.strip() else None


def set_led_layout(pi, layout):
    """
    Set the Pi's LED_LAYOUT; layout None removes the line, a "LED_LAYOUT=..."
    line is put back as it was. LED_LAYOUT_VERIFIED stays: it drives the
    first-login check.
    """
    if layout is None:
        cmd = f"sudo sed -i '/^LED_LAYOUT=/d' {ENV_FILE}"
    elif layout.startswith("LED_LAYOUT="):
        cmd = (f"sudo sed -i '/^LED_LAYOUT=/d' {ENV_FILE} && "
               f"echo {shlex.quote(layout)} | sudo tee -a {ENV_FILE} >/dev/null")
    else:
        cmd = f"sudo bash -c '. /usr/bin/rq_common.sh && update_env_var LED_LAYOUT {shlex.quote(layout)}'"
    ssh(pi["host"], cmd, timeout=60, check=True)


def layout_row(m, log, want):
    """The report row for the layout led_fill.py resolved on the Pi."""
    if not m:
        return {"verdict": "FAIL", "name": "led-setup: layout",
                "detail": f"led_fill.py reported no layout: {log.strip()[-160:] or 'no output'}"}
    if not want:
        return {"verdict": "WARN", "name": "led-setup: layout",
                "detail": f"Pi has {m.group(1)}; put \"led_layout\" into rig.json to check it"}
    if m.group(2) == "yes":
        return {"verdict": "PASS", "name": "led-setup: layout",
                "detail": m.group(1) + ("" if m.group(1) == want else f" (maps like {want})")}
    return {"verdict": "FAIL", "name": "led-setup: layout", "detail": f"Pi has {m.group(1)}, rig.json expects {want}"}


def check_led_setup(pi, camera, outdir, all_pis):
    """
    Before a Pi's LED demos: does its LED layout map like rig.json's, and do
    the corner blocks sit in the panel's corners, the right way round? A wrong
    layout drew Lights Out's grid in one corner and still counted as lit.

    It repairs what it can, each repair a WARN row: the panel's crop is found
    in the frame every run (a moved camera; rig.json's panel_crop is the
    fallback), and a wrong layout is set to rig.json's, put back if the panel
    then looks no better.

    Returns:
        tuple: (report rows, True if this Pi's LED demos can be judged by the camera)
    """
    want, crop = pi.get("led_layout"), pi.get("panel_crop")
    frame = outdir / f"{pi['name']}-setup-corners.png"
    repairs = []
    with PANEL_LOCK:
        baseline, _ = (fresh_baseline(all_pis, camera, outdir / f"{pi['name']}-setup-baseline.png")
                       if camera else (None, None))
        m, log, found, seen = corner_pattern(pi, camera, baseline, crop, want, frame)
        # only with the camera: it shows whether rig.json's layout draws right
        if m and want and m.group(2) == "no" and baseline:
            before = led_layout_setting(pi)
            accepted = False
            try:
                set_led_layout(pi, want)
                baseline, _ = fresh_baseline(all_pis, camera, outdir / f"{pi['name']}-setup-baseline2.png")
                for _ in range(2):   # once more if the panel stayed dark (a Pi 4 write that didn't show)
                    m2, log2, found2, seen2 = corner_pattern(pi, camera, baseline, crop, want,
                                                             outdir / f"{pi['name']}-setup-corners2.png")
                    if seen2[0] is not None:
                        break
                # kept only if the panel now looks right
                accepted = bool(m2) and m2.group(2) == "yes" and seen2[0] is True
            finally:
                if not accepted:
                    set_led_layout(pi, before)
            if accepted:
                repairs.append({"verdict": "WARN", "name": "led-setup: layout repaired",
                                "detail": f"LED_LAYOUT was {m.group(1)}, set to {want} as rig.json says"})
                m, log, found, seen = m2, log2, found2, seen2
            else:
                repairs.append({"verdict": "WARN", "name": "led-setup: layout not repaired",
                                "detail": f"{want} didn't look right on the panel either: the Pi's setting put back"})
    if seen[0] and found != crop:
        # this run judges the Pi's LED demos in the crop found now; say so when it moved
        pi["panel_crop"] = found
    if seen[0] and crop and inside(found, crop) < MOVED_INSIDE:
        repairs.append({"verdict": "WARN", "name": "led-setup: camera moved",
                        "detail": f"panel found at {found}, rig.json has {crop}: used for this run"})
    rows = [layout_row(m, log, want), *repairs]
    if baseline:
        ok, what = seen
        detail = what if ok else f"{what} ({frame.name}): " + (
            "the LED output, or the panel is out of the camera's view" if ok is None
            else "check the camera and the Pi's LED wiring")
        rows.append({"verdict": "PASS" if ok else "FAIL", "name": "led-setup: corners in the panel", "detail": detail})
    # a dark panel is more likely the image's LED output than the rig: keep
    # judging, so the LED demos fail "panel dark" and point at it
    failed = [r for r in rows if r["verdict"] == "FAIL"]
    judged = not failed or (seen[0] is None and failed == rows[-1:] and baseline is not None)
    if not judged:
        rows.append({"verdict": "WARN", "name": "led-setup: camera judging",
                     "detail": "off for this Pi's LED demos (they would give wrong results)"})
    return rows, judged


def holder_alive(pi):
    """True while the led_fill.py holder still runs on the Pi."""
    return ssh(pi["host"], f"p=$(cat {HOLDER_PID} 2>/dev/null) && grep -qa led_fill /proc/$p/cmdline 2>/dev/null",
               timeout=30)[0] == 0


def stop_holder(pi):
    """Kill the led_fill.py holder (by its pid file; never by pattern)."""
    ssh(pi["host"], f"p=$(cat {HOLDER_PID} 2>/dev/null); [ -n \"$p\" ] && grep -qa led_fill /proc/$p/cmdline 2>/dev/null "
                    f"&& sudo kill -9 $p; sudo rm -f {HOLDER_PID}; true", timeout=30)


def _run_and_judge(pi, demo, hint, seconds, camera, outdir, env, baseline, before, notes):
    """Run the demo (demo_smoke.sh), sample the camera, and judge."""
    host = pi["host"]
    result = {}
    tag = demo_tag(demo)
    crop = pi.get("panel_crop")
    threshold = pi.get("lit_threshold", 0.006)

    def worker():
        name = f"icon:{demo['icon']}" if demo.get("icon") else f"demo:{demo['id']}"
        try:
            _, out = ssh(host, f"{env}bash {REMOTE_DIR}/demo_smoke.sh {shlex.quote(demo['id'])} {seconds} {REMOTE_DIR}",
                         timeout=seconds + INSTALL_ALLOWANCE + 180)
        except Exception as exc:  # noqa: BLE001 - one demo must not lose the whole report
            result.update({"verdict": "FAIL", "name": name, "detail": f"harness: {type(exc).__name__}: {exc}"[:200]})
            return
        parsed = parse_lines(out)
        result.update(parsed[0] if parsed else {"verdict": "FAIL", "name": name, "detail": out.strip()[:200]})

    t = threading.Thread(target=worker)
    t.start()
    led = None
    service_state = None
    if hint.get("service"):
        end = time.time() + seconds - 5
        while time.time() < end and t.is_alive():
            _, service_state = ssh(host, f"systemctl is-active {hint['service']}")
            service_state = service_state.strip() or "unknown"
            if service_state == "active":
                break
            time.sleep(3)
        service_state = service_state or "not checked"
    elif baseline:
        # LED demos blink, animate and (on a Pi 4) take a while to import
        # Qiskit: sample every couple of seconds for the whole run, keep the best
        best, kept, last = -1.0, None, -1.0
        end = time.time() + seconds - 2 + (0 if hint.get("dark") else INSTALL_ALLOWANCE)
        time.sleep(4)
        i = 0
        while time.time() < end and t.is_alive():
            frame = camera.grab(outdir / f"{pi['name']}-{tag}-camera{i}.png")
            score = lit_score(frame, baseline, crop)
            last = score
            if score > best:
                if kept:
                    kept.unlink()
                best, kept = score, frame
            elif hint.get("dark"):   # keep the last frame: it is the one judged
                if kept:
                    kept.unlink()
                kept = frame
            else:
                frame.unlink()
            i += 1
        if kept:
            kept.rename(outdir / f"{pi['name']}-{tag}-camera.png")
        # a demo that switches the panel off is judged by where it ends up
        led = (last if hint.get("dark") else best) if best >= 0 else None
    t.join()
    holder = None
    if before is not None:
        holder = "still running" if holder_alive(pi) else "stopped"
    fetch(host, f"{REMOTE_DIR}/{tag}.png", outdir / f"{pi['name']}-{tag}-screen.png")
    if service_state is not None:
        result["detail"] = result.get("detail", "") + f" {hint['service']}={service_state}"
        if service_state != "active" and result.get("verdict") == "PASS":
            result["verdict"] = "FAIL"
    if led is not None:
        lit = led >= threshold
        detail = result.get("detail", "")
        if hint.get("dark"):
            result["detail"] = (detail + f" before={before:.3f} led={led:.3f}"
                                + (" (panel still lit)" if lit else " (panel off)")
                                + f" holder={holder}" + notes)
            if (lit or holder != "stopped") and result.get("verdict") == "PASS":
                result["verdict"] = "FAIL"
            elif before < threshold and result.get("verdict") == "PASS":
                # the panel never lit: nothing was shown to be switched off
                result["detail"] += " (could not light the panel first: check panel_crop)"
                result["verdict"] = "WARN"
            return result
        waits = "dialog=yes" in detail            # waiting for input: nothing to show
        ended = "alive=no" in detail and "exit=0" in detail   # finished by itself
        result["detail"] = detail + f" led={led:.3f}" + ("" if lit else " (panel dark)") + notes
        if not lit and hint.get("led_optional"):
            result["detail"] += " (expected without an IBM account)"
        elif not lit and result.get("verdict") == "PASS":
            result["verdict"] = "WARN" if (waits or ended) else "FAIL"
    return result


def run_demos(pi, demos, section, args, camera, outdir, cfg):
    """Smoke-test each demo (menu demos and icons) and add its report row."""
    for d in demos:
        label = f"icon:{d['icon']}" if d.get("icon") else f"demo:{d['id']}"
        print(f"   {label} ...", flush=True)
        if d["id"] == "?":
            section["rows"].append({"verdict": "FAIL", "name": label, "detail": "no demo found for this icon"})
            continue
        try:
            section["rows"].append(smoke_demo(pi, d, args.seconds, camera, outdir, cfg["pis"], args.docker))
        except Exception as exc:  # one broken demo must not end the run
            section["rows"].append({"verdict": "FAIL", "name": label, "detail": f"harness: {exc}"})


# ----------------------------------------------------------------------------
def main():
    # SIGTERM/SIGHUP (a killed or closed run) end through sys.exit, so the
    # atexit handlers run and the camera stream stops
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(1))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(HERE / "rig.json"))
    ap.add_argument("--pi", help="comma-separated Pi names from rig.json (default: all)")
    ap.add_argument("--demos", default="all", help="comma-separated demo ids, 'all' or 'none'")
    ap.add_argument("--seconds", type=int, default=30, help="how long each demo runs")
    ap.add_argument("--docker", action="store_true", help="also run docker demos")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--checks-only", action="store_true")
    ap.add_argument("--update", metavar="TAG", help="first install this release into the other slot (A/B images); "
                                                 "'latest': what the Pi itself offers. The first update to a new "
                                                 "release goes the real user's way, later ones use the image cache")
    ap.add_argument("--no-web-check", action="store_true",
                    help="don't check web/Jupyter pages in the desktop Chromium (and don't restart it)")
    ap.add_argument("--icons", nargs="?", const=DEFAULT_ICONS, metavar="FILES",
                    help="also start demos by double-clicking their desktop icons with a real (uinput) "
                         f"mouse; comma-separated .desktop names (default: {DEFAULT_ICONS})")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    pis = cfg["pis"] = [rig_pi(p) for p in cfg["pis"]]
    if args.pi:
        wanted = args.pi.split(",")
        pis = [p for p in pis if p["name"] in wanted]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = HERE / "results" / stamp
    outdir.mkdir(parents=True)

    camera = None
    if not args.no_camera and cfg.get("camera_url") and not args.checks_only:
        camera = Camera(cfg["camera_url"], outdir)
        if not camera.start():
            print("camera: no frame - LED checks skipped")
            camera = None

    report, failed = [], False
    try:
        for pi in pis:
            print(f"== {pi['name']} ({pi['host']})")
            section = {"pi": pi["name"], "rows": []}
            report.append(section)
            try:
                no_usage_counts(pi)
                if args.update:
                    tag = args.update
                    if tag == "latest":   # what this Pi's own lookup offers, as a user's would
                        tag = latest_on_pi(pi).get("tag") or "?"
                    section["rows"] += update_slot(pi, tag)
                    no_usage_counts(pi)     # the new slot (carried over since this release)
                section["rows"] += run_checks(pi)
                if not args.checks_only:
                    every = list_demos(pi)
                    demos = [] if args.demos == "none" else every
                    if args.demos not in ("all", "none"):
                        wanted = args.demos.split(",")
                        # a base id selects all its variants (id:variant)
                        demos = [d for d in demos if d["id"] in wanted or d["id"].split(":")[0] in wanted]
                    if args.icons:
                        demos += icon_demos(pi, args.icons.split(","), every)
                    # web checks: the desktop Chromium with remote debugging,
                    # restored when this Pi is done
                    pi["web_check"] = (not args.no_web_check and any(
                        d["type"] in ("jupyter", "browser", "web-static", "docker")
                        or DEMO_HINTS.get(d["id"], {}).get("web") for d in demos)
                        and browser_debug(pi, True))
                    try:
                        if any(d["leds"] for d in demos):
                            try:
                                rows, pi["led_setup_ok"] = check_led_setup(pi, camera, outdir, cfg["pis"])
                            except Exception as exc:   # the demos still run, unjudged
                                rows, pi["led_setup_ok"] = [{"verdict": "FAIL", "name": "led-setup",
                                                             "detail": f"harness: {exc}"}], False
                            section["rows"] += rows
                        run_demos(pi, demos, section, args, camera, outdir, cfg)
                    finally:
                        if pi["web_check"]:
                            browser_debug(pi, False)
            except Exception as exc:  # keep going with the next Pi
                section["rows"].append({"verdict": "FAIL", "name": "run", "detail": str(exc)})
            for r in section["rows"]:
                print(f"   {r['verdict']:<4} {r['name']:<34} {r['detail']}")
                failed |= r["verdict"] == "FAIL"
    finally:
        if camera:
            camera.stop()

    lines = [f"# RasQberry rig test {stamp}", ""]
    for s in report:
        n = {v: sum(r["verdict"] == v for r in s["rows"]) for v in ("PASS", "FAIL", "WARN", "SKIP")}
        lines += [f"## {s['pi']}: {n['PASS']} pass, {n['FAIL']} fail, {n['WARN']} warn, {n['SKIP']} skipped", "",
                  "| | Check | Detail |", "|---|---|---|"]
        lines += [f"| {r['verdict']} | {r['name']} | {r['detail'].replace('|', '/')} |" for r in s["rows"]]
        lines.append("")
    (outdir / "report.md").write_text("\n".join(lines))
    print(f"\nReport: {outdir / 'report.md'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
