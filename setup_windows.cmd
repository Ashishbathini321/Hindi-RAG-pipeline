@echo off
setlocal
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
    echo Creating a Python 3.11 virtual environment...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo.
        echo Could not create .venv. Make sure Python 3.11 is installed and `py -3.11 --version` works.
        exit /b 1
    )
)

echo Installing project packages...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Running the built-in checks...
.venv\Scripts\python.exe -m unittest discover -s tests -v
if errorlevel 1 exit /b 1

echo.
echo Setup finished successfully.
