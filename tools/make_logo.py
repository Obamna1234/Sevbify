"""Draw Sevbify's logo and app icon (original artwork, made in code so it stays sharp at every size).

Usage:  python tools/make_logo.py

Writes assets/branding/:
  sevbify_logo_1024.png   logo with the SEVBIFY wordmark (README, releases)
  sevbify_icon_512.png    icon without text (window / taskbar)
  sevbify.ico             Windows icon for Sevbify.exe, its window, taskbar and shortcuts (16-256 px)
  sevbify.icns            macOS app icon (used when the macOS build is switched on)
  sevbify_256.png         Linux menu icon (used with packaging/sevbify.desktop)
  For Android later: start from sevbify_icon_512.png (Play Store icon size).

Design: the SEVBY family look (dark rounded square, SEVBY green, dotted sound wave) turned into a player:
a white play button with SEVBY's green download arrow tucked into its corner.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "branding")
FONT = os.path.join(ROOT, "assets", "fonts", "Figtree-ExtraBold.ttf")

BG = (20, 20, 22)            # SEVBY's background
EDGE = (60, 60, 66)
WHITE = (245, 245, 245)
GREEN = (52, 229, 138)       # SEVBY's accent green
S = 4                        # draw 4x larger, then shrink (smooth edges)


def rounded_triangle(d, pts, radius, fill):
    """A play triangle with rounded corners."""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1]); v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1 = math.hypot(*v1); l2 = math.hypot(*v2)
        a = (p1[0] + v1[0] / l1 * radius, p1[1] + v1[1] / l1 * radius)
        b = (p1[0] + v2[0] / l2 * radius, p1[1] + v2[1] / l2 * radius)
        for t in [k / 12 for k in range(13)]:          # quadratic curve a -> p1 -> b
            x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * b[0]
            y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * b[1]
            out.append((x, y))
    d.polygon(out, fill=fill)


def draw(size, wordmark):
    W = size * S
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = W * 0.02
    d.rounded_rectangle([m, m, W - m, W - m], radius=W * 0.2, fill=BG, outline=EDGE, width=max(1, int(W * 0.004)))

    # Play button, a little left of centre (optically centred), higher when there is a wordmark.
    cy = W * (0.40 if wordmark else 0.47)
    h = W * (0.40 if wordmark else 0.50)
    left = W * (0.33 if wordmark else 0.30)
    pts = [(left, cy - h / 2), (left, cy + h / 2), (left + h * 0.9, cy)]
    rounded_triangle(d, pts, W * 0.045, WHITE)

    # Green download arrow in the lower-right, with an even dark outline so it reads on top of the triangle.
    ax, ay = left + h * 0.80, cy + h * 0.22
    aw = W * (0.17 if wordmark else 0.21)
    arrow = Image.new("L", (W, W), 0)
    ad = ImageDraw.Draw(arrow)
    ad.rounded_rectangle([ax - aw * 0.18, ay - aw * 0.62, ax + aw * 0.18, ay + aw * 0.05], radius=aw * 0.08, fill=255)
    rounded_triangle(ad, [(ax - aw * 0.5, ay), (ax + aw * 0.5, ay), (ax, ay + aw * 0.55)], aw * 0.06, 255)
    box = (int(ax - aw), int(ay - aw), int(ax + aw), int(ay + aw))
    gap = aw * 0.11                                              # width of the dark outline
    grown = arrow.crop(box).filter(ImageFilter.GaussianBlur(gap)).point(lambda v: 255 if v > 6 else 0)
    outline = Image.new("L", (W, W), 0)
    outline.paste(grown.filter(ImageFilter.GaussianBlur(S * 0.6)), box[:2])     # rounded, soft-edged
    img.paste(Image.new("RGBA", (W, W), BG), (0, 0), outline)
    img.paste(Image.new("RGBA", (W, W), GREEN), (0, 0), arrow)
    d = ImageDraw.Draw(img)

    # SEVBY's dotted sound wave.
    wy = W * (0.705 if wordmark else 0.83)
    count = 23
    span = W * (0.62 if wordmark else 0.56)
    for i in range(count):
        x = W / 2 - span / 2 + span * i / (count - 1)
        k = 1 - abs(i - (count - 1) / 2) / ((count - 1) / 2)
        hgt = W * (0.008 + 0.045 * (k ** 1.6) * (0.55 + 0.45 * abs(math.sin(i * 1.7))))
        bw = W * 0.0125
        d.rounded_rectangle([x - bw / 2, wy - hgt / 2, x + bw / 2, wy + hgt / 2], radius=bw / 2, fill=GREEN)

    if wordmark:
        text = "SEVBIFY"
        fsize = int(W * 0.155)
        font = ImageFont.truetype(FONT, fsize)
        while d.textlength(text, font=font) > W * 0.78:
            fsize -= 4
            font = ImageFont.truetype(FONT, fsize)
        d.text((W / 2, W * 0.835), text, font=font, fill=WHITE, anchor="mm")

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    draw(1024, True).save(os.path.join(OUT, "sevbify_logo_1024.png"))
    icon = draw(512, False)
    icon.save(os.path.join(OUT, "sevbify_icon_512.png"))
    big = draw(256, False)
    big.save(os.path.join(OUT, "sevbify.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(os.path.join(OUT, "sevbify_256.png"))
    draw(1024, False).save(os.path.join(OUT, "sevbify.icns"))
    print("written", OUT)


if __name__ == "__main__":
    main()
