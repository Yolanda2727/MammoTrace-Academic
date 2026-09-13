@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero ejecute INSTALAR_WINDOWS.bat y espere a que finalice sin errores.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
pause
