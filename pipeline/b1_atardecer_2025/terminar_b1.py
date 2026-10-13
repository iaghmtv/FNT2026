# -*- coding: utf-8 -*-
"""Termina los fijos de atardecer del Bloque 1: salida cruda de Flux -> máscara de mapping -> silueta 2025 (montañas)
-> quita el cielo/resplandor que la IA agrega sobre la silueta (escenas que en 2025 no tenían cielo).
Uso: python terminar_b1.py DIR_RAW DIR_SALIDA"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, "D:/FNT2026/WEB_FNT2026/pipeline")
import numpy as np
from PIL import Image
import surfaces, flux_cine, cortar_cielo

raw, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for code in [f"B1.{i:02d}" for i in range(1, 12)]:
    for s in ("izq", "cen", "der"):
        fs = sorted(glob.glob(os.path.join(raw, f"{code}_{s}_*.png")))
        if not fs:
            print("falta", code, s); continue
        im = surfaces.apply_mask(Image.open(fs[-1]).convert("RGB"), s)
        if s != "cen":
            sil = flux_cine.silueta_2025(code, s, im.size)
            im = Image.fromarray((np.asarray(im).astype(np.float32) * sil[..., None] + .5).astype(np.uint8))
            if False and code in cortar_cielo.SIN_CIELO:   # ya no hace falta: la IA no inventa cielo con la indicación nueva
                im, _ = cortar_cielo.cortar(im)
        im.save(os.path.join(out, f"{code}_{s}_d0.5.png"))
print("ok")
