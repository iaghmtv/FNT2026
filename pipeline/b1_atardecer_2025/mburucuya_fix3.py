# -*- coding: utf-8 -*-
"""B1.04 · mburucuyá a escala real: se agrega en recortes de la zona de arbustos (donde estaban las flores en 2025), se pega reducido
con borde difuminado sobre la imagen sin flores, y Flux suave unifica. Máscara + silueta 2025.
Uso: python mburucuya_fix3.py DIR_PASO1(sin flores) DIR_SALIDA [denoise_flux]"""
import glob, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, "D:/FNT2026/WEB_FNT2026/pipeline")
import numpy as np
from PIL import Image, ImageFilter
import comfy, graphs, surfaces, flux_cine

P1, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
DEN = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
B = "D:/FNT2026/03_BLOQUES/B1_PAISAJES/B1.04_HIJOS_DE_LA_SELVA_GUARANIES"
REFS = sorted(glob.glob(B + "/01_REFERENCIAS/mburucuya/*.jpg"))
EXT = {"izq": "left", "der": "right"}
# zonas (en la imagen de 1920x600 / 2048x600) donde estaban las flores de 2025, ~2.4:1 de proporción
ZONAS = {"izq": [(1030, 215, 1530, 425)], "der": [(30, 205, 610, 445)]}


def agregar(s):
    return ("Add a climbing passion flower vine (mburucuya, Passiflora caerulea) scrambling over the green shrubs in image 1, exactly like the plant in the "
            "reference photos (image 2 and image 3): thin stems with curly tendrils, palmate leaves, a few closed green buds and three to five open flowers. "
            "Each open flower: five white petals and five sepals, a ring of many fine filaments banded blue-violet at the tips, white in the middle and dark purple "
            "near the center, and in the center an upright green stalk with five yellow-green anthers and three dark purple stigmas forming a cross. "
            "The flowers face different directions and sit among the leaves of the shrubs, partly hidden, at the same distance as the shrubs (not in the foreground). "
            "Everything is lit by the same warm golden sunset light coming from the " + EXT[s] + " as image 1: the white petals take a warm amber-orange tint, "
            "with the shadow sides darker. Keep the shrubs, the trees, the composition and the black background of image 1 exactly the same. Photorealistic.")


ref_names = []
for i, p in enumerate(REFS):
    im = Image.open(p).convert("RGB"); im.thumbnail((1024, 1024))
    ref_names.append(comfy.put_input(im, f"fnt26_mburucuya_ref_{i}.png"))
for s in ("izq", "der"):
    base = Image.open(os.path.join(P1, f"B1.04_{s}_1_sin_flores.png")).convert("RGB")
    out = base.copy()
    seed = int(hashlib.md5(("B1.04" + s + "mbur3").encode()).hexdigest()[:6], 16)
    for k, (x0, y0, x1, y1) in enumerate(ZONAS[s]):
        crop = base.crop((x0, y0, x1, y1))
        cn = comfy.put_input(crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS), f"fnt26_b104_{s}_z{k}.png")
        r = comfy.run(graphs.qwen_edit([cn] + ref_names, agregar(s), seed + k, f"FNT26/B104mbur3/{s}_z{k}", megapixels=1.0), os.path.join(OUT, "raw"), label=f"B1.04 {s} zona {k}")
        res = Image.open(r[0]).convert("RGB").resize(crop.size, Image.LANCZOS)
        res.save(os.path.join(OUT, f"B1.04_{s}_zona{k}.png"))
        # pegar con borde difuminado
        m = Image.new("L", crop.size, 0); f = 22
        m.paste(255, (f, f, crop.width - f, crop.height - f)); m = m.filter(ImageFilter.GaussianBlur(f * 0.6))
        out.paste(res, (x0, y0), m)
    p2 = os.path.join(OUT, f"B1.04_{s}_2_mburucuya.png"); out.save(p2)
    w, h = surfaces.SURF[s][3]
    pf = flux_cine.prompt("B1.04", s).replace("white passion flowers", "a climbing passion flower vine (mburucuya, Passiflora caerulea) among the shrubs, with small white flowers with a corona of fine blue, white and purple filaments")
    r = comfy.run(flux_cine.flux_i2i(comfy.put_input(out, f"fnt26_b104_{s}_m3.png"), pf, w, h, seed, f"FNT26/B104mbur3/{s}_flux", DEN), os.path.join(OUT, "raw"), label=f"B1.04 {s} flux {DEN}")
    fin = surfaces.apply_mask(Image.open(r[0]).convert("RGB"), s)
    sil = flux_cine.silueta_2025("B1.04", s, fin.size)
    fin = Image.fromarray((np.asarray(fin).astype(np.float32) * sil[..., None] + .5).astype(np.uint8))
    fin.save(os.path.join(OUT, f"B1.04_{s}_final_d{DEN}.png"))
    print("ok", s, flush=True)
print("===LISTO===")
