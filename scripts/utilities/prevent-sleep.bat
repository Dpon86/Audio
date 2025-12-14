@echo off
echo Preventing Windows sleep while development servers are running...
echo This will keep your computer awake for development work.
echo Press Ctrl+C to stop and allow normal sleep behavior.

REM Prevent sleep indefinitely using powercfg
powercfg -change -standby-timeout-ac 0
powercfg -change -standby-timeout-dc 0
powercfg -change -hibernate-timeout-ac 0  
powercfg -change -hibernate-timeout-dc 0

echo Sleep prevention activated!
echo Your computer will not sleep while this script is running.
echo.
echo Current power settings:
powercfg /query SCHEME_CURRENT SUB_SLEEP

echo.
echo To restore normal sleep behavior, run: ./restore-sleep.bat
echo Or press Ctrl+C and the restore script will run automatically.

REM Keep script running
:loop
timeout /t 30 /nobreak >nul
echo [%time%] Keeping system awake...
goto loop