param(
  [string]$Title = "Friday",
  [string]$Body  = "Ping to all devices",
  [string]$Url   = "/pwa/",
  [string]$SubsPath = "F:\Friday\pwa\subs",
  [string]$VapidPath = "F:\Friday\pwa\vapid.json"
)

# Load VAPID keys
$vapid = Get-Content $VapidPath -Raw | ConvertFrom-Json
$pub = $vapid.publicKey
$priv = $vapid.privateKey

# Build JSON payload safely
$payload = @{ title = $Title; body = $Body; url = $Url } | ConvertTo-Json -Compress

# npx shim
$npx = "$env:ProgramFiles\nodejs\npx.cmd"

# Send to every *.json in subs folder
Get-ChildItem $SubsPath -Filter *.json | ForEach-Object {
  try {
    $sub = Get-Content $_.FullName -Raw | ConvertFrom-Json
    & $npx -y web-push send-notification `
      --endpoint $sub.endpoint `
      --key $sub.keys.p256dh `
      --auth $sub.keys.auth `
      --vapid-subject mailto:you@example.com `
      --vapid-pubkey $pub `
      --vapid-pvtkey $priv `
      --payload $payload `
      --ttl 60
    Write-Host "Sent to $($_.Name)"
  } catch {
    Write-Host "Failed $($_.Name): $($_.Exception.Message)" -ForegroundColor Red
  }
}
