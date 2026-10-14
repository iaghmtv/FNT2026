# -*- coding: utf-8 -*-
"""B1.03 · cardones variados con control de calidad por zona.
Cada recorte -> Qwen (recorte + referencia, o solo texto si la referencia contamina) -> se acepta solo si el borde del recorte
(la ladera alrededor) quedó igual (diff medio < UMBRAL) -> pegado solo de lo que cambió con color medido en el suelo ->
Flux suave -> máscara + silueta 2025.
Uso: python cardones_fix2.py DIR_FIJOS DIR_PREVIOS_RAW DIR_SALIDA [denoise]"""
import glob, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, "D:/FNT2026/WEB_FNT2026/pipeline")
import numpy as np
from PIL import Image, ImageFilter
import comfy, graphs, surfaces, flux_cine

FIJOS, PREV, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
DEN = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
UMBRAL = 30.0
REFD = "D:/FNT2026/03_BLOQUES/B1_PAISAJES/B1.03_PASTORES/01_REFERENCIAS/cardones"
REFS = sorted(glob.glob(REFD + "/*.png") + glob.glob(REFD + "/*.jpg"))
EXT = {"izq": "left", "der": "right"}
VAR = {
    1: "a flowering cardon cactus with ribbed green columns and golden spines, with large white flowers and pink-red hairy flower buds on the tips of the arms",
    2: "a pale hairy cardon cactus (Leucostele pasacana) covered in long whitish-golden spines, with a thick trunk and three upturned arms",
    3: "an old many-armed green cardon cactus (Leucostele terscheckii) with many tall upturned ribbed arms branching from a short trunk, golden spines",
    4: "a classic candelabra cardon cactus with a tall trunk and four or five upturned arms, golden-brown spines",
    5: "two tall old cardon cacti side by side, weathered ribbed columns with a couple of arms and small round woodpecker holes",
    6: "a tall old cardon with two arms next to a few young single-column cardones",
}
ZONAS = {
    "izq": [(520, 90, 800, 340, 5), (800, 190, 1070, 450, 3), (1210, 270, 1490, 520, 1), (520, 270, 610, 400, 2)],
    "der": [(340, 300, 580, 560, 4), (790, 170, 1110, 510, 2)],
}


def prompt(s, v, con_ref):
    p = "Replace the cactus or cacti in image 1 with " + VAR[v]
    p += ", like the plant in the reference photo (image 2), but only the plant: do not copy the sky, background or ground of image 2. " if con_ref else ". "
    return p + ("It is an Argentine cardon of the Andean valleys, not a Mexican saguaro. Keep it in the same place, standing on the same ground, with the same "
                "height and the same size in the frame as the cactus it replaces. Light it with the warm golden sunset light coming from the " + EXT[s] +
                " like the rest of image 1, with a long soft shadow on the ground. Keep the reddish hillside behind it, the ground, stones, dry shrubs and "
                "everything else in image 1 exactly the same, with the same warm sunset colors and the same framing; only the cactus changes. Photorealistic.")


def blur(m, r):
    return np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255


def dil(m, k):
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k))).astype(np.float32) / 255


