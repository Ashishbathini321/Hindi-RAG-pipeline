@echo off
setlocal
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment is missing. Run setup_windows.cmd first.
    exit /b 1
)

.venv\Scripts\python.exe main.py run-tests --generator extractive
