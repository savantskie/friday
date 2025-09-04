@echo on
REM Set the API key environment variable for Caddy to read
set MCPO_API_KEY=0d4b94f58f5a401ea88b149a17f09fc9

timeout /t 60
cd /d F:\Friday\caddy
caddy.exe run --config Caddyfile --watch

