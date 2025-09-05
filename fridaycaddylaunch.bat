@echo on
REM Friday Caddy Launcher with OpenWebUI Recovery
REM Set the API key environment variable for Caddy to read
set MCPO_API_KEY=0d4b94f58f5a401ea88b149a17f09fc9

echo Starting Friday Caddy with OpenWebUI Recovery...
timeout /t 60

:main_loop
cd /d F:\Friday\caddy

REM Start Caddy in background
echo Starting Caddy...
start "Caddy Server" caddy.exe run --config Caddyfile --watch

REM Monitor loop - check every 30 seconds
:monitor_loop
timeout /t 30 /nobreak >nul

REM Check if OpenWebUI is responding
curl -s --max-time 5 http://localhost:3000 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo OpenWebUI appears down, checking again in 10 seconds...
    timeout /t 10 /nobreak >nul
    
    curl -s --max-time 5 http://localhost:3000 >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo OpenWebUI confirmed down, restarting Caddy...
        
        REM Kill Caddy processes
        taskkill /f /im caddy.exe >nul 2>&1
        
        echo Waiting 10 seconds before restart...
        timeout /t 10 /nobreak >nul
        
        REM Go back to main loop to restart
        goto main_loop
    )
)

REM Check if Caddy is still running
tasklist /fi "imagename eq caddy.exe" 2>nul | find /i "caddy.exe" >nul
if %ERRORLEVEL% neq 0 (
    echo Caddy process not found, restarting...
    timeout /t 10 /nobreak >nul
    goto main_loop
)

REM Continue monitoring
goto monitor_loop

