#!/usr/bin/env python3
"""
RasQberry: unpack an image straight into an A/B slot (R-052).

rq_update_slot.sh used to unpack the whole -ab image (about 12 GB) into
/var/tmp before writing its partitions into the other slot, so an update
needed about 15 GB free on the running system. This helper reads the image
once, as a stream from `xz -dc`, and copies the two partitions a slot needs
straight to the slot's partitions in one forward pass:

- The partition table (MBR) at the start of the stream says where the
  partitions are; the label of the first partition says which image it is
  (the mapping rq_update_slot.sh used on the unpacked image):
    CONFIG  the A/B image:      boot = p2 (BOOT-A), root = p5 (SYSTEM-A, the
                                first logical partition: its EBR is the first
                                sector of the extended partition)
    BOOTFS  the standard image: boot = p1, root = p2
  The partitions lie in this order, so one forward pass reaches them all.
- The boot partition has to start with a FAT boot sector, the root partition
  with an ext4 superblock, and each has to fit its target.
- The SHA256 of the whole unpacked stream is computed on the way and compared
  with --extract-sha256 (extract_sha256 / ab_extract_sha256 in
  RQB-releases.json) at the end.
- Targets that belong to the running system (--forbid) are never written. A
  block device is opened with O_EXCL, which the kernel refuses (EBUSY) while
  the device is mounted.

Usage:
    rq_stream_image.py IMAGE.img.xz --boot DEV --root DEV [--extract-sha256 SUM]
                       [--forbid DEV]... [--probe] [--log FILE]

--probe reads only as far as needed to check the layout (about 1.5 GB of the
A/B image: seconds, not minutes) and writes nothing: rq_update_slot.sh runs it before
the target slot is touched.

Prints key=value lines (layout, partitions, extract_sha256) on stdout,
progress on a terminal (stderr), errors as "ERROR: ..." on stderr.

Exit codes:
    0  done; with --probe: the image fits the targets
    2  usage error                      (nothing was written)
    3  refused                          (nothing was written)
    4  stopped after writing began      (the targets hold no usable system)
    5  all written, but the SHA256 of the unpacked image does not match
"""

import argparse
import hashlib
import os
import queue
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time

SECTOR = 512
# Bytes per read and write. RQ_STREAM_CHUNK is for tests (small images,
# many chunk boundaries).
CHUNK = int(os.environ.get("RQ_STREAM_CHUNK") or 4 * 1024 * 1024)
EXTENDED_TYPES = (0x05, 0x0F, 0x85)
EXT4_MAGIC_OFFSET = 1024 + 56      # s_magic in the ext2/3/4 superblock
EXT4_MAGIC = b"\x53\xef"           # 0xEF53, little endian

RC_OK, RC_USAGE, RC_REFUSED, RC_FAILED, RC_MISMATCH = 0, 2, 3, 4, 5


class ImageError(Exception):
    """The image or a target cannot be used; the message is for the user."""


class Mismatch(Exception):
    """All written, but the unpacked image is not the published one."""


def mb(size):
    """Size in whole MB (as the old updater's messages had it)."""
    return size // (1024 * 1024)


