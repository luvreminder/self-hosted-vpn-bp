@echo off
chcp 65001 >nul
title 3X-UI Administrator Password Reset

set SERVER_IP=YOUR_SERVER_IP
set SSH_PORT=22
set SSH_USER=root
set SSH_KEY=%USERPROFILE%\.ssh\id_ed25519

echo ========================================================
echo  3X-UI Administrator Password Reset Tool
echo ========================================================
echo.
set /p NEW_PASS="Enter new administrator password: "

if "%NEW_PASS%"=="" (
    echo [!] Error: Password cannot be empty.
    pause
    exit /b
)

if not exist "%SSH_KEY%" (
    set KEY_PARAM=
) else (
    set KEY_PARAM=-i "%SSH_KEY%"
)

echo Updating administrator password on server %SERVER_IP%...
ssh %KEY_PARAM% -p %SSH_PORT% %SSH_USER%@%SERVER_IP% "x-ui setting -username admin -password '%NEW_PASS%'"

echo.
echo Password updated successfully!
pause
