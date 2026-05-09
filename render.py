"""PayPal motion graphics — white minimalist edition.

Apple/Stripe-flavored: white backgrounds, soft shadows, the iconic
PayPal double-P mark, minimal typography, generous whitespace, subtle
blue accents only.
"""
from __future__ import annotations

import math
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 30
OUT_DIR = Path("frames")

# Palette — soft, clean, premium
BG_LIGHT_INNER = (255, 255, 255)
BG_LIGHT_OUTER = (236, 241, 248)
TEXT_DARK = (12, 26, 64)
TEXT_MID = (90, 105, 140)
PP_DARK = (0, 48, 135)     # back P
PP_LIGHT = (0, 156, 222)   # front P
ACCENT = (0, 156, 222)
SOFT_BLUE = (210, 226, 245)
HAIR_BLUE = (190, 210, 232)

FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

random.seed(1)
np.random.seed(1)


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rgb(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


# ---------- backgrounds ----------

def make_white_bg(w=W, h=H, inner=BG_LIGHT_INNER, outer=BG_LIGHT_OUTER,
                  cx_frac=0.5, cy_frac=0.5) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * cx_frac, h * cy_frac
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    d /= d.max()
    d = d ** 1.4
    r = inner[0] * (1 - d) + outer[0] * d
    g = inner[1] * (1 - d) + outer[1] * d
    b = inner[2] * (1 - d) + outer[2] * d
    arr = np.stack([r, g, b], axis=-1).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr).convert("RGBA")


def add_dot_pattern(img: Image.Image, spacing: int = 60, color=(180, 200, 230),
                    alpha: int = 60, offset_x: int = 0, offset_y: int = 0):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    r = 1.2
    for x in range(-spacing + offset_x % spacing, img.width, spacing):
        for y in range(-spacing + offset_y % spacing, img.height, spacing):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color + (alpha,))
    img.alpha_composite(overlay)


# ---------- soft shadow ----------

def soft_shadow(layer: Image.Image, blur: int = 18, offset=(0, 8),
                color=(0, 30, 90), opacity: float = 0.18) -> Image.Image:
    """Return a shadow Image the same size as layer (bleed via expanded canvas)."""
    pad = blur * 4
    canvas = Image.new("RGBA",
                       (layer.width + pad * 2, layer.height + pad * 2),
                       (0, 0, 0, 0))
    # alpha-only silhouette
    if layer.mode != "RGBA":
        layer = layer.convert("RGBA")
    a = layer.split()[3]
    sil = Image.new("RGBA", layer.size, color + (0,))
    sil.putalpha(a)
    arr = np.array(sil).astype(np.float32)
    arr[..., 3] *= opacity
    sil = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    canvas.alpha_composite(sil, (pad + offset[0], pad + offset[1]))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    return canvas, pad


# ---------- the PayPal P mark ----------

