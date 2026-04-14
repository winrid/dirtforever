"""Post-process locid_results.json: re-OCR all valid probes with PSM 11."""
from __future__ import annotations

import json
import os
import subprocess

DISC = "C:/Users/winrid/dr2server/runtime/discovery"
CROP = "C:/Users/winrid/dr2server/scripts/crop.py"
TESS = "C:/Program Files/Tesseract-OCR/tesseract.exe"
HEADER_RECT = (1080, 380, 1500, 460)


def re_ocr(lid: int) -> str:
    full = f"{DISC}/locid_{lid:03d}.png"
    if not os.path.exists(full):
        return ""
    hdr = f"{DISC}/locid_{lid:03d}_header_final.png"
    subprocess.run(
        ["python", CROP, full, hdr, *(str(v) for v in HEADER_RECT)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    r = subprocess.run(
        [TESS, hdr, "stdout", "--psm", "11"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return r.stdout.strip()


def main() -> None:
    with open(f"{DISC}/locid_results.json", encoding="utf-8") as f:
        results = json.load(f)

    for r in results:
        if r["status"] != "ok":
            continue
        lid = r["loc_id"]
        text = re_ocr(lid)
        r["header_ocr"] = text
        cleaned = " | ".join(
            line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().isdigit()
        )
        print(f"L{lid:03d}  {cleaned}")

    with open(f"{DISC}/locid_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
