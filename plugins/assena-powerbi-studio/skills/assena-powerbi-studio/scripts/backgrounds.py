"""
ASSENA Power BI Studio - fondos generativos para la portada (PNG, solo stdlib).

Compone a partir de la paleta: degradado diagonal del color de encabezado,
dos resplandores (acento y acento secundario), anillos concentricos finos y
una vineta lateral que asegura la legibilidad del texto. Con dithering para
evitar bandas en el degradado.
"""
from __future__ import annotations

import math
import random
import struct
import zlib


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def _mix(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def _png(w, h, rows) -> bytes:
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def cover_light_png(accent: str, w: int = 1600, h: int = 900, seed: int = 7) -> bytes:
    """Portada clara: fondo blanco con un velo azul muy suave y ondas
    concentricas finas del color de acento (marca)."""
    rnd = random.Random(seed)
    white = [1.0, 1.0, 1.0]
    acc = _rgb(accent)
    tint = _mix(white, acc, 0.05)
    cx, cy = 0.86 * w, 0.56 * h
    r0, step, nr = 0.07 * w, 0.042 * w, 12
    rows = []
    for y in range(h):
        row = bytearray()
        fy = y / h
        for x in range(w):
            fx = x / w
            # velo: blanco puro a la izquierda, tinte azul muy leve a la derecha
            t = max(0.0, min(1.0, (fx - 0.35) / 0.65)) * (0.6 + 0.4 * fy)
            c = _mix(white, tint, t)
            d = math.hypot(x - cx, y - cy)
            glow = 0.07 * math.exp(-(d / (0.30 * w)) ** 2 * 2.0)
            if glow > 0.002:
                c = _mix(c, acc, glow)
            k = round((d - r0) / step)
            if 0 <= k < nr:
                dist = abs(d - (r0 + k * step))
                if dist < 1.6:
                    # ondas mas marcadas cerca del centro, se desvanecen hacia afuera
                    a = 0.34 * (1 - dist / 1.6) * (1 - k / (nr + 1)) ** 1.2
                    # desvanecer hacia la zona del texto (izquierda)
                    a *= max(0.0, min(1.0, (fx - 0.40) / 0.25))
                    c = _mix(c, acc, a)
            n = (rnd.random() - 0.5) / 255.0 * 1.2
            row.extend(max(0, min(255, int((ch + n) * 255 + 0.5))) for ch in c)
        rows.append(row)
    return _png(w, h, rows)


def cover_png(pal: dict, w: int = 1600, h: int = 900, style: str = "aurora", seed: int = 7,
              accent: str | None = None) -> bytes:
    rnd = random.Random(seed)
    base = _rgb(pal["header"])
    deep = _mix(base, [0, 0, 0], 0.45)
    lift = _mix(base, [1, 1, 1], 0.06)
    acc = _rgb(accent or pal["accent"])
    ring_col = _mix(acc, [1, 1, 1], 0.35)
    dot = 0.028 * w
    acc2 = _rgb(pal.get("accent2") or pal["dataColors"][1])
    g1 = (0.80 * w, 0.20 * h, 0.55 * w, 0.48)   # x, y, radio, intensidad
    g2 = (0.08 * w, 1.05 * h, 0.50 * w, 0.40)
    g3 = (0.55 * w, -0.15 * h, 0.35 * w, 0.18)
    rings_c = (0.86 * w, 0.58 * h)
    r0, step, nr = 0.11 * w, 0.045 * w, 9
    ring_a = 0.22
    rows = []
    for y in range(h):
        row = bytearray()
        fy = y / h
        for x in range(w):
            fx = x / w
            t = min(max((fx * 0.55 + fy * 0.45), 0.0), 1.0)
            c = _mix(lift, deep, t)
            for gx, gy, gr, gi in (g1, g2, g3):
                d = math.hypot(x - gx, y - gy) / gr
                k = gi * math.exp(-d * d * 2.2)
                if k > 0.002:
                    col = acc if (gx, gy) != (g2[0], g2[1]) else acc2
                    c = [c[i] + (col[i] - c[i]) * k for i in range(3)]
            if style in ("aurora", "rings"):
                d = math.hypot(x - rings_c[0], y - rings_c[1])
                kk = round((d - r0) / step)
                if 0 <= kk < nr:
                    dist = abs(d - (r0 + kk * step))
                    if dist < 1.5:
                        a = ring_a * (1 - dist / 1.5) * (1 - kk / (nr + 1)) ** 1.3
                        c = _mix(c, ring_col, a)
            # haz de luz diagonal muy sutil
            beam = abs((fx - 0.58) - (fy - 0.0) * 0.55)
            if beam < 0.10:
                c = _mix(c, [1, 1, 1], 0.035 * (1 - beam / 0.10) ** 2)
            # textura de puntos (esquina inferior izquierda)
            if fx < 0.34 and fy > 0.70:
                gx_, gy_ = x % dot - dot / 2, y % dot - dot / 2
                dd = math.hypot(gx_, gy_)
                if dd < 1.6:
                    fade = (1 - fx / 0.34) * ((fy - 0.70) / 0.30)
                    c = _mix(c, [1, 1, 1], 0.10 * fade * (1 - dd / 1.6))
            # vineta izquierda para legibilidad del titulo
            v = max(0.0, 0.42 - fx) / 0.42
            if v:
                c = _mix(c, deep, 0.35 * v * v)
            n = (rnd.random() - 0.5) / 255.0 * 1.6
            row.extend(max(0, min(255, int((ch + n) * 255 + 0.5))) for ch in c)
        rows.append(row)
    return _png(w, h, rows)


def page_png(P: dict, accent: str, header_frac: float = 68 / 720, w: int = 1600, h: int = 900, seed: int = 11) -> bytes:
    """Fondo de pagina de contenido: banda superior con degradado (color de
    encabezado -> azul de marca), resplandor y ondas a la derecha, linea de
    acento inferior; cuerpo con el fondo de la paleta y un leve degradado."""
    rnd = random.Random(seed)
    hb = int(round(h * header_frac))
    head = _rgb(P["header"])
    acc = _rgb(accent)
    head_end = _mix(head, acc, 0.42)
    body = _rgb(P["background"])
    dark = P.get("mode") == "dark"
    body_top = _mix(body, [1, 1, 1] if not dark else acc, 0.0 if not dark else 0.05)
    body_bot = _mix(body, [0, 0, 0] if not dark else [0, 0, 0], 0.025 if not dark else 0.18)
    ring_col = _mix(acc, [1, 1, 1], 0.45)
    cx, cy = 0.80 * w, hb * 0.5
    r0, step, nr = 0.03 * w, 0.03 * w, 10
    line_h = max(3, int(h * 0.004))
    rows = []
    for y in range(h):
        row = bytearray()
        fy = y / h
        for x in range(w):
            fx = x / w
            if y < hb:
                t = fx ** 1.3
                c = _mix(head, head_end, t)
                d = math.hypot(x - cx, (y - cy) * 1.0)
                g = 0.30 * math.exp(-(d / (0.22 * w)) ** 2 * 2.0)
                c = _mix(c, acc, g)
                k = round((d - r0) / step)
                if 0 <= k < nr:
                    dist = abs(d - (r0 + k * step))
                    if dist < 1.4:
                        c = _mix(c, ring_col, 0.20 * (1 - dist / 1.4) * (1 - k / (nr + 1)))
                # brillo superior sutil
                c = _mix(c, [1, 1, 1], 0.05 * (1 - y / hb))
            elif y < hb + line_h:
                c = _mix(acc, _mix(acc, [1, 1, 1], 0.45), fx)  # linea de acento
            else:
                t = (y - hb) / (h - hb)
                c = _mix(body_top, body_bot, t)
            n = (rnd.random() - 0.5) / 255.0 * 1.4
            row.extend(max(0, min(255, int((ch + n) * 255 + 0.5))) for ch in c)
        rows.append(row)
    return _png(w, h, rows)


if __name__ == "__main__":  # vista previa: python backgrounds.py <paleta> salida.png
    import sys
    from themes import get_palette
    p = get_palette(sys.argv[1] if len(sys.argv) > 1 else "corporativo")
    open(sys.argv[2] if len(sys.argv) > 2 else "cover.png", "wb").write(cover_png(p))
