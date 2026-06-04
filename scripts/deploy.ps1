$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — update secrets before production."
}

docker compose build
docker compose up -d

Write-Host "TAVA stack running:"
Write-Host "  Frontend: http://localhost:4200"
Write-Host "  API/Swagger: http://localhost:8000/docs"
Write-Host "  PostgreSQL: localhost:5432"
