#!/usr/bin/env python3
"""
RasQberry rig test (issue #234): test a real image on the test Pis.

Runs from a machine on the rig's network (not in CI: the Pis and the camera
are on a local LAN). For every Pi in rig.json it

  1. optionally installs a release into the other A/B slot and boots it
     (--update TAG: switch to Slot A, OTA the release into Slot B),
  2. runs the system checks (tests/rig/pi/checks.sh),
  3. smoke-tests each demo the way a person does - desktop terminal, runs,
     Ctrl+C, nothing left behind (tests/rig/pi/demo_smoke.sh),
  4. for LED demos, checks with the camera that the Pi's panel actually lights,

and writes results/<timestamp>/report.md with screenshots and camera frames.
Exit status 1 if anything failed.

Usage:
    python3 tests/rig/rig_test.py                       # all Pis, all demos
    python3 tests/rig/rig_test.py --pi pi5 --demos quantum-lights-out,rasq-led
    python3 tests/rig/rig_test.py --update beta-2026-09-30-142314
    python3 tests/rig/rig_test.py --checks-only

Needs on this machine: ssh (key login to the Pis), ffmpeg, Python 3 + Pillow.
Needs on the Pis: nothing beyond the image (key login for the rig user).
"""

import argparse
import datetime
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
REMOTE_DIR = "/tmp/rigtest"


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def ssh(host, command, timeout=600, check=False):
    """Run a command on a Pi; returns (rc, stdout)."""
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, command],
        capture_output=True, text=True, timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"{host}: {command!r} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout


def scp(host, sources, dest):
    """Copy local files to the Pi."""
    subprocess.run(["scp", "-q", *map(str, sources), f"{host}:{dest}"], check=True, timeout=120)


