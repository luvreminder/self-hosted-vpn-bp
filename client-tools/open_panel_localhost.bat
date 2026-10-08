@echo off
chcp 65001 >nul
title 3X-UI Localhost Secure Tunnel

:: ==============================================================================
:: Connection Settings (Populate with your server details)
:: ==============================================================================
set SERVER_IP=YOUR_SERVER_IP
set SSH_PORT=22
set SSH_USER=root
set SSH_KEY=%USERPROFILE%\.ssh\id_ed25519
set PANEL_PORT=23600
set PANEL_PATH=web_secret_path

echo ========================================================
echo  Connecting to 3X-UI Panel via Encrypted SSH Tunnel
echo ========================================================
echo Target Server: %SERVER_IP%
echo Local Port:    %PANEL_PORT%
echo.

:: Check for SSH Key
if not exist "%SSH_KEY%" (
    echo [!] Notice: SSH private key %SSH_KEY% not found.
    echo Attempting password authentication...
    set KEY_PARAM=
) else (
    set KEY_PARAM=-i "%SSH_KEY%"
)

echo Initializing secure SSH tunnel...
start "" http://localhost:%PANEL_PORT%/%PANEL_PATH%/

ssh %KEY_PARAM% -p %SSH_PORT% -N -L %PANEL_PORT%:127.0.0.1:%PANEL_PORT% %SSH_USER%@%SERVER_IP%

echo.
echo Tunnel closed.
pause
