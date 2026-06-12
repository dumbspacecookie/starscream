#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Starting dev compose stack..."
docker compose up -d

$env:ENRICH_GEOCODE = "false"
$env:ENRICH_HABITAT = "false"
$env:ENRICH_WEATHER = "false"
$env:ENRICH_OSM = "false"

Write-Host "Waiting for Postgres, Meilisearch, and MinIO..."
$healthy = $false
for ($i = 1; $i -le 60; $i++) {
    python scripts/healthcheck.py
    if ($LASTEXITCODE -eq 0) {
        $healthy = $true
        break
    }
    if ($i -eq 60) {
        Write-Error "Timed out waiting for dependency health checks"
    }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    exit 1
}

Write-Host "Running migrations..."
alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Seeding taxonomy, sources, bucket, and search index..."
python -m starscream.seed
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running E2E integration tests..."
$env:STARSCREAM_E2E_COMPOSE = "1"
python -m pytest tests/test_e2e.py tests/test_e2e_export.py -m integration -v
exit $LASTEXITCODE
