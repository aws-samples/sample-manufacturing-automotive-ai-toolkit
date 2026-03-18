@echo off
setlocal
set SCRIPT_DIR=%~dp0
set PKG_ROOT=%SCRIPT_DIR%..
cd /d "%PKG_ROOT%"
for /f "usebackq delims=" %%i in (`python -c "import json; print(json.load(open('iot/iot-config.json'))['packageId'])"`) do set PKG_ID=%%i
set IMAGE_NAME=sfc-launch-package-%PKG_ID%
docker build -f docker/Dockerfile -t "%IMAGE_NAME%" .
docker run --rm "%IMAGE_NAME%"
