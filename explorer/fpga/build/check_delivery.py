#!/usr/bin/env python3
"""Verify a KR260 PL delivery against evidence/artifact_consistency.json.

Section 3.2.5.1(2) of the competition guide asks for the produced
.bit / .xsa / .hwh next to the build scripts.  The routed binaries ship in
KR260_PL_CAN_FIX_DELIVERY_*.zip, so this script checks any candidate copy
(directory or zip) against the sizes and SHA-256 recorded in the package
before it is published.

Usage:
    python fpga/build/check_delivery.py <dir-or-zip> [more...]

Exit code 0 only when every expected file is found with the exact size and
hash.  A file that exists but differs is reported as MISMATCH and fails:
do not publish a different build in place of the final one.
"""

import hashlib
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.normpath(os.path.join(HERE, "..", "evidence", "artifact_consistency.json"))


def load_expected():
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    return doc.get("files", {})


def sha256_bytes(chunk_iter):
    h = hashlib.sha256()
    for chunk in chunk_iter:
        h.update(chunk)
    return h.hexdigest()


def scan_dir(root):
    found = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            found.setdefault(name.lower(), []).append(os.path.join(base, name))
    return found


def hash_path(path):
    with open(path, "rb") as fh:
        size = os.fstat(fh.fileno()).st_size
        digest = sha256_bytes(iter(lambda: fh.read(1 << 20), b""))
    return size, digest


def hash_zip_entry(zf, entry):
    with zf.open(entry) as fh:
        digest = sha256_bytes(iter(lambda: fh.read(1 << 20), b""))
    return entry.file_size, digest


def check_source(source, expected):
    results = []
    if os.path.isdir(source):
        found = scan_dir(source)
        for name, meta in sorted(expected.items()):
            paths = found.get(name.lower(), [])
            if not paths:
                results.append((name, "NOT FOUND", None, meta))
                continue
            size, digest = hash_path(paths[0])
            ok = size == meta["bytes"] and digest == meta["sha256"]
            results.append((name, "OK" if ok else "MISMATCH", (size, digest), meta))
        return results

    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as zf:
            index = {}
            for entry in zf.infolist():
                if entry.is_dir():
                    continue
                index.setdefault(os.path.basename(entry.filename).lower(), []).append(entry)
            for name, meta in sorted(expected.items()):
                entries = index.get(name.lower(), [])
                if not entries:
                    results.append((name, "NOT FOUND", None, meta))
                    continue
                size, digest = hash_zip_entry(zf, entries[0])
                ok = size == meta["bytes"] and digest == meta["sha256"]
                results.append((name, "OK" if ok else "MISMATCH", (size, digest), meta))
        return results

    raise SystemExit("not a directory and not a zip: %s" % source)


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    expected = load_expected()
    if not expected:
        raise SystemExit("no files section in %s" % MANIFEST)

    failed = False
    for source in argv[1:]:
        print("source: %s" % source)
        for name, status, got, meta in check_source(source, expected):
            line = "  %-28s %-9s expected %s B  %s" % (
                name, status, meta["bytes"], meta["sha256"][:16])
            if got is not None:
                line += "  got %s B  %s" % (got[0], got[1][:16])
            print(line)
            if status != "OK":
                failed = True
        print("")
    print("RESULT: %s" % ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
