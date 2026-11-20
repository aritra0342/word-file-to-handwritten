#!/usr/bin/env python3
"""Download the bundled fonts into the skill folder if they are missing.

The fonts come from the Google Fonts repository at a pinned commit and are
checked against known SHA-256 hashes. Used by the GitHub workflows.
"""
import hashlib
import pathlib
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/google/fonts/06bfe0d62a98375cb09c942fa18e68bd32cff057/ofl/"
DEST = pathlib.Path(__file__).resolve().parents[1] / "skills" / "word-file-to-handwritten" / "assets" / "fonts"
FILES = {
    "Mali-Regular.ttf": ("mali/Mali-Regular.ttf", "e3212f0f9be130743d32a4f174b7d79628daa5db0d72ca4c63c799ae465597bb"),
    "OFL-Mali.txt": ("mali/OFL.txt", "bc1175730d609233043cde47e48f69831f012e85537c5ec1a2cf4836757c1540"),
    "PlaypenSans.ttf": ("playpensans/PlaypenSans%5Bwght%5D.ttf", "e083f9da8be210e08ea982ab510894641aab37590e70620d6db73f8de881ec4a"),
    "OFL-PlaypenSans.txt": ("playpensans/OFL.txt", "59440310cc2c539b53c835306f74ac8c01f1ece58bf4c65e556fca275b80a730"),
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for name, (path, want) in FILES.items():
        target = DEST / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == want:
            print("ok      ", name)
            continue
        data = urllib.request.urlopen(BASE + path, timeout=60).read()
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            sys.exit(f"{name}: hash mismatch (got {got})")
        target.write_bytes(data)
        print("fetched ", name)


if __name__ == "__main__":
    main()
