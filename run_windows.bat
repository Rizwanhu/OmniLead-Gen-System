@echo off
echo.
echo Gmail Personalized Sender
echo.
echo 1. Preview
echo 2. Send
echo 3. Gmail auth test
echo.
set /p choice=Choose 1, 2 or 3: 

if "%choice%"=="1" python main.py --preview
if "%choice%"=="2" python main.py --send
if "%choice%"=="3" python main.py --auth-test

pause