def borde_diff(res, crop):
    h, w = crop.shape[:2]; f = max(6, min(h, w) // 10)
    ring = np.zeros((h, w), bool); ring[:f] = 1; ring[-f:] = 1; ring[:, :f] = 1; ring[:, -f:] = 1
    m = ring & (crop.mean(-1) > 20)
    return float(np.abs(res - crop).mean(-1)[m].mean()) if m.sum() > 50 else 0.0


def pegar(crop, res):
    diff = np.abs(res - crop).mean(-1)
    cambio = dil((blur((diff > 28).astype(np.float32), 1.5) > 0.35).astype(np.float32), 7)
    bg = cambio < 0.5; adj = res.copy()
    if bg.sum() > 200:
        for c in range(3):
            rm, rs = res[..., c][bg].mean(), res[..., c][bg].std() + 1e-3
            cm, cs = crop[..., c][bg].mean(), crop[..., c][bg].std() + 1e-3
            adj[..., c] = (res[..., c] - rm) * (cs / rs) + cm
    borde = np.zeros(cambio.shape, np.float32); f = 8; borde[f:-f, f:-f] = 1; borde = blur(borde, 4)
    m = blur(cambio, 3) * borde
    return crop * (1 - m[..., None]) + np.clip(adj, 0, 255) * m[..., None]


ref_names = {}
for i, p in enumerate(REFS, 1):
    im = Image.open(p).convert("RGB"); im.thumbnail((1024, 1024))
    ref_names[i] = comfy.put_input(im, f"fnt26_cardon_ref_{i}.png")
for s in ("izq", "der"):
    base = Image.open(os.path.join(FIJOS, f"B1.03_{s}_d0.5.png")).convert("RGB")
    out = np.asarray(base).astype(np.float32).copy()
    seed = int(hashlib.md5(("B1.03" + s + "card").encode()).hexdigest()[:6], 16)
    for k, (x0, y0, x1, y1, v) in enumerate(ZONAS[s]):
        crop = out[y0:y1, x0:x1].copy(); sz = (x1 - x0, y1 - y0)
        ok = None
        # 1) lo ya generado
        for p in sorted(glob.glob(os.path.join(PREV, f"{s}_z{k}_*.png"))):
            r = np.asarray(Image.open(p).convert("RGB").resize(sz, Image.LANCZOS)).astype(np.float32)
            d = borde_diff(r, crop); print(s, k, "previo", os.path.basename(p), round(d, 1), flush=True)
            if d < UMBRAL: ok = r; break
        # 2) intentos nuevos: con referencia (otra semilla y prompt reforzado) y después solo texto
        intentos = [(True, seed + k + 100), (False, seed + k), (False, seed + k + 200), (True, seed + k + 300), (False, seed + k + 400)]
        cimg = Image.fromarray(crop.astype(np.uint8)); fac = 3 if max(sz) < 300 else 2
        cn = None
        for n, (con_ref, sd) in enumerate(intentos):
            if ok is not None: break
            if cn is None:
                cn = comfy.put_input(cimg.resize((sz[0] * fac, sz[1] * fac), Image.LANCZOS), f"fnt26_b103_{s}_z{k}_v2.png")
            imgs = [cn, ref_names[v]] if con_ref else [cn]
            rr = comfy.run(graphs.qwen_edit(imgs, prompt(s, v, con_ref), sd, f"FNT26/B103card3/{s}_z{k}_t{n}", megapixels=1.0),
                           os.path.join(OUT, "raw"), label=f"B1.03 {s} zona {k} intento {n} ref={con_ref}")
            r = np.asarray(Image.open(rr[0]).convert("RGB").resize(sz, Image.LANCZOS)).astype(np.float32)
            d = borde_diff(r, crop); print(s, k, "intento", n, "ref" if con_ref else "texto", round(d, 1), flush=True)
            if d < UMBRAL: ok = r
        if ok is None:
            print(s, k, "SIN RESULTADO ACEPTABLE: se deja el cactus original", flush=True); continue
        Image.fromarray(ok.astype(np.uint8)).save(os.path.join(OUT, f"B1.03_{s}_zona{k}_ok.png"))
        out[y0:y1, x0:x1] = pegar(crop, ok)
    img = Image.fromarray(out.astype(np.uint8)); img.save(os.path.join(OUT, f"B1.03_{s}_2_cardones.png"))
    w, h = surfaces.SURF[s][3]
    pf = flux_cine.prompt("B1.03", s).replace("small round cacti", "varied Argentine cardon cacti (flowering, hairy pasacana, many-armed)")
    r = comfy.run(flux_cine.flux_i2i(comfy.put_input(img, f"fnt26_b103_{s}_p3.png"), pf, w, h, seed, f"FNT26/B103card3/{s}_flux", DEN), os.path.join(OUT, "raw"), label=f"B1.03 {s} flux {DEN}")
    fin = surfaces.apply_mask(Image.open(r[0]).convert("RGB"), s)
    sil = flux_cine.silueta_2025("B1.03", s, fin.size)
    fin = Image.fromarray((np.asarray(fin).astype(np.float32) * sil[..., None] + .5).astype(np.uint8))
    fin.save(os.path.join(OUT, f"B1.03_{s}_final_d{DEN}.png"))
    print("ok", s, flush=True)
print("===LISTO===")
