@echo off
cd /d "%~dp0"
py -3 main.py
if errorlevel 1 (
    echo.
    echo No se pudo iniciar el programa. Comprueba que Python 3 este instalado.
    pause
)
