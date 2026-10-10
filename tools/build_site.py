# -*- coding: utf-8 -*-
"""Arma data/site.json para la página: escenas + contexto 2025/German + referencias del equipo + previos IA.
Lo corre GitHub Actions en cada push (y se puede correr local para probar)."""
import json, os, subprocess
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = (".jpg", ".jpeg", ".png", ".webp", ".gif")
REPO = os.environ.get("GITHUB_REPOSITORY", "iaghmtv/FNT2026")
BRANCH = os.environ.get("FNT_BRANCH", "main")


def git_info(path):
    """Autor, fecha y mensaje del commit que agregó el archivo."""
    try:
        out = subprocess.run(["git", "-c", f"safe.directory={ROOT.replace(chr(92), chr(47))}", "-C", ROOT, "log", "--diff-filter=A", "--follow", "-1", "--format=%an%x1f%ad%x1f%s",
                              "--date=format:%Y-%m-%d %H:%M", "--", path], capture_output=True, text=True, check=True).stdout.strip()
        if out:
            a, d, m = out.split("\x1f")
            if m.lower().startswith(("add files via upload", "upload")):
                m = ""
            return {"autor": a, "fecha": d, "nota": m}
    except Exception:
        pass
    return {"autor": "", "fecha": "", "nota": ""}


def main():
    escenas = json.load(open(os.path.join(ROOT, "escenas.json"), encoding="utf-8"))
    ctx = json.load(open(os.path.join(ROOT, "data", "contexto.json"), encoding="utf-8"))
    cmap = {s["code"]: s for b in ctx["blocks"] for s in b["scenes"]}
    out = {"generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "repo": REPO, "branch": BRANCH, "blocks": []}
    by_block = {}
    for e in escenas:
        slug = e["slug"]
        rdir = os.path.join(ROOT, "referencias", slug)
        refs = []
        if os.path.isdir(rdir):
            for f in sorted(os.listdir(rdir)):
                if f.lower().endswith(IMG):
                    rel = f"referencias/{slug}/{f}"
                    refs.append({"src": rel, **git_info(rel)})
        refs.sort(key=lambda r: r["fecha"], reverse=True)
        prev = None
        mp = os.path.join(ROOT, "previos", slug, "meta.json")
        if os.path.exists(mp):
            prev = json.load(open(mp, encoding="utf-8"))
            prev["files"] = {k: f"previos/{slug}/{v}" for k, v in prev.get("files", {}).items()}
            prev.pop("prompts", None)
            prev["refs_al_generar"] = prev.pop("refs", [])
            prev["desactualizado"] = sorted(prev["refs_al_generar"]) != sorted(os.path.basename(r["src"]) for r in refs)
        item = {k: e.get(k) for k in ("code", "slug", "block", "title", "time", "verse", "kind", "timelapse", "nota")}
        item["generar"] = e.get("generar", True)
        item["ctx"] = cmap.get(e["code"], {})
        item["refs"] = refs
        item["previos"] = prev
        by_block.setdefault(e["block"], []).append(item)
    for b in ctx["blocks"]:
        out["blocks"].append({k: b[k] for k in ("id", "name", "track", "intro")} | {"scenes": by_block.get(b["id"], [])})
    json.dump(out, open(os.path.join(ROOT, "data", "site.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_refs = sum(len(s["refs"]) for b in out["blocks"] for s in b["scenes"])
    n_prev = sum(1 for b in out["blocks"] for s in b["scenes"] if s["previos"])
    print(f"site.json: {sum(len(b['scenes']) for b in out['blocks'])} escenas, {n_refs} referencias, {n_prev} con previos")


if __name__ == "__main__":
    main()
