# -*- coding: utf-8 -*-
"""FNT 2026 · Bloque 1 · pasada Flux Krea img2img 'cinematografica' sobre el atardecer Qwen (hecho desde lo proyectado en 2025)
+ silueta exacta de 2025 (donde en 2025 habia negro, queda negro: sin resplandor sobre la silueta).
Uso: python flux_cine.py DIR_QWEN DIR_SALIDA CODE:sup:denoise:depth ..."""
import glob, json, os, sys, hashlib
PIPE = "D:/FNT2026/WEB_FNT2026/pipeline"
sys.path.insert(0, PIPE)
import numpy as np
from PIL import Image, ImageFilter
import comfy, graphs, surfaces

B = "D:/FNT2026/03_BLOQUES/B1_PAISAJES"
W = "D:/FNT2026/WEB_FNT2026"
EXT = {"izq": "left", "der": "right"}
DESC = {
    "B1.01": ("lush subtropical Misiones rainforest hills: dense green tree canopy, palm trees and grassy clearings, a red earth path",
              "a jungle waterfall pouring down a rock wall between green rainforest trees, a big mossy branch across the frame"),
    "B1.02": ("Yungas cloud forest slopes with dense green trees and large white waterfalls cascading down the rocks into a stream",
              "the interior of a dark Yungas jungle with tall trees, hanging vines, palms and distant waterfalls"),
    "B1.03": ("an arid Andean slope in Catamarca: reddish earth, scattered stones, small round cacti and low dry shrubs",
              "an arid Andean desert valley with tall cardon cacti and dry shrubs, mountains in the distance"),
    "B1.04": ("dense Misiones rainforest undergrowth: lush green leafy bushes, red flowering shrubs and white passion flowers",
              "a red earth path through lush green Misiones rainforest with red and pink flowering trees"),
    "B1.05": ("green grassy mountain slopes of Tafi del Valle with tussock grass, scattered boulders and a lone cardon cactus",
              "a high green grassland valley with rolling hills under an open sky"),
    "B1.06": ("Serrania de Hornocal in Jujuy: mountains of folded rock strata in red, ochre and cream bands above a dry plateau, open sky",
              "the Hornocal fourteen-colors mountains with zigzag strata of red, ochre, green and purple, high Andean plateau"),
    "B1.07": ("red Salta mountains with green grass at their foot and many tall cardon cacti",
              "Quebrada de las Conchas in Salta: red sandstone cliffs, green grass and cardon cacti along a valley"),
    "B1.08": ("Talampaya canyon in La Rioja: towering red sandstone cliff walls with deep vertical grooves, green shrubs at the base, open sky",
              "Talampaya canyon: a towering red sandstone cliff with vertical grooves, a dry riverbed and green algarrobo trees"),
    "B1.09": ("green wooded sierras with granite boulders along the shore of a calm lake and a winding river",
              "green wooded hills with granite boulders around a calm lake"),
    "B1.10": ("the Ibera wetlands: a calm lagoon with rippling water, a line of trees on the far shore and dark tree silhouettes",
              "a calm Ibera lagoon at sunset with a small wooden canoe and trees on the far shore"),
    "B1.11": ("Sierras de Cordoba: golden tussock grass hills, a winding dirt trail, granite boulders and an open sky",
              "the Sierras de Cordoba: golden grassland hills and granite outcrops under an open sky"),
}
CASCADAS = {("B1.01", "cen"), ("B1.02", "izq"), ("B1.02", "der")}   # solo donde había cascadas en 2025
SIN_CIELO = {"B1.01", "B1.02", "B1.03", "B1.04", "B1.05", "B1.07", "B1.09"}
CINE = ("Shot on ARRI Alexa with an anamorphic lens, real filmed footage, natural film grain, photorealistic, sharp detailed textures, "
        "crisp clear air, no fog, no mist, no haze, no glow along the outline. The black background stays pure black.")
SC = {s["code"]: s for s in json.load(open(f"{W}/escenas.json", encoding="utf-8"))}


def prompt(code, s):
    d_side, d_cen = DESC[code]
    c = " The waterfalls are large, powerful and clearly visible, with bright white foaming water." if (code, s) in CASCADAS else " No waterfalls."
    if s == "cen":
        return (f"Cinematic film still, calm soft golden hour sunset: {d_cen}. Gentle warm light, low contrast, subtle and peaceful mood, "
                "natural colors, no animals, no birds, no people, no bright sun disk." + c + " " + CINE)
    return (f"Cinematic film still, golden hour sunset: {d_side}. Warm low sunlight from the {EXT[s]} rakes across the landscape with long soft shadows; "
            "rich natural colors, green vegetation stays green under the warm golden light." + c +
            (" There is no sky: above the ridgeline and the treetops everything is pure black, no sky, no clouds, no glow." if code in SIN_CIELO else "") +
            " " + CINE)


