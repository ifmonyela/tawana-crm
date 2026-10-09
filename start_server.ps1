# Tawana CRM Launch Script
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting Tawana CRM Advanced Capacity Platform..." -ForegroundColor Green
Write-Host "Opening at: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

$backendDir = Join-Path $PSScriptRoot "backend"
Set-Location $backendDir
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
