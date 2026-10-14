@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === FNT 2026 - Publicar el tablero (reemplazos a mano) ===
echo Reemplaza las imagenes en previos\ESCENA\ con el MISMO nombre (ej. atardecer_izq.jpg) y ejecuta esto.
echo.
git -c safe.directory=* pull --rebase --autostash
python tools\revisar_previos.py
echo.
git -c safe.directory=* add previos referencias
git -c safe.directory=* diff --cached --quiet && (echo No hay cambios para publicar. & pause & exit /b)
git -c safe.directory=* commit -m "Tablero: reemplazo manual de imagenes"
git -c safe.directory=* push
echo.
echo Listo: en 1-2 minutos se ve en https://iaghmtv.github.io/FNT2026/
pause
