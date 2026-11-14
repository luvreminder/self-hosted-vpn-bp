@echo off
setlocal
chcp 65001 >nul
title 3X-UI Localhost Secure Tunnel

:: ==============================================================================
:: Connection Settings (Populate with your server details)
:: ==============================================================================
set "SERVER_IP=YOUR_SERVER_IP"
set "SSH_PORT=22"
set "SSH_USER=root"
set "SSH_KEY=%USERPROFILE%\.ssh\id_ed25519"
set "PANEL_PORT=23600"
set "SUB_PORT=2096"
set "PANEL_PATH=web_secret_path"

echo ========================================================
echo  Connecting to 3X-UI Panel via Encrypted SSH Tunnel
echo ========================================================
echo Target Server:    %SERVER_IP%
echo Local Panel Port: %PANEL_PORT%
echo Local Sub Port:   %SUB_PORT%
echo.

echo Initializing secure SSH tunnel...
start /b cmd /c "timeout /t 2 /nobreak >nul & start \"\" \"http://localhost:%PANEL_PORT%/%PANEL_PATH%/\""

if exist "%SSH_KEY%" (
    ssh -i "%SSH_KEY%" -p %SSH_PORT% -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:%PANEL_PORT%:127.0.0.1:%PANEL_PORT% -L 127.0.0.1:%SUB_PORT%:127.0.0.1:%SUB_PORT% %SSH_USER%@%SERVER_IP%
) else (
    echo [!] Notice: SSH private key %SSH_KEY% not found.
    echo Attempting password authentication...
    ssh -p %SSH_PORT% -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:%PANEL_PORT%:127.0.0.1:%PANEL_PORT% -L 127.0.0.1:%SUB_PORT%:127.0.0.1:%SUB_PORT% %SSH_USER%@%SERVER_IP%
)

echo.
echo Tunnel closed.
pause
