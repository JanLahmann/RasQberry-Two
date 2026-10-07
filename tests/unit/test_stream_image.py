"""
Tests for RQB2-bin/rq_stream_image.py and how rq_update_slot.sh uses it
(R-052: an A/B update unpacks the image straight into the other slot instead
of into /var/tmp, so it needs the download plus 0.5 GB free, not 15 GB).

A small fake image stands in for the real one: an MBR with the -ab image's
partition order (p1 CONFIG, p2 BOOT-A, p3 BOOT-B, p4 extended with p5
SYSTEM-A, p6 SYSTEM-B, p7 DATA, each logical partition behind its own EBR),
FAT boot sectors with the real labels, an ext4 superblock magic, random
content - and regular files of the partitions' sizes stand in for the slot's
block devices.
"""

import hashlib
import os
import pty
import select
import shutil
import struct
import subprocess
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_BIN = os.path.join(_HERE, "..", "..", "RQB2-bin")
_HELPER = os.path.join(_BIN, "rq_stream_image.py")
_SCRIPT = os.path.join(_BIN, "rq_update_slot.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("xz") is None,
    reason="bash and xz are required",
)

SECTOR = 512
U = 64                      # one "MiB" of the fake image, in sectors (32 KiB)


def _rand(n, seed):
    """Deterministic pseudo-random bytes (a different stream per seed)."""
    out, block = bytearray(), 0
    while len(out) < n:
        out += hashlib.sha256(f"{seed}:{block}".encode()).digest()
        block += 1
    return bytes(out[:n])


def _fat(label, size, seed, fat32=True):
    data = bytearray(_rand(size, seed))
    data[0:3] = b"\xeb\x58\x90"
    data[3:11] = b"mkfs.fat"
    struct.pack_into("<HBHB", data, 11, 512, 4, 32, 2)
    if fat32:
        struct.pack_into("<H", data, 22, 0)
        data[66] = 0x29
        data[71:82] = label.ljust(11).encode()
        data[82:90] = b"FAT32   "
    else:
        struct.pack_into("<H", data, 22, 8)
        data[38] = 0x29
        data[43:54] = label.ljust(11).encode()
        data[54:62] = b"FAT16   "
    data[510:512] = b"\x55\xaa"
    return bytes(data)


def _ext4(size, seed):
    data = bytearray(_rand(size, seed))
    data[1080:1082] = b"\x53\xef"
    return bytes(data)


def _table(entries, seed):
    sector = bytearray(_rand(SECTOR, seed))           # boot code: noise
    sector[446:510] = bytes(64)
    for i, (ptype, lba, count) in enumerate(entries):
        struct.pack_into("<B3sB3sII", sector, 446 + 16 * i, 0, b"\0\0\0", ptype, b"\0\0\0", lba, count)
    sector[510:512] = b"\x55\xaa"
    return bytes(sector)


class Img:
    """A fake image: its bytes and where each partition lies (bytes)."""

    def __init__(self, data, parts):
        self.data, self.parts = data, parts

    def part(self, name):
        start, size = self.parts[name]
        return self.data[start:start + size]


