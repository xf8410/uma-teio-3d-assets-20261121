"""Compose rendered views into one labelled three-view sheet."""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

outdir = sys.argv[1]
target = sys.argv[2]
labels = sys.argv[3:] or ["FRONT", "SIDE", "BACK"]

meta = {}
meta_path = os.path.join(outdir, "meta.json")
if os.path.exists(meta_path):
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)

files = [os.path.join(outdir, n.replace(" ", "_").lower() + ".png") for n in labels]
files = [f for f in files if os.path.exists(f)]
if not files:
    raise SystemExit("no renders found")
imgs = [Image.open(f).convert("RGB") for f in files]

PW, PH = imgs[0].size
GAP, MARGIN, LABEL, HEADER = 24, 40, 56, 74
W = MARGIN * 2 + PW * len(imgs) + GAP * (len(imgs) - 1)
H = HEADER + LABEL + PH + MARGIN
sheet = Image.new("RGB", (W, H), (250, 250, 252))
draw = ImageDraw.Draw(sheet)

try:
    font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    font_small = ImageFont.truetype("DejaVuSans.ttf", 20)
except Exception:
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

title = "TOKAI TEIO  BEYOND THE HORIZON  ORTHOGRAPHIC THREE VIEW"
sub = "MODEL %s   TRIS %s   YAW %s   %s" % (
    meta.get("model", "?"), meta.get("triangles", "?"), meta.get("yaw_deg", "?"),
    "  ".join("%s %s" % (v["name"], v["deg"]) for v in meta.get("views", [])),
)
draw.text((MARGIN, 14), title, fill=(30, 32, 38), font=font_big)
draw.text((MARGIN, 50), sub, fill=(110, 112, 120), font=font_small)

for i, im in enumerate(imgs):
    x = MARGIN + i * (PW + GAP)
    y = HEADER + LABEL
    sheet.paste(im, (x, y))
    draw.rectangle([x - 1, y - 1, x + PW, y + PH], outline=(205, 205, 212))
    draw.text((x + 4, HEADER + 14), labels[i].upper(), fill=(30, 32, 38), font=font_big)

sheet.save(target)
print("wrote", target, sheet.size)
