# -*- coding: utf-8 -*-
"""Cliente mínimo de la API de ComfyUI local (submit, espera, copia de salidas)."""
import json, os, shutil, time, urllib.request, urllib.error

COMFY = os.environ.get("FNT_COMFY_URL", "http://127.0.0.1:8188")
COMFY_ROOT = os.environ.get("FNT_COMFY_ROOT", r"E:\ComfyUI\ComfyUI_windows_portable\ComfyUI")
COMFY_IN = os.path.join(COMFY_ROOT, "input")
COMFY_OUT = os.path.join(COMFY_ROOT, "output")


def alive():
    try:
        urllib.request.urlopen(COMFY + "/system_stats", timeout=3)
        return True
    except Exception:
        return False


def put_input(pil_img, name):
    """Guarda una imagen PIL en la carpeta input de ComfyUI y devuelve el nombre."""
    os.makedirs(COMFY_IN, exist_ok=True)
    pil_img.save(os.path.join(COMFY_IN, name))
    return name


def run(graph, dest_dir, timeout=3600, poll=5, label=""):
    """Encola el grafo, espera y copia imágenes/videos a dest_dir. Devuelve la lista de rutas."""
    body = json.dumps({"prompt": graph, "client_id": "fnt2026"}).encode()
    req = urllib.request.Request(COMFY + "/prompt", data=body, headers={"Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ComfyUI rechazó el grafo {label}: {e.read().decode()[:2000]}")
    pid = r["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(poll)
        h = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=60).read())
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI error {label}: {json.dumps(st.get('messages'))[-2000:]}")
            outs = []
            os.makedirs(dest_dir, exist_ok=True)
            for o in h[pid]["outputs"].values():
                for key in ("images", "videos", "gifs"):
                    for it in o.get(key, []):
                        if it.get("type") == "temp":
                            continue
                        src = os.path.join(COMFY_OUT, it.get("subfolder", ""), it["filename"])
                        dst = os.path.join(dest_dir, it["filename"])
                        shutil.copy(src, dst)
                        outs.append(dst)
            print(f"  [{label}] {time.time() - t0:.0f}s -> {len(outs)} archivo(s)", flush=True)
            return outs
        if time.time() - t0 > timeout:
            raise TimeoutError(f"ComfyUI timeout {label}")
