"""PayPal motion graphics video renderer.

Generates a 1920x1080 30fps MP4 (~40s) procedurally with PIL + numpy,
encoded by ffmpeg. Five scenes, PayPal palette, neon/glow accents.
"""
from __future__ import annotations

import math
import os
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 30
OUT_DIR = Path("frames")
AUDIO_OUT = Path("audio.wav")
VIDEO_OUT = Path("paypal.mp4")

PP_BLUE = (0, 48, 135)
PP_BLUE_LT = (0, 156, 222)
PP_CYAN = (0, 180, 230)
PP_NAVY = (3, 20, 64)
NEON = (90, 200, 255)
WHITE = (255, 255, 255)
BLACK = (5, 8, 18)

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


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_rgb(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


# ---------- background helpers ----------

def make_radial_bg(w: int, h: int, inner, outer, cx_frac=0.5, cy_frac=0.5) -> Image.Image:
    """Premium dark radial gradient base."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * cx_frac, h * cy_frac
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    d /= d.max()
    d = d ** 1.2
    r = inner[0] * (1 - d) + outer[0] * d
    g = inner[1] * (1 - d) + outer[1] * d
    b = inner[2] * (1 - d) + outer[2] * d
    arr = np.stack([r, g, b], axis=-1).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def add_grid(img: Image.Image, spacing: int = 80, color=(20, 50, 100), alpha: int = 40, offset: int = 0):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(-spacing + offset % spacing, img.width, spacing):
        d.line([(x, 0), (x, img.height)], fill=color + (alpha,), width=1)
    for y in range(-spacing + offset % spacing, img.height, spacing):
        d.line([(0, y), (img.width, y)], fill=color + (alpha,), width=1)
    img.paste(overlay, (0, 0), overlay)


def add_vignette(img: Image.Image, strength: float = 0.55):
    yy, xx = np.mgrid[0:img.height, 0:img.width].astype(np.float32)
    cx, cy = img.width / 2, img.height / 2
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    d /= d.max()
    mask = (1 - (d ** 2) * strength).clip(0, 1)
    arr = np.array(img).astype(np.float32)
    arr[..., :3] *= mask[..., None]
    img.paste(Image.fromarray(arr.clip(0, 255).astype(np.uint8)))


def glow_layer(img: Image.Image, radius: int = 20, intensity: float = 0.7) -> Image.Image:
    """Return a glow halo of the bright pixels of `img`."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius))
    if intensity != 1.0:
        arr = np.array(blurred).astype(np.float32)
        arr[..., :3] *= intensity
        blurred = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    return blurred


def composite_screen(base: Image.Image, top: Image.Image) -> Image.Image:
    """Screen blend (additive-ish) for glow."""
    a = np.array(base).astype(np.float32) / 255.0
    b = np.array(top).astype(np.float32) / 255.0
    if b.shape[2] == 4:
        alpha = b[..., 3:4]
        b = b[..., :3]
        a_rgb = a[..., :3]
        out = 1 - (1 - a_rgb) * (1 - b * alpha)
        a[..., :3] = out
    else:
        a[..., :3] = 1 - (1 - a[..., :3]) * (1 - b)
    return Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))


# ---------- text helpers ----------

def draw_text_centered(img: Image.Image, text: str, y: int, size: int, color, alpha: int = 255,
                       letter_spacing: int = 0, glow: bool = True, glow_color=NEON):
    f = font(size, bold=True)
    # letter-spacing
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

    if glow and alpha > 30:
        # glow
        glow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_img)
        cx = x
        for c, w in zip(letters, widths):
            gd.text((cx, y), c, font=f, fill=glow_color + (alpha,))
            cx += w + letter_spacing
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(8))
        img.alpha_composite(glow_img)
    img.alpha_composite(layer)


# ---------- particle field ----------

