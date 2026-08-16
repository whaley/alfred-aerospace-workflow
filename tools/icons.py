"""Generate the workflow's PNG icons with nothing but the standard library.

Keeping icons as *code* means no binary blobs in git, reproducible builds, and
trivial restyling: change a colour constant and rebuild.

Everything is drawn on a supersampled canvas and box-filtered down, which gives
clean anti-aliased edges without an imaging library.
"""

from __future__ import annotations

import os
import struct
import zlib

SUPERSAMPLE = 4

# Palette -- AeroSpace-flavoured teal on a deep slate tile.
SLATE = (36, 42, 54, 255)
TEAL = (94, 214, 199, 255)
TEAL_DIM = (58, 138, 133, 255)
CLOUD = (232, 238, 245, 255)
AMBER = (245, 191, 102, 255)
TRANSPARENT = (0, 0, 0, 0)


class Canvas(object):
    """A supersampled RGBA canvas with rounded-rectangle fills."""

    def __init__(self, size, background=TRANSPARENT):
        self.size = size
        self.scale = SUPERSAMPLE
        self.hi = size * self.scale
        self.pixels = [background] * (self.hi * self.hi)

    def fill_round_rect(self, x, y, width, height, radius, color):
        """Fill a rounded rect given in *final* (un-supersampled) coordinates."""
        s = self.scale
        x0, y0 = x * s, y * s
        x1, y1 = (x + width) * s, (y + height) * s
        r = radius * s

        for py in range(max(0, int(y0)), min(self.hi, int(y1) + 1)):
            for px in range(max(0, int(x0)), min(self.hi, int(x1) + 1)):
                if _inside_round_rect(px + 0.5, py + 0.5, x0, y0, x1, y1, r):
                    self.pixels[py * self.hi + px] = _blend(
                        self.pixels[py * self.hi + px], color
                    )

    def downsample(self):
        """Box-filter to the final resolution, returning RGBA bytes."""
        s = self.scale
        out = bytearray()
        samples = s * s
        for y in range(self.size):
            for x in range(self.size):
                r = g = b = a = 0
                for dy in range(s):
                    row = (y * s + dy) * self.hi + x * s
                    for dx in range(s):
                        pr, pg, pb, pa = self.pixels[row + dx]
                        # Premultiply so transparent pixels don't darken edges.
                        r += pr * pa
                        g += pg * pa
                        b += pb * pa
                        a += pa
                if a:
                    out += bytes((r // a, g // a, b // a, a // samples))
                else:
                    out += b"\x00\x00\x00\x00"
        return bytes(out)

    def save(self, path):
        write_png(path, self.size, self.size, self.downsample())


def _inside_round_rect(px, py, x0, y0, x1, y1, r):
    if px < x0 or px > x1 or py < y0 or py > y1:
        return False
    if r <= 0:
        return True
    cx = min(max(px, x0 + r), x1 - r)
    cy = min(max(py, y0 + r), y1 - r)
    dx, dy = px - cx, py - cy
    return dx * dx + dy * dy <= r * r


def _blend(dst, src):
    """Source-over compositing."""
    sa = src[3]
    if sa == 255:
        return src
    if sa == 0:
        return dst
    inv = 255 - sa
    da = dst[3]
    out_a = sa + da * inv // 255
    if out_a == 0:
        return TRANSPARENT
    return (
        (src[0] * sa + dst[0] * da * inv // 255) // out_a,
        (src[1] * sa + dst[1] * da * inv // 255) // out_a,
        (src[2] * sa + dst[2] * da * inv // 255) // out_a,
        out_a,
    )


def write_png(path, width, height, rgba):
    """Write 8-bit RGBA `rgba` bytes as a PNG."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        head = struct.pack(">I", len(data)) + tag + data
        return head + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", ihdr))
        handle.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        handle.write(chunk(b"IEND", b""))


# ---------------------------------------------------------------- the icons

def _tiles(canvas, size, color_a, color_b):
    """The shared motif: one tall pane beside two stacked panes."""
    pad = size * 0.18
    gap = size * 0.055
    radius = size * 0.045
    inner = size - pad * 2
    left_w = inner * 0.46
    right_w = inner - left_w - gap
    right_h = (inner - gap) / 2

    canvas.fill_round_rect(pad, pad, left_w, inner, radius, color_a)
    canvas.fill_round_rect(pad + left_w + gap, pad, right_w, right_h, radius,
                           color_b)
    canvas.fill_round_rect(pad + left_w + gap, pad + right_h + gap, right_w,
                           right_h, radius, color_b)


def workflow_icon(size=256):
    canvas = Canvas(size)
    canvas.fill_round_rect(0, 0, size, size, size * 0.22, SLATE)
    _tiles(canvas, size, TEAL, TEAL_DIM)
    return canvas


def workspace_icon(size=128):
    canvas = Canvas(size)
    _tiles(canvas, size, CLOUD, (232, 238, 245, 140))
    return canvas


def new_icon(size=128):
    canvas = Canvas(size)
    _tiles(canvas, size, (232, 238, 245, 90), (232, 238, 245, 60))
    # A plus badge in the lower-right corner.
    bar = size * 0.075
    cx = size * 0.70
    cy = size * 0.70
    arm = size * 0.16
    canvas.fill_round_rect(cx - arm, cy - bar / 2, arm * 2, bar, bar / 2, AMBER)
    canvas.fill_round_rect(cx - bar / 2, cy - arm, bar, arm * 2, bar / 2, AMBER)
    return canvas


ICONS = {
    "icon.png": workflow_icon,
    "icons/workspace.png": workspace_icon,
    "icons/new.png": new_icon,
}


def generate_all(destination):
    """Write every icon under `destination`. Returns the paths written."""
    written = []
    for relative, factory in sorted(ICONS.items()):
        path = os.path.join(destination, relative)
        factory().save(path)
        written.append(path)
    return written


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "build/workflow"
    for created in generate_all(target):
        print("wrote {0}".format(created))
