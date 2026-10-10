# -*- coding: utf-8 -*-
"""Motor alternativo (EXPERIMENTAL): Seedream vía API de Higgsfield, como etapa 1 en lugar de Flux.

Requisitos en la PC de render:
  pip install higgsfield-client pillow numpy
  variable de entorno HF_KEY="<api-key-id>:<api-key-secret>"   (se crea en cloud.higgsfield.ai)
  opcional: HF_SEEDREAM_MODEL (por defecto bytedance/seedream/v4/edit) y HF_SEEDREAM_IMAGE_ARG (por defecto image_urls)

Para cada superficie le pasa a Seedream el render del cerro (clay iluminado + Z-depth en los canales) y hasta
2 referencias del equipo, con el mismo prompt de luz. La salida se recorta con la máscara igual que con Flux.
La documentación pública de Higgsfield no confirma el nombre del argumento de imágenes del modelo de edición:
si la primera corrida falla, el error lo indica y se ajusta HF_SEEDREAM_IMAGE_ARG sin tocar el código.
"""
import io, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prompts, surfaces

MODEL = os.environ.get("HF_SEEDREAM_MODEL", "bytedance/seedream/v4/edit")
IMAGE_ARG = os.environ.get("HF_SEEDREAM_IMAGE_ARG", "image_urls")


def _client():
    if not os.environ.get("HF_KEY") and not os.environ.get("HF_API_KEY"):
        sys.exit("Motor seedream: falta la variable HF_KEY (api-key-id:api-key-secret de cloud.higgsfield.ai).")
    import higgsfield_client
    return higgsfield_client


def _guide(s):
    """Guía de forma para Seedream: clay del cerro con el relieve marcado, recortado con la máscara."""
    w, h = surfaces.SURF[s][3]
    if s == "cen":
        return None
    clay = Image.open(os.path.join(surfaces.INS, f"clay_{s}_{surfaces.SURF[s][2][0]}x{surfaces.SURF[s][2][1]}.png")).convert("RGB").resize((w, h))
    depth = surfaces.depth_for_generation(s).convert("L").resize((w, h))
    g = (np.array(clay).astype(np.float32) * 0.6 + np.array(depth)[..., None].astype(np.float32) * 0.4)
    g = surfaces.apply_mask(Image.fromarray(g.clip(0, 255).astype(np.uint8)), s, (w, h))
    return _pad(g)


CANVAS = 21 / 9


def _pad(im):
    """Centra la franja de la montaña en un lienzo 21:9 negro (el formato que devuelve Seedream)."""
    w, h = im.size
    H = round(w / CANVAS)
    c = Image.new("RGB", (w, H)); c.paste(im, (0, (H - h) // 2))
    return c


def _download(url):
    import urllib.request
    return Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=120).read())).convert("RGB")


def stage(sc, wd, video, refs):
    hf = _client()
    ref_urls = []
    for p in refs[-2:]:
        im = Image.open(p).convert("RGB"); im.thumbnail((1536, 1536))
        ref_urls.append(hf.upload_image(im, format="jpeg"))
    lights = list(prompts.STILL_LIGHTS) if hasattr(prompts, "STILL_LIGHTS") else ["luna", "atardecer"]
    for s in ("izq", "der", "cen"):
        ls = lights + (["mediodia"] if video and sc.get("timelapse") and s != "cen" else [])
        guide = _guide(s)
        guide_url = hf.upload_image(guide, format="png") if guide is not None else None
        for L in ls:
            dst = os.path.join(wd, f"flux_{L}_{s}.png")
            if os.path.exists(dst):
                continue
            p = prompts.build(sc, s, L)
            if guide_url:
                p = ("Image 1 is a grey render of the real mountain seen from the audience: keep EXACTLY its silhouette, ridges, gullies and relief, "
                     "and paint this landscape onto it. " + p)
            imgs = ([guide_url] if guide_url else []) + ref_urls
            args = {"prompt": p, "resolution": "2K", "aspect_ratio": "21:9"}
            if imgs:
                args[IMAGE_ARG] = imgs
            model = MODEL if imgs else "bytedance/seedream/v4/text-to-image"
            print(f"  [{sc['code']} seedream {L} {s}] {model}", flush=True)
            r = hf.subscribe(model, arguments=args)
            out = _download(r["images"][0]["url"])
            w, h = surfaces.SURF[s][3]
            # Seedream devuelve 21:9: se lleva al lienzo de la guía y se recorta la franja de la montaña
            H = round(w / CANVAS)
            out = out.resize((w, H), Image.LANCZOS)
            top = (H - h) // 2
            out.crop((0, top, w, top + h)).save(dst)