class Particles:
    def __init__(self, n=140, w=W, h=H, seed=2):
        rng = np.random.default_rng(seed)
        self.x = rng.uniform(0, w, n)
        self.y = rng.uniform(0, h, n)
        self.vx = rng.uniform(-12, 12, n)
        self.vy = rng.uniform(-8, 8, n)
        self.r = rng.uniform(1.0, 3.5, n)
        self.bright = rng.uniform(0.4, 1.0, n)
        self.phase = rng.uniform(0, math.tau, n)
        self.w, self.h = w, h

    def render(self, t: float, img: Image.Image, color=NEON, alpha_scale=1.0):
        # update positions (drift)
        x = (self.x + self.vx * t) % self.w
        y = (self.y + self.vy * t) % self.h
        twinkle = 0.6 + 0.4 * np.sin(self.phase + t * 2.0)

        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for xi, yi, ri, bi, tw in zip(x, y, self.r, self.bright, twinkle):
            a = int(255 * bi * tw * alpha_scale)
            if a <= 4:
                continue
            d.ellipse([xi - ri, yi - ri, xi + ri, yi + ri], fill=color + (a,))
        layer = layer.filter(ImageFilter.GaussianBlur(1.2))
        img.alpha_composite(layer)


# ---------- PayPal logo (stylized) ----------

