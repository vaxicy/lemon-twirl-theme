"""Build the Chrome Web Store ZIP for Lemon Twirl Theme.

Only the theme body is packaged; the store artwork and the tooling are kept
separately in the repository.

Usage:  python3 scripts/package.py [--force]
Output: dist/lemon-twirl-theme-<version>.zip plus the same file in the default
        release folder (two levels above this project, derived at run time).
"""

import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "lemon-twirl-theme"
EXPECTED_VERSION = "1.0.0"
INCLUDE = ("manifest.json", "README.md", "logo")

# Derived from the project location: .../<projects>/Chrome-themes/<project>
DEFAULT_OUT = Path(os.path.abspath(os.path.join(ROOT, os.pardir, os.pardir)))


def build(zip_path):
    manifest = json.loads((ROOT / "manifest.json").read_text("utf-8-sig"))

    # 1. manifest sanity (first upload stays on the initial version)
    assert manifest["manifest_version"] == 3, "expected manifest_version 3"
    assert manifest["version"] == EXPECTED_VERSION, (
        "expected version %s, got %s" % (EXPECTED_VERSION, manifest["version"]))

    # 2. every file the manifest references must exist
    refs = list(manifest.get("icons", {}).values())
    missing = [r for r in refs if not (ROOT / r).is_file()]
    assert not missing, "manifest references missing files: %s" % missing

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in INCLUDE:
            src = ROOT / rel
            assert src.exists(), "missing %s" % rel
            if src.is_dir():
                for f in sorted(src.rglob("*")):
                    if f.is_file():
                        z.write(f, str(f.relative_to(ROOT)))
            else:
                z.write(src, rel)

        names = z.namelist()
        # 3. manifest.json sits at the root of the archive
        assert "manifest.json" in names, "manifest.json must be at the archive root"
        # 4. the manifest inside the zip parses and matches the local one
        inside = json.loads(z.read("manifest.json").decode("utf-8"))
        assert inside["name"] == manifest["name"], "name mismatch inside the archive"
        assert inside["version"] == manifest["version"], "version mismatch inside the archive"
        # 5. nothing that belongs to the tooling or the store listing slipped in
        forbidden = ("store-assets/", "scripts/", "dist/", ".codebuddy/", ".git",
                     "Cached Theme", ".gitignore", "LICENSE")
        leaked = [n for n in names if n.startswith(forbidden)]
        assert not leaked, "unexpected entries in the archive: %s" % leaked
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="release folder for the upload copy")
    parser.add_argument("--force", action="store_true", help="overwrite an existing ZIP")
    args = parser.parse_args()

    manifest = build(ROOT / "dist" / ("%s-%s.zip" % (NAME, EXPECTED_VERSION)))
    local = ROOT / "dist" / ("%s-%s.zip" % (NAME, manifest["version"]))

    release = Path(args.out)
    release.mkdir(parents=True, exist_ok=True)
    dst = release / local.name
    if dst.exists() and not args.force:
        raise SystemExit("archive already exists: %s (use --force to overwrite)" % dst)
    shutil.copy2(local, dst)

    # 6. the release copy is byte-identical (never ship a stale archive)
    assert local.read_bytes() == dst.read_bytes(), "release copy differs from the build"

    with zipfile.ZipFile(dst) as z:
        print("%s (%d bytes)" % (dst, dst.stat().st_size))
        for info in z.infolist():
            print("  %s  %d bytes" % (info.filename, info.file_size))
    print("build copy: %s" % local)


if __name__ == "__main__":
    main()
