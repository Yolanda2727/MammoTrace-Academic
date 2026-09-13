@echo off
setlocal
cd /d "%~dp0"
echo MammoTrace Academic 4.1.0 - instalacion local. Requiere Internet y Python 3.13 de 64 bits.
py -3.13 --version
if errorlevel 1 (
  echo Instale Python 3.13 de 64 bits y vuelva a ejecutar este archivo.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3.13 -m venv .venv
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error
.venv\Scripts\python.exe scripts\check_environment.py
if errorlevel 1 goto :error
echo Instalacion terminada. Ejecute INICIAR_WINDOWS.bat.
pause
exit /b 0
:error
echo No se completo la instalacion. Conserve el mensaje de error; no continue con una instalacion incompleta.
pause
exit /b 1
