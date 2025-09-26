@echo off
REM Frontend Security Audit Script for Windows
REM Run this script to check for security vulnerabilities in Node.js dependencies

echo 🔍 Running Frontend Security Audit...
echo ==================================

cd /d "%~dp0audio-waveform-visualizer"

echo 📋 Current package versions:
call npm list --depth=0

echo.
echo 🔒 Security audit:
call npm audit

echo.
echo 📊 Audit summary:
call npm audit --audit-level=moderate

echo.
echo 💡 To fix issues automatically, run:
echo    npm audit fix
echo.
echo ⚠️  For more severe issues that require manual review:
echo    npm audit fix --force
echo.
echo 📈 To check for outdated packages:
echo    npm outdated

pause