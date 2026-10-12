@echo off
cd /d "%~dp0"
python -c "import wx" 2>nul
if errorlevel 1 (
    echo Faltan dependencias o Python no esta instalado.
    echo Ejecuta: pip install -r requisitos.txt
    pause
    exit /b 1
)
start "" pythonw iniciar_descargador.py
