# -*- coding: utf-8 -*-
"""
FNT 2026 · Cola de pedidos de previos (corre en la GHM17 con FNT_COLA.bat).

Cada pedido es un issue del repo creado desde la página ("Pedir previo con prompt"): escena, prompt,
imágenes de referencia y qué luces generar. La cola:
  1. revisa los issues abiertos con la etiqueta "previo" cada 30 s;
  2. acepta solo pedidos de miembros del repo (dueño o colaboradores invitados);
  3. busca una ComfyUI desocupada (sin nada corriendo ni en cola) entre las máquinas de maquinas.json
     y le asigna el pedido; si las dos están libres, procesa dos pedidos a la vez;
  4. al terminar sube las imágenes del pedido a referencias/<escena>/ y los previos a previos/<escena>/pedidos/<n>/,
     comenta en el issue con los resultados y lo cierra.

Necesita en pipeline/.env (no se sube al repo):
  FNT_GH_TOKEN=<token fine-grained de GitHub con permiso Issues: read/write sobre iaghmtv/FNT2026>
El push de git usa las credenciales que ya tiene Windows (Git Credential Manager).
"""
import json, os, re, sys, threading, time, traceback, urllib.request, urllib.error
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import comfy
import fnt_previos as fp

REPO_SLUG = os.environ.get("FNT_REPO", "iaghmtv/FNT2026")
API = "https://api.github.com/repos/" + REPO_SLUG
PAGES = "https://" + REPO_SLUG.split("/")[0].lower() + ".github.io/" + REPO_SLUG.split("/")[1] + "/"
LABEL = "previo"
ALLOWED = {"OWNER", "MEMBER", "COLLABORATOR"}
POLL = 30
git_lock = threading.Lock()
busy = {}            # nombre de máquina -> número de pedido


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_env():
    p = os.path.join(HERE, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def gh(method, path, data=None):
    req = urllib.request.Request(API + path if path.startswith("/") else path, method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": "Bearer " + os.environ["FNT_GH_TOKEN"],
                                          "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                          "User-Agent": "fnt2026-cola"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return json.loads(body) if body else None


def machines():
    with open(os.path.join(HERE, "maquinas.json"), encoding="utf-8") as f:
        return json.load(f)


def free_machine():
    for m in machines():
        if m["nombre"] in busy or not m.get("activa", True):
            continue
        if comfy.idle_stable(m["url"]):
            return m
    return None


# ------------------------------------------------------------------ lectura del pedido
def sections(body):
    """Issue form -> {título de sección: texto}."""
    out, cur = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.*)", line)
        if m:
            cur = m.group(1).strip(); out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def parse(issue, scenes):
    sec = sections(issue.get("body"))
    esc = sec.get("Escena", "")
    m = re.search(r"(B\d\.\d\d)", esc) or re.search(r"(B\d\.\d\d)", issue.get("title", ""))
    code = m.group(1).upper() if m else ""
    sc = next((s for s in scenes if s["code"].upper() == code), None)
    if not sc:
        raise ValueError(f"No reconozco la escena «{esc}».")
    prompt = sec.get("Prompt", "").replace("_No response_", "").strip()
    refs_md = sec.get("Imágenes de referencia", "") + "\n" + sec.get("Prompt", "")
    urls = re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", refs_md) + re.findall(r'<img[^>]+src="(https?://[^"]+)"', refs_md)
    luz = sec.get("Qué generar", "")
    lights = [k for k, t in (("luna", "luna"), ("atardecer", "atardecer")) if re.search(r"\[x\][^\n]*" + t, luz, re.I)] or ["luna", "atardecer"]
    timelapse = bool(re.search(r"\[x\][^\n]*timelapse", luz, re.I)) and sc.get("timelapse", False)
    return sc, prompt, list(dict.fromkeys(urls)), lights, timelapse


def download_refs(urls, sc, n, author):
    """Baja las imágenes del pedido a referencias/<escena>/ (quedan como referencias de la escena)."""
    d = os.path.join(fp.REFS, sc["slug"]); os.makedirs(d, exist_ok=True)
    paths = []
    for i, u in enumerate(urls[:4]):
        req = urllib.request.Request(u, headers={"Authorization": "Bearer " + os.environ["FNT_GH_TOKEN"], "User-Agent": "fnt2026-cola"})
        with urllib.request.urlopen(req, timeout=120) as r:
            ctype = r.headers.get("Content-Type", "")
            data = r.read()
        ext = ".png" if "png" in ctype else ".webp" if "webp" in ctype else ".jpg"
        safe = re.sub(r"[^A-Za-z0-9_-]", "", author)[:20] or "equipo"
        p = os.path.join(d, f"pedido{n}_{safe}_{i + 1}{ext}")
        with open(p, "wb") as f:
            f.write(data)
        paths.append(p)
    return paths


# ------------------------------------------------------------------ trabajo
def comment(n, text):
    gh("POST", f"/issues/{n}/comments", {"body": text})


def labels(n, add=(), remove=()):
    for l in remove:
        try:
            gh("DELETE", f"/issues/{n}/labels/{urllib.request.quote(l)}")
        except urllib.error.HTTPError:
            pass
    if add:
        gh("POST", f"/issues/{n}/labels", {"labels": list(add)})


def git_publish(paths, msg):
    with git_lock:
        fp.git("pull", "--rebase", "--autostash", check=False)
        fp.git("add", *paths)
        if fp.git("status", "--porcelain", *paths).stdout.strip():
            fp.git("commit", "-m", msg)
            fp.git("push")


def work(issue, m, scenes):
    n = issue["number"]; author = issue["user"]["login"]
    comfy.use(m["url"])
    try:
        sc, prompt, urls, lights, timelapse = parse(issue, scenes)
        log(f"#{n} {sc['code']} -> {m['nombre']} · luces {lights} · timelapse {timelapse} · {len(urls)} imagen(es)")
        refs = download_refs(urls, sc, n, author) if urls else []
        job = dict(sc, extra=prompt, timelapse=timelapse, _refs=refs, _lights=lights, _pedido=n,
                   _out=os.path.join(fp.PREV, sc["slug"], "pedidos", str(n)))
        wd = os.path.join(fp.WORK, sc["slug"], f"pedido_{n}")
        od = fp.process_one(job, wd, video=timelapse)
        with open(os.path.join(od, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        meta.update({"autor": author, "issue": issue["html_url"], "maquina": m["nombre"]})
        with open(os.path.join(od, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        rel = [os.path.relpath(od, fp.REPO)] + [os.path.relpath(p, fp.REPO) for p in refs]
        git_publish(rel, f"Pedido #{n} ({sc['code']}) de {author}: previos en {m['nombre']}")
        raw = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/" + os.path.relpath(od, fp.REPO).replace("\\", "/") + "/"
        imgs = "\n".join(f"**{k.replace('_', ' ')}**\n\n![{k}]({raw}{v})" for k, v in meta["files"].items() if v.endswith(".jpg") and not k.startswith("luz"))
        vids = "\n".join(f"- [{k.replace('_', ' ')}]({raw}{v})" for k, v in meta["files"].items() if v.endswith(".mp4"))
        comment(n, f"✅ Listo en **{m['nombre']}** ({meta['generated_at']}).\n\n{imgs}\n\n{vids}\n\nEn la página: {PAGES}#{sc['code']}")
        labels(n, add=["listo"], remove=["en-proceso", m["nombre"].lower()])
        gh("PATCH", f"/issues/{n}", {"state": "closed"})
        log(f"#{n} listo")
    except Exception as e:
        log(f"#{n} ERROR: {e}"); traceback.print_exc()
        try:
            comment(n, f"⚠️ No se pudo generar en {m['nombre']}: `{str(e)[:400]}`\n\nRevisá el pedido y quitá la etiqueta `error` para reintentar.")
            labels(n, add=["error"], remove=["en-proceso", m["nombre"].lower()])
        except Exception:
            pass
    finally:
        busy.pop(m["nombre"], None)


LABELS = {"previo": "7fa8e8", "en-proceso": "e6b54a", "listo": "3f8a3a", "error": "d06a5a", "no-autorizado": "7b736a"}


def ensure_labels():
    have = {l["name"] for l in (gh("GET", "/labels?per_page=100") or [])}
    todo = dict(LABELS, **{m["nombre"].lower(): "e8843a" for m in machines()})
    for name, color in todo.items():
        if name not in have:
            try:
                gh("POST", "/labels", {"name": name, "color": color})
            except urllib.error.HTTPError:
                pass


def pending():
    items = gh("GET", "/issues?state=open&per_page=100&sort=created&direction=asc") or []
    out = []
    for it in items:
        names = {l["name"] for l in it.get("labels", [])}
        if "pull_request" in it or not (LABEL in names or it.get("title", "").lower().startswith("[previo]")):
            continue
        if LABEL not in names:
            labels(it["number"], add=[LABEL])
        if names & {"en-proceso", "listo", "error"}:
            continue
        if it.get("author_association") not in ALLOWED:
            if "no-autorizado" not in names:
                comment(it["number"], "Este pedido no se procesa: solo se aceptan pedidos de miembros del equipo invitados al repo.")
                labels(it["number"], add=["no-autorizado"])
            continue
        out.append(it)
    return out


def main():
    load_env()
    if not os.environ.get("FNT_GH_TOKEN"):
        sys.exit("Falta FNT_GH_TOKEN en pipeline/.env (ver LEEME_COLA.md).")
    scenes = fp.load_scenes()
    ensure_labels()
    log("Cola FNT 2026 · máquinas:", ", ".join(f"{m['nombre']} ({m['url']})" for m in machines()))
    for m in machines():
        if not comfy.alive(m["url"]):
            log(f"  {m['nombre']}: ComfyUI no responde (se reintenta en cada vuelta)")
        else:
            falta = comfy.missing_models(m["url"])
            log(f"  {m['nombre']}: OK" + (f" · FALTAN MODELOS: {falta}" if falta else ""))
    while True:
        try:
            for it in pending():
                if any(v == it["number"] for v in busy.values()):
                    continue
                m = free_machine()
                if not m:
                    break
                busy[m["nombre"]] = it["number"]
                labels(it["number"], add=["en-proceso", m["nombre"].lower()])
                comment(it["number"], f"⏳ Tomado por **{m['nombre']}**. Te aviso acá cuando esté.")
                threading.Thread(target=work, args=(it, m, scenes), daemon=True).start()
        except Exception as e:
            log("vuelta con error:", e)
        time.sleep(POLL)


if __name__ == "__main__":
    main()
