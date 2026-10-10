# -*- coding: utf-8 -*-
"""
FNT 2026 · Generador de previos por escena (ComfyUI local en la PC con la 4090).

Para cada escena genera:
  - Fijos de noche de luna y de atardecer para montaña izquierda, pantallas centro y montaña derecha.
    En las montañas, Flux Krea + LoRA de profundidad usa el Z-depth del cerro: el paisaje toma la forma real.
  - Si el equipo subió referencias (referencias/<escena>/), Qwen Image Edit repinta los fijos siguiendo esas imágenes.
  - Timelapse de luz para cada montaña (MiniMax H3): luna -> contraluz desde el centro -> mañana -> mediodía rápido ->
    golden hour larga desde el lado exterior -> crepúsculo -> luna (loop: el último cuadro es igual al primero).

Uso (doble clic en GENERAR_PREVIOS.bat o desde consola):
  python fnt_previos.py                 # solo escenas con referencias nuevas o sin previos
  python fnt_previos.py B1.08 B1.06     # escenas puntuales
  python fnt_previos.py --todas         # todo (varias horas)
  opciones: --sin-video  --sin-git  --motor seedream (requiere HF_KEY, experimental)
"""
import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import numpy as np
from PIL import Image, ImageOps
import comfy, graphs, prompts, surfaces

WORK = os.path.join(HERE, "_work")
REFS = os.path.join(REPO, "referencias")
PREV = os.path.join(REPO, "previos")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
STILL_LIGHTS = ["luna", "atardecer"]
H3_SIZE = {"izq": (1152, 352), "der": (1216, 352)}
FFMPEG = os.environ.get("FNT_FFMPEG", "ffmpeg")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def git(*args, check=True):
    return subprocess.run(["git", "-c", f"safe.directory={REPO.replace(chr(92), chr(47))}", "-C", REPO, *args], check=check, capture_output=True, text=True)


def load_scenes():
    with open(os.path.join(REPO, "escenas.json"), encoding="utf-8") as f:
        return json.load(f)


def scene_seed(code):
    return int(hashlib.md5(code.encode()).hexdigest()[:6], 16) + 2026


def refs_of(sc):
    if "_refs" in sc:                     # pedido puntual: solo las imágenes que vinieron con el pedido
        return list(sc["_refs"])
    d = os.path.join(REFS, sc["slug"])
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(IMG_EXT))


def refs_hash(paths):
    h = hashlib.md5()
    for p in paths:
        h.update(os.path.basename(p).encode()); h.update(str(os.path.getsize(p)).encode())
    return h.hexdigest()


