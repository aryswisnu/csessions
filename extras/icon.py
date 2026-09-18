#!/usr/bin/env python3
"""Draw the csessions app icon: orange starburst on a dark rounded square."""
import math, os, subprocess, sys
from PIL import Image, ImageDraw

S = 1024            # master size, all icns variants are downscaled from this
BG = (32, 30, 28)
FG = (217, 119, 87)  # Claude orange
SS = 4               # supersample factor for smooth edges

img = Image.new("RGBA", (S * SS, S * SS), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([0, 0, S * SS - 1, S * SS - 1], radius=int(S * SS * 0.22), fill=BG)

cx = cy = S * SS / 2
# 12 tapered rays, alternating long and short, like the Claude burst
for i in range(12):
    a = math.radians(i * 30 - 90)
    outer = S * SS * (0.40 if i % 2 == 0 else 0.27)
    half = math.radians(5.4 if i % 2 == 0 else 4.4)   # ray half-width at the base
    inner = S * SS * 0.075
    d.polygon([
        (cx + outer * math.cos(a), cy + outer * math.sin(a)),
        (cx + inner * math.cos(a + half * 6), cy + inner * math.sin(a + half * 6)),
        (cx + inner * math.cos(a - half * 6), cy + inner * math.sin(a - half * 6)),
    ], fill=FG)
d.ellipse([cx - S * SS * 0.072, cy - S * SS * 0.072,
           cx + S * SS * 0.072, cy + S * SS * 0.072], fill=FG)

img = img.resize((S, S), Image.LANCZOS)

out = sys.argv[1] if len(sys.argv) > 1 else "icon.icns"
iconset = out.replace(".icns", ".iconset")
os.makedirs(iconset, exist_ok=True)
for px in (16, 32, 64, 128, 256, 512, 1024):          # iconutil wants both @1x and @2x
    img.resize((px, px), Image.LANCZOS).save(f"{iconset}/icon_{px}x{px}.png")
    img.resize((px, px), Image.LANCZOS).save(f"{iconset}/icon_{px // 2}x{px // 2}@2x.png")
for stray in ("icon_8x8.png", "icon_1024x1024.png"):   # sizes iconutil rejects
    p = f"{iconset}/{stray}"
    os.path.exists(p) and os.remove(p)
subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out], check=True)
print("wrote", out)