def ab_image(root_units=20, p1_label="CONFIG", gap_fill=None):
    """The -ab layout (convert-to-ab-boot-v3.sh), scaled down: 4U CONFIG,
    BOOT-A, BOOT-B; extended from 13U; SYSTEM-A 20U, SYSTEM-B 2U, DATA 2U."""
    total = (13 + 1 + root_units + 1 + 1 + 2 + 1 + 1 + 2 + 1) * U
    img = bytearray(_rand(total * SECTOR, "gaps")) if gap_fill is None else bytearray(gap_fill * (total * SECTOR))
    parts = {}

    def put(name, lba, blob):
        img[lba * SECTOR:lba * SECTOR + len(blob)] = blob
        parts[name] = (lba * SECTOR, len(blob))

    ext = 13 * U
    p5 = ext + U
    ebr2 = p5 + root_units * U + U // 2
    p6 = ebr2 + U
    ebr3 = p6 + 2 * U + U // 2
    p7 = ebr3 + U
    put("mbr", 0, _table([(0x0C, U, 4 * U), (0x0C, 5 * U, 4 * U), (0x0C, 9 * U, 4 * U),
                          (0x0F, ext, total - ext)], "mbr"))
    put("p1", U, _fat(p1_label, 4 * U * SECTOR, "p1"))
    put("p2", 5 * U, _fat("BOOT-A", 4 * U * SECTOR, "p2"))
    put("p3", 9 * U, _fat("BOOT-B", 4 * U * SECTOR, "p3"))
    # EBR: entry 0 relative to the EBR itself, entry 1 (next EBR) to the
    # start of the extended partition
    put("ebr1", ext, _table([(0x83, p5 - ext, root_units * U), (0x05, ebr2 - ext, 3 * U)], "ebr1"))
    put("p5", p5, _ext4(root_units * U * SECTOR, "p5"))
    put("ebr2", ebr2, _table([(0x83, p6 - ebr2, 2 * U), (0x05, ebr3 - ext, 3 * U)], "ebr2"))
    put("p6", p6, _ext4(2 * U * SECTOR, "p6"))
    put("ebr3", ebr3, _table([(0x83, p7 - ebr3, 2 * U)], "ebr3"))
    put("p7", p7, _ext4(2 * U * SECTOR, "p7"))
    return Img(bytes(img), parts)


def standard_image():
    """The standard image: p1 bootfs (FAT32), p2 rootfs (ext4)."""
    total = 27 * U
    img = bytearray(_rand(total * SECTOR, "std-gaps"))
    parts = {}
    for name, lba, blob in (("mbr", 0, _table([(0x0C, U, 4 * U), (0x83, 5 * U, 20 * U)], "std-mbr")),
                            ("p1", U, _fat("bootfs", 4 * U * SECTOR, "std-p1")),
                            ("p2", 5 * U, _ext4(20 * U * SECTOR, "std-p2"))):
        img[lba * SECTOR:lba * SECTOR + len(blob)] = blob
        parts[name] = (lba * SECTOR, len(blob))
    return Img(bytes(img), parts)


def _xz(tmp_path, data, name="image.img"):
    raw = tmp_path / name
    raw.write_bytes(data)
    subprocess.run(["xz", "-f", "-T0", str(raw)], check=True)
    return tmp_path / (name + ".xz")


FILL = b"\xaa"


def _targets(tmp_path, boot_size=4 * U * SECTOR, root_size=40 * U * SECTOR):
    """Regular files standing in for BOOT-B and SYSTEM-B (old content: 0xAA)."""
    boot, root = tmp_path / "boot-b", tmp_path / "system-b"
    boot.write_bytes(FILL * boot_size)
    root.write_bytes(FILL * root_size)
    return boot, root


def _helper(*args, env=None, chunk="4096"):
    env = dict(env or os.environ, RQ_STREAM_CHUNK=chunk)
    return subprocess.run(["python3", _HELPER, *map(str, args)], capture_output=True, text=True, env=env)


def _values(stdout):
    return dict(line.split("=", 1) for line in stdout.splitlines() if "=" in line)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


# --- the streaming writer ------------------------------------------------------

def test_ab_image_lands_byte_exact_in_the_slot(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", _sha(img.data))
    assert proc.returncode == 0, proc.stderr
    values = _values(proc.stdout)
    assert values["layout"] == "ab"
    assert values["root"].startswith("p5 ")
    assert values["extract_sha256"] == _sha(img.data)
    assert int(values["image_bytes"]) == len(img.data)
    # BOOT-A (p2) -> boot target, SYSTEM-A (p5) -> system target, byte-exact;
    # what lies behind them in the targets is left alone
    p2, p5 = img.part("p2"), img.part("p5")
    assert boot.read_bytes() == p2
    written = root.read_bytes()
    assert written[:len(p5)] == p5
    assert written[len(p5):] == FILL * (len(written) - len(p5))
    # not CONFIG, BOOT-B, SYSTEM-B or DATA
    for other in ("p1", "p3", "p6", "p7"):
        assert img.part(other)[:4096] not in written


def test_large_chunks_give_the_same_result(tmp_path):
    # the real chunk size (4 MiB) is bigger than the whole fake image
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, chunk="")
    assert proc.returncode == 0, proc.stderr
    assert boot.read_bytes() == img.part("p2")
    assert root.read_bytes()[:len(img.part("p5"))] == img.part("p5")


