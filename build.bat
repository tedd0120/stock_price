@echo off
echo ===================================================
echo Building Stock Ticker...
echo ===================================================

echo.
echo [1/3] Cleaning old build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo [2/3] Running PyInstaller...
python -m PyInstaller --noconfirm --clean ^
    --windowed ^
    --icon "icon.ico" ^
    --add-data "config.json;." ^
    --add-data "icon.png;." ^
    --name "StockTicker" ^
    main.py

echo.
echo Build complete!
echo.
echo ===================================================
echo Done! Executable at: dist\StockTicker\StockTicker.exe
echo ===================================================
pause
