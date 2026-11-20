# ViceClip Archiver — Automated Build & Release PowerShell Runner
$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  ViceClip Archiver — Automated Build & Release   " -ForegroundColor Magenta
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Run Automated Test Suite
Write-Host "`n[1/3] Running pytest suite..." -ForegroundColor Yellow
& .venv\Scripts\pytest.exe -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Tests failed! Aborting release." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 2. Run Desktop Builder
Write-Host "`n[2/3] Compiling standalone Windows .exe..." -ForegroundColor Yellow
& .venv\Scripts\python.exe build_desktop.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Build failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}

# 3. Compute SHA-256 Checksum
Write-Host "`n[3/3] Generating SHA-256 verification checksum..." -ForegroundColor Yellow
$exePath = "dist\ViceClipArchiver.exe"
if (Test-Path $exePath) {
    $hash = (Get-FileHash -Path $exePath -Algorithm SHA256).Hash
    Set-Content -Path "dist\ViceClipArchiver.exe.sha256" -Value $hash
    Write-Host "`n✔ Standalone Binary: $exePath" -ForegroundColor Green
    Write-Host "✔ SHA-256 Checksum:  $hash" -ForegroundColor Green
    Write-Host "`nAll release artifacts generated successfully!" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Output binary not found at $exePath" -ForegroundColor Red
    exit 1
}
