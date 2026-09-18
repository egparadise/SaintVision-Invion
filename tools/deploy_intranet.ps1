# SaintVision-Invion Intranet Automated Deployment Preflight & Validation Script
# Note: Validates TLS certificate files, unit tests, fresh production build, API contract smoke process, and compose config.
# Physical multi-node container deployment requires on-prem hardware launch and operator acceptance.
# Usage: powershell -ExecutionPolicy Bypass -File tools/deploy_intranet.ps1

$ErrorActionPreference = "Stop"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host " SaintVision-Invion Intranet Web Portal Preflight Pipeline" -ForegroundColor Cyan
Write-Host " Owner: Gemini (Antigravity) | Target Scope: Frontend & Intranet Web" -ForegroundColor Cyan
Write-Host " (Physical 5-node launch requires on-prem operator hardware acceptance)" -ForegroundColor DarkGray
Write-Host "================================================================" -ForegroundColor Cyan

try {
    # Step 1: Generate TLS Certificates
    Write-Host "`n[1/5] Verifying TLS 1.3 Certificate Files on Disk..." -ForegroundColor Yellow
    $certDir = if ([string]::IsNullOrWhiteSpace($env:SAINTVISION_DEV_CERT_DIR)) { "deploy/certs" } else { $env:SAINTVISION_DEV_CERT_DIR }
    $certFile = Join-Path $certDir "saintvision.crt"
    $keyFile = Join-Path $certDir "saintvision.key"
    $pythonCmd = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

    # A failed bind mount can leave a directory where a certificate file must
    # be. Remove only these exact generated targets before regeneration.
    foreach ($tlsPath in @($certFile, $keyFile)) {
        if (Test-Path -LiteralPath $tlsPath -PathType Container) {
            Write-Host "⚠ Removing stale TLS directory at $tlsPath" -ForegroundColor Yellow
            Remove-Item -LiteralPath $tlsPath -Recurse -Force
        }
    }

    $needsGen = $false
    if (-not (Test-Path -LiteralPath $certFile -PathType Leaf) -or -not (Test-Path -LiteralPath $keyFile -PathType Leaf)) {
        $needsGen = $true
    } elseif ((Get-Item $certFile).Length -eq 0 -or (Get-Item $keyFile).Length -eq 0) {
        Write-Host "⚠ Found empty (0-byte) TLS certificate or key, regenerating..." -ForegroundColor Yellow
        $needsGen = $true
    }

    if ($needsGen) {
        Write-Host "Generating TLS certificates via $pythonCmd tools/generate_tls_cert.py..." -ForegroundColor DarkGray
        & $pythonCmd tools/generate_tls_cert.py --output-dir $certDir
        if ($LASTEXITCODE -ne 0) {
            throw "TLS certificate generation failed with exit code $LASTEXITCODE"
        }
    }

    # Strict file existence and non-zero byte size assertion
    if (-not (Test-Path -LiteralPath $certFile -PathType Leaf) -or -not (Test-Path -LiteralPath $keyFile -PathType Leaf)) {
        throw "TLS certificate files ($certFile, $keyFile) do not exist after generation step."
    }

    $certItem = Get-Item $certFile
    $keyItem = Get-Item $keyFile

    if ($certItem.Length -eq 0 -or $keyItem.Length -eq 0) {
        throw "TLS certificate files ($($certFile): $($certItem.Length) bytes, $($keyFile): $($keyItem.Length) bytes) must be non-empty (>0 bytes)."
    }

    & $pythonCmd tools/verify_tls_cert_pair.py --certificate $certFile --private-key $keyFile
    if ($LASTEXITCODE -ne 0) {
        throw "TLS certificate and private key do not match or could not be parsed."
    }

    Write-Host "✔ Certificate files present and non-empty: $($certFile) ($($certItem.Length) bytes), $($keyFile) ($($keyItem.Length) bytes)" -ForegroundColor Green

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

    # Step 3: Build Production Assets with PWA/Offline Shell (with freshness guarantee)
    Write-Host "`n[3/5] Building Production Assets (Vite + PWA Offline Shell)..." -ForegroundColor Yellow
    Push-Location apps/web
    try {
        # Ensure build freshness: clean pre-existing build output so dist/ cannot be stale
        if (Test-Path "dist") {
            Remove-Item -Path "dist" -Recurse -Force
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Production build failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }

    $distHtml = "apps/web/dist/index.html"
    if (-not (Test-Path $distHtml)) {
        throw "Production build artifact '$distHtml' does not exist."
    }
    $distHtmlItem = Get-Item $distHtml
    if ($distHtmlItem.Length -eq 0) {
        throw "Production build artifact '$distHtml' is empty (0 bytes)."
    }
    Write-Host "✔ Fresh production build succeeded (dist/index.html verified, $($distHtmlItem.Length) bytes)!" -ForegroundColor Green

    # Step 4: Run API Contract Smoke Suite
    Write-Host "`n[4/5] Running API Contract Smoke Suite (tools/run_browser_smoke.mjs)..." -ForegroundColor Yellow
    node tools/run_browser_smoke.mjs
    if ($LASTEXITCODE -ne 0) { throw "API contract smoke suite failed with exit code $LASTEXITCODE" }
    Write-Host "✔ API contract smoke process exited with code 0!" -ForegroundColor Green

    # Step 5: Docker Compose Production Config Validation & Live Gateway Probe
    Write-Host "`n[5/5] Docker Compose Intranet Deployment Orchestration & Preflight..." -ForegroundColor Yellow
    $dockerValidated = $false
    $dockerSkipped = $false

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        $authConfigPath = if (Test-Path "README.md") { ((Resolve-Path "README.md").Path -replace '\\', '/') } else { "README.md" }
        if (-not $env:INV_WEB_AUTH_CONFIG) { $env:INV_WEB_AUTH_CONFIG = $authConfigPath }
        if (-not $env:INV_CONFIG_VOLUME) { $env:INV_CONFIG_VOLUME = "saintvision-config-preflight" }
        if (-not $env:INV_BUSINESS_DSN) { $env:INV_BUSINESS_DSN = "postgresql+psycopg://preflight:preflight@postgres/saintvision" }
        if (-not $env:INV_RUNTIME_DSN) { $env:INV_RUNTIME_DSN = "postgresql://preflight-kernel:preflight@postgres/saintvision" }
        if (-not $env:INV_RECOVERY_EPOCH) { $env:INV_RECOVERY_EPOCH = "11111111-1111-4111-8111-111111111111" }
        if (-not $env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD = "preflight-postgres-password" }
        if (-not $env:MINIO_ROOT_USER) { $env:MINIO_ROOT_USER = "preflight-minio-user" }
        if (-not $env:MINIO_ROOT_PASSWORD) { $env:MINIO_ROOT_PASSWORD = "preflight-minio-password" }

        docker compose -f docker-compose.prod.yml config --quiet
        if ($LASTEXITCODE -ne 0) {
            throw "Docker compose production configuration validation failed with exit code $LASTEXITCODE"
        }
        $dockerValidated = $true
        Write-Host "✔ docker-compose.prod.yml syntax and service graph validated successfully!" -ForegroundColor Green
    } else {
        $dockerSkipped = $true
        Write-Host "ℹ Docker CLI not detected on host environment; skipping container stack preflight." -ForegroundColor Yellow
    }

    # Probe Live Gateway Status (Optional dev probe)
    $gwHealthy = $false
    try {
        $gwResp = Invoke-WebRequest -Uri "http://127.0.0.1:8080/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($gwResp.StatusCode -eq 200) {
            $gwHealthy = $true
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
    Write-Host " [API Contract Smoke Suite / Local Preflight Pipeline Summary]" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host " [1/5] TLS Certificate Files:       PRESENT & NON-EMPTY ($($certFile): $($certItem.Length)B, $($keyFile): $($keyItem.Length)B; cryptographic validity & TLS negotiation unverified)" -ForegroundColor Green
    Write-Host " [2/5] Frontend & Protocol Tests:    VERIFIED (apps/web unit/protocol tests passed)" -ForegroundColor Green
    Write-Host " [3/5] Production Asset Build:       FRESH DIST GENERATED (apps/web/dist/index.html rebuilt cleanly, $($distHtmlItem.Length)B)" -ForegroundColor Green
    Write-Host " [4/5] API Contract Smoke Suite:    PROCESS EXITED 0 (browser/physical-node acceptance unverified)" -ForegroundColor Green
    if ($dockerValidated) {
        Write-Host " [5/5] Compose Production Graph:     SYNTAX & GRAPH VALIDATED (docker-compose.prod.yml valid; services not started)" -ForegroundColor Green
    } elseif ($dockerSkipped) {
        Write-Host " [5/5] Compose Production Graph:     SKIPPED (Docker CLI not detected on host)" -ForegroundColor Yellow
    } else {
        Write-Host " [5/5] Compose Production Graph:     NOT RUN" -ForegroundColor Yellow
    }

    if ($gwHealthy) {
        Write-Host " [OPT] Live Gateway Probe:           ACTIVE (HTTP 200 on :8080; optional dev probe)" -ForegroundColor Green
    } else {
        Write-Host " [OPT] Live Gateway Probe:           OFFLINE / NOT RUNNING (Optional dev probe)" -ForegroundColor Yellow
    }

    Write-Host "`nScope Assurance Boundary:" -ForegroundColor Cyan
    Write-Host "  - [1/5] Confirms cert/key files exist and are non-empty; cryptographic validity, SAN, and TLS 1.3 handshake unverified." -ForegroundColor DarkGray
    Write-Host "  - [2/5] Runs apps/web Vitest suite; verifies client-side component logic and mock contracts." -ForegroundColor DarkGray
    Write-Host "  - [3/5] Cleans prior dist/ and verifies fresh apps/web/dist/index.html generation; does not verify CDN/proxy serving." -ForegroundColor DarkGray
    Write-Host "  - [4/5] Confirms node tools/run_browser_smoke.mjs process exited 0; does not constitute browser/physical-node acceptance." -ForegroundColor DarkGray
    Write-Host "  - [5/5] Validates docker-compose.prod.yml syntax and service graph only; containers not started." -ForegroundColor DarkGray
    Write-Host "  - [OPT] Live Gateway probe is an optional non-fatal dev convenience check on :8080." -ForegroundColor DarkGray
    Write-Host "  - Overall: This is a local developer/CI preflight check, NOT physical 5-node hardware acceptance or bare-metal deployment." -ForegroundColor DarkGray
    Write-Host "================================================================" -ForegroundColor Cyan
} catch {
    Write-Host "`n❌ PREFLIGHT PIPELINE FAILED: $($_.Exception.Message)" -ForegroundColor Red
    throw $_
}
