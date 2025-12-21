#!/usr/bin/env pwsh
# Audio Repetitive Detection - Stop Development Environment
# Cleanly stops Django, React, Celery, and Docker containers

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Stopping Development Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# [1/5] Stop Django (port 8000)
Write-Host "[1/5] Stopping Django development server..." -ForegroundColor Yellow
$djangoProcesses = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Get-Process -ErrorAction SilentlyContinue
if ($djangoProcesses) {
    $djangoProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Django stopped (port 8000 freed)" -ForegroundColor Green
} else {
    Write-Host "  Django was not running" -ForegroundColor DarkGray
}

# [2/5] Stop React (port 3000)
Write-Host "[2/5] Stopping React development server..." -ForegroundColor Yellow
$reactProcesses = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Get-Process -ErrorAction SilentlyContinue
if ($reactProcesses) {
    $reactProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    # Verify it's actually stopped
    $stillRunning = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    if (-not $stillRunning) {
        Write-Host "  React stopped (port 3000 freed)" -ForegroundColor Green
    } else {
        # Force kill all node processes if port still occupied
        Get-Process -Name "node" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        $finalCheck = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
        if (-not $finalCheck) {
            Write-Host "  React stopped (forcefully killed all Node processes)" -ForegroundColor Green
        } else {
            Write-Host "  React process killed but port may take a moment to free" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  React was not running" -ForegroundColor DarkGray
}

# [3/5] Stop Celery workers
Write-Host "[3/5] Stopping Celery workers..." -ForegroundColor Yellow
$celeryProcesses = Get-Process -Name "celery" -ErrorAction SilentlyContinue
if ($celeryProcesses) {
    $celeryProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Celery workers stopped" -ForegroundColor Green
} else {
    Write-Host "  Celery was not running" -ForegroundColor DarkGray
}

# [4/5] Stop Docker containers
Write-Host "[4/5] Stopping Docker containers..." -ForegroundColor Yellow
Push-Location "$PSScriptRoot\..\..\backend"
try {
    # Try docker compose down first
    $dockerOutput = docker compose down 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Docker containers stopped" -ForegroundColor Green
    } else {
        # Fallback: Stop Redis container directly
        docker stop redis 2>$null
        docker rm redis 2>$null
        Write-Host "  Redis container stopped" -ForegroundColor Green
    }
    # Also kill any orphaned Redis processes on port 6379
    $redisPort = Get-NetTCPConnection -LocalPort 6379 -ErrorAction SilentlyContinue
    if ($redisPort) {
        $redisPort | Select-Object -ExpandProperty OwningProcess | Get-Process -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "  No Docker containers running" -ForegroundColor DarkGray
} finally {
    Pop-Location
}

# [5/5] Verify ports are free
Write-Host "[5/5] Verifying ports..." -ForegroundColor Yellow
Start-Sleep -Seconds 2  # Give ports time to free up
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port3000 = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
$port6379 = Get-NetTCPConnection -LocalPort 6379 -ErrorAction SilentlyContinue

if (-not $port8000) {
    Write-Host "  Port 8000 is free" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Port 8000 still in use!" -ForegroundColor Red
}

if (-not $port3000) {
    Write-Host "  Port 3000 is free" -ForegroundColor Green
} else {
    Write-Host "  Port 3000 still in use (may free up shortly)" -ForegroundColor Yellow
}

if (-not $port6379) {
    Write-Host "  Port 6379 is free" -ForegroundColor Green
} else {
    Write-Host "  Port 6379 in use (Redis container may still be shutting down)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " All services stopped!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start again: backend\scripts\startup\start-dev-venv.ps1" -ForegroundColor Cyan
Write-Host ""
