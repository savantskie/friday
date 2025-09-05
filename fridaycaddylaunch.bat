@echo on
REM Friday Caddy Launcher with OpenWebUI Recovery
REM Set the API key environment variable for Caddy to read
set MCPO_API_KEY=0d4b94f58f5a401ea88b149a17f09fc9

echo Starting Friday Caddy with OpenWebUI Recovery...
timeout /t 60

:main_loop
cd /d F:\Friday\caddy

REM Start Caddy in background so we can monitor
echo Starting Caddy...
start /b "Friday Caddy" caddy.exe run --config Caddyfile --watch

REM Monitor loop - check OpenWebUI and Caddy status every 30 seconds
:monitor_loop
timeout /t 60 /nobreak >nul

REM Check if Caddy is still running
tasklist /fi "imagename eq caddy.exe" 2>nul | find /i "caddy.exe" >nul
if %ERRORLEVEL% neq 0 (
    echo Caddy process crashed, restarting...
    timeout /t 10 /nobreak >nul
    goto main_loop
)

REM Check if OpenWebUI is responding
curl -s --max-time 20 http://localhost:3000 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo OpenWebUI appears down, checking again in 10 seconds...
    timeout /t 10 /nobreak >nul
    
    curl -s --max-time 20 http://localhost:3000 >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo OpenWebUI confirmed down, but keeping Caddy running for error pages...
    ) else (
        echo OpenWebUI is back up!
    )
)

REM Continue monitoring
goto monitor_loop

