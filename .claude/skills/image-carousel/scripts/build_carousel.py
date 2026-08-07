#!/usr/bin/env python3
"""Download images from URLs (or read local files) and assemble them into a
professional-looking numbered carousel: consistent aspect ratio, consistent
resolution, editorial typography, ready to upload as an Instagram/LinkedIn
-style multi-image post.

Design language (see SKILL.md "What good looks like" for the reasoning):
  - Cinematic bottom gradient scrim behind text, never a flat boxed rectangle.
  - A small colored eyebrow tag/pill above the headline (category, moment,
    team name...) — this one element does more for "looks professional" than
    anything else.
  - Condensed display font for headlines (impact), a separate clean font for
    body/subtitle text, optionally a script accent font for one flourish word.
  - A consistent small watermark/footer across every slide in the set.

v2.0 additions (all opt-in, all off unless requested — none of this changes
how images are found or downloaded, only how finished slides are decorated):
  - Optional profile header (photo or initials + name/handle), top-left.
  - Optional progress-bar slide indicator as an alternative to the "N/total"
    chip (--indicator-style bar).
  - Optional CTA/closing slide type ('type=cta') — a deliberate light-
    background pattern-break with an engagement question and a follow/share
    prompt, matching how real personal-brand carousels close a set.
  - Optional persistent profile config (--profile-config a.json) so repeat
    carousels for the same account don't need --footer/--accent-color/etc
    retyped every time.
  - Optional big "number=" field for numbered-list content (tips, mistakes,
    steps) — a different visual treatment than the tag pill, better suited
    to that content shape.

Source forms:
  - a plain image URL or local path
  - "text:tag=..|title=..|accent=..|subtitle=..|bg=..|number=.."  -> a
    generated text card (cover/closing/stat slides). Only 'title' required
    unless type=cta (see below).
  - "text:type=cta|title=..|accent=..|question=..|cta=.."  -> the closing
    CTA slide (see make_cta_slide).
  - --captions-file  -> JSON list (same length as sources) of null or
    {"tag":.., "title":.., "subtitle":.., "number":..} name-tag captions
    drawn over photos (for carousels about people/moments).
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RATIOS = {
    "1:1": (1, 1),
    "4:5": (4, 5),
    "16:9": (16, 9),
    "9:16": (9, 16),
}

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
HEADLINE_CANDIDATES = [FONT_DIR / "BigShoulders-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
BODY_CANDIDATES = [FONT_DIR / "Outfit-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
SCRIPT_CANDIDATES = [FONT_DIR / "NothingYouCouldDo-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
# Editorial serif for long-form "story" slides — real magazine/newsroom
# carousels (long narrative broken across many slides, not one-liners) lean
# on a serif body font for gravitas; a condensed display sans everywhere
# reads as social-media-template, not journalism.
SERIF_CANDIDATES = [FONT_DIR / "Lora-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
SERIF_BOLD_CANDIDATES = [FONT_DIR / "Lora-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]

DARK_TEXT = (16, 22, 30)


# ---------------------------------------------------------------------------
# Image sourcing
# ---------------------------------------------------------------------------

_SEEN_IMAGE_HASHES: list[tuple[int, str]] = []


def _image_hash(img: Image.Image, hash_size: int = 8) -> int:
    """Cheap perceptual hash (average hash) so the same photo is still
    caught even if it was fetched at a different size/compression — not
    meant to be exact, just good enough to flag an accidental repeat."""
    small = img.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    # get_flattened_data (Pillow 12+) replaces the deprecated getdata(); fall
    # back for older Pillow installs so this stays portable across machines.
    pixels = list(getattr(small, "get_flattened_data", small.getdata)())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits


def _warn_if_duplicate(img: Image.Image, source: str, threshold: int = 6) -> None:
    """This skill's #1 image rule is 'never reuse the same photo twice in
    one carousel' — a rule that has been broken in practice before because
    it depended entirely on remembering it across many sources in one CLI
    call. Back it with an automatic check: flag (not block, in case of a
    false positive on two genuinely similar-but-different photos) any
    photo that hashes close to one already used earlier in this run."""
    h = _image_hash(img)
    for prev_hash, prev_source in _SEEN_IMAGE_HASHES:
        distance = bin(h ^ prev_hash).count("1")
        if distance <= threshold:
            print(
                f"⚠ DUPLICATE PHOTO WARNING: '{source}' looks like the same image as "
                f"'{prev_source}' already used earlier in this carousel (hash distance {distance}/64). "
                "The rule is never reuse a photo — swap one of these out for a different image.",
                file=sys.stderr,
            )
            break
    _SEEN_IMAGE_HASHES.append((h, source))


def fetch_image(source: str, retries: int = 3) -> Image.Image:
    if source.startswith("http://") or source.startswith("https://"):
        # curl picks up the environment's proxy + CA bundle correctly in this
        # sandbox; the requests/urllib3 stack does not verify TLS through the
        # proxy tunnel here, so shell out instead.
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            last_err = None
            for attempt in range(retries):
                try:
                    subprocess.run(
                        ["curl", "-sSL", "--fail", "-A", "Mozilla/5.0", "-o", tmp_path, source],
                        check=True,
                        timeout=30,
                    )
                    img = Image.open(tmp_path).convert("RGB")
                    _warn_if_duplicate(img, source)
                    return img
                except Exception as e:
                    # A rate-limited or erroring host (e.g. Wikimedia's "robot
                    # policy" page after several requests in quick succession)
                    # often still returns HTTP 200 with an HTML body — curl
                    # --fail doesn't catch that, only opening the file as an
                    # image does. Back off and retry instead of silently
                    # saving a broken slide from a corrupt/empty photo.
                    last_err = e
                    if attempt < retries - 1:
                        time.sleep(5 * (attempt + 1))
            raise RuntimeError(f"Not a valid image after {retries} attempts: {source} ({last_err})")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    img = Image.open(source).convert("RGB")
    _warn_if_duplicate(img, source)
    return img


def crop_to_ratio(img: Image.Image, ratio: tuple[int, int]) -> Image.Image:
    """Center-crop so the image exactly matches the target aspect ratio."""
    target_aspect = ratio[0] / ratio[1]
    w, h = img.size
    current_aspect = w / h
    if current_aspect > target_aspect:
        new_w = round(h * target_aspect)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = round(w / target_aspect)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

def load_font(candidates: list, size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def apply_gradient_scrim(img: Image.Image, side: str = "bottom", height_frac: float = 0.55,
                          max_alpha: int = 235, exponent: float = 1.6) -> Image.Image:
    """Cinematic gradient (transparent -> dark) behind text, not a boxed panel.

    This is the single biggest difference between an amateur text overlay and
    a professional one: real editorial carousels never put text in a flat
    rounded rectangle, they darken a gradient region of the photo itself.

    exponent controls how quickly the gradient reaches useful opacity: the
    default 1.6 stays subtle for most of the band (nice for a plain photo),
    but on a busy/text-heavy source image (a labeled map, a screenshot, a
    crowded scene) that subtlety lets the photo's own detail bleed through
    right where a caption sits. Pass a lower exponent (e.g. 0.6-0.8) for
    those cases to reach solid coverage sooner.
    """
    img = img.convert("RGBA")
    w, h = img.size
    band_h = round(h * height_frac)
    gradient = Image.new("L", (1, band_h), color=0)
    for y in range(band_h):
        alpha = int(max_alpha * (y / band_h) ** exponent)
        gradient.putpixel((0, y), alpha)
    gradient = gradient.resize((w, band_h))
    overlay = Image.new("RGBA", (w, band_h), (0, 0, 0, 255))
    overlay.putalpha(gradient)
    full_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if side == "bottom":
        full_overlay.paste(overlay, (0, h - band_h))
    else:
        full_overlay.paste(overlay.transpose(Image.FLIP_TOP_BOTTOM), (0, 0))
    return Image.alpha_composite(img, full_overlay)


def draw_tag(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont,
             bg_color: tuple, text_color: tuple = (255, 255, 255, 255)) -> tuple[int, int]:
    """Small uppercase pill/chip (eyebrow label). Returns (width, height) drawn."""
    x, y = xy
    pad_x, pad_y = font.size // 2, font.size // 3
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.rounded_rectangle(
        [x, y, x + tw + pad_x * 2, y + th + pad_y * 2],
        radius=(th + pad_y * 2) // 2,
        fill=bg_color,
    )
    draw.text((x + pad_x - bbox[0], y + pad_y - bbox[1]), text, font=font, fill=text_color)
    return tw + pad_x * 2, th + pad_y * 2


def big_number_line_height(width: int) -> int:
    """True line height (ascent+descent) for the big-number font at this
    width. font.size alone undershoots real glyph extent — e.g. at 180px
    BigShoulders-Bold, size*1.05 gives ~189px but ascent+descent is ~217px,
    enough of a gap to visibly overlap whatever is drawn right after."""
    font = load_font(HEADLINE_CANDIDATES, width // 6)
    return sum(font.getmetrics())


def draw_big_number(draw: ImageDraw.ImageDraw, xy: tuple[int, int], number: str, width: int, accent_rgb: tuple) -> int:
    """Large accent-colored number (e.g. '1', '05') — the right treatment for
    numbered-list content (tips, mistakes, steps), where a tag pill under-
    sells the structure. Returns the height consumed (see big_number_line_height)."""
    font = load_font(HEADLINE_CANDIDATES, width // 6)
    draw.text(xy, number, font=font, fill=accent_rgb + (255,))
    return sum(font.getmetrics())


def draw_footer(img: Image.Image, text: str, dark_text: bool = False) -> Image.Image:
    """Small, consistent watermark/credit line — every professional carousel
    in a series carries the same footer, it's what makes a set read as one
    coherent piece of content instead of loose slides.

    A short handle always fits on one line at the default size, but a real
    source citation ("Fontes: X, Y, Z ...") can be too wide — shrink first,
    then wrap to two lines rather than letting it run off both edges."""
    draw = ImageDraw.Draw(img, "RGBA")
    max_width = round(img.width * 0.9)
    font_size = img.width // 34
    font = load_font(BODY_CANDIDATES, font_size)
    while font_size > img.width // 55 and draw.textlength(text, font=font) > max_width:
        font_size -= 2
        font = load_font(BODY_CANDIDATES, font_size)

    lines = [text] if draw.textlength(text, font=font) <= max_width else wrap_text(draw, text, font, max_width)
    color = DARK_TEXT + (200,) if dark_text else (255, 255, 255, 200)
    line_h = int(font_size * 1.25)
    y = img.height - line_h * len(lines) - img.height // 40
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (img.width - (bbox[2] - bbox[0])) // 2
        draw.text((x - bbox[0], y - bbox[1]), line, font=font, fill=color)
        y += line_h
    return img


def add_badge(img: Image.Image, text: str) -> Image.Image:
    """Small, understated slide-count chip, top-right — a number, not the focus."""
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    font = load_font(BODY_CANDIDATES, max(22, img.width // 26))
    pad = font.size // 3
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = img.width - tw - pad * 2 - img.width // 30
    y = img.height // 30
    draw.rounded_rectangle([x - pad, y - pad, x + tw + pad, y + th + pad], radius=pad * 2, fill=(0, 0, 0, 130))
    draw.text((x - bbox[0], y - bbox[1]), text, font=font, fill=(255, 255, 255, 230))
    return img.convert("RGB")


def draw_progress_bar(img: Image.Image, index: int, total: int, accent_rgb: tuple,
                       bottom_margin: int, dark_text: bool = False) -> Image.Image:
    """Thin filled progress bar + 'i/total' label — an alternative to the
    corner chip, closer to what native Instagram carousel indicators look
    like. Track/fill/label colors adapt to whether the slide reads as a
    light or dark background (the CTA slide is deliberately light)."""
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    margin = img.width // 20
    bar_h = max(3, img.width // 260)
    label_font = load_font(BODY_CANDIDATES, img.width // 34)
    label = f"{index + 1}/{total}"
    label_w = draw.textbbox((0, 0), label, font=label_font)[2]

    y = img.height - bottom_margin - bar_h
    track_x0, track_x1 = margin, img.width - margin - label_w - margin // 2
    track_color = (0, 0, 0, 45) if dark_text else (255, 255, 255, 60)
    fill_color = accent_rgb + (255,) if dark_text else (255, 255, 255, 255)
    label_color = DARK_TEXT + (160,) if dark_text else (255, 255, 255, 200)

    draw.rounded_rectangle([track_x0, y, track_x1, y + bar_h], radius=bar_h, fill=track_color)
    fill_w = round((track_x1 - track_x0) * (index + 1) / total)
    if fill_w > 0:
        draw.rounded_rectangle([track_x0, y, track_x0 + fill_w, y + bar_h], radius=bar_h, fill=fill_color)
    draw.text((img.width - margin - label_w, y - bar_h // 2), label, font=label_font, fill=label_color)
    return img.convert("RGB")


# ---------------------------------------------------------------------------
# Profile header (v2.0, opt-in)
# ---------------------------------------------------------------------------

def initials_from_name(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else "?"


def circular_crop(img: Image.Image, diameter: int) -> Image.Image:
    img = crop_to_ratio(img, (1, 1)).resize((diameter, diameter), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter, diameter], fill=255)
    img.putalpha(mask)
    return img


def profile_header_height(width: int) -> int:
    return width // 11 + width // 30


def draw_profile_header(img: Image.Image, profile: dict, accent_rgb: tuple, dark_text: bool = False) -> Image.Image:
    """Photo (or initials) + name + handle, top-left — brand identity on
    every slide. Purely opt-in: only called when profile info was given."""
    img = img.convert("RGBA")
    margin = img.width // 24
    diameter = img.width // 11

    photo_path = profile.get("photo")
    if photo_path and Path(photo_path).exists():
        try:
            circle = circular_crop(Image.open(photo_path).convert("RGB"), diameter)
            ring = Image.new("RGBA", (diameter + 6, diameter + 6), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse([0, 0, diameter + 6, diameter + 6], fill=accent_rgb + (255,))
            ring.paste(circle, (3, 3), circle)
            img.paste(ring, (margin, margin), ring)
            diameter += 6
        except Exception:
            photo_path = None
    if not photo_path or not Path(photo_path or "").exists():
        circle = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
        cd = ImageDraw.Draw(circle)
        cd.ellipse([0, 0, diameter, diameter], fill=accent_rgb + (255,))
        initials = initials_from_name(profile.get("name", "?"))
        ifont = load_font(HEADLINE_CANDIDATES, diameter // 2)
        ibbox = cd.textbbox((0, 0), initials, font=ifont)
        iw, ih = ibbox[2] - ibbox[0], ibbox[3] - ibbox[1]
        cd.text(((diameter - iw) / 2 - ibbox[0], (diameter - ih) / 2 - ibbox[1]), initials, font=ifont, fill=(12, 18, 26, 255))
        img.paste(circle, (margin, margin), circle)

    draw = ImageDraw.Draw(img, "RGBA")
    text_color = DARK_TEXT + (255,) if dark_text else (255, 255, 255, 255)
    sub_color = DARK_TEXT + (170,) if dark_text else (255, 255, 255, 180)
    tx = margin + diameter + margin // 2
    name_font = load_font(BODY_CANDIDATES, img.width // 32)
    handle_font = load_font(BODY_CANDIDATES, img.width // 42)
    name = profile.get("name", "").upper()
    handle = profile.get("handle", "")
    ty = margin + diameter // 2 - name_font.size - handle_font.size // 2
    if name:
        draw.text((tx, ty), name, font=name_font, fill=text_color)
        ty += int(name_font.size * 1.15)
    if handle:
        draw.text((tx, ty), handle, font=handle_font, fill=sub_color)
    return img.convert("RGB")


# ---------------------------------------------------------------------------
# Text-card slides: cover/closing/stat cards + the CTA slide
# ---------------------------------------------------------------------------

def parse_kv_spec(spec: str) -> dict:
    """Parse 'tag=A|title=B|accent=C|subtitle=D' into a dict. title required
    (except for type=cta, which has its own required fields)."""
    parts = {}
    for chunk in spec.split("|"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    if "title" not in parts and parts.get("type") != "cta":
        raise ValueError("text: card spec needs at least 'title=...'")
    return parts


def _prepare_background(fields: dict, size: tuple[int, int], ratio: tuple[int, int],
                         bg_color: str, band_colors: list[str] | None) -> Image.Image:
    if fields.get("bg"):
        img = fetch_image(fields["bg"])
        img = crop_to_ratio(img, ratio).resize(size, Image.LANCZOS).convert("RGBA")
        # Real photos/maps need a stronger uniform darken pass than flat
        # colors do — busy image detail behind text hurts legibility more
        # than a flat color ever does.
        darken = Image.new("RGBA", img.size, (0, 0, 0, 130))
        img = Image.alpha_composite(img, darken)
    else:
        img = Image.new("RGB", size, bg_color)
        if band_colors:
            d = ImageDraw.Draw(img)
            b1, b2 = size[1] // 4, size[1] // 2
            d.rectangle([0, 0, size[0], b1], fill=band_colors[0])
            d.rectangle([0, b1, size[0], b1 + b2], fill=band_colors[1])
            d.rectangle([0, b1 + b2, size[0], size[1]], fill=band_colors[2])
        img = img.convert("RGBA")
        if band_colors:
            # Flag/brand bands can land any color directly behind the text
            # (e.g. a gold accent word over a yellow stripe would vanish) —
            # a uniform darken pass first guarantees contrast everywhere.
            darken = Image.new("RGBA", img.size, (0, 0, 0, 100))
            img = Image.alpha_composite(img, darken)
    return img


def make_text_card(spec: str, size: tuple[int, int], ratio: tuple[int, int], bg_color: str,
                    band_colors: list[str] | None, accent_color: str, profile: dict | None,
                    top_offset: int) -> Image.Image:
    """Generate a cover/closing/stat card: tag pill + two-tone headline +
    subtitle, optionally led by a big number for numbered-list content.

    Prefer a real background image (fields['bg']) over a flat/banded color —
    a photo, map, chart or diagram related to the topic. Flat color is a
    fallback for when no suitable image exists, not the default: a slide
    with zero real imagery reads as a generic template, not real content.
    """
    fields = parse_kv_spec(spec)
    accent_rgb = hex_to_rgb(accent_color)

    img = _prepare_background(fields, size, ratio, bg_color, band_colors)
    img = apply_gradient_scrim(img, "bottom", height_frac=0.5, max_alpha=140)
    img = apply_gradient_scrim(img, "top", height_frac=0.28, max_alpha=90)
    draw = ImageDraw.Draw(img)
    max_width = round(size[0] * 0.82)
    margin = size[0] // 12

    y = size[1] // 8 + top_offset
    if fields.get("number"):
        y += draw_big_number(draw, (margin, y), fields["number"], size[0], accent_rgb)

    if fields.get("tag"):
        tag_font = load_font(BODY_CANDIDATES, size[0] // 26)
        _, th = draw_tag(draw, (margin, y), fields["tag"].upper(), tag_font, bg_color=accent_rgb + (255,))
        y += th + size[1] // 40

    title_font = load_font(HEADLINE_CANDIDATES, size[0] // 9)
    title_lines = wrap_text(draw, fields["title"].upper(), title_font, max_width)
    line_h = int(title_font.size * 1.02)
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += line_h

    if fields.get("accent"):
        accent_lines = wrap_text(draw, fields["accent"].upper(), title_font, max_width)
        for line in accent_lines:
            draw.text((margin, y), line, font=title_font, fill=accent_rgb + (255,))
            y += line_h

    if fields.get("subtitle"):
        y += size[1] // 28
        sub_font = load_font(BODY_CANDIDATES, size[0] // 22)
        for line in wrap_text(draw, fields["subtitle"], sub_font, max_width):
            draw.text((margin, y), line, font=sub_font, fill=(235, 235, 235, 255))
            y += int(sub_font.size * 1.25)

    if profile:
        img = draw_profile_header(img, profile, accent_rgb, dark_text=False)

    return img.convert("RGB")


def make_cta_slide(spec: str, size: tuple[int, int], accent_color: str, profile: dict | None, cta_bg: str) -> Image.Image:
    """Closing CTA slide: deliberately light/plain regardless of the rest of
    the carousel's palette — a pattern-break that signals 'this is the last
    slide, here's the ask', same principle real personal-brand carousels use.
    Only worth using when there's a real ask (follow/share); skip it for
    purely informational carousels."""
    fields = parse_kv_spec(spec)
    accent_rgb = hex_to_rgb(accent_color)

    img = Image.new("RGB", size, cta_bg).convert("RGBA")
    draw = ImageDraw.Draw(img)
    margin = size[0] // 12
    max_width = round(size[0] * 0.82)

    y = size[1] // 8 + (profile_header_height(size[0]) if profile else 0)
    if fields.get("title"):
        title_font = load_font(HEADLINE_CANDIDATES, size[0] // 10)
        for line in wrap_text(draw, fields["title"].upper(), title_font, max_width):
            draw.text((margin, y), line, font=title_font, fill=DARK_TEXT + (255,))
            y += int(title_font.size * 1.05)
    if fields.get("accent"):
        title_font = load_font(HEADLINE_CANDIDATES, size[0] // 10)
        for line in wrap_text(draw, fields["accent"].upper(), title_font, max_width):
            draw.text((margin, y), line, font=title_font, fill=accent_rgb + (255,))
            y += int(title_font.size * 1.05)

    if fields.get("question"):
        y += size[1] // 25
        q_font = load_font(BODY_CANDIDATES, size[0] // 20)
        for line in wrap_text(draw, fields["question"], q_font, max_width):
            draw.text((margin, y), line, font=q_font, fill=DARK_TEXT + (255,))
            y += int(q_font.size * 1.3)

    if fields.get("cta"):
        y += size[1] // 45
        c_font = load_font(BODY_CANDIDATES, size[0] // 24)
        for line in wrap_text(draw, fields["cta"], c_font, max_width):
            draw.text((margin, y), line, font=c_font, fill=(90, 100, 110, 255))
            y += int(c_font.size * 1.3)

    # "Share, save & follow" prompt, bottom-left — the actual ask.
    prompt = fields.get("prompt", "Compartilhe, salve e siga")
    prompt_font = load_font(HEADLINE_CANDIDATES, size[0] // 20)
    prompt_lines = wrap_text(draw, prompt.upper(), prompt_font, round(size[0] * 0.55))
    py = size[1] - margin - int(prompt_font.size * 1.05) * len(prompt_lines) - size[1] // 12
    for line in prompt_lines:
        draw.text((margin, py), line, font=prompt_font, fill=accent_rgb + (255,))
        py += int(prompt_font.size * 1.05)

    if profile:
        img = draw_profile_header(img, profile, accent_rgb, dark_text=True)
        photo_path = profile.get("photo")
        diameter = size[0] // 5
        cx, cy = size[0] - margin - diameter, size[1] - margin - diameter - size[1] // 14
        ring = Image.new("RGBA", (diameter + 8, diameter + 8), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([0, 0, diameter + 8, diameter + 8], fill=accent_rgb + (255,))
        if photo_path and Path(photo_path).exists():
            circle = circular_crop(Image.open(photo_path).convert("RGB"), diameter)
            ring.paste(circle, (4, 4), circle)
        else:
            cd = ImageDraw.Draw(ring)
            initials = initials_from_name(profile.get("name", "?"))
            ifont = load_font(HEADLINE_CANDIDATES, diameter // 2)
            ibbox = cd.textbbox((0, 0), initials, font=ifont)
            iw, ih = ibbox[2] - ibbox[0], ibbox[3] - ibbox[1]
            cd.ellipse([4, 4, diameter + 4, diameter + 4], fill=(255, 255, 255, 255))
            cd.text(((diameter + 8 - iw) / 2 - ibbox[0], (diameter + 8 - ih) / 2 - ibbox[1]), initials, font=ifont, fill=DARK_TEXT + (255,))
        img.paste(ring, (cx, cy), ring)

    return img.convert("RGB")


# ---------------------------------------------------------------------------
# Long-form "story" slide — a narrative paragraph (not a one-liner) with
# inline **highlighted** phrases, an optional inset photo, and a masthead.
# This is the format real newsroom/analysis carousel accounts use to pack
# far more information into a slide than the punchy tag+headline system
# above — reach for it when the content is a genuine multi-sentence
# explanation, not a quick hook or a name-tag.
# ---------------------------------------------------------------------------

def round_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)
    return mask


def parse_highlight_spans(text: str) -> list[tuple[str, bool]]:
    """Split '...normal **highlighted** normal...' into (word, is_accent)
    pairs, one entry per word, for word-by-word colored wrapping.

    Punctuation glued directly to a ** boundary with no space (e.g.
    "...**highlighted**, more text") gets merged onto the previous word
    instead of becoming its own token — otherwise it renders as a stray,
    visibly-spaced-out character. This shipped as a real bug twice
    ("...decadas , Pelé..." / "...votos . O prémio...") before this
    merge step was added; every draw call advances by word-width +
    space-width, so a lone "," or "." token always gets an unwanted gap
    on both sides."""
    spans = []
    parts = text.split("**")
    for i, part in enumerate(parts):
        is_accent = i % 2 == 1
        prev_part = parts[i - 1] if i > 0 else None
        # Only glue across the ** boundary itself — not any old word break —
        # so both sides must be non-empty and touch the delimiter with no
        # whitespace (e.g. "décadas**," but not "décadas **," or "word **x").
        glued = (
            bool(part) and not part[0].isspace()
            and prev_part is not None and bool(prev_part) and not prev_part[-1].isspace()
        )
        for j, word in enumerate(part.split()):
            if j == 0 and glued and spans:
                prev_word, prev_accent = spans[-1]
                spans[-1] = (prev_word + word, prev_accent)
            else:
                spans.append((word, is_accent))
    return spans


def draw_rich_paragraph(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                         font: ImageFont.FreeTypeFont, max_width: int, line_h: int,
                         base_color: tuple, accent_color: tuple) -> int:
    """Word-wrapped paragraph where **phrase** runs render in accent_color
    inline, everything else in base_color. Returns height consumed."""
    x0, y = xy
    x = x0
    space_w = draw.textlength(" ", font=font)
    for word, is_accent in parse_highlight_spans(text):
        w = draw.textlength(word, font=font)
        if x > x0 and x + w > x0 + max_width:
            x = x0
            y += line_h
        draw.text((x, y), word, font=font, fill=(accent_color if is_accent else base_color) + (255,))
        x += w + space_w
    return y + line_h - xy[1]


def draw_masthead(draw: ImageDraw.ImageDraw, size: tuple[int, int], brand: str, index: int, total: int,
                   text_color: tuple, margin: int) -> int:
    """Small top row: brand/source label left, 'i/total' counter right —
    the thin consistent header real editorial carousel series use instead
    of (or alongside) a corner badge. Returns the row height."""
    font = load_font(BODY_CANDIDATES, size[0] // 34)
    y = margin
    if brand:
        draw.text((margin, y), brand.upper(), font=font, fill=text_color + (170,))
    counter = f"{index}/{total}"
    cw = draw.textlength(counter, font=font)
    draw.text((size[0] - margin - cw, y), counter, font=font, fill=text_color + (170,))
    return int(font.size * 1.6)


def make_story_slide(spec: str, size: tuple[int, int], ratio: tuple[int, int], accent_color: str,
                      brand: str, index: int, total: int, bottom_reserve: int = 0) -> Image.Image:
    """Long-form narrative slide: masthead, optional inset photo (not full-
    bleed), a headline, and a real paragraph of body text with inline
    **highlighted** phrases. Background is a flat color (fields['bgcolor'],
    falling back to a dark neutral) — deliberately text-forward, the photo
    (if any) supports the story instead of being the whole slide.
    """
    fields = parse_kv_spec(spec)
    bg = fields.get("bgcolor", "#12181F")
    layout = fields.get("layout") or ("bleed" if fields.get("photo") and fields.get("bleed") else ("inset" if fields.get("photo") else "text"))
    accent_rgb = hex_to_rgb(accent_color)
    margin = size[0] // 14
    max_width = size[0] - margin * 2

    if layout == "bleed" and fields.get("photo"):
        try:
            photo = fetch_image(fields["photo"])
            img = crop_to_ratio(photo, ratio).resize(size, Image.LANCZOS).convert("RGBA")
        except Exception:
            img = Image.new("RGB", size, bg).convert("RGBA")
        img = apply_gradient_scrim(img, "bottom", height_frac=0.65, max_alpha=225, exponent=0.75)
        img = apply_gradient_scrim(img, "top", height_frac=0.3, max_alpha=140)
        text_color = (255, 255, 255)
    else:
        img = Image.new("RGB", size, bg).convert("RGBA")
        dark_bg = sum(hex_to_rgb(bg)) < 380
        text_color = (255, 255, 255) if dark_bg else DARK_TEXT

    draw = ImageDraw.Draw(img)
    y = margin
    y += draw_masthead(draw, size, brand, index, total, text_color, margin)
    y += size[1] // 60

    if layout == "bleed":
        y = max(y, round(size[1] * 0.46))

    if fields.get("title"):
        title_font = load_font(SERIF_BOLD_CANDIDATES, size[0] // 13)
        for line in wrap_text(draw, fields["title"], title_font, max_width):
            draw.text((margin, y), line, font=title_font, fill=text_color + (255,))
            y += int(title_font.size * 1.15)
        y += size[1] // 45

    if layout == "inset" and fields.get("photo"):
        try:
            photo = fetch_image(fields["photo"])
            photo = crop_to_ratio(photo, (16, 9)).resize((max_width, round(max_width * 9 / 16)), Image.LANCZOS)
            mask = round_rect_mask(photo.size, size[0] // 40)
            img.paste(photo, (margin, y), mask)
            y += photo.size[1] + size[1] // 40
        except Exception:
            pass

    if fields.get("body"):
        paragraphs = [p.strip() for p in fields["body"].split("\\n\\n") if p.strip()]
        para_gap = size[1] // 55
        available = size[1] - margin - bottom_reserve - y  # vertical room left before the slide edge

        def total_height(font_size: int, paras: list) -> int:
            font = load_font(SERIF_CANDIDATES, font_size)
            line_h = int(font_size * 1.45)
            scratch = ImageDraw.Draw(Image.new("RGB", (max_width + 20, 20)))
            h = 0
            for para in paras:
                h += draw_rich_paragraph(scratch, (0, 0), para, font, max_width, line_h, (0, 0, 0), (0, 0, 0))
                h += para_gap
            return h

        # Auto-shrink: long stories vs. a short quote both come through this
        # same field, so pick the largest size that actually fits rather
        # than assuming one fixed size — a fixed size either overflows past
        # the slide edge on long copy or looks tiny/timid on short copy.
        body_size = size[0] // 24
        min_size = size[0] // 42
        while body_size > min_size and total_height(body_size, paragraphs) > available:
            body_size -= 2

        while len(paragraphs) > 1 and total_height(min_size, paragraphs) > available:
            paragraphs = paragraphs[:-1]

        body_font = load_font(SERIF_CANDIDATES, body_size)
        line_h = int(body_size * 1.45)
        for para in paragraphs:
            y += draw_rich_paragraph(draw, (margin, y), para, body_font, max_width, line_h,
                                      text_color, accent_rgb)
            y += para_gap

    return img.convert("RGB")


def add_name_caption(img: Image.Image, tag: str | None, title: str, subtitle: str | None, number: str | None,
                      accent_color: str, bottom_reserve: int = 0) -> Image.Image:
    """Cinematic bottom scrim + optional big number/eyebrow tag + big name +
    subtitle, for slides built from a real photo (e.g. a person).
    bottom_reserve keeps the block clear of a footer/progress-bar drawn
    afterwards."""
    img = apply_gradient_scrim(img, "bottom", height_frac=0.5, max_alpha=230, exponent=0.7)
    draw = ImageDraw.Draw(img)
    margin = img.width // 20
    max_width = img.width - margin * 2
    rgb = hex_to_rgb(accent_color)

    title_font = load_font(HEADLINE_CANDIDATES, img.width // 9)
    sub_font = load_font(BODY_CANDIDATES, img.width // 24)
    tag_font = load_font(BODY_CANDIDATES, img.width // 28)

    title_lines = wrap_text(draw, title.upper(), title_font, max_width)
    line_h = int(title_font.size * 1.0)
    sub_line_h = int(sub_font.size * 1.25)
    subtitle_lines = wrap_text(draw, subtitle, sub_font, max_width) if subtitle else []

    block_h = line_h * len(title_lines)
    if subtitle_lines:
        block_h += sub_line_h * len(subtitle_lines) + img.height // 30
    if tag:
        block_h += tag_font.size + img.height // 60 + img.height // 60
    if number:
        block_h += big_number_line_height(img.width) + img.height // 90

    y = img.height - margin - bottom_reserve - block_h
    if number:
        y += draw_big_number(draw, (margin, y), number, img.width, rgb)
        y += img.height // 90
    if tag:
        _, th = draw_tag(draw, (margin, y), tag.upper(), tag_font, bg_color=rgb + (255,))
        y += th + img.height // 60

    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += line_h
    if subtitle_lines:
        y += img.height // 30
        for line in subtitle_lines:
            draw.text((margin, y), line, font=sub_font, fill=rgb + (255,))
            y += sub_line_h

    return img.convert("RGB")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_profile(args) -> dict | None:
    """Resolve profile fields: explicit CLI flags > --profile-config file.
    Returns None if no profile info was given at all (profile header/CTA
    photo stay off by default — this is opt-in, not automatic branding)."""
    config = {}
    if args.profile_config:
        config = json.loads(Path(args.profile_config).read_text())

    profile = {
        "name": args.profile_name or config.get("name"),
        "handle": args.profile_handle or config.get("handle"),
        "photo": args.profile_photo or config.get("photo"),
    }
    if not (profile["name"] or profile["handle"]):
        return None
    return profile


def resolve(cli_value, config: dict, key: str, default):
    if cli_value is not None:
        return cli_value
    if config.get(key) is not None:
        return config[key]
    return default


def main():
    parser = argparse.ArgumentParser(description="Build a professional numbered image carousel from URLs, local files, or text: cards")
    parser.add_argument("sources", nargs="+",
                         help="Image URLs, local file paths, 'text:title=..|tag=..|accent=..|subtitle=..|bg=..|number=..' for a generated card, "
                              "or 'text:type=cta|title=..|accent=..|question=..|cta=..' for the closing CTA slide")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ratio", default="4:5", choices=sorted(RATIOS.keys()),
                         help="Target aspect ratio (default 4:5, the standard Instagram/LinkedIn carousel format)")
    parser.add_argument("--width", type=int, default=1080, help="Output width in pixels (default 1080)")
    parser.add_argument("--no-badge", action="store_true", help="Skip the slide-count indicator entirely")
    parser.add_argument("--indicator-style", default="badge", choices=["badge", "bar"],
                         help="'badge' (default): small N/total chip, top-right. 'bar': thin progress bar + label, bottom edge.")
    parser.add_argument("--prefix", default="slide", help="Output filename prefix (default 'slide')")
    parser.add_argument("--bg-color", default=None, help="Background color for text: cards (default deep navy, or --profile-config value)")
    parser.add_argument("--accent-color", default=None, help="Accent color for tags/headline highlight/subtitles (hex, default gold, or --profile-config value)")
    parser.add_argument("--band-colors", help="3 comma-separated hex colors for a flag-style banded background on text: cards, e.g. '#AA151B,#F1BF00,#AA151B'")
    parser.add_argument("--footer", default=None, help="Small watermark/credit text repeated on every slide, e.g. '@handle · fonte: FIFA' (or --profile-config value)")
    parser.add_argument("--captions-file", help="JSON file: list (same length as sources) of null or {tag, title, subtitle, number}")
    parser.add_argument("--cta-bg", default="#F5F1E8", help="Background color for type=cta slides (default warm off-white — deliberately light regardless of carousel palette)")
    parser.add_argument("--profile-config", help="JSON file with {name, handle, photo, accent_color, footer} reused across carousels for the same account")
    parser.add_argument("--profile-name", default=None, help="Override/set profile name (enables the profile header if name or handle is set)")
    parser.add_argument("--profile-handle", default=None, help="Override/set @handle (enables the profile header if name or handle is set)")
    parser.add_argument("--profile-photo", default=None, help="Path to a square-ish profile photo; falls back to an initials circle if omitted/missing")
    parser.add_argument("--brand", default="", help="Masthead label (top-left) for type=story slides, e.g. a source/brand name. Optional.")
    args = parser.parse_args()
    band_colors = args.band_colors.split(",") if args.band_colors else None

    config = json.loads(Path(args.profile_config).read_text()) if args.profile_config else {}
    accent_color = resolve(args.accent_color, config, "accent_color", "#FFC800")
    bg_color = resolve(args.bg_color, config, "bg_color", "#0B2545")
    footer = resolve(args.footer, config, "footer", None)
    profile = load_profile(args)
    accent_rgb = hex_to_rgb(accent_color)

    ratio = RATIOS[args.ratio]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target_size = (args.width, round(args.width * ratio[1] / ratio[0]))
    top_offset = profile_header_height(target_size[0]) if profile else 0

    captions = [None] * len(args.sources)
    if args.captions_file:
        loaded = json.loads(Path(args.captions_file).read_text())
        if len(loaded) != len(args.sources):
            print("captions-file length must match number of sources", file=sys.stderr)
            sys.exit(1)
        captions = loaded

    total = len(args.sources)
    saved = []
    for i, source in enumerate(args.sources, start=1):
        is_cta = source.startswith("text:") and "type=cta" in source
        is_story = source.startswith("text:") and "type=story" in source
        try:
            if is_cta:
                img = make_cta_slide(source[len("text:"):], target_size, accent_color, profile, args.cta_bg)
            elif is_story:
                story_footer_reserve = round(target_size[1] * 0.075) if footer else 0
                img = make_story_slide(source[len("text:"):], target_size, ratio, accent_color, args.brand, i, total,
                                        bottom_reserve=story_footer_reserve)
            elif source.startswith("text:"):
                img = make_text_card(source[len("text:"):], target_size, ratio, bg_color, band_colors,
                                      accent_color, profile, top_offset)
            else:
                img = fetch_image(source)
                img = crop_to_ratio(img, ratio)
                img = img.resize(target_size, Image.LANCZOS)
                if profile:
                    # Plain photos (unlike text: cards) have no built-in top
                    # scrim — a light safety gradient keeps the header
                    # readable regardless of what's in the top of the photo.
                    img = apply_gradient_scrim(img, "top", height_frac=0.22, max_alpha=110)
                    img = draw_profile_header(img, profile, accent_rgb, dark_text=False)
        except Exception as e:
            print(f"Skipping slide {i} ({source}): {e}", file=sys.stderr)
            continue

        is_plain_photo = not is_cta and not is_story and not source.startswith("text:")
        caption = captions[i - 1]
        bar_h = round(target_size[1] * 0.045) if args.indicator_style == "bar" and not args.no_badge else 0
        footer_h = round(target_size[1] * 0.075) if footer else 0
        bottom_reserve = footer_h + bar_h
        if caption:
            img = add_name_caption(img, caption.get("tag"), caption["title"], caption.get("subtitle"),
                                    caption.get("number"), accent_color, bottom_reserve=bottom_reserve)
        elif is_plain_photo and (footer or not args.no_badge):
            # No caption means no scrim was applied yet — a light one keeps
            # the footer/indicator legible over a busy or light photo.
            img = apply_gradient_scrim(img, "bottom", height_frac=0.16, max_alpha=150)

        # Story slides carry their own masthead (brand + N/total) — a corner
        # badge on top of that would just be visual noise, but the footer
        # is still worth keeping when there's a real source to cite.
        if not is_story and not args.no_badge:
            if args.indicator_style == "bar":
                img = draw_progress_bar(img, i - 1, total, accent_rgb, bottom_margin=footer_h, dark_text=is_cta)
            else:
                img = add_badge(img, f"{i}/{total}")
        if footer:
            story_light = is_story and "layout=bleed" not in source and "bgcolor=" in source and \
                sum(hex_to_rgb(source.split("bgcolor=", 1)[1].split("|", 1)[0])) >= 380
            img = draw_footer(img, footer, dark_text=is_cta or story_light)

        out_path = out_dir / f"{args.prefix}-{i:02d}.jpg"
        img.convert("RGB").save(out_path, "JPEG", quality=92)
        saved.append(str(out_path))
        print(f"Saved {out_path}")

    if not saved:
        print("No slides were saved — all sources failed.", file=sys.stderr)
        sys.exit(1)

    print(f"\n{len(saved)}/{total} slides saved to {out_dir}")


if __name__ == "__main__":
    main()
