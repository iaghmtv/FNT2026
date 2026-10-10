# -*- coding: utf-8 -*-
"""Plantillas de luz y armado de prompts.

Criterio de luz del show (nocturno):
- Look base de los fijos: noche de luna (azul) y atardecer (naranja).
- La luz SIEMPRE entra desde el centro del anfiteatro (detrás del escenario):
  montaña derecha -> la luz entra por la IZQUIERDA; montaña izquierda -> entra por la DERECHA.
  Arranca como contraluz desde atrás de la cresta, barre el relieve marcando los detalles,
  pasa rápido por el mediodía (pocas sombras) y se demora en la golden hour, que es lo que más luce en el mapping.
"""

# lado por donde entra la luz (centro) y lado contrario (exterior) en cada superficie
SIDE = {
    "izq": {"centro": "right", "exterior": "left"},
    "der": {"centro": "left", "exterior": "right"},
    "cen": {"centro": "behind", "exterior": "behind"},
}


def _from(surface, which):
    s = SIDE[surface][which]
    return "from behind the scene (backlight)" if s == "behind" else f"from the {s}"


def light(name, surface):
    c, e = _from(surface, "centro"), _from(surface, "exterior")
    return {
        "luna": (f"Moonlit night scene. Everything is bathed in cold blue moonlight coming {c}: silver-blue rim light on the ridges, "
                 "deep navy-blue shadows in every gully, strong blue color grading, local colors desaturated by the moonlight, "
                 "very dark sky with a few stars. "),
        "atardecer": (f"Golden hour sunset. Warm low orange sunlight rakes across the relief coming {e}: glowing orange and amber highlights "
                      "on every ridge, rock and plant, long violet shadows in the gullies, warm orange and magenta color grading, dusky sky. "),
        "contraluz": (f"First light of dawn coming from behind the ridge and {c}: a thin bright pink-gold rim light outlines the crest, "
                      "the slopes are still in soft blue shadow, light mist in the valleys. "),
        "manana": (f"Early morning. Low warm sunlight rakes across the relief coming {c}, long shadows reveal every gully, rock and plant. "),
        "mediodia": "Midday. High neutral sunlight from above, very short shadows, flat natural colors, clear sky. ",
        "tarde": (f"Late afternoon. The sun is lower now and rakes across the relief coming {e}, shadows lengthen and every detail pops. "),
        "crepusculo": ("Dusk. The sun has just set, violet and deep blue twilight, the last warm glow on the highest ridge, "
                       "shadows merge into blue. "),
    }[name]


QUALITY = " Natural landscape photography, highly detailed, realistic textures, no people, no text, no buildings unless described."

MOUNTAIN_RULE = ("Treat the mountain as one continuous surface texture: vegetation only as low ground cover or as a continuous canopy seen from above, "
                 "no isolated tall trees, no tall cacti, no poles, no vertical objects, no buildings. The beauty comes from color, rock texture, "
                 "strata and the raking light that sculpts every ridge and gully. ")

SURFACE_HINT = {
    "izq": "The landscape covers the whole mountain from base to summit. " + MOUNTAIN_RULE,
    "der": "The landscape covers the whole long hill from base to ridge. " + MOUNTAIN_RULE,
    "cen": "Wide panoramic landscape view. ",
}


def build(scene, surface, light_name):
    """Prompt para Flux. scene: dict de escenas.json. surface: izq/der/cen."""
    body = scene["prompt_cen"] if surface == "cen" else scene["prompt_montana"]
    if surface == "cen" and scene.get("fauna"):
        body += f" {scene['fauna']} in the middle ground."
    extra = scene.get("extra", "").strip()
    if extra:     # indicación del equipo que vino con el pedido: manda sobre la descripción base
        body = f"{extra}. Context: {body}"
    return light(light_name, surface) + SURFACE_HINT[surface] + body + QUALITY


KEEP = (" Keep every rock, plant, ridge, gully and the whole composition exactly the same; only the lighting, shadows and colors change. "
        "Keep the black background pure black.")


def relight(light_name, surface):
    """Instrucción para Qwen Image Edit: re-ilumina el mismo cuadro (cuadros guía del timelapse)."""
    return "Relight this exact landscape. " + light(light_name, surface) + KEEP


def refs(n, light_name, surface):
    plural = "s" if n > 1 else ""
    imgs = ", ".join(f"image {i + 2}" for i in range(n))
    return (f"Repaint image 1 so that its landscape, vegetation, rocks, textures and color palette follow the reference image{plural} ({imgs}). "
            "Keep the exact silhouette, relief, composition and framing of image 1. "
            + light(light_name, surface) + "Keep the black background pure black. Photorealistic.")


# Timelapse: cuadros guía y en qué cuadro caen (243 cuadros = 10,1 s a 24 fps).
# Mediodía pasa rápido; la golden hour (tarde -> atardecer) dura mucho más.
TIMELINE = [
    ("luna", 0),
    ("contraluz", 26),
    ("manana", 62),
    ("mediodia", 88),
    ("tarde", 112),
    ("atardecer", 168),
    ("crepusculo", 214),
    ("luna", 242),
]
LENGTH = 243


def timelapse(surface, scene):
    c, e = _from(surface, "centro"), _from(surface, "exterior")
    return ("Static locked-off camera, no camera movement: a time-lapse of one full day of light over this landscape. "
            f"It starts at night in blue moonlight. Dawn breaks from behind the ridge {c}: a thin rim of pink-gold light outlines the crest, "
            f"then the low sun rakes across the relief {c} and long shadows sweep slowly over every gully, rock and plant, revealing the details. "
            "Midday passes quickly with short shadows. Then the light slows down: a long warm golden hour "
            f"{e}, glowing orange highlights and long violet shadows crawling across the slopes, lingering. "
            "Then violet dusk and finally night with blue moonlight again, exactly like the first frame. "
            f"Gentle wind in the vegetation, cloud shadows drifting over the slopes. {scene.get('timelapse_extra', '')} "
            "The black background stays pure black. Smooth continuous light transition, no cuts.")
