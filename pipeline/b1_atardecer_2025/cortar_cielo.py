# -*- coding: utf-8 -*-
"""Corta la franja lisa y clara ("cielo"/resplandor) que la IA deja sobre la silueta en las escenas que en 2025 NO tenían cielo.
Por columna: desde el borde superior, baja hasta el primer píxel con textura real (desvío local alto) y corta lo de arriba.
Uso: python cortar_cielo.py DIR_ENTRADA DIR_SALIDA"""
import glob, os, sys
import numpy as np
from PIL import Image, ImageFilter

SIN_CIELO = {"B1.01", "B1.02", "B1.03", "B1.04", "B1.05", "B1.07", "B1.09"}


def box(a, r):
    k = 2 * r + 1
    c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0)), mode="edge"), 0); a = (c[k:] - c[:-k]) / k
    c = np.cumsum(np.pad(a, ((0, 0), (r + 1, r)), mode="edge"), 1); return (c[:, k:] - c[:, :-k]) / k


def cortar(im):
    """Oscurece en forma suave lo liso y claro (cielo/resplandor) en una franja angosta bajo la silueta. Sin escalones."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    g = a.mean(-1)
    h, w = g.shape
    hay = g > 8
    top = np.where(hay.any(0), hay.argmax(0), h).astype(np.float32)
    # borde superior suavizado (para medir la profundidad dentro de la franja sin saltos)
    k = 31
    pad = np.pad(top, (k // 2, k // 2), mode="edge")
    tops = np.array([np.median(pad[i:i + k]) for i in range(w)])
    D = 0.15 * h
    rows = np.arange(h, dtype=np.float32)[:, None]
    prof = rows - np.minimum(top, tops)[None, :]
    peso = np.clip((D - prof) / (0.25 * D), 0, 1) * (prof >= 0)      # parejo en la franja, se apaga solo al final
    m1 = box(g, 3); m2 = box(g * g, 3)
    sd = np.sqrt(np.maximum(m2 - m1 * m1, 0))
    banda = (prof >= 0) & (prof < D)
    r_, g_, b_ = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(-1); mn = a.min(-1); sat = (mx - mn) / np.maximum(mx, 1)
    # cielo IA: rosado/lila (con azul) o durazno claro y desaturado; tierra, roca y follaje al sol: naranjas saturados
    color_cielo = ((b_ > 0.52 * r_) & (g > 95)) | ((sat < 0.42) & (mx > 140))
    cand = banda & color_cielo & ((sd < 12) | (prof < 6))
    # cielo = candidatos CONECTADOS con el borde superior (reconstrucción geodésica): rocas/claros rodeados de contenido no se tocan
    semilla = (prof >= 0) & (prof < 6)                                 # todo el borde superior siembra (ahí los píxeles están suavizados)
    sky = semilla.copy()
    for _ in range(int(D) + 10):
        d = sky.copy()
        d[1:] |= sky[:-1]; d[:-1] |= sky[1:]; d[:, 1:] |= sky[:, :-1]; d[:, :-1] |= sky[:, 1:]
        d = (d & cand) | semilla
        if (d == sky).all():
            break
        sky = d
    sky |= (prof >= 0) & (prof < 3)                                    # el borde mismo siempre afuera (sin línea fina)
    sk = Image.fromarray(sky.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    f = 1 - np.asarray(sk).astype(np.float32) / 255
    out = a * f[..., None]
    return Image.fromarray((out + .5).astype(np.uint8)), float((1 - f).sum() / max(1, w))


def cortar_columnas(im):
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    g = a.mean(-1)
    h, w = g.shape
    hay = g > 8
    top = np.where(hay.any(0), hay.argmax(0), h)
    m1 = box(g, 3); m2 = box(g * g, 3)
    sd = np.sqrt(np.maximum(m2 - m1 * m1, 0))
    tex = sd > 9.0
    tex3 = tex & np.roll(tex, -1, 0) & np.roll(tex, -2, 0)
    lim = int(0.22 * h)
    nuevo = top.copy()
    for x in range(w):
        t0 = top[x]
        if t0 >= h:
            continue
        col = tex3[t0 + 4:min(h, t0 + lim), x]          # +4: salta el borde duro de la silueta
        idx = np.argmax(col) if col.any() else 0
        nuevo[x] = t0 + 4 + idx if col.any() else t0
    # suavizar el nuevo borde (mediana horizontal) y no subir nunca por encima del borde original
    nb = np.asarray(Image.fromarray(nuevo.astype(np.float32)[None, :].repeat(3, 0)).filter(ImageFilter.MedianFilter(3)))[1] if False else nuevo
    k = 21
    pad = np.pad(nuevo.astype(np.float32), (k // 2, k // 2), mode="edge")
    med = np.array([np.median(pad[i:i + k]) for i in range(w)])
    nuevo = np.maximum(np.minimum(med, nuevo + 6), top)
    rows = np.arange(h)[:, None]
    m = (rows >= nuevo[None, :]).astype(np.uint8) * 255
    mm = np.asarray(Image.fromarray(m).filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32) / 255
    return Image.fromarray((a * mm[..., None] + .5).astype(np.uint8)), float(np.mean(nuevo - np.minimum(top, h)))


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(src, "B1.*_d0.5.png"))):
        n = os.path.basename(p); code, s = n.split("_")[0], n.split("_")[1]
        im = Image.open(p)
        if s != "cen" and code in SIN_CIELO:
            im, d = cortar(im)
            print(f"{code} {s}: corte medio {d:.1f} px")
        im.save(os.path.join(dst, n))
