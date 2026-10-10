# -*- coding: utf-8 -*-
"""Superficies del show: máscaras de mapping, Z-depth de los cerros y tamaños de generación.

La máscara de mapping (la que usa Resolume) manda. El relieve sale del Z-depth renderizado en 3ds Max
desde la cámara de cada proyector (blanco = cerca). Donde la máscara se sale del Z-depth, el relieve se
extiende con un relleno suave para que no queden huecos."""
import os
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
INS = os.path.join(HERE, "insumos")

SURF = {
    # nombre: (archivo máscara, archivo Z-depth, tamaño final, tamaño de generación)
    "izq": ("mascara_izq_3840x1200.png", "zdepth_izq_3840x1200.png", (3840, 1200), (1792, 560)),
    "der": ("mascara_der_4096x1200.png", "zdepth_der_4096x1200.png", (4096, 1200), (1856, 544)),
    "cen": ("mascara_cen_3712x896.png", None, (3712, 896), (1856, 448)),
}
LABEL = {"izq": "Montaña izquierda", "cen": "Pantallas centro", "der": "Montaña derecha"}


def mask(s, size=None):
    m = Image.open(os.path.join(INS, SURF[s][0])).convert("L")
    return m.resize(size, Image.LANCZOS) if size else m


def depth_for_generation(s):
    """Z-depth recortado y completado dentro de la máscara, a tamaño de generación, fondo negro."""
    mfile, zfile, full, gen = SURF[s]
    z = Image.open(os.path.join(INS, zfile)).convert("RGBA")
    m = np.array(mask(s, z.size)).astype(np.float32) / 255
    a = np.array(z.split()[3]).astype(np.float32) / 255
    d = np.array(z.convert("L")).astype(np.float32) / 255
    # relleno normalizado: extiende el relieve hacia las zonas de máscara sin Z-depth
    w = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(25))
    v = Image.fromarray((d * a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(25))
    w = np.array(w).astype(np.float32) / 255
    v = np.array(v).astype(np.float32) / 255
    fill = np.where(w > 1e-3, v / np.maximum(w, 1e-3), 0.3)
    dd = np.where(a > 0.5, d, fill)
    dd = np.clip(dd, 0, 1) * m
    img = Image.fromarray((dd * 255 + .5).astype(np.uint8)).convert("RGB")
    return img.resize(gen, Image.LANCZOS)


def apply_mask(img, s, size=None):
    """Recorta con la máscara de mapping sobre negro, al tamaño pedido (por defecto mitad del final)."""
    full = SURF[s][2]
    size = size or (full[0] // 2, full[1] // 2)
    img = img.convert("RGB").resize(size, Image.LANCZOS)
    m = np.array(mask(s, size)).astype(np.float32)[..., None] / 255
    return Image.fromarray((np.array(img).astype(np.float32) * m + .5).astype(np.uint8))
