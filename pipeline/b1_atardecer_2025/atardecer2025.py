# -*- coding: utf-8 -*-
"""FNT 2026 · Bloque 1 · atardecer a partir de lo proyectado en 2025.
Toma el cuadro 2025 de cada superficie (03_BLOQUES/B1_PAISAJES/<escena>/01_REFERENCIAS/2025_<sup>_t*.png) y lo re-ilumina al
atardecer con Qwen Image Edit, conservando la composición. Laterales: sin bruma en la silueta. Centro: sutil, sin animales.
Uso: python atardecer2025.py SALIDA_DIR [B1.01 B1.02 ...]"""
import glob, json, os, sys, hashlib
PIPE = "D:/FNT2026/WEB_FNT2026/pipeline"
sys.path.insert(0, PIPE)
from PIL import Image
import comfy, graphs, surfaces

W = "D:/FNT2026/WEB_FNT2026"; B = "D:/FNT2026/03_BLOQUES/B1_PAISAJES"
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
scenes = {s["code"]: s for s in json.load(open(f"{W}/escenas.json", encoding="utf-8"))}
want = sys.argv[2:] or sorted(c for c in scenes if c.startswith("B1."))
CASCADAS = {("B1.01", "cen"), ("B1.02", "izq"), ("B1.02", "der")}   # solo donde había cascadas en 2025
EXT = {"izq": "left", "der": "right"}

LIMPIO = ("Crisp clear air: no fog, no mist, no haze, no smoke and no glow along the outline; "
          "the outer silhouette stays sharp and clean against the black background. Keep the black background pure black.")
CASCADA = " The waterfalls stay large, powerful and clearly visible, with bright white foaming water."
# escenas que en 2025 no tenían cielo en las montañas: la IA no debe inventarlo (se proyecta como resplandor sobre la silueta)
SIN_CIELO = {"B1.01", "B1.02", "B1.03", "B1.04", "B1.05", "B1.07", "B1.09"}
NO_CIELO = ("There is no sky in this image: everything above the ridgeline, the treetops and the hilltops is the pure black background; "
            "do not paint any sky, clouds, sunset glow or distant mountains above the landscape, and keep the pale distant slopes as land. ")

def prompt(code, s):
    c = CASCADA if (code, s) in CASCADAS else " Do not add any waterfall or new element."
    if s == "cen":
        return ("Relight this exact image as a calm, soft golden hour sunset: gentle warm light, low contrast, muted warm colors, "
                "a quiet and subtle mood where nothing dramatic happens, no bright sun disk. "
                "Remove every animal and bird from the image and fill those areas naturally with the surrounding landscape. "
                "Where there is sky, make it a soft warm sunset sky. Keep the landscape, vegetation, rocks, water and the composition the same." + c +
                " Crisp clear air: no fog, no mist, no haze. Keep the black areas pure black.")
    return (f"Relight this exact image as a golden hour sunset. Warm low orange sunlight comes from the {EXT[s]} and rakes across the landscape: "
            "glowing orange and amber highlights on every ridge, rock, tree and plant, long soft shadows on the opposite sides, warm golden color grading. "
            "Vegetation keeps its natural green color, only lit by the warm golden light. "
            + (NO_CIELO if code in SIN_CIELO else "Where there is sky, turn it into a warm sunset sky with soft orange, pink and lilac clouds. ") +
            "Keep every tree, plant, flower, rock, cliff, water and the whole composition exactly the same; only the lighting and colors change." + c + " " + LIMPIO)

if not comfy.alive():
    sys.exit("ComfyUI no responde")
log = {}
for code in want:
    slug = scenes[code]["slug"]
    for s in ("izq", "cen", "der"):
        src = sorted(glob.glob(os.path.join(B, slug, "01_REFERENCIAS", f"2025_{s}_t*.png")))
        if not src:
            print("falta", code, s); continue
        dst = os.path.join(OUT, f"{code}_atardecer_{s}.png")
        if os.path.exists(dst):
            continue
        im = Image.open(src[0]).convert("RGB")
        im.thumbnail((2400, 2400))
        name = comfy.put_input(im, f"fnt26_b1v2_{code}_{s}.png")
        p = prompt(code, s)
        seed = int(hashlib.md5((code + s).encode()).hexdigest()[:6], 16)
        out = comfy.run(graphs.qwen_edit([name], p, seed, f"FNT26/B1v2/{code}_{s}", megapixels=1.4), os.path.join(OUT, "raw"), label=f"{code} {s}")
        res = Image.open(out[0]).convert("RGB")
        surfaces.apply_mask(res, s).save(dst)
        log[f"{code}_{s}"] = {"fuente_2025": src[0], "prompt": p, "seed": seed}
        print("ok", code, s, res.size, flush=True)
json.dump(log, open(os.path.join(OUT, f"log_{'_'.join(want)}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("===LISTO===")
