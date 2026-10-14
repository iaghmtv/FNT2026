# -*- coding: utf-8 -*-
"""FNT 2026 · Bloque 1 · timelapse SOLO de atardecer (montañas) a partir del fijo nuevo (2025 -> Qwen -> Flux cine).
Cuadros guía (Qwen re-ilumina el fijo): tarde dorada (0) -> atardecer = el fijo (80) -> atardecer profundo (165) -> última luz (242).
La luz entra desde el lado exterior, igual que en los fijos. Sin noche, sin bruma; nada por encima de la silueta de 2025.
Uso: python timelapse_atardecer.py DIR_FIJOS DIR_TRABAJO [B1.01 ...]"""
import glob, json, os, sys, hashlib, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = "D:/FNT2026/WEB_FNT2026/pipeline"
sys.path.insert(0, PIPE); sys.path.insert(0, HERE)
import numpy as np
from PIL import Image
import comfy, graphs, surfaces
import flux_cine

FIJOS, WD = sys.argv[1], sys.argv[2]
os.makedirs(WD, exist_ok=True)
want = sys.argv[3:] or [f"B1.{i:02d}" for i in range(1, 12)]
EXT = {"izq": "left", "der": "right"}
H3_SIZE = {"izq": (1152, 352), "der": (1216, 352)}
LENGTH = 243
TIMELINE = [("tarde", 0), ("atardecer", 80), ("profundo", 165), ("ultima", 242)]
KEEP = (" Keep every tree, plant, rock, cliff, water and the whole composition exactly the same; only the lighting and colors change. "
        "Crisp clear air, no fog, no mist, no haze, no glow along the outline. Keep the black background pure black.")
CASC = {("B1.02", "izq"), ("B1.02", "der")}
SIN_CIELO = flux_cine.SIN_CIELO
NO_SOL = (" The sun itself is outside the frame and never visible: no sun disk, no lens flare, no bright glow or hot spot at the edges of the image; "
          "only its warm light enters from outside. Do not add any new element (no trees, no rocks, no buildings).")
NO_CIELO = " There is no sky: above the ridgeline and the treetops everything stays pure black, no sky, no clouds, no glow."


def relight(L, s, code=""):
    e = EXT[s]
    return {
        "tarde": (f"Relight this exact landscape as late afternoon golden light: the sun is a bit higher, warm golden-yellow light from the {e}, "
                  "shorter shadows, everything clearly lit with natural rich colors, green vegetation stays green."),
        "profundo": (f"Relight this exact landscape as a deep sunset: the sun is very low on the {e}, intense orange and red light grazes only the upper slopes, "
                     "the tops of the trees and the rocks, the lower parts fall into soft warm violet shadow, long dramatic shadows."),
        "ultima": ("Relight this exact landscape with the very last light of the sunset: only the highest ridge and the tallest treetops glow with a thin "
                   "pink-orange light, everything else is in soft dusky violet shadow but still clearly visible; it is not night yet."),
    }[L] + (NO_SOL if L in ("profundo", "ultima") else "") + (NO_CIELO if code in SIN_CIELO else "") + KEEP


def prompt_video(code, s):
    e = EXT[s]
    agua = " The waterfalls keep flowing, large and white." if (code, s) in CASC else ""
    return ("Static locked-off camera, no camera movement: a time-lapse of a long golden hour sunset over this landscape. "
            f"The low sun keeps sinking on the {e}: warm golden light rakes across the relief, long shadows slowly stretch and crawl across every gully, "
            "rock and plant, the light turns deeper orange and pink and slowly climbs up the slopes, until only the highest ridge glows with the last light. "
            f"Gentle wind in the vegetation.{agua}{NO_CIELO if code in SIN_CIELO else ''}{NO_SOL} Crisp clear air, no fog, no mist. The black background stays pure black. "
            "Smooth continuous light transition, no cuts, no night.")


def mascara(code, s, size):
    """Máscara de mapping x silueta de 2025 (nada por encima de la silueta)."""
    m = np.asarray(surfaces.mask(s, size)).astype(np.float32) / 255
    return m * flux_cine.silueta_2025(code, s, size)


