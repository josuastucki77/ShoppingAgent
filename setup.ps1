$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker-Aufruf fehlgeschlagen (Exit $LASTEXITCODE)." }
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host '.env mit lokalen Ollama-Voreinstellungen erstellt.'
}
if (-not (Select-String -LiteralPath '.env' -Pattern '^POSTGRES_PASSWORD=' -Quiet)) {
    $password = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    Add-Content -LiteralPath '.env' -Encoding ASCII -Value "`nPOSTGRES_PASSWORD=$password"
    Write-Host 'Zufaelliges Datenbankpasswort in .env ergaenzt.'
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker fehlt. Installiere Docker Desktop mit WSL2 und Linux-Containern.'
}
Invoke-Docker compose version
Invoke-Docker info --format '{{.OSType}}'
Invoke-Docker compose config --quiet
New-Item -ItemType Directory -Path 'output' -Force | Out-Null
Invoke-Docker compose run --rm --no-deps hermes-init python /project/scripts/check_services.py
Invoke-Docker compose build honcho honcho-deriver
Invoke-Docker compose up -d --wait database redis honcho
Invoke-Docker compose up -d honcho-deriver
Invoke-Docker compose stop hermes
Invoke-Docker compose run --rm hermes-init
Invoke-Docker compose up -d hermes
Write-Host 'Setup fertig. Chat: docker compose exec -u hermes hermes hermes chat'
Write-Host 'Job testen: docker compose exec -u hermes hermes hermes cron run shopping-daily'