def fetch(host, remote, local):
    """Copy a file from the Pi; ignore missing files."""
    subprocess.run(["scp", "-q", f"{host}:{remote}", str(local)], timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def parse_lines(text):
    """Parse 'VERDICT name | detail' lines into dicts."""
    out = []
    for line in text.splitlines():
        head, _, detail = line.partition(" | ")
        parts = head.split(None, 1)
        if len(parts) == 2 and parts[0] in ("PASS", "FAIL", "WARN", "INFO", "SKIP"):
            out.append({"verdict": parts[0], "name": parts[1], "detail": detail.strip()})
    return out


def wait_for(host, predicate_cmd, timeout, interval=10):
    """Poll until the command succeeds on the Pi (e.g. after a reboot)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            if ssh(host, predicate_cmd, timeout=30)[0] == 0:
                return True
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
        """Stop ffmpeg."""
        if self.proc:
            self.proc.terminate()


def lit_score(frame, baseline, crop):
    """
    How much brighter the panel region is than with the LEDs off.

    Args:
        frame, baseline (Path): camera frames with the demo running / LEDs off.
        crop (list): [x1, y1, x2, y2] as fractions of the frame size.

    Returns:
        float: share of pixels in the crop that got clearly brighter (0..1).
    """
    from PIL import Image, ImageChops
    a, b = Image.open(frame).convert("L"), Image.open(baseline).convert("L")
    w, h = a.size
    box = tuple(int(v * (w if i % 2 == 0 else h)) for i, v in enumerate(crop))
    diff = ImageChops.subtract(a.crop(box), b.crop(box))
    hist = diff.histogram()
    bright = sum(hist[40:])
    return bright / max(1, sum(hist))


# ----------------------------------------------------------------------------
# steps
# ----------------------------------------------------------------------------
def update_slot(pi, tag):
    """Switch to Slot A and OTA `tag` into Slot B with this repo's updater."""
    host = pi["host"]
    rel = subprocess.run(["gh", "api", f"repos/JanLahmann/RasQberry-Two/releases/tags/{tag}",
                          "--jq", '.assets[]|select(.name|endswith("-ab.img.xz"))|.browser_download_url+" "+.digest'],
                         capture_output=True, text=True, check=True).stdout.split()
    url, digest = rel[0], rel[1].split(":", 1)[1]
    print(f"  {pi['name']}: switching to Slot A")
    ssh(host, "sudo rq_slot_manager.sh switch-to A --reboot >/dev/null 2>&1 || true", timeout=60)
    time.sleep(30)
    if not wait_for(host, "findmnt -no SOURCE / | grep -q p5", 600):
        raise RuntimeError("Slot A did not come up")
    ssh(host, f"mkdir -p {REMOTE_DIR}/ota", check=True)
    scp(host, [REPO / "RQB2-bin" / f for f in ("rq_update_slot.sh", "rq_carry_ssh_identity.sh", "rq_common.sh")],
        f"{REMOTE_DIR}/ota/")
    print(f"  {pi['name']}: installing {tag} into Slot B (15-25 min)")
    ssh(host, f"chmod +x {REMOTE_DIR}/ota/*.sh; sudo setsid nohup {REMOTE_DIR}/ota/rq_update_slot.sh "
              f"{shlex.quote(url)} {shlex.quote(tag)} --slot B --sha256 {digest} "
              f"</dev/null >{REMOTE_DIR}/ota.log 2>&1 &", timeout=60)
    time.sleep(120)
    if not wait_for(host, f"grep -qx {shlex.quote(tag)} /etc/rasqberry-version", 3600, interval=30):
        raise RuntimeError("new slot did not come up with the release")
    wait_for(host, "! systemctl is-active -q rasqberry-health-check.service", 600)


def run_checks(pi):
    """Copy the Pi-side scripts and run the system checks."""
    host = pi["host"]
    ssh(host, f"mkdir -p {REMOTE_DIR}", check=True)
    scp(host, [HERE / "pi" / "checks.sh", HERE / "pi" / "demo_smoke.sh"], f"{REMOTE_DIR}/")
    _, out = ssh(host, f"bash {REMOTE_DIR}/checks.sh", timeout=300)
    return parse_lines(out)


def list_demos(pi):
    """Demo ids with their type and LED need, from the Pi's manifests."""
    _, out = ssh(pi["host"], "for f in /usr/config/demo-manifests/rq_demo_*.json; do "
                             "jq -r 'select(.id) | [.id, .entrypoint.type, (.needs_hw.leds // false|tostring), "
                             "([.variants[]?.id] | join(\",\"))] | @tsv' \"$f\"; done")
    demos = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        base = {"type": parts[1], "leds": parts[2] == "true"}
        variants = [v for v in parts[3].split(",") if v]
        # a manifest with variants is a menu; each variant is its own demo
        for spec in ([f"{parts[0]}:{v}" for v in variants] or [parts[0]]):
            demos.append(dict(base, id=spec))
    return demos


def smoke_demo(pi, demo, seconds, camera, outdir, baseline, docker):
    """Run one demo smoke test; for LED demos grab a camera frame mid-run."""
    host = pi["host"]
    env = "RIG_ALLOW_DOCKER=1 " if docker else ""
    result = {}

    def worker():
        _, out = ssh(host, f"{env}bash {REMOTE_DIR}/demo_smoke.sh {shlex.quote(demo['id'])} {seconds} {REMOTE_DIR}",
                     timeout=seconds + 180)
        parsed = parse_lines(out)
        result.update(parsed[0] if parsed else {"verdict": "FAIL", "name": f"demo:{demo['id']}", "detail": out.strip()[:200]})

    t = threading.Thread(target=worker)
    t.start()
    led = None
    if camera and demo["leds"] and pi.get("panel_crop"):
        # LED demos blink, animate and (on a Pi 4) take a while to import
        # Qiskit: sample every couple of seconds for the whole run, keep the best
        tag = demo["id"].replace(":", "-")
        best, kept = -1.0, None
        end = time.time() + seconds - 2
        time.sleep(4)
        i = 0
        while time.time() < end and t.is_alive():
            frame = camera.grab(outdir / f"{pi['name']}-{tag}-camera{i}.png")
            score = lit_score(frame, baseline, pi["panel_crop"])
            if score > best:
                if kept:
                    kept.unlink()
                best, kept = score, frame
            else:
                frame.unlink()
            i += 1
        if kept:
            kept.rename(outdir / f"{pi['name']}-{tag}-camera.png")
        led = best if best >= 0 else None
    t.join()
    name = demo["id"].replace(":", "-")
    fetch(host, f"{REMOTE_DIR}/{name}.png", outdir / f"{pi['name']}-{name}-screen.png")
    if led is not None:
        lit = led >= pi.get("lit_threshold", 0.006)
        detail = result.get("detail", "")
        waits = "dialog=yes" in detail            # waiting for input: nothing to show
        ended = "alive=no" in detail and "exit=0" in detail   # finished by itself
        result["detail"] = detail + f" led={led:.3f}" + ("" if lit else " (panel dark)")
        if not lit and result.get("verdict") == "PASS":
            result["verdict"] = "WARN" if (waits or ended) else "FAIL"
    return result


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(HERE / "rig.json"))
    ap.add_argument("--pi", help="comma-separated Pi names from rig.json (default: all)")
    ap.add_argument("--demos", default="all", help="comma-separated demo ids, 'all' or 'none'")
    ap.add_argument("--seconds", type=int, default=30, help="how long each demo runs")
    ap.add_argument("--docker", action="store_true", help="also run docker demos")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--checks-only", action="store_true")
    ap.add_argument("--update", metavar="TAG", help="first install this release into Slot B (A/B images)")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    pis = cfg["pis"]
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
                if args.update:
                    update_slot(pi, args.update)
                section["rows"] += run_checks(pi)
                if not args.checks_only and args.demos != "none":
                    demos = list_demos(pi)
                    if args.demos != "all":
                        wanted = args.demos.split(",")
                        # a base id selects all its variants (id:variant)
                        demos = [d for d in demos if d["id"] in wanted or d["id"].split(":")[0] in wanted]
                    baseline = None
                    if camera:
                        # every panel off (another Pi's lit panel or a demo's
                        # last frame would pollute the baseline)
                        for other in cfg["pis"]:
                            ssh(other["host"], "sudo /home/*/RasQberry-Two/venv/RQB2/bin/python3 /usr/bin/turn_off_LEDs.py >/dev/null 2>&1; true", timeout=60)
                        time.sleep(2)
                        baseline = camera.grab(outdir / f"{pi['name']}-baseline.png")
                    for d in demos:
                        print(f"   demo {d['id']} ...", flush=True)
                        try:
                            section["rows"].append(smoke_demo(pi, d, args.seconds, camera, outdir, baseline, args.docker))
                        except Exception as exc:  # one broken demo must not end the run
                            section["rows"].append({"verdict": "FAIL", "name": f"demo:{d['id']}", "detail": f"harness: {exc}"})
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