def recortar(im, code, s, size):
    im = im.convert("RGB").resize(size, Image.LANCZOS)
    return Image.fromarray((np.asarray(im).astype(np.float32) * mascara(code, s, size)[..., None] + .5).astype(np.uint8))


log = {}
for code in want:
    for s in ("izq", "der"):
        base_p = os.path.join(FIJOS, f"{code}_{s}_d0.5.png")
        if not os.path.exists(base_p):
            print("falta fijo", base_p); continue
        seed = int(hashlib.md5((code + s + "tl").encode()).hexdigest()[:6], 16)
        base = Image.open(base_p).convert("RGB")
        kf = {"atardecer": base}
        bn = comfy.put_input(base, f"fnt26_b1tl_{code}_{s}_base.png")
        for L in ("tarde", "profundo", "ultima"):
            dst = os.path.join(WD, f"{code}_kf_{L}_{s}.png")
            if not os.path.exists(dst):
                out = comfy.run(graphs.qwen_edit([bn], relight(L, s, code), seed, f"FNT26/B1tl/{code}_{L}_{s}", megapixels=1.4),
                                os.path.join(WD, "raw"), label=f"{code} {L} {s}")
                recortar(Image.open(out[0]), code, s, base.size).save(dst)
            kf[L] = Image.open(dst).convert("RGB")
        raw = os.path.join(WD, f"{code}_timelapse_{s}_raw.mp4")
        if not os.path.exists(raw):
            w, h = H3_SIZE[s]
            names = {L: comfy.put_input(recortar(kf[L], code, s, (w, h)), f"fnt26_b1tl_{code}_h3_{L}_{s}.png") for L, _ in TIMELINE}
            guides = [(names[L], fi) for L, fi in TIMELINE[1:-1]]
            g = graphs.h3_timelapse(names["tarde"], names["ultima"], guides, prompt_video(code, s), w, h, LENGTH, seed,
                                    f"video/FNT26/B1tl/{code}_timelapse_{s}")
            out = comfy.run(g, os.path.join(WD, "raw"), timeout=5400, poll=15, label=f"{code} H3 atardecer {s}")
            os.replace(out[0], raw)
        # salida con máscara x silueta, tamaño del tablero (1/3 del final)
        fw, fh = surfaces.SURF[s][2][0] // 3, surfaces.SURF[s][2][1] // 3
        fw -= fw % 2; fh -= fh % 2
        mpng = os.path.join(WD, f"{code}_mask_{s}.png")
        Image.fromarray((mascara(code, s, (fw, fh)) * 255 + .5).astype(np.uint8)).convert("RGB").save(mpng)
        mp4 = os.path.join(WD, f"{code}_timelapse_{s}.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-loop", "1", "-i", mpng, "-filter_complex",
                        f"[0:v]scale={fw}:{fh}:flags=lanczos,format=gbrp[v];[1:v]format=gbrp[m];[v][m]blend=all_mode=multiply:shortest=1,format=yuv420p[o]",
                        "-map", "[o]", "-c:v", "libx264", "-crf", "26", "-preset", "slow", "-movflags", "+faststart", "-an", mp4], check=True)
        tiles = [recortar(kf[L], code, s, (384, 120)) for L, _ in TIMELINE]
        strip = Image.new("RGB", (384 * len(tiles), 120))
        for i, t in enumerate(tiles):
            strip.paste(t, (384 * i, 0))
        strip.save(os.path.join(WD, f"{code}_luz_{s}.jpg"), quality=82)
        log[f"{code}_{s}"] = {"seed": seed, "prompt_video": prompt_video(code, s), "relight": {L: relight(L, s, code) for L in ("tarde", "profundo", "ultima")}}
        print("ok", code, s, flush=True)
with open(os.path.join(WD, "log.json"), "a", encoding="utf-8") as fh:
    json.dump(log, fh, ensure_ascii=False, indent=1)
print("===LISTO===")
