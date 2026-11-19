"""Step 2 of the branding pipeline: compose icons, splash screens and the feature graphic.

Usage (repo root): python3 tools/branding/compose.py
Needs Pillow and the renders from `node tools/branding/render.mjs` in tools/branding/build/.
Writes:
  android/app/src/main/res/mipmap-*/ic_launcher*.png   legacy, round and adaptive layers
  android/app/src/main/res/drawable*/splash.png        launch screens
  public/icons/*.png                                   web manifest, favicon, apple-touch-icon
  store/icon-512.png, store/feature-graphic.png        Play listing art
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "tools/branding/build"
RES = ROOT / "android/app/src/main/res"
BG = (9, 13, 22)  # #090D16
THEME = (27, 54, 93)  # #1B365D
CYAN = (63, 216, 255)
GOLD = (255, 198, 107)


def load_hero(name: str) -> Image.Image:
    img = Image.open(BUILD / f"{name}.png").convert("RGBA")
    return img.crop(img.getbbox())


def radial(size, inner, outer, center=(0.5, 0.5), radius=0.75) -> Image.Image:
    """Radial gradient from inner colour at center to outer colour at radius (fraction of width)."""
    w, h = size
    small = (max(1, w // 4), max(1, h // 4))
    mask = Image.new("L", small)
    cx, cy, r = center[0] * small[0], center[1] * small[1], radius * small[0]
    px = mask.load()
    for y in range(small[1]):
        for x in range(small[0]):
            d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / r
            px[x, y] = int(255 * max(0.0, min(1.0, d)) ** 1.3)
    mask = mask.resize(size, Image.BICUBIC)
    return Image.composite(Image.new("RGB", size, outer), Image.new("RGB", size, inner), mask)


def glow(sprite: Image.Image, color, radius: float, strength: float = 1.0) -> Image.Image:
    """A coloured blurred halo from the sprite's alpha, same size as the sprite plus padding."""
    pad = int(radius * 3)
    alpha = Image.new("L", (sprite.width + pad * 2, sprite.height + pad * 2))
    alpha.paste(sprite.getchannel("A"), (pad, pad))
    alpha = alpha.filter(ImageFilter.GaussianBlur(radius))
    alpha = alpha.point(lambda v: min(255, int(v * strength)))
    halo = Image.new("RGBA", alpha.size, color + (0,))
    halo.putalpha(alpha)
    return halo


def rim_light(sprite: Image.Image, color, width: int) -> Image.Image:
    """Thin coloured edge on the upper-right silhouette so the dark hull reads on dark ground."""
    a = sprite.getchannel("A")
    shifted = ImageChops.offset(a, -width, width)
    edge = ImageChops.subtract(a, shifted).filter(ImageFilter.GaussianBlur(max(1, width / 2)))
    layer = Image.new("RGBA", sprite.size, color + (0,))
    layer.putalpha(ImageChops.multiply(edge, a))
    out = sprite.copy()
    out.alpha_composite(layer)
    return out


