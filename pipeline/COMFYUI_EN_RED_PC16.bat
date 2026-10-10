@echo off
REM ComfyUI accesible desde la red de la oficina (para que la PC17 le mande pedidos).
REM Copiar en la PC16 junto a run_nvidia_gpu.bat (E:\ComfyUI\ComfyUI_windows_portable) y usar este en lugar del otro.
cd /d "%~dp0"
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 0.0.0.0 --port 8188 --disable-auto-launch
pause
