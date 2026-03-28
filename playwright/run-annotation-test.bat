@echo off
cd /d "%~dp0"
echo Running Playwright annotation test...
echo This will generate annotated screenshots with visual highlights.
echo.
call npm test -- tests/03-annotate-key-steps.spec.js --headed
echo.
echo Test complete! Check user-manual-screenshots\ for new annotated images.
pause
