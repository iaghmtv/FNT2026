# -*- coding: utf-8 -*-
"""Información de los tracks del show por escena: duración, formato, sonoridad, forma de onda.

Se corre en la PC que tiene los audios (lee la carpeta de tracks del Fogón):
  python tools/audio_info.py "G:/DD3/FT2025_dd3/Tracks del FOGON"
Escribe data/audio.json y assets/audio/<escena>_onda.png, copia los MP3 originales a audio/ (no se sube)
y hace copias de 128 kbps en audio_web/, que sí se publican: el reproductor del tablero usa esas (pedido del 15/10).
"""
import json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = os.environ.get("FNT_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FNT_FFPROBE", "ffprobe")

# número de track en la carpeta -> escenas que lo usan (orden del guion)
MAPA = {
    "00": ["B0.00", "B0.01"], "1": ["B1.01"], "2": ["B1.02"], "3": ["B1.03"], "4": ["B1.04"], "5": ["B1.05"],
    "6": ["B1.06"], "7": ["B1.07"], "8": ["B1.08"], "9": ["B1.09"], "10": ["B1.10"], "11": ["B1.11"],
    "12": ["B2.02"], "13": ["B3.01"], "14": ["B3.02"], "15": ["B3.03"], "16": ["B3.04"], "17": ["B3.05"],
    "18": ["B3.06"], "19": ["B3.07"], "20": ["B3.08"], "21": ["B3.09"], "22": ["B3.10"], "23": ["B3.11"],
    "24": ["B3.12"], "25": ["B4.01"], "26": ["B4.02"], "27": ["B5.01"], "28.1": ["B5.02"], "29": ["B5.03"],
    "30": ["B6.01"], "31": ["B6.02"],
}
FINALES = ["32", "33", "34"]          # marchas de la desconcentración
NOTAS = {"cambiar": "Marcado para CAMBIAR en 2025", "por las dudas": "Versión «por las dudas» (alternativa)",
         "bajar despacio": "Indicación: BAJAR DESPACIO (fade lento)", "bien": "Versión marcada como buena"}
SIN_TRACK = {"B2.01": "Sin música: voz en off con apagón completo (opción de dejar solo el fogón iluminado)."}


def probe(p):
    j = json.loads(subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", p],
                                  capture_output=True, text=True, check=True).stdout)
    a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    f = j["format"]
    tags = {k.lower(): v for k, v in (f.get("tags") or {}).items()}
    return {"duracion": round(float(f["duration"]), 2), "codec": a.get("codec_name", ""),
            "kbps": round(int(f.get("bit_rate", 0)) / 1000), "hz": int(a.get("sample_rate", 0)),
            "canales": a.get("channels", 0), "mb": round(os.path.getsize(p) / 1e6, 2),
            "titulo_tag": tags.get("title", ""), "artista_tag": tags.get("artist", ""), "album_tag": tags.get("album", "")}


def loudness(p):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", p, "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr[r.stderr.rfind("Summary:"):]
    I = re.search(r"I:\s+(-?[\d.]+) LUFS", txt); LRA = re.search(r"LRA:\s+([\d.]+) LU", txt); TP = re.search(r"Peak:\s+(-?[\d.]+) dBFS", txt)
    return {"lufs": float(I.group(1)) if I else None, "lra": float(LRA.group(1)) if LRA else None, "pico_dbtp": float(TP.group(1)) if TP else None}


def waveform(p, dst):
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", p, "-filter_complex",
                    "aformat=channel_layouts=mono,showwavespic=s=1600x140:colors=0xE8843A:scale=sqrt", "-frames:v", "1", dst], check=True)


def main(src):
    files = [f for f in os.listdir(src) if f.lower().endswith((".mp3", ".wav", ".m4a"))]
    by_num = {}
    for f in files:
        m = re.match(r"^\s*([\d.]+)\s*-", f)
        if m:
            by_num[m.group(1)] = f
    os.makedirs(os.path.join(ROOT, "assets", "audio"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "audio"), exist_ok=True)
    out = {"fuente": "Tracks del FOGON (show 2025)", "escenas": {}, "finales": [], "sin_track": SIN_TRACK}

    def info(num):
        f = by_num[num]; p = os.path.join(src, f)
        nombre = re.sub(r"^\s*[\d.]+\s*-\s*track\s*", "", f, flags=re.I).rsplit(".", 1)[0].strip()
        low = f.lower()
        notas = [v for k, v in NOTAS.items() if re.search(r"\b" + k + r"\b", low)]
        d = {"track": num, "archivo": f, "nombre": nombre, "notas": notas, **probe(p), **loudness(p)}
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", f)
        shutil.copy2(p, os.path.join(ROOT, "audio", safe))
        d["audio_local"] = "audio/" + safe
        os.makedirs(os.path.join(ROOT, "audio_web"), exist_ok=True)
        web = os.path.join(ROOT, "audio_web", safe)
        subprocess.run([FFMPEG, "-nostdin", "-v", "error", "-y", "-i", p, "-map", "0:a:0", "-c:a", "libmp3lame",
                        "-b:a", f"{min(128, int(d.get('kbps') or 128))}k", "-map_metadata", "-1", web], check=True)
        d["audio_web"] = "audio_web/" + safe
        return d, p

    for num, codes in MAPA.items():
        if num not in by_num:
            print("falta track", num); continue
        d, p = info(num)
        wave = f"assets/audio/track{num.replace('.', '_')}_onda.png"
        waveform(p, os.path.join(ROOT, wave)); d["onda"] = wave
        for c in codes:
            out["escenas"][c] = d
        print(f"{num:>4} {d['nombre'][:40]:40} {d['duracion']:7.1f}s  {d['lufs']} LUFS  pico {d['pico_dbtp']} dBTP")
    for num in FINALES:
        if num in by_num:
            d, p = info(num)
            wave = f"assets/audio/track{num}_onda.png"; waveform(p, os.path.join(ROOT, wave)); d["onda"] = wave
            out["finales"].append(d)
    with open(os.path.join(ROOT, "data", "audio.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("data/audio.json:", len(out["escenas"]), "escenas,", len(out["finales"]), "pistas finales")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "G:/DD3/FT2025_dd3/Tracks del FOGON")
