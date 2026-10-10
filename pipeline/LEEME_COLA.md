# Cola de pedidos de previos (PC16 / PC17)

En la página, cada escena tiene **✦ Pedir previo con prompt**: abre un formulario de GitHub (issue) con la escena,
el prompt, las imágenes de referencia y qué generar. La cola que corre en la **GHM17** (`FNT_COLA.bat`) lo toma,
lo manda a la ComfyUI que esté desocupada (PC17 local o PC16 por red), sube los previos y responde en el pedido.

## Puesta en marcha (una sola vez)

### 1. Token para que la cola lea y responda los pedidos (en la GHM17)
1. Con la cuenta **iaghmtv** entrá a https://github.com/settings/personal-access-tokens/new
2. *Token name*: `FNT cola GHM17` · *Expiration*: hasta después del show.
3. *Repository access*: **Only select repositories** → `iaghmtv/FNT2026`.
4. *Permissions → Repository permissions*: **Issues: Read and write** (y Metadata: Read, que viene sola).
5. *Generate token* y copialo.
6. En `pipeline/` copiá `.env.ejemplo` como `.env` y pegá el token: `FNT_GH_TOKEN=github_pat_...`
   El archivo `.env` está en `.gitignore`: no se sube.

### 2. ComfyUI de la PC16 accesible por red
1. En la PC16 copiá `pipeline/COMFYUI_EN_RED_PC16.bat` a `E:\ComfyUI\ComfyUI_windows_portable\` y abrí ComfyUI con ese .bat.
2. Permití el puerto en el firewall de la PC16 (PowerShell como administrador, una vez):
   `netsh advfirewall firewall add rule name="ComfyUI FNT 8188" dir=in action=allow protocol=TCP localport=8188 profile=private`
3. La PC16 necesita los mismos modelos que la 17 (Flux Krea + LoRA depth, Qwen Image Edit 2511 + Lightning, MiniMax H3 + turbo).
   Al arrancar, la cola avisa si a alguna máquina le falta un modelo.
4. La IP de la PC16 está en `pipeline/maquinas.json` (hoy `192.168.1.38`). Para sacar una máquina de la cola: `"activa": false`.

### 3. Arrancar la cola
Doble clic en `FNT_COLA.bat` en la GHM17 y dejarla abierta.

## Cómo reparte
- Revisa los pedidos cada 30 s. Solo acepta pedidos de miembros del repo (dueño o colaboradores invitados);
  a los demás les responde que no se procesan.
- Una máquina está libre si su ComfyUI no tiene nada corriendo ni en cola durante ~12 s seguidos.
  Si alguien está usando esa ComfyUI a mano, la cola espera o usa la otra.
- Si las dos están libres, procesa dos pedidos en paralelo.
- Etiquetas del pedido: `en-proceso` + `pc16`/`pc17` → `listo` (o `error`, con el motivo en un comentario; quitando `error` se reintenta).

## Qué queda en el repo
- Las imágenes del pedido → `referencias/<escena>/pedido<n>_<usuario>_<i>.jpg` (quedan como referencias de la escena).
- Los previos → `previos/<escena>/pedidos/<n>/` (fijos de luna/atardecer y, si se pidió, timelapse de cada montaña).
- La página los muestra en la escena, en "Pedidos al generador", con el estado de cada uno.
