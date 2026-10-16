@echo off
setlocal
set PYTHONUTF8=1
set "PDF=data\Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf"

if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment is missing. Run setup_windows.cmd first.
    exit /b 1
)

if not exist "%PDF%" (
    echo.
    echo Source PDF not found: %PDF%
    echo Put Agni_Ki_Udaan_Adhyayan_Sahayika_Hindi.pdf in this project's data folder,
    echo then run this file again.
    exit /b 1
)

.venv\Scripts\python.exe main.py ingest --pdf "%PDF%" --preview
