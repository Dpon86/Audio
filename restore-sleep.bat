@echo off
echo Restoring normal Windows sleep settings...

REM Restore default sleep timeouts (15 minutes on AC, 15 minutes on battery)
powercfg -change -standby-timeout-ac 15
powercfg -change -standby-timeout-dc 15
powercfg -change -hibernate-timeout-ac 0
powercfg -change -hibernate-timeout-dc 0

echo Normal sleep behavior restored!
echo Your computer will now sleep after 15 minutes of inactivity.
pause