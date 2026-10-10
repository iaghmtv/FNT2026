@echo off
chcp 65001 >nul
cd /d "%~dp0"
title FNT 2026 - Cola de pedidos (PC16 / PC17)
echo === FNT 2026 - Cola de pedidos de previos ===
echo Toma los pedidos de la pagina y los manda a la ComfyUI libre (PC17 local / PC16 en red).
echo Dejala abierta. Para cortar: cerra esta ventana.
echo.
curl -s -m 3 http://127.0.0.1:8188/system_stats >nul 2>&1
if not errorlevel 1 goto run
echo Iniciando ComfyUI local...
start "ComfyUI" /min cmd /c "cd /d E:\ComfyUI\ComfyUI_windows_portable && .\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --disable-auto-launch"
:wait
timeout /t 5 >nul
curl -s -m 3 http://127.0.0.1:8188/system_stats >nul 2>&1
if errorlevel 1 goto wait
:run
python pipeline\fnt_cola.py
echo.
pause
