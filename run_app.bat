@echo off
REM Launch the app with the PROJECT venv, not whatever is on PATH.
REM Bare `streamlit run app.py` uses the system Python, which lacks chromadb.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No virtualenv found. Create one first:
    echo   uv venv .venv
    echo   uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    exit /b 1
)

.venv\Scripts\python.exe -m streamlit run app.py %*
