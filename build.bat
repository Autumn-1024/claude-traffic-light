@echo off
echo Building Claude Traffic Light...
python -m PyInstaller --onefile --windowed --name "ClaudeTrafficLight" main.py
echo.
echo Build complete! Check dist\ClaudeTrafficLight.exe
pause