def draw_paypal_logo(target: Image.Image, cx: int, cy: int, scale: float = 1.0,
                     alpha: float = 1.0, glow_radius: int = 22):
    """Stylized 'PayPal' wordmark — cinema-friendly typography (not a trademark replica).
    Uses two-tone PayPal blues with subtle shadow + glow."""
    if alpha <= 0.01:
        return
    h = int(160 * scale)
    f = font(h, bold=True)
    # measure
    pay = "Pay"
    pal = "Pal"
    w_pay = f.getlength(pay)
    w_pal = f.getlength(pal)
    total = w_pay + w_pal
    x0 = cx - total / 2

    layer = Image.new("RGBA", target.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    # subtle shadow underneath
    sh = Image.new("RGBA", target.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((x0 + 4, cy - h * 0.55 + 4), pay + pal, font=f, fill=(0, 0, 0, int(160 * alpha)))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    target.alpha_composite(sh)

    d.text((x0, cy - h * 0.55), pay, font=f, fill=(0, 70, 160) + (a,))
    d.text((x0 + w_pay, cy - h * 0.55), pal, font=f, fill=(0, 156, 222) + (a,))

    # glow
    glow = layer.filter(ImageFilter.GaussianBlur(glow_radius))
    arr = np.array(glow).astype(np.float32)
    arr[..., :3] *= 0.7
    glow = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    target.alpha_composite(glow)
    target.alpha_composite(layer)


# ---------- scenes ----------

def scene_intro(t: float, dur: float) -> Image.Image:
    """0-8s: dark + particles, logo emerges, tagline."""
    img = make_radial_bg(W, H, (12, 22, 50), (2, 4, 14)).convert("RGBA")
    add_grid(img, spacing=120, color=(20, 60, 130), alpha=22)
    P = scene_intro.particles  # type: ignore[attr-defined]
    P.render(t, img, color=NEON, alpha_scale=0.9)

    # logo entrance
    progress = clamp(t / 2.5)
    e = ease_out(progress)
    scale = lerp(0.6, 1.0, e)
    alpha = e
    # slight float
    bob = math.sin(t * 1.5) * 4
    draw_paypal_logo(img, W // 2, H // 2 - 40 + int(bob), scale=scale, alpha=alpha)

    # underline accent
    if progress > 0.7:
        u = clamp((progress - 0.7) / 0.3)
        ulen = int(700 * u)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        y = H // 2 + 70
        d.line([(W // 2 - ulen // 2, y), (W // 2 + ulen // 2, y)],
               fill=PP_CYAN + (220,), width=4)
        layer = composite_screen(img, glow_layer(layer, 12, 0.8))
        img = layer

    # tagline
    if t > 2.8:
        tt = clamp((t - 2.8) / 1.2)
        a = int(255 * ease_out(tt))
        draw_text_centered(img, "Pagamentos rápidos. Seguros. Globais.", H // 2 + 160,
                           54, WHITE, alpha=a, letter_spacing=2, glow_color=PP_CYAN)

    # outro fade for handoff
    if t > dur - 0.8:
        f = clamp((t - (dur - 0.8)) / 0.8)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    add_vignette(img, 0.5)
    return img


scene_intro.particles = Particles(n=180)  # type: ignore[attr-defined]


def draw_card(img: Image.Image, x: int, y: int, w: int, h: int, angle: float,
              color1, color2, alpha: float = 1.0, label: str = "PAYPAL"):
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    # gradient body
    grad = np.zeros((h, w, 4), dtype=np.uint8)
    for i in range(h):
        t = i / max(1, h - 1)
        c = lerp_rgb(color1, color2, t)
        grad[i, :, :3] = c
        grad[i, :, 3] = int(235 * alpha)
    card = Image.fromarray(grad)
    cd = ImageDraw.Draw(card)
    # rounded corners mask
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=255)
    card.putalpha(mask)
    # chip
    cd.rounded_rectangle([26, h - 86, 90, h - 50], radius=6,
                         fill=(255, 215, 90, int(240 * alpha)))
    # label
    f = font(22, bold=True)
    cd.text((26, 24), label, font=f, fill=(255, 255, 255, int(240 * alpha)))
    # number
    f2 = font(28, bold=True)
    cd.text((26, h - 38), "**** **** **** 0824", font=f2,
            fill=(255, 255, 255, int(220 * alpha)))
    # rotate
    rotated = card.rotate(angle, resample=Image.BICUBIC, expand=True)
    rx, ry = rotated.size
    img.alpha_composite(rotated, (int(x - rx / 2), int(y - ry / 2)))


def scene_platform(t: float, dur: float) -> Image.Image:
    """8-16s: cards, phone UI, fast transactions, world icons."""
    img = make_radial_bg(W, H, (8, 24, 60), (2, 4, 14)).convert("RGBA")
    add_grid(img, spacing=100, color=(30, 80, 160), alpha=28, offset=int(t * 30))

    # left: stacked cards floating
    fade_in = clamp(t / 1.0)
    e = ease_out(fade_in)
    base_x = int(lerp(-200, 540, e))
    base_y = H // 2
    for i, (c1, c2, ang_off, dy) in enumerate([
        ((0, 60, 150), (0, 130, 210), -8, -90),
        ((0, 30, 100), (0, 90, 180), 4, 30),
        ((10, 10, 30), (40, 40, 70), 12, 150),
    ]):
        ang = ang_off + math.sin(t * 1.2 + i) * 2.5
        dyy = dy + math.sin(t * 1.4 + i * 1.2) * 6
        draw_card(img, base_x + i * 18, base_y + int(dyy), 460, 280, ang, c1, c2,
                  alpha=clamp(fade_in - i * 0.05))

    # right: phone frame
    px = int(lerp(W + 200, 1380, e))
    py = H // 2
    pw, ph = 360, 720
    phone = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
    pd = ImageDraw.Draw(phone)
    pd.rounded_rectangle([20, 20, pw + 20, ph + 20], radius=44, fill=(15, 18, 30, 255))
    pd.rounded_rectangle([34, 34, pw + 6, ph + 6], radius=36,
                         outline=(70, 120, 200, 255), width=2)
    # screen
    screen = Image.new("RGBA", (pw - 28, ph - 28), (5, 12, 30, 255))
    sd = ImageDraw.Draw(screen)
    # status bar
    sd.text((16, 12), "9:41", font=font(20, True), fill=(220, 230, 255, 255))
    sd.text((screen.width - 70, 12), "PayPal", font=font(20, True), fill=PP_CYAN + (255,))
    # balance
    sd.text((22, 60), "Saldo", font=font(22, False), fill=(180, 200, 230, 255))
    sd.text((22, 92), "$ 12,480.50", font=font(40, True), fill=WHITE + (255,))
    # transaction list — animate sliding in
    rows = [
        ("Spotify",      "-$ 9.99",  (140, 200, 90)),
        ("Apple",        "-$ 99.00", (120, 180, 240)),
        ("Recebido • João", "+$ 250.00", (90, 230, 180)),
        ("Amazon",       "-$ 38.40", (255, 170, 90)),
        ("Uber",         "-$ 14.20", (240, 240, 240)),
    ]
    appear_at = [1.5, 2.0, 2.5, 3.0, 3.5]
    for i, ((name, val, dot), at) in enumerate(zip(rows, appear_at)):
        a = clamp((t - at) / 0.5)
        if a <= 0:
            continue
        ae = ease_out(a)
        ox = int(lerp(80, 0, ae))
        ya = 180 + i * 64
        alpha_v = int(255 * ae)
        sd.rounded_rectangle([14 + ox, ya, screen.width - 14 + ox, ya + 54],
                             radius=12, fill=(20, 32, 60, alpha_v))
        sd.ellipse([26 + ox, ya + 18, 44 + ox, ya + 36], fill=dot + (alpha_v,))
        sd.text((58 + ox, ya + 14), name, font=font(20, True), fill=(220, 230, 255, alpha_v))
        col = (90, 230, 180) if val.startswith("+") else (210, 220, 240)
        sd.text((screen.width - 130 + ox, ya + 14), val, font=font(20, True),
                fill=col + (alpha_v,))
    # CTA button
    if t > 4.0:
        a = clamp((t - 4.0) / 0.6)
        pulse = 0.85 + 0.15 * math.sin(t * 4)
        col = tuple(int(c * pulse) for c in PP_BLUE_LT)
        sd.rounded_rectangle([22, ph - 96, screen.width - 22, ph - 46], radius=14,
                             fill=col + (int(240 * a),))
        sd.text((screen.width // 2 - 60, ph - 86), "Pagar agora",
                font=font(22, True), fill=WHITE + (int(255 * a),))

    # mask screen to rounded corners
    sm = Image.new("L", screen.size, 0)
    ImageDraw.Draw(sm).rounded_rectangle([0, 0, screen.width - 1, screen.height - 1],
                                         radius=30, fill=255)
    screen.putalpha(sm)
    phone.alpha_composite(screen, (34, 34))
    img.alpha_composite(phone, (px - phone.width // 2, py - phone.height // 2))

    # connector lines / data flow between cards and phone
    if t > 1.2:
        flow_a = clamp((t - 1.2) / 0.8)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        # bezier-ish — sample points
        x0, y0 = base_x + 230, base_y - 30
        x1, y1 = px - 200, py
        for k in range(6):
            phase = (t * 1.2 + k * 0.18) % 1.0
            xx = lerp(x0, x1, phase)
            yy = lerp(y0, y1, phase) + math.sin(phase * math.pi) * -120
            r = 6 + 4 * math.sin(t * 5 + k)
            d.ellipse([xx - r, yy - r, xx + r, yy + r],
                      fill=NEON + (int(220 * flow_a),))
        layer = layer.filter(ImageFilter.GaussianBlur(2))
        glow = layer.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(glow)
        img.alpha_composite(layer)

    # caption
    if t > 0.8:
        a = int(255 * clamp((t - 0.8) / 0.6))
        draw_text_centered(img, "Tudo em um só lugar", 80, 44, WHITE, alpha=a,
                           letter_spacing=2, glow_color=PP_CYAN)

    # in/out fade
    if t < 0.4:
        f = 1 - clamp(t / 0.4)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if t > dur - 0.6:
        f = clamp((t - (dur - 0.6)) / 0.6)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))

    add_vignette(img, 0.55)
    return img


def scene_security(t: float, dur: float) -> Image.Image:
    """16-24s: shield, locks, encryption, authentication."""
    img = make_radial_bg(W, H, (5, 16, 50), (1, 2, 10)).convert("RGBA")
    add_grid(img, spacing=80, color=(40, 90, 180), alpha=24, offset=int(-t * 20))

    # rotating shield
    cx, cy = W // 2, H // 2 + 20
    shield_w, shield_h = 520, 620

    e = ease_out(clamp(t / 1.4))
    sc = lerp(0.6, 1.0, e)
    sh_img = Image.new("RGBA", (shield_w, shield_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh_img)
    pts = [
        (shield_w // 2, 0),
        (shield_w - 20, 100),
        (shield_w - 60, shield_h - 200),
        (shield_w // 2, shield_h - 10),
        (60, shield_h - 200),
        (20, 100),
    ]
    # outline + fill
    sd.polygon(pts, fill=(0, 60, 140, int(180 * e)))
    # inner gradient via concentric polygons
    for k, scale in enumerate([0.92, 0.84, 0.76, 0.66]):
        ipts = [(shield_w // 2 + (x - shield_w // 2) * scale,
                 (shield_h * 0.45) + (y - shield_h * 0.45) * scale) for x, y in pts]
        col = lerp_rgb(PP_CYAN, PP_BLUE, k / 3)
        sd.polygon(ipts, fill=col + (int(220 * e),))
    sd.polygon(pts, outline=NEON + (int(255 * e),), width=4)

    # padlock inside
    lk_w, lk_h = 160, 200
    lkx = (shield_w - lk_w) // 2
    lky = int(shield_h * 0.36)
    sd.rounded_rectangle([lkx, lky + 70, lkx + lk_w, lky + lk_h], radius=22,
                         fill=(255, 255, 255, int(240 * e)))
    sd.arc([lkx + 24, lky, lkx + lk_w - 24, lky + 130], start=180, end=360,
           fill=(255, 255, 255, int(240 * e)), width=14)
    # keyhole
    sd.ellipse([lkx + lk_w // 2 - 14, lky + 110, lkx + lk_w // 2 + 14, lky + 138],
               fill=PP_BLUE + (255,))
    sd.rectangle([lkx + lk_w // 2 - 6, lky + 130, lkx + lk_w // 2 + 6, lky + 168],
                 fill=PP_BLUE + (255,))

    sh_img = sh_img.resize((int(shield_w * sc), int(shield_h * sc)),
                           Image.BICUBIC)
    glow = sh_img.filter(ImageFilter.GaussianBlur(28))
    arr = np.array(glow).astype(np.float32)
    arr[..., :3] *= 0.55
    glow = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    img.alpha_composite(glow, (cx - sh_img.width // 2, cy - sh_img.height // 2))
    img.alpha_composite(sh_img, (cx - sh_img.width // 2, cy - sh_img.height // 2))

    # orbiting binary / hex digits
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(22, True)
    rng = random.Random(7)
    chars = "01ABCDEF"
    for k in range(36):
        ang = (t * 0.5 + k / 36 * math.tau)
        rad = 380 + (k % 3) * 26
        xx = cx + math.cos(ang) * rad
        yy = cy + math.sin(ang) * rad * 0.55
        ch = rng.choice(chars)
        a = int(180 + 60 * math.sin(t * 2 + k))
        d.text((xx, yy), ch, font=f, fill=NEON + (a,))
    layer = layer.filter(ImageFilter.GaussianBlur(0.6))
    img.alpha_composite(layer)

    # scanning line
    if t > 2.0:
        sa = clamp((t - 2.0) / 0.4)
        sline = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd2 = ImageDraw.Draw(sline)
        ly = int(cy - 240 + ((t * 280) % 480))
        for w_off, alpha in [(40, 60), (20, 120), (4, 220)]:
            sd2.rectangle([cx - 240, ly - w_off, cx + 240, ly + w_off],
                          fill=NEON + (int(alpha * sa),))
        sline = sline.filter(ImageFilter.GaussianBlur(6))
        img.alpha_composite(sline)

    # caption
    if t > 1.6:
        a = int(255 * clamp((t - 1.6) / 0.8))
        draw_text_centered(img, "Proteção avançada para cada transação.",
                           H - 160, 50, WHITE, alpha=a, letter_spacing=2,
                           glow_color=PP_CYAN)

    # check mark pulse (auth ok)
    if t > 4.5:
        cha = clamp((t - 4.5) / 0.6)
        pulse = 1.0 + 0.15 * math.sin(t * 6)
        cl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(cl)
        gx, gy = cx + 480, cy - 160
        r = int(70 * pulse)
        cd.ellipse([gx - r, gy - r, gx + r, gy + r],
                   fill=(80, 220, 150, int(220 * cha)))
        cd.line([(gx - 30, gy + 4), (gx - 8, gy + 24), (gx + 30, gy - 18)],
                fill=WHITE + (255,), width=10)
        glow = cl.filter(ImageFilter.GaussianBlur(20))
        img.alpha_composite(glow)
        img.alpha_composite(cl)

    if t < 0.4:
        f = 1 - clamp(t / 0.4)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if t > dur - 0.6:
        f = clamp((t - (dur - 0.6)) / 0.6)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    add_vignette(img, 0.55)
    return img


def scene_global(t: float, dur: float) -> Image.Image:
    """24-32s: digital globe with neon connections."""
    img = make_radial_bg(W, H, (4, 14, 44), (1, 2, 10)).convert("RGBA")

    cx, cy = W // 2, H // 2 + 20
    R = 360
    e = ease_out(clamp(t / 1.4))
    rot = t * 0.35

    # build 'globe' as latitude/longitude wireframe
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # latitude rings (ellipses)
    for k in range(-4, 5):
        lat = k / 4 * (math.pi / 2 * 0.85)
        rr = R * math.cos(lat) * e
        ry = abs(rr) * 0.35  # squashed for 3D feel
        yc = cy + math.sin(lat) * R * e
        if rr < 4:
            continue
        d.ellipse([cx - rr, yc - ry, cx + rr, yc + ry],
                  outline=(0, 130, 220, 110), width=1)

    # longitude lines (rotated ellipses)
    for k in range(0, 12):
        ang = k / 12 * math.pi + rot
        # parametric: sample many points
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
            a = int(160 * ((dp1 + dp2) / 2) ** 1.4)
            d.line([(x1, y1), (x2, y2)], fill=(0, 156, 222, a), width=1)

    layer_glow = layer.filter(ImageFilter.GaussianBlur(8))
    arr = np.array(layer_glow).astype(np.float32)
    arr[..., :3] *= 0.6
    layer_glow = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    img.alpha_composite(layer_glow)
    img.alpha_composite(layer)

    # nodes + arcs
    rng = random.Random(11)
    nodes = []
    for _ in range(14):
        lat = rng.uniform(-1.1, 1.1)
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
        if z < -10:  # back of globe — dim
            continue
        depth = (z + R) / (2 * R)
        xs = cx + x * e
        ys = cy + y * e * 0.95
        rr = 4 + 4 * depth
        a = int(255 * (0.4 + 0.6 * depth))
        pd.ellipse([xs - rr, ys - rr, xs + rr, ys + rr],
                   fill=NEON + (a,))
        proj_pts.append((xs, ys, depth))

    # arcs between nodes (animated)
    arc_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ad = ImageDraw.Draw(arc_layer)
    pairs = [(0, 5), (1, 8), (2, 9), (3, 11), (6, 12), (4, 7), (10, 13)]
    for i, j in pairs:
        if i >= len(proj_pts) or j >= len(proj_pts):
            continue
        x1, y1, _ = proj_pts[i]
        x2, y2, _ = proj_pts[j]
        # bezier with arch
        steps = 32
        prev = None
        for s in range(steps + 1):
            tt = s / steps
            xx = lerp(x1, x2, tt)
            yy = lerp(y1, y2, tt) - 130 * math.sin(tt * math.pi)
            if prev is not None:
                ad.line([prev, (xx, yy)], fill=(120, 220, 255, 160), width=2)
            prev = (xx, yy)
        # moving packet
        phase = (t * 0.6 + (i + j) * 0.17) % 1.0
        xx = lerp(x1, x2, phase)
        yy = lerp(y1, y2, phase) - 130 * math.sin(phase * math.pi)
        ad.ellipse([xx - 6, yy - 6, xx + 6, yy + 6],
                   fill=(255, 255, 255, 240))

    arc_glow = arc_layer.filter(ImageFilter.GaussianBlur(10))
    arr = np.array(arc_glow).astype(np.float32)
    arr[..., :3] *= 0.6
    arc_glow = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    img.alpha_composite(arc_glow)
    img.alpha_composite(arc_layer)
    img.alpha_composite(pt_layer)

    # caption
    if t > 0.6:
        a = int(255 * clamp((t - 0.6) / 0.8))
        draw_text_centered(img, "Conectando você ao mundo todo.", 100,
                           48, WHITE, alpha=a, letter_spacing=2, glow_color=PP_CYAN)

    # currency labels around
    if t > 1.4:
        a = int(255 * clamp((t - 1.4) / 0.8))
        cl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cd2 = ImageDraw.Draw(cl)
        f = font(36, True)
        labels = [("$", 200, H - 220), ("€", W - 230, 240), ("¥", 220, 260),
                  ("£", W - 220, H - 230), ("R$", W // 2 + 520, H - 140)]
        for txt, xx, yy in labels:
            cd2.text((xx, yy), txt, font=f, fill=NEON + (a,))
        cl_glow = cl.filter(ImageFilter.GaussianBlur(10))
        img.alpha_composite(cl_glow)
        img.alpha_composite(cl)

    if t < 0.4:
        f = 1 - clamp(t / 0.4)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if t > dur - 0.6:
        f = clamp((t - (dur - 0.6)) / 0.6)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    add_vignette(img, 0.55)
    return img


def scene_outro(t: float, dur: float) -> Image.Image:
    """32-40s: final logo + slogan."""
    img = make_radial_bg(W, H, (10, 26, 70), (1, 2, 10)).convert("RGBA")
    add_grid(img, spacing=140, color=(30, 80, 160), alpha=22)
    P = scene_outro.particles  # type: ignore[attr-defined]
    P.render(t, img, color=NEON, alpha_scale=0.9)

    # logo zoom-in subtle
    e = ease_out(clamp(t / 1.4))
    scale = lerp(0.85, 1.05, e)
    bob = math.sin(t * 1.2) * 3
    draw_paypal_logo(img, W // 2, H // 2 - 60 + int(bob), scale=scale, alpha=e)

    # accent line
    if t > 1.2:
        u = clamp((t - 1.2) / 0.5)
        ulen = int(820 * u)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.line([(W // 2 - ulen // 2, H // 2 + 50),
                (W // 2 + ulen // 2, H // 2 + 50)],
               fill=PP_CYAN + (220,), width=4)
        glow = layer.filter(ImageFilter.GaussianBlur(10))
        img.alpha_composite(glow)
        img.alpha_composite(layer)

    # slogan
    if t > 1.8:
        a = int(255 * clamp((t - 1.8) / 1.0))
        draw_text_centered(img, "O futuro dos pagamentos começa agora.",
                           H // 2 + 130, 56, WHITE, alpha=a, letter_spacing=3,
                           glow_color=PP_CYAN)

    # closing fade out
    if t > dur - 1.5:
        f = clamp((t - (dur - 1.5)) / 1.5)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f * 0.95)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if t < 0.4:
        f = 1 - clamp(t / 0.4)
        arr = np.array(img).astype(np.float32)
        arr[..., :3] *= (1 - f)
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    add_vignette(img, 0.5)
    return img


scene_outro.particles = Particles(n=200, seed=9)  # type: ignore[attr-defined]


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
    total_dur = sum(d for _, _, d in SCENES)
    total_frames = int(total_dur * FPS)
    print(f"Rendering {total_frames} frames @ {FPS}fps for {total_dur:.1f}s")

    for name, fn, dur in SCENES:
        nf = int(dur * FPS)
        for i in range(nf):
            t = i / FPS
            im = fn(t, dur)
            im.convert("RGB").save(OUT_DIR / f"f{frame_idx:05d}.jpg",
                                   quality=92, optimize=False)
            frame_idx += 1
            if frame_idx % 30 == 0:
                pct = frame_idx / total_frames * 100
                print(f"  {frame_idx}/{total_frames}  ({pct:.0f}%)  scene={name}")
    print(f"Done. {frame_idx} frames.")


if __name__ == "__main__":
    render_all()
