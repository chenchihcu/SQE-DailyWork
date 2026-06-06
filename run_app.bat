@echo off
chcp 65001 > nul
setlocal
cd /d "%~dp0"

echo [SQETOOL] Starting desktop app...

where uv > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Launch via uv run
    set UV_CACHE_DIR=%~dp0.uv-cache
    set PYTHONPATH=%~dp0src;%~dp0
    uv run --no-project --with-requirements requirements.txt python main.py
    goto :after_run
)

if exist ".venv\Scripts\python.exe" (
    echo [INFO] Launch via .venv python
    ".venv\Scripts\python.exe" main.py
) else (
    echo [INFO] Launch via system python
    python main.py
)

:after_run
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application terminated with error code: %ERRORLEVEL%
    pause
)

endlocal
