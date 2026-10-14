"""Antes de publicar a mano: si una imagen de previos se reemplazo con otra extension (atardecer_izq.png en vez de .jpg),
la convierte al nombre que espera el tablero y borra la otra. Lista lo que cambio."""
import json, os, subprocess
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALT = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")

for slug in sorted(os.listdir(os.path.join(ROOT, "previos"))):
    d = os.path.join(ROOT, "previos", slug); mp = os.path.join(d, "meta.json")
    if not os.path.isfile(mp):
        continue
    for nombre in json.load(open(mp, encoding="utf-8")).get("files", {}).values():
        base, ext = os.path.splitext(nombre)
        if ext.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        for a in ALT:
            otro = os.path.join(d, base + a)
            if a != ext.lower() and os.path.isfile(otro):
                im = Image.open(otro).convert("RGB")
                im.save(os.path.join(d, nombre), quality=90, progressive=True)
                os.remove(otro)
                print(f"convertido: previos/{slug}/{base + a} -> {nombre} ({im.width}x{im.height})")

out = subprocess.run(["git", "-c", "safe.directory=*", "status", "--short", "--", "previos", "referencias"],
                     cwd=ROOT, capture_output=True, text=True).stdout.strip()
print("\nCambios para publicar:\n" + (out or "  (ninguno)"))
