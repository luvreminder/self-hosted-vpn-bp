@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
title 3X-UI Administrator Password Reset

set "SERVER_IP=YOUR_SERVER_IP"
set "SSH_PORT=22"
set "SSH_USER=root"
set "SSH_KEY=%USERPROFILE%\.ssh\id_ed25519"
set "PANEL_USER=admin"

echo ========================================================
echo  3X-UI Administrator Password Reset Tool
echo ========================================================
echo.
set /p "NEW_PASS=Enter new administrator password: "

if not defined NEW_PASS (
    echo [!] Error: Password cannot be empty.
    pause
    exit /b 1
)

set "PW_B64="
for /f "usebackq delims=" %%B in (`powershell -NoProfile -Command "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($env:NEW_PASS))"`) do set "PW_B64=%%B"
set "USER_B64="
for /f "usebackq delims=" %%U in (`powershell -NoProfile -Command "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($env:PANEL_USER))"`) do set "USER_B64=%%U"
set "NEW_PASS="

if not defined PW_B64 (
    echo [!] Error: Failed to encode password safely.
    pause
    exit /b 1
)

echo Updating administrator credentials on server %SERVER_IP%...
if exist "%SSH_KEY%" (
    ssh -i "%SSH_KEY%" -p %SSH_PORT% %SSH_USER%@%SERVER_IP% "python3 -c \"import base64, subprocess; subprocess.run(['x-ui', 'setting', '-username', base64.b64decode('%USER_B64%').decode(), '-password', base64.b64decode('%PW_B64%').decode()], check=True)\""
) else (
    echo [!] Notice: SSH private key %SSH_KEY% not found. Attempting interactive SSH authentication...
    ssh -p %SSH_PORT% %SSH_USER%@%SERVER_IP% "python3 -c \"import base64, subprocess; subprocess.run(['x-ui', 'setting', '-username', base64.b64decode('%USER_B64%').decode(), '-password', base64.b64decode('%PW_B64%').decode()], check=True)\""
)

if errorlevel 1 (
    echo.
    echo [!] Error: Failed to update administrator password.
    pause
    exit /b 1
)

echo.
echo Password updated successfully!
pause
