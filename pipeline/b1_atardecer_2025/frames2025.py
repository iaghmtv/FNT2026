# Extrae de los masters 2025 el cuadro más parecido a la captura del tablero (assets/2025) y lo guarda a resolución completa.
import subprocess, json, os, sys
import numpy as np
from PIL import Image
G = "G:/00 RESOLUME ROLLECT/Media/RENDERS"
W = "D:/FNT2026/WEB_FNT2026"; B = "D:/FNT2026/03_BLOQUES"
FILES = {
 "B1.01": ("B.1 1 COMP GRAL SELVATICO IZQUIERDO_DXV Normal Quality No Alpha.mov", "B.1 1 COMP GRAL SELVATICO CENTRO_DXV Normal Quality No Alpha.mov", "B.1 1 COMP GRAL SELVATICO DERECHO_DXV Normal Quality No Alpha.mov"),
 "B1.02": ("B.1 2 COMP GRAL SELVA IZQUIERDO.mov", "B.1 2 COMP GRAL SELVA CENTRO.mov", "B.1 2 COMP GRAL SELVA DERECHO.mov"),
 "B1.03": ("B.1 3 PASTORES IZQUIERDO.mov", "B.1 3 PASTORES CENTRO.mov", "B.1 3 PASTORES DERECHO.mov"),
 "B1.04": ("B1.4 Los Hijos de la Selva Guaraníes 01 IZQUIERDO_DXV Normal Quality No Alpha.mov", "B1.4 Los Hijos de la Selva Guaraníes 02 PANTALLAS CENTRO_DXV Normal Quality No Alpha.mov", "B1.4 Los Hijos de la Selva Guaraníes 01 DERECHO_DXV Normal Quality No Alpha.mov"),
 "B1.05": ("B.1 5 VIEJO RUNA IZQUIERDO.mov", "B.1 5 VIEJO RUNA  CENTRO.mov", "B.1 5 VIEJO RUNA DERECHO.mov"),
 "B1.06": ("B.1 6 JUJUY IZQUIERDO.mov", "B.1 6 JUJUY CENTRO.mov", "B.1 6 JUJUY DERECHO.mov"),
 "B1.07": ("B.1 7 Los de Salta IZQUIERDO_1.mov", "B.1 7 Los de Salta CENTRO.mov", "B.1 7 Los de Salta DERECHO.mov"),
 "B1.08": ("1.8 Los Riojanos 01 IZQUIERDO_DXV Normal Quality No Alpha.mov", "1.8 Los Riojanos 02 PANTALLAS CENTRO_DXV Normal Quality No Alpha.mov", "1.8 Los Riojanos 01 DERECHO_DXV Normal Quality No Alpha.mov"),
 "B1.09": ("B.1 9 VERDES LLANURAS IZQUIERDO.mov", "B.1 9 VERDES LLANURAS CENTRO.mov", "B.1 9 VERDES LLANURAS DERECHO.mov"),
 "B1.10": ("B1.10 Los Correntinos 01 IZQUIERDO_DXV Normal Quality No Alpha.mov", "B1.10 Los Correntinos PANTALLAS CENTRO_DXV Normal Quality No Alpha.mov", "B1.10 Los Correntinos 01 DERECHO_DXV Normal Quality No Alpha.mov"),
 "B1.11": ("B1.11- Los Cordobeses 01 IZQUIERDO_DXV Normal Quality No Alpha.mov", "B1.11- Los Cordobeses PANTALLAS CENTRO_DXV Normal Quality No Alpha.mov", "B1.11- Los Cordobeses 01 DERECHO_DXV Normal Quality No Alpha.mov"),
}
scenes = {s["code"]: s for s in json.load(open(f"{W}/escenas.json", encoding="utf-8"))}
want = sys.argv[1:] or list(FILES)
res = {}
for code in want:
    slug = scenes[code]["slug"]; dst_dir = os.path.join(B, "B1_PAISAJES", slug, "01_REFERENCIAS"); os.makedirs(dst_dir, exist_ok=True)
    for surf, fn in zip(("izq", "cen", "der"), FILES[code]):
        src = os.path.join(G, fn)
        thumb = Image.open(f"{W}/assets/2025/{code}_{surf}.jpg").convert("RGB"); tw, th = thumb.size
        tarr = np.asarray(thumb).astype(np.float32)
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vf", f"fps=2,scale={tw}:{th}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        fr = np.frombuffer(p.stdout, np.uint8).reshape(-1, th, tw, 3).astype(np.float32)
        err = ((fr - tarr) ** 2).mean((1, 2, 3)); i = int(err.argmin()); t = i / 2.0
        out = os.path.join(dst_dir, f"2025_{surf}_t{t:04.1f}s.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", out], check=True)
        sz = Image.open(out).size
        res[f"{code}_{surf}"] = {"archivo": out, "t": t, "error": round(float(err[i]), 1), "error_mediana": round(float(np.median(err)), 1), "size": sz}
        print(code, surf, f"t={t}s", "error", round(float(err[i]), 1), "(mediana", round(float(np.median(err)), 1), ")", sz, flush=True)
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames2025.json"), "w"), indent=1)
