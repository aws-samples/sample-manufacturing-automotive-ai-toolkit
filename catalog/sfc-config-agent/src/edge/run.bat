@echo off
:: SFC Launch Package — run.bat (Windows)
:: One-click launcher: checks Java & uv, installs if missing, then runs the agent.
setlocal

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "CORRETTO_URL=https://corretto.aws/downloads/latest/amazon-corretto-21-x64-windows-jdk.msi"
set "CORRETTO_MSI=%SCRIPT_DIR%\.java\corretto21.msi"

:: ── 1. Java check ──────────────────────────────────────────────────────────
where java >nul 2>&1
if not errorlevel 1 goto java_ok

echo.
echo [WARNING] Java not found.
echo   Amazon Corretto 21 will be downloaded and installed system-wide.
echo   A UAC prompt may appear to allow the installer to run.
echo.
set /p JAVA_CHOICE=Install Amazon Corretto 21 now? [Y/n]: 
if /i "%JAVA_CHOICE%"=="n" goto java_abort

if not exist "%SCRIPT_DIR%\.java" mkdir "%SCRIPT_DIR%\.java"
echo ^> Downloading Corretto 21 ...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%CORRETTO_URL%' -OutFile '%CORRETTO_MSI%'"
if errorlevel 1 goto download_error

echo ^> Installing Corretto 21 (this may take a moment) ...
msiexec /i "%CORRETTO_MSI%" /quiet /norestart
if errorlevel 1 goto install_error

del /f /q "%CORRETTO_MSI%"
echo [OK] Corretto 21 installed.

:: Re-read system PATH from registry so java is found in this session
for /f "skip=2 tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path') do set "PATH=%%B;%PATH%"

goto java_done

:java_abort
echo [ERROR] Java is required. Aborting.
exit /b 1

:download_error
echo [ERROR] Download failed. Please install manually from:
echo   https://downloads.corretto.aws/#/downloads?version=21
exit /b 1

:install_error
echo [ERROR] Installation failed. Please install manually from:
echo   https://downloads.corretto.aws/#/downloads?version=21
exit /b 1

:java_ok
echo [OK] Java found.

:java_done

:: ── 2. uv check ────────────────────────────────────────────────────────────
where uv >nul 2>&1
if not errorlevel 1 goto uv_ok

echo.
echo [WARNING] uv (Python package manager) not found.
echo.
set /p UV_CHOICE=Install uv now? [Y/n]: 
if /i "%UV_CHOICE%"=="n" goto uv_abort

echo ^> Installing uv ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 goto uv_error

:: Add common uv install paths for this session
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

where uv >nul 2>&1
if errorlevel 1 goto uv_path_warn

echo [OK] uv installed.
goto uv_done

:uv_abort
echo [ERROR] uv is required. Aborting.
exit /b 1

:uv_error
echo [ERROR] uv installation failed. Aborting.
exit /b 1

:uv_path_warn
echo [WARNING] uv was installed but is not yet on PATH.
echo   Please open a new terminal and re-run this script.
exit /b 1

:uv_ok
echo [OK] uv found.

:uv_done

:: ── 3. Run the agent ────────────────────────────────────────────────────────
echo.
echo [START] Starting SFC runner ...
echo.
cd /d "%SCRIPT_DIR%\runner"
uv run runner.py
