# -*- coding: utf-8 -*-
"""B1.03 · noche de luna a partir de la imagen del usuario (ElevenLabs/gpt-image, upscale Topaz 3240x1080 con 3 filas).
- centro: la fila 1 del usuario, llevada a 1856x448 + máscara de las pantallas (calza con la composición del atardecer).
- montañas: las filas del usuario vienen achatadas y no siguen la silueta -> se re-ilumina de noche el atardecer actual
  (con los cardones nuevos) con Qwen, se copia la paleta de la fila del usuario y se aplica máscara + silueta 2025.
Uso: python luna_b103.py COMPOSITE.png DIR_SALIDA"""
import os, sys, hashlib
sys.path.insert(0, "D:/FNT2026/WEB_FNT2026/pipeline"); sys.path.insert(0, "D:/FNT2026/WEB_FNT2026/pipeline/b1_atardecer_2025")
import numpy as np
from PIL import Image
import comfy, graphs, surfaces, flux_cine

COMP, OUT = sys.argv[1], sys.argv[2]; os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
B = "D:/FNT2026/03_BLOQUES/B1_PAISAJES/B1.03_PASTORES/02_IA_GENERACION/ATARDECER_2026_v2"
FILAS = {"cen": (0, 462), "der": (464, 753), "izq": (755, 1080)}
TAM = {"cen": (1856, 448), "der": (2048, 600), "izq": (1920, 600)}
EXT = {"izq": "right", "der": "left"}          # la luna entra desde el centro del escenario
C = Image.open(COMP).convert("RGB")


def prompt(s):
    return ("Relight this exact image as a clear moonlit night. Cold silver-blue moonlight comes from the " + EXT[s] + " and rakes across the slope: "
            "pale blue-white highlights on the stones, the cacti spines and the tops of the shrubs, deep navy-blue shadows, long soft moon shadows on the ground, "
            "strong cool blue color grading, the local colors desaturated by the moonlight. The cacti glow with a thin silver rim light on their spines. "
            "There is no sky in this image: everything above the ridgeline is the pure black background; do not paint any sky, moon, stars or distant mountains. "
            "Keep every cactus, shrub, stone and the whole composition exactly the same; only the lighting and colors change. "
            "Crisp clear air: no fog, no mist, no haze and no glow along the outline. Keep the black background pure black.")


def paleta(img, ref, mask):
    """Transfiere media y desvío por canal (en el área del cerro) de ref a img."""
    a = np.asarray(img).astype(np.float32); r = np.asarray(ref).astype(np.float32); o = a.copy()
    rm = r.mean(-1) > 12
    for c in range(3):
        am, as_ = a[..., c][mask].mean(), a[..., c][mask].std() + 1e-3
        bm, bs = r[..., c][rm].mean(), r[..., c][rm].std() + 1e-3
        o[..., c] = (a[..., c] - am) * (bs / as_) + bm
    return Image.fromarray(np.clip(o, 0, 255).astype(np.uint8))


for s in ("cen", "izq", "der"):
    y0, y1 = FILAS[s]
    fila = C.crop((0, y0, C.width, y1))
    if s == "cen":
        fin = surfaces.apply_mask(fila.resize(TAM[s], Image.LANCZOS), s)
    else:
        base = Image.open(f"{B}/B1.03_atardecer_v2_{s}_{TAM[s][0]}x{TAM[s][1]}.png").convert("RGB")
        seed = int(hashlib.md5(("B1.03" + s + "luna_user").encode()).hexdigest()[:6], 16)
        r = comfy.run(graphs.qwen_edit([comfy.put_input(base, f"fnt26_b103_{s}_atd.png")], prompt(s), seed, f"FNT26/B103luna/{s}", megapixels=1.4),
                      os.path.join(OUT, "raw"), label=f"B1.03 luna {s}")
        q = Image.open(r[0]).convert("RGB").resize(TAM[s], Image.LANCZOS)
        sil = flux_cine.silueta_2025("B1.03", s, TAM[s])
        q = paleta(q, fila, sil > 0.5)
        fin = surfaces.apply_mask(q, s)
        fin = Image.fromarray((np.asarray(fin).astype(np.float32) * sil[..., None] + .5).astype(np.uint8))
    fin.save(os.path.join(OUT, f"B1.03_luna_{s}_{TAM[s][0]}x{TAM[s][1]}.png"))
    print("ok", s, flush=True)
print("===LISTO===")