def flux_i2i(base_name, prompt_txt, w, h, seed, prefix, denoise, depth_name=None, lora=0.7, steps=28):
    g = graphs._flux_base(prompt_txt, 10.0 if depth_name else 3.5)
    g.update({
        "20": {"class_type": "LoadImage", "inputs": {"image": base_name}},
        "21": {"class_type": "ImageScale", "inputs": {"image": ["20", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "disabled"}},
        "22": {"class_type": "VAEEncode", "inputs": {"pixels": ["21", 0], "vae": ["4", 0]}},
    })
    model, pos, neg = ["1", 0], ["6", 0], ["7", 0]
    if depth_name:
        g.update({
            "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": graphs.FLUX_DEPTH_LORA, "strength_model": lora}},
            "8": {"class_type": "LoadImage", "inputs": {"image": depth_name}},
            "9": {"class_type": "ImageScale", "inputs": {"image": ["8", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "disabled"}},
            "10": {"class_type": "InstructPixToPixConditioning", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["4", 0], "pixels": ["9", 0]}},
        })
        model, pos, neg = ["2", 0], ["10", 0], ["10", 1]
    g.update({
        "11": {"class_type": "KSampler", "inputs": {"model": model, "positive": pos, "negative": neg, "latent_image": ["22", 0],
                                                    "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "denoise": denoise}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": prefix}},
    })
    return g


def silueta_2025(code, s, size):
    """Silueta superior del contenido 2025, por columnas: todo lo que está debajo del primer píxel con contenido se conserva;
    lo de arriba (lo que en 2025 era negro sobre la silueta) queda negro. Sin huecos en las sombras oscuras."""
    slug = SC[code]["slug"]
    src = sorted(glob.glob(os.path.join(B, slug, "01_REFERENCIAS", f"2025_{s}_t*.png")))[0]
    im = Image.open(src).convert("L").resize(size, Image.LANCZOS)
    c = (np.asarray(im) > 10)
    # contenido "real": al menos 3 píxeles seguidos en vertical (evita ruido suelto)
    c3 = c & np.roll(c, -1, 0) & np.roll(c, -2, 0)
    h = c.shape[0]
    top = np.where(c3.any(0), c3.argmax(0), h)
    # puentea huecos angostos entre copas/rocas (~40 px): sin barras verticales cuando el contenido nuevo no coincide hueco a hueco
    r = max(4, int(round(0.035 * h)))
    tt = np.pad(top.astype(np.float32), r, mode="edge")
    top = np.lib.stride_tricks.sliding_window_view(tt, 2 * r + 1).min(1)
    rows = np.arange(h)[:, None]
    m = (rows >= top[None, :]).astype(np.uint8) * 255
    mm = Image.fromarray(m).filter(ImageFilter.GaussianBlur(0.8))
    return np.asarray(mm).astype(np.float32) / 255


def procesar(code, s, qwen_png, out_png, denoise=0.45, depth=False, lora=0.7):
    w, h = surfaces.SURF[s][3]
    base = Image.open(qwen_png).convert("RGB")
    bn = comfy.put_input(base, f"fnt26_b1cine_{code}_{s}.png")
    dn = None
    if depth and s != "cen":
        dn = comfy.put_input(surfaces.depth_for_generation(s), f"fnt26_depth_{s}.png")
    seed = int(hashlib.md5((code + s + "cine").encode()).hexdigest()[:6], 16)
    out = comfy.run(flux_i2i(bn, prompt(code, s), w, h, seed, f"FNT26/B1cine/{code}_{s}", denoise, dn, lora),
                    os.path.join(os.path.dirname(out_png), "raw"), label=f"{code} {s} flux d={denoise}{' depth' if dn else ''}")
    res = Image.open(out[0]).convert("RGB")
    fin = surfaces.apply_mask(res, s)
    if s != "cen":                       # montañas: nada por encima de la silueta de 2025 (sin resplandor ni bruma)
        sil = silueta_2025(code, s, fin.size)
        fin = Image.fromarray((np.asarray(fin).astype(np.float32) * sil[..., None] + .5).astype(np.uint8))
    fin.save(out_png)
    return prompt(code, s), seed


if __name__ == "__main__":
    qdir, odir = sys.argv[1], sys.argv[2]
    os.makedirs(odir, exist_ok=True)
    log = {}
    for j in sys.argv[3:]:            # CODE:sup:denoise:depth(0/1)
        code, s, d, dp = j.split(":")
        out = os.path.join(odir, f"{code}_{s}_d{d}{'_depth' if dp == '1' else ''}.png")
        p, seed = procesar(code, s, os.path.join(qdir, f"{code}_atardecer_{s}.png"), out, float(d), dp == "1")
        log[os.path.basename(out)] = {"prompt": p, "seed": seed, "denoise": float(d), "depth": dp == "1"}
        print("ok", out, flush=True)
    with open(os.path.join(odir, "log.json"), "a", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
