@echo off
cd /d "%~dp0"
chcp 65001 >nul
python inventariar_biblioteca.py %*
echo.
pause
