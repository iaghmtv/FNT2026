@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === FNT 2026 - Generar previos IA ===
echo Uso: GENERAR_PREVIOS.bat            (escenas con referencias nuevas)
echo      GENERAR_PREVIOS.bat B1.08 B1.06 (escenas puntuales)
echo      GENERAR_PREVIOS.bat --todas     (todo, varias horas)
echo.
curl -s -m 3 http://127.0.0.1:8188/system_stats >nul 2>&1
if not errorlevel 1 goto run
echo Iniciando ComfyUI...
start "ComfyUI" /min cmd /c "cd /d E:\ComfyUI\ComfyUI_windows_portable && .\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --disable-auto-launch"
:wait
timeout /t 5 >nul
curl -s -m 3 http://127.0.0.1:8188/system_stats >nul 2>&1
if errorlevel 1 goto wait
:run
python pipeline\fnt_previos.py %*
echo.
pause