def test_standard_image_maps_p1_and_p2(tmp_path):
    img = standard_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", _sha(img.data))
    assert proc.returncode == 0, proc.stderr
    assert _values(proc.stdout)["layout"] == "standard"
    assert boot.read_bytes() == img.part("p1")
    assert root.read_bytes()[:len(img.part("p2"))] == img.part("p2")


def test_wrong_extract_sha256_exits_5_after_writing(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", "0" * 64)
    assert proc.returncode == 5
    assert "does not match the published one" in proc.stderr
    assert _sha(img.data) in proc.stderr


def test_extract_sha256_is_compared_case_insensitively(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", _sha(img.data).upper())
    assert proc.returncode == 0, proc.stderr


def test_a_truncated_image_stops_after_writing_began(tmp_path):
    img = ab_image()
    cut = img.parts["p5"][0] + img.parts["p5"][1] // 2       # in the middle of SYSTEM-A
    xz = _xz(tmp_path, img.data[:cut])
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", _sha(img.data))
    assert proc.returncode == 4
    assert "ended early" in proc.stderr and "the system partition" in proc.stderr


def test_a_cut_off_download_says_xz_could_not_unpack_it(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    data = xz.read_bytes()
    xz.write_bytes(data[:int(len(data) * 0.8)])               # the .xz itself cut off
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root)
    assert proc.returncode == 4
    assert "ERROR:" in proc.stderr and "xz:" in proc.stderr


def test_a_corrupt_download_never_passes(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    data = bytearray(xz.read_bytes())
    data[int(len(data) * 0.9)] ^= 0xFF                        # late: after the boot partition
    xz.write_bytes(bytes(data))
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", _sha(img.data))
    assert proc.returncode in (4, 5), proc.stderr
    assert "ERROR:" in proc.stderr


def test_an_unknown_image_is_refused_before_anything_is_written(tmp_path):
    img = ab_image(p1_label="SOMETHING")
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root)
    assert proc.returncode == 3
    assert "Unknown image type: p1 label 'SOMETHING'" in proc.stderr
    assert boot.read_bytes() == FILL * (4 * U * SECTOR)
    assert set(root.read_bytes()) == set(FILL)


def test_a_boot_partition_too_big_for_the_target_is_refused_untouched(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path, boot_size=2 * U * SECTOR)
    proc = _helper(xz, "--boot", boot, "--root", root)
    assert proc.returncode == 3
    assert "boot partition" in proc.stderr and "does not fit" in proc.stderr
    assert boot.read_bytes() == FILL * (2 * U * SECTOR)


def test_probe_checks_the_whole_layout_and_writes_nothing(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--probe")
    assert proc.returncode == 0, proc.stderr
    values = _values(proc.stdout)
    assert values["layout"] == "ab"
    assert values["root"] == f"p5 start={img.parts['p5'][0]} size={img.parts['p5'][1]}"
    assert "extract_sha256" not in values
    assert boot.read_bytes() == FILL * (4 * U * SECTOR)
    assert set(root.read_bytes()) == set(FILL)


def test_probe_refuses_a_system_partition_too_big_for_the_target(tmp_path):
    # the root's size is in the EBR, behind the boot partition: only the
    # probe can check it before the slot is touched
    img = ab_image(root_units=50)
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path, root_size=40 * U * SECTOR)
    proc = _helper(xz, "--boot", boot, "--root", root, "--probe")
    assert proc.returncode == 3
    assert "system partition" in proc.stderr and "does not fit" in proc.stderr
    assert boot.read_bytes() == FILL * (4 * U * SECTOR)


def test_write_without_probe_stops_with_4_when_the_root_does_not_fit(tmp_path):
    img = ab_image(root_units=50)
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path, root_size=40 * U * SECTOR)
    proc = _helper(xz, "--boot", boot, "--root", root)
    assert proc.returncode == 4
    assert set(root.read_bytes()) == set(FILL)           # the root was not started


def test_probe_needs_an_ext4_system_partition(tmp_path):
    img = ab_image()
    data = bytearray(img.data)
    start = img.parts["p5"][0]
    data[start + 1080:start + 1082] = b"\0\0"
    xz = _xz(tmp_path, bytes(data))
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--probe")
    assert proc.returncode == 3
    assert "no ext4 file system" in proc.stderr


def test_probe_reads_no_further_than_the_system_partition(tmp_path):
    # the image is cut off right after the start of SYSTEM-A: enough for the probe
    img = ab_image()
    cut = img.parts["p5"][0] + 4096
    xz = _xz(tmp_path, img.data[:cut])
    boot, root = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", root, "--probe")
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("which", ["boot", "root"])
def test_a_target_of_the_running_system_is_never_written(tmp_path, which):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    running = boot if which == "boot" else root
    proc = _helper(xz, "--boot", boot, "--root", root, "--forbid", running)
    assert proc.returncode == 3
    assert "belongs to the system that is running now" in proc.stderr
    assert boot.read_bytes() == FILL * (4 * U * SECTOR)
    assert set(root.read_bytes()) == set(FILL)


def test_boot_and_root_must_differ(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, _ = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", boot)
    assert proc.returncode == 3


def test_a_missing_target_is_refused(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, _ = _targets(tmp_path)
    proc = _helper(xz, "--boot", boot, "--root", tmp_path / "nope")
    assert proc.returncode == 3 and "cannot be opened" in proc.stderr


def test_progress_on_a_terminal_and_byte_exact_targets(tmp_path):
    """R-002's lesson: on a terminal (as in the menu) the progress goes to the
    screen, never into the slot."""
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    master, slave = pty.openpty()
    env = dict(os.environ, RQ_STREAM_CHUNK="4096")
    proc = subprocess.Popen(["python3", _HELPER, str(xz), "--boot", str(boot), "--root", str(root),
                             "--extract-sha256", _sha(img.data)],
                            stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    shown = b""
    while True:
        ready, _, _ = select.select([master], [], [], 60)
        if not ready:
            proc.kill()
            raise AssertionError(f"timed out: {shown!r}")
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        shown += chunk
    os.close(master)
    assert proc.wait(timeout=30) == 0, shown
    assert b"(100%)" in shown and b" of " in shown
    assert boot.read_bytes() == img.part("p2")
    assert root.read_bytes()[:len(img.part("p5"))] == img.part("p5")


def test_the_log_gets_the_layout_and_the_result(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    log = tmp_path / "update.log"
    proc = _helper(xz, "--boot", boot, "--root", root, "--extract-sha256", _sha(img.data), "--log", log)
    assert proc.returncode == 0, proc.stderr
    text = log.read_text()
    assert "layout=ab" in text and "unpacked image checksum OK" in text


# --- rq_update_slot.sh around it -------------------------------------------------

def _bash_env(tmp_path, root_src="/dev/mmcblk0p5", boot_src="/dev/mmcblk0p2", **extra):
    """findmnt says what the running system is; sync does nothing (the real one
    flushes the whole machine)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "findmnt").write_text(textwrap.dedent(f"""\
        #!/bin/bash
        case "$1" in
            /) echo "{root_src}" ;;
            /boot/firmware) echo "{boot_src}" ;;
            *) exit 1 ;;
        esac
        """))
    (bindir / "sync").write_text("#!/bin/sh\nexit 0\n")
    for name in ("findmnt", "sync"):
        (bindir / name).chmod(0o755)
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", RQ_BOOT_COMMON_DIR=str(config),
               RQ_UPDATE_LOG=str(tmp_path / "update.log"), RQ_STREAM_CHUNK="4096", **extra)
    return env, config


def _stream_into_slot(tmp_path, xz, boot, root, expected="", **env_extra):
    env, config = _bash_env(tmp_path, **env_extra)
    proc = subprocess.run(
        ["bash", "-c", f'. "{_SCRIPT}"\nstream_into_slot "{xz}" "{root}" "{boot}" B "{expected}" beta-2026-10-15-101010\n'
                       'echo STREAMED'],
        capture_output=True, text=True, env=env, timeout=120)
    return proc, config


def test_stream_into_slot_writes_and_keeps_the_slot_marked_until_it_is_finished(tmp_path):
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc, config = _stream_into_slot(tmp_path, xz, boot, root, _sha(img.data))
    assert proc.returncode == 0, proc.stderr
    assert "STREAMED" in proc.stdout and "Unpacked image checked: OK" in proc.stdout
    assert boot.read_bytes() == img.part("p2")
    # cleared only after the new system is set up (write_image_to_slot)
    assert (config / "slot-B-incomplete").exists()


@pytest.mark.parametrize("damage", ["truncated", "checksum"])
def test_a_failed_write_leaves_the_slot_marked_incomplete(tmp_path, damage):
    img = ab_image()
    if damage == "truncated":
        xz = _xz(tmp_path, img.data[:img.parts["p5"][0] + 8192])
    else:
        xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc, config = _stream_into_slot(tmp_path, xz, boot, root, "1" * 64)
    assert proc.returncode != 0
    assert "STREAMED" not in proc.stdout
    assert (config / "slot-B-incomplete").exists()
    assert "Writing Slot B stopped" in (tmp_path / "update.log").read_text()


def test_a_refused_image_leaves_the_slot_as_it_was(tmp_path):
    img = ab_image(p1_label="SOMETHING")
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc, config = _stream_into_slot(tmp_path, xz, boot, root)
    assert proc.returncode == 1
    assert "Nothing was written to Slot B" in proc.stderr
    assert not (config / "slot-B-incomplete").exists()
    assert boot.read_bytes() == FILL * (4 * U * SECTOR)


def test_a_slot_that_was_incomplete_before_stays_marked_when_refused(tmp_path):
    img = ab_image(p1_label="SOMETHING")
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    env, config = _bash_env(tmp_path)
    (config / "slot-B-incomplete").write_text("earlier failed update\n")
    proc, config = _stream_into_slot(tmp_path, xz, boot, root)
    assert proc.returncode == 1
    assert (config / "slot-B-incomplete").exists()


def test_the_running_system_is_passed_as_forbidden(tmp_path):
    # findmnt says the "system" target is mounted at /: the helper refuses it
    img = ab_image()
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path)
    proc, config = _stream_into_slot(tmp_path, xz, boot, root, root_src=str(root))
    assert proc.returncode == 1
    assert "belongs to the system that is running now" in proc.stderr
    assert set(root.read_bytes()) == set(FILL) and boot.read_bytes() == FILL * (4 * U * SECTOR)
    assert not (config / "slot-B-incomplete").exists()


def test_probe_image_refuses_without_marking_the_slot(tmp_path):
    img = ab_image(root_units=50)
    xz = _xz(tmp_path, img.data)
    boot, root = _targets(tmp_path, root_size=40 * U * SECTOR)
    env, config = _bash_env(tmp_path)
    proc = subprocess.run(
        ["bash", "-c", f'. "{_SCRIPT}"\nprobe_image "{xz}" "{root}" "{boot}" B\necho PROBED'],
        capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 1
    assert "does not fit" in proc.stderr and "Nothing was written: Slot B is unchanged" in proc.stderr
    assert "PROBED" not in proc.stdout
    assert not (config / "slot-B-incomplete").exists()


def test_the_update_checks_and_probes_before_it_writes():
    text = open(_SCRIPT).read()
    main = text[text.index("main() {"):]
    assert main.index("download_image ") < main.index("verify_checksum ")
    assert main.index("verify_checksum ") < main.index("probe_image ")
    assert main.index("probe_image ") < main.index("write_image_to_slot ")
    body = text[text.index("write_image_to_slot() {"):text.index("cleanup_download() {")]
    assert body.index("unmount_target ") < body.index("stream_into_slot ")
    stream = text[text.index("stream_into_slot() {"):text.index("unmount_target() {")]
    assert stream.index("mark_slot_incomplete ") < stream.index("run_streamer ")


def test_nothing_is_unpacked_to_disk_any_more():
    text = open(_SCRIPT).read()
    for gone in ("image.img", "losetup", "decompress_image", "MIN_FREE_KB", "15GB", "dd if="):
        assert gone not in text, gone


# --- free space: the download plus 0.5 GB ----------------------------------------

def _space(tmp_path, snippet, avail_kb):
    bindir = tmp_path / "dfbin"
    bindir.mkdir(exist_ok=True)
    (bindir / "df").write_text(f"#!/bin/bash\necho Avail\necho {avail_kb}\n")
    (bindir / "df").chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", RQ_UPDATE_DIR=str(tmp_path / "dl"),
               RQ_UPDATE_LOG=str(tmp_path / "update.log"))
    return subprocess.run(["bash", "-c", f'. "{_SCRIPT}"\n{snippet}\necho FITS'],
                          capture_output=True, text=True, env=env)


GB_KB = 1_000_000_000 // 1024


def test_a_known_download_needs_its_size_plus_half_a_gb(tmp_path):
    size = 2_066_617_064                                        # a dev -ab.img.xz
    proc = _space(tmp_path, f"check_free_space {size}", int(2.6 * GB_KB))
    assert proc.returncode == 0 and "FITS" in proc.stdout, proc.stderr
    proc = _space(tmp_path, f"check_free_space {size}", int(2.5 * GB_KB))
    assert proc.returncode == 22
    assert "2.6 GB needed" in proc.stderr and "the download plus 0.5 GB" in proc.stderr


def test_without_a_size_3_gb_are_needed(tmp_path):
    proc = _space(tmp_path, "check_free_space", int(2.9 * GB_KB))
    assert proc.returncode == 22 and "3.0 GB needed" in proc.stderr
    proc = _space(tmp_path, "check_free_space ''", int(3.1 * GB_KB))
    assert proc.returncode == 0


def test_a_64_gb_card_with_all_docker_demos_can_update(tmp_path):
    # R-052: about 6 GB free on the running slot used to be refused (15 GB)
    proc = _space(tmp_path, "check_free_space", 6 * GB_KB)
    assert proc.returncode == 0, proc.stderr


def test_the_download_size_comes_from_the_manifest_then_github(tmp_path):
    manifest = tmp_path / "releases.json"
    manifest.write_text('{"streams": {"beta": {"tag": "beta-2026-10-04-143935", '
                        '"image_download_size": 1645458180, "ab_image_download_size": 1663679844}}}')
    api = tmp_path / "api" / "repos" / "JanLahmann" / "RasQberry-Two" / "releases" / "tags"
    api.mkdir(parents=True)
    (api / "beta-2026-09-30-221656").write_text('{"assets": [{"name": "x-ab.img.xz", "size": 1700000000}]}')
    env = dict(os.environ, RQB_RELEASES_URL=f"file://{manifest}", RQ_GITHUB_API=f"file://{tmp_path}/api",
               RQ_UPDATE_LOG=str(tmp_path / "update.log"))
    base = "https://github.com/JanLahmann/RasQberry-Two/releases/download"

    def size(url, tag):
        return subprocess.run(["bash", "-c", f'. "{_SCRIPT}"\nresolve_download_size "{url}" "{tag}"'],
                              capture_output=True, text=True, env=env).stdout.strip()

    assert size(f"{base}/beta-2026-10-04-143935/x-ab.img.xz", "beta-2026-10-04-143935") == "1663679844"
    assert size(f"{base}/beta-2026-10-04-143935/x.img.xz", "beta-2026-10-04-143935") == "1645458180"
    assert size(f"{base}/beta-2026-09-30-221656/x-ab.img.xz", "beta-2026-09-30-221656") == "1700000000"
    assert size(f"{base}/beta-2026-09-01-000000/x-ab.img.xz", "beta-2026-09-01-000000") == ""