def scene_hash(sc):
    """Cambia si cambia el prompt o la configuración de la escena."""
    return hashlib.md5(json.dumps(sc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]


def needs_run(sc):
    meta = os.path.join(PREV, sc["slug"], "meta.json")
    if not os.path.exists(meta):
        return True
    with open(meta, encoding="utf-8") as f:
        m = json.load(f)
    return (m.get("refs_hash") != refs_hash(refs_of(sc)) or m.get("version") != prompts_version()
            or m.get("scene_hash") != scene_hash(sc))


def prompts_version():
    with open(os.path.join(HERE, "prompts.py"), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:10]


def ref_inputs(sc):
    """Copia hasta 2 referencias a la carpeta input de ComfyUI (máx. 1024 px de lado)."""
    names = []
    for i, p in enumerate(refs_of(sc)[-2:]):
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        im.thumbnail((1024, 1024))
        names.append(comfy.put_input(im, f"fnt26_ref_{sc['code']}_{i}.png"))
    return names


# ---------------------------------------------------------------- etapa 1: Flux
def stage_flux(sc, wd, video):
    seed = scene_seed(sc["code"])
    jobs = []
    for s in ("izq", "der", "cen"):
        lights = list(sc.get("_lights", STILL_LIGHTS))
        if video and sc.get("timelapse") and s != "cen":
            lights.append("mediodia")          # base neutra para re-iluminar los cuadros guía
        for L in lights:
            jobs.append((s, L))
    for s in ("izq", "der"):
        comfy.put_input(surfaces.depth_for_generation(s), f"fnt26_depth_{s}.png")
    for s, L in jobs:
        dst = os.path.join(wd, f"flux_{L}_{s}.png")
        if os.path.exists(dst):
            continue
        w, h = surfaces.SURF[s][3]
        p = prompts.build(sc, s, L)
        if s == "cen":
            g = graphs.flux_t2i(p, w, h, seed, f"FNT26/{sc['code']}_{L}_{s}")
        else:
            g = graphs.flux_depth(f"fnt26_depth_{s}.png", p, w, h, seed, f"FNT26/{sc['code']}_{L}_{s}")
        out = comfy.run(g, os.path.join(wd, "raw"), label=f"{sc['code']} flux {L} {s}")
        Image.open(out[0]).save(dst)


def stage_flux_seedream(sc, wd, video):
    """Motor alternativo: Seedream vía API de Higgsfield (requiere HF_KEY). Experimental."""
    import seedream
    seedream.stage(sc, wd, video, refs_of(sc))


# ---------------------------------------------------------------- etapa 2: Qwen
def masked_input(path, s, name):
    im = Image.open(path).convert("RGB")
    w, h = surfaces.SURF[s][3]
    return comfy.put_input(surfaces.apply_mask(im, s, (w, h)), name)


def stage_qwen(sc, wd, video):
    seed = scene_seed(sc["code"])
    refs = ref_inputs(sc)
    if refs:   # repintar con las referencias del equipo
        for f in sorted(os.listdir(wd)):
            if not f.startswith("flux_") or not f.endswith(".png"):
                continue
            L, s = f[5:-4].split("_")
            dst = os.path.join(wd, f"refs_{L}_{s}.png")
            if os.path.exists(dst):
                continue
            n = masked_input(os.path.join(wd, f), s, f"fnt26_{sc['code']}_{L}_{s}.png")
            out = comfy.run(graphs.qwen_edit([n] + refs, prompts.refs(len(refs), L, s), seed, f"FNT26/{sc['code']}_refs_{L}_{s}"),
                            os.path.join(wd, "raw"), label=f"{sc['code']} refs {L} {s}")
            Image.open(out[0]).save(dst)
    if not (video and sc.get("timelapse")):
        return
    for s in ("izq", "der"):    # cuadros guía del timelapse a partir de la base de mediodía
        base = os.path.join(wd, f"refs_mediodia_{s}.png")
        if not os.path.exists(base):
            base = os.path.join(wd, f"flux_mediodia_{s}.png")
        n = masked_input(base, s, f"fnt26_{sc['code']}_base_{s}.png")
        for L in sorted({k for k, _ in prompts.TIMELINE}):
            dst = os.path.join(wd, f"kf_{L}_{s}.png")
            if os.path.exists(dst):
                continue
            if L == "mediodia":
                Image.open(base).save(dst); continue
            out = comfy.run(graphs.qwen_edit([n], prompts.relight(L, s), seed, f"FNT26/{sc['code']}_kf_{L}_{s}"),
                            os.path.join(wd, "raw"), label=f"{sc['code']} luz {L} {s}")
            Image.open(out[0]).save(dst)


# ---------------------------------------------------------------- etapa 3: H3
def stage_h3(sc, wd):
    if not sc.get("timelapse"):
        return
    seed = scene_seed(sc["code"])
    for s in ("izq", "der"):
        dst = os.path.join(wd, f"timelapse_{s}_raw.mp4")
        if os.path.exists(dst):
            continue
        w, h = H3_SIZE[s]
        names = {}
        for L, _ in prompts.TIMELINE:
            im = surfaces.apply_mask(Image.open(os.path.join(wd, f"kf_{L}_{s}.png")), s, (w, h))
            names[L] = comfy.put_input(im, f"fnt26_{sc['code']}_h3_{L}_{s}.png")
        guides = [(names[L], fi) for L, fi in prompts.TIMELINE[1:-1]]
        g = graphs.h3_timelapse(names["luna"], names["luna"], guides, prompts.timelapse(s, sc), w, h, prompts.LENGTH, seed,
                                f"video/FNT26/{sc['code']}_timelapse_{s}")
        out = comfy.run(g, os.path.join(wd, "raw"), timeout=5400, poll=15, label=f"{sc['code']} H3 timelapse {s}")
        os.replace(out[0], dst)


# ---------------------------------------------------------------- publicar en previos/
def publish(sc, wd, video, engine):
    od = sc.get("_out") or os.path.join(PREV, sc["slug"]); os.makedirs(od, exist_ok=True)
    files = {}
    for L in sc.get("_lights", STILL_LIGHTS):
        for s in ("izq", "cen", "der"):
            src = os.path.join(wd, f"refs_{L}_{s}.png")
            if not os.path.exists(src):
                src = os.path.join(wd, f"flux_{L}_{s}.png")
            if os.path.exists(src):
                fn = f"{L}_{s}.jpg"
                surfaces.apply_mask(Image.open(src), s).save(os.path.join(od, fn), quality=84, optimize=True, progressive=True)
                files[f"{L}_{s}"] = fn
    if video and sc.get("timelapse"):
        for s in ("izq", "der"):
            raw = os.path.join(wd, f"timelapse_{s}_raw.mp4")
            if not os.path.exists(raw):
                continue
            mp4 = os.path.join(od, f"timelapse_{s}.mp4")
            mask = os.path.join(surfaces.INS, surfaces.SURF[s][0])
            w, h = surfaces.SURF[s][2][0] // 3, surfaces.SURF[s][2][1] // 3
            w -= w % 2; h -= h % 2
            subprocess.run([FFMPEG, "-y", "-v", "error", "-i", raw, "-loop", "1", "-i", mask, "-filter_complex",
                            f"[0:v]scale={w}:{h}:flags=lanczos,format=gbrp[v];[1:v]scale={w}:{h},format=gbrp[m];"
                            f"[v][m]blend=all_mode=multiply:shortest=1,format=yuv420p[o]",
                            "-map", "[o]", "-c:v", "libx264", "-crf", "26", "-preset", "slow", "-movflags", "+faststart", "-an", mp4], check=True)
            files[f"timelapse_{s}"] = os.path.basename(mp4)
            strip = keyframe_strip(wd, s)
            strip.save(os.path.join(od, f"luz_{s}.jpg"), quality=82)
            files[f"luz_{s}"] = f"luz_{s}.jpg"
    meta = {
        "code": sc["code"], "slug": sc["slug"], "version": prompts_version(), "scene_hash": scene_hash(sc), "engine": engine,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "refs": [os.path.basename(p) for p in refs_of(sc)], "refs_hash": refs_hash(refs_of(sc)),
        "files": files, "seed": scene_seed(sc["code"]),
        "prompts": {f"{L}_{s}": prompts.build(sc, s, L) for L in sc.get("_lights", STILL_LIGHTS) for s in ("izq", "cen", "der")},
        "pedido": sc.get("_pedido"), "prompt_equipo": sc.get("extra", ""), "maquina": comfy.url(),
    }
    with open(os.path.join(od, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return od


def keyframe_strip(wd, s):
    """Tira con los cuadros guía del timelapse (para ver la secuencia de luz de un vistazo)."""
    tiles = []
    for L, fi in prompts.TIMELINE[:-1]:
        im = surfaces.apply_mask(Image.open(os.path.join(wd, f"kf_{L}_{s}.png")), s, (384, 120))
        tiles.append(im)
    strip = Image.new("RGB", (384 * len(tiles), 120))
    for i, t in enumerate(tiles):
        strip.paste(t, (384 * i, 0))
    return strip


def process_one(sc, wd, video=True, engine="comfy"):
    """Corre las tres etapas y publica una escena (lo usa la cola de pedidos, en la máquina del hilo)."""
    os.makedirs(wd, exist_ok=True)
    (stage_flux_seedream if engine == "seedream" else stage_flux)(sc, wd, video)
    stage_qwen(sc, wd, video)
    if video:
        stage_h3(sc, wd)
    return publish(sc, wd, video, engine)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("escenas", nargs="*")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--sin-video", action="store_true")
    ap.add_argument("--sin-git", action="store_true")
    ap.add_argument("--motor", default="comfy", choices=["comfy", "seedream"])
    a = ap.parse_args()
    video = not a.sin_video

    if not a.sin_git:
        log("git pull…"); git("pull", "--rebase", "--autostash")
    scenes = [s for s in load_scenes() if s.get("generar", True)]
    if a.escenas:
        want = {x.upper() for x in a.escenas}
        scenes = [s for s in scenes if s["code"].upper() in want]
    elif not a.todas:
        scenes = [s for s in scenes if needs_run(s)]
    if not scenes:
        log("No hay escenas con referencias nuevas. Nada para generar."); return
    log("Escenas:", ", ".join(s["code"] for s in scenes))
    if a.motor == "comfy" and not comfy.alive():
        sys.exit("ComfyUI no responde en " + comfy.url() + ". Abrí run_nvidia_gpu.bat y volvé a intentar.")

    dirs = {}
    for sc in scenes:
        wd = os.path.join(WORK, sc["slug"], refs_hash(refs_of(sc))[:8] + "_" + prompts_version() + "_" + scene_hash(sc))
        os.makedirs(wd, exist_ok=True); dirs[sc["code"]] = wd
    # por etapas: así cada modelo se carga una sola vez para todas las escenas
    for sc in scenes:
        (stage_flux_seedream if a.motor == "seedream" else stage_flux)(sc, dirs[sc["code"]], video)
    for sc in scenes:
        stage_qwen(sc, dirs[sc["code"]], video)
    if video:
        for sc in scenes:
            stage_h3(sc, dirs[sc["code"]])
    for sc in scenes:
        od = publish(sc, dirs[sc["code"]], video, a.motor)
        log("listo", sc["code"], "->", od)

    if not a.sin_git:
        git("add", "previos")
        st = git("status", "--porcelain", "previos").stdout.strip()
        if st:
            git("commit", "-m", f"Previos IA: {', '.join(s['code'] for s in scenes)}")
            log("git push…"); git("push")
            log("Subido. La página se actualiza en 1-2 minutos.")


if __name__ == "__main__":
    main()
