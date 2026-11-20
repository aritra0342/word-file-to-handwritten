#!/usr/bin/env python3
"""Render examples/sample.md to examples/sample.png (the image shown in the README)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "word-file-to-handwritten" / "scripts"))
from handwrite import Doc  # noqa: E402
from PIL import Image  # noqa: E402

doc = Doc(paper="ruled", ink="blue")
doc.write_text((ROOT / "examples" / "sample.md").read_text(encoding="utf-8"))
tmp = ROOT / "examples" / "_page.png"
doc.preview(str(tmp))
Image.open(tmp).crop((0, 60, 1654, 860)).resize((1100, 532), Image.LANCZOS).save(ROOT / "examples" / "sample.png", optimize=True)
tmp.unlink()
print("wrote examples/sample.png")
