#!/usr/bin/env python3
"""Validate registry entries. Usage: validate.py mods/foo.json [...]

Env: BASE_REF (git ref holding the previous entry, default origin/main),
     PR_AUTHOR (github login; enforces authorship on updates when set).
"""
import hashlib, io, json, os, re, subprocess, sys, urllib.request, zipfile

REQUIRED = ("name", "version", "abi", "description", "authors", "repository", "license", "download", "sha256")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def semver(v):
    m = SEMVER_RE.match(v)
    if not m:
        raise SystemExit(f"version {v!r} is not MAJOR.MINOR.PATCH")
    return tuple(int(x) for x in m.groups())


def previous(path):
    ref = os.environ.get("BASE_REF", "origin/main")
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def check(path):
    entry = json.load(open(path))
    missing = [k for k in REQUIRED if k not in entry]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")
    name = entry["name"]
    if not NAME_RE.match(name):
        raise SystemExit(f"{path}: bad name {name!r} (lowercase, digits, dashes)")
    if os.path.basename(path) != f"{name}.json":
        raise SystemExit(f"{path}: filename must be {name}.json")
    if not entry["authors"]:
        raise SystemExit(f"{path}: authors is empty")
    if not entry["download"].startswith("https://"):
        raise SystemExit(f"{path}: download must be https")

    prev = previous(path)
    if prev:
        if semver(entry["version"]) <= semver(prev["version"]):
            raise SystemExit(f"{path}: version {entry['version']} must be > {prev['version']}")
        actor = os.environ.get("PR_AUTHOR")
        if actor and actor not in prev["authors"]:
            raise SystemExit(f"{path}: {actor} is not in authors {prev['authors']}")
    else:
        semver(entry["version"])

    data = urllib.request.urlopen(entry["download"], timeout=60).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry["sha256"].lower():
        raise SystemExit(f"{path}: sha256 mismatch: got {digest}")

    zf = zipfile.ZipFile(io.BytesIO(data))
    names = set(zf.namelist())
    if "mod.json" not in names:
        raise SystemExit(f"{path}: zip has no mod.json at root")
    manifest = json.loads(zf.read("mod.json"))
    if manifest.get("name") != name or manifest.get("version") != entry["version"]:
        raise SystemExit(f"{path}: mod.json name/version {manifest.get('name')}@{manifest.get('version')} != registry entry")
    wasm = manifest.get("wasm", "")
    if wasm not in names:
        raise SystemExit(f"{path}: zip missing wasm {wasm!r}")
    head = zf.read(wasm)[:8]
    # core module preamble = magic + version 1; a Component Model binary carries
    # 0d 00 01 00 here and the host loader rejects it, so refuse it upfront.
    if head != b"\0asm\x01\x00\x00\x00":
        raise SystemExit(f"{path}: {wasm} is not a core wasm module (preamble {head.hex()})")
    print(f"ok {name}@{entry['version']} ({len(data)} bytes)")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        check(p)