def place(canvas: Image.Image, sprite: Image.Image, box_w: float, box_h: float, cx: float, cy: float,
          halo=CYAN, halo_strength=1.6, ground=True):
    """Fit sprite into box (pixels) centred on (cx, cy), with halo, rim and ground glow."""
    s = min(box_w / sprite.width, box_h / sprite.height)
    spr = sprite.resize((max(1, int(sprite.width * s)), max(1, int(sprite.height * s))), Image.LANCZOS)
    spr = rim_light(spr, halo, max(1, spr.width // 120))
    x, y = int(cx - spr.width / 2), int(cy - spr.height / 2)
    if ground:
        g = Image.new("L", canvas.size)
        ImageDraw.Draw(g).ellipse(
            [x + spr.width * 0.08, y + spr.height * 0.70, x + spr.width * 0.92, y + spr.height * 1.04], fill=150)
        g = g.filter(ImageFilter.GaussianBlur(spr.width / 14))
        layer = Image.new("RGBA", canvas.size, halo + (0,))
        layer.putalpha(g)
        canvas.alpha_composite(layer)
    h = glow(spr, halo, max(2, spr.width / 28), halo_strength)
    pad = (h.width - spr.width) // 2
    canvas.alpha_composite(h, (x - pad, y - pad))
    canvas.alpha_composite(spr, (x, y))


def hud_lines(canvas: Image.Image, color, alpha=28, step=None):
    """Faint diagonal tactical grid."""
    w, h = canvas.size
    step = step or max(8, w // 16)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(-h, w + h, step):
        d.line([(i, 0), (i + h, h)], fill=color + (alpha,), width=max(1, w // 512))
    canvas.alpha_composite(layer)


def icon_background(size: int) -> Image.Image:
    bg = radial((size, size), (24, 52, 92), BG, center=(0.5, 0.42), radius=0.78).convert("RGBA")
    hud_lines(bg, CYAN, alpha=14)
    return bg


def icon_full(size: int, tank: Image.Image, fill: float = 0.86) -> Image.Image:
    """Square icon with the tank filling most of it (Play icon, legacy square, web)."""
    big = 1024
    c = icon_background(big)
    place(c, tank, big * fill, big * fill, big / 2, big * 0.53)
    return c.resize((size, size), Image.LANCZOS)


def rounded(img: Image.Image, radius_frac: float) -> Image.Image:
    m = Image.new("L", (img.width * 4, img.height * 4))
    ImageDraw.Draw(m).rounded_rectangle([0, 0, m.width - 1, m.height - 1], radius=int(m.width * radius_frac), fill=255)
    out = img.copy()
    out.putalpha(m.resize(img.size, Image.LANCZOS))
    return out


def main():
    tank = load_hero("terran_hero")
    icon_tank = load_hero("terran_icon")
    alien = load_hero("arcadian_hero")
    out_store = ROOT / "store"
    out_web = ROOT / "public/icons"
    out_store.mkdir(exist_ok=True)
    out_web.mkdir(exist_ok=True)

    # Play icon: full-bleed square (Play applies its own mask).
    icon_full(512, icon_tank, fill=0.8).convert("RGB").save(out_store / "icon-512.png")

    # Adaptive icon layers, 108dp with the 66dp safe zone in the middle.
    fg_big = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    place(fg_big, icon_tank, 1024 * 0.56, 1024 * 0.56, 512, 520)
    bg_big = icon_background(1024)
    densities = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
    legacy = icon_full(1024, icon_tank, fill=0.82)
    for name, k in densities.items():
        d = RES / f"mipmap-{name}"
        layer = int(108 * k)
        fg_big.resize((layer, layer), Image.LANCZOS).save(d / "ic_launcher_foreground.png")
        bg_big.convert("RGB").resize((layer, layer), Image.LANCZOS).save(d / "ic_launcher_background.png")
        px = int(48 * k)
        sq = legacy.resize((px, px), Image.LANCZOS)
        rounded(sq, 0.18).save(d / "ic_launcher.png")
        circ = sq.copy()
        m = Image.new("L", (px * 4, px * 4))
        ImageDraw.Draw(m).ellipse([0, 0, px * 4 - 1, px * 4 - 1], fill=255)
        circ.putalpha(m.resize((px, px), Image.LANCZOS))
        circ.save(d / "ic_launcher_round.png")

    # Web icons.
    for px in (192, 512):
        icon_full(px, icon_tank).convert("RGB").save(out_web / f"icon-{px}.png")
    maskable = bg_big.copy()
    maskable.alpha_composite(fg_big)
    maskable.convert("RGB").resize((512, 512), Image.LANCZOS).save(out_web / "maskable-512.png")
    icon_full(180, icon_tank).convert("RGB").save(out_web / "apple-touch-icon.png")
    icon_full(64, icon_tank, fill=0.96).convert("RGB").save(out_web / "favicon-64.png")

    # Launch screens: flat #090D16 with the tank centred, a third of the short side.
    for d in sorted(RES.glob("drawable*/splash.png")):
        w, h = Image.open(d).size
        c = Image.new("RGBA", (w, h), BG + (255,))
        short = min(w, h)
        place(c, icon_tank, short * 0.46, short * 0.46, w / 2, h / 2, halo_strength=1.2)
        c.convert("RGB").save(d)

    # Feature graphic 1024x500: Terran (cool, left) faces Arcadian (warm, right). No lettering.
    W, H = 2048, 1000
    fgx = radial((W, H), (20, 40, 72), BG, center=(0.5, 0.55), radius=0.62).convert("RGBA")
    for color, cx in ((CYAN, 0.18), (GOLD, 0.82)):
        g = Image.new("L", (W, H))
        ImageDraw.Draw(g).ellipse([W * cx - 520, H * 0.55 - 360, W * cx + 520, H * 0.55 + 360], fill=70)
        g = g.filter(ImageFilter.GaussianBlur(180))
        layer = Image.new("RGBA", (W, H), color + (0,))
        layer.putalpha(g)
        fgx.alpha_composite(layer)
    hud_lines(fgx, (120, 160, 210), alpha=10, step=64)
    hz = Image.new("L", (W, H))
    ImageDraw.Draw(hz).line([(0, int(H * 0.78)), (W, int(H * 0.78))], fill=90, width=3)
    hz = hz.filter(ImageFilter.GaussianBlur(3))
    hl = Image.new("RGBA", (W, H), (150, 190, 230, 0))
    hl.putalpha(hz)
    fgx.alpha_composite(hl)
    place(fgx, alien, W * 0.40, H * 0.60, W * 0.71, H * 0.50, halo=GOLD, halo_strength=1.0)
    place(fgx, tank, W * 0.50, H * 0.80, W * 0.30, H * 0.54, halo=CYAN, halo_strength=1.4)
    fgx.convert("RGB").resize((1024, 500), Image.LANCZOS).save(out_store / "feature-graphic.png")
    print("composed icons, splash screens and feature graphic")


if __name__ == "__main__":
    main()
