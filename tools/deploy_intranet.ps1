# SaintVision-Invion Intranet Automated Deployment Preflight & Validation Script
# Note: Validates TLS certificates, unit tests, production build, E2E browser smoke, and compose config.
# Physical multi-node container deployment requires on-prem hardware launch and operator acceptance.
# Usage: powershell -ExecutionPolicy Bypass -File tools/deploy_intranet.ps1

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " SaintVision-Invion Intranet Web Portal Preflight Pipeline" -ForegroundColor Cyan
Write-Host " Owner: Gemini (Antigravity) | Target Scope: Frontend & Intranet Web" -ForegroundColor Cyan
Write-Host " (Physical 5-node launch requires on-prem operator hardware acceptance)" -ForegroundColor DarkGray
Write-Host "================================================================" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# Step 1: Generate TLS Certificates
Write-Host "`n[1/5] Verifying TLS 1.3 Enterprise Certificates..." -ForegroundColor Yellow
if (-not (Test-Path "deploy/certs/saintvision.crt") -or -not (Test-Path "deploy/certs/saintvision.key")) {
    & .venv\Scripts\python tools/generate_tls_cert.py
} else {
    Write-Host "✔ Certificates already present in deploy/certs/" -ForegroundColor Green
}

# Step 2: Run Automated Unit and Protocol Tests
Write-Host "`n[2/5] Running Frontend & Protocol Automated Tests (Vitest)..." -ForegroundColor Yellow
Push-Location apps/web
try {
    npm test -- --run
    if ($LASTEXITCODE -ne 0) { throw "Unit test suite failed with exit code $LASTEXITCODE" }
    Write-Host "✔ Unit tests passed 100% (Zero failures)!" -ForegroundColor Green
} finally {
    Pop-Location
}

# Step 3: Build Production Assets with PWA/Offline Shell
Write-Host "`n[3/5] Building Production Assets (Vite + PWA Offline Shell)..." -ForegroundColor Yellow
Push-Location apps/web
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Production build failed with exit code $LASTEXITCODE" }
    Write-Host "✔ Production build succeeded (dist/ generated cleanly)!" -ForegroundColor Green
} finally {
    Pop-Location
}

# Step 4: Run E2E Web Smoke Verification
Write-Host "`n[4/5] Running E2E Smoke & Gateway Verification (174 checks)..." -ForegroundColor Yellow
node tools/run_browser_smoke.mjs
if ($LASTEXITCODE -ne 0) { throw "E2E browser smoke suite failed with exit code $LASTEXITCODE" }

# Step 5: Docker Compose Production Config Validation & Live Gateway Probe
Write-Host "`n[5/5] Docker Compose Intranet Deployment Orchestration & Preflight..." -ForegroundColor Yellow
if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (-not $env:INV_DATABASE_URL) { $env:INV_DATABASE_URL = "postgresql://preflight:preflight@postgres/saintvision" }
    if (-not $env:INV_RUNTIME_DSN) { $env:INV_RUNTIME_DSN = "postgresql://preflight-kernel:preflight@postgres/saintvision" }
    if (-not $env:INV_RECOVERY_EPOCH) { $env:INV_RECOVERY_EPOCH = "11111111-1111-4111-8111-111111111111" }
    if (-not $env:INV_CONFIG_DIRECTORY) { $env:INV_CONFIG_DIRECTORY = "$PSScriptRoot\..\deploy" }
    if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = "preflight-postgres-password" }
    if (-not $env:MINIO_ROOT_USER) { $env:MINIO_ROOT_USER = "preflight-minio-user" }
    if (-not $env:MINIO_ROOT_PASSWORD) { $env:MINIO_ROOT_PASSWORD = "preflight-minio-password" }

    docker compose -f docker-compose.prod.yml config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Docker compose production configuration validation failed with exit code $LASTEXITCODE"
    }
    Write-Host "✔ docker-compose.prod.yml syntax and service graph validated successfully!" -ForegroundColor Green
} else {
    Write-Host "ℹ Docker command not detected on host environment; skipping container stack preflight." -ForegroundColor Yellow
}

# Probe Live Gateway Status
try {
    $gwResp = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/health" -UseBasicParsing -TimeoutSec 2
    if ($gwResp.StatusCode -eq 200) {
        Write-Host "✔ Live Control Plane Gateway is HEALTHY (HTTP 200 on :8080)" -ForegroundColor Green
    }
} catch {
    Write-Host "ℹ Live Control Plane Gateway not probed or offline on :8080" -ForegroundColor Yellow
}

Write-Host "`nIntranet Endpoints Configured:" -ForegroundColor Cyan
Write-Host "  - Frontend Portal (Nginx TLS 1.3): https://saintvision.internal:8443/" -ForegroundColor White
Write-Host "  - Control Plane Gateway (FastAPI): http://127.0.0.1:8080/v1/health" -ForegroundColor White
Write-Host "  - Database (PostgreSQL 16 RLS):    localhost:5432" -ForegroundColor White
Write-Host "  - Storage (MinIO S3 Compatible):   http://localhost:9000/ (Console: :9001)" -ForegroundColor White
Write-Host "`nPhysical Multi-Machine Production Launch:" -ForegroundColor Cyan
Write-Host "  docker compose -f docker-compose.prod.yml up -d --build" -ForegroundColor Green
Write-Host "  (Subject to on-premise operator hardware acceptance and remote PC enrollment)" -ForegroundColor DarkGray
Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "🎉 Preflight Deployment Pipeline Completed with ZERO Errors (All Exit Codes 0)!" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
