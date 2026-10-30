"""Render a real run log into a terminal-style GIF + PNG (no faces, no editing of content).
Usage: python3 docs/render_terminal.py logs/<run>.log docs/demo
Emoji are mapped to ASCII-safe glyphs because the mono font has no colour emoji."""
import sys, textwrap
from PIL import Image, ImageDraw, ImageFont
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
EMO = {"🕯": "[candle]", "👻": "[ghost]", "🧿": "[exorcism]", "🔧": "[repair]", "✨": "[reborn]"}
W_CH, SIZE, PAD = 110, 15, 16
font = ImageFont.truetype(FONT, SIZE)
cw = font.getbbox("M")[2]; lh = SIZE + 5
def color(l):
    if l.startswith("$"): return (120, 200, 255)
    if l.startswith("#"): return (130, 130, 130)
    if "[ghost]" in l: return (200, 170, 255)
    if "[exorcism]" in l or "[repair]" in l: return (255, 190, 90)
    if "[reborn]" in l or l.startswith("OK") or "reincarnated." in l: return (120, 230, 140)
    return (220, 220, 220)
src, out = sys.argv[1], sys.argv[2]
lines = []
for raw in open(src, encoding="utf-8").read().splitlines():
    for e, r in EMO.items(): raw = raw.replace(e, r)
    w = textwrap.wrap(raw, W_CH, subsequent_indent="     ") or [""]
    lines += w
ROWS = 34
W = PAD * 2 + cw * W_CH; H = PAD * 2 + lh * ROWS + 28
def frame(visible):
    img = Image.new("RGB", (W, H), (24, 24, 30)); d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 26], fill=(45, 45, 55))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([12 + i * 20, 8, 24 + i * 20, 20], fill=c)
    d.text((80, 5), "ghost-workflow-medium - real run log: " + src.split("/")[-1], font=font, fill=(170, 170, 170))
    for i, l in enumerate(visible[-ROWS:]):
        d.text((PAD, 28 + PAD + i * lh), l, font=font, fill=color(l))
    return img
frames, durs = [], []
for n in range(1, len(lines) + 1):
    frames.append(frame(lines[:n])); durs.append(350 if lines[n-1].strip() else 150)
durs[-1] = 4000
frames[0].save(out + ".gif", save_all=True, append_images=frames[1:], duration=durs, loop=0, optimize=True)
# full static PNG
H2 = PAD * 2 + lh * len(lines) + 28
ROWS = len(lines); H = H2
frame(lines).save(out + ".png")
print(len(lines), "lines ->", out + ".gif", out + ".png")