class Log:
    """Timestamped lines appended to rq_update_slot.sh's log (optional)."""

    def __init__(self, path):
        self.path = path

    def __call__(self, text):
        if not self.path:
            return
        try:
            with open(self.path, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
        except OSError:
            pass


class Hasher:
    """SHA256 of everything read, in a thread of its own: hashlib releases
    the GIL, so hashing runs while the main thread waits for xz or the card."""

    def __init__(self):
        self._sha = hashlib.sha256()
        self._queue = queue.Queue(maxsize=8)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            data = self._queue.get()
            if data is None:
                return
            self._sha.update(data)

    def update(self, data):
        self._queue.put(data)

    def hexdigest(self):
        self._queue.put(None)
        self._thread.join()
        return self._sha.hexdigest()


class Progress:
    """One line on the terminal, updated in place about once a second."""

    def __init__(self, total, stream):
        self.total = total
        self.stream = stream
        self.next = 0.0
        self.shown = False

    def update(self, pos, final=False):
        now = time.monotonic()
        if not final and now < self.next:
            return
        self.next = now + 1.0
        if self.total:
            pct = min(100, pos * 100 // self.total)
            text = f"{pos / 1e9:.1f} of {self.total / 1e9:.1f} GB ({pct}%)"
        else:
            text = f"{pos / 1e9:.1f} GB"
        self.stream.write(f"\r  {text}   ")
        self.stream.flush()
        self.shown = True

    def done(self, pos):
        if self.shown:
            self.update(pos, final=True)
            self.stream.write("\n")
            self.stream.flush()


class Source:
    """The unpacked image as a forward-only stream. Every byte is hashed once,
    when it comes out of xz; peek() looks ahead without consuming."""

    def __init__(self, pipe, hasher=None, progress=None):
        self._pipe = pipe
        self._hasher = hasher
        self._progress = progress
        self._buf = b""
        self.pos = 0
        self.eof = False

    def _pull(self, n):
        data = self._pipe.read(n)
        if not data:
            self.eof = True
        elif self._hasher:
            self._hasher.update(data)
        return data

    def read(self, n):
        """Up to n bytes; b"" at the end of the stream."""
        if self._buf:
            data, self._buf = self._buf[:n], self._buf[n:]
        else:
            data = self._pull(n)
        self.pos += len(data)
        if self._progress:
            self._progress.update(self.pos)
        return data

    def peek(self, n, what):
        while len(self._buf) < n:
            data = self._pull(max(n - len(self._buf), SECTOR))
            if not data:
                raise ImageError(ended(what, self.pos + len(self._buf)))
            self._buf += data
        return self._buf[:n]

    def skip_to(self, offset, what):
        if offset < self.pos:
            raise ImageError(f"The image's partitions are not in the expected order ({what} starts at "
                             f"byte {offset}, the stream is already at {self.pos}).")
        while self.pos < offset:
            if not self.read(min(CHUNK, offset - self.pos)):
                raise ImageError(ended(what, self.pos))

    def read_exact(self, n, what):
        parts, got = [], 0
        while got < n:
            data = self.read(n - got)
            if not data:
                raise ImageError(ended(what, self.pos))
            parts.append(data)
            got += len(data)
        return b"".join(parts)

    def copy(self, offset, size, target, what):
        self.skip_to(offset, what)
        end = offset + size
        while self.pos < end:
            data = self.read(min(CHUNK, end - self.pos))
            if not data:
                raise ImageError(ended(what, self.pos))
            target.write(data)

    def drain(self):
        while self.read(CHUNK):
            pass


def ended(what, pos):
    return (f"The image ended early, at {pos / 1e9:.2f} GB, before the end of {what}: "
            f"the download is damaged or incomplete.")


class Part:
    """A partition of the image: byte offset and size."""

    def __init__(self, name, start, size):
        self.name, self.start, self.size = name, start, size

    @property
    def end(self):
        return self.start + self.size

    def __str__(self):
        return f"{self.name} start={self.start} size={self.size}"


def parse_table(sector, what):
    """The four entries of an MBR or EBR sector: [(type, first LBA, sectors)]."""
    if len(sector) < SECTOR or sector[510:512] != b"\x55\xaa":
        raise ImageError(f"The image has no valid partition table ({what}).")
    entries = []
    for i in range(4):
        entry = sector[446 + 16 * i: 446 + 16 * (i + 1)]
        lba, count = struct.unpack_from("<II", entry, 8)
        entries.append((entry[4], lba, count))
    return entries


def fat_label(boot_sector):
    """Volume label of a FAT boot sector; None when it is no FAT boot sector,
    '' when it has no label."""
    if len(boot_sector) < SECTOR or boot_sector[510:512] != b"\x55\xaa":
        return None
    fat32 = struct.unpack_from("<H", boot_sector, 22)[0] == 0     # BPB_FATSz16
    sig, label, fstype = (66, 71, 82) if fat32 else (38, 43, 54)
    if not boot_sector[fstype:fstype + 3] == b"FAT":
        return None
    if boot_sector[sig] != 0x29:                                 # no BS_VolLab
        return ""
    text = boot_sector[label:label + 11].decode("ascii", "replace").strip()
    return "" if text.upper() == "NO NAME" else text


def is_ext4(head):
    return head[EXT4_MAGIC_OFFSET:EXT4_MAGIC_OFFSET + 2] == EXT4_MAGIC


def same_file(a, b):
    """True when a and b are the same block device (or file)."""
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    if stat.S_ISBLK(sa.st_mode) and stat.S_ISBLK(sb.st_mode):
        return sa.st_rdev == sb.st_rdev
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


class Target:
    """A slot partition (or, in tests, a regular file of its size)."""

    def __init__(self, path, role):
        self.path, self.role = path, role
        self.fd = None
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError as e:
            raise ImageError(f"{path} ({role}) cannot be opened: {e.strerror}.")
        try:
            self.size = os.lseek(fd, 0, os.SEEK_END)
        finally:
            os.close(fd)

    def open(self):
        flags = os.O_WRONLY
        if stat.S_ISBLK(os.stat(self.path).st_mode):
            flags |= os.O_EXCL          # EBUSY while it is mounted
        try:
            self.fd = os.open(self.path, flags)
        except OSError as e:
            raise ImageError(f"{self.path} ({self.role}) cannot be opened for writing: {e.strerror}. "
                             f"Is it mounted or in use?")

    def write(self, data):
        view = memoryview(data)
        while view:
            try:
                n = os.write(self.fd, view)
            except OSError as e:
                raise ImageError(f"Writing {self.path} failed: {e.strerror}.")
            view = view[n:]

    def finish(self):
        """Flush to the card (errors of earlier writes show up here) and close."""
        try:
            os.fsync(self.fd)
        except OSError as e:
            raise ImageError(f"Writing {self.path} failed: {e.strerror}.")
        finally:
            os.close(self.fd)
            self.fd = None

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None


def unpacked_size(image):
    """Size of the unpacked image from the .xz index (for the progress line)."""
    try:
        out = subprocess.run(["xz", "--robot", "--list", "--", image],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        fields = line.split("\t")
        if fields[0] == "totals" and len(fields) > 4 and fields[4].isdigit():
            return int(fields[4])
    return None


class Writer:
    """One pass over the image: find the partitions, check them, write them."""

    def __init__(self, src, boot, root, probe, log, out):
        self.src, self.boot_t, self.root_t = src, boot, root
        self.probe, self.log, self.out = probe, log, out
        self.written = False

    def say(self, key, value):
        self.out.write(f"{key}={value}\n")
        self.log(f"{key}={value}")

    def fits(self, part, target, what):
        if part.size <= 0:
            raise ImageError(f"The image has no {what} partition.")
        if part.size > target.size:
            raise ImageError(f"The image's {what} partition ({mb(part.size)} MB) does not fit "
                             f"{target.path} ({mb(target.size)} MB).")

    def first_logical(self, ext):
        """The first logical partition: entry 0 of the EBR at the start of the
        extended partition, its start relative to that EBR."""
        self.src.skip_to(ext.start, "the extended partition")
        ebr = parse_table(self.src.read_exact(SECTOR, "the extended partition"),
                          "the extended partition's first EBR")
        ptype, rel, count = ebr[0]
        if ptype == 0 or rel == 0 or count == 0:
            raise ImageError("The image's extended partition holds no system partition.")
        return Part("p5", ext.start + rel * SECTOR, count * SECTOR)

    def check_root_start(self, root):
        self.src.skip_to(root.start, "the system partition")
        if not is_ext4(self.src.peek(EXT4_MAGIC_OFFSET + 2, "the system partition")):
            raise ImageError("The image's system partition holds no ext4 file system.")

    def run(self):
        src = self.src
        mbr = parse_table(src.read_exact(SECTOR, "the partition table"), "MBR")
        if any(ptype == 0xEE for ptype, _, _ in mbr):
            raise ImageError("The image has a GPT partition table; a RasQberry image has an MBR.")
        parts = [Part(f"p{i + 1}", lba * SECTOR, count * SECTOR) if ptype else None
                 for i, (ptype, lba, count) in enumerate(mbr)]
        if parts[0] is None:
            raise ImageError("The image has no first partition.")

        # Which image: the label of p1 (CONFIG on the A/B image, BOOTFS on the
        # standard one), as the old updater read it with lsblk
        src.skip_to(parts[0].start, "the first partition")
        label = fat_label(src.peek(SECTOR, "the first partition"))
        kind = (label or "").upper()
        ext = root = None
        if kind == "CONFIG":
            boot = parts[1]
            ext = next((parts[i] for i, (ptype, _, _) in enumerate(mbr)
                        if ptype in EXTENDED_TYPES), None)
            if boot is None or ext is None:
                raise ImageError("The A/B image lacks BOOT-A (p2) or its extended partition (p4).")
            layout = "ab"
        elif kind == "BOOTFS":
            boot, root = parts[0], parts[1]
            if root is None:
                raise ImageError("The standard image has no root partition (p2).")
            layout = "standard"
        else:
            raise ImageError(f"Unknown image type: p1 label '{label or ''}' (expected 'CONFIG' or 'BOOTFS').")
        self.say("layout", layout)
        self.say("boot", boot)
        self.fits(boot, self.boot_t, "boot")
        if root is not None:
            self.fits(root, self.root_t, "system")
            if root.start < boot.end:
                raise ImageError("The image's system partition lies before its boot partition.")

        src.skip_to(boot.start, "the boot partition")
        if fat_label(src.peek(SECTOR, "the boot partition")) is None:
            raise ImageError("The image's boot partition holds no FAT file system.")

        if self.probe:
            if root is None:
                if ext.start < boot.end:
                    raise ImageError("The image's extended partition starts inside its boot partition.")
                root = self.first_logical(ext)
            self.say("root", root)
            self.fits(root, self.root_t, "system")
            self.check_root_start(root)
            return

        # Both targets are opened before the first byte is written: one that
        # is mounted or in use stops the update with the slot unchanged
        self.boot_t.open()
        self.root_t.open()
        self.written = True
        src.copy(boot.start, boot.size, self.boot_t, "the boot partition")
        if root is None:
            root = self.first_logical(ext)
        self.say("root", root)
        self.fits(root, self.root_t, "system")
        self.check_root_start(root)
        src.copy(root.start, root.size, self.root_t, "the system partition")
        # Flushed once both are written (the kernel writes the boot partition
        # back while the system partition streams in)
        self.boot_t.finish()
        self.root_t.finish()
        src.drain()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Unpack an A/B image straight into a slot.")
    parser.add_argument("image", help="the .img.xz (checked against its SHA256 before)")
    parser.add_argument("--boot", required=True, help="target boot partition (BOOT-A/BOOT-B)")
    parser.add_argument("--root", required=True, help="target system partition (SYSTEM-A/SYSTEM-B)")
    parser.add_argument("--extract-sha256", default="", help="SHA256 of the unpacked image")
    parser.add_argument("--forbid", action="append", default=[],
                        help="a device that is never written (the running system's)")
    parser.add_argument("--probe", action="store_true", help="only check the layout; write nothing")
    parser.add_argument("--log", default="", help="append what happens to this file")
    args = parser.parse_args(argv)
    log = Log(args.log)
    expected = args.extract_sha256.strip().lower()

    targets = []
    try:
        if same_file(args.boot, args.root):
            raise ImageError(f"Boot and system target are the same device ({args.boot}).")
        for path, role in ((args.boot, "boot"), (args.root, "system")):
            for forbidden in filter(None, args.forbid):
                if same_file(path, forbidden):
                    raise ImageError(f"{path} belongs to the system that is running now, "
                                     f"so it is never written.")
            targets.append(Target(path, role))
        if not os.path.isfile(args.image):
            raise ImageError(f"{args.image} not found.")
    except ImageError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        log(f"refused: {e}")
        return RC_REFUSED

    progress = None
    if not args.probe and sys.stderr.isatty():
        progress = Progress(unpacked_size(args.image), sys.stderr)
    errors = tempfile.TemporaryFile()
    xz = subprocess.Popen(["xz", "-dc", "-T0", "--", args.image],
                          stdout=subprocess.PIPE, stderr=errors)
    # the probe reads a part of the image only: nothing to hash
    hasher = None if args.probe else Hasher()
    src = Source(xz.stdout, hasher, progress)
    writer = Writer(src, targets[0], targets[1], args.probe, log, sys.stdout)
    log(f"{'probe' if args.probe else 'write'}: {args.image} -> boot {args.boot}, system {args.root}")

    def xz_said():
        """xz's last error line, without its "xz: <file>: " prefix."""
        errors.seek(0)
        text = errors.read().decode(errors="replace").strip().splitlines()
        line = text[-1] if text else ""
        for prefix in ("xz: ", f"{args.image}: "):
            if line.startswith(prefix):
                line = line[len(prefix):]
        return line

    try:
        writer.run()
        if args.probe:
            xz.kill()
            xz.wait()
            log("probe: the image fits the slot")
            return RC_OK
        rc = xz.wait()
        if rc != 0:
            raise ImageError(f"The image could not be unpacked (xz: {xz_said() or f'exit code {rc}'}): "
                             f"the download is damaged.")
        if progress:
            progress.done(src.pos)
        actual = hasher.hexdigest()
        writer.say("image_bytes", src.pos)
        writer.say("extract_sha256", actual)
        if expected and actual != expected:
            raise Mismatch(f"The unpacked image does not match the published one (SHA256 expected "
                           f"{expected}, got {actual}): the download is damaged or not the published image.")
        log("unpacked image checksum " + ("OK" if expected else "not published - not compared"))
        return RC_OK
    except (ImageError, Mismatch, KeyboardInterrupt) as e:
        rc = RC_MISMATCH if isinstance(e, Mismatch) else RC_FAILED if writer.written else RC_REFUSED
        message = "Stopped." if isinstance(e, KeyboardInterrupt) else str(e)
        if progress:
            progress.done(src.pos)
        if src.eof and "(xz: " not in message:
            # xz ended the stream early: its own message says why (a damaged file)
            try:
                if xz.wait(timeout=10) != 0 and xz_said():
                    message = f"{message.rstrip('.')} (xz: {xz_said()})."
            except subprocess.TimeoutExpired:
                pass
        if xz.poll() is None:
            xz.kill()
            xz.wait()
        sys.stderr.write(f"ERROR: {message}\n")
        log(f"stopped (exit {rc}): {message}")
        return rc
    finally:
        for target in targets:
            target.close()
        errors.close()


if __name__ == "__main__":
    sys.exit(main())
