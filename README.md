# FNT 2026 · Tablero de referencias y previos IA

Fiesta Nacional de la Tradición (Jáchal) · El Fogón de los Arrieros · producción visual GHM.

Página: **https://iaghmtv.github.io/FNT2026/**

## Para el equipo (Gabi, Valentín, Analía, German, …)

1. Entrá a la página y buscá la escena.
2. Pestaña **Referencias** → **Subir referencia**. Se abre GitHub en la carpeta de esa escena (`referencias/<escena>/`).
3. Arrastrá las imágenes y en el mensaje del commit contá qué querés tomar de cada una (luz, paleta, vegetación, roca…).
4. **Commit changes**. En 1–2 minutos aparecen en la página con tu nombre.

Hace falta un usuario de GitHub con acceso de escritura al repo (invitación desde *Settings → Collaborators*).

## Criterio visual

- El show es de noche: paisajes en **luz de luna azul** y **atardeceres naranjas**.
- El fuerte del mapping es **color e iluminación** que transforman la montaña, más elementos claros y definidos.
- Sin elementos altos en las laderas (cactus, árboles, postes): desde el fondo de las tribunas se ven acostados.
  Los elementos definidos van en las **zonas aptas** (`assets/zonas/`), calculadas desde el Z-depth de la cámara de cada proyector.
- Paso de luz: entra **desde el centro** (montaña derecha por la izquierda, montaña izquierda por la derecha),
  arranca como contraluz detrás de la cresta, **pasa rápido por el mediodía** y **se demora en la golden hour**.
- Cascadas: las rehace Diego en Blender 3D. Banderas (B2.2 / B4.2): las resuelve German.

## Generar previos (PC de render con la RTX 4090)

Doble clic en `GENERAR_PREVIOS.bat` (abre ComfyUI si no está abierto). Baja las referencias nuevas, genera y sube los previos.

```
GENERAR_PREVIOS.bat               escenas con referencias nuevas o sin previos
GENERAR_PREVIOS.bat B1.08 B1.06   escenas puntuales
GENERAR_PREVIOS.bat --todas       todas (varias horas)
opciones: --sin-video  --sin-git  --motor seedream
```

Por escena:

| Etapa | Modelo (ComfyUI local) | Qué hace |
|---|---|---|
| 1 | Flux Krea + LoRA de profundidad | Fijos de luna y atardecer. En las montañas el Z-depth del cerro define el relieve: el paisaje toma la forma real. |
| 2 | Qwen Image Edit 2511 | Si hay referencias, repinta los fijos siguiéndolas. Arma los cuadros guía de luz (contraluz, mañana, mediodía, tarde, atardecer, crepúsculo, luna) sobre la misma imagen. |
| 3 | MiniMax H3 (primer/último cuadro + guías) | Timelapse en loop de 10 s por montaña, con la golden hour más larga que el mediodía. |

Motor opcional `--motor seedream`: Seedream vía API de Higgsfield para la etapa 1 (necesita `HF_KEY` y `pip install higgsfield-client`; experimental, ver `pipeline/seedream.py`).

Superficies: montaña izquierda 3840×1200 · pantallas centro 3712×896 (11 LED) · montaña derecha 4096×1200.
Los previos se publican a un tercio/mitad de resolución; los masters se generan aparte.

## Estructura

```
index.html            tablero (lee data/site.json)
comparativo.html      edición 2025 vs propuestas de German (estático)
escenas.json          escenas y prompts del generador
referencias/<escena>/ imágenes que sube el equipo
previos/<escena>/     previos IA generados (fijos, timelapse, meta.json)
assets/               miniaturas 2025, German y mapas de zonas aptas
pipeline/             generador (ComfyUI) · insumos: máscaras, Z-depth, clay
tools/build_site.py   arma data/site.json (lo corre GitHub Actions en cada push)
```
