# -*- coding: utf-8 -*-
"""Arma data/site.json para la página: escenas + contexto 2025/German + referencias del equipo + previos IA.
Lo corre GitHub Actions en cada push (y se puede correr local para probar)."""
import json, os, re, subprocess
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


def issues():
    """Pedidos (issues con etiqueta 'previo'). En GitHub Actions usa GITHUB_TOKEN; local, sin token (API pública)."""
    import urllib.request
    out, page = [], 1
    while page < 6:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page={page}",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "fnt2026-site",
                                              **({"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"]} if os.environ.get("GITHUB_TOKEN") else {})})
        try:
            items = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            print("no se pudieron leer los pedidos:", e); break
        out += items
        if len(items) < 100:
            break
        page += 1
    return out


def estado(it):
    names = {l["name"] for l in it.get("labels", [])}
    if "listo" in names: return "listo", ""
    if "error" in names: return "error", ""
    if "no-autorizado" in names: return "no autorizado", ""
    if "en-proceso" in names:
        maq = next((n.upper() for n in names if n.startswith("pc")), "")
        return "procesando", maq
    return ("cerrado", "") if it.get("state") == "closed" else ("en cola", "")


def main():
    escenas = json.load(open(os.path.join(ROOT, "escenas.json"), encoding="utf-8"))
    ctx = json.load(open(os.path.join(ROOT, "data", "contexto.json"), encoding="utf-8"))
    cmap = {s["code"]: s for b in ctx["blocks"] for s in b["scenes"]}
    out = {"generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "repo": REPO, "branch": BRANCH, "blocks": []}
    by_block = {}
    peds = {}
    for it in issues():
        body = it.get("body") or ""
        names = {l["name"] for l in it.get("labels", [])}
        if "pull_request" in it or not ("previo" in names or it.get("title", "").lower().startswith("[previo]")):
            continue
        m = re.search(r"###\s*Escena\s+(B\d\.\d\d)", body) or re.search(r"(B\d\.\d\d)", it.get("title", ""))
        if not m:
            continue
        code = m.group(1)
        sec = body.split("### Prompt", 1)[1].split("###", 1)[0].strip() if "### Prompt" in body else ""
        st, maq = estado(it)
        peds.setdefault(code, []).append({"n": it["number"], "url": it["html_url"], "autor": it["user"]["login"],
                                          "fecha": it["created_at"][:16].replace("T", " "), "prompt": sec[:400],
                                          "estado": st, "maquina": maq})
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
        # resultados de cada pedido: previos/<escena>/pedidos/<n>/meta.json
        res = {}
        pdir = os.path.join(ROOT, "previos", slug, "pedidos")
        if os.path.isdir(pdir):
            for n in os.listdir(pdir):
                mp2 = os.path.join(pdir, n, "meta.json")
                if os.path.exists(mp2):
                    m2 = json.load(open(mp2, encoding="utf-8"))
                    res[n] = {k: f"previos/{slug}/pedidos/{n}/{v}" for k, v in m2.get("files", {}).items()}
        lst = peds.get(e["code"], [])
        for pd in lst:
            pd["files"] = res.get(str(pd["n"]), {})
        item["pedidos"] = sorted(lst, key=lambda x: x["n"], reverse=True)
        by_block.setdefault(e["block"], []).append(item)
    for b in ctx["blocks"]:
        out["blocks"].append({k: b[k] for k in ("id", "name", "track", "intro")} | {"scenes": by_block.get(b["id"], [])})
    json.dump(out, open(os.path.join(ROOT, "data", "site.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_refs = sum(len(s["refs"]) for b in out["blocks"] for s in b["scenes"])
    n_prev = sum(1 for b in out["blocks"] for s in b["scenes"] if s["previos"])
    print(f"site.json: {sum(len(b['scenes']) for b in out['blocks'])} escenas, {n_refs} referencias, {n_prev} con previos")


if __name__ == "__main__":
    main()
