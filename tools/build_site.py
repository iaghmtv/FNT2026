# -*- coding: utf-8 -*-
"""Arma data/site.json para la página: escenas + contexto 2025/German + referencias del equipo + previos IA.
Lo corre GitHub Actions en cada push (y se puede correr local para probar)."""
import hashlib, json, os, re, subprocess
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = (".jpg", ".jpeg", ".png", ".webp", ".gif")
REPO = os.environ.get("GITHUB_REPOSITORY", "iaghmtv/FNT2026")
BRANCH = os.environ.get("FNT_BRANCH", "main")


def ver(rel):
    """Agrega ?v=<hash del contenido> para que una imagen reemplazada con el mismo nombre se vea al instante (sin caché vieja)."""
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return rel
    with open(p, "rb") as f:
        return rel + "?v=" + hashlib.md5(f.read()).hexdigest()[:8]


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


def _seccion(body, nombre):
    m = re.search(r"###\s*" + nombre + r"\s*\n(.*?)(?=\n###\s|\Z)", body, re.S)
    v = m.group(1).strip() if m else ""
    return "" if v in ("_No response_", "None") else v


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _hora(txt):
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.\s?m\.|p\.\s?m\.|hs|h)\b", txt or "", re.I)
    if not m:
        return ""
    h = int(m.group(1)); mi = int(m.group(2) or 0); suf = m.group(3).lower().replace(".", "").replace(" ", "")
    if suf == "pm" and h < 12:
        h += 12
    return f"{h}:{mi:02d}" if 0 <= h < 24 and mi < 60 else ""


def _fecha(txt):
    m = re.search(r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")(?:\s+(?:de\s+)?(20\d\d))?", txt or "", re.I)
    if m:
        return f"{int(m.group(3) or 2026):04d}-{MESES.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(20\d\d)-(\d{1,2})-(\d{1,2})", txt or "")
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", txt or "")
    if m:
        y = int(m.group(3)) if m.group(3) else 2026
        y = y + 2000 if y < 100 else y
        return f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


def calendario(todos):
    """Calendario: notas fijas de data/calendario.json + issues '[Nota]' del formulario nota.yml (cerrada = hecha)."""
    cp = os.path.join(ROOT, "data", "calendario.json")
    cal = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {"desde": "", "hasta": "", "notas": []}
    notas = [dict(n, fuente="tablero") for n in cal.get("notas", [])]
    TIPOS = {"entrega": "entrega", "revis": "revision", "correc": "correccion"}
    for it in todos:
        names = {l["name"] for l in it.get("labels", [])}
        body = it.get("body") or ""
        es_nota = "calendario" in names or "[nota]" in it.get("title", "").lower() or ("### Fecha" in body and "### Tipo" in body)
        if "pull_request" in it or not es_nota or it["number"] in cal.get("notas_ignoradas", []):
            continue
        f = _fecha(_seccion(body, "Fecha")) or _fecha(it.get("title", "")) or it["created_at"][:10]
        t = _seccion(body, "Tipo").lower()
        tipo = next((v for k, v in TIPOS.items() if k in t), "otro")
        esc = _seccion(body, "Escena"); m = re.search(r"B\d\.\d\d", esc)
        titulo = re.sub(r"\[nota\]\s*(20\d\d-\d\d-\d\d)?", "", it.get("title", ""), flags=re.I).strip(" -:·")
        det = _seccion(body, "Detalle")
        texto = (titulo + ": " + det) if (titulo and det and titulo.lower() not in det.lower()) else (det or titulo)
        hora = _hora(det) or _hora(it.get("title", ""))
        resp = _seccion(body, "Responsable")
        notas.append({"fecha": f, "tipo": tipo, "escena": m.group(0) if m else ("General" if esc else ""), "texto": texto[:500],
                      "responsable": resp[:60], "hora": hora, "autor": it["user"]["login"], "url": it["html_url"], "n": it["number"],
                      "hecho": it.get("state") == "closed", "fuente": "nota"})
    notas.sort(key=lambda n: (n["fecha"], n.get("n", 0)))
    return {"desde": cal.get("desde", ""), "hasta": cal.get("hasta", ""), "notas": notas}


def main():
    escenas = json.load(open(os.path.join(ROOT, "escenas.json"), encoding="utf-8"))
    ctx = json.load(open(os.path.join(ROOT, "data", "contexto.json"), encoding="utf-8"))
    cmap = {s["code"]: s for b in ctx["blocks"] for s in b["scenes"]}
    op = os.path.join(ROOT, "data", "ocultos.json")       # imágenes que no se muestran en el tablero
    ocultos = json.load(open(op, encoding="utf-8")) if os.path.exists(op) else {}
    oprev, oger = ocultos.get("previos", {}), ocultos.get("german_por_tipo", {})
    for code, kinds in oger.items():
        if code in cmap:
            cmap[code] = dict(cmap[code], img26=[x for x in cmap[code].get("img26", []) if x.get("kind") not in kinds])
    ap = os.path.join(ROOT, "data", "audio.json")
    audio = json.load(open(ap, encoding="utf-8")) if os.path.exists(ap) else {"escenas": {}, "finales": [], "sin_track": {}}
    out = {"generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "repo": REPO, "branch": BRANCH, "blocks": []}
    by_block = {}
    peds = {}
    todos = issues()
    out["calendario"] = calendario(todos)
    for it in todos:
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
            prev["files"] = {k: ver(f"previos/{slug}/{v}") for k, v in prev.get("files", {}).items() if k not in oprev.get(e["code"], [])}
            prev.pop("prompts", None)
            for im in (prev.get("propuesta") or {}).get("imgs", []):   # propuesta en el lugar de un previo
                im["src"] = ver(im["src"])
                if im.get("poster"):
                    im["poster"] = ver(im["poster"])
            if prev.get("animacion"):        # render final de la escena (videos por montaña)
                an = prev["animacion"]
                for k in ("izq", "cen", "der"):
                    if an.get(k):
                        an[k] = ver(f"previos/{slug}/{an[k]}")
            prev["refs_al_generar"] = prev.pop("refs", [])
            prev["desactualizado"] = sorted(prev["refs_al_generar"]) != sorted(os.path.basename(r["src"]) for r in refs)
        item = {k: e.get(k) for k in ("code", "slug", "block", "title", "time", "verse", "kind", "timelapse", "nota")}
        item["generar"] = e.get("generar", True)
        item["ctx"] = cmap.get(e["code"], {})
        item["audio"] = audio["escenas"].get(e["code"])
        item["audio_nota"] = audio.get("sin_track", {}).get(e["code"], "")
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
    out["audio_finales"] = audio.get("finales", [])
    json.dump(out, open(os.path.join(ROOT, "data", "site.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_refs = sum(len(s["refs"]) for b in out["blocks"] for s in b["scenes"])
    n_prev = sum(1 for b in out["blocks"] for s in b["scenes"] if s["previos"])
    print(f"site.json: {sum(len(b['scenes']) for b in out['blocks'])} escenas, {n_refs} referencias, {n_prev} con previos")


if __name__ == "__main__":
    main()
