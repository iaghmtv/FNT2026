# -*- coding: utf-8 -*-
"""Cliente de la API de ComfyUI por HTTP (sirve igual para la PC local y para otra PC de la red).

Cada hilo trabaja contra una ComfyUI: comfy.use("http://192.168.1.38:8188") fija la máquina del hilo actual.
Por defecto usa FNT_COMFY_URL o la local."""
import json, os, threading, time, uuid, urllib.request, urllib.error, urllib.parse
from io import BytesIO

DEFAULT = os.environ.get("FNT_COMFY_URL", "http://127.0.0.1:8188")
_local = threading.local()
REQUIRED = {
    "diffusion_models": ["flux1-krea-dev_fp8_scaled.safetensors", "qwen_image_edit_2511_fp8mixed.safetensors",
                         "minimax_h3_fl2va_pruned_int8_convrot.safetensors"],
    "loras": ["flux1-depth-dev-lora.safetensors", "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
              "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"],
}


def use(url):
    _local.url = url.rstrip("/")


def url():
    return getattr(_local, "url", DEFAULT)


def _get(path, base=None, timeout=10):
    return urllib.request.urlopen((base or url()) + path, timeout=timeout).read()


def alive(base=None):
    try:
        _get("/system_stats", base, 3)
        return True
    except Exception:
        return False


def idle(base=None):
    """True si la ComfyUI responde y no tiene nada corriendo ni en cola."""
    try:
        q = json.loads(_get("/queue", base, 5))
        return not q.get("queue_running") and not q.get("queue_pending")
    except Exception:
        return False


def idle_stable(base=None, checks=5, interval=3):
    """Libre de verdad: la cola vacía en varias lecturas seguidas (entre paso y paso de un trabajo
    la cola queda vacía un instante y no queremos meternos en el medio)."""
    for i in range(checks):
        if not idle(base):
            return False
        if i < checks - 1:
            time.sleep(interval)
    return True


def missing_models(base=None):
    falta = []
    for folder, names in REQUIRED.items():
        try:
            have = set(json.loads(_get(f"/models/{folder}", base, 10)))
        except Exception:
            have = set()
        falta += [n for n in names if n not in have]
    return falta


def put_input(pil_img, name):
    """Sube una imagen PIL a la carpeta input de la ComfyUI del hilo (POST /upload/image)."""
    buf = BytesIO(); pil_img.save(buf, format="PNG")
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            "Content-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url() + "/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return (r.get("subfolder") + "/" if r.get("subfolder") else "") + r["name"]


def _download(item, dest_dir):
    q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")})
    data = _get("/view?" + q, timeout=600)
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, item["filename"])
    with open(dst, "wb") as f:
        f.write(data)
    return dst


def run(graph, dest_dir, timeout=3600, poll=5, label=""):
    """Encola el grafo en la ComfyUI del hilo, espera y descarga imágenes/videos a dest_dir."""
    body = json.dumps({"prompt": graph, "client_id": "fnt2026"}).encode()
    req = urllib.request.Request(url() + "/prompt", data=body, headers={"Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ComfyUI rechazó el grafo {label}: {e.read().decode()[:2000]}")
    pid = r["prompt_id"]
    t0 = time.time()
    while True:
        time.sleep(poll)
        h = json.loads(_get(f"/history/{pid}", timeout=60))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI error {label}: {json.dumps(st.get('messages'))[-2000:]}")
            outs = []
            for o in h[pid]["outputs"].values():
                for key in ("images", "videos", "gifs"):
                    for it in o.get(key, []):
                        if it.get("type") == "temp":
                            continue
                        outs.append(_download(it, dest_dir))
            print(f"  [{label}] {url().split('//')[1]} {time.time() - t0:.0f}s -> {len(outs)} archivo(s)", flush=True)
            return outs
        if time.time() - t0 > timeout:
            raise TimeoutError(f"ComfyUI timeout {label}")
