# -*- coding: utf-8 -*-
"""Mapa de zonas aptas para elementos definidos sobre cada montaña.

El Z-depth está renderizado desde la cámara del proyector (blanco = cerca). Una imagen proyectada se ve
sin distorsión solo desde el proyector; desde otro punto del público, cada punto se corre en proporción
a cuánto se aleja la superficie de un plano de frente. Por eso:
  - pendiente de profundidad baja (|grad|)  -> la superficie mira al público: lo dibujado se mantiene;
  - curvatura baja (laplaciano)              -> la zona es casi plana: no se quiebra el dibujo;
  - pendiente vertical baja (|gy|)           -> los elementos verticales siguen parados (no se "acuestan").
Lejos de esas zonas conviene usar solo color, textura y luz.

Salida: zonas_<sup>.png (verde = figuras y elementos altos, amarillo = figuras bajas o en movimiento
horizontal, rojo = solo color/textura/luz) y zonas_<sup>_overlay.jpg sobre el render de la montaña.
"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import surfaces


def blur(a, r):
    """Desenfoque aproximadamente gaussiano (3 pasadas de caja) sobre float32."""
    out = a.astype(np.float32)
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(out, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode="edge"), axis=ax)
            if ax == 0:
                out = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
            else:
                out = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return out


def compute(s, width=1920):
    zfile = surfaces.SURF[s][1]
    z = Image.open(os.path.join(surfaces.INS, zfile)).convert("RGBA")
    W, H = z.size
    h = round(H * width / W)
    z = z.resize((width, h), Image.LANCZOS)
    a = np.array(z.split()[3]).astype(np.float32) / 255
    d = np.array(z.convert("L")).astype(np.float32) / 255
    m = np.array(surfaces.mask(s, (width, h))).astype(np.float32) / 255
    inside = (a > 0.5) & (m > 0.5)
    # margen: lejos del borde de la silueta (cresta y base) para que nada se salga del cerro
    core = blur(inside.astype(np.float32), 18) > 0.97
    ds = blur(np.where(inside, d, 0), 6) / np.maximum(blur(inside.astype(np.float32), 6), 1e-3)
    gy, gx = np.gradient(ds)
    gy, gx = gy * h, gx * width                  # en unidades de profundidad por ancho/alto de imagen
    grad = np.hypot(gx, gy)
    lap = np.abs(blur(ds, 20) - ds) * 50
    g = blur(grad, 10); v = blur(np.abs(gy), 10); c = blur(lap, 10)
    sel = core
    def q(x, p):
        return np.percentile(x[sel], p)
    # verde: frontal, plano y sin pendiente vertical (elementos altos ok)
    green = sel & (g < q(g, 35)) & (c < q(c, 50)) & (v < q(v, 35))
    # amarillo: frontal o en curva de nivel (figuras bajas, recorridos horizontales)
    yellow = sel & ~green & (g < q(g, 60)) & (c < q(c, 70))
    # Z-depth saturado (zona más cercana al público): sin dato de relieve -> nunca verde
    sat = inside & (blur((d >= 0.975).astype(np.float32), 4) > 0.5)
    yellow = (yellow | (green & sat)) & ~(sat & (c > q(c, 70)))
    green = green & ~sat
    red = inside & ~green & ~yellow
    zmap = np.zeros((h, width, 3), np.uint8)
    zmap[red] = (190, 40, 40); zmap[yellow] = (235, 190, 40); zmap[green] = (60, 190, 90)
    stats = {k: round(float(x.sum() / max(inside.sum(), 1)) * 100, 1) for k, x in (("verde", green), ("amarillo", yellow), ("rojo", red))}
    return zmap, inside, stats


def overlay(s, zmap, inside, width=1920):
    clay = Image.open(os.path.join(surfaces.INS, f"clay_{s}_{surfaces.SURF[s][2][0]}x{surfaces.SURF[s][2][1]}.png")).convert("RGB")
    clay = clay.resize((zmap.shape[1], zmap.shape[0]), Image.LANCZOS)
    c = np.array(clay).astype(np.float32)
    o = np.where(inside[..., None], c * 0.45 + zmap.astype(np.float32) * 0.55, c * 0.25)
    cam = os.path.join(surfaces.INS, f"camino2025_{s}_{surfaces.SURF[s][2][0]}x{surfaces.SURF[s][2][1]}.png")
    if os.path.exists(cam):     # recorrido de los granaderos 2025, en blanco
        ln = np.array(Image.open(cam).convert("L").resize((zmap.shape[1], zmap.shape[0]), Image.LANCZOS)).astype(np.float32) / 255
        ln = np.clip(ln * 2.2, 0, 1)[..., None]
        o = o * (1 - ln) + 255 * ln
    return Image.fromarray(o.clip(0, 255).astype(np.uint8))


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "assets", "zonas")
    os.makedirs(outdir, exist_ok=True)
    for s in ("izq", "der"):
        zmap, inside, stats = compute(s)
        Image.fromarray(zmap).save(os.path.join(outdir, f"zonas_{s}.png"))
        overlay(s, zmap, inside).save(os.path.join(outdir, f"zonas_{s}_overlay.jpg"), quality=86)
        print(s, stats)