def make_p_glyph(height: int, color, italic: float = 0.18) -> Image.Image:
    """Build a stylized italicized 'p' glyph with bowl + descender.
    Supersampled 2x for clean edges."""
    SS = 2
    h = height * SS
    pad = int(h * 0.35)
    w = int(h * 1.1) + pad
    img_w = w + pad
    img_h = h + pad
    mask = Image.new("L", (img_w, img_h), 0)
    md = ImageDraw.Draw(mask)

    ox, oy = pad, pad

    # bowl
    bowl_d = int(h * 0.78)
    bowl_x = ox
    bowl_y = oy
    md.ellipse([bowl_x, bowl_y, bowl_x + bowl_d, bowl_y + bowl_d], fill=255)

    # stem
    stem_w = int(h * 0.26)
    stem_x = ox + int(bowl_d * 0.04)
    stem_top = oy + int(bowl_d * 0.42)
    stem_bot = oy + h
    md.rounded_rectangle([stem_x, stem_top, stem_x + stem_w, stem_bot],
                         radius=stem_w // 2, fill=255)

    # counter (hole)
    hole_d = int(bowl_d * 0.40)
    hole_x = bowl_x + int(bowl_d * 0.30)
    hole_y = bowl_y + int((bowl_d - hole_d) / 2)
    md.ellipse([hole_x, hole_y, hole_x + hole_d, hole_y + hole_d], fill=0)

    if italic:
        from PIL import Image as PIM
        mask = mask.transform(mask.size, PIM.AFFINE,
                              (1, -italic, italic * h, 0, 1, 0),
                              resample=PIM.BICUBIC)

    # downsample for AA
    target_size = (mask.size[0] // SS, mask.size[1] // SS)
    mask = mask.resize(target_size, Image.LANCZOS)

    solid = Image.new("RGBA", mask.size, color + (255,))
    solid.putalpha(mask)
    return solid


def draw_paypal_mark(target: Image.Image, cx: int, cy: int, height: int,
                     alpha: float = 1.0, soft: bool = True):
    """The two-tone double-P mark. Back P dark, front P cyan, slightly offset."""
    if alpha <= 0.01:
        return

    # back P
    backP = make_p_glyph(height, PP_DARK)
    # front P (offset right, slightly smaller-tone)
    frontP = make_p_glyph(height, PP_LIGHT)

    # apply alpha
    if alpha < 1.0:
        for im in (backP, frontP):
            arr = np.array(im).astype(np.float32)
            arr[..., 3] *= alpha
            im.paste(Image.fromarray(arr.clip(0, 255).astype(np.uint8)))

    # composite mark = back at (cx-offset, cy), front at (cx+offset, cy)
    offset = int(height * 0.18)

    # soft drop shadow under the whole mark
    combo = Image.new("RGBA",
                      (backP.width + offset * 2, backP.height + 30),
                      (0, 0, 0, 0))
    combo.alpha_composite(backP, (0, 15))
    combo.alpha_composite(frontP, (offset * 2, 15))

    if soft:
        shadow, pad = soft_shadow(combo, blur=22, offset=(0, 14),
                                  color=(0, 40, 100), opacity=0.18 * alpha)
        target.alpha_composite(shadow,
                               (cx - combo.width // 2 - pad,
                                cy - combo.height // 2 - pad))
    target.alpha_composite(combo,
                           (cx - combo.width // 2,
                            cy - combo.height // 2))


# ---------- typography ----------

def draw_text_centered(img: Image.Image, text: str, y: int, size: int, color,
                       alpha: int = 255, letter_spacing: int = 0,
                       weight_bold: bool = True):
    f = font(size, bold=weight_bold)
    letters = list(text)
    widths = [f.getlength(c) for c in letters]
    total = sum(widths) + letter_spacing * max(0, len(letters) - 1)
    x = (img.width - total) / 2

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = x
    for c, w in zip(letters, widths):
        d.text((cx, y), c, font=f, fill=color + (alpha,))
        cx += w + letter_spacing
    img.alpha_composite(layer)


def draw_text_left(img: Image.Image, text: str, x: int, y: int, size: int,
                   color, alpha: int = 255, weight_bold: bool = True):
    f = font(size, bold=weight_bold)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((x, y), text, font=f, fill=color + (alpha,))
    img.alpha_composite(layer)


def draw_text_with_reveal(img, text: str, y: int, size: int, color,
                          progress: float, letter_spacing: int = 0,
                          bold: bool = True):
    """Reveal text left-to-right with subtle fade on each letter."""
    f = font(size, bold=bold)
    letters = list(text)
    widths = [f.getlength(c) for c in letters]
    total = sum(widths) + letter_spacing * max(0, len(letters) - 1)
    x = (img.width - total) / 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = x
    n = len(letters)
    for i, (c, w) in enumerate(zip(letters, widths)):
        # each letter reveals over a small window
        per = 1.0 / max(1, n)
        local_t = clamp((progress - i * per * 0.5) / max(per, 0.06))
        a = int(255 * ease_out(local_t))
        dy = int(8 * (1 - ease_out(local_t)))
        d.text((cx, y + dy), c, font=f, fill=color + (a,))
        cx += w + letter_spacing
    img.alpha_composite(layer)


# ---------- particles (faint) ----------

class SoftParticles:
    def __init__(self, n=80, w=W, h=H, seed=2):
        rng = np.random.default_rng(seed)
        self.x = rng.uniform(0, w, n)
        self.y = rng.uniform(0, h, n)
        self.vx = rng.uniform(-6, 6, n)
        self.vy = rng.uniform(-3, 3, n)
        self.r = rng.uniform(1.2, 3.0, n)
        self.bright = rng.uniform(0.3, 0.8, n)
        self.phase = rng.uniform(0, math.tau, n)
        self.w, self.h = w, h

    def render(self, t: float, img: Image.Image, color=ACCENT, alpha_scale=1.0):
        x = (self.x + self.vx * t) % self.w
        y = (self.y + self.vy * t) % self.h
        twinkle = 0.5 + 0.5 * np.sin(self.phase + t * 1.2)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for xi, yi, ri, bi, tw in zip(x, y, self.r, self.bright, twinkle):
            a = int(120 * bi * tw * alpha_scale)
            if a <= 4:
                continue
            d.ellipse([xi - ri, yi - ri, xi + ri, yi + ri], fill=color + (a,))
        layer = layer.filter(ImageFilter.GaussianBlur(0.8))
        img.alpha_composite(layer)


# ---------- scene utilities ----------

def fade(img: Image.Image, t: float, dur: float, fin: float = 0.5, fout: float = 0.7,
         to_white: bool = True):
    """Apply fade in/out by mixing toward white (clean cinema crossfade)."""
    if t < fin:
        f = 1 - clamp(t / fin)
        arr = np.array(img).astype(np.float32)
        if to_white:
            arr[..., :3] = arr[..., :3] * (1 - f) + 255 * f
        else:
            arr[..., :3] *= (1 - f)
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if t > dur - fout:
        f = clamp((t - (dur - fout)) / fout)
        arr = np.array(img).astype(np.float32)
        if to_white:
            arr[..., :3] = arr[..., :3] * (1 - f) + 255 * f
        else:
            arr[..., :3] *= (1 - f)
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    return img


# ---------- scene 1: intro ----------

def scene_intro(t: float, dur: float) -> Image.Image:
    img = make_white_bg()
    SoftParticles  # silence
    P = scene_intro.particles  # type: ignore[attr-defined]
    P.render(t, img, color=SOFT_BLUE, alpha_scale=1.0)

    # Mark scales in
    progress = clamp(t / 1.6)
    e = ease_out(progress)
    mark_h = int(lerp(120, 380, e))
    bob = math.sin(t * 1.3) * 3
    draw_paypal_mark(img, W // 2, H // 2 - 90 + int(bob), mark_h, alpha=e)

    # Tagline reveal
    if t > 1.6:
        rev = clamp((t - 1.6) / 1.8)
        draw_text_with_reveal(img, "Pagamentos rápidos. Seguros. Globais.",
                              H // 2 + 200, 52, TEXT_DARK, rev,
                              letter_spacing=2, bold=True)

    # tiny accent line
    if t > 2.6:
        u = clamp((t - 2.6) / 0.5)
        ulen = int(160 * u)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        y = H // 2 + 320
        d.rectangle([W // 2 - ulen // 2, y, W // 2 + ulen // 2, y + 4],
                    fill=ACCENT + (220,))
        img.alpha_composite(layer)

    return fade(img, t, dur, fin=0.4, fout=0.7)


scene_intro.particles = SoftParticles(n=80)  # type: ignore[attr-defined]


# ---------- scene 2: platform ----------

def make_phone(t: float, alpha: float = 1.0) -> Image.Image:
    pw, ph = 380, 760
    pad = 30
    canvas = Image.new("RGBA", (pw + pad * 2, ph + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    # white phone body with thin border
    d.rounded_rectangle([pad, pad, pad + pw, pad + ph], radius=44,
                        fill=(255, 255, 255, 255),
                        outline=(220, 230, 244, 255), width=2)
    # screen area
    sx, sy = pad + 14, pad + 14
    sw, sh = pw - 28, ph - 28
    # screen bg subtle gradient
    grad_h = sh
    grad = np.zeros((grad_h, sw, 3), dtype=np.uint8)
    for i in range(grad_h):
        f = i / max(1, grad_h - 1)
        c = lerp_rgb((250, 252, 255), (240, 246, 253), f)
        grad[i, :, :] = c
    screen = Image.fromarray(grad).convert("RGBA")
    sd = ImageDraw.Draw(screen)
    # status bar
    sd.text((18, 14), "9:41", font=font(18, True), fill=TEXT_DARK + (255,))
    sd.text((sw - 80, 14), "PayPal", font=font(18, True), fill=PP_LIGHT + (255,))
    # title
    sd.text((22, 64), "Saldo disponível", font=font(20, False),
            fill=TEXT_MID + (255,))
    sd.text((22, 92), "$ 12,480.50", font=font(40, True),
            fill=TEXT_DARK + (255,))
    # transactions
    rows = [
        ("Spotify",            "−$ 9,99",   (60, 200, 130)),
        ("Apple",              "−$ 99,00",  (90, 130, 220)),
        ("Recebido • João",    "+$ 250,00", (60, 200, 130)),
        ("Amazon",             "−$ 38,40",  (240, 160, 60)),
        ("Uber",               "−$ 14,20",  (90, 100, 130)),
    ]
    appear_at = [0.5, 1.0, 1.5, 2.0, 2.5]
    for i, ((name, val, dot), at) in enumerate(zip(rows, appear_at)):
        a_local = clamp((t - at) / 0.45)
        if a_local <= 0:
            continue
        ae = ease_out(a_local)
        ox = int(lerp(60, 0, ae))
        ya = 180 + i * 64
        a = int(255 * ae * alpha)
        sd.rounded_rectangle([14 + ox, ya, sw - 14 + ox, ya + 54],
                             radius=14, fill=(245, 248, 253, a),
                             outline=(225, 232, 244, a), width=1)
        sd.ellipse([26 + ox, ya + 18, 44 + ox, ya + 36], fill=dot + (a,))
        sd.text((58 + ox, ya + 14), name, font=font(20, True),
                fill=TEXT_DARK + (a,))
        col = (60, 170, 110) if val.startswith("+") else TEXT_DARK
        sd.text((sw - 130 + ox, ya + 14), val, font=font(20, True),
                fill=col + (a,))
    # CTA pill
    cta_a = clamp((t - 3.0) / 0.5)
    if cta_a > 0:
        a = int(255 * cta_a * alpha)
        sd.rounded_rectangle([22, ph - 86, sw - 22, ph - 30], radius=22,
                             fill=PP_LIGHT + (a,))
        cta = "Pagar agora"
        f = font(22, True)
        cw = f.getlength(cta)
        sd.text(((sw - cw) / 2, ph - 76), cta, font=f, fill=(255, 255, 255, a))

    # mask screen rounded
    sm = Image.new("L", screen.size, 0)
    ImageDraw.Draw(sm).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=30, fill=255)
    screen.putalpha(sm)
    canvas.alpha_composite(screen, (sx, sy))
    return canvas


def draw_card(img: Image.Image, x: int, y: int, w: int, h: int, angle: float,
              gradient_a, gradient_b, alpha: float = 1.0):
    grad = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(h):
        f = i / max(1, h - 1)
        c = lerp_rgb(gradient_a, gradient_b, f)
        grad[i, :, :] = c
    card = Image.fromarray(grad).convert("RGBA")
    # rounded mask with alpha
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=255)
    if alpha < 1.0:
        m_arr = (np.array(mask).astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)
        mask = Image.fromarray(m_arr)
    card.putalpha(mask)
    # chip + label
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([26, h - 86, 90, h - 50], radius=6,
                         fill=(255, 215, 90, int(240 * alpha)))
    cd.text((26, 24), "PayPal", font=font(22, True),
            fill=(255, 255, 255, int(240 * alpha)))
    cd.text((26, h - 38), "**** **** **** 0824", font=font(28, True),
            fill=(255, 255, 255, int(220 * alpha)))
    # rotate (with shadow)
    rot = card.rotate(angle, resample=Image.BICUBIC, expand=True)
    sh, pad = soft_shadow(rot, blur=24, offset=(0, 14),
                          color=(0, 30, 90), opacity=0.18 * alpha)
    img.alpha_composite(sh, (int(x - rot.width / 2) - pad,
                              int(y - rot.height / 2) - pad))
    img.alpha_composite(rot, (int(x - rot.width / 2),
                                int(y - rot.height / 2)))


def scene_platform(t: float, dur: float) -> Image.Image:
    img = make_white_bg()
    add_dot_pattern(img, spacing=80, color=(195, 215, 240), alpha=70)

    # caption top
    a = int(255 * clamp((t - 0.4) / 0.6))
    if a > 0:
        draw_text_centered(img, "Tudo em um só lugar", 110, 44, TEXT_DARK,
                           alpha=a, letter_spacing=2)

    # phone slides up from below
    phone = make_phone(t, alpha=1.0)
    e = ease_out(clamp((t - 0.2) / 1.2))
    py = int(lerp(H + 200, H // 2 + 30, e))
    px = W // 2 + 380
    img.alpha_composite(phone, (px - phone.width // 2, py - phone.height // 2))

    # cards float in from left
    e2 = ease_out(clamp((t - 0.6) / 1.4))
    base_x = int(lerp(-200, 540, e2))
    base_y = H // 2 + 30
    for i, (c1, c2, ang_off, dy) in enumerate([
        ((0, 90, 200), (0, 156, 222), -8, -90),
        ((0, 48, 135), (0, 100, 200), 4, 30),
    ]):
        ang = ang_off + math.sin(t * 1.0 + i) * 1.5
        dyy = dy + math.sin(t * 1.2 + i * 1.2) * 5
        draw_card(img, base_x + i * 18, base_y + int(dyy), 460, 280, ang,
                  c1, c2, alpha=clamp(e2 - i * 0.05))

    # connection dots from cards to phone
    if t > 1.6:
        flow_a = clamp((t - 1.6) / 0.6)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x0, y0 = base_x + 230, base_y - 30
        x1, y1 = px - 200, py
        for k in range(5):
            phase = (t * 1.1 + k * 0.2) % 1.0
            xx = lerp(x0, x1, phase)
            yy = lerp(y0, y1, phase) + math.sin(phase * math.pi) * -100
            r = 5 + 3 * math.sin(t * 4 + k)
            d.ellipse([xx - r, yy - r, xx + r, yy + r],
                      fill=ACCENT + (int(220 * flow_a),))
        glow = layer.filter(ImageFilter.GaussianBlur(8))
        img.alpha_composite(glow)
        img.alpha_composite(layer)

    return fade(img, t, dur, fin=0.5, fout=0.7)


# ---------- scene 3: security ----------

def scene_security(t: float, dur: float) -> Image.Image:
    img = make_white_bg()
    add_dot_pattern(img, spacing=70, color=(195, 215, 240), alpha=60,
                    offset_x=int(t * 12), offset_y=int(-t * 8))

    cx, cy = W // 2, H // 2 + 30

    # shield outline (single, elegant)
    e = ease_out(clamp(t / 1.4))
    sw, sh = 380, 460
    pts = [
        (cx, cy - sh // 2),
        (cx + sw // 2, cy - sh // 2 + 60),
        (cx + sw // 2 - 30, cy + sh // 2 - 90),
        (cx, cy + sh // 2),
        (cx - sw // 2 + 30, cy + sh // 2 - 90),
        (cx - sw // 2, cy - sh // 2 + 60),
    ]
    # scale pts toward center for entry
    spts = [(cx + (px - cx) * e, cy + (py - cy) * e) for (px, py) in pts]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # subtle gradient fill via two-pass
    d.polygon(spts, fill=(232, 242, 252, int(255 * e)))
    d.polygon(spts, outline=PP_LIGHT + (int(255 * e),), width=4)

    # padlock inside
    if e > 0.4:
        la = clamp((e - 0.4) / 0.6)
        lk_w = max(40, int(120 * la))
        lk_h = max(60, int(150 * la))
        lkx = cx - lk_w // 2
        lky = cy - lk_h // 2 + 6
        # body
        body_top = lky + min(50, lk_h - 20)
        d.rounded_rectangle([lkx, body_top, lkx + lk_w, lky + lk_h],
                            radius=min(18, (lk_h - 50) // 2),
                            fill=PP_DARK + (int(230 * la),))
        # shackle
        d.arc([lkx + 18, lky - 10, lkx + lk_w - 18, lky + 90],
              start=180, end=360, fill=PP_DARK + (int(230 * la),), width=12)
        # keyhole
        kh_d = 16
        d.ellipse([cx - kh_d // 2, lky + 75, cx + kh_d // 2, lky + 75 + kh_d],
                  fill=(255, 255, 255, int(255 * la)))
        d.rectangle([cx - 4, lky + 88, cx + 4, lky + 110],
                    fill=(255, 255, 255, int(255 * la)))

    img.alpha_composite(layer)

    # rotating perimeter dashes
    perim_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(perim_layer)
    rad = 290
    n = 60
    for k in range(n):
        ang = (k / n) * math.tau + t * 0.5
        ang2 = ((k + 0.5) / n) * math.tau + t * 0.5
        if (k + int(t * 8)) % 3 == 0:
            continue
        x1 = cx + math.cos(ang) * rad
        y1 = cy + math.sin(ang) * rad
        x2 = cx + math.cos(ang2) * rad
        y2 = cy + math.sin(ang2) * rad
        pd.line([(x1, y1), (x2, y2)], fill=PP_LIGHT + (int(180 * e),), width=3)
    img.alpha_composite(perim_layer)

    # caption
    if t > 0.8:
        a = int(255 * clamp((t - 0.8) / 0.7))
        draw_text_centered(img, "Proteção avançada para cada transação.",
                           H - 160, 44, TEXT_DARK, alpha=a, letter_spacing=2)

    # auth check pulse on right
    if t > 3.5:
        cha = clamp((t - 3.5) / 0.6)
        pulse = 1.0 + 0.10 * math.sin(t * 6)
        cl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(cl)
        gx, gy = cx + 360, cy - 120
        r = int(54 * pulse)
        cd.ellipse([gx - r, gy - r, gx + r, gy + r],
                   fill=(60, 200, 130, int(230 * cha)))
        cd.line([(gx - 22, gy + 2), (gx - 6, gy + 18), (gx + 22, gy - 14)],
                fill=(255, 255, 255, 255), width=8)
        glow = cl.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(glow)
        img.alpha_composite(cl)

    return fade(img, t, dur, fin=0.5, fout=0.7)


# ---------- scene 4: global ----------

def scene_global(t: float, dur: float) -> Image.Image:
    img = make_white_bg()
    add_dot_pattern(img, spacing=80, color=(200, 218, 240), alpha=50)

    cx, cy = W // 2, H // 2 + 30
    R = 320
    e = ease_out(clamp(t / 1.4))
    rot = t * 0.35

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # latitude rings
    for k in range(-4, 5):
        lat = k / 4 * (math.pi / 2 * 0.85)
        rr = R * math.cos(lat) * e
        ry = abs(rr) * 0.32
        yc = cy + math.sin(lat) * R * e
        if rr < 4:
            continue
        d.ellipse([cx - rr, yc - ry, cx + rr, yc + ry],
                  outline=PP_LIGHT + (110,), width=1)

    # longitude
    for k in range(0, 12):
        ang = k / 12 * math.pi + rot
        pts = []
        for s in range(0, 121):
            theta = s / 120 * math.tau
            x = R * math.sin(theta) * math.cos(ang)
            y = R * math.cos(theta)
            z = R * math.sin(theta) * math.sin(ang)
            depth = (z + R) / (2 * R)
            xs = cx + x * e
            ys = cy + y * e * 0.95
            pts.append((xs, ys, depth))
        for i in range(len(pts) - 1):
            x1, y1, dp1 = pts[i]
            x2, y2, dp2 = pts[i + 1]
            a = int(140 * ((dp1 + dp2) / 2) ** 1.4)
            d.line([(x1, y1), (x2, y2)], fill=PP_LIGHT + (a,), width=1)
    img.alpha_composite(layer)

    # nodes & arcs (clean blue)
    rng = random.Random(11)
    nodes = []
    for _ in range(12):
        lat = rng.uniform(-1.0, 1.0)
        lon = rng.uniform(0, math.tau)
        nodes.append((lat, lon))

    pt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pt_layer)
    proj_pts = []
    for lat, lon in nodes:
        ang = lon + rot
        x = R * math.cos(lat) * math.sin(ang)
        y = -R * math.sin(lat)
        z = R * math.cos(lat) * math.cos(ang)
        if z < -10:
            continue
        depth = (z + R) / (2 * R)
        xs = cx + x * e
        ys = cy + y * e * 0.95
        rr = 4 + 4 * depth
        pd.ellipse([xs - rr, ys - rr, xs + rr, ys + rr],
                   fill=PP_LIGHT + (int(255 * (0.4 + 0.6 * depth)),))
        proj_pts.append((xs, ys, depth))

    arc_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ad = ImageDraw.Draw(arc_layer)
    pairs = [(0, 5), (1, 8), (2, 9), (3, 11), (6, 4), (10, 7)]
    for i, j in pairs:
        if i >= len(proj_pts) or j >= len(proj_pts):
            continue
        x1, y1, _ = proj_pts[i]
        x2, y2, _ = proj_pts[j]
        prev = None
        steps = 32
        for s in range(steps + 1):
            tt = s / steps
            xx = lerp(x1, x2, tt)
            yy = lerp(y1, y2, tt) - 110 * math.sin(tt * math.pi)
            if prev is not None:
                ad.line([prev, (xx, yy)], fill=PP_DARK + (160,), width=2)
            prev = (xx, yy)
        # moving packet
        phase = (t * 0.5 + (i + j) * 0.17) % 1.0
        xx = lerp(x1, x2, phase)
        yy = lerp(y1, y2, phase) - 110 * math.sin(phase * math.pi)
        ad.ellipse([xx - 6, yy - 6, xx + 6, yy + 6],
                   fill=PP_LIGHT + (255,))

    img.alpha_composite(arc_layer)
    img.alpha_composite(pt_layer)

    # caption
    if t > 0.5:
        a = int(255 * clamp((t - 0.5) / 0.7))
        draw_text_centered(img, "Conectando você ao mundo todo.", 110,
                           44, TEXT_DARK, alpha=a, letter_spacing=2)

    # currency labels
    if t > 1.3:
        a = int(255 * clamp((t - 1.3) / 0.7))
        cl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cd2 = ImageDraw.Draw(cl)
        f = font(34, True)
        labels = [("$", 240, H - 220), ("€", W - 270, 260), ("¥", 260, 260),
                  ("£", W - 240, H - 230), ("R$", W // 2 + 520, H - 150)]
        for txt, xx, yy in labels:
            cd2.text((xx, yy), txt, font=f, fill=PP_LIGHT + (a,))
        img.alpha_composite(cl)

    return fade(img, t, dur, fin=0.5, fout=0.7)


# ---------- scene 5: outro ----------

def scene_outro(t: float, dur: float) -> Image.Image:
    img = make_white_bg()
    P = scene_outro.particles  # type: ignore[attr-defined]
    P.render(t, img, color=SOFT_BLUE, alpha_scale=1.0)

    e = ease_out(clamp(t / 1.4))
    mark_h = int(lerp(280, 360, e))
    bob = math.sin(t * 1.2) * 2
    draw_paypal_mark(img, W // 2, H // 2 - 80 + int(bob), mark_h, alpha=e)

    # accent line
    if t > 1.0:
        u = clamp((t - 1.0) / 0.5)
        ulen = int(220 * u)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        y = H // 2 + 200
        d.rectangle([W // 2 - ulen // 2, y, W // 2 + ulen // 2, y + 4],
                    fill=ACCENT + (220,))
        img.alpha_composite(layer)

    # slogan reveal
    if t > 1.4:
        rev = clamp((t - 1.4) / 1.6)
        draw_text_with_reveal(img, "O futuro dos pagamentos começa agora.",
                              H // 2 + 250, 50, TEXT_DARK, rev,
                              letter_spacing=3)

    # subtle "paypal.com" footer
    if t > 3.0:
        a = int(180 * clamp((t - 3.0) / 0.7))
        draw_text_centered(img, "paypal.com", H - 90, 24, TEXT_MID,
                           alpha=a, letter_spacing=3, weight_bold=False)

    return fade(img, t, dur, fin=0.4, fout=1.5)


scene_outro.particles = SoftParticles(n=80, seed=9)  # type: ignore[attr-defined]


SCENES = [
    ("intro",    scene_intro,    8.0),
    ("platform", scene_platform, 8.0),
    ("security", scene_security, 8.0),
    ("global",   scene_global,   8.0),
    ("outro",    scene_outro,    8.0),
]


def render_all():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    frame_idx = 0
    total = sum(int(d * FPS) for _, _, d in SCENES)
    print(f"Rendering {total} frames")
    for name, fn, dur in SCENES:
        nf = int(dur * FPS)
        for i in range(nf):
            t = i / FPS
            im = fn(t, dur)
            im.convert("RGB").save(OUT_DIR / f"f{frame_idx:05d}.jpg",
                                   quality=92, optimize=False)
            frame_idx += 1
    print("Done.")


if __name__ == "__main__":
    render_all()
