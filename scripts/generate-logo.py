#!/usr/bin/env python3
"""Write the Lemon Twirl theme icon to logo/logo.png (128x128).

Chrome themes only need the 128 px icon, and it is kept at logo/logo.png so it
is easy to find when uploading to the Web Store.

  python3 scripts/generate-logo.py            # logo/logo.png
  python3 scripts/generate-logo.py --options  # also re-render the candidates
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logo_art  # noqa: E402  (needs the path tweak above)

ROOT = logo_art.ROOT
LOGO_DIR = os.path.join(ROOT, "logo")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--options", action="store_true",
                    help="also write the four candidates into store-assets/icon-options/")
    args = ap.parse_args()

    os.makedirs(LOGO_DIR, exist_ok=True)
    path = os.path.join(LOGO_DIR, "logo.png")
    logo_art.render().save(path)
    print("wrote logo/logo.png (128x128) from design: %s" % logo_art.CHOSEN)

    if args.options:
        logo_art.write_options(os.path.join(ROOT, "store-assets", "icon-options"))


if __name__ == "__main__":
    main()
